# Cross-System Integration Bug Scan

**Date:** 2026-04-02
**Scope:** 7 major data flow boundaries traced end-to-end
**Files examined:** 20+ handler/server/template files

---

## 1. Terrain -> Settlement Placement Flow

### Data Flow Traced
- `environment.py::handle_generate_terrain` creates a Blender mesh with Z heights from heightmap
- `settlement_generator.py::generate_settlement` accepts `heightmap: Optional[Callable[[float, float], float]]`
- `blender_server.py::compose_map` Step 5 uses `_sample_terrain_height()` (raycast) to get `anchor_z`

### What Works
- `settlement_generator.py` has full terrain-awareness: `_sample_heightmap()`, `_compute_foundation_height()`, `_compute_foundation_profile()` all accept a heightmap callable
- `generate_concentric_districts()` (medieval_town) samples heightmap for each lot, computes foundation profiles
- `compose_map` Step 5 raycasts terrain for each location, flattens terrain under building footprints, computes foundation profiles from corner heights

### BUG 1: Foundation profile side_heights uses WRONG corner indices
**File:** `blender_server.py` lines 2893-2897
**Severity:** MEDIUM
```python
"side_heights": {
    "front": max(0.0, anchor_z - corner_heights[0]),   # corner[0] = (-radius, -radius)
    "back": max(0.0, anchor_z - corner_heights[2]),    # corner[2] = (-radius, +radius)
    "left": max(0.0, anchor_z - corner_heights[0]),    # BUG: same as front!
    "right": max(0.0, anchor_z - corner_heights[1]),   # corner[1] = (+radius, -radius)
},
```
The `left` side uses `corner_heights[0]` (front-left corner) which is the SAME as `front`. It should use a left-side sample. The corners sampled are: `[0]=(-r,-r)`, `[1]=(+r,-r)`, `[2]=(-r,+r)`, `[3]=(+r,+r)`, `[4]=(0,0)`. Correct mapping would be:
- front: average of [0] and [1] (both at -radius Y)
- back: average of [2] and [3] (both at +radius Y)
- left: average of [0] and [2] (both at -radius X)
- right: average of [1] and [3] (both at +radius X)

Currently left=front corner and right=front-right corner, which means on terrain sloping left-to-right, the left retaining wall gets the wrong height.

### BUG 2: worldbuilding_layout.py `generate_location_spec` ignores terrain entirely
**File:** `worldbuilding_layout.py` lines 965-1079
**Severity:** MEDIUM
Building positions are generated with only (x, y) coordinates -- no Z component, no terrain sampling, no heightmap parameter. All positions are placed on a flat plane. This is a pure-logic function so it's expected, but it means any consumer must apply terrain heights separately. The function generates `position: (x, y)` 2-tuples while the Blender wiring in compose_map expects to position objects at terrain height. This is handled by the compose_map pipeline via `_position_generated_object()`, so not a runtime bug, but the spec itself has no elevation data for downstream consumers who don't go through compose_map.

### BUG 3: `generate_concentric_districts` heightmap type mismatch
**File:** `settlement_generator.py` line 2154
**Severity:** LOW
`generate_concentric_districts()` accepts `heightmap: list[list[float]] | None` (2D grid), but its internal `_sample_heightmap()` (line 1479) accepts `Callable[[float, float], float] | None`. The function passes the `list[list[float]]` heightmap to `_sample_heightmap()` which expects a callable -- the list would be called as a function, raising `TypeError`. However, this path may not be exercised because compose_map passes heightmap through the blender_server's raycast mechanism instead.

**Wait -- re-checking:** `generate_concentric_districts` line 2180: `az = _sample_heightmap(heightmap, ax, ay)`. But `_sample_heightmap` at line 1479 does: `if heightmap is None: return 0.0; return heightmap(x, y)`. If `heightmap` is a `list[list[float]]`, calling `heightmap(ax, ay)` will raise `TypeError: 'list' object is not callable`.

**This IS a real bug** -- `generate_concentric_districts()` declares `heightmap: list[list[float]] | None` but the internal helper tries to call it as a function. Currently saved by callers always passing `None` for heightmap, but the type signature lies about what it accepts.

---

