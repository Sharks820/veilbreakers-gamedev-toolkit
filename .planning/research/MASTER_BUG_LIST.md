# MASTER BUG LIST -- VeilBreakers MCP Toolkit

**Compiled:** 2026-04-02
**Sources:** 17 bug scan files in `.planning/research/`
**Total unique bugs:** 219
**Deduplicated from:** ~258 raw findings across all scans

---

## CRASH Severity (17 bugs)

| ID | Severity | File | Description |
|----|----------|------|-------------|
| BUG-001 | CRASH | blender_server.py | `generate_prop` passes `jwt_token=` instead of `session_token=` to TripoStudioClient, causing TypeError on every call. |
| BUG-002 | CRASH | blender_server.py | `generate_prop` uses `TripoStudioClient` without importing it first; NameError if called before `generate_3d`. |
| BUG-003 | CRASH | blender_server.py | Importing `blender_addon.handlers.pipeline_state` triggers `import bpy` which crashes the MCP server process. |
| BUG-004 | CRASH | terrain_advanced.py | `flatten_layers` heightmap reshape assumes square vertex grid; crashes with ValueError on non-square meshes. |
| BUG-005 | CRASH | environment.py | `handle_carve_river` heightmap reshape assumes square grid; crashes with ValueError on non-square terrain. |
| BUG-006 | CRASH | environment.py | `handle_generate_road` heightmap reshape assumes square grid; same crash as BUG-005. |
| BUG-007 | CRASH | terrain_advanced.py | `handle_erosion_paint` heightmap reshape assumes square grid; same crash as BUG-004. |
| BUG-008 | CRASH | terrain_materials.py | `BIOME_PALETTES["ruined_fortress"]["slopes"]` references `"moss"` key that resolves via MATERIAL_LIBRARY fallback but may produce wrong material semantically. |
| BUG-009 | CRASH | lod_pipeline.py | Billboard quad faces +Z (horizontal) instead of camera; vegetation LOD3 is invisible from all horizontal viewing angles. |
| BUG-010 | CRASH | vegetation_system.py | Seasonal color_tint values can push RGB channels below 0 (autumn/corrupted variants have negative tint components) with no clamping. |
| BUG-011 | CRASH | lod_pipeline.py | Vegetation LOD preset ratio 0.0 triggers billboard generation which produces a broken flat invisible quad (depends on BUG-009). |
| BUG-012 | CRASH | animation_monster.py | `DEF-jaw` bone name mismatch -- facial rig creates `jaw` without DEF- prefix; all jaw monster animations silently do nothing. |
| BUG-013 | CRASH | settlement_generator.py | `_furnish_interior` calls `rng.uniform(a, b)` with swapped bounds in small rooms, placing furniture outside room bounds. |
| BUG-014 | CRASH | gemini_client.py | REST fallback accesses `data["candidates"][0]` without IndexError handling; crashes on empty/blocked Gemini responses. |
| BUG-015 | CRASH | _dungeon_gen.py | `_place_spawn_points` uses `rng.randint(room.x+1, room.x2-2)` which raises ValueError on tiny rooms (width < 4). |
| BUG-016 | CRASH | gameplay_templates.py | `NavMeshAgent.SetDestination()` called without `isOnNavMesh` check in 8 generated call sites; throws InvalidOperationException at runtime. |
| BUG-017 | CRASH | combat_vfx_templates.py | `Shader.Find()` returns null when URP not installed; `new Material(null)` throws ArgumentNullException in 8+ generated sites. |

---

## HIGH Severity (42 bugs)

