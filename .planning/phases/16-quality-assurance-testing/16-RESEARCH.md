# Phase 16: Quality Assurance & Testing - Research

**Researched:** 2026-03-20
**Domain:** Unity Editor TCP bridge addon, test runner integration, profiling, static analysis, crash reporting, analytics, live inspection
**Confidence:** HIGH

## Summary

Phase 16 centers on QA-00: building a Unity Editor TCP bridge addon that mirrors the proven Blender bridge pattern (`blender_addon/socket_server.py` on port 9876), enabling the VB Unity MCP server to communicate directly with Unity Editor over TCP (port 9877). This eliminates the dependency on mcp-unity and the brittle "write C# script, recompile, execute menu item, read result" two-step pattern.

The Blender bridge architecture is well-proven in this codebase with ~260 handler registrations in `COMMAND_HANDLERS`. The Unity equivalent uses the same length-prefixed JSON protocol (4-byte big-endian length header + JSON payload) but adapts to Unity's threading model: `[InitializeOnLoad]` with `EditorApplication.update` for main-thread command dispatch instead of Blender's `bpy.app.timers`. The remaining requirements (QA-01 through QA-08) build on this bridge by adding specialized command handlers: test runner, profiler capture, memory snapshots, static analysis, crash reporting setup, analytics scaffolding, and live state inspection.

**Primary recommendation:** Build the Unity TCP bridge addon first (QA-00) as all other QA requirements depend on it. Mirror the Blender bridge architecture exactly: background `TcpListener` thread + `ConcurrentQueue` + `EditorApplication.update` poll for main-thread execution. Python-side client (`UnityConnection`) mirrors `BlenderConnection` with connection-per-command pattern.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **TCP bridge addon for Unity Editor**: Similar to the Blender TCP bridge (localhost:9876), create a Unity Editor TCP listener addon that runs inside Unity Editor
- **Eliminates mcp-unity dependency entirely**: The VB Unity MCP server connects directly to the Unity Editor via TCP, can trigger AssetDatabase.Refresh, execute menu items, enter/exit play mode, read console logs, take screenshots, and read result JSON -- all without needing any external MCP server
- **Protocol**: JSON-based command/response over TCP, matching the Blender bridge pattern
- **Unity-side addon**: An EditorWindow or [InitializeOnLoad] class that listens on a configurable port (default: 9877), receives commands, dispatches to Unity Editor APIs, returns structured JSON results
- **Python-side client**: TCP client in the VB Unity MCP server that sends commands and reads responses, replacing the current "write script + hope someone clicks it" pattern
- **Commands to support**: `recompile` (AssetDatabase.Refresh), `execute_menu_item` (EditorApplication.ExecuteMenuItem), `enter_play_mode`, `exit_play_mode`, `screenshot`, `console_logs`, `read_result` (read Temp/vb_result.json), `get_game_objects` (scene hierarchy query)
- **TestRunnerApi integration**: Use the programmatic TestRunnerApi to run tests and collect results via ICallbacks
- **Editor scripted testing**: Generate C# scripts that use EditorApplication.isPlaying + coroutines for automated play sessions
- **Unity Profiler API**: Use ProfilerRecorder to capture frame time, draw calls, memory allocation
- **Pattern-based analyzers**: Scan for common Unity performance anti-patterns in generated C#
- **Sentry integration**: Generate Sentry SDK initialization code with DSN configuration
- **Custom event system**: Generate analytics event tracking code
- **EditorWindow inspector**: Generate custom inspector window for live variable inspection during Play Mode

### Claude's Discretion
- TCP bridge port number and connection timeout defaults
- Profiler budget default values
- Memory snapshot comparison algorithm
- Static analysis rule severity levels
- Analytics event naming conventions
- Live inspection update frequency

