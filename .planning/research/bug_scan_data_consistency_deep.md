# Deep Bug Scan: String Formatting, Data Consistency, Configuration, Numeric Precision

**Date:** 2026-04-02
**Scope:** Entire `Tools/mcp-toolkit/` codebase (458 .py files, excluding .venv)
**Focus:** String/f-string bugs, data structure cross-references, config mismatches, numeric precision
**Previous scans:** ~163 bugs already reported across 11 prior scan files. Only NEW bugs below.

---

## MISSION 1: String/f-string Bugs

### BUG-STR-01: No new f-string escaping bugs found [CLEAN]

All 65+ f-strings containing double braces `{{...}}` in Unity templates correctly escape C# braces. The pattern `f'... {{ ... }}'` correctly outputs literal `{...}` in generated C# code. Verified across:
- animation_templates.py (blend trees, additive layers)
- build_templates.py (build results JSON)
- code_templates.py (service locator, state machine, game events)
- encounter_templates.py (boss phases, simulation)
- pipeline_templates.py (normal map baking)

The `pipeline_templates.py:302` pattern `f"...{{HIGH_POLY}}..."` inside a triple-quoted f-string is correct: it generates a Blender Python script where `HIGH_POLY` is a local variable, so the literal `{HIGH_POLY}` in the output is an f-string in the generated script.

### BUG-STR-02: No `.format()` mismatches found [CLEAN]

Only 2 `.format()` calls in production code:
1. `_settlement_grammar.py:142` -- `template.format(corruption_desc=desc)` -- verified: all 8 PROP_PROMPTS templates contain exactly one `{corruption_desc}` placeholder. Correct.
2. `security.py:124` -- comment only, not a call.

### BUG-STR-03: No type-mixing string concatenation found [CLEAN]

No instances of `str + int` or `str + float` concatenation found in the codebase. All string building uses f-strings or list-join patterns.

---

## MISSION 2: Data Consistency

### BUG-DATA-01: "market" room type missing from _ROOM_CONFIGS [MEDIUM]
- **File:** `_building_grammar.py` / `settlement_generator.py`
- **Evidence:**
  - `settlement_generator.py:449` maps `"general_store"` to rooms `["market", "storage", "storage"]`
  - `settlement_generator.py:433` maps `"market_stall_cluster"` to rooms `["market"]`
  - `settlement_generator.py:1365` has lighting config for `"market"` room type
  - `_building_grammar.py` has NO `"market"` key in `_ROOM_CONFIGS`
- **Impact:** When `_ROOM_CONFIGS.get("market", [])` is called (line 2901), it returns `[]`. The room gets no furniture placed. General stores and market stall clusters have empty interiors.
- **Fix:** Add a `"market"` entry to `_ROOM_CONFIGS` with appropriate furniture (market_stall, crate, barrel, sack, shelf, signpost).

### BUG-DATA-02: "prison" room type missing from _ROOM_CONFIGS [MEDIUM]
- **File:** `_building_grammar.py` / `settlement_generator.py`
- **Evidence:**
  - `settlement_generator.py:437` maps `"cage"` building to rooms `["prison"]`
  - `settlement_generator.py:418` has prop list for `"prison"` room type
  - `settlement_generator.py:1355` has lighting config for `"prison"` room type
  - `_building_grammar.py` has `"dungeon_cell"` but NO `"prison"` key in `_ROOM_CONFIGS`
- **Impact:** Cage buildings in bandit camps get empty prison rooms (no furniture). The `_LANDMARK_ROOM_TYPE_MAP` (worldbuilding.py:458) correctly maps `"prison"` -> `"dungeon_cell"` for landmarks, but the settlement_generator's `_BUILDING_ROOMS` bypasses that mapping.
- **Fix:** Either add `"prison"` as a key in `_ROOM_CONFIGS` (with chains, shackle, bucket, cot), OR change `_BUILDING_ROOMS["cage"]` to `["dungeon_cell"]`.