## 2. Settlement -> Interior Generation Flow

### Data Flow Traced
- `settlement_generator.py` generates buildings with `room_functions`, `footprint`, `position`, `floors`
- `building_interior_binding.py` provides `generate_interior_spec_from_building()` to create interior specs
- Interior specs should feed into `compose_interior` via blender_server

### BUG 4: building_interior_binding.py is NEVER imported or called
**File:** `building_interior_binding.py`
**Severity:** HIGH -- Dead integration code
The `building_interior_binding` module defines:
- `BUILDING_ROOM_MAP` -- maps building types to room specs
- `align_rooms_to_building()` -- constrains rooms to building footprint
- `generate_door_metadata()` -- creates door positions based on building walls
- `generate_interior_spec_from_building()` -- master integration function

**grep confirms: ZERO imports of this module outside test files.** The settlement_generator has its OWN parallel room system (`_BUILDING_ROOMS`, `ROOM_FURNISHINGS`). The two systems are completely disconnected:

| Property | settlement_generator | building_interior_binding |
|----------|---------------------|--------------------------|
| Room mapping | `_BUILDING_ROOMS` (simple string lists) | `BUILDING_ROOM_MAP` (dicts with floor, size_ratio) |
| Building types | 25+ types including Hearthvale | 14 types (missing Hearthvale types) |
| Multi-floor | Implicit via furnishing code | Explicit floor indices |
| Room sizing | Uses building footprint | Uses size_ratio per room |
| Door metadata | Not generated | Full door positions with scene links |

**Impact:** Interior generation uses `settlement_generator`'s simplistic room lists instead of the spatially-aware `building_interior_binding`. No door metadata is generated. No spatial alignment happens. Interior rooms don't match exterior dimensions through proper constraint solving.

### BUG 5: building_interior_binding room types don't match settlement_generator room types
**File:** Both files
**Severity:** MEDIUM (if binding were wired)
`building_interior_binding` uses room types like `tavern_hall`, `throne_room`, `guard_barracks`, `alchemy_lab`, `blacksmith`, `treasury`, `war_room`. Settlement generator uses `tavern`, `smithy`, `great_hall`, `shrine_room`, `barracks`, `guard_post`. These are DIFFERENT strings. Even if binding were connected, room type lookups would fail silently.

### BUG 6: building_interior_binding missing Hearthvale building types
**File:** `building_interior_binding.py` line 23
**Severity:** MEDIUM (if binding were wired)
`BUILDING_ROOM_MAP` has entries for: tavern, house, castle, cathedral, tower, shop, forge, ruin, gate, bridge, wall_section, dungeon_entrance, shrine. It is MISSING: blacksmith, temple, town_hall, general_store, apothecary, bakery, guard_barracks, manor, guild_hall -- all Hearthvale Phase 38 types. If called with these types, `get_room_types_for_building()` returns `[]`.

---

## 3. Terrain -> Vegetation Scatter Flow

### Data Flow Traced
- `environment.py::handle_generate_terrain` creates terrain mesh in Blender
- `environment_scatter.py::handle_scatter_vegetation` reads terrain geometry from Blender object
- `vegetation_system.py::compute_vegetation_placement` accepts terrain vertices/normals for slope/height filtering
- `_scatter_engine.py::poisson_disk_sample` generates candidate positions

### What Works Well
- `handle_scatter_vegetation` (environment_scatter.py) extracts fresh terrain geometry from Blender object
- Slope map is recomputed from current heightmap data
- Biome filter uses actual terrain data for height/slope filtering
- Building exclusion zones are computed from scene objects (lines 1289-1313)
- Road exclusion zones are also computed

### BUG 7: vegetation_system's `handle_scatter_biome_vegetation` uses LOCAL mesh coordinates, not WORLD coordinates
**File:** `vegetation_system.py` lines 693-709
**Severity:** HIGH
```python
terrain_vertices = [(v.co.x, v.co.y, v.co.z) for v in bm.verts]  # LOCAL space
# ...
dims = obj.dimensions
loc = obj.location
half_x = dims.x / 2.0
half_y = dims.y / 2.0
area_bounds = (loc.x - half_x, loc.y - half_y, loc.x + half_x, loc.y + half_y)
```
The `area_bounds` are computed in WORLD space (using `obj.location` and `obj.dimensions`) but `terrain_vertices` are in LOCAL space (using `v.co` not `obj.matrix_world @ v.co`). If the terrain object has a non-zero location, the grid lookup will be offset. `_sample_terrain` finds the nearest vertex by comparing world-space query positions against local-space vertex positions.

