# Stress Test Bug Scan

**Date:** 2026-04-02
**Methodology:** Mental stress-testing with extreme/adversarial inputs across 5 categories
**Scope:** blender_addon/handlers/, blender_addon/socket_server.py, blender_addon/security.py, src/veilbreakers_mcp/blender_server.py

---

## STRESS TEST 1: Unicode and Special Characters

### BUG ST1-01: Code injection via single quotes in object names (CRITICAL)

**Files:** `character_advanced.py:1819-1838`, `geometry_nodes.py:525-526,588,632,659-660,720,783,828-829,877,915`

Object names are interpolated into Python code strings using single quotes with NO escaping:

```python
# character_advanced.py:1819-1820
f"arm = bpy.data.objects['{armature_name}']",
f"mesh = bpy.data.objects['{face_mesh_name}']",

# character_advanced.py:1832
f"b = arm.data.edit_bones.new('{name}')",
f"b.parent = arm.data.edit_bones.get('{parent}')"
```

```python
# geometry_nodes.py:525-526
target = bpy.data.objects[{target_name!r}]
instance = bpy.data.objects[{instance_name!r}]
```

**character_advanced.py** uses f-strings with single quotes (`'{armature_name}'`). If the armature is named `Player's Armature`, the generated code becomes:
```python
arm = bpy.data.objects['Player's Armature']
```
This is a **SyntaxError** that crashes the operation. The same pattern appears for `face_mesh_name`, bone names, and parent names.

**geometry_nodes.py** uses `!r` (repr), which properly escapes special characters. This is the correct pattern that character_advanced.py should follow.

**Trigger:** Any object name containing a single quote.
**Impact:** SyntaxError crash, generated code cannot execute.
**Fix:** Use `!r` repr formatting or `json.dumps()` for all names interpolated into code strings.

---

### BUG ST1-02: Bone name injection in animation data_path strings (MEDIUM)

**Files:** `animation.py:467`, `animation_export.py:726,758,769,772,1201`, `animation_production.py:1438`

Bone names are interpolated into data_path strings using double-quote f-strings:

```python
# animation.py:467
data_path = f'pose.bones["{bone_name}"].{resolved_channel}'

# animation_export.py:726
root_loc_data_path = f'pose.bones["{root_bone_name}"].location'
```

If `bone_name` contains a double quote (e.g., `bone_12"_long`), the data_path string breaks. While Blender bone names rarely contain quotes, the code has no validation. This produces silent failures (fcurve creation fails to find the bone) rather than crashes.

**Trigger:** Bone name containing `"` character.
**Impact:** Silent failure -- keyframes not created, animation broken with no error.
**Fix:** Escape double quotes in bone names, or validate bone name characters.

---

### BUG ST1-03: Pipeline checkpoint filename sanitization incomplete (LOW)

**File:** `pipeline_state.py:61`

```python
safe_name = map_name.replace(" ", "_").replace("/", "_")
path = os.path.join(checkpoint_dir, f"{safe_name}_checkpoint.json")
```

Only spaces and forward slashes are sanitized. Characters like `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|` (all invalid in Windows filenames) are NOT replaced. A map named `Castle: Phase 1` creates a file `Castle:_Phase_1_checkpoint.json` which fails on Windows.

**Trigger:** Map name containing Windows-invalid path characters.
**Impact:** `FileNotFoundError` or `OSError` on Windows when saving checkpoint.
**Fix:** Use a proper sanitizer: `re.sub(r'[^\w\-.]', '_', map_name)` or similar.

---

### BUG ST1-04: Export filepath with bare filename crashes on os.path.dirname (LOW)

**File:** `export.py:19,63`

```python
os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
```

If `filepath` is a bare filename like `"model.fbx"` (no directory), `os.path.dirname(os.path.abspath("model.fbx"))` returns the CWD, which is fine. However, if `filepath` is empty string after `.endswith` check (e.g., someone passes `filepath=""`), the earlier check catches it. This is actually handled correctly. **Not a bug.** (Removed from count.)

---

## STRESS TEST 2: Extreme Numeric Values

### BUG ST2-01: Zero world_size causes ZeroDivisionError in biome grammar (HIGH)

