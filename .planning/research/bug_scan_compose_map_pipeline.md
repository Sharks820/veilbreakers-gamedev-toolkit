# Deep Bug Scan: compose_map Pipeline

**Scanned:** 2026-04-02
**Files traced:** `blender_server.py` (lines 2685-3143), `map_composer.py`, `pipeline_state.py`
**Known bugs excluded:** bpy import crash, interior_results reset, scatter ValueError on no locations, silent game_check failure, silent FBX export failure

---

## NEW Bugs Found

### BUG-CM-01: Water/River steps have NO checkpoint resume skip logic (SEVERITY: HIGH)

**Location:** `blender_server.py` lines 2800-2841

The water step (Step 3) has no `steps_completed` check to skip already-completed rivers or water plane on resume. Compare with Step 4 (Roads) which has:
```python
_completed_roads = {s for s in steps_completed if s.startswith("road_")}
for i, road in enumerate(spec.get("roads", [])):
    if f"road_{i}" in _completed_roads:
        continue
```

But Step 3 (Water) does:
```python
water_cfg = spec.get("water", {})
if water_cfg:
    for i, river in enumerate(water_cfg.get("rivers", [])):
        # NO skip check for f"river_{i}" in steps_completed!
```

Similarly, the water plane creation has no skip check for `"water_plane"` in `steps_completed`.

**Impact:** On checkpoint resume, ALL rivers get re-carved and the water plane gets recreated, potentially duplicating geometry or causing errors if terrain was already modified.

---

### BUG-CM-02: Foundation profile `side_heights` uses wrong corner indices for "left" (SEVERITY: MEDIUM)

**Location:** `blender_server.py` lines 2940-2957

The corner sampling order is:
```python
for dx, dy in [(-loc_radius, -loc_radius),   # index 0: SW corner
               (loc_radius, -loc_radius),     # index 1: SE corner
               (-loc_radius, loc_radius),     # index 2: NW corner
               (loc_radius, loc_radius),      # index 3: NE corner
               (0.0, 0.0)]:                   # index 4: center
```

But `side_heights` and `retaining_sides` use:
```python
"side_heights": {
    "front": max(0.0, anchor_z - corner_heights[0]),  # SW -- ok-ish
    "back": max(0.0, anchor_z - corner_heights[2]),    # NW -- ok-ish
    "left": max(0.0, anchor_z - corner_heights[0]),    # SW -- WRONG, should be index 2 (NW) or average of 0+2
    "right": max(0.0, anchor_z - corner_heights[1]),   # SE -- ok-ish
},
```

"left" reuses index 0 (same as "front"), so the left side height is always identical to the front side height. The `retaining_sides` list has the same bug: `("left", corner_heights[0])` duplicates the front corner.

**Impact:** Foundation profiles on sloped terrain will have incorrect left-side wall heights. Buildings on terrain sloping left-to-right will get wrong retaining walls.

---

### BUG-CM-03: `atmosphere` spec field is silently ignored (SEVERITY: LOW)

**Location:** `blender_server.py` -- the compose_map handler

The example spec shows `"atmosphere": "foggy"` as a valid field (line 2706), but no step in the pipeline reads `spec.get("atmosphere")`. The biome step applies lighting based on biome name but never reads the atmosphere field.

**Impact:** Users who set `atmosphere: "foggy"` or `atmosphere: "stormy"` get no atmosphere setup. The field is documented in the example but never consumed.

---

### BUG-CM-04: Biome paint step always runs even on checkpoint resume (SEVERITY: MEDIUM)

**Location:** `blender_server.py` lines 2991-3017

Step 6 (Biome paint) checks `if biome:` but does NOT check if `"biome_painted"` is already in `steps_completed`:
```python
biome = spec.get("biome")
if biome:
    try:
        await blender.send_command("env_paint_terrain", {...})
        # ...
```

Compare with terrain (Step 2) which properly checks:
```python
if "terrain_generated" not in steps_completed:
```