This means: if terrain is at (0,0,0), it works. If terrain is at (50, 50, 0), vegetation positions will be correct but height sampling will be wrong because the vertex grid index assumes vertices start at the bounds origin.

The `environment_scatter.py` handler does NOT have this bug -- it uses the heightmap array directly.

### BUG 8: Post-erosion vegetation does NOT re-sample
**File:** `vegetation_system.py` / `environment_scatter.py`
**Severity:** LOW -- by design
After `handle_generate_terrain` applies erosion, the heightmap is baked into the mesh vertices. When `handle_scatter_biome_vegetation` later reads terrain geometry via `bm.from_mesh(mesh)`, it gets the POST-erosion vertices. So vegetation DOES sample the eroded terrain -- but only if called after terrain generation. The data flow is temporal (dependent on call order) not structural (no direct link). The compose_map pipeline enforces correct order.

### BUG 9: vegetation_system exclusion zones are not implemented
**File:** `vegetation_system.py`
**Severity:** MEDIUM
Unlike `environment_scatter.py` which scans the scene for EMPTY objects and road meshes to build exclusion zones (lines 1289-1328), `vegetation_system.py::handle_scatter_biome_vegetation` has NO exclusion zone logic. It places vegetation everywhere including inside building footprints. The two scatter systems have different capabilities:

| Feature | environment_scatter.py | vegetation_system.py |
|---------|----------------------|---------------------|
| Building exclusion | YES (scene scan) | NO |
| Road exclusion | YES (mesh name scan) | NO |
| Slope filtering | YES (slope map) | YES (from normals) |
| Height filtering | YES (heightmap) | YES (from vertices) |
| Moisture filtering | YES | NO |

---

## 4. Map Composition Pipeline (compose_map)

### Data Flow Traced
`blender_server.py` compose_map action, lines 2636-3100+

### Pipeline Order (CORRECT)
1. **Clear scene** -- `clear_scene`
2. **Generate terrain** -- `env_generate_terrain` (creates mesh with heights)
3. **Water bodies** -- `env_carve_river` + `env_create_water` (modifies terrain mesh for rivers, creates water planes)
4. **Roads** -- `env_generate_road` (modifies terrain for road grading)
5. **Place locations** -- for each location: raycast terrain height, flatten terrain, generate building, position at terrain height
6. **Biome paint** -- `env_paint_terrain` + `terrain_create_biome_material` + lighting
7. **Vegetation scatter** -- `env_scatter_vegetation` with terrain name
8. **Prop scatter** -- `env_scatter_props` with building footprints
9. **Generate interiors** -- for buildings with interior specs

### What Works
- Step ordering is correct: terrain before water before roads before buildings before vegetation
- Each step uses the terrain object name to reference the same mesh
- Terrain is modified in-place (erosion, river carving, road grading, flattening) so later steps see accumulated changes
- Vegetation scatter (Step 7) reads from the already-modified terrain mesh
- Building anchors are raycasted from the current terrain state (post-flatten)
- Checkpoint system allows resume from any step

### BUG 10: compose_map Step 7 vegetation receives NO building exclusion data
**File:** `blender_server.py` lines 2971-2987
**Severity:** MEDIUM
```python
await blender.send_command("env_scatter_vegetation", {
    "terrain_name": terrain_name,
    "rules": veg_rules,
    "min_distance": veg_cfg.get("min_distance", 2.0),
    "seed": map_seed + 300,
    "max_instances": ...,
})
```
The vegetation scatter command does NOT pass building locations or exclusion zones. However, `handle_scatter_vegetation` in `environment_scatter.py` (lines 1289-1328) independently scans the Blender scene for EMPTY objects (building parents) and road meshes to build exclusion zones. So the exclusion actually works IF buildings are already in the scene (which they are, since Step 5 runs before Step 7). **This is a fragile coupling** -- it relies on implementation detail (scene scanning) rather than explicit data passing, but it works.

