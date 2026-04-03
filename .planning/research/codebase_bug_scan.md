# VeilBreakers MCP Toolkit - Comprehensive Bug Scan

**Date:** 2026-04-02
**Test suite:** 19,348 passed, 1 skipped (173.27s)
**Files scanned:** ~120 source files (src/ + blender_addon/ + tests/)

---

## CRASH Bugs (will throw exceptions at runtime)

### BUG-01: CRASH - TripoStudioClient wrong kwarg in generate_prop action
**File:** `src/veilbreakers_mcp/blender_server.py`, line 2558
**Severity:** CRASH
**Confirmed:** Yes (live test: `TypeError: TripoStudioClient.__init__() got an unexpected keyword argument 'jwt_token'`)

The `generate_prop` action constructs `TripoStudioClient` with `jwt_token=` but the constructor expects `session_token=`.

```python
# Line 2556-2559 (BUGGY):
gen = TripoStudioClient(
    session_cookie=studio_cookie or None,
    jwt_token=studio_token or None,      # WRONG: should be session_token=
)
```

Compare with correct usage at lines 2233-2236 and 2457-2459:
```python
gen = TripoStudioClient(
    session_cookie=studio_cookie,
    session_token=studio_token,           # CORRECT
)
```

**Fix:** Change `jwt_token=studio_token or None` to `session_token=studio_token or None` on line 2558.

---

### BUG-02: CRASH - TripoStudioClient not imported in generate_prop action
**File:** `src/veilbreakers_mcp/blender_server.py`, line 2556
**Severity:** CRASH
**Confirmed:** Yes (`TripoStudioClient` is not in module namespace)

The `generate_prop` action uses `TripoStudioClient` at line 2556, but never imports it. The import `from veilbreakers_mcp.shared.tripo_studio_client import TripoStudioClient` only exists inside the `generate_3d` (line 2232) and `generate_building` (line 2456) action branches. These local imports do NOT persist across separate tool calls.

If `generate_prop` is called without a prior `generate_3d` or `generate_building` call in the same session, it will crash with `NameError: name 'TripoStudioClient' is not defined`.

**Fix:** Add `from veilbreakers_mcp.shared.tripo_studio_client import TripoStudioClient` inside the `generate_prop` branch, before line 2556. Example:

```python
if studio_cookie or studio_token:
    from veilbreakers_mcp.shared.tripo_studio_client import TripoStudioClient
    gen = TripoStudioClient(
        session_cookie=studio_cookie or None,
        session_token=studio_token or None,
    )
```

---

### BUG-03: CRASH - blender_addon import triggers bpy in MCP server process
**File:** `src/veilbreakers_mcp/blender_server.py`, lines 2681, 2708, 3122
**Severity:** CRASH (feature-blocking)
**Confirmed:** Yes (`ModuleNotFoundError: No module named 'bpy'`)

Three code paths in `blender_server.py` import from `blender_addon.handlers.pipeline_state`:

```python
# Line 2681 (compose_map checkpoint resume):
from blender_addon.handlers.pipeline_state import (
    load_pipeline_checkpoint as _load_chkpt,
    validate_checkpoint_compatibility as _validate_chkpt,
    delete_pipeline_checkpoint as _delete_chkpt,
)

# Line 2708 (compose_map checkpoint save):
from blender_addon.handlers.pipeline_state import (
    save_pipeline_checkpoint as _save_cp,
)

# Line 3122 (generate_map_package):
from blender_addon.handlers.pipeline_state import (
    derive_addressable_groups as _derive_groups,
    emit_scene_hierarchy as _emit_hierarchy,
)
```

The MCP server runs as a standalone Python process (NOT inside Blender). Importing `blender_addon.handlers.pipeline_state` triggers `blender_addon/__init__.py` which does `import bpy` unconditionally at line 11. Since `bpy` is only available inside Blender, this crashes with `ModuleNotFoundError`.

**Affected features:**
- `compose_map` with `checkpoint_dir` + `resume=True` or `force_restart=True`
- `compose_map` checkpoint saving (all `_save_chkpt()` calls)
- `generate_map_package` action entirely

**Fix:** The `pipeline_state.py` module itself is pure Python (no bpy dependency except `emit_scene_hierarchy`). The fix is to either:
1. Change the import path to avoid triggering `blender_addon/__init__.py` (e.g., move `pipeline_state.py` into `shared/`)
2. Or make `blender_addon/__init__.py` guard the `import bpy` with a try/except

Option 1 (recommended): Move `pipeline_state.py` to `src/veilbreakers_mcp/shared/pipeline_state.py` and update imports to `from veilbreakers_mcp.shared.pipeline_state import ...`.

---

## LOGIC Bugs

### BUG-04: LOGIC - compose_map interior_results reset before generation
**File:** `src/veilbreakers_mcp/blender_server.py`, line 3022
**Severity:** LOGIC (data loss on resume)

In the `compose_map` action, `interior_results` is unconditionally reset to `[]` at line 3022, even when resuming from a checkpoint that has prior `interior_results`:

```python
# Line 2700-2702 (checkpoint loads interior_results):
location_results = ckpt.get("location_results", [])
interior_results = ckpt.get("interior_results", [])
_CHKPT_LOADED = True

# Line 3022 (unconditionally resets!):
interior_results = []
if "interiors_generated" not in steps_completed:
    # ... generates interiors
```