**File:** `_biome_grammar.py:168,191-195`

```python
transition_width_norm = transition_width_m / world_size  # line 168

cx = plot["x"] / world_size   # line 191
cy = plot["y"] / world_size   # line 192
radius = (max_dim / 2.0) / world_size * 1.2  # line 195
```

If `world_size=0.0` is passed to `generate_world_map_spec()`, this divides by zero. The parameter comes from user input at `environment.py:1223`:
```python
world_size = params.get("world_size", 512.0)
```
No validation prevents `world_size=0`.

**Trigger:** `blender_worldbuilding` action `compose_map` with `world_size=0`.
**Impact:** `ZeroDivisionError` crash.
**Fix:** Validate `world_size > 0` in `generate_world_map_spec()`.

---

### BUG ST2-02: Zero width/height in biome noise creates division-by-zero in numpy (HIGH)

**File:** `_biome_grammar.py:260-261`, `_terrain_noise.py:1344-1345`

```python
ys = np.arange(height, dtype=np.float64) / height  # ZeroDivisionError if height=0
xs = np.arange(width, dtype=np.float64) / width     # ZeroDivisionError if width=0
```

The `generate_world_map_spec` function accepts `width` and `height` without lower-bound validation. While `_validate_terrain_params` checks `resolution < 3`, that only applies to the `handle_generate_terrain` path. The multibiome terrain path at `environment.py:1224-1225` passes `width` and `height` directly without validation:

```python
width = params.get("width", 256)
height = params.get("height", 256)
```

**Trigger:** `compose_multibiome_terrain` with `width=0` or `height=0`.
**Impact:** `ZeroDivisionError` in numpy (Python float division) or empty array operations.
**Fix:** Add `width >= 3` and `height >= 3` validation in `generate_world_map_spec()`.

---

### BUG ST2-03: Unbounded image_size/texture_size can allocate gigabytes of RAM (MEDIUM)

**Files:** `mesh_enhance.py:554,687,775`, `texture.py:210,949,1209,1398,1550`, `uv.py:198,358,544,646,809`

```python
image_size = params.get("image_size", 2048)
# ... later:
img = bpy.data.images.new(output_name, image_size, image_size)
```

No upper bound is validated on `image_size` or `texture_size`. A value of `image_size=100000` would attempt to allocate `100000 * 100000 * 4 bytes = ~37 GB` of RAM, crashing Blender.

The terrain resolution is properly capped at `_MAX_RESOLUTION = 4096`, but texture/image sizes have no such cap.

**Trigger:** Any texture/bake operation with `image_size` > 16384.
**Impact:** Out-of-memory crash, Blender becomes unresponsive.
**Fix:** Add `MAX_IMAGE_SIZE = 8192` (or 16384) validation for all image creation calls.

---

### BUG ST2-04: NaN/Inf float params silently corrupt Blender state (MEDIUM)

**Files:** All handlers using `float(params.get(...))` -- approximately 30+ sites across animation, mesh, environment handlers.

```python
frame_count = int(params.get("frame_count", 24))
intensity = float(params.get("intensity", 1.0))
```

If the MCP client sends `"intensity": "NaN"` or `"intensity": float('inf')`, `float()` accepts these without error. The resulting `NaN` or `Inf` values propagate into keyframe values, vertex positions, and material parameters, silently corrupting Blender state.

For `int()`: `int(float('nan'))` raises `ValueError`, which is caught. But `int(float('inf'))` raises `OverflowError`, which may not be caught by specific handlers.

**Trigger:** Sending NaN or Inf as any float parameter via JSON.
**Impact:** Silent data corruption in Blender scene, or uncaught `OverflowError`.
**Fix:** Add a `_validate_finite(value, name)` helper that rejects NaN/Inf.

---

### BUG ST2-05: Enormous erosion_iterations with no practical upper bound (LOW)

**File:** `environment.py:266`

```python
"erosion_iterations": params.get("erosion_iterations", 5000),
```

No validation caps this. The erosion loop at `environment.py:376` computes:
```python
erosion_iters = max(150000, resolution * resolution // 2)
```

But if user passes `erosion_iterations=999999999`, and the erosion implementation respects it, this could run for hours.

