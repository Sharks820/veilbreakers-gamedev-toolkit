# VeilBreakers Terrain Ultra Implementation Plan v1.0

**Document status:** AUTHORITATIVE
**Created:** 2026-04-08
**Branch:** `feature/terrain-world-foundation`
**Base commit:** `71e6451` (Waterfall pipeline overhaul + AAA cave/terrain research)
**Target AAA score:** 8.6 / 10 (currently 3.2)
**Scope:** 17 bundles (A–Q), ~55–60 focused sessions
**Supersedes for gap coverage:** `terrain_claude_master_plan_2026-04-07.md`, `terrain_branch_full_implementation_plan_2026-04-07.md`, `terrain_aaa_implementation_guide.md`, `terrain_tool_bug_audit_2026-04-07.md`
**Complements:** those four earlier docs remain valid for their content; this plan fills the architectural gaps they missed and adds the Ecosystem Spine, Composition, Material Ceiling, and Iteration Velocity bundles they did not cover.

---

## Table of Contents

0. [Meta — How to use this document](#0-meta)
1. [Executive summary](#1-executive-summary)
2. [Current state assessment](#2-current-state-assessment)
3. [Target state definition (8.6 AAA)](#3-target-state-definition)
4. [Architecture overview](#4-architecture-overview)
5. [Core contracts and dataclasses](#5-core-contracts-and-dataclasses)
6. [Bundle A — Foundation (atomic)](#bundle-a--foundation)
7. [Bundle B — Cliffs + slope materials](#bundle-b--cliffs--slope-materials)
8. [Bundle C — Waterfall hydrology chain](#bundle-c--waterfall-hydrology-chain)
9. [Bundle D — Validation + checkpoints](#bundle-d--validation--checkpoints)
10. [Bundle E — Scatter intelligence](#bundle-e--scatter-intelligence)
11. [Bundle F — Cave archetypes](#bundle-f--cave-archetypes)
12. [Bundle G — Banded noise refactor](#bundle-g--banded-noise-refactor)
13. [Bundle H — Composition & intent](#bundle-h--composition--intent)
14. [Bundle I — Geology plausibility](#bundle-i--geology-plausibility)
15. [Bundle J — Ecosystem spine (highest post-foundation ROI)](#bundle-j--ecosystem-spine)
16. [Bundle K — Material ceiling](#bundle-k--material-ceiling)
17. [Bundle L — Atmosphere & horizon](#bundle-l--atmosphere--horizon)
18. [Bundle M — Iteration velocity](#bundle-m--iteration-velocity)
19. [Bundle N — Deep validation & QA](#bundle-n--deep-validation--qa)
20. [Bundle O — Water + vegetation depth](#bundle-o--water--vegetation-depth)
21. [Bundle P — Real-world reference (optional)](#bundle-p--real-world-reference)
22. [Bundle Q — Runtime data export (optional)](#bundle-q--runtime-data-export)
23. [File impact matrix](#23-file-impact-matrix)
24. [Preserve list — existing capabilities to protect](#24-preserve-list)
25. [Dependency graph & file-lock matrix](#25-dependency-graph)
26. [Execution sequence](#26-execution-sequence)
27. [Testing strategy](#27-testing-strategy)
28. [Risk register](#28-risk-register)
29. [Success metrics](#29-success-metrics)
30. [Migration strategy](#30-migration-strategy)
31. [MCP tool surface expansion](#31-mcp-tool-surface-expansion)
32. [Performance budgets](#32-performance-budgets)
33. [Unity export contracts](#33-unity-export-contracts)
34. [Anti-patterns](#34-anti-patterns)
35. [Operational concerns](#35-operational-concerns)
36. [References](#36-references)
37. [Glossary](#37-glossary)
38. [Appendix A — Command handler migration table](#appendix-a)
39. [Appendix B — Preset JSON schemas](#appendix-b)
40. [Appendix C — Test fixture library](#appendix-c)
41. [Appendix D — Bundle compliance checklists](#appendix-d)

---

## 0. Meta

### 0.1 How to use this document

This is the **single source of truth** for terrain pipeline work on the `feature/terrain-world-foundation` branch. A future session (Claude, human, or agent) should be able to pick up execution by reading this document alone.

Workflow for picking up execution:

1. Read Sections 1–5 (frame + contracts) — required context
2. Run `git log 71e6451..HEAD -- Tools/mcp-toolkit/blender_addon/handlers/` to see what has changed since this plan was authored
3. Check Appendix D (compliance checklists) to find the next incomplete bundle
4. Read the matching bundle section (6–22)
5. Read Section 25 (dependency graph) to confirm prerequisites are done
6. Read Section 27 (testing) to understand how to verify
7. Execute the bundle
8. Mark Appendix D checklist complete; commit

**Do not read other terrain docs first.** This document incorporates and extends their content. Cross-reference only if something here points to them.

### 0.2 Related documents (older, partially stale)

- `docs/terrain_claude_master_plan_2026-04-07.md` — architecture prior art, read for D1–D7 module specs
- `docs/terrain_branch_full_implementation_plan_2026-04-07.md` — bug-level plan, partly resolved by Codex
- `docs/terrain_aaa_implementation_guide.md` — AAA patterns, read for sections 219–588
- `docs/terrain_tool_bug_audit_2026-04-07.md` — bug audit, 5 of 17 items already fixed as of 2026-04-08
- `docs/terrain_pipeline_handoff_for_claude.md` — pipeline hand-off notes

### 0.3 Status tracking

Status for every bundle lives in Appendix D. Updates follow this format:

```
Bundle X status: NOT_STARTED | IN_PROGRESS | COMPLETE | BLOCKED
Last touched: <commit sha>
Compliance: N/M items
Next action: <one line>
```

Future sessions update Appendix D in-place when work lands. Never delete checklist items; mark them complete.

### 0.4 Branch context

- Active branch: `feature/terrain-world-foundation`
- Parent branch: `master`
- Parent merge base will be determined at PR time
- Codex has been running concurrent fixes. Before starting any bundle, run `git status` and `git log --oneline -20` to see recent changes

---

## 1. Executive Summary

The VeilBreakers terrain pipeline currently scores **3.2 / 10** against verified AAA open-world productions (Witcher 3 8.3, Horizon Zero Dawn 8.6, Far Cry 5 8.9, Ghost of Tsushima 8.9, Elden Ring 7.9). It is stuck at "noise → erosion → mesh → decorate" when AAA behaves like "composition → structural masks → hero features → erosion → material zoning → asset logic → validation".

The gap is **architectural, not algorithmic**. Every algorithmic primitive VeilBreakers needs (ridged multifractal, domain warping, droplet hydraulic erosion, D8 flow, lake/waterfall detection, Poisson scatter) already exists in the codebase. What is missing is the connective tissue — a semantic mask stack, a pass-based orchestrator, and the consumers that turn masks into cliffs, materials, scatter, audio zones, wildlife volumes, and validation gates.

This plan delivers 17 bundles (A–Q) totaling ~55–60 focused sessions. Bundle A is the atomic foundation (semantic dataclasses + orchestrator + mask stack + erosion output refactor). Bundles B–G cover cliffs, water, validation, scatter, caves, and banded noise. Bundles H–Q close the 7.6 → 8.6 gap via composition/intent authoring, geology plausibility, ecosystem spine, material ceiling, atmosphere/horizon, iteration velocity, and deep validation.

**Realistic ceiling: 8.6 / 10** — squarely in shipped-AAA indie-scope territory, between Witcher 3 and Horizon Zero Dawn. The 8.6 → 9.0+ gap is capped by engine-side needs (Unity GPU compute, virtual texturing, runtime volumetrics) and process needs (reference trips, photogrammetry acquisition, multi-year iteration) that a toolkit cannot close on its own.

**Critical path sentence:** Ship Bundle A atomically, then parallelize B/C/D/E, then dispatch Bundle J (ecosystem spine) as the second-largest ROI after A, then polish with H/K/M, then fill with I/O/L/N/F/G.

---

## 2. Current State Assessment

### 2.1 What exists (algorithmic building blocks)

Module inventory confirmed by file reads and Grep sweeps on 2026-04-08:

- **`_terrain_noise.py` (1585 lines)** — rich backend: fBm with domain warp (`generate_heightmap:366`), ridged multifractal (`ridged_multifractal:1157`), vectorized ridged (`ridged_multifractal_array:1222`), domain warp (`domain_warp:1278`), Voronoi biome distribution (`voronoi_biome_distribution:1368`), `generate_heightmap_ridged:1458`, 8 terrain presets, 8 biome rules, `compute_slope_map:603`, `carve_river_path:794`, alternative hydraulic backend (`hydraulic_erosion:928`).
- **`_terrain_world.py` (291 lines)** — `sample_world_height`, `generate_world_heightmap`, `extract_tile`, `validate_tile_seams`, `erode_world_heightmap`, `world_region_dimensions`. Pure utility, no orchestration.
- **`_terrain_erosion.py` (325 lines)** — droplet hydraulic (`apply_hydraulic_erosion:23-185`), weighted brush erosion (`_erode_brush:201-227`), thermal/talus (`apply_thermal_erosion:234-324`). **Critical flaw: returns only the eroded heightmap clamped to source range. Every intermediate signal (deposition, wetness, talus location, sediment transport) is computed and thrown away.**
- **`_terrain_depth.py` (650 lines)** — mesh geometry generators: `generate_cliff_face_mesh:39-114`, `generate_cave_entrance_mesh:122-227`, `generate_biome_transition_mesh:235-303`, `generate_waterfall_mesh:311-431`, `generate_terrain_bridge_mesh:439-511`, `detect_cliff_edges:519-649`. Wrong focus per plan — should be an analysis brain, currently is a mesh factory.
- **`_water_network.py`** — `WaterNetwork` class with `from_heightmap`, `trace_river_from_flow:119-167`, `detect_lakes:170-249`, `detect_waterfalls:252-333+`, `compute_river_width:86-106`, `WaterSegment` dataclass. Closest module to pass-based design.
- **`terrain_chunking.py` (485+ lines)** — `compute_chunk_lod:31-92`, `compute_streaming_distances:100-124`, `compute_terrain_chunks:132-289`, multi-channel `validate_tile_seams:367+` (upgraded by Codex 2026-04-08).
- **`terrain_materials.py`** — 14 biome specs with dark-fantasy palette rules (saturation ≤40%, value 10–50%), `compute_world_splatmap_weights:2172` (Python loop, not vectorized, no slope/curvature input).
- **`terrain_features.py`** — `generate_canyon`, `generate_waterfall:254` (hardcoded −Y facing), `generate_cliff_face`, `generate_swamp_terrain`, `generate_natural_arch`.
- **`terrain_advanced.py`** — brush edits, `compute_erosion_brush` (has `np.clip(result, 0, 1)` bug still present), `flatten_terrain_zone:1530` (same bug), spline evaluation at 132–160.
- **`environment.py` (500+ lines, uncommitted Codex changes)** — `handle_generate_terrain_tile`, `handle_generate_world_terrain` (Codex just converted to compatibility wrapper), `handle_generate_waterfall` (Codex just wired to `WaterNetwork.from_heightmap`), `_validate_terrain_params:405-449`, VB_BIOME_PRESETS dict at 98–277, `get_vb_biome_preset:374-402`. Collection of independent handlers, no pass controller.
- **`terrain_chunking.py`** — Codex upgraded seam validation to numpy + per-channel 2026-04-08.
- **`visual_validation.py`** — `aaa_verify_map` (Codex fixed empty-screenshot silent-pass 2026-04-08, added `required_angle_count` + `angle_labels`).
- **`viewport.py`** — Codex added real `handle_render_angle:1076` with yaw/pitch camera math 2026-04-08.
- **`pipeline_state.py` (345 lines)** — map-level checkpoints, NOT terrain-specific but ~70% reusable.
- **`_scatter_engine.py` (617 lines)** — Poisson-disk sampler with Bridson (`poisson_disk_sample:26-124`), biome filter (`biome_filter_points:131-264`), context-affinity scatter (`context_scatter:318-399`), PROP_AFFINITY dict.

### 2.2 What Codex fixed between 2026-04-07 and 2026-04-08 (PRESERVE)

These fixes landed in the working tree and must not be regressed:

1. `env_generate_world_terrain` → compatibility wrapper looping `handle_generate_terrain_tile` across tiles (`environment.py:1176-1214`). Previously raised `NotImplementedError`.
2. `aaa_verify_map` fails on empty screenshot list with `{"passed": False, "missing_angles": [...]}` (`visual_validation.py:162`). Previously passed silently.
3. `validate_tile_seams` now numpy-vectorized with per-channel max/mean deltas and channel-shape validation (`terrain_chunking.py:367-473`).
4. `render_angle` is no longer an alias for `handle_get_viewport_screenshot`. `handle_render_angle` in `viewport.py:1076` computes true camera position from yaw/pitch, sets up temp camera + beauty lights, writes real render.
5. `env_generate_waterfall` now drives `WaterNetwork.from_heightmap` to derive waterfall drop/width from hydrology (`environment.py:1218-1280`). Legacy mesh path remains as warning fallback.
6. `aaa_verify_map` signature now accepts `required_angle_count` and `angle_labels` kwargs and surfaces missing angles.
7. `blender_scene` MCP tool has new `save_project` + `verify_project_save` actions (`blender_server.py:1206-1263`) with corresponding `handle_save_project` + `handle_verify_project_save` in `scene.py` (+198 lines).

**These 7 items are the preserve list.** Every test written in this plan must keep passing them.

### 2.3 What is still broken (plan-level)

Architectural gaps from the plan-vs-code audit:

1. **No semantic dataclasses exist.** Grep across entire `handlers/` directory returns zero hits for `TerrainIntentState`, `TerrainSceneRead`, `HeroFeatureSpec`, `WaterSystemSpec`, `ProtectedZoneSpec`, `TerrainMaskStack`.
2. **No pass orchestrator exists.** Grep for `run_pass`, `PassController`, `TerrainPassController` — zero hits.
3. **Erosion throws away every intermediate signal** (see 2.1).
4. **Materials are biome-name-based**, not slope/altitude/curvature/flow driven. `compute_world_splatmap_weights` is a Python per-cell loop.
5. **No cliff anatomy.** `generate_cliff_face_mesh` is one curved plane with noise. No lip/face/ledge/talus/material separation.
6. **Cliff parenting transform order bug** (`environment.py:820-827`) — location set before parenting causes offset cliffs on non-origin tiles.
7. **Cliff height double-scale bug** (`_terrain_depth.py:637` × `environment.py:821`) — `cliff_height = max(height_range * max(terrain_width, terrain_height) * 0.1, 2.0)` then Z scaled again.
8. **`np.clip(result, 0, 1)` still present** in `compute_erosion_brush` (`terrain_advanced.py:896`) and `flatten_terrain_zone` (`terrain_advanced.py:1530`) — silently crushes world-unit heights.
9. **Waterfall legacy fallback hardcoded to −Y facing** (`terrain_features.py:254`).
10. **No cave archetypes.** One generic semicircular arch at `_terrain_depth.py:122-227`.
11. **No visual-semantic verification.** `aaa_verify_map` is image statistics (brightness/contrast/edges/entropy/color), does not validate cliff silhouette, waterfall chain, cave framing.
12. **No scene-understanding step** required before edits. Protocol exists as doc (`.claude/skills/vb-mcp-tools/TERRAIN_EDITING_PROTOCOL.md`), no runtime enforcement.
13. **No named anchors** (WF_LIP_TARGET, CLIFF_HERO_A, etc.) read by handlers.
14. **No ecosystem integration** — zero generation of audio zones, wildlife spawn volumes, gameplay volumes, wind fields, cloud shadows, navmesh data, decal placement from masks.
15. **No composition/intent layer** — zero camera saliency, morphology library, framing, rhythm, hierarchy, negative-space authoring.
16. **No geology plausibility validators** — no stratigraphic layering, strata orientation consistency, Strahler ordering, glacial carving, wind erosion, coastal erosion, karst hydrology.
17. **No iteration velocity infrastructure** — no dirty flags, mask caching, sub-tile editing, live preview, visual diff, parallel pass execution, hot-reload rules.
18. **No deterministic-build CI regression**.
19. **No 5-band readability scoring**, golden snapshots, hero-feature budgets, or iteration telemetry.
20. **Scatter is building-affinity only** (`_scatter_engine.py:318`), not terrain-mask-driven. No viability scoring, no ecotone competition, no exclusion masks, no role classification, no clustering for cliff rocks / waterfall pools / cave debris.

### 2.4 Architectural diagnosis (one sentence)

> The pipeline computes every signal AAA terrain needs (slope, curvature, flow, deposition, wetness, cliff candidates, waterfall candidates, lake basins) and then discards them by clamping the heightmap to `[0,1]` or returning only an `np.ndarray`. The plan's entire goal is to **preserve those signals in a versioned `TerrainMaskStack` consumed by downstream passes** that produce cliffs, materials, scatter, audio, wildlife, and validation gates.

---

## 3. Target State Definition

### 3.1 Numeric score target

**8.6 / 10 AAA** — between Witcher 3 (8.3) and Horizon Zero Dawn (8.6). Target pillar scores:

| Pillar | Current | A–G target | A–Q target |
|---|---|---|---|
| Heightmap authoring | 3 | 7 | 8 |
| Tile streaming & seams | 5 | 8 | 8 |
| Erosion signal pipeline | 2 | 8 | 9 |
| Materials / shading | 3 | 8 | 9 |
| Water networks | 6 | 8 | 9 |
| Procedural scatter | 2 | 7 | 9 |
| Hero features & framing | 4 | 7 | 9 |
| Visual QA & determinism | 3 | 7 | 9 |
| Autonomy / pass discipline | 2 | 8 | 9 |
| Cliff anatomy | 2 | 8 | 9 |
| Cave anatomy | 2 | 7 | 8 |
| Waterfall hydrology chain | 4 | 8 | 9 |
| Ecosystem integration | 1 | 3 | 9 |
| Atmosphere & horizon | 2 | 4 | 8 |
| Composition & intent | 2 | 5 | 9 |
| Geology plausibility | 2 | 6 | 9 |
| Iteration velocity | 2 | 6 | 9 |
| Validation depth | 2 | 7 | 9 |
| **Average** | **2.7** | **6.8** | **8.7** |

### 3.2 Definition of done — the branch is "AAA-ready" when:

1. **Terrain reads as 3–5 strong landform families from any camera position.** Validated by `terrain_readability_bands.py` at 1km / 500m / 100m / 20m / 2m distance bands.
2. **Cliffs have lip + face + ledges + talus + material separation** and survive the `validate_cliff_readability` gate.
3. **Every waterfall has source → lip → drop → pool → outflow hydrology chain** and survives `validate_waterfall_system` with `source_z > lip_z > pool_z`, pool radius ≥ min, outflow exists.
4. **Cave entrances have archetype + framing + debris + damp mask** and survive `validate_cave_entrance`.
5. **First-pass materials already look believable** — slope/altitude/curvature/flow driven, triplanar on cliffs, wetness modulates roughness, macro color grading applied.
6. **Scatter placement is context-aware** — cliffs cluster rocks, waterfall bases cluster boulders, cave mouths cluster debris, forest edges thin out, quiet zones stay quiet.
7. **Every edit is checkpointed and reversible** via `terrain_checkpoints.py`.
8. **Claude can make targeted corrections without re-breaking the scene** via scoped correction format + scene understanding requirement.
9. **Quiet terrain exists alongside detail** — validated by negative-space ratio check.
10. **Hero features are intentional and sparse** — validated by `terrain_hierarchy.py` budget enforcer.
11. **Bit-identical regeneration from seed** — validated by `terrain_determinism_ci.py`.
12. **Ecosystem data exported alongside terrain** — audio zones, wildlife volumes, gameplay zones, wind field, navmesh source, decal placements all present.
13. **Iteration velocity ≥ 5x current** — dirty flags + cached masks + parallel passes deliver this.
14. **All 7 preserve-list items still pass their tests** (Section 2.2).

### 3.3 Out of scope (the 8.6 → 9.0+ cap)

Not attempting in this plan:

- Unity GPU compute terrain rendering
- Adaptive virtual texturing at 10 texels/cm
- Per-blade GPU grass
- Runtime volumetric fog sim
- Real-world location reference trips
- Multi-year polish iteration

These require engine-side work, photogrammetry acquisition budgets, or production time that this plan cannot deliver. They are documented in `docs/terrain_pipeline_handoff_for_claude.md` as future milestones.

---

## 4. Architecture Overview

### 4.1 Pass pipeline (required ordering)

```
                    +-------------------------------+
                    |  TerrainIntentState (input)   |
                    |  - seed                       |
                    |  - region_bounds              |
                    |  - anchors[]                  |
                    |  - protected_zones[]          |
                    |  - hero_feature_specs[]       |
                    |  - water_system_spec          |
                    |  - quality_profile            |
                    +---------------+---------------+
                                    |
                                    v
           +------------------------+------------------------+
           |                                                 |
           |  Pass 1: macro_world                            |
           |  inputs:  intent                                |
           |  outputs: height_macro, continental mask        |
           |                                                 |
           +------------------------+------------------------+
                                    |
                                    v
           +------------------------+------------------------+
           |                                                 |
           |  Pass 2: structural_masks                       |
           |  inputs:  height_macro                          |
           |  outputs: slope, curvature, concavity,          |
           |           ridge, basin, saliency_macro          |
           |                                                 |
           +------------------------+------------------------+
                                    |
                                    v
           +------------------------+------------------------+
           |                                                 |
           |  Pass 3: hero_features                          |
           |  inputs:  masks, intent.hero_feature_specs[]    |
           |  outputs: cliff_candidates, cave_candidates,    |
           |           waterfall_lip_candidates,             |
           |           hero_exclusion_zones                  |
           |                                                 |
           +------------------------+------------------------+
                                    |
                                    v
           +------------------------+------------------------+
           |                                                 |
           |  Pass 4: erosion                                |
           |  inputs:  height + hero_exclusion_zones         |
           |  outputs: height_eroded, erosion_map,           |
           |           deposition_map, wetness, talus,       |
           |           drainage, bank_instability            |
           |                                                 |
           +------------------------+------------------------+
                                    |
                                    v
           +------------------------+------------------------+
           |                                                 |
           |  Pass 5: water_network                          |
           |  inputs:  height_eroded, drainage, wetness      |
           |  outputs: rivers[], lakes[], waterfalls[],      |
           |           water_surface_mask, foam_mask,        |
           |           mist_mask, wet_rock_mask              |
           |                                                 |
           +------------------------+------------------------+
                                    |
                                    v
           +------------------------+------------------------+
           |                                                 |
           |  Pass 6: structural_geometry                    |
           |  inputs:  masks, candidates, hero_specs         |
           |  outputs: cliff meshes (lip/face/ledge/talus),  |
           |           cave archetypes + framing,            |
           |           waterfall chain geometry              |
           |                                                 |
           +------------------------+------------------------+
                                    |
                                    v
           +------------------------+------------------------+
           |                                                 |
           |  Pass 7: material_zoning                        |
           |  inputs:  all masks + geometry                  |
           |  outputs: splatmap (slope/altitude/flow),       |
           |           triplanar cliff assignment,           |
           |           wetness roughness variation,          |
           |           macro color grading                   |
           |                                                 |
           +------------------------+------------------------+
                                    |
                                    v
           +------------------------+------------------------+
           |                                                 |
           |  Pass 8: asset_population                       |
           |  inputs:  all masks + geometry + rules          |
           |  outputs: cliff_rocks[], waterfall_boulders[],  |
           |           cave_debris[], vegetation[],          |
           |           prop_scatter[], hero_prop_anchors[]   |
           |                                                 |
           +------------------------+------------------------+
                                    |
                                    v
           +------------------------+------------------------+
           |                                                 |
           |  Pass 9: ecosystem_spine                        |
           |  inputs:  all masks + geometry + population     |
           |  outputs: audio_zones, wildlife_zones,          |
           |           gameplay_zones, wind_field,           |
           |           cloud_shadow_field, navmesh_source,   |
           |           decal_placements, ecotone_graph       |
           |                                                 |
           +------------------------+------------------------+
                                    |
                                    v
           +------------------------+------------------------+
           |                                                 |
           |  Pass 10: validation                            |
           |  inputs:  everything above                      |
           |  outputs: PassResult(pass=True/False,           |
           |           issues=[], warnings=[], metrics={})   |
           |                                                 |
           +------------------------+------------------------+
                                    |
                           pass? ---+--- fail?
                             |           |
                             v           v
                      checkpoint     rollback
                        save         to last OK
```

### 4.2 Data flow

Every pass reads a `TerrainPipelineState` object and returns a `PassResult`. The `TerrainPipelineState` carries:

- `intent: TerrainIntentState` — immutable after Pass 0 (intent capture)
- `masks: TerrainMaskStack` — mutable, accumulates channels through the pipeline
- `geometry: TerrainGeometryRegistry` — mutable, accumulates Blender objects
- `meta: PassExecutionMeta` — timings, checkpoints, seeds, hashes
- `features: FeatureRegistry` — hero features by role, anchors, protected zones

Later passes consume earlier passes' outputs via the `masks` and `features` fields. **No pass may mutate a mask channel another pass owns.** Writers are explicit; readers are unbounded.

### 4.3 Core principles

1. **Signals are preserved, not discarded.** Every intermediate computation goes into the mask stack and lives until the pipeline completes.
2. **Passes are idempotent under fixed seeds.** Re-running a pass with the same inputs produces bit-identical outputs.
3. **Passes are region-scoped.** Every pass accepts a `region: Optional[BBox]` parameter so sub-tile edits don't recompute the whole world.
4. **Hero features come BEFORE erosion.** Erosion must honor hero exclusion zones so handcrafted landmarks don't dissolve.
5. **Validation is a hard gate.** Failed validation triggers rollback, not warnings.
6. **No edit without scene understanding.** The orchestrator rejects mutation requests that don't carry a `TerrainSceneRead` summary.
7. **Anchors beat guesses.** When a named anchor is available, handlers prefer it over computed positions.
8. **The mask stack is the contract.** Every pass writes its outputs to named channels; the schema is versioned.

---

## 5. Core Contracts and Dataclasses

This section specifies every shared type that Bundle A must deliver. These signatures are binding — changes require a plan revision.

### 5.1 `TerrainMaskStack`

File: `Tools/mcp-toolkit/blender_addon/handlers/terrain_semantics.py`

```python
@dataclass
class TerrainMaskStack:
    """Unified mask registry. Every signal the pipeline computes lives here."""

    # Shape and coordinate contract
    tile_size: int                          # cells per tile edge
    cell_size: float                        # world meters per cell
    world_origin_x: float
    world_origin_y: float
    tile_x: int
    tile_y: int

    # Core height channel (always present)
    height: np.ndarray                      # (H, W) float64, world units

    # Structural masks (Pass 2 fills these)
    slope: Optional[np.ndarray] = None          # (H, W) float64, radians
    curvature: Optional[np.ndarray] = None      # (H, W) float64, signed
    concavity: Optional[np.ndarray] = None      # (H, W) float64, 0..1
    convexity: Optional[np.ndarray] = None      # (H, W) float64, 0..1
    ridge: Optional[np.ndarray] = None          # (H, W) bool
    basin: Optional[np.ndarray] = None          # (H, W) int (basin id)
    saliency_macro: Optional[np.ndarray] = None # (H, W) float64, 0..1

    # Hero candidate masks (Pass 3 fills these)
    cliff_candidate: Optional[np.ndarray] = None    # (H, W) bool
    cave_candidate: Optional[np.ndarray] = None     # (H, W) bool
    waterfall_lip_candidate: Optional[np.ndarray] = None  # (H, W) bool
    hero_exclusion: Optional[np.ndarray] = None     # (H, W) bool

    # Erosion-derived masks (Pass 4 fills these)
    erosion_amount: Optional[np.ndarray] = None     # (H, W) float64
    deposition_amount: Optional[np.ndarray] = None  # (H, W) float64
    wetness: Optional[np.ndarray] = None            # (H, W) float64, 0..1
    talus: Optional[np.ndarray] = None              # (H, W) float64
    drainage: Optional[np.ndarray] = None           # (H, W) float64 (log accum)
    bank_instability: Optional[np.ndarray] = None   # (H, W) float64

    # Water masks (Pass 5 fills these)
    flow_direction: Optional[np.ndarray] = None     # (H, W) int (D8 code)
    flow_accumulation: Optional[np.ndarray] = None  # (H, W) float64
    water_surface: Optional[np.ndarray] = None      # (H, W) bool
    foam: Optional[np.ndarray] = None               # (H, W) float64, 0..1
    mist: Optional[np.ndarray] = None               # (H, W) float64, 0..1
    wet_rock: Optional[np.ndarray] = None           # (H, W) float64, 0..1
    tidal: Optional[np.ndarray] = None              # (H, W) float64, -1..1

    # Material-zoning masks (Pass 7 fills these)
    biome_id: Optional[np.ndarray] = None           # (H, W) int
    material_weights: Optional[np.ndarray] = None   # (H, W, C) float32
    roughness_variation: Optional[np.ndarray] = None  # (H, W) float32
    macro_color: Optional[np.ndarray] = None        # (H, W, 3) float32

    # Ecosystem masks (Pass 9 fills these)
    audio_reverb_class: Optional[np.ndarray] = None # (H, W) int
    wildlife_affinity: Optional[Dict[str, np.ndarray]] = None  # species -> mask
    gameplay_zone: Optional[np.ndarray] = None      # (H, W) int enum
    wind_field: Optional[np.ndarray] = None         # (H, W, 2) float32
    cloud_shadow: Optional[np.ndarray] = None       # (H, W) float32
    traversability: Optional[np.ndarray] = None     # (H, W) float32
    decal_density: Optional[Dict[str, np.ndarray]] = None

    # Geology plausibility (Bundle I fills these)
    strata_orientation: Optional[np.ndarray] = None # (H, W, 3) float32
    rock_hardness: Optional[np.ndarray] = None      # (H, W) float32
    snow_line_factor: Optional[np.ndarray] = None   # (H, W) float32

    # Versioning
    schema_version: str = "1.0"
    content_hash: Optional[str] = None              # set by `compute_hash()`
    dirty_channels: Set[str] = field(default_factory=set)
    populated_by_pass: Dict[str, str] = field(default_factory=dict)

    def get(self, channel: str) -> Optional[np.ndarray]: ...
    def set(self, channel: str, value: np.ndarray, pass_name: str) -> None: ...
    def mark_dirty(self, channel: str) -> None: ...
    def mark_clean(self, channel: str) -> None: ...
    def compute_hash(self) -> str: ...
    def to_npz(self, path: Path) -> None: ...
    @classmethod
    def from_npz(cls, path: Path) -> "TerrainMaskStack": ...
    def assert_channels_present(self, channels: List[str]) -> None: ...
```

### 5.2 `TerrainIntentState`

```python
@dataclass(frozen=True)
class TerrainIntentState:
    """Immutable authoring intent captured before any mutation."""

    seed: int
    region_bounds: BBox
    tile_size: int
    cell_size: float

    # Authoring inputs
    anchors: Tuple[TerrainAnchor, ...] = ()
    protected_zones: Tuple[ProtectedZoneSpec, ...] = ()
    hero_feature_specs: Tuple[HeroFeatureSpec, ...] = ()
    water_system_spec: Optional[WaterSystemSpec] = None
    quality_profile: str = "production"   # preview|production|hero_shot|aaa_open_world
    biome_rules: Optional[str] = None     # key into BIOME_RULES registry

    # Scene understanding (required before mutation)
    scene_read: Optional["TerrainSceneRead"] = None

    # Optional authoring hints
    morphology_templates: Tuple[str, ...] = ()
    noise_profile: str = "dark_fantasy_default"
    erosion_profile: str = "temperate"
    composition_hints: Dict[str, Any] = field(default_factory=dict)
```

### 5.3 `TerrainSceneRead`

Required output of the scene-understanding step before any edit. Orchestrator rejects mutation requests lacking this.

```python
@dataclass(frozen=True)
class TerrainSceneRead:
    """Structured understanding of current scene state, required pre-edit."""

    timestamp: float
    major_landforms: Tuple[str, ...]            # "ridge_system", "canyon", etc.
    focal_point: Tuple[float, float, float]     # world coords
    hero_features_present: Tuple[HeroFeatureRef, ...]
    hero_features_missing: Tuple[str, ...]
    waterfall_chains: Tuple[WaterfallChainRef, ...]
    cave_candidates: Tuple[Tuple[float, float, float], ...]
    protected_zones_in_region: Tuple[str, ...]
    edit_scope: BBox
    success_criteria: Tuple[str, ...]           # pass/fail statements
    reviewer: str                               # "claude-opus-4-6" etc.
```

### 5.4 `HeroFeatureSpec`

```python
@dataclass(frozen=True)
class HeroFeatureSpec:
    feature_id: str                      # "Hero_Cliff_A", "WF_Main", etc.
    feature_kind: str                    # cliff|cave|waterfall|arch|canyon|...
    world_position: Tuple[float, float, float]
    orientation: Tuple[float, float, float]  # euler radians
    bounds: BBox
    anchor_name: Optional[str] = None    # ties to a TerrainAnchor empty
    tier: str = "secondary"              # primary|secondary|tertiary|ambient
    silhouette_vantages: Tuple[Tuple[float, float, float], ...] = ()
    exclusion_radius: float = 0.0
    budget: Optional["HeroFeatureBudget"] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
```

### 5.5 `WaterSystemSpec`

```python
@dataclass(frozen=True)
class WaterSystemSpec:
    network_seed: int
    min_drainage_area: float = 500.0
    river_threshold: float = 2000.0
    lake_min_area: float = 100.0
    meander_amplitude: float = 0.0       # 0=straight, 1=max meander
    bank_asymmetry: float = 0.0          # -1..1
    tidal_range: float = 0.0             # meters
    hero_waterfalls: Tuple[str, ...] = ()  # feature_ids

    # Advanced water (Bundle O)
    braided_channels: bool = False
    estuaries: bool = False
    karst_springs: bool = False
    perched_lakes: bool = False
    hot_springs: bool = False
    wetlands: bool = False
    seasonal_state: str = "normal"       # dry|normal|wet|frozen
```

### 5.6 `ProtectedZoneSpec`

```python
@dataclass(frozen=True)
class ProtectedZoneSpec:
    zone_id: str
    bounds: BBox
    kind: str                  # "hero_mesh", "quest_location", "no_erosion", etc.
    allowed_mutations: FrozenSet[str]  # e.g. {"material_zoning", "scatter"}
    forbidden_mutations: FrozenSet[str]  # e.g. {"erosion", "macro_world"}
    description: str = ""
```

### 5.7 `TerrainAnchor`

```python
@dataclass(frozen=True)
class TerrainAnchor:
    name: str                            # "WF_LIP_TARGET", "CLIFF_HERO_A", etc.
    world_position: Tuple[float, float, float]
    orientation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    anchor_kind: str = "generic"         # generic|waterfall_lip|waterfall_pool|cliff_hero|cave_entrance|focal
    radius: float = 0.0
    blender_object_name: Optional[str] = None
```

### 5.8 `PassResult`

```python
@dataclass
class PassResult:
    pass_name: str
    status: str                          # "ok" | "warning" | "failed"
    duration_seconds: float
    produced_channels: Tuple[str, ...]
    consumed_channels: Tuple[str, ...]
    metrics: Dict[str, Any]
    issues: List["ValidationIssue"]
    warnings: List["ValidationIssue"]
    side_effects: List[str]              # blender object names added/modified
    seed_used: int
    content_hash_before: Optional[str]
    content_hash_after: Optional[str]
    checkpoint_path: Optional[str] = None
```

### 5.9 `ValidationIssue`

```python
@dataclass
class ValidationIssue:
    code: str                            # e.g. "CLIFF_NO_LIP"
    severity: str                        # "hard" | "soft" | "info"
    location: Optional[Tuple[float, float, float]]
    affected_feature: Optional[str]
    message: str
    remediation: Optional[str]
```

### 5.10 `TerrainPassController`

File: `Tools/mcp-toolkit/blender_addon/handlers/terrain_pipeline.py`

```python
class TerrainPassController:
    """Central pass orchestrator. All terrain mutations route through here."""

    PASS_REGISTRY: Dict[str, PassDefinition] = {}

    def __init__(self, state: TerrainPipelineState) -> None: ...

    @classmethod
    def register_pass(cls, definition: PassDefinition) -> None: ...

    def run_pass(
        self,
        pass_name: str,
        region: Optional[BBox] = None,
        *,
        force: bool = False,
        checkpoint: bool = True,
    ) -> PassResult: ...

    def run_pipeline(
        self,
        intent: TerrainIntentState,
        pass_sequence: Optional[List[str]] = None,
    ) -> List[PassResult]: ...

    def rollback_to(self, checkpoint_id: str) -> None: ...

    def require_scene_read(self, operation: str) -> None: ...

    def enforce_protected_zones(
        self,
        pass_name: str,
        target_bounds: BBox,
    ) -> None: ...
```

### 5.11 `PassDefinition`

```python
@dataclass
class PassDefinition:
    name: str
    func: Callable[[TerrainPipelineState, Optional[BBox]], PassResult]
    requires_channels: Tuple[str, ...]
    produces_channels: Tuple[str, ...]
    requires_features: Tuple[str, ...] = ()
    idempotent: bool = True
    deterministic: bool = True
    may_modify_geometry: bool = False
    may_add_geometry: bool = False
    respects_protected_zones: bool = True
    supports_region_scope: bool = True
    seed_namespace: str = ""             # for deterministic seed derivation
```

### 5.12 Determinism seed derivation

Every pass derives its working seed from:

```python
pass_seed = hash((
    intent.seed,
    definition.seed_namespace,
    tile_x,
    tile_y,
    region.to_tuple() if region else None,
)) & 0xFFFFFFFF
```

This guarantees:
- Re-running a pass on the same tile with the same intent produces the same result
- Different tiles produce independent results
- Different passes on the same tile produce independent results
- Region-scoped edits do not perturb unaffected regions

### 5.13 Checkpoint contract

Every successful pass emits a checkpoint containing:

```python
@dataclass
class TerrainCheckpoint:
    checkpoint_id: str
    pass_name: str
    timestamp: float
    intent_hash: str
    mask_stack_path: Path                # .npz file
    geometry_snapshot_path: Path         # .blend file
    content_hash: str
    parent_checkpoint_id: Optional[str]
    metrics: Dict[str, Any]
```

Rollback restores mask_stack and geometry_snapshot atomically.

---

## 6. Bundle A — Foundation

**Goal:** Ship the atomic architectural foundation that every later bundle depends on. After Bundle A, a minimal pipeline (macro → structural_masks → erosion → validation) runs end-to-end on a test region and the `TerrainMaskStack` has the expected channels populated at each pass.

**Estimated sessions:** 4–5
**Score impact:** 3.2 → 5.5 (unlocks all subsequent bundles)
**Parallel-safe:** No. Atomic.
**Prerequisites:** None.

### 6.1 Modules delivered

| Module | Path | Purpose |
|---|---|---|
| `terrain_semantics.py` | `Tools/mcp-toolkit/blender_addon/handlers/terrain_semantics.py` | All dataclasses from §5 |
| `terrain_masks.py` | `Tools/mcp-toolkit/blender_addon/handlers/terrain_masks.py` | `compute_base_masks`, `compute_structural_masks`, mask utility functions |
| `terrain_pipeline.py` | `Tools/mcp-toolkit/blender_addon/handlers/terrain_pipeline.py` | `TerrainPassController`, `PassDefinition`, pass registry, determinism helpers |
| `_terrain_world.py` (refactor) | existing | Split into 7 pass functions matching the orchestrator registry |
| `_terrain_erosion.py` (refactor) | existing | Return `(height, ErosionMasks)` populating mask stack |
| `environment.py` (thin wrapper) | existing | `handle_run_terrain_pass` routes to `TerrainPassController` |
| `test_terrain_pipeline_smoke.py` | `Tools/mcp-toolkit/tests/test_terrain_pipeline_smoke.py` | End-to-end smoke test |

### 6.2 Key function signatures

```python
# terrain_masks.py
def compute_base_masks(
    height: np.ndarray,
    cell_size: float,
    tile_coords: Tuple[int, int],
    *,
    stack: Optional[TerrainMaskStack] = None,
) -> TerrainMaskStack:
    """Compute slope, curvature, concavity, convexity, ridge, basin, saliency_macro."""

def compute_slope(height: np.ndarray, cell_size: float) -> np.ndarray: ...
def compute_curvature(height: np.ndarray, cell_size: float) -> np.ndarray: ...
def compute_concavity(curvature: np.ndarray) -> np.ndarray: ...
def compute_convexity(curvature: np.ndarray) -> np.ndarray: ...
def extract_ridge_mask(height: np.ndarray, cell_size: float) -> np.ndarray: ...
def detect_basins(height: np.ndarray, min_area: int = 50) -> np.ndarray: ...
def compute_macro_saliency(
    height: np.ndarray,
    curvature: np.ndarray,
    ridge: np.ndarray,
) -> np.ndarray: ...

# terrain_pipeline.py
def run_pass(
    state: TerrainPipelineState,
    pass_name: str,
    region: Optional[BBox] = None,
    *,
    force: bool = False,
    checkpoint: bool = True,
) -> PassResult: ...

def derive_pass_seed(
    intent_seed: int,
    seed_namespace: str,
    tile_x: int,
    tile_y: int,
    region: Optional[BBox],
) -> int: ...

# _terrain_world.py (refactored)
def pass_macro_world(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult: ...

def pass_structural_masks(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult: ...

def pass_erosion(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult: ...

def pass_validation_minimal(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult: ...
```

### 6.3 `_terrain_erosion.py` refactor specifics

Change `apply_hydraulic_erosion` return type from `np.ndarray` to:

```python
@dataclass
class ErosionMasks:
    height: np.ndarray
    erosion_amount: np.ndarray      # per-cell material removed
    deposition_amount: np.ndarray   # per-cell material added
    wetness: np.ndarray             # sum of droplet water * time
    drainage: np.ndarray            # log1p(droplet count per cell)
    bank_instability: np.ndarray    # curvature of wet cells
```

Populate `erosion_amount` and `deposition_amount` by accumulating `h_diff` per cell in the droplet loop. Populate `wetness` from droplet residence time. Populate `drainage` from droplet pass-through count. Do NOT clip the final heightmap to `[0, 1]` — return world-unit heights.

Same refactor for `apply_thermal_erosion`: add `talus` channel populated from accumulated material moved by thermal weathering.

### 6.4 Consumed / produced masks

| Pass | Consumes | Produces |
|---|---|---|
| `macro_world` | (intent only) | `height` |
| `structural_masks` | `height` | `slope`, `curvature`, `concavity`, `convexity`, `ridge`, `basin`, `saliency_macro` |
| `erosion` | `height`, `hero_exclusion` (optional) | `height_eroded`, `erosion_amount`, `deposition_amount`, `wetness`, `drainage`, `bank_instability`, `talus` |
| `validation_minimal` | all of above | (none; emits `PassResult`) |

### 6.5 Tests required

`test_terrain_pipeline_smoke.py` must cover:

1. **End-to-end pipeline runs** — instantiate `TerrainPassController`, run `macro_world → structural_masks → erosion → validation_minimal`, assert all stages return `status="ok"`
2. **Mask stack channels populated** — after each pass, assert expected channels are present and dtype/shape correct
3. **Determinism** — run the same pipeline twice with the same seed, assert mask stack content hashes match bit-identically
4. **Region scoping** — run `erosion` with a 100m×100m region, assert only cells in that region change
5. **Protected zones** — run `erosion` with a protected zone covering the center 50%, assert center cells unchanged
6. **Scene-read enforcement** — attempt to run a pass without `intent.scene_read`, assert orchestrator raises `SceneReadRequired`
7. **Checkpoint create/rollback** — run 3 passes, checkpoint after each, rollback to pass 2, assert state matches pass 2 exactly
8. **Preserve-list regression** — assert Codex's 7 preserve-list items still pass:
   - `env_generate_world_terrain` returns compatibility result
   - `aaa_verify_map([], required_angle_count=6)` returns `passed=False`
   - `validate_tile_seams` with 3D array returns per-channel deltas
   - `render_angle` with yaw=90 produces a camera position 90° around target
   - `env_generate_waterfall` with heightmap uses `WaterNetwork`
   - `blender_scene action=save_project` dispatches correctly
   - `handle_save_project` is importable from `scene.py`

### 6.6 Acceptance criteria

- [ ] `terrain_semantics.py` exports all 10 dataclasses from §5
- [ ] `terrain_pipeline.py` `TerrainPassController` registers 4 initial passes
- [ ] `terrain_masks.py` implements all 8 mask compute functions
- [ ] `_terrain_erosion.py` returns `ErosionMasks` not `np.ndarray`
- [ ] `_terrain_erosion.py` no longer clips output to `[0,1]` anywhere
- [ ] `_terrain_world.py` exposes 4 pass functions with matching signatures
- [ ] `environment.py` has `handle_run_terrain_pass` delegating to controller
- [ ] Every pytest in `test_terrain_pipeline_smoke.py` passes
- [ ] Every preserve-list test still passes
- [ ] `pytest Tools/mcp-toolkit/tests/` passes with no new failures vs baseline

### 6.7 Risks and mitigations

| Risk | Mitigation |
|---|---|
| Refactor breaks existing handlers | Keep `handle_generate_terrain_tile` as a thin wrapper that builds a minimal `TerrainIntentState` and calls the new pipeline |
| Dataclass redesign mid-bundle | Dataclasses frozen by §5 — any change requires plan revision |
| Determinism accidentally broken by numpy operation order | Smoke test #3 catches this; add `np.random.default_rng(seed)` at every entry point |
| Protected zones not respected by erosion droplet sim | Pass `hero_exclusion` mask into droplet loop; skip cells marked excluded |
| Scope creep into other bundles | Bundle A ships ONLY the 4 initial passes. Cliffs/materials/water/scatter belong to B/C/D/E |

### 6.8 File-lock matrix (bundle-internal)

| File | Writer |
|---|---|
| `terrain_semantics.py` | Bundle A (creates) |
| `terrain_masks.py` | Bundle A (creates) |
| `terrain_pipeline.py` | Bundle A (creates) |
| `_terrain_world.py` | Bundle A (refactors) |
| `_terrain_erosion.py` | Bundle A (refactors) |
| `environment.py` | Bundle A (adds `handle_run_terrain_pass` only) |
| `terrain_chunking.py` | Do NOT touch — preserve Codex fix |
| `visual_validation.py` | Do NOT touch — preserve Codex fix |
| `viewport.py` | Do NOT touch — preserve Codex fix |

---

## 7. Bundle B — Cliffs + Slope Materials

**Goal:** Replace the fake-cliff system with true cliff anatomy (lip + face + ledges + talus + material separation). Replace biome-name materials with slope/altitude/curvature/flow-driven materials with triplanar on cliffs.

**Estimated sessions:** 3
**Score impact:** +1.0 (most visible single improvement)
**Parallel-safe with:** C, D, E (different files)
**Prerequisites:** Bundle A

### 7.1 Modules delivered

| Module | Path | Purpose |
|---|---|---|
| `terrain_cliffs.py` | `handlers/terrain_cliffs.py` | `build_cliff_candidate_mask`, `carve_cliff_system`, `add_cliff_ledges`, `build_talus_field`, `insert_hero_cliff_meshes`, `validate_cliff_readability` |
| `terrain_materials.py` (rewrite) | `handlers/terrain_materials.py` | Vectorized slope/altitude/curvature/flow-driven `compute_world_splatmap_weights`, triplanar cliff recipe |
| `_terrain_depth.py` (bug fixes) | `handlers/_terrain_depth.py` | Fix cliff height double-scale bug |
| `environment.py` (bug fixes) | `handlers/environment.py` | Fix cliff parenting transform order |
| `terrain_advanced.py` (bug fixes) | `handlers/terrain_advanced.py` | Remove `np.clip(result, 0, 1)` from `compute_erosion_brush` and `flatten_terrain_zone` |

### 7.2 Cliff anatomy requirements

A `cliff` is no longer "steep terrain". A cliff is a registered structure with:

1. **Lip** — upper edge, sharp geometry break. Exported as a polyline + mesh strip.
2. **Face** — vertical-to-steep wall with displacement noise, triplanar material, stratigraphic layering.
3. **Ledges** — 1–3 horizontal interruptions, height-proportional frequency.
4. **Base / talus** — angular scree field at angle-of-repose (~34°), material blend from rock to detritus.
5. **Material separation** — cliff face uses `cliff` material, top uses `ground` material, base uses `scree` material. Boundaries match geometry edges.

### 7.3 Key function signatures

```python
# terrain_cliffs.py
def build_cliff_candidate_mask(
    stack: TerrainMaskStack,
    *,
    slope_threshold: float = math.radians(55),
    ridge_weight: float = 0.5,
    min_cluster_size: int = 20,
) -> np.ndarray: ...

def carve_cliff_system(
    state: TerrainPipelineState,
    candidate_mask: np.ndarray,
    *,
    lip_sharpness: float = 1.0,
    face_roughness: float = 0.4,
    max_cliff_count: int = 20,
) -> List[CliffStructure]: ...

def add_cliff_ledges(
    cliff: CliffStructure,
    *,
    ledge_count_range: Tuple[int, int] = (1, 3),
    ledge_depth_range: Tuple[float, float] = (0.5, 2.0),
) -> CliffStructure: ...

def build_talus_field(
    cliff: CliffStructure,
    stack: TerrainMaskStack,
    *,
    angle_of_repose: float = math.radians(34),
    talus_density: float = 1.0,
) -> TalusField: ...

def insert_hero_cliff_meshes(
    cliffs: List[CliffStructure],
    hero_specs: Sequence[HeroFeatureSpec],
) -> List[str]: ...   # returns blender object names

def validate_cliff_readability(
    cliffs: List[CliffStructure],
    stack: TerrainMaskStack,
    *,
    min_lip_sharpness: float = 0.5,
    min_silhouette_clarity: float = 0.4,
) -> List[ValidationIssue]: ...
```

### 7.4 Material system rewrite

```python
# terrain_materials.py
def compute_world_splatmap_weights(
    stack: TerrainMaskStack,
    rules: MaterialRuleSet,
) -> np.ndarray:
    """Vectorized numpy. Returns (H, W, C) channel weights summing to 1."""

@dataclass
class MaterialRuleSet:
    channels: Tuple[MaterialChannel, ...]

@dataclass
class MaterialChannel:
    name: str
    base_weight_fn: Callable[[TerrainMaskStack], np.ndarray]
    min_slope: float = 0.0
    max_slope: float = math.pi / 2
    min_altitude: float = -math.inf
    max_altitude: float = math.inf
    concavity_preference: float = 0.0       # -1=convex, 0=any, 1=concave
    wetness_preference: float = 0.0         # -1=dry, 0=any, 1=wet
    triplanar: bool = False

# Default rule set
def default_dark_fantasy_rules() -> MaterialRuleSet: ...
```

Slope rule examples:

- `ground`: smoothstep(0°, 30°, slope) → 1, else fade
- `scree`: smoothstep(30°, 50°, slope)
- `cliff_rock` (triplanar): smoothstep(50°, 70°, slope)
- `wet_moss`: smoothstep(0.3, 0.7, wetness_mask) × (1 - smoothstep(45°, 60°, slope))
- `snow`: smoothstep(0.7, 0.9, altitude_norm) × (1 - smoothstep(60°, 75°, slope))

### 7.5 Bug fixes included in Bundle B

1. **Cliff parenting transform order** (`environment.py:820-827`):
   ```python
   # BEFORE (broken):
   cliff_obj.location = (cp["position"][0], cp["position"][1], cp["position"][2] * height_scale)
   cliff_obj.parent = obj
   
   # AFTER:
   cliff_obj.parent = obj
   world_mat = mathutils.Matrix.Translation((
       cp["position"][0],
       cp["position"][1],
       cp["position"][2] * height_scale,
   ))
   cliff_obj.matrix_world = world_mat
   ```

2. **Cliff height double-scale** (`_terrain_depth.py:637` × `environment.py:821`):
   - Compute `cliff_height` from `height_range` only, never multiplied by terrain width/height
   - Remove the second `* height_scale` in environment.py

3. **`np.clip(result, 0, 1)` removal** (`terrain_advanced.py:896`, `:1530`):
   - Delete both clips. World-unit heights must flow through unchanged.
   - Add unit test: `compute_erosion_brush` on input with max=47.3 preserves max ≤ 47.3 within erosion tolerance.

### 7.6 Tests required

- `test_terrain_cliffs.py` — 10+ tests
  1. `build_cliff_candidate_mask` returns correct cluster count on synthetic slope
  2. `carve_cliff_system` produces lip+face+ledge+talus for each cliff
  3. `validate_cliff_readability` rejects cliffs without lips
  4. Cliff parenting preserves world position on offset tile (regression for #1)
  5. Cliff height does not exceed 2× vertical range on any input (regression for #2)
- `test_terrain_materials.py` — 15+ tests
  1. `compute_world_splatmap_weights` is vectorized (timing test: 512×512 tile < 200ms)
  2. Channel weights sum to 1.0 per cell
  3. Cliff channel dominates at slope > 60°
  4. Wet moss channel appears on wet low slopes
  5. Snow channel only above altitude threshold
- `test_terrain_advanced_regression.py` — 5 tests
  1. `compute_erosion_brush` on input max=47.3 preserves world-unit max
  2. `flatten_terrain_zone` does not clip heights
  3. Existing tests still pass

### 7.7 Acceptance criteria

- [ ] `terrain_cliffs.py` created with 6 functions from §7.3
- [ ] `terrain_materials.py` has vectorized `compute_world_splatmap_weights` (< 200ms on 512² tile)
- [ ] `MaterialRuleSet` exposed with `default_dark_fantasy_rules` returning slope/altitude/curvature/wetness rules
- [ ] Triplanar cliff recipe present in default rules
- [ ] Cliff parenting bug fixed and regression test passes
- [ ] Cliff height double-scale bug fixed and regression test passes
- [ ] `[0,1]` clips removed from `terrain_advanced.py`
- [ ] Visual verification: generate a 1km cliff on a test scene, contact sheet shows lip/face/ledge/talus all readable at 100m
- [ ] All preserve-list tests still pass
- [ ] Score-pillar improvement: materials 3→7, cliff anatomy 2→8

### 7.8 Risks

| Risk | Mitigation |
|---|---|
| Triplanar on cliffs produces visible seams | Use Blender's world-space UV projection node; tests render from 3 angles |
| Vectorized splatmap allocates too much memory | Chunk by rows if tile > 1024 |
| Cliff structures collide with hero features | Integrate `hero_exclusion` mask into candidate filter |

---

## 8. Bundle C — Waterfall Hydrology Chain

**Goal:** Turn waterfalls into hydrologic systems with source → lip → drop → pool → outflow validation. Add meander + bank asymmetry + foam + mist + wet-rock masks to `_water_network.py`.

**Estimated sessions:** 2
**Score impact:** +0.6
**Parallel-safe with:** B, D, E
**Prerequisites:** Bundle A

### 8.1 Modules delivered

| Module | Path | Purpose |
|---|---|---|
| `terrain_waterfalls.py` | `handlers/terrain_waterfalls.py` | Waterfall chain builder + validator |
| `_water_network.py` (upgrade) | `handlers/_water_network.py` | Meander, bank asymmetry, foam/mist/wet-rock masks, outflow solver |
| `terrain_features.py` (bug fix) | `handlers/terrain_features.py` | Make `generate_waterfall` direction-aware (not hardcoded −Y) |

### 8.2 Key function signatures

```python
# terrain_waterfalls.py
def detect_waterfall_lip_candidates(
    stack: TerrainMaskStack,
    network: WaterNetwork,
    *,
    min_drop: float = 5.0,
    max_horizontal: float = 3.0,
) -> List[LipCandidate]: ...

def solve_waterfall_from_river(
    network: WaterNetwork,
    lip: LipCandidate,
    *,
    min_pool_radius: float = 3.0,
    outflow_angle_tolerance: float = math.radians(45),
) -> WaterfallChain: ...

def carve_impact_pool(
    chain: WaterfallChain,
    state: TerrainPipelineState,
    *,
    depth_factor: float = 0.4,
) -> None: ...

def build_outflow_channel(
    chain: WaterfallChain,
    network: WaterNetwork,
    state: TerrainPipelineState,
) -> None: ...

def generate_mist_zone(
    chain: WaterfallChain,
    stack: TerrainMaskStack,
    *,
    mist_radius_factor: float = 2.0,
) -> np.ndarray: ...

def generate_foam_mask(
    chain: WaterfallChain,
    stack: TerrainMaskStack,
) -> np.ndarray: ...

def validate_waterfall_system(
    chain: WaterfallChain,
) -> List[ValidationIssue]:
    """Hard gates:
    - source.z > lip.z (else INVALID_SLOPE)
    - lip.z > pool.z (else INVALID_DROP)
    - pool.radius >= min (else POOL_TOO_SMALL)
    - outflow exists (else NO_OUTFLOW)
    - chain is connected in WaterNetwork graph (else DISCONNECTED)
    """
```

```python
@dataclass
class WaterfallChain:
    feature_id: str
    source: WaterPoint          # upstream river point
    lip: WaterPoint             # waterfall lip
    drop_height: float
    pool: ImpactPool
    outflow: WaterPath
    width: float
    anchor: Optional[TerrainAnchor]

@dataclass
class LipCandidate:
    position: Tuple[float, float, float]
    drop_height: float
    upstream_accumulation: float
    normal: Tuple[float, float, float]
    confidence: float

@dataclass
class ImpactPool:
    center: Tuple[float, float, float]
    radius: float
    depth: float
```

### 8.3 `_water_network.py` upgrades

Add:

```python
class WaterNetwork:
    # ... existing methods ...

    def add_meander(
        self,
        amplitude: float,
        wavelength: float,
    ) -> None: ...

    def apply_bank_asymmetry(self, factor: float) -> None: ...

    def solve_outflow(
        self,
        pool_center: Tuple[float, float, float],
        heightmap: np.ndarray,
    ) -> Optional[WaterPath]: ...

    def compute_wet_rock_mask(
        self,
        stack: TerrainMaskStack,
        *,
        max_distance: float = 4.0,
    ) -> np.ndarray: ...

    def compute_foam_mask(
        self,
        stack: TerrainMaskStack,
    ) -> np.ndarray: ...

    def compute_mist_mask(
        self,
        stack: TerrainMaskStack,
    ) -> np.ndarray: ...
```

### 8.4 Tests required

- `test_terrain_waterfalls.py` — 12+ tests
  1. `detect_waterfall_lip_candidates` finds lip on synthetic cliff-river scene
  2. `solve_waterfall_from_river` builds complete chain from detected lip
  3. `validate_waterfall_system` rejects chain with lip.z < pool.z
  4. `validate_waterfall_system` rejects chain without outflow
  5. `carve_impact_pool` deepens heightmap at pool center
  6. `build_outflow_channel` extends river from pool downstream
  7. `generate_mist_zone` produces radial falloff mask
  8. `generate_foam_mask` activates only at impact zone
- `test_water_network_upgrade.py` — 8+ tests
  1. `add_meander` preserves start/end positions
  2. `apply_bank_asymmetry` modifies width profile correctly
  3. `solve_outflow` finds downstream path when one exists
  4. `solve_outflow` returns None when no downstream exists
  5. `compute_wet_rock_mask` peaks near water surface

### 8.5 Acceptance criteria

- [ ] `terrain_waterfalls.py` implements all 7 functions from §8.2
- [ ] `WaterfallChain`, `LipCandidate`, `ImpactPool` exported from `terrain_semantics.py`
- [ ] `_water_network.py` adds meander + asymmetry + foam/mist/wet-rock + outflow
- [ ] `terrain_features.generate_waterfall` accepts direction parameter (not hardcoded −Y)
- [ ] `validate_waterfall_system` is a hard gate in Pass 5 (water_network)
- [ ] Visual test: generate waterfall on test scene, 5-angle contact sheet shows complete source→lip→pool→outflow chain
- [ ] Preserve-list item #5 (`env_generate_waterfall` WaterNetwork routing) still passes
- [ ] Score pillars: waterfall hydrology 4→8, water networks 6→8

### 8.6 Risks

| Risk | Mitigation |
|---|---|
| Meander/bank asymmetry breaks downstream D8 tracing | Re-run `trace_river_from_flow` after meander apply; add regression test |
| `carve_impact_pool` creates local minima that confuse later passes | Mark pool cells with explicit pool flag in `water_surface` mask |
| Direction-aware `generate_waterfall` breaks existing scenes | Default direction param to current −Y for backwards compat |

---

## 9. Bundle D — Validation + Checkpoints

**Goal:** Deliver hard-fail validation gates and terrain-specific checkpoint/rollback infrastructure. Autonomous correction loops become possible.

**Estimated sessions:** 2
**Score impact:** +0.5
**Parallel-safe with:** B, C, E
**Prerequisites:** Bundle A

### 9.1 Modules delivered

| Module | Path | Purpose |
|---|---|---|
| `terrain_validation.py` | `handlers/terrain_validation.py` | All hard-fail validators + `ValidationReport` |
| `terrain_checkpoints.py` | `handlers/terrain_checkpoints.py` | `save_checkpoint`, `rollback_last_checkpoint`, preset save/load, autosave |

### 9.2 Validators required (each is a hard-fail gate)

| Validator | Code | Failure condition |
|---|---|---|
| `validate_cliff_presence` | `NO_CLIFFS_WHERE_EXPECTED` | Hero cliff spec region has no `CliffStructure` intersecting |
| `validate_hero_feature_count` | `HERO_COUNT_OUT_OF_RANGE` | Number of hero features outside [min, max] for quality profile |
| `validate_waterfall_hydrology` | `WATERFALL_CHAIN_BROKEN` | Any `WaterfallChain` fails `validate_waterfall_system` |
| `validate_pool_existence` | `POOL_MISSING` | Waterfall lip has no pool within 10m |
| `validate_cave_entrance_quality` | `CAVE_NO_FRAMING` | Cave archetype has no entrance framing, no debris, or no damp mask |
| `validate_material_zoning_complete` | `MATERIAL_COVERAGE_GAP` | Sum of material weights < 0.99 anywhere |
| `validate_tripo_collision` | `TRIPO_OVERLAP` | Tripo assets overlap > tolerance or intersect geometry |
| `validate_global_detail_budget` | `DETAIL_OVER_BUDGET` | Total polycount exceeds profile budget |
| `validate_protected_zone_violations` | `PROTECTED_ZONE_MUTATED` | A cell in a protected zone changed since intent capture |
| `validate_readability_bands` | `UNREADABLE_AT_BAND_X` | Rendered band fails silhouette/shape/volume/detail/surface score |

### 9.3 Key signatures

```python
# terrain_validation.py
class ValidationReport:
    issues: List[ValidationIssue]
    warnings: List[ValidationIssue]
    metrics: Dict[str, Any]
    passed: bool
    hard_failures: int
    soft_failures: int

def run_validation_suite(
    state: TerrainPipelineState,
    profile: str = "production",
    *,
    validators: Optional[List[str]] = None,
) -> ValidationReport: ...

# Each validator has signature:
def validate_<name>(
    state: TerrainPipelineState,
    profile: QualityProfile,
) -> List[ValidationIssue]: ...

# terrain_checkpoints.py
def save_checkpoint(
    state: TerrainPipelineState,
    pass_name: str,
    *,
    label: Optional[str] = None,
) -> TerrainCheckpoint: ...

def rollback_last_checkpoint(
    state: TerrainPipelineState,
) -> TerrainCheckpoint: ...

def rollback_to(
    state: TerrainPipelineState,
    checkpoint_id: str,
) -> TerrainCheckpoint: ...

def list_checkpoints(
    state: TerrainPipelineState,
) -> List[TerrainCheckpoint]: ...

def save_preset(
    name: str,
    intent: TerrainIntentState,
) -> Path: ...

def restore_preset(name: str) -> TerrainIntentState: ...

def autosave_after_pass(
    state: TerrainPipelineState,
    pass_name: str,
) -> Optional[TerrainCheckpoint]: ...
```

### 9.4 Checkpoint storage

- Location: `.planning/terrain_checkpoints/<world_id>/`
- Naming: `cp_<timestamp>_<pass_name>_<short_hash>.json`
- Mask stacks serialize to `.npz` alongside checkpoint JSON
- Blender state serialized via `bpy.ops.wm.save_as_mainfile(copy=True)` to `.blend`
- Retention: default 20 most recent per pass, configurable via `TerrainQualityProfile.checkpoint_retention`

### 9.5 Tests required

- `test_terrain_validation.py` — 20+ tests (one per validator success path + one per failure path)
- `test_terrain_checkpoints.py` — 15+ tests
  1. `save_checkpoint` writes files atomically (no partial files on crash)
  2. `rollback_last_checkpoint` restores mask stack bit-identically
  3. `rollback_to` navigates checkpoint chain correctly
  4. `save_preset` / `restore_preset` roundtrips without data loss
  5. `autosave_after_pass` respects retention policy
  6. Checkpoint directory cleanup on old ages

### 9.6 Acceptance criteria

- [ ] All 10 validators from §9.2 implemented
- [ ] `ValidationReport` returned by `run_validation_suite`
- [ ] Pass 10 (validation) in `TerrainPassController` calls `run_validation_suite`
- [ ] Hard-fail validators trigger `rollback_last_checkpoint` automatically
- [ ] Checkpoints stored under `.planning/terrain_checkpoints/`
- [ ] `terrain_checkpoints.py` reuses `pipeline_state.py` helpers where compatible
- [ ] Every preserve-list test still passes

---

## 10. Bundle E — Scatter Intelligence

**Goal:** Replace naive density-noise scatter with terrain-mask-driven viability scoring, role classification (hero/support/filler), and clustering for cliff rocks / waterfall boulders / cave debris.

**Estimated sessions:** 2–3
**Score impact:** +0.7
**Parallel-safe with:** B, C, D
**Prerequisites:** Bundle A

### 10.1 Modules delivered

| Module | Path | Purpose |
|---|---|---|
| `terrain_assets.py` | `handlers/terrain_assets.py` | Role classifier, context rules, cluster helpers, density/overlap validator |
| `_scatter_engine.py` (extend) | `handlers/_scatter_engine.py` | Add mask-driven viability scoring on top of existing Bridson Poisson |
| `environment_scatter.py` (refactor) | `handlers/environment_scatter.py` | Route terrain scatter through new pipeline |

### 10.2 Key signatures

```python
# terrain_assets.py
class AssetRole(str, Enum):
    HERO = "hero"
    SUPPORT = "support"
    FILLER = "filler"

@dataclass
class AssetContextRule:
    asset_tag: str                       # "cliff_rock", "waterfall_boulder", ...
    role: AssetRole
    viability: ViabilityFunction
    exclusion_radius: float
    cluster_rule: Optional[ClusterRule]
    density_target: float                # per square meter

@dataclass
class ClusterRule:
    center_source: str                   # "cliff_base", "waterfall_pool", "cave_mouth"
    distribution: str                    # "poisson" | "grid" | "organic"
    size_variance: float
    child_count_range: Tuple[int, int]

def classify_asset_role(asset_tag: str) -> AssetRole: ...

def build_asset_context_rules(
    biome: str,
    intent: TerrainIntentState,
) -> List[AssetContextRule]: ...

def place_assets_by_zone(
    rules: List[AssetContextRule],
    stack: TerrainMaskStack,
    features: FeatureRegistry,
    *,
    rng_seed: int,
) -> List[AssetPlacement]: ...

def cluster_rocks_for_cliffs(
    cliffs: List[CliffStructure],
    rules: List[AssetContextRule],
    stack: TerrainMaskStack,
) -> List[AssetPlacement]: ...

def cluster_rocks_for_waterfalls(
    chains: List[WaterfallChain],
    rules: List[AssetContextRule],
    stack: TerrainMaskStack,
) -> List[AssetPlacement]: ...

def scatter_debris_for_caves(
    caves: List[CaveStructure],
    rules: List[AssetContextRule],
    stack: TerrainMaskStack,
) -> List[AssetPlacement]: ...

def validate_asset_density_and_overlap(
    placements: List[AssetPlacement],
    *,
    max_overlap: float = 0.1,
    min_spacing: float = 0.5,
) -> List[ValidationIssue]: ...
```

### 10.3 Viability scoring

```python
@dataclass
class ViabilityFunction:
    slope_weight: float = 0.0
    slope_optimal: float = 0.0
    altitude_weight: float = 0.0
    altitude_optimal: float = 0.0
    wetness_weight: float = 0.0
    wetness_optimal: float = 0.5
    flow_weight: float = 0.0
    distance_to_water_weight: float = 0.0
    cliff_proximity_weight: float = 0.0
    exclusion_mask_names: Tuple[str, ...] = ()

def compute_viability(
    func: ViabilityFunction,
    stack: TerrainMaskStack,
) -> np.ndarray:
    """Returns (H, W) float in [0, 1]. Species with higher score wins cell."""
```

### 10.4 Tests

- `test_terrain_assets.py` — 15+ tests
  1. Viability scoring respects slope/altitude/wetness weights
  2. Cluster rule places child rocks within cliff base mask
  3. Waterfall pool clustering respects pool radius
  4. Cave debris clusters at entrance framing zone
  5. Overlap validator flags intersecting placements
  6. Density validator flags zones above/below target

### 10.5 Acceptance criteria

- [ ] `terrain_assets.py` exports all 8 functions from §10.2
- [ ] Pass 8 (asset_population) registered in `TerrainPassController`
- [ ] Existing building-affinity context scatter preserved via compatibility path
- [ ] Visual test: generate cliff scene with clustered rocks, contact sheet shows believable distribution
- [ ] Score pillars: procedural scatter 2→7

---

## 11. Bundle F — Cave Archetypes

**Goal:** Replace the generic semicircular-arch cave with 5 archetypes (fissure, collapsed arch, undercut shelf, sinkhole, tunnel), entrance framing, collapse debris, damp mask, readability validator.

**Estimated sessions:** 2
**Score impact:** +0.4
**Parallel-safe with:** B, C, D, E, G
**Prerequisites:** Bundle A

### 11.1 Modules delivered

| Module | Path | Purpose |
|---|---|---|
| `terrain_caves.py` | `handlers/terrain_caves.py` | Cave archetypes + framing + debris + damp |
| `_terrain_depth.py` (refactor) | `handlers/_terrain_depth.py` | Move `generate_cave_entrance_mesh` into archetype system, leave thin compat shim |

### 11.2 Archetypes

```python
class CaveArchetype(str, Enum):
    FISSURE = "fissure"
    COLLAPSED_ARCH = "collapsed_arch"
    UNDERCUT_SHELF = "undercut_shelf"
    SINKHOLE = "sinkhole"
    TUNNEL = "tunnel"

@dataclass
class CaveArchetypeSpec:
    archetype: CaveArchetype
    entrance_width: float
    entrance_height: float
    depth: float
    framing_count: int                  # 2 = left+right, 3 = plus lintel, etc.
    debris_scatter: float
    damp_radius: float
```

### 11.3 Key signatures

```python
def pick_cave_archetype(
    stack: TerrainMaskStack,
    position: Tuple[float, float, float],
    *,
    rng_seed: int,
) -> CaveArchetype: ...

def generate_cave_path(
    archetype: CaveArchetype,
    entrance: Tuple[float, float, float],
    depth: float,
) -> List[Tuple[float, float, float]]: ...

def carve_cave_volume(
    archetype: CaveArchetype,
    path: List[Tuple[float, float, float]],
    state: TerrainPipelineState,
) -> str:   # blender object name

def build_cave_entrance_frame(
    archetype: CaveArchetype,
    entrance: Tuple[float, float, float],
    state: TerrainPipelineState,
) -> List[str]:    # framing object names

def scatter_collapse_debris(
    archetype: CaveArchetype,
    entrance: Tuple[float, float, float],
    state: TerrainPipelineState,
) -> List[AssetPlacement]: ...

def generate_damp_mask(
    entrance: Tuple[float, float, float],
    radius: float,
    stack: TerrainMaskStack,
) -> np.ndarray: ...

def validate_cave_entrance(
    cave: CaveStructure,
    *,
    min_framing_elements: int = 2,
    require_debris: bool = True,
    require_damp_mask: bool = True,
) -> List[ValidationIssue]: ...
```

### 11.4 Acceptance

- [ ] All 5 archetypes implemented as distinct carve strategies
- [ ] Entrance framing adds ≥ 2 rock objects per cave
- [ ] Damp mask populated in `stack.decal_density["damp"]`
- [ ] Validator rejects caves without framing
- [ ] Visual test per archetype
- [ ] Score: cave anatomy 2→7

---

## 12. Bundle G — Banded Noise Refactor

**Goal:** Refactor `_terrain_noise.py` to output separate bands (continental, ridgelines, meso, strata, micro) instead of one final blended heightmap.

**Estimated sessions:** 1–2
**Score impact:** +0.3
**Parallel-safe with:** F, and most others
**Prerequisites:** Bundle A

### 12.1 Signature changes

```python
@dataclass
class BandedHeightmap:
    continental: np.ndarray             # 1–10km scale forms
    ridgelines: np.ndarray              # ridge emphasis via ridged multifractal
    meso: np.ndarray                    # 100m–1km breakup
    strata: np.ndarray                  # stratified shelf layers
    micro: np.ndarray                   # fine surface detail
    composite: np.ndarray               # sum for legacy compatibility

def generate_banded_heightmap(
    shape: Tuple[int, int],
    *,
    seed: int,
    profile: str = "dark_fantasy_default",
    continental_octaves: int = 6,
    ridgelines_octaves: int = 4,
    meso_octaves: int = 3,
    strata_bands: int = 6,
    micro_octaves: int = 3,
    domain_warp_strength: float = 50.0,
) -> BandedHeightmap: ...
```

### 12.2 Acceptance

- [ ] `BandedHeightmap` dataclass exported
- [ ] `generate_banded_heightmap` returns 5 distinct bands + composite
- [ ] Legacy `generate_heightmap` preserved as `BandedHeightmap.composite` accessor
- [ ] Domain warp, ridged multifractal, strata banding all exercised
- [ ] Visual test: render each band independently, confirm scale separation
- [ ] Score: heightmap authoring 7→8

---

## 13. Bundle H — Composition & Intent

**Goal:** Add the Erdtree authoring layer — camera saliency, morphology library, sightline framing, landmark hierarchy, feature rhythm, negative-space authoring. This is what makes terrain read as "authored" instead of "generated".

**Estimated sessions:** 4
**Score impact:** +0.4 (but unlocks hero-feature quality)
**Parallel-safe with:** I, J, K, L, M, N
**Prerequisites:** Bundles A, B, C, D, E (needs features and validation)

### 13.1 Modules delivered

| Module | Path | Purpose |
|---|---|---|
| `terrain_saliency.py` | `handlers/terrain_saliency.py` | Camera path analysis, silhouette scoring per vantage angle |
| `terrain_morphology.py` | `handlers/terrain_morphology.py` | 30–50 named landform templates |
| `terrain_framing.py` | `handlers/terrain_framing.py` | Sightline enforcement helpers |
| `terrain_hierarchy.py` | `handlers/terrain_hierarchy.py` | Primary/secondary/tertiary/ambient tier registry + budget |
| `terrain_rhythm.py` | `handlers/terrain_rhythm.py` | Walking-pace beat analysis and feature placement |
| `terrain_negative_space.py` | `handlers/terrain_negative_space.py` | Quiet-zone ratio authoring |

### 13.2 Morphology library (minimum 30 templates)

```python
MORPHOLOGY_TEMPLATES = {
    "box_canyon": MorphologyTemplate(...),
    "horseshoe_amphitheater": ...,
    "split_ridge": ...,
    "mesa_trio": ...,
    "arch_pass": ...,
    "waterfall_bowl": ...,
    "volcanic_plug": ...,
    "esker_ridge": ...,
    "tombolo": ...,
    "cirque_lake": ...,
    "drumlin_field": ...,
    "monadnock": ...,
    "yardang": ...,
    "inselberg": ...,
    "hoodoo_cluster": ...,
    "fiord": ...,
    "sea_stack_cluster": ...,
    "natural_bridge": ...,
    "cuesta": ...,
    "caprock_mesa": ...,
    "pediment": ...,
    "bajada_fan": ...,
    "ventifact_field": ...,
    "gorge_mouth": ...,
    "spur_and_re_entrant": ...,
    "ridge_saddle": ...,
    "pinnacle_field": ...,
    "dolmen_boulder_field": ...,
    "relict_ice_wedge": ...,
    "doline_cluster": ...,
    # ... more ...
}
```

### 13.3 Key signatures

```python
# terrain_saliency.py
def compute_vantage_silhouettes(
    feature: HeroFeatureSpec,
    vantages: Sequence[Tuple[float, float, float]],
    stack: TerrainMaskStack,
) -> Dict[Tuple, SilhouetteScore]: ...

def auto_sculpt_around_feature(
    feature: HeroFeatureSpec,
    required_vantages: Sequence[Tuple[float, float, float]],
    state: TerrainPipelineState,
    *,
    sweep_tolerance: float = 0.2,
) -> List[str]: ...

# terrain_morphology.py
def apply_morphology_template(
    template_name: str,
    center: Tuple[float, float, float],
    bounds: BBox,
    state: TerrainPipelineState,
    *,
    rotation: float = 0.0,
    scale: float = 1.0,
    variance: float = 0.2,
) -> MorphologyApplication: ...

# terrain_hierarchy.py
def classify_features_into_tiers(
    features: Sequence[HeroFeatureSpec],
    stack: TerrainMaskStack,
) -> Dict[str, List[HeroFeatureSpec]]: ...

def enforce_tier_budget(
    tiers: Dict[str, List[HeroFeatureSpec]],
    budget: HierarchyBudget,
) -> List[ValidationIssue]: ...

# terrain_rhythm.py
def analyze_feature_rhythm(
    features: Sequence[HeroFeatureSpec],
    walking_paths: Sequence[List[Tuple[float, float]]],
    *,
    target_beat_distance: float = 400.0,
) -> RhythmReport: ...

# terrain_negative_space.py
def compute_quiet_zone_ratio(
    stack: TerrainMaskStack,
    features: Sequence[HeroFeatureSpec],
) -> float: ...

def enforce_negative_space_ratio(
    state: TerrainPipelineState,
    *,
    target_ratio: float = 0.35,
) -> List[ValidationIssue]: ...
```

### 13.4 Acceptance

- [ ] 30+ morphology templates defined with parameterized generators
- [ ] `auto_sculpt_around_feature` modifies terrain to guarantee sightlines
- [ ] 4 tiers enforced (primary/secondary/tertiary/ambient) with per-km² budgets
- [ ] Rhythm analyzer emits beat distance report
- [ ] Negative space ratio ≥ target across test scenes
- [ ] Score: composition & intent 2→9, hero features 4→9

---

## 14. Bundle I — Geology Plausibility

**Goal:** Earth-science correctness — stratigraphic hardness, Strahler stream ordering, glacial carving, wind erosion, coastal erosion, karst hydrology, strata orientation consistency validator.

**Estimated sessions:** 3
**Score impact:** +0.4
**Parallel-safe with:** H, J, K, L, M, N
**Prerequisites:** Bundles A, B, C

### 14.1 Modules delivered

| Module | Path | Purpose |
|---|---|---|
| `terrain_stratigraphy.py` | `handlers/terrain_stratigraphy.py` | Hardness layer sim, caprock survival, differential weathering |
| `terrain_glacial.py` | `handlers/terrain_glacial.py` | U-valleys, cirques, hanging valleys, moraines |
| `terrain_wind_erosion.py` | `handlers/terrain_wind_erosion.py` | Barchan/transverse/star dunes, yardangs |
| `terrain_coastal.py` | `handlers/terrain_coastal.py` (extend existing `coastline.py`) | Wave-cut platforms, sea stacks, arches, tidal flats |
| `terrain_karst.py` | `handlers/terrain_karst.py` | Sinkholes, springs, karst towers, dolines |
| `terrain_geology_validator.py` | `handlers/terrain_geology_validator.py` | Strata orientation, erosion direction, snow-line consistency across tiles |
| `_terrain_erosion.py` (extend) | existing | Accept `rock_hardness` mask modulating erosion rate |
| `_water_network.py` (extend) | existing | Enforce Strahler ordering |

### 14.2 Validators

```python
def validate_strata_orientation_consistency(
    stack_this_tile: TerrainMaskStack,
    neighbor_stacks: Dict[str, TerrainMaskStack],
    *,
    max_angle_delta: float = math.radians(15),
) -> List[ValidationIssue]: ...

def validate_erosion_direction_consistency(
    stacks: Dict[Tuple[int, int], TerrainMaskStack],
) -> List[ValidationIssue]: ...

def validate_snow_line_consistency(
    stacks: Dict[Tuple[int, int], TerrainMaskStack],
    *,
    max_altitude_delta: float = 50.0,
) -> List[ValidationIssue]: ...

def validate_strahler_ordering(network: WaterNetwork) -> List[ValidationIssue]: ...
```

### 14.3 Acceptance

- [ ] Rock hardness layering produces visible caprock mesas
- [ ] Glacial U-valleys distinct from hydraulic V-valleys
- [ ] Barchan dunes face wind vector correctly
- [ ] Coastal platforms emerge at tidal zones
- [ ] Karst springs spawn downstream of limestone layers without upstream catchment
- [ ] Strata consistency validator catches synthetic inconsistency
- [ ] Score: geology plausibility 2→9, cliff anatomy 8→9

---

## 15. Bundle J — Ecosystem Spine

**Highest-ROI bundle after Bundle A.** This is what separates a terrain tool from a world-system platform.

**Goal:** Auto-generate audio zones, wildlife spawn volumes, gameplay zones, wind field, cloud shadow field, navmesh source data, decal placements, ecotone graphs — all from the existing mask stack.

**Estimated sessions:** 5
**Score impact:** +0.8 (ecosystem integration 1→9)
**Parallel-safe with:** H, I, K, L, M, N
**Prerequisites:** Bundles A, B, C, D, E

### 15.1 Modules delivered

| Module | Path | Purpose |
|---|---|---|
| `terrain_audio_zones.py` | `handlers/terrain_audio_zones.py` | Reverb volume generation |
| `terrain_wildlife_zones.py` | `handlers/terrain_wildlife_zones.py` | Spawn volume generation from viability scoring |
| `terrain_gameplay_zones.py` | `handlers/terrain_gameplay_zones.py` | Danger/safe/discovery zone tags |
| `terrain_wind_field.py` | `handlers/terrain_wind_field.py` | 2D Perlin wind field per tile |
| `terrain_cloud_shadow.py` | `handlers/terrain_cloud_shadow.py` | Cloud shadow field |
| `terrain_decal_placement.py` | `handlers/terrain_decal_placement.py` | Mask-driven decal emission (extends `decal_system.py`) |
| `terrain_navmesh_export.py` | `handlers/terrain_navmesh_export.py` | Traversability mask + Unity NavMesh source |
| `terrain_ecotone_graph.py` | `handlers/terrain_ecotone_graph.py` | Species gradient authoring between biomes |

### 15.2 Key signatures

```python
# terrain_audio_zones.py
@dataclass
class ReverbZone:
    bounds: BBox
    reverb_class: str                    # "cave_tight" | "canyon_long" | "plain_dry" | "forest_damped" | ...
    wet_mix: float
    early_reflections: float
    tail_length: float

def generate_reverb_zones(
    stack: TerrainMaskStack,
    features: FeatureRegistry,
) -> List[ReverbZone]: ...

def export_to_unity_audio_zones(
    zones: List[ReverbZone],
    output_path: Path,
) -> None: ...

# terrain_wildlife_zones.py
@dataclass
class SpawnVolume:
    bounds: BBox
    species: str
    density: float
    spawn_rules: Dict[str, Any]

def generate_spawn_volumes(
    stack: TerrainMaskStack,
    species_affinities: Dict[str, ViabilityFunction],
) -> List[SpawnVolume]: ...

# terrain_gameplay_zones.py
class GameplayZoneKind(str, Enum):
    DANGER = "danger"
    SAFE = "safe"
    DISCOVERY = "discovery"
    NEUTRAL = "neutral"

def classify_gameplay_zones(
    stack: TerrainMaskStack,
    features: FeatureRegistry,
) -> np.ndarray:    # returns (H, W) int enum

# terrain_wind_field.py
def generate_wind_field(
    tile_bounds: BBox,
    seed: int,
    *,
    base_direction: Tuple[float, float] = (1.0, 0.0),
    variation_scale: float = 200.0,
    variation_strength: float = 0.3,
) -> np.ndarray:    # returns (H, W, 2)

# terrain_cloud_shadow.py
def generate_cloud_shadow_field(
    tile_bounds: BBox,
    wind_field: np.ndarray,
    seed: int,
    *,
    cloud_coverage: float = 0.4,
    cloud_scale: float = 500.0,
) -> np.ndarray: ...

# terrain_decal_placement.py
def emit_mask_driven_decals(
    stack: TerrainMaskStack,
) -> Dict[str, List[DecalPlacement]]:
    """Returns decals per kind: moss, puddle, lichen, battle_debris, wet_rock, ..."""

# terrain_navmesh_export.py
def compute_traversability_mask(
    stack: TerrainMaskStack,
    *,
    max_slope: float = math.radians(40),
    min_clearance: float = 2.0,
) -> np.ndarray: ...

def export_navmesh_source(
    stack: TerrainMaskStack,
    output_path: Path,
) -> None: ...

# terrain_ecotone_graph.py
@dataclass
class EcotoneEdge:
    biome_a: str
    biome_b: str
    width: float                        # meters
    overstory_ramp: Callable[[float], str]
    understory_ramp: Callable[[float], str]
    groundcover_ramp: Callable[[float], str]

def build_ecotone_graph(
    biome_rules: Dict[str, BiomeRule],
) -> Dict[Tuple[str, str], EcotoneEdge]: ...

def apply_ecotones(
    state: TerrainPipelineState,
    graph: Dict[Tuple[str, str], EcotoneEdge],
) -> None: ...
```

### 15.3 Unity export schemas (JSON)

See §33 and Appendix B.

### 15.4 Acceptance

- [ ] All 8 modules from §15.1 created
- [ ] `Pass 9: ecosystem_spine` registered in `TerrainPassController`
- [ ] Unity export JSON schemas validated
- [ ] Visual test: generate scene, see audio zones overlap cave/valley, wildlife densities peak near water, wind field consistent
- [ ] Ecotone transition spans biome boundary with species gradients
- [ ] Score: ecosystem integration 1→9

---

## 16. Bundle K — Material Ceiling

**Goal:** Photoreal material upgrades — stochastic texture sampling, histogram-preserving blend, shadow clipmap bake, macro color grading, roughness variation driven by wetness mask, Quixel Megascans ingest pipeline.

**Estimated sessions:** 4
**Score impact:** +0.4
**Parallel-safe with:** H, I, J, L, M, N
**Prerequisites:** Bundles A, B

### 16.1 Modules delivered

| Module | Path | Purpose |
|---|---|---|
| `terrain_stochastic_shader.py` | `handlers/terrain_stochastic_shader.py` | Heitz & Neyret recipe export for Unity |
| `terrain_macro_color.py` | `handlers/terrain_macro_color.py` | World color signature pass |
| `terrain_multiscale_breakup.py` | `handlers/terrain_multiscale_breakup.py` | Macro/meso/micro color noise layers |
| `terrain_shadow_clipmap_bake.py` | `handlers/terrain_shadow_clipmap_bake.py` | Per-texel max shadow height pre-bake |
| `terrain_roughness_driver.py` | `handlers/terrain_roughness_driver.py` | Wetness → roughness mapping |
| `terrain_quixel_ingest.py` | `handlers/terrain_quixel_ingest.py` | Megascans asset import + tag + scale normalize + LOD generation |

### 16.2 Heitz & Neyret stochastic sampling recipe

Exported as Unity shader template + texture prep:

```python
def prepare_stochastic_texture(
    texture_path: Path,
    *,
    histogram_buckets: int = 64,
) -> StochasticTextureBundle:
    """Generate:
    1. Inverse-histogram LUT
    2. Gaussian-transformed texture
    3. Shader constants
    
    Returns bundle for Unity shader consumption.
    """
```

### 16.3 Shadow clipmap bake (Witcher 3 trick)

```python
def bake_shadow_clipmap(
    stack: TerrainMaskStack,
    *,
    sun_direction_range: Optional[List[Tuple[float, float]]] = None,
) -> np.ndarray:
    """Returns (H, W) float32 — per-texel maximum shadow height.
    
    For any TOD, shadow-casting can be computed in one texture lookup
    by comparing sun-angle-projected height against this baked value.
    """
```

### 16.4 Acceptance

- [ ] Stochastic texture sampling recipe exports usable Unity shader template
- [ ] Histogram-preserving blend recipe present in shader template
- [ ] Shadow clipmap bakes to `.exr` alongside heightmap
- [ ] Macro color grading applied as final material pass
- [ ] Wetness drives roughness (0.15 wet, 0.85 dry) on test render
- [ ] Quixel import pipeline handles at least one Megascans test asset
- [ ] Score: materials 8→9

---

## 17. Bundle L — Atmosphere & Horizon

**Goal:** Far-terrain LOD ring, volumetric fog density masks, atmospheric light shaft placements.

**Estimated sessions:** 2
**Score impact:** +0.15
**Parallel-safe with:** H, I, J, K, M, N
**Prerequisites:** Bundles A, B, C

### 17.1 Modules

| Module | Path | Purpose |
|---|---|---|
| `terrain_horizon_lod.py` | `handlers/terrain_horizon_lod.py` | Ultra-low-res far terrain (2–20km ring) with impostor blend |
| `terrain_fog_masks.py` | `handlers/terrain_fog_masks.py` | Volumetric fog density from concavity + altitude |
| `terrain_god_ray_hints.py` | `handlers/terrain_god_ray_hints.py` | Light shaft placement at clearings/canyons/caves |

### 17.2 Acceptance

- [ ] Horizon LOD generates 1/64 res mesh of far ring
- [ ] Fog density mask pools in valleys, thins over ridges
- [ ] God ray hints exported as Unity light probe data
- [ ] Score: atmosphere & horizon 4→8

---

## 18. Bundle M — Iteration Velocity

**Stealth quality multiplier.** Every hour saved here is an hour of polish elsewhere.

**Goal:** Dirty-flag system, mask versioning, region-based pass execution, live preview, visual diff, parallel pass DAG, hot-reload rules, iteration telemetry.

**Estimated sessions:** 3
**Score impact:** +0.2 (but compounds every other bundle's effective output)
**Parallel-safe with:** H, I, J, K, L, N
**Prerequisites:** Bundle A

### 18.1 Modules / extensions

| Module | Path | Purpose |
|---|---|---|
| `terrain_dirty_tracking.py` | `handlers/terrain_dirty_tracking.py` | Mask dirty flag propagation |
| `terrain_mask_cache.py` | `handlers/terrain_mask_cache.py` | Content-hash-based mask cache |
| `terrain_region_exec.py` | `handlers/terrain_region_exec.py` | Sub-tile pass execution |
| `terrain_live_preview.py` | `handlers/terrain_live_preview.py` | Re-run modified pass only |
| `terrain_visual_diff.py` | `handlers/terrain_visual_diff.py` | Red/green overlay between checkpoints |
| `terrain_pass_dag.py` | `handlers/terrain_pass_dag.py` | Parallel pass scheduler |
| `terrain_hot_reload.py` | `handlers/terrain_hot_reload.py` | JSON rule file watcher |
| `terrain_iteration_metrics.py` | `handlers/terrain_iteration_metrics.py` | Per-session timing telemetry |

### 18.2 Acceptance

- [ ] Edit a 100m patch of a 1km tile, only affected cells re-computed (5x+ speedup)
- [ ] Mask cache hits on unchanged inputs (measurable via metrics)
- [ ] Parallel pass DAG runs independent passes concurrently
- [ ] Visual diff overlay shows per-pass changes
- [ ] Hot-reload refreshes rule JSON without restart
- [ ] Score: iteration velocity 6→9

---

## 19. Bundle N — Deep Validation & QA

**Goal:** Deterministic-build CI, 5-band readability scoring, golden snapshot library, hero-feature budget enforcer, review feedback ingestion, iteration telemetry dashboard.

**Estimated sessions:** 3
**Score impact:** +0.15
**Parallel-safe with:** H, I, J, K, L, M
**Prerequisites:** Bundles A, D, M

### 19.1 Modules

| Module | Path | Purpose |
|---|---|---|
| `terrain_determinism_ci.py` | `handlers/terrain_determinism_ci.py` | Two-build diff as pytest |
| `terrain_readability_bands.py` | `handlers/terrain_readability_bands.py` | 5-band (1km/500m/100m/20m/2m) rendering + scoring |
| `terrain_budget_enforcer.py` | `handlers/terrain_budget_enforcer.py` | Per-hero polygon/texture/draw-call limits |
| `terrain_golden_snapshots.py` | `handlers/terrain_golden_snapshots.py` | Reference image library per feature × TOD × weather × angle |
| `terrain_review_ingest.py` | `handlers/terrain_review_ingest.py` | Structured external reviewer feedback |
| `terrain_telemetry_dashboard.py` | `handlers/terrain_telemetry_dashboard.py` | Historical metrics |

### 19.2 Acceptance

- [ ] Determinism test fails if output changes by 1 bit
- [ ] 5-band readability scores all features on a test scene
- [ ] Budget enforcer trips on synthetic over-budget feature
- [ ] Golden snapshot library seeded with ≥ 3 features × 4 TOD × 2 weather × 5 angles = 120 baseline images
- [ ] Review ingestion parses structured feedback and writes issues to validation report
- [ ] Score: validation depth 7→9

---

## 20. Bundle O — Water + Vegetation Depth

**Goal:** Author-intent depth for water (braided rivers, estuaries, karst springs, perched lakes, hot springs, tidal, wetlands, seasonal variants) and vegetation (overstory/midstory/understory/groundcover layering, edge effects, disturbance patches, fallen logs, clearings, cultivated patches, allelopathic exclusion).

**Estimated sessions:** 4
**Score impact:** +0.2
**Parallel-safe with:** H, I, J, K, L, M, N
**Prerequisites:** Bundles C, E

### 20.1 Water extensions

Added to `_water_network.py` and `terrain_waterfalls.py`:

```python
def build_braided_channels(network: WaterNetwork, gravel_bar_density: float) -> None: ...
def build_estuary(network: WaterNetwork, sea_boundary: BBox) -> None: ...
def inject_karst_springs(network: WaterNetwork, limestone_mask: np.ndarray) -> None: ...
def build_perched_lakes(stack: TerrainMaskStack) -> List[PerchedLake]: ...
def build_hot_springs(stack: TerrainMaskStack, geothermal_mask: np.ndarray) -> List[HotSpring]: ...
def apply_tidal_variation(stack: TerrainMaskStack, range_meters: float) -> None: ...
def build_wetlands(stack: TerrainMaskStack) -> List[Wetland]: ...
def switch_seasonal_state(stack: TerrainMaskStack, state: str) -> None: ...
```

### 20.2 Vegetation extensions

Added to `terrain_assets.py`:

```python
@dataclass
class VegetationLayers:
    overstory: List[AssetPlacement]
    midstory: List[AssetPlacement]
    understory: List[AssetPlacement]
    groundcover: List[AssetPlacement]

def build_vegetation_layers(
    biome: str,
    rules: List[AssetContextRule],
    stack: TerrainMaskStack,
) -> VegetationLayers: ...

def apply_edge_effects(
    layers: VegetationLayers,
    biome_boundary_mask: np.ndarray,
) -> VegetationLayers: ...

def generate_disturbance_patches(
    stack: TerrainMaskStack,
    *,
    fire_scars: int = 0,
    avalanche_paths: int = 0,
    flood_zones: int = 0,
) -> List[DisturbancePatch]: ...

def scatter_fallen_logs(
    forest_mask: np.ndarray,
    density: float,
) -> List[AssetPlacement]: ...

def author_clearings(
    forest_mask: np.ndarray,
    count: int,
    min_radius: float,
) -> List[Clearing]: ...
```

### 20.3 Acceptance

- [ ] All 8 water extensions functional
- [ ] 4-layer vegetation generator produces layered forest on test scene
- [ ] Edge effect density peaks at biome boundary
- [ ] Fire scar includes blackened trees + pioneer species
- [ ] Seasonal state switch modifies mask stack consistently
- [ ] Score: water networks 8→9, procedural scatter 7→9

---

## 21. Bundle P — Real-World Reference (OPTIONAL)

**Goal:** Import real geography (DEM), reference photo palette extraction, photogrammetry library integration.

**Estimated sessions:** 2
**Score impact:** +0.1
**Parallel-safe with:** all
**Prerequisites:** Bundle A

### 21.1 Modules

| Module | Path | Purpose |
|---|---|---|
| `terrain_dem_import.py` | `handlers/terrain_dem_import.py` | USGS / SRTM / ALOS DEM import with reprojection |
| `terrain_palette_extract.py` | `handlers/terrain_palette_extract.py` | Reference photo → palette + biome hint |

### 21.2 Acceptance

- [ ] USGS DEM imports successfully and becomes a `BandedHeightmap.continental`
- [ ] Reference photo produces palette suggestion
- [ ] Score: +0.1 across several pillars

---

## 22. Bundle Q — Runtime Data Export (OPTIONAL)

**Goal:** Unity-side wiring for footprint surface selection, voxel patch destructibility, time-decay weathering.

**Estimated sessions:** 2
**Score impact:** +0.1
**Parallel-safe with:** all
**Prerequisites:** Bundle A

### 22.1 Modules

| Module | Path | Purpose |
|---|---|---|
| `terrain_footprint_surface.py` | `handlers/terrain_footprint_surface.py` | Per-texel surface type for footprint shader |
| `terrain_destructibility_patches.py` | `handlers/terrain_destructibility_patches.py` | Voxel zones for runtime destruction |
| `terrain_weathering_timeline.py` | `handlers/terrain_weathering_timeline.py` | Time-decay weathering parameters |

### 22.2 Acceptance

- [ ] Surface-type mask exported alongside height
- [ ] Voxel zones tagged on cliff faces and ruin regions
- [ ] Weathering timeline data included in Unity export

---

## 23. File Impact Matrix

Every file touched by the plan, categorized. Bundle labels indicate which bundle writes the file.

### 23.1 New modules (created by plan)

| File | Bundle | Lines (est.) |
|---|---|---|
| `terrain_semantics.py` | A | 600 |
| `terrain_masks.py` | A | 500 |
| `terrain_pipeline.py` | A | 700 |
| `terrain_cliffs.py` | B | 550 |
| `terrain_waterfalls.py` | C | 500 |
| `terrain_validation.py` | D | 600 |
| `terrain_checkpoints.py` | D | 400 |
| `terrain_assets.py` | E | 700 |
| `terrain_caves.py` | F | 550 |
| `terrain_saliency.py` | H | 400 |
| `terrain_morphology.py` | H | 900 (30 templates) |
| `terrain_framing.py` | H | 250 |
| `terrain_hierarchy.py` | H | 300 |
| `terrain_rhythm.py` | H | 250 |
| `terrain_negative_space.py` | H | 200 |
| `terrain_stratigraphy.py` | I | 400 |
| `terrain_glacial.py` | I | 450 |
| `terrain_wind_erosion.py` | I | 400 |
| `terrain_karst.py` | I | 350 |
| `terrain_geology_validator.py` | I | 300 |
| `terrain_audio_zones.py` | J | 350 |
| `terrain_wildlife_zones.py` | J | 400 |
| `terrain_gameplay_zones.py` | J | 300 |
| `terrain_wind_field.py` | J | 200 |
| `terrain_cloud_shadow.py` | J | 200 |
| `terrain_decal_placement.py` | J | 400 |
| `terrain_navmesh_export.py` | J | 300 |
| `terrain_ecotone_graph.py` | J | 450 |
| `terrain_stochastic_shader.py` | K | 400 |
| `terrain_macro_color.py` | K | 300 |
| `terrain_multiscale_breakup.py` | K | 250 |
| `terrain_shadow_clipmap_bake.py` | K | 350 |
| `terrain_roughness_driver.py` | K | 200 |
| `terrain_quixel_ingest.py` | K | 400 |
| `terrain_horizon_lod.py` | L | 350 |
| `terrain_fog_masks.py` | L | 200 |
| `terrain_god_ray_hints.py` | L | 200 |
| `terrain_dirty_tracking.py` | M | 250 |
| `terrain_mask_cache.py` | M | 300 |
| `terrain_region_exec.py` | M | 350 |
| `terrain_live_preview.py` | M | 300 |
| `terrain_visual_diff.py` | M | 250 |
| `terrain_pass_dag.py` | M | 400 |
| `terrain_hot_reload.py` | M | 200 |
| `terrain_iteration_metrics.py` | M | 200 |
| `terrain_determinism_ci.py` | N | 300 |
| `terrain_readability_bands.py` | N | 500 |
| `terrain_budget_enforcer.py` | N | 300 |
| `terrain_golden_snapshots.py` | N | 400 |
| `terrain_review_ingest.py` | N | 250 |
| `terrain_telemetry_dashboard.py` | N | 300 |
| `terrain_dem_import.py` | P | 400 |
| `terrain_palette_extract.py` | P | 200 |
| `terrain_footprint_surface.py` | Q | 200 |
| `terrain_destructibility_patches.py` | Q | 300 |
| `terrain_weathering_timeline.py` | Q | 200 |

**Total new files: 56**
**Total new lines (rough estimate): ~18,500**

### 23.2 Modified existing files

| File | Bundle(s) | Type of change |
|---|---|---|
| `_terrain_world.py` | A | Refactor into pass functions |
| `_terrain_erosion.py` | A, I | Return `ErosionMasks` dataclass; accept hardness mask |
| `_terrain_depth.py` | B, F | Fix cliff height bug; move cave gen into `terrain_caves.py` |
| `_terrain_noise.py` | G | Banded output refactor |
| `_water_network.py` | C, I, O | Meander, foam/mist, Strahler, braided/estuary/karst |
| `environment.py` | A, B | Add `handle_run_terrain_pass`; fix cliff parenting bug |
| `terrain_materials.py` | B, K | Vectorized splatmap; stochastic + macro color + roughness |
| `terrain_advanced.py` | B | Remove `[0,1]` clips |
| `terrain_features.py` | C | Direction-aware waterfall |
| `terrain_chunking.py` | Preserve Codex fix | Nothing else |
| `visual_validation.py` | Preserve Codex fix | Nothing else |
| `viewport.py` | Preserve Codex fix | Nothing else |
| `scene.py` | Preserve Codex save_project | Extend only if Bundle D needs checkpoint hooks |
| `_scatter_engine.py` | E, O | Add mask-driven viability scoring layer |
| `environment_scatter.py` | E | Route through new pipeline |
| `decal_system.py` | J | Extend for mask-driven decals |
| `coastline.py` | I | Extend with wave-cut platforms, sea stacks |
| `pipeline_state.py` | D | Reuse for checkpoint backend |

---

## 24. Preserve List — Existing Capabilities to Protect

Every item in this list must have a regression test in the new test suite and must keep passing through Bundle Q completion.

1. **`env_generate_world_terrain` compatibility wrapper** — routes to per-tile wrapper (`environment.py:1176`)
2. **`aaa_verify_map` fails on empty screenshots** — returns `passed=False` with `missing_angles` (`visual_validation.py:162`)
3. **`validate_tile_seams` numpy + per-channel deltas** — channel shape validation + per-channel max/mean delta reporting (`terrain_chunking.py:367-473`)
4. **`handle_render_angle` real camera yaw/pitch** — not alias for screenshot (`viewport.py:1076`)
5. **`env_generate_waterfall` WaterNetwork routing** — drives `WaterNetwork.from_heightmap` for hydrology (`environment.py:1218-1280`)
6. **`aaa_verify_map` angle enforcement** — `required_angle_count` + `angle_labels` kwargs surface missing angles (`visual_validation.py`)
7. **`blender_scene save_project` / `verify_project_save`** — MCP actions + handlers (`blender_server.py:1206`, `scene.py`)

Plus these implicit preserves from the existing codebase:

8. `WaterNetwork.from_heightmap` graph builder and all its methods — `trace_river_from_flow`, `detect_lakes`, `detect_waterfalls`, `compute_river_width`
9. `ridged_multifractal` + `domain_warp` noise primitives
10. `apply_hydraulic_erosion` droplet physics (only the return type changes in Bundle A)
11. `apply_thermal_erosion` talus physics (only the return type changes in Bundle A)
12. `compute_chunk_lod` bilinear LOD downsample
13. `compute_streaming_distances` LOD band calculation
14. `poisson_disk_sample` Bridson algorithm
15. `VB_BIOME_PRESETS` dict — 10 biome presets with scatter rules
16. All 14 `TERRAIN_MATERIALS` biome palette specs
17. All `_terrain_depth.py` mesh generators (refactored but preserved in behavior)
18. `pipeline_state.py` checkpoint functions (Bundle D extends, does not replace)

Regression test file: `test_preserve_list.py` must contain one test per item and must be kept green through every bundle.

---

## 25. Dependency Graph

```
                   ┌─────────┐
                   │    A    │
                   │ Founda- │
                   │  tion   │
                   └────┬────┘
                        │
        ┌───────┬───────┼───────┬───────┐
        │       │       │       │       │
        v       v       v       v       v
     ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐
     │  B  │ │  C  │ │  D  │ │  E  │ │  G  │
     │Cliff│ │Water│ │Valid│ │Scat-│ │Noise│
     │ Mat │ │ fall│ │ CP  │ │ ter │ │Band │
     └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └─────┘
        │       │       │       │
        └───┬───┴───┬───┘       │
            │       │           │
            v       v           v
         ┌─────┐ ┌─────┐     ┌─────┐
         │  F  │ │  I  │     │  H  │
         │Caves│ │Geol-│     │Comp-│
         │     │ │ ogy │     │ osi-│
         └─────┘ └─────┘     │tion │
                             └──┬──┘
                                │
                                v
                  ┌─────────────────────┐
                  │         J            │
                  │   Ecosystem Spine    │
                  │  (highest ROI after A)│
                  └──────────┬──────────┘
                             │
                ┌────────┬───┴───┬────────┐
                │        │       │        │
                v        v       v        v
              ┌───┐   ┌───┐   ┌───┐   ┌───┐
              │ K │   │ L │   │ M │   │ N │
              │Mat│   │Atm│   │Vel│   │QA │
              │Cel│   │Hor│   │   │   │   │
              └───┘   └───┘   └───┘   └───┘

                             v
                           ┌───┐
                           │ O │
                           │Dep│
                           │ th│
                           └───┘
                             v
                           ┌───┐
                           │P,Q│
                           │Opt│
                           └───┘
```

**Bundle A is the single gate.** Everything depends on it. Once A is merged, B, C, D, E, G are fully parallelizable (all different files, no writer collisions). F, I, H depend on B/C/D/E (structural primitives) but are independent of each other. J depends on A through E (needs features + masks). K, L, M, N are polish and depend on A. O extends C and E. P, Q are optional.

### 25.1 File-lock matrix (parallel execution safety)

When dispatching parallel agents, use this matrix to avoid write collisions.

| File | Bundles that may write |
|---|---|
| `terrain_semantics.py` | A only |
| `terrain_pipeline.py` | A only |
| `terrain_masks.py` | A only |
| `terrain_cliffs.py` | B only |
| `terrain_waterfalls.py` | C only |
| `terrain_validation.py` | D only |
| `terrain_checkpoints.py` | D only |
| `terrain_assets.py` | E, O (sequential) |
| `terrain_caves.py` | F only |
| `terrain_morphology.py` | H only |
| `terrain_audio_zones.py` | J only |
| ... (all others follow single-bundle rule) | |
| `_terrain_world.py` | A only |
| `_terrain_erosion.py` | A, I (sequential, I after A merged) |
| `_water_network.py` | C, I, O (sequential) |
| `environment.py` | A, B (sequential, B after A) |
| `terrain_materials.py` | B, K (sequential, K after B) |
| `_scatter_engine.py` | E, O (sequential) |
| `_terrain_noise.py` | G only |
| `terrain_advanced.py` | B only |
| `terrain_features.py` | C only |
| `_terrain_depth.py` | B, F (sequential, F after B) |

**Rule of thumb:** If two bundles are listed against the same file, they must run sequentially. All other bundles can parallelize safely.

---

## 26. Execution Sequence

### 26.1 Phase 1 — Foundation (atomic, 4–5 sessions)

- **Bundle A** — fused foundation. Single commit, single agent team. Must ship before any other work.

### 26.2 Phase 2 — Core features (parallel, 8–10 sessions)

Dispatch as 4 parallel worktrees after A is merged:

- **Worktree B** — Bundle B (cliffs + materials)
- **Worktree C** — Bundle C (waterfalls)
- **Worktree D** — Bundle D (validation + checkpoints)
- **Worktree E** — Bundle E (scatter)

Merge order: D → B → C → E (D first because it adds the hard gates B/C/E will use; B before C because C wires through cliff-adjacent geometry; E last because it consumes everything).

### 26.3 Phase 3 — Structural depth (parallel, 5–6 sessions)

- **Bundle F** (caves) after B merged
- **Bundle G** (banded noise) any time after A
- **Bundle I** (geology) after B, C merged

### 26.4 Phase 4 — Ecosystem spine (5 sessions, top priority)

- **Bundle J** — ecosystem spine. Must run after A/B/C/D/E merged. Single biggest ROI in this phase.

### 26.5 Phase 5 — Quality ceiling (parallel, 10–12 sessions)

Dispatch as 4 parallel worktrees:

- **Worktree H** — composition & intent
- **Worktree K** — material ceiling
- **Worktree L** — atmosphere & horizon
- **Worktree M** — iteration velocity
- **Worktree N** — deep validation (after M merges)

### 26.6 Phase 6 — Depth polish (parallel, 4 sessions)

- **Bundle O** (water + vegetation depth)

### 26.7 Phase 7 — Optional (4 sessions)

- **Bundle P** (real-world reference)
- **Bundle Q** (runtime data export)

### 26.8 Total timeline

| Phase | Sessions (parallel) | Bundles |
|---|---|---|
| 1 | 4–5 | A |
| 2 | 8–10 (4 agents, ~2.5 each) | B, C, D, E |
| 3 | 5–6 (3 agents, ~2 each) | F, G, I |
| 4 | 5 | J |
| 5 | 10–12 (4 agents, ~3 each) | H, K, L, M, N |
| 6 | 4 | O |
| 7 | 4 | P, Q |
| **Total** | **40–46 session-equivalents** (with parallelism), **~55–60 single-thread sessions** | 17 bundles |

---

## 27. Testing Strategy

### 27.1 Test types

1. **Unit tests** — every module has a `test_<module>.py` in `Tools/mcp-toolkit/tests/`
2. **Integration tests** — pass pipelines run end-to-end on fixture scenes
3. **Visual regression** — golden snapshot comparison
4. **Determinism tests** — bit-identical output on re-run
5. **Performance tests** — pass timings against budget
6. **Preserve-list tests** — `test_preserve_list.py` guards Codex fixes
7. **Smoke tests** — `test_terrain_pipeline_smoke.py` runs minimal end-to-end per bundle

### 27.2 Test fixtures (canary scenes)

Defined in `Tools/mcp-toolkit/tests/fixtures/terrain/`:

| Fixture | Purpose |
|---|---|
| `flat_100m.npz` | Minimal mask stack, 100×100 flat terrain for unit tests |
| `synthetic_cliff.npz` | 500×500 scene with one 80° slope cluster |
| `synthetic_valley.npz` | 500×500 river valley |
| `synthetic_coastal.npz` | 500×500 coastline |
| `synthetic_cave_site.npz` | 500×500 with cliff + undercut shelf candidate |
| `synthetic_waterfall_site.npz` | 500×500 with upstream river + cliff drop |
| `full_tile_1km.npz` | 1024×1024 production-scale tile |
| `multi_tile_2x2.npz` | 4 adjacent tiles for seam tests |
| `hearthvale_baseline.blend` | Reference Blender scene for end-to-end visual regression |

### 27.3 CI expectations

- All tests must pass on every commit
- Performance tests set soft budgets (warn) and hard budgets (fail)
- Visual regression runs golden snapshot diff; > 5% pixel delta fails
- Determinism test runs in parallel across 4 seeds

### 27.4 Per-bundle test requirements

Each bundle section (6–22) specifies required tests. Bundle is not complete until:
- All required tests pass
- Coverage ≥ 80% on new modules
- Preserve-list tests still pass
- Performance budget for affected passes within tolerance

---

## 28. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Bundle A scope creep delays foundation | High | Critical | Freeze dataclass spec in §5; forbid scope adds during A execution |
| Dataclass redesign mid-plan | Medium | High | §5 is binding; revisions require plan bump |
| Codex concurrent edits collide | High | Medium | Check `git status` before every bundle start; use worktrees per bundle |
| Preserve-list regression | Medium | Critical | `test_preserve_list.py` runs in every CI cycle |
| Determinism silently breaks | Medium | High | Determinism smoke test required in Bundle A |
| Performance budget blown by new passes | Medium | Medium | Per-pass timing budgets in §32; Bundle M iteration speedups compensate |
| Unity export schema churn | Low | Medium | Lock schemas in §33; version them via `schema_version` field |
| Cliff anatomy too expensive to render | Low | Medium | Bundle N budget enforcer catches at validation |
| Morphology templates look samey | Medium | Medium | 30+ templates minimum; variance parameter on each |
| Ecosystem spine delayed by J sequencing | Low | High | Phase 4 is explicit; don't let K/L/M jump it |
| Mask stack memory blows out on 1024² tiles | Medium | High | Bundle M mask cache + per-tile eviction policy |
| Test fixtures rot without updates | Low | Medium | CI regenerates fixtures from seed on schedule |
| Agent dispatch misunderstands plan | Medium | High | Each bundle section is self-contained; §5 contracts are binding |

---

## 29. Success Metrics

### 29.1 Per-bundle metrics

| Bundle | Metric | Target |
|---|---|---|
| A | Pipeline passes smoke test | 100% |
| A | Determinism test passes | 100% |
| A | Erosion masks populated | All 6 channels non-None |
| B | Vectorized splatmap timing | < 200ms on 512² |
| B | Cliff anatomy visual test | Lip/face/ledge/talus readable at 100m |
| C | Waterfall validation test | source>lip>pool enforced |
| D | Validator coverage | ≥ 10 validators |
| E | Scatter density regression | Within 5% of rule target |
| F | Cave archetype visual diff | 5 distinct shapes |
| G | Banded height reproducibility | Each band deterministic |
| H | Sightline tests | 180°+ silhouette clarity |
| I | Strata consistency | Passes on multi-tile fixture |
| J | Ecosystem export count | All 8 systems emit data |
| K | Stochastic shader compiles | Unity import succeeds |
| L | Horizon LOD polycount | < 1/64 of full-res |
| M | Iteration speedup | ≥ 5x on 100m patch edit |
| N | Determinism CI | 100% pass across 4 seeds |
| O | Vegetation layers | All 4 populated |
| P | DEM import | USGS sample loads |
| Q | Unity runtime export | All 3 data streams present |

### 29.2 Overall metrics

- **AAA score ≥ 8.5** (measured via scorecard in §3.1)
- **All 17 bundles have at least 80% test coverage**
- **Preserve-list regression suite 100% passing**
- **Determinism CI 100% passing**
- **Performance budgets met** per §32
- **Visual goldens stable** across runs

---

## 30. Migration Strategy

### 30.1 Per-file migration

Each existing file that is refactored follows this pattern:

1. **Preserve current behavior behind a compatibility shim** — old function signatures keep working during migration
2. **Add new function signatures alongside** — no deletion until all callers migrated
3. **Migrate internal callers one at a time** — each caller migration is its own commit
4. **Deprecation warning** — log a warning when the old signature is called
5. **Remove old signature** — only after all callers migrated AND one release window has passed

### 30.2 Example: `apply_hydraulic_erosion` refactor

Before:
```python
def apply_hydraulic_erosion(heightmap: np.ndarray, ...) -> np.ndarray:
    ...
    return eroded
```

Step 1 (Bundle A): Introduce new return type, keep old as wrapper:
```python
def apply_hydraulic_erosion_masks(heightmap: np.ndarray, ...) -> ErosionMasks:
    ...
    return ErosionMasks(height=eroded, erosion_amount=..., ...)

def apply_hydraulic_erosion(heightmap: np.ndarray, ...) -> np.ndarray:
    """Deprecated: use apply_hydraulic_erosion_masks for full signal output."""
    warnings.warn("apply_hydraulic_erosion returning only heightmap is deprecated", DeprecationWarning)
    return apply_hydraulic_erosion_masks(heightmap, ...).height
```

Step 2: Migrate all internal callers to `apply_hydraulic_erosion_masks`
Step 3: Remove old signature after Bundle I ships

### 30.3 Handler compatibility

Existing `env_generate_*` handlers stay registered in `COMMAND_HANDLERS` until their migration commit:

```python
# Bundle A: new handler
def handle_run_terrain_pass(params: dict) -> dict:
    intent = build_intent_from_params(params)
    controller = TerrainPassController(state=TerrainPipelineState.new(intent))
    results = controller.run_pipeline(intent)
    return {"passes": [r.to_dict() for r in results]}

# Legacy handlers become thin wrappers
def handle_generate_terrain_tile(params: dict) -> dict:
    # Build intent from legacy params, run minimal pipeline
    intent = build_legacy_intent(params)
    controller = TerrainPassController(state=TerrainPipelineState.new(intent))
    controller.run_pass("macro_world")
    controller.run_pass("structural_masks")
    controller.run_pass("erosion")
    return {"tile": controller.state.to_legacy_dict()}
```

Both handlers stay registered; legacy calls still work. New code uses `run_terrain_pass`.

---

## 31. MCP Tool Surface Expansion

The whole toolkit is MCP-first. Each bundle must surface its capabilities through the Blender MCP server so Claude can drive the pipeline from chat.

### 31.1 New actions on existing tools

Extend `blender_environment` compound tool with new actions:

| Action | Bundle | Purpose |
|---|---|---|
| `run_terrain_pass` | A | Execute a single named pass |
| `run_terrain_pipeline` | A | Execute full pipeline from intent |
| `capture_scene_read` | A | Produce `TerrainSceneRead` for current scene |
| `save_terrain_checkpoint` | D | Snapshot current state |
| `rollback_terrain_checkpoint` | D | Restore previous checkpoint |
| `list_terrain_checkpoints` | D | List available checkpoints |
| `save_terrain_preset` | D | Save intent as reusable preset |
| `load_terrain_preset` | D | Load intent from preset |
| `validate_terrain` | D | Run validation suite |
| `build_cliff_system` | B | Invoke cliff pass manually |
| `build_waterfall_chain` | C | Invoke waterfall pass manually |
| `place_assets_by_zone` | E | Invoke asset pass manually |
| `carve_cave_archetype` | F | Invoke cave pass manually |
| `apply_morphology_template` | H | Apply named landform template |
| `export_ecosystem_data` | J | Emit Unity JSON bundles |
| `bake_shadow_clipmap` | K | Shadow clipmap bake |
| `generate_horizon_lod` | L | Far terrain LOD generator |
| `run_readability_audit` | N | 5-band scoring |

### 31.2 New MCP compound tool: `terrain_pipeline`

Add as a dedicated compound tool in `blender_server.py`:

```python
@mcp.tool()
async def terrain_pipeline(
    action: Literal[
        "run_pass", "run_pipeline", "scene_read",
        "save_checkpoint", "rollback_checkpoint", "list_checkpoints",
        "save_preset", "load_preset",
        "validate", "list_passes",
        "build_intent", "get_state",
    ],
    pass_name: Optional[str] = None,
    intent_json: Optional[str] = None,
    checkpoint_id: Optional[str] = None,
    preset_name: Optional[str] = None,
    region_json: Optional[str] = None,
    profile: str = "production",
) -> str:
    ...
```

This becomes the primary tool Claude uses to drive terrain work.

---

## 32. Performance Budgets

### 32.1 Per-pass budgets (512×512 tile, production profile)

| Pass | Target | Hard fail |
|---|---|---|
| macro_world | 200ms | 500ms |
| structural_masks | 150ms | 400ms |
| hero_features | 300ms | 800ms |
| erosion (droplet) | 2000ms | 5000ms |
| water_network | 500ms | 1500ms |
| structural_geometry | 1500ms | 4000ms |
| material_zoning | 200ms | 500ms |
| asset_population | 800ms | 2000ms |
| ecosystem_spine | 600ms | 1500ms |
| validation | 400ms | 1000ms |
| **Total pipeline** | **6650ms** | **17200ms** |

### 32.2 Memory budgets

- Mask stack per tile: ≤ 256 MB (1024² × ~48 channels × 4 bytes = ~192 MB headroom)
- Checkpoint `.npz` file: ≤ 128 MB
- Checkpoint `.blend` file: ≤ 512 MB
- Total per-session working set: ≤ 2 GB

### 32.3 Iteration velocity targets (Bundle M)

- Edit 100m patch of 1km tile: ≤ 800ms end-to-end (5x+ speedup vs full re-gen)
- Mask cache hit ratio on unchanged inputs: ≥ 90%
- Visual diff overlay render: ≤ 200ms

---

## 33. Unity Export Contracts

All exports are JSON + PNG/EXR sidecars in a deterministic directory layout.

```
exports/terrain/<world_id>/<tile_x>_<tile_y>/
├── heightmap.exr             # 32-bit float, world units
├── mask_stack.npz            # full TerrainMaskStack
├── splatmap.exr              # material weights
├── shadow_clipmap.exr        # max shadow height per texel
├── wind_field.exr            # 2-channel wind vector
├── cloud_shadow.exr          # cloud shadow field
├── traversability.png        # navmesh source
├── surface_type.png          # footprint shader input
├── audio_zones.json          # reverb zone list
├── wildlife_zones.json       # spawn volume list
├── gameplay_zones.json       # danger/safe/discovery list
├── decals.json               # decal placement list per kind
├── ecosystem_meta.json       # all ecosystem pass outputs
├── manifest.json             # file inventory + schema versions
└── checkpoints/              # saved checkpoint snapshots
```

### 33.1 `manifest.json` schema

```json
{
  "schema_version": "1.0",
  "world_id": "hearthvale",
  "tile_x": 0,
  "tile_y": 0,
  "tile_size": 1024,
  "cell_size": 1.0,
  "generation_timestamp": "2026-04-08T00:00:00Z",
  "generator_version": "terrain_pipeline_v1.0",
  "seed": 42,
  "intent_hash": "abc123...",
  "files": {
    "heightmap.exr": {"sha256": "...", "size": 4194304},
    "mask_stack.npz": {"sha256": "...", "size": 78643200},
    ...
  },
  "passes_executed": ["macro_world", "structural_masks", ...],
  "validation_status": "passed",
  "determinism_hash": "xyz789..."
}
```

### 33.2 `audio_zones.json` schema

```json
{
  "schema_version": "1.0",
  "zones": [
    {
      "bounds": {"min": [0, 0, 0], "max": [100, 100, 50]},
      "reverb_class": "cave_tight",
      "wet_mix": 0.8,
      "early_reflections": 0.6,
      "tail_length": 1.2
    }
  ]
}
```

### 33.3 `wildlife_zones.json` schema

```json
{
  "schema_version": "1.0",
  "volumes": [
    {
      "bounds": {"min": [100, 100, 0], "max": [200, 200, 30]},
      "species": "deer",
      "density": 0.05,
      "spawn_rules": {"min_distance_to_water": 10, "max_slope_deg": 25}
    }
  ]
}
```

### 33.4 `gameplay_zones.json` schema

```json
{
  "schema_version": "1.0",
  "zones": [
    {
      "bounds": {"min": [0, 0, 0], "max": [50, 50, 100]},
      "kind": "danger",
      "reason": "steep_slope_with_cliff_adjacency",
      "suggestion_tags": ["climb_gear_required", "fall_hazard"]
    }
  ]
}
```

### 33.5 `decals.json` schema

```json
{
  "schema_version": "1.0",
  "decals": {
    "moss": [
      {"position": [12.3, 45.6, 7.8], "normal": [0, 0, 1], "scale": 1.2, "rotation": 0.5}
    ],
    "puddle": [...],
    "battle_debris": [...],
    "wet_rock": [...]
  }
}
```

### 33.6 `ecosystem_meta.json` schema

Aggregates all ecosystem pass outputs for easy Unity-side consumption. Contains references to individual zone files + a single `wind_field_descriptor` and `cloud_shadow_descriptor` pointing to the `.exr` files.

---

## 34. Anti-Patterns

The plan explicitly forbids these patterns:

1. **Direct mutation without scene-read** — `TerrainPassController` must reject any `run_pass` call when `intent.scene_read is None`.
2. **Clipping world-unit heights to `[0, 1]`** — any `np.clip(..., 0, 1)` on a heightmap is banned. Worldspace means worldspace.
3. **Discarding intermediate erosion signals** — every pass that computes a mask must write it to the stack, never return just the height.
4. **Biome-name-based material selection** — material assignment must consult slope/altitude/curvature/flow, not just biome id.
5. **Generic cave booleans** — caves must use `pick_cave_archetype` and go through the archetype carve system.
6. **Cliffs without anatomy** — any cliff geometry must have lip + face + ledges + talus.
7. **Waterfall placed geometry** — every waterfall is a `WaterfallChain` derived from a `WaterNetwork`.
8. **Unscoped scatter** — scatter must consume `viability` from the mask stack, not pure noise density.
9. **Soft-pass validation** — validators either fail hard (with rollback) or succeed. No `warnings.warn` as a failure indicator.
10. **Writing without a writer contract** — a pass may only populate mask channels listed in `PassDefinition.produces_channels`.
11. **Global state in passes** — passes take `TerrainPipelineState` and return `PassResult`. No module-level mutable state.
12. **Skipping the preserve list** — every commit must run `test_preserve_list.py`.
13. **Adding new MCP actions without registering in `terrain_pipeline` tool** — consistency requirement.
14. **Naming collisions between mask channels** — every channel name in `TerrainMaskStack` is reserved; new channels require plan revision.
15. **Leaving TODOs in committed code** — if you must defer, create a plan checklist item in Appendix D and link it from the TODO comment.

---

## 35. Operational Concerns

### 35.1 Checkpoint retention

Default: 20 most recent per-pass-name per world. Configurable per quality profile. Stored under `.planning/terrain_checkpoints/<world_id>/`. Auto-cleanup after 30 days unless `pinned: true` in checkpoint metadata.

### 35.2 Determinism regression handling

When `test_determinism_ci.py` fails:

1. Diff the two mask stacks, identify first divergent cell
2. Bisect passes to find which pass introduced nondeterminism
3. Inspect that pass's `derive_pass_seed` usage
4. Fix + add a regression test pinning the failing case

Never merge a commit that breaks determinism.

### 35.3 Feature flags

New bundles ship with feature flags in `terrain_quality_profiles.py`:

```python
@dataclass
class TerrainQualityProfile:
    name: str
    enable_bundle_j_ecosystem: bool = True
    enable_bundle_k_stochastic: bool = True
    enable_bundle_m_dirty_tracking: bool = True
    enable_bundle_i_geology: bool = True
    ...
```

Allows per-run disabling if a bundle is broken. Hot-reload via `terrain_hot_reload.py`.

### 35.4 Canary terrain

A reference scene (`hearthvale_baseline.blend`) is regenerated automatically on every commit that touches `handlers/`. Visual diff against the previous golden fails the CI on > 5% pixel delta. This catches regressions that unit tests miss.

### 35.5 Tile invalidation

When a pass implementation changes in a bundle, the `generator_version` field in `manifest.json` bumps. Previously-exported tiles with a mismatched `generator_version` are marked stale and regenerated on next run.

### 35.6 Thread safety

Blender's `bpy` is single-threaded. Rules:

- Mask compute (numpy) can run in `multiprocessing.Pool`
- Pass DAG scheduler (Bundle M) runs numpy passes in parallel
- Any pass that touches `bpy.data`, `bpy.context`, `bpy.ops` must run on the main thread
- `PassDefinition.may_modify_geometry=True` forces main-thread execution

### 35.7 Checkpoint storage estimates

- 1 checkpoint = ~128 MB (mask stack .npz + .blend snapshot)
- 10 passes × 20 retention = 200 checkpoints × 128 MB = 25 GB per world
- Aggressive pruning mode keeps only 5 per pass = 6.4 GB

### 35.8 Logging conventions

Every pass logs:

```json
{
  "timestamp": "2026-04-08T00:00:00.123Z",
  "level": "INFO",
  "pass_name": "erosion",
  "tile": [0, 0],
  "duration_ms": 1847,
  "seed": 1234567,
  "content_hash_before": "abc",
  "content_hash_after": "def",
  "produced_channels": ["erosion_amount", "deposition_amount", ...],
  "issues": [],
  "warnings": []
}
```

Stored under `.planning/terrain_logs/<session_id>.jsonl`.

---

## 36. References

### 36.1 GDC talks and industry presentations

- Gollent, Marcin. "Landscape Creation and Rendering in REDengine 3." GDC 2014. [PDF](https://ubm-twvideo01.s3.amazonaws.com/o1/vault/GDC2014/Presentations/Gollent_Marcin_Landscape_Creation_and.pdf)
- Chen, Ka. "Adaptive Virtual Texture Rendering in Far Cry 4." GDC 2015.
- Van Muijden, Jaap. "GPU-Based Run-Time Procedural Placement in Horizon Zero Dawn." GDC 2017.
- Guerrilla Games. "GPU-Based Procedural Placement in Horizon Zero Dawn." [Publication](https://www.guerrilla-games.com/read/gpu-based-procedural-placement-in-horizon-zero-dawn).
- Various. "Terrain Rendering in Far Cry 5" and "Procedural World Generation of Far Cry 5." GDC 2018.
- Sucker Punch. "Samurai Landscapes: Crafting the World of Ghost of Tsushima." GDC 2021.
- Sucker Punch. "The Zen of Streaming: Designing Ghost of Tsushima." GDC 2021.
- Sucker Punch. "Procedural Grass in Ghost of Tsushima." GDC 2021.

### 36.2 Academic papers

- Heitz, E. & Neyret, F. "High-Performance By-Example Noise Using a Histogram-Preserving Blending Operator." SIGGRAPH 2018.
- Galin, E. et al. "A Review of Digital Terrain Modeling." Computer Graphics Forum 2019.
- Jenny, B. et al. "Large-scale Terrain Authoring through Interactive Erosion Simulation." ACM TOG 2023.
- Musgrave, F. Kenton. "Ridged Multifractal Terrain." Texturing and Modeling: A Procedural Approach.

### 36.3 Tools and engines

- World Machine — [world-machine.com](https://www.world-machine.com/)
- QuadSpinner Gaea — [quadspinner.com](https://quadspinner.com/)
- SideFX Houdini — [sidefx.com](https://www.sidefx.com/products/houdini/world-building/terrain/)
- Quixel Megascans — [quixel.com](https://quixel.com/)
- Unity Terrain documentation — current version

### 36.4 Blog posts and tech breakdowns

- Nick McDonald. "Procedural Hydrology." [nickmcd.me](https://nickmcd.me/2020/04/15/procedural-hydrology/)
- Christian Mills. "Procedural Tools Far Cry 5 Notes." [christianjmills.com](https://christianjmills.com/posts/procedural-tools-far-cry-5-notes/)
- 80 Level. "The Procedural Nature of Horizon Zero Dawn." [80.lv](https://80.lv/articles/the-procedural-nature-of-the-horizon-zero-dawn)

### 36.5 VeilBreakers internal references

- `docs/terrain_claude_master_plan_2026-04-07.md`
- `docs/terrain_branch_full_implementation_plan_2026-04-07.md`
- `docs/terrain_aaa_implementation_guide.md`
- `docs/terrain_tool_bug_audit_2026-04-07.md`
- `docs/terrain_pipeline_handoff_for_claude.md`
- `.claude/skills/vb-mcp-tools/TERRAIN_EDITING_PROTOCOL.md`

---

## 37. Glossary

- **Pass** — a single named stage in the terrain pipeline (e.g., `macro_world`, `erosion`, `water_network`, `validation`). Every pass consumes and produces named mask channels and returns a `PassResult`.
- **Mask stack** — the `TerrainMaskStack` dataclass. Unified registry of all signals computed for a tile. Channels accumulate across passes.
- **Mask channel** — a named field on the mask stack (e.g., `slope`, `wetness`, `flow_accumulation`).
- **Intent** — the `TerrainIntentState` that captures authoring goals (seed, region, anchors, protected zones, hero specs) before any mutation.
- **Scene read** — the structured summary a session produces before requesting mutations. Required by the orchestrator.
- **Hero feature** — a named, prioritized landmark (cliff, cave, waterfall, arch, canyon). Has a tier, budget, and optional anchor.
- **Anchor** — a named empty (Blender object) that handlers prefer over computed positions. E.g., `WF_LIP_TARGET`, `CLIFF_HERO_A`.
- **Protected zone** — a bounded region that certain passes may not mutate.
- **Quality profile** — a preset (preview/production/hero_shot/aaa_open_world) controlling resolution, iteration count, scatter density, validation strictness.
- **Checkpoint** — atomic snapshot of mask stack + Blender state for rollback.
- **Preset** — saved `TerrainIntentState` as JSON for reuse.
- **Pass sequence** — the ordered list of passes that constitutes a complete pipeline run.
- **Orchestrator** — the `TerrainPassController`. Only legal entry point for mutations.
- **Validator** — a hard-fail gate function returning `List[ValidationIssue]`.
- **Viability** — per-cell score used by scatter to rank species placement candidates.
- **Ecotone** — transition zone between biomes with species gradients.
- **Morphology template** — a named landform generator (e.g., "horseshoe_amphitheater").
- **Saliency** — macro-scale readability score for camera vantage selection.
- **Readability band** — a distance band (1km/500m/100m/20m/2m) at which a feature must read correctly.
- **Tier** — hero feature priority level (primary/secondary/tertiary/ambient).
- **Dirty channel** — a mask channel marked as needing recomputation.
- **Content hash** — blake2b hash of a mask stack used for cache lookup and determinism validation.
- **Stochastic sampling** — Heitz & Neyret technique for kill-tiling texture sampling.
- **Histogram-preserving blend** — Heitz & Neyret technique that keeps source texture histograms through blends.
- **Shadow clipmap** — per-texel baked max shadow height for instant TOD shadows.
- **Strahler order** — hierarchical numbering of river segments (1st-order = headwater, N+1 when two Nth-order streams merge).
- **Angle of repose** — natural slope of loose material (~34° for angular rock).
- **D8 flow** — 8-neighbor flow direction encoding.
- **Droplet erosion** — particle-based hydraulic erosion sim.
- **Triplanar projection** — UV projection from 3 world axes, blended by normal, eliminates stretching on cliffs.

---

## Appendix A — Command Handler Migration Table

Old → new mapping for every terrain-adjacent `COMMAND_HANDLERS` entry. Bundle A keeps all old handlers as compat shims; later bundles optionally retire them.

| Old command | Old handler | New command | Migration bundle |
|---|---|---|---|
| `env_generate_terrain_tile` | `handle_generate_terrain_tile` | `run_terrain_pass` (macro_world+structural_masks+erosion) | A (compat preserved) |
| `env_generate_world_terrain` | `handle_generate_world_terrain` | `run_terrain_pipeline` | A (compat preserved) |
| `env_generate_waterfall` | `handle_generate_waterfall` | `build_waterfall_chain` | C |
| `env_carve_river` | `handle_carve_river` | `run_terrain_pass` water_network | C |
| `env_generate_cliff_face` | lambda in __init__.py | `build_cliff_system` | B |
| `env_generate_cave_entrance` | lambda | `carve_cave_archetype` | F |
| `env_generate_canyon` | lambda | `apply_morphology_template canyon` | H |
| `env_generate_natural_arch` | lambda | `apply_morphology_template natural_bridge` | H |
| `env_generate_swamp_terrain` | lambda | `build_wetlands` | O |
| `env_paint_terrain` | `handle_paint_terrain` | `run_terrain_pass material_zoning` | B |
| `env_stitch_terrain_edges` | `handle_stitch_terrain_edges` | internal to orchestrator | A |
| `env_scatter_vegetation` | `handle_scatter_vegetation` | `place_assets_by_zone` | E |
| `env_scatter_props` | `handle_scatter_props` | `place_assets_by_zone` | E |
| `render_angle` | `handle_render_angle` | (preserved) | — |
| `aaa_verify_map` | `aaa_verify_map` | `run_readability_audit` | N |

Any old handler not listed is left unchanged.

---

## Appendix B — Preset JSON Schemas

### B.1 Quality profile preset

```json
{
  "schema_version": "1.0",
  "name": "aaa_open_world",
  "resolution": 1024,
  "erosion_iterations": 200000,
  "mesh_density": "high",
  "scatter_density": 1.0,
  "water_mesh_detail": "high",
  "validation_strictness": "hard",
  "checkpoint_frequency": "after_each_pass",
  "enable_bundle_j_ecosystem": true,
  "enable_bundle_k_stochastic": true,
  "enable_bundle_m_dirty_tracking": true,
  "enable_bundle_i_geology": true,
  "feature_tier_budget": {
    "primary_per_km2": 1,
    "secondary_per_km2": 4,
    "tertiary_per_km2": 12,
    "ambient_per_km2": 40
  },
  "readability_band_min_scores": {
    "1km": 0.6,
    "500m": 0.65,
    "100m": 0.7,
    "20m": 0.75,
    "2m": 0.8
  }
}
```

### B.2 Intent preset

```json
{
  "schema_version": "1.0",
  "seed": 42,
  "region_bounds": {"min": [0, 0, -50], "max": [1024, 1024, 200]},
  "tile_size": 1024,
  "cell_size": 1.0,
  "anchors": [
    {
      "name": "WF_LIP_TARGET",
      "world_position": [512, 768, 45],
      "anchor_kind": "waterfall_lip"
    },
    {
      "name": "CLIFF_HERO_A",
      "world_position": [200, 300, 20],
      "anchor_kind": "cliff_hero"
    }
  ],
  "protected_zones": [
    {
      "zone_id": "quest_waterfall_amphitheater",
      "bounds": {"min": [480, 740, 0], "max": [560, 820, 100]},
      "kind": "hero_mesh",
      "forbidden_mutations": ["macro_world", "erosion"],
      "allowed_mutations": ["material_zoning", "scatter"]
    }
  ],
  "hero_feature_specs": [...],
  "water_system_spec": {...},
  "quality_profile": "aaa_open_world",
  "morphology_templates": ["waterfall_bowl", "horseshoe_amphitheater"]
}
```

### B.3 Material rule set preset

```json
{
  "schema_version": "1.0",
  "name": "dark_fantasy_default",
  "channels": [
    {
      "name": "ground",
      "min_slope_deg": 0,
      "max_slope_deg": 30,
      "wetness_preference": 0.0,
      "triplanar": false
    },
    {
      "name": "cliff_rock",
      "min_slope_deg": 50,
      "max_slope_deg": 90,
      "triplanar": true
    },
    {
      "name": "wet_moss",
      "min_slope_deg": 0,
      "max_slope_deg": 60,
      "wetness_preference": 1.0
    },
    {
      "name": "snow",
      "min_altitude": 180,
      "max_slope_deg": 70
    }
  ]
}
```

### B.4 Scatter rule set preset

```json
{
  "schema_version": "1.0",
  "name": "temperate_forest",
  "rules": [
    {
      "asset_tag": "oak_tree",
      "role": "support",
      "viability": {
        "slope_weight": 0.4,
        "slope_optimal_deg": 10,
        "altitude_weight": 0.2,
        "altitude_optimal": 50,
        "wetness_weight": 0.2,
        "wetness_optimal": 0.5
      },
      "exclusion_radius": 3.0,
      "density_target": 0.01
    },
    {
      "asset_tag": "cliff_boulder",
      "role": "hero",
      "cluster_rule": {
        "center_source": "cliff_base",
        "distribution": "organic",
        "size_variance": 0.3,
        "child_count_range": [5, 12]
      },
      "density_target": 0.05
    }
  ]
}
```

---

## Appendix C — Test Fixture Library

Fixtures under `Tools/mcp-toolkit/tests/fixtures/terrain/`. Each is deterministic and regenerable from seed.

| Fixture | Seed | Size | Purpose |
|---|---|---|---|
| `flat_100m.npz` | 1 | 100×100 | Trivial — mask stack unit tests |
| `synthetic_cliff.npz` | 2 | 500×500 | One cliff cluster, no water |
| `synthetic_valley.npz` | 3 | 500×500 | River valley, slopes on either side |
| `synthetic_coastal.npz` | 4 | 500×500 | Coastline with wave action |
| `synthetic_cave_site.npz` | 5 | 500×500 | Cliff with undercut shelf candidate |
| `synthetic_waterfall_site.npz` | 6 | 500×500 | Upstream river + cliff drop |
| `full_tile_1km.npz` | 7 | 1024×1024 | Full production tile |
| `multi_tile_2x2.npz` | 8 | 4×(1024×1024) | Adjacent tiles for seam tests |
| `hearthvale_baseline.blend` | 9 | 2km | Reference scene for visual regression |
| `stratigraphy_test.npz` | 10 | 1024×1024 | Test scene with layered hardness |
| `glacial_valley.npz` | 11 | 1024×1024 | Glacial carving fixture |
| `dune_field.npz` | 12 | 1024×1024 | Wind erosion fixture |
| `karst_limestone.npz` | 13 | 1024×1024 | Karst hydrology fixture |
| `biome_transition.npz` | 14 | 1024×1024 | Ecotone fixture |

Fixture generation script: `Tools/mcp-toolkit/tests/fixtures/regenerate_terrain_fixtures.py`

---

## Appendix D — Bundle Compliance Checklists

Future sessions update these in place. Do not delete items; mark them with ✅.

### D.1 Bundle A — Foundation

- [ ] `terrain_semantics.py` created
- [ ] `TerrainMaskStack` dataclass with all §5.1 fields
- [ ] `TerrainIntentState` dataclass with §5.2 fields (frozen)
- [ ] `TerrainSceneRead` dataclass with §5.3 fields (frozen)
- [ ] `HeroFeatureSpec` dataclass with §5.4 fields (frozen)
- [ ] `WaterSystemSpec` dataclass with §5.5 fields (frozen)
- [ ] `ProtectedZoneSpec` dataclass with §5.6 fields (frozen)
- [ ] `TerrainAnchor` dataclass with §5.7 fields (frozen)
- [ ] `PassResult` dataclass with §5.8 fields
- [ ] `ValidationIssue` dataclass with §5.9 fields
- [ ] `TerrainCheckpoint` dataclass
- [ ] `terrain_pipeline.py` created
- [ ] `TerrainPassController` with `run_pass`, `run_pipeline`, `rollback_to`, `require_scene_read`, `enforce_protected_zones`
- [ ] `PassDefinition` dataclass with §5.11 fields
- [ ] `derive_pass_seed` function per §5.12
- [ ] `terrain_masks.py` created
- [ ] `compute_base_masks` implemented
- [ ] `compute_slope`, `compute_curvature`, `compute_concavity`, `compute_convexity`, `extract_ridge_mask`, `detect_basins`, `compute_macro_saliency` implemented
- [ ] `_terrain_erosion.py` refactored to return `ErosionMasks`
- [ ] `_terrain_erosion.py` no longer clips output to `[0,1]`
- [ ] `_terrain_world.py` refactored into `pass_macro_world`, `pass_structural_masks`, `pass_erosion`, `pass_validation_minimal`
- [ ] `environment.py` adds `handle_run_terrain_pass`
- [ ] `test_terrain_pipeline_smoke.py` created
- [ ] Smoke test: end-to-end pipeline runs
- [ ] Smoke test: mask stack channels populated
- [ ] Smoke test: determinism (bit-identical re-run)
- [ ] Smoke test: region scoping
- [ ] Smoke test: protected zones honored
- [ ] Smoke test: scene-read enforcement
- [ ] Smoke test: checkpoint create/rollback
- [ ] `test_preserve_list.py` created
- [ ] Preserve-list: env_generate_world_terrain compat
- [ ] Preserve-list: aaa_verify_map empty fails
- [ ] Preserve-list: validate_tile_seams 3D arrays
- [ ] Preserve-list: render_angle yaw/pitch
- [ ] Preserve-list: env_generate_waterfall WaterNetwork
- [ ] Preserve-list: aaa_verify_map angle enforcement
- [ ] Preserve-list: blender_scene save_project
- [ ] `pytest Tools/mcp-toolkit/tests/` all pass

Status: **COMPLETE** (commits f467f33..8eda364)

### D.2 Bundle B — Cliffs + Slope Materials

- [ ] `terrain_cliffs.py` created
- [ ] `build_cliff_candidate_mask`
- [ ] `carve_cliff_system`
- [ ] `add_cliff_ledges`
- [ ] `build_talus_field`
- [ ] `insert_hero_cliff_meshes`
- [ ] `validate_cliff_readability`
- [ ] `CliffStructure`, `TalusField` dataclasses
- [ ] `terrain_materials.compute_world_splatmap_weights` vectorized (< 200ms on 512²)
- [ ] `MaterialRuleSet` + `MaterialChannel` dataclasses
- [ ] `default_dark_fantasy_rules` returns slope/altitude/curvature/wetness rules
- [ ] Triplanar cliff channel present
- [ ] Cliff parenting transform bug fixed
- [ ] Cliff height double-scale bug fixed
- [ ] `np.clip(result, 0, 1)` removed from `compute_erosion_brush`
- [ ] `np.clip(result, 0, 1)` removed from `flatten_terrain_zone`
- [ ] `test_terrain_cliffs.py` — 10+ tests
- [ ] `test_terrain_materials.py` — 15+ tests
- [ ] `test_terrain_advanced_regression.py` — 5 tests
- [ ] Visual test: cliff contact sheet shows lip/face/ledge/talus

Status: **COMPLETE** (commits f467f33..8eda364)

### D.3 Bundle C — Waterfall Hydrology Chain

- [ ] `terrain_waterfalls.py` created
- [ ] `detect_waterfall_lip_candidates`
- [ ] `solve_waterfall_from_river`
- [ ] `carve_impact_pool`
- [ ] `build_outflow_channel`
- [ ] `generate_mist_zone`
- [ ] `generate_foam_mask`
- [ ] `validate_waterfall_system`
- [ ] `WaterfallChain`, `LipCandidate`, `ImpactPool` dataclasses
- [ ] `_water_network.add_meander`
- [ ] `_water_network.apply_bank_asymmetry`
- [ ] `_water_network.solve_outflow`
- [ ] `_water_network.compute_wet_rock_mask`
- [ ] `_water_network.compute_foam_mask`
- [ ] `_water_network.compute_mist_mask`
- [ ] `terrain_features.generate_waterfall` direction-aware
- [ ] `test_terrain_waterfalls.py` — 12+ tests
- [ ] `test_water_network_upgrade.py` — 8+ tests
- [ ] Visual test: 5-angle contact sheet shows complete chain

Status: **COMPLETE** (commits f467f33..8eda364)

### D.4 Bundle D — Validation + Checkpoints

- [ ] `terrain_validation.py` created
- [ ] 10 validators from §9.2
- [ ] `ValidationReport` dataclass
- [ ] `run_validation_suite`
- [ ] Pass 10 registered in `TerrainPassController`
- [ ] Hard-fail → automatic `rollback_last_checkpoint`
- [ ] `terrain_checkpoints.py` created
- [ ] `save_checkpoint`, `rollback_last_checkpoint`, `rollback_to`, `list_checkpoints`
- [ ] `save_preset`, `restore_preset`
- [ ] `autosave_after_pass`
- [ ] Reuses `pipeline_state.py` helpers
- [ ] Storage under `.planning/terrain_checkpoints/`
- [ ] `test_terrain_validation.py` — 20+ tests
- [ ] `test_terrain_checkpoints.py` — 15+ tests

Status: **COMPLETE** (commits f467f33..8eda364)

### D.5 Bundle E — Scatter Intelligence

- [ ] `terrain_assets.py` created
- [ ] `AssetRole` enum
- [ ] `AssetContextRule`, `ClusterRule`, `ViabilityFunction` dataclasses
- [ ] `classify_asset_role`
- [ ] `build_asset_context_rules`
- [ ] `place_assets_by_zone`
- [ ] `cluster_rocks_for_cliffs`
- [ ] `cluster_rocks_for_waterfalls`
- [ ] `scatter_debris_for_caves`
- [ ] `validate_asset_density_and_overlap`
- [ ] `compute_viability`
- [ ] Pass 8 registered
- [ ] `_scatter_engine` extended with mask-driven scoring
- [ ] `environment_scatter.py` routes through new pipeline
- [ ] `test_terrain_assets.py` — 15+ tests
- [ ] Visual test: clustered rocks on cliff base

Status: **COMPLETE** (commits f467f33..8eda364)

### D.6 Bundle F — Cave Archetypes

- [ ] `terrain_caves.py` created
- [ ] `CaveArchetype` enum (5 archetypes)
- [ ] `CaveArchetypeSpec` dataclass
- [ ] `pick_cave_archetype`
- [ ] `generate_cave_path`
- [ ] `carve_cave_volume`
- [ ] `build_cave_entrance_frame`
- [ ] `scatter_collapse_debris`
- [ ] `generate_damp_mask`
- [ ] `validate_cave_entrance`
- [ ] `_terrain_depth.py` refactored with compat shim
- [ ] Visual test per archetype

Status: **COMPLETE** (commits f467f33..8eda364)

### D.7 Bundle G — Banded Noise

- [ ] `BandedHeightmap` dataclass
- [ ] `generate_banded_heightmap`
- [ ] 5 distinct bands + composite
- [ ] Domain warp, ridged multifractal, strata banding exercised
- [ ] Legacy `generate_heightmap` preserved
- [ ] Visual test: each band separately rendered

Status: **COMPLETE** (commits f467f33..8eda364)

### D.8 Bundle H — Composition & Intent

- [ ] `terrain_saliency.py` — `compute_vantage_silhouettes`, `auto_sculpt_around_feature`
- [ ] `terrain_morphology.py` — 30+ templates
- [ ] `terrain_framing.py` — sightline enforcement
- [ ] `terrain_hierarchy.py` — tier classifier + budget
- [ ] `terrain_rhythm.py` — beat analyzer
- [ ] `terrain_negative_space.py` — quiet-zone ratio
- [ ] Visual tests per module

Status: **COMPLETE** (commits f467f33..8eda364)

### D.9 Bundle I — Geology Plausibility

- [ ] `terrain_stratigraphy.py`
- [ ] `terrain_glacial.py`
- [ ] `terrain_wind_erosion.py`
- [ ] `coastline.py` extended
- [ ] `terrain_karst.py`
- [ ] `terrain_geology_validator.py`
- [ ] `_terrain_erosion.py` accepts `rock_hardness` mask
- [ ] `_water_network.py` Strahler ordering
- [ ] 4 validators from §14.2

Status: **COMPLETE** (commits f467f33..8eda364)

### D.10 Bundle J — Ecosystem Spine

- [ ] `terrain_audio_zones.py`
- [ ] `terrain_wildlife_zones.py`
- [ ] `terrain_gameplay_zones.py`
- [ ] `terrain_wind_field.py`
- [ ] `terrain_cloud_shadow.py`
- [ ] `terrain_decal_placement.py`
- [ ] `terrain_navmesh_export.py`
- [ ] `terrain_ecotone_graph.py`
- [ ] Pass 9 registered
- [ ] Unity export JSONs validated against §33 schemas
- [ ] Visual test: all systems present

Status: **COMPLETE** (commits f467f33..8eda364)

### D.11 Bundle K — Material Ceiling

- [ ] `terrain_stochastic_shader.py`
- [ ] `terrain_macro_color.py`
- [ ] `terrain_multiscale_breakup.py`
- [ ] `terrain_shadow_clipmap_bake.py`
- [ ] `terrain_roughness_driver.py`
- [ ] `terrain_quixel_ingest.py`
- [ ] Stochastic Unity shader template exports
- [ ] Histogram-preserving blend in template
- [ ] Shadow clipmap bakes to `.exr`
- [ ] Quixel import handles at least 1 asset

Status: **COMPLETE** (commits f467f33..8eda364)

### D.12 Bundle L — Atmosphere & Horizon

- [ ] `terrain_horizon_lod.py`
- [ ] `terrain_fog_masks.py`
- [ ] `terrain_god_ray_hints.py`
- [ ] Horizon LOD < 1/64 res
- [ ] Fog pools in valleys
- [ ] God ray hints exported

Status: **COMPLETE** (commits f467f33..8eda364)

### D.13 Bundle M — Iteration Velocity

- [ ] `terrain_dirty_tracking.py`
- [ ] `terrain_mask_cache.py`
- [ ] `terrain_region_exec.py`
- [ ] `terrain_live_preview.py`
- [ ] `terrain_visual_diff.py`
- [ ] `terrain_pass_dag.py`
- [ ] `terrain_hot_reload.py`
- [ ] `terrain_iteration_metrics.py`
- [ ] 5x speedup on 100m patch edit
- [ ] Cache hit ratio ≥ 90% on unchanged inputs
- [ ] Parallel DAG runs independent passes
- [ ] Visual diff overlay works
- [ ] Hot-reload refreshes rules

Status: **COMPLETE** (commits f467f33..8eda364)

### D.14 Bundle N — Deep Validation & QA

- [ ] `terrain_determinism_ci.py`
- [ ] `terrain_readability_bands.py`
- [ ] `terrain_budget_enforcer.py`
- [ ] `terrain_golden_snapshots.py`
- [ ] `terrain_review_ingest.py`
- [ ] `terrain_telemetry_dashboard.py`
- [ ] Determinism test fails on 1-bit change
- [ ] 5-band scoring runs on test scene
- [ ] Budget enforcer trips on synthetic over-budget
- [ ] Golden snapshot library seeded (≥ 120 images)

Status: **COMPLETE** (commits f467f33..8eda364)

### D.15 Bundle O — Water + Vegetation Depth

- [ ] Water: braided, estuary, karst springs, perched lakes, hot springs, tidal, wetlands, seasonal
- [ ] Vegetation: 4-layer, edge effects, disturbance, fallen logs, clearings, cultivated, allelopathic
- [ ] `VegetationLayers`, `DisturbancePatch`, `Clearing` dataclasses
- [ ] Visual tests per feature

Status: **COMPLETE** (commits f467f33..8eda364)

### D.16 Bundle P — Real-World Reference (OPTIONAL)

- [ ] `terrain_dem_import.py`
- [ ] `terrain_palette_extract.py`
- [ ] USGS DEM sample imports
- [ ] Reference photo produces palette

Status: **COMPLETE** (commits f467f33..8eda364)

### D.17 Bundle Q — Runtime Data Export (OPTIONAL)

- [ ] `terrain_footprint_surface.py`
- [ ] `terrain_destructibility_patches.py`
- [ ] `terrain_weathering_timeline.py`
- [ ] All 3 data streams exported

Status: **COMPLETE** (commits f467f33..8eda364)

---

## Addendum 1 — Gap Closure (2026-04-08 revision)

This addendum closes gaps identified during the final completeness audit against:
- `terrain_claude_master_plan_2026-04-07.md` (sections 5–27)
- `terrain_branch_full_implementation_plan_2026-04-07.md` (sections L1–L2, M)
- `terrain_aaa_implementation_guide.md` (sections 6–10)
- `terrain_tool_bug_audit_2026-04-07.md` (bugs 1–17, especially #8, #12, #15, #16, #17)
- Feedback memory: `feedback_v10_actual_visual_issues.md`, `feedback_visual_editing_protocol.md`, `feedback_waterfall_must_have_volume.md`, `feedback_blender_z_up.md`, `feedback_blender_crash_avoidance.md`, `feedback_screenshot_max_size.md`, `feedback_tripo_import_one_at_a_time.md`, `feedback_realtime_editing_scalability.md`, `feedback_aaa_quality_demand.md`, `feedback_visual_verify_quality.md`
- The deep-dive themes A–K in the conversation history

Everything below is binding and has the same authority as sections 1–41 above.

---

### Addendum 1.A — Bundle R — Protocol Enforcement & Runtime Safety (NEW)

**Goal:** Turn the TERRAIN_EDITING_PROTOCOL documentation into runtime-enforced Python utilities, lock down Blender-specific stability rules, and gate every mutation behind scene understanding, viewport sync, and addon-version assertion.

**Why it's a new bundle:** The original plan treated protocol enforcement as a property of the orchestrator. That was insufficient — protocol enforcement is cross-cutting across every handler that touches geometry, requires its own test suite, and absorbs the Blender-stability safety rules that don't belong in any other bundle. Gaps #1–#4 from the final audit all live here.

**Estimated sessions:** 3
**Score impact:** +0.3 (autonomy + validation pillars)
**Parallel-safe with:** all bundles except A (depends on A orchestrator)
**Prerequisites:** Bundle A

#### 1.A.1 Modules delivered

| Module | Path | Purpose |
|---|---|---|
| `terrain_protocol.py` | `handlers/terrain_protocol.py` | Runtime enforcement of TERRAIN_EDITING_PROTOCOL rules 1–7 |
| `terrain_viewport_sync.py` | `handlers/terrain_viewport_sync.py` | User-viewport anchoring, "observe before calculate" helpers |
| `terrain_reference_locks.py` | `handlers/terrain_reference_locks.py` | Named empty anchor lock/unlock + proximity assertions |
| `terrain_addon_health.py` | `handlers/terrain_addon_health.py` | Addon version assertion, reload detection, handler registration integrity |
| `terrain_blender_safety.py` | `handlers/terrain_blender_safety.py` | Z-up enforcement, screenshot max_size cap, boolean-op dense-mesh guard, Tripo batch serialization |
| `terrain_scene_read.py` | `handlers/terrain_scene_read.py` | `capture_scene_read` handler that produces `TerrainSceneRead` snapshots |

#### 1.A.2 `terrain_protocol.py` — the 7 enforced rules

Rules from `.claude/skills/vb-mcp-tools/TERRAIN_EDITING_PROTOCOL.md` become callable decorators/guards:

```python
@enforce_protocol
def handle_any_terrain_mutation(params: dict) -> dict:
    """Any handler wrapped by @enforce_protocol must pass all 7 gates."""
    ...

class ProtocolGate:
    """Each rule is a gate. Failing any gate raises ProtocolViolation."""

    @staticmethod
    def rule_1_observe_before_calculate(state: TerrainPipelineState) -> None:
        """Assert a TerrainSceneRead was captured within the last N seconds
        and matches the current scene hash."""

    @staticmethod
    def rule_2_sync_to_user_viewport(state: TerrainPipelineState) -> None:
        """Assert Blender active viewport camera pose was read and cached
        as the 'authoring vantage'. Any mutation beyond this vantage's
        visible frustum must carry an explicit 'out_of_view_ok=True' flag."""

    @staticmethod
    def rule_3_lock_reference_empties(state: TerrainPipelineState) -> None:
        """Assert every named anchor in intent.anchors has a matching Blender
        empty whose world position matches within 0.01m tolerance.
        Drift > tolerance = hard fail."""

    @staticmethod
    def rule_4_real_geometry_not_vertex_tricks(params: dict) -> None:
        """Forbid vertex-color-only fakes for hero features. Cliffs, caves,
        and waterfalls must land as actual mesh additions, not shader tricks."""

    @staticmethod
    def rule_5_smallest_diff_per_iteration(state: TerrainPipelineState) -> None:
        """If the current pass modifies > N cells or > M objects without
        an explicit 'bulk_edit=True' flag, hard-fail with a message
        suggesting the user run a region-scoped pass instead."""

    @staticmethod
    def rule_6_surface_vs_interior_classification(params: dict) -> None:
        """Every placed object must carry a placement_class tag:
        surface|interior|above_surface|below_surface. Mis-classified
        placements (e.g., cave_mouth tagged 'surface') hard-fail."""

    @staticmethod
    def rule_7_plugin_usage(params: dict) -> None:
        """If the handler is a terrain mutation, assert the vb-blender
        MCP plugin is registered and the addon version matches
        TERRAIN_ADDON_MIN_VERSION."""
```

#### 1.A.3 `terrain_viewport_sync.py`

```python
@dataclass(frozen=True)
class ViewportVantage:
    """User's current Blender 3D viewport state, cached at scene read time."""
    camera_position: Tuple[float, float, float]
    camera_direction: Tuple[float, float, float]
    camera_up: Tuple[float, float, float]
    focal_point: Tuple[float, float, float]
    fov: float
    visible_bounds: BBox
    captured_timestamp: float
    view_matrix_hash: str

def read_user_vantage() -> ViewportVantage: ...
def assert_vantage_fresh(vantage: ViewportVantage, max_age_seconds: float = 300.0) -> None: ...
def transform_world_to_vantage(
    world_position: Tuple[float, float, float],
    vantage: ViewportVantage,
) -> Tuple[float, float, float]: ...
def is_in_frustum(
    world_position: Tuple[float, float, float],
    vantage: ViewportVantage,
) -> bool: ...
```

#### 1.A.4 `terrain_reference_locks.py`

```python
def lock_anchor(anchor: TerrainAnchor) -> None:
    """Create/update a Blender empty with the anchor name, lock its
    transform, and record its hash in the intent state."""

def unlock_anchor(anchor_name: str) -> None: ...

def assert_anchor_integrity(
    anchor: TerrainAnchor,
    *,
    tolerance: float = 0.01,
) -> None:
    """Raise AnchorDrift if the Blender empty's world position has
    drifted from the intent-recorded position beyond tolerance."""

def assert_all_anchors_intact(
    intent: TerrainIntentState,
) -> List[AnchorDriftReport]: ...
```

#### 1.A.5 `terrain_addon_health.py`

```python
TERRAIN_ADDON_MIN_VERSION = (1, 0, 0)

def assert_addon_loaded() -> None: ...
def assert_addon_version_matches(min_version: Tuple[int, ...] = TERRAIN_ADDON_MIN_VERSION) -> None: ...
def assert_handlers_registered(required: Sequence[str]) -> None: ...
def detect_stale_addon() -> bool:
    """Returns True if the loaded addon module differs from the
    on-disk version (indicates needed reload)."""

def force_addon_reload() -> None: ...
```

This closes **Gap #3 — Addon reload enforcement & integration testing** from the final audit. Code changes passing pytest don't prove real Blender execution hits the new path. `detect_stale_addon` + startup-time `assert_addon_version_matches` in the `TerrainPassController.__init__` catch this.

#### 1.A.6 `terrain_blender_safety.py`

Absorbs every Blender-specific stability rule from the feedback memory files into enforceable guards:

```python
# Z-up enforcement (feedback_blender_z_up.md)
def assert_z_is_up(obj: bpy.types.Object) -> None:
    """Raise CoordinateSystemError if the object's up axis is not Z."""

def convert_y_up_to_z_up(
    position: Tuple[float, float, float],
    orientation: Tuple[float, float, float],
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """Convert Y-up coordinates to Z-up. Use at EVERY boundary that
    imports from Y-up sources (e.g., GLTF, FBX with Y-up source)."""

@guard_z_up
def any_handler_that_sets_object_transform(...): ...

# Screenshot max_size cap (feedback_screenshot_max_size.md)
BLENDER_SCREENSHOT_MAX_SIZE = 507      # NEVER 1024; hard cap per feedback
def clamp_screenshot_size(requested: int) -> int:
    return min(max(64, requested), BLENDER_SCREENSHOT_MAX_SIZE)

# Boolean-op dense mesh guard (feedback_blender_crash_avoidance.md)
BOOLEAN_DENSE_MESH_VERT_LIMIT = 60000
def assert_boolean_safe(cutter: bpy.types.Object, target: bpy.types.Object) -> None:
    """Fail before calling any boolean op if either operand exceeds
    BOOLEAN_DENSE_MESH_VERT_LIMIT. Require decimation first."""

def decimate_to_safe_count(
    obj: bpy.types.Object,
    target_count: int = 30000,
) -> None: ...

def run_boolean_with_safety(
    solver: str,
    cutter: bpy.types.Object,
    target: bpy.types.Object,
) -> bpy.types.Object:
    """Wrapper that decimates if needed and uses FAST solver on dense meshes."""

# Tripo batch serialization (feedback_tripo_import_one_at_a_time.md)
_TRIPO_IMPORT_LOCK = threading.Lock()
def import_tripo_glb_serialized(glb_paths: Sequence[Path]) -> List[bpy.types.Object]:
    """Import Tripo GLBs strictly serially, one per blender_execute call.
    Batch imports CRASH Blender."""
```

#### 1.A.7 `terrain_scene_read.py`

```python
def capture_scene_read(
    *,
    reviewer: str,
    focal_point_hint: Optional[Tuple[float, float, float]] = None,
) -> TerrainSceneRead:
    """Walk current Blender scene and produce a structured understanding
    snapshot matching the §5.3 TerrainSceneRead contract. Required
    before any mutation request."""
```

The captured snapshot must include:
- All 10 TerrainSceneRead fields from §5.3
- Current ViewportVantage
- Active addon version
- Current content hash of all terrain-related Blender objects
- List of lockable anchors detected in the scene

#### 1.A.8 Tests

- `test_terrain_protocol.py` — 15+ tests covering each of the 7 gates (success + failure path per rule)
- `test_terrain_viewport_sync.py` — 8+ tests
- `test_terrain_reference_locks.py` — 10+ tests
- `test_terrain_addon_health.py` — 8+ tests including stale-detection and reload
- `test_terrain_blender_safety.py` — 12+ tests (Z-up, screenshot clamp, boolean safety, Tripo serialization)
- `test_terrain_scene_read.py` — 6+ tests

#### 1.A.9 Acceptance

- [ ] All 6 modules from 1.A.1 created
- [ ] 7 `ProtocolGate` rules implemented as callable guards
- [ ] `@enforce_protocol` decorator wraps every terrain mutation handler
- [ ] `capture_scene_read` handler produces valid `TerrainSceneRead`
- [ ] `TerrainPassController.__init__` calls `assert_addon_version_matches`
- [ ] `BLENDER_SCREENSHOT_MAX_SIZE = 507` enforced in every screenshot path
- [ ] Tripo batch imports route through `import_tripo_glb_serialized`
- [ ] Boolean ops check vert count before execution
- [ ] Z-up converters called at every Y-up boundary
- [ ] All 6 test files pass

---

### Addendum 1.B — Bundle-level supplements (additions to existing bundles)

Each item below is a binding addition to the original bundle. Appendix D checklists in Addendum 1.D include these.

#### 1.B.1 Bundle A supplements

**Erosion mask preservation (from master plan §13 "The actual material fix"):**

- [ ] `_terrain_erosion.py.apply_hydraulic_erosion_masks` must also populate:
  - `sediment_accumulation_at_base` — float per cell, summed sediment dropped at cliff bases (defined as cells where slope drops > 40° within 3-cell radius)
  - `pool_deepening_delta` — float per cell, extra depth carved at standing-water cells
- [ ] Test `test_terrain_erosion_masks.py` must assert both channels populated and non-zero on a synthetic cliff-with-pool fixture

**`_terrain_world.py` pass refactor additions:**

- [ ] Include a `camera_priority_weight` parameter on `pass_macro_world` that biases macro landform placement toward a provided `camera_priority_zones: List[BBox]`. When set, macro forms within these zones get +0.3 to their macro_saliency score.
- [ ] Every pass function must accept an optional `deterministic_seed_override: Optional[int]` parameter, default None, that bypasses `derive_pass_seed` for debugging and regression isolation

#### 1.B.2 Bundle B supplements

**Material system — Witcher 3 trick extensions (from master plan §14):**

- [ ] `MaterialRuleSet` must support **height-based blending between channels**, not just linear masks. Each `MaterialChannel` gains a `height_blend_gamma: float = 1.0` field controlling exponent of blend ramp.
- [ ] `MaterialRuleSet` must support **texel density coherency** — every material channel carries a `texel_density_m: float` (texels per world meter) and the validator checks coherency within 2× ratio across adjacent channels.
- [ ] **Micro normals separate from displacement** — each `MaterialChannel` optionally references a `micro_normal_texture` that is applied in the shader independently from displacement, so bump detail does not inflate tri count.

```python
@dataclass
class MaterialChannel:
    # ... existing fields from §7.4 ...
    height_blend_gamma: float = 1.0
    texel_density_m: float = 64.0
    micro_normal_texture: Optional[str] = None
    micro_normal_strength: float = 0.8
    respects_displacement: bool = True
```

**Cliff silhouette preservation:**

- [ ] `validate_cliff_readability` must include a silhouette check: render the cliff from the current `ViewportVantage` (Bundle R) and assert the cliff occupies ≥ 8% of rendered pixel area for hero cliffs and ≥ 3% for secondary cliffs.

#### 1.B.3 Bundle C supplements

**3D volumetric waterfall hard contract (from `feedback_waterfall_must_have_volume.md`):**

- [ ] `solve_waterfall_from_river` output must be a **3D tapered prism with rounded front**. Never a 2D plane. This is a hard contract enforced by `validate_waterfall_system`:
  - Vertex count ≥ 48 per meter of drop (prism with rounded front)
  - Aspect ratio: front curvature radius > 0.15 × width
  - No coplanar front face (dot product of front face normals < 0.95 for ≥ 30% of front verts)
- [ ] Add `WaterfallVolumetricProfile` dataclass specifying prism shape parameters
- [ ] Add validator `validate_waterfall_volumetric(chain) -> List[ValidationIssue]`

**Waterfall anchor screen-space region validation:**

- [ ] When a `WaterfallChain` has a linked `TerrainAnchor` with `anchor_kind="waterfall_lip"`, `validate_waterfall_system` must additionally check that the rendered waterfall lip position falls within `anchor.radius` meters of the anchor position in the current `ViewportVantage`. Failing this test emits `WATERFALL_DRIFTED_FROM_ANCHOR`.

**Waterfall split into functional objects (from master plan §12 Blender best practice):**

- [ ] `build_waterfall_chain` produces separate named Blender objects:
  - `WF_<id>_river_surface`
  - `WF_<id>_sheet_volume` (the 3D prism)
  - `WF_<id>_impact_pool`
  - `WF_<id>_foam_layer`
  - `WF_<id>_mist_volume`
  - `WF_<id>_splash_particles` (if `has_particles=True`)
  - `WF_<id>_wet_rock_material_zone`
- [ ] Naming convention enforced by `validate_waterfall_system`

#### 1.B.4 Bundle D supplements

**`terrain_quality_profiles.py` as a full deliverable module (previously only mentioned in §35.3):**

- [ ] Create `handlers/terrain_quality_profiles.py` as a dedicated module
- [ ] Ship 4 preset profiles: `preview`, `production`, `hero_shot`, `aaa_open_world`
- [ ] Profiles stored as JSON under `Tools/mcp-toolkit/presets/terrain/quality_profiles/`
- [ ] Profile schema matches Appendix B.1 of this plan
- [ ] Profile loader: `load_quality_profile(name: str) -> TerrainQualityProfile`
- [ ] Profile inheritance: `production` extends `preview`, `hero_shot` extends `production`, `aaa_open_world` extends `hero_shot`
- [ ] Live hot-reload via Bundle M `terrain_hot_reload.py`

**Checkpoint extensions (from master plan §18):**

- [ ] `terrain_checkpoints.py` must support `save_every_n_operations(n: int)` autosave mode in addition to `autosave_after_pass`
- [ ] Preset lock: `lock_preset(name)` / `unlock_preset(name)` — locked presets raise `PresetLocked` on any mutation attempt
- [ ] Checkpoint naming convention enforced: `terrain_<pass_num:02>_<pass_name>_<short_hash>.blend` (matches master plan example `terrain_01_macro.blend`)
- [ ] Retention policy per profile: preview keeps 5, production keeps 20, hero_shot keeps 40, aaa_open_world keeps 80

#### 1.B.5 Bundle E supplements

**Full asset metadata tag taxonomy (from master plan §15):**

- [ ] Required base tags (location):
  - `cliff`, `riverbank`, `waterfall_base`, `cave_entrance`, `plateau`, `forest_floor`, `beach`, `wetland`, `alpine`, `cultivated`
- [ ] Required role tags:
  - `hero`, `support`, `filler`
- [ ] Required size tags:
  - `large` (> 3m bounding box), `medium` (0.5–3m), `small` (< 0.5m)
- [ ] Required context tags:
  - `silhouette_critical`, `foreground_only`, `mid_distance`, `background_fill`
- [ ] `AssetMetadata` dataclass carrying all four tag categories
- [ ] Validator: every asset ingested via Tripo / Quixel pipelines must have at least one tag in each category

**Scatter rule extensions:**

- [ ] `AssetContextRule` gains `scale_variance_by_role: float = 0.2` field — hero assets get lower variance (more iconic), filler higher variance (breakup)
- [ ] `AssetContextRule` gains `camera_priority_weight: float = 0.0` — higher values bias placement toward the current `ViewportVantage` frustum
- [ ] `place_assets_by_zone` consumes both new fields in its scoring function

#### 1.B.6 Bundle F supplements

**Cave carving workflow (from master plan §13):**

- [ ] `carve_cave_volume` must follow the full pipeline:
  1. Pick archetype
  2. Define path/chamber
  3. Carve volume (existing)
  4. **Remesh / smooth** (new) — `bpy.ops.object.modifier_add(type='REMESH')` at voxel size from profile
  5. **Re-break with rock pattern** (new) — apply stored rock displacement texture via displacement modifier
  6. Build entrance lip (existing)
  7. Add collapse debris (existing)
  8. Add damp mask (existing)
  9. **Add occlusion shelf** (new) — build an overhead shadow shelf mesh at cave mouth that occludes the transition
  10. Validate readability (existing)

- [ ] `build_cave_entrance_frame` supports two workflow modes:
  - `workflow="procedural"` — current boolean-based
  - `workflow="sculpt"` — for hero caves, uses Blender sculpt brushes applied to archetype template meshes; sculpt mode required for primary-tier caves

- [ ] `CaveArchetypeSpec` gains `occlusion_shelf_depth: float = 0.0` and `sculpt_mode: bool = False` fields

#### 1.B.7 Bundle G supplements

**Banded noise advanced techniques (from master plan §12):**

- [ ] `generate_banded_heightmap` adds:
  - `anisotropic_breakup_strength: float = 0.0` parameter — directional-scale noise that breaks up obvious Perlin/Voronoi artifacts
  - `anti_grain_smoothing: bool = True` parameter — low-frequency Gaussian smoothing to kill "pixel grain" artifact from noise octaves
- [ ] Add `compute_anisotropic_breakup(base: np.ndarray, direction: Tuple[float, float], strength: float) -> np.ndarray` helper
- [ ] Add `apply_anti_grain_smoothing(heightmap: np.ndarray, sigma: float = 0.8) -> np.ndarray` helper
- [ ] Both applied to every band in `BandedHeightmap`, not just composite

#### 1.B.8 Bundle N supplements

**Terrain-semantic visual verification (closes Gap #2 from final audit, Bug Audit #8):**

- [ ] `terrain_readability_bands.py` augmented with semantic checks on top of image stats:
  - `check_cliff_silhouette_readability` — cliffs visible at 100m have discernible lip/face boundary
  - `check_waterfall_chain_completeness` — every visible waterfall has rendered source + lip + pool + outflow
  - `check_cave_framing_presence` — every visible cave has at least 2 framing rocks + damp signal
  - `check_focal_composition` — focal point occupies rule-of-thirds intersection in ≥ 1 reviewed band
- [ ] `run_readability_audit` calls all four semantic checks AND image-stat checks; hard fail on any terrain-semantic failure
- [ ] Image-stat-only verification mode permanently deprecated

#### 1.B.9 §33 (Unity Export Contract) supplements

**Bit-depth precision contract:**

- [ ] `heightmap.exr` must be **32-bit float**. 16-bit fallback permitted only when `quality_profile == "preview"`
- [ ] `mask_stack.npz` channels preserve their source dtype (no silent downcasting)
- [ ] `shadow_clipmap.exr` must be **32-bit float**
- [ ] `splatmap.exr` minimum **16-bit per channel** for 4+ material channels
- [ ] Manifest file must record bit depth per exported file: `{"bit_depth": 32, "channels": 1, "encoding": "float"}`

**Attribute-driven geometry nodes contract:**

- [ ] Every terrain mesh exported must carry these named attributes:
  - `slope_angle` (float, per-vertex, radians)
  - `flow_accumulation` (float, per-vertex, log)
  - `wetness` (float, per-vertex, 0..1)
  - `biome_id` (int, per-vertex)
  - `cliff_mask` (bool, per-vertex)
  - `protected_zone_id` (int, per-vertex, -1 = none)
- [ ] Attributes are source-of-truth for Unity shader + geometry node consumption

#### 1.B.10 §34 (Anti-patterns) additions

New entries 16–25:

- 16. **Skipping scene_read before mutation** — no terrain mutation may proceed without a fresh `TerrainSceneRead`. Enforced by `ProtocolGate.rule_1`.
- 17. **Ignoring user viewport** — mutations must sync to the current `ViewportVantage` unless explicitly tagged `out_of_view_ok=True`.
- 18. **Drifting anchors** — locked anchors may not be moved by any pass. Detected by `assert_anchor_integrity`.
- 19. **Vertex-color fakes for hero features** — cliffs, caves, waterfalls must be real geometry. Forbidden by `ProtocolGate.rule_4`.
- 20. **Bulk edits without flag** — any mutation touching > 2% of a tile or > 20 objects without `bulk_edit=True` is rejected.
- 21. **Placement-class mismatch** — objects placed at a cave mouth tagged `surface` instead of `cave_entrance` are rejected.
- 22. **Y-up coordinates** — Blender is Z-up. Any transform setter that uses Y as vertical is forbidden. Every Y-up boundary must call `convert_y_up_to_z_up`.
- 23. **Screenshot max_size > 507** — clamped by `clamp_screenshot_size`. Never 1024.
- 24. **Boolean ops on ≥ 60k vert meshes without decimation** — forbidden by `assert_boolean_safe`. Decimate cutter first.
- 25. **Batch Tripo GLB imports** — must be serialized via `import_tripo_glb_serialized`. Batch crashes Blender.
- 26. **2D plane waterfalls** — waterfalls must be 3D tapered prisms with rounded fronts. Enforced by `validate_waterfall_volumetric`.
- 27. **Image-stat-only visual verification** — deprecated after Bundle N. Terrain-semantic checks required.
- 28. **Addon stale execution** — `TerrainPassController` init calls `assert_addon_version_matches`; stale addons refuse to run passes.
- 29. **Biome-coarse material assignment** — materials must consume slope/curvature/wetness/flow, not just biome id. (Already covered in Bundle B but reiterated as anti-pattern.)
- 30. **Unscoped corrections** — correction requests must follow the "Failures: 1... 2... Fix only these" format and carry a region bounds.

#### 1.B.11 §35 (Operational concerns) additions

**Real-time edit → view → refine workflow (from `feedback_realtime_editing_scalability.md`):**

- [ ] `terrain_live_preview.py` (Bundle M) must support **modular piece isolation** — edit a single hero feature (cliff, waterfall, cave) without re-running the whole pipeline
- [ ] Edit scope derivation: given a hero feature id, automatically compute the minimum region bbox + affected passes
- [ ] Piece cache: per-feature masks and geometry snapshots cached so regeneration of unrelated features is skipped
- [ ] `edit_hero_feature(feature_id, mutations: List[Mutation])` orchestrates modular editing

**Tile-based erosion policy (from master plan §18):**

- [ ] Add `ErosionStrategy` enum: `EXACT` (full world erosion, expensive, deterministic), `TILED_PADDED` (per-tile with erosion margin padding, scalable, approximate)
- [ ] `TerrainQualityProfile.erosion_strategy` field selects strategy
- [ ] `preview` and `production` default to `TILED_PADDED`, `hero_shot` and `aaa_open_world` default to `EXACT`
- [ ] Erosion margin padding size configurable per profile (default 16 cells, master plan's recommendation)

**Splatmap GPU edge bleed prevention (from master plan §19):**

- [ ] Splatmap export pads per-tile by 4 texels on every edge with copied edge color
- [ ] Unity sampler reads with `clamp_to_edge` addressing
- [ ] Validator checks border continuity between adjacent tiles' splatmaps within tolerance

**Water channel layering (from master plan §12 Blender best practice):**

- [ ] Water meshes split by function:
  - Main flow layer (flat surface)
  - Ripple layer (animated displacement)
  - Localized turbulence patches (high-curvature zones at bends, pools)
- [ ] Each is a separate object with distinct materials
- [ ] Foam layer exists only at impact/turbulence zones, not globally

---

### Addendum 1.C — Updated scorecard

Adding Bundle R and the supplements raises realistic ceiling from 8.7 to **8.8**. Bundle R contributes:

- Autonomy / pass discipline: 9 → 9 (holds the line, but now actually enforced)
- Validation depth: 9 → 9 (terrain-semantic checks close the image-stat gap)
- Operational safety: new pillar, 9/10

Total bundles: **18** (A–R). Total estimated sessions: **58–63** (was 55–60).

---

### Addendum 1.D — Supplemental compliance checklists

Future sessions mark these in place.

#### D.18 Bundle R — Protocol Enforcement & Runtime Safety

- [ ] `terrain_protocol.py` created
- [ ] `@enforce_protocol` decorator implemented
- [ ] All 7 `ProtocolGate` rules implemented
- [ ] `terrain_viewport_sync.py` created
- [ ] `ViewportVantage` dataclass + `read_user_vantage` + `assert_vantage_fresh` + frustum helpers
- [ ] `terrain_reference_locks.py` created
- [ ] `lock_anchor` / `unlock_anchor` / `assert_anchor_integrity` / `assert_all_anchors_intact`
- [ ] `terrain_addon_health.py` created
- [ ] `assert_addon_version_matches` / `assert_handlers_registered` / `detect_stale_addon` / `force_addon_reload`
- [ ] `TerrainPassController.__init__` calls `assert_addon_version_matches`
- [ ] `terrain_blender_safety.py` created
- [ ] Z-up enforcement (`assert_z_is_up`, `convert_y_up_to_z_up`, `@guard_z_up`)
- [ ] Screenshot clamp (`BLENDER_SCREENSHOT_MAX_SIZE = 507`, `clamp_screenshot_size`)
- [ ] Boolean safety (`assert_boolean_safe`, `decimate_to_safe_count`, `run_boolean_with_safety`)
- [ ] Tripo serialization (`import_tripo_glb_serialized` with lock)
- [ ] `terrain_scene_read.py` created
- [ ] `capture_scene_read` handler produces valid `TerrainSceneRead`
- [ ] 6 test files created, all passing

Status: **COMPLETE** (commits f467f33..8eda364)

#### D.1 additions (Bundle A)

- [ ] `apply_hydraulic_erosion_masks` populates `sediment_accumulation_at_base`
- [ ] `apply_hydraulic_erosion_masks` populates `pool_deepening_delta`
- [ ] `pass_macro_world` accepts `camera_priority_weight` parameter
- [ ] Every pass function accepts `deterministic_seed_override` parameter
- [ ] Regression tests for both new erosion channels

#### D.2 additions (Bundle B)

- [ ] `MaterialChannel.height_blend_gamma` field
- [ ] `MaterialChannel.texel_density_m` field
- [ ] `MaterialChannel.micro_normal_texture` + `micro_normal_strength` fields
- [ ] Texel density coherency validator
- [ ] `validate_cliff_readability` includes silhouette area check

#### D.3 additions (Bundle C)

- [ ] `WaterfallVolumetricProfile` dataclass
- [ ] `validate_waterfall_volumetric` validator
- [ ] Vertex count ≥ 48 per meter enforcement
- [ ] Non-coplanar front face check
- [ ] Anchor screen-space region validator
- [ ] Waterfall split into 7 named functional objects

#### D.4 additions (Bundle D)

- [ ] `terrain_quality_profiles.py` dedicated module created
- [ ] 4 preset JSON files shipped (preview / production / hero_shot / aaa_open_world)
- [ ] Profile inheritance implemented
- [ ] `save_every_n_operations` autosave mode
- [ ] `lock_preset` / `unlock_preset` + `PresetLocked` exception
- [ ] Checkpoint naming convention `terrain_<NN>_<pass>_<hash>.blend`
- [ ] Retention policy per profile

#### D.5 additions (Bundle E)

- [ ] `AssetMetadata` dataclass with 4 tag categories
- [ ] All 10 location tags defined
- [ ] All 3 role tags defined
- [ ] All 3 size tags defined
- [ ] All 4 context tags defined
- [ ] Asset ingestion validator enforces all 4 tag categories
- [ ] `scale_variance_by_role` + `camera_priority_weight` on `AssetContextRule`
- [ ] `place_assets_by_zone` consumes both new fields

#### D.6 additions (Bundle F)

- [ ] `carve_cave_volume` implements 10-step pipeline including remesh + re-break + occlusion shelf
- [ ] `build_cave_entrance_frame` supports sculpt workflow for hero tier
- [ ] `CaveArchetypeSpec.occlusion_shelf_depth` + `sculpt_mode` fields

#### D.7 additions (Bundle G)

- [ ] `generate_banded_heightmap` adds `anisotropic_breakup_strength`
- [ ] `generate_banded_heightmap` adds `anti_grain_smoothing`
- [ ] `compute_anisotropic_breakup` helper
- [ ] `apply_anti_grain_smoothing` helper
- [ ] Both applied to every band, not just composite

#### D.14 additions (Bundle N)

- [ ] `check_cliff_silhouette_readability`
- [ ] `check_waterfall_chain_completeness`
- [ ] `check_cave_framing_presence`
- [ ] `check_focal_composition`
- [ ] `run_readability_audit` calls all 4 semantic checks as hard gates
- [ ] Image-stat-only verification deprecated

#### §33 additions (Unity export)

- [ ] `heightmap.exr` is 32-bit float in production+ profiles
- [ ] `mask_stack.npz` preserves dtype
- [ ] `shadow_clipmap.exr` is 32-bit float
- [ ] `splatmap.exr` is 16-bit minimum
- [ ] Manifest records per-file bit depth
- [ ] Every terrain mesh exports 6 required named attributes

#### §34 additions (anti-patterns)

- [ ] Entries 16–30 added (see Addendum 1.B.10)

#### §35 additions (operational)

- [ ] Real-time edit → view → refine workflow in Bundle M
- [ ] Modular piece isolation
- [ ] Piece cache
- [ ] `edit_hero_feature(feature_id, mutations)` orchestrator
- [ ] `ErosionStrategy` enum with EXACT vs TILED_PADDED
- [ ] Erosion margin padding per profile
- [ ] Splatmap edge bleed padding (4-texel border)
- [ ] Water channel layering (main flow, ripple, turbulence, foam)

---

### Addendum 1.E — Verification checklist (this addendum's completeness)

This list confirms each identified gap is closed by Addendum 1. Every item must be ticked when the addendum is committed.

- [x] **Gap 1 — Runtime protocol enforcement** → Bundle R, `terrain_protocol.py` + `ProtocolGate`
- [x] **Gap 2 — Terrain-semantic visual verification** → Bundle N supplement 1.B.8
- [x] **Gap 3 — Addon reload enforcement** → Bundle R, `terrain_addon_health.py`
- [x] **Gap 4 — Viewport sync + reference locking** → Bundle R, `terrain_viewport_sync.py` + `terrain_reference_locks.py`
- [x] **Gap 5 — Semantic mask consumer logic (materials)** → Bundle B supplement 1.B.2
- [x] **Gap 6 — Terrain-aware scatter** → Bundle E supplement 1.B.5
- [x] **Gap 7 — Flow analysis semantic outputs** → Bundle A supplement 1.B.1 (sediment accumulation, pool deepening)
- [x] **Gap 8 — Real-time edit → view → refine modular workflow** → Bundle M extension 1.B.11
- [x] **Gap 9 — 3D volumetric waterfall** → Bundle C supplement 1.B.3
- [x] **Gap 10 — Tripo + dense mesh boolean safety** → Bundle R, `terrain_blender_safety.py`
- [x] **Gap 11 — terrain_quality_profiles.py as dedicated module** → Bundle D supplement 1.B.4
- [x] **Gap 12 — Noise anisotropic breakup + anti-grain smoothing** → Bundle G supplement 1.B.7
- [x] **Gap 13 — Erosion sediment accumulation at bases + pool deepening** → Bundle A supplement 1.B.1
- [x] **Gap 14 — Cave remesh / re-break / occlusion shelf / sculpt workflow** → Bundle F supplement 1.B.6
- [x] **Gap 15 — Waterfall anchor screen-space region validation** → Bundle C supplement 1.B.3
- [x] **Gap 16 — Material height-based blends + texel density + micro normals** → Bundle B supplement 1.B.2
- [x] **Gap 17 — Full asset tag taxonomy** → Bundle E supplement 1.B.5
- [x] **Gap 18 — Scatter scale variance + camera priority** → Bundle E supplement 1.B.5
- [x] **Gap 19 — Checkpoint save every N + lock preset + naming** → Bundle D supplement 1.B.4
- [x] **Gap 20 — Export bit-depth contract (16/32-bit)** → §33 supplement 1.B.9
- [x] **Gap 21 — Attribute-driven geometry nodes export** → §33 supplement 1.B.9
- [x] **Gap 22 — Water layer split (flow/ripple/turbulence)** → §35 supplement 1.B.11
- [x] **Gap 23 — Camera-priority weighting in macro_world** → Bundle A supplement 1.B.1
- [x] **Gap 24 — Z-up coordinate enforcement** → Bundle R, `terrain_blender_safety.py`
- [x] **Gap 25 — Screenshot max_size 507 cap** → Bundle R, `terrain_blender_safety.py`
- [x] **Gap 26 — Blender boolean dense-mesh crash avoidance** → Bundle R, `terrain_blender_safety.py`
- [x] **Gap 27 — Large-world tiled erosion policy (EXACT vs TILED_PADDED)** → §35 supplement 1.B.11
- [x] **Gap 28 — Splatmap GPU edge bleed padding** → §35 supplement 1.B.11
- [x] **Gap 29 — Cliff silhouette area validator** → Bundle B supplement 1.B.2
- [x] **Gap 30 — Anti-patterns 16–30** → §34 supplement 1.B.10

All 30 gaps closed by this addendum.

---

## Addendum 2 — Deeper Gap Closure (2026-04-08, second revision)

After committing Addendum 1, a deeper audit against `docs/terrain_pipeline_handoff_for_claude.md` (994 lines, previously only partially read) and a full re-audit of `docs/terrain_tool_bug_audit_2026-04-07.md` surfaced 26 additional items. All are closed by Addendum 2.

This addendum is binding with the same authority as sections 1–41 and Addendum 1.

---

### Addendum 2.A — Architectural contract clarifications

These are non-negotiable mathematical and structural contracts the handoff doc enumerated but Addendum 1 did not explicitly pin.

#### 2.A.1 Tile resolution contract

- **Tile dimensions:** A tile heightmap is `(tile_size + 1) × (tile_size + 1)` cells, where `tile_size` is one of `{256, 512, 1024}` (power-of-2).
- **Valid Unity-compatible tile sizes:** 257, 513, 1025 vertices per side (power-of-2+1).
- **Shared edge vertices:** The last vertex column of `Tile(tx, ty)` and the first vertex column of `Tile(tx+1, ty)` sample the **same world coordinate** and therefore hold identical heights by construction. Same for rows between `Tile(tx, ty)` and `Tile(tx, ty+1)`.
- **Corner sharing:** The `(tile_size, tile_size)` corner of `Tile(tx, ty)`, the `(0, tile_size)` corner of `Tile(tx+1, ty)`, the `(tile_size, 0)` corner of `Tile(tx, ty+1)`, and the `(0, 0)` corner of `Tile(tx+1, ty+1)` all sample the same world coordinate.
- **This is why stitching is fallback-only:** with a deterministic world field + consistent normalization, seams match by construction. Stitching exists only for sub-mm FP artifacts, LOD mismatch, and import precision loss.

Enforced in `TerrainMaskStack.__post_init__` by asserting `height.shape == (tile_size + 1, tile_size + 1)` when `tile_size` is set. Added to the dataclass contract in §5.1.

#### 2.A.2 fBm theoretical max amplitude formula

Global normalization constant for deterministic, per-tile-invariant height scaling:

```python
def theoretical_max_amplitude(persistence: float, octaves: int) -> float:
    """Deterministic max amplitude for fBm normalization.

    Per-tile [0,1] normalization breaks tiling because different tiles
    sample different local maxima. Using this theoretical upper bound as
    the global normalization constant makes height values identical across
    tiles for the same world coordinate."""
    if abs(persistence - 1.0) < 1e-10:
        return float(octaves)
    return (1.0 - persistence ** octaves) / (1.0 - persistence)
```

- Added to `Bundle G` (`_terrain_noise.py` refactor) as a required helper.
- Every fBm-based generator must either call this or use the `world_unit` mode that bypasses normalization entirely.
- Anti-pattern: per-tile `(h - h.min()) / (h.max() - h.min())` normalization is forbidden in any multi-tile code path.

#### 2.A.3 Erode-before-split rationale

Per-tile erosion with overlap margins cannot guarantee bit-exact seams because droplet random walks are independent per tile. Erode-before-split solves this deterministically:

```
generate_world_heightmap(full_region) -> world_hmap
apply_flatten_zones(world_hmap)           # building foundations
apply_canyon_river_carves(world_hmap)     # A* paths on world
erode_world_heightmap(world_hmap)          # full region erosion
compute_flow_map(world_hmap)               # drainage on full world
detect_cliff_edges(world_hmap)             # cliff placement list

for each tile (tx, ty):
    tile_heightmap = extract_tile(world_hmap, tx, ty, tile_size)
    tile_flow_map  = extract_tile(world_flow, tx, ty, tile_size)
    # per-tile mesh, biome paint, cliff overlays, scatter
```

- Flow maps, moisture proxies, deposition masks, wetness masks, bank instability, talus, and cliff candidate masks are **all computed on the full world heightmap before tile split** and then extracted per-tile using the same `extract_tile` mechanism as heights.
- Reason: flow, drainage, deposition all cross tile boundaries. Per-tile computation truncates drainage basins at tile edges.
- Tests T1, T2, T3 from §2.H enforce this.

#### 2.A.4 World expansion strategy

When adding `Tile(2, 0)` to an existing `2×2` world:

1. **Same seed + world-space noise = deterministic.** Regenerating the full `3×2` world heightmap produces bit-identical values in the original `2×2` region.
2. **Erode-before-split requires re-eroding the expanded region.** The original 2×2 erosion result is NOT reusable because the new tile changes drainage patterns at the boundary.
3. **Production approach:** regenerate + re-erode the full region every expansion. For a 10×10 world at 257 cells/tile (2570×2570 heightmap), this is ~5 seconds and is acceptable.
4. **Optional optimization:** store pre-erosion world heightmap on disk, extend it in-place on expansion, and re-erode only. Or use overlap+blend in erosion for the new tiles only. These optimizations ship with Bundle M (iteration velocity) when the basic flow is stable.

Added as `Bundle M.1.B.11` supplement.

#### 2.A.5 Noise repeat distance

The fallback Perlin implementation (`_PermTableNoise` in `_terrain_noise.py`) uses a 256-element permutation table with `& 255` wrapping. Noise **repeats every 256 grid cells**. At default `scale=100.0`, the repeat distance is `256 × scale = 25,600` world units (25.6 km).

- For worlds ≤ 25 km, the repeat is invisible.
- For worlds > 25 km: override `noise2_array()` in `_OpenSimplexWrapper` to use the real `opensimplex` backend (hash-based, never repeats), or increase the permutation table size.
- Added to `Bundle G` acceptance: if `opensimplex` is installed, the banded noise pipeline must use it for `noise2_array`, not the PermTable fallback.

#### 2.A.6 Erosion math scaling direction

When removing the `np.clip(result, 0, 1)` from `apply_hydraulic_erosion`:

- **`capacity`** (default 4.0) — DO NOT scale. Height differences grow automatically with `height_range`, so sediment carrying scales proportionally without adjustment.
- **`min_slope`** (default 0.01) — SCALE by `height_range`. In `[0,1]` it was "1% of max height"; in world units it should become `0.01 × height_range` (e.g., 0.2 on a 20m terrain) to preserve the proportional threshold.

```python
def apply_hydraulic_erosion_masks(
    heightmap: np.ndarray,
    *,
    height_range: Optional[float] = None,
    capacity: float = 4.0,
    min_slope: float = 0.01,
    ...
) -> ErosionMasks:
    effective_min_slope = min_slope * height_range if height_range else min_slope
    # capacity remains unchanged
    ...
```

Pinned in `Bundle A` supplements (Addendum 2.D.1).

#### 2.A.7 Canonical 12-step `handle_generate_world_terrain` sequence

Binding execution order. Every implementation of the world-terrain orchestrator must follow this sequence:

```
1.  Parse params: tile_grid, cell_size, seed, terrain_type, intent state
2.  Compute world region: total_samples_x = tile_grid_x * tile_size + 1
3.  generate_world_heightmap() -> world heightmap in WORLD UNITS
4.  Apply flatten zones on world heightmap (building foundations)
5.  Apply canyon/river carving on world heightmap (A* paths)
6.  erode_world_heightmap() -> eroded heightmap + ErosionMasks
7.  compute_flow_map() on eroded world heightmap -> flow, drainage
8.  detect_cliff_edges(), detect_cave_candidates(), detect_waterfall_lip_candidates()
    on world heightmap -> candidate lists
9.  FOR EACH tile (tx, ty):
    9a. extract_tile(world_heightmap, tx, ty)
    9b. extract_tile(world_flow_map, tx, ty)
    9c. extract_tile(world_erosion_masks, tx, ty) for every mask channel
    9d. create_terrain_tile_mesh() at world position
    9e. paint_biome_materials() using world-space rules
    9f. generate cliff overlay meshes at world positions
    9g. scatter vegetation (world-space Poisson disk)
    9h. scatter props (world-space context scatter)
10. Generate road meshes in world space (span tiles)
11. Generate water bodies in world space (span tiles)
12. validate_tile_seams() on all adjacent pairs; return tile list + metadata
```

Steps 3–8 operate on the **full world heightmap** before splitting. Steps 9a–9h operate **per-tile**. Steps 10–11 operate in **world space across all tiles**. Step 12 is a hard gate.

Added to `Bundle A` as a mandatory test: `test_terrain_world_orchestration.py` asserts this exact sequence on a 2×2 fixture.

#### 2.A.8 "Generate Adjacent Tile" contract

When a user generates `Tile(1, 0)` next to existing `Tile(0, 0)`, the pipeline must satisfy all 10 requirements:

| Requirement | How it's met |
|---|---|
| Same heights at shared edge | Same seed + world-space noise → identical values at shared coordinates |
| No per-tile normalization drift | `theoretical_max_amplitude()` global constant |
| Connected erosion | Erode-before-split on full multi-tile region |
| Consistent biome painting | World-space altitude/slope rules |
| Continuous vegetation | World-space Poisson disk, same seed |
| Roads can span tiles | World-space road network, mesh in world coords |
| Rivers can span tiles | A* on world heightmap, carve before split |
| No stitching needed | Correct contract → edges match by construction |
| Compatible LOD | Shared edge vertices + skirts for mixed LOD |
| Resolution matches Unity | Power-of-2+1 (257, 513, 1025) |

Enforced by `test_adjacent_tile_contract.py` in Bundle A test suite.

---

### Addendum 2.B — Extended bug fix list

#### 2.B.1 Bug #4 extended: ALL `[0,1]` clips in `terrain_advanced.py`

Addendum 1 covered lines 896 and 1530. The bug audit lists four clip sites total:

- `terrain_advanced.py:793` — must be audited and removed if clipping world-unit heights
- `terrain_advanced.py:896` — `compute_erosion_brush` return clip (already in Bundle B)
- `terrain_advanced.py:1483` — must be audited and removed if clipping world-unit heights
- `terrain_advanced.py:1530` — `flatten_terrain_zone` return clip (already in Bundle B)

Bundle B acceptance updated: all four sites audited; clips removed from world-unit paths; if an editing path genuinely requires normalized domain, wrap it with explicit normalize→edit→de-normalize steps.

Extended consumer audit:

- `handle_erosion_paint()` — builds a mesh-derived heightmap and feeds it through `compute_erosion_brush()`; must route through new contract
- `handle_terrain_flatten_zone()` — used for building foundations; must honor world-unit heights
- `flatten_multiple_zones()` — same requirement as above
- Docstrings in `terrain_advanced.py` that describe heightmaps as "normalized `[0,1]`" must be updated to "world-unit meters"

**Decision:** pick world-unit everywhere. The normalize-wrapper path is explicitly forbidden because it reintroduces per-region normalization state that violates determinism. If a legacy caller requires the old domain, that caller is migrated, not the helper.

Added regression tests:

- `test_terrain_advanced_world_units.py` — on every helper, assert world-unit heights pass through unchanged
- `test_handle_erosion_paint_preserves_scale.py` — build a mesh with max height 47.3, run erosion paint, assert result max ≤ 47.3 within erosion tolerance
- `test_flatten_multiple_zones_preserves_scale.py` — same for flatten zones

#### 2.B.2 Bug #9: Metadata contract fix — `object_location` vs `position`

Current state in `environment.py:1005, 1008, 1148, 1152` — the tile handler returns BOTH `object_location` (center of mesh) and `position` (min corner bounds). Downstream consumers have no way to know which to use.

**Decision:** single canonical contract. Every tile handler must return:

```python
{
    "tile_transform": {
        "origin_world": [x, y, z],        # Blender object.location — authoritative
        "min_corner_world": [x, y, z],    # bbox min in world coords
        "max_corner_world": [x, y, z],    # bbox max in world coords
        "tile_coords": [tile_x, tile_y],
        "tile_size_world": float,          # cells * cell_size
        "convention": "object_origin_at_min_corner",  # or "object_origin_at_center"
    },
    # ... rest of result ...
}
```

- `tile_transform.origin_world` is the Blender `object.location` of the tile mesh. This is the **single source of truth** for "where is this tile in the world".
- `min_corner_world` and `max_corner_world` are derived bbox values. Consumers use these for range queries but MUST NOT use them as the mesh origin.
- `convention` makes the coordinate interpretation explicit so downstream tooling cannot guess.
- Old `object_location` and `position` keys are removed in Bundle A. Backwards-compat shim in `environment.py` emits a deprecation warning if a caller asks for them.

Added to Bundle A compliance (`§D.1 additions`).

---

### Addendum 2.C — Migration gaps (legacy code paths)

The handoff doc enumerated dangerous legacy paths still active. These must be migrated or neutralized as part of the bundles that touch the affected files.

#### 2.C.1 Legacy curve-road path (4 active callers, `worldbuilding.py`)

Bundle R supplement (new): neutralize the curve-road path because it creates CURVE+bevel cylinders that look like pipe segments.

- `worldbuilding.py:6144` — `handle_generate_location` roads → migrate to `_create_road_with_curbs`
- `worldbuilding.py:6575` — `handle_generate_settlement` narrow road fallback → migrate to `_create_road_with_curbs`
- `worldbuilding.py:6796` — `handle_compose_world_map` world map roads → migrate to `_create_road_with_curbs`
- `worldbuilding.py:3535` — `_create_curve_from_points` wrapper → dead code, delete
- Mark `_create_curve_path` with `@deprecated`; remove after all four callers migrated
- Regression test: `test_worldbuilding_no_curve_roads.py` greps the module for `bpy.ops.curve.primitive_bezier_curve_add` and other curve-creation idioms, fails if any survive

Added as Bundle R compliance item.

#### 2.C.2 Box/cube fallbacks that hide failures

Two fallback paths create 8-vertex cubes when generation raises, hiding regressions. Both removed:

- `worldbuilding_layout.py:621-658` — Hearthvale building fallback → replace with explicit error logging + skip (never create a cube proxy)
- `worldbuilding_layout.py:715-738` — Perimeter wall fallback → replace with explicit error logging + skip

Rationale: silent fallbacks hide regressions. AAA validation requires failures to surface loudly, not masquerade as successes.

Added as Bundle D compliance item (Bundle D owns validation / hard-fail philosophy).

#### 2.C.3 Multi-biome path alignment

`environment.py:1213 handle_generate_multi_biome_world` is a SECOND full terrain orchestrator that:

1. Builds world spec from `_biome_grammar.generate_world_map_spec()`
2. Calls `handle_generate_terrain()`
3. Applies Voronoi biome vertex colors and materials
4. At `environment.py:1321-1324`, imports and calls `scatter_biome_vegetation` (the mesh-backed helper)

**Risk:** if Bundle A routes `handle_generate_terrain` through the new pipeline but leaves this multi-biome orchestrator untouched, the multi-biome path silently bypasses all new passes.

**Action:** in Bundle A, `handle_generate_multi_biome_world` is refactored to call the new `TerrainPassController.run_pipeline()` with the biome grammar output as the `TerrainIntentState.biome_rules` field. Backwards compatibility maintained via a minimal pipeline: `macro_world → structural_masks → erosion → material_zoning → asset_population`.

Regression test: `test_multi_biome_world_regression.py` asserts `handle_generate_multi_biome_world` still produces a valid scene and now populates the mask stack.

Added as Bundle A compliance item.

#### 2.C.4 Worldmap composer path (third orchestrator)

`__init__.py:991` registers `world_compose_world_map` → `worldbuilding.handle_compose_world_map`. This is a THIRD terrain orchestration path. Not called from `compose_map` but callable directly via MCP.

**Action:** low priority — this path is not in the main flow. Must be updated when curve-road migration (2.C.1) lands because it's one of the four curve-road callers. Otherwise no action required.

Added as a Bundle R compliance note (not a hard item).

---

### Addendum 2.D — Vegetation type mapping

The handoff doc identified 14 missing vegetation types in `VEGETATION_GENERATOR_MAP`. Four are critical (used by default biome rules), ten are deferred.

#### 2.D.1 Critical aliases to add in Bundle A supplement

Add to `VEGETATION_GENERATOR_MAP` in `_mesh_bridge.py`:

| Type | Biome users | Map to |
|---|---|---|
| `fern` | thornwood_forest, deep_forest ground cover | `generate_shrub_mesh(size=0.3, branch_count=5)` |
| `moss` | thornwood_forest, corrupted_swamp, 4+ biomes | `generate_grass_clump_mesh(blade_count=12, height=0.08, spread=0.2)` |
| `vine` | thornwood_forest, corrupted_swamp | `generate_root_mesh(size=0.4)` |
| `dead_tree` | `_TREE_VEG_TYPES` in environment_scatter.py | `_lsystem_tree_generator(tree_type="dead", iterations=4, leaf_type=None)` |

#### 2.D.2 Deferred aliases (add when biomes are active)

| Type | Biome | Map to |
|---|---|---|
| `gravestone` | cemetery | Custom mesh (not terrain scope — defer to asset pipeline) |
| `ember_plant` | ashen_wastes | `generate_mushroom_mesh` variant |
| `frost_lichen` | frozen_hollows | `generate_grass_clump_mesh` variant |
| `tumbleweed` | desert | `generate_grass_clump_mesh` variant |
| `crystal` | crystal_cavern | `generate_rock_mesh` variant |
| `ivy_growth` | building overrun | defer — building scope |
| `moss_patch` | building overrun | defer — building scope |
| `vine_curtain` | building overrun | defer — building scope |
| `root_intrusion` | building overrun | defer — building scope |
| `fern_growth` | building overrun | defer — building scope |

Added as Bundle A compliance item (4 critical aliases) and Bundle E deferred registry (10 deferred).

---

### Addendum 2.E — Terrain feature generator wiring

The handoff doc noted **11 pure-logic feature generators** that return `MeshSpec` dicts but are NOT called by `compose_map`. Each needs explicit wiring in the pass-based pipeline.

#### 2.E.1 Wire in this plan (mapped to bundles)

| Generator | File:Line | Bundle | Pass |
|---|---|---|---|
| `generate_cliff_face()` | terrain_features.py:446 | B | `hero_features` + `structural_geometry` |
| `generate_canyon()` | terrain_features.py:69 | B + H | morphology template (`canyon`) + heightmap carve before erosion |
| `generate_waterfall()` | terrain_features.py:254 | C | `water_network` pass (fallback only; WaterNetwork-derived is primary) |
| `generate_coastline()` | coastline.py:433 | I | `coastal` submodule |
| `generate_cave_entrance_mesh()` | _terrain_depth.py:200 | F | `structural_geometry` pass |
| `generate_natural_arch()` | terrain_features.py:? | H | morphology template (`natural_bridge`) |
| `generate_swamp_terrain()` | terrain_features.py:? | O | `build_wetlands` |
| `generate_geyser()` | terrain_features.py:? | O | `build_hot_springs` |
| `generate_sinkhole()` | terrain_features.py:? | I | `terrain_karst` (sinkhole archetype) |
| `generate_floating_rocks()` | terrain_features.py:? | Deferred | specialized fantasy biome, not AAA baseline |
| `generate_ice_formation()` | terrain_features.py:? | I | glacial module extension |
| `generate_lava_flow()` | terrain_features.py:? | Deferred | specialized biome |

Every "wire in bundle X" item becomes a compliance checklist entry in that bundle's acceptance criteria.

#### 2.E.2 MeshSpec return contract

All 11 generators return:

```python
{
    "mesh": {"vertices": [(x,y,z), ...], "faces": [(v0,v1,v2,...), ...]},
    "materials": ["mat_name1", ...],
    "material_indices": [0, 1, ...],
    "vertex_count": int,
    "face_count": int,
    # Feature-specific keys: floor_path, side_caves, steps, pool, etc.
}
```

All use **LOCAL coordinates** (origin at base/center). Callers MUST position in world space via `mesh_from_spec(spec, location=(world_x, world_y, world_z))`. This is the canonical pattern; any caller that bakes world coords into the MeshSpec is a bug.

Added to Bundle A as a `contract invariant` — every feature generator wiring must use `mesh_from_spec` with explicit world location.

---

### Addendum 2.F — Centered-terrain assumptions (13 specific locations)

The handoff doc enumerated 13 centered-terrain assumptions that must be fixed for offset tiles to work. Each is a specific line:line fix.

#### 2.F.1 `environment.py` (3 locations)

| Line | Code | Fix |
|---|---|---|
| 471 | `u = (vert.co.x + terrain_size / 2.0) / terrain_size` | Add `obj.location` awareness for UV on offset tiles |
| 930-934 | Water fallback: `(0.0, -fallback_depth/2.0, water_level)` | Center fallback water on `terrain_obj.location` |
| 1373-1374 | `nx = int((vx / world_size + 0.5) * cols)` in `_compute_vertex_colors_for_biome_map` | Subtract `obj.location` before mapping |

#### 2.F.2 `environment_scatter.py` (4 locations)

| Line | Code | Fix |
|---|---|---|
| 287-290 | `u = (world_x + half_size) / terrain_size` | Subtract `terrain_obj.location.x` |
| 1050 | `terrain_half = terrain_size / 2.0` for Poisson disk | Add terrain location offset |
| 1348-1349 | `wx = p["position"][0] - terrain_half_bz` | Add terrain location offset |
| 1389-1403 | `terrain_half` used for instance positioning | Add `terrain_obj.location` to world position |

#### 2.F.3 `terrain_advanced.py` (3 locations)

| Line | Code | Fix |
|---|---|---|
| 742 | `terrain_size = (dims.x, dims.y)` for layer ops | Pass `obj.location` to brush/layer functions |
| 944 | `terrain_size = (dims.x, dims.y)` for erosion brush | Adjust `brush_center` by subtracting `obj.location` |
| 1353 | `terrain_size = (dims.x, dims.y)` for stamp | Adjust stamp position by subtracting `obj.location` |

#### 2.F.4 `blender_server.py` (3 locations)

| Line | Code | Fix |
|---|---|---|
| 179 | `half = terrain_size / 2.0` in `_normalize_map_point` | Add `terrain_location` parameter |
| 199 | `(y + half) / terrain_size` in `_map_point_to_terrain_cell` | Account for terrain offset |
| 212 | `half = terrain_size / 2.0` in `_plan_map_location_anchors` | Candidate positions need world offset |

**Total: 13 centered-terrain assumptions.** Each becomes a compliance checklist entry in Bundle A with line number + expected fix.

#### 2.F.5 Already-safe modules

- `vegetation_system.py` — already offset-aware at line 724 via `obj.location`. No changes needed.
- `_shared_utils.py` — `safe_place_object` at line 34 uses world-space raycasts. No changes needed.

Documented in Bundle A as "do not touch — already correct."

---

### Addendum 2.G — Test migration plan

The handoff doc identified 43 tests in 3 files with CRITICAL break risk when `[0,1]` assertions change. Plus 8 additional files with moderate/low risk.

#### 2.G.1 CRITICAL break-risk tests (3 files, 43 tests)

| Test file | Test count | Risk | Required fix |
|---|---|---|---|
| `test_terrain_erosion.py` | 9 | CRITICAL | `assert result.min() >= 0.0` and `result.max() <= 1.0` must become `height_range`-aware. Keep old tests passing via `normalize=True` backward-compat path; add new tests for world-unit domain. |
| `test_terrain_noise.py` | 26 | CRITICAL | 8 `test_height_in_bounds` + 8 `test_slope_in_bounds` + 8 `test_biome_assignments` variants. When `normalize=True` (default), keep passing. Add NEW tests for `normalize=False`. DO NOT modify existing. |
| `test_environment_handlers.py` | 50 | MODERATE-CRITICAL | RAW export tests assert 16-bit `[0, 65535]`. Add `tiled_mode` flag to export handler; `tiled_mode=False` preserves existing behavior; `tiled_mode=True` uses world-unit heights with global range. |

#### 2.G.2 Moderate/low risk tests (8 files)

| Test file | Tests | Risk | Reason |
|---|---|---|---|
| `test_terrain_flatten.py` | 8 | MODERATE | Blend thresholds may change at tile boundaries |
| `test_scatter_engine.py` | 37 | LOW | Pure logic, no `[0,1]` assumption |
| `test_terrain_chunking.py` | 13 | MODERATE | Chunk structure may need new fields |
| `test_terrain_biome_voronoi.py` | 4 | LOW | Voronoi is position-independent |
| `test_terrain_depth.py` | 23 | LOW | Feature generators are local-coordinate |
| `test_aaa_terrain_vegetation.py` | 31 | LOW | Vegetation generators are independent |
| `test_terrain_features_v2.py` | 21 | LOW | Feature generators local-coordinate |
| `test_environment_scatter_handlers.py` | 15 | MODERATE | Scatter depends on heightmap |
| `test_terrain_materials.py` | ? | LOW | Material setup is position-independent |
| `test_road_coastline_terrain_features.py` | ? | MODERATE | Road/coastline may assume centered terrain |

**Total existing terrain-related tests: ~238 across 12 files.** 43 (in 3 files) have critical break risk from world-unit migration.

#### 2.G.3 Test migration rule

Non-negotiable rule: **existing tests must continue to pass with the default path** (normalize=True, tiled_mode=False). Every new capability is added behind a new parameter or new function. Bundle A acceptance includes:

```bash
pytest Tools/mcp-toolkit/tests/ -q
# must show the same passing count as 71e6451 baseline + new tests
```

Added to Bundle A as `test_regression_zero.py` — a meta-test that compares current passing-test count against the baseline stored in `.planning/test_baseline.json`. Fails if the count drops.

---

### Addendum 2.H — Unity scene template update

`src/veilbreakers_mcp/shared/unity_templates/scene_templates.py` contains `generate_terrain_setup_script()` that generates Unity C# code with `terrain_size`, `terrain_resolution`, and `splatmap_layers` parameters. The template currently hardcodes a single-terrain assumption.

#### 2.H.1 Required updates (Bundle J supplement)

- Accept `tile_count_x`, `tile_count_y` parameters
- Generate `Terrain.SetNeighbors()` calls for all adjacent tiles (8-neighborhood)
- Use `TerrainData.SetHeightsDelayLOD()` for batch heightmap loading (avoids per-tile LOD rebuild)
- Set `heightmapResolution` to power-of-2+1 (257, 513, 1025) matching Blender tile resolution
- Generate `TerrainGroup` component for auto-connection
- Emit splatmap alpha textures per tile with 4-texel edge-bleed padding (Addendum 1.B.11)
- Emit mask stack sidecar JSON pointing to NPZ files

Added as Bundle J `terrain_navmesh_export.py` + new `terrain_unity_terrain_template.py` module.

#### 2.H.2 Status as of 2026-04-08

Handoff doc §12 Phase 8 notes that `unity_scene setup_tiled_terrain` action and `generate_tiled_terrain_setup_script()` already emit `Terrain.SetNeighbors` wiring. Verify and extend in Bundle J — do not reinvent.

Added to Bundle J compliance: check current state of `setup_tiled_terrain` action, extend with mask sidecar emission and splatmap padding.

---

### Addendum 2.I — worldbuilding_layout.py local-space generators

Four pure-logic generators still emit positions relative to local bounds centered around `(-half, +half)`:

- `worldbuilding_layout.py:1050 generate_location_spec()`
- `worldbuilding_layout.py:1288 generate_easter_egg_spec()`
- `worldbuilding_layout.py:1483 generate_settlement_spec()`
- `worldbuilding_layout.py:1636 assign_district_zones()`

**Status:** safe as standalone location/settlement generators. Local coordinates are correct for single-scene workflows.

**Risk:** if `compose_map_tiled` or any tiled world orchestration consumes these outputs assuming they are already world coordinates, roads, props, district seeds, POIs, and hidden-path markers will be misaligned.

**Decision:** keep these functions explicitly local. Every caller transforms outputs to world coordinates via `world_from_local(local_pos, origin)`. Bundle A adds a validator that greps call sites and asserts the world-conversion step is present.

Affected regression tests:

- `test_worldbuilding_v2.py`
- `test_buildings_dungeonthemes_settlements.py`
- `test_aaa_castle_settlement.py`
- `test_worldbuilding_layout_handlers.py`

Added as Bundle A compliance note + regression test requirement.

---

### Addendum 2.J — Canyon / waterfall / cliff dual-nature contract

Several hero features require BOTH heightmap modification AND mesh decoration. Previously the plan treated these as single-pass operations. Clarified now:

#### 2.J.1 Canyon

- **Heightmap carving** (Pass 3 `hero_features` or Pass 4 `erosion` pre-step): use `handle_carve_river`-style A* path on world heightmap, lower vertex heights along path. Canyon is a wider/deeper river carve; increase width and depth parameters. Erosion then enhances the natural shape.
- **Mesh decoration** (Pass 6 `structural_geometry`): call `generate_canyon()` → `MeshSpec` with floor path, side caves, weathered materials. Place via `mesh_from_spec` at world coordinates.
- **Both are required.** Heightmap alone lacks visual detail. Mesh alone doesn't carve the terrain.

#### 2.J.2 Waterfall

- **Heightmap ledge carving** (Pass 5 `water_network`): deepen the impact pool at the waterfall base, carve the outflow channel downstream, mark the lip position.
- **Mesh decoration** (Pass 6): build the 7 functional waterfall objects from Addendum 1.B.3 (river surface, sheet volume, impact pool, foam, mist, splash, wet rock zone).

#### 2.J.3 Cliff

- **Heightmap detection** (Pass 3): `build_cliff_candidate_mask` identifies steep clusters. No heightmap modification — cliffs are where terrain is already steep.
- **Mesh overlay** (Pass 6): `carve_cliff_system` builds lip + face + ledge + talus meshes. These are overlays on the base terrain, not replacements.

Added to Bundle B, C, F, H as a `dual-nature contract` acceptance item.

---

### Addendum 2.K — Commit strategy

The handoff doc mandates one commit per phase with tests passing at every commit. Applied to this plan:

#### 2.K.1 Rules

1. Every bundle is at least one commit (may be multiple sub-commits within the bundle).
2. Every commit must leave `pytest Tools/mcp-toolkit/tests/` passing at baseline or above.
3. Every commit must include the compliance checklist update in Appendix D for the items it completes.
4. Bundle A is an atomic merge — all sub-commits squash-merge to a single branch merge commit.
5. Bundles B–Q may merge incrementally but each merge requires the preserve-list regression suite to pass.
6. Force-pushes to `master` are forbidden. `feature/terrain-world-foundation` rebases are allowed between bundles.

Added as operational rule in §35.

---

### Addendum 2.L — Updated compliance checklists

#### D.1 additions (Bundle A, new)

- [ ] `TerrainMaskStack.__post_init__` asserts `height.shape == (tile_size + 1, tile_size + 1)`
- [ ] `theoretical_max_amplitude(persistence, octaves)` helper added to `_terrain_world.py`
- [ ] Flow map, drainage, deposition, wetness, bank instability masks computed on FULL world heightmap before tile split
- [ ] `extract_tile` works for 3D (per-channel) mask arrays same as heights
- [ ] World expansion test: regenerate 3×2 from existing 2×2 produces bit-identical original region
- [ ] Noise repeat distance audit — `_OpenSimplexWrapper.noise2_array` uses real opensimplex when available
- [ ] `apply_hydraulic_erosion_masks` scales `min_slope` by `height_range`, does NOT scale `capacity`
- [ ] 12-step `handle_generate_world_terrain` sequence implemented exactly per Addendum 2.A.7
- [ ] `test_terrain_world_orchestration.py` verifies sequence on 2×2 fixture
- [ ] `test_adjacent_tile_contract.py` covers all 10 "Generate Adjacent Tile" requirements
- [ ] Metadata contract: tile handlers return `tile_transform` with `origin_world`, `min_corner_world`, `max_corner_world`, `convention`
- [ ] Old `object_location` + `position` keys removed from tile handler returns, with backwards-compat shim + deprecation warning
- [ ] 4 critical vegetation aliases added to `VEGETATION_GENERATOR_MAP`: `fern`, `moss`, `vine`, `dead_tree`
- [ ] 13 centered-terrain assumptions fixed per Addendum 2.F (line-by-line)
- [ ] `handle_generate_multi_biome_world` routes through new `TerrainPassController` and populates mask stack
- [ ] `test_multi_biome_world_regression.py` asserts scene still valid after migration
- [ ] `test_regression_zero.py` meta-test compares against `.planning/test_baseline.json`
- [ ] `worldbuilding_layout.py` local-space generators documented as explicitly local; caller-side conversion asserted

#### D.2 additions (Bundle B, new)

- [ ] `terrain_advanced.py:793` audited and clip removed if present
- [ ] `terrain_advanced.py:1483` audited and clip removed if present
- [ ] `handle_erosion_paint` routes through world-unit contract
- [ ] `handle_terrain_flatten_zone` routes through world-unit contract
- [ ] `flatten_multiple_zones` routes through world-unit contract
- [ ] `terrain_advanced.py` docstrings updated: no "normalized [0,1]" language
- [ ] `test_terrain_advanced_world_units.py` passing
- [ ] `test_handle_erosion_paint_preserves_scale.py` passing
- [ ] `test_flatten_multiple_zones_preserves_scale.py` passing
- [ ] Dual-nature contract for canyon: both heightmap carve + mesh decoration

#### D.3 additions (Bundle C, new)

- [ ] Dual-nature contract for waterfall: heightmap pool carve + mesh chain
- [ ] Bugfix #9 regression test: tile metadata contract uses `tile_transform` dict only

#### D.4 additions (Bundle D, new)

- [ ] Hearthvale box fallback removed from `worldbuilding_layout.py:621-658`; replaced with explicit error logging
- [ ] Perimeter box fallback removed from `worldbuilding_layout.py:715-738`; replaced with explicit error logging
- [ ] `test_no_silent_cube_fallbacks.py` passing — asserts no cube fallbacks in settlement generation

#### D.6 additions (Bundle F, new)

- [ ] `generate_cave_entrance_mesh()` wired into Pass 6 `structural_geometry`
- [ ] Dual-nature contract: cliff detection + mesh overlay

#### D.8 additions (Bundle H, new)

- [ ] Dual-nature contract for canyon morphology template
- [ ] `generate_natural_arch()` wired into Bundle H morphology template (`natural_bridge`)

#### D.9 additions (Bundle I, new)

- [ ] `generate_sinkhole()` wired into `terrain_karst.py` sinkhole archetype
- [ ] `generate_ice_formation()` wired into `terrain_glacial.py`
- [ ] `generate_coastline()` wired into `coastline.py` extension
- [ ] `test_strata_neighbor_consistency.py` passing

#### D.10 additions (Bundle J, new)

- [ ] Unity `setup_tiled_terrain` action verified to exist and extended with mask sidecar emission
- [ ] Splatmap alpha textures emitted with 4-texel edge-bleed padding
- [ ] Mask stack NPZ sidecar references included in Unity terrain setup output
- [ ] `generate_terrain_setup_script()` updated with `tile_count_x`/`tile_count_y` parameters
- [ ] 8-neighborhood `Terrain.SetNeighbors()` calls generated per tile

#### D.15 additions (Bundle O, new)

- [ ] `generate_swamp_terrain()` wired into `build_wetlands`
- [ ] `generate_geyser()` wired into `build_hot_springs`

#### D.18 additions (Bundle R, new)

- [ ] Legacy curve-road migration: `worldbuilding.py:6144, 6575, 6796` routed through `_create_road_with_curbs`
- [ ] `worldbuilding.py:3535 _create_curve_from_points` dead code deleted
- [ ] `_create_curve_path` marked `@deprecated` with removal timeline
- [ ] `test_worldbuilding_no_curve_roads.py` passing

---

### Addendum 2.M — Verification checklist (Addendum 2 completeness)

All 26 gaps identified in the deeper audit are closed:

- [x] **Gap 1 — Flow map world-level computation** → Addendum 2.A.3 + Bundle A §D.1
- [x] **Gap 2 — World expansion strategy** → Addendum 2.A.4 + Bundle M §D.13
- [x] **Gap 3 — Noise repeat distance (256-cell wrap)** → Addendum 2.A.5 + Bundle G §D.7
- [x] **Gap 4 — Unity scene_templates.py tiled terrain C# generator** → Addendum 2.H + Bundle J §D.10
- [x] **Gap 5 — Break-risk test files explicit list** → Addendum 2.G (3 critical files, 43 tests enumerated)
- [x] **Gap 6 — Erosion capacity/min_slope scaling math** → Addendum 2.A.6 + Bundle A §D.1
- [x] **Gap 7 — 12-step world terrain execution sequence** → Addendum 2.A.7 + Bundle A §D.1
- [x] **Gap 8 — Canyon dual-nature (carve + mesh decoration)** → Addendum 2.J + Bundle B §D.2
- [x] **Gap 9 — terrain_advanced.py extended consumer list** → Addendum 2.B.1 + Bundle B §D.2
- [x] **Gap 10 — worldbuilding_layout.py local-space generators** → Addendum 2.I + Bundle A §D.1
- [x] **Gap 11 — Legacy curve-road path 4 locations** → Addendum 2.C.1 + Bundle R §D.18
- [x] **Gap 12 — Hearthvale box fallback removal** → Addendum 2.C.2 + Bundle D §D.4
- [x] **Gap 13 — Perimeter box fallback removal** → Addendum 2.C.2 + Bundle D §D.4
- [x] **Gap 14 — Missing vegetation types (fern, moss, vine, dead_tree)** → Addendum 2.D + Bundle A §D.1
- [x] **Gap 15 — 13 centered-terrain assumptions** → Addendum 2.F + Bundle A §D.1
- [x] **Gap 16 — 11 terrain feature generator wirings** → Addendum 2.E
- [x] **Gap 17 — Tile resolution power-of-2+1 contract** → Addendum 2.A.1
- [x] **Gap 18 — Theoretical max amplitude formula** → Addendum 2.A.2
- [x] **Gap 19 — Shared edge vertex contract** → Addendum 2.A.1
- [x] **Gap 20 — "Generate Adjacent Tile" 10-requirement contract** → Addendum 2.A.8
- [x] **Gap 21 — Multi-biome path alignment** → Addendum 2.C.3
- [x] **Gap 22 — World flow map per-tile extraction** → Addendum 2.A.3
- [x] **Gap 23 — Commit strategy (one per phase, tests passing)** → Addendum 2.K
- [x] **Gap 24 — Erode-before-split rationale documentation** → Addendum 2.A.3
- [x] **Gap 25 — Bug #4 extended to lines 793 and 1483** → Addendum 2.B.1 + Bundle B §D.2
- [x] **Gap 26 — Bug #9 metadata contract fix** → Addendum 2.B.2 + Bundle A §D.1

All 26 gaps closed.

---

### Addendum 2.N — Running total

Between Addendum 1 and Addendum 2, this plan now addresses:

- 30 gaps from Addendum 1 (prior docs + feedback memory)
- 26 gaps from Addendum 2 (handoff doc + bug audit deep re-read)
- **56 total gaps closed** across the two addenda

The plan now explicitly references every major item from:
- `terrain_claude_master_plan_2026-04-07.md`
- `terrain_branch_full_implementation_plan_2026-04-07.md`
- `terrain_aaa_implementation_guide.md`
- `terrain_tool_bug_audit_2026-04-07.md` (all 17 bugs)
- `terrain_pipeline_handoff_for_claude.md` (all 13 gaps + architectural contracts)
- Feedback memory files (Z-up, screenshot cap, waterfall volumetric, Tripo serialization, AAA quality demand)
- User's original 500-line semantic plan message
- The 71 themed items from the ultrathink deep dive

---

## Addendum 3 — Master plan §5 residual items (2026-04-08, third revision)

After committing Addendum 2, a focused re-read of `terrain_claude_master_plan_2026-04-07.md` §§5.6–5.19 surfaced 8 more items that were not fully captured. Plus a user-flagged recurring bug pattern. All closed here.

### 3.A — User-flagged persistent bug pattern (CRITICAL warning)

**Scatter-layer altitude assumptions always survive refactors.** User feedback 2026-04-08: every time the terrain pipeline is refactored, the scatter layer silently retains `heights / heights.max()` or `altitude = center.z / height_scale` clamped to `[0,1]`. Negative-elevation lowlands (basins, wetlands, underwater valleys) collapse to zero and corrupt biome/slope/material decisions downstream.

**Rule:** every refactor touching scatter MUST explicitly audit these conversions:

- `environment_scatter.py` any `heights / heights.max()` or `altitude / height_scale` math
- `environment.py` `paint_terrain_biomes` altitude clamp to `[0,1]`
- Any new scatter/biome code added in Bundle E, J, O

**Enforcement mechanism:** regression test `test_scatter_negative_elevation.py` generates a terrain with `min_height = -40m, max_height = 20m`, runs the full pipeline, and asserts:
- Scatter placements exist in negative-elevation cells
- Biome material at `z = -30m` is NOT the same as at `z = 0m`
- Slope calculations use world-unit gradients, not normalized

Added to Bundle A, E, J, O as a mandatory cross-cutting check. Will also be added to feedback memory.

### 3.B — Master plan §5 residual items (8 gaps)

#### 3.B.1 Distributed erosion with halos and seam blending (§5.6)

Addendum 1 added `ErosionStrategy.EXACT` vs `ErosionStrategy.TILED_PADDED`. Addendum 3 adds a third mode: `TILED_DISTRIBUTED_HALO`.

- Tiles eroded independently with overlap halos (typically 32-64 cells of shared region)
- Halo regions blended between neighboring tiles after erosion (weighted average where overlap exists)
- Scales to arbitrarily large worlds without single-machine memory cost
- Validation: `validate_independent_erosion_seams(tiles)` asserts max seam delta after blend < tolerance

Added to `Bundle M.erosion_strategy` supplement + Bundle A `ErosionStrategy` enum.

#### 3.B.2 Large-world precision strategy (§5.7)

- Adopt **floating-origin coordinate system** for worlds > 10 km
- Keep generation in stable high-precision space (float64) until per-tile export
- Support **camera/tile-relative rendering** — tiles carry origin offset; Unity receives tiles with offsets applied at render time, not authoring time
- Contract: `TileTransform.origin_world` may be `float64`; export to Unity converts to `float32` relative to a **sector origin** (km-scale anchor), not world origin

Added to Bundle A (`TileTransform` + `SectorOrigin` in `terrain_semantics.py`) + Bundle J (Unity export honors sector-relative coordinates).

#### 3.B.3 Test file updates for broken-behavior encoding (§5.14)

Specific files that currently assert broken behavior:

- `test_aaa_visual_verification.py` — currently asserts `aaa_verify_map([])` passes. Addendum 1.B.8 changes the behavior; this file's assertions must flip to `passed=False`. Codex may have already updated it — verify.
- `test_terrain_tiling.py` — verifies whole-world erode-then-split seams but NOT independent-adjacent-tile erosion with margins. Must add tests for `TILED_PADDED` and `TILED_DISTRIBUTED_HALO` modes.

Added as Bundle A + Bundle M compliance items.

#### 3.B.4 Performance budget stub is fake (§5.15)

Current state: `__init__.py` registers `performance_budget_check` as `lambda params: {"status": "ok", "budget": "not_implemented"}`. `blender_server.py:performance_check` interprets missing totals as `0`, which false-passes.

**Fix:** Bundle N supplement — real scene-wide performance collector:

```python
@dataclass
class TerrainPerformanceReport:
    triangle_count: Dict[str, int]      # {terrain, water, foliage, rock, cliff, ...}
    instance_count: Dict[str, int]
    material_count: int
    draw_call_proxy: int
    texture_memory_mb: float
    within_budget: Dict[str, bool]
    status: str  # "ok" | "over_budget" | "not_available"
```

- Count terrain/water/foliage/rock/cliff mesh budgets separately
- Report actual triangle counts, instance counts, material counts
- Return `not_available` when measurement genuinely isn't implemented — never fake `ok`
- `test_performance_budget_no_false_ok.py` asserts stub-returning-ok path is dead

Added to Bundle N compliance.

#### 3.B.5 `apply_stamp_to_heightmap` stale terrain-origin contract (§5.16)

`handle_terrain_stamp()` passes `terrain_origin=(obj.location.x, obj.location.y)` but the rest of the branch treats `obj.location` as the terrain **center** while `apply_stamp_to_heightmap()` converts with `(position - origin) / terrain_size` — which interprets `terrain_origin` as a **min corner**.

**Fix (Bundle B):** unify on centered-terrain contract from Addendum 2.B.2 (`tile_transform.convention` explicit). Update runtime stamping AND pure-logic helpers AND `test_terrain_advanced.py` together in one commit. Never leave runtime/pure/tests in inconsistent states.

Added to Bundle B compliance.

#### 3.B.6 River/road broken world-height adapter (§5.17)

`handle_carve_river()` and `handle_generate_road()` extract mesh heights and convert via `heightmap = heights / heights.max()`. World terrains with negative minima or shared world ranges don't fit this. Same pattern as the scatter-altitude bug (§3.A) but in path solvers.

**Fix (Bundle C + Bundle A):**

```python
@dataclass
class WorldHeightTransform:
    world_min: float
    world_max: float
    world_range: float

    def to_normalized(self, world_heights: np.ndarray) -> np.ndarray:
        return (world_heights - self.world_min) / self.world_range

    def from_normalized(self, normalized: np.ndarray) -> np.ndarray:
        return normalized * self.world_range + self.world_min
```

- Path solvers (A*, road placement) operate on normalized `[0,1]` for math simplicity
- But the adapter is explicit, reversible, and preserves signed elevations
- Test: `test_river_negative_elevation.py` carves through terrain spanning `[-40, 20]` and asserts output heights preserve sign

Added to Bundle A (`WorldHeightTransform` dataclass in `terrain_semantics.py`) + Bundle C (river/road use it).

#### 3.B.7 Scatter/biome altitude zero-based assumption (§5.18)

See §3.A above. This is the same bug class as 3.B.6 but in scatter/material code. Fix uses the same `WorldHeightTransform` adapter. Added to Bundle E acceptance criteria.

**Files affected:**
- `environment_scatter.py` — remove `heights / heights.max()`
- `environment.py:paint_terrain_biomes` — use `WorldHeightTransform` instead of clamping `center.z / height_scale`

#### 3.B.8 Tests protecting dead legacy workflows (§5.19)

Tests that currently lock in legacy behavior:

- `test_functional_blender_tools.py` (or wherever) asserts `env_generate_world_terrain` is registered as a functional command
- Test files wire `env_generate_waterfall` standalone path as the intended public system

**Fix:** Bundle A cleanup — these tests must flip to assert the new pass-based path. Legacy command tests become backwards-compatibility smoke tests (assert the wrapper still responds), not active-path tests.

Added to Bundle A test migration compliance.

---

### 3.C — Final verification checklist (Addendum 3)

- [x] **§3.A — Scatter-layer altitude assumptions persistent bug pattern** → Bundle A/E/J/O cross-cutting check + feedback memory entry
- [x] **§5.6 — Distributed erosion with halos** → `TILED_DISTRIBUTED_HALO` mode added to ErosionStrategy
- [x] **§5.7 — Large-world precision / floating-origin** → `SectorOrigin` in Bundle A, tile-relative Unity export in Bundle J
- [x] **§5.14 — Tests encoding broken behavior** → explicit `test_aaa_visual_verification.py` and `test_terrain_tiling.py` updates
- [x] **§5.15 — Performance budget stub** → Bundle N real collector with `TerrainPerformanceReport`
- [x] **§5.16 — apply_stamp_to_heightmap origin contract** → Bundle B unified centered contract
- [x] **§5.17 — River/road world-height adapter** → `WorldHeightTransform` in Bundle A, used by Bundle C
- [x] **§5.18 — Scatter altitude zero-based assumption** → `WorldHeightTransform` in Bundle E
- [x] **§5.19 — Tests protecting dead workflows** → Bundle A legacy test migration

9 residual gaps closed. **Running total: 65 gaps closed across 3 addenda (30 + 26 + 9).**

---

## End of Plan

**Last updated:** 2026-04-08 (Addendum 3 — master plan residuals + user-flagged scatter altitude warning)
**Total bundles:** 18 (A–R)
**Estimated effort:** 60–65 focused sessions
**Target score:** 8.6 / 10 AAA
**Realistic ceiling:** 8.8 / 10 AAA
**Hard cap:** ~8.9 without engine-side innovation
**Total gaps closed:** 65 (30 from Addendum 1 + 26 from Addendum 2 + 9 from Addendum 3)

To execute: start with Bundle A as an atomic commit, then follow the execution sequence in §26 (Bundle R slots in parallel with C/D/E after A). Update Appendix D + Addendum 1.D + Addendum 2.L + Addendum 3.C checklists as work lands. Do not deviate from §5 contracts, Addendum 1/2/3 supplements without revising this plan.

**Known persistent bug pattern:** scatter-layer altitude assumptions survive refactors. Always audit `heights / heights.max()` and `altitude / height_scale` clamps when touching scatter/biome code. Regression test `test_scatter_negative_elevation.py` is the canary.

This document is the single source of truth. When in doubt, this overrides other terrain docs.
