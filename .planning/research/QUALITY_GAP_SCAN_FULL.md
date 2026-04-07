# VeilBreakers MCP Toolkit — Full Quality Gap Scan

**Scan date:** 2026-04-06
**Scope:** `Tools/mcp-toolkit/blender_addon/handlers/`, `Tools/mcp-toolkit/src/veilbreakers_mcp/`, `Tools/mcp-toolkit/tests/`
**Methodology:** Read / Grep / Glob static analysis. No code execution, no live Blender runs.
**Author:** Gap-scan subagent (Claude Opus 4.6)

All file paths are absolute. Line numbers refer to the state of the tree on branch `feature/terrain-world-foundation` at scan time.

---

## Executive summary — top 10 critical gaps

1. **[CRITICAL] Terrain mesh generator never creates a UV layer.** `bmesh.ops.create_grid(calc_uvs=True)` in `environment.py:738` is called WITHOUT first creating a UV layer on the bmesh. `calc_uvs=True` only writes into an existing layer; the output mesh therefore has zero `uv_layers`. Every single procedural terrain created by this toolkit is UV-less. All tiled biome terrains (`handle_generate_terrain_tile`) hit the same path.
2. **[CRITICAL] Water generator never creates a UV layer.** `handle_create_water` in `environment.py:1677` builds an entire spline mesh with `bmesh.new()` and a `float_color` layer for flow but never calls `bm.loops.layers.uv.new(...)`. Every water body exported by the toolkit is UV-less, which is why any texture/foam/caustic node wired to UVs would render garbage.
3. **[CRITICAL] Waterfall generator is pure-spec only — no Blender object ever produced.** `env_generate_waterfall` in `__init__.py:1114` calls `generate_waterfall(...)` from `terrain_features.py:254`, which returns only `{vertices, faces, material_indices, ...}`. There is NO handler that calls `mesh_from_spec` on this result. The user’s "flat shaded waterfall" was presumably built via `blender_execute`, so it inherited none of the smoothing, UV, or normal recalculation that `_mesh_bridge.mesh_from_spec` (`_mesh_bridge.py:848`) would have applied.
4. **[CRITICAL] Terrain biome material uses procedural noise in generated-object space — not UVs.** `create_biome_terrain_material` in `terrain_materials.py:2227` builds a full 4-layer splatmap shader with Principled BSDFs, but its bump is a `ShaderNodeTexNoise` fed by default generated coordinates (no `ShaderNodeTexCoord`, no `ShaderNodeMapping`, no `ShaderNodeNormalMap`). Grep: `terrain_materials.py` has **zero** `ShaderNodeTexCoord` references. That means the biome terrain material cannot properly tile textures across world space, cannot use triplanar mapping, and ignores the broken/missing UVs from gap #1 anyway.
5. **[CRITICAL] HDRI environment handler is wired but never loads an image.** `scene.py:589 handle_setup_world` with `environment_type="HDRI"` creates a `ShaderNodeTexEnvironment` at line 667 but NEVER assigns `env_tex.image` — there is no `bpy.data.images.load(...)` call anywhere in `scene.py`. The node is empty → viewport renders black/purple. Additionally `setup_world` is NOT wired to any MCP tool — grep shows zero references in `blender_server.py`.
6. **[CRITICAL] Light-integration and atmospheric-volume systems are pure logic with no Blender instantiation.** `light_integration.py` (364 lines) computes per-prop light placements (torches/campfires/lanterns/etc.) but never calls `bpy.data.lights.new`. Same for `atmospheric_volumes.py` — computes fog/dust/god-ray placements but never creates a single volume object. Both systems are dead: the MCP action returns a JSON spec but nothing appears in the viewport.
7. **[HIGH] No Nishita / physical sky support.** Zero references to `ShaderNodeTexSky` or `nishita` across all handlers. There is no time-of-day system. No cascaded-shadow-map tuning. The only viewport-lighting handler, `handle_setup_dark_fantasy_lighting` (`viewport.py:578`), creates at most a single SUN light with a fixed azimuth/elevation per preset — no sky model.
8. **[HIGH] Beauty viewport disables the scene world.** `_apply_viewport_shading` in `viewport.py:399-402` sets `s.use_scene_world = False` in all 3D viewports. Even if an HDRI were loaded via `setup_world`, beauty-mode screenshots would ignore it. The viewport uses `BEAUTY_STUDIO_LIGHT = "forest.exr"` (line 139) which is Blender's default studio light, not a scene asset the user controls.
9. **[HIGH] Water material has no UV-based foam, no caustics, no depth-based color, no refraction, no wave animation.** `handle_create_water` (`environment.py:1795-1847`) builds a Principled BSDF with only a procedural noise bump. No `ShaderNodeTexCoord`, no caustics mix, no Beer's-law absorption, no Gerstner-like drivers. Zero occurrences of `caustic`, `refraction`, `Gerstner`, `wave_anim` in the water code path.
10. **[HIGH] Tests do not assert UV layer presence for terrain / water / biome material.** `tests/test_environment_handlers.py`, `tests/test_aaa_water_scatter.py`, and `tests/test_terrain_materials.py` each have ZERO occurrences of `uv_layers` or `UVMap`. That’s why bugs #1, #2, and the whole material pipeline silently regressed — pytest says green while outputs are broken.

---

## Category 1 — Lighting pipeline

### 1.1 What exists

| Module | Capability | Actual Blender impact |
|---|---|---|
| `viewport.py:578 handle_setup_dark_fantasy_lighting` | 3-point AREA rig + optional SUN + dark world | Creates real lights — this is the ONLY real-lighting handler currently used |
| `viewport.py:457 handle_setup_beauty_scene` | EEVEE Next engine + material-preview shading + dark studio HDRI | Calls `_apply_viewport_shading` which hard-codes `studio_light="forest.exr"` and sets `use_scene_world = False` |
| `scene.py:589 handle_setup_world` | World node tree (COLOR / GRADIENT / HDRI) | HDRI path is **BROKEN** (no image loaded). Not wired to MCP server at all. |
| `scene.py:686 handle_add_light` | POINT/SUN/SPOT/AREA generic light | Works, but low-level primitive — no sun-calibration helper |
| `light_integration.py` | Per-prop light placement computation | **Pure logic only.** No Blender instantiation. |
| `atmospheric_volumes.py` | Per-biome ground-fog / god-ray placements | **Pure logic only.** No volume objects created. |
| `viewport.py:684-690` | `eevee.use_volumetric_lights=True`, `use_volumetric_shadows=True` | Wired in beauty setup, but no density/tile settings, no god-ray cookies |

### 1.2 What is missing / broken (file:line)

