# Phase 45: Data Safety & Integrity - Research

**Researched:** 2026-04-04
**Domain:** Pipeline data integrity, atomic writes, texture preservation, spatial semantics, scene hierarchy scoping
**Confidence:** HIGH

## Summary

Phase 45 fixes six data-safety bugs across the Tripo texture pipeline, compose_interior spatial planning, settlement scaling, and scene hierarchy export. These are not architectural rewrites -- they are surgical fixes to well-understood code paths where data is silently lost, overwritten, or miscomputed.

The highest-impact bug is SAFE-01 (Tripo texture overwrite): `generate_and_process()` in `pipeline_runner.py` calls `full_asset_pipeline()` without extracting textures from the GLB first, so the pipeline falls back to creating blank PBR materials that replace the model's embedded textures. The `generate_3d` action in `blender_server.py` already has the correct post-processing code -- the fix is to replicate that texture extraction logic in `generate_and_process()` before calling the pipeline.

The remaining five bugs are all in `blender_server.py` and its supporting modules (`pipeline_state.py`, `building_interior_binding.py`, `settlement_generator.py`). Each is a localized logic fix: adding checkpoint guards, respecting binding geometry, implementing floor-aware Z offsets, adding building count overrides, and scoping the scene hierarchy to map objects only.

**Primary recommendation:** Fix each bug surgically in its source file, add targeted unit tests for the specific behavior, and run the full 19,850+ test suite to verify no regressions.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SAFE-01 | Fix Tripo texture overwrite (cleanup overwrites embedded textures with blanks) | `generate_and_process()` at pipeline_runner.py:1278 does not call `post_process_tripo_model()` or pass `has_extracted_textures=True` to `full_asset_pipeline()`. The `generate_3d` action at blender_server.py:2351 has the correct pattern. |
| SAFE-02 | Fix checkpoint atomicity (interior_results guard + atomic writes via temp+rename) | `pipeline_state.py` save function already uses atomic temp+rename (line 80-87). The remaining bug is `interior_results = []` at blender_server.py:3154 -- already inside guard but needs to append rather than reset when partially populated from checkpoint. |
| SAFE-03 | Fix compose_interior discarding binding geometry | `_plan_interior_rooms()` at blender_server.py:927 replans from spec width/depth/height only, ignoring `building_interior_binding.align_rooms_to_building()` output. compose_interior should accept and prefer pre-aligned room data. |
| SAFE-04 | Fix multi-floor interior semantics (Z=0 flat, not multi-level) | `_plan_interior_rooms()` hardcodes Z=0.0 at lines 992 and 1029. Must read room `floor` field and compute `floor * floor_height` Z offsets, matching the logic in `building_interior_binding.align_rooms_to_building()` line 200. |
| SAFE-05 | Fix settlement scaling mismatch (village=4-8 vs plan=15, city=20-40 vs plan=100+) | `SETTLEMENT_TYPES` in settlement_generator.py defines fixed ranges. `_build_location_generation_params()` at blender_server.py:427-429 does not pass a `building_count` override. Settlement generator needs to accept and honor an explicit count. |
| SAFE-06 | Fix scene_hierarchy.json not map-scoped (leaks helpers/unrelated objects) | `emit_scene_hierarchy()` at pipeline_state.py:298 iterates ALL `bpy.data.objects`. Must filter to only objects in the map's `created_objects` list or matching location_results names. |
| TEST-04 | Opus verification scan after every phase -- follow-up rounds until CLEAN | Existing test infrastructure: 243 relevant tests across 4 test files covering pipeline_state, building_interior_binding, tripo_post_processor, settlement_generator. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Always verify visually after Blender mutations
- Pipeline order: repair -> UV -> texture -> rig -> animate -> export. Do not skip steps.
- Use seeds for reproducible environment/worldbuilding generation
- All agents have access to MCP tools (Context7, zread, Episodic Memory, etc.)
- Prefer MCP tools over raw Grep/Glob when they fit
- Bug scan after every phase, follow-up rounds until CLEAN

## Architecture Patterns

### Affected File Map

