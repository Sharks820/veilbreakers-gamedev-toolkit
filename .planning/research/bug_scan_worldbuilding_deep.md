# Deep Bug Scan: Worldbuilding, Settlement, and Interior Generation Systems

**Date:** 2026-04-02
**Files Scanned:** 7 files (~8,000+ lines)
**Method:** Full code path trace through all entry points, cross-module data flow verification

---

## Critical Bugs (CRASH)

### BUG-WB-001: `_furnish_interior` crashes on small rooms via `rng.uniform(a, b)` where a > b
- **File:** `settlement_generator.py`
- **Function:** `_furnish_interior`, ~line 1258-1298
- **Type:** CRASH
- **Severity:** CRASH
- **Description:** When placing furniture against east/west walls, the code does:
  ```python
  py = rng.uniform(
      ry_min + wall_margin + item_size[0] / 2,
      ry_max - wall_margin - item_size[0] / 2,
  )
  ```
  If `room_d < wall_margin * 2 + item_size[0]` (e.g., room depth 1.5m with a 1.0m bed), the lower bound exceeds the upper bound. `random.uniform(a, b)` with `a > b` returns a value outside [min, max] but doesn't crash. However, the *center placement* code at ~line 1290-1298 has the same pattern with `center_margin`:
  ```python
  px = rng.uniform(
      rx_min + center_margin + item_size[0] / 2,
      rx_max - center_margin - item_size[0] / 2,
  )
  ```
  `center_margin = room_w * 0.25`, so for a 3m wide room with a 2.0m market_stall, the bounds are `0 + 0.75 + 1.0 = 1.75` and `3.0 - 0.75 - 1.0 = 1.25`. This produces a swapped range. While `random.uniform` technically still returns a float, the placed furniture will be outside room bounds, and the AABB collision check later could infinite-loop the 30-attempt retry for subsequent items if all candidate positions are invalid.

### BUG-WB-002: `_BUILDING_ROOMS` missing key `"armory"` used by `guild_hall` room list
- **File:** `settlement_generator.py`
- **Function:** `_furnish_interior` / `_place_buildings`
- **Type:** DATA
- **Severity:** LOGIC
- **Description:** In `_BUILDING_ROOMS`, `guild_hall` maps to `["great_hall", "study", "storage", "armory"]`. But `ROOM_FURNISHINGS` has no `"armory"` key. When `_furnish_interior` is called with `room_type="armory"`, it falls through to `ROOM_FURNISHINGS.get("armory", ["crate"])`, which returns `["crate"]`. The room gets only a single crate, which is not what an armory should contain. Not a crash, but functionally wrong.

### BUG-WB-003: Module-level `_PROP_CACHE` stale state across Blender sessions
- **File:** `worldbuilding.py`
- **Function:** `_get_or_generate_prop`, ~line 41
- **Type:** PERF / DATA
- **Severity:** LOGIC
- **Description:** `_PROP_CACHE: dict[tuple[str, str], str] = {}` is module-level. Blender keeps Python modules loaded across file reloads. If a user opens a new .blend file, the cache still holds paths to GLB files from the previous session, which may no longer exist on disk. `clear_prop_cache()` exists but is never called automatically on scene change. This will cause silent import failures when the cached GLB path is stale.

### BUG-WB-004: `building_interior_binding` room type mismatch with `_building_grammar` room configs
- **File:** `building_interior_binding.py`
- **Function:** `BUILDING_ROOM_MAP`
- **Type:** DATA
- **Severity:** LOGIC
- **Description:** `BUILDING_ROOM_MAP` uses room types like `"tavern_hall"`, `"treasury"`, `"war_room"`, `"torture_chamber"`, `"crypt"`, `"generic"`, `"alchemy_lab"`. However, `settlement_generator.py`'s `ROOM_FURNISHINGS` does not have entries for `"tavern_hall"`, `"treasury"`, `"war_room"`, `"torture_chamber"`, `"crypt"`, `"generic"`, or `"alchemy_lab"`. When these room types flow through the interior composition pipeline, they get default furnishing (`["crate"]`). The two systems use different room type vocabularies that were never reconciled.