### Deferred Ideas (OUT OF SCOPE)
None -- autonomous mode stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| QA-00 | Unity Editor TCP bridge addon for direct communication (eliminates mcp-unity) | Blender bridge pattern fully analyzed; `[InitializeOnLoad]` + `EditorApplication.update` confirmed viable; length-prefixed JSON protocol documented |
| QA-01 | Run EditMode/PlayMode tests via Unity Test Runner and report results through MCP | Existing `generate_test_runner_script` code provides TestRunnerApi + ICallbacks pattern; bridge enables direct execution |
| QA-02 | Script automated play sessions for integration testing | `EditorApplication.isPlaying` + `EditorApplication.EnterPlaymode()` APIs confirmed; coroutine-based verification pattern documented |
| QA-03 | Capture GPU profiling data and continuous performance analysis | `ProfilerRecorder` API with `StartNew()` for frame time, draw calls, memory; extends existing `performance_templates.py` |
| QA-04 | Detect memory leaks via managed/native memory snapshots | `Unity.Profiling.ProfilerRecorder` for managed heap; `com.unity.memoryprofiler` package already installed in VeilBreakers |
| QA-05 | Run static code analysis (Roslyn-style pattern matching) | C# regex/string-based pattern scanner for common anti-patterns; simpler than Roslyn analyzers, works at code generation time |
| QA-06 | Set up crash reporting (Sentry, Unity Cloud Diagnostics) | Sentry Unity SDK via `SentrySdk.Init()`; Cloud Diagnostics deprecated in Unity 6.2+, Sentry preferred |
| QA-07 | Set up analytics/telemetry events | Custom event system with JSON local logging fallback; template generator pattern |
| QA-08 | Inspect live game state during Play Mode | Custom EditorWindow with `EditorApplication.update` polling during Play Mode; BT/FSM state visualization |

</phase_requirements>

## Standard Stack

### Core (Unity-side C# addon)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| System.Net.Sockets (TcpListener) | .NET BCL | TCP server inside Unity Editor | Built-in, no package needed, proven pattern in Blender bridge |
| System.Collections.Concurrent (ConcurrentQueue) | .NET BCL | Thread-safe command queue | Lock-free producer-consumer between network thread and main thread |
| UnityEditor (EditorApplication, AssetDatabase) | Unity 6 | Main thread dispatch, asset refresh, play mode control | Official Unity Editor API |
| Unity.Profiling (ProfilerRecorder) | Unity 6 | Frame time, draw calls, memory stats | Official profiler API, works in Editor and Player |
| UnityEditor.TestTools.TestRunner.Api | com.unity.test-framework 1.3+ | Programmatic test execution | Official test framework API |

### Core (Python-side client)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| socket (stdlib) | Python 3.12 | TCP client connection | Mirrors BlenderConnection pattern exactly |
| struct (stdlib) | Python 3.12 | Length-prefix encoding/decoding | Same 4-byte big-endian protocol as Blender bridge |
| asyncio (stdlib) | Python 3.12 | Async wrapper via run_in_executor | Matches FastMCP async tool pattern |
| pydantic | 2.x | Command/Response models | Matches existing BlenderCommand/BlenderResponse pattern |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Sentry Unity SDK | Latest via UPM | Crash reporting | QA-06 crash reporting setup |
| com.unity.memoryprofiler | Already installed | Native memory snapshots | QA-04 memory leak detection |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| TcpListener | Named pipes | Cross-platform TCP is simpler, matches Blender bridge |
| ConcurrentQueue | lock + Queue | ConcurrentQueue is lock-free, better performance |
| Regex-based static analysis | Roslyn analyzers | Roslyn requires NuGet setup in Unity; regex works at code-gen time in Python |
| Cloud Diagnostics | Sentry only | Cloud Diagnostics deprecated in Unity 6.2+; Sentry is actively maintained |

## Architecture Patterns

### Unity-Side Bridge Addon Structure

```
Assets/Editor/VBBridge/
  VBBridgeServer.cs          # [InitializeOnLoad] TCP listener + command dispatch
  VBBridgeCommands.cs        # COMMAND_HANDLERS dictionary + handler methods
  VBBridgeWindow.cs          # Optional EditorWindow for status display
```

### Python-Side Client Structure

```
src/veilbreakers_mcp/shared/
  unity_client.py            # UnityConnection class (mirrors blender_client.py)
  models.py                  # Add UnityCommand, UnityResponse (parallel to Blender models)
```

### Pattern 1: TCP Bridge Architecture (mirrors Blender bridge)

**What:** Background `TcpListener` thread accepts connections, queues commands into `ConcurrentQueue`, `EditorApplication.update` callback dequeues and executes on main thread, result sent back via `ManualResetEventSlim`.

**When to use:** All Unity Editor communication from MCP server.

**Unity C# pattern (high confidence -- derived from working Blender bridge):**

