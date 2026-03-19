# Phase 1: Foundation & Server Architecture - Research

**Researched:** 2026-03-19
**Domain:** MCP Python Server + Blender TCP Socket Bridge + Visual Verification Pipeline
**Confidence:** HIGH

## Summary

This phase builds the core communication layer between Claude (MCP host) and Blender: a Python MCP server that dispatches validated commands over TCP to a Blender addon, receives structured responses, captures viewport screenshots as visual proof, and composes multi-angle contact sheets. The entire chain must work end-to-end before any higher-level tools (asset generation, mesh processing) are meaningful.

The existing project has a working `blender-mcp` (ahujasid) integration via `.mcp.json` and a `Tools/DCC_Bridge/BlenderAddon/` with a manually-operated export addon. This phase replaces the third-party blender-mcp with a custom `blender-gamedev` server that uses compound action tools (fewer tools, lower token cost), mandatory visual verification, and AST-validated code execution instead of raw `exec()`.

**Primary recommendation:** Build the Blender addon socket server first (queue + timer pattern), then the MCP server with compound tools, then visual verification. The socket bridge is the riskiest component -- if threading is wrong, everything built on top crashes silently.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ARCH-01 | Claude can invoke compound tools that dispatch multiple Blender operations in a single call | Compound action tool pattern (Section: Architecture Patterns > Compound Action Tools); FastMCP `@mcp.tool()` decorator with `action: Literal[...]` parameter multiplexing |
| ARCH-02 | Blender operation returns viewport screenshot proving mutation happened | FastMCP `Image` class for returning PNG bytes; Blender `bpy.ops.screen.screenshot_area()` or `bpy.ops.render.opengl()` for viewport capture; screenshot-after-mutation pattern (Section: Visual Verification) |
| ARCH-03 | Malformed/dangerous commands return structured error with recovery suggestion -- no raw Python exec reaches Blender | AST-based validation with import whitelist using `ast.parse()` + `ast.NodeVisitor`; RestrictedPython for hardened subset; structured error response pattern `{error_type, message, suggestion, can_retry}` (Section: Security > Code Execution Sandboxing) |
| ARCH-04 | Contact sheet system renders multi-angle/multi-frame composite image | Multi-camera turntable render via Python-scripted camera placement + `bpy.ops.render.render(write_still=True)` per angle; Pillow `Image.new()` + `paste()` for grid composition; return via FastMCP `Image(data=bytes, format="png")` (Section: Contact Sheet System) |
| ARCH-05 | Blender addon survives rapid sequential tool calls without deadlocks or dropped commands | Queue + timer pattern: `queue.Queue()` on socket thread, `bpy.app.timers.register()` polling every 0.05s on main thread; single-command serialization; never call bpy from background thread (Section: Architecture Patterns > Timer-Bridged Main Thread Execution) |
| ARCH-06 | TCP socket bridge between MCP server and Blender addon handles connect/reconnect/timeout | BlenderConnection dataclass with connect/disconnect/reconnect lifecycle; 180s receive timeout; ping-based health check; graceful reconnection on socket death (Section: Socket Protocol) |
| ARCH-07 | MCP server uses stdio transport for Claude Code integration | FastMCP `mcp.run(transport="stdio")` -- zero configuration; `.mcp.json` entry with `uv run` command (Section: Transport) |
| ARCH-08 | Project scaffolded with uv, pyproject.toml, proper package structure | `uv init --python 3.12`, `uv add "mcp[cli]>=1.26.0"`, monorepo under `Tools/mcp-toolkit/` with `src/veilbreakers_mcp/` package (Section: Project Structure) |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.x | Runtime for MCP server and shared utilities | MCP SDK requires >=3.10; Blender 4.x embeds 3.11-3.12; 3.12 is the sweet spot for both compatibility and performance |
| mcp (official SDK) | >=1.26.0 | MCP protocol, FastMCP decorator API, stdio transport | The official Anthropic SDK; includes `mcp.server.fastmcp.FastMCP`, `Image` class, structured content support. No alternative exists. |
| uv | latest | Package management, venv, project scaffolding | MCP ecosystem standard. 10-100x faster than pip. `uv init`, `uv add`, `uv sync`. Lock files committed. |
| Pillow | >=12.1.0 | Contact sheet composition, image resizing, format conversion | Standard Python image library. Used to compose multi-angle screenshots into grid contact sheets. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | >=2.12.0 | Tool parameter validation, config schemas | Already bundled with MCP SDK. Use Pydantic models for all command/response schemas. |
| pydantic-settings | >=2.5.2 | Environment variable + .env configuration | Already bundled with MCP SDK. Use for BLENDER_PORT, BLENDER_HOST, project paths. |
| python-dotenv | >=1.0.0 | .env file loading | Lightweight. Keep port/host config in `.env`, never in code. |
| RestrictedPython | >=7.0 | Hardened Python subset for code execution tool | Use for the `execute_blender_code` escape hatch tool. Blocks `os`, `sys`, `subprocess` imports at AST level. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Official MCP SDK FastMCP | Standalone FastMCP 3.x | Standalone adds composition/proxying not needed for Phase 1. Use built-in SDK FastMCP. Upgrade later if multi-server composition is needed. |
| RestrictedPython | Custom AST walker | RestrictedPython is battle-tested; custom walker risks missing bypass vectors. Use RestrictedPython. |
| Pillow for contact sheets | ImageMagick/Wand | ImageMagick is an external system dependency. Pillow is pure Python, already needed for other image tasks. |
| TCP raw sockets | WebSocket (websockets lib) | TCP JSON protocol matches proven ahujasid/blender-mcp pattern. WebSocket adds handshake overhead with no benefit for localhost IPC. |