---

## Serious Logic Bugs

### BUG-WB-005: `ring_for_position` uses XY distance but Blender is Z-up
- **File:** `_settlement_grammar.py`
- **Function:** `ring_for_position`, ~line 150-174
- **Type:** DATA
- **Severity:** LOGIC
- **Description:** `ring_for_position` computes distance using `pos[0] - center[0]` (X) and `pos[1] - center[1]` (Y), which is correct for a Z-up world (XY is the ground plane in Blender). However, when called from `generate_prop_manifest` at line 668, the position is `(px, py)` -- a 2-tuple. The function accepts Vec2|Vec3, and the indexing `pos[0]` and `pos[1]` works fine. **No bug here on review** -- the coordinate system is consistent (XY ground plane, Z up).

### BUG-WB-006: `concentric_organic` layout pattern not handled in `_place_buildings`
- **File:** `settlement_generator.py`
- **Function:** `_place_buildings`, ~line 800-907
- **Type:** LOGIC
- **Severity:** LOGIC
- **Description:** `SETTLEMENT_TYPES["medieval_town"]` and `SETTLEMENT_TYPES["hearthvale"]` use `"layout_pattern": "concentric_organic"`. However, `_place_buildings` has `if/elif` checks for `"circular"`, `"grid"`, `"concentric"`, `"axial"`, `"radial_spokes"`, `"terraced"`, `"waterfront_edge"`, and `else` (organic). The `"concentric_organic"` pattern is not explicitly handled and falls through to the `else` (organic) branch. This means medieval towns and Hearthvale get purely random organic placement instead of the intended concentric+organic hybrid layout. For Hearthvale specifically (which has exact 14 buildings), this produces a scattered mess instead of a structured layout.

### BUG-WB-007: `hearthvale` building types mismatch with `_BUILDING_FOOTPRINTS`
- **File:** `settlement_generator.py`
- **Function:** `_place_buildings` / `_try_place`
- **Type:** DATA
- **Severity:** LOGIC
- **Description:** `SETTLEMENT_TYPES["hearthvale"]` has `"guard_barracks"` in its building_types list. `_BUILDING_FOOTPRINTS` has a `"guard_barracks"` entry (14.0, 10.0), which is correct. However, the `_BUILDING_FLOORS` dict inside `_try_place` maps `"guard_barracks": 2`, which is correct. BUT: the `remaining_types` filter at line 796-800 filters out types containing `"shrine"` or `"market"`. Since `hearthvale` has `"temple"` (not `"shrine"`), the temple type survives the filter and can be placed as a regular building rather than a priority shrine placement. The `has_shrine` logic at line 759-774 searches for types with `"shrine"` in the name, which doesn't match `"temple"`. Result: Hearthvale's temple is NOT placed at the center as a priority shrine -- it gets random organic placement.

### BUG-WB-008: `handle_generate_town` uses unseeded `random.seed()` for rotation
- **File:** `worldbuilding_layout.py`
- **Function:** `handle_generate_town`, ~line 498-501
- **Type:** DATA
- **Severity:** LOGIC
- **Description:** The code does:
  ```python
  import random as _rng_town
  _rng_town.seed(seed + i)
  rot_z = _rng_town.choice([0.0, math.pi * 0.5, math.pi, math.pi * 1.5])
  ```
  This uses the **global** `random` module, which pollutes the global random state. Other code running concurrently or subsequently in the same Blender session that relies on global `random` will get different results. Should use a local `random.Random(seed + i)` instance instead.

### BUG-WB-009: `_LANDMARK_ROOM_TYPE_MAP` is incomplete vs. `VB_LANDMARK_PRESETS`
- **File:** `worldbuilding.py`
- **Function:** `_LANDMARK_ROOM_TYPE_MAP`, ~line 456-464
- **Type:** DATA
- **Severity:** LOGIC
- **Description:** The map only covers: `throne_room`, `prison`, `shrine_room`, `guard_post`, `storage`, `smithy`, `barracks`. But `VB_LANDMARK_PRESETS["thornwood_heart"]` has `interior_rooms: ["shrine_room"]` which maps fine. However, any landmark room name not in this map (currently all are covered) would silently fail to find a room config. The concern is future-proofing, but currently this is safe. **Not a bug currently.**