```csharp
// Source: Blender bridge pattern (blender_addon/socket_server.py) adapted for Unity
using UnityEngine;
using UnityEditor;
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

[InitializeOnLoad]
public static class VBBridgeServer
{
    private static TcpListener _listener;
    private static Thread _listenerThread;
    private static bool _running;
    private static readonly ConcurrentQueue<CommandEnvelope> _commandQueue = new();
    private static int _port = 9877;

    static VBBridgeServer()
    {
        Start();
        EditorApplication.update += ProcessCommands;
        // Clean up on domain reload
        AssemblyReloadEvents.beforeAssemblyReload += Stop;
    }

    static void Start()
    {
        if (_running) return;
        _running = true;
        _listenerThread = new Thread(ListenerLoop) { IsBackground = true };
        _listenerThread.Start();
        Debug.Log($"[VBBridge] Listening on localhost:{_port}");
    }

    static void Stop()
    {
        _running = false;
        _listener?.Stop();
        _listenerThread?.Join(2000);
    }

    static void ListenerLoop()
    {
        _listener = new TcpListener(IPAddress.Loopback, _port);
        _listener.Start();
        while (_running)
        {
            try
            {
                if (!_listener.Pending()) { Thread.Sleep(50); continue; }
                var client = _listener.AcceptTcpClient();
                ThreadPool.QueueUserWorkItem(_ => HandleClient(client));
            }
            catch (SocketException) { if (_running) throw; }
        }
    }

    static void HandleClient(TcpClient client)
    {
        try
        {
            using var stream = client.GetStream();
            client.NoDelay = true;
            // Read 4-byte length prefix (big-endian)
            var lenBytes = ReadExactly(stream, 4);
            int len = (lenBytes[0] << 24) | (lenBytes[1] << 16) | (lenBytes[2] << 8) | lenBytes[3];
            var jsonBytes = ReadExactly(stream, len);
            string json = Encoding.UTF8.GetString(jsonBytes);

            var envelope = new CommandEnvelope
            {
                RequestJson = json,
                DoneEvent = new ManualResetEventSlim(false)
            };
            _commandQueue.Enqueue(envelope);
            envelope.DoneEvent.Wait(TimeSpan.FromSeconds(300));

            // Send response with length prefix
            byte[] responseBytes = Encoding.UTF8.GetBytes(envelope.ResponseJson ?? "{}");
            byte[] responseLen = new byte[4];
            responseLen[0] = (byte)(responseBytes.Length >> 24);
            responseLen[1] = (byte)(responseBytes.Length >> 16);
            responseLen[2] = (byte)(responseBytes.Length >> 8);
            responseLen[3] = (byte)(responseBytes.Length);
            stream.Write(responseLen, 0, 4);
            stream.Write(responseBytes, 0, responseBytes.Length);
        }
        catch (Exception e) { Debug.LogError($"[VBBridge] Client error: {e.Message}"); }
        finally { client?.Close(); }
    }

    static void ProcessCommands()
    {
        // Process one command per editor tick (avoid blocking UI)
        if (_commandQueue.TryDequeue(out var envelope))
        {
            try
            {
                envelope.ResponseJson = VBBridgeCommands.Dispatch(envelope.RequestJson);
            }
            catch (Exception e)
            {
                envelope.ResponseJson = $"{{\"status\":\"error\",\"message\":\"{EscapeJson(e.Message)}\"}}";
            }
            finally
            {
                envelope.DoneEvent.Set();
            }
        }
    }

    // ... ReadExactly, EscapeJson helpers
}

class CommandEnvelope
{
    public string RequestJson;
    public string ResponseJson;
    public ManualResetEventSlim DoneEvent;
}
```

### Pattern 2: Command Handler Dispatch (mirrors Blender COMMAND_HANDLERS)

**What:** Dictionary mapping command type strings to handler methods, same pattern as `blender_addon/handlers/__init__.py`.

**Unity C# pattern:**

