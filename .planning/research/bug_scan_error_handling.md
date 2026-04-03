# Error Handling Quality Scan - VeilBreakers MCP Toolkit

**Date:** 2026-04-02
**Scope:** All 458 Python files in Tools/mcp-toolkit (excluding .venv)
**Method:** Systematic grep + manual code review of flagged patterns
**Known bugs excluded:** compose_map except pass, Tripo 429, bare except in roslynator, and ~186 previously found bugs

---

## Summary

Found **23 new bugs** across 5 missions. The codebase has generally good error handling in the blender_client TCP layer and tripo_client retry logic. The worst patterns are in the worldbuilding/environment generators (silent `except Exception: pass` blocks hiding geometry failures) and in the HTTP client layer (httpx.HTTPStatusError not caught by any error handler).

---

## MISSION 1: Silent Failures

### BUG-EH-01: blender_server.py game_check silently swallows failures (line 3144)
**File:** `src/veilbreakers_mcp/blender_server.py:3144`
**Pattern:** `except Exception: pass`
**Impact:** HIGH -- In `compose_map`, if `mesh_check_game_ready` fails (e.g., connection drops mid-batch), the object is silently skipped. The final report says "0 game_check_failures" which is a lie -- it should say "N objects could not be checked." The caller at line 3147 uses `_game_failures` to decide whether to block export, but unchecked objects are invisible.
```python
# Line 3130-3145
for _obj_name in _mp_objects:
    try:
        _chk = await blender.send_command("mesh_check_game_ready", ...)
        ...
    except Exception:
        pass  # BUG: silently drops check failures
```
**Fix:** Append to `_game_failures` with `"status": "check_failed"`.

### BUG-EH-02: blender_server.py LOD generation silently swallows failures (line 3165)
**File:** `src/veilbreakers_mcp/blender_server.py:3165`
**Pattern:** `except Exception: pass`
**Impact:** MEDIUM -- `_lod_count` doesn't increment, so the report shows fewer LODs, but there's no record of *which* objects failed or *why*. User sees "lod_variants_generated: 2" and assumes everything worked when 3 failed.
**Fix:** Track failures in a `_lod_failures` list.

### BUG-EH-03: blender_server.py FBX export silently swallows failures (line 3187)
**File:** `src/veilbreakers_mcp/blender_server.py:3187`
**Pattern:** `except Exception: pass`
**Impact:** HIGH -- Export failures are invisible. The result dict has `_fbx_files` with only successful exports but no record of which groups failed. The status is "partial" only if *zero* FBX files succeeded, not if some failed.
**Fix:** Track export failures with error messages.

### BUG-EH-04: worldbuilding.py UV repair silently swallows all errors (line 5396)
**File:** `blender_addon/handlers/worldbuilding.py:5396`
**Pattern:** `except Exception: pass`
**Impact:** MEDIUM -- bmesh UV operations fail silently. The result says `uv_layers_added: 0` but doesn't distinguish "no UVs needed" from "all UV attempts crashed."
**Fix:** At minimum, log a warning. Track failures separately from skips.

### BUG-EH-05: worldbuilding.py mesh repair silently swallows all errors (line 5413)
**File:** `blender_addon/handlers/worldbuilding.py:5413`
**Pattern:** `except Exception: pass`
**Impact:** MEDIUM -- Same as BUG-EH-04 but for remove_doubles/recalc_normals. Corrupted meshes pass through without any signal.

### BUG-EH-06: worldbuilding.py weathering application silently swallows all errors (line 5437)
**File:** `blender_addon/handlers/worldbuilding.py:5437`
**Pattern:** `except Exception: pass`
**Impact:** MEDIUM -- `weathering_applied_count` stays at 0, but the result dict still reports `weathering_preset: "medium"` as if weathering was configured. Misleading combination: preset is set but count is 0 with no error.

### BUG-EH-07: environment.py noise/bump node creation swallowed (line 1079)
**File:** `blender_addon/handlers/environment.py:1079`
**Pattern:** `except Exception: pass`
**Impact:** LOW-MEDIUM -- If shader node creation fails (e.g., Blender version incompatibility), water surfaces render without bump mapping. Result still reports the water as successful with all features enabled.