### BUG-WB-010: `settlement_generator._generate_roads` produces 2-tuple positions, but `_settlement_grammar.generate_road_network_organic` produces 3-tuples
- **File:** `settlement_generator.py` vs `_settlement_grammar.py`
- **Function:** `_generate_roads` (~line 985-1013) vs `generate_road_network_organic`
- **Type:** DATA
- **Severity:** LOGIC
- **Description:** `_generate_roads` produces road segments with `"start"` and `"end"` as 2-tuples `(x, y)`. But `_settlement_grammar.generate_road_network_organic` produces `"start"` and `"end"` as 3-tuples `(x, y, z)`. When `worldbuilding.py`'s `_create_road_with_curbs` at line 2698-2704 reads:
  ```python
  start_2d = road_segment.get("start")
  sx, sy = start_2d[0], start_2d[1]
  ```
  This works for both 2-tuples and 3-tuples. But `_road_segment_mesh_spec_with_curbs` expects `Vec3` (3-tuples) for its `start`/`end` params. If a 2-tuple road from `_generate_roads` is passed to `_create_road_with_curbs`, line 2712:
  ```python
  spec = _road_segment_mesh_spec_with_curbs(
      start=(sx, sy, sz),  # reconstructed as 3-tuple
      end=(ex, ey, ez),
  ```
  The reconstruction works. **Not a crash, but the inconsistent tuple arity is fragile.**

### BUG-WB-011: `building_interior_binding.align_rooms_to_building` positions rooms in building-local space using `bx + wall_thickness` but `generate_interior_spec_from_building` passes `building_position=(0,0,0)` by default
- **File:** `building_interior_binding.py`
- **Function:** `align_rooms_to_building`, ~line 159-231
- **Type:** DATA
- **Severity:** LOGIC
- **Description:** `align_rooms_to_building` uses `bx, by, bz = building_position` and computes `current_x = bx + wall_thickness`. When `generate_interior_spec_from_building` is called without specifying `building_position`, it defaults to `(0, 0, 0)`. This means all rooms are positioned relative to world origin, not the building's actual location. The downstream `compose_interior` call would need to account for this offset. The `building_bounds` in the returned spec correctly shows the building's footprint from its position, but the room positions inside may be misaligned if the building is not at origin. This is a design choice (local space), but the inconsistency between `building_bounds` being absolute and `room.position` being absolute could cause issues.

### BUG-WB-012: `generate_prop_manifest` uses single `spacing` for entire settlement
- **File:** `_settlement_grammar.py`
- **Function:** `generate_prop_manifest`, ~line 636
- **Type:** LOGIC
- **Severity:** LOGIC (minor)
- **Description:** The spacing value is computed once at line 636:
  ```python
  spacing = rng.uniform(spacing_min, spacing_max)
  ```
  Then reused for ALL road segments. But the per-segment loop at line 686 does:
  ```python
  t += spacing * rng.uniform(0.8, 1.2)
  ```
  This adds local variation. However, the base `spacing` is determined by veil pressure for the whole settlement -- a high-corruption settlement gets sparse props everywhere, including the pristine market center. This is a design bug: prop density should vary by district, not be uniform.

### BUG-WB-013: `_hash_noise_2d` integer overflow on 32-bit Python
- **File:** `map_composer.py`
- **Function:** `_hash_noise_2d`, ~line 310-324
- **Type:** DATA
- **Severity:** LOGIC
- **Description:** The function does:
  ```python
  h = (ix * 73856093) ^ (iy * 19349669) ^ (seed * 83492791)
  h = ((h >> 16) ^ h) * 0x45D9F3B
  ```
  Python integers have arbitrary precision, so this won't overflow. But `ix` is masked to `0xFFFFFFFF`, and the multiplication `ix * 73856093` can produce values >> 32 bits before the XOR. The final `h & 0xFFFFFFFF` at line 324 constrains the result. This is fine in CPython. **Not actually a bug in Python** (unlike C). However, the noise quality may be poor because the intermediate hash values aren't properly constrained to 32-bit at each step.