| ID | Severity | File | Description |
|----|----------|------|-------------|
| BUG-018 | HIGH | environment.py | Division by max height in carve_river can produce division by zero or inverted heightmap if terrain is below origin. |
| BUG-019 | HIGH | terrain_features.py | Global mutable `_features_gen` and `_features_seed` cause state corruption in concurrent/repeated calls; not thread-safe. |
| BUG-020 | HIGH | environment.py | Road path grid index `r0 * side + c0` can exceed array bounds causing IndexError when path includes boundary cells. |
| BUG-021 | HIGH | environment.py | Water mesh `obj.location = (0, 0, water_level)` causes double-offset; water appears at 2x water_level since vertices already include it. |
| BUG-022 | HIGH | terrain_advanced.py | Erosion paint writes Z values back to bmesh vertices assuming row-major order; corrupts terrain if mesh was edited or non-grid. |
| BUG-023 | HIGH | vegetation_lsystem.py | Leaf card tilt modifies up vector non-orthogonally, producing parallelogram-shaped (skewed) leaf cards instead of rectangles. |
| BUG-024 | HIGH | texture_quality.py | Chitin metallic=0.12, obsidian=0.05, ice=0.02, crystal=0.05 -- all dielectric materials with incorrect non-zero metallic PBR values. |
| BUG-025 | HIGH | terrain_materials.py | `crystal_surface` metallic=0.12, `prismatic_rock`=0.20, `crystal_wall`=0.30 -- dielectric terrain materials with incorrect metallic. |
| BUG-026 | HIGH | vegetation_system.py | `_sample_terrain()` returns default `(0.5, 0.0)` when no nearby vertex found, placing vegetation floating mid-air at terrain edges. |
| BUG-027 | HIGH | unity_tools/vfx.py | Unsanitized `name` parameter used directly in file path for VFX particle scripts; names with spaces/dashes create invalid .cs files. |
| BUG-028 | HIGH | camera.py, world.py | Unsanitized `name` in file paths across 32 call sites in camera and world Unity tool handlers. |
| BUG-029 | HIGH | animation_blob.py | `DEF-pseudopod_*` bones referenced in blob animations but never created by any rig template; animations silently do nothing. |
| BUG-030 | HIGH | rigging_advanced.py | Ragdoll preset references `DEF-head` bone that doesn't exist; actual head bone is `DEF-spine.005`. Head has no physics colliders. |
| BUG-031 | HIGH | pipeline_runner.py | `full_asset_pipeline` export uses `selected_only=True` but never selects the target object; may export nothing or wrong objects. |
| BUG-032 | HIGH | pipeline_runner.py | Multi-material GLB texture channels (`albedo_mat0`, `albedo_mat1`) silently lost in pipeline wiring; only `albedo` key is checked. |
| BUG-033 | HIGH | tripo_post_processor.py | Post-processor only processes first material of multi-material models; scoring biased against multi-material variants. |
| BUG-034 | HIGH | blender_server.py | `generate_building` and `generate_prop` skip all post-processing and Blender import that `generate_3d` performs; wastes Tripo credits. |
| BUG-035 | HIGH | blender_server.py | Foundation `side_heights` uses wrong corner indices; left retaining wall gets front corner height instead of left-side average. |
| BUG-036 | HIGH | vegetation_system.py | `handle_scatter_biome_vegetation` uses LOCAL mesh coordinates but WORLD space bounds; wrong height sampling if terrain not at origin. |
| BUG-037 | HIGH | performance_templates.py | Unity LOD expects child objects via `transform.Find()` but Blender creates LOD meshes as siblings; LOD1+ never discovered. |
| BUG-038 | HIGH | Cross-file | No automated material property transfer from Blender to Unity; PBR values silently lost on export. |
| BUG-039 | HIGH | building_interior_binding.py | Module is NEVER imported or called by production code; spatial room alignment and door metadata generation are dead code. |
| BUG-040 | HIGH | worldbuilding.py | BMesh `free()` leak in UV auto-fix and mesh repair loops; exceptions skip `_bm.free()`, leaking GPU memory per building child. |
| BUG-041 | HIGH | blender_server.py | `mesh_name` injected unsanitized into f-string `execute_code`; crafted names can inject arbitrary bpy operations. |
| BUG-042 | HIGH | socket_server.py | Frozen Blender handler causes 300-second cascading timeout for ALL connected clients, not just the one whose command hung. |
| BUG-043 | HIGH | _dungeon_gen.py | Multi-floor dungeon connection positions desynchronized from transition assignments due to separate RNG calls. |
| BUG-044 | HIGH | scene_templates.py | `prefab_paths` unsanitized in generated C# string array; backslashes or quotes in paths break generated code. |
| BUG-045 | HIGH | settlement_generator.py | `"concentric_organic"` layout pattern not handled in `_place_buildings`; falls through to random organic scatter instead. |
| BUG-046 | HIGH | building_interior_binding.py | Room type vocabulary mismatch between binding (`tavern_hall`, `treasury`) and settlement generator (`tavern`, `smithy`). |
| BUG-047 | HIGH | worldbuilding.py | Missing VB_BUILDING_PRESETS for 8 building types (tavern, blacksmith, temple, general_store, house, guard_barracks, manor, guild_hall). |
| BUG-048 | HIGH | building_interior_binding.py | Hardcoded 3.5m floor height in `align_rooms_to_building` ignores preset wall_height; upper-floor rooms clip into geometry. |
| BUG-049 | HIGH | settlement_generator.py | Two parallel building type vocabularies conflict between `_DISTRICT_BUILDING_TYPES` and `SETTLEMENT_TYPES`. |
| BUG-050 | HIGH | settlement_generator.py | Hearthvale temple not treated as priority shrine; `has_shrine` logic checks for `"shrine"` substring which doesn't match `"temple"`. |
| BUG-051 | HIGH | _building_grammar.py | "market" room type missing from `_ROOM_CONFIGS`; general stores and market stalls get empty interiors. |
| BUG-052 | HIGH | _building_grammar.py | "prison" room type missing from `_ROOM_CONFIGS`; cage buildings in bandit camps get empty rooms. |
| BUG-175 | HIGH | fal_client.py, texture_ops.py | `os.environ["FAL_KEY"]` race between concurrent async calls; interleaved set/restore corrupts env state or uses wrong API key. |
| BUG-176 | HIGH | prop_density.py | Wall/floor/ceiling prop rotation output in degrees but consumer (`worldbuilding.py` `rotation_euler`) expects radians; props wildly misoriented. |
| BUG-177 | HIGH | blender_server.py | `compose_map` game_check `except Exception: pass` silently drops check failures; report says 0 failures when objects were never checked. |
| BUG-178 | HIGH | blender_server.py | `compose_map` FBX export `except Exception: pass` makes export failures invisible; partial exports not reported. |
| BUG-179 | HIGH | blender_server.py | `_collect_mesh_targets` returns empty list on connection failure; `_validate_world_quality` reports success with 0 meshes validated. |
| BUG-180 | HIGH | fal_client.py | `httpx.HTTPStatusError` not caught by except clause; fal.ai CDN 403/404/500 crashes MCP tool handler with raw traceback. |
| BUG-181 | HIGH | gemini_client.py | `httpx.HTTPStatusError` not caught by `_call_gemini` except clause; Gemini 429/401/500 crashes instead of returning error dict. |

