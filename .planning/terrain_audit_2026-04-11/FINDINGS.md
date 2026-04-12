# VeilBreakers Terrain Pipeline — Full Defect Inventory

**Branch:** `feature/terrain-world-foundation`
**Audit date:** 2026-04-11
**Audit rounds:** 2 completed (7 parallel agents R1 + 5 Opus agents + 1 codex pass R2)
**Status:** Evidence-gathering phase. NO fixes applied yet.

---

## Architectural revelation (the pattern behind every finding)

`compose_terrain_node` (blender_server.py:3156-3569) dispatches **three separate TCP commands in sequence**, not one:

1. `env_run_terrain_pass` (line 3247) — runs the pass DAG (macro_world → … → validation_full). Produces `solved_height` numpy array + metrics.
2. `env_generate_terrain` (line 3382-3394) — **LEGACY** monolithic generator. Takes `solved_height` and builds the actual Blender mesh via `_create_terrain_mesh_from_heightmap` (environment.py:798). Hard-codes `erosion: "none"`.
3. `env_build_cliff_face` / `env_build_cave_entrance` / `env_build_waterfall` (lines 3413-3445+) — **separate hero-mesh builders** consuming `scene_read.focal_point` + hard-coded hero params. They do NOT read `pass_cliffs`, `pass_caves`, or `pass_waterfalls` output.

**Consequence:** Fixing dead-deltas in the pass DAG for caves/waterfalls/cliffs does NOT change visuals. Only `pass_erosion`'s writeback to `height` (the input to step 2) matters. Hero features come from divergent procedural builders. Tests validate the pass DAG; visuals come from the legacy path.

`compose_map` (blender_server.py:3570-4224) is a FOURTH path that bypasses `compose_terrain_node` entirely and calls `env_generate_terrain` directly — no pass DAG at all.

---

## Severity key

- **P0** — Silently wrong output, data loss, visually broken in production
- **P1** — Partial, degraded, fragile, or latent
- **P2** — Maintenance / style / doc drift

## Status key

- **✅ CONFIRMED** — Verified by two or more independent agents reading source
- **⚠️ CORRECTED** — Prior claim revised after verification
- **🆕 NEW R2** — Added in round 2
- **🔍 NEEDS VERIFY** — Not yet ground-truthed

---

# CATEGORY 1 — Dead-delta bugs (pass computes mutation, discards it)

| ID | Sev | Status | File:line | Finding |
|---|---|---|---|---|
| F001 | P0 | ✅ | `terrain_caves.py:822,842` | `pass_caves` computes `_delta = carve_cave_volume()`, stores in `CaveStructure.height_delta` dataclass, never calls `stack.set()`. Caves are metadata-only. |
| F002 | P0 | ✅ | `terrain_waterfalls.py:706-741` | `pass_waterfalls` writes `pool_delta` to separate channel `waterfall_pool_delta`, never merged into `height`. Helper comments say "Return a HEIGHT DELTA mask (NOT applied)." |
| F003 | P0 | ✅ | `_terrain_world.py:579-584` | `pass_erosion` computes `bank_instability` + `talus`, writes only to `PassResult.metrics`, never `stack.set()`. `pass_navmesh` reads both with always-None guards → erosion penalties silently skip. |
| F004 | P0 | ✅ | `terrain_water_variants.py:579-661` | 8 detectors (`generate_braided_channels`, `detect_estuary`, `detect_karst_springs`, `detect_perched_lakes`, `detect_hot_springs`, `detect_wetlands`, `apply_seasonal_water_state`, seasonal depth) defined in `__all__`, zero call sites in pass body. Body only does inverse-depth wetness. |
| F005 | P1 | ⚠️ | `terrain_cliffs.py:552-641` | `pass_cliffs` is analysis-only (computes lip polylines/face masks, zero deltas). **CORRECTED:** hero cliff meshes DO get built — but by `env_build_cliff_face` (blender_server.py:3413), a separate TCP call with hard-coded params that IGNORES pass_cliffs output entirely. Bundle B cliff analysis is architecturally dead. |
| F006 | P0 | ✅ | `terrain.yaml` P0-016 | 4 Bundle H composition modules (morphology/hierarchy/rhythm/negative_space, 899 LOC) completely unwired from pipeline. See also F073. |

---

# CATEGORY 2 — Channel stack clobber / multi-writer

`TerrainMaskStack.set()` (`terrain_semantics.py:432`) is **overwrite, not merge**. No blend semantics. No provenance-aware composition.

| ID | Sev | Status | Channel | Writers | Detail |
|---|---|---|---|---|---|
| F007 | P0 | ✅ | `height` | 7 writers | erosion, framing, glacial, banded_macro, wind_erosion, karst, coastline. Last-writer-wins. Mountain passes don't look natural because erosion output gets overwritten by coastline or banded_macro. |
| F008 | P0 | ⚠️ | `roughness_variation` | **4 writers** (R1 said 3) | multiscale_breakup, roughness_driver, stochastic_shader (4th, new), plus implicit material writes |
| F009 | P1 | ✅ | `wetness` | 3 writers | water_variants writes twice + erosion |
| F010 | P1 | ✅ | `cloud_shadow` | 2 writers | `terrain_cloud_shadow:104` + `terrain_shadow_clipmap_bake:192` — both declare `produces_channels=("cloud_shadow",)`, non-deterministic ordering |
| F011 | P1 | ✅ | `mist` | 2 writers | waterfalls:744 + fog_masks:170 (fog overwrites waterfall contribution) |
| F012 | P1 | ✅ | `wet_rock` | 2 writers | caves:658 + waterfalls:745 |
| F013 | P1 | ✅ | `traversability` | 2 writers | `terrain_navmesh_export:190` + `terrain_ecotone_graph:159` (ecotones overwrites) |
| F014 | P1 | ✅ | `cave_candidate`, `saliency_macro`, `navmesh_area_id`, `water_surface`, `splatmap_weights_layer`, `detail_density` | 2+ writers each | Silent clobbers |
| F015 | P1 | ✅ | — | — | `stack.get()` returns a view, not a copy. Mutation through view bypasses integrity checks and content hash |
| F016 | P0 | ✅ | — | — | No merge/delta method on TerrainMaskStack. Architectural — no way to correctly compose multi-writer channels today |
| F017 | P0 | 🆕 | — | — | Multi-producer DAG non-determinism: `roughness_variation`, `cloud_shadow`, `detail_density`, `mist`, `traversability`, `splatmap_weights_layer` each have 2+ passes declaring `produces_channels=(same,)`. `terrain_pass_dag.py:68 _producers` dict uses last-writer-wins on registration order. |
| F018 | P2 | 🆕 | — | `terrain_masks.py:314` | Pseudo-write: `stack.set("height", h.copy(), "structural_masks")` writes height back to itself as a "touch". Inflates writer count, marks dirty without mutation. |

---

# CATEGORY 3 — Silent exception swallowing

**65 total `except Exception` hits across 30 files** (codex + Opus agent count).

| ID | Sev | Status | File:line | Finding |
|---|---|---|---|---|
| F019 | P0 | ✅ | `terrain_master_registrar.py:59,70` | `_safe_import_registrar` catches all exceptions on bundle registration. If Bundle F (caves) fails to import, caller gets KeyError later with no bundle attribution. Return value is **discarded** by handler at environment.py:1389 |
| F020 | P1 | ✅ | `terrain_checkpoints.py:352` | Bare `except Exception:` on autosave chain with wrong arity (P0-031) |
| F021 | P1 | ✅ | `terrain_waterfalls.py:699` | `except Exception:` marked "defensive" |
| F022 | P1 | ✅ | `terrain_region_exec.py:85,168,182` | Three bare `except Exception:` — region execution, checkpoint save, rollback. Failed checkpoints → silent skipped rollback |
| F023 | P1 | ✅ | `terrain_banded.py:617,621` | Two nested `pass` swallows on `state.banded_cache` attribute cache, no comment |
| F024 | P0 | ✅ | `blender_server.py:5249` | `terrain_pipeline` MCP action has NO try/except. Handler crashes surface as raw TCP errors |
| F025 | P1 | ✅ | `terrain_addon_health.py:48,128,147` | Three swallows — health check can't crash but can lie |
| F026 | P1 | ✅ | `terrain_hot_reload.py:44,49` | Reload failures indistinguishable from missing modules |
| F027 | P1 | ✅ | `terrain_golden_snapshots.py:234` | Snapshot diffing swallow |
| F028 | P1 | ✅ | `terrain_checkpoints_ext.py:89` | Sidecar write swallow |
| F029 | P1 | 🆕 | `terrain_validation.py:833-840` | `pass_validation_full` rollback failure caught: `metrics["rollback_error"] = repr(exc)`. `triggered_rollback` stays False. Caller treats failed rollback as successful. |
| F030 | P2 | ✅ | `environment.py:2728,2748,2803` | Three `pass` swallows in material / vegetation / unnamed paths |

---

# CATEGORY 4 — Workflow preset trap

