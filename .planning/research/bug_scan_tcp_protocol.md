# Deep Bug Scan: Blender TCP Communication Protocol

**Date:** 2026-04-02
**Scope:** Full command lifecycle from MCP tool call through TCP to Blender and back
**Files Analyzed:**
- `src/veilbreakers_mcp/shared/blender_client.py` (BlenderConnection - MCP side)
- `blender_addon/socket_server.py` (BlenderMCPServer - Blender side)
- `blender_addon/handlers/__init__.py` (COMMAND_HANDLERS dispatch)
- `src/veilbreakers_mcp/shared/models.py` (BlenderCommand / BlenderResponse)
- `src/veilbreakers_mcp/shared/config.py` (Settings / timeouts)
- `src/veilbreakers_mcp/blender_server.py` (connection management, tool layer)

---

## Protocol Architecture Summary

```
MCP Tool Call (async)
  -> BlenderConnection.send_command() [async wrapper]
    -> loop.run_in_executor(_sync_send) [offloaded to thread]
      -> _send_lock acquired (threading.Lock)
      -> lazy connect() if no socket
      -> _send_on_socket():
          - Pydantic model -> JSON bytes
          - Send: 4-byte big-endian length prefix + JSON payload
          - Recv: 4-byte length prefix + JSON response
          - Parse into BlenderResponse
      -> On failure: disconnect, retry once
  <- Return result or raise BlenderCommandError

Blender Side:
  _server_loop() [daemon thread]
    -> accept() connections
    -> spawn _handle_client() thread per connection
      -> Persistent connection loop:
        - Recv 4-byte length prefix
        - Recv JSON payload
        - Parse command
        - Put (command, Event, container) on command_queue
        - Event.wait(timeout=300)
      <- Main thread timer picks up command
  
  _process_commands() [bpy.app.timers, main thread, 10ms interval]
    -> queue.get_nowait() ONE command
    -> Look up handler in COMMAND_HANDLERS dict
    -> Execute handler(params) synchronously
    -> Store result in container, event.set()
```

---

## BUG CATEGORY: CRITICAL (System Stability)

### TCP-CRIT-01: Head-of-Line Blocking - Single Command Per Tick
**Location:** `socket_server.py:167-203` (`_process_commands`)
**Severity:** CRITICAL
**Status:** KNOWN (mentioned in prompt)

The timer processes exactly ONE command per tick (10ms interval). If a handler takes 5 seconds (e.g., terrain generation, mesh operations), ALL other queued commands are blocked for 5 seconds + 10ms. During this time:
- Other connected clients' threads are blocked on `result_event.wait(timeout=300)`
- No new commands can execute
- The Blender UI is frozen (handler runs on main thread)

**Impact:** A single expensive operation freezes the entire MCP pipeline. If an LLM fires multiple tool calls in parallel, they serialize through a single bottleneck.

**Fix:** This is inherent to Blender's architecture (bpy calls MUST run on main thread). Mitigation options:
1. Process multiple NON-bpy commands per tick (ping, read-only queries)
2. Add command priority levels (fast reads skip ahead of slow mutations)
3. Yield periodically in long handlers (cooperative multitasking via bpy.app.timers)

---

### TCP-CRIT-02: Frozen Handler Blocks All Clients Permanently
**Location:** `socket_server.py:167-203` (`_process_commands`)
**Severity:** CRITICAL
**Status:** KNOWN (mentioned in prompt)

If a handler raises an unhandled exception type NOT caught by the `except Exception` (e.g., `SystemExit`, `KeyboardInterrupt`), or if a handler enters an infinite loop / deadlock:
- The timer callback either crashes (gets silently unregistered by Blender) or never returns
- ALL clients waiting on `result_event.wait()` will block until their 300s timeout
- No new commands will ever execute
- The outer `except Exception` guard on line 200-202 catches most crashes, but NOT `BaseException` subclasses

