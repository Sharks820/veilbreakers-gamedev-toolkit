# Deep Bug Scan: Tripo AI Integration, Asset Pipeline & Export Systems

**Date:** 2026-04-02
**Scope:** tripo_client.py, tripo_studio_client.py, pipeline_runner.py, blender_server.py (asset_pipeline handler), model_validation.py, glb_texture_extractor.py, tripo_post_processor.py, delight.py, export.py, blender_client.py
**Severity scale:** CRITICAL (crashes or wastes money), HIGH (data loss or silent failure), MEDIUM (wrong behavior), LOW (code quality)

---

## CRITICAL BUGS

### BUG-01: `generate_prop` passes wrong keyword argument to TripoStudioClient -- CRASH

**File:** `blender_server.py` line 2556-2558
**Severity:** CRITICAL (crashes every generate_prop call using studio credits)

```python
gen = TripoStudioClient(
    session_cookie=studio_cookie or None,
    jwt_token=studio_token or None,       # <--- WRONG KEYWORD
)
```

`TripoStudioClient.__init__` accepts `session_token`, NOT `jwt_token`. This raises a `TypeError: __init__() got an unexpected keyword argument 'jwt_token'` every time `generate_prop` is invoked with studio credentials.

The `generate_3d` and `generate_building` actions use the correct keyword `session_token`. Only `generate_prop` is broken.

**Impact:** Every attempt to generate a prop via Tripo Studio will crash. The user may then repeatedly retry, not understanding why it fails. No API credits are wasted (the call never reaches the API), but the feature is 100% broken for studio users.

**Fix:**
```python
gen = TripoStudioClient(
    session_cookie=studio_cookie,
    session_token=studio_token,
)
```

---

### BUG-02: `generate_building` and `generate_prop` API-key paths never close the TripoGenerator

**File:** `blender_server.py` lines 2478-2485, 2576-2583
**Severity:** MEDIUM (resource leak, minor)

In the `generate_building` and `generate_prop` actions, when using the API-key fallback path (`TripoGenerator`), the generator object is never wrapped in try/finally and `gen.close()` is never called. Compare with `generate_3d` which properly calls `gen.close()` in a finally block (line 2374).

Currently `TripoGenerator.close()` is a no-op, so this is not actively harmful, but if the SDK ever adds resource cleanup it will leak.

**Fix:** Wrap in try/finally like the other code paths.

---

### BUG-03: `generate_building` and `generate_prop` skip post-processing and Blender import -- MONEY WASTE

**File:** `blender_server.py` lines 2461-2485 (generate_building), 2560-2583 (generate_prop)
**Severity:** HIGH (significant usability gap, wasted manual effort)

The `generate_3d` action performs a full post-processing chain after downloading from Tripo:
1. Post-process GLB (extract textures, de-light albedo, validate palette, score)
2. Auto-import all variants into Blender in a grid layout
3. Attach `texture_channels` to each variant for downstream wiring

The `generate_building` and `generate_prop` actions do NONE of this. They just return the raw download result. The user then has to manually:
- Run `import_model` for each variant
- Manually extract textures
- Manually figure out which variant is best (no scoring)

This means every building/prop generation costs the same Tripo credits but delivers significantly less value. The user pays for 4 variants but gets no automated quality scoring to pick the best one.

**Fix:** Share the post-processing and auto-import logic from `generate_3d` into `generate_building` and `generate_prop`. Extract it into a helper function to avoid the massive code duplication.

---

### BUG-04: `full_asset_pipeline` export uses `selected_only=True` but never selects the object

**File:** `pipeline_runner.py` lines 1079-1086
**Severity:** HIGH (export may export wrong objects or nothing)

```python
export_result = await self._run_step(
    "export",
    export_cmd,
    {
        "filepath": export_path,
        "selected_only": True,      # <--- requires object to be selected
        "apply_modifiers": True,
    },
    ...
)
```

The pipeline runs many Blender commands (repair, UV, material, LOD, etc.) and none of them guarantee that the target object remains selected in Blender after completion. By the time we reach the export step, the Blender selection state is undefined.

Possible outcomes:
- Nothing is selected: export produces an empty file (0 meshes)
- Wrong objects are selected: export includes stale objects from previous operations
- LOD objects are selected but not the main object: partial export

The `batch_process` method has the same bug (line 497): exports with `selected_only=True` without selecting first.

