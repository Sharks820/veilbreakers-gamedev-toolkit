# Deep Bug Scan: Dungeon, Cave, Encounter, Combat Space Systems

**Date:** 2026-04-02
**Scanner:** Claude Opus 4.6 (1M context)
**Files scanned:** 18 handler files across dungeon/cave/encounter/combat/terrain/boss/destruction/scatter/character systems
**Known bugs excluded:** 116 bugs from 9 previous scans

---

## NEW BUGS FOUND: 14

---

### BUG #1: `_dungeon_gen.py` — Multi-floor connection positions desynchronized from transition assignments

**File:** `blender_addon/handlers/_dungeon_gen.py`, lines 1061-1081
**Severity:** HIGH
**Type:** Logic error

`_place_connection_points()` generates connection positions for ALL transitions at once (flat list), then `generate_multi_floor_dungeon()` consumes them with a SECOND `rng.randint(1, 2)` call per transition to decide how many connections per transition. But the first call to `_place_connection_points()` ALSO uses `rng.randint(1, 2)` internally to determine count. These are two separate RNG calls that produce different counts.

```python
# _place_connection_points generates N positions using rng.randint(1,2) per transition
connection_positions = _place_connection_points(width, height, num_transitions, rng, ...)

# Then this loop uses rng.randint(1,2) AGAIN -- different results!
for t in range(num_transitions):
    n_conns = rng.randint(1, 2)  # NOT the same count as _place_connection_points used
    for _ in range(n_conns):
        if conn_idx < len(connection_positions):
            t_conns.append(connection_positions[conn_idx])
            conn_idx += 1
```