### BUG-DATA-03: "generic" room type in building_interior_binding.py has no _ROOM_CONFIGS entry [LOW]
- **File:** `building_interior_binding.py:65`
- **Evidence:** `BUILDING_ROOM_MAP["ruin"]` references `{"type": "generic", ...}`. No `"generic"` key exists in `_ROOM_CONFIGS`.
- **Impact:** Ruin buildings get an empty main_chamber with no furniture. For ruins this is arguably acceptable, but the intent seems to be at least some debris/rubble.
- **Fix:** Either add a `"generic"` entry to `_ROOM_CONFIGS` with minimal debris props, or change the type to an existing room like `"storage"` or `"dungeon_cell"`.

### BUG-DATA-04: 13 room types in _ROOM_CONFIGS have no ROOM_SPATIAL_GRAPHS entry [LOW - COMPLETENESS GAP]
- **File:** `_building_grammar.py`
- **Missing ROOM_SPATIAL_GRAPHS for:** armory, barracks, dungeon_cell, guard_barracks, guard_post, guild_hall, manor, shrine_room, storage, study, tavern_hall, torture_chamber, treasury
- **Impact:** These rooms fall back to basic random placement (line 2917: `spatial = ROOM_SPATIAL_GRAPHS.get(room_type)` returns None). Furniture is placed without spatial relationship awareness (no clusters, no focal points, no wall preferences). Results in less realistic layouts.
- **Severity:** LOW because the fallback placement still works, just less intelligently.

### BUG-DATA-05: VB_BIOME_PRESETS scatter assets have no generator validation [LOW - DESIGN]
- **File:** `environment.py`
- **Evidence:** Scatter rules reference 30+ unique asset types (`tree_healthy`, `poison_pool`, `crystal_shard`, `void_tendril`, `floating_rock`, `gravestone`, `fog_emitter`, etc.) but there is no validation that scatter assets have corresponding Blender generators. These are placeholder names that require actual asset creation.
- **Impact:** Runtime behavior depends on how the scatter engine handles missing assets. If it silently skips, biomes will be sparser than designed. If it errors, biome generation fails.
- **Severity:** LOW -- this is a content pipeline issue, not a code bug.

### BUG-DATA-06: LOD_PRESETS consistency check [CLEAN]
All LOD_PRESETS verified:
- **Ratios:** Monotonically decreasing for all 8 asset types (1.0 -> 0.5 -> 0.25 -> 0.1 etc.)
- **Screen percentages:** Monotonically decreasing for all 8 asset types
- **Min tris:** Reasonable values -- hero_character (30000 -> 3000), standard_mob (8000 -> 800), vegetation (5000 -> 4, billboard quad)
- **Array lengths:** All internal arrays are consistent length within each preset

### BUG-DATA-07: MATERIAL_LIBRARY / TERRAIN_MATERIALS / BIOME_PALETTES cross-reference [CLEAN]
All 70+ material keys referenced in BIOME_PALETTES exist in either TERRAIN_MATERIALS or MATERIAL_LIBRARY:
- `"mud"` and `"moss"` correctly resolve to MATERIAL_LIBRARY entries
- All terrain-specific materials (dark_leaf_litter, black_mud, gravel, etc.) are in TERRAIN_MATERIALS
- All RGB values are in 0-1 range
- All roughness/metallic values are in 0-1 range

### BUG-DATA-08: BIOME_PALETTES_V2 zone consistency [CLEAN]
All 14 V2 biomes have all 4 required zones (ground, slope, cliff, special). All material parameter values are in valid ranges.

### BUG-DATA-09: ROOM_ACTIVITY_ZONES fraction validation [CLEAN]
All 13 room types with activity zones have fractions that sum to exactly 1.0.

---

## MISSION 3: Configuration Mismatches

### BUG-CFG-01: .mcp.json server configuration [CLEAN]
- Both `vb-blender` and `vb-unity` servers correctly configured
- Environment variables properly use `${VAR}` syntax
- FAL_KEY present in vb-blender env (was missing in prior audit, now fixed)
- No stale server references