---

## MEDIUM Severity (93 bugs)

| ID | Severity | File | Description |
|----|----------|------|-------------|
| BUG-053 | MEDIUM | blender_server.py | `compose_map` unconditionally resets `interior_results = []` even when resuming from checkpoint; partial interior results lost. |
| BUG-054 | MEDIUM | blender_server.py | `compose_map` step 8 raises ValueError when no locations exist; should skip or use terrain-only scatter mode. |
| BUG-055 | MEDIUM | environment_scatter.py | `_terrain_height_sampler` returns negative heights if terrain entirely below Z=0; vegetation placed below terrain. |
| BUG-056 | MEDIUM | _terrain_noise.py | `compute_slope_map` uses `np.gradient(heightmap)` with unit spacing; slopes incorrect for non-unit-scale heightmaps. |
| BUG-057 | MEDIUM | settlement_generator.py | Absolute imports from `blender_addon.handlers` instead of relative; breaks if package structure changes. |
| BUG-058 | MEDIUM | environment.py | `handle_carve_river` silently defaults source/destination to (0,0); produces zero-length path with no river and no warning. |
| BUG-059 | MEDIUM | worldbuilding_layout.py | `_ops_to_mesh` bmesh.ops.create_cube geom extraction fragile; fallback `result.get("geom")` includes edges and faces. |
| BUG-060 | MEDIUM | terrain_materials.py | `"thornwood_forest"` biome references `"mud"` which exists in MATERIAL_LIBRARY but is semantically different from `"terrain_mud"`. |
| BUG-061 | MEDIUM | terrain_advanced.py | Wind erosion removes 5% but deposits only 3% per pass; 40% of eroded material vanishes causing terrain to sink. |
| BUG-062 | MEDIUM | vegetation_system.py | Two wind vertex color baking functions have completely different channel semantics; Unity shader behavior differs per tree source. |
| BUG-063 | MEDIUM | lod_pipeline.py | `_auto_detect_regions` uses Y axis for height but Blender convention is Z-up; face/hands detection targets wrong mesh regions. |
| BUG-064 | MEDIUM | terrain_materials.py | Duplicate `"sandstone"` key in TERRAIN_MATERIALS and SMART_MATERIAL_PRESETS creates maintenance confusion. |
| BUG-065 | MEDIUM | vegetation_system.py | Rotation generated in degrees but only fragile implicit contract that consumers must convert to radians. |
| BUG-066 | MEDIUM | lod_pipeline.py | Edge-collapse decimation at very low ratios can produce zero-area faces and non-manifold configurations. |
| BUG-067 | MEDIUM | unity_tools/vfx.py | Orphaned expression `effect_type.replace("_", " ").title()` is a no-op; return value discarded. |
| BUG-068 | MEDIUM | 15 template files | `_CS_RESERVED` and `_safe_namespace` duplicated across 15+ files; maintenance hazard if C# keywords change. |
| BUG-069 | MEDIUM | animation_export.py | Root motion extraction mixes world space reads with local space writes; incorrect if armature has any transform. |
| BUG-070 | MEDIUM | animation.py | Quaternion axis mapping shifts euler axes 0/1/2 to quaternion 1/2/3 but never sets W component (index 0); produces 180-degree rotation. |
| BUG-071 | MEDIUM | animation_gaits.py | Bone name filter compares raw composite key `"bone__sway"` against simple bone names; sway channels silently dropped. |
| BUG-072 | MEDIUM | animation_export.py | Root rotation quaternion extraction writes only Z component; single quaternion component is not a valid rotation. |
| BUG-073 | MEDIUM | unity_tools/audio.py | SFX output paths use `.mp3` extension but stub mode writes WAV content; extension/format mismatch. |
| BUG-074 | MEDIUM | rigging.py | Multi-arm parent bone reference lacks `DEF-` prefix; inconsistent naming between bone creation and animation time. |
| BUG-075 | MEDIUM | blender_server.py | Tripo `generate_3d` variant import failures logged at DEBUG only; user sees successful count without knowing which variants failed. |
| BUG-076 | MEDIUM | tripo_post_processor.py | De-lighting errors completely swallowed with `except Exception: pass`; raw albedo used silently. |
| BUG-077 | MEDIUM | delight.py | Returns error dict when numpy missing but caller only checks `correction_applied` key; de-lighting silently skipped. |
| BUG-078 | MEDIUM | model_validation.py | GLB declared length check doesn't verify BIN chunk completeness; truncated binary blob can pass validation. |
| BUG-079 | MEDIUM | tripo_studio_client.py | Download doesn't verify Content-Length vs actual bytes; partial downloads not detected before writing. |
| BUG-080 | MEDIUM | tripo_studio_client.py | JWT regex extraction from Tripo Studio page is fragile; takes first JWT found which may not be correct. |
| BUG-081 | MEDIUM | blender_server.py | `generate_3d` output_dir fallback chain is fragile; could write models to unexpected CWD location. |
| BUG-082 | MEDIUM | blender_server.py | `except Exception: pass` in compose_map terrain flatten suppresses all errors including NameError/TypeError silently. |
| BUG-083 | MEDIUM | tripo_studio_client.py | All 4xx/5xx API errors become RuntimeError; callers cannot distinguish 401/402/429/500 for proper retry/handling. |
| BUG-084 | MEDIUM | blender_server.py | `safe_path` escaping doesn't strip newlines; filepath with `\n` could inject statements into Blender code. |
| BUG-085 | MEDIUM | execute.py | `bpy.ops` unrestricted in sandbox; export_scene, object.delete, scene.delete, orphans_purge all allowed. |
| BUG-086 | MEDIUM | blender_server.py | `_sample_terrain_height` returns 0.0 on failure; buildings placed at Z=0 underground with no way to distinguish from success. |
| BUG-087 | MEDIUM | socket_server.py | Unicode object names with single quotes break f-string code generation in execute_code calls. |
| BUG-088 | MEDIUM | environment.py | NaN/Inf in terrain heightmap data silently propagates through all downstream operations causing invisible geometry. |
| BUG-089 | MEDIUM | _tool_runner.py | `run_roslynator` uses deprecated `tempfile.mktemp` with TOCTOU race condition. |
| BUG-090 | MEDIUM | _terrain_depth.py | `detect_cliff_edges` calls `np.gradient(heightmap)` inside per-cluster loop; redundant computation up to 50x. |
| BUG-091 | MEDIUM | fal_client.py | `generate_concept_art` sets `os.environ["FAL_KEY"]` before `_FAL_AVAILABLE` check; leaks env var if fal-client missing. |
| BUG-092 | MEDIUM | pyproject.toml | `httpx` used as direct import in 4 files but not declared in dependencies; works only as transitive dependency. |
| BUG-093 | MEDIUM | terrain_materials.py | Color space mismatch between Blender (linear) and Unity (sRGB for albedo); no conversion utility exists. |
| BUG-094 | MEDIUM | terrain_materials.py | Biome palette names don't map to any Unity terrain layer system; terrain materials lost on export. |
| BUG-095 | MEDIUM | lod_pipeline.py | LOD screen percentages from Blender presets not transferred to Unity; per-asset-type distances silently discarded. |
| BUG-096 | MEDIUM | lod_pipeline.py | LOD `export_dir` parameter is accepted/documented but never used; API lies about auto-export capability. |
| BUG-097 | MEDIUM | settlement_generator.py | `generate_concentric_districts` declares heightmap as `list[list[float]]` but internal helper calls it as a function; TypeError if grid passed. |
| BUG-098 | MEDIUM | vegetation_system.py | `handle_scatter_biome_vegetation` has no building/road exclusion zones; vegetation placed inside buildings. |
| BUG-099 | MEDIUM | worldbuilding_layout.py | `handle_generate_town` seeds global `random` module instead of local `Random` instance; pollutes global random state. |
| BUG-100 | MEDIUM | worldbuilding.py | Module-level `_PROP_CACHE` becomes stale across Blender file reloads; `clear_prop_cache()` never called automatically. |
| BUG-101 | MEDIUM | settlement_generator.py | `_BUILDING_ROOMS["guild_hall"]` references `"armory"` room type with no furnishing OR lighting config; gets single crate. |
| BUG-102 | MEDIUM | settlement_generator.py | Inconsistent 2-tuple vs 3-tuple road positions between `_generate_roads` and `generate_road_network_organic`. |
| BUG-103 | MEDIUM | texture_quality.py | `rusted_armor` metallic=0.95, `aged_bronze`=0.90, `tarnished_gold`=0.95, `rusted_iron`=0.85 -- base metals should be 1.0. |
| BUG-104 | MEDIUM | lod_pipeline.py | Billboard quad returns XY extent ignoring Z height; tree billboards are tiny/squat instead of tall. |
| BUG-105 | MEDIUM | _combat_timing.py | `phase_ranges` becomes stale after `apply_brand_timing` modifies frame counts but doesn't recalculate ranges. |
| BUG-106 | MEDIUM | destruction_system.py | Rubble center uses Y as ground but Blender is Z-up; rubble placed at back of mesh instead of bottom. |
| BUG-107 | MEDIUM | encounter_spaces.py | `enemy_count=0` with list-based template bypasses `min_enemies` constraint; uses `max(0, ...)` instead of `max(min_e, ...)`. |
| BUG-108 | MEDIUM | worldbuilding_layout.py | `generate_linked_interior_spec` only handles "south" facing correctly; east/west doors get wrong probe offsets. |
| BUG-109 | MEDIUM | performance_templates.py | LODGroup applied to every MeshRenderer indiscriminately including UI/particles; same mesh assigned to all levels when no LOD siblings. |
| BUG-110 | MEDIUM | audio_templates.py | `zone_label` unsanitized in C# class name; `zone_type="my cave"` generates invalid identifier. |
| BUG-111 | MEDIUM | ui_templates.py | Raw `screen_name` used in MenuItem and C# string interpolation without sanitization. |
| BUG-112 | MEDIUM | prefab_templates.py | NavMesh `configure_area` records Undo on target but `SetAreaCost` modifies global state; undo won't work. |
| BUG-113 | MEDIUM | scene_templates.py | Terrain heightmap reader assumes little-endian byte order with no parameter; big-endian files produce garbled terrain. |
| BUG-114 | MEDIUM | scene_templates.py | Heightmap resolution not validated as power-of-two-plus-one; mismatched RAW file size causes visible seam. |
| BUG-115 | MEDIUM | audio_middleware_templates.py | Static `_occlusionHits` RaycastHit buffer shared across all instances; concurrent occlusion updates cause data race. |
| BUG-116 | MEDIUM | editor_templates.py | Screenshot JSON path not escaped for double quotes; path containing `"` produces malformed JSON. |
| BUG-117 | MEDIUM | combat_vfx_templates.py | `renderer.material` property access creates material instances that are never Destroyed; GPU memory leak per combo hit. |
| BUG-118 | MEDIUM | _dungeon_gen.py | Town landmark search uses 101x101 brute-force radius scan per district; O(N^2) blowup on large maps. |
| BUG-119 | MEDIUM | _dungeon_gen.py | Town road adjacency check iterates ALL road cells per district pair; O(districts^2 * roads) complexity. |
| BUG-120 | MEDIUM | socket_server.py | 30-second idle timeout on server vs 300-second timeout on client causes unnecessary reconnections during slow pipelines. |
| BUG-121 | MEDIUM | settlement_generator.py | `_place_buildings` silently drops buildings when all 80 placement attempts fail; no warning logged. |
| BUG-182 | MEDIUM | blender_client.py | Retry mechanism sends duplicate commands to Blender; expensive operations (terrain gen) execute twice, first result discarded. |
| BUG-183 | MEDIUM | elevenlabs_client.py | `time.sleep()` in rate-limit retry blocks the entire async event loop for 2-8 seconds; all MCP tools frozen. |
| BUG-184 | MEDIUM | fal_client.py | Sync `httpx.get()` blocks event loop for up to 30 seconds during image download from fal.ai CDN. |
| BUG-185 | MEDIUM | pipeline_state.py | Pipeline checkpoint written directly to final path without atomic rename; crash during write corrupts checkpoint. |
| BUG-186 | MEDIUM | asset_catalog.py | SQLite connection not thread-safe; concurrent async access via `run_in_executor` causes "database is locked" errors. |
| BUG-187 | MEDIUM | 50+ handler files | Handlers set `bpy.context.view_layer.objects.active` without saving/restoring previous active object; silent state corruption. |
| BUG-188 | MEDIUM | environment_scatter.py | BMesh `free()` not guarded by try/finally in `_create_tree_mesh`, `_create_grass_blade`, and cave mesh; GPU memory leak on exception. |
| BUG-189 | MEDIUM | environment_scatter.py | Fragment/debris rotation values generated but never applied to objects; all breakable fragments spawn axis-aligned. |
| BUG-190 | MEDIUM | _terrain_depth.py | `np.gradient(heightmap)` in cliff detection lacks cell spacing parameter; cliff face rotation angles wrong for non-unit terrain cells. |
| BUG-191 | MEDIUM | character_advanced.py | Hair strand binormal computed as `cross(normal, tangent)` instead of `cross(tangent, normal)`; curly/braided styles spiral wrong direction. |
| BUG-192 | MEDIUM | _building_grammar.py | Mixed rotation formats: some functions return scalar float, others return 3-tuple; consumer expects scalar, 3-tuple causes TypeError. |
| BUG-193 | MEDIUM | _terrain_depth.py | Cliff meshes rotated to face along slope direction instead of perpendicular to it; off by 90 degrees. |
| BUG-194 | MEDIUM | worldbuilding.py | Stairs `rotation_euler` hardcoded to `(pi/2, 0, 0)` ignoring actual connection direction; stairs always face same world direction. |
| BUG-195 | MEDIUM | blender_server.py | `compose_map` LOD generation `except Exception: pass` silently drops failures; no record of which objects failed or why. |
| BUG-196 | MEDIUM | worldbuilding.py | UV repair `except Exception: pass` silently swallows all errors; cannot distinguish "no UVs needed" from "all UV attempts crashed." |
| BUG-197 | MEDIUM | worldbuilding.py | Mesh repair `except Exception: pass` silently swallows all errors; corrupted meshes pass through without signal. |
| BUG-198 | MEDIUM | worldbuilding.py | Weathering application `except Exception: pass` silently swallows all errors; result reports preset but 0 applications with no error. |
| BUG-199 | MEDIUM | tripo_studio_client.py | `resp.json()` called before status code check; non-JSON error responses (502/503 HTML) crash with unhelpful JSONDecodeError. |
| BUG-200 | MEDIUM | terrain_advanced.py | `json.loads(layers_json)` has no try/except; corrupted `terrain_layers` custom property crashes handler with JSONDecodeError. |
| BUG-201 | MEDIUM | glb_texture_extractor.py | `json.loads(json_chunk_data)` has no try/except; corrupted GLB JSON chunk crashes with unhandled JSONDecodeError. |
| BUG-202 | MEDIUM | elevenlabs_client.py | Retry only catches 5 exception types; `httpx.HTTPStatusError` and other httpx exceptions bypass retry entirely. |
| BUG-203 | MEDIUM | blender_server.py | `_validate_world_quality` reports success with `validated_meshes: 0` when connection failed; indistinguishable from "nothing to validate." |
| BUG-204 | MEDIUM | blender_server.py | `compose_map` pipeline (game_check, LOD, export) has zero logging for per-object failures; only result dict counts available. |
| BUG-205 | MEDIUM | worldbuilding.py | Interior generation has no diagnostic counters for UV, repair, or weathering failures; no way to diagnose which step failed. |