| ID | Sev | Status | File:line | Finding |
|---|---|---|---|---|
| F031 | P0 | ✅ | `addon_toolchain.py:603-610` | Only preset `terrain_unity_ready_free`. Pass list: `[macro_world, structural_masks, erosion, navmesh, prepare_heightmap_raw_u16, validation_full]`. **No cliffs, no caves, no waterfalls, no water_variants, no materials_v2, no scatter_intelligent.** CLAUDE.md tells agents to prefer this preset. |
| F032 | P1 | ⚠️ | `terrain_unity_export.py:81-118`, `terrain_bundle_j.py:29,50` | `pass_prepare_heightmap_raw_u16` **does exist** (R1 agent couldn't find it). Registered via Bundle J aggregator. Auto-inserted at environment.py:1589-1592 before validation_full unless `unity_export_opt_out` is set. |
| F033 | P1 | ✅ | — | No `terrain_unity_ready_aaa` or `terrain_unity_ready_full` preset exists anywhere. No "good" preset to switch to. |

---

# CATEGORY 5 — Shader / materials (the "texture glitching")

| ID | Sev | Status | File:line | Finding |
|---|---|---|---|---|
| F034 | P0 | ✅ | `terrain_materials.py` (entire file) | **Zero `bpy.data.images.load()`** in any terrain_*.py file. No real textures ever bound. |
| F035 | P0 | ✅ | `terrain_materials.py:2382-2400` | Material assigned to mesh **before** `VB_TerrainSplatmap` vertex color attribute created. Shader references an attribute that doesn't exist at bind time → undefined sampling. |
| F036 | P0 | ✅ | `terrain_materials.py:2291-2305` | Base Color hardcoded from `palette["base_color"]` tuple. Roughness hardcoded. No `ShaderNodeTexImage` anywhere. |
| F037 | P0 | ✅ | `terrain_materials.py` | Uses `ShaderNodeBump` on `ShaderNodeTexNoise` instead of `ShaderNodeNormalMap` with real normal textures. Bump-on-noise produces high-frequency garbage. |
| F038 | P1 | ✅ | `terrain_materials_v2.py:53,130,152` | `triplanar: bool = True` flag on cliff/wet_rock MaterialChannel. Only read by `tests/test_terrain_materials_v2.py:159`. **Zero production readers.** |
| F039 | P1 | ✅ | `terrain_materials.py:1774` | `slot_offset = len(obj.material_slots) - len(zone_materials)` computed after appending slots → misaligns to pre-existing slots |
| F040 | P1 | ✅ | All terrain handlers | **No UV unwrap anywhere.** Zero `bpy.ops.uv.unwrap` / `smart_project` / `lightmap_pack` / `uv_layers.new` in any terrain code path. |
| F041 | P1 | ✅ | `terrain_materials.py` | No `ShaderNodeTexCoord` or `ShaderNodeMapping` nodes. Implicit Generated space. |
| F042 | P1 | ✅ | `terrain_materials.py` | No `ShaderNodeDisplacement`, no POM, no tessellation. Cliffs render flat. Displacement output socket never connected. |
| F043 | P2 | ✅ | `terrain_materials.py` | No macro+detail normal blend |
| F044 | P2 | ✅ | `terrain_materials.py` | No Fresnel/curvature wetness, no moss mask, no snow dot-product |
| F045 | P1 | ✅ | `terrain_materials.py:2282-2289` | `mat = bpy.data.materials.get(mat_name)` reuses by name but `nodes.clear()` unconditionally rebuilds node tree every call. Parallel biome-tile generation silently rewires each other's materials. |
| F046 | P1 | 🆕 | `terrain_materials.py:2382,2404-2407` | **Material double-append**: `obj.data.materials.append(mat)` at 2382 and `materials[0] = mat` at 2404-2407. Harmless but indicates copy/paste. |
| F047 | P1 | 🆕 | `terrain_materials.py:2346-2373` | HeightBlend "heights" are `noise_nodes[i].outputs["Fac"]`, **not heightmap samples**. "HeightBlend" is decoratively named — it's noise-driven mix weighting. |
| F048 | P2 | 🆕 | `terrain_materials.py` | Terrain path does not call `mesh.update()` after color_attributes write in `create_biome_terrain_material` (legacy path at line 1804 does). Loop-domain writes may not propagate on some Blender versions. |
| F049 | P1 | ✅ | `texture.py:214-350,673-789` | Full ShaderNodeTexImage + NormalMap + AO mix wiring EXISTS in the generic PBR builder, with real `bpy.data.images.load` calls. **Never invoked by any world/terrain/city generator.** |

---

# CATEGORY 6 — Unity export

| ID | Sev | Status | File:line | Finding |
|---|---|---|---|---|
| F050 | P0 | ✅ | `terrain_unity_export.py` | **No Z-up → Y-up axis swap.** Blender terrain imports inverted into Unity. Recurring bug per memory. |
| F051 | P0 | ✅ | `terrain_unity_export.py:47-55` | Endianness not explicitly little-endian — NPY is native-endian, correct on x86 but fragile |
| F052 | P0 | ✅ | `terrain_unity_export.py` | No resolution validation. Unity Terrain requires 2^n+1 (513/1025/2049). Export doesn't check. |
| F053 | P0 | ⚠️ | `scene_templates.py:75-140`, `unity_tools/scene.py:159-204` | **Partial correction:** Unity-side HAS splatmap→TerrainLayer mapping via `_handle_scene_setup_terrain` + `generate_terrain_setup_script`. BUT producer side never calls it from compose_terrain_node or compose_map. Bridge exists, not invoked. |
| F054 | P0 | ✅ | `environment_scatter.py:1361-1560` | No placement manifest JSON written for vegetation/props. Scatter happens in Blender only; Unity never sees instance transforms. |
| F055 | P0 | ✅ | — | **No FBX or TerrainData generation** anywhere. Pipeline writes `.npy` + `.json`; no C# consumer turns them into a TerrainData asset. |
| F056 | P1 | ✅ | `terrain_chunking.py:132-209` | Tile stitching computes overlap borders but no verification that Unity side welds them. Seams likely visible. |
| F057 | P1 | ✅ | `terrain_unity_export.py` | No LOD FBX chain export |
| F058 | P1 | ✅ | `splatmap_exporter.py` | Only 4-channel RGBA. AAA needs 6-8 layers. |
| F059 | P1 | 🆕 | `scene_templates.py:122` | Hardcoded `if len(splatmap_layers) != 4: raise ValueError`. Unity-side bridge literally cannot consume more than 4 layers even if producer changed. |
| F060 | P1 | 🆕 | `blender_server.py:4036-4155`, `terrain_unity_export.py` | **Two incompatible export schemas coexist:** compose_map writes `.raw` + `_vegetation_instances.json` + `_splatmap.png` + `{group}.fbx` to tempdir; compose_terrain_node uses `terrain_unity_export_contracts` manifest. Neither cleans up. No run-ID. Leak on repeated runs. |
| F061 | P1 | 🆕 | `terrain_unity_export.py:162-171` | `export_unity_manifest` has hidden `stack.set("heightmap_raw_u16", ...)` side-effect — mutates stack from inside an "export" function. Non-idempotent export. |
| F062 | P2 | 🆕 | `terrain_unity_export.py:244` | `determinism_hash = stack.compute_hash()` computed AFTER `stack.set` of heightmap_raw_u16. Same export on fresh vs populated stack yields different hash. |
| F063 | P1 | 🆕 | `export.py:215,311` | `handle_export_fbx` / `handle_export_gltf` have **zero** heightmap/splatmap/manifest awareness. Agents calling `blender_export` directly on a terrain object lose all terrain metadata. |

---

# CATEGORY 7 — Tripo / scatter wiring

| ID | Sev | Status | File:line | Finding |
|---|---|---|---|---|
| F064 | P0 | ✅ | `environment_scatter.py:1625-1716` | `handle_scatter_props` dispatches to `PROP_GENERATOR_MAP` which produces procedural primitive meshes. **Zero Tripo API calls in the scatter path.** Rocks/trees are capsules/cubes. |
| F065 | P0 | ✅ | `terrain_blender_safety.py:158-191` | `import_tripo_glb_serialized` is a GLB import utility. Nothing in the terrain pipeline calls it. Dead code relative to scatter. |
| F066 | P0 | ✅ | — | No Tripo asset cache, no Tripo→vegetation wiring, no placement manifest |
| F067 | P0 | 🆕 | `environment_scatter.py:1676,1690,1716` | **Silent flat-plane fallback:** `terrain_sampler = _terrain_height_sampler(bpy.data.objects.get(area_name))`. Default `area_name="PropScatter"` returns None → sampler None → `wz = 0.0`. Every prop placed at Z=0 with no warning when area_name mismatches. |

---

# CATEGORY 8 — Stubs, TODO, NotImplementedError

| ID | Sev | Status | File:line | Function | Finding |
|---|---|---|---|---|---|
| F068 | P1 | ✅ | `terrain_dirty_tracking.py:130` | `coalesce` | Stub return. Dirty-region tracking broken. |
| F069 | P0 | ✅ | `terrain_twelve_step.py:56` | `_detect_cliff_edges_stub` | Literally a stub. Cliff detection in 12-step orchestrator returns `[]`. |
| F070 | P0 | ✅ | `terrain_twelve_step.py:60` | `_detect_cave_candidates_stub` | Literally a stub. |
| F071 | P0 | ✅ | `terrain_twelve_step.py:64` | `_detect_waterfall_lips_stub` | Literally a stub. |
| F072 | P1 | 🆕 | `terrain_twelve_step.py:43,48` | `_apply_flatten_zones_stub`, `_apply_canyon_river_carves_stub` | Two more stubs in the same file (5 total). Steps 3/4/5/8 of the canonical 12-step sequence do nothing. |
| F073 | P1 | ✅ | `terrain_water_variants.py:449` | `detect_wetlands` | Stub body (one of the 8 dead detectors from F004) |
| F074 | P2 | ⚠️ | `terrain_quixel_ingest.py:79` | `_classify_texture` | **CORRECTED:** fully implemented (regex at lines 37-49). The **dead** part is `apply_quixel_to_layer` which only writes a JSON string to `stack.populated_by_pass` — no Blender shader consumer exists. |
| F075 | P2 | ✅ | `terrain_scene_read.py:101` | `_coerce_bbox` | Stub return |
| F076 | P2 | ✅ | `terrain_validation.py:89` | `_safe_asarray` | Stub return |
| F077 | P2 | ✅ | `terrain_telemetry_dashboard.py:99` | `_load_records` | Stub return |
| F078 | P2 | ✅ | `terrain_review_ingest.py:57` | `_coerce_location` | Stub return |
| F079 | P1 | ⚠️ | `honesty_lint.py` output | — | **CORRECTED:** 33 reported gaps include ~21 prose false positives (codex found broken symbol extractor). Real gap count ~12. Needs rerun with fixed extractor. |

---

# CATEGORY 9 — Bundle H phantom / orphan modules

| ID | Sev | Status | File:line | Finding |
|---|---|---|---|---|
| F080 | P0 | 🆕 | `terrain_master_registrar.py:96-112` | Docstring claims Bundle H includes saliency/morphology/framing/hierarchy/rhythm/negative_space but `registrars` list only has `H-saliency` and `H-framing`. |
| F081 | P0 | 🆕 | `terrain_morphology.py`, `terrain_hierarchy.py`, `terrain_rhythm.py`, `terrain_negative_space.py` | **Zero `register_*` or `pass_*` functions.** Orphan helper modules never wired into pass registry. Confirms `terrain.yaml` P0-016 (899 LOC unwired). |

---

# CATEGORY 10 — Stack.set bypass (dirty tracking invisible)

| ID | Sev | Status | File:line | Finding |
|---|---|---|---|---|
| F082 | P1 | 🆕 | `terrain_decal_placement.py:121` | `pass_decals` mutates `stack.decal_density` directly and assigns `populated_by_pass` manually. Dirty tracking, content hashing, quality-lint L1/L2 all skip this channel. |
| F083 | P1 | 🆕 | `terrain_wildlife_zones.py:189-216` | `pass_wildlife_zones` same pattern on `stack.wildlife_affinity`. |
| F084 | P1 | 🆕 | `terrain_vegetation_depth.py:557` | Same pattern on `stack.detail_density` |
| F085 | P0 | 🆕 | `terrain_assets.py:847-849` vs `terrain_vegetation_depth.py:557` | **Clobber collision:** both `pass_scatter_intelligent` and `pass_vegetation_depth` fully overwrite `stack.detail_density` dict. Last-wins wipes the other entirely. |
| F086 | P1 | 🆕 | `terrain_pass_dag.py:41-46` | `_merge_pass_outputs` uses `setattr` to bypass `stack.set`. Manually rewrites `populated_by_pass` and `dirty_channels.discard(channel)`, no content hash recompute until line 51. Race-window. |
| F087 | P1 | 🆕 | `terrain_navmesh_export.py:139-142` | Hidden `stack.set("navmesh_area_id", ...)` inside `export_navmesh_json`. Export function with side-effect. Non-idempotent. |

---

# CATEGORY 11 — Dead-side-effect passes (compute and discard)

| ID | Sev | Status | File:line | Finding |
|---|---|---|---|---|
| F088 | P1 | 🆕 | `terrain_god_ray_hints.py:216` | `pass_god_ray_hints` computes `hints = compute_god_ray_hints(...)` then reports only `len(hints)` and `max_intensity` in metrics. Never stored on stack, never exported. `export_god_ray_hints_json` exists but only test code calls it. |
| F089 | P1 | 🆕 | `terrain_stochastic_shader.py:151` | `pass_stochastic_shader` builds `[H,W,2]` mask (stochastic UV X,Y offsets). Only folds magnitude `sqrt(x²+y²)` into roughness_variation. Direction info discarded. Docstring admits "shader-consumed not mask-stack consumed" but no exporter exists. |

---

# CATEGORY 12 — Infrastructure / addon lifecycle

| ID | Sev | Status | File:line | Finding |
|---|---|---|---|---|
| F090 | P0 | ✅ | `terrain_hot_reload.py:21-50` | Only reloads 4 modules (terrain_ecotone_graph, terrain_materials_v2, terrain_banded, terrain_materials). Every other handler needs full Blender restart. |
| F091 | P0 | 🆕 | `terrain_hot_reload.py` | **Defined but never called.** Zero callers in production code anywhere. Only test files reference it. |
| F092 | P1 | 🆕 | — | `importlib.reload` does not cascade. Even the 4 reloaded modules don't pick up changes in their imported helpers. |
| F093 | P1 | ✅ | `terrain_pipeline.py` P0-007 | `PassDAG.execute_parallel` is serial under coarse lock. Parallel pass execution is a lie. |
| F094 | P1 | 🆕 | `TerrainPassController.register_pass` | Raises `ValueError("pass already registered")` on duplicate. None of 18 `register_*_pass` calls are idempotent. Hot reload landmine. |
| F095 | P2 | 🆕 | `terrain_bundle_n.py:34` | `register_bundle_n_passes` body is `_ = module.func` no-ops. Bundle N adds nothing. Cosmetic. |
| F096 | P1 | ✅ | `blender_server.py:4680+` | `batch_process` has no mid-batch checkpoint save. If a batch fails, no rollback. |
| F097 | P0 | 🆕 | `__init__.py:1-9` | `bl_info["blender"] = (4, 2, 0)` — Blender's install-time min. **Zero `bpy.app.version` runtime checks.** CLAUDE.md says target is 4.5 LTS. 4.2/4.3/4.4/4.5/4.6 all load. Silent API drift. |

---

# CATEGORY 13 — TCP boundary / protocol

| ID | Sev | Status | File:line | Finding |
|---|---|---|---|---|
| F098 | P0 | 🆕 | `socket_server.py:123` | `json.dumps(response).encode("utf-8")` has **no numpy encoder, no `default=` arg**. Any pass stashing `np.float32`/`np.int64`/`np.ndarray` in `PassResult.metrics` (e.g. `metrics["peak"] = height.max()` without `float()` cast) crashes with `TypeError: Object of type float32 is not JSON serializable`. |
| F099 | P0 | 🆕 | `socket_server.py:193-197` | Exception → `str(e)` only. **Traceback is LOST.** Agents see opaque 1-line errors. |
| F100 | P1 | 🆕 | `socket_server.py:12` | Inbound cap 64 MB. **Outbound cap unchecked.** 1025² heightmap `.tolist()` is ~100 MB JSON. `struct.pack(">I", len)` overflows at 4 GB. |
| F101 | P1 | 🆕 | `socket_server.py:167,172` | Timer pops 1 command per 10ms tick. N concurrent clients queue up to 300s. Fragile under load. |
| F102 | P0 | 🆕 | `environment.py:1636-1645` | `handle_run_terrain_pass` return dict excludes created objects list. `compose_terrain_node:3240 created_objects: list[str] = []` is never populated from pipeline response. MCP side blind to spawned meshes. |
| F103 | P1 | 🆕 | `environment.py:1456,1581` | Empty-dict `scene_read={}` is not None → builds `TerrainSceneRead` with empty tuples → `if scene_read is not None: pipeline.insert(2, "erosion")` fires even though client provided no real context. |
| F104 | P1 | 🆕 | `environment.py:1545-1569` vs `blender_server.py:3247` | `ProtocolGate` defaults `enforce_protocol=False`. compose_terrain_node doesn't pass the arg. **All 7 Addendum 1.A.2 protocol rules are bypassed in production.** |

---

# CATEGORY 14 — Integration divergent paths

| ID | Sev | Status | File:line | Finding |
|---|---|---|---|---|
| F105 | P0 | 🆕 | `blender_server.py:3570-4224` | **`compose_map` is a completely separate terrain code path** that calls legacy `env_generate_terrain` directly at line 3680-3701. Bypasses pass DAG, mask stack, contract, Bundle A–R semantics, terrain_unity_export_contracts. Every "ship a map" run uses legacy procedural terrain. |
| F106 | P0 | 🆕 | `blender_server.py:729-782` | `_compose_map_redirect_notice` appends warnings to output but **still runs the divergent path**. Warning is cosmetic. |
| F107 | P0 | 🆕 | `blender_server.py:3382-3394` | **compose_terrain_node calls legacy `env_generate_terrain` with hardcoded `erosion: "none"`**. The pass DAG's erosion output is NOT fed in. Only `solved_height` array is passed — everything else is lost. |
| F108 | P1 | 🆕 | `environment.py:877-897` | Inside `_create_terrain_mesh_from_heightmap`, legacy cliff overlays emit via `_terrain_depth.detect_cliff_edges` + `generate_cliff_face_mesh`. **Second cliff detection pipeline parallel to `pass_cliffs`.** No reconciliation. They can disagree on cliff count. |
| F109 | P0 | 🆕 | `blender_server.py:1496-1560`, `:3814-3888` | `_sample_terrain_height` raycasts the legacy `{map_name}_Terrain` mesh for foundation sampling. Not the mask stack. Not the hero terrain. |
| F110 | P0 | 🆕 | `blender_server.py:3832-3846` | Building foundations use `terrain_flatten_zone` + fallback `terrain_spline_deform`. **No mesh boolean/bmesh cut.** Buildings sit on a flattened disc, not carved in. |
| F111 | P0 | 🆕 | `settlement_generator.py:1703-1761` | `_sample_heightmap` takes `Optional[Callable]`. Zero `compose_terrain_node` imports. **Callables can't cross TCP.** Inside the addon `heightmap=None` → line 1722 returns 0.0. All settlement foundation math runs as if terrain is flat. |
| F112 | P1 | 🆕 | `tests/integration/test_full_terrain_pipeline.py:1-9` | Explicitly says *"The test does NOT require Blender — it exercises the pure-Python pipeline logic only."* **Zero end-to-end Blender tests.** Explains why all these bugs stayed hidden. |

---

# CATEGORY 15 — AAA features missing (industry gap)

15 missing + 18 partial vs the 50-item AAA checklist. Top 17 by visual impact:

| ID | Sev | Status | Feature | Impact |
|---|---|---|---|---|
| F113 | P0 | ✅ | Pipe-model flux hydraulic erosion | Single biggest "mountains don't look natural" lever. Droplet erosion produces soft lumps; pipe-flux (Gaea 2) produces sharp dendritic drainage. |
| F114 | P0 | ✅ | River 3D geometry (carved bed, banks, flow UVs) | Rivers are painted stripes because they are literally painted stripes. |
| F115 | P0 | ✅ | rock_hardness → erosion wiring | Stratigraphy produces `rock_hardness`, erosion ignores it. No banded differential erosion. |
| F116 | P0 | ✅ | Fault lines / tectonic displacement | Missing entirely. Mountains feel noise-shaped. |
| F117 | P0 | ✅ | Waterfall volumetric mesh | `terrain_waterfalls_volumetric.py` exists but dead-delta. Flat plane waterfalls. |
| F118 | P0 | ✅ | Curvature-driven wetness/moss | Defining dark-fantasy look. `bank_instability` curvature already computed — unused. |
| F119 | P0 | ✅ | Priority-flood lake basins | Lakes likely placed by altitude threshold → disc-shaped. |
| F120 | P1 | ✅ | Macro + detail normal blend | Anything >30m reads as plastic. |
| F121 | P1 | ✅ | Strahler stream order | Every tributary gets same width. |
| F122 | P1 | ✅ | Debris / talus cone geometry | Cliff bases look like cardboard. |
| F123 | P1 | ✅ | Meander sinuosity | Lowland rivers run straight. |
| F124 | P1 | ✅ | Natural arches / hoodoos | Missing entirely. |
| F125 | P1 | ✅ | Glacial carving depth | `terrain_glacial.py` exists, flagged stub. |
| F126 | P1 | ✅ | GPU scatter / impostors | Unity HDRP target, no GPU instance path. |
| F127 | P1 | ✅ | Lighting/reflection probe auto-placement | Missing. |
| F128 | P1 | ✅ | Occlusion volumes | Missing. |
| F129 | P1 | ✅ | Seasonal / snow accumulation | Missing. |

---

# CATEGORY 16 — Tests (the reason nothing was caught)

| ID | Sev | Status | File:line | Finding |
|---|---|---|---|---|
| F130 | P0 | 🆕 | `tests/test_terrain_cliffs.py:369-371` | **Bug-ratifying test:** asserts `"insert_hero_cliff_mesh" in s for s in state.side_effects`. Tests the intent-STRING placeholder not actual mesh creation. Violates "would stub pass?" rule. |
| F131 | P1 | ✅ | `tests/` overall | Test substance is actually good: real_ratio 0.96 (13,857 tests). But they test side-channel metrics, not final Blender output. |
| F132 | P0 | ✅ | — | **No integration test** reads the actual Blender scene after compose_terrain_node and asserts visual properties. |
| F133 | P1 | 🆕 | `tests/test_mcp_dispatch.py` + 3 others | Four tests reference `compose_terrain_node` or `env_generate_terrain` — all mock the TCP `blender.send_command` calls. Zero boot Blender. |

---

# CATEGORY 17 — Commits / git history smells

| ID | Sev | Status | Ref | Finding |
|---|---|---|---|---|
| F134 | P1 | 🔍 | commit `85ea32e` | Title: *"fix(terrain): P0 bug fixes — apply discarded deltas + fix scatter normalization"*. Codex tried to verify; current branch still shows the bugs. Either the commit never applied them or was reverted. **Needs `git show 85ea32e -- terrain_caves.py terrain_waterfalls.py`** |
| F135 | P1 | 🔍 | `terrain_legacy_bug_fixes.py` | File name is a risk signal. Unaudited. May contain half-applied patches competing with Bundle code. |
| F136 | P2 | ✅ | commit `f3e4498` | Squash-merge of PR #19. Loses per-commit granularity. Worth `git show f3e4498 --stat` audit. |
| F137 | P2 | ✅ | commit `a3a5e37` | *"feat(terrain): implement remaining addendum items — seed override, hero editing, generator wiring"*. Likely commit where compose_terrain_node was wired but compose_map was NOT updated — created the divergent path F105. |

---

# CATEGORY 18 — Code quality / outside-terrain bugs in same package

| ID | Sev | Status | File:line | Finding |
|---|---|---|---|---|
| F138 | P1 | 🆕 | `geometry_nodes.py:529,634,785,831,879,917` | **Missing `f` prefix** on six string literals: `"GN_Scatter_{target_name}"`, `"GN_Boolean_{base_name}"`, `"GN_EdgeWear_{target_name}"`, `"GN_ProximityBlend_{target_name}"`, `"GN_RandomTransform_{target_name}"`, `"GN_Subdivision_{target_name}"`. Every invocation creates groups named literally with braces. Latent bug in same handler package. |

---

# Verification still open

| ID | Ref | Action needed |
|---|---|---|
| V1 | `git show 85ea32e` | Did it actually apply cave/waterfall deltas? Was it reverted? |
| V2 | `terrain_legacy_bug_fixes.py` | Full read |
| V3 | `env_generate_terrain` handler source | What does the legacy monolithic generator actually do? Previously unread. |
| V4 | `env_build_cliff_face` / `env_build_cave_entrance` / `env_build_waterfall` handlers | Hero builder source — previously unread. Determine if they're procedural hacks or real geometry. |
| V5 | Files flagged for follow-up by sibling agent: `terrain_materials.py` (full 2000+ lines), `terrain_advanced.py`, `terrain_features.py`, `terrain_sculpt.py`, `terrain_waterfalls_volumetric.py`, `terrain_semantics.py`, `terrain_protocol.py`, `terrain_scene_read.py`, `terrain_dem_import.py`, `terrain_unity_export_contracts.py`, `terrain_chunking.py`, `terrain_live_preview.py`, `terrain_viewport_sync.py`, `terrain_mask_cache.py` | Full dead-delta + stub sweep |
| V6 | `cowork_bridge/rebuild_riftpass_01.py`, `riftpass_runtime_builder.py` | New untracked files — may contain fresh insights |
| V7 | `.planning/deliverables/Riftpass_01/REPORT.md` | Recent, not yet read |

---

# Totals

- **138 numbered findings** (F001-F138) spanning 18 categories
- **Severity breakdown:** 41 P0 · 64 P1 · 33 P2
- **Verification status:** 102 ✅ confirmed · 5 ⚠️ corrected · 31 🆕 new R2 · 3 🔍 need-verify
- **Verification items still open:** 7

---

# Meta-pattern (Round 1-2)

**Passes compute rich metadata into side channels and dataclasses. There is no integrator stage that composes them into a final heightfield, mesh, and material graph. The system assumes a downstream "applier" that was never built.** On top of that:

1. The pass DAG and the production render path are decoupled (3-call TCP flow F107/F108)
2. compose_map is a 4th parallel path that uses neither (F105)
3. Materials load zero textures (F034)
4. Unity export has no consumer (F053/F055)
5. "Tripo environmentals" are procedural cubes (F064-F067)
6. 41 P0s and one giant reload gap (F090-F092) mean fixes don't propagate to running Blender
7. Zero end-to-end Blender tests (F112/F132) keep everything invisible

Fix architecture must target both pipelines simultaneously.

---

# ROUND 3 APPENDIX (2026-04-11 evening)

**Dispatched:** 6 Opus agents + 3 codex-5.4 passes, all parallel.
**Raw reports preserved:** agent outputs in session task results; codex outputs in `/tmp/codex_pass{2,3,4}.out`.

## Round 3 meta-findings

- **Falsified:** F077 (`_load_records` is fully implemented, not a stub)
- **Falsified:** F134 (commit `85ea32e` IS on current HEAD and IS intact — but the fix only stores deltas in new channels, NO code consumes them — it's a half-fix, not a revert)
- **Falsified:** F135 — `terrain_legacy_bug_fixes.py` is a **misleadingly named static auditor**, not a runtime fix. Hardcoded line numbers already stale.
- **Partially corrected:** F006/F081 — `terrain_framing.py` DOES register + mutate height. morphology/hierarchy/rhythm/negative_space still orphan.
- **New architectural revelation:** there is not just 1 divergent path, there are **five**:
  1. Pass DAG (env_run_terrain_pass)
  2. Legacy generator called from compose_terrain_node (env_generate_terrain, erosion="none")
  3. compose_map direct legacy path
  4. `_create_terrain_mesh_from_heightmap` internal cliff overlays via `_terrain_depth.detect_cliff_edges`
  5. `Tools/cowork_bridge/rebuild_riftpass_01.py` + `riftpass_runtime_builder.py` — a **1769-line hand-authored workspace** that bypasses MCP entirely and uses TCP `execute_code` with `bpy.ops.*` directly

## Round 3 findings — env_generate_terrain + hero builders (Opus A / Codex 2)

| ID | Sev | File:line | Finding |
|---|---|---|---|
| F139 | P0 | `environment.py:939-1098` | `handle_generate_terrain` is the pre-DAG legacy generator. Uses `generate_heightmap` + `erode_world_heightmap` + `_create_terrain_mesh_from_heightmap`. **Zero TerrainMaskStack, zero DAG use.** This is the ACTUAL production render path when `compose_terrain_node` runs. |
| F140 | P0 | `environment.py:1006-1007` | Silently escalates `erosion_iterations` to `max(150000, resolution²/2)`. Caller can't opt out. 1025² tile → 525,312 droplets, 15-30 min of CPU. |
| F141 | P1 | `environment.py:1010-1011` | Hardcoded `warp_strength=0.4`, `warp_scale=0.5` — undocumented. |
| F142 | P1 | `environment.py:1069` | `terrain_size = scale` — noise scale reused as world size. No separate world-size param. |
| F143 | P0 | `environment.py:1049-1053` | `flatten_zones` runs BEFORE moisture map computation. Any building flatten erases drainage signal upstream. |
| F144 | P1 | `environment.py:1057-1067` | Moisture map computed only if `erosion_applied=True`. Callers with erosion disabled get uniform moisture → downstream splatmap painting uses uniform. Inconsistent across sibling handlers. |
| F145 | P1 | `environment.py:1070-1080` | `_create_terrain_mesh_from_heightmap` with `cliff_overlays=True`+`cliff_threshold=60°` triggers the **second** cliff detection pipeline that bypasses `terrain_cliffs.py`. |
| F146 | P1 | `environment.py:981-987` | Biome preset merge explicitly drops the preset's seed. Biome can never enforce a reproducible seed. |
| F147 | P0 | `environment.py:1015-1020` | When caller supplies `heightmap`, erosion is silently disabled. Doc advertises erosion/erosion_iterations but custom-heightmap branch hard-sets `erosion_applied=False`. |
| F148 | P0 | `environment.py:1171-1185` | `handle_generate_terrain_tile` with `erosion="both"` runs erosion **TWICE** (hydraulic + thermal branches are not exclusive). 2x wall-clock. |
| F149 | P1 | `environment.py:1187-1196` | `erosion_margin` cropping: `flatten_zones` applied to CROPPED heightmap, interpreted in inner-tile grid space instead of padded space. Silent offset. |
| F150 | P0 | `environment.py:1332-1645` | `handle_run_terrain_pass` has no cleanup path. Mid-pipeline exception leaks bpy meshes/objects, re-raises, socket thread gets raw traceback. No try/finally. |
| F151 | P1 | `environment.py:1384-1389` | `register_all_terrain_passes(strict=False)` — return value discarded. Missing bundle → later KeyError deep in run_pipeline, no bundle attribution. |
| F152 | P0 | `environment.py:1577` | `bool(composition_hints.get("unity_export_opt_out"))` — caller passing `"false"` (string) yields `bool("false")=True`, inverting intent. |
| F153 | P0 | `environment.py:1628-1634` | `shared_height_range` computed from `mask_stack.height` AFTER pipeline, but falls back to `_estimate_tile_height_range` when resolution is None. Estimates diverge from real channel. Silent fidelity loss. |
| F154 | P0 | `environment.py:1677-1701` | `handle_build_cliff_face` — hardcoded `width=20, height=15, overhang=3, num_cave_entrances=2, has_ledge_path=True, seed=42`. **Hero cliffs look identical across tiles.** Never reads pass_cliffs output. |
| F155 | P0 | `terrain_features.py:497-681` | `generate_cliff_face` is a **procedurally displaced vertical quad grid** — single-surface strip with noise on Y. **NOT volumetric.** No back face, no sides, no thickness. Paper-thin. Cave entrance dicts are metadata only. |
| F156 | P0 | `terrain_features.py:634-659` | Ledge path is a 2-vert-wide quad strip — flat ribbon, not walkable wedge. |
| F157 | P0 | `environment.py:1704-1729` | `handle_build_cave_entrance` — hardcoded `width=4, height=4, depth=3, arch_segments=12, terrain_edge_height=0.0`. Caves float if terrain at position isn't at Z=0. |
| F158 | P0 | `environment.py:1800-1820, 1732-1797` | `handle_build_waterfall` → `handle_generate_waterfall` — when compose_terrain_node doesn't supply `heightmap`, emits `legacy_geometry_fallback` warning and continues. **Every hero waterfall in the pipeline goes through the legacy fallback.** Warning is string, never raised. |
| F159 | P0 | `terrain_features.py:254-490` | `generate_waterfall` — **NOT volumetric** (violates `feedback_waterfall_must_have_volume.md` hard rule). Single-surface cliff-face backdrop, 8-vert box step ledges (only top+front faces), flat disk fan for pool, splash metadata only, cave-behind-waterfall is metadata-only. **There is no water-sheet mesh at all.** |
| F160 | P0 | `terrain_features.py:305-311` | `materials = ["cliff_rock","wet_rock","pool_bottom","ledge_stone","moss"]` — 5 entries, moss never referenced. Orphan slot. |
| F161 | P1 | `terrain_features.py:261-269,285-288`, `environment.py:1771-1778` | Waterfall generator has `facing_direction` param. Handler never passes it. Waterfalls always face legacy -Y instead of river direction. |
| F162 | P0 | `terrain_waterfalls_volumetric.py` | **File is validator-only.** Defines `WaterfallVolumetricProfile`, `validate_waterfall_volumetric`, `enforce_functional_object_naming`. Nothing emits geometry. Never imported by any handler. Only `test_bundle_r.py` runs it. The volumetric contract is unenforced. |
| F163 | P0 | `environment.py:1795-1796` | `legacy["warning"] = "should be driven from heightmap..."` — warning is a string in the return dict. Callers that don't inspect `result["warning"]` treat as success. |
| F164 | P0 | `environment.py:1823-1904` | `handle_stitch_terrain_edges` mutates both `obj_a` and `obj_b` in-place, averages Z at seam. Not idempotent. Runs twice → drifts toward avg of avgs. |
| F165 | P0 | `environment.py:1842-1861` | `_edge_vertices` uses `tolerance=1e-4` on raw coords. For tiles at `world_origin_x=500000` this rounds to ~0 → zero matches → stitch silently returns error without raising. |
| F166 | P0 | `environment.py:1911-1993` | `handle_paint_terrain` creates new materials every call. Reruns leak materials. No `bpy.data.materials.remove` on replace. |
| F167 | P0 | `environment.py:2039` | `handle_carve_river` `height_scale = heights.max() if heights.max() > 0 else 1.0` — sub-sea-level flats (`max()=0.01`) get normalization divide by 0.01, 100x inflation. Same bug at `handle_generate_road:2103`. |
| F168 | P0 | `environment.py:2550-2607` | `handle_export_heightmap` — reads Z from bmesh verts, reshapes by `_detect_grid_dims`. If sculpted grid is non-rectangular, export produces garbled heightmap. No `rows*cols == len(heights)` assertion. |
| F169 | P0 | `environment.py:2580-2586` | Unity compat resize is **nearest-neighbor only**. Downsampling 2049→1025 loses every other hero detail row. |

## Round 3 findings — Stack semantics + numpy + frozen dataclasses (Opus B)

| ID | Sev | File:line | Finding |
|---|---|---|---|
| F170 | P0 | `terrain_semantics.py:687` | `HeroFeatureSpec(frozen=True)` with `parameters: Dict[str, Any] = field(default_factory=dict)`. **Frozen + mutable dict.** Auto-generated `__hash__` raises `TypeError` on any set/dict usage. |
| F171 | P0 | `terrain_semantics.py:768` | `TerrainIntentState(frozen=True)` with `composition_hints: Dict[str, Any]`. Same footgun. Comment at 768 knows it's bad and hand-waves. |
| F172 | P0 | `terrain_semantics.py:522-572` | `compute_hash` uses `tobytes()` — NaN bytes compare equal but `__eq__` (auto-dataclass) treats NaN as unequal. **Violates hash/eq contract.** `dict[stack]=foo` misbehaves. |
| F173 | P0 | `terrain_semantics.py:549-559` | `compute_hash` iterates `_ARRAY_CHANNELS` (static tuple) + second loop for dict channels. **`detail_density` is NEVER hashed.** Dict channel written by `pass_scatter_intelligent` and `pass_vegetation_depth` doesn't affect `content_hash` → determinism CI blind to scatter regressions. |
| F174 | P0 | `terrain_semantics.py:576-598` | `to_npz` — `detail_density`, `wildlife_affinity`, `decal_density` never persisted to `.npz`. Round-trip loses all three. |
| F175 | P0 | `terrain_semantics.py:600-624` | `from_npz` uses `setattr` bypass + only restores `populated_by_pass` from meta dict. If meta is truncated, provenance is a lie. |
| F176 | P1 | `terrain_semantics.py:154` | `populated_by_pass.setdefault("height", "__init__")`. Mutation via `get()` view (F148 in R1) never updates provenance → reads "__init__" even after 6 writers mutated. |
| F177 | P1 | — | Channel orphans (declared, never written): `physics_collider_mask`, `lightmap_uv_chart_id`, `lod_bias`, `tree_instance_points`, `ambient_occlusion_bake`. Unity manifest always shows them as `None`. |
| F178 | P0 | `terrain_semantics.py, all passes` | **f64 dominant, not f32.** 273 f64 allocations vs handful of f32. 1025² heightmap f64=8.4MB vs f32=4.2MB × 15 intermediate channels → ~60MB/tile wasted. Silent upcast at every `np.asarray(stack.height, dtype=np.float64)`. |
| F179 | P1 | `terrain_advanced.py:615,827,1142,1271` | `base_heights.astype(np.float64).copy()` — upcast-then-copy double allocation inside erosion droplet iterations. |
| F180 | P0 | `terrain_pipeline.py, terrain_cliffs.py:565, terrain_caves.py:579,773, terrain_karst.py:238, terrain_glacial.py:274` | **Confirmed circular import** — `terrain_pipeline ↔ everything`. Multiple lazy-import workarounds. Runtime order depends on `terrain_master_registrar.py`. |
| F181 | P0 | `terrain_features.py:33-34` | **Module-level globals** `_features_gen`, `_features_seed` mutated by `_hash_noise`. Thread-unsafe — parallel passes race. |
| F182 | P0 | `terrain_checkpoints.py:48-53` | Three module-level dicts keyed by `id(controller)`. Python id reuse → stale entries shadow new controllers. |
| F183 | P0 | `terrain_validation.py:801-807` | Module-level `_ACTIVE_CONTROLLER` — concurrent pipelines clobber it, rollback each other's checkpoints. |
| F184 | P0 | `terrain_master_registrar.py` | Bundle **M is completely missing** from registrars list. Only Bundles A-L, N, O registered. No comment explaining the skip. |
| F185 | P0 | `terrain_master_registrar.py:117-124` | Even successful `fn()` is wrapped in another `except Exception`. Partial registration where `terrain_waterfalls.pass_waterfalls` is in registry but `pass_waterfalls_volumetric` is not. `clear_registry` never called to rollback. **PASS_REGISTRY can become corrupted.** |
| F186 | P1 | `terrain_master_registrar.py:124` | Error strings appended as `f"{label}:SKIPPED({exc!r})"` to same return list. Membership test `"F" in loaded` misses skipped case → silent mis-report. |
| F187 | P1 | `terrain_bundle_o.py:10` | `from . import terrain_vegetation_depth, terrain_water_variants` at module top. If either child blows up at import, Bundle O silently drops. |

## Round 3 findings — Unity side (Opus C)

| ID | Sev | File:line | Finding |
|---|---|---|---|
| F188 | P0 | `scene_templates.py:210-218` | C# heightmap reader uses `ushort value = (ushort)(rawBytes[i] | (rawBytes[i+1] << 8))` — little-endian. Producer writes NumPy native-endian (works on x86, breaks on BE hosts). |
| F189 | P0 | `scene_templates.py:203-218` | C# reader never validates file size. Caller passes `terrain_resolution=513` but producer exported 1025² → reader silently truncates at 131KB of 2.1MB → terrain full of zeros for missing rows. |
| F190 | P0 | `scene_templates.py:232-237` | `AssetDatabase.CreateAsset(terrainData, "Assets/Terrain/Generated/VB_TerrainData.asset")` — **hardcoded path**. Two calls in same Unity project silently overwrite each other. |
| F191 | P0 | `scene_templates.py:241` | Success JSON hand-built via string concatenation. `"size": "1000x600x1000"` as STRING (not array). Windows paths with `\` in `ex.Message.Replace("\"", ...)` produces malformed JSON. |
| F192 | P1 | `scene_templates.py:222-223` | Missing heightmap: `Debug.LogWarning "Creating flat terrain"` and continues into splatmap block. Silent flat terrain with splatmaps on zero plane. |
| F193 | P0 | `unity_tools/scene.py:140,222` | `terrain_size` defaults hardcoded `(1000, 600, 1000)` — producer emits real world metrics in manifest, Unity handler never reads manifest. Every call re-guesses scale. |
| F194 | P0 | `unity_tools/scene.py:159-204` | `_handle_scene_setup_terrain` has **no `manifest_path` parameter**. The §33 manifest (`world_origin_*_m`, `coordinate_system`, `heightmap_bit_depth`, `cell_size`, `tile_x/y`) is orphan. Unity blind to producer contract. |
| F195 | P0 | `scene_templates.py:126-170` | Alphamap reader ignores per-pixel weight normalization — silently "fixes" miscoded weights (NaN, negative) so QA never sees upstream bugs. |
| F196 | P0 | `scene_templates.py:456-469` | Tiled terrain neighbor wiring depends on `flip_vertical=True` default. Nothing asserts it. |
| F197 | P0 | `production_templates.py:163-164` | Pipeline `create_level` step `terrain_import` declares `required_params=["terrain_size"]` but handler requires `heightmap_path`. Validator LIES. |
| F198 | P0 | `production_templates.py:169-170` | `scatter_objects` declares `required_params=["prefabs"]`, handler uses `prefab_paths`. Mismatched param name. |
| F199 | P0 | Unity tools, all | **Zero consumers** for Bundle J's 10+ `.npy` channels + 5 JSON descriptors. No C# NumPy reader exists. Producer ecosystem-only, unusable by Unity. |
| F200 | P0 | Unity tools, all | **Zero `TreePrototype` / `DetailPrototype` wiring.** No Unity Terrain trees/details supported. Producer exports tree_instance_points — dead. |
| F201 | P0 | Unity C# | No navmesh consumer. `terrain_navmesh_export.export_navmesh_json` writer has zero callers on both sides. |
| F202 | P0 | `unity_tools/scene.py:159-204` | `setup_terrain` single-tile handler has **no position parameter** — always places terrain at Unity (0,0,0) regardless of `world_origin_x_m`. |
| F203 | P0 | `splatmap_exporter.py` vs `environment.py:571-589` | **Two splatmap exporters with different formats.** `splatmap_exporter.py` writes real PNG (IHDR/IDAT/CRC). `environment.py._export_splatmap_raw` writes raw 8-bit bytes. Unity C# reader is RAW-only — if routed to the PNG path, reads header as channel weights → garbage. Only signal is `.png` vs `.raw` extension. |

## Round 3 findings — untracked + unread files (Opus D)

| ID | Sev | File:line | Finding |
|---|---|---|---|
| F204 | P0 | `Tools/cowork_bridge/rebuild_riftpass_01.py:60-270` | **Fifth parallel terrain-authoring path** — 1177 lines of hand-tuned numpy build a heightmap from scratch, upload via `env_run_terrain_pass`. Pass DAG runs on already-authored data; its outputs are cosmetic. |
| F205 | P0 | `rebuild_riftpass_01.py:935-1007` | Calls `env_run_terrain_pass` twice, clears scene, calls `env_generate_terrain` with `erosion="none"` — reproduces F107 freshly. |
| F206 | P1 | `rebuild_riftpass_01.py:366-489` | `apply_terrain_material` writes a full shader with `ShaderNodeTexCoord` + `ShaderNodeMapping` + slope/height ramps. **All missing from production `terrain_materials.py`.** The knowledge exists outside the pipeline but never went into it. |
| F207 | P1 | `rebuild_riftpass_01.py:730-904` | `author_manual_dressing` spawns trees/shrubs/reeds via `primitive_cylinder/cone/ico_sphere/cube`. Literally the "procedural cubes instead of Tripo" pattern, admitted in code. |
| F208 | P0 | `riftpass_runtime_builder.py:490-494` | **Boolean EXACT solver on dense terrain mesh** for cave carving. Memory `feedback_blender_crash_avoidance.md` explicitly forbids this. High-probability crash — rebuild report round 22 describes matching scene state loss. |
| F209 | P0 | `riftpass_runtime_builder.py:578-579` | After sculpting, `cliff_obj.hide_render=True; route_preview.hide_render=True`. **Cluster-hull cliff mass and cave route preview are invisible to every render.** Report's 6/10 plateau is the terrain mesh alone. |
| F210 | P1 | `riftpass_runtime_builder.py:70-73` | `use_auto_smooth`/`auto_smooth_angle` guarded with `hasattr`. Blender 4.1 removed `use_auto_smooth` → silent no-op → mesh renders flat-faceted. |
| F211 | P1 | `REPORT.md:77-81` | Vision-review plateau at 6/10. Report admits "vision reviewer scoring is non-deterministic and biased toward photogrammetry". Deliverable shipped despite failing "both reviewers AAA-pass" gate. |
| F212 | P1 | `REPORT.md:109` | "Sandbox blocked `bpy.ops.wm.save_as_mainfile` — no `.blend` checkpoint". Session artifacts process-resident only. Non-reproducible. |
| F213 | P1 | `.planning/terrain_checkpoints/` | 35 `.npz` files, multiple duplicates per stage with different hashes. No rollup index. None in `.gitignore`. |
| F214 | P0 | `terrain_god_ray_hints.py:216` | `pass_god_ray_hints` computes hints, reports only `len()` in metrics. Dead side-effect. |
| F215 | P0 | `terrain_budget_enforcer.py:178` | `enforce_budget` has **zero production callers**. Only referenced by test + Bundle N no-op. Ship budgets unenforced. |
| F216 | P0 | `terrain_stratigraphy.py:195-229` | `apply_differential_erosion` is defined, exported in `__all__`, docstring says "caller can add it to stack.height". **Zero callers.** Reinforces F115 at source. |
| F217 | P0 | `terrain_performance_report.py:50` | `collect_performance_report` **zero production callers**. Triangle estimates are per-cell heuristics (bears no relationship to actual mesh triangle counts). |
| F218 | P0 | `terrain_decal_placement.py:121-154` | `pass_decals` declares `produces_channels=()` (empty) yet writes `stack.decal_density`. DAG topological sort can run decals BEFORE its inputs. |
| F219 | P0 | `terrain_framing.py:131` | **New height writer** — `stack.set("height", new_height, "framing")`. Bundle H framing pass partially wires (contradicts F006's "899 LOC unwired" — saliency + framing ARE wired, only morph/hier/rhythm/neg unwired). |
| F220 | P0 | `terrain_roughness_driver.py:56-70` | Reads `erosion_amount` / `deposition_amount` channels. **Neither produced by any pass.** Roughness driver silently degrades to "just wetness". |
| F221 | P1 | `terrain_multiscale_breakup.py:109-115` | On re-run, additive: `rough = existing + 0.15*breakup`. Not idempotent — drifts upward each run. |
| F222 | P1 | `test_terrain_caves.py` | Tests CaveArchetype dataclass fields. **Zero assertions on stack.height deltas or mesh.** F001 would pass every test. |
| F223 | P0 | `test_bundle_r.py` | **All hero builders mocked.** Divergence like F107 (hardcoded erosion="none") invisible by design. |
| F224 | P1 | `honesty_lint.py:10` | 5-LOC stub heuristic is AST-ignorant. `def f(): return do_everything(...)` triggers false stub. Root of F079 false positives. |

## Round 3 findings — MCP layer (Opus E)

| ID | Sev | File:line | Finding |
|---|---|---|---|
| F225 | P0 | `blender_server.py:3423,3439,3464` | Hero builder calls don't check `.get("status")` before appending to `hero_features_built`. **Failed hero builders are recorded as successes** and leak into final JSON as `"hero_features_built"` step completed. |
| F226 | P0 | `blender_server.py:3482-3499` | compose_terrain_node has its own **water/river override path** calling `env_carve_river`+`env_create_water` **after** hero feature builders. Pass DAG's water_variants + hero waterfalls + legacy river all fight over the same mesh. |
| F227 | P0 | `blender_server.py:3503-3511, 3515-3522` | `env_paint_terrain`, `terrain_create_biome_material`, `env_scatter_vegetation` are **fire-and-forget**. Return values discarded. No error check. |
| F228 | P0 | `blender_server.py:3539-3548` | `env_export_heightmap` capture but its `.get("ok")`/`.get("status")` never checked. Failed export counts as success. |
| F229 | P0 | `blender_server.py:3551` | Final status: `"success" if seam_report.get("seam_ok", True) else "partial"`. **No `"error"` state after initial guard at 3266-3283.** Every post-pipeline failure becomes silent success or partial. |
| F230 | P0 | `blender_server.py:3259` | **Caller-supplied `spec.protected_zones` is never merged** with `seam_protected_zones`. User-authored protected zones never reach pass DAG. |
| F231 | P1 | `blender_server.py:3195-3206` | compose_terrain_node's default pipeline includes `cliffs,caves,waterfalls,materials_v2,scatter_intelligent` — **different from `terrain_unity_ready_free` preset** (F031). MCP hard-codes a richer pipeline than the only preset. |
| F232 | P0 | `blender_server.py` entire compose_terrain_node | **No try/except anywhere** in compose_terrain_node body. TCP disconnects/timeouts/JSON decode errors → raw traceback to FastMCP. |
| F233 | P0 | `blender_server.py` | **compose_terrain_node (no try/except, swallows post-3283 silently) vs compose_map (try/except every step, never raises)** — opposite incompatible error semantics in same file. |
| F234 | P0 | `blender_server.py:3392-3393` | compose_terrain_node unconditionally enables `cliff_overlays=True`, `cliff_threshold_deg=60.0`. **Three cliff systems run per call**: pass_cliffs (dead), `_terrain_depth.detect_cliff_edges` (legacy overlay), `env_build_cliff_face` (hero). Uncoordinated. |
| F235 | P0 | `blender_server.py:3244` | `clear_scene` called unconditionally with no error check. Running compose_terrain_node on a populated scene silently wipes everything before any validation. |
| F236 | P1 | `blender_server.py:3302` | `verify_adjacent_seams=True` default triggers 4 full preview pipeline runs (N/S/E/W). **5× TCP traffic**. No cache, no memoization. |
| F237 | P1 | `blender_environment.py:5975` | `build_waterfall`/`build_cliff_face`/`build_cave_entrance`/`build_breakable`/`sculpt_terrain` branches reference `position` parameter. **`position` is NOT in the `blender_environment` function signature (5760-5840).** Runtime `NameError` for every call via this tool. Latent P0. |
| F238 | P1 | `blender_server.py:2679` | asset_pipeline tool docstring advertises ~13 actions, **omits 16 more** (`aaa_verify`, `screenshot_regression`, `performance_check`, `generate_lod_chain`, `generate_map_package`, `generate_prop`, etc). Agents have no machine-readable signal. |
| F239 | P1 | `blender_server.py:2668-2669` | `checkpoint_dir`, `resume`, `force_restart` declared for compose_map + compose_interior. **compose_terrain_node does NOT support checkpoints.** Long runs lose progress. |
| F240 | P2 | Prior audit | compose_terrain_node block runs 3156-**3568**, prior audits only examined 3156-3283 (~40% coverage). compose_map block 3570-4541, prior examined through 4224 (~60%). ~600 lines total were previously unread. |

## Round 3 findings — non-terrain handlers (Opus F)

| ID | Sev | File:line | Finding |
|---|---|---|---|
| F241 | P0 | `environment_scatter.py:1152-1354` | `_scatter_pass` hardcodes `_BIOME_DENSITY.get(biome, 0.5)`. **Unknown biome silently defaults to 0.5**. No warning. |
| F242 | P0 | `environment_scatter.py:1243,1263,1303` | Slope/height thresholds `sl > 30.0 or h < 0.1 or h > 0.7` hardcoded independent of biome. **Alpine biome can't place trees above h=0.7.** |
| F243 | P0 | `environment_scatter.py:1404-1413` | Grid dim detection fallback `side = int(sqrt(vert_count))` silently corrupts non-square terrains. `round(..., 3)` means two verts 1mm apart collide. |
| F244 | P0 | `environment_scatter.py:1472-1494` | Iterates ALL `bpy.data.objects` looking for EMPTYs with children as "building footprints". Any empty with children (armature, light rig, grouping) treated as exclusion zone. |
| F245 | P0 | `environment_scatter.py:1497` | Road detection: `"road" in _obj.name.lower()`. A prop named "Broadsword" contains "road" → excluded. |
| F246 | P0 | `environment_scatter.py:1563-1566` | `bpy.data.objects.new()` per instance, naming not collision-checked. Re-running produces `.001`, `.002` ever-growing. No cleanup. |
| F247 | P0 | `environment_scatter.py:1586` | `slope_roll = math.atan2(dzdx, 1.0)` — the `1.0` is wrong. Slope roll artificially damped. Same bug at `slope_pitch`. |
| F248 | P0 | `environment_scatter.py:1690` | **`handle_scatter_props` passes scatter-collection name as terrain_name** — collection doesn't exist yet as object. `bpy.data.objects.get(area_name)` is None → `terrain_sampler=None` → every prop spawns at Z=0. Terrain-aware scatter is **silently broken by default**. |
| F249 | P0 | `settlement_generator.py:1761` | `_sample_heightmap` called 4× per building corner. On 200-building towns → 800 raycasts. No caching. Performance cliff. |
| F250 | P1 | `settlement_generator.py:1828` | `platform_elevation = max_elevation` across 9 samples. On terraced terrain all pads match highest corner. Retaining walls instead of terraces. |
| F251 | P0 | `settlement_generator.py:2913-2930` | `_place_buildings` runs BEFORE heightmap-aware computation. `_compute_foundation_profile` runs AFTER placement. Nothing rejects a placement requiring a 10m foundation. |
| F252 | P0 | `settlement_generator.py:2934-2943` | `_generate_alleys` + `_scatter_settlement_props` never receive `heightmap`. Alleys planar, props at Z=0. |
| F253 | P0 | `worldbuilding.py:2597-2640` | `_sample_scene_height` uses `ray_cast` with `origin=Vector((x,y,10000.0))` — hardcoded 10km ceiling. Terrains >10km high silently return fallback. |
| F254 | P0 | `worldbuilding.py:5447,5465,5489` | **Castle mesh generation swallows** — one battlement fails → ALL subsequent battlements skipped in that castle (loop escaped by exception, silent partial walls). |
| F255 | P0 | `worldbuilding.py:6395-6396` | **GLB import swallow** — Tripo prop import failures logged but settlement proceeds without prop → gaps. |
| F256 | P0 | `worldbuilding.py:6443-6444` | **Terrain alignment on prop placement swallowed** → prop floats/sinks. |
| F257 | P0 | `__init__.py:1002` | `"env_generate_world_terrain"` commented DEPRECATED but still registered. Old callers hit old monolithic path. |
| F258 | P0 | `__init__.py:1124-1230` | ~25 terrain-adjacent handlers registered as **inline lambdas**: `env_compute_road_network`, `env_generate_coastline`, `env_generate_canyon`, `env_generate_waterfall` (alias), `env_generate_cliff_face`, etc. No error handling, no validation, not linted. Hidden attack surface. |
| F259 | P1 | `__init__.py:1694,1700` | `"terrain_validate_tile_seams"` and `"env_validate_tile_seams"` both point to same function. Future divergence will silently miss one. |
| F260 | P1 | `__init__.py:1040-1080` | `equipment_generate_weapon` implements 6-way if/elif chain via nested conditionals inside a dict value. Unreadable. Unknown weapon type silently generates a sword. |
| F261 | P0 | `blender_addon/__init__.py:96-97` | `_auto_start_timer = _deferred_auto_start` registers module reference. Addon reload creates NEW object, `unregister_timer(_auto_start_timer)` compares against OLD → `is_registered` returns False → **orphan timer stays**, two servers attempt port 9876, second errors OSError but first keeps running → addon state out of sync. |
| F262 | P1 | `blender_addon/__init__.py:100-109` | `unregister` only stops `_server`, not in-flight background `_handle_client` threads. Reload orphans daemon threads holding state. |
| F263 | P0 | `socket_server.py:109-113` | `result_event.wait(timeout=300)` — 5min. Handlers that exceed KEEP RUNNING on main thread. Next command STOMPS result_event (no per-cmd id). **Race: slow command N's result silently overwrites fast command N+1's result.** |
| F264 | P0 | `socket_server.py:167-203` | `_process_commands` pops ONE command per 10ms tick. **Throughput ceiling 100 cmd/sec regardless of handler speed.** |
| F265 | P0 | `socket_server.py:186-192` | Wraps in `{"status":"success","result":...}` only when handler doesn't already have `status` key. Handler returning `{"status":"partial"}` bypasses wrapper → downstream checking `== "success"` silently treats partial as error. |
| F266 | P0 | `socket_server.py:123-127` | **No outbound size cap.** Handler returning 100MB dict crashes `sendall` with BrokenPipeError. Caller gets "Server error" with no info. |
| F267 | P0 | `socket_server.py:111` | `command_queue.put(...)` unbounded. 1000 queued commands → memory explosion. `queue.Queue` no `maxsize`. |
| F268 | P0 | `socket_server.py:80-154` | `_handle_client` runs in BACKGROUND thread and enqueues to `command_queue`. Response is `json.dumps`'d in background using result dict written by main. If handler stashes a `bpy.types.Object` into result, serialization reads object properties from background thread → **Blender API violation → random crash.** |
| F269 | P1 | `socket_server.py:34,227` | `bpy.app.timers.register(..., persistent=True)` — survives file-load. User opens new `.blend` → timer polls queue bound to old server instance → **crash on scene reload.** |

## Round 3 findings — Codex Pass 2 (additional / cross-verifying)

| ID | Sev | File:line | Finding |
|---|---|---|---|
| F270 | P0 | `terrain_materials.py:1691-1695,1738-1742,1846-1849,2296` | **`terrain_materials.py` is split-brain.** Legacy API uses zones `ground/slopes/cliffs/water_edges`; V2 shader expects `ground/slope/cliff/special`. Two incompatible material systems coexist in one file. |
| F271 | P0 | `terrain_materials.py:1784-1789,2291-2292,2384-2400` | Two systems disagree on splatmap attribute names. Legacy paints `TerrainSplatmap_<biome>`; V2 shader reads `VB_TerrainSplatmap`. Cross-calling yields wrong attribute. |
| F272 | P0 | `terrain_materials.py:1860,1896,1902,1920,1937,2299-2334` | V2 palettes define translucent layers via `alpha`, but shader never reads `alpha`, never sets `blend_method`, never wires transparency. **"Translucent" is fiction.** |
| F273 | P0 | `terrain_materials.py:1840-1844,2299-2334` | V2 layer keys `roughness_variation`, `wear_intensity`, `node_recipe` are **declared required** but the actual shader builder ignores all of them. Different recipes collapse to the same noise+bump template. |
| F274 | P1 | `terrain_protocol.py:4-5`, `environment.py:1545-1568`, `blender_server.py:5141,5227` | **Protocol gate is theater.** Default `enforce_protocol=False`. When enabled, environment neuters rule 2 with `out_of_view_ok=True` and rule 5 with `bulk_edit=True`, catches `ProtocolViolation` and returns `{ok: false}`. `@enforce_protocol` decorator is defined, unused. |
| F275 | P0 | `environment.py:1689-1692,1805-1808`, `_mesh_bridge.py:906-916,1042-1058` | Hero builders pass per-face `material_ids`, but `mesh_from_spec(...)` only validates them and then ignores on the Blender path. **Cliff/waterfall material partitioning is dropped.** |
| F276 | P0 | `_terrain_depth.py:139-220` | `env_build_cave_entrance` geometry is real tunnel-shell, BUT axis contract is **confused**: doc says depth is Y-axis (:139), code comment says "tunnel goes in -Z direction" (:167), emitted coords `(x, y_depth, z_height)`. |

---

# Round 3 totals

- **138 Round 1-2 findings** (F001-F138)
- **+138 Round 3 findings** (F139-F276)
- **= 276 total numbered findings**, 18+ categories
- **Severity (Round 3 only):** ~78 P0, ~52 P1, ~8 P2
- **Severity (all rounds):** ~119 P0, ~116 P1, ~41 P2

## Round 3 meta-pattern (updated)

1. **The production path is NOT one path — it is five.** Pass DAG, legacy compose_terrain_node call, compose_map, legacy cliff overlay, and cowork_bridge hand-scripts. Every round of investigation discovers another parallel path.
2. **Commit 85ea32e is present but orphaned.** Dead-delta fixes stored values in new channels, but NO code consumes those channels. Half-fix.
3. **Hero builders are paper-thin single-surface grids** (F155, F156, F159). Volumetric contract is a test-only module (F162).
4. **The five divergent paths each create and discard their own state.** Materials are split-brain (F270). Shaders advertise features they don't implement (F272, F273). Protocol gate is theater (F274).
5. **Tests validate modules that are never called and mock the path that actually runs.** F222-F224 confirm this definitively.
6. **`cowork_bridge/rebuild_riftpass_01.py` is authoring evidence** that the production screenshots the user evaluates come from a hand-driven TCP workflow, not the MCP pipeline. That script knows how to write slope-based shaders (F206) but that knowledge never made it upstream.
7. **Socket server has a race where slow command N clobbers fast command N+1's result** (F263). Plus unbounded queue (F267) and background-thread bpy crash (F268). Pipeline reliability has a hard ceiling.
8. **41 Round-1/2 P0s + 78 Round-3 P0s = 119 P0s total.** The system is not broken in one place; every layer has silent failures.

## Top 20 new P0 fires to put out first

1. **F147** — `handle_generate_terrain` silently disables erosion when heightmap supplied (explains why most tiles have no erosion)
2. **F154, F157, F155, F159** — Hero builders are paper-thin grids with hardcoded params
3. **F162** — `terrain_waterfalls_volumetric.py` is validator-only, never enforced
4. **F167** — `handle_carve_river` height_scale fallback amplifies flats by 100x
5. **F168** — `handle_export_heightmap` garbles if grid detection wrong
6. **F170, F171** — Frozen dataclasses with mutable Dict fields break hashing
7. **F178** — f64 dominance doubles memory for every terrain run
8. **F184** — Bundle M completely missing from registrar
9. **F185** — Partial registration can corrupt PASS_REGISTRY silently
10. **F188, F189, F203** — Unity C# reader endianness + size validation + PNG-vs-RAW ambiguity
11. **F197, F198** — Production pipeline validator schemas LIE about required params
12. **F204-F209** — `cowork_bridge/rebuild_riftpass_01.py` uses EXACT Boolean on dense mesh, then `hide_render=True` on the sculpted cliff
13. **F225, F228** — Hero builder and export failures counted as successes
14. **F230** — User-supplied protected_zones dropped silently
15. **F234** — Three cliff systems run per compose_terrain_node call, uncoordinated
16. **F237** — `blender_environment` build_* branches reference undeclared `position` parameter → latent NameError
17. **F248** — `handle_scatter_props` passes wrong arg → every prop at Z=0 silently
18. **F254-F256** — worldbuilding.py silent swallows hide castle/GLB/terrain-alignment failures
19. **F261** — Addon reload orphans timer → two servers fight for port 9876
20. **F263, F266, F267, F268** — Socket server races + outbound cap missing + unbounded queue + background-thread bpy crash

Fix architecture must address: (a) the 5 divergent paths → unify to one, (b) hero builders → real volumetric mesh geometry, (c) material system → one shader using real textures + triplanar + UV, (d) Unity side → real manifest consumer, (e) socket server → thread safety + numpy encoder + traceback propagation, (f) state machinery → frozen-mutable cleanup + determinism hash audit.

---

# ROUND 4 APPENDIX (2026-04-11 late evening)

**Dispatched:** 6 Opus agents + 3 codex-5.4 passes in parallel.
**All agents completed with clean findings.**
**New findings:** ~354 numbered, spanning F277-F767 with some gaps.

## Round 4 meta-findings (corrections + biggest reveals)

- **FALSIFIED F003** — Codex R4A + Opus G F409 confirm: `pass_erosion` DOES call `stack.set("bank_instability",...)` and `stack.set("talus",...)` at `_terrain_world.py:564-565`. These are real writes; the prior finding was wrong. F003 needs retraction. The actual bug is that `pass_navmesh`'s channel guards (`if stack.X is not None`) still short-circuit because the timing is wrong or the test doesn't boot the pipeline. Needs re-verification.
- **FALSIFIED F138** — Opus I F527 confirms the six `geometry_nodes.py` `name="GN_*_{var}"` lines are inside outer `textwrap.dedent(f"""...""")` strings — the f-string interpolation resolves at Python source-generation time. Not a bug. **F138 retracted.** Real bug in same region: F529 — none of those 9 node_group creators have reuse guards, so rerunning creates `.001/.002/...` leaks.
- **RESOLVED F134** — Opus J (F577) confirms commit `85ea32e` is intact on HEAD and stores deltas in new channels `cave_height_delta` / `waterfall_pool_delta`. The fix was architectural: **"passes compute, never mutate"** was the deliberate design (per commit messages in `80a5f68`, `cb22267`). The missing consumer was never built. Wave 1/2 shipped this pattern on purpose. F001/F002 are still live in visuals.
- **NEW ARCHITECTURAL:** Commit `2735c70` (most recent on branch, Apr 11) **re-cements `erosion: "none"` into compose_map** AFTER the 85ea32e fix. The divergent path is actively maintained. This is not accidental drift — it is an ongoing choice.
- **NEW ARCHITECTURAL:** There is one master-only commit `2877ed5` ("Deepen terrain audit and fix high-priority pipeline issues", Apr 10) **not merged into feature branch** (Opus J F562). Touches `addon_toolchain.py`, `blender_server.py`, `terrain_checkpoints_ext.py`, `terrain_unity_export_contracts.py`, `texture.py`. May contain real fixes we're missing.

## 🔥 THE BIGGEST BUG OF THE AUDIT (Round 4)

**F R4A CODEX — `_terrain_noise.py:928` `hydraulic_erosion`** — The droplet erosion primitive has a **sign bug**:
```
speed_sq = speed * speed + delta_h * gravity
```
This should be `- delta_h * gravity` (droplets accelerate going DOWN). As written, **droplets accelerate uphill and slow down going downhill**. Every terrain generated with the non-legacy noise erosion path has physically inverted erosion.

This is the erosion primitive used by `_terrain_noise.generate_heightmap` → `erode_world_heightmap` → `handle_generate_terrain` → `compose_terrain_node` via the legacy path. Combined with F147 (erosion silently disabled when heightmap supplied), this is why mountain passes don't look natural: either erosion doesn't run at all, or when it runs, it runs backwards.

---

## Round 4 findings — Codex R4A (terrain math primitives)

| ID | Sev | File:line | Finding |
|---|---|---|---|
| F277 | **P0** | `_terrain_noise.py:928` | **`hydraulic_erosion` sign bug:** `speed_sq = speed*speed + delta_h*gravity` — droplets accelerate UPHILL. Physics inverted. |
| F278 | P0 | `_terrain_noise.py:366` | `generate_heightmap` with default `normalize=True` returns all zeros for any 1x1 request — `hmin == hmax` branch collapses to `np.zeros_like`. |
| F279 | P0 | `_terrain_noise.py:794` | `carve_river_path` hard-clips carved result to `[0,1]` — crushes world-unit heightmaps. `seed` param is unused. |
| F280 | P0 | `_terrain_noise.py:852` | `generate_road_path` — same `[0,1]` clip + unused seed. |
| F281 | P0 | `terrain_advanced.py:793` | `compute_erosion_brush` interprets `terrain_origin` as min corner while `handle_erosion_paint` passes object center — brush placement shifted by ~half terrain span. |
| F282 | P0 | `terrain_advanced.py:1245` | `apply_stamp_to_heightmap` repeats same origin-contract bug as erosion brush — handler-driven stamps offset from requested world center. |
| F283 | P0 | `terrain_advanced.py:1592` | `handle_terrain_flatten_zone` normalizes `target_height` into [0,1] before blending into world-unit Z data — explicit flatten heights land at wrong elevation. |
| F284 | P0 | `_terrain_depth.py:439` | `generate_terrain_bridge_mesh` only yaws the bridge, ignores endpoint pitch — bridges between different Z heights can't meet both endpoints. |
| F285 | P0 | `_terrain_depth.py:519` | `detect_cliff_edges` runs slope detection on raw heightmap values and applies `height_scale` only to outputs — normalized heightmaps under-report cliffs. |
| F286 | P1 | `terrain_advanced.py:281` | `compute_spline_deformation` `mode="smooth"` is a dead placeholder — ignores `neighbor_heights` scaffold, applies hardcoded 0.3 spline pull. |
| F287 | P1 | `terrain_advanced.py:1245` | `apply_stamp_to_heightmap` `falloff` parameter algebraically cancels: `edge_falloff * (1.0-falloff) + edge_falloff * falloff` = `edge_falloff`. Param is dead. |
| F288 | P1 | `terrain_advanced.py:910` | `handle_erosion_paint` never forwards `params["seed"]` — deterministic callers get internal default seed `42`. |
| F289 | P1 | `_terrain_world.py:415` | `pass_structural_masks` accepts `region` and `deterministic_seed_override`, ignores both — region-scoped runs still recompute whole stack. |
| F290 | P1 | `_terrain_world.py:457` | `pass_erosion` silently falls back to `"temperate"` for unknown profiles; thermal pass hardcoded to 6 iterations outside profile table. |
| F291 | P1 | `_terrain_world.py:593` | `pass_validation_minimal` docstring promises slope existence + finite validation over every channel — body inspects 4 channels, never fails on missing `slope`. |
| F292 | P1 | `_water_network.py:803` | `get_tile_contracts` returns live internal dict/list — external callers mutate network state in place. |
| F293 | P1 | `_water_network.py:817` | `get_tile_water_features` default `cell_size=1.0` ignores stored `_cell_size` — non-1m worlds return wrong tile bounds. |
| F294 | P1 | `_water_network.py:995` | `assign_strahler_orders` swallows `setattr` failures; `to_dict()` uses `asdict()` which drops dynamic `strahler_order` anyway — double dead. |
| F295 | P1 | `_terrain_depth.py:311` | `generate_waterfall_mesh` — `steps` unvalidated, `height/steps` raises ZeroDivisionError on public `steps=0`. |
| F296 | P1 | `_terrain_noise.py:198` | `TERRAIN_PRESETS` / `BIOME_RULES` exported as mutable module-level dict/list — runtime mutation globally changes future terrain generation. |
| F297 | P1 | `_terrain_noise.py:1157` | `ridged_multifractal` scalar uses `_RealOpenSimplex.noise2` when library present; `ridged_multifractal_array` uses inherited Perlin fallback — same seed drifts between scalar and vector paths. |
| F298 | P1 | `_terrain_noise.py:1278` | `domain_warp` has same backend split as `domain_warp_array` — scalar and vectorized warps disagree. |
| F299 | P1 | `_terrain_noise.py:1509` | `generate_heightmap_with_noise_type` `"hybrid"` mode forwards almost none of `**kwargs` to Perlin half — warp/normalize/preset silently ignored. |
| F300 | P2 | `_terrain_noise.py:1584` | `auto_splat_terrain` — `biome` param accepted but never used. |

## Round 4 findings — Codex R4B (blender_server.py unaudited)

| ID | Sev | File:line | Finding |
|---|---|---|---|
| F320 | P1 | `blender_server.py:3064-3069` | `generate_prop` claims "using procedural generator" when Tripo credentials absent — but only returns an error/fallback message, never actually invokes any procedural fallback. |
| F321 | **P0** | `blender_server.py:4267-4341` | `generate_map_package` **suppresses per-object game-check, LOD, and FBX export failures**. Reports success whenever any FBX was written. **Incomplete district packages ship as healthy.** |
| F322 | P1 | `blender_server.py:4386-4430` | `aaa_verify` compacts surviving screenshot paths then rebuilds `angle_labels` by truncating original angle list — mid-sequence capture failure mislabels screenshots and corrupts per-angle attribution. |
| F323 | **P0** | `blender_server.py:4481-4520`, `__init__.py:1736-1737` | **`performance_check` is wired to a stub `performance_budget_check` handler that returns only `not_implemented`.** MCP action fabricates 0 tris, 0 draw calls, and a passing summary for any scene. |
| F324 | P1 | `blender_server.py:4532-4540`, `mesh_enhance.py:1003-1018` | `generate_lod_chain` reports success even when source object doesn't exist — helper returns synthetic LOD spec instead of failing. |
| F325 | P1 | `blender_server.py:4643-4654, 4708-4737` | `compose_interior` checkpoint resume only covers room-generation loop — linked interior, geometry enhancement, and storytelling-prop passes ignore completion markers and duplicate scene content on resume. |
| F326 | P1 | `blender_server.py:4741-4759`, `prop_quality.py:266-321` | `compose_interior` prop quality stage validates room shell object per room, **not the props spawned by `env_add_storytelling_props`**. Advertised prop gate never inspects generated props. |
| F327 | P1 | `pipeline_runner.py:495-497`, `export.py:319-341` | `batch_process` leaks selection state between items — export step calls `export_gltf` with `selected_only=True` but never selects target object. Each batch item exports whatever happens to be selected from prior steps. |
| F328 | P1 | `blender_server.py:4975-4999, 5031-5048` | `import_model`, `import_and_process`, `full_pipeline`, `generate_and_process` all misuse `execute_code` as if it returned last expression — imported-object discovery falls back to filename stem instead of actual imported mesh names. |
| F329 | P1 | `blender_server.py:5175-5190`, `execute.py:190-199` | `terrain_pipeline list_passes` and `list_bundles` execute bare expressions through `execute_code` — but `execute_code` only captures stdout. **Subcommands return empty wrapper payloads instead of actual registered lists.** |
| F330 | **P0** | `blender_server.py:5192-5208`, `environment.py:1539-1571`, `terrain_checkpoints.py:120-127` | **`terrain_pipeline list_checkpoints` and `rollback` are nonfunctional by design.** Each terrain run creates a fresh controller and discards it; subcommands call controller-bound helpers without a controller argument. Checkpoint listing/rollback cannot work across MCP calls. |
| F331 | P2 | `addon_toolchain.py:646-653, 751-787` | `inspect_external_toolchain` live contract omits `selection` and `disabled_but_installed` fields from `agent_contract` even though the terrain protocol tells agents to read them. "Capability" probe is a static `EXTERNAL_ADDON_SPECS` name match, not a deeper capability check. |

## Round 4 findings — Codex R4C (Unity compound tools)

**11 DEAD ACTION REFERENCES in production_templates.py** — every built-in Unity pipeline step routes to nonexistent actions:

| ID | Sev | File:line | Finding |
|---|---|---|---|
| F360 | P0 | `production_templates.py:146` | `create_character.mesh_import` → nonexistent `unity_assets.fbx_import`. Real action name differs. |
| F361 | P0 | `production_templates.py:152` | `create_character.prefab_create` requires `type`, but `unity_prefab.create` takes `prefab_type`. Schema lies. |
| F362 | P0 | `production_templates.py:176` | `create_item.mesh_import` repeats dead `unity_assets.fbx_import`. |
| F363 | P0 | `production_templates.py:178` | `create_item.material_setup` → nonexistent `unity_assets.material_auto_generate`. Doubly invalid. |
| F364 | P0 | `production_templates.py:180` | `create_item.icon_render` → nonexistent `unity_camera.virtual_camera`. Real action is `create_virtual_camera`. |
| F365 | P0 | `production_templates.py:182` | `create_item.prefab_create` — same `type` vs `prefab_type` mismatch. |
| F366 | P0 | `production_templates.py:184` | `create_item.loot_table_add` → nonexistent `unity_content.loot_table`. Real action is `create_loot_table` with different params. |
| F367 | P0 | `production_templates.py:193` | `full_build.run_tests` → nonexistent `unity_qa.test_runner`. Real action is `run_tests`. |
| F368 | P0 | `production_templates.py:197` | `full_build.build` requires `build_target`, but `unity_build.build_multi_platform` uses `platforms`. Schema lies. |
| F369 | P0 | `production_templates.py:199` | `full_build.smoke_test` → nonexistent `unity_qa.play_session`. |
| F370 | P0 | `production_templates.py:1340` | `generate_pipeline_orchestrator_script` never invokes MCP tools — marks every step successful on a delayed callback. **"Orchestrator" is theater.** |
| F371 | P1 | `camera_templates.py:174` | Dolly mode adds `CinemachineSplineDolly` without assigning any spline/path source — dolly camera cannot produce usable travel shot. |
| F372 | P1 | `audio_templates.py:386` | `setup_audio_zones` places each reverb zone at Scene view camera instead of deriving bounds from cave/interior/terrain data. No terrain-aware reverb. |
| F373 | P1 | `vfx.py:152` | Environmental VFX actions forward only `effect_type` / `area_size` — no terrain/splatmap/heightmap/zone inputs. Mist/god-rays/dust cannot bind to terrain features. |
| F374 | P1 | `world_templates.py:826` | `paint_terrain_detail` fills every detail layer with constant density map over full active terrain — ignores slope, height, biome, splat. |
| F375 | P1 | `world_templates.py:2595` | `create_terrain_blend` derives depression radius solely from `terrainData.size.x`, reuses on both axes — non-square terrains get distorted depressions. |
| F376 | P1 | `world_templates.py:610` | `setup_occlusion` only scans `Renderer` objects — Unity `Terrain` components never marked as occluders/occludees. |
| F377 | P1 | `world_templates.py:236` | Multiple generated world scripts emit `status: ok` instead of toolkit's usual `status: success` — inconsistent contract. |
| F378 | P1 | `world_streaming_templates.py:48` | `setup_map_streaming` groups only named FBX objects by district, hardcoded path — terrain tiles, TerrainData, raw heightmaps excluded from streaming. |
| F379 | P1 | `quality_templates.py:734` | Combined AAA audit only scans `Mesh`, `Texture2D`, `Material` — `TerrainData`/`TerrainLayer` never participate in quality gates. |
| F380 | P1 | `performance_templates.py:326` | `setup_lod_groups` only processes `MeshRenderer` + `_LOD#` siblings — cannot configure Unity Terrain LOD/streaming. |
| F381 | P1 | `game_templates.py:142` | Generated save schema stores only coarse strings (`currentLocation`, discovered states) — no player transform, terrain tile, or streamed-world state. **Terrain-dependent restores not save-compatible.** |

## Round 4 findings — Opus G (contract YAML drift)

54 findings F400-F453. Highlights:

| ID | Sev | File:line | Finding |
|---|---|---|---|
| F400-F408 | P2 | `terrain.yaml` throughout | **9 line-number drifts** — contract claims pass defs at wrong lines (off by 1-140). |
| F409 | P1 | `terrain.yaml:50` vs `_terrain_world.py:564-565` | `pass_erosion` mutates list omits `bank_instability` + `talus` but code DOES write them. **Falsifies F003** — the prior "dead-delta" claim was wrong. |
| F410 | P0 | `terrain.yaml:98` | Contract misses `waterfall_pool_delta` write — orphan channel undeclared. |
| F411 | P0 | `terrain.yaml:165` | Contract misses `cave_height_delta` write — same orphan pattern. |
| F418 | P0 | `terrain.yaml:101-103` | P0-004 status description stale — omits the half-fix (delta IS now on stack). |
| F419 | P0 | `terrain.yaml:167-169` | P0-008 stale wording — `_delta … discarded` misdescribes current half-fix. |
| F425 | P1 | `terrain.yaml:17-21` | Bundle counts stale: `total_bundles: 18, registered_bundles: 15` — actual registrar has 14 distinct bundles. |
| F432 | **P0** | `REQUIREMENTS.md:95` | **CITY-01 marked `[x]`** — "Generate full terrain with cliffs, waterfalls, rivers" — all three are dead-delta or unwired. **Checkmark is false.** |
| F433 | **P0** | `REQUIREMENTS.md:96` | **CITY-02 marked `[x]`** — "Generate starter city integrated into terrain" — terrain-conforming foundations not implemented. **False.** |
| F434 | P1 | `REQUIREMENTS.md:53` | WIRE-09 marked `[x]` — "Wire coastline + 7 dead terrain features" — 4 of 7 still dead. |
| F438 | P0 | `STATE.md:50` | Claims "A1 Terrain contract YAML: ✅ Complete" — 15+ drift facts proven. **State lies.** |
| F440 | P1 | `ROADMAP.md:52` | Phase 18 marked `[x]` — 3 of 5 terrain generators have zero callers outside their own file. Hides dead code. |
| F441 | P1 | `ROADMAP.md:500` | Phase 26 promises "50,000+ droplets" — actual profile caps at 600 iterations. |
| F442 | P1 | `ROADMAP.md:532-541` | Phase 34 "Building foundations generate terrain-conforming meshes" — no flatten code in environment.py or terrain_*.py. Stale claim. |
| F443-F447 | P1 | `.planning/phases/31-*`, `34-*`, `39-*`, `42-*` | Phase summaries claim deliverables that contradict live P0s. Five phase docs misreport state. |
| F451 | P1 | Meta | **F003 in current FINDINGS.md ratifies a bug that is already fixed** — retract per `feedback_no_bug_ratifying_tests.md` rule. |

## Round 4 findings — Opus H (test suite)

33 findings F450-F482. Highlights:

| ID | Sev | File:line | Finding |
|---|---|---|---|
| F450 | **P0** | `test_terrain_waterfalls.py:335` | **`test_build_outflow_channel_returns_delta` asserts `np.testing.assert_array_equal(stack.height, h_before)`.** **Literally ratifies F002** — test PASSES because waterfall is never merged into height; fixing the bug will BREAK this test. Textbook bug-ratification. |
| F451 | P0 | `test_terrain_caves.py:569-573` | `test_pass_caves_populates_channels_and_structures` asserts `.get("cave_candidate") is not None`, `cave_count==2`, side_effect string — **zero assertion that height was carved**. Passes on stub. |
| F452 | P0 | `test_terrain_cliffs.py:271-283` | Same stub-ratifying pattern. |
| F453 | P0 | `test_terrain_cliffs.py:286-296` | Asserts `"cliff_structure:"` substring in side_effects. Ratifies intent strings. |
| F454 | P0 | `test_terrain_cliffs.py:360-371` | Canonical F130 instance — `"insert_hero_cliff_mesh"` intent string test. |
| F455 | P1 | `test_terrain_waterfalls.py:255-260` | Asserts `stack.foam is not None`, etc. — zero verification of volumetric geometry. |
| F457 | P1 | `test_full_terrain_pipeline.py:69-88` | `test_register_all_terrain_passes_loads_bundle_a` asserts `"A" in loaded` — but `loaded` contains `"A:SKIPPED(...)"` on failure, and substring test still passes. **Registration failures satisfy it.** |
| F458 | P1 | `test_full_terrain_pipeline.py:78-88` | Filters `:SKIPPED` then asserts `>= 5`. Accepts two-thirds of bundles silently failing. Bundle M missing and test passes. |
| F459 | P0 | `test_full_terrain_pipeline.py:196-205` | `test_pass_validation_full_runs_end_to_end` only asserts `isinstance(result, PassResult)`. Per F029, rollback failure silently swallows into `metrics["rollback_error"]`. Test passes on silent rollback. |
| F461 | **P0** | `tests/conftest.py:11-98` | **Global `MagicMock` stub for bpy/bmesh/mathutils/gpu.** Every handler import resolves bpy to a MagicMock. **Root cause of why 21,000+ tests missed 41 P0 bugs** — the bpy surface is a lie by construction. |
| F462 | P0 | `test_terrain_materials.py:757-816` | Shader node graph tested with `MagicMock` — returns MagicMock for `.new("ShaderNodeTexNoise")`. Shape doesn't match real bpy. **Test cannot fail regardless of shader correctness.** |
| F463 | P0 | `test_mcp_dispatch.py:11,23-28,458-541` | `AsyncMock` for all TCP calls. Verifies dispatch sequence, not output. F107 `erosion: "none"` hard-code is invisible to dispatch test. |
| F465 | **P0** | `test_terrain_composition.py:171-500` | Classes `TestMorphology`, `TestHierarchy`, `TestRhythm`, `TestNegativeSpace` cover Bundle H dead modules (F081). **~30 tests for code nothing invokes.** |
| F466 | P0 | `test_terrain_iteration.py:485-495` | Tests `terrain_hot_reload.HotReloadWatcher` + `reload_biome_rules` — per F091 module has zero production callers. |
| F467 | P1 | `test_bundle_bcd_supplements.py:6,32` | Tests `terrain_waterfalls_volumetric` — per F162 module is validator-only, never emits geometry. |
| F472 | **P0** | `test_weapon_quality.py:759-838` | **9 unconditional `@pytest.mark.xfail(strict=False)` on sword/axe/mace/bow/shield/staff/pauldron/chestplate/gauntlet vertex-count tests.** Marks real unmet AAA quality budgets as expected to fail. `strict=False` means they never fail CI. **Hides the "weapons too low-poly" bug class.** |
| F473 | P0 | `test_creature_anatomy.py:887-901` | 3 xfail markers on wolf/bear/chimera vertex counts. Same pattern — locks "creatures too low-poly" as expected. |
| F475 | P2 | Across 10+ files | Conditional `pytest.skip("No X generated")` hides empty-output bugs. When generator fails, test silently skips. |
| F476 | P1 | `test_no_silent_cube_fallbacks.py:40-43` | **File name is the lie** — it explicitly xfails "All N buildings have degenerate (1.0, 1.0) footprints -- known cube fallback bug". |
| F477 | **P0** | `scripts/regen_contract_tests.py:83-102` | `_check_mutates` is pure text regex — matches channel names in comments/docstrings/variable names. Does NOT verify `stack.set(...)` call. **L3 contract tests are architecturally incapable of catching dead-delta bugs.** |
| F478 | P0 | `scripts/regen_contract_tests.py:154` | "Not a stub" check is literally `loc > 5`. Docstring + return stub + blanks trivially passes. |
| F479 | P0 | `tests/contract/test_terrain_contracts.py:83-132` | **Contract tests are schema-only.** YAML loads, file exists, AST has function name, `is_stub != True`. Zero behavior assertions. **L3 layer is a table-of-contents validator, not a contract test suite.** |
| F480 | P0 | `test_full_terrain_pipeline.py:1-9` | **Integration test file explicitly says "does NOT require Blender".** Sole file under `tests/integration/`. **L6 Integration Gate is this 206-line pure-Python test.** |

## Round 4 findings — Opus I (non-terrain generators)

30 findings F520-F549. Highlights:

| ID | Sev | File:line | Finding |
|---|---|---|---|
| F520-F526 | P1/P2 | `execute.py:140-207` | Universal sandbox: no stdout truncation, no wall-clock timeout, only stdout captured (no stderr), swallows addon ImportError, shallow builtins copy, restricted import drops dotted imports, zero execution logging. |
| F527 | **P2 (CORRECTS F138)** | `geometry_nodes.py:529,634,785,...` | **F138 falsified.** F-strings resolve correctly at generation time. |
| F528 | P1 | `geometry_nodes.py` same lines | Generated names are unsanitised — `target_name="my rock.01"` produces `name="GN_Scatter_my rock.01"` with dots/spaces. |
| F529 | P1 | `geometry_nodes.py` 9 sites | **No reuse guard on `bpy.data.node_groups.new()`.** Every call leaks `.001/.002/...`. |
| F530 | P1 | `geometry_nodes.py:1169-1176` | `bpy.ops.object.modifier_apply` without context override — may fail silently on Blender 4.x. |
| F532 | P1 | `mesh_enhance.py:959-960` | `except Exception: pass  # Non-fatal` on curvature→roughness graph wiring — function still reports `"applied": True`. |
| F533 | **P0** | `mesh_enhance.py:1021-1058` | `auto_generate_lod_chain` is a datablock leak — new `{obj_name}_LOD_group` empty per call, no `.get()` lookup. |
| F536 | **P0** | `road_network.py:340-343` | **Heightmap indexing uses `int(py) % rows` — modulo wraps world coords around heightmap edge.** Waypoint at (500,500) samples from (244,244) on 256² map. Wrong cell, wrong Z, wrong bridge decision. |
| F537 | **P0** | `road_network.py:379-554` | **`_road_segment_mesh_spec` does not sample terrain at all.** Road Z values come only from linear interpolation of waypoint Z. Roads slice through hills and float over valleys. |
| F538 | P1 | `road_network.py:561-699` | `compute_road_network` accepts `terrain_heightmap=None` silent default — no warning, roads are flat interpolations. |
| F540 | **P0** | `_building_grammar.py:1083-1084` | **`except Exception: pass  # fall through to box expansion below`.** Entire rich detail mesh generation (buttresses, arches, ARCH-005) in blanket try. Any `TypeError` turns ALL buildings into boxes with zero log. **Direct explanation for "buildings are boxes" user complaint.** |
| F541 | P1 | `_building_grammar.py` whole file | Zero terrain_heightmap references. Building local-Z origins start at 0.0. |
| F542 | **P0** | `_settlement_grammar.py` whole file | Zero terrain awareness. Buildings placed on 2D grid. |
| F543 | **P0** | `_dungeon_gen.py:248,609,693,1016` | `generate_bsp_dungeon` / `generate_cave_map` / `generate_town_layout` / `generate_multi_floor_dungeon` — none accept or reference heightmap. Dungeon entrances land at Z=0 regardless of terrain. "Door in mid-air over a valley" bug. |
| F544 | P1 | `_biome_grammar.py:121,232` | Operates in (0,1) noise space — no coupling to heightmap-derived biome hints. Two independent biome sources. |
| F545-F547 | P1/P2 | `_mesh_bridge.py:1014,1027,1059-1065`, `modeling_advanced.py:635-659` | Datablock leak + silent material-assignment failure. |
| F548 | **P0** | Cross-file | **Systemic terrain-blindness in the non-terrain generator chain.** `_settlement_grammar → _building_grammar → _dungeon_gen → _biome_grammar → road_network → geometry_nodes` form a complete pipeline with **no shared `sample_terrain_height(x,y)` helper**. Every generator defaults to Z=0 and relies on an unwritten contract. |
| F549 | **P0** | Cross-file | **Systemic datablock-leak pattern** — `bpy.data.X.new()` without reuse guards across 5+ handler files. Every handler leaks on re-run. Needs shared `ensure_datablock` helper. |

## Round 4 findings — Opus J (git history + archive)

33 findings F560-F592. Highlights:

| ID | Sev | Finding |
|---|---|---|
| F562 | P1 | **`master` is AHEAD of feature branch** with `2877ed5` (Apr 10): "Deepen terrain audit and fix high-priority pipeline issues" — touches `addon_toolchain.py`, `blender_server.py`, `terrain_checkpoints_ext.py`, `terrain_unity_export_contracts.py`, `texture.py`. **Unmerged fixes.** |
| F571 | **P0** | `.planning/deliverables/Riftpass_01/REPORT.md` — **Step 5: "env_build_cliff_face → replaced by direct terrain carve in iter 11."** Step 6: "env_build_cave_entrance → reinforced with terrain mesh recess." Translation: authored pipeline's hero builders did NOT produce readable geometry; human manually carved verts via `blender_execute`. **F005/F108 confirmed blocking in practice, not theoretical.** |
| F573 | P1 | REPORT preset differs from `addon_toolchain.py:603-610` — two different sources of truth for `terrain_unity_ready_free`. |
| F575 | **P0** | Commit `80a5f68` (Wave 1) body: `"carve_impact_pool (returns delta, never mutates stack)"`. **Dead-delta bug was an intentional architectural choice** — "passes compute, don't mutate" without wiring a consumer. |
| F576 | P0 | Commit `cb22267` (Wave 2): same pattern. `"carve_cave_volume (returns delta not mutation)"`. Phantom Bundle H shipped in this commit. |
| F577 | P0 | Commit `85ea32e`: dead-delta half-fix CONFIRMED present. Adds `cave_height_delta` + `waterfall_pool_delta` channels. Fix is pass-DAG-local; actual Blender mesh still built from `solved_height` only. **F001/F002 fixed in metrics, still broken in visuals.** |
| F578 | P0 | `85ea32e` does NOT touch F003, F004, F005, F006. **Fixes 5 of 31 P0s; other 26 never scheduled.** |
| F583 | **P0** | Commit `2735c70` (most recent, Apr 11) — **re-cements `erosion: "none"` into compose_map** AFTER the 85ea32e P0 fix. F107 is actively maintained, not drift. |
| F584 | P0 | `2735c70` test coverage: `test_mcp_dispatch.py` (221 lines) mocks `send_command`, never validates visual output. Tests shipped with the hardening commit explicitly test the wrong layer. |
| F585 | P1 | `.planning/research/TERRAIN_FINAL_POLISH.md` — AAA research doc lists exact deliverables (micro-normal maps, cross-quad grass, wetness masks, skirt meshes, RNM normal blending, biome fog). **None are wired.** Research doc is a checklist of unbuilt AAA features. |
| F592 | P0 | Merge `ada9177` merged `origin/master` — but master moved forward again after the merge with `2877ed5`. F562 confirmed: one unreplicated master commit. |

## Round 4 findings — Opus K (materials deep)

22 findings F600-F621. Highlights:

| ID | Sev | File:line | Finding |
|---|---|---|---|
| F601 | **P0** | `texture.py:197,635` + grep | **Zero terrain paths import from `.texture`.** `handle_create_pbr_material` and `handle_load_extracted_textures` exist with full ShaderNodeTexImage + NormalMap + AO mix wiring — never invoked by any terrain, environment, settlement, or worldbuilding code. The entire real PBR builder is dead for terrain. **Generalizes F049 definitively.** |
| F603 | P1 | Cross-file | **Three disjoint rule schemas coexist** with no shared vocabulary: legacy `BIOME_PALETTES` (`ground/slopes/cliffs/water_edges`), V2 palettes (`ground/slope/cliff/special`), `MaterialRuleSet` (`ground/cliff/scree/wet_rock/snow`). Cross-calling yields silent attribute miss. |
| F604 | **P0** | `terrain_materials_v2.py:144,168` | **Snow line hardcoded `altitude_min_m=250.0`, scree line `altitude_max_m=200.0`** — absolute world Z meters. Terrain generated with default `height_scale=80` never reaches 250m → **snow channel produces zero contribution on every default terrain.** |
| F605 | **P0** | `environment.py:2776` | Multi-biome vertex-color path reads **legacy `BIOME_PALETTES`** but biome names come from V2 → every V2-only biome falls through to hardcoded `(0.15, 0.12, 0.10, 1.0)` dark-brown fallback. **16-biome world paints one uniform dark-brown.** |
| F610 | **P0** | All terrain materials | **Zero Displacement wiring anywhere.** `ShaderNodeOutputMaterial.inputs["Displacement"]` never linked. No POM, no tessellation, no `displacement_method='BOTH'`. Every terrain shader is surface-only. |
| F612 | **P0** | Repo-wide glob | **Zero shipped PBR texture assets.** 10 image files total, all user screenshots or coverage icons. F034 decisively confirmed: texture-less is not by choice — there is nothing to load. |
| F615 | P0 | Cross-file | **No actual triplanar shader node group exists anywhere.** `modular_building_kit.py:79-105` has CPU UV unwrapping called "triplanar" — not GPU shader sampling. V2 flag architecturally unimplementable. |
| F616 | **P0** | `terrain_materials.py:1851-1945` | **Every V2 biome pins `metallic: 0.0` across 64 slots.** Descriptions say "high metallic" for crystal_cavern/mountain_pass slope layers — values remain 0.0. **Field is dead; descriptions lie.** |
| F617 | P1 | `terrain_materials.py` | `node_recipe` (terrain/stone/organic) distinguishes per layer, zero code reads it. |
| F619 | P1 | `terrain_materials.py` | `emission_color/strength/subsurface_weight/alpha` appear in ~12 of 64 slots — reach `_get_material_def` but `_compute_vertex_colors_for_biome_map` reads only `base_color`. |

## Round 4 findings — Opus L (remaining terrain files, 118 findings)

F650-F767 — massive inventory across `terrain_advanced.py`, `terrain_features.py`, `terrain_sculpt.py`, `terrain_stratigraphy.py`, `terrain_checkpoints.py`, `terrain_chunking.py`, `terrain_pass_dag.py`, `terrain_pipeline.py`, `terrain_banded.py`, `terrain_ecotone_graph.py`, `terrain_geology_validator.py`, `terrain_roughness_driver.py`, `terrain_wind_field.py`, `terrain_wind_erosion.py`, `terrain_saliency.py`, `terrain_framing.py`, `terrain_cliffs.py` hero helpers, `terrain_karst.py`, `terrain_glacial.py`.

**P0 highlights (38 total in this section):**

| ID | File:line | Finding |
|---|---|---|
| F658 | `terrain_advanced.py:35-36` | `_detect_grid_dims` fallback `side = int(sqrt(len(bm.verts)))` — silent square assumption (duplicated from environment.py). |
| F664 | `terrain_advanced.py:625-633` | `flatten_layers` resize uses nearest-neighbor when layer res ≠ base — mixing resolutions silently aliases. |
| F676 | `terrain_advanced.py:1441-1443` | Snap origin `terrain.location.z + terrain.dimensions.z + 100` — terrain with Z-shift modifier has base location below surface → raycast misses above, silent "miss". |
| F680 | `terrain_features.py:915-1103` | `generate_natural_arch` has no ground interface mesh — pillars end at `-actual_pillar_h`, float on uneven ground. |
| F685 | `terrain_features.py:1110-1297` | `generate_geyser` `rng = random.Random(seed)` at 1147 — **declared and never used**. Dead variable. |
| F689 | `terrain_features.py:1304-1526` | `generate_sinkhole` uses `random.Random` AND `_hash_noise` interleaved — global state coupling. Two sinkholes in one session drift. |
| F693-F695 | `terrain_features.py:1533-1757` | `generate_floating_rocks` ring topology: `int(s*ratio) % r1_size` produces **duplicate triangles** when `ratio<1` and **skipped cells** when `ratio>1` — degenerate faces. |
| F697 | `terrain_features.py:1867-1872` | **`generate_ice_formation` stalactite material zoning uses stale outer-loop variable `kt`.** Every face gets the last stalactite's final `kt≈1` — all stalactite quads flagged `blue` (mat 2). |
| F700 | `terrain_features.py:2038-2044` | `generate_lava_flow` tangent computation at last segment uses previous segment's direction — flow has a kink at final vertex. |
| F710 | `terrain_checkpoints.py:48-53` | Module-level `_LABEL_REGISTRY`, `_AUTOSAVE_CONTROLLERS`, `_ORIGINAL_RUN_PASS` keyed by `id(controller)` — id reuse aliases distinct controllers. |
| F716 | `terrain_chunking.py:186-187` | `grid_cols = max(1, total_cols // chunk_size)` — integer floor **silently drops non-multiple-of-chunk_size rows**. 100-col input with chunk=64 → grid=1 → every col past 63 is silently dropped. |
| F721 | `terrain_pass_dag.py:25-56` | `_merge_pass_outputs` uses `setattr` bypass, then calls `compute_hash()` which has F172/F173 NaN/dict-channel bugs. |
| F722 | `terrain_pass_dag.py:62-68` | `_producers[ch] = p.name` last-wins — registrar file ordering silently picks producers. |
| F726 | `terrain_pipeline.py:110-111` | `register_pass` silently OVERWRITES duplicates. Hot reload + partial try/except → split pass registry. |
| F734 | `terrain_banded.py:181,206` vs `terrain_banded_advanced.py:20` | **`compute_anisotropic_breakup` DEFINED TWICE** — two incompatible implementations of same public name. Import shadow ambiguity. |
| F735 | `terrain_banded.py:224-234` | `apply_anti_grain_smoothing` tries scipy first, silently falls back to numpy on ImportError — **non-deterministic output based on environment.** |
| F745 | `terrain_roughness_driver.py:56-70` | Reads `erosion_amount` + `deposition_amount` channels — **never produced by any pass.** Guards return None → base `0.55` flat roughness always. |
| F747 | `terrain_wind_field.py:93-98` | Seed derivation doesn't consult `intent.seed` — same tile_x/tile_y produce same wind regardless of user seed. **Determinism violation.** |
| F754 | `terrain_framing.py:131` | `stack.set("height", ...)` — **new height writer confirmed**, adds to F007's multi-writer tally. |
| F756 | `terrain_cliffs.py:454-475` | **`insert_hero_cliff_meshes` is a placeholder** — literal comment: "Real bmesh geometry generation ships in a later Bundle B extension." Records intent strings, emits no geometry. |
| F761 | `terrain_karst.py:198-201` | `stack.set("height", ...)` — another multi-writer. |
| F764 | `terrain_glacial.py:239` | `stack.set("height", ...)` — another multi-writer. |
| F766 | `terrain_glacial.py:122-162` | `scatter_moraines` returns `(x,y,radius)` dicts — metadata only, no geometry. |

**Cross-cutting findings:**
- F650-F655: RNG clean (all use `np.random.default_rng(seed)`), no bare `np.random.random()`. But `time.time()` and `uuid.uuid4()` in checkpoint/telemetry layer cause filename-vs-content-hash drift (F651, F652).
- F656-F657, F681, F685, F689, F693: **Protocol Rule 4 drift** — `terrain_features.py` and `terrain_advanced.py` universally use Python stdlib `random.Random` instead of numpy's `default_rng`. Inconsistent with the rest of the codebase.
- F679: `terrain_features.py:33-34` module-level `_features_gen`, `_features_seed` cache mutated by `_hash_noise` — thread-unsafe under any future parallel pass DAG.
- F724-F725: Parallel DAG deep-copies state per worker (~1.2 GB per 1025² tile) — 5 GB peak RAM at max_workers=4.

---

# Round 4 totals

- **Round 1-2:** 138 findings (F001-F138)
- **Round 3:** 138 findings (F139-F276)
- **Round 4:** ~354 findings (F277-F767 with gaps)
- **Grand total:** ~630 numbered findings

**Severity (Round 4 only):** ~85 P0, ~230 P1, ~39 P2
**Severity (all rounds):** ~204 P0, ~346 P1, ~80 P2

## Retractions made in Round 4

1. **F003 FALSIFIED** — `pass_erosion` does write `bank_instability` and `talus` via `stack.set()` at `_terrain_world.py:564-565`. The bank_instability/talus "dead-delta" claim was wrong. Re-verify the navmesh consumption path.
2. **F077 FALSIFIED** (already retracted in R3 as F177) — `_load_records` is fully implemented.
3. **F134 RESOLVED** — commit `85ea32e` is intact, just a half-fix stored in new orphan channels. Not a revert.
4. **F135 RESOLVED** — `terrain_legacy_bug_fixes.py` is a misleadingly named static auditor, not a runtime fix (F161, F197, F580).
5. **F138 FALSIFIED** — `geometry_nodes.py` f-strings resolve correctly at generation time; real bug is F529 (no reuse guards).

## TOP 20 NEW P0 FIRES FROM ROUND 4

1. **F277** — `_terrain_noise.py:928` hydraulic erosion **sign bug on gravity** — droplets accelerate uphill. The entire legacy erosion primitive is physics-broken.
2. **F279, F280** — `carve_river_path` / `generate_road_path` hard-clip to `[0,1]`, crushing world-unit heightmaps. Both ignore `seed`.
3. **F281, F282** — `compute_erosion_brush` + `apply_stamp_to_heightmap` origin-contract mismatch — brush/stamp placement offset by ~half terrain span.
4. **F283** — `handle_terrain_flatten_zone` normalizes target_height to `[0,1]` before blending into world units.
5. **F321** — `generate_map_package` suppresses per-object failures; incomplete district packages ship as healthy.
6. **F323** — `performance_check` wired to `not_implemented` stub; returns 0 tris + passing summary always.
7. **F330** — `terrain_pipeline list_checkpoints/rollback` nonfunctional by design; controllers discarded between calls.
8. **F360-F370** — Unity `production_templates.py` has **11 dead action references** + schema lies across create_character/create_item/full_build pipelines. "Orchestrator" is theater.
9. **F432, F433** — `REQUIREMENTS.md` CITY-01 + CITY-02 marked done; both are demonstrably false.
10. **F438** — `STATE.md` lies about contract being "complete".
11. **F450** — `test_build_outflow_channel_returns_delta` **literally asserts `stack.height` is UNCHANGED** — textbook bug-ratifying test.
12. **F461** — Global `conftest.py` MagicMock stubs bpy/bmesh/mathutils — root cause of why 21,000+ tests missed 41 P0 bugs.
13. **F477, F479** — L3 contract tests use text regex for mutation check + schema-only assertions — architecturally incapable of catching dead-delta bugs.
14. **F480** — L6 "integration gate" is 206 lines of pure-Python pytest that doesn't boot Blender.
15. **F536, F537, F543, F548** — Non-terrain generators (`road_network`, `_dungeon_gen`, `_settlement_grammar`, `_building_grammar`) are terrain-blind end-to-end. No shared `sample_terrain_height` helper exists.
16. **F540** — `_building_grammar.py:1083` blanket `except Exception: pass` turns all rich building details into boxes. **Direct cause of "buildings are boxes" complaint.**
17. **F571** — Riftpass REPORT admits human manually carved verts via `blender_execute` because hero builders failed. F005/F108 confirmed blocking in practice.
18. **F583** — Commit `2735c70` (most recent) re-cements `erosion: "none"` AFTER the 85ea32e fix. Divergence is actively maintained.
19. **F601, F612** — texture.py real PBR builder exists, zero terrain paths import it. Zero PBR textures in repo.
20. **F604, F605, F610, F616** — V2 material system is architecturally dead: snow line unreachable at default height_scale, multi-biome falls through to dark-brown, zero Displacement wiring, metallic pinned to 0.0 across all 64 slots.

## Round 4 meta-pattern (updated)

1. **The production path is still five paths** — no change, but every path has new bugs. Round 4 added the divergent production_templates.py create_character/create_item/full_build pipelines which are **entirely dead** (11 nonexistent actions).
2. **The erosion foundation is physics-broken.** F277 means any terrain ever generated through `_terrain_noise.hydraulic_erosion` has inverted gravity. Combined with F147 (erosion silently disabled), F148 (double-erosion), F290 (silent fallback on unknown profile), erosion in VeilBreakers is fundamentally unreliable.
3. **Tests are the cause, not the cure.** F461 (global MagicMock conftest) + F477-F479 (L3 regex + schema-only contract tests) + F480 (L6 pure-Python integration) mean the quality infrastructure is structurally incapable of catching the bugs it claims to catch.
4. **L1-L6 defense-in-depth documented in CLAUDE.md is theater.** L1 (AST lint) catches trivial patterns. L2 (contract tests) is regex-only. L3 (behavior tests) is substance-good but tests the wrong layer. L5 (honesty lint) has a broken symbol extractor. L6 (integration) doesn't boot Blender. L0 (contract YAML) has 15+ drift facts and P0-016/P0-004 stale wording.
5. **11 dead Unity actions prove the same problem exists in Unity templates as in terrain.** Schema lies about required params, actions point to nonexistent handlers, "orchestrators" don't invoke tools.
6. **The single-directive Bundles N, M, legacy_bug_fixes.py, performance_check handler, performance_report, twelve_step stubs, terrain_hot_reload, enforce_budget, apply_differential_erosion, export_god_ray_hints_json, WaterfallVolumetricProfile all share the same pattern:** code exists, tests exist, production has zero callers.
7. **Five parallel terrain-authoring paths + Unity production pipelines with 11 dead actions + tests mocking everything = a toolkit where nothing is what it appears.**
8. **Master has unmerged fixes** (F562). Feature branch may be missing real work.
9. **The `feedback_no_bug_ratifying_tests.md` rule has been violated at least 10 times.** F450 is the worst (`assert_array_equal(stack.height, h_before)`). F472-F473 lock "weapons too low-poly" and "creatures too low-poly" as expected to fail.

Fix strategy remains unchanged from Round 3 summary: unify the 5 paths, build real hero geometry, wire real textures, build Unity consumer, fix socket thread safety, audit frozen/mutable dataclasses. Round 4 adds: **fix the gravity sign in `_terrain_noise.py:928` before anything else** — that's the foundation primitive.

---

# Round 5 — Node Generation + Merging + Erosion Integration Scan (2026-04-11)

**Agents dispatched:** 7 Opus agents in parallel
**Focus:** node generation, node merging/stitching, pass DAG + materials, scatter/rivers/Tripo, tests/quality, socket server + Unity, architecture fit for analytical erosion
**New references:** runevision analytical erosion filter, lpmitchell/AdvancedTerrainErosion (C# Burst port), Perlin noise hash optimization (Miles Oetzel)

## Round 5 findings (deduplicated, renumbered F800-F899)

### NODE GENERATION — Seam System Failures

| ID | Sev | Location | Finding |
|---|---|---|---|
| F800 | P0 | blender_server.py:892-917 | **Seam guard zones are a complete no-op.** `_build_tile_edge_protected_zones` returns zone dicts WITHOUT `allowed_mutations` or `forbidden_mutations` keys. `ProtectedZoneSpec` defaults both to `frozenset()`. `permits()` returns True for ALL passes. The entire seam protection system protects nothing. |
| F801 | P0 | _terrain_erosion.py:132-253 | **Droplet erosion destroys tile seams.** Per-tile random droplet positions + droplets killed at array edges (ix < 1 or ix >= cols-2) create systematic edge artifacts. Adjacent tiles erode independently → visible seam discontinuities. |
| F802 | P0 | _terrain_erosion.py:106 | **Erosion is tile-local, not world-coherent.** No overlapping windows, no neighbor data padding. Erosion patterns abruptly stop at tile boundaries. Analytical erosion filter (per-point eval) is the architectural fix. |
| F803 | P1 | environment.py:1023 | **Legacy handler uses normalize=True** — per-tile min/max normalization guarantees adjacent tiles won't match at seams. compose_terrain_node correctly uses normalize=False, but direct `generate_terrain` callers get broken tiling. |
| F804 | P1 | environment.py:1023 | **Legacy handler missing world_origin params** — generate_heightmap called without world_origin_x/y, so all standalone tiles sample noise from (0,0). Multiple tiles = identical heightmaps. |
| F805 | P1 | _terrain_noise.py:163-186 | **OpenSimplex wrapper uses different noise for scalar vs array.** noise2() calls real opensimplex, noise2_array() inherits Perlin gradient noise. Same (x,y) returns different heights depending on call path. |
| F806 | P2 | _terrain_noise.py:529-535 | **Smooth post-process box blur not tile-safe.** np.pad(mode="edge") duplicates edge values → 1px seam artifact. |
| F807 | P2 | _terrain_noise.py:537-563 | **Crater/volcanic preset uses tile-local center.** Volcano straddling tile boundary → multi-crater artifact. |

### NODE MERGING — Missing Architecture

| ID | Sev | Location | Finding |
|---|---|---|---|
| F810 | P0 | (missing) | **No node registry / world graph exists.** No data structure tracks which nodes exist, their coordinates, or neighbor relationships at authoring time. |
| F811 | P0 | (missing) | **No cross-tile edge comparison ever performed.** `validate_tile_seam_continuity` is self-referential — checks own edges, never loads/compares neighbor data. Riftpass_01 "4 neighbors PASS" was internal-consistency only. |
| F812 | P0 | (missing) | **No hero geometry blend-down protocol.** Seam guard prevents placement at edge but no smooth falloff. Cliff carved 16 cells from border creates height discontinuity. |
| F813 | P1 | terrain_pipeline.py:134-163 | **Protected zone enforcement is permissive.** Partial intersection explicitly allowed. Erosion, waterfalls, materials_v2 have NO per-cell zone checking. Only cliffs/caves/vegetation implement `_protected_mask_for_*`. |
| F814 | P1 | blender_server.py:3302-3376 | **Seam validation is verify-only, not repair.** If validation fails → warning string appended. No repair, no re-erosion, no edge blending. `handle_stitch_terrain_edges` exists but never called from compose_terrain_node. |
| F815 | P1 | environment.py:1842-1904 | **Stitch function uses local-space coordinates.** Tiles with different `obj.location` offsets → vertex local coords don't correspond to same world position. |
| F816 | P1 | environment.py:1872 | **Stitch hard-fails on vertex count mismatch.** No interpolation or nearest-vertex fallback. Any pass that changes topology (subdivision, remesh) breaks stitcher. |
| F817 | P1 | _terrain_erosion.py:259,273 | **Erosion uses np.pad edge mode, creates false boundaries.** Duplicated border values create artificial "wall" deflecting erosion away from edges. Should pad with neighbor tile data. |
| F818 | P2 | terrain_materials_v2.py:53 | **Triplanar flag exists but no cross-tile UV continuity.** Cliff materials set triplanar=True, but pass_materials only computes splatmaps — actual triplanar projection per-tile-independent. |

### PASS DAG — Dead Deltas + Missing Integrator (confirmed from R1-R4)

| ID | Sev | Location | Finding |
|---|---|---|---|
| F820 | P0 | terrain_waterfalls.py:741 | **CONFIRMED: waterfall pool_delta written to channel, never merged into stack.height.** Pools and outflow channels invisible on final heightmap. |
| F821 | P0 | terrain_caves.py:868 | **CONFIRMED: cave_height_delta written to channel, never merged.** Module docstring expects downstream integrator — that pass was never built. |
| F822 | P0 | (missing) | **No integrator pass exists.** Pipeline runs macro_world → ... → waterfalls → materials, with no delta-integration step. Bundles C+F compute deltas by design, but the consumer was never written. |
| F823 | P0 | blender_server.py:3680-3696 | **CONFIRMED: compose_map bypasses pass DAG entirely.** Calls env_generate_terrain directly — no waterfalls, caves, cliffs, V2 materials, scatter, or validation passes run. |
| F824 | P1 | terrain_waterfalls.py:787-790 | **waterfall_pool_delta not declared in produces_channels.** Registration says produces ("waterfall_lip_candidate", "foam", "mist", "wet_rock") — missing the delta. |
| F825 | P1 | terrain_caves.py:900 | **cave_height_delta not declared in produces_channels.** Registration says ("cave_candidate", "wet_rock") — missing the delta. |
| F826 | P1 | terrain_materials_v2.py:269 | **V2 material weights computed but never wired to Blender.** pass_materials writes numpy arrays to stack — no downstream pass creates materials, vertex colors, or mesh attributes from them. |
| F827 | P1 | terrain_materials.py:2384-2400 | **Material auto-assign uses local vertex positions, not pass DAG data.** Disconnected from curvature/wetness/drainage channels. |
| F828 | P1 | terrain_materials_v2.py:269 | **Material weights have no cross-tile continuity.** Slope/curvature at boundary cells use one-sided finite differences (no neighbor data). |

### SCATTER / RIVERS / TRIPO

| ID | Sev | Location | Finding |
|---|---|---|---|
| F830 | P0 | environment_scatter.py:1690 | **Prop scatter height sampler uses wrong object name.** Terrain objects rarely named "PropScatter" → sampler returns None → all props at Z=0 (silent fallback line 1716). |
| F831 | P0 | environment_scatter.py:1716-1718 | **Prop scatter has zero slope filtering.** Props placed on any slope including vertical cliffs. Vegetation path reads slope_map; prop path does not. |
| F832 | P0 | (missing) | **Rivers have no 3D geometry.** _water_network.py stores waypoint lists, handle_carve_river deforms heightmap, but no water surface mesh is ever created. No pass_rivers exists. |
| F833 | P1 | terrain_waterfalls.py (all) | **Waterfalls are mask-stack data only.** WaterfallVolumetricProfile defines volumetric spec, validate function exists, but the mesh builder "separate bundle" referenced in docstring was never written. |
| F834 | P1 | environment_scatter.py (all) | **Scatter never reads ridge_map or analytical erosion output.** Slope is recomputed via finite-difference from vertex Z, not from erosion filter gradient. |
| F835 | P1 | environment_scatter.py:1584-1590 | **Slope alignment gradient uses normalized [0,1] heightmap.** Gradient magnitude scaled by height_range/terrain_width → under-rotated on tall terrain, over-rotated on flat. |
| F836 | P1 | environment.py:294-363 | **Tripo environment manifest is data-only.** Biome presets build manifest dict but no downstream function calls Tripo. Scatter uses procedural generators exclusively. |
| F837 | P2 | environment.py:2038-2052 | **River carving destroys negative heights.** Normalizes by dividing by max → Z<0 terrain clamped/inverted. |
| F838 | P2 | terrain_water_variants.py | **Water surface/wetness masks produced but no mesh consumer.** Bundle O is pure numpy — no Blender geometry. |

### TEST INFRASTRUCTURE

| ID | Sev | Location | Finding |
|---|---|---|---|
| F840 | P0 | tests/ (global) | **No test verifies terrain passes modify heightmap correctly in aggregate.** End-to-end test only asserts `r.status == "ok"`. A pass_erosion that does `pass` satisfies every test. |
| F841 | P1 | tests/ (global) | **Zero tests for terrain node edge-matching.** No test composes two adjacent nodes and validates height continuity at their shared boundary. |
| F842 | P1 | scripts/test_substance_lint.py:247 | **Lint blind to np.testing.assert_*.** Only recognizes bare `assert` and unittest self.assertX(). At least 3 tests wrongly flagged SHALLOW. |
| F843 | P1 | tests/test_terrain_noise.py:52-105 | **6 terrain type tests structurally identical.** Each asserts shape==(64,64), min>=0, max<=1. A generate_heightmap ignoring terrain_type passes all six. |
| F844 | P1 | tests/test_terrain_wiring_integration.py | **"Integration" test explicitly avoids geometry verification.** Self-described "intentionally a smoke test." |
| F845 | P2 | terrain_semantics.py:687,768 | **Frozen dataclass with mutable Dict field.** HeroFeatureSpec and TerrainIntentState bypass frozen protection via dict mutation. |

### SOCKET SERVER / UNITY

| ID | Sev | Location | Finding |
|---|---|---|---|
| F850 | P0 | unity_server.py + unity_tools/ | **Zero Unity-side AdvancedTerrainErosion integration.** No tool, action, template, or placeholder for the new erosion package. No C# template generates erosion code. |
| F851 | P1 | unity_tools/scene.py:174 | **Blender-Unity terrain size mismatch.** Default terrain_size (1000,600,1000) vs Blender 256x256. No auto-bridging; Blender export includes terrain_world_size but Unity doesn't read it. |
| F852 | P1 | unity_tools/scene.py:179 | **Resolution mismatch.** Unity defaults 513, Blender defaults 257. Mismatched resolution → corrupted RAW import. No file-size validation. |
| F853 | P1 | terrain_master_registrar.py:25-26 | **4 Bundle H modules exist on disk but not registered.** terrain_morphology, terrain_hierarchy, terrain_rhythm, terrain_negative_space have no register_*_pass function. |
| F854 | P1 | terrain_cliffs.py:450-475 | **insert_hero_cliff_meshes is a placeholder.** Only records intent strings on state.side_effects. No mesh geometry created. Docstring says "later Bundle B extension" — doesn't exist. |
| F855 | P1 | terrain_twelve_step.py:43-64 | **5 stubs in 12-step orchestrator.** Steps 4 (flatten zones), 5 (canyon/river carves), 8a-c (cliff/cave/waterfall detection) are all no-ops returning empty/passthrough. |
| F856 | P1 | terrain_master_registrar.py:58-71 | **Silent import swallow.** Both import attempts catch bare Exception with pass. Broken bundle modules produce zero diagnostic output. |
| F857 | P2 | blender_server.py:4144-4329 | **15 silent exception swallows in compose_map export pipeline.** game_check, texture bake, LOD generation, FBX export, screenshot capture — all bare `except Exception: pass`. Failed exports produce no file but pipeline continues. |

### ANALYTICAL EROSION INTEGRATION BLOCKERS

| ID | Sev | Location | Finding |
|---|---|---|---|
| F860 | P0 | ARCHITECTURE | **ErosionMasks dataclass has no ridgeMap field.** Analytical filter outputs (height, ridgeMap) but current pass infrastructure can't store ridge data. |
| F861 | P1 | _terrain_world.py:455 | **pass_erosion signature expects tile-local mutation.** Analytical erosion needs world-coherent input or per-point evaluation — current orchestration runs per-tile with no overlap. |
| F862 | P1 | (multiple) | **Multi-writer channel clobber.** 7 passes write to `height` with last-writer-wins. Analytical filter must be final height writer, but pass_coastline/pass_karst/pass_wind_erosion run after and overwrite. |
| F863 | P1 | _terrain_noise.py:928-1150 | **Dead duplicate hydraulic_erosion in _terrain_noise.py.** 222-line separate implementation from _terrain_erosion.py version. Different params, different defaults, no callers. Confusion risk. |
| F864 | P2 | terrain_pipeline.py:90 | **PASS_REGISTRY is class-level mutable shared state.** In parallel node generation, passes registered for one tile could interfere with another. |

## Round 5 summary

### Counts
- **New unique findings:** 65 (F800-F864)
- **P0:** 16
- **P1:** 33
- **P2:** 16

### Running totals (all rounds)
- **Total findings:** ~695 (F001-F767 from R1-R4 + F800-F864 from R5)
- **Total P0:** ~220

### Top 10 P0s from Round 5

1. **F800** — Seam guard zones are a no-op (empty mutations = permits all)
2. **F801** — Droplet erosion destroys tile seams (random per-tile, killed at edges)
3. **F810** — No node registry exists (no world graph, no neighbor tracking)
4. **F811** — No cross-tile edge comparison ever performed (Riftpass_01 claim was false)
5. **F812** — No hero geometry blend-down (cliff near edge = hard discontinuity)
6. **F822** — Missing integrator pass (cave/waterfall deltas never applied to height)
7. **F832** — Rivers have no 3D geometry (data only, no mesh)
8. **F830** — Prop scatter Z=0 fallback (wrong object name → null sampler)
9. **F840** — No test verifies terrain height correctness in aggregate
10. **F850** — Zero Unity integration for analytical erosion package

### The architectural answer: analytical erosion + three-layer composition

The architecture audit agent confirmed that the analytical erosion filter **eliminates** the hard problem of cross-tile seam matching:

```
final_height(x, z) = base_height(x, z)                    # Layer 0: world-coherent
                   + hero_delta(x, z) * blend_weight(x, z) # Layer 1+2: tile-local, faded at edges

blend_weight = smoothstep(distance_from_edge / seam_guard_width)
```

- **Layer 0** (base + erosion): `f(x, z, seed, config)` → bit-identical at shared boundaries by construction
- **Layer 1** (hero deltas): cliffs, caves, waterfalls — forbidden at edges, smooth falloff via blend weight
- **Layer 2** (blend weight): `smoothstep` C1-continuous, zero at edge, one at interior

No constraint propagation, no cross-tile communication, no stitching needed for base layer. Nodes plug together like puzzle pieces because they all evaluate the same analytical function at shared world coordinates.

See `BEST_PRACTICES.md` §7 for the lpmitchell/AdvancedTerrainErosion integration plan and §6 for the Reddit community techniques (slope-threshold scatter, triplanar cliff noise, stairs-as-intersection).

---

# Round 6 — AAA Gap Scan + Plan Verification + False Positive Check (2026-04-11)

**Agents dispatched:** 6 Opus agents
**Focus:** AAA rendering gaps, geology gaps, Unity runtime gaps, plan conflict verification, false positive spot-check, web research for missed techniques

## Round 6a: False positive corrections

| Finding | Verdict | Correction |
|---|---|---|
| F800 | CONFIRMED (mechanism differs) | Zones parse OK but `permits()` defaults to allow-all with empty frozensets. Same outcome, cleaner root cause. |
| F801 | CONFIRMED | Standard boundary guard kills droplets at edges → erosion fades at tile seams. |
| F810 | PARTIAL | A world_graph exists for game locations (settlements/dungeons), NOT for terrain tile management. |
| F820 | CONFIRMED | pool_delta stored as channel, never applied to height. |
| F822 | CONFIRMED | No integrator pass merges deltas into heightmap. |
| F830 | CONFIRMED | Uses area_name ("PropScatter") instead of terrain object name. |
| **F832** | **FALSE POSITIVE** | `handle_create_water()` in `environment.py:2246` DOES build real 3D spline-following bmesh geometry with flow vertex colors. The real bug is that the terrain pipeline never calls this function automatically from river network data. Reclassify: "rivers have no geometry" → "river geometry builder exists but is never invoked by the pipeline." |
| F840 | CONFIRMED | Tests check status/channels/determinism, never assert height changed. |
| F850 | CONFIRMED (expected gap) | Unity package not yet adopted, correctly classified as gap. |
| F860 | CONFIRMED | ErosionMasks lacks ridge field. Ridge exists only as separate mask stack channel from structural_masks pass. |

**Round 5 accuracy: ~80% true positive (7 confirmed, 1 partial, 1 FP, 1 expected gap).**

## Round 6b: Plan consistency conflicts (18 found)

### HIGH severity

| ID | Description | Resolution |
|---|---|---|
| CONFLICT-002 | Plan says "no layer overwrites previous" but 7+ passes use last-writer-wins on height. No migration plan for converting Bundle I passes (coastline, karst, wind, glacial) from height-overwriters to delta-producers. | Add explicit commit converting Bundle I passes to delta-returning. |
| CONFLICT-003 | Analytical erosion needs `base_height_fn(x,z)` callable, but DEM imports and hand-authored heightmaps have no analytical function. No fallback gradient computation planned. | Add finite-difference gradient fallback for non-analytical heightmaps. |
| CONFLICT-004 | Fix sequence addresses 2 of 5 divergent paths (pass DAG + compose_terrain_node). compose_map, legacy cliff overlays, and cowork_bridge remain untouched. | Add commits for compose_map→BakedTerrain, remove legacy overlays, deprecate cowork_bridge. |
| CONFLICT-005 | §9 says use smoothstep blend for hero geometry, §9b says use Poisson blending. Two incompatible techniques for same problem. | Adopt smoothstep now, label Poisson as future upgrade requiring scipy solver. |
| CONFLICT-006 | fake_bpy (commit 7) should precede terrain fixes (commits 1-6) — fixes need real tests to validate. | Reorder: fake_bpy → gravity fix → analytical filter → ... |
| CONFLICT-018 | Master has unmerged commit 2877ed5 touching addon_toolchain.py, blender_server.py, terrain exports. Fix sequence doesn't account for this. | Add "commit 0: merge master" before any terrain work. |

### MED severity

| ID | Description |
|---|---|
| CONFLICT-007 | Path network (A* on heightfield) needed for stairs-as-intersection but no commit for it. |
| CONFLICT-008 | "Height as Callable[[float,float],float]" contradicts "numpy vectorized batch eval." Clarify: callable wraps numpy 1x1 eval. |
| CONFLICT-009 | BEST_PRACTICES §2 cites retracted F003 as motivation. Update citation. |
| CONFLICT-010 | terrain.yaml declares 18 bundles / 15 registered. Actual: 14. Regenerate before fix sequence. |
| CONFLICT-011 | Triplanar shader commit needs PBR texture assets to sample — none exist. Add texture generation prerequisite. |
| CONFLICT-015 | Unity-side AdvancedTerrainErosion has no commit. Plan implies both sides use same filter but only delivers Blender side. |
| CONFLICT-016 | ~30-40 of 695 findings are cross-round restatements. Consolidate under primary IDs. |

## Round 6c: AAA gaps vs current codebase

### Rendering (33 gaps, 11 HIGH)

**Critical pattern: data-to-shader gap.** Pipeline computes wetness masks, wind fields, macro color, stochastic offsets, fog pools, roughness variation — but the Unity shader is a basic 4-layer blender that consumes none of it.

Top 5 rendering gaps:
1. **No wetness/puddle rendering** — pipeline has wetness masks, shader has zero wetness integration (no albedo darkening, no glossy specular, no puddle accumulation)
2. **No POM or tessellation** — height textures exist per-layer but only used for blend weights, never for surface displacement. Close-up terrain is flat.
3. **No wind animation shader** — wind vertex colors are baked, wind field computed, but no Unity shader reads them. All vegetation is static.
4. **No terrain holes** — shader is always opaque, no clip(). Cave entrances impossible.
5. **No macro-variation** — terrain_macro_color.py computes large-scale color noise, shader has no _MacroVariation sampler. Tiling visible at medium distance.

### Geology (30 gaps, 8 HIGH)

**5 of 8 HIGH gaps are wiring, not missing code:**
- Cave carving (5 archetypes), waterfall pools, cliff anatomy, 8 water variant detectors all EXIST but are architecturally dead.

**Truly missing geological processes:**
1. Tectonic system (fault lines, uplift, folding)
2. Volcanic geomorphology (caldera, columnar basalt, pyroclastic)
3. Sediment deposition landforms (alluvial fans, deltas, floodplains)
4. River meander/oxbow system
5. Cirque/arete/horn alpine features

### Runtime / Unity (21 gaps, 6 HIGH)

1. No terrain-specific LOD control (heightmapPixelError, basemapDistance)
2. No runtime terrain streaming/chunking (quadtree, distance-based activation)
3. No terrain holes (SetHoles API)
4. No TreePrototype support (SpeedTree, billboard LOD, wind)
5. No collision mesh tuning
6. No AdvancedTerrainErosion Unity integration

### Web research — new techniques (11 found)

| Priority | Technique | Impact | Effort |
|---|---|---|---|
| 1 | **POM on terrain shader** | Close-up terrain goes from flat to 3D | MED — shader addition |
| 2 | **30-line GPU erosion** (ProceduralPixels) | Real-time preview during authoring | LOW — 30 lines compute |
| 3 | **River mesh + baked flowmap** (Arnklit Waterways pattern) | Rivers actually look like water | MED — spline mesh + UV bake |
| 4 | **Attribute-driven scatter** (InstaMAT pattern) | More natural vegetation from erosion byproducts | LOW — pipe existing outputs |
| 5 | **Shallow water GPU erosion** (bshishov) | Better erosion + flow co-products | MED — compute shader port |
| 6 | **Transvoxel** for volumetric cave LOD seams | Seamless cave mesh tiling | HIGH — volumetric pipeline |
| 7 | **Dual contouring** for caves/overhangs | Caves carved into unified terrain mesh | HIGH — SDF pipeline |
| 8 | **DSS seam strips** for multi-LOD tile merging | Watertight seams between LOD levels | MED — geometry pass |
| 9 | **PCG feedback loops** (UE5 Biome Core pattern) | Tree placement suppresses grass, etc. | LOW — accumulation buffer |

## Round 6 grand totals

| Category | Gaps/Findings |
|---|---|
| Round 5 findings (F800-F864) | 65 (16 P0, 33 P1, 16 P2) |
| Round 6 AAA rendering gaps | 33 (11 HIGH, 14 MED, 8 LOW) |
| Round 6 AAA geology gaps | 30 (8 HIGH, 8 MED, 14 LOW) |
| Round 6 AAA runtime gaps | 21 (6 HIGH, 8 MED, 7 LOW) |
| Round 6 plan conflicts | 18 (6 HIGH, 7 MED, 5 LOW) |
| Round 6 new techniques | 11 |
| False positive corrections | 1 (F832 reclassified) |
| Cross-round duplicates | ~30-40 |
| **CUMULATIVE AUDIT TOTAL** | **~780 unique findings + 84 AAA gaps + 18 plan conflicts + 11 new techniques**

## The three pillars to fix

Everything in this 6-round, 13-agent audit reduces to three architectural problems:

1. **Wire existing code to production.** 5+ geological feature systems (caves, waterfalls, water variants, cliff anatomy, stratigraphy) are computed but never consumed. The pass DAG produces data that the legacy render path ignores. Fix: BakedTerrain contract + integrator pass + route all paths through it.

2. **Bridge Blender data to Unity shaders.** 15+ data channels (wetness, wind, macro color, stochastic offsets, fog, roughness, ridge map) are computed but die at export. The Unity shader consumes only 4-layer RGBA splatmap. Fix: export additional mask textures + upgrade terrain shader to consume them (wetness, POM, wind, macro variation).

3. **Replace simulation erosion with analytical + per-point evaluation.** The droplet sim is broken (F277 gravity sign), tile-local (F801-F802), and destroys seams (F800). The analytical filter is world-coherent, chunk-parallel, and produces ridge maps for free. Fix: port runevision filter to numpy, adopt lpmitchell C# package for Unity, add finite-diff gradient fallback for imported heightmaps.