Additionally, even if the outer guard catches the exception, it only prints to console and returns 0.01. The command that caused the crash still has its Event never set if the exception happens between `get_nowait()` and the `finally: event.set()`. Wait -- actually, looking more carefully at the code structure:

```python
try:
    cmd, event, container = self.command_queue.get_nowait()  # line 172
    try:
        ...execute handler...
        container["response"] = ...
    except Exception as e:
        container["response"] = {"status": "error", "message": str(e)}
    finally:
        event.set()  # line 199
except Exception as e:  # line 200 - OUTER guard
    print(f"[VeilBreakers MCP] Timer error: {e}")
```

The `event.set()` is in the inner `finally`. If the outer guard triggers (meaning the inner block raised something that escaped), the event is NOT set. The client thread would then wait 300 seconds before timing out. This can happen if `command_queue.get_nowait()` somehow raises something unexpected, though `queue.Empty` is handled separately. More realistically, if the `event.set()` call itself fails (corrupted Event object), the outer guard catches it but the client hangs.

**Fix:** Move `event.set()` into outer finally, or add a secondary timeout/watchdog.

---

### TCP-CRIT-03: No Command Cancellation or Abort Mechanism
**Location:** `socket_server.py:109-113`, `blender_client.py:207-234`
**Severity:** HIGH

Once a command is queued, there is no way to cancel it. If a client disconnects (timeout, user cancels), the command still executes on the main thread. The result is computed and placed in `result_container`, but nobody reads it. This wastes Blender main thread time on abandoned work.

Worse: if the MCP client retries after a timeout (which `_sync_send` does), the SAME logical command can execute TWICE -- once from the original queued entry and once from the retry.

**Fix:** 
1. Add a cancellation flag to the queue entry that `_process_commands` checks before executing
2. Add an idempotency token so duplicate commands are detected and skipped

---

### TCP-CRIT-04: No Idempotency Token
**Location:** Entire protocol
**Severity:** HIGH  
**Status:** KNOWN (mentioned in prompt)

The retry logic in `_sync_send` (lines 215-234) reconnects and resends on transient failure. But the original command may have already been queued and partially/fully executed. There is no idempotency token to detect duplicates.

**Scenario:**
1. Client sends "clear_scene" command
2. Blender receives it, queues it, starts executing
3. Client's recv times out (maybe the response was slow)
4. Client disconnects, reconnects, sends "clear_scene" again
5. Blender executes it a second time (no harm for clear_scene, but catastrophic for "create_object" or "execute_code")

**Fix:** Add a UUID `request_id` to BlenderCommand. Server tracks recently-completed IDs and returns cached response for duplicates.

---

## BUG CATEGORY: HIGH (Data Loss / Corruption)

### TCP-HIGH-01: Race Condition in Connection Singleton
**Location:** `blender_server.py:82-99` (`get_blender_connection`)
**Severity:** HIGH

The double-checked locking pattern has a subtle issue. Line 84 reads `_connection` outside the lock:

```python
if _connection is not None:
    return _connection  # No lock held
```

In Python's GIL model this is technically safe for reference reads, but the returned `BlenderConnection` object's `_socket` field could be in a torn state if another thread is calling `disconnect()` + `connect()` simultaneously. The `_send_lock` inside `BlenderConnection._sync_send` protects the send path, so this is mitigated. However, `capture_viewport_bytes` calls `send_command` which also uses `_send_lock`, so parallel screenshot + command would correctly serialize.

**Actual risk:** LOW due to `_send_lock`. But if anyone calls `is_alive()` from a different thread while `_sync_send` holds the lock, `is_alive()` does NOT acquire `_send_lock` and could read stale socket state.

**Fix:** Make `is_alive()` also acquire `_send_lock`, or document that it is advisory only.

---

### TCP-HIGH-02: 300-Second Event.wait() Timeout vs 300-Second Socket Timeout Mismatch
**Location:** `socket_server.py:113`, `blender_client.py:63`
**Severity:** HIGH

Both the Blender-side Event wait and the MCP-side socket timeout are 300 seconds. This creates a race:

1. MCP client sends command, socket timeout = 300s
2. Blender queues it, `result_event.wait(timeout=300)`
3. If the handler takes exactly ~300s, the Event times out, Blender sends "Command execution timed out"
4. But the MCP client's `_receive_exactly` may ALSO have timed out at the socket level
5. The client gets `socket.timeout`, triggers retry logic
6. Now there are TWO commands in flight and the response from the first is lost

The server-side event timeout and client-side socket timeout should have different values, with the server timeout being shorter than the client timeout, so the server always responds (even with an error) before the client gives up.

**Fix:** Set `result_event.wait(timeout=280)` (20s less than socket timeout) so the error response arrives before the socket times out.

---

### TCP-HIGH-03: Large Response Can Exceed 64MB Without Warning
**Location:** `blender_client.py:252-254`, `socket_server.py:102-104`
**Severity:** HIGH

`MAX_MESSAGE_SIZE = 64 * 1024 * 1024` on both sides. But handlers have no awareness of this limit. A handler returning a massive result (e.g., full mesh vertex data, all scene objects with attributes) could easily generate JSON > 64MB, which would:
1. Be silently truncated? No -- `json.dumps` would complete, then `struct.pack(">I", len(response_bytes))` would pack the full length
2. The receiver checks `if length > MAX_MESSAGE_SIZE` and raises `ValueError` (server) or `ConnectionError` (client)
3. The error message does NOT tell you which command caused it or what the actual size was

But wait -- `struct.pack(">I", length)` uses an unsigned 32-bit integer. Max value = 4,294,967,295 (~4GB). The 64MB limit is well under this. So framing works. The issue is that handlers don't know they're approaching the limit and there's no streaming protocol for large results.

**Fix:** 
1. Add response size check before sending, with a clear error message
2. For known-large operations (mesh vertex data, full scene dumps), implement pagination or streaming
3. Log a warning when response exceeds 1MB

---

### TCP-HIGH-04: JSON Serialization Failures Crash the Client Thread
**Location:** `socket_server.py:123`
**Severity:** HIGH

```python
response_bytes = json.dumps(response).encode("utf-8")
```

If the handler result contains non-serializable objects (e.g., a bpy object reference, a numpy array, bytes), `json.dumps` raises `TypeError`. This exception is NOT caught in the inner try/except -- it propagates to the OUTER except on line 131, which tries to send an error response. But by this point, the `event` has already been set (via the inner finally), so the client already received a response... wait, no:

Looking at the flow more carefully:
1. Handler executes, result stored in `container["response"]` (line 188-193)
2. `event.set()` (line 199) -- client thread can now read `container["response"]`
3. THEN `json.dumps(response)` on line 123 serializes for sending back over TCP

Actually no. The `_process_commands` (main thread timer) only puts the result in `container["response"]` and calls `event.set()`. The `_handle_client` thread then reads `container["response"]` (line 115) and serializes it for sending (line 123).

So the flow is:
1. `_handle_client` queues command, waits on event
2. Main thread executes handler, sets `container["response"]`, calls `event.set()`
3. `_handle_client` wakes up, reads `container["response"]`, serializes with `json.dumps`

If `json.dumps` fails on line 123, the exception is caught by the outer `except` on line 131, which tries to send an error message. The client receives the error. This is actually handled correctly.

BUT: the `container["response"]` could contain a dict with non-JSON-serializable values (e.g., `set()`, `bytes`, custom objects). The handler's result goes through:

```python
result = handler(params)
if isinstance(result, dict) and "status" in result:
    container["response"] = result
else:
    container["response"] = {"status": "success", "result": result}
```

If `result` is a complex nested structure with non-serializable types, the error only surfaces during JSON serialization in `_handle_client`, not during handler execution. The error message sent back is generic (`"Server error: ..."`) and doesn't identify the problematic field.

**Fix:** Wrap `json.dumps` in the serialization step with a try/except that provides the command type and a truncated repr of the failing data.

---