**Fix:** Add a select-object command before the export step:
```python
await self.blender.send_command("execute_code", {
    "code": f'import bpy\nbpy.ops.object.select_all(action="DESELECT")\nobj = bpy.data.objects.get("{name}")\nif obj: obj.select_set(True); bpy.context.view_layer.objects.active = obj'
})
```

---

## HIGH SEVERITY BUGS

### BUG-05: Multi-material GLB texture channels silently lost in pipeline wiring

**File:** `pipeline_runner.py` lines 190-207, `glb_texture_extractor.py` lines 269-313
**Severity:** HIGH (textures paid for but thrown away)

When a Tripo model has multiple materials, `extract_glb_textures` correctly appends material indices: `albedo_mat0`, `albedo_mat1`, `orm_mat0`, etc.

But `cleanup_ai_model` only looks for exact keys `"albedo"`, `"albedo_delit"`, `"normal"`, `"orm"`:
```python
if channels.get("albedo_delit"):
    tex_params["albedo_delit_path"] = channels["albedo_delit"]
elif channels.get("albedo"):
    tex_params["albedo_path"] = channels["albedo"]
```

For ANY multi-material model (which many Tripo outputs are), none of the texture channels will be wired. The pipeline falls through to the `else` branch and creates a blank Principled BSDF placeholder material, completely discarding the extracted textures.

**Impact:** User pays for Tripo generation, textures are extracted to disk but never applied. The model appears with a blank grey material. User thinks Tripo didn't generate textures.

**Fix:** Handle the `_mat{N}` suffix pattern. For single-material models, check both `"albedo"` and `"albedo_mat0"`. For multi-material, wire each material separately.

---

### BUG-06: `tripo_post_processor` only processes first material of multi-material models

**File:** `tripo_post_processor.py` lines 118-149, `glb_texture_extractor.py`
**Severity:** HIGH (incomplete quality scoring for multi-material models)

`post_process_tripo_model` checks for `"albedo"` in channels dict for de-lighting, then validates palette on that single albedo. For multi-material models where keys are `"albedo_mat0"`, `"albedo_mat1"`, etc., the de-lighting and palette validation are completely skipped.

The scoring function `_score_channels` similarly only checks for `"albedo"` (not `"albedo_mat0"`), so multi-material models get systematically lower scores even when they have complete texture sets.

**Impact:** Variant scoring is biased against multi-material models, potentially causing the system to select worse single-material variants over better multi-material ones.

---

### BUG-07: `_download_file` in tripo_client.py retries ALL failures including validation failures

**File:** `tripo_client.py` lines 48-65
**Severity:** MEDIUM (wastes bandwidth, not credits)

```python
for attempt in range(max_retries):
    try:
        downloaded = await asyncio.to_thread(_do_download)
        validation = validate_generated_model_file(downloaded)
        if not validation.get("valid", False):
            Path(downloaded).unlink(missing_ok=True)
            raise RuntimeError("Downloaded model failed validation: ...")
    except Exception as exc:
        last_exc = exc
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)
```