```
Tools/mcp-toolkit/
  src/veilbreakers_mcp/
    blender_server.py           # SAFE-01 (generate_3d), SAFE-03/04 (_plan_interior_rooms),
                                # SAFE-05 (_build_location_generation_params)
    shared/
      pipeline_runner.py        # SAFE-01 (generate_and_process)
      tripo_post_processor.py   # SAFE-01 (already correct, needs to be called)
      glb_texture_extractor.py  # SAFE-01 (already correct, needs to be called)
  blender_addon/handlers/
    pipeline_state.py           # SAFE-02 (save_pipeline_checkpoint), SAFE-06 (emit_scene_hierarchy)
    building_interior_binding.py # SAFE-03/04 (align_rooms_to_building, generate_interior_spec_from_building)
    settlement_generator.py     # SAFE-05 (SETTLEMENT_TYPES, generate_settlement)
  tests/
    test_pipeline_state.py      # Existing: 25 tests
    test_building_interior_binding.py # Existing: ~50 tests
    test_tripo_post_processor.py     # Existing: tests for extraction + scoring
    test_settlement_generator.py     # Existing: ~80 tests
```

### Pattern 1: Tripo Texture Preservation (SAFE-01)

**What:** `generate_and_process()` must extract textures BEFORE calling `full_asset_pipeline()`.

**Root cause:** Line 1278 in `pipeline_runner.py` calls `self.full_asset_pipeline(object_name=model_path, ...)` without `has_extracted_textures=True` or `texture_channels=<extracted>`. The pipeline's cleanup step 7 falls through to `texture_create_pbr` which creates a blank Principled BSDF, silently replacing the model's embedded PBR textures.

**The correct pattern already exists** in `blender_server.py` lines 2345-2364 (studio path) and 2412-2432 (API key path): call `post_process_tripo_model()` to extract textures, then pass `has_extracted_textures=True` and `texture_channels` to the pipeline.

**Fix location:** `pipeline_runner.py` `generate_and_process()`, between lines 1275 and 1278. Insert texture extraction, then pass results to `full_asset_pipeline()`.

```python
# After model validation passes, extract textures before pipeline:
from veilbreakers_mcp.shared.tripo_post_processor import post_process_tripo_model
post_result = await post_process_tripo_model(
    model_path, str(Path(output_dir) / "textures"),
    asset_type=asset_type,
)
extracted_channels = post_result.get("channels", {})
if post_result.get("albedo_delit"):
    extracted_channels["albedo_delit"] = post_result["albedo_delit"]

pipeline_result = await self.full_asset_pipeline(
    object_name=model_path,
    asset_type=asset_type,
    has_extracted_textures=bool(extracted_channels),
    texture_channels=extracted_channels if extracted_channels else None,
    export_dir=pipeline_kwargs.pop("export_dir", output_dir),
    **pipeline_kwargs,
)
```

### Pattern 2: Checkpoint Interior Results Guard (SAFE-02)

**What:** Ensure `interior_results` is not reset when resuming from checkpoint.

**Current state:** `pipeline_state.py` `save_pipeline_checkpoint()` already uses atomic temp+rename (lines 80-87). The original BUG-CHKPT-01 was already partially fixed: `interior_results = []` was moved inside the `"interiors_generated" not in steps_completed` guard (line 3154). However, the issue is that this STILL resets `interior_results` to `[]` even when partial interior data was loaded from checkpoint but the step wasn't marked complete.

**Fix:** Only reset if NOT resuming with partial interior data:
```python
if "interiors_generated" not in steps_completed:
    if not interior_results:  # Only reset if empty (not loaded from checkpoint)
        interior_results = []
```

### Pattern 3: Binding Geometry Preservation (SAFE-03)

**What:** `compose_interior` should use pre-aligned room data from `building_interior_binding` when available.

**Root cause:** `compose_interior` calls `_plan_interior_rooms(spec)` which replans from scratch using only `width`/`depth`/`height` from the spec rooms. If `building_interior_binding.generate_interior_spec_from_building()` was used to create the spec, the rooms already have `position` and `bounds` fields set correctly -- but `_plan_interior_rooms` ignores them entirely.

**Fix:** In `_plan_interior_rooms()`, check if rooms already have valid `bounds` data. If all rooms have pre-set bounds (from binding), use those directly instead of replanning:

```python
def _plan_interior_rooms(interior_spec: dict) -> dict:
    rooms = list(interior_spec.get("rooms", []))
    doors = list(interior_spec.get("doors", []))
    if not rooms:
        return {"rooms": [], "doors": [], "building_bounds": {...}}
    
    # Check if rooms already have pre-computed bounds from binding
    all_have_bounds = all(
        room.get("bounds") and room.get("position")
        for room in rooms
    )
    if all_have_bounds:
        return _use_precomputed_bounds(rooms, doors)
    
    # ... existing replanning logic ...
```

### Pattern 4: Multi-Floor Z Offsets (SAFE-04)

**What:** `_plan_interior_rooms()` must compute floor-aware Z coordinates.

**Root cause:** `candidate_bounds()` at lines 992 and 1029 hardcodes `0.0` for the Z component of bounds min/max. The `floor` field from `building_interior_binding.BUILDING_ROOM_MAP` (e.g., `"floor": -1` for cellars, `"floor": 1` for upstairs) is never read.

**Fix:** Read `floor` from room spec, compute `floor_z = floor * floor_height`, use in bounds:
```python
floor = float(target.get("floor", 0))
floor_height = float(target.get("height", 3.5))
floor_z = floor * floor_height
# In bounds:
"min": (round(min_x, 3), round(min_y, 3), round(floor_z, 3)),
"max": (round(min_x + width, 3), round(min_y + depth, 3), round(floor_z + height, 3)),
```

This matches the existing logic in `building_interior_binding.align_rooms_to_building()` line 200: `floor_y = bz + floor_idx * 3.5`.

### Pattern 5: Settlement Count Override (SAFE-05)

**What:** Allow `compose_map` to override the `building_count` range in `SETTLEMENT_TYPES`.

**Root cause:** `settlement_generator.py` `SETTLEMENT_TYPES` defines fixed ranges (e.g., `village: (4,8)`, `city: (20,40)`). The `generate_settlement()` function reads from `SETTLEMENT_TYPES` and there is no parameter to override the count. `_build_location_generation_params()` in `blender_server.py` (line 427-429) passes `settlement_type` and `radius` but no `building_count`.

**Fix (two parts):**

1. In `settlement_generator.py` `generate_settlement()`, accept optional `building_count_override` parameter:
```python
def generate_settlement(
    settlement_type="town", ..., building_count_override=None,
):
    config = dict(SETTLEMENT_TYPES[settlement_type])
    if building_count_override is not None:
        config["building_count"] = (building_count_override, building_count_override)
    ...
```

2. In `blender_server.py` `_build_location_generation_params()`, pass through the location's building_count:
```python
elif loc_type == "settlement":
    params["settlement_type"] = location.get("settlement_type", "town")
    params["radius"] = location.get("radius", 50.0)
    if "building_count" in location:
        params["building_count_override"] = location["building_count"]
```

### Pattern 6: Map-Scoped Scene Hierarchy (SAFE-06)

**What:** `emit_scene_hierarchy()` must only include objects that belong to the current map.

**Root cause:** `pipeline_state.py` line 298 iterates `bpy.data.objects` (ALL objects in the scene). Name-substring matching for district assignment (line 306) can match helpers, cameras, lights, and objects from other maps.

**Fix:** Accept a `created_objects` whitelist parameter and filter:
```python
def emit_scene_hierarchy(
    map_name: str,
    location_results: list[dict],
    created_objects: list[str] | None = None,
) -> dict:
    ...
    whitelist = set(created_objects) if created_objects else None
    objects = []
    for obj in bpy.data.objects:
        if obj.type not in {"MESH", "EMPTY", "LIGHT", "CAMERA"}:
            continue
        if whitelist and obj.name not in whitelist:
            # Check if any whitelisted name is a parent prefix
            if not any(obj.name.startswith(wl) for wl in whitelist):
                continue
        ...
```

Then update the caller in `blender_server.py` `generate_map_package` (line 3328) to pass `created_objects`:
```python
_hierarchy = _emit_hierarchy(_mp_name, _mp_locations, created_objects=_mp_objects)
```