### BUG 11: compose_map Step 9 overwrites interior_results
**File:** `blender_server.py` line 3022
**Severity:** LOW
```python
interior_results = []  # Overwrites any checkpoint-loaded interior_results
```
Line 3022 reinitializes `interior_results = []` regardless of whether interiors were loaded from checkpoint. This means resumed pipelines always regenerate all interiors. The checkpoint guard `if "interiors_generated" not in steps_completed` partially mitigates this -- once interiors complete, the step marker prevents re-entry. But if the pipeline failed MID-interior-generation, the partial results from checkpoint are discarded.

### BUG 12: compose_map passes no heightmap to settlement generation
**File:** `blender_server.py` Step 5
**Severity:** LOW
The compose_map pipeline uses raycast-based terrain sampling (`_sample_terrain_height`) for positioning objects at terrain height. But the settlement_generator's `generate_settlement` function accepts a `heightmap` callable for internal building placement. The compose_map does NOT pass a heightmap callable to settlement generation -- buildings within a settlement are placed on a flat plane, then the entire settlement is positioned at anchor_z. This means on sloped terrain within a settlement radius, individual buildings don't adapt to local terrain variations. Only the compose_map-level flatten + position handles this.

---

## 5. LOD -> Export -> Unity Import Flow

### Data Flow Traced
- `lod_pipeline.py::handle_generate_lods` creates LOD objects with naming `{name}_LOD{level}`
- Export is via `export.py::handle_export_fbx` (standard Blender FBX export)
- Unity import uses `asset_templates.py` and `performance_templates.py`

### BUG 13: LOD export_dir parameter is accepted but NEVER used
**File:** `lod_pipeline.py` line 911
**Severity:** MEDIUM
The handler docstring says `export_dir (str, optional): Directory to export LOD FBX files` and the params dict is parsed, but **the code never reads `params.get("export_dir")`**. LOD meshes are only created as Blender objects -- they are never auto-exported. The user must manually call `handle_export_fbx` separately for each LOD object.

### BUG 14: LOD screen_percentages mismatch between Blender and Unity
**File:** `lod_pipeline.py` LOD_PRESETS vs `performance_templates.py` _DEFAULT_LOD_PERCENTAGES
**Severity:** MEDIUM
Blender LOD_PRESETS define per-asset-type screen percentages:
- `hero_character`: [1.0, 0.5, 0.25, 0.05]
- `building`: [1.0, 0.4, 0.15, 0.02]
- `vegetation`: [1.0, 0.3, 0.08, 0.02]

Unity LODGroup setup (`performance_templates.py`) uses a FLAT default: `[0.6, 0.3, 0.15]`.

The Blender-side screen percentages are NOT exported as metadata and are NOT consumed by the Unity LOD setup script. The Unity script uses its own defaults or user-provided values. This means Blender's carefully tuned per-asset-type LOD distances are silently discarded.

### BUG 15: Unity LOD naming convention expects child objects, Blender creates siblings
**File:** `performance_templates.py` line 301 vs `lod_pipeline.py` line 973
**Severity:** HIGH
Unity's `generate_lod_setup_script` looks for LOD meshes as **children** of the main object:
```csharp
var lodChild1 = go.transform.Find(go.name + "_LOD1");
```
This searches for a child named `{parent}_LOD1` under the parent object.

Blender's `handle_generate_lods` creates LOD meshes as **siblings** in the same collection:
```python
new_obj = bpy.data.objects.new(lod_name, new_mesh)
bpy.context.collection.objects.link(new_obj)  # Sibling, not child
```

When exported to FBX, these will be sibling GameObjects, not parent-child. The Unity LOD script uses `transform.Find()` which only searches direct children. **LOD1+ meshes will never be found by the Unity auto-setup.**

Additionally, the asset_templates.py import pipeline (line 1960) uses string matching `rName.Contains("_LOD" + i)` on renderer names, which WOULD match siblings. But the performance_templates.py LOD setup uses `transform.Find()` which won't. Two different Unity systems with incompatible LOD discovery.

---

## 6. Blender Server <-> Blender Addon Communication