**Impact:** On resume, biome painting and lighting setup re-execute unnecessarily. Could overwrite manual adjustments the user made between checkpoints.

---

### BUG-CM-05: Vegetation and prop scatter steps have no checkpoint resume skip (SEVERITY: MEDIUM)

**Location:** `blender_server.py` lines 3019-3068

Step 7 (Vegetation) checks `if veg_cfg:` but never checks `"vegetation_scattered" in steps_completed`. Step 8 (Props) checks `if spec.get("props", True):` but never checks `"props_scattered" in steps_completed`.

**Impact:** On resume, vegetation and props are re-scattered on top of existing instances, causing double-density vegetation and duplicate props.

---

### BUG-CM-06: `interior_results` is unconditionally reset to empty list before interior generation (SEVERITY: HIGH -- ALREADY KNOWN but this is a DIFFERENT manifestation)

**Location:** `blender_server.py` line 3071

```python
interior_results = []  # <-- unconditional reset
if "interiors_generated" not in steps_completed:
```

While the known bug is about interior_results being reset, the checkpoint-specific impact is: even when checkpoint data loaded `interior_results` from disk (line 2750), line 3071 unconditionally wipes it. So on a resume where interiors were already generated (`"interiors_generated" in steps_completed`), the interior_results list is still empty in the final output.

Note: This is listed as "known" but this checkpoint-resume interaction is a distinct manifestation -- the checkpoint loads interior_results from disk, then line 3071 destroys them even when the if-block is skipped.

---

### BUG-CM-07: `_map_point_to_terrain_cell` returns (row, col) but `env_carve_river` receives it as [source, destination] coordinates (SEVERITY: HIGH)

**Location:** `blender_server.py` lines 2806-2815

`_map_point_to_terrain_cell` returns `(row, col)` -- grid cell indices in row-major order (Y-first):
```python
def _map_point_to_terrain_cell(...) -> tuple[int, int]:
    row = int(round(((y + half) / ...) * (side - 1)))
    col = int(round(((x + half) / ...) * (side - 1)))
    return (row, col)  # Y-axis first, X-axis second
```

But the compose_map handler passes this directly to `env_carve_river` as `source` and `destination`:
```python
source = _map_point_to_terrain_cell(river.get("source", [10, 10]), ...)
destination = _map_point_to_terrain_cell(river.get("destination", [190, 190]), ...)
await blender.send_command("env_carve_river", {
    "source": list(source),       # passes [row, col] = [y, x]
    "destination": list(destination),
})
```

If `env_carve_river` expects `[x, y]` coordinates (which is the standard convention), the river will be carved with X and Y swapped. The river's path would be mirrored diagonally.

**Impact:** All rivers are carved along transposed coordinates (X and Y swapped), appearing at 90-degree rotated positions from what the user specified.

---

### BUG-CM-08: Road waypoints also go through `_map_point_to_terrain_cell` with same (row, col) swap (SEVERITY: HIGH)

**Location:** `blender_server.py` lines 2849-2866

Same issue as BUG-CM-07 but for roads:
```python
waypoints = [
    list(_map_point_to_terrain_cell(waypoint, ...))
    for waypoint in road.get("waypoints", [])
]
await blender.send_command("env_generate_road", {
    "waypoints": waypoints,  # [row, col] pairs passed as [x, y]
})
```

**Impact:** Roads are generated along X/Y-swapped paths, misaligned with user-specified waypoints.

---

### BUG-CM-09: `env_generate_terrain` receives `scale` but `generate_terrain_mesh` sends `size` (SEVERITY: LOW)

**Location:** `blender_server.py` lines 2782-2793 vs lines 2665-2673

The `compose_map` step sends:
```python
await blender.send_command("env_generate_terrain", {
    "scale": terrain_size,  # uses "scale" key
    ...
})
```

But the `generate_terrain_mesh` action sends:
```python
await blender.send_command("env_generate_terrain", {
    "size": terrain_size,  # uses "size" key
    ...
})
```

One of these is wrong, or the handler accepts both. If the Blender handler only accepts `size`, then compose_map's terrain is generated at default size regardless of spec.