**Trigger:** `erosion_iterations=10000000` on even moderate terrain.
**Impact:** Blender hangs for hours, appears frozen.
**Fix:** Cap `erosion_iterations` at a reasonable maximum (e.g., 500000).

---

## STRESS TEST 3: Empty/Null Inputs

### BUG ST3-01: Empty biomes list with non-zero biome_count crashes (HIGH)

**File:** `_biome_grammar.py:162-165`

```python
if biomes is None:
    chosen = list(_DEFAULT_BIOMES[:biome_count])
    ...
else:
    chosen = [resolve_biome_name(b) for b in biomes]

if len(chosen) != biome_count:
    raise ValueError(...)
```

If the user passes `biomes=[]` (empty list, not None), `chosen` becomes `[]`, then the check `len(chosen) != biome_count` raises `ValueError` -- but only if `biome_count != 0`. If BOTH `biomes=[]` and `biome_count=0` are passed, the function proceeds with zero biomes, eventually hitting:

```python
biome_ids, biome_weights = voronoi_biome_distribution(
    biome_count=0, ...
)
```

This creates `distances = np.zeros((height, width, 0))` and `np.argmin(distances, axis=2)` on an empty axis, which raises `ValueError: attempt to get argmin of an empty sequence`.

**Trigger:** `compose_multibiome_terrain` with `biomes=[], biome_count=0`.
**Impact:** Uncaught `ValueError` crash in numpy.
**Fix:** Validate `biome_count >= 1` at the start of `generate_world_map_spec()`.

---

### BUG ST3-02: Empty building_plots dicts missing required keys crash flatten zones (MEDIUM)

**File:** `_biome_grammar.py:189-201`

```python
for plot in (building_plots or []):
    cx = plot["x"] / world_size
    cy = plot["y"] / world_size
    max_dim = max(plot.get("width", 8.0), plot.get("depth", 8.0))
```

If `building_plots` contains an empty dict `{}`, `plot["x"]` raises `KeyError`. The `x` and `y` keys are accessed with bracket notation (no default), while `width` and `depth` use `.get()` with defaults.

**Trigger:** `building_plots=[{}]` in compose_multibiome_terrain.
**Impact:** `KeyError: 'x'` crash.
**Fix:** Validate building_plot entries or use `.get("x", 0.0)`.

---

### BUG ST3-03: None passed as object name bypasses string validation in some handlers (LOW)

**Files:** Many handlers use `params.get("object_name")` followed by `bpy.data.objects.get(name)`.

Most handlers correctly check `if not name: raise ValueError(...)` which catches None. However, `bpy.data.objects.get(None)` actually returns None in Blender without raising, so the pattern `obj = bpy.data.objects.get(name); if obj is None: raise` handles this correctly. The real issue is:

```python
# objects.py:156
obj.location = tuple(params["position"])
```

If `params["position"]` is None, `tuple(None)` raises `TypeError`. This is caught by the socket_server's general exception handler, but the error message is unhelpful ("NoneType object is not iterable" vs. "position is required").

**Impact:** Poor error messages for None inputs.
**Fix:** Validate position/rotation/scale are not None before use.

---

## STRESS TEST 4: Concurrent/Repeated Operations

### BUG ST4-01: Socket server processes only one command per 10ms tick (DESIGN LIMITATION)

**File:** `socket_server.py:171`

```python
# Process one command per tick to avoid freezing Blender UI
try:
    cmd, event, container = self.command_queue.get_nowait()
except queue.Empty:
    return 0.01
```

The server intentionally processes one command per tick (every 10ms). If two clients send commands simultaneously, the second command waits in the queue. The wait timeout is 300 seconds (line 113), so it won't timeout -- but it IS sequential, not concurrent.

This is a deliberate design choice (documented in comment), but it means rapid-fire commands queue up. If the first command takes 30 seconds (e.g., a terrain generation), the second command blocks for 30 seconds.

**Impact:** Commands pile up during long operations. Not a crash, but can cause perceived hangs.
**Mitigation:** Already documented as intentional. Could add queue depth monitoring.

---

### BUG ST4-02: Race condition on global _connection in blender_server.py (LOW)

**File:** `blender_server.py:82-99`