**Installation:**
```bash
# From project root
cd Tools/mcp-toolkit
uv init --python 3.12
uv add "mcp[cli]>=1.26.0"
uv add "Pillow>=12.1.0"
uv add "python-dotenv>=1.0.0"
uv add "RestrictedPython>=7.0"

# Dev dependencies
uv add --dev "pytest>=8.0"
uv add --dev "pytest-asyncio>=0.24.0"
uv add --dev "ruff>=0.8.0"
```

## Architecture Patterns

### Recommended Project Structure

```
Tools/
  mcp-toolkit/
    pyproject.toml              # uv project, entry points, dependencies
    uv.lock                     # Committed to git
    .env                        # BLENDER_PORT=9876, etc. (NOT committed)
    .env.example                # Template (committed)
    src/
      veilbreakers_mcp/
        __init__.py
        blender_server.py       # MCP server: compound Blender tools
        shared/
          __init__.py
          blender_client.py     # TCP socket client (BlenderConnection)
          models.py             # Pydantic models for commands/responses
          config.py             # pydantic-settings configuration
          image_utils.py        # Contact sheet composition, screenshot helpers
          security.py           # AST validation, import whitelist
    tests/
      test_blender_connection.py
      test_compound_tools.py
      test_security.py
      test_contact_sheet.py
    blender_addon/
      __init__.py               # Blender addon registration (bl_info)
      socket_server.py          # TCP server + command queue + timer dispatch
      handlers/
        __init__.py
        scene.py                # Scene inspection, configuration
        objects.py              # Object CRUD, transforms, hierarchy
        viewport.py             # Screenshot capture, multi-angle render
        execute.py              # Sandboxed code execution handler
```

### Pattern 1: Compound Action Tools (Token-Efficient)

**What:** Each MCP tool covers a domain and uses an `action` parameter to multiplex operations. Instead of 40+ individual tools consuming ~8000 tokens, use ~6 compound tools consuming ~1200 tokens.

**When:** Always. This is the primary tool design pattern.

**Why:** ahujasid/blender-mcp ships 25+ tools, consuming significant context. Compound tools reduce token budget by 80%+ while maintaining full capability. Anthropic's engineering blog confirms coarse-grained tools outperform fine-grained ones for LLM accuracy.

**Example:**
```python
# Source: Architecture research + FastMCP official docs
from mcp.server.fastmcp import FastMCP, Image
from typing import Literal

mcp = FastMCP("veilbreakers-blender")

@mcp.tool()
async def blender_scene(
    action: Literal["inspect", "clear", "configure", "list_objects"],
    render_engine: str | None = None,
    fps: int | None = None,
) -> dict:
    """Manage Blender scene state.

    Actions:
    - inspect: Get full scene info (objects, materials, render settings)
    - clear: Remove all objects from scene
    - configure: Set render engine, FPS, unit scale
    - list_objects: Get names and types of all objects
    """
    blender = get_blender_connection()
    if action == "inspect":
        return await blender.send_command("get_scene_info")
    elif action == "clear":
        return await blender.send_command("clear_scene")
    elif action == "configure":
        return await blender.send_command("configure_scene", {
            "render_engine": render_engine,
            "fps": fps,
        })
    elif action == "list_objects":
        return await blender.send_command("list_objects")
```

