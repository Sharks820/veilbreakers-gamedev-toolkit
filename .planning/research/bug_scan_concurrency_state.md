# Bug Scan: Concurrency, Race Conditions & State Management

**Date:** 2026-04-02
**Scope:** TCP communication, module-level mutable state, async/await, file system races, Blender state corruption
**Method:** Deep code review of blender_client.py, socket_server.py, all handlers/, shared/ modules
**Prior scans referenced:** 13 previous scans (~186 bugs). Only NEW bugs reported below.

---

## Previously Found (NOT repeated here)

These were already identified in prior scans:
- BUG-05 (handlers scan): `_features_gen`/`_features_seed` global mutable state in terrain_features.py
- BUG-10 (tripo scan): `TripoStudioClient._ensure_client` race on JWT refresh
- BUG-165 (remaining scan): `tempfile.mktemp` TOCTOU in _tool_runner.py
- BUG-169 (remaining scan): fal_client env var set before availability check
- ERR-02 (security scan): BMesh free() leak in worldbuilding UV/repair loops
- STATE-02 (tripo scan): Confirmed `_connection` singleton is thread-safe via double-checked locking (NOT a bug)

---

## MISSION 1: TCP Communication Race Conditions

### BUG-RC-01: Stale response after timeout+retry causes response misalignment [MEDIUM]

**File:** `shared/blender_client.py`, lines 207-234
**Severity:** MEDIUM (can cause wrong response returned to wrong command)

**The scenario:**
1. Client sends Command A, waits for response
2. Blender is slow, socket `recv` times out
3. `_sync_send` catches the error, calls `disconnect()` (closes socket), then retries
4. Retry creates a new socket, sends Command A again, gets correct response

This works correctly for the retry case. However, consider:
1. Client sends Command A via socket S1
2. Blender starts processing Command A
3. Network hiccup causes `recv` to fail (not timeout -- a transient error)
4. Client disconnects S1, reconnects with S2, sends Command A again
5. Blender finishes original Command A, tries to send response on S1 -- but S1 is closed server-side (the server thread for S1 gets a broken pipe)
6. Meanwhile Blender's command queue also receives Command A from S2