**Impact:** If the terrain handler doesn't recognize `scale`, the terrain size setting from the map spec is silently ignored.

---

### BUG-CM-10: `terrain_name` is always truthy -- heightmap export guard is meaningless (SEVERITY: TRIVIAL)

**Location:** `blender_server.py` line 3097

```python
if terrain_name:  # terrain_name = f"{map_name}_Terrain" -- always truthy
```

This guard never prevents execution. If terrain generation failed (Step 2), the heightmap export will attempt to export a non-existent terrain, causing an error that gets silently caught. Not a real bug since the error is caught, but the guard creates a false sense of safety.

---

### BUG-CM-11: Heightmap export uses hardcoded `/tmp/` path on Windows (SEVERITY: MEDIUM)

**Location:** `blender_server.py` lines 3098-3099

```python
_hm_dir = checkpoint_dir or "/tmp/veilbreakers_exports"
```

On Windows (the target platform per env info), `/tmp/` does not exist. When no `checkpoint_dir` is provided, `os.makedirs("/tmp/veilbreakers_exports", exist_ok=True)` will create `C:\tmp\veilbreakers_exports` (relative to current drive root), which is non-standard and may fail if the drive root is write-protected.

**Impact:** On Windows without a checkpoint_dir, heightmap export writes to a non-standard location or fails.

---

### BUG-CM-12: `_normalize_map_point` has a flawed heuristic that mishandles mid-range coordinates (SEVERITY: MEDIUM)

**Location:** `blender_server.py` lines 159-175

```python
threshold = terrain_size * 0.6
if 0.0 <= x <= terrain_size and 0.0 <= y <= terrain_size and (x > threshold or y > threshold):
    return (x - half, y - half)
return (x, y)
```

For a terrain_size=200: threshold=120.

- Input `(60, 60)`: Both < 120, no shift. Returns `(60, 60)`. Correct if already centered.
- Input `(60, 130)`: y > 120, so BOTH get shifted. Returns `(-40, 30)`. But what if only Y was in 0..size space and X was already centered? The heuristic can't distinguish.
- Input `(-10, -10)`: Outside `[0, size]` range, no shift. Correct for centered space.
- Input `(0, 0)`: Both in range but both < threshold, no shift. Returns `(0, 0)`. But if the user intended 0..size space (top-left corner), this should become `(-100, -100)`.

**Impact:** Points near the origin in 0..size coordinate space (like `(0, 0)`, `(50, 50)`) are never shifted to centered coordinates, causing locations/roads/rivers to be placed at wrong positions.

---

### BUG-CM-13: Quality check runs on ALL created_objects including Water plane and Terrain (SEVERITY: LOW)

**Location:** `blender_server.py` lines 3116-3120

```python
quality_report = await _enforce_world_quality(
    blender,
    object_names=created_objects,  # includes "{map_name}_Water" and "{map_name}_Terrain"
    ...
)
```

But `_should_validate_world_mesh` skips objects with "Terrain" in the name (line 445):
```python
if "_LOD" in name or "Terrain" in name:
    return False
```

The Water plane passes through and gets UV-unwrapped, PBR-textured, and LOD-generated -- unnecessary for a flat water plane that should use a water shader.

**Impact:** Water plane gets unnecessary quality remediation (PBR textures, UV unwrap, LOD generation), wasting time and potentially breaking the water material.

---

### BUG-CM-14: No memory cleanup between expensive steps (SEVERITY: MEDIUM)

**Location:** The entire compose_map handler (lines 2685-3143)

The pipeline generates terrain, carves rivers, places multiple locations (each potentially generating thousands of polygons), scatters vegetation (up to 8000 instances), scatters props, generates interiors, and then runs quality validation on everything. There is zero memory cleanup or Blender garbage collection between steps.

For a max-spec map (cinematic quality, 8+ locations, 8000 vegetation instances), this can exhaust Blender's memory before reaching the quality check step.

No `bpy.ops.outliner.orphans_purge()` or equivalent cleanup call exists anywhere in the pipeline.

