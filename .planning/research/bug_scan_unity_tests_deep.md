# Deep Bug Scan: Unity MCP Server, C# Templates, and Test Suite

**Date:** 2026-04-02
**Scanned by:** Claude Opus 4.6
**Test suite result:** 19,348 passed, 1 skipped (174.94s)
**Scope:** unity_server.py, unity_tools/, shared/unity_templates/, blender_server.py (compose_map, Tripo, worldbuilding), all .py files for anti-patterns

---

## Summary

The codebase is in strong shape -- 19,348 tests pass, sanitization is applied consistently across 634 call sites in 44 template files, and the overall architecture is sound. However, I found **7 real bugs** (2 HIGH, 3 MEDIUM, 2 LOW) and **4 code quality issues** worth addressing.

---

## BUGS FOUND

### BUG-1: Unsanitized `name` in VFX particle file path [HIGH]

**File:** `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_tools/vfx.py`, line 263

**Problem:** The `name` parameter is used directly in the file path without sanitization. While the template generator correctly calls `sanitize_cs_identifier(name)` for the C# class name, the tool handler uses raw `name` for the `.cs` file path:

```python
script_path = f"Assets/Editor/Generated/VFX/VeilBreakers_VFX_{name}.cs"
```

If `name` contains spaces, dashes, dots, or path-traversal characters (e.g. `../../../evil`), this will either:
- Create files with invalid names that Unity cannot compile
- Potentially write files outside the intended directory (mitigated by `_write_to_unity`'s path traversal check, but still bad practice)

**Compare to correct pattern** (same file, line 344):
```python
safe_name = name.replace(" ", "_").replace("-", "_")
script_path = f"Assets/Editor/Generated/VFX/VeilBreakers_Trail_{safe_name}.cs"
```

**Fix:** Replace line 263 with:
```python
safe_name = name.replace(" ", "_").replace("-", "_")
script_path = f"Assets/Editor/Generated/VFX/VeilBreakers_VFX_{safe_name}.cs"
```

---

### BUG-2: Unsanitized `name` in file paths across camera.py and world.py [HIGH]

**Files:**
- `unity_tools/camera.py` lines 194, 213, 275, 297 (4 occurrences)
- `unity_tools/world.py` lines 312, 315, 339, 360, 382, 402, 424, 448, 469, 491, 494, 513, 516, 538, 541, 563, 566, 588, 591, 613, 616, 636, 639, 642, 667, 670, 693, 696 (28 occurrences)

**Problem:** Same issue as BUG-1. Raw `name` is interpolated directly into file paths:
```python
rel_path = f"Assets/Editor/Generated/Camera/{name}_CinemachineSetup.cs"
rel_path = f"Assets/Editor/Generated/World/{name}_TransitionSetup.cs"
```

**Note:** `_write_to_unity()` does have path traversal protection (line 162-168 of `_common.py`), which prevents the worst-case exploit. But names with spaces or special characters will create files Unity's compiler chokes on.

**Fix pattern:** All handlers should do:
```python
safe_name = name.replace(" ", "_").replace("-", "_")
```
before using in file paths. The gameplay.py, scene.py, and shader.py handlers already do this correctly.

---

### BUG-3: Orphaned expression statement in VFX screen effect handler [MEDIUM]

**File:** `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_tools/vfx.py`, line 530

**Problem:** A string method is called but its result is discarded (not assigned):
```python
effect_type.replace("_", " ").title()
```

This is a no-op -- `str.replace().title()` returns a new string but it is not stored. This was likely intended to be a variable assignment for use in the response, or is dead code left from refactoring. Strings are immutable in Python.

**Fix:** Either remove the line (it does nothing) or assign its result if it was meant to be used:
```python
# If intended for display:
display_name = effect_type.replace("_", " ").title()
```

---

### BUG-4: Duplicated `_CS_RESERVED` and `_safe_namespace` across 15 template files [MEDIUM]

**Files:** game_templates.py, content_templates.py, world_templates.py, vb_combat_templates.py, ux_templates.py, qa_templates.py, pipeline_templates.py, data_templates.py, combat_feel_templates.py, camera_templates.py, build_templates.py, shader_templates.py, encounter_templates.py, code_templates.py, equipment_templates.py

**Problem:** `_CS_RESERVED` (a frozenset of ~60 C# keywords) and `_safe_namespace()` (a 15-line function) are copy-pasted into 15 separate files. If a C# reserved word is added to the language, it must be updated in all 15 locations.

This is NOT a correctness bug today, but it is a maintenance hazard. One copy getting out of sync would cause generated C# to use a reserved word as a namespace segment.

**Fix:** Move `_CS_RESERVED` and `_safe_namespace()` into `_cs_sanitize.py` (which already has `sanitize_cs_string` and `sanitize_cs_identifier`) and import from there.

---

### BUG-5: `blender_server.py` imports from `blender_addon.handlers.pipeline_state` at runtime [MEDIUM]

**File:** `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py`, lines 2681, 2708, 3122

**Problem:** The compose_map checkpoint logic imports from `blender_addon.handlers.pipeline_state` via deferred imports:
```python
from blender_addon.handlers.pipeline_state import (
    load_pipeline_checkpoint as _load_chkpt,
    ...
)
```

The `blender_addon` package lives at `Tools/mcp-toolkit/blender_addon/` and is designed to run inside Blender's Python environment. When the MCP server process (running in standard Python) hits these code paths, the import will FAIL unless the Python path is specifically configured to include the blender_addon directory AND none of its transitive imports use bpy.

This means:
- compose_map with `checkpoint_dir` set will crash with ImportError
- generate_map_package will crash with ImportError
- These paths are guarded by `if checkpoint_dir:` so they only trigger when explicitly requested

**Fix:** Either:
1. Extract `pipeline_state.py` into `shared/` (so it runs without bpy)
2. Or add a try/except ImportError with clear error messaging

---

### BUG-6: compose_interior does not checkpoint (unlike compose_map) [LOW]

**File:** `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py`, lines 3387-3557

**Problem:** The `compose_map` action has full checkpoint/resume support (save state after each step, resume from last checkpoint). But `compose_interior` has NO checkpoint support at all. If interior generation fails partway through (e.g., after 5 of 8 rooms), all progress is lost and must be re-generated from scratch.

This is inconsistent behavior between the two composition pipelines and can waste significant generation time on complex interiors.

**Fix:** Add checkpoint support to compose_interior using the same pattern as compose_map.

---

### BUG-7: Terrain heightmap `_sample_terrain_height` does not validate x/y floats [LOW]

**File:** `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py`, lines 1088-1133

**Problem:** The function builds a Python code string with f-string interpolation of `x` and `y` float values:
```python
code = f"""
import bpy
...
origin = Vector(({x}, {y}, 10000.0))
"""
```

While `terrain_name` IS validated against injection (line 1097), `x` and `y` are typed as `float` and come from `_normalize_map_point` output which constrains them. However, if a NaN or Inf float leaked through, it would create invalid Python code in Blender. This is LOW risk because the values are computed internally, not from user input.

---

## CODE QUALITY ISSUES

### CQ-1: Skipped test with unclear value

**File:** `tests/test_character_skin_modifier.py:202`
**Skip reason:** "Serpent has no lateral symmetry"

The skip is conditional (`pytest.skip()` inside test body). This is fine -- it correctly skips when test data does not apply. No action needed.

---

### CQ-2: No bare `except:` statements in production code

The grep for `except:` found only:
- Test fixture files (intentionally buggy code for the code reviewer to detect)
- The code reviewer's own rule descriptions
- Test assertions

**Verdict:** CLEAN. No bare except statements in production code.

---

### CQ-3: No `== None` in production code

Only found in test fixture files (intentionally buggy). Production code uses `is None` correctly.

**Verdict:** CLEAN.

---

### CQ-4: No mutable default arguments in production code

Only found in test fixture files (intentionally buggy). Production code uses `None` with body assignment pattern.

**Verdict:** CLEAN.

---

## TEST COVERAGE GAPS

### GAP-1: No tests for unsanitized file paths in tool handlers

The template generators are well-tested (19,348 tests), but the tool HANDLERS (unity_tools/*.py) that construct file paths from `name` parameters are not tested for path safety. Tests mock `_write_to_unity` or test template output, but don't verify that the file path itself is properly sanitized.

**Impact:** BUG-1 and BUG-2 would have been caught with a test like:
```python
def test_vfx_particle_path_sanitizes_name():
    """Names with spaces/dashes should produce valid .cs paths."""
    # Call handler with name="fire blast"
    # Assert script_path does not contain spaces
```

### GAP-2: No integration tests for checkpoint/resume in compose_map

The checkpoint code at lines 2678-2720 uses deferred imports from `blender_addon.handlers.pipeline_state`. There are no tests that verify these imports succeed in the MCP server's Python environment (as opposed to Blender's).

### GAP-3: No tests for compose_interior error recovery

The compose_interior pipeline catches exceptions per-step but has no tests verifying that partial failures produce correct "partial" status with proper step tracking.

---

## BLENDER SERVER ADDITIONAL FINDINGS

### compose_map pipeline: Well-structured but risky imports

The compose_map pipeline (lines 2636-3094) is well-designed with:
- Step-by-step execution with individual error handling per step
- Checkpoint save after each major phase
- Budget system that adapts resolution to terrain size
- Location placement with collision avoidance

But the checkpoint import issue (BUG-5) means the resume feature is likely broken outside of Blender.

### Tripo integration: Properly structured

The Tripo integration (lines 2210-2340) correctly:
- Checks for studio credentials before API key
- Has proper try/finally for client cleanup
- Post-processes models with texture extraction
- Handles variant grid import into Blender
- Falls through to API key path if studio unavailable

No bugs found in Tripo integration code.

### TCP connection handling: Sound

The `BlenderConnection` singleton (lines 82-99) uses double-checked locking with proper thread safety. The `_cleanup_connection` atexit handler ensures cleanup. Connection-per-command pattern avoids stale socket issues.

---

## SUMMARY TABLE

| ID | Severity | File | Description |
|----|----------|------|-------------|
| BUG-1 | HIGH | unity_tools/vfx.py:263 | Unsanitized `name` in file path |
| BUG-2 | HIGH | camera.py, world.py (32 sites) | Unsanitized `name` in file paths |
| BUG-3 | MEDIUM | unity_tools/vfx.py:530 | Orphaned expression (no-op) |
| BUG-4 | MEDIUM | 15 template files | Duplicated _CS_RESERVED/_safe_namespace |
| BUG-5 | MEDIUM | blender_server.py:2681 | blender_addon import crashes MCP server |
| BUG-6 | LOW | blender_server.py:3387 | compose_interior has no checkpoint |
| BUG-7 | LOW | blender_server.py:1105 | No NaN/Inf guard on terrain sample |
| GAP-1 | TEST | unity_tools/*.py | No path sanitization tests for handlers |
| GAP-2 | TEST | blender_server.py | No checkpoint import integration test |
| GAP-3 | TEST | blender_server.py | No compose_interior partial-failure test |

---

## WHAT'S WORKING WELL

1. **Sanitization coverage:** 634 uses of `sanitize_cs_string`/`sanitize_cs_identifier` across 44 template files
2. **Path traversal protection:** `_write_to_unity()` prevents writing outside project root
3. **Error handling pattern:** Every tool handler has try/except with logger.exception
4. **Consistent compound tool pattern:** All 22 Unity tools follow same structure
5. **Template C# quality:** Generated C# uses proper namespaces, XML docs, null checks, and Unity-correct APIs
6. **No anti-patterns in production code:** Zero bare excepts, zero `== None`, zero mutable defaults
7. **Test suite is comprehensive:** 19,348 tests with only 1 legitimate skip
8. **Checkpoint support for compose_map:** Well-designed resume system (when imports work)