### BUG-CFG-02: pyproject.toml dependency analysis
- All 9 direct dependencies listed
- `httpx` used directly but NOT listed (previously reported in BUG-CFG-01 of security_edge_cases scan -- SKIP)
- Version pins use `>=` floor pins (acceptable for development, not for production)
- No conflicting version requirements detected

### BUG-CFG-03: No actionable TODO/FIXME/HACK comments in production code [CLEAN]
- Only instance: `gameplay_templates.py:775` has `// TODO: Implement {safe_nt} logic` inside a **generated C# string** (a template placeholder comment). Not a real TODO in the Python code.
- All other matches are in test files, code reviewer rules (detecting TODOs), or comments explaining security rationale. No forgotten/stale TODOs found.

---

## MISSION 4: Numeric Precision

### BUG-NUM-01: Float equality comparisons [CLEAN - MINOR]
Only 3 float equality checks found:
1. `character_advanced.py:1805` -- `motion_range[0] != 0.0 or motion_range[1] != 0.0` -- comparing user-provided config values, not computed floats. Safe.
2. `rigging_weights.py:415` -- `roll == 0.0` -- checking for default bone roll, which is exactly 0.0 when unmodified. Safe.
3. `vegetation_lsystem.py:1025` -- `angle_deg == 0.0` -- checking user parameter, not computed value. Safe.

### BUG-NUM-02: Integer vs float division [CLEAN]
- `animation_blob.py:367` -- `mid = len(BLOB_SPINE_BONES) / 2` -- produces float, used for proportional distance calculation (not indexing). Correct.
- All angle computations use `math.pi / N` which is float division. Correct.

### BUG-NUM-03: Angle unit consistency [CLEAN]
All Blender handler code consistently uses radians (via `math.pi`, `math.sin()`, `math.cos()`). No mixing of degrees and radians detected. Where degrees are used for user-facing parameters, they're explicitly converted.

### BUG-NUM-04: Y/Z axis confusion between Blender and Unity [CLEAN]
- Blender code uses Z-up consistently (`.co.z` for height)
- Unity template code uses Y-up consistently (`_velocity.y` for gravity, `position.y` for height)
- Export handlers (animation_export.py) correctly convert coordinate systems

### BUG-NUM-05: Veil crack zone has metallic=0.50 on slope layer [LOW - DESIGN]
- **File:** `terrain_materials.py:1843`
- **Value:** `"metallic": 0.50` for veil_crack_zone slope ("Crystal surfaces")
- **Context:** All other terrain materials have metallic between 0.0 and 0.30. A metallic value of 0.50 is unusually high for terrain but may be intentional for crystal/void aesthetics.
- **Impact:** May look unrealistic under certain lighting conditions.

---

## Summary

| ID | Severity | Category | Description |
|----|----------|----------|-------------|
| DATA-01 | MEDIUM | Data | "market" room type missing from _ROOM_CONFIGS -- empty general stores |
| DATA-02 | MEDIUM | Data | "prison" room type missing from _ROOM_CONFIGS -- empty cage interiors |
| DATA-03 | LOW | Data | "generic" room type in building_interior_binding has no _ROOM_CONFIGS entry |
| DATA-04 | LOW | Completeness | 13 room types lack ROOM_SPATIAL_GRAPHS (fallback to random placement) |
| DATA-05 | LOW | Design | VB_BIOME_PRESETS scatter assets not validated against generators |
| NUM-05 | LOW | Design | Veil crack zone metallic=0.50 may look unrealistic |

**New bugs found: 6** (2 MEDIUM, 4 LOW)
**Areas verified clean: 15** (string formatting, f-strings, LOD presets, material cross-refs, biome palettes, zone fractions, axis conventions, angle units, float equality, config files, TODO scanning, etc.)

### Priority Fix Order
1. **DATA-01** + **DATA-02**: Add "market" and "prison" entries to `_ROOM_CONFIGS` in `_building_grammar.py`
2. **DATA-03**: Add "generic" or remap "ruin" rooms in `building_interior_binding.py`
3. **DATA-04**: Add ROOM_SPATIAL_GRAPHS for the 13 missing room types (quality improvement, not blocking)