### Anti-Patterns to Avoid
- **Resetting lists inside checkpoint guards:** Clearing `interior_results = []` inside a step guard destroys partial checkpoint data. Always check if the list already has data from checkpoint before resetting.
- **Assuming all bpy.data.objects belong to current operation:** Blender scenes can contain leftover objects. Always filter by an explicit whitelist.
- **Ignoring pre-computed spatial data:** When a binding module computes room positions relative to a building, do not recompute from scratch in the consumer. Use the pre-computed data when available.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file writes | Custom file locking | `tempfile.mkstemp` + `os.replace` | `os.replace` is atomic on all platforms; already implemented in `pipeline_state.py` |
| GLB texture extraction | Manual binary parsing | `glb_texture_extractor.extract_glb_textures()` | Already handles pygltflib/struct fallback, multi-material, channel mapping |
| Texture post-processing | Manual de-lighting | `tripo_post_processor.post_process_tripo_model()` | Already handles extraction, de-lighting, palette validation, scoring |
| Building interior specs | Manual room layout | `building_interior_binding.generate_interior_spec_from_building()` | Already handles room-type mapping, spatial alignment, multi-floor, door metadata |

## Common Pitfalls

### Pitfall 1: Tripo Texture Channels Lost Through Pipeline Chain
**What goes wrong:** GLB textures are extracted correctly but then overwritten by blank PBR material creation in cleanup step.
**Why it happens:** The `has_extracted_textures` flag defaults to `False` -- any call path that omits it silently destroys textures.
**How to avoid:** Every code path that calls `cleanup_ai_model()` or `full_asset_pipeline()` on a model with embedded textures MUST extract first and pass `has_extracted_textures=True` + `texture_channels`.
**Warning signs:** Models appearing pure grey/blank after pipeline processing.

### Pitfall 2: Checkpoint Resume Destroying Partial Data
**What goes wrong:** Pipeline resumes from checkpoint but partial results arrays are reset to empty.
**Why it happens:** Code resets arrays inside the step guard but before checking if checkpoint data was loaded.
**How to avoid:** Always gate resets on `not already_loaded_from_checkpoint`.
**Warning signs:** Interior/location results missing after a resume despite the checkpoint containing them.

### Pitfall 3: Multi-Floor Rooms All Rendered At Z=0
**What goes wrong:** Tavern cellar, upstairs room, tower upper floors -- all placed at ground level, overlapping.
**Why it happens:** `_plan_interior_rooms()` ignores `floor` field in room specs and hardcodes Z=0.0.
**How to avoid:** Read `floor` field, compute Z offset as `floor * floor_height`.
**Warning signs:** Room geometry overlapping at origin; cellar visible above ground.

### Pitfall 4: Settlement Building Count Ignoring Plan Specification
**What goes wrong:** Map plan requests 15 buildings for a village but only 4-8 are generated.
**Why it happens:** `SETTLEMENT_TYPES` hard-caps the range and there is no override mechanism.
**How to avoid:** Add explicit `building_count_override` parameter that bypasses the type default.
**Warning signs:** Generated settlements appearing much smaller than the map plan intended.

### Pitfall 5: Scene Hierarchy JSON Including Stale Objects
**What goes wrong:** Export includes cameras, lights, helper empties, and objects from previous maps.
**Why it happens:** `bpy.data.objects` contains everything in the .blend file, not just the current map.
**How to avoid:** Pass whitelist of `created_objects` from `compose_map` tracking.
**Warning signs:** Unity import loading unexpected objects; hierarchy JSON much larger than expected.

## Code Examples

### Current Tripo generate_and_process (BUG -- no texture extraction)
```python
# pipeline_runner.py line 1277-1283
# BUG: Calls full_asset_pipeline without extracting textures first
pipeline_result = await self.full_asset_pipeline(
    object_name=model_path,
    asset_type=asset_type,
    export_dir=pipeline_kwargs.pop("export_dir", output_dir),
    **pipeline_kwargs,
)
```

### Correct Pattern (from blender_server.py generate_3d)
```python
# blender_server.py lines 2345-2363
# CORRECT: Extracts textures BEFORE pipeline
post_result = await post_process_tripo_model(
    m["path"], glb_out_dir,
    asset_type=asset_type or "prop",
)
m["texture_channels"] = post_result.get("channels", {})
if post_result.get("albedo_delit"):
    m["texture_channels"]["albedo_delit"] = post_result["albedo_delit"]
# Then passed to cleanup via has_extracted_textures=true
```

