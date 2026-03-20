# Phase 16: Quality Assurance & Testing - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning
**Source:** Auto-generated (autonomous mode)

<domain>
## Phase Boundary

Quality assurance and testing infrastructure: Unity Editor direct communication bridge (TCP addon that eliminates mcp-unity dependency), test runner integration (run EditMode/PlayMode tests, collect results), automated play sessions (walk to point, interact, verify state), GPU profiling (frame time, draw calls, memory), memory leak detection (managed/native snapshots), static code analysis (Roslyn-style analyzers for Update allocations, Camera.main), crash reporting setup (Sentry, Unity Cloud Diagnostics), analytics/telemetry event setup, and live game state inspection during Play Mode.

Requirements: QA-00, QA-01, QA-02, QA-03, QA-04, QA-05, QA-06, QA-07, QA-08.

</domain>

<decisions>
## Implementation Decisions

### Unity Editor Direct Communication — QA-00 (CRITICAL)
- **TCP bridge addon for Unity Editor**: Similar to the Blender TCP bridge (localhost:9876), create a Unity Editor TCP listener addon that runs inside Unity Editor
- **Eliminates mcp-unity dependency entirely**: The VB Unity MCP server connects directly to the Unity Editor via TCP, can trigger AssetDatabase.Refresh, execute menu items, enter/exit play mode, read console logs, take screenshots, and read result JSON — all without needing any external MCP server
- **Protocol**: JSON-based command/response over TCP, matching the Blender bridge pattern
- **Unity-side addon**: An EditorWindow or [InitializeOnLoad] class that listens on a configurable port (default: 9877), receives commands, dispatches to Unity Editor APIs, returns structured JSON results
- **Python-side client**: TCP client in the VB Unity MCP server that sends commands and reads responses, replacing the current "write script + hope someone clicks it" pattern
- **Commands to support**: `recompile` (AssetDatabase.Refresh), `execute_menu_item` (EditorApplication.ExecuteMenuItem), `enter_play_mode`, `exit_play_mode`, `screenshot`, `console_logs`, `read_result` (read Temp/vb_result.json), `get_game_objects` (scene hierarchy query)

### Test Runner (QA-01)
- **TestRunnerApi integration**: Use the programmatic TestRunnerApi (from Phase 12 research) to run tests and collect results via ICallbacks
- **Structured results**: Pass/fail counts, failure messages, test names, duration — machine-readable JSON via the TCP bridge

### Automated Play Sessions (QA-02)
- **Editor scripted testing**: Generate C# scripts that use EditorApplication.isPlaying + coroutines to walk a character to positions, interact with objects, and verify game state
- **Checkpoint-based verification**: Each step has expected state assertions

### Profiling (QA-03)
- **Unity Profiler API**: Use ProfilerRecorder to capture frame time, draw calls, memory allocation in real-time
- **Budget comparisons**: Compare against configurable targets (target frame time, max draw calls, max memory)

### Memory Leak Detection (QA-04)
- **Managed heap snapshots**: Compare managed memory before/after operations to detect growing allocations
- **Native memory tracking**: Use Unity's MemoryProfiler package (already installed in VeilBreakers)

### Static Analysis (QA-05)
- **Pattern-based analyzers**: Scan for common Unity performance anti-patterns in generated C#:
  - `Camera.main` in Update (should be cached)
  - `GetComponent<T>()` in Update (should be cached)
  - String concatenation in hot paths (use StringBuilder)
  - Allocations in Update (new, LINQ, boxing)
  - `FindObjectOfType` in runtime code

### Crash Reporting (QA-06)
- **Sentry integration**: Generate Sentry SDK initialization code with DSN configuration
- **Unity Cloud Diagnostics**: Enable crash reporting through PlayerSettings

### Analytics (QA-07)
- **Custom event system**: Generate analytics event tracking code with configurable event names and properties
- **Local logging fallback**: Write events to JSON log files when no analytics service is configured

### Live Inspection (QA-08)
- **EditorWindow inspector**: Generate custom inspector window that shows live variable values on selected GameObjects during Play Mode
- **State machine visualization**: Show current BT/FSM state in a debug overlay

### Claude's Discretion
- TCP bridge port number and connection timeout defaults
- Profiler budget default values
- Memory snapshot comparison algorithm
- Static analysis rule severity levels
- Analytics event naming conventions
- Live inspection update frequency

</decisions>

<canonical_refs>
## Canonical References

### VeilBreakers Game Project
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Editor/` — Existing editor tools (TCP bridge addon goes here)
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Packages/manifest.json` — com.unity.memoryprofiler already installed

### Toolkit Implementation
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_server.py` — Add TCP client, replace two-step pattern
- `Tools/mcp-toolkit/blender_addon/` — Reference for TCP bridge addon pattern (Blender side)
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/editor_templates.py` — Existing editor script generators

### Requirements
- `.planning/REQUIREMENTS.md` — QA-00 through QA-08

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Blender TCP bridge pattern: `blender_addon/handlers/` with COMMAND_HANDLERS dispatch — replicate for Unity
- Existing `_write_to_unity()` + `_read_unity_result()` pattern — TCP bridge replaces this with direct execution
- Phase 10 `unity_code` `run_tests` action — extends with TCP-based test execution
- Phase 8 `unity_performance` `profile_scene` — extends with real-time profiler data

### Established Patterns
- TCP socket communication (Blender bridge uses localhost:9876)
- JSON command/response protocol
- Handler dispatch pattern with COMMAND_HANDLERS dict

### Integration Points
- Unity Editor addon: New C# addon that listens on TCP port
- Python TCP client: Replaces or augments existing `_write_to_unity` + `_read_unity_result`
- All existing unity_* tools benefit from direct execution capability

</code_context>

<specifics>
## Specific Ideas

- The Blender bridge already proves this TCP addon pattern works — the Unity version follows the same architecture
- Once QA-00 is done, the "write C# + recompile + execute menu item" flow becomes: "send command over TCP → Unity executes → return result" — much faster and no mcp-unity needed
- The Unity addon should auto-start when Unity Editor opens (via [InitializeOnLoad])
- Connection retry logic needed since Unity may not be running when MCP server starts
- Profiler data should be queryable in real-time during Play Mode via the TCP bridge

</specifics>

<deferred>
## Deferred Ideas

None — autonomous mode stayed within phase scope

</deferred>

---

*Phase: 16-quality-assurance-testing*
*Context gathered: 2026-03-20 via autonomous mode*