**Impact:** Large maps can cause Blender to run out of memory or become extremely slow in later pipeline steps.

---

### BUG-CM-15: Two concurrent compose_map calls will corrupt each other's checkpoint files (SEVERITY: MEDIUM)

**Location:** `pipeline_state.py` save/load functions

The checkpoint file path is derived from `map_name`:
```python
safe_name = map_name.replace(" ", "_").replace("/", "_")
path = os.path.join(checkpoint_dir, f"{safe_name}_checkpoint.json")
```

If two compose_map calls use the same map_name and checkpoint_dir simultaneously, they will read/write the same checkpoint file with interleaved state, corrupting progress tracking.

Additionally, the MCP server is async and nothing prevents a second compose_map call from starting while the first is still running. There is no lock, mutex, or "pipeline in progress" check.

**Impact:** Concurrent calls with the same map name corrupt checkpoint state. Even with different names, they share the same Blender scene and will have conflicting objects.

---

### BUG-CM-16: `_save_chkpt` closure captures mutable lists by reference but checkpoint validation only checks seed + location count (SEVERITY: LOW)

**Location:** `pipeline_state.py` lines 126-158

`validate_checkpoint_compatibility` only checks:
1. Seed matches
2. Location count matches

It does NOT check:
- Terrain size changed
- Terrain preset changed
- Water configuration changed
- Road configuration changed
- Biome changed

So if a user resumes with the same seed and same number of locations but changes the terrain from "mountains" to "plains" or changes the terrain size from 200 to 400, the checkpoint is considered "compatible" and the pipeline resumes with the old terrain but new parameters for subsequent steps.

**Impact:** Resuming with changed terrain/water/road params silently produces a map with mismatched configuration between early and late pipeline steps.

---

### BUG-CM-17: Location placement step tracks `location_placed_` AND `location_mesh_` but resume only checks `location_mesh_` (SEVERITY: LOW)

**Location:** `blender_server.py` lines 2873, 2968, 2975

The skip check uses:
```python
_completed_locs = {s.replace("location_mesh_", "") for s in steps_completed if s.startswith("location_mesh_")}
```

But after successful placement, TWO entries are added:
```python
steps_completed.append(f"location_placed_{loc.get('name', i)}")  # line 2968
steps_completed.append(f"location_mesh_{loc.get('name', i)}")    # line 2975
```

On resume, a location whose mesh was generated but positioning failed gets the `location_mesh_` entry (line 2975 runs even if positioning fails) and will be skipped. But its position was never set. The location sits at origin (0,0,0) instead of its terrain anchor.

**Impact:** On checkpoint resume, locations that failed positioning the first time will never be re-positioned -- they remain at origin.

---

### BUG-CM-18: `loc.get('name', i)` mixes string and int in step tracking keys (SEVERITY: LOW)

**Location:** `blender_server.py` lines 2968, 2975, 2987

When a location has no `name` field, the fallback is the loop index `i` (an integer):
```python
steps_completed.append(f"location_mesh_{loc.get('name', i)}")
```

This creates keys like `"location_mesh_0"`, `"location_mesh_1"`. But the skip check:
```python
_completed_locs = {s.replace("location_mesh_", "") for s in steps_completed if s.startswith("location_mesh_")}
```

Creates a set containing `"0"`, `"1"` (strings). Then:
```python
if loc_name in _completed_locs:  # loc_name = loc.get("name", str(i))
```

Wait -- `loc_name` is `loc.get("name", str(i))` at line 2885. So it's `str(i)`. And the set has `str(i)` from f-string formatting of `int(i)`. These match. **Not actually a bug** -- f-string coerces int to str, and `str(i)` matches. Withdrawing this one.

---

### BUG-CM-19: `env_generate_terrain` param mismatch: compose_map sends `name` but generate_terrain_mesh does not (SEVERITY: LOW)

**Location:** `blender_server.py` lines 2783, 2665

