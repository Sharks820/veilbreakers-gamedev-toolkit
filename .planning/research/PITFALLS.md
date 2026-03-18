# Domain Pitfalls: AI Game Dev Toolkit (MCP Servers for Blender + Unity)

**Domain:** MCP server ecosystem bridging Blender and Unity for AI-assisted 3D game asset creation
**Researched:** 2026-03-18
**Confidence:** HIGH (verified against official Blender API docs, MCP specification, blender-mcp issue tracker, and multiple production post-mortems)

---

## Critical Pitfalls

Mistakes that cause architectural rewrites, data loss, or project abandonment.

---

### Pitfall 1: Tool Explosion Destroys Token Budget Before Work Begins

**What goes wrong:**
Every MCP tool definition is injected into the LLM's context window at conversation start. A Blender MCP server with 40+ tools consumes 15,000-25,000 tokens just in schema definitions. Add a Unity MCP server with another 30+ tools and you burn 30,000-60,000 tokens before the first user message. At that point 25-30% of the context window is metadata, the LLM struggles to select the right tool, and per-session costs balloon. The existing blender-mcp project (ahujasid/blender-mcp) ships 40+ tools and users report 100K+ token sessions for simple tasks.

**Why it happens:**
Developers design MCP tools like REST APIs -- one endpoint per operation. `create_cube`, `create_sphere`, `create_cylinder`, `create_cone` become four tools when `create_primitive(shape="cube")` would suffice. Each tool carries a full JSON schema with parameter descriptions, types, and examples. The LLM sees ALL tools regardless of whether it needs them for the current task.

**Consequences:**
- 25-30% of context window wasted on tool schemas the LLM never uses
- LLM accuracy degrades as tool count increases -- it picks wrong tools or hallucinates parameters
- Session costs 5-10x higher than necessary (Speakeasy measured 102,000 tokens for a task that should use 2,000)
- Users hit context limits mid-task and lose conversation state

**Prevention:**
1. **Dynamic toolsets:** Expose 3 meta-tools (`search_tools`, `describe_tool`, `execute_tool`) instead of 40 individual tools. LLM discovers what it needs, loads schemas on demand. Speakeasy achieved 96.7% token reduction with this pattern.
2. **Intent-based tool design:** Group by user goal, not API operation. `create_character_model` (high-level) instead of 15 mesh/bone/material tools. Anthropic's engineering blog confirms coarse-grained tools outperform fine-grained ones.
3. **Code execution fallback:** For complex Blender operations, expose a single `execute_blender_code` tool that runs Python. This avoids encoding every bpy operation as an MCP tool. Token cost drops from 150K to 2K per Anthropic's measurements.
4. **Category gating:** Register tools by workflow context (modeling, rigging, texturing, export). Only load the relevant category for the current task.

**Warning signs:**
- Conversation starts consume more than 10,000 tokens before user's first message
- LLM frequently calls wrong tools or passes incorrect parameters
- Users report "the AI forgot what I asked" mid-session (context eviction)

**Detection:**
Monitor `tools_list` token count at session init. If it exceeds 15% of context window, you have a tool explosion.

**Phase to address:**
Phase 1 (Architecture) -- tool API design must be decided before any tool implementation. Retrofitting dynamic toolsets onto a static 40-tool server is a rewrite.

---

### Pitfall 2: Blender Socket Bridge Dies Silently on Long Operations

**What goes wrong:**
The standard Blender MCP architecture uses a TCP socket (typically localhost:9876) between the MCP server process and a Blender addon. The MCP server sends JSON commands, Blender executes them, returns JSON results. For quick operations (create cube, move object) this works. For long operations (generate rig, bake textures, boolean operations on complex meshes, Rodin/Hyper3D API polling), the socket times out or Blender's main thread blocks so long that the heartbeat fails. The blender-mcp issue tracker has multiple reports: "Successfully connected to Blender on startup but can't receive answer" (Issue #73), "MCP error -32001: Request Timed out" (Issue #50), and repeated "Server transport closed unexpectedly" errors.