### BUG-EH-08: environment.py biome palette lookup swallowed (line 1366)
**File:** `blender_addon/handlers/environment.py:1366`
**Pattern:** `except Exception: pass`
**Impact:** LOW -- Falls back to hardcoded brown `(0.15, 0.12, 0.10, 1.0)` color. The terrain renders with wrong colors but no error is reported.

### BUG-EH-09: _collect_mesh_targets returns empty list on connection failure (line 695)
**File:** `src/veilbreakers_mcp/blender_server.py:695`
**Pattern:** `except (...): return []`
**Impact:** HIGH -- If Blender connection drops during `_collect_mesh_targets`, the caller `_validate_world_quality` receives an empty list and reports `"validated_meshes": 0` with status "success" -- appearing as if validation passed when nothing was checked. The caller should distinguish "no targets found" from "failed to query targets."

---

## MISSION 2: Misleading Error Messages

### BUG-EH-10: elevenlabs_client rate limit detection by string parsing (line 119)
**File:** `src/veilbreakers_mcp/shared/elevenlabs_client.py:119`
**Pattern:** Fragile rate limit detection
**Impact:** MEDIUM -- Rate limit is detected by checking if "429" or "rate" appears in `str(exc)`. The ElevenLabs SDK likely throws a specific exception type (e.g., `elevenlabs.RateLimitError` or an httpx-based error). This string matching is brittle:
1. A ValueError with message "parameter must be between 1-429" would be misidentified as rate limit
2. The actual httpx.HTTPStatusError for 429 is NOT caught by `(ConnectionError, TimeoutError, OSError, ValueError, KeyError)` -- so real rate limits crash through unretried
```python
except (ConnectionError, TimeoutError, OSError, ValueError, KeyError) as exc:
    is_rate_limit = "429" in str(exc) or "rate" in str(exc).lower()
```
**Fix:** Catch httpx.HTTPStatusError explicitly and check `exc.response.status_code == 429`.

### BUG-EH-11: worldbuilding.py reports weathering_preset even when all applications failed
**File:** `blender_addon/handlers/worldbuilding.py:5439-5440`
**Impact:** LOW -- Result includes `weathering_preset: "heavy"` and `weathering_applied_count: 0`. To a consumer, this looks like "heavy weathering was configured but applied to nothing" vs "all weathering attempts failed." Not actionable from the error output.

---

## MISSION 3: Missing Error Handling

### BUG-EH-12: httpx.HTTPStatusError not caught in fal_client (line 127)
**File:** `src/veilbreakers_mcp/shared/fal_client.py:115,127`
**Pattern:** `raise_for_status()` throws `httpx.HTTPStatusError`, caught by `except (ConnectionError, TimeoutError, OSError, ValueError, KeyError)` -- HTTPStatusError is NOT a subclass of any of these.
**Impact:** HIGH -- If fal.ai image CDN returns 403/404/500, `raise_for_status()` throws an uncaught exception that crashes the MCP tool handler, producing a raw traceback instead of a structured error response.
**Fix:** Add `httpx.HTTPStatusError` to the except tuple, or catch `httpx.HTTPError` (parent class).

### BUG-EH-13: httpx.HTTPStatusError not caught in gemini_client._call_via_rest
**File:** `src/veilbreakers_mcp/shared/gemini_client.py:146,64-80`
**Pattern:** Same as BUG-EH-12. `_call_via_rest` calls `response.raise_for_status()`, but the parent `_call_gemini` only catches `(ConnectionError, TimeoutError, OSError, ValueError, KeyError)`.
**Impact:** HIGH -- Gemini 429/401/500 errors crash through as unhandled exceptions instead of returning the graceful error dict.
**Fix:** Add `httpx.HTTPStatusError` to the except clause in `_call_gemini`.