---

## Data Flow / Integration Bugs

### BUG-WB-014: `_DISTRICT_BUILDING_TYPES` vs `SETTLEMENT_TYPES` building type vocabulary mismatch
- **File:** `_settlement_grammar.py` vs `settlement_generator.py`
- **Function:** `_DISTRICT_BUILDING_TYPES` vs `SETTLEMENT_TYPES`
- **Type:** DATA
- **Severity:** LOGIC
- **Description:** `_settlement_grammar._DISTRICT_BUILDING_TYPES` maps district rings to building types like `"market_stall_cluster"`, `"tavern"`, `"guild_hall"`, `"blacksmith"`, `"manor"`, `"shrine_major"`, `"barracks"`, `"forge"`, `"abandoned_house"`, `"shrine_minor"`, `"watchtower"`. These are used by `assign_buildings_to_lots()`.

  Meanwhile, `settlement_generator.SETTLEMENT_TYPES` configs define their own `"building_types"` lists which use overlapping but NOT identical vocabularies. For example, `bandit_camp` uses `"tent"`, `"lean_to"`, `"campfire_area"`, `"cage"` -- none of which appear in `_DISTRICT_BUILDING_TYPES`.

  When `generate_settlement` uses the settlement-generator's building placement (which uses its own type list) but also calls `assign_buildings_to_lots` (which uses `_DISTRICT_BUILDING_TYPES`), the building types from the two systems can conflict. The grammar system may assign `"market_stall_cluster"` to a lot that was placed as an `"abandoned_house"` by the settlement generator.

### BUG-WB-015: `VB_BUILDING_PRESETS` missing several types used by settlement generator
- **File:** `worldbuilding.py` vs `settlement_generator.py`
- **Type:** DATA
- **Severity:** LOGIC
- **Description:** `settlement_generator._BUILDING_FOOTPRINTS` defines footprints for: `"tavern"`, `"blacksmith"`, `"temple"`, `"town_hall"`, `"general_store"`, `"apothecary"`, `"bakery"`, `"house"`, `"guard_barracks"`, `"manor"`, `"guild_hall"`. 

  `VB_BUILDING_PRESETS` in `worldbuilding.py` has presets for: `"shrine_minor"`, `"shrine_major"`, `"ruined_fortress_tower"`, `"abandoned_house"`, `"forge"`, `"inn"`, `"warehouse"`, `"barracks"`, `"gatehouse"`, `"rowhouse"`, `"town_hall"`, `"apothecary"`, `"bakery"`.

  Missing from presets: `"tavern"`, `"blacksmith"`, `"temple"`, `"general_store"`, `"house"`, `"guard_barracks"`, `"manor"`, `"guild_hall"`. When `_generate_location_building` handles these types, it falls through to either the general building handler (which uses `evaluate_building_grammar` with generic parameters) or the preset lookup returns `None` and no preset is applied. The buildings generate but without their intended preset configurations (wall heights, opening styles, etc.).

### BUG-WB-016: `_BUILDING_ROOMS["guild_hall"]` references `"armory"` room type not in any furnishing config
- **File:** `settlement_generator.py`
- **Function:** `_BUILDING_ROOMS`, `ROOM_FURNISHINGS`
- **Type:** DATA
- **Severity:** LOGIC
- **Description:** `_BUILDING_ROOMS["guild_hall"] = ["great_hall", "study", "storage", "armory"]`. The `"armory"` room type has no entry in `ROOM_FURNISHINGS`. It falls back to `["crate"]`, producing an armory with a single crate. Similarly, `_ROOM_LIGHTS` has no `"armory"` entry, so the room gets no lighting at all.

---

## Performance Bugs