If a compose_map run crashes after generating some interiors but before marking "interiors_generated", resuming will lose those results because `interior_results = []` runs regardless of checkpoint state.

**Fix:** Only reset `interior_results` when NOT resuming from checkpoint:
```python
if not _CHKPT_LOADED:
    interior_results = []
```

---

### BUG-05: LOGIC - _normalize_map_point false-positive centering
**File:** `src/veilbreakers_mcp/blender_server.py`, lines 159-175
**Severity:** LOGIC (minor, edge case)

The heuristic for centering coordinates can produce incorrect results when one coordinate is near the threshold and another is near zero. The comment says "at least one exceeds 60%", but if `x=61` and `y=0` on a size-100 map, the point `(61, 0)` would be shifted to `(11, -50)` even though `y=0` is likely already centered.

This is a known design trade-off noted in the code comments but worth flagging as an edge case that could cause unexpected location placement.

**Impact:** Minor. Affects only locations with unusual coordinate combinations.

---

## DEAD Code / Unnecessary Code

### BUG-06: DEAD - Unused `pos` variable in blender_quality
**File:** `src/veilbreakers_mcp/blender_server.py`, line 5083
**Severity:** DEAD (wasteful, not broken)

```python
pos = tuple(position) if position else (0.0, 0.0, 0.0)
```

The `pos` variable is constructed for all `blender_quality` actions but only used by creature anatomy actions (creature_mouth, creature_eyelid, creature_paw, creature_wing, creature_serpent, creature_quadruped). For all weapon, riggable, clothing, vegetation, and texture actions, `pos` is computed but never used.

**Impact:** Negligible performance cost. Not a bug per se.

---

### BUG-07: DEAD - type: ignore comments throughout _enforce_world_quality
**File:** `src/veilbreakers_mcp/blender_server.py`, lines 739-844
**Severity:** CODE QUALITY

Multiple `# type: ignore` comments suppress legitimate type checking. The `report` dict uses dynamic typing (`report["failures"]` starts as `list` but type checker can't see it). These are noise, not bugs, but indicate the function would benefit from a typed dataclass.

---

## PERFORMANCE Bugs

### BUG-08: PERF - O(n*m) location placement search
**File:** `src/veilbreakers_mcp/blender_server.py`, lines 195-278 (`_plan_map_location_anchors`)
**Severity:** PERF (acceptable for typical use)

The location placement algorithm checks every candidate point against all previously placed locations with O(n*m) complexity where n=candidates and m=placed locations. For large maps with many locations (8+), the fallback ring search adds another factor.

**Impact:** Acceptable for typical use (< 20 locations). Would degrade on very large location counts (50+), which is unlikely in practice.

---

### BUG-09: PERF - _collect_mesh_targets iterates all scene objects
**File:** `src/veilbreakers_mcp/blender_server.py`, lines 688-716
**Severity:** PERF (minor)

`_collect_mesh_targets` sends a `list_objects` command to Blender and iterates all objects in the scene. For very large scenes (1000+ objects), this could be slow. The `max_targets = 64` cap mitigates the worst case.

---

## INTEGRATION Bugs

### BUG-10: INTEGRATION - compose_map step 8 raises ValueError when no locations
**File:** `src/veilbreakers_mcp/blender_server.py`, line 3004
**Severity:** LOGIC (partial)

```python
if not scatter_buildings:
    raise ValueError("No location anchors available for contextual prop scatter")
```

If a compose_map spec has no locations (only terrain + water + roads), the prop scatter step will throw a ValueError that gets caught as `steps_failed`. This is handled gracefully (doesn't crash the pipeline), but the error message is misleading -- props should still be scatterable on terrain without buildings.

**Fix:** Skip prop scatter silently or use terrain-only scatter mode when no buildings exist.

---

## Test Suite Summary

- **19,348 tests passed**, 1 skipped
- No test failures detected
- Tests run in 173.27s (2:53)
- The crash bugs (BUG-01, BUG-02, BUG-03) are not caught by tests because they require either:
  - Tripo credentials to be configured (BUG-01, BUG-02)
  - A `checkpoint_dir` parameter to be set (BUG-03)
  - These are integration-level runtime paths that unit tests mock away

---

## Priority Fix Order

1. **BUG-01** (CRASH): Wrong kwarg -- single-line fix, immediate
2. **BUG-02** (CRASH): Missing import -- add one import line
3. **BUG-03** (CRASH): bpy import chain -- move `pipeline_state.py` to `shared/`
4. **BUG-04** (LOGIC): interior_results reset -- conditional reset
5. **BUG-10** (LOGIC): Prop scatter without buildings -- skip or fallback

---

## Files with Bugs

| File | Bug IDs | Total |
|------|---------|-------|
| `src/veilbreakers_mcp/blender_server.py` | BUG-01, BUG-02, BUG-03, BUG-04, BUG-05, BUG-06, BUG-08, BUG-09, BUG-10 | 9 |
| `blender_addon/__init__.py` | BUG-03 (root cause) | 1 |

---

## Security Notes

- No bare `except:` clauses found in project code (only in code reviewer rule descriptions)
- Path sanitization is consistently applied (backslash to forward slash for Blender Python)
- `validate_code` is called before any user code execution via `blender_execute`
- No hardcoded credentials found
- BLOCKED_FUNCTIONS sandbox is maintained per user requirements