compose_map sends:
```python
await blender.send_command("env_generate_terrain", {
    "name": terrain_name,  # explicit name
    ...
})
```

But `generate_terrain_mesh` sends:
```python
await blender.send_command("env_generate_terrain", {
    # no "name" param
    "terrain_type": preset,
    ...
})
```

If the Blender handler uses a default name when none is provided, the terrain object won't be named `{map_name}_Terrain` and all subsequent steps referencing `terrain_name` will fail to find the object.

Actually this is about compose_map sending both `name` AND `terrain_type` but `generate_terrain_mesh` only sending `terrain_type`. compose_map appears correct since it provides a name. The inconsistency is in `generate_terrain_mesh` which might create a differently-named object. Not a compose_map bug per se.

---

### BUG-CM-20: Prop scatter step raises ValueError when no locations exist, but this is caught silently (SEVERITY: ALREADY KNOWN -- skipping)

---

### BUG-CM-21: `_enforce_world_quality` deletes keys from report dict then pipeline references them (SEVERITY: LOW)

**Location:** `blender_server.py` lines 841-844 and line 3123

`_enforce_world_quality` does:
```python
del report["mesh_targets"]
del report["uv_fixed"]
del report["materials_fixed"]
del report["lod_generated"]
```

These are replaced with `_count` and `_sample` variants. The final compose_map result includes `quality_report` which is this modified dict. Not actually a bug -- the report dict is consumed correctly with the sample/count keys. No code downstream reads the deleted keys.

---

### BUG-CM-22: `_with_screenshot` returns a list but compose_map builds `result` dict -- type confusion for callers (SEVERITY: LOW)

**Location:** `blender_server.py` line 3143

```python
return await _with_screenshot(blender, result, capture_viewport)
```

`_with_screenshot` returns `list` (JSON string + optional Image). The caller of the MCP tool receives a list, not a dict. This is consistent with other tools, but compose_map's `result` dict with `next_steps`, `quality_report`, etc. is serialized to JSON string inside the list. Any programmatic consumer parsing the response needs to know to JSON-parse the first element. This is by design for MCP tools, not a bug.

---

### BUG-CM-23: Minimum spec (terrain only, no locations/water/roads) hits prop scatter ValueError (SEVERITY: ALREADY KNOWN -- skipping)

---

### BUG-CM-24: `_plan_map_location_anchors` ignores terrain heightmap for placement (SEVERITY: MEDIUM)

**Location:** `blender_server.py` lines 195-278

`_plan_map_location_anchors` is a pure-Python function that runs BEFORE any Blender commands. It places locations using concentric ring geometry only. It does not consider:
- Actual terrain elevation (terrain hasn't been generated yet when this runs)
- Water body positions (a location could be placed under a river/lake)
- Road positions (no road-awareness for settlement placement)

The function places locations based on geometric ring patterns and collision avoidance, but a town could easily end up in the middle of a lake or river.

**Impact:** Locations can be placed at positions that conflict with water bodies or roads specified in the same map_spec. A town could be partially submerged.

---

### BUG-CM-25: `terrain_spline_deform` flatten runs BEFORE checking if terrain generation succeeded (SEVERITY: LOW)

**Location:** `blender_server.py` lines 2917-2932

The terrain flattening step runs inside the location loop:
```python
if terrain_name:  # always truthy (string literal)
    # ... sample heights, flatten terrain ...
```

If Step 2 (terrain generation) failed and was added to `steps_failed`, the terrain object doesn't exist in Blender. But `terrain_name` is always truthy (it's a formatted string), so the code tries to sample heights and flatten a non-existent terrain. The `_sample_terrain_height` function returns 0.0 on failure (silent), and `terrain_spline_deform` failure is caught by `except Exception: pass`.

**Impact:** When terrain generation fails, every subsequent location placement does 5 unnecessary raycast calls that return 0.0, creates a foundation profile with all-zero heights, and silently fails the flatten step. Wastes time but doesn't crash.

---

### BUG-CM-26: Checkpoint `params_snapshot` only stores `terrain_size` and `seed` -- insufficient for validation (SEVERITY: LOW)