```python
def get_blender_connection() -> BlenderConnection:
    global _connection
    if _connection is not None:  # <-- check outside lock
        return _connection
    with _connection_lock:
        if _connection is None:  # <-- double-check inside lock
            _connection = BlenderConnection(...)
    return _connection
```

The double-checked locking pattern is implemented correctly for creation. However, `_cleanup_connection()` (line 103) sets `_connection = None` inside the lock, while `get_blender_connection()` checks `_connection is not None` OUTSIDE the lock first. Between the non-locked check and the return, `_cleanup_connection()` could set it to None. This would return a disconnected connection.

**Trigger:** Extremely unlikely in practice -- only during server shutdown.
**Impact:** Could return a stale connection during cleanup. Very unlikely to hit.

---

## STRESS TEST 5: Blender State Edge Cases

### BUG ST5-01: active_object is None after operator in headless/background mode (MEDIUM)

**Files:** `objects.py:110,131`, `viewport.py:736`, `mesh_enhance.py:576`

```python
# objects.py:110 (_create_torus)
bpy.ops.mesh.primitive_torus_add()
obj = bpy.context.active_object  # Could be None if no 3D viewport
obj.name = name  # AttributeError: 'NoneType' has no attribute 'name'
```

After `bpy.ops.mesh.primitive_torus_add()`, the active_object should be set. However, when running in background mode or without a 3D viewport, some operators don't set active_object. The `get_3d_context_override()` check on line 107 provides a context override, but if it's None, the function falls through to the bmesh fallback -- this path is safe.

The real risk is `viewport.py:736`:
```python
bpy.ops.mesh.primitive_plane_add(...)
plane = bpy.context.active_object
plane.name = GROUND_PLANE_NAME  # Crashes if active_object is None
```