### Data Flow Traced
- `blender_client.py::BlenderConnection` -- TCP client (MCP server side)
- `socket_server.py::BlenderMCPServer` -- TCP server (Blender addon side)
- Length-prefixed framing: 4-byte big-endian length + JSON payload

### What Works Well
- Persistent connections with auto-reconnect on failure
- Length-prefixed framing prevents message boundary issues
- Thread-safe with `_send_lock` mutex
- Command queue with `threading.Event` for response synchronization
- 64 MB max message size on both sides (matched)
- TCP_NODELAY for low latency

### BUG 16: Single-command-per-tick processing blocks long pipelines
**File:** `socket_server.py` line 172
**Severity:** LOW-MEDIUM
```python
# Process one command per tick to avoid freezing Blender UI
try:
    cmd, event, container = self.command_queue.get_nowait()
except queue.Empty:
    return 0.01
```
Only ONE command is dequeued per 10ms timer tick. The compose_map pipeline sends 20+ sequential commands. Each command must wait for the previous to complete (async send_command waits for response). But if multiple clients send commands concurrently, they queue up and execute at 100 commands/second maximum. This is adequate for single-client use.

### BUG 17: 30-second idle timeout on persistent connections
**File:** `socket_server.py` line 93
**Severity:** MEDIUM
```python
client_sock.settimeout(30.0)
```
The client socket has a 30-second idle timeout between commands. But the MCP server's `BlenderConnection` has a 300-second timeout. If the MCP server is waiting for a long operation and doesn't send the next command within 30 seconds, the Blender server will close the connection. The client will then reconnect on the next command, which works, but:
1. The persistent connection benefit is lost
2. If Blender is executing a 30+ second operation (erosion, large terrain generation), and the MCP client sends the NEXT command before the first completes, the queue will hold it. But the CLIENT socket that's waiting for the first command's response has a 300s timeout on its side, while a DIFFERENT client connection in the server thread has a 30s idle timeout. These are different sockets so there's no conflict here.

Actually, re-analyzing: Each client connection runs in its own thread. The 30s timeout applies to `_receive_exactly` calls in `_handle_client`. After sending a response, the loop waits for the NEXT command from the same socket. If the client takes >30s between commands (e.g., processing results), the server drops the connection. The client reconnects transparently. **Not a bug, just a design choice that causes unnecessary reconnections during slow pipelines.**

### Responses are correctly matched to requests
The protocol is synchronous per-connection: client sends command, waits for response, then sends next command. There's no request ID or multiplexing. Responses can't get mixed up because there's only ever one outstanding request per socket.

### No truncation risk (within limits)
Messages up to 64 MB are supported. JSON responses from handlers are typically < 1 MB. Viewport screenshots are returned as file paths, not inline data. The only large payload risk is `execute_code` results with extensive print output, which would need to exceed 64 MB to truncate.

---

## 7. Material System -> Unity Shader Mapping

### Data Flow Traced
- `terrain_materials.py` defines `TERRAIN_MATERIALS` with PBR properties (base_color, roughness, metallic, normal_strength)
- `procedural_materials.py` has `MATERIAL_LIBRARY` with same property format
- Blender materials use node-based shading (Principled BSDF)
- Unity shader generation via `unity_tools/shader.py` creates arbitrary HLSL/ShaderLab
- No automatic Blender-to-Unity material conversion pipeline

### BUG 18: No automated material property transfer from Blender to Unity
**File:** Systemic gap across terrain_materials.py, unity_tools/shader.py
**Severity:** HIGH -- Fundamental integration gap
There is NO system that:
1. Reads Blender material properties (base_color, roughness, metallic, normal_strength)
2. Maps them to Unity shader properties
3. Generates Unity materials with matched values

The terrain_materials.py defines palettes like:
```python
"dark_leaf_litter": {
    "base_color": (0.07, 0.06, 0.04, 1.0),
    "roughness": 0.92,
    "metallic": 0.0,
    "normal_strength": 0.6,
}
```

But the Unity shader tool (`unity_shader`) generates empty shader templates that require manual property assignment. There's no pipeline that says "this Blender material should become this Unity material with these property values."