```csharp
// Source: blender_addon/handlers/__init__.py pattern adapted for Unity
public static class VBBridgeCommands
{
    private static readonly Dictionary<string, Func<Dictionary<string, object>, Dictionary<string, object>>>
        HANDLERS = new()
    {
        ["ping"] = _ => new() { ["status"] = "success", ["result"] = "pong" },
        ["recompile"] = HandleRecompile,
        ["execute_menu_item"] = HandleExecuteMenuItem,
        ["enter_play_mode"] = HandleEnterPlayMode,
        ["exit_play_mode"] = HandleExitPlayMode,
        ["screenshot"] = HandleScreenshot,
        ["console_logs"] = HandleConsoleLogs,
        ["read_result"] = HandleReadResult,
        ["get_game_objects"] = HandleGetGameObjects,
        ["run_tests"] = HandleRunTests,
        ["profile_frame"] = HandleProfileFrame,
        ["memory_snapshot"] = HandleMemorySnapshot,
        ["inspect_gameobject"] = HandleInspectGameObject,
    };

    public static string Dispatch(string requestJson)
    {
        var request = JsonUtility.FromJson<BridgeRequest>(requestJson);
        // ... or use MiniJSON / manual parsing since JsonUtility has limitations
        if (HANDLERS.TryGetValue(request.type, out var handler))
        {
            var result = handler(request.parameters);
            return SerializeResponse("success", result);
        }
        return SerializeResponse("error", null, $"Unknown command: {request.type}");
    }

    static Dictionary<string, object> HandleRecompile(Dictionary<string, object> p)
    {
        AssetDatabase.Refresh(ImportAssetOptions.ForceUpdate);
        return new() { ["refreshed"] = true };
    }

    static Dictionary<string, object> HandleExecuteMenuItem(Dictionary<string, object> p)
    {
        string path = p["menu_path"].ToString();
        bool ok = EditorApplication.ExecuteMenuItem(path);
        return new() { ["executed"] = ok, ["menu_path"] = path };
    }

    static Dictionary<string, object> HandleEnterPlayMode(Dictionary<string, object> p)
    {
        EditorApplication.EnterPlaymode();
        return new() { ["is_playing"] = true };
    }

    static Dictionary<string, object> HandleExitPlayMode(Dictionary<string, object> p)
    {
        EditorApplication.ExitPlaymode();
        return new() { ["is_playing"] = false };
    }
    // ... other handlers
}
```

### Pattern 3: Python-side UnityConnection (mirrors BlenderConnection)

**What:** `UnityConnection` class in `shared/unity_client.py` that mirrors `shared/blender_client.py` exactly, with connection-per-command pattern.

**Python pattern:**

```python
# Source: blender_client.py adapted for Unity
class UnityConnection:
    def __init__(self, host="localhost", port=9877, timeout=300):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket = None
        self._send_lock = threading.Lock()

    def _sync_send(self, command_type: str, params: dict) -> Any:
        with self._send_lock:
            self.reconnect()
            command = UnityCommand(type=command_type, params=params)
            json_bytes = command.model_dump_json().encode("utf-8")
            self._socket.sendall(struct.pack(">I", len(json_bytes)) + json_bytes)
            length_bytes = self._receive_exactly(4)
            length = struct.unpack(">I", length_bytes)[0]
            response_bytes = self._receive_exactly(length)
            response = UnityResponse(**json.loads(response_bytes))
            if response.status == "error":
                raise UnityCommandError(response)
            return response.result

    async def send_command(self, command_type: str, params=None) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_send, command_type, params or {})
```

### Anti-Patterns to Avoid

- **Calling Unity API from background thread:** All UnityEditor/UnityEngine API calls MUST happen on the main thread. The network thread can only enqueue; `EditorApplication.update` dequeues and executes. This is the exact same constraint as Blender's `bpy` (must run on main thread via `bpy.app.timers`).
- **Persistent TCP connections:** Use connection-per-command pattern (connect, send, receive, close) matching the Blender bridge. This avoids stale socket issues when Unity domain reloads.
- **Blocking EditorApplication.update:** Process only ONE command per update tick. Multiple commands in a single tick can freeze the Editor UI. The Blender bridge uses `get_nowait()` for the same reason.
- **Using JsonUtility for command parsing:** `JsonUtility` cannot deserialize to `Dictionary<string,object>`. Use a lightweight JSON parser (MiniJSON or manual parsing) for the command parameters dict.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TCP framing protocol | Custom delimiter-based protocol | 4-byte length prefix (big-endian) | Proven in Blender bridge, handles arbitrary JSON payloads, no delimiter escaping |
| JSON serialization in C# | Manual string building | MiniJSON or JsonUtility for simple types | Edge cases in escaping, Unicode handling |
| Thread-safe queue | lock + List | ConcurrentQueue<T> | Lock-free, designed for producer-consumer |
| Main thread dispatch | Custom lock/flag pattern | EditorApplication.update + ConcurrentQueue | Unity's official editor update mechanism |
| Profiler data collection | Manual frame counters | ProfilerRecorder.StartNew() | Official API, handles all timing/counter categories |
| Test execution | Custom test discovery | TestRunnerApi + ICallbacks | Official framework, handles EditMode and PlayMode |
| Roslyn analyzers DLL | Building Roslyn analyzer NuGet package | Python regex pattern scanner | Much simpler, works at code-gen time, no Unity compilation dependency |