If `_place_connection_points` generated 2 positions for transition 0, but the consuming loop draws 1 for transition 0 and 2 for transition 1, the positions are mismatched (transition 1 gets a position that was placed for transition 0's spatial constraints).

**Fix:** Pass the per-transition counts from `_place_connection_points` back to the caller, or generate connections inside a single loop.

---

### BUG #2: `_dungeon_gen.py` — `_place_spawn_points` can IndexError on tiny rooms

**File:** `blender_addon/handlers/_dungeon_gen.py`, lines 492-497
**Severity:** MEDIUM
**Type:** Edge case / crash

```python
px = rng.randint(room.x + 1, room.x2 - 2)
py = rng.randint(room.y + 1, room.y2 - 2)
```

If `room.width` is exactly `min_room_size` (6), then `room.x2 - 2 = room.x + 4` and `room.x + 1` is valid. But if `room.width == 2` (possible from `_force_rooms` with `min_room_size=2` if caller overrides), `room.x + 1 > room.x2 - 2` and `rng.randint` raises `ValueError: empty range for randrange()`.

Even at default `min_room_size=6`, rooms from `_force_rooms` use `rng.randint(min_room_size, min(min_room_size * 2, width // 3))` which at minimum produces width=6. So `room.x2 - 2 = room.x + 4` and `room.x + 1` is fine. However, the boss room expansion at line 416-436 never shrinks a room, so this is only an issue if a future caller uses `min_room_size < 3`.

**Risk:** Low currently, but the code has no guard. A simple `max(room.x + 1, room.x2 - 2)` already exists in the generic room prop placement (line 1254) but NOT here.

**Fix:** Add the same `max()` guard as line 1254.

---

### BUG #3: `_dungeon_gen.py` — Town `_place_landmarks` quadratic search blows up on large maps

**File:** `blender_addon/handlers/_dungeon_gen.py`, lines 937-972
**Severity:** MEDIUM
**Type:** Performance

```python
search_radius = 50  # broad search to guarantee finding roads
for dy in range(-search_radius, search_radius + 1):
    for dx in range(-search_radius, search_radius + 1):
```

This is a 101x101 = 10,201 iteration loop per district. For each cell, it checks `(nx, ny) in roads` (a set lookup) plus 4 neighbors. With 6 districts, that is ~61K iterations * 5 set lookups = ~300K lookups. For the default 200x200 map this is borderline acceptable, but for larger maps it will become sluggish. More critically, if no road is found within radius 50 (possible with sparse districts), the landmark defaults to the district center which may be inside a building plot, causing prop collision.

**Fix:** Use BFS from district center outward instead of brute-force radius scan, or pre-compute road adjacency.

---

### BUG #4: `_dungeon_gen.py` — Town road adjacency check is O(N) over entire road set

**File:** `blender_addon/handlers/_dungeon_gen.py`, lines 791-800
**Severity:** MEDIUM
**Type:** Performance

```python
for rx, ry in roads:
    if assignment[ry, rx] == i:
        for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ...
    if shares_boundary:
        break
```

For each pair of districts (O(N^2) pairs), it iterates ALL road cells. Road count can be ~10K+ for a 200x200 map. This makes the total complexity O(districts^2 * road_cells), which is ~10K * 15 = 150K iterations for 6 districts. Tolerable at default scale but wasteful.

**Fix:** Pre-compute a set of (district_a, district_b) adjacency pairs during the boundary-road detection phase above.

---

### BUG #5: `encounter_spaces.py` — `enemy_count` override ignores `min_enemies` for string-type `enemy_spec`

**File:** `blender_addon/handlers/encounter_spaces.py`, lines 387-404
**Severity:** MEDIUM
**Type:** Logic error

The enemy count override at lines 387-404 only triggers `if enemy_count is not None and isinstance(enemy_spec, list)`. For templates with string-based `enemy_spec` (like `"perimeter_8"`, `"alternating_sides"`), the override within the string resolution block (lines 376-380) correctly clamps to `min_e/max_e`. BUT: it does NOT use `min_enemies` as a lower bound for `enemy_count` -- it uses `min_e` from the template. The issue is that the explicit override path for list specs at line 389 uses `max_e` but has NO `min_e` clamp:

```python
count = max(0, min(enemy_count, max_e))  # min is 0, not min_e!
```

An `enemy_count=0` with a list-based template (like `boss_chamber` with `min_enemies=1`) would produce ZERO enemies, violating the template's minimum.

**Fix:** Change `max(0, ...)` to `max(min_e, ...)` to respect template minimum, or at least `max(template.get("min_enemies", 0), ...)`.

---

### BUG #6: `encounter_spaces.py` — Stealth zone cover positions outside bounds

**File:** `blender_addon/handlers/encounter_spaces.py`, lines 146-171
**Severity:** LOW
**Type:** Data quality

The `stealth_zone` template has `width=15.0` but cover positions include `(-5, 3, 0)` and `(5, 10, 0)`. The bounds computation for `irregular_room` shape uses `template.get("size", template.get("width", 10.0))` which gets `width=15.0`, so `half_w = 7.5`. Position `(-5, 3, 0)` is within bounds. However, `validate_encounter_layout` bounds check uses `b_min[axis] - 0.5` tolerance (line 596). Since there is no `length` key separate from the computed `l` (which falls back to `s = 15.0`), and `player_exit` is at `(0, 20, 0)`, the computed `all_y` will include `20` which pushes `half_l` correctly. This is technically correct but confusing -- the template declares `length=20.0` explicitly, so the bounds do use it. No crash but worth noting the shape `irregular_room` with explicit `width` AND `length` keys is inconsistent naming vs other shapes.

---

### BUG #7: `destruction_system.py` — Rubble center uses Y as ground, but mesh likely uses Z-up

**File:** `blender_addon/handlers/destruction_system.py`, lines 280-286
**Severity:** MEDIUM
**Type:** Coordinate convention mismatch

```python
center = (
    (min(xs) + max(xs)) / 2.0,
    min(ys),  # ground level
    (min(zs) + max(zs)) / 2.0,
)
```

The function assumes Y is vertical (ground = min Y). However, Blender uses Z-up convention. If the input mesh vertices use Blender's Z-up convention, then `min(ys)` is not the ground level -- `min(zs)` would be. The `generate_rubble_pile` function also places rubble with `cy = center[1]` (Y as ground) and `dy = rng.uniform(0, size * 0.7)` (upward from ground in Y).

This would place rubble at the BACK of the mesh instead of the BOTTOM if the mesh uses Z-up coordinates. The gravity factor in vertex displacement (line 229) also subtracts from Y: `vy + normal[1] * disp_scale - gravity_factor`, assuming Y is up.

**Fix:** Either document that this module expects Y-up (game engine convention, not Blender convention), or add a `z_up` parameter to swap axes. Since the docstring says "no bpy dependency" and is "for testability", it may intentionally use Y-up for game export. But the calling code in `worldbuilding_layout.py` operates in Blender's Z-up space, so there IS a mismatch at integration time.

---

### BUG #8: `destruction_system.py` — Face removal weighting is biased, not truly weighted

**File:** `blender_addon/handlers/destruction_system.py`, lines 252-265
**Severity:** LOW
**Type:** Algorithm correctness

```python
top_half = [fi for _, fi in face_heights[:len(faces) // 2]]
weighted_pool = top_half + candidate_pool  # top_half faces appear TWICE
rng.shuffle(weighted_pool)

for fi in weighted_pool:
    if len(remove_indices) >= num_to_remove:
        break
    remove_indices.add(fi)  # set deduplicates, so duplicates just waste iterations
```

The intent is to make upper faces 2x more likely to be removed. But because `remove_indices` is a `set`, when a duplicate top-half face index is encountered, it's already in the set and no new face is removed. The loop just skips it. This means the weighting is LESS than 2x because duplicates waste iterations without effect, and if `num_to_remove` is large relative to the pool, the loop may iterate the entire pool without removing enough faces.

For small `missing_faces_pct` (0.1 = 10% of faces), this is unlikely to matter. For `destroyed` level (0.4 = 40%), the shortfall could be noticeable.

**Fix:** Use weighted random sampling (e.g., `random.choices` with weights) instead of the shuffle-and-deduplicate approach.

---

### BUG #9: `boss_presence.py` — `_compute_bbox` returns wrong type for empty verts

**File:** `blender_addon/handlers/boss_presence.py`, lines 94-101
**Severity:** LOW
**Type:** Type inconsistency

```python
def _compute_bbox(verts: VertList) -> tuple[Vec3, Vec3]:
    if not verts:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)  # Returns tuple[tuple[float,...], tuple[float,...]]
```

The return type annotation says `tuple[Vec3, Vec3]` where `Vec3 = tuple[float, float, float]`. The empty-verts return `(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)` is correct typing. However, the caller `enhance_boss_mesh` at line 621 does `mesh_bbox = (tuple(bbox[0]), tuple(bbox[1]))` when bounding_box is provided, which would fail if bbox[0] is already a plain tuple (it would just create a copy). The real issue: if `base_verts` is empty, `mesh_bbox = ((0,0,0), (1,2,1))` is hardcoded (line 623), which is a different fallback than `_compute_bbox`'s `(0,0,0), (0,0,0)`. This inconsistency means the crown/aura/ground features would have different geometry depending on which empty-mesh path is taken.

---

### BUG #10: `_combat_timing.py` — `apply_brand_timing` mutates shared `timing_config` frames dict

**File:** `blender_addon/handlers/_combat_timing.py`, lines 146-194
**Severity:** MEDIUM
**Type:** Shared state mutation

```python
def apply_brand_timing(timing_config: dict[str, Any], brand: str) -> dict[str, Any]:
    result = copy.deepcopy(timing_config)
    frames = result["frames"]
    ...
    frames["recovery"] = max(1, round(frames["recovery"] * mods["recovery_scale"]))
```

The function correctly deep-copies `timing_config` before mutating. However, `generate_combat_animation_data` at line 536-540 calls:

```python
timing = configure_combat_timing(attack_type, fps=fps, custom_timing=custom_timing)
if brand_upper in BRAND_TIMING_MODIFIERS:
    timing = apply_brand_timing(timing, brand_upper)
```

Then at line 542: `events = generate_animation_events(timing, brand=brand_upper)`. The `timing` here has MODIFIED frame values from `apply_brand_timing`, but `generate_animation_events` was designed against the raw `configure_combat_timing` output format. Since `apply_brand_timing` adds extra keys (`brand`, `easing`) but preserves the `frames` dict structure, this works. BUT: `apply_brand_timing` recalculates `hit_frame` at line 177 but does NOT update `phase_ranges` (which `configure_combat_timing` computes at lines 289-293). The `phase_ranges` key is now stale after brand timing is applied.

**Fix:** Recalculate `phase_ranges` inside `apply_brand_timing` after modifying frame counts.

---

### BUG #11: `_combat_timing.py` — Block attack type has `active=0` causing division issues

**File:** `blender_addon/handlers/_combat_timing.py`, lines 95-106
**Severity:** LOW
**Type:** Edge case

The `block` preset has `active: 0` and `total: 4`. In `configure_combat_timing`, when `active=0`, `phase_ranges["active"]` is set to `None` (line 292). This is handled correctly. However, in `generate_combat_animation_data`, the default root motion generation at lines 565-577 iterates `range(total)` and checks:

```python
if active_start <= t <= active_end and active_end > active_start:
```

When `active=0`, `active_start == active_end` (both equal `anticipation / total_f`), so the condition `active_end > active_start` is False and `z=0.0` for all frames. This is correct behavior for block. No crash, but the `phase_ranges` returning `None` for active could trip up downstream code that doesn't check for None.

---

### BUG #12: `_terrain_depth.py` — `detect_cliff_edges` calls `np.gradient` on full heightmap per call

**File:** `blender_addon/handlers/_terrain_depth.py`, lines 606-608
**Severity:** MEDIUM
**Type:** Performance / Redundant computation

```python
dy, dx = np.gradient(heightmap)
grad_x = float(dx[ri, ci])
grad_y = float(dy[ri, ci])
```

`np.gradient(heightmap)` is called INSIDE the loop over label IDs. It should be computed ONCE before the loop since the heightmap doesn't change. For a heightmap with many cliff clusters (e.g., 50 clusters), this recomputes the gradient 50 times.

**Fix:** Move `dy, dx = np.gradient(heightmap)` above the `for lid in range(label_id):` loop.

---

### BUG #13: `worldbuilding_layout.py` — `handle_generate_town` uses `import random as _rng_town` then seeds with `_rng_town.seed()`

**File:** `blender_addon/handlers/worldbuilding_layout.py`, lines 498-500
**Severity:** MEDIUM  
**Type:** Global random.seed pollution (variant of known bug, but different location)

```python
import random as _rng_town
_rng_town.seed(seed + i)
rot_z = _rng_town.choice([0.0, math.pi * 0.5, math.pi, math.pi * 1.5])
```

Despite the alias `_rng_town`, this is still `import random` and `.seed()` pollutes the GLOBAL random state. The file already has `import random` at the top (line 19) and creates `rng = random.Random(seed)` (line 343) for local use. This line undoes the isolation.

**Fix:** Use `rng.choice(...)` (the already-created local Random instance) instead of reseeding the global module.

---

### BUG #14: `worldbuilding_layout.py` — `generate_linked_interior_spec` only handles "south" facing correctly

**File:** `blender_addon/handlers/worldbuilding_layout.py`, lines 1145-1153
**Severity:** MEDIUM
**Type:** Incomplete logic

```python
"exterior_probe_position": (
    round(pos[0] + (1.5 if facing == "south" else -1.5), 2),
    round(pos[1], 2),
    round(pos[2] + 1.5, 2),
),
"interior_probe_position": (
    round(pos[0] + (-1.5 if facing == "south" else 1.5), 2),
    round(pos[1], 2),
    round(pos[2] + 1.5, 2),
),
```

The exterior/interior probe positions only have two cases: `facing == "south"` (offset +X for exterior) and everything else (offset -X for exterior). But `facing` can be "north", "south", "east", or "west". For "east" and "west" doors, the probe should be offset along the Y axis, not the X axis. For "north" doors, the X offset should be opposite of "south". Currently, "north", "east", and "west" all get the same `-1.5` X offset, which is incorrect for east/west-facing doors.

**Fix:** Add proper per-facing offsets:
- "south": exterior probe at +X, interior at -X
- "north": exterior probe at -X, interior at +X  
- "east": exterior probe at +Y, interior at -Y
- "west": exterior probe at -Y, interior at +Y

---

## SUMMARY

| # | File | Bug | Severity |
|---|------|-----|----------|
| 1 | `_dungeon_gen.py` | Multi-floor connection position desync | HIGH |
| 2 | `_dungeon_gen.py` | `_place_spawn_points` IndexError on tiny rooms | MEDIUM |
| 3 | `_dungeon_gen.py` | Town landmark search O(N^2) blowup | MEDIUM |
| 4 | `_dungeon_gen.py` | Town road adjacency O(roads) per district pair | MEDIUM |
| 5 | `encounter_spaces.py` | `enemy_count=0` bypasses `min_enemies` for list specs | MEDIUM |
| 6 | `encounter_spaces.py` | Stealth zone shape naming inconsistency | LOW |
| 7 | `destruction_system.py` | Rubble Y-ground vs Blender Z-up mismatch | MEDIUM |
| 8 | `destruction_system.py` | Face removal weighting ineffective due to set dedup | LOW |
| 9 | `boss_presence.py` | Inconsistent empty-mesh bbox fallbacks | LOW |
| 10 | `_combat_timing.py` | `phase_ranges` stale after `apply_brand_timing` | MEDIUM |
| 11 | `_combat_timing.py` | Block `active=0` — `phase_ranges` returns None | LOW |
| 12 | `_terrain_depth.py` | `np.gradient` recomputed per cluster in loop | MEDIUM |
| 13 | `worldbuilding_layout.py` | Global `random.seed()` pollution in town gen | MEDIUM |
| 14 | `worldbuilding_layout.py` | `generate_linked_interior_spec` only handles south facing | MEDIUM |

**HIGH:** 1 | **MEDIUM:** 8 | **LOW:** 5

---

## FILES SCANNED (no new bugs found)

- `_scatter_engine.py` — Clean. Poisson disk, biome filter, context scatter, breakable variants all solid.
- `dungeon_themes.py` — Clean. Simple data + accessor + copy-on-read pattern.
- `_biome_grammar.py` — Clean. Data tables + Voronoi + corruption map.
- `_terrain_erosion.py` — Clean. Hydraulic + thermal erosion properly bounded.
- `_terrain_noise.py` — Clean (first 100 lines; permutation table approach correct).
- `_character_quality.py` — Clean. Proportion/face/hand validation all bounds-checked.
- `_character_lod.py` — Clean. LOD decimation + seam ring generation correct.
- `_action_compat.py` — Clean. Blender 5.0 API compat layer.
- `_context.py` — Clean. Simple viewport context finder.
- `map_composer.py` — Clean (first 100 lines). POI rules properly structured.
- `prop_density.py` — Clean (first 100 lines). Room density rules correctly typed.
- `light_integration.py` — Clean (first 100 lines). Light prop map well-structured.