**FBX export preserves:** mesh geometry, UV coordinates, vertex colors, bone weights. It does NOT reliably preserve: Blender node-based materials, procedural textures, roughness maps. Standard FBX workflow exports textures as separate files that Unity reimports, but VeilBreakers' procedural Blender materials have no texture files to export.

### BUG 19: Color space mismatch between Blender and Unity
**File:** `terrain_materials.py`, Unity templates
**Severity:** MEDIUM
Blender material colors are in LINEAR space (as stored in the BSDF node). Unity expects sRGB for albedo/base color and linear for metallic/roughness. The terrain_materials colors like `(0.07, 0.06, 0.04, 1.0)` are LINEAR values. If manually transferred to Unity without gamma correction, they'll appear darker than intended. No conversion utility exists.

### BUG 20: Biome palette names don't map to any Unity terrain layer system
**File:** `terrain_materials.py` BIOME_PALETTES, Unity terrain tools
**Severity:** MEDIUM
Blender biome palettes define terrain zone materials ("ground", "slopes", "cliffs", "water_edges") with specific material names. Unity Terrain uses TerrainLayers with diffuse/normal textures. There's no mapping between Blender's procedural biome materials and Unity's texture-based terrain layers. The `export_heightmap` function exports the raw heightmap for Unity Terrain import, but material/splatmap data is not exported.

---

## Summary of All Bugs Found

### CRITICAL (breaks functionality)
| # | Bug | File | Impact |
|---|-----|------|--------|
| 4 | building_interior_binding.py NEVER imported/called | building_interior_binding.py | Dead code -- spatial room alignment, door metadata generation never executes |
| 15 | Unity LOD expects children, Blender creates siblings | lod_pipeline.py / performance_templates.py | LOD auto-setup fails -- LOD1+ meshes never discovered |
| 18 | No material property transfer Blender -> Unity | Systemic | PBR values lost on export, Unity materials are blank |

### HIGH (incorrect behavior)
| # | Bug | File | Impact |
|---|-----|------|--------|
| 1 | Foundation side_heights wrong corner indices | blender_server.py:2893 | Left retaining wall gets wrong height on sloped terrain |
| 3 | heightmap type mismatch in generate_concentric_districts | settlement_generator.py:2154 | Would crash if heightmap grid passed (currently always None) |
| 7 | vegetation_system uses local coords vs world bounds | vegetation_system.py:693 | Wrong height sampling if terrain not at origin |

### MEDIUM (degraded quality or silent data loss)
| # | Bug | File | Impact |
|---|-----|------|--------|
| 5 | Room type names don't match between systems | Both interior systems | Room lookups would fail if binding were connected |
| 6 | Missing Hearthvale types in building_interior_binding | building_interior_binding.py | No interior specs for 9+ building types |
| 9 | vegetation_system has no exclusion zones | vegetation_system.py | Vegetation placed inside buildings |
| 10 | compose_map vegetation gets no explicit exclusion data | blender_server.py:2971 | Works via scene scan but fragile coupling |
| 11 | interior_results overwritten on checkpoint resume | blender_server.py:3022 | Partial interior results lost on resume |
| 13 | LOD export_dir parameter accepted but never used | lod_pipeline.py:911 | API lies about auto-export capability |
| 14 | LOD screen percentages not transferred to Unity | Both LOD systems | Per-asset-type LOD distances silently discarded |
| 17 | 30s idle timeout vs 300s client timeout | socket_server.py:93 | Unnecessary reconnections during slow ops |
| 19 | Linear/sRGB color space mismatch | terrain_materials.py | Colors appear darker in Unity |
| 20 | Biome palettes don't map to Unity terrain layers | terrain_materials.py | Terrain materials lost on export |

### LOW (minor or edge-case)
| # | Bug | File | Impact |
|---|-----|------|--------|
| 2 | generate_location_spec ignores terrain Z | worldbuilding_layout.py:965 | By design, handled by compose_map positioning |
| 8 | Post-erosion vegetation re-sampling | vegetation_system.py | Works correctly via temporal ordering |
| 12 | compose_map passes no heightmap to settlement gen | blender_server.py | Individual buildings don't adapt within settlement |
| 16 | Single-command-per-tick processing | socket_server.py:172 | Adequate for single-client, limits throughput |