**Phase 1 tool set (~6 tools):**

| Tool | Actions | Purpose |
|------|---------|---------|
| `blender_scene` | inspect, clear, configure, list_objects | Scene lifecycle and inspection |
| `blender_object` | create, modify, delete, duplicate, list | Object CRUD and transforms |
| `blender_material` | create, assign, modify, list | Material setup (basic PBR) |
| `blender_viewport` | screenshot, contact_sheet, set_shading, navigate | Visual verification and navigation |
| `blender_execute` | (code string) | Sandboxed Python execution escape hatch |
| `blender_export` | fbx, gltf | Game-ready export with presets |

### Pattern 2: Timer-Bridged Main Thread Execution (Blender Addon)

**What:** Socket I/O runs on a daemon thread. Commands are placed in a `queue.Queue()`. A `bpy.app.timers.register()` callback polls the queue every 0.05 seconds and executes commands on Blender's main thread. Results are returned via a threading.Event + shared result container.

**When:** Every single bpy API call. No exceptions. This is the foundational safety pattern.

**Why:** bpy is NOT thread-safe. Calling bpy from any non-main thread causes segfaults, data corruption, or silent failures. The timer mechanism is Blender's official way to schedule main-thread work.

**Example:**
```python
# Source: Blender bpy.app.timers docs + ahujasid/blender-mcp addon.py pattern
import queue
import threading
import json
import socket
import bpy

class BlenderMCPServer:
    def __init__(self, port=9876):
        self.port = port
        self.command_queue = queue.Queue()
        self.server_thread = None
        self.running = False

    def start(self):
        self.running = True
        self.server_thread = threading.Thread(
            target=self._server_loop, daemon=True
        )
        self.server_thread.start()
        # Register timer to poll command queue on main thread
        bpy.app.timers.register(
            self._process_commands, first_interval=0.05, persistent=True
        )

    def _server_loop(self):
        """Runs on background thread -- NO bpy access here."""
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("localhost", self.port))
        srv.listen(1)
        srv.settimeout(1.0)
        while self.running:
            try:
                client, _ = srv.accept()
                self._handle_client(client)
            except socket.timeout:
                continue

    def _handle_client(self, client_sock):
        """Runs on background thread -- NO bpy access here."""
        # Receive JSON command, parse, enqueue with result Event
        data = self._receive_json(client_sock)
        result_event = threading.Event()
        result_container = {}
        self.command_queue.put((data, result_event, result_container))
        # Block until main thread processes command
        result_event.wait(timeout=180)
        # Send result back over socket
        response = result_container.get("response", {"status": "error", "message": "Timeout"})
        client_sock.sendall(json.dumps(response).encode("utf-8"))

    def _process_commands(self):
        """Runs on MAIN THREAD via bpy.app.timers -- safe to call bpy here."""
        try:
            while not self.command_queue.empty():
                cmd, event, container = self.command_queue.get_nowait()
                try:
                    result = self._execute_command(cmd)
                    container["response"] = {"status": "success", "result": result}
                except Exception as e:
                    container["response"] = {"status": "error", "message": str(e)}
                finally:
                    event.set()  # Unblock the socket thread
        except queue.Empty:
            pass
        return 0.05  # Re-register timer in 0.05 seconds
```