**Location:** `blender_server.py` lines 2760-2769

```python
"params_snapshot": {"terrain_size": terrain_size, "seed": map_seed},
```

The checkpoint stores only terrain_size and seed, but `validate_checkpoint_compatibility` (pipeline_state.py) doesn't even read `params_snapshot` -- it checks `seed` and `location_count` from the top-level checkpoint keys. The `params_snapshot` is written but never consumed by any validation logic.

**Impact:** Dead data. The snapshot exists but is never used for validation, contributing to BUG-CM-16's weak validation.

---

### BUG-CM-27: `_enforce_world_quality` generates LODs for ALL mesh targets unconditionally (SEVERITY: MEDIUM)

**Location:** `blender_server.py` lines 807-811

```python
await blender.send_command(
    "pipeline_generate_lods",
    {"object_name": mesh_name, "ratios": lod_ratios or [0.6, 0.3, 0.12]},
)
report["lod_generated"].append(mesh_name)
```

LOD generation runs for EVERY validated mesh, even if:
1. The mesh already has LODs (from a previous run or manual setup)
2. The mesh is very small (< 100 polys) and LODs are wasteful
3. LOD generation fails -- the failure is NOT caught separately from the outer try/except

If LOD generation throws an exception, the entire quality check for that mesh is marked as failed, even though the mesh might otherwise be game-ready.

**Impact:** Unnecessary LOD generation for small meshes; LOD failures cascade to mark otherwise-valid meshes as failed.

---

### BUG-CM-28: `scale_range` in vegetation rules is a tuple but JSON serialization converts it to list (SEVERITY: LOW)

**Location:** `blender_server.py` lines 458-674

The default vegetation rules use tuples:
```python
"scale_range": (0.6, 1.2),
```

But when these are sent to Blender via `send_command`, they go through JSON serialization which converts tuples to lists. If the Blender handler expects tuples specifically, this would fail. More importantly, the user-provided rules via `_normalize_vegetation_rules` explicitly convert to tuple:
```python
"scale_range": tuple(entry.get("scale_range", (0.6, 1.2))),
```

But `tuple()` on a JSON-parsed input (already a list) creates a tuple, which then gets serialized back to a list when sent to Blender. Inconsistent but only a real bug if the handler is type-sensitive.

**Impact:** Minimal -- JSON roundtrip normalizes everything to lists anyway.

---

## Summary of NEW Bugs

| ID | Severity | Description |
|----|----------|-------------|
| CM-01 | HIGH | Water/river steps have no checkpoint resume skip logic |
| CM-02 | MEDIUM | Foundation profile `side_heights` uses wrong corner index for "left" |
| CM-03 | LOW | `atmosphere` spec field is silently ignored |
| CM-04 | MEDIUM | Biome paint step always runs on checkpoint resume |
| CM-05 | MEDIUM | Vegetation and prop scatter have no checkpoint resume skip |
| CM-07 | HIGH | `_map_point_to_terrain_cell` returns (row,col) but river/road handlers expect (x,y) -- coordinates are swapped |
| CM-08 | HIGH | Roads have the same row/col swap as rivers |
| CM-09 | LOW | compose_map sends `scale` param but generate_terrain_mesh sends `size` -- possible mismatch |
| CM-11 | MEDIUM | Heightmap export uses `/tmp/` hardcoded path, fails on Windows |
| CM-12 | MEDIUM | `_normalize_map_point` heuristic mishandles coordinates near origin |
| CM-14 | MEDIUM | No memory cleanup between expensive pipeline steps |
| CM-15 | MEDIUM | Concurrent compose_map calls corrupt shared checkpoint and scene state |
| CM-16 | LOW | Checkpoint validation only checks seed + location count, ignores terrain/water/road changes |
| CM-17 | LOW | Location mesh skip on resume skips repositioning for locations that failed placement |
| CM-24 | MEDIUM | Location anchor placement ignores water/road positions -- locations can be placed under water |
| CM-25 | LOW | Terrain flatten attempts run even when terrain generation failed |
| CM-26 | LOW | Checkpoint `params_snapshot` is written but never read |
| CM-27 | MEDIUM | LOD generation runs unconditionally; failures cascade to mark valid meshes as failed |
| CM-13 | LOW | Water plane gets unnecessary quality remediation (PBR, UV, LOD) |

