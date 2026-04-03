# Deep Bug Scan: Security, Error Handling, Configuration, and Edge Cases

**Date:** 2026-04-02
**Scope:** Full codebase security audit, error handling patterns, configuration, Python compatibility, extreme edge cases
**Method:** AST analysis of security.py, code injection vector tracing, error pattern grep, config/dependency audit
**Prior scans:** 136 bugs across 7 scans -- all findings below are NEW

---

## SCAN 1: Security & Sandbox

### BUG-SEC-01: `mesh_name` injected unsanitized into f-string code sent to `execute_code` [HIGH]
**File:** `blender_server.py` line 761
**Severity:** HIGH (code injection into sandbox)

```python
f"obj = bpy.data.objects.get('{mesh_name}')\n"
```

The `mesh_name` variable comes from user-controlled MCP tool parameters. While the sandbox's AST validator would catch `exec()`/`eval()` calls, it does NOT catch string-level injection. A crafted `mesh_name` like `'); import bpy; bpy.ops.wm.save_mainfile(filepath="/tmp/pwned.blend'); #` would break out of the `get()` call and execute arbitrary bpy operations.

The sandbox blocks `import os` and similar, but `bpy.ops` is fully allowed. A malicious name could invoke `bpy.ops.wm.save_mainfile`, `bpy.ops.export_scene.fbx` (exfiltrate scene data), or delete all objects.

Compare with `_sample_terrain_height` (line 1097) which correctly validates `terrain_name` against `^[A-Za-z0-9_\-. ]+$`. The same sanitization is NOT applied to `mesh_name` in the cleanup handler or any other f-string code generation site.

**Other affected sites:**
- Line 761: `bpy.data.objects.get('{mesh_name}')` in cleanup handler
- Line 2282: `filepath="{safe}"` -- this one IS sanitized (replaces `\` and `"`)
- Line 3710: `filepath="{safe_path}"` -- also sanitized
- BUT: The `bpy.ops.{op}` on line 3710 uses `op` from a fixed dict, which is safe.

**Fix:** Add a `_sanitize_name(name)` function that strips or rejects characters outside `[A-Za-z0-9_\-. ]` and apply it to ALL names before f-string interpolation into code strings. Or better: pass names as data via the params dict, not as string interpolation in code.

---

### BUG-SEC-02: Sandbox `_SAFE_BUILTINS` exposes `type()` constructor indirectly via `isinstance` [LOW]
**File:** `blender_addon/handlers/execute.py` line 56
**Severity:** LOW (theoretical, hard to exploit)

The sandbox provides `isinstance` in `_SAFE_BUILTINS` and also `bpy` as a full module. While `type()` is excluded from builtins, a sandbox user can do:
```python
t = isinstance.__class__  # <class 'builtin_function_or_method'>
```
This doesn't directly give `type()`, but combined with allowed dunders like `__init__`, `__new__`, and `__doc__`, plus unrestricted `bpy` attribute access, there may be chained escapes. The sandbox correctly removed `__call__` from `_ALLOWED_DUNDERS` and blocks `__class__` access (not in allowlist), so this is well mitigated. Noting for awareness only.

---

### BUG-SEC-03: `safe_path` escaping in import code is insufficient for shell-like injection [MEDIUM]
**File:** `blender_server.py` line 3705
**Severity:** MEDIUM (path injection)

```python
safe_path = filepath.replace("\\", "/").replace('"', '\\"')
```

This escapes backslashes and double-quotes, but does NOT escape:
- Newlines (`\n`) -- a filepath containing `\n` would break the f-string code into multiple statements
- Single quotes
- Null bytes

A filepath like `/tmp/model.glb\nimport bpy\nbpy.ops.wm.quit_blender()` would inject an extra statement after the import line. The AST validator on the Blender addon side WOULD catch this (it parses the entire code block), so this is defense-in-depth, but the MCP server side should also reject filenames with newlines.

**Fix:** Add `filepath = filepath.replace("\n", "").replace("\r", "").replace("\0", "")` before the replace chain, or validate filepath against a strict pattern like `_sample_terrain_height` does.

---

### BUG-SEC-04: `bpy.ops` is unrestricted in sandbox -- can export/delete scene data [MEDIUM]
**File:** `blender_addon/handlers/execute.py` line 109, `security.py` line 52-66
**Severity:** MEDIUM (data exfiltration via allowed bpy operations)

The sandbox blocks specific dangerous `bpy` operations (`save_mainfile`, `run_script`, `python_file_run`, etc.) via `BLOCKED_BPY_ATTRS`. However, several dangerous operations are NOT blocked:
- `bpy.ops.export_scene.fbx()` -- can export entire scene to arbitrary path
- `bpy.ops.export_scene.gltf()` -- same
- `bpy.ops.export_mesh.stl()` -- same
- `bpy.ops.object.delete()` -- can delete all objects
- `bpy.ops.scene.delete()` -- can delete scenes
- `bpy.ops.outliner.orphans_purge()` -- can purge all unused data

The code execution endpoint is intended for internal use by the MCP server (not direct user access), so this is lower severity. But since execute_code IS exposed as a Blender handler via `COMMAND_HANDLERS`, any TCP client on localhost can send these commands.

**Fix:** Consider adding `export_scene`, `export_mesh`, `scene.delete`, `outliner.orphans_purge` to `BLOCKED_BPY_ATTRS`. Or maintain an allowlist of permitted `bpy.ops` namespaces (only `object`, `mesh`, `material`, `uv`, etc.).

---

### BUG-SEC-05: Socket server binds to `localhost` only -- safe, but no authentication [LOW]
**File:** `blender_addon/socket_server.py` line 57
**Severity:** LOW (design limitation, not a bug per se)

The server binds to `("localhost", self.port)` which only accepts connections from the same machine. However, there is zero authentication -- any process on localhost can send commands. This is acceptable for a dev tool but worth documenting: any local malware or compromised process can control Blender.

No fix needed for current use case, but documenting for awareness.

---

## SCAN 2: Error Handling Patterns

### BUG-ERR-01: `except Exception: pass` in `compose_map` terrain flatten suppresses ALL errors including `NameError` [MEDIUM]
**File:** `blender_server.py` line 2882
**Severity:** MEDIUM (silent failure hides real bugs)

```python
try:
    await blender.send_command("terrain_spline_deform", {...})
except Exception:
    pass  # Non-fatal
```

This catches and silences everything including programming errors (`NameError`, `TypeError`, `AttributeError`). The comment says "Non-fatal" but if the command name is wrong (typo) or the params dict is malformed, it will silently skip terrain flattening, causing buildings to float or clip through terrain.

The same pattern appears at:
- Line 3144: game_check in map_pack_for_unity -- silences game readiness check failures
- Line 3165: LOD generation in map_pack -- silences LOD failures  
- Line 3187: FBX export in map_pack -- silences export failures
- Line 3486: mesh enhancement in compose_interior -- silences enhancement failures

**Fix:** At minimum, log the exception. Replace `pass` with `logger.debug("terrain_spline_deform failed: %s", exc, exc_info=True)`.

---

### BUG-ERR-02: `worldbuilding.py` UV auto-fix and mesh repair swallow bmesh errors including `free()` leak [HIGH]
**File:** `blender_addon/handlers/worldbuilding.py` lines 5387-5414
**Severity:** HIGH (memory leak in Blender)

```python
try:
    _bm = bmesh.new()
    _bm.from_mesh(child_obj.data)
    if _bm.faces:
        ...
        _bm.to_mesh(child_obj.data)
        uv_fixed_count += 1
    _bm.free()
except Exception:
    pass
```

If `_bm.from_mesh()` or `_bm.to_mesh()` raises, `_bm.free()` is never called. BMesh objects that aren't freed leak GPU memory in Blender. For a settlement with 50+ building children, each leaking a BMesh, this can cause Blender to crash from memory exhaustion.

The same pattern appears in the repair loop (lines 5401-5414) and the `worldbuilding_layout.py` fallback boxes (lines 637-657, though those do call `bm.free()`).

**Fix:** Use try/finally:
```python
_bm = bmesh.new()
try:
    _bm.from_mesh(child_obj.data)
    ...
    _bm.to_mesh(child_obj.data)
finally:
    _bm.free()
```

---

### BUG-ERR-03: `_retry_on_rate_limit` in ElevenLabs client detects rate limits by string matching [LOW]
**File:** `shared/elevenlabs_client.py` line 119
**Severity:** LOW (fragile detection)

```python
is_rate_limit = "429" in str(exc) or "rate" in str(exc).lower()
```

This string-matches the exception message to detect rate limits. If the ElevenLabs SDK changes error message format, or if an unrelated error message happens to contain "429" or "rate" (e.g., "generate at a moderate rate"), this will incorrectly retry or fail to retry.

**Fix:** Check the HTTP status code directly if the SDK provides it, or catch the specific rate-limit exception type.

---

### BUG-ERR-04: `tripo_studio_client.py` `_request` raises `RuntimeError` for ALL API errors [MEDIUM]
**File:** `shared/tripo_studio_client.py` line 176
**Severity:** MEDIUM (no way to distinguish error types)

```python
if resp.status_code >= 400:
    raise RuntimeError(f"Tripo Studio API error {code}: {msg}. {suggestion}")
```

All 4xx and 5xx errors become `RuntimeError`. Callers cannot distinguish:
- 401 Unauthorized (need JWT refresh) from
- 402 Payment Required (out of credits) from
- 429 Rate Limit (need backoff) from
- 500 Server Error (transient)

The retry logic in `generate_from_text` catches `(ConnectionError, TimeoutError, OSError)` but NOT `RuntimeError`, so API rate limits (429) will NOT trigger retry.

**Fix:** Map status codes to specific exception types, or at minimum check for 429 and raise a retryable exception.

---

### BUG-ERR-05: `gemini_client.py` REST fallback accesses nested JSON without safety checks [MEDIUM]
**File:** `shared/gemini_client.py` line 149
**Severity:** MEDIUM (crash on unexpected API response format)

```python
data = response.json()
text = data["candidates"][0]["content"]["parts"][0]["text"]
```

If Gemini returns an error response, a blocked-by-safety response, or an empty candidates list, this will raise `KeyError` or `IndexError`. These ARE caught by the outer `except (ConnectionError, ... ValueError, KeyError)` but `IndexError` is NOT in the catch list.

**Fix:** Add `IndexError` to the catch clause, or use `.get()` chains with defaults.

---

## SCAN 3: Configuration & Environment

### BUG-CFG-01: `httpx` is used as a direct import but not declared in `pyproject.toml` dependencies [MEDIUM]
**File:** `pyproject.toml`, `shared/tripo_studio_client.py` line 26, `shared/fal_client.py` line 113, `shared/gemini_client.py` line 112, `shared/texture_ops.py` line 843
**Severity:** MEDIUM (works by accident, fragile)

`httpx` is imported at the top level in `tripo_studio_client.py` (unconditional) and lazily in 3 other files. It is NOT listed in `pyproject.toml` `dependencies`. It works because `httpx` is a transitive dependency of `mcp`, `elevenlabs`, `fal-client`, and `google-genai`. But:
1. If any of those packages drops `httpx` as a dependency, the import fails
2. Version compatibility is not enforced -- the tripo_studio_client uses `httpx.AsyncClient` features that require httpx >= 0.23
3. The `tripo_studio_client.py` import is top-level and unconditional, so it crashes on import if httpx is somehow missing

**Fix:** Add `"httpx>=0.24.0"` to pyproject.toml dependencies.

---

### BUG-CFG-02: `.mcp.json` uses `${VAR}` env var syntax but this is NOT standard JSON [LOW]
**File:** `.mcp.json` lines 8-11, 19-20
**Severity:** LOW (works because MCP client handles substitution)

```json
"ELEVENLABS_API_KEY": "${ELEVENLABS_API_KEY}"
```

Standard JSON has no variable substitution. This works because the Claude Code MCP client processes `${...}` before parsing. But if this file is loaded by any other JSON parser (e.g., a test harness, a deployment script), the literal string `${ELEVENLABS_API_KEY}` would be passed as the API key, causing authentication failures with confusing error messages.

Not a bug per se, but worth documenting in comments.

---

### BUG-CFG-03: `Settings.realesrgan_path` default is Windows-specific relative path [LOW]
**File:** `shared/config.py` line 36
**Severity:** LOW (cross-platform issue)

```python
realesrgan_path: str = "bin/realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan.exe"
```

The default path includes `.exe` and is relative. On Linux/Mac, the binary name would be different. This is a dev-machine tool so cross-platform is low priority, but it would cause confusing `FileNotFoundError` messages on non-Windows.

---

### BUG-CFG-04: `Settings` loads `.env` from CWD, which varies depending on how MCP is launched [LOW]
**File:** `shared/config.py` line 54
**Severity:** LOW (user confusion)

```python
model_config = SettingsConfigDict(
    env_file=(".env", "pipeline.local.env"),
)
```

pydantic-settings resolves `.env` relative to the CWD. When launched via `uv --directory Tools/mcp-toolkit run vb-blender-mcp`, the CWD is `Tools/mcp-toolkit`. But if launched differently (e.g., from the repo root), a different `.env` would be loaded (or none). This is standard behavior but can cause "my API key isn't found" confusion.

---

## SCAN 4: Extreme Edge Cases

### BUG-EDGE-01: `_sample_terrain_height` returns 0.0 on failure, causing buildings at Z=0 [MEDIUM]
**File:** `blender_server.py` line 1099, 1133
**Severity:** MEDIUM (buildings sink into or float above terrain)

When terrain height sampling fails (Blender error, invalid terrain name, raycast miss), the function returns `0.0`. The caller uses this as `anchor_z` for building placement. If the terrain is at Y=50m (e.g., a mountain), the building gets placed at Z=0, completely underground. The caller has no way to distinguish "terrain is at Z=0" from "sampling failed".

**Fix:** Return `None` on failure and have callers skip placement or use a fallback strategy.

---

### BUG-EDGE-02: `compose_map` does NOT validate that `locations` list is non-empty [LOW]
**File:** `blender_server.py` line ~2700+
**Severity:** LOW (produces empty map with only terrain)

If `compose_map` is called with `locations=[]`, it creates terrain and water but skips all buildings. The result reports `"status": "success"` with empty `location_results`. This is technically correct but the next_steps still reference buildings that don't exist.

---

### BUG-EDGE-03: Unicode in Blender object names causes JSON serialization issues [MEDIUM]
**File:** `blender_addon/socket_server.py` line 123
**Severity:** MEDIUM (crashes on Unicode-heavy scenes)

The socket server does `json.dumps(response).encode("utf-8")`. This is correct for Unicode. However, the Blender client does `json.loads(response_bytes)` which can fail if Blender returns object names with surrogate pairs or invalid Unicode that somehow got into bpy.data.objects names. More critically, the f-string code injection in `blender_server.py` line 761:

```python
f"obj = bpy.data.objects.get('{mesh_name}')\n"
```

A Unicode name like `建物_01` would work fine in the f-string BUT if the name contains a single quote (`O'Brien's Chair`), it breaks the Python string literal and causes a SyntaxError in the sandbox. This is also a code injection vector (see BUG-SEC-01).

**Fix:** Escape single quotes in names, or use `repr()` for safe string embedding.

---

### BUG-EDGE-04: `result_event.wait(timeout=300)` in socket server -- frozen Blender blocks ALL clients for 5 minutes [HIGH]
**File:** `blender_addon/socket_server.py` line 113
**Severity:** HIGH (denial of service)

When a command handler takes too long (e.g., generating a complex settlement), `result_event.wait(timeout=300)` blocks the client thread for up to 5 minutes. Meanwhile, the socket server accepts new connections (line 64-67), but `_process_commands` only processes ONE command per tick (line 172: `command_queue.get_nowait()`). 

If Blender freezes (e.g., infinite loop in a handler, heavy sculpt operation), ALL queued commands pile up. When the 300s timeout expires, the blocked client gets a "Command execution timed out" error. But any subsequently queued commands still wait their turn in the single-command-per-tick queue.

The existing scan noted single-command-per-tick as BUG-16 in integration scan. This is the additional observation that a FROZEN Blender causes a 300-second cascading timeout for ALL connected clients, not just the one whose command hung.

**Fix:** Add a per-command timeout that's shorter (e.g., 60s for typical operations, 300s only for known-slow operations like settlement generation). Also consider a heartbeat mechanism.

---

### BUG-EDGE-05: `NaN`/`Inf` in terrain heightmap data causes cascading math errors [MEDIUM]
**File:** `blender_addon/handlers/environment.py`, `terrain_sculpt.py`, `terrain_advanced.py`
**Severity:** MEDIUM (corrupted terrain silently propagates)

None of the terrain handlers validate that heightmap values are finite. If a heightmap contains `NaN` (from a division by zero in noise computation, or from corrupted input data):
- `math.sqrt(dx*dx + dy*dy)` with NaN inputs produces NaN
- Brush weight calculations with NaN produce NaN vertices
- NaN propagates through all downstream operations (material assignment, vegetation placement, building foundation calculation)
- Blender renders NaN vertices at the origin or not at all, creating invisible geometry

The `_terrain_noise.py` module has hash-based noise functions that could theoretically produce division-by-zero if the denominator in the interpolation is zero (though this is extremely unlikely with the current hash function).

**Fix:** Add `if not math.isfinite(value): value = 0.0` guards at terrain data input boundaries.

---

### BUG-EDGE-06: `compose_style_board` with 0 images creates a 0-width swatch crash [LOW]
**File:** `shared/fal_client.py` line 194
**Severity:** LOW (zero-division on empty palette)

```python
swatch_width = swatch_size * len(colors)
```

If `extract_color_palette` returns 0 colors (e.g., from a 1x1 image or error), `swatch_width` is 0. The `Image.new("RGB", (max(1, swatch_width), swatch_height), ...)` line handles this with `max(1, ...)`. However, `compose_style_board` calls `max(1, len(palette_colors))` on line 304:

```python
swatch_w = min(60, (board_width - padding * 2) // max(1, len(palette_colors)))
```

This is correctly guarded. No crash, but documenting that the `max(1, ...)` is load-bearing.

Actually wait -- looking more carefully at `extract_color_palette`, line 196-197:

```python
swatch_img = Image.new("RGB", (max(1, swatch_width), swatch_height), (0, 0, 0))
```

This IS guarded. Retracting this as not-a-bug.

---

## SCAN 5: Python Version & Compatibility

### BUG-PY-01: `list[str]` type hints in `blender_addon/security.py` require Python 3.9+ [MEDIUM]
**File:** `blender_addon/security.py` line 79, 212
**Severity:** MEDIUM (affects Blender 3.x with Python 3.10, but could affect older Blender)

```python
self.violations: list[str] = []
def validate_code(code: str) -> tuple[bool, list[str]]:
```

The blender_addon uses lowercase generic types (`list[str]`, `tuple[bool, list[str]]`). This requires Python 3.9+ (PEP 585). Blender 4.x bundles Python 3.11+, so this is fine for current Blender. But:
- Blender 3.6 LTS bundles Python 3.10 (OK)
- Blender 3.3 LTS bundles Python 3.10 (OK)

This is actually fine for all supported Blender versions. But the `int | None` union syntax (PEP 604) in `security.py` line 181:

```python
def _is_large_literal(node) -> int | None:
```

This requires Python 3.10+. Blender 3.3+ all have 3.10+, so this is fine. No issue found.

---

### BUG-PY-02: `pyproject.toml` requires Python >= 3.12 but some features may need 3.12 specifics [LOW]
**File:** `pyproject.toml` line 4
**Severity:** LOW (informational)

```
requires-python = ">=3.12"
```

The MCP server requires Python 3.12+. However, the blender_addon runs in Blender's bundled Python (3.11 in Blender 4.0-4.2). Since the addon and server are separate processes communicating via TCP, this is fine -- the addon doesn't need to satisfy `requires-python`. But if someone tries to `pip install` the package into Blender's Python for testing, it would be rejected.

The addon code itself avoids 3.12-only features (no `type` statement, no improved f-string parsing). I found no walrus operators (`:=`) or `match/case` statements in the blender_addon directory. This is correct.

---

### BUG-PY-03: `list[str]` annotations in multiple blender_addon handler files [LOW]
**File:** `blender_addon/handlers/addon_toolchain.py` lines 24, 301-302, 303, 305, etc.
**Severity:** LOW (works with Python 3.10+ which is minimum Blender version)

Multiple handler files use `list[str]`, `dict[str, Any]`, `tuple[str, ...]`, `set[str]`, `frozenset[str]` in function signatures and variable annotations. All of these require Python 3.9+ (runtime) or `from __future__ import annotations` (any version).

Notably, `addon_toolchain.py` does NOT have `from __future__ import annotations` but uses these annotations as runtime type hints. This works in Python 3.9+ but would fail in 3.8. Since Blender 3.0+ ships Python 3.10+, this is fine.

No actual bug found.

---

## SCAN SUMMARY

### New Bugs Found: 15

| ID | Severity | Category | Summary |
|----|----------|----------|---------|
| SEC-01 | HIGH | Security | `mesh_name` injected unsanitized into f-string execute_code |
| SEC-02 | LOW | Security | Theoretical sandbox bypass via isinstance.__class__ |
| SEC-03 | MEDIUM | Security | `safe_path` escaping doesn't strip newlines |
| SEC-04 | MEDIUM | Security | bpy.ops export/delete operations not blocked in sandbox |
| SEC-05 | LOW | Security | No authentication on localhost TCP socket |
| ERR-01 | MEDIUM | Error handling | `except Exception: pass` in compose_map (5+ sites) |
| ERR-02 | HIGH | Error handling | BMesh free() leak in worldbuilding UV/repair loops |
| ERR-03 | LOW | Error handling | Rate limit detection by string matching in ElevenLabs |
| ERR-04 | MEDIUM | Error handling | TripoStudio 429 errors not retried (wrong exception type) |
| ERR-05 | MEDIUM | Error handling | Gemini REST fallback missing IndexError catch |
| CFG-01 | MEDIUM | Config | httpx used but not declared in pyproject.toml |
| CFG-02 | LOW | Config | .mcp.json uses non-standard ${VAR} syntax |
| CFG-03 | LOW | Config | ESRGAN path default is Windows-specific |
| EDGE-01 | MEDIUM | Edge case | _sample_terrain_height returns 0.0 on failure (ambiguous) |
| EDGE-03 | MEDIUM | Edge case | Single-quote in object names breaks f-string code generation |
| EDGE-04 | HIGH | Edge case | Frozen Blender causes 300s cascading timeout for all clients |
| EDGE-05 | MEDIUM | Edge case | NaN/Inf in terrain heightmap propagates silently |

### Priority Fixes

**Fix immediately (HIGH):**
1. **SEC-01**: Sanitize all names before f-string interpolation into execute_code
2. **ERR-02**: Add try/finally around BMesh operations in worldbuilding loops
3. **EDGE-04**: Add shorter per-command timeouts and consider heartbeat

**Fix soon (MEDIUM):**
4. **SEC-03**: Strip newlines from file paths before code interpolation
5. **SEC-04**: Expand BLOCKED_BPY_ATTRS to include export operations
6. **ERR-01**: Replace `except Exception: pass` with logging in compose_map
7. **ERR-04**: Handle 429 status codes properly in tripo_studio_client
8. **ERR-05**: Add IndexError to gemini_client catch clause
9. **CFG-01**: Add httpx to pyproject.toml dependencies
10. **EDGE-03**: Escape single quotes in object names for code strings
11. **EDGE-05**: Add NaN guards at terrain data boundaries