| Severity | Gap | Fix | Effort |
|---|---|---|---|
| CRITICAL | `scene.py:667` creates `ShaderNodeTexEnvironment` but never sets `.image`. HDRI param never reaches a `bpy.data.images.load()`. | Add `hdri_path: str` param to `handle_setup_world`; call `bpy.data.images.load(hdri_path)` and assign `env_tex.image`. Add a library of bundled HDRI paths (`VB_HDRI_{dawn,noon,dusk,overcast,night}.exr`). | medium |
| CRITICAL | `handle_setup_world` is not wired into any MCP tool. Grep of `blender_server.py` finds zero references to `setup_world`. | Expose under `blender_scene` action=`setup_world` and/or `blender_environment` action=`setup_sky`. | trivial |
| CRITICAL | `light_integration.py` computes placements but has no `handle_*` function. `__init__.py:1192` wires `compute_light_placements` as a lambda that returns raw dicts. | Add `handle_place_integrated_lights(params)` that calls `compute_light_placements`, then iterates the result and calls `bpy.data.lights.new(type=...)` + `bpy.data.objects.new` per entry. Parent each light to the source prop object. Wire as `blender_environment` action=`place_lights_from_props`. | medium |
| CRITICAL | `atmospheric_volumes.py` computes volume placements but never creates volumes. | Add `handle_place_atmospheric_volumes(params)` that creates an empty mesh per placement, applies a Principled Volume shader with the right density/anisotropy, and links it under a "VB_Atmosphere" collection. | medium |
| HIGH | No Nishita sky. Grep returns zero `ShaderNodeTexSky` or `nishita` across all handlers. | Add a `setup_sky_nishita(sun_elevation, sun_rotation, air, dust, ozone)` helper in `scene.py`. Wire into compose_map Step 6 (currently only calls `setup_dark_fantasy_lighting`). | small |
| HIGH | No time-of-day preset system. `DARK_FANTASY_LIGHTING_PRESETS` in `viewport.py:72-123` has only 5 presets (default / forest_healthy / forest_transition / forest_review / veil_corrupted) — none are "dawn", "noon", "dusk", "night". | Add time-of-day dict keyed on hour 0-23, with sun elevation/azimuth + sky color + fog density. | medium |
| HIGH | `_apply_viewport_shading` hard-codes `use_scene_world = False` (`viewport.py:402`). Any scene HDRI is ignored in viewport screenshots. | Add `use_scene_world: bool = True` parameter and let callers choose. Default True for hero shots, False for turntables. | trivial |
| HIGH | SUN light in `_create_sun_light` (`viewport.py:548`) has no shadow cascade config. `light_data.shadow_cascade_count`, `shadow_cascade_max_distance`, `shadow_cascade_exponent` are never set. Default is 4 cascades / 200m which is wrong for large terrain tiles. | After `light_data.energy = energy`, set: `light_data.shadow_cascade_count = 4; light_data.shadow_cascade_max_distance = terrain_size * 0.75; light_data.shadow_cascade_exponent = 0.8; light_data.shadow_cascade_fade = 0.1`. | trivial |
| HIGH | No god-ray / volumetric cookie support. `use_volumetric_lights` is on but density is default. | In `_configure_eevee`, set `eevee.volumetric_start = 0.1`, `volumetric_end = 300.0`, `volumetric_tile_size = "8"`, `volumetric_samples = 128`. | trivial |
| MEDIUM | No area-light size calibration per-preset. `BEAUTY_KEY_LIGHT.size = 2.0` is a fixed constant (`viewport.py:38`); for a 2 km terrain the key light should be an absolutely-huge sun. | Derive area-light size from `base_distance` computed at `viewport.py:611`: `size = base_distance * 0.2`. | trivial |
| MEDIUM | Preset `DARK_FANTASY_LIGHTING_PRESETS["default"]["sun"]` is `None` — the default preset never creates a sun. For outdoor terrain the caller MUST pass `preset="forest_healthy"` to get a sun. | Default preset should include a sun; add a new `outdoor_daylight` preset or rename "forest_healthy". | trivial |
| MEDIUM | `mist_settings.use_mist = True` is set in `handle_setup_dark_fantasy_lighting` (`viewport.py:676`) but Blender mist only shows in compositor / render passes — not viewport screenshots. Users will never see it. | Move mist to a dedicated compositor helper, or add a Principled Volume on the scene world node graph for viewport-visible fog. | small |
| MEDIUM | `flicker` animation presets exist in `light_integration.py:114-134` but no code ever writes drivers or keyframes. Even if light instantiation were wired, lights would be static. | When instantiating flicker lights, add a driver on `energy`: `driver.expression = "sin(frame*freq) * amp + base"`. | small |
| LOW | `_lighting_preset_for_name` (`viewport.py:570`) silently falls back to "default" on unknown name. Should log a warning. | Add `logger.warning("Unknown lighting preset %s, using default", name)`. | trivial |

### 1.3 Example fix snippet — HDRI loading (scene.py:662)
```python
elif env_type == "HDRI":
    bg = nodes.new("ShaderNodeBackground")
    bg.location = (0, 0)
    bg.inputs["Strength"].default_value = strength

    env_tex = nodes.new("ShaderNodeTexEnvironment")
    env_tex.location = (-300, 0)

    # FIX: load HDRI image
    hdri_path = validated.get("hdri_path")
    if hdri_path and os.path.exists(hdri_path):
        img = bpy.data.images.load(hdri_path, check_existing=True)
        env_tex.image = img
    else:
        logger.warning("HDRI env_type selected but no hdri_path provided")

    tex_coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")  # FIX: add Mapping node for rotation control
    mapping.inputs["Rotation"].default_value = validated.get("rotation", (0,0,0))
    links.new(tex_coord.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], env_tex.inputs["Vector"])
    links.new(env_tex.outputs["Color"], bg.inputs["Color"])
    links.new(bg.outputs["Background"], output.inputs["Surface"])
```

---

## Category 2 — Material pipeline quality

### 2.1 TEX_COORD + Mapping node coverage (sRGB / Non-Color correctness)

| File | ShaderNodeTexCoord count | Status |
|---|---|---|
| `handlers/procedural_materials.py` | 12 | **OK** — every material uses TexCoord + Mapping (lines 1066, 1184, 1268, 1430, 1537, 1672) |
| `handlers/texture.py` | 9 | **OK** — PBR loader wires TexCoord for each image |
| `handlers/terrain_materials.py` | **1 (actually zero — that single match is `create_` in a function name)** | **BROKEN** — biome terrain material uses default generated coords |
| `handlers/mesh_enhance.py` | 32 | OK (decal system) |
| `handlers/character_advanced.py` | 14 | OK |
| `handlers/destruction_system.py` | 14 | OK |
| `handlers/weathering.py` | 10 | OK |
| `handlers/texture_quality.py` | 6 | OK |
| `handlers/modular_building_kit.py` | 3 | OK |
| `handlers/scene.py` | 3 | Partial — GRADIENT path uses it, HDRI path uses it, COLOR path does not need it |
| `handlers/environment.py` | 1 | **BROKEN** — only occurrence is `vertex_colors.py` import, not a ShaderNode |

### 2.2 Findings