**Total NEW bugs: 19** (3 HIGH, 8 MEDIUM, 8 LOW)

---

## Pipeline Flow Diagram with Bug Locations

```
compose_map(map_spec)
  |
  v
[1] Clear scene .................. (checkpoint-aware: OK)
  |
  v
[2] Generate terrain ............. (checkpoint-aware: OK)
  |                                 BUG-CM-09: "scale" vs "size" param name
  |                                 BUG-CM-25: terrain_name always truthy guard
  v
[3] Water bodies ................. BUG-CM-01: NO checkpoint resume skip
  |   Rivers ..................... BUG-CM-07: row/col coordinate swap
  |   Water plane ................ BUG-CM-01: NO checkpoint resume skip
  v
[4] Roads ........................ (checkpoint-aware: OK)
  |                                 BUG-CM-08: row/col coordinate swap
  v
[5] Place locations .............. (checkpoint-aware: OK)
  |   Anchor planning ........... BUG-CM-24: ignores water/road positions
  |   Foundation profile ......... BUG-CM-02: wrong "left" corner index
  |   Positioning ................ BUG-CM-17: skipped on resume if mesh exists
  |   Coordinate normalization ... BUG-CM-12: origin-area heuristic failure
  v
[6] Biome paint .................. BUG-CM-04: NO checkpoint resume skip
  |                                 BUG-CM-03: atmosphere field ignored
  v
[7] Vegetation scatter ........... BUG-CM-05: NO checkpoint resume skip
  v
[8] Prop scatter ................. BUG-CM-05: NO checkpoint resume skip
  v
[9] Interior generation .......... (interior_results reset: KNOWN)
  v
[10] Heightmap export ............ BUG-CM-11: /tmp/ hardcoded path
  v
[11] Quality check ............... BUG-CM-13: water plane gets remediated
  |                                 BUG-CM-27: unconditional LOD + cascade failure
  v
[RETURN] ......................... BUG-CM-14: no memory cleanup anywhere
                                   BUG-CM-15: no concurrency protection
                                   BUG-CM-16: weak checkpoint validation
                                   BUG-CM-26: params_snapshot dead code
```

---

## Edge Case Analysis

### Minimum spec (terrain only):
- Terrain generates OK
- Water step: `water_cfg = spec.get("water", {})` -- empty dict is falsy, skipped. OK.
- Roads: `spec.get("roads", [])` -- empty, skipped. OK.
- Locations: `planned_locations` is empty, loop doesn't execute. OK.
- Biome: `spec.get("biome")` -- None, skipped. OK.
- Vegetation: `spec.get("vegetation", {})` -- empty dict is falsy, skipped. OK.
- Props: `spec.get("props", True)` -- defaults to True! But `location_results` is empty, so `scatter_buildings` is empty, raising ValueError (KNOWN BUG).
- **Conclusion:** Minimum spec hits the known props ValueError. No additional issues.

### Maximum spec (everything enabled, 8+ locations, cinematic quality):
- Budget: `large_world` profile auto-selected (>= 8 locations). Resolution capped at 256.
- Terrain: 512x512 max (cinematic). ~131K vertices. OK.
- Water: Multiple rivers + water plane. All re-executed on resume (CM-01).
- Roads: Multiple roads with many waypoints. Coordinates swapped (CM-08).
- Locations: 8+ locations, all get foundation profiles. Potential memory pressure.
- Quality check: Up to 64 mesh targets validated. Each gets UV fix + material fix + LOD generation. Very slow.
- **Critical risk:** BUG-CM-14 (no memory cleanup) + 8 locations + 8000 vegetation instances + props + quality remediation = high risk of Blender OOM or timeout.