---

## LOW Severity (61 bugs)

| ID | Severity | File | Description |
|----|----------|------|-------------|
| BUG-122 | LOW | blender_server.py | `_normalize_map_point` false-positive centering when one coordinate near threshold and another near zero. |
| BUG-123 | LOW | blender_server.py | Unused `pos` variable computed for all `blender_quality` actions but only used by creature anatomy actions. |
| BUG-124 | LOW | blender_server.py | Multiple `# type: ignore` comments throughout `_enforce_world_quality` suppress legitimate type checking. |
| BUG-125 | LOW | blender_server.py | `_collect_mesh_targets` iterates all scene objects; slow for 1000+ objects but mitigated by max_targets=64. |
| BUG-126 | LOW | _scatter_engine.py | Poisson disk active list swap-remove slightly biases spatial distribution toward end-of-list points. |
| BUG-127 | LOW | terrain_advanced.py | `TerrainLayer.from_dict` doesn't validate `blend_mode` against `VALID_BLEND_MODES`; crash deferred to usage. |
| BUG-128 | LOW | terrain_advanced.py | `apply_stamp_to_heightmap` falloff blend calculation simplifies to just `edge_falloff`; `falloff` param has no effect. |
| BUG-129 | LOW | terrain_advanced.py | `TerrainLayer` strength silently clamped to [0,1] with no warning to user. |
| BUG-130 | LOW | _building_grammar.py | Duplicate dict keys in `_DETAIL_TYPE_MATERIAL_CATEGORY`; later entries silently overwrite earlier ones. |
| BUG-131 | LOW | worldbuilding.py | `_get_or_generate_prop` may return None; callers handle it but contract is implicit. |
| BUG-132 | LOW | _scatter_engine.py | Poisson disk `min_distance` of 0 or negative causes division by zero in grid index; caller should validate. |
| BUG-133 | LOW | terrain_materials.py | `_simple_noise_2d` hash modular arithmetic produces slightly biased range [-1.0, 0.9998] instead of [-1.0, 1.0]. |
| BUG-134 | LOW | lod_pipeline.py | Billboard quad has no UV coordinates; texture cannot be mapped (unlike vegetation_lsystem.py which does it correctly). |
| BUG-135 | LOW | _scatter_engine.py | `context_scatter` building footprint exclusion uses axis-aligned rectangles; rotated buildings not properly excluded. |
| BUG-136 | LOW | terrain_materials.py | `reality_torn_rock` normal_strength=2.0 is double typical max; causes extreme surface distortion. |
| BUG-137 | LOW | blender_server.py | `compose_interior` has no checkpoint support unlike `compose_map`; all progress lost on failure. |
| BUG-138 | LOW | blender_server.py | No NaN/Inf guard on terrain sample x/y floats; NaN would create invalid Python code in Blender. |
| BUG-139 | LOW | tripo_studio_client.py | `_ensure_client` can leak old httpx client on JWT refresh race under concurrent async calls. |
| BUG-140 | LOW | tripo_client.py | `_download_file` retries ALL failures including deterministic validation failures; wastes time on inherently corrupt models. |
| BUG-141 | LOW | blender_server.py | Code duplication across generate_3d, generate_building, generate_prop leads to inconsistent behavior (root cause of BUG-001). |
| BUG-142 | LOW | blender_server.py | `__import__("pathlib").Path` used instead of existing `Path` import; anti-pattern from copy-paste. |
| BUG-143 | LOW | pipeline_runner.py | Import step code references `bpy` without importing it first; relies on implicit Blender namespace. |
| BUG-144 | LOW | tripo_client.py | Creates new `TripoClient` on every retry attempt instead of reusing the client. |
| BUG-145 | LOW | blender_server.py | `generate_building`/`generate_prop` API-key paths never call `gen.close()` on TripoGenerator. |
| BUG-146 | LOW | elevenlabs_client.py | Voice line duration estimated by word count, not actual audio duration; timing will be inaccurate. |
| BUG-147 | LOW | audio_templates.py | Adaptive music starts ALL layers playing simultaneously at volume 0; unnecessary AudioSource processing overhead. |
| BUG-148 | LOW | rigging_weights.py | Deformation test poses reset quaternion before setting rotation mode; sequencing is correct but fragile. |
| BUG-149 | LOW | animation_combat.py | `generate_approach_keyframes` writes duplicate keyframes on same bone/channel/axis per frame; last value wins. |
| BUG-150 | LOW | animation.py | No scale channel validation; negative/zero scale values from intense animations not caught. |
| BUG-151 | LOW | elevenlabs_client.py | Rate limit detection uses string matching (`"429" in str(exc)`); fragile if error message format changes. |
| BUG-152 | LOW | .mcp.json | Uses `${VAR}` env var syntax which is non-standard JSON; works only because MCP client handles substitution. |
| BUG-153 | LOW | config.py | `realesrgan_path` default is Windows-specific `.exe`; confusing FileNotFoundError on Linux/Mac. |
| BUG-154 | LOW | config.py | Settings loads `.env` from CWD which varies by launch method; can cause "API key not found" confusion. |
| BUG-155 | LOW | execute.py | Theoretical sandbox bypass via `isinstance.__class__` chain; well mitigated by dunder allowlist. |
| BUG-156 | LOW | socket_server.py | No authentication on localhost TCP socket; any local process can control Blender. |
| BUG-157 | LOW | _settlement_grammar.py | Uniform prop spacing for entire settlement ignores district variation; high-corruption area gets same density as market. |
| BUG-158 | LOW | _settlement_grammar.py | `subdivide_block_to_lots` can produce zero-area lots from degenerate polygons; may cause division-by-zero downstream. |
| BUG-159 | LOW | settlement_generator.py | `"portcullis_gate"` perimeter type may have no generator; produces fallback volume cube instead of geometry. |
| BUG-160 | LOW | settlement_generator.py | Several road prop types (`planter`, `brazier`, `torch_post`, `milestone`) have no generators; produce fallback cubes. |
| BUG-161 | LOW | settlement_generator.py | `_SCATTER_PROPS` types (`rock_small`, `debris_pile`, `bone_scatter`, etc.) likely have no generators; produce identical gray boxes. |
| BUG-162 | LOW | _tool_runner.py | Module docstring lists InferSharp but no `run_infersharp()` function exists; documentation inaccuracy. |
| BUG-163 | LOW | _terrain_depth.py | `detect_cliff_edges` position mapping uses confusing axis naming (`wy` for depth coordinate). |
| BUG-164 | LOW | wcag_checker.py | `validate_uxml_contrast` has no graceful fallback for missing defusedxml; raises ImportError at runtime. |
| BUG-165 | LOW | fal_client.py | `compose_style_board` leaks PIL Image objects; accumulates unclosed file handles in long-running server. |
| BUG-166 | LOW | screenshot_diff.py | `compare_screenshots` leaks diff Image object; `ref_img` and `cur_img` closed but `diff` is not. |
| BUG-167 | LOW | _tool_runner.py | `run_roslynator` bare `except Exception: pass` swallows XML parsing errors with no logging. |
| BUG-168 | LOW | _character_lod.py | `character_aware_lod` rebuilds `set(kept_face_indices)` on every face iteration instead of pre-computing once. |
| BUG-206 | LOW | socket_server.py | `_process_commands` processes only one command per 10ms tick; head-of-line blocking under concurrent clients, no priority or cancellation. |
| BUG-207 | LOW | unity_tools/audio.py | `_audio_client` module-level singleton initialization lacks thread safety; double-init possible under concurrent access. |
| BUG-208 | LOW | _ast_analyzer.py | `_cs_parser`/`_py_parser` globals lack thread safety; concurrent init can leak a parser object. |
| BUG-209 | LOW | objects.py | Handler reads `bpy.context.active_object` without verifying it matches the requested object; wrong object modified silently. |
| BUG-210 | LOW | mesh_enhance.py | Reads `bpy.context.active_object` after `bpy.ops.object.duplicate()` without verifying duplicate succeeded; may modify original. |
| BUG-211 | LOW | environment_scatter.py | Terrain slope uses single-sided finite differences (forward from one corner); systematically biases gradient at coarse resolutions. |
| BUG-212 | LOW | lod_pipeline.py | `_normalize` returns zero vector `(0,0,0)` for degenerate input; degenerate faces incorrectly inflate LOD silhouette importance scores. |
| BUG-213 | LOW | animation_production.py | Nlerp quaternion blend produces near-zero quaternion for near-opposite inputs; normalization amplifies noise causing orientation pops. |
| BUG-214 | LOW | environment.py | Noise/bump shader node creation `except Exception: pass`; water surfaces render without bump mapping with no error reported. |
| BUG-215 | LOW | environment.py | Biome palette lookup `except Exception: pass`; terrain renders with hardcoded brown fallback color with no warning. |
| BUG-216 | LOW | worldbuilding.py | Reports `weathering_preset: "heavy"` alongside `weathering_applied_count: 0` when all attempts failed; misleading combination. |
| BUG-217 | LOW | texture_ops.py | Download error message says "fal.ai inpainting failed" when actual problem is CDN HTTP error; misleading diagnostic. |
| BUG-218 | LOW | tripo_studio_client.py | `generate_from_text` and `_poll_and_download_variants` return different error dict shapes; inconsistent `models` key presence. |
| BUG-219 | LOW | gemini_client.py | Exception routing confusing: SDK import succeeds but SDK's internal httpx.HTTPStatusError falls through both except clauses. |