### BUG-WB-017: Prim's MST implementation is O(n^3) in `_generate_roads`
- **File:** `settlement_generator.py`
- **Function:** `_generate_roads`, ~line 961-975
- **Type:** PERF
- **Severity:** PERF
- **Description:** The MST loop is `O(n^2)` per iteration, with `n-1` iterations = `O(n^3)` total. For a medieval_town with 40-80 buildings, this is 64,000-512,000 iterations. Not catastrophic but unnecessary. A priority queue (min-heap) would bring this to `O(n^2 log n)`. For settlements with 80+ buildings this becomes noticeable.

### BUG-WB-018: `_create_road_with_curbs` samples terrain height N+1 times per vertex plus redundant midpoint sampling
- **File:** `worldbuilding.py`
- **Function:** `_create_road_with_curbs`, ~line 2727-2739
- **Type:** PERF
- **Severity:** PERF
- **Description:** For terrain-snapped roads, each vertex samples the terrain height, AND there's a redundant midpoint sample at line 2732-2733:
  ```python
  base_z = _sample_scene_height(
      (sx + ex) / 2.0, (sy + ey) / 2.0, terrain_name
  )
  ```
  This midpoint sample is computed inside the per-vertex loop but uses the same values every iteration. It should be hoisted outside the loop. With `resolution=4` (default), that's 5 cross-sections * 7 columns = 35 vertices, each triggering a redundant midpoint raycast. For a settlement with 20+ roads, that's 700+ unnecessary raycasts.

### BUG-WB-019: `_place_buildings` has 80 placement attempts per building with O(n) collision checks
- **File:** `settlement_generator.py`
- **Function:** `_place_buildings`, ~line 807
- **Type:** PERF
- **Severity:** PERF (minor)
- **Description:** Each building attempt checks against all previously placed buildings. With 80 buildings (medieval_town), the worst case is `80 * 80 * 80 = 512,000` AABB overlap checks. Still fast in Python for these sizes, but could become a bottleneck for very large settlements.

---

## Coordinate / Scale Bugs

### BUG-WB-020: `building_interior_binding.align_rooms_to_building` uses `floor_idx * 3.5` hardcoded floor height
- **File:** `building_interior_binding.py`
- **Function:** `align_rooms_to_building`, ~line 200
- **Type:** DATA
- **Severity:** LOGIC
- **Description:** The floor height offset is hardcoded: `floor_y = bz + floor_idx * 3.5`. But `VB_BUILDING_PRESETS` define different `wall_height` values per building type (3.4m for rowhouse, 5.0m for shrine_minor, 6.0m for shrine_major, etc.). This means for buildings with tall walls (e.g., 6m), rooms on floor 1 will be at Z=3.5 instead of Z=6.0. The rooms will clip into the upper floor's geometry.

### BUG-WB-021: `building_interior_binding.generate_door_metadata` door Z position uses `floor * wall_height + 1.1`
- **File:** `building_interior_binding.py`
- **Function:** `generate_door_metadata`, ~line 275-289
- **Type:** DATA
- **Severity:** LOGIC (minor)
- **Description:** Door Z position is `bz + floor * wall_height + 1.1`. The `1.1` is the door center height. For a standard 2.2m door, the center should be at 1.1m, which is correct for ground floor doors. But for upper floors, the door Z is `bz + wall_height + 1.1` which assumes the upper floor starts at `wall_height`, not at `wall_height` + floor_slab_thickness. The door will be slightly too low relative to the actual floor slab. Minor visual issue.

---

## Missing Validation / Edge Cases

### BUG-WB-022: `subdivide_block_to_lots` has no guard against infinite recursion with degenerate polygons
- **File:** `_settlement_grammar.py`
- **Function:** `subdivide_block_to_lots` -> `_split`, ~line 460-493
- **Type:** LOGIC
- **Severity:** LOGIC
- **Description:** The recursion guard is `depth > 6` AND `area < effective_min * 2`. But if a degenerate polygon (zero area but non-empty vertex list) is passed, `_block_area` returns 0.0, which is `< effective_min * 2`, so recursion stops. However, the `0.0` area lot is still returned (line 491-492 check `half_area > 0.0`). The parent `subdivide_block_to_lots` will then produce a lot with `area: 0.0`, which could cause division-by-zero downstream if anything divides by lot area.