**The server-side behavior is actually safe** because each client socket gets its own `_handle_client` thread, and the command queue uses `threading.Event` per command. The orphaned S1 command result simply gets written to a container that nobody reads (S1's `_handle_client` thread will fail on `sendall` and exit cleanly).

**However**, there is no deduplication of commands. If the same expensive operation (e.g., terrain generation with seed=42) is sent twice due to retry, Blender executes it twice. This wastes time but does not corrupt state since commands execute sequentially on the main thread.

**Verdict:** Not a data corruption bug, but a **duplicate work issue**. The retry mechanism can cause expensive Blender operations to execute twice. The first execution's result is thrown away.

**Fix:** Add a command ID / idempotency token so the server can deduplicate retried commands.

---

### BUG-RC-02: `_process_commands` processes only one command per 10ms tick, creating head-of-line blocking [LOW-MEDIUM]

**File:** `blender_addon/socket_server.py`, line 167-203
**Severity:** LOW-MEDIUM (performance issue under concurrent clients)

The Blender timer callback `_process_commands` dequeues exactly ONE command per tick (10ms interval). If multiple MCP clients send commands simultaneously, they queue up. A single 30-second terrain generation blocks ALL subsequent commands for 30 seconds -- including lightweight queries like `get_viewport_screenshot`.

This is documented as intentional ("Process one command per tick to avoid freezing Blender UI"), but the design means:
- No priority system for fast vs. slow commands
- A contact_sheet request after a terrain gen waits for the full terrain to complete
- No way to cancel a long-running command

**Not a correctness bug** but a design limitation that can cause apparent hangs.

---

### BUG-RC-03: `_handle_client` 30s idle timeout drops persistent connections during slow pipelines [LOW]

**File:** `blender_addon/socket_server.py`, line 93
**Severity:** LOW (handled gracefully by client reconnect, but wastes time)

```python
client_sock.settimeout(30.0)
```

After a client receives a response, the server waits up to 30s for the next command on the same socket. If the MCP server takes >30s processing the response (e.g., downloading a Tripo model, running post-processing), the server drops the persistent connection. The client then reconnects for the next command, adding ~2-5ms latency.

**Already noted in integration scan** but as a design choice. Including here for completeness since it interacts with the retry logic in BUG-RC-01.

---

## MISSION 2: Module-Level Mutable State

### BUG-MS-01: `fal_client.generate_concept_art` and `texture_ops.inpaint_texture` race on `os.environ["FAL_KEY"]` [HIGH]

**Files:** `shared/fal_client.py` lines 72-137, `shared/texture_ops.py` lines 799-823
**Severity:** HIGH (silent credential leak or API auth failure)

Both functions follow the pattern:
```python
prev_fal_key = os.environ.get("FAL_KEY")
os.environ["FAL_KEY"] = fal_key  # Mutate process-global state
try:
    _fal.subscribe(...)
finally:
    if prev_fal_key is not None:
        os.environ["FAL_KEY"] = prev_fal_key
    else:
        del os.environ["FAL_KEY"]
```

The MCP server is async. If two async tool calls execute concurrently (e.g., one generating concept art while another inpaints a texture), the interleaving is:
1. Task A sets `FAL_KEY` to key_A
2. Task B sets `FAL_KEY` to key_B (overwriting key_A)
3. Task A calls `_fal.subscribe()` -- uses key_B instead of key_A
4. Task A's `finally` restores to `prev_fal_key` (which was whatever was set before A)
5. Task B's `finally` restores to key_B's prev (which was key_A, already overwritten)

**Impact:** Wrong API key used, or env left in inconsistent state. In practice the MCP server likely uses the same key for all calls, but the pattern is fundamentally broken for concurrent use.

**Note:** BUG-169 from the remaining files scan found a different sub-bug (env set before availability check). This bug is about the concurrent race between two functions that both mutate the same env var.

**Fix:** Pass the API key directly to the fal-client call instead of using env vars, or use a threading lock around the env mutation.

---

### BUG-MS-02: `_audio_client` module-level singleton in `unity_tools/audio.py` has no thread safety [LOW]

**File:** `src/veilbreakers_mcp/unity_tools/audio.py`, lines 215-226
**Severity:** LOW (unlikely to cause issues in practice)

```python
_audio_client: ElevenLabsAudioClient | None = None

def _get_audio_client() -> ElevenLabsAudioClient:
    global _audio_client
    if _audio_client is None:
        _audio_client = ElevenLabsAudioClient(...)
    return _audio_client
```

No lock protects initialization. If two async tasks call `_get_audio_client()` concurrently during the first invocation, two clients could be created and one leaked. In practice, the MCP server runs on a single thread with async concurrency (no true parallelism), so the check-then-act is safe because `asyncio` won't preempt between the `if` and assignment. But this relies on implementation details of asyncio.

**Fix:** Add a lock, or accept the current behavior with a comment explaining why it's safe.

---

### BUG-MS-03: `_AST_GREP_CMD` global in `_tool_runner.py` caches forever, even if tool is installed later [LOW]

**File:** `src/veilbreakers_mcp/_tool_runner.py`, lines 71-78
**Severity:** LOW (only affects code reviewer tool discovery)

```python
_AST_GREP_CMD = None

def _get_ast_grep() -> Optional[str]:
    global _AST_GREP_CMD
    if _AST_GREP_CMD is None:
        _AST_GREP_CMD = _which("sg") or _which("ast-grep") or ""
    return _AST_GREP_CMD or None
```

Once `_AST_GREP_CMD` is set to `""` (not found), it's cached forever. If the user installs ast-grep during a session, it won't be detected until the MCP server restarts. The empty string `""` is truthy for `is None` check, so subsequent calls return `None` correctly. **Actually this is fine** -- the cache returns `""`, and `or None` converts it to `None`. Not a bug.

**Verdict:** FALSE POSITIVE. Removing from count.

---

### BUG-MS-04: `_cs_parser` and `_py_parser` globals in `_ast_analyzer.py` are not thread-safe [LOW]

**File:** `src/veilbreakers_mcp/_ast_analyzer.py`, lines 51-63
**Severity:** LOW (tree-sitter parsers are generally thread-safe for different inputs)

```python
_cs_parser = None
_py_parser = None

def _get_cs_parser() -> "Parser":
    global _cs_parser
    if _cs_parser is None:
        _cs_parser = Parser(_CS_LANG)
    return _cs_parser
```

Same check-then-act pattern. If called concurrently, two parsers may be created and one leaked. Parser objects are lightweight so the impact is minimal.

---

## MISSION 3: Async/Await Issues

### BUG-AS-01: `TripoGenerator` creates and closes a `tripo3d.TripoClient` per attempt but `close()` may be a no-op [LOW]

**File:** `shared/tripo_client.py`, lines 123-191
**Severity:** LOW (resource leak if tripo3d SDK client holds connections)

Each retry attempt creates a new `_create_tripo_client()` and calls `client.close()` in `finally`. If the tripo3d SDK's `close()` returns a coroutine, it's properly awaited. If `close()` is sync, it's fine. But if the SDK internally holds an httpx.AsyncClient that needs `aclose()`, calling sync `close()` from an async context might not actually close the underlying connection pool.

The code handles both sync and async close:
```python
coro = client.close()
if asyncio.iscoroutine(coro):
    await coro
```

This is correct. **Actually not a bug.** Removing from count.

---

### BUG-AS-02: `TripoStudioClient._ensure_client` can leak an `httpx.AsyncClient` on concurrent calls [MEDIUM]

**File:** `shared/tripo_studio_client.py`, lines 143-158
**Severity:** MEDIUM (connection pool leak)

```python
async def _ensure_client(self) -> httpx.AsyncClient:
    jwt = await self._get_valid_jwt()           # <-- await here
    if self._client and not self._client.is_closed and self._client_jwt == jwt:
        return self._client
    if self._client and not self._client.is_closed:
        await self._client.aclose()             # <-- close old client
    self._client = httpx.AsyncClient(...)       # <-- create new
    self._client_jwt = jwt
    return self._client
```

**Already found as BUG-10 in tripo scan.** Confirmed -- two concurrent async tasks can both enter `_ensure_client`, both close the old client (double-close is safe due to `is_closed` check), but both create new clients and only the last one's assignment sticks.

**Skipping** -- already reported.

---

### BUG-AS-03: `ElevenLabsAudioClient._retry_on_rate_limit` uses `time.sleep()` which blocks the event loop [MEDIUM]

**File:** `shared/elevenlabs_client.py`, lines 112-123
**Severity:** MEDIUM (blocks entire MCP server during rate-limit backoff)

```python
@staticmethod
def _retry_on_rate_limit(fn, *args, max_retries: int = 3, **kwargs) -> Any:
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except (...) as exc:
            is_rate_limit = "429" in str(exc) or "rate" in str(exc).lower()
            if is_rate_limit and attempt < max_retries:
                time.sleep(2 ** (attempt + 1))  # BLOCKS EVENT LOOP
                continue
            raise
```

This is a sync function called from async handlers in `unity_tools/audio.py`. The `time.sleep(2 ** (attempt + 1))` call blocks for 2, 4, or 8 seconds. During this time, the entire async event loop is frozen -- no other MCP tool calls can be processed.

The ElevenLabs SDK functions (`client.text_to_sound_effects.convert`, etc.) are also sync blocking calls, but those are expected to be relatively fast. The rate-limit sleep is the bigger problem because it's explicitly long.

**Fix:** Either wrap the entire retry function in `asyncio.to_thread()`, or convert to an async retry with `await asyncio.sleep()`.

---

### BUG-AS-04: `fal_client.generate_concept_art` makes blocking `httpx.get()` call from sync function called in async context [MEDIUM]

**File:** `shared/fal_client.py`, lines 113-117
**Severity:** MEDIUM (blocks event loop during image download)

```python
resp = httpx.get(image_url, timeout=30.0, follow_redirects=True)
resp.raise_for_status()
```

This sync HTTP call blocks for up to 30 seconds. The function is called from the MCP server's async handler. While this blocks, no other MCP tool calls can execute.

Similarly, `_fal.subscribe()` on line 84 is also a sync blocking call.

**Fix:** Wrap in `asyncio.to_thread()` or use `httpx.AsyncClient`.

---

## MISSION 4: File System Race Conditions

### BUG-FS-01: `save_pipeline_checkpoint` writes directly to final path without atomic rename [MEDIUM]

**File:** `blender_addon/handlers/pipeline_state.py`, lines 41-81
**Severity:** MEDIUM (checkpoint corruption on crash during write)

```python
with open(path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, default=str)
```

If Blender crashes (or the process is killed) while `json.dump` is writing, the checkpoint file is left in a partially-written state. On next startup, `load_pipeline_checkpoint` reads the corrupted JSON and crashes with `json.JSONDecodeError`.

For a compose_map pipeline that takes 10+ minutes, losing the checkpoint means restarting from scratch.

**Fix:** Write to a temp file in the same directory, then `os.replace()` atomically:
```python
tmp_path = path + ".tmp"
with open(tmp_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, default=str)
os.replace(tmp_path, path)  # atomic on same filesystem
```

---

### BUG-FS-02: `capture_viewport_bytes` has TOCTOU between Blender writing screenshot and MCP reading it [LOW]

**File:** `shared/blender_client.py`, lines 280-301
**Severity:** LOW (unlikely in practice -- single-threaded command queue)

```python
async def capture_viewport_bytes(self) -> bytes:
    result = await self.send_command("get_viewport_screenshot", {"format": "png"})
    filepath = result.get("filepath", "")
    ...
    return await loop.run_in_executor(None, self._read_and_cleanup, filepath)
```

The screenshot is written by Blender (main thread), then read by the MCP server (different process). There's a window where the file exists but Blender hasn't fully flushed it. In practice, Blender completes the write before returning the command response, so this is safe. But if Blender's file buffering is OS-level (unlikely for image saves), partial reads are theoretically possible.

**Verdict:** Theoretical only. Not actionable in practice.

---

### BUG-FS-03: `AssetCatalog` SQLite connection is not thread-safe [MEDIUM]

**File:** `shared/asset_catalog.py`, lines 39-49
**Severity:** MEDIUM (SQLite "database is locked" errors under concurrent access)

```python
def __init__(self, db_path: str = "assets.db"):
    self.conn = sqlite3.connect(db_path)
```

SQLite connections are not thread-safe by default in Python. If two async tool calls share the same `AssetCatalog` instance and execute queries concurrently via `run_in_executor`, they'll hit "database is locked" errors or worse.

The current code doesn't use `check_same_thread=False`, which means SQLite will raise `ProgrammingError: SQLite objects created in a thread can only be used in that same thread` if accessed from a different thread than the one that created it.

Since MCP tools are async and may use `run_in_executor` for blocking operations, the catalog connection could be accessed from executor threads.

**Fix:** Either pass `check_same_thread=False` and add a threading lock around all operations, or create connections per-operation.

---

## MISSION 5: Blender State Corruption

### BUG-BS-01: Handlers set `view_layer.objects.active` without saving/restoring previous active object [MEDIUM]

**Files:** 50+ locations across mesh.py, equipment.py, rigging.py, curves.py, autonomous_loop.py, etc.
**Severity:** MEDIUM (silent state corruption affecting subsequent operations)

Pattern found in 50+ places:
```python
bpy.context.view_layer.objects.active = obj
bpy.ops.object.modifier_apply(...)
# Never restores previous active object
```

When a handler sets the active object to perform an operation, it never saves/restores the previous active object. If the user (or a previous MCP command) had a specific object selected/active, that context is silently lost.

**In the current architecture this is LOW risk** because:
1. Commands execute sequentially on Blender's main thread (one at a time via the command queue)
2. Each command typically works on explicitly named objects, not "whatever is active"
3. The MCP tools generally look up objects by name, not relying on active state

**However**, the `objects.py` handler does rely on active state:
```python
# objects.py line 110
obj = bpy.context.active_object
```
If a previous command changed the active object, this could silently operate on the wrong object.

**Fix:** Handlers that use `bpy.context.active_object` as input should require explicit object names instead. Handlers that set active object for operator calls should save/restore.

---

### BUG-BS-02: BMesh operations in `environment_scatter.py` lack try/finally guards on `bm.free()` [MEDIUM]

**File:** `blender_addon/handlers/environment_scatter.py`, multiple locations
**Severity:** MEDIUM (GPU memory leak on exception)

Several BMesh usage sites have correct `bm.free()` calls on the happy path but no `try/finally` to ensure cleanup on exception:

```python
# Line 704
bm = bmesh.new()
# ... 50 lines of vertex/face creation that could raise ValueError ...
bm.to_mesh(mesh)
bm.free()  # Never reached if exception above
```

Specific unguarded locations in environment_scatter.py:
- Line 704: `_create_tree_mesh` -- 50+ lines of vertex creation between new() and free()
- Line 785: `_create_grass_blade` -- 80+ lines between new() and free()
- Line 916 in environment.py: cave mesh -- 100+ lines between new() and free()

**Note:** ERR-02 from the security scan found BMesh leaks in worldbuilding UV/repair loops specifically. This bug covers the scatter and environment generators which were not in that finding.

**Fix:** Wrap all BMesh operations in try/finally:
```python
bm = bmesh.new()
try:
    # ... operations ...
    bm.to_mesh(mesh)
finally:
    bm.free()
```

---

### BUG-BS-03: `objects.py` handler reads `bpy.context.active_object` without verifying it matches the requested object [LOW-MEDIUM]

**File:** `blender_addon/handlers/objects.py`, lines 110, 131
**Severity:** LOW-MEDIUM (wrong object modified silently)

```python
# Line 110 (in select handler)
obj = bpy.context.active_object

# Line 131 (in another handler)
obj = bpy.context.active_object
```

These handlers rely on the active object being "correct" but don't verify it matches any expected name. If a previous command changed the active object (see BUG-BS-01), these handlers silently operate on the wrong object.

**Fix:** Accept explicit object name parameter and look up via `bpy.data.objects.get(name)`.

---

### BUG-BS-04: `mesh_enhance.py` reads `bpy.context.active_object` after `bpy.ops.object.duplicate()` without error checking [LOW]

**File:** `blender_addon/handlers/mesh_enhance.py`, line 576
**Severity:** LOW (crash if duplicate fails)

```python
bpy.context.view_layer.objects.active = obj
bpy.ops.object.duplicate()
high_poly = bpy.context.active_object  # Assumes duplicate set active
```

If `bpy.ops.object.duplicate()` fails (e.g., object is non-duplicatable or in wrong mode), `active_object` may still be `obj`, not the duplicate. Subsequent operations on `high_poly` would modify the original instead of the copy.

**Fix:** Check the return value of `bpy.ops.object.duplicate()` and verify `active_object` changed.

---

## Summary

| ID | Severity | Category | Description |
|----|----------|----------|-------------|
| BUG-RC-01 | MEDIUM | TCP | Retry mechanism causes duplicate Blender command execution |
| BUG-RC-02 | LOW-MEDIUM | TCP | Head-of-line blocking in command queue (1 cmd per 10ms tick) |
| BUG-MS-01 | HIGH | Mutable State | `os.environ["FAL_KEY"]` race between concurrent fal_client/texture_ops calls |
| BUG-MS-02 | LOW | Mutable State | `_audio_client` singleton lacks thread safety (safe in practice due to asyncio) |
| BUG-MS-04 | LOW | Mutable State | `_cs_parser`/`_py_parser` globals lack thread safety |
| BUG-AS-03 | MEDIUM | Async | `time.sleep()` in ElevenLabs retry blocks entire event loop |
| BUG-AS-04 | MEDIUM | Async | Sync `httpx.get()` in fal_client blocks event loop for up to 30s |
| BUG-FS-01 | MEDIUM | Filesystem | Pipeline checkpoint write not atomic -- corruption on crash |
| BUG-FS-03 | MEDIUM | Filesystem | SQLite AssetCatalog connection not thread-safe |
| BUG-BS-01 | MEDIUM | Blender State | 50+ handlers set active_object without save/restore |
| BUG-BS-02 | MEDIUM | Blender State | BMesh free() not guarded by try/finally in scatter/environment |
| BUG-BS-03 | LOW-MEDIUM | Blender State | objects.py reads active_object without verification |
| BUG-BS-04 | LOW | Blender State | mesh_enhance.py reads active_object after unverified duplicate |

**New bugs found:** 13 (excluding false positives and already-reported bugs)
**HIGH severity:** 1 (BUG-MS-01)
**MEDIUM severity:** 7 (BUG-RC-01, BUG-AS-03, BUG-AS-04, BUG-FS-01, BUG-FS-03, BUG-BS-01, BUG-BS-02)
**LOW-MEDIUM severity:** 3 (BUG-RC-02, BUG-BS-03)
**LOW severity:** 2 (BUG-MS-02, BUG-MS-04, BUG-BS-04)

### Priority Fix Order

1. **BUG-MS-01** (HIGH): FAL_KEY env var race -- pass key directly to SDK instead of env mutation
2. **BUG-AS-03** (MEDIUM): ElevenLabs `time.sleep` blocking event loop -- use `asyncio.to_thread`
3. **BUG-AS-04** (MEDIUM): fal_client sync HTTP blocking -- wrap in `asyncio.to_thread`
4. **BUG-FS-01** (MEDIUM): Checkpoint atomic write -- use temp file + `os.replace()`
5. **BUG-BS-02** (MEDIUM): BMesh try/finally guards in scatter/environment handlers
6. **BUG-FS-03** (MEDIUM): SQLite thread safety -- add `check_same_thread=False` + lock
7. **BUG-BS-01** (MEDIUM): Active object save/restore (large refactor, lower priority)
8. **BUG-RC-01** (MEDIUM): Command deduplication (nice to have, rare in practice)