If the download succeeds but validation fails (e.g., corrupted model from Tripo's servers), the code retries the download 3 times. This is correct for transient corruption but will re-download an inherently corrupt model 3 times for deterministic failures. The wait time compounds: 1s + 2s + failure = 3s wasted.

Not a major issue since it doesn't waste API credits (the task already completed), but it does waste time and bandwidth.

---

### BUG-08: `generate_3d` output_dir can fall back to `.` (current working directory)

**File:** `blender_server.py` lines 2207-2224
**Severity:** MEDIUM (files written to unexpected location)

The `output_dir` parameter defaults to `"."`. If `settings.unity_project_path` is not set AND no `name` or `asset_type` is specified, the models land in whatever the MCP server's CWD happens to be. The code does have a tempdir fallback at line 2218, but only when `output_dir == "."` AND `_vb3d` is falsy AND the first two conditions don't match.

The fallback chain is:
1. Unity project asset folder (if unity_project_path + asset_type)
2. Unity project Tripo_Downloads folder (if unity_project_path)
3. Temp directory with timestamp
4. Literal `"."` (this case shouldn't be reachable but the logic is fragile)

This is actually handled correctly in practice, but the code structure is confusing and could break if conditions change.

---

## MEDIUM SEVERITY BUGS

### BUG-09: Tripo Studio JWT regex extraction is fragile

**File:** `tripo_studio_client.py` lines 105-111
**Severity:** MEDIUM (can break when Tripo updates their page)

```python
jwts = re.findall(
    r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"
    r"\.[A-Za-z0-9_-]{20,}",
    body,
)
if not jwts:
    raise RuntimeError("Failed to extract JWT from studio page...")
jwt = jwts[0]
```

This scrapes the HTML of `studio.tripo3d.ai` to find JWT tokens. Issues:
- Takes the FIRST JWT found, which may not be the right one if the page embeds multiple tokens
- If Tripo moves to a SPA that loads JWTs via XHR instead of embedding in HTML, this breaks silently
- No validation that the found JWT actually works before returning it

**Impact:** Could silently use a wrong or expired token, leading to confusing API errors downstream.

---

### BUG-10: `TripoStudioClient._ensure_client` leaks old client on JWT refresh race

**File:** `tripo_studio_client.py` lines 143-158
**Severity:** LOW (minor resource leak under race conditions)

```python
async def _ensure_client(self) -> httpx.AsyncClient:
    jwt = await self._get_valid_jwt()
    if self._client and not self._client.is_closed and self._client_jwt == jwt:
        return self._client
    if self._client and not self._client.is_closed:
        await self._client.aclose()     # <--- closes old client
    self._client = httpx.AsyncClient(...)
```

If two async tasks call `_ensure_client` concurrently during a JWT refresh, they could both close the old client and create new ones, but only the last one's client gets stored in `self._client`. The first task's client is orphaned (never closed).

This is unlikely in practice since MCP tools are typically called sequentially, but the code is not async-safe.

---

### BUG-11: `generate_3d` variant import code swallows Blender errors silently

**File:** `blender_server.py` lines 2291-2302
**Severity:** MEDIUM (user doesn't know import failed)

```python
try:
    import_result = await blender.send_command("execute_code", {"code": code})
    imported_names.append(f"variant_{i+1}")
except Exception as exc:
    logger.debug("Failed to import variant %s into Blender: %s", i + 1, exc, exc_info=True)
```

When a variant fails to import into Blender (e.g., corrupt GLB, Blender out of memory), the error is logged at DEBUG level only. The result dict still shows `"imported_to_blender": N` where N counts only successful imports, but there's no indication of which variants failed or why.

The user sees "3 variants imported" and assumes all 4 were fine, when actually 1 failed silently.

**Fix:** Add failed variant info to the result:
```python
result["import_failures"] = [{"variant": i+1, "error": str(exc)} for ...]
```

---

### BUG-12: `tripo_post_processor` silently swallows de-lighting errors

**File:** `tripo_post_processor.py` lines 136-138
**Severity:** MEDIUM (quality degradation goes unreported)

```python
try:
    delight_result = delight_albedo(channels["albedo"], delit_out)
    if delight_result.get("correction_applied"):
        albedo_delit_path = delit_out
        result["albedo_delit"] = albedo_delit_path
except Exception:  # noqa: BLE001
    pass  # Non-fatal; proceed with raw albedo for validation
```

If de-lighting fails (e.g., numpy not installed, image file corrupted), the error is completely swallowed. The raw albedo is used for validation instead, which may have baked-in lighting that throws off palette validation scores.

The result dict should at minimum include a warning that de-lighting was skipped and why.

---

### BUG-13: `delight_albedo` fails silently when numpy is missing

**File:** `delight.py` lines 76-77
**Severity:** MEDIUM (returns error dict instead of raising, caller may not check)

```python
if not _HAS_NUMPY:
    return {"error": "numpy is required for this operation but is not installed"}
```

This returns a dict with an `error` key but no `correction_applied` key. The caller in `tripo_post_processor.py` checks `delight_result.get("correction_applied")` which will be `None` (falsy), so de-lighting is silently skipped. No crash, but also no indication to the user that their entire post-processing pipeline is degraded because numpy is missing.

---

### BUG-14: GLB declared length check allows mismatched files through

**File:** `model_validation.py` lines 79-83
**Severity:** MEDIUM (truncated files may pass validation)

```python
result["checks"]["declared_length"] = {
    "passed": declared_length == actual_length,
    "value": declared_length,
    "actual": actual_length,
}
```

The declared_length check correctly detects mismatches, but the overall validation at line 46-48 requires ALL checks to pass:
```python
result["valid"] = all(
    check.get("passed", False) for check in result["checks"].values()
)
```

This is actually correct. However, the check does NOT handle the case where the file is truncated WITHIN the binary chunk (the JSON chunk parses fine but the BIN chunk is incomplete). A partially downloaded GLB can have valid magic, valid JSON chunk, valid declared length (if the connection dropped after reading the full header), but a truncated binary blob. The model_validation code doesn't verify the BIN chunk exists or is complete.

**Impact:** A partially downloaded model could pass validation and then crash Blender during import.

**Fix:** Add a BIN chunk completeness check.

---

### BUG-15: `TripoStudioClient._download_file` doesn't verify Content-Length

**File:** `tripo_studio_client.py` lines 235-259
**Severity:** MEDIUM (partial downloads not detected before writing to disk)

The download streams chunks to disk but doesn't check the `Content-Length` header against actual bytes received. If the connection drops mid-download, the file is written incompletely.

The `validate_generated_model_file` call afterward catches GLB corruption (magic bytes, JSON chunk), but for large files where the GLB header and JSON chunk are downloaded correctly, a truncated BIN chunk (containing mesh/texture data) would not be caught (see BUG-14).

The combination of BUG-14 + BUG-15 means a partially downloaded model could pass all validation and then crash or produce corrupt results in Blender.

**Fix:** Check Content-Length vs actual bytes received before validation.

---

## LOW SEVERITY ISSUES

### BUG-16: Code duplication across generate_3d, generate_building, generate_prop

**File:** `blender_server.py` lines 2182-2585
**Severity:** LOW (maintenance burden)

The three Tripo generation actions each contain nearly identical credential-checking logic, client instantiation, and result formatting, but with subtle differences (BUG-01 is a direct consequence of this duplication). The `generate_3d` action has post-processing and auto-import; the others don't (BUG-03).

**Recommendation:** Extract a shared helper:
```python
async def _tripo_generate(prompt, image_path, output_dir, settings, post_process=True) -> dict:
```

---

### BUG-17: `__import__("pathlib").Path` used instead of existing Path import

**File:** `blender_server.py` lines 2199, 2203, etc.
**Severity:** LOW (code smell, no functional impact)

`pathlib.Path` is already imported at the top of several modules. Using `__import__("pathlib").Path` is an anti-pattern that may have been introduced by copy-paste.

---

### BUG-18: `pipeline_runner.py` import step doesn't pass `bpy` import

**File:** `pipeline_runner.py` lines 914-918
**Severity:** LOW (may fail if bpy is not in Blender's auto-import namespace)

```python
import_code = (
    f'_pre = set(o.name for o in bpy.data.objects)\n'
    f'bpy.ops.{op}(filepath="{safe_path}")\n'
    ...
)
```

The code references `bpy` without importing it first. The Blender execute_code handler likely has `bpy` in its namespace, but this is an implicit dependency. Compare with the import code in `blender_server.py` line 2280 which explicitly starts with `import bpy`.

---

### BUG-19: `tripo_client.py` creates new client on EVERY retry attempt

**File:** `tripo_client.py` lines 123-124
**Severity:** LOW (unnecessary overhead)

```python
for attempt in range(3):
    client = _create_tripo_client(self.api_key)
```

A new `tripo3d.TripoClient` is instantiated on each retry. The previous client is closed in the `finally` block, but this means 3 separate HTTP sessions for one operation. If the client does any auth handshake, this is unnecessary overhead.

---

## PATH & CROSS-PLATFORM CONCERNS

### PATH-01: Forward slash normalization is inconsistent

The codebase has multiple `replace("\\", "/")` calls (lines 2256, 2346, 2705, 2761, 913) for Blender path safety. This is correct because Blender's Python on Windows can handle forward slashes.

However, the `delight.py` module uses `os.makedirs(os.path.dirname(output_path), ...)` which relies on OS-native path handling. Similarly, `glb_texture_extractor.py` uses `Path(path).write_bytes()`. These are fine because they run on the MCP server side, not in Blender.

**Status:** No actual bug, but the inconsistency between server-side (OS paths) and Blender-side (forward slashes) code could cause confusion during maintenance.

### PATH-02: Filename escaping for Blender code injection

**File:** `blender_server.py` lines 2256, 2346, 2705
**Pattern:** `safe = m["path"].replace("\\", "/").replace('"', '\\"')`

This escaping handles basic quote injection but NOT:
- Newlines in paths (unlikely but possible on some OSes)
- Unicode characters that could break Python string parsing
- Paths containing `\n` or `\t` literal sequences

For Windows OneDrive paths with spaces (like this project's path), the current escaping works. But adversarial filenames could inject arbitrary Python code into the Blender execute_code call. This is low risk since the paths come from Tripo download (controlled) or user input (trusted).

---

## CREDIT WASTE ANALYSIS

### CREDIT-01: Studio client defaults to 4 variants (max_variants=4)

**File:** `tripo_studio_client.py` line 327
**Severity:** INFO

Every `generate_from_text` call requests and downloads up to 4 variants by default. For simple props (barrel, crate), 4 variants is overkill. Each variant consumes studio credits.

The `generate_3d` action in blender_server.py doesn't override `max_variants`, so every generation always downloads 4 variants even when the user only needs one.

**Recommendation:** Add a `max_variants` parameter to the asset_pipeline generate_3d action, defaulting to 2 for props and 4 for complex assets.

### CREDIT-02: generate_building and generate_prop don't expose model_version parameter

These actions always use the client's default model version. If the user wants a cheaper/faster lower-quality generation for testing, they can't request it without going through `generate_3d` directly.

---

## TIMEOUT & ERROR HANDLING ANALYSIS

### TIMEOUT-01: Blender TCP connection handles disconnects well

**File:** `blender_client.py` lines 207-234

The `_sync_send` method retries once on connection failure with transparent reconnection. The `_receive_exactly` method gives clear error messages on partial reads and timeouts. The 300-second default timeout is appropriate for long-running Blender operations.

**Status:** GOOD -- no issues found.

### TIMEOUT-02: Tripo Studio polling has good adaptive behavior

**File:** `tripo_studio_client.py` lines 203-233

The `wait_for_task` method uses `running_left_time` from the API response to adapt polling intervals. Timeout handling is correct with `time.monotonic()`. Failed/banned/cancelled states are properly detected.

**Status:** GOOD -- well implemented.

### TIMEOUT-03: Pipeline failure doesn't clean up partial state

**File:** `pipeline_runner.py` throughout

If the pipeline fails midway (e.g., at Step 5 "quality gate"), partially created LOD objects, UV layers, and materials remain in the Blender scene. There's no rollback mechanism.

**Severity:** LOW (expected behavior for a Blender pipeline, user can undo manually)

---

## STATE LEAKAGE ANALYSIS

### STATE-01: Pipeline called twice on same object is safe

The `cleanup_ai_model` method doesn't check if the object was already processed. Running it twice would:
- Re-repair (idempotent -- removing doubles on an already-clean mesh is a no-op)
- Re-UV unwrap (overwrites existing UVs -- data loss but not corruption)
- Re-apply material (adds another material slot -- may cause issues)

**Severity:** MEDIUM -- running the pipeline twice on the same object adds duplicate material slots. Should check for existing materials.

### STATE-02: Global `_connection` singleton is thread-safe

The `get_blender_connection()` uses double-checked locking with a threading lock. The `BlenderConnection._sync_send` uses `_send_lock` to serialize commands. This is correct for the MCP server's async model (which runs on a single thread with async concurrency).

**Status:** GOOD

---

## SUMMARY OF REQUIRED FIXES (by priority)

| # | Severity | Bug | Effort |
|---|----------|-----|--------|
| 1 | CRITICAL | BUG-01: `generate_prop` uses wrong keyword `jwt_token` instead of `session_token` | 1 min |
| 2 | HIGH | BUG-04: Export uses `selected_only=True` without selecting object first | 5 min |
| 3 | HIGH | BUG-05: Multi-material texture channels silently lost in pipeline wiring | 30 min |
| 4 | HIGH | BUG-03: generate_building/generate_prop skip post-processing and Blender import | 1 hr |
| 5 | HIGH | BUG-06: Post-processor scoring biased against multi-material models | 20 min |
| 6 | MEDIUM | BUG-11: Variant import failures swallowed silently | 10 min |
| 7 | MEDIUM | BUG-12 + BUG-13: De-lighting errors swallowed, numpy missing unreported | 10 min |
| 8 | MEDIUM | BUG-14 + BUG-15: Partial downloads can pass validation | 30 min |
| 9 | LOW | BUG-16: Extract shared Tripo generation helper to eliminate duplication | 1 hr |
| 10 | LOW | BUG-02: Missing gen.close() in API-key fallback paths | 5 min |