### TCP-HIGH-05: Client-Side _read_and_cleanup File Race
**Location:** `blender_client.py:294-301`
**Severity:** MEDIUM-HIGH

```python
@staticmethod
def _read_and_cleanup(filepath: str) -> bytes:
    with open(filepath, "rb") as f:
        data = f.read()
    try:
        os.unlink(filepath)
    except OSError:
        pass
    return data
```

This reads a viewport screenshot file written by Blender. If two concurrent screenshot requests write to similar temp paths, or if Blender hasn't finished flushing the file to disk before the MCP client reads it, you get a truncated/empty image. The `_send_lock` prevents concurrent `send_command` calls, so concurrent screenshot requests are serialized, mitigating this. But the file could still be incomplete if Blender's file write and the response send are not atomically ordered.

Looking at the screenshot handler, it writes the file, then returns the filepath. Since the handler runs synchronously on the main thread, the file should be complete before the response is sent. So this is likely safe in practice.

**Actual risk:** LOW in current architecture (serialized by `_send_lock`), but fragile if concurrency is ever added.

---

## BUG CATEGORY: MEDIUM (Reliability / Error Handling)

### TCP-MED-01: 30-Second Client Idle Timeout Kills Persistent Connections
**Location:** `socket_server.py:93`
**Severity:** MEDIUM

```python
client_sock.settimeout(30.0)
```

The Blender server sets a 30-second idle timeout on client sockets. But the MCP side keeps a persistent connection (`BlenderConnection._socket`) alive indefinitely. If the MCP server goes 30 seconds without sending a command, the next `_receive_exactly` for the length prefix will raise `socket.timeout` on the Blender side, and the Blender server will close the connection.

When the MCP side next sends a command, it sends on the dead socket, gets an error, and the retry logic in `_sync_send` reconnects. This works, but:
1. The first attempt is always wasted (send succeeds due to TCP buffering, recv fails)
2. Every command after a 30s idle pays the reconnection penalty
3. The "persistent connection" optimization is defeated for interactive use patterns