---

## LOW -- Design/Completeness (6 bugs)

| ID | Severity | File | Description |
|----|----------|------|-------------|
| BUG-169 | LOW | building_interior_binding.py | "generic" room type has no `_ROOM_CONFIGS` entry; ruin buildings get empty main chambers. |
| BUG-170 | LOW | _building_grammar.py | 13 room types lack `ROOM_SPATIAL_GRAPHS` entries; furniture placed randomly instead of with spatial awareness. |
| BUG-171 | LOW | environment.py | VB_BIOME_PRESETS scatter assets (30+ types) not validated against actual generators; may silently skip or error. |
| BUG-172 | LOW | terrain_materials.py | Veil crack zone metallic=0.50 is unusually high for terrain; may look unrealistic under certain lighting. |
| BUG-173 | LOW | world_templates.py | `sanitize_cs_identifier` called but return value discarded (dead expression) on lines 188 and 280. |
| BUG-174 | LOW | combat_vfx_templates.py | `_brand_colors_cs_dict` generates Dictionary for ALL 10 brands even though combo VFX uses only one. |

---

## TEST QUALITY ISSUES (from bug_scan_test_gaps.md)

| ID | Severity | File | Description |
|----|----------|------|-------------|
| TQ-001 | HIGH | conftest.py | bpy MagicMock returns MagicMock for everything; 253 mock references across 22 files test mock plumbing, not real behavior. |
| TQ-002 | HIGH | test_dungeon_gen.py | `test_loot_points_include_secret_rooms` computes result but NEVER asserts anything; always passes regardless. |
| TQ-003 | HIGH | test_gameplay_templates.py | 18 validation tests use only `assert result is not None`; passes for any non-None return including empty strings or error dicts. |
| TQ-004 | HIGH | test_lod_pipeline.py | Billboard test asserts coplanar-Z (horizontal) which may be asserting WRONG orientation; vegetation billboards should be vertical. |
| TQ-005 | MEDIUM | test_map_composer.py | Soft assertion `avg_dungeon_elev >= avg_village_elev * 0.5` allows 50% deviation; effectively meaningless. |
| TQ-006 | MEDIUM | test_map_composer.py | Hash noise range assertion allows [-2, 2] but docstring says [-1, 1]; 100% overshoot is not "small." |
| TQ-007 | MEDIUM | test_dungeon_gen.py | Road connectivity allows 10% disconnected cells; hides real connectivity bugs. |
| TQ-008 | MEDIUM | Multiple test files | 85 `assert result is not None` weak assertions across 36 files that verify nothing meaningful. |
| TQ-009 | MEDIUM | Multiple | Zero integration tests for compose_map pipeline, generate_prop Tripo flow, multi-floor dungeons, LOD-to-Unity, or material transfer. |
| TQ-010 | MEDIUM | test_worldbuilding_v2.py | All 4 interior door alignment tests hardcode `facing: "south"`; east/west door alignment completely untested. |
| TQ-011 | LOW | test_blender_client.py | ResourceWarning: unclosed socket in connection test; missing cleanup in test fixture. |
| TQ-012 | LOW | test_delight.py | ResourceWarning: 2 unclosed file handles; PNG files opened but never closed. |
| TQ-013 | LOW | test_performance_optimization.py | ResourceWarning: unclosed socket; same pattern as TQ-011. |
| TQ-014 | LOW | test_map_composer.py | Uses module-level `random.uniform()` without seed; technically non-deterministic test. |
| TQ-015 | LOW | Multiple test files | Exact float equality checks (`== 0.15`) instead of `pytest.approx()`; IEEE 754 precision risk. |
| TQ-016 | LOW | test_full_pipeline.py | Creates temp images at module load time in shared tempdir; could conflict between parallel workers. |