**Key insight:** The Blender bridge already solved every hard problem (threading, framing, main-thread dispatch, connection lifecycle). The Unity bridge is a mechanical translation from Python/Blender to C#/Unity with the same architecture.

## Common Pitfalls

### Pitfall 1: Domain Reload Kills TCP Listener

**What goes wrong:** Unity performs domain reload when scripts change (entering Play Mode, recompile). This destroys all static state including the TCP listener thread.
**Why it happens:** `[InitializeOnLoad]` static constructors re-execute after domain reload, but the old thread/socket is gone without cleanup.
**How to avoid:** Register cleanup via `AssemblyReloadEvents.beforeAssemblyReload += Stop`. The `[InitializeOnLoad]` static constructor will re-create the server after reload. Also handle `EditorApplication.quitting`.
**Warning signs:** "Address already in use" error on port 9877 after recompile.

### Pitfall 2: Unity API Calls From Background Thread

**What goes wrong:** Calling `AssetDatabase.Refresh()`, `EditorApplication.ExecuteMenuItem()`, or any Editor API from the network listener thread causes crashes or silent failures.
**Why it happens:** Unity Engine is not thread-safe. All Editor API must run on the main thread.
**How to avoid:** The command queue pattern -- network thread enqueues, `EditorApplication.update` dequeues and executes on main thread. This is identical to Blender's `bpy.app.timers.register` approach.
**Warning signs:** "can only be called from the main thread" exception in Unity console.

### Pitfall 3: JsonUtility Limitations for Generic Dictionaries

**What goes wrong:** `JsonUtility.FromJson<T>()` cannot deserialize to `Dictionary<string, object>` or handle polymorphic types.
**Why it happens:** JsonUtility requires concrete serializable classes with `[Serializable]` attribute.
**How to avoid:** Use a lightweight JSON parser like MiniJSON (single-file, MIT licensed, commonly embedded in Unity projects) or use `System.Text.Json` (.NET Standard 2.1 in Unity 6). For simple commands, define specific C# classes per command type.
**Warning signs:** Empty or null parameter values after deserialization.

### Pitfall 4: Port Conflicts Between Blender and Unity Bridges

**What goes wrong:** Both bridges try to use the same port.
**Why it happens:** Misconfiguration or copy-paste error.
**How to avoid:** Blender bridge: port 9876 (established). Unity bridge: port 9877 (new). Store in `Settings` as `unity_bridge_port` with clear defaults.
**Warning signs:** "Address already in use" or wrong application responding.

### Pitfall 5: Screenshot Capture Timing in Play Mode

**What goes wrong:** `ScreenCapture.CaptureScreenshot` returns blank image when called immediately.
**Why it happens:** Must wait for frame rendering to complete.
**How to avoid:** For Play Mode screenshots, use coroutine with `WaitForEndOfFrame()`. For Editor screenshots, use `EditorApplication.delayCall` to ensure the frame renders first.
**Warning signs:** All-black or all-white screenshot images.

### Pitfall 6: TestRunnerApi RunSynchronously Blocking Editor

**What goes wrong:** `runSynchronously = true` blocks the Unity Editor thread during test execution, including the TCP listener's main-thread dispatch.
**Why it happens:** Synchronous test execution monopolizes the main thread.
**How to avoid:** For short test suites, synchronous is fine. For long suites, use async execution with ICallbacks and signal completion. The bridge command handler can use `ManualResetEventSlim` with a longer timeout (60s+) and execute tests asynchronously, setting the event when RunFinished fires.
**Warning signs:** TCP bridge appears unresponsive during test runs.

### Pitfall 7: Static Analysis False Positives

**What goes wrong:** Python regex scanner flags valid code patterns as anti-patterns.
**Why it happens:** Regex can't understand C# scope/context (e.g., `Camera.main` in a cached property getter is fine).
**How to avoid:** Apply rules only within method bodies named `Update`, `FixedUpdate`, `LateUpdate`. Use line-based context detection, not just pattern matching. Report findings as warnings, not errors.
**Warning signs:** High false positive rate making the tool noisy and ignored.