This does NOT have a fallback. If the primitive_plane_add operator fails silently (e.g., in a context where it can't create objects), `active_object` stays None.

**Trigger:** Running viewport ground plane creation when no 3D viewport is active.
**Impact:** `AttributeError` crash.
**Fix:** Add `if plane is None: raise RuntimeError(...)` check.

---

### BUG ST5-02: handle_clear_scene + concurrent handler = deleted objects accessed (MEDIUM)

**File:** `scene.py:357-362`

```python
def handle_clear_scene(params: dict) -> dict:
    count = len(bpy.data.objects)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    return {"cleared": True, "objects_removed": count}
```

Since the socket server processes one command at a time (ST4-01), true concurrent access shouldn't happen. However, if a handler stores an object reference and a subsequent command clears the scene, the reference becomes a dangling pointer. Blender's Python API raises `ReferenceError` when accessing removed objects, but no handlers check for this.

**Trigger:** Storing object references across commands (not common in current code).
**Impact:** `ReferenceError` crash if it occurs. Low probability with current architecture.

---

### BUG ST5-03: configure_scene accepts arbitrary render_engine strings (LOW)

**File:** `scene.py:367-368`

```python
if params.get("render_engine") is not None:
    scene.render.engine = params["render_engine"]
```

No validation that the engine name is a valid Blender render engine. If someone passes `render_engine="NONEXISTENT"`, Blender raises a `TypeError` or the assignment silently fails (depending on Blender version). This is caught by the socket_server's generic exception handler, but the error message is confusing.

**Impact:** Unclear error message for invalid engine names.
**Fix:** Validate against `bpy.app.render_engines` or similar.

---

### BUG ST5-04: Dungeon/cave generation with width or height < 3 produces degenerate grids (MEDIUM)

**File:** `_dungeon_gen.py:610-632`

```python
def generate_cave_map(
    width: int = 64,
    height: int = 64,
    ...
)
```

No minimum size validation. With `width=1, height=1`:
- `grid = np.zeros((1, 1))` -- a single-cell grid
- `range(1, height - 1)` = `range(1, 0)` -- empty, so no cells get randomized
- Border enforcement overwrites everything to wall
- Result: all-wall grid, no floor cells
- Later code looking for floor cells will find none, potentially causing issues in corridor generation

For BSP dungeon (`generate_bsp_dungeon`), `width=1` means `_split_bsp` can't split, `_place_rooms` may fail to place rooms, and `_force_rooms` creates rooms that might be 0-width.

**Trigger:** `generate_dungeon` or `generate_cave` with `width` or `height` < 3.
**Impact:** Degenerate grids with no floor cells; downstream code may crash or produce empty geometry.
**Fix:** Validate `width >= 8` and `height >= 8` for viable dungeon/cave generation.

---

### BUG ST5-05: Multibiome terrain passes user width/height as terrain resolution, bypassing validation (HIGH)

**File:** `environment.py:1224-1225,1252-1253`

```python
width = params.get("width", 256)
height = params.get("height", 256)
...
terrain_params = {
    ...
    "resolution": width,  # <-- user width becomes terrain resolution
    ...
}
terrain_result = handle_generate_terrain(terrain_params)
```

`handle_generate_terrain` calls `_validate_terrain_params` which caps resolution at `_MAX_RESOLUTION = 4096` and enforces `>= 3`. But the multibiome path directly uses `width` as resolution. If `width=100000`, `_validate_terrain_params` will reject it.

However, if `width != height` (e.g., `width=256, height=512`), only `width` is used as `resolution`. The `height` parameter feeds into `_biome_grammar.py` where it becomes the grid height for noise/voronoi arrays, which is separate from the terrain mesh resolution. This means the biome computation grid dimensions can be arbitrarily large even though terrain resolution is capped.

Specifically, `_generate_corruption_map(width=256, height=100000, ...)` would create a `np.zeros((100000, 256))` array -- 200MB of RAM for the corruption map alone, plus the voronoi distance array at `(100000, 256, biome_count)` which at 6 biomes = ~11GB.

**Trigger:** `compose_multibiome_terrain` with `height=100000`.
**Impact:** Massive memory allocation, OOM crash.
**Fix:** Validate both `width` and `height` against `_MAX_RESOLUTION` in multibiome path, not just in `_validate_terrain_params`.

---

## SUMMARY

| ID | Severity | Category | File(s) | Description |
|----|----------|----------|---------|-------------|
| ST1-01 | CRITICAL | Unicode/Injection | character_advanced.py | Single-quote in object names breaks generated Python code |
| ST2-01 | HIGH | Numeric | _biome_grammar.py | world_size=0 causes ZeroDivisionError |
| ST2-02 | HIGH | Numeric | _biome_grammar.py, _terrain_noise.py | width/height=0 causes division-by-zero in numpy |
| ST3-01 | HIGH | Empty Input | _biome_grammar.py | biomes=[], biome_count=0 crashes numpy argmin |
| ST5-05 | HIGH | Numeric | environment.py, _biome_grammar.py | height param unbounded, can allocate >10GB RAM |
| ST1-02 | MEDIUM | Unicode | animation.py, animation_export.py, animation_production.py | Double-quote in bone names breaks data_path |
| ST2-03 | MEDIUM | Numeric | mesh_enhance.py, texture.py, uv.py | Unbounded image_size can allocate >30GB RAM |
| ST2-04 | MEDIUM | Numeric | 30+ handler files | NaN/Inf float params silently corrupt Blender state |
| ST3-02 | MEDIUM | Empty Input | _biome_grammar.py | Empty dict in building_plots raises KeyError |
| ST5-01 | MEDIUM | Blender State | viewport.py | active_object None after operator in restricted context |
| ST5-02 | MEDIUM | Concurrent | scene.py | clear_scene can invalidate references held by in-flight ops |
| ST5-04 | MEDIUM | Blender State | _dungeon_gen.py | width/height < 3 produces degenerate all-wall grids |
| ST1-03 | LOW | Unicode | pipeline_state.py | Windows-invalid chars in map name crash checkpoint save |
| ST2-05 | LOW | Numeric | environment.py | Unbounded erosion_iterations can hang for hours |
| ST3-03 | LOW | Empty Input | objects.py | None position/rotation gives unhelpful error message |
| ST4-02 | LOW | Concurrent | blender_server.py | Theoretical TOCTOU race on _connection during cleanup |
| ST5-03 | LOW | Blender State | scene.py | No validation of render_engine string |

**Total new bugs found: 16**
- CRITICAL: 1
- HIGH: 4
- MEDIUM: 6
- LOW: 5