**Fix:** Either:
1. Remove the 30s idle timeout on the server (rely on the server loop's `self.running` check to clean up on shutdown)
2. Add a keepalive ping from the MCP client every 20s
3. Set the idle timeout to match the MCP socket timeout (300s)

---

### TCP-MED-02: Error Response for Unknown Commands Lacks Detail
**Location:** `socket_server.py:179-182`
**Severity:** MEDIUM

```python
if handler is None:
    container["response"] = {
        "status": "error",
        "message": f"Unknown command: {cmd_type}",
    }
```

When an unknown command type arrives, the error message only shows the command type. It doesn't suggest similar valid commands or list available commands. With 150+ command types, typos are easy.

**Fix:** Add fuzzy matching or at least list the first 10 alphabetically close handlers.

---

### TCP-MED-03: Exception Message Truncation in Handler Error Path
**Location:** `socket_server.py:193-197`
**Severity:** MEDIUM

```python
except Exception as e:
    container["response"] = {
        "status": "error",
        "message": str(e),
    }
```

Only `str(e)` is captured. Stack trace is lost. For complex handlers (267 of them), debugging production issues requires knowing WHERE in the handler the error occurred, not just the message.

Additionally, `error_type` is not set in this path (it's `None` in the BlenderResponse model), unlike handler-returned errors which typically include `error_type`. This makes it impossible to distinguish between "handler deliberately returned an error" and "handler crashed".

**Fix:** 
1. Capture `traceback.format_exc()` and include as a `traceback` field
2. Set `error_type` to `"unhandled_exception"` for crashes vs `"handler_error"` for deliberate errors
3. Log the full traceback server-side

---

### TCP-MED-04: No Logging of Command Execution on Server Side
**Location:** `socket_server.py:167-203`
**Severity:** MEDIUM

The server does not log which commands are received, when they start executing, when they finish, or how long they took. The only console output is the initial "Server listening" and "Server stopped" messages.

For a system executing 150+ different command types with handlers that can take seconds, this makes debugging extremely difficult.

**Fix:** Add structured logging:
```python
logger.info("CMD %s started (queue_depth=%d)", cmd_type, self.command_queue.qsize())
# ... execute ...
logger.info("CMD %s completed in %.2fs", cmd_type, elapsed)
```

---

### TCP-MED-05: Client `is_alive()` Probe Creates Spurious Server Connections
**Location:** `blender_client.py:159-166`
**Severity:** MEDIUM

When no persistent socket exists, `is_alive()` does a full `connect()` / `close()` probe:

```python
probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
probe.settimeout(2)
try:
    probe.connect((self.host, self.port))
    probe.close()
    return True
```

Each probe triggers `_server_loop`'s `srv.accept()`, which spawns a `_handle_client` thread. That thread calls `_receive_exactly(4)` on the probe socket, which immediately gets `ConnectionError("Connection closed")` because the probe closed. The thread then exits. This is wasteful -- each `is_alive()` call creates and destroys a thread.

**Fix:** Use a non-connecting check (e.g., check if port is open without full TCP handshake), or add a lightweight "are you there" mechanism that doesn't spawn a handler thread.

---

### TCP-MED-06: Server Socket Not Bound to IPv4 Only
**Location:** `socket_server.py:55-58`
**Severity:** LOW-MEDIUM

```python
srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.bind(("localhost", self.port))
```

This binds to `localhost` which on some systems resolves to `127.0.0.1` and on others to `::1` (IPv6 loopback). If the server binds to IPv4 but the client connects via IPv6 (or vice versa), the connection fails with "Connection refused."

The client uses `socket.AF_INET` explicitly, so it will always try IPv4. But if the server's `localhost` resolves to IPv6, the bind succeeds on IPv6 and the client can't connect.

**Fix:** Bind to `"127.0.0.1"` explicitly instead of `"localhost"` on both sides, or use `socket.AF_UNSPEC` with `getaddrinfo`.

---

### TCP-MED-07: No Graceful Shutdown Signal to Connected Clients
**Location:** `socket_server.py:38-51` (`stop()`)
**Severity:** MEDIUM

When `stop()` is called:
1. `self.running = False`
2. Server socket closed (stops new connections)
3. Timer unregistered (stops command processing)
4. Server thread joined

But connected client threads are daemon threads that may still be waiting on `result_event.wait(timeout=300)`. They'll eventually time out or get an error when trying to send the response on a now-closed socket. There's no notification to waiting clients that the server is shutting down.

Additionally, commands already in the queue but not yet processed are silently dropped. The clients waiting on those commands will time out after 300 seconds.

**Fix:** 
1. On stop, drain the queue and set all events with an error response
2. Close all tracked client sockets to wake up waiting threads

---

### TCP-MED-08: Blender Timer Can Be Silently Unregistered
**Location:** `socket_server.py:167-203`
**Severity:** MEDIUM

Blender's `bpy.app.timers` will silently unregister a timer callback that raises an exception. The outer guard on line 200 catches `Exception`, but `BaseException` subclasses (`KeyboardInterrupt`, `SystemExit`, `GeneratorExit`) would pass through and kill the timer permanently.

If the timer dies, no commands will ever be processed. All connected clients will time out after 300 seconds. The only visible sign is that commands stop working, with no error message.

**Fix:** Catch `BaseException` in the outer guard (but re-raise `SystemExit`/`KeyboardInterrupt` after logging).

---

## BUG CATEGORY: LOW (Robustness / Edge Cases)

### TCP-LOW-01: `_receive_exactly` Does Not Handle Zero-Length Messages
**Location:** `blender_client.py:177-201`, `socket_server.py:156-165`
**Severity:** LOW

If a length prefix of 0 is received, `_receive_exactly(0)` immediately returns `b""`, which is then passed to `json.loads(b"")`, raising `json.JSONDecodeError`. This is caught and converted to a `ConnectionError` on the client side. On the server side, `json.loads(b"")` would raise in `_handle_client`, caught by the outer except.

Not a crash, but produces a confusing error message.

**Fix:** Check for `length == 0` before calling `_receive_exactly` and return a clear error.

---

### TCP-LOW-02: No Backpressure on Command Queue
**Location:** `socket_server.py:19` (`queue.Queue` unbounded)
**Severity:** LOW

The command queue has no max size. If commands arrive faster than they're processed (one per 10ms tick), the queue grows without bound. In theory, if many MCP clients connect and spam commands, memory usage grows.

In practice, the MCP server is single-threaded per tool call and uses `_send_lock`, so only one command is in flight at a time. But if multiple MCP server instances connect to the same Blender, this could become an issue.

**Fix:** Set `queue.Queue(maxsize=100)` and handle `queue.Full` in `_handle_client`.

---

### TCP-LOW-03: `struct.unpack` on Partial Data
**Location:** `socket_server.py:101`
**Severity:** LOW

```python
length_bytes = self._receive_exactly(client_sock, 4)
# ...
length = struct.unpack(">I", length_bytes)[0]
```

If `_receive_exactly` raises `ConnectionError` (line 98-100), the exception propagates correctly. But if somehow `length_bytes` is less than 4 bytes (impossible with current `_receive_exactly` implementation but defensive coding), `struct.unpack` would raise `struct.error`, caught by the outer except. This is fine.

**No fix needed** -- current code is correct but could add an assertion for safety.

---

### TCP-LOW-04: Pydantic Validation on Response Can Fail
**Location:** `blender_client.py:263`
**Severity:** LOW

```python
response = BlenderResponse(**response_data)
```

If the Blender handler returns a dict that doesn't match the `BlenderResponse` schema (missing `status` field, wrong types), Pydantic raises `ValidationError`. This is NOT caught by the `try/except` around JSON parsing (line 257-262). It would propagate as an uncaught exception from `_send_on_socket`, which IS caught by `_sync_send`'s `except (ConnectionError, BrokenPipeError, OSError)` -- but `ValidationError` is NOT one of those types.

So a malformed Blender response would raise `ValidationError` that escapes `_sync_send` entirely and propagates up to the MCP tool handler as an unhandled exception.

**Fix:** Catch `pydantic.ValidationError` in `_send_on_socket` and convert to `BlenderCommandError` with a clear message.

---

### TCP-LOW-05: Thread Leak on Rapid Connect/Disconnect
**Location:** `socket_server.py:65-66`
**Severity:** LOW

Each accepted connection spawns a daemon thread. If a client connects and immediately disconnects (network scanner, `is_alive()` probe, etc.), the thread starts, tries to read 4 bytes, gets `ConnectionError`, and exits. This is fast, but rapid probing could create hundreds of short-lived threads.

**Fix:** Use a thread pool instead of unbounded thread creation, or use `selectors` for async I/O.

---

### TCP-LOW-06: No Connection Tracking
**Location:** `socket_server.py`
**Severity:** LOW

The server has no list of active client connections. This means:
- Can't report how many clients are connected
- Can't force-disconnect a specific client
- Can't broadcast notifications (e.g., "scene changed")
- `stop()` can't cleanly close client sockets

**Fix:** Maintain a `set` of active client sockets, protected by a lock.

---

## BUG CATEGORY: DESIGN ISSUES (Not Bugs, But Architectural Weaknesses)

### TCP-DESIGN-01: No Heartbeat / Keepalive Protocol
The protocol has no mechanism for either side to detect a stale connection without attempting a command. The 30s idle timeout on the server side is a blunt instrument.

### TCP-DESIGN-02: No Progress Reporting for Long Operations
When a handler takes 30+ seconds (terrain generation, full scene composition), the MCP client has no way to know the operation is still running. It just waits. A progress callback or periodic heartbeat during execution would improve UX.

### TCP-DESIGN-03: No Command Queuing Visibility
The MCP client cannot query how many commands are queued or what's currently executing. When things are slow, there's no diagnostic information available.

### TCP-DESIGN-04: Synchronous Handler Model Limits Throughput
All handlers run synchronously on the main thread. Read-only operations (get_scene_info, list_objects) could theoretically run concurrently, but the architecture doesn't distinguish between read and write operations.

### TCP-DESIGN-05: No Protocol Version Negotiation
If the MCP server and Blender addon are different versions, there's no handshake to detect incompatibility. A changed command format or new required fields would cause silent failures or confusing errors.

---

## Summary of Findings

| ID | Severity | Category | Description |
|----|----------|----------|-------------|
| TCP-CRIT-01 | CRITICAL | Head-of-line blocking | One command per tick blocks all clients |
| TCP-CRIT-02 | CRITICAL | Frozen handler | Unset Event if timer callback crashes in outer guard |
| TCP-CRIT-03 | HIGH | No cancellation | Disconnected client's command still executes; retries cause duplicates |
| TCP-CRIT-04 | HIGH | No idempotency | Retry logic can execute same command twice |
| TCP-HIGH-01 | HIGH | Race condition | `is_alive()` doesn't acquire `_send_lock` |
| TCP-HIGH-02 | HIGH | Timeout mismatch | Server and client both 300s, causes race on boundary |
| TCP-HIGH-03 | HIGH | Large responses | No handler-side size awareness, 64MB limit only at framing layer |
| TCP-HIGH-04 | HIGH | Serialization | Non-JSON-serializable handler results surface as generic errors |
| TCP-HIGH-05 | MEDIUM-HIGH | File race | Screenshot file read/delete could race in theory |
| TCP-MED-01 | MEDIUM | Idle timeout | 30s server timeout defeats persistent connection for interactive use |
| TCP-MED-02 | MEDIUM | Error UX | Unknown command error lacks suggestions |
| TCP-MED-03 | MEDIUM | Error detail | Handler crashes lose stack trace, no error_type |
| TCP-MED-04 | MEDIUM | Observability | No command execution logging |
| TCP-MED-05 | MEDIUM | Probe waste | `is_alive()` spawns a server thread per check |
| TCP-MED-06 | LOW-MEDIUM | Address binding | localhost may resolve to IPv6, client is IPv4-only |
| TCP-MED-07 | MEDIUM | Shutdown | No graceful shutdown for connected clients or queued commands |
| TCP-MED-08 | MEDIUM | Timer death | BaseException kills timer permanently with no recovery |
| TCP-LOW-01 | LOW | Edge case | Zero-length message produces confusing error |
| TCP-LOW-02 | LOW | Backpressure | Unbounded command queue |
| TCP-LOW-03 | LOW | Defensive | struct.unpack edge case (already handled) |
| TCP-LOW-04 | LOW | Validation | Pydantic ValidationError escapes retry logic |
| TCP-LOW-05 | LOW | Thread leak | Rapid connections create many short-lived threads |
| TCP-LOW-06 | LOW | Tracking | No active connection tracking |

**Total: 22 bugs/issues found (4 CRITICAL/HIGH, 5 HIGH, 8 MEDIUM, 5 LOW)**

---

## What's Actually Good

The protocol gets several things RIGHT:

1. **Length-prefixed framing** -- Proper 4-byte big-endian prefix solves message boundary detection. No delimiter-based parsing bugs.
2. **TCP_NODELAY on both sides** -- Eliminates Nagle's algorithm latency for small messages.
3. **Persistent connections with retry** -- Single-retry on failure is a good pattern. Not too aggressive.
4. **Thread-safe send with `_send_lock`** -- Prevents interleaved writes from concurrent callers.
5. **Main-thread command execution** -- Correctly handles Blender's thread-unsafe bpy API.
6. **`_receive_exactly` handles partial reads** -- Proper loop handles TCP packet fragmentation.
7. **MAX_MESSAGE_SIZE limits** -- Prevents memory exhaustion from malicious/buggy large messages.
8. **Daemon threads** -- Server threads won't prevent process exit.
9. **Clean error propagation** -- Most handler errors are properly wrapped and returned to clients.