### BUG-EH-14: httpx.HTTPStatusError not caught in texture_ops.py inpainting
**File:** `src/veilbreakers_mcp/shared/texture_ops.py:845,863`
**Pattern:** `_dl_resp.raise_for_status()` inside a `try` block, but the outer except at line 863 catches `Exception` broadly so this one is actually caught. However, the error message says "fal.ai inpainting failed" which is misleading when it's a download failure, not an inpainting failure.
**Impact:** LOW -- Error is caught but the message is misleading. "fal.ai inpainting failed" when the actual problem is "CDN returned 404."

### BUG-EH-15: tripo_studio_client._request resp.json() can fail on non-JSON responses
**File:** `src/veilbreakers_mcp/shared/tripo_studio_client.py:171`
**Pattern:** `data = resp.json()` called before checking status code
**Impact:** MEDIUM -- If Tripo's API returns a 502/503 with HTML body (common during outages), `resp.json()` throws `json.JSONDecodeError` with an unhelpful "Expecting value: line 1 column 1" message. The structured error handling at line 172-178 never executes.
```python
resp = await client.request(method, url, json=json_data)
data = resp.json()  # BUG: crashes on non-JSON error response
if resp.status_code >= 400:  # never reached on JSON parse failure
```
**Fix:** Move status code check before json() call, or wrap json() in try/except.

### BUG-EH-16: terrain_advanced.py json.loads without try/except (line 672)
**File:** `blender_addon/handlers/terrain_advanced.py:672`
**Pattern:** `layers_data = json.loads(layers_json)` -- no error handling
**Impact:** MEDIUM -- If a Blender custom property `terrain_layers` contains corrupted JSON (e.g., user manually edited it, or a previous operation was interrupted), this crashes the entire terrain layer handler with an unhandled JSONDecodeError. The fallback at line 674 (`layers_data = []`) only triggers if the value is not a string, not on malformed JSON.
**Fix:** Wrap in try/except JSONDecodeError, default to empty list with a warning.

### BUG-EH-17: glb_texture_extractor.py json.loads without try/except (line 86)
**File:** `src/veilbreakers_mcp/shared/glb_texture_extractor.py:86`
**Pattern:** `gltf = json.loads(json_chunk_data.rstrip(b"\x00"))` -- no error handling
**Impact:** MEDIUM -- If a GLB file has a corrupted JSON chunk (e.g., partial download), this throws an unhandled JSONDecodeError. The caller needs to wrap this in try/except or the extractor should handle it gracefully.
**Fix:** Add try/except JSONDecodeError with a descriptive ValueError.

### BUG-EH-18: elevenlabs_client doesn't catch httpx/SDK-specific exceptions
**File:** `src/veilbreakers_mcp/shared/elevenlabs_client.py:118`
**Pattern:** The retry handler only catches `(ConnectionError, TimeoutError, OSError, ValueError, KeyError)`. The ElevenLabs SDK and httpx can throw other exceptions (httpx.HTTPStatusError, httpx.ReadTimeout, etc.) that bypass the retry logic entirely.
**Impact:** MEDIUM -- Any HTTP error from ElevenLabs that isn't one of those 5 types crashes through to the caller without retry.

---

## MISSION 4: Return Value Contracts

### BUG-EH-19: _validate_world_quality reports success with 0 meshes validated
**File:** `src/veilbreakers_mcp/blender_server.py:720-736`
**Pattern:** Empty mesh_targets produces a report with no failures but also no validations
**Impact:** MEDIUM (related to BUG-EH-09) -- When `_collect_mesh_targets` returns `[]` (either because there are no targets OR because the connection failed), the report has `validated_meshes: 0, uv_fixed: [], materials_fixed: [], lod_generated: [], failures: []`. This looks like "everything is fine, nothing to do" instead of "validation couldn't run."
**Fix:** Include a `"skipped_reason"` field when mesh_targets is empty, or check connection state before proceeding.

### BUG-EH-20: tripo_studio_client generate methods return different error shapes
**File:** `src/veilbreakers_mcp/shared/tripo_studio_client.py:342-353,397-411`
**Pattern:** `generate_from_text` and `generate_from_image` catch `Exception` and return `{"status": "failed", "error": str(exc)}`. But `_poll_and_download_variants` returns a different shape: `{"status": "failed", "models": [...], "downloaded": 0, ...}`. Callers checking `result.get("models")` after a task creation failure get None, not a list.
**Impact:** LOW -- Callers should check `status` first, but the inconsistent shapes can confuse downstream logic.