**Why it happens:**
Blender's Python API is single-threaded. While a bpy operation executes, Blender cannot process socket reads. The MCP server's socket has a 180-second timeout (in ahujasid's implementation). Complex operations like rigging, mesh booleans, or subdivision surface baking can exceed this. The socket connection has no keepalive/heartbeat mechanism -- it's blocking send/receive with a fixed timeout. If the MCP transport (stdio or SSE) also has its own timeout, you get cascading timeouts at multiple layers.

**Consequences:**
- User's 72-hour rigging session produces nothing because the connection dropped after the first complex operation
- No way to distinguish "Blender is still working" from "Blender crashed"
- Partial state: Blender may have completed half the operation when the timeout fires, leaving the scene in an inconsistent state
- Port conflicts after unclean disconnection require Blender restart

**Prevention:**
1. **Async command pattern:** Send command, immediately return a job ID. Poll for completion via a separate lightweight status endpoint. Blender addon uses `bpy.app.timers` to check job completion without blocking.
2. **Progress reporting:** Blender addon writes progress to a shared file or separate status socket. MCP server streams progress events back to client. This solves both timeout and "is it still working?" problems.
3. **Operation chunking:** Break long operations (e.g., "rig this character") into discrete steps (create armature, add bones, set constraints, bind mesh). Each step is a short socket call. LLM orchestrates the sequence.
4. **Heartbeat mechanism:** Blender addon sends periodic "still alive" pings on a separate lightweight channel while the main operation runs.
5. **Graceful timeout recovery:** On timeout, query Blender's state before retrying. Don't blindly re-send the command -- the first one may have partially completed.

**Warning signs:**
- Operations that take more than 30 seconds in Blender fail when triggered via MCP
- "Socket timeout during chunked receive" warnings in server logs
- Users must restart Blender after failed operations due to port binding issues

**Detection:**
Log operation start time and completion time. Any operation exceeding 60 seconds without progress callback is at risk.

**Phase to address:**
Phase 1 (Architecture) -- the socket communication protocol must support async operations from day one. You cannot bolt async onto a synchronous request-response protocol without rewriting the addon.

---

### Pitfall 3: Blind Execution Without Visual Verification Loops

**What goes wrong:**
The LLM generates Blender Python code, sends it through the MCP bridge, receives a text response ("mesh created successfully"), and moves on. It never sees what it actually created. A "humanoid rig" might have bones pointing in wrong directions, inverted normals, intersecting geometry, or textures mapped to the wrong UV islands. The LLM optimistically reports success based on the absence of Python exceptions, not on visual correctness. The user's experience of "72 hours of rigging that was still broken" stems directly from this pattern.

**Why it happens:**
MCP's default response format is text/JSON. Rendering a viewport screenshot, transmitting it as base64, and having the LLM evaluate it adds latency and token cost. Most MCP server implementations skip this because it's hard and expensive. But 3D modeling is inherently visual -- text confirmation of geometric correctness is unreliable.

**Consequences:**
- Hours of LLM iterations produce geometrically invalid output
- Errors compound: wrong bone orientation in step 3 makes steps 4-20 worthless
- User doesn't discover problems until they inspect manually, at which point recovery requires starting over
- Trust erosion: users stop using the tool after one bad experience

**Prevention:**
1. **Mandatory viewport capture after mutations:** After every operation that changes geometry, materials, or armature, render a viewport screenshot and return it as part of the tool response. The LLM can then evaluate visual correctness before proceeding.
2. **Multi-angle verification:** For 3D operations, capture front + side + top views (3 screenshots). A single perspective hides problems on other axes.
3. **Automated validation checks:** Before returning "success," run programmatic checks:
   - Mesh: `bpy.ops.mesh.normals_check()`, vertex count, face count, non-manifold edges
   - Armature: bone count, chain connectivity, symmetry validation
   - UV: island count, overlap detection, coverage percentage
   - Materials: slot assignment verification, texture path validation
4. **Checkpoint/rollback system:** Before each major operation, save a `.blend` checkpoint. If the LLM determines the result is wrong, roll back to the checkpoint instead of trying to fix broken geometry.
5. **Diff visualization:** Show before/after comparisons for modifications, not just the final state.

**Warning signs:**
- Tool responses contain only text like "Object created" with no visual data
- User reports "it said it worked but when I looked in Blender it was wrong"
- LLM confidently proceeds through a 20-step workflow without any visual checkpoints

**Detection:**
Count tool responses that include image data vs. text-only. If less than 50% of mutation operations include visual verification, the feedback loop is broken.

**Phase to address:**
Phase 2 (Core Tools) -- every tool that mutates scene state must include a viewport capture in its response. This is not a "nice to have" -- it is the single most important differentiator from existing broken implementations.

---

### Pitfall 4: Arbitrary Code Execution Creates an Unrestricted Shell

**What goes wrong:**
The most powerful MCP tool for Blender is `execute_blender_code` -- it takes a Python string and passes it to `exec()` inside Blender. This gives the LLM (and by extension, any prompt injection) full access to the host machine's filesystem, network, and processes. A malicious prompt or confused LLM can run `import subprocess; subprocess.run(["rm", "-rf", "/"])` through the Blender Python interpreter. The existing blender-mcp project does exactly this: accepts arbitrary Python, passes it to `exec()` with no restriction.

**Why it happens:**
Blender's Python API (`bpy`) is so vast that encoding every operation as a typed MCP tool is impractical. The escape hatch is "just run Python." But Python's `exec()` has no sandbox -- it's a full interpreter with OS access. Developers assume the MCP server runs locally and is therefore "trusted," but MCP connections can be established remotely, and prompt injection can weaponize even local execution.

**Consequences:**
- Full filesystem access: read SSH keys, credentials, environment variables
- Network access: exfiltrate data, download malware
- Process execution: launch arbitrary binaries
- Blender state corruption: malicious scripts can corrupt the scene file

**Prevention:**
1. **Allowlist-based execution:** Instead of raw `exec()`, parse the Python AST and reject any code that imports modules outside a whitelist (`bpy`, `mathutils`, `bmesh`, `math`, `random`). Block `subprocess`, `os`, `sys`, `socket`, `http`, `shutil`, `ctypes`.
2. **Code review before execution:** Return generated code to the user for approval before running it. Add a `--auto-approve` flag for trusted workflows, but default to manual review.
3. **Scoped API surface:** Prefer typed MCP tools for common operations. Reserve `execute_blender_code` for edge cases and require explicit user opt-in.
4. **Filesystem isolation:** Run Blender in a container or with restricted filesystem permissions. Mount only the project directory, not the home folder.
5. **Execution logging:** Log every Python string sent to `exec()` with timestamp, source, and result. Enable audit trail for security review.

**Warning signs:**
- MCP tool accepts arbitrary string and passes to `exec()` without validation
- No import restrictions on executed code
- No user confirmation step before code execution
- Server documentation doesn't mention security implications

**Detection:**
Search for `exec(` and `eval(` in the server codebase. If they accept user/LLM-provided strings without AST validation, you have an unrestricted shell.

**Phase to address:**
Phase 1 (Architecture) -- security model must be designed before any `execute_code` tool is implemented. Retrofitting sandboxing onto an existing unrestricted system requires rewriting the execution layer.

---

### Pitfall 5: Blender Python Threading Prohibition Causes Deadlocks and Crashes

**What goes wrong:**
Blender's Python integration is explicitly not thread-safe. The official documentation states: "Python Threads are Not Supported." Attempting to call any `bpy` API from a background thread causes crashes, data corruption, or silent incorrect behavior. The MCP bridge naturally wants to handle socket I/O on a background thread and dispatch bpy calls on the main thread, but getting this wrong is trivial and the failure modes are catastrophic (Blender segfault, corrupted .blend file).

**Why it happens:**
The socket server in the Blender addon must listen for incoming connections without blocking Blender's UI. The obvious solution is a background thread for socket I/O. But developers then call `bpy.ops` or modify `bpy.data` directly from that thread, causing crashes. The correct pattern (thread-safe queue + `bpy.app.timers` dispatch) is non-obvious and poorly documented.

**Consequences:**
- Random Blender crashes with no Python traceback (segfault in C code)
- Corrupted scene data that only manifests when saving
- Race conditions where two MCP commands interleave their bpy modifications
- Crashes that only occur under load (multiple rapid commands), making them hard to reproduce

**Prevention:**
1. **Queue + Timer pattern:** Socket listener thread puts commands on a `queue.Queue()`. A `bpy.app.timers.register()` callback polls the queue every 0.05-0.1 seconds and executes commands on Blender's main thread. This is the ONLY safe pattern.
2. **Single-command serialization:** Process one MCP command at a time. Do not allow concurrent bpy operations even if they appear independent. Blender's internal state is globally mutable.
3. **No `bpy` imports in thread context:** The socket handler module should not import `bpy` at the module level. Only the timer callback (which runs on the main thread) should access `bpy`.
4. **Crash recovery:** Implement auto-save before each MCP command. If Blender crashes, the addon can recover from the auto-save on restart.
5. **Test under load:** Send 10 rapid MCP commands in sequence and verify no crash. This is the minimum reliability test.

**Warning signs:**
- Blender crashes with no Python error message (segfault)
- Operations work individually but fail when combined rapidly
- `bpy` calls appear in any code path that could execute off the main thread
- Threading module imported alongside bpy in the same file

**Detection:**
Grep for `import threading` or `Thread(` in addon code. Trace all code paths from thread entry points to verify no `bpy` access occurs.

**Phase to address:**
Phase 1 (Architecture) -- the Blender addon's threading model is foundational. Getting it wrong corrupts everything built on top. The queue+timer pattern must be the first thing implemented and tested.

---

### Pitfall 6: FBX Pipeline Between Blender and Unity Silently Corrupts Assets

**What goes wrong:**
The Blender-to-Unity asset pipeline via FBX is riddled with silent data loss. Per-vertex normals exported with `IndexToDirect` reference mode are misinterpreted by Unity (Blender bug #123088). Materials and textures are not embedded in FBX files -- they must be manually reassigned in Unity. Unity's FBX importer applies a 0.01 scale factor (Blender uses meters, Unity uses... also meters, but the importer scales anyway). Blender-specific modifiers (boolean, subdivision, mirror) don't export -- they must be applied first. Armature bone orientations differ between Blender and Unity conventions. An automated pipeline that doesn't account for ALL of these produces assets that look correct in Blender but are broken in Unity.

**Why it happens:**
FBX is a proprietary Autodesk format. Blender's FBX exporter is a reverse-engineered Python implementation, not an official SDK integration. Unity's FBX importer makes assumptions about authoring tools (primarily Maya/Max). The format itself cannot represent all Blender features (geometry nodes, EEVEE materials, Cycles shader trees). Every translation step is lossy.

**Consequences:**
- Models appear inside-out in Unity (inverted normals)
- Materials show as pink (missing references)
- Characters are 100x too small or too large
- Animations play at wrong speed (different FPS assumptions)
- Rigs don't deform correctly (bone roll/orientation mismatch)

**Prevention:**
1. **Standardized export preset:** Create a Blender FBX export preset that matches Unity's expectations: Apply Modifiers ON, Forward -Z, Up Y, Apply Unit ON, Apply Transform ON, Mesh > Smoothing: Face. Store this preset in version control.
2. **Pre-export validation:** Before FBX export, run automated checks: all modifiers applied, no n-gons, no zero-area faces, UV maps present, materials assigned, armature in rest pose.
3. **Post-import validation:** After Unity import, verify: correct scale (compare bounding box), material count matches, bone hierarchy intact, animation clip count/duration correct.
4. **Use glTF instead:** glTF 2.0 is an open standard with better Blender support (official exporter) and Unity support (via UnityGLTF package). It embeds textures, preserves PBR materials, and has fewer conversion gotchas than FBX.
5. **Round-trip test:** Part of CI: export from Blender, import to Unity, compare metrics (vertex count, bone count, material count, bounding box dimensions). Flag any deviation.

**Warning signs:**
- Models in Unity look different from Blender viewport
- Pink/missing materials after import
- Character is tiny or enormous
- Bones are rotated 90 degrees from expected orientation

**Detection:**
Automated comparison script that exports from Blender, imports to Unity, and diffs key metrics.

**Phase to address:**
Phase 2 (Asset Pipeline) -- export/import validation must be built into every pipeline tool, not treated as a post-hoc check.

---

## Moderate Pitfalls

Mistakes that cause significant debugging time or feature regression but not complete rewrites.

---

### Pitfall 7: Blender Operator Context Requirements Break Automation

**What goes wrong:**
Many `bpy.ops` functions require specific UI context to execute: the correct area type, an active object, a specific mode (Edit/Object/Pose), or a selected object. In interactive Blender, this context is naturally set by the user's workflow. In automated/headless mode, context is often wrong. `bpy.ops.mesh.subdivide()` fails silently if no mesh is selected. `bpy.ops.object.modifier_apply()` requires the object to be active AND in Object mode. `bpy.ops.armature.bone_primitive_add()` requires Edit mode on an armature. The error messages are often just `RuntimeError: Operator bpy.ops.mesh.subdivide.poll() failed`.

**What to do instead:**
- Prefer `bpy.data` API (low-level data manipulation) over `bpy.ops` (operator calls) wherever possible. Data API doesn't require context.
- When operators are unavoidable, use `bpy.context.temp_override()` to explicitly set the required context.
- For mode switches, always verify current mode before switching: `if obj.mode != 'EDIT': bpy.ops.object.mode_set(mode='EDIT')`.
- Wrap every operator call in try/except and return meaningful error messages that include what context was expected.

**Warning signs:**
- `poll() failed` errors with no additional context
- Operations that work in Blender UI but fail when scripted
- Mode-dependent tools that only work sometimes

**Phase to address:**
Phase 2 (Core Tools) -- every Blender tool implementation must handle context setup explicitly.

---

### Pitfall 8: Blender Undo System Corrupts State During Automated Sequences

**What goes wrong:**
Every `bpy.ops` call pushes an undo step. In a 50-step automated rigging sequence, this creates 50 undo snapshots consuming gigabytes of memory. Worse, if a step fails mid-sequence and the user (or recovery code) calls undo, it may undo to an intermediate state that was never meant to be standalone. The undo system can also crash Blender in background mode when called programmatically (Blender bug T60934). Memory from undo snapshots is NOT released until the file is saved, closed, and reopened.

**What to do instead:**
- Disable undo for automated sequences: `bpy.context.preferences.edit.use_global_undo = False` before the sequence, restore after.
- For recovery, use file-level checkpoints (save .blend before the sequence) instead of undo steps.
- After long automated sequences, use `bpy.ops.outliner.orphans_purge(do_recursive=True)` to clean up orphaned data blocks.
- Never call `bpy.ops.ed.undo()` or `bpy.ops.ed.undo_history()` in automated/background mode.

**Warning signs:**
- Memory usage grows continuously during long MCP sessions
- Blender crashes during automated sequences with no Python error
- Undo after a failed automation puts scene in unexpected state

**Phase to address:**
Phase 2 (Core Tools) -- undo management must be explicitly handled in the Blender addon, not left to Blender's defaults.

---

### Pitfall 9: MCP Error Responses That Kill the Conversation

**What goes wrong:**
When a tool fails, returning a bare error string ("Error: operation failed") gives the LLM no information to recover. It either retries blindly (same error, same result, wasting tokens) or gives up and tells the user it cannot proceed. Conversely, returning a massive stack trace (500+ tokens of Python traceback) wastes context and confuses the LLM. The sweet spot -- actionable error information that enables recovery -- is rarely implemented.

**What to do instead:**
- Return errors using MCP's `isError: true` flag in the tool response (NOT as a protocol-level JSON-RPC error). This tells the LLM "the tool ran but the operation failed" vs. "the tool itself is broken."
- Structure error responses: `{ error_type, message, suggestion, can_retry }`. Example: `{ "error_type": "context_error", "message": "No active mesh object", "suggestion": "Select a mesh object first using select_object tool", "can_retry": true }`.
- Include recovery instructions that reference other available tools.
- Limit error detail to 200 tokens maximum. Log full details server-side.
- For Blender-specific errors, translate bpy error codes into actionable messages: `poll() failed, context is incorrect` becomes "The armature must be in Edit Mode. Call set_mode('EDIT') first."

**Warning signs:**
- LLM retries the same failing operation 3+ times
- Error messages contain raw Python tracebacks
- Errors say "operation failed" without saying why or how to fix it

**Phase to address:**
Phase 2 (Core Tools) -- error handling format should be standardized before individual tools are implemented.

---

### Pitfall 10: Blender Data Block References Invalidated by Operations

**What goes wrong:**
Python objects that reference Blender data (`mesh = bpy.data.meshes["MyMesh"]`) can become dangling pointers when Blender operations reallocate internal memory. Adding items to a collection can trigger reallocation that invalidates all existing Python references to items in that collection. Accessing invalidated references causes crashes (not Python exceptions -- actual segfaults). The official docs warn: "When removing data, be sure not to hold references to it."

**What to do instead:**
- Never cache `bpy.data` references across MCP tool calls. Resolve references fresh at the start of each tool execution by name/index.
- After any operation that adds or removes objects, meshes, or materials, re-resolve all references.
- Use object names (strings) as stable identifiers passed between MCP calls, not Python object references.
- Implement a naming convention for MCP-created objects (e.g., `mcp_char_arm_01`) to enable reliable re-resolution.

**Warning signs:**
- Blender crashes when accessing objects after other operations modified the scene
- `ReferenceError: StructRNA of type Object has been removed` in Python console
- Crashes that only occur when operations are sequenced (not when run individually)

**Phase to address:**
Phase 1 (Architecture) -- the Blender addon must use name-based resolution, never cached references. This is a design principle, not a per-tool fix.

---

### Pitfall 11: MCP Transport Choice Locks You Into Architecture

**What goes wrong:**
Choosing the wrong MCP transport (stdio vs. Streamable HTTP vs. SSE) at the start constrains deployment options later. stdio is simplest but requires the server to run as a subprocess of the client -- no remote operation, no multi-client support. SSE was the original HTTP transport but is now deprecated (as of MCP spec 2025-03-26). Streamable HTTP is the current standard for remote/production servers but adds complexity. Building on stdio and discovering later that you need remote operation means rewriting the transport layer.

**What to do instead:**
- **Local-only tool (user runs Blender on their machine):** Use stdio. It's simpler, faster, and has zero network overhead. This is the right choice for a dev tool.
- **Design the server to be transport-agnostic:** Use a framework like FastMCP that abstracts transport. Switching from stdio to Streamable HTTP should be a configuration change, not a code change.
- **Never build on SSE for new projects.** It is deprecated and will be removed.
- If you must support remote operation (e.g., cloud rendering), plan for Streamable HTTP from the start.

**Warning signs:**
- Server code directly handles stdin/stdout parsing instead of using a transport abstraction
- SSE-specific code in a new project
- "We'll add remote support later" without transport abstraction

**Phase to address:**
Phase 1 (Architecture) -- transport abstraction is a one-time decision with long-lasting consequences.

---

## Minor Pitfalls

Issues that cause friction or minor bugs but are easily fixable.

---

### Pitfall 12: Blender File Path Encoding Breaks Cross-Platform

**What goes wrong:**
Blender internally uses UTF-8 for file paths, but Windows uses UTF-16. Paths with non-ASCII characters (accented usernames, CJK characters in project names) can cause silent failures in file operations. The `//` relative path prefix in Blender (relative to .blend file) doesn't translate to absolute paths correctly in all contexts.

**What to do instead:**
- Always use `bpy.path.abspath()` to resolve Blender relative paths before passing them to Python `os` functions.
- Use `pathlib.Path` instead of string concatenation for path operations.
- Test with a project path containing spaces and non-ASCII characters.

**Phase to address:**
Phase 3 (Polish) -- edge case that should be tested but doesn't block core functionality.

---

### Pitfall 13: Blender Version Skew Between Addon and Server

**What goes wrong:**
Blender 4.x/5.x changed numerous Python APIs: `bpy.props` dictionary-style access removed, `BGL` module removed entirely, new `temp_override()` syntax. If the MCP addon is developed against Blender 4.2 but the user runs Blender 5.0, scripts silently fail or crash. Blender has no built-in addon version compatibility checking.

**What to do instead:**
- Check `bpy.app.version` at addon startup and warn/block on unsupported versions.
- Document minimum and maximum supported Blender versions explicitly.
- Use `hasattr()` checks before accessing APIs that changed between versions.
- Test against the 2-3 most recent Blender stable releases.

**Phase to address:**
Phase 3 (Polish) -- version compatibility is important but can be handled after core functionality works on the primary target version.

---

### Pitfall 14: Node Wrangler and Addon Conflicts

**What goes wrong:**
Many Blender users have third-party addons installed (Node Wrangler, Auto Rig Pro, Hard Ops). These addons register custom operators, modify keymap, and can intercept or conflict with MCP tool operations. Auto Rig Pro, for example, has known syntax errors in certain Blender versions (bug #74319). If the MCP addon assumes a vanilla Blender installation, operations may fail due to addon conflicts.

**What to do instead:**
- Don't depend on any third-party addon being installed.
- Catch and handle errors from addon conflicts gracefully.
- For rigging, implement your own tools rather than depending on Auto Rig Pro being available.
- Document known addon conflicts.

**Phase to address:**
Phase 3 (Polish) -- addon conflicts are edge cases but should be documented.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Architecture & Protocol Design | Tool explosion (#1), transport lock-in (#11), threading model (#5) | Design dynamic toolset API, use transport abstraction, implement queue+timer pattern from day one |
| Blender Addon Core | Silent socket death (#2), threading crashes (#5), data block invalidation (#10) | Async command pattern with job IDs, main-thread-only bpy access, name-based resolution |
| Core Tool Implementation | Blind execution (#3), operator context failures (#7), undo corruption (#8) | Mandatory viewport capture, explicit context setup, disable undo for sequences |
| Security Layer | Arbitrary code execution (#4) | AST-validated code execution, import whitelist, user approval flow |
| Asset Pipeline (FBX/glTF) | Silent corruption (#6) | Standardized export presets, pre/post validation, prefer glTF |
| Error Handling | Conversation-killing errors (#9) | Structured error responses with recovery suggestions |
| Cross-Platform & Compatibility | Path encoding (#12), version skew (#13), addon conflicts (#14) | pathlib usage, version checking, graceful addon conflict handling |

## Domain-Specific Anti-Patterns

Patterns that seem reasonable but are consistently wrong in this domain.

| Anti-Pattern | Why It Seems Right | Why It Fails | Instead |
|-------------|-------------------|--------------|---------|
| One MCP tool per bpy operator | Clean API mapping | Tool explosion, 500+ tools, unusable token budget | Intent-based tools or code execution |
| Raw `exec()` for flexibility | Covers all Blender operations | Security nightmare, no validation | AST-checked execution with import whitelist |
| Synchronous socket protocol | Simple request/response | Long operations timeout, no progress feedback | Async jobs with status polling |
| Cached bpy.data references | Performance optimization | Dangling pointers cause crashes | Name-based resolution per-call |
| Relying on operator `poll()` | Let Blender validate context | Unhelpful error messages, silent failures | Explicit context setup with meaningful errors |
| FBX as universal interchange | Industry standard format | Lossy, proprietary, convention mismatches | glTF 2.0 or validated FBX presets |
| Text-only tool responses for 3D | Lower bandwidth/tokens | LLM cannot verify visual correctness | Viewport screenshots after mutations |
| Global undo during automation | Safety net for recovery | Memory explosion, state corruption | File-level checkpoints, disable global undo |

## "Looks Working But Isn't" Checklist

Things that pass basic testing but fail in real workflows.

- [ ] **Socket recovery:** Kill and restart the MCP server mid-session. Does Blender addon recover the connection without restarting Blender?
- [ ] **Long operation:** Trigger a 2-minute Blender operation (subdivide a 1M-poly mesh). Does the MCP connection survive?
- [ ] **Rapid fire:** Send 10 MCP commands in 2 seconds. Do all execute correctly without crashes?
- [ ] **Error recovery:** Cause a tool to fail (e.g., operate on deleted object). Does the next tool call work correctly?
- [ ] **Memory stability:** Run 50 create/delete cycles. Does Blender memory return to baseline?
- [ ] **Visual accuracy:** Create a rigged character via MCP. Compare viewport screenshot with expected result. Are bones oriented correctly?
- [ ] **FBX round-trip:** Export from Blender, import to Unity, compare vertex count, bone count, and bounding box. All match within 1%?
- [ ] **Code execution safety:** Submit code with `import os; os.listdir("/")` through execute_code tool. Is it blocked?
- [ ] **Context handling:** Call a mesh operation when an armature is selected. Does it return a meaningful error, not `poll() failed`?
- [ ] **Token budget:** Start a new session with all tools loaded. How many tokens are consumed before the first user message? Under 10K?

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|--------------|----------------|
| Tool explosion (100K+ tokens/session) | HIGH | Redesign to dynamic toolsets. Requires rewriting tool registration and adding discovery/describe meta-tools. |
| Socket timeout on long operations | MEDIUM | Add job queue and status polling to addon. Keep existing sync path for quick operations. |
| No visual verification | MEDIUM | Add viewport capture to existing tool responses. Requires adding screenshot capability to Blender addon. |
| Security hole via exec() | HIGH | Implement AST parser and import whitelist. Existing code paths must be audited and restricted. |
| Threading crash | HIGH | Rewrite addon to use queue+timer pattern. All existing bpy calls in thread context must be moved. |
| FBX corruption | LOW | Create and distribute standardized export preset. Add validation scripts. |
| Operator context failures | LOW | Add context setup wrapper around each bpy.ops call. Per-tool fix. |
| Undo memory explosion | LOW | Add undo disable/enable wrapper around automated sequences. |
| Unhelpful error responses | MEDIUM | Standardize error format across all tools. Add bpy error code translation. |
| Data block reference crash | MEDIUM | Refactor all cached references to name-based resolution. Requires auditing all addon code. |

## Sources

### Official Documentation (HIGH confidence)
- [Blender Python API: Gotchas](https://docs.blender.org/api/current/info_gotcha.html) -- Threading prohibition, operator context, data block references
- [Blender Python API: Best Practice](https://docs.blender.org/api/current/info_best_practice.html) -- Data API vs operators, context handling
- [Blender Python API: Application Timers](https://docs.blender.org/api/current/bpy.app.timers.html) -- Timer-based main thread dispatch
- [MCP Specification: Transports](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports) -- stdio vs SSE vs Streamable HTTP
- [MCP Error Handling Guide](https://mcpcat.io/guides/error-handling-custom-mcp-servers/) -- Three-tier error model, JSON-RPC codes
- [Anthropic Engineering: Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) -- 98.7% token reduction via code execution pattern

### Issue Trackers & Project Analysis (HIGH confidence)
- [blender-mcp Issue #50: Request Timed Out](https://github.com/ahujasid/blender-mcp/issues/50) -- Socket timeout failures
- [blender-mcp Issue #73: Connected but no response](https://github.com/ahujasid/blender-mcp/issues/73) -- Silent connection failures
- [blender-mcp Issue #137: Connection failing](https://github.com/ahujasid/blender-mcp/issues/137) -- Recurring connection reliability problems
- [Blender Bug #123088: FBX Normals export issue](https://projects.blender.org/blender/blender/issues/123088) -- IndexToDirect normals misinterpreted by Unity
- [Blender Bug T60934: Undo crashes in background mode](https://developer.blender.org/T60934) -- Undo system unreliable for automation

### Industry Analysis (MEDIUM confidence)
- [Speakeasy: Reducing MCP token usage by 100x](https://www.speakeasy.com/blog/how-we-reduced-token-usage-by-100x-dynamic-toolsets-v2) -- Dynamic toolsets achieving 96.7% token reduction
- [a16z: Deep Dive Into MCP and AI Tooling](https://a16z.com/a-deep-dive-into-mcp-and-the-future-of-ai-tooling/) -- Tool granularity analysis
- [Jenova.ai: MCP Context Overload](https://www.jenova.ai/en/resources/mcp-tool-scalability-problem) -- Performance degradation with tool count
- [Eclipse Source: MCP and Context Overload](https://eclipsesource.com/blogs/2026/01/22/mcp-context-overload/) -- 25-30% context window consumed by tool schemas
- [Socket communication with Blender](https://ciesie.com/post/blender_sockets/) -- Timer-based socket architecture for Blender addon

### Community & Practical Reports (MEDIUM confidence)
- [Blender Developer Forum: Thread/socket issue](https://devtalk.blender.org/t/blender-thread-socket-issue/17273) -- Threading crash patterns
- [Blender Developer Forum: Application timers usage](https://devtalk.blender.org/t/about-using-application-timers-bpy-app-timers/9593) -- Timer best practices
- [Unity Discussions: FBX import problems in 2025](https://discussions.unity.com/t/fbx-import-problems-in-2025/1576069) -- Ongoing FBX import issues
- [MCP Server Security Report (Astrix)](https://astrix.security/learn/blog/state-of-mcp-server-security-2025/) -- 53% of servers use static API keys
- [MCP Vulnerabilities (Composio)](https://composio.dev/content/mcp-vulnerabilities-every-developer-should-know) -- Confused deputy problem, prompt injection

---
*Pitfalls research for: AI Game Dev Toolkit (MCP Servers for Blender + Unity)*
*Researched: 2026-03-18*
*Confidence: HIGH overall -- critical pitfalls verified against official docs and real-world failure reports*