---

## STATISTICS

| Category | Count |
|----------|-------|
| CRASH | 17 |
| HIGH | 42 |
| MEDIUM | 93 |
| LOW | 61 |
| LOW (Design) | 6 |
| **Total Code Bugs** | **219** |
| Test Quality Issues | 16 |
| **Grand Total** | **235** |

### New Bugs Added (2026-04-02 batch)

| Source Scan | New Bugs | IDs |
|-------------|----------|-----|
| bug_scan_concurrency_state.md | 13 | BUG-175 (HIGH), BUG-182--188 (MEDIUM), BUG-206--210 (LOW) |
| bug_scan_math_precision.md | 10 | BUG-176 (HIGH), BUG-189--194 (MEDIUM), BUG-211--213 (LOW) |
| bug_scan_error_handling.md | 22 | BUG-177--181 (HIGH), BUG-195--205 (MEDIUM), BUG-214--219 (LOW) |
| **Total new** | **45** | (3 duplicates removed vs existing list) |

### Duplicates Removed

| New Bug | Existing Bug | Reason |
|---------|-------------|--------|
| M-02 (gradient recomputed per cluster) | BUG-090 | Same bug, same file, same issue |
| M-05 (quaternion .z as rotation) | BUG-072 | Same file, same root cause (quaternion component extraction) |
| EH-10 (rate limit string matching) | BUG-151 | Same file, same fragile string detection pattern |

### Top Affected Files (updated)

| File | Bug Count |
|------|-----------|
| blender_server.py | 28 |
| worldbuilding.py | 10 |
| environment.py | 10 |
| settlement_generator.py | 14 |
| terrain_materials.py | 8 |
| lod_pipeline.py | 8 |
| environment_scatter.py | 6 |
| terrain_advanced.py | 7 |
| elevenlabs_client.py | 5 |
| fal_client.py | 5 |
| tripo_studio_client.py | 5 |
| vegetation_system.py | 5 |
| _terrain_depth.py | 4 |
| _building_grammar.py | 4 |
| combat_vfx_templates.py | 4 |
| worldbuilding_layout.py | 4 |
| building_interior_binding.py | 4 |
| _dungeon_gen.py | 4 |
| gemini_client.py | 3 |
| performance_templates.py | 3 |
| animation_export.py | 3 |