## Code Examples

### Example 1: Length-Prefixed TCP Protocol (existing Blender pattern)

```python
# Source: blender_client.py lines 79-104 (proven, production-ready)
def _sync_send(self, command_type: str, params: dict) -> Any:
    with self._send_lock:
        self.reconnect()  # connection-per-command
        command = BlenderCommand(type=command_type, params=params)
        json_bytes = command.model_dump_json().encode("utf-8")
        # 4-byte big-endian length prefix + JSON payload
        self._socket.sendall(struct.pack(">I", len(json_bytes)) + json_bytes)
        length_bytes = self._receive_exactly(4)
        length = struct.unpack(">I", length_bytes)[0]
        response_bytes = self._receive_exactly(length)
        response = BlenderResponse(**json.loads(response_bytes))
        if response.status == "error":
            raise BlenderCommandError(response)
        return response.result
```

### Example 2: Blender Main-Thread Command Processing (to replicate in Unity)

```python
# Source: blender_addon/socket_server.py lines 134-170
def _process_commands(self) -> float:
    """MAIN THREAD via bpy.app.timers - safe for bpy calls."""
    try:
        try:
            cmd, event, container = self.command_queue.get_nowait()
        except queue.Empty:
            return 0.05  # Poll interval
        try:
            cmd_type = cmd.get("type", "unknown")
            params = cmd.get("params", {})
            handler = COMMAND_HANDLERS.get(cmd_type)
            if handler is None:
                container["response"] = {"status": "error", "message": f"Unknown command: {cmd_type}"}
            else:
                result = handler(params)
                container["response"] = {"status": "success", "result": result}
        except Exception as e:
            container["response"] = {"status": "error", "message": str(e)}
        finally:
            event.set()  # Unblock network thread
    except Exception as e:
        print(f"[VeilBreakers MCP] Timer error: {e}")
    return 0.05
```

### Example 3: ProfilerRecorder for Real-Time Stats

```csharp
// Source: Unity docs -- ProfilerRecorder API
using Unity.Profiling;

static Dictionary<string, object> HandleProfileFrame(Dictionary<string, object> p)
{
    using var frameTimeRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Internal, "Main Thread");
    using var drawCallsRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Render, "Draw Calls Count");
    using var memoryRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Memory, "System Used Memory");

    // For immediate snapshot (current frame data):
    return new()
    {
        ["frame_time_ms"] = frameTimeRecorder.LastValue * 1e-6,  // ns to ms
        ["draw_calls"] = drawCallsRecorder.LastValue,
        ["memory_mb"] = memoryRecorder.LastValue / (1024.0 * 1024.0),
        ["is_playing"] = EditorApplication.isPlaying
    };
}
```

### Example 4: Existing Test Runner Pattern (already in codebase)

```csharp
// Source: editor_templates.py generate_test_runner_script (CODE-05)
var api = ScriptableObject.CreateInstance<TestRunnerApi>();
var collector = new TestResultCollector();
api.RegisterCallbacks(collector);
api.Execute(new ExecutionSettings
{
    runSynchronously = true,
    filters = new[] { new Filter { testMode = TestMode.EditMode } }
});
// collector.PassCount, collector.FailCount, collector.Details available
```

### Example 5: Static Analysis Pattern Scanner (Python-side)