---

## MISSION 5: Diagnostic Gaps

### BUG-EH-21: blender_server.py compose_map has zero logging for per-object failures
**File:** `src/veilbreakers_mcp/blender_server.py:3130-3200`
**Impact:** MEDIUM -- The compose_map pipeline (game_check -> LOD -> export) has no logging at any step. When objects fail silently (BUG-EH-01/02/03), there's no way to diagnose which object failed or why from log output. The only diagnostic is the result dict counts.
**Fix:** Add `logger.warning(...)` in each except block before passing.

### BUG-EH-22: worldbuilding.py interior generation has no diagnostic counters for failures
**File:** `blender_addon/handlers/worldbuilding.py:5380-5440`
**Impact:** MEDIUM -- Three separate except-pass blocks (UV, repair, weathering) produce no diagnostic output. When a building interior looks wrong, there's no way to tell if UV, repair, or weathering failed without stepping through in a debugger.
**Fix:** Add `uv_failures`, `repair_failures`, `weathering_failures` counters to result dict.

### BUG-EH-23: gemini_client._call_gemini exception routing is confusing
**File:** `src/veilbreakers_mcp/shared/gemini_client.py:64-80`
**Impact:** LOW -- The error handling flow is:
1. Try SDK -> catch ImportError -> try REST
2. Catch (ConnectionError, ...) -> return error dict

The problem: if the SDK import succeeds but the SDK call itself throws httpx.HTTPStatusError (from the SDK's internal HTTP client), it falls through both catches and crashes. The except-ImportError only catches the initial import, not HTTP errors from the SDK.

---

## Previously Known (Not Counted)

These were mentioned in the prompt as known:
- `except Exception: pass` in compose_map (BUG-EH-01/02/03 are new *specific* instances within compose_map)
- Tripo 429 not caught
- Bare except in roslynator

---

## Severity Summary

| Severity | Count | Bug IDs |
|----------|-------|---------|
| HIGH | 5 | EH-01, EH-03, EH-09, EH-12, EH-13 |
| MEDIUM | 13 | EH-02, EH-04, EH-05, EH-06, EH-10, EH-15, EH-16, EH-17, EH-18, EH-19, EH-21, EH-22, EH-23 |
| LOW | 5 | EH-07, EH-08, EH-11, EH-14, EH-20 |

## Patterns NOT Found (Clean Areas)

The following areas have GOOD error handling:

1. **blender_client.py** -- Excellent TCP error handling with actionable messages, retry logic, proper exception chaining (`from exc`), and specific error types for each failure mode.
2. **tripo_client.py** -- Proper retry with exponential backoff, connection/timeout errors caught, model validation after download.
3. **model_validation.py** -- Comprehensive GLB/FBX validation with structured error reporting.
4. **socket_server.py** -- Clean connection lifecycle error handling with proper resource cleanup.
5. **unity_tools/_common.py** -- json.loads wrapped in try/except with structured error returns.
6. **animation_production.py** -- json.loads of custom properties properly wrapped in try/except.
7. **prefab_templates.py** -- json.loads with exception chaining (from exc).

## Fix Priority

1. **Add httpx.HTTPStatusError to except clauses** (BUG-EH-12, EH-13, EH-18) -- 3 files, same pattern, easy fix
2. **Fix tripo_studio_client._request JSON parsing order** (BUG-EH-15) -- swap status check and json() call
3. **Replace except-pass with failure tracking in compose_map** (BUG-EH-01, EH-02, EH-03) -- high impact, one function
4. **Add failure tracking to worldbuilding interior generation** (BUG-EH-04, EH-05, EH-06) -- medium impact
5. **Add try/except to json.loads in terrain_advanced and glb_texture_extractor** (BUG-EH-16, EH-17) -- quick fixes
