# Phase 1: Foundation & Server Architecture - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the MCP server skeleton, Blender socket bridge, compound tool dispatch pattern, async job queue, visual feedback system (screenshots + contact sheets), and security layer. This is the foundation everything else depends on — Claude can connect to Blender, dispatch validated commands, and receive visual proof of every mutation.

Requirements: ARCH-01 through ARCH-08 (8 requirements)

</domain>

<decisions>
## Implementation Decisions

### Command Dispatch Pattern
- Compound tool granularity: 12 category-level tools (blender_rig, blender_animate, blender_mesh_edit, etc.), each accepting an `action` string and `params` dict
- Action parameter format: `action: str` + `params: dict` — simple, fast to parse, easy to document in tool descriptions
- Response format: Structured dict with `{status, data, errors, screenshot_base64?}` — every response has consistent shape
- Unknown action handling: Return structured error listing all valid actions for that tool — self-documenting API
- Total tool count across all 3 servers must not exceed 26 (token budget: ~5,200 tokens)

### Visual Feedback System
- Screenshot resolution: 512x512 default, configurable per-call via `resolution` param — balances quality vs token cost
- Contact sheet layout: Grid of 3 angles (front, side, three-quarter) x N frames, configurable frame step — maximum information per image
- Auto-capture: After every mutation by default, skippable via `capture=False` parameter — safety-first approach
- Image encoding: Base64 PNG embedded in response dict, with option to save to disk and return file path instead for large images
- Contact sheet rendering uses Blender's offscreen render with temporary cameras positioned around the object

### Blender Bridge Reliability
- Timeout strategy: Per-operation timeout (default 30s) with async job queue for operations expected to take >5 seconds (rigging, baking, boolean, etc.)
- Reconnection: Auto-reconnect with 3 retries, exponential backoff (1s, 2s, 4s) on connection loss
- Long operation pattern: Async job ID returned immediately → poll for status → get result when complete. Prevents socket death on 30s+ operations.
- Main thread safety: ALL bpy calls dispatched via command queue + `bpy.app.timers.register`. Socket thread NEVER calls bpy directly. This is non-negotiable per Blender API docs — bpy is not thread-safe.
- Command queue: Thread-safe `queue.Queue` between socket listener thread and timer-dispatched handler

### Security Model
- Command validation: Whitelist of registered command handlers only. NO arbitrary code execution, NO raw exec(), NO eval(). Every command must be explicitly registered.
- Input sanitization: Validate all params against expected types (str, int, float, list, dict) before dispatch. Reject unexpected types.
- File path handling: Restrict to project directory + OS temp directory. No arbitrary filesystem traversal.
- Error disclosure: Full error details in structured response (this is a dev tool, not a public API — detailed errors help debugging)

### Claude's Discretion
- Exact socket port number (default 9877 to avoid conflict with blender-mcp on 9876)
- Internal code organization within each module
- Blender addon UI panel design details
- Specific bpy.app.timers polling interval (recommend 0.1s)
- Whether to use msgpack or JSON for socket wire format (JSON recommended for debuggability)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### MCP Server Architecture
- `docs/MASTERPLAN_V2.md` — Full architecture overview, compound tool definitions, all 26 tools with action lists
- `.planning/research/STACK.md` — Technology stack decisions: FastMCP 3.0, Python 3.12, MCP SDK 1.26.0
- `.planning/research/ARCHITECTURE.md` — Three-legged IPC pattern, component boundaries, data flow
- `.planning/research/PITFALLS.md` — 14 domain pitfalls with prevention strategies (especially #1 tool explosion, #2 socket death, #3 blind execution, #4 exec security, #5 threading)

### Existing Code (Skeleton)
- `blender-gamedev/server.py` — V1 FastMCP server skeleton with individual tool definitions (MUST be refactored to compound pattern)
- `blender-gamedev/blender_addon.py` — V1 Blender addon with socket server, command dispatcher, basic handlers (topology, deformation test, export)
- `asset-pipeline/server.py` — V1 asset pipeline server skeleton (not Phase 1 scope but shows FastMCP patterns)

### External References
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk (v1.26.0)
- FastMCP: https://gofastmcp.com/ (v3.0)
- Blender Python API: https://docs.blender.org/api/current/ (bpy.app.timers, bmesh, bpy.types.Operator)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `blender-gamedev/server.py`: Has FastMCP server setup, tool decorator pattern, and `send_to_blender()` socket communication function. Tool definitions need refactoring from individual to compound pattern but the communication layer is usable.
- `blender-gamedev/blender_addon.py`: Has CommandServer class with socket listener, command dispatcher, handler decorator, basic UI panel. Threading model needs upgrade from blocking to async job queue.
- `blender_addon.py` handlers: `analyze_mesh_for_rigging`, `analyze_topology`, `test_deformation`, `export_to_unity` — basic implementations exist but need validation layer added.

### Established Patterns
- Handler registration via `@handler("name")` decorator pattern in addon — good, keep this
- Socket protocol: length-prefixed JSON messages (4-byte big-endian length header) — proven pattern, keep this
- Blender addon registered as Panel with start/stop operators — standard approach

### Integration Points
- Server entry point: `blender-gamedev/server.py` → `mcp.run()` for stdio transport
- Addon ↔ Server: TCP socket on port 9877 (separate from blender-mcp's 9876)
- Server reads `.mcp.json` in VeilBreakers project for Claude Code integration

</code_context>

<specifics>
## Specific Ideas

- The V1 skeleton has ~50 individual tool definitions — Phase 1 MUST refactor to compound pattern before ANY domain tools are added
- Contact sheet is the #1 priority visual feedback feature — it's what lets Claude "see" animation and deformation results
- The async job queue pattern must be proven with a known-heavy operation (like boolean or subdivision) before Phase 2 depends on it
- Every tool response must include `status` field for programmatic checking — not just free-form text

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation-server-architecture*
*Context gathered: 2026-03-18*