### BUG-WB-023: `generate_settlement` function signature requires checking
- **File:** `settlement_generator.py`
- **Function:** `generate_settlement`
- **Type:** DATA
- **Severity:** Need more context (function was not fully read)
- **Description:** The `generate_settlement` function is called from multiple places (`worldbuilding_layout.py`, `worldbuilding.py`) with different parameter sets. Need to verify parameter consistency, but the function body was not fully read due to file size limits. The integration points between `generate_settlement` output and `worldbuilding.py` consumption should be verified.

### BUG-WB-024: `_place_buildings` can silently produce fewer buildings than requested
- **File:** `settlement_generator.py`
- **Function:** `_place_buildings`, ~line 905-907
- **Type:** LOGIC
- **Severity:** LOGIC
- **Description:** If all 80 placement attempts fail for a building (due to collisions), the building is silently dropped:
  ```python
  if placed_building is not None:
      buildings.append(placed_building)
  ```
  No warning is logged. For dense settlements, this can mean significantly fewer buildings than the config's `building_count` range specifies. The caller (`generate_settlement`) may not know that placement failed.

### BUG-WB-025: `map_composer._find_valid_position` can return `None` silently for all POI types
- **File:** `map_composer.py`
- **Function:** `_find_valid_position`, ~line 430-500
- **Type:** LOGIC
- **Severity:** LOGIC
- **Description:** After `_MAX_PLACEMENT_ATTEMPTS = 500` failures, the function returns `None`. The caller must handle this, but if no POIs can be placed (e.g., heightmap doesn't match any biome preferences), the world map will be empty. This is by design but could be surprising with default parameters.

---

## String Key / Type Mismatches

### BUG-WB-026: `settlement_generator.SETTLEMENT_TYPES["hearthvale"]` uses `"portcullis_gate"` perimeter type not handled anywhere
- **File:** `settlement_generator.py`
- **Function:** `_generate_perimeter`, ~line 1768-1773
- **Type:** DATA
- **Severity:** LOGIC
- **Description:** `hearthvale` config has `"perimeter_props": ["wall_segment", "portcullis_gate", "corner_tower"]`. The `_generate_perimeter` function filters gate types by checking `"gate" in t`, which matches `"portcullis_gate"`. The gate_type becomes `"portcullis_gate"`. But downstream in `worldbuilding.py`, `_create_settlement_prop_cluster` and `_spawn_catalog_object` look up the type in `CASTLE_ELEMENT_MAP`, `DUNGEON_PROP_MAP`, `FURNITURE_GENERATOR_MAP`, and `PROP_GENERATOR_MAP`. If `"portcullis_gate"` is not in any of these maps, the gate will get a fallback volume cube instead of proper geometry.

### BUG-WB-027: Settlement generator uses `"cobblestone"` road style, but `_ROAD_PROPS` maps to generic props
- **File:** `settlement_generator.py`
- **Function:** `_scatter_settlement_props`, ~line 1062
- **Type:** DATA
- **Severity:** LOGIC (minor)
- **Description:** `_ROAD_PROPS["cobblestone"]` maps to `["lantern_post", "bench", "planter"]`. But `"planter"` is not a known prop type in any of the generator maps (`PROP_GENERATOR_MAP`, etc.). It will produce a fallback volume cube. Similarly, `"brazier"` and `"banner_stand"` and `"statue_small"` from the `"stone"` road style, and `"torch_post"` and `"milestone"` from `"dirt_path"` may not have generators.

### BUG-WB-028: `_SCATTER_PROPS` contains types unlikely to have generators
- **File:** `settlement_generator.py`
- **Function:** `_scatter_settlement_props`, ~line 534-538
- **Type:** DATA
- **Severity:** LOGIC (minor)
- **Description:** `_SCATTER_PROPS = ["rock_small", "rock_medium", "debris_pile", "dead_bush", "fallen_log", "mushroom_cluster", "bone_scatter"]`. Most of these prop types likely don't have entries in the generator maps. They'll all become fallback volume cubes, producing a field of identical gray boxes instead of environmental scatter.

---

## Seed Determinism Issues

### BUG-WB-029: `handle_generate_town` pollutes global random state
- **File:** `worldbuilding_layout.py`
- **Function:** `handle_generate_town`, ~line 498-501
- **Type:** DATA
- **Severity:** LOGIC
- **Description:** (Duplicate of BUG-WB-008, listed here for completeness in seed determinism section.) Uses `random.seed(seed + i)` on the global `random` module instead of a local `Random` instance. This affects all subsequent calls to the global `random` module, breaking determinism for any code that runs after this function.

### BUG-WB-030: `_generate_landmark_unique_features` creates its own RNG with `import random as _random`
- **File:** `worldbuilding.py`
- **Function:** `_generate_landmark_unique_features`, ~line 4285-4286
- **Type:** DATA
- **Severity:** LOGIC (minor)
- **Description:** This function imports the random module inside the function body and creates `rng = _random.Random(seed)`. This is fine for local use, but the import-inside-function pattern is unusual. More importantly, the `seed` parameter is the only source of variation -- if two landmarks share the same seed, they get identical random unique features.

---

## Summary Table

| ID | File | Severity | Type | Description |
|----|------|----------|------|-------------|
| WB-001 | settlement_generator.py | CRASH (potential) | DATA | `rng.uniform(a, b)` with swapped bounds in small rooms |
| WB-002 | settlement_generator.py | LOGIC | DATA | Missing `"armory"` room furnishing config |
| WB-003 | worldbuilding.py | LOGIC | DATA | Stale `_PROP_CACHE` across Blender sessions |
| WB-004 | building_interior_binding.py | LOGIC | DATA | Room type vocabulary mismatch between binding and settlement systems |
| WB-006 | settlement_generator.py | LOGIC | LOGIC | `"concentric_organic"` layout pattern falls through to organic |
| WB-007 | settlement_generator.py | LOGIC | DATA | Hearthvale temple not treated as priority shrine |
| WB-008 | worldbuilding_layout.py | LOGIC | DATA | Global random state pollution |
| WB-010 | settlement_generator.py | LOGIC (fragile) | DATA | Inconsistent 2-tuple vs 3-tuple road positions |
| WB-012 | _settlement_grammar.py | LOGIC (minor) | LOGIC | Uniform prop spacing ignores district variation |
| WB-014 | Cross-file | LOGIC | DATA | Two parallel building type vocabularies conflict |
| WB-015 | worldbuilding.py | LOGIC | DATA | Missing presets for 8 building types |
| WB-016 | settlement_generator.py | LOGIC | DATA | `"armory"` has no furnishing OR lighting |
| WB-017 | settlement_generator.py | PERF | PERF | O(n^3) MST for large settlements |
| WB-018 | worldbuilding.py | PERF | PERF | Redundant terrain raycasts in road loop |
| WB-020 | building_interior_binding.py | LOGIC | DATA | Hardcoded 3.5m floor height ignores preset wall_height |
| WB-022 | _settlement_grammar.py | LOGIC | LOGIC | Zero-area lots can propagate |
| WB-024 | settlement_generator.py | LOGIC | LOGIC | Silent building placement failures |
| WB-026 | settlement_generator.py | LOGIC | DATA | `"portcullis_gate"` may have no generator |
| WB-027 | settlement_generator.py | LOGIC (minor) | DATA | Several road prop types have no generators |
| WB-028 | settlement_generator.py | LOGIC (minor) | DATA | Scatter prop types produce fallback cubes |

**Total bugs found: 20 confirmed, 2 noted as non-issues after review**

**Priority fixes:**
1. **WB-006** (concentric_organic fallback) -- Hearthvale and medieval_town layouts are broken
2. **WB-020** (hardcoded floor height) -- Multi-floor interiors clip into geometry
3. **WB-007** (temple not treated as shrine) -- Hearthvale layout missing central temple
4. **WB-004 + WB-015** (vocabulary mismatches) -- 8+ building types generate with wrong configs
5. **WB-008** (global random pollution) -- Non-deterministic builds
6. **WB-003** (stale prop cache) -- Silent failures after file reload