**Confidence: HIGH** -- Verified against [Blender bpy.app.timers docs](https://docs.blender.org/api/current/bpy.app.timers.html) and [ahujasid/blender-mcp addon.py](https://github.com/ahujasid/blender-mcp/blob/main/addon.py).

### Pattern 3: Visual Verification After Every Mutation

**What:** Every tool that changes scene state (create, modify, delete, material change) captures a viewport screenshot and returns it alongside the structured result. The LLM sees what it did.

**When:** After every mutation operation. Non-negotiable for 3D work.

**Why:** Text confirmation ("Object created successfully") is meaningless for 3D modeling. The LLM cannot verify visual correctness without seeing the result. This is the #1 differentiator from existing broken implementations.

**Example:**
```python
# Source: FastMCP Image class docs + ahujasid/blender-mcp screenshot pattern
from mcp.server.fastmcp import Image

@mcp.tool()
async def blender_object(
    action: Literal["create", "modify", "delete", "duplicate", "list"],
    name: str | None = None,
    mesh_type: str | None = None,
    position: list[float] | None = None,
    rotation: list[float] | None = None,
    scale: list[float] | None = None,
    capture_viewport: bool = True,
) -> list[str | Image]:
    """Manage Blender objects with visual verification."""
    blender = get_blender_connection()
    result = await blender.send_command(f"object_{action}", {
        "name": name, "mesh_type": mesh_type,
        "position": position, "rotation": rotation, "scale": scale,
    })

    response_parts = [json.dumps(result, indent=2)]

    if capture_viewport and action != "list":
        screenshot_bytes = await blender.capture_viewport()
        response_parts.append(Image(data=screenshot_bytes, format="png"))

    return response_parts
```

### Pattern 4: Contact Sheet Composition

**What:** Render multiple camera angles of an object (front, side, top, 3/4 view) into a single composite grid image. Returns one image containing 4-9 views instead of 4-9 separate images.

**When:** After complex operations (rigging, material setup, full character creation) where a single angle is insufficient.

**Why:** Token-efficient (one image vs many) and gives the LLM comprehensive spatial understanding. Modeled after reference sheet / turntable patterns used in 3D art production.

**Implementation approach:**
```python
# Blender addon side: render multiple angles to temp files
def render_contact_sheet(object_name, angles, resolution=(512, 512)):
    """Render N camera angles and return file paths."""
    import tempfile
    paths = []
    cam = bpy.data.objects.get("ContactSheet_Camera")
    if not cam:
        cam_data = bpy.data.cameras.new("ContactSheet_Camera")
        cam = bpy.data.objects.new("ContactSheet_Camera", cam_data)
        bpy.context.scene.collection.objects.link(cam)

    target = bpy.data.objects.get(object_name)
    if not target:
        return {"status": "error", "message": f"Object '{object_name}' not found"}

    center = target.location
    for i, (azimuth, elevation) in enumerate(angles):
        # Position camera on sphere around target
        import math
        distance = max(target.dimensions) * 2.5
        x = center.x + distance * math.cos(math.radians(elevation)) * math.cos(math.radians(azimuth))
        y = center.y + distance * math.cos(math.radians(elevation)) * math.sin(math.radians(azimuth))
        z = center.z + distance * math.sin(math.radians(elevation))
        cam.location = (x, y, z)

        # Point camera at target
        direction = center - cam.location
        cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

        bpy.context.scene.camera = cam
        bpy.context.scene.render.resolution_x = resolution[0]
        bpy.context.scene.render.resolution_y = resolution[1]

        path = os.path.join(tempfile.gettempdir(), f"contact_{i}.png")
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        paths.append(path)

    return {"status": "success", "paths": paths, "count": len(paths)}

# MCP server side: compose grid with Pillow
from PIL import Image as PILImage

def compose_contact_sheet(image_paths, cols=3):
    """Stitch individual renders into a grid contact sheet."""
    images = [PILImage.open(p) for p in image_paths]
    w, h = images[0].size
    rows = math.ceil(len(images) / cols)
    sheet = PILImage.new("RGB", (w * cols, h * rows), (30, 30, 30))
    for i, img in enumerate(images):
        x = (i % cols) * w
        y = (i // cols) * h
        sheet.paste(img, (x, y))
    buf = io.BytesIO()
    sheet.save(buf, format="PNG")
    return buf.getvalue()
```

**Default angles for contact sheet:**
- Front (0, 0)
- Right Side (90, 0)
- Back (180, 0)
- Left Side (270, 0)
- Top (0, 90)
- 3/4 View (45, 30)

### Anti-Patterns to Avoid

- **One tool per bpy operation:** Creates 40-80 tools, wastes 8000-16000 tokens. Use compound action tools.
- **Raw `exec()` without validation:** Security hole. Always AST-validate or use RestrictedPython.
- **Calling bpy from socket thread:** Causes segfaults. Always dispatch through queue + timer.
- **Text-only tool responses for mutations:** LLM cannot verify 3D correctness. Always include viewport screenshot.
- **Synchronous long-running calls:** Block MCP connection, risk timeout. Use async job pattern for operations over 30 seconds.
- **Cached bpy.data references across tool calls:** Dangling pointers cause crashes. Resolve by name every time.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MCP protocol handling | Custom JSON-RPC over stdio | `mcp.server.fastmcp.FastMCP` | Protocol is complex (JSON-RPC + lifecycle + capability negotiation). SDK handles it. |
| Image encoding for MCP | Manual base64 encoding | `mcp.server.fastmcp.Image(data=bytes, format="png")` | FastMCP auto-handles base64 encoding, MIME type, and MCP content blocks. |
| Python sandboxing | Custom AST walker | RestrictedPython | Battle-tested library. Custom walker risks missing bypass vectors (e.g., `__import__`, `__builtins__`, `getattr` chains). |
| Package management | pip + requirements.txt | uv | MCP ecosystem standard. Lock files, fast resolution, reproducible installs. |
| Config management | Manual env var parsing | pydantic-settings | Type-safe, validates on load, reads .env files, documents config schema. |
| Contact sheet grid layout | Manual pixel math | Pillow `Image.new()` + `paste()` | Handles format conversion, memory management, and encoding. Trivial API. |

**Key insight:** The MCP SDK and Blender's bpy API are both large, well-documented surfaces. The value add is in the INTEGRATION (socket bridge, visual verification, compound tools, security) -- not in reimplementing what already exists.

## Common Pitfalls

### Pitfall 1: Blender Threading Crashes (CRITICAL)

**What goes wrong:** Calling any bpy API from the socket handler thread causes segfaults or data corruption. No Python traceback -- Blender just crashes.
**Why it happens:** bpy is not thread-safe. The GIL does NOT protect bpy internals (they use C-level locks that don't interoperate with Python threading).
**How to avoid:** Queue + timer pattern. Socket thread puts commands in `queue.Queue()`. `bpy.app.timers.register()` callback processes them on main thread. Single-command serialization -- never allow concurrent bpy operations.
**Warning signs:** Blender crashes with no error output. Operations work individually but fail when sequenced rapidly.

### Pitfall 2: Socket Timeout on Long Operations

**What goes wrong:** Complex operations (rigging, booleans, contact sheet renders) take >60s. Socket timeout fires. Connection dies. Partial state left in Blender.
**Why it happens:** ahujasid/blender-mcp uses 180s timeout, but contact sheet rendering 6 angles at 512x512 can exceed this with EEVEE.
**How to avoid:** For Phase 1, set generous timeout (300s). For Phase 2+, implement async job pattern: return job_id immediately, poll via status command, download result when done. Also chunk contact sheet renders into individual angle requests if timeout is an issue.
**Warning signs:** "Socket timeout during chunked receive" errors. Operations that work in Blender UI but fail via MCP.

### Pitfall 3: Tool Explosion Token Budget

**What goes wrong:** Defining 25+ individual tools consumes 5000+ tokens before the first user message. LLM accuracy degrades with more tools.
**Why it happens:** Natural tendency to map each bpy operation to one MCP tool.
**How to avoid:** ~6 compound tools with action parameter multiplexing. Total schema cost ~1200 tokens. Each tool has clear domain responsibility.
**Warning signs:** Conversation starts consuming >5000 tokens in tool definitions. LLM frequently picks wrong tool.

### Pitfall 4: No Visual Feedback Loop

**What goes wrong:** LLM creates objects, receives "success" text, proceeds through 20 steps. Final result is visually broken because step 3 had wrong bone orientation.
**Why it happens:** Text confirmation for 3D operations is meaningless. LLM cannot detect geometric/visual errors without seeing the viewport.
**How to avoid:** Every mutation tool returns `list[str | Image]` -- structured result + viewport screenshot. LLM evaluates visual correctness before proceeding.
**Warning signs:** Tools return only text. User discovers problems only on manual inspection.

### Pitfall 5: Unrestricted Code Execution

**What goes wrong:** `execute_blender_code` tool accepts arbitrary Python and passes to `exec()`. Prompt injection or confused LLM runs `import os; os.system("rm -rf /")`.
**Why it happens:** bpy API is vast; encoding every operation as a tool is impractical. Code execution is the escape hatch. But `exec()` has full OS access.
**How to avoid:** AST validation with import whitelist (`bpy`, `mathutils`, `bmesh`, `math`, `random`, `json`). Block `os`, `sys`, `subprocess`, `socket`, `http`, `shutil`, `ctypes`, `importlib`. Use RestrictedPython for hardened subset. Log all executed code.
**Warning signs:** `exec(` or `eval(` in code without AST validation. No import restrictions.

### Pitfall 6: Blender Data Block Reference Invalidation

**What goes wrong:** Python references to `bpy.data.meshes["MyMesh"]` become dangling pointers when Blender reallocates internal memory (e.g., when adding new objects). Accessing invalidated references causes segfaults.
**Why it happens:** Blender C-level memory management doesn't notify Python wrappers of reallocation.
**How to avoid:** Never cache bpy.data references across MCP tool calls. Resolve by name at the start of each command handler. Use object names (strings) as stable identifiers in MCP commands.
**Warning signs:** `ReferenceError: StructRNA of type Object has been removed`. Crashes after adding objects to a scene that already has cached references.

## Code Examples

### MCP Server Entry Point

```python
# Source: MCP Python SDK official docs + FastMCP official docs
# File: src/veilbreakers_mcp/blender_server.py

from mcp.server.fastmcp import FastMCP, Image, Context
from veilbreakers_mcp.shared.blender_client import BlenderConnection
from veilbreakers_mcp.shared.config import Settings

settings = Settings()
mcp = FastMCP(
    "veilbreakers-blender",
    description="VeilBreakers Blender game development tools",
)

_connection: BlenderConnection | None = None

def get_blender_connection() -> BlenderConnection:
    global _connection
    if _connection is None or not _connection.is_alive():
        _connection = BlenderConnection(
            host=settings.blender_host,
            port=settings.blender_port,
        )
        _connection.connect()
    return _connection

# ... tool definitions ...

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
```

### FastMCP Image Return (Verified)

```python
# Source: https://gofastmcp.com/servers/tools (FastMCP official docs)
from mcp.server.fastmcp import Image

# Return image from file path
@mcp.tool()
async def get_viewport() -> Image:
    blender = get_blender_connection()
    path = await blender.capture_viewport_to_file()
    return Image(path=path)

# Return image from bytes
@mcp.tool()
async def get_contact_sheet(object_name: str) -> Image:
    blender = get_blender_connection()
    paths = await blender.render_contact_sheet(object_name)
    sheet_bytes = compose_contact_sheet(paths)
    return Image(data=sheet_bytes, format="png")

# Return mixed text + images
@mcp.tool()
async def create_and_verify(name: str, mesh_type: str) -> list[str | Image]:
    blender = get_blender_connection()
    result = await blender.send_command("create_object", {"name": name, "mesh_type": mesh_type})
    screenshot = await blender.capture_viewport_bytes()
    return [
        f"Created {name} ({mesh_type}): {result['vertex_count']} vertices",
        Image(data=screenshot, format="png"),
    ]
```

### Structured Error Response

```python
# Source: PITFALLS.md research + MCP error handling best practices
from pydantic import BaseModel

class BlenderError(BaseModel):
    error_type: str        # "context_error", "validation_error", "timeout", "security"
    message: str           # Human-readable description
    suggestion: str        # What to do to fix it
    can_retry: bool        # Whether retrying might succeed

    def to_tool_response(self) -> str:
        return (
            f"ERROR [{self.error_type}]: {self.message}\n"
            f"SUGGESTION: {self.suggestion}\n"
            f"RETRYABLE: {'yes' if self.can_retry else 'no'}"
        )

# Usage in tool handler:
def handle_error(exc: Exception, context: str) -> str:
    if "poll() failed" in str(exc):
        return BlenderError(
            error_type="context_error",
            message=f"Blender operator failed: {context}",
            suggestion="Ensure an object is selected and in the correct mode. Use blender_object(action='list') to check scene state.",
            can_retry=True,
        ).to_tool_response()
    elif isinstance(exc, socket.timeout):
        return BlenderError(
            error_type="timeout",
            message=f"Blender did not respond within 300 seconds",
            suggestion="The operation may still be running in Blender. Use blender_scene(action='inspect') to check current state.",
            can_retry=True,
        ).to_tool_response()
    # ... more error types
```

### AST-Validated Code Execution

```python
# Source: RestrictedPython docs + Python ast module
import ast

ALLOWED_IMPORTS = frozenset({
    "bpy", "mathutils", "bmesh", "math", "random", "json",
    "bpy.data", "bpy.context", "bpy.ops", "bpy.types",
    "mathutils.Vector", "mathutils.Matrix", "mathutils.Euler",
    "mathutils.Quaternion", "mathutils.Color",
})

BLOCKED_IMPORTS = frozenset({
    "os", "sys", "subprocess", "socket", "http", "urllib",
    "shutil", "ctypes", "importlib", "pathlib", "io",
    "pickle", "shelve", "tempfile", "glob", "fnmatch",
    "__builtins__", "builtins", "code", "codeop",
})

class SecurityValidator(ast.NodeVisitor):
    def __init__(self):
        self.violations = []

    def visit_Import(self, node):
        for alias in node.names:
            module = alias.name.split(".")[0]
            if module in BLOCKED_IMPORTS:
                self.violations.append(
                    f"Blocked import: '{alias.name}' (security restriction)"
                )
            elif module not in {m.split(".")[0] for m in ALLOWED_IMPORTS}:
                self.violations.append(
                    f"Unknown import: '{alias.name}' (not in allowlist)"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            module = node.module.split(".")[0]
            if module in BLOCKED_IMPORTS:
                self.violations.append(
                    f"Blocked import: 'from {node.module}' (security restriction)"
                )
        self.generic_visit(node)

    def visit_Call(self, node):
        # Block exec() and eval() calls
        if isinstance(node.func, ast.Name) and node.func.id in ("exec", "eval", "compile"):
            self.violations.append(
                f"Blocked function: '{node.func.id}()' (security restriction)"
            )
        # Block getattr/setattr with dynamic arguments (bypass vectors)
        if isinstance(node.func, ast.Name) and node.func.id in ("getattr", "setattr", "delattr"):
            self.violations.append(
                f"Blocked function: '{node.func.id}()' (potential bypass vector)"
            )
        self.generic_visit(node)

def validate_code(code: str) -> tuple[bool, list[str]]:
    """Validate Python code against security whitelist.
    Returns (is_safe, violations)."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, [f"Syntax error: {e}"]

    validator = SecurityValidator()
    validator.visit(tree)
    return len(validator.violations) == 0, validator.violations
```

### .mcp.json Integration

```json
{
  "mcpServers": {
    "vb-blender": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "Tools/mcp-toolkit", "run", "vb-blender-mcp"],
      "env": {
        "BLENDER_PORT": "9876",
        "BLENDER_HOST": "localhost"
      },
      "description": "VeilBreakers Blender tools: scene, objects, materials, viewport, export"
    }
  }
}
```

### pyproject.toml Entry Points

```toml
[project.scripts]
vb-blender-mcp = "veilbreakers_mcp.blender_server:main"
```

## Socket Protocol

### Message Format

```
# Command (MCP server -> Blender addon)
{"type": "create_object", "params": {"name": "Dragon", "mesh_type": "cube", "position": [0, 0, 0]}}

# Success response (Blender addon -> MCP server)
{"status": "success", "result": {"object_name": "Dragon", "vertex_count": 8, "bounds": [1, 1, 1]}}

# Error response (Blender addon -> MCP server)
{"status": "error", "message": "No active mesh object for subdivision", "error_type": "context_error"}

# Screenshot command
{"type": "get_viewport_screenshot", "params": {"max_size": 1024, "filepath": "/tmp/vb_screenshot.png", "format": "png"}}

# Contact sheet command
{"type": "render_contact_sheet", "params": {"object_name": "Dragon", "angles": [[0,0],[90,0],[180,0],[270,0],[0,90],[45,30]], "resolution": [512,512]}}
```

### Connection Lifecycle

1. MCP server starts (via stdio from Claude Code)
2. First tool call triggers `BlenderConnection.connect()` to `localhost:9876`
3. If Blender addon is not running, connection fails with actionable error: "Start Blender and enable the VeilBreakers addon"
4. Each tool call: send JSON command, wait for JSON response (300s timeout)
5. On timeout or connection error: set socket to None, next call attempts reconnect
6. Ping/health check: `send_command("ping")` returns `{"status": "success", "result": "pong"}`

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SSE transport for MCP | Streamable HTTP (remote) or stdio (local) | MCP spec 2025-03-26 | SSE deprecated. Use stdio for local. |
| One tool per operation | Compound action tools | 2025 (Speakeasy, mcp-unity) | 80-96% token reduction |
| Raw exec() for Blender code | AST-validated execution with import whitelist | 2025-2026 (security research) | Prevents prompt injection attacks |
| Text-only tool responses | Image + text mixed responses | FastMCP 2025 | Visual verification enables 3D work |
| Synchronous socket protocol | Async job pattern for long operations | ahujasid/blender-mcp issues 2025 | Prevents timeout failures |

**Deprecated/outdated:**
- SSE transport: Removed from MCP spec 2025-03-26. Do not use.
- `bgl` module in Blender: Removed in Blender 4.0. Use `gpu` module for offscreen rendering.
- `BGL` based viewport capture: Replace with `bpy.ops.screen.screenshot_area()` or `bpy.ops.render.opengl()`.

## Open Questions

1. **Blender version compatibility scope**
   - What we know: Blender 4.2+ uses Python 3.11-3.12. `bpy.context.temp_override()` was introduced in 3.2+. `bgl` was removed in 4.0.
   - What's unclear: Does the user have Blender 4.x or 5.x installed? What specific version?
   - Recommendation: Target Blender 4.2+ as minimum. Add version check in addon `register()`. Test with whatever Blender version the user has installed.

2. **Viewport screenshot vs render for contact sheets**
   - What we know: `bpy.ops.screen.screenshot_area()` captures the viewport (fast, shows current shading). `bpy.ops.render.render(write_still=True)` does a full render (slow, uses render settings).
   - What's unclear: For contact sheets, is viewport capture sufficient quality, or do we need full EEVEE renders?
   - Recommendation: Default to `bpy.ops.render.opengl(write_still=True)` which renders the viewport at configured resolution -- faster than full render but better than screenshot. Fall back to full render only if explicitly requested.

3. **Existing blender-mcp coexistence**
   - What we know: `.mcp.json` already has a `"blender"` entry using `uvx blender-mcp`. Both would try to connect to port 9876.
   - What's unclear: Should we replace or coexist?
   - Recommendation: Replace. The custom server is a superset. Remove the `"blender"` entry from `.mcp.json` when the custom `"vb-blender"` entry is added.

4. **Contact sheet camera: temporary vs persistent**
   - What we know: Creating a camera for contact sheet renders adds it to the scene. Deleting it after may trigger undo issues.
   - What's unclear: Should the contact sheet camera be a persistent hidden object or created/destroyed per render?
   - Recommendation: Create once, hide from viewport and render (`cam.hide_set(True)`, `cam.hide_render = True`). Reuse across contact sheet calls. Clean up on addon unregister.

## Sources

### Primary (HIGH confidence)
- [MCP Python SDK - GitHub](https://github.com/modelcontextprotocol/python-sdk) -- v1.26.0, FastMCP API, Image class, structured content
- [FastMCP Tools Documentation](https://gofastmcp.com/servers/tools) -- Image return type, ToolResult, mixed content responses
- [Blender bpy.app.timers](https://docs.blender.org/api/current/bpy.app.timers.html) -- Timer-based main thread dispatch
- [ahujasid/blender-mcp addon.py](https://github.com/ahujasid/blender-mcp/blob/main/addon.py) -- Socket server architecture, screenshot capture, command dispatch
- [ahujasid/blender-mcp server.py](https://github.com/ahujasid/blender-mcp/blob/main/src/blender_mcp/server.py) -- 25+ tool definitions, BlenderConnection lifecycle, Image return
- [RestrictedPython - PyPI](https://pypi.org/project/RestrictedPython/) -- Python sandboxing library
- [Blender Render Operators](https://docs.blender.org/api/current/bpy.ops.render.html) -- render.render(), render.opengl() for viewport/full render

### Secondary (MEDIUM confidence)
- [Speakeasy: 100x Token Reduction](https://www.speakeasy.com/blog/how-we-reduced-token-usage-by-100x-dynamic-toolsets-v2) -- Dynamic toolset and compound tool pattern validation
- [Two Six Technologies: AST Sandboxing](https://twosixtech.com/blog/hijacking-the-ast-to-safely-handle-untrusted-python/) -- AST-based Python sandboxing approach
- [Blender Developer Forum: Thread Safety](https://devtalk.blender.org/t/thread-safety-with-bpy-api/16468) -- Threading prohibition confirmation
- [MCP Error Handling Guide](https://mcpcat.io/guides/error-handling-custom-mcp-servers/) -- Structured error responses
- [zmaril/multirender](https://github.com/zmaril/multirender) -- Contact sheet composition pattern for Blender

### Tertiary (LOW confidence)
- Contact sheet default camera angles (0/90/180/270 azimuth + top + 3/4 view) -- Based on 3D art production conventions, not verified against a specific tool

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- MCP SDK, uv, Pillow all verified against official sources
- Architecture (socket bridge): HIGH -- Proven pattern from ahujasid/blender-mcp with 5k+ stars
- Architecture (compound tools): HIGH -- Token reduction validated by Speakeasy, mcp-unity, Anthropic blog
- Visual verification: HIGH -- FastMCP Image class verified, screenshot APIs documented
- Security (AST validation): MEDIUM -- RestrictedPython is proven, but custom AST walker needs testing
- Contact sheet system: MEDIUM -- Individual components verified (render API, Pillow composition), but end-to-end integration is novel
- Pitfalls: HIGH -- All critical pitfalls verified against official docs and real-world issue reports

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable domain -- MCP SDK and Blender API are not fast-moving)