```python
# Pattern-based C# static analysis (QA-05)
ANTI_PATTERNS = {
    "camera_main_in_update": {
        "pattern": r"Camera\.main",
        "context": r"void\s+(Update|FixedUpdate|LateUpdate)\s*\(",
        "severity": "warning",
        "message": "Camera.main in Update loop -- cache in Awake/Start",
        "fix": "private Camera _mainCam; void Awake() { _mainCam = Camera.main; }"
    },
    "getcomponent_in_update": {
        "pattern": r"GetComponent<\w+>\(\)",
        "context": r"void\s+(Update|FixedUpdate|LateUpdate)\s*\(",
        "severity": "warning",
        "message": "GetComponent in Update loop -- cache in Awake/Start"
    },
    "find_object_at_runtime": {
        "pattern": r"FindObjectOfType|FindObjectsOfType|FindFirstObjectByType",
        "context": r"void\s+(Update|FixedUpdate|LateUpdate|OnTrigger|OnCollision)",
        "severity": "error",
        "message": "FindObjectOfType in hot path -- use cached references"
    },
    "string_concat_in_update": {
        "pattern": r'\+\s*"[^"]*"|\"\s*\+',
        "context": r"void\s+(Update|FixedUpdate|LateUpdate)\s*\(",
        "severity": "info",
        "message": "String concatenation in Update -- use StringBuilder or interpolation cache"
    },
    "linq_in_update": {
        "pattern": r"\.(Where|Select|Any|All|First|Last|Count|OrderBy|GroupBy|ToList|ToArray)\s*\(",
        "context": r"void\s+(Update|FixedUpdate|LateUpdate)\s*\(",
        "severity": "warning",
        "message": "LINQ in Update loop -- allocates enumerators each frame"
    },
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| mcp-unity external dependency | Direct TCP bridge (this phase) | Phase 16 | Eliminates external dependency, enables instant command execution |
| Write C# + recompile + execute menu item | TCP command -> immediate execution | Phase 16 | Reduces command latency from 5-15s (recompile) to <100ms |
| Unity Cloud Diagnostics | Sentry Unity SDK | Unity 6.2+ (2025) | Cloud Diagnostics deprecated; Sentry actively maintained |
| Manual profiler data inspection | ProfilerRecorder API | Unity 2021+ | Programmatic access to frame time, draw calls, memory |
| Roslyn analyzer DLLs | Python regex pattern scanner | This project | Simpler, works at code-gen time, no build toolchain dependency |

**Deprecated/outdated:**
- Unity Cloud Diagnostics: Deprecated in Unity 6.2+, replaced by Sentry or custom solutions
- `Application.CaptureScreenshot`: Replaced by `ScreenCapture.CaptureScreenshot` and `CaptureScreenshotAsTexture`

## Open Questions

1. **MiniJSON vs System.Text.Json for C# command parsing**
   - What we know: `JsonUtility` cannot handle `Dictionary<string,object>`. MiniJSON is a single-file drop-in. System.Text.Json is available in .NET Standard 2.1 (Unity 6).
   - What's unclear: Whether Unity 6's .NET version includes System.Text.Json by default or if it needs explicit reference.
   - Recommendation: Use MiniJSON (single file, MIT, well-tested in Unity projects). Fall back to manual JSON parsing if needed. Keep it simple.

2. **TestRunnerApi async vs sync execution over TCP**
   - What we know: `runSynchronously = true` blocks the main thread. The TCP bridge processes one command per `EditorApplication.update` tick.
   - What's unclear: Whether synchronous test execution will cause the TCP response to time out for large test suites.
   - Recommendation: Use synchronous for short runs (<30s), add async option with callback-based completion for longer runs. Set TCP timeout to 300s (matching Blender bridge).

3. **Memory snapshot comparison algorithm**
   - What we know: Can capture managed heap size via ProfilerRecorder. com.unity.memoryprofiler provides native snapshots.
   - What's unclear: Best algorithm for detecting growth vs normal allocation churn.
   - Recommendation: Simple before/after comparison with configurable threshold (default: 10MB growth over N frames). Report absolute values and delta.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x with pytest-asyncio |
| Config file | `Tools/mcp-toolkit/pyproject.toml` |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_qa_templates.py -x` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QA-00 | Unity bridge C# addon generates valid code | unit | `pytest tests/test_qa_templates.py::TestBridgeAddon -x` | Wave 0 |
| QA-00 | Python UnityConnection class connects/sends/receives | unit | `pytest tests/test_unity_client.py -x` | Wave 0 |
| QA-00 | UnityCommand/UnityResponse models serialize correctly | unit | `pytest tests/test_unity_client.py::TestModels -x` | Wave 0 |
| QA-01 | Test runner command handler generates valid results | unit | `pytest tests/test_qa_templates.py::TestTestRunner -x` | Wave 0 |
| QA-02 | Play session script generator produces valid C# | unit | `pytest tests/test_qa_templates.py::TestPlaySession -x` | Wave 0 |
| QA-03 | Profiler command handler captures correct metrics | unit | `pytest tests/test_qa_templates.py::TestProfiler -x` | Wave 0 |
| QA-04 | Memory snapshot comparison detects growth | unit | `pytest tests/test_qa_templates.py::TestMemory -x` | Wave 0 |
| QA-05 | Static analysis scanner detects anti-patterns | unit | `pytest tests/test_qa_templates.py::TestStaticAnalysis -x` | Wave 0 |
| QA-06 | Crash reporting template generates valid C# | unit | `pytest tests/test_qa_templates.py::TestCrashReporting -x` | Wave 0 |
| QA-07 | Analytics template generates valid C# | unit | `pytest tests/test_qa_templates.py::TestAnalytics -x` | Wave 0 |
| QA-08 | Live inspector template generates valid C# | unit | `pytest tests/test_qa_templates.py::TestLiveInspector -x` | Wave 0 |
| ALL | Generated C# passes syntax validation | unit | `pytest tests/test_csharp_syntax_deep.py -x` | Exists (extend) |
| ALL | Tool wiring maps actions to handlers | unit | `pytest tests/test_qa_tool_wiring.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/test_qa_templates.py tests/test_unity_client.py -x`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_qa_templates.py` -- covers QA-00 through QA-08 template generation
- [ ] `tests/test_unity_client.py` -- covers UnityConnection, UnityCommand, UnityResponse
- [ ] `tests/test_qa_tool_wiring.py` -- covers unity_qa compound tool action dispatch

## Sources

### Primary (HIGH confidence)
- Blender bridge source code: `blender_addon/socket_server.py`, `blender_addon/handlers/__init__.py`, `shared/blender_client.py` -- exact pattern to replicate
- [Unity InitializeOnLoad docs](https://docs.unity3d.com/6000.1/Documentation/Manual/running-editor-code-on-launch.html) -- static constructor + EditorApplication.update pattern
- [Unity EditorApplication API](https://docs.unity3d.com/ScriptReference/EditorApplication.html) -- update delegate, isPlaying, ExecuteMenuItem, EnterPlaymode/ExitPlaymode
- [Unity ProfilerRecorder API](https://docs.unity3d.com/ScriptReference/Unity.Profiling.ProfilerRecorder.html) -- frame time, draw calls, memory recording
- [Unity TestRunnerApi docs](https://docs.unity3d.com/Packages/com.unity.test-framework@1.1/api/UnityEditor.TestTools.TestRunner.Api.TestRunnerApi.html) -- ICallbacks, Filter, ExecutionSettings
- [Unity AssetDatabase.Refresh](https://docs.unity3d.com/ScriptReference/AssetDatabase.Refresh.html) -- programmatic recompile trigger
- [Sentry Unity SDK docs](https://docs.sentry.io/platforms/unity/) -- DSN setup, auto-configuration

### Secondary (MEDIUM confidence)
- [TCP Server in Unity (Daniel Bierwirth gist)](https://gist.github.com/danielbierwirth/0636650b005834204cb19ef5ae6ccedb) -- TcpListener pattern in Unity
- [Unity Main Thread Dispatcher pattern](https://gist.github.com/LotteMakesStuff/f1e7a0fbcb05adcbd017d6f4f0913264) -- threaded editor code dispatching to main thread
- [Microsoft.Unity.Analyzers](https://github.com/microsoft/Microsoft.Unity.Analyzers) -- reference for anti-pattern detection rules

### Tertiary (LOW confidence)
- Cloud Diagnostics deprecation timeline -- confirmed deprecated, but exact removal version unclear

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all APIs are Unity built-in or well-established packages
- Architecture: HIGH -- direct mechanical translation of proven Blender bridge pattern
- Pitfalls: HIGH -- derived from existing Blender bridge operational experience and Unity threading docs
- QA-00 bridge: HIGH -- Blender bridge is working production code, Unity version follows same architecture
- QA-01 test runner: HIGH -- existing `generate_test_runner_script` in codebase, just needs bridge integration
- QA-02 play sessions: MEDIUM -- coroutine + EditorApplication.isPlaying pattern is standard but timing can be tricky
- QA-03 profiler: HIGH -- ProfilerRecorder API well-documented
- QA-04 memory: MEDIUM -- comparison algorithm needs tuning for real workloads
- QA-05 static analysis: HIGH -- Python regex is well-understood, rules are straightforward
- QA-06 crash reporting: HIGH -- Sentry SDK docs comprehensive
- QA-07 analytics: HIGH -- simple template generation pattern
- QA-08 live inspector: HIGH -- standard EditorWindow pattern

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable APIs, 30-day validity)