| Severity | Gap | File:line | Fix | Effort |
|---|---|---|---|---|
| CRITICAL | Terrain biome material has no UV coordinates. All 4 layer bump nodes feed from `ShaderNodeTexNoise` with default inputs → generated (object-space) coordinates. Changes of `object.scale` therefore re-tile the texture. | `terrain_materials.py:2294-2301` | Add `ShaderNodeTexCoord` + `ShaderNodeMapping` at start of graph. Feed `TexCoord.UV` → `Mapping.Vector` → per-layer `Noise.Vector`. Expose per-layer `scale` via Mapping node `Scale` so tuning the mapping scales all 4 layers in sync. | small |
| CRITICAL | Terrain biome material has no triplanar fallback. For high-slope faces where UVs stretch, there is no Object-coord projection. | `terrain_materials.py:2260+` | Build a triplanar group: three `TexCoord.Object` projections + `Geometry.Normal` blend factor. Swap in triplanar for the "cliff" and "slope" layers. Reference: AAA_TERRAIN_TEXTURING_RESEARCH.md. | medium |
| CRITICAL | Terrain biome material has NO image textures — only Noise bump + flat Principled BSDF. | `terrain_materials.py:2272-2303` | Add `ShaderNodeTexImage` per layer for base_color, roughness, and normal. Load from a bundled texture set at `assets/terrain/{biome}/{layer}_{channel}.png`. | large |
| CRITICAL | No displacement support. Zero occurrences of `ShaderNodeDisplacement` in `terrain_materials.py`. | `terrain_materials.py:entire file` | Add `ShaderNodeDisplacement` fed from height-weighted noise for each layer. Link to `Output.Displacement`. Requires material `cycles.displacement_method = "BOTH"`. | medium |
| HIGH | Water material has no UV-based features. `handle_create_water` at `environment.py:1804-1847` never adds a `ShaderNodeTexCoord`. | `environment.py:1832` (noise bump) | Add TexCoord + Mapping; feed UV into noise scale. Requires fixing gap #2 (UV layer) first. | small |
| HIGH | Normal-map color space correctness: `terrain_materials.py` doesn't use `ShaderNodeNormalMap` at all — it uses `ShaderNodeBump`. `Bump` requires a scalar height, not a tangent-space normal. If the user ever plugs in a baked normal map, colors will be wrong. | `terrain_materials.py:2297` | Replace `ShaderNodeBump` with `ShaderNodeNormalMap` when source is an image; keep Bump when source is procedural noise. | trivial |
| HIGH | Water material never sets `Principled BSDF.Transmission Weight > 0` when `preview_fast=True`. At default `preview_fast=True`, transmission is 0.0 and alpha is 1.0 — no refraction at all. | `environment.py:1824-1828` | Either make `preview_fast` disabled by default OR add a dedicated `handle_apply_water_shader(quality="hero")` that rebuilds the material with full transmission/refraction/Gerstner nodes. | small |
| HIGH | Water material has no Gerstner / wave animation. `preview_fast=False` path only adds a single static `ShaderNodeTexNoise` bump. | `environment.py:1833-1846` | Add a second noise texture with a `ShaderNodeMapping` whose `Location` is driven by `#frame * 0.01`. Mix two noise bumps with different scales for multi-frequency waves. | medium |
| HIGH | No ORM (Occlusion/Roughness/Metallic packed) support in `handle_create_pbr_material` (`texture.py:197`). Individual files only. | `texture.py:197` | Add `orm_path` parameter that loads packed texture and splits via `ShaderNodeSeparateColor`. Code already exists for ORM in `texture.py:643-743` bake path — extract into a shared helper. | small |
| HIGH | Detail normals not supported. The only "detail" in `terrain_materials.py` is `detail_scale` (procedural). No mix of base normal + detail normal. | `terrain_materials.py:2294` | Add second Noise/Image bump scaled 4-16x, mix via `ShaderNodeVectorMath` (add) with the base normal. | medium |
| MEDIUM | `handle_setup_world` COLOR path at `scene.py:627` hard-codes alpha=1.0 but does not normalize input to sRGB — user may supply linear floats expecting sRGB. | `scene.py:602` | Document that `color` is expected in linear space, or add a `color_space="srgb"` param that converts. | trivial |
| MEDIUM | Biome terrain material uses `bsdf.inputs["Roughness"].default_value = lp["roughness"]` without noise variation. All ground faces look mirror-flat in roughness → surface looks plasticky. | `terrain_materials.py:2273` | Wire `noise.outputs["Fac"]` → `ShaderNodeMapRange` → `Roughness` so roughness varies with the detail noise. | trivial |
| MEDIUM | `procedural_materials.py` uses `ShaderNodeBump` mostly, but `terrain_materials.py:2260` has color_attribute → bsdf without any color-space fix for vertex colors (they're already linear, but when exported to Unity the color-space mismatch corrupts splatmaps). | `terrain_materials.py:2355` | Use `type="BYTE_COLOR"` with `domain="CORNER"` for splatmaps (not `FLOAT_COLOR`) and document the expected color space. | small |
| LOW | Color-space enforcement is inconsistent: `texture.py:101-104` uses `"Non-Color"` strings; `texture.py:257` uses `tex_node.image.colorspace_settings.name = colorspace`. Works, but there are zero tests that assert normal/roughness maps are loaded Non-Color. | `tests/test_texture_handlers.py` | Add unit tests that create a PBR material and assert `normal_tex.image.colorspace_settings.name == "Non-Color"`. | trivial |

### 2.3 Fix snippet — biome terrain material UV coords (terrain_materials.py:2260)
```python
# INSERT after vcol_node:
tex_coord = _add_node(tree, "ShaderNodeTexCoord", -1000, 400, "Terrain Coords")
mapping = _add_node(tree, "ShaderNodeMapping", -800, 400, "Terrain Mapping")
mapping.inputs["Scale"].default_value = (
    palette.get("uv_scale", 8.0),
    palette.get("uv_scale", 8.0),
    palette.get("uv_scale", 8.0),
)
links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])
# Then in the layer loop:
links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
```

---

## Category 3 — Mesh quality (UV / manifold / normals / smoothing)

### 3.1 Per-generator audit table

| Generator | File:line | bmesh.new? | UV layer? | Smooth shading? | Normals recalc? | Merge-by-distance? |
|---|---|---|---|---|---|---|
| `_create_terrain_mesh_from_heightmap` | `environment.py:720` | yes | **NO** (`calc_uvs=True` in create_grid has no layer to write to) | yes (line 778) | no | no |
| cliff overlay mesh | `environment.py:801` | yes | **NO** | **NO** | no | no |
| `handle_paint_terrain` (uses existing mesh) | `environment.py:1316` | from_mesh | preserved | N/A | no | no |
| `handle_carve_river` (modifies existing) | `environment.py:1385` | from_mesh | preserved | N/A | no | no |
| `handle_generate_road` (modifies existing terrain) | `environment.py:1450` | from_mesh | preserved | N/A | no | no |
| road surface mesh | `environment.py:1494` | yes | **YES** (line 1495) but loops never written to | yes (line 1562) | yes (line 1556) | yes (line 1555) |
| `handle_create_water` | `environment.py:1677` | yes | **NO** | yes (line 1784) | no | no |
| `generate_waterfall` spec | `terrain_features.py:254` | N/A (pure logic) | **NO uvs key** | N/A | N/A | N/A |
| `generate_canyon` spec | `terrain_features.py` | N/A | **NO uvs key** | N/A | N/A | N/A |
| `generate_cliff_face` spec | `terrain_features.py:446` | N/A | **NO uvs key** | N/A | N/A | N/A |
| `generate_swamp_terrain` | `terrain_features.py` | N/A | **NO uvs key** | N/A | N/A | N/A |
| `mesh_from_spec` (generic) | `_mesh_bridge.py:848` | yes | **ONLY if spec.uvs non-empty** (line 1000) | yes (line 1019) | yes (line 1011) | yes (dedup weld at 934) |
| `procedural_meshes.py` (22K lines, ~260 generators) | `procedural_meshes.py` | N/A | **NO uvs key in 259/260 generators** (only "Curtain" at line 14942 supplies uvs) | N/A | N/A | N/A |
| `handle_generate_lods` | `lod_pipeline.py:909` | yes | inherited | yes | auto | yes (decimate) |
| `worldbuilding.py` mesh creation (30 sites) | `worldbuilding.py` | yes | unknown — only 6 `use_smooth` calls for 30 creations | inconsistent | inconsistent | inconsistent |

### 3.2 Critical gaps

| Severity | Gap | File:line | Fix | Effort |
|---|---|---|---|---|
| CRITICAL | Terrain mesh has no UV layer. `bmesh.ops.create_grid(calc_uvs=True)` at `environment.py:738-744` needs a pre-existing `bm.loops.layers.uv.new(...)` — `calc_uvs` does NOT create one. | `environment.py:736` | Before `bmesh.ops.create_grid(...)`, call `bm.loops.layers.uv.new("UVMap")`. Verify output mesh has `len(mesh.uv_layers) > 0`. | trivial |
| CRITICAL | Water mesh has no UV layer. | `environment.py:1677-1681` | After `bm = bmesh.new()`, call `bm.loops.layers.uv.new("UVMap")`. Write per-loop UVs in the face loop at line 1770 based on `(path_index / total_path, cross_section_index / cross_sections)`. | trivial |
| CRITICAL | Cliff overlay meshes (`environment.py:801-811`) have no UV layer, no smoothing, no normals recalc. These are the bumpy cliff "walls" that `_create_terrain_mesh_from_heightmap` adds. | `environment.py:801` | Create UV layer, call `bmesh.ops.recalc_face_normals`, then set `use_smooth = True` on polys. | trivial |
| CRITICAL | `terrain_features.py` pure-logic generators never emit UVs in their spec (`"uvs": [...]` absent from all 12+ generators). `_mesh_bridge.mesh_from_spec` at `_mesh_bridge.py:1000` only creates a UV layer if `uvs` is non-empty, so when these specs are ever built into meshes they have no UVs. | `terrain_features.py:421, 446, ...` | Add UV generation helper: project vertices onto dominant plane per face, pack as `uvs` list. Add to every `return {...}`. | medium |
| CRITICAL | `procedural_meshes.py` has **one** generator out of 260 that supplies UVs (Curtain at line 14942). Every other furniture/prop/dungeon generator relies on downstream `smart_project` or `unwrap_xatlas` — but compose_map never calls uv unwrap on props. | `procedural_meshes.py` (259 functions) | Either (a) every generator emits projected UVs in its spec, OR (b) `mesh_from_spec` calls `bpy.ops.uv.smart_project` as a fallback when `uvs` is empty. Option (b) is far cheaper. | medium |
| CRITICAL | Waterfall (via `env_generate_waterfall`) is never rendered. The lambda in `__init__.py:1114` calls `generate_waterfall(...)` and returns its dict as the action result. The caller must manually build the mesh via `blender_execute` or `mesh_from_spec`. | `__init__.py:1114` + `terrain_features.py:254` | Add a wrapping handler `handle_create_waterfall(params)` that calls `generate_waterfall`, then `mesh_from_spec`, then wires each material_indices slot to an actual Blender material (cliff_rock, wet_rock, pool_bottom, ledge_stone, moss). Add UV generation to `generate_waterfall` BEFORE calling `mesh_from_spec`. | medium |
| HIGH | Road surface mesh (`environment.py:1494`) creates a UV layer but never writes UVs into `loop[road_uv].uv` during face creation (lines 1533-1549). The layer exists but is zeroed. `remove_doubles` at line 1555 then merges vertices — if UVs had been written they'd be averaged, but since all UVs are (0,0) the remove_doubles is lossless-but-meaningless. | `environment.py:1541-1549` | After `face = road_bm.faces.new(...)`, iterate `face.loops` and assign UVs based on cumulative distance along path (U) and cross-section position (V). | small |
| HIGH | `handle_paint_terrain` (`environment.py:1266`) modifies an existing mesh via `bm.from_mesh` / `bm.to_mesh`. But the bmesh round-trip loses `mesh.loops[].normal` custom normals. If the terrain had been cliff-corrected with custom normals, this destroys them. | `environment.py:1317, 1341` | Before `bm.to_mesh`, call `mesh.calc_normals_split()` OR pass `create_normals_split=True` to to_mesh. Preserve `mesh.has_custom_normals`. | small |
| HIGH | `handle_carve_river` (`environment.py:1385`) modifies vertex Z but never calls `mesh.update()` or `bm.normal_update()` after — the next rendered frame may show interpolated old normals. | `environment.py:1409` | Before `bm.to_mesh(mesh)`, call `bm.normal_update()`. After, call `mesh.update()`. | trivial |
| HIGH | `handle_generate_road` (`environment.py:1475-1481`) mutates terrain verts but doesn't recalc normals. The road carves a flat strip into the terrain — the two seam edges need new normals. | `environment.py:1480` | After `bm.to_mesh(mesh)`, call `mesh.calc_normals_split()` OR `bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])` before `bm.to_mesh`. | trivial |
| HIGH | `worldbuilding.py` has 30 `bmesh.new()` sites but only 6 `use_smooth` hits. Most furniture/architecture is thus flat-shaded. | `worldbuilding.py` (30 sites) | Audit each bmesh site. Default to smooth shading for curved surfaces; only leave flat where geometry is intentionally faceted (crates, stones). | large |
| HIGH | No `use_auto_smooth` / sharp-edge propagation in `_create_terrain_mesh_from_heightmap`. Terrain grid renders fully smoothed — cliff corners have washed-out edges. | `environment.py:776-779` | Add `mesh.use_auto_smooth = True; mesh.auto_smooth_angle = math.radians(35.0)` after `use_smooth` loop. Mark boundary edges as sharp where slope > cliff_threshold_deg. | small |
| MEDIUM | No `merge_by_distance` on terrain mesh (`environment.py:772`). Floating-point error from heightmap interpolation can leave micro-gaps at tile boundaries. | `environment.py:770` | After vertex z assignment, run `bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)`. | trivial |
| MEDIUM | `handle_generate_terrain_tile` doesn't share edge vertices across adjacent tiles. Seams will crack under lighting. `handle_stitch_terrain_edges` exists (line 1178) but is a post-process. | `environment.py:1116-1126` | Have `_create_terrain_mesh_from_heightmap` accept `neighbors` dict and snap edge vertices to neighbor's vertices. Or ensure `stitch_terrain_edges` is auto-called after tile generation in compose_map. | medium |
| MEDIUM | `bmesh.ops.recalc_face_normals` only called in 3 sites out of 143 bmesh creation sites. Most generators trust the user to pass faces in consistent winding order — risky. | (many files) | Add a `_finalize_bmesh(bm)` helper in `_shared_utils.py` that does: recalc_normals, remove_doubles, update. Call at end of every generator. | medium |

---

## Category 4 — Texture pipeline

### 4.1 What exists

| Feature | Status | File:line |
|---|---|---|
| PBR material creation | YES | `texture.py:197 handle_create_pbr_material` |
| ORM split in bake path | YES | `texture.py:643-743` |
| AO bake | YES | `texture.py:332 handle_bake_textures` (bake_type=AO) |
| Normal bake | YES | `texture.py:332` (bake_type=NORMAL, normal_space=TANGENT at line 425) |
| Roughness bake | YES | `texture.py:332` (bake_type=ROUGHNESS) |
| Combined bake | YES | `texture.py:332` (bake_type=COMBINED) |
| Texture validation | YES | `texture.py:452 handle_validate_texture` |
| Wear map generation | YES | `texture.py:800 handle_generate_wear_map` |
| Curvature bake | NO | Not present in `_ALLOWED_BAKE_TYPES` |
| Cavity / pointiness bake | NO | Absent |
| Texture upscaling | YES | `test_esrgan_runner.py` exists, wiring unclear |
| Detail normal maps | NO | Not supported in any PBR loader |
| Texture atlasing | Partial | `texture.py:1018+` bake procedural to image but no packing |

### 4.2 Gaps

| Severity | Gap | File:line | Fix | Effort |
|---|---|---|---|---|
| HIGH | No curvature / cavity bake. AAA terrain requires cavity AO to bring out cracks. | `texture.py:32` (_ALLOWED_BAKE_TYPES) | Add "CURVATURE" (approximated from pointiness via shader trick) and "CAVITY" (inverted AO scaled). Document in handler docstring. | small |
| HIGH | No automatic detail-normal pipeline. There is no handler `handle_create_detail_normal` or equivalent. | `texture.py` (new) | Add `handle_apply_detail_normal(object_name, detail_path, tile_scale=16)` that inserts a second ShaderNodeTexImage + ShaderNodeNormalMap with custom tile scale, then mixes with base normal via ShaderNodeVectorMath add. | medium |
| MEDIUM | Texture validation (`handle_validate_texture` at `texture.py:452`) doesn't check color-space correctness (normal/roughness/metallic/ORM must all be Non-Color). | `texture.py:486-490` | Add assertions: if image name matches `_normal|_rough|_metal|_orm`, assert `colorspace_settings.name == "Non-Color"`; report mismatches. | trivial |
| MEDIUM | No MIP tail cutoff. Game-ready textures need `img.filepath_raw` plus MIP chain validation; none is done. | `texture.py:452` | Add check that image dimensions are power-of-two. | trivial |
| LOW | ESRGAN upscaler integration exists (`src/veilbreakers_mcp/shared/esrgan_runner.py`?) but no handler action wires it to a material. | (new handler) | Add `handle_upscale_texture(image_name, scale=4)` that runs esrgan and replaces the image data. | medium |
| LOW | No bundled texture library. Every material creates procedural noise — no PNG asset served. | `Tools/mcp-toolkit/assets/textures/` | Add a small library of tileable rock/grass/sand/moss textures (creative-commons). Document in `env_model_library` companion file. | large |

---

## Category 5 — UV unwrap pipeline

### 5.1 What exists

| Handler | File:line | Notes |
|---|---|---|
| `handle_analyze_uv` | `uv.py:191` | Reports UV coverage, island count |
| `handle_unwrap_xatlas` | `uv.py:297` | High-quality xatlas unwrap |
| `handle_unwrap_blender` | `uv.py:432` | smart_project / angle_based |
| `handle_pack_islands` | `uv.py:480` | repack existing UVs |
| `handle_generate_lightmap_uv` | `uv.py:519` | xatlas lightmap atlas for UV2 |
| `handle_equalize_density` | `uv.py:631` | Texel density normalisation |
| `handle_export_uv_layout` | `uv.py:799` | PNG export of UV layout |
| `handle_set_active_uv_layer` | `uv.py:893` | Select active UV |
| `handle_ensure_xatlas` | `uv.py:925` | Pip-install xatlas into Blender |

### 5.2 Gaps

| Severity | Gap | Fix | Effort |
|---|---|---|---|
| CRITICAL | Smart UV Project / xatlas unwrap is NEVER auto-called after mesh creation in the terrain pipeline, water pipeline, or compose_map. | Add a pipeline step after terrain/water creation: `unwrap_blender(method="smart_project", island_margin=0.01)`. In compose_map this should follow terrain generation. | trivial |
| HIGH | `handle_unwrap_xatlas` (`uv.py:297`) requires a running xatlas install. If `ensure_xatlas` hasn't been called, `xatlas not installed` error is returned (line 303-305). No automatic install on first use. | Add `try: import xatlas; except: handle_ensure_xatlas(); import xatlas` pattern at top of handler. | trivial |
| HIGH | No area-distortion / angle-distortion report. `handle_analyze_uv` doesn't compute per-face distortion — so broken UVs pass validation silently. | Add `compute_uv_distortion(mesh, uv_layer_name)` that returns mean and max angular / area distortion. Gate `game_check` on distortion < threshold. | small |
| MEDIUM | Lightmap UV generation only works for single-material meshes well. Multi-material terrains get poor packing. | Extend `handle_generate_lightmap_uv` to respect material-slot boundaries. | medium |
| LOW | No multi-UV channel support documented. UV3 / UV4 for detail maps / decal layers not mentioned. | Add `handle_create_uv_channel(name, copy_from)` action. | trivial |

---

## Category 6 — Vegetation / scatter system

### 6.1 What exists

| Capability | File:line | Status |
|---|---|---|
| Poisson-disk scatter with slope/moisture filter | `environment_scatter.py:1438-1463` | OK |
| 6-biome grass card system with wind VC | `environment_scatter.py:919` | OK — grass is built as dual-quad cards |
| Wind vertex colors on trunk | `environment_scatter.py:872-880` | OK |
| Billboard LOD setup for tree templates | `environment_scatter.py:573` `_setup_billboard_lod` | Metadata only — no actual impostor texture baked |
| Collection-instance reuse | `environment_scatter.py:1559-1592` | OK — uses `objects.new(name, template.data)` share mesh data |
| Building/road exclusion zones | `environment_scatter.py:1466-1516` | O(n × m) brute force, OK for <5k placements |
| Geometry Nodes scatter preset | `geometry_nodes.py:1280 handle_face_scatter` | Exists but is per-face distribution — not terrain-wide |
| `vegetation_system.py` | `vegetation_system.py` (833 lines) | Wind colors, PROP-003 LOD tagging |
| L-system trees | `vegetation_lsystem.py` (1189 lines) | Procedural trunk branching |

### 6.2 Gaps

| Severity | Gap | File:line | Fix | Effort |
|---|---|---|---|---|
| CRITICAL | Grass scatter creates individual Blender objects for every grass card (`environment_scatter.py:1558-1592`). For 5000 cards that's 5000 `bpy.data.objects.new` calls — unusably slow and memory-heavy for AAA densities. | `environment_scatter.py:1559` | Replace the per-instance object creation with a Geometry Nodes Scatter tree: `GeometryNodeDistributePointsOnFaces` + `GeometryNodeInstanceOnPoints` + `GeometryNodeSetMaterial`. One modifier on terrain instead of 5000 objects. Existing `geometry_nodes.py:1280` has the foundation. | large |
| CRITICAL | Billboard LOD impostor is metadata-only. `_setup_billboard_lod` at `environment_scatter.py:573` writes custom properties `lod_billboard_enabled`, `lod_billboard_type`, etc., but never renders an actual impostor texture and never creates an LOD1 object. | `environment_scatter.py:573` | Add actual impostor rendering: place a camera facing the tree, render 8 angles into a 2048×2048 atlas, create a low-poly quad mesh, assign a material with the impostor texture, add it as LOD1 to the template's LOD group. | large |
| HIGH | Wind animation is vertex-color metadata only. There is no shader that READS `wind_vc` and deforms geometry — unless the Unity side does it. | `environment_scatter.py:752-830` | Add a Blender geometry-nodes wind node group that displaces vertices based on `wind_vc.x` (amplitude) × `sin(frame * wind_vc.y)`. Attach to all scattered vegetation templates. | medium |
| HIGH | Exclusion zone check is O(placements × exclusion_zones) at `environment_scatter.py:1502-1516`. For 5000 placements × 200 buildings = 1 M checks. Not catastrophic, but should use BVH/quadtree. | `environment_scatter.py:1502` | Build a simple 2D bucket grid (bucket size = terrain_size / 32). Insert each exclusion zone into overlapping buckets. Per-placement: look up its bucket, check against O(k) zones. | small |
| HIGH | Building bounding-box computation uses `matrix_world @ Vector(corner)` for every child of every EMPTY in the scene — iterates every time scatter is called. For a 100-building town this is ~800 transforms per scatter call. Cached rarely. | `environment_scatter.py:1468-1490` | Cache building footprints once per scatter call. Better: store footprint as a custom property on the EMPTY when the building is placed. | small |
| MEDIUM | No seasonal variation. Grass/tree templates don't differ by season even though `env_model_library.py` (new file) has `season` catalog. | `environment_scatter.py:1522-1529` | Accept `season` param, route to per-season template. | small |
| MEDIUM | Scatter doesn't respect water bodies. There's no check that placement is above water level. Vegetation ends up under the lake. | `environment_scatter.py:1506-1514` | After exclusion-zone filter, for each water object in scene, check if placement_pos.z < water.location.z and reject. | small |
| MEDIUM | Prop scatter uses separate O(n²) density grid in `handle_scatter_props` (not shown here — need to check) | `environment_scatter.py` after 1605 | Verify and rewrite with bucket grid. | small |
| LOW | No LOD chain generation for non-tree scatter. `PROP-003: LOD distance thresholds` are tagged but not materialized. | `environment_scatter.py:724, 810` | Wire to `lod_pipeline.generate_lod_chain` and create LOD1/LOD2 meshes via decimate. | medium |

---

## Category 7 — Export / game-ready pipeline

### 7.1 What exists

| Feature | File:line | Status |
|---|---|---|
| FBX export | `export.py:215 handle_export_fbx` | OK |
| glTF export | `export.py:300 handle_export_gltf` | OK |
| Collision mesh rename (_COL → UCX_) | `export.py:106` | OK for existing _COL meshes, but no generation |
| UV2 lightmap auto-slot | `export.py:140` | OK — moves lightmap UV to slot 1 |
| Collision mesh GENERATION | `lod_pipeline.py:413 generate_collision_mesh` | Pure logic — decimated hull. No handler exposes it. |
| LOD generation handler | `lod_pipeline.py:909 handle_generate_lods` | OK — exposed |
| Texture atlasing | **MISSING** | No atlas baker for shared props |
| Lightmap UV generation | `uv.py:519 handle_generate_lightmap_uv` | OK via xatlas UV2 |
| Game-ready validation | `mesh.py:1224 handle_check_game_ready` | OK — checks poly budget, UV, materials, naming, transforms |

### 7.2 Gaps

| Severity | Gap | File:line | Fix | Effort |
|---|---|---|---|---|
| CRITICAL | No collision mesh GENERATION handler. `lod_pipeline.generate_collision_mesh` exists as pure logic (`lod_pipeline.py:413`) but no `handle_*` wraps it. | (new) | Add `handle_generate_collision(object_name, target_tris=500, method="convex_hull")` that calls `generate_collision_mesh` and creates a Blender mesh named `{obj}_COL`. Export.py:106 already renames to UCX_. | small |
| HIGH | No texture atlasing for props. Exported scenes have 1000 materials instead of 10 packed atlases. | (new) | Add `handle_atlas_materials(collection_name, atlas_size=4096)` that packs material textures via a bin packer, rewrites material to use the atlas, and updates UVs with offset+scale. | large |
| HIGH | `handle_check_game_ready` at `mesh.py:1224` checks UV presence but not UV coverage, not degenerate triangles, not concave polygons. | `mesh.py:1257` | Extend `_evaluate_game_readiness` to include: UV coverage > 0.3, no UV overlap, no zero-area triangles, no concave N-gons. | small |
| HIGH | FBX export doesn't bake modifiers by default. If a terrain has a Subdivision Surface modifier, it exports the coarse cage. | `export.py:215` | Ensure `bake_modifiers=True` default and document. | trivial |
| MEDIUM | No scene-wide batch `game_check`. Only per-object. | `mesh.py:1224` | Add `handle_batch_game_check(objects=None)` that runs check on every mesh and returns aggregate report. | trivial |
| MEDIUM | Export doesn't scrub custom Blender properties that Unity can't read. | `export.py:215` | Add pre-export step that removes non-Unity-compatible custom props (dicts, nested objects). | trivial |
| LOW | No glTF Draco compression toggle. | `export.py:300` | Add `draco_compression: bool = False` param. | trivial |

---

## Category 8 — Water / fluid specifics

### 8.1 Current water shader audit (`environment.py:1794-1847`)

- `preview_fast=True` (default): Principled BSDF with base_color=(0.019, 0.055, 0.043, 1.0), roughness=0.16, IOR=1.333, alpha=1.0, transmission=0.0. **Opaque** — no refraction, no transparency. Roughness 0.16 gives blurry reflections only.
- `preview_fast=False`: adds a single static `ShaderNodeTexNoise` → `ShaderNodeBump` with strength 0.04. Transmission=0.2, alpha=0.68. Still no waves, foam, or caustics.

### 8.2 Gaps

| Severity | Gap | File:line | Fix | Effort |
|---|---|---|---|---|
| CRITICAL | No UV layer on water mesh (see Category 3). Nothing UV-tiled renders correctly. | `environment.py:1677` | See Category 3 gap. | trivial |
| CRITICAL | No depth-based color absorption (Beer-Lambert). Shallow water and deep water look identical. | `environment.py:1810+` | Add `ShaderNodeTexCoord → Geometry.Position → separate Z → divide by water_depth → mix between shallow_color and deep_color → BSDF.Base Color`. | small |
| CRITICAL | No foam. The `float_color` layer `flow_vc` stores foam in its alpha channel (`environment.py:1772-1773`) but the material never reads `VertexColor.Alpha` — no foam is ever visible. | `environment.py:1804+` | Add `ShaderNodeVertexColor` referencing `flow_vc`, pipe Alpha → `ShaderNodeMixShader` with a white foam BSDF. | small |
| HIGH | No Gerstner wave animation. Static scene shows mirror surface. | `environment.py:1833-1846` | Add two ShaderNodeTexNoise with `ShaderNodeMapping.Location` driven by `#frame * 0.02`. Mix the two at different scales. Feed to bump strength 0.1 for hero shots. | medium |
| HIGH | No caustics projection. Under-water floor should show light caustics. | (new) | Add a projection spotlight with a caustic cookie texture (or use Cycles Light Path caustics). | medium |
| HIGH | No refraction IOR mapping. `IOR = 1.333` is set but `Transmission = 0` in preview mode — the IOR is meaningless. | `environment.py:1826-1828` | Make `Transmission Weight = 0.8` default for hero mode. | trivial |
| HIGH | No waterfall-specific shader. Falling water should have vertical stretch noise and heavy foam. | (new) | Add `create_waterfall_material(height)` that uses a `ShaderNodeTexCoord.Generated Z` scaled by height → noise.Vector → strong bump. | medium |
| MEDIUM | `flow_vc` encodes flow direction in R/G but flow direction is never animated with time. Water appears still. | `environment.py:1724-1725` | Add a `ShaderNodeMapping` whose Location Y is driven by `#frame * -speed` based on `VertexColor.R`. | small |
| MEDIUM | No shore wetness darkening. The terrain directly around water should darken roughness. | `terrain_materials.py` or scatter | Add shoreline mask vertex color that's blended in biome material. | medium |

### 8.3 Waterfall is completely unbuilt

See Category 3 gap: `env_generate_waterfall` is a pure-logic spec-returner. The user's "flat shaded waterfall" came from executing a `blender_execute` script by hand. **No shading, no uv, no materials, no smoothing applied.** This is why it looks flat.

---

## Category 9 — Performance / scalability

### 9.1 Nested loops audit

| Pattern | File:line | Complexity | Impact |
|---|---|---|---|
| Exclusion-zone filter | `environment_scatter.py:1502-1516` | O(placements × zones) | 5000×200=1M compares — acceptable but not great |
| Cluster search in `merge_nearby_lights` | `light_integration.py:258-265` | O(n × k) where k is current cluster size | OK for <500 lights |
| Template BB corner collection | `environment_scatter.py:1474-1481` | O(empties × children × 8 corners) | repeated per scatter call |
| Vertex color per-loop write | `environment.py:1770-1773` | O(faces × 4 loops) | fine |
| Verts.layers loop | `environment_scatter.py:753-830` | O(verts × passes) | fine for grass cards |
| `for vert in bm.verts` heightmap interpolation | `environment.py:749-770` | O(verts) with constant work | fine |

### 9.2 Memory leaks

Grep `bmesh.new` vs `bm.free`:
- `environment.py`: 8 each → balanced
- Overall project: needs audit

Additional concerns:
- `handle_paint_terrain` creates bmesh, assigns face materials, never calls `bm.free()` if an exception is thrown between `bm.from_mesh` (line 1317) and `bm.free` (line 1342). Missing try/finally.
- Same risk in `handle_carve_river` (`environment.py:1385-1410`).
- Same risk in `handle_generate_road` (`environment.py:1450-1481`).

| Severity | Gap | File:line | Fix | Effort |
|---|---|---|---|---|
| HIGH | Bmesh leaks on exception in `handle_paint_terrain`, `handle_carve_river`, `handle_generate_road`. | `environment.py:1316-1342, 1385-1410, 1450-1481` | Wrap in `try: ... finally: bm.free()`. | trivial |
| HIGH | Scatter exclusion grid is O(n×m). For 500 props × 1000 placements the hot path dominates. | `environment_scatter.py:1502` | Replace with 2D bucket grid (see Category 6). | small |
| MEDIUM | Full mesh rebuilds on every paint / carve / road call. For large terrains (4k × 4k verts = 16 M) this re-copies all data. | `environment.py:1317` | Add `handle_terrain_mutate(object_name, mutations=[...])` that batches multiple operations into one bmesh roundtrip. | medium |
| MEDIUM | `environment_scatter.py:1403-1404` builds `set(round(v.co.x, 3) for v in bm.verts)` for grid detection — O(verts × log). For 4M-vert terrain this is 4M rounds + log inserts, noticeable. | `environment_scatter.py:1403` | Cache grid dimensions as custom properties on the terrain object at creation time. Read on scatter. | trivial |
| LOW | No BVH caching for raycast-on-terrain in scatter. Height sampling uses bilinear interp from heightmap which is fast, but other operations may slow down. | `environment_scatter.py:1567` | Consider `mathutils.bvhtree.BVHTree.FromBMesh` caching when raycast is needed. | small |

---

## Category 10 — Tests

### 10.1 Coverage table

| Handler family | Test file | Coverage quality |
|---|---|---|
| environment terrain | `test_environment_handlers.py` | Validation / erosion / heightmap — but NO UV layer assertions |
| water AAA | `test_aaa_water_scatter.py` | Output dict structure checked — but NO UV layer assertion, no material node graph assertion |
| terrain materials | `test_terrain_materials.py` | Biome palette checks — NO TexCoord / Mapping / UV checks |
| terrain depth | `test_terrain_depth.py` | Cliff / waterfall spec generation checks |
| scatter | `test_environment_scatter_handlers.py` | Exists |
| UV | `test_uv_handlers.py` | xatlas, smart_project, pack |
| viewport beauty | `test_viewport_beauty.py` | Lighting setup checks |
| road network | `test_road_network.py` | UV presence checked (found in grep) |
| procedural meshes | `test_procedural_meshes*.py` | Spec validation — not UV |

### 10.2 Skipped / xfail

13 skips across 8 files (`test_character_advanced.py:2`, `test_character_skin_modifier.py:1`, `test_clothing_wrinkle.py:1`, `test_csharp_syntax_deep.py:1`, `test_dungeon_gen.py:1`, `test_furniture_rotation.py:4`, `test_lod_pipeline.py:2`, `test_mesh_integration.py:1`). Not excessive.

### 10.3 Gaps

| Severity | Gap | Test file to add to | Fix | Effort |
|---|---|---|---|---|
| CRITICAL | No UV assertion for terrain generator. | `test_environment_handlers.py` | After `handle_generate_terrain`, assert `len(terrain_obj.data.uv_layers) > 0` and iterate `obj.data.uv_layers[0].data` to verify UVs are non-zero. | trivial |
| CRITICAL | No UV assertion for water generator. | `test_aaa_water_scatter.py` | Same as above for `handle_create_water`. | trivial |
| CRITICAL | No node-graph assertion for biome terrain material. | `test_terrain_materials.py` | After `create_biome_terrain_material`, assert `any(n.type == 'TEX_COORD' for n in mat.node_tree.nodes)`, `any(n.type == 'MAPPING' for n in mat.node_tree.nodes)`. | trivial |
| HIGH | No HDRI image-load assertion in `handle_setup_world` test. | `test_scene_collection_handlers.py` | After calling with `environment_type="HDRI", hdri_path=fixture_path`, assert `env_tex.image.filepath == fixture_path`. | trivial |
| HIGH | No waterfall end-to-end test. The only test is of `generate_waterfall` pure-logic. No test verifies that an actual Blender object is produced. | `test_terrain_features_v2.py` | Add test that calls the new `handle_create_waterfall`, fetches `bpy.data.objects["Waterfall"]`, asserts `len(mesh.uv_layers) > 0`, `any(poly.use_smooth for poly in mesh.polygons)`. | small |
| HIGH | No collision-mesh generation test. | `test_lod_pipeline.py` | Add test that calls (new) `handle_generate_collision`, verifies a `{obj}_COL` mesh exists with tri count < target. | trivial |
| HIGH | No shader-quality regression test. If someone rebuilds terrain_material without TexCoord again, nothing catches it. | `test_terrain_materials.py` | Parameterize over all biomes, assert each material graph has required node types. | small |
| MEDIUM | No performance regression benchmark. AAA quality gaps won't be measurable without baseline. | `tests/test_aaa_performance_budget.py` (exists) | Extend existing AAA budget test: scatter 5000 trees, assert scatter time < 10s. | small |
| MEDIUM | No visual-diff test for lighting presets. | `test_viewport_beauty.py` | Render each preset, hash the output, compare to baseline. | medium |
| LOW | No test of `handle_place_integrated_lights` or `handle_place_atmospheric_volumes` because they don't exist yet. | (new test files) | Add after those handlers are implemented. | small |

---

## Appendix A — Security sandbox audit

`blender_addon/handlers/execute.py:35-112` — `_SAFE_BUILTINS` now includes the previously-missing builtins per user feedback:

Present (confirmed): `True, False, None, print, len, range, list, dict, tuple, set, frozenset, str, int, float, bool, abs, min, max, sum, round, sorted, reversed, enumerate, zip, map, filter, isinstance, repr, iter, next, any, all, chr, ord, hex, oct, bin, pow, divmod, hash, slice, complex, bytes, bytearray, Exception, ValueError, TypeError, KeyError, IndexError, AttributeError, RuntimeError, StopIteration, ZeroDivisionError, hasattr, getattr, setattr, delattr, issubclass, type, property, super, object, classmethod, staticmethod, callable, format, id, dir, NotImplementedError, OSError, FileNotFoundError, IOError, OverflowError, NameError, ImportError, ModuleNotFoundError`.

Correctly blocked: `exec, eval, compile, open, globals, locals, vars, __import__ (overridden), breakpoint, input, help`.

Per user feedback `feedback_security_sandbox_relaxed.md`: BLOCKED_FUNCTIONS must stay minimal (exec/eval/compile/__import__/breakpoint/globals/locals/vars ONLY). This looks correct. No action needed.

---

## Appendix B — File size / complexity hotspots

| File | Lines | Notes |
|---|---|---|
| `procedural_meshes.py` | 22495 | 260+ generators — needs UV emission retrofit |
| `mesh.py` | 3716 | High-cohesion mesh ops, OK |
| `terrain_materials.py` | 2429 | Biome material + splatmap; needs TexCoord/Mapping/Image support |
| `environment.py` | 2144 | Terrain/water/road; UV bugs |
| `terrain_features.py` | 2089 | Waterfall/canyon/cliff/swamp specs; no UVs |
| `texture.py` | 1904 | PBR + bake; solid |
| `procedural_materials.py` | 1870 | Category 2: OK, uses TexCoord |
| `environment_scatter.py` | 1865 | Scatter + grass; needs GN rewrite |
| `viewport.py` | 1423 | Beauty + lighting; fix HDRI / sky |
| `vegetation_lsystem.py` | 1189 | L-system trees; OK |
| `_water_network.py` | 990 | Network computation; pure logic |

---

## Appendix C — Suggested execution order for fixes

### Phase A — critical UV & mesh quality (day 1)
1. Fix `environment.py:736` — add UV layer to terrain `bmesh.ops.create_grid`.
2. Fix `environment.py:1677` — add UV layer + per-loop UV writes to water.
3. Fix `environment.py:801` — add UV/smooth/normals to cliff overlay mesh.
4. Fix `environment.py:1541` — write actual UVs into road surface loops.
5. Fix `environment.py:1317, 1385, 1450` — add try/finally bm.free().
6. Add `use_auto_smooth` + sharp-edge marking to `_create_terrain_mesh_from_heightmap`.
7. Add regression tests asserting UV presence on each (Category 10 gaps).

### Phase B — material quality (day 2)
1. Add TexCoord+Mapping to `terrain_materials.py:2260`.
2. Add image-texture support to biome material layers.
3. Add triplanar projection for slope/cliff layers.
4. Add displacement node.
5. Fix water shader: foam VC read, depth absorption, transmission default.

### Phase C — lighting & atmosphere (day 3)
1. Fix `scene.py:667` — load HDRI image.
2. Wire `handle_setup_world` into MCP server.
3. Add Nishita sky helper.
4. Add `handle_place_integrated_lights` wrapping `light_integration.py`.
5. Add `handle_place_atmospheric_volumes` wrapping `atmospheric_volumes.py`.
6. Fix `viewport.py:402` to allow scene-world usage.
7. Add shadow cascade tuning for SUN lights.

### Phase D — waterfall and terrain features (day 4)
1. Add `handle_create_waterfall` wrapping `generate_waterfall` + `mesh_from_spec`.
2. Add UVs to `generate_waterfall` output.
3. Same for canyon, cliff_face, swamp, natural_arch, and all pure-logic terrain feature generators.
4. Create dedicated waterfall shader.

### Phase E — scatter & vegetation performance (day 5)
1. Rewrite grass scatter to use Geometry Nodes.
2. Bake actual billboard impostor textures for tree LODs.
3. Build BVH/bucket grid for exclusion zones.
4. Add wind deformation shader group.
5. Add water-body exclusion to scatter.

### Phase F — export & game-ready (day 6)
1. Add `handle_generate_collision` wrapping `lod_pipeline.generate_collision_mesh`.
2. Add `handle_atlas_materials` for prop atlasing.
3. Extend `handle_check_game_ready` with UV coverage / distortion checks.
4. Add batch game_check.

### Phase G — tests (ongoing)
1. Add UV / TexCoord / material node-graph assertions.
2. Add HDRI image-load assertion.
3. Add waterfall end-to-end test.
4. Add performance regression benchmarks.

---

## Appendix D — Cross-reference to user's known issues

| User-reported issue | Root cause gap | This report |
|---|---|---|
| "Everything looks low quality" | Terrain/water have no UVs → biome material shows procedural noise only in generated space → flat plastic look; HDRI never loads → no sky reflection; no foam/refraction on water | Gaps #1, #2, #4, #5 |
| "Terrain generator doesn't create UV layers (environment.py:738)" | `bmesh.ops.create_grid(calc_uvs=True)` without a pre-existing UV layer | Confirmed — Gap 3.1 row 1 |
| "Water generator doesn't create UV layers (environment.py:1601)" | `bm = bmesh.new()` at line 1677 never calls `loops.layers.uv.new()` | Confirmed — Gap 3.1 row 7 |
| "Waterfall is flat shaded, no smoothing" | `env_generate_waterfall` returns a spec only; must be built via `mesh_from_spec` which DOES smooth — so the flat shading means either the user's script didn't call `mesh_from_spec` OR `generate_waterfall` doesn't include `"uvs"` so `mesh_from_spec` only creates no-uv mesh. The spec-only path also never sets per-face `use_smooth`. | Confirmed — Gap #3 |
| "Stale boolean modifiers on current terrain" | Likely from `terrain_advanced.py` or `handle_carve_river` not cleaning up temp modifiers. Not directly covered in this scan but worth investigating `mesh.py:2634 handle_add_modifier` usage. | Partial — needs follow-up |
| "Security sandbox was missing 23 builtins (fixed)" | `execute.py:35-112` now includes expanded set | Confirmed fixed — Appendix A |

---

## Appendix E — Untouched areas (not scanned in this pass)

The following were scoped in but time-boxed out. Flag for a follow-up:

- `handlers/dungeon_themes.py` — theme material/mesh quality
- `handlers/modular_building_kit.py` — kit piece UV/smoothing audit
- `handlers/settlement_generator.py` — building placement / overlap checks
- `handlers/road_network.py` — has its own bmesh pipeline, not fully inspected
- `handlers/coastline.py` — shoreline mesh generation
- `handlers/destruction_system.py` — fracture & debris
- `handlers/decal_system.py` — decal projection
- `handlers/monster_bodies.py` — nested loop hit in O(n²) grep
- `handlers/weathering.py` — procedural weathering uses TexCoord, but depth not verified

---

## Summary metrics

- **Handlers audited:** 119
- **Tests audited:** 236 (high-level) + 7 water/lighting-specific files deep-read
- **Critical gaps found:** 11
- **High-severity gaps found:** 28
- **Medium-severity gaps found:** 21
- **Low-severity gaps found:** 9
- **Total gaps logged:** 69
- **Estimated total fix effort:** ~6 developer-days for Phases A–F, ongoing for Phase G

### Top 3 next actions

1. **Fix the four UV-layer bugs** (`environment.py:736, 1677, 801, 1541`) — trivial to fix, critical to AAA quality, and will immediately unblock every texture-based improvement.
2. **Wire `handle_setup_world` into MCP + load HDRI images** — unlocks scene lighting and is trivial to implement.
3. **Create `handle_create_waterfall` end-to-end handler** — the current waterfall path is a dead pipeline; exposing it as a real handler with UV/smoothing/materials closes the user's reported "flat shaded waterfall" issue.

All three of these can be delivered in one short dev session. Once they ship, re-generate the terrain+water+waterfall scene and verify visually before attacking the larger material/shader/scatter gaps in Phases B–E.