### Current _plan_interior_rooms Z=0 Bug
```python
# blender_server.py line 992
"bounds": {
    "min": (round(min_x, 3), round(min_y, 3), 0.0),           # <-- hardcoded Z=0
    "max": (round(min_x + width, 3), round(min_y + depth, 3), round(height, 3)),
},
```

### Correct Multi-Floor Pattern (from building_interior_binding.py)
```python
# building_interior_binding.py line 200
floor_y = bz + floor_idx * 3.5  # 3.5m per floor
# Rooms get correct vertical positions
```

### Current Settlement Types (Fixed Ranges)
```python
# settlement_generator.py
SETTLEMENT_TYPES = {
    "village":  {"building_count": (4, 8), ...},
    "town":     {"building_count": (8, 16), ...},
    "city":     {"building_count": (20, 40), ...},
    "medieval_town": {"building_count": (40, 80), ...},
    "hearthvale": {"building_count": (14, 14), ...},
}
```

### Current emit_scene_hierarchy (Unscoped)
```python
# pipeline_state.py line 298
for obj in bpy.data.objects:  # ALL objects, not just map objects
    if obj.type not in {"MESH", "EMPTY", "LIGHT", "CAMERA"}:
        continue
    # No whitelist filtering
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `Tools/mcp-toolkit/pyproject.toml` |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_pipeline_state.py tests/test_building_interior_binding.py tests/test_tripo_post_processor.py tests/test_settlement_generator.py -x` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x --timeout=60` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SAFE-01 | generate_and_process extracts textures before pipeline | unit | `pytest tests/test_tripo_post_processor.py -x` | Partial -- needs new test for pipeline integration |
| SAFE-02 | interior_results preserved on checkpoint resume | unit | `pytest tests/test_pipeline_state.py -x` | Partial -- needs new test for resume-with-partial-data |
| SAFE-03 | compose_interior uses pre-aligned binding bounds | unit | `pytest tests/test_building_interior_binding.py -x` | Partial -- needs test for _plan_interior_rooms with pre-set bounds |
| SAFE-04 | Multi-floor rooms get correct Z offsets | unit | `pytest tests/test_building_interior_binding.py -x` | Partial -- needs test for Z offset in _plan_interior_rooms |
| SAFE-05 | Settlement accepts building_count override | unit | `pytest tests/test_settlement_generator.py -x` | Partial -- needs test for override mechanism |
| SAFE-06 | emit_scene_hierarchy respects whitelist | unit | `pytest tests/test_pipeline_state.py -x` | No -- needs new test |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/test_pipeline_state.py tests/test_building_interior_binding.py tests/test_tripo_post_processor.py tests/test_settlement_generator.py -x`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x --timeout=60`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_tripo_post_processor.py` -- add test: `test_generate_and_process_extracts_textures_before_pipeline`
- [ ] `tests/test_pipeline_state.py` -- add test: `test_interior_results_preserved_on_resume`
- [ ] `tests/test_pipeline_state.py` -- add test: `test_emit_scene_hierarchy_respects_whitelist`
- [ ] `tests/test_building_interior_binding.py` or `tests/test_compose_planners.py` -- add test: `test_plan_interior_rooms_uses_precomputed_bounds`
- [ ] `tests/test_building_interior_binding.py` or `tests/test_compose_planners.py` -- add test: `test_plan_interior_rooms_multi_floor_z_offsets`
- [ ] `tests/test_settlement_generator.py` -- add test: `test_building_count_override`

## Sources

### Primary (HIGH confidence)
- Direct code audit of `pipeline_runner.py` (lines 85-230, 1120-1290)
- Direct code audit of `blender_server.py` (lines 927-1040, 2264-2460, 2930-3180, 3526-3650)
- Direct code audit of `pipeline_state.py` (lines 40-97, 268-335)
- Direct code audit of `building_interior_binding.py` (lines 1-370)
- Direct code audit of `settlement_generator.py` (lines 1-240)
- Direct code audit of `tripo_post_processor.py` (full file)
- Direct code audit of `glb_texture_extractor.py` (full file)
- V9_MASTER_FINDINGS.md sections 16.4, 16.19, 19.2

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all fixes are within existing codebase, no new dependencies
- Architecture: HIGH -- code paths fully traced, root causes identified with line numbers
- Pitfalls: HIGH -- each bug verified by code reading, patterns from existing correct code

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable codebase, internal fixes only)
