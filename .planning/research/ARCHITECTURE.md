# Architecture Patterns: Multi-MCP-Server Game Development Toolkit

**Domain:** AI-assisted game development MCP toolkit (3 servers)
**Researched:** 2026-03-18
**Confidence:** HIGH (verified against MCP specification, existing open-source implementations, and official FastMCP documentation)

## System Overview

The toolkit consists of three MCP servers that collectively cover the Blender-to-Unity game development pipeline. Each server is independently deployable and communicates with the AI host (Claude Code, Cursor, etc.) via the standard MCP protocol. Servers do NOT communicate with each other directly -- the AI host orchestrates cross-server workflows by calling tools on each server sequentially and passing data through the shared filesystem.

```
+=========================================================================+
|                        AI HOST (Claude Code / Cursor / IDE)             |
|  The host maintains 3 MCP client instances, one per server.             |
|  Cross-server orchestration happens here -- the LLM reasons about       |
|  which server to call next and passes data via filesystem references.   |
+====+==================+==================+=============================+
     |                  |                  |
     | MCP Client 1     | MCP Client 2     | MCP Client 3
     | (stdio)          | (stdio)          | (stdio)
     |                  |                  |
+----v----+       +-----v-----+      +-----v------+
| BLENDER |       |   ASSET   |      |   UNITY    |
| GAMEDEV |       | PIPELINE  |      |  ENHANCED  |
| SERVER  |       |  SERVER   |      |   SERVER   |
+---------+       +-----------+      +------------+
| Python  |       | Python    |      | Node.js    |
| FastMCP |       | FastMCP   |      | TypeScript |
| ~8 tools|       | ~8 tools  |      | ~10 tools  |
+----+----+       +-----+-----+      +-----+------+
     |                  |                  |
     | TCP Socket       | HTTP/CLI         | WebSocket
     | (localhost:9876)  | (external APIs)  | (localhost:8090)
     |                  |                  |
+----v----+       +-----v-----+      +-----v------+
| BLENDER |       | AI APIs   |      | UNITY      |
| (bpy)   |       | Meshy     |      | EDITOR     |
| Addon   |       | Scenario  |      | C# Scripts |
| Plugin  |       | Local CLI |      | McpToolBase|
+---------+       +-----------+      +------------+

Shared Filesystem (project directory):
  Assets/           <-- Unity reads, asset pipeline writes, Blender exports to
  Assets/Art/       <-- Primary artifact exchange directory
  Assets/Resources/ <-- ScriptableObjects, configs
  *.blend           <-- Blender source files
  temp/pipeline/    <-- Intermediate processing artifacts
```

## Recommended Architecture

### Core Principle: Host-Orchestrated, Filesystem-Mediated

MCP servers are architecturally isolated by design. Per the MCP specification: "Servers should not be able to read the whole conversation, nor see into other servers." Cross-server communication is mediated by the AI host, which:

1. Calls Server A to produce an artifact (e.g., export FBX from Blender)
2. Receives the file path in the tool response
3. Passes that path to Server B as input (e.g., process textures in asset pipeline)
4. Passes the processed path to Server C (e.g., import into Unity)

This is not a limitation -- it is the correct pattern. The host has the context to make intelligent decisions about what to pass between servers, retry on failure, and adapt the workflow based on intermediate results.

**Confidence: HIGH** -- Verified against the [MCP Architecture Specification (2025-06-18)](https://modelcontextprotocol.io/specification/2025-06-18/architecture) which explicitly states each client maintains a 1:1 relationship with a server, and the host coordinates across clients.

### Component Boundaries

| Component | Responsibility | Communicates With | Technology |
|-----------|----------------|-------------------|------------|
| **blender-gamedev** | 3D modeling automation: scene creation, object manipulation, material setup, UV layout, rigging helpers, game-ready export | Blender via TCP socket to addon | Python + FastMCP + Blender bpy addon |
| **asset-pipeline** | Asset processing: AI texture generation, mesh optimization, format conversion, batch processing, validation | External APIs (Meshy, Scenario, etc.) + local CLI tools | Python + FastMCP + httpx/aiohttp |
| **unity-enhanced** | Unity Editor control: scene management, GameObject manipulation, component editing, prefab operations, build automation | Unity Editor via WebSocket to C# scripts | Node.js/TypeScript + MCP SDK + C# Editor scripts |
| **Shared Filesystem** | Artifact exchange: exported models, processed textures, import-ready assets | All three servers read/write | Project directory structure |

## Server 1: blender-gamedev

### Architecture: Three-Tier FastMCP + TCP Socket Bridge

```
AI Host
  |
  | stdio (MCP protocol)
  v
+---------------------------+
| blender-gamedev Server    |
| (Python / FastMCP)        |
|                           |
| @mcp.tool() decorators    |
| BlenderConnection class   |  <-- Singleton TCP client
| Tool implementations      |
+----------+----------------+
           |
           | TCP Socket (JSON protocol)
           | localhost:9876 (configurable)
           |
+----------v----------------+
| Blender Addon             |
| (bpy Python environment)  |
|                           |
| BlenderMCPServer class    |
| - TCP socket listener     |
| - Daemon thread for I/O   |
| - Command queue           |
| - bpy.app.timers bridge   |
|                           |
| Handler registry:         |
| - scene operations        |
| - object manipulation     |
| - material/shader ops     |
| - export operations       |
| - gamedev-specific ops    |
+---------------------------+
```

### Why This Architecture

The Blender bpy API is fundamentally thread-unsafe -- all bpy calls MUST execute on Blender's main thread. This forces a specific pattern:

1. FastMCP server runs as its own Python process (separate from Blender)
2. Communication happens over TCP socket to a Blender addon
3. The addon receives commands on a background thread
4. Commands are dispatched to the main thread via `bpy.app.timers.register(callback, first_interval=0.0)`
5. Results are captured in a closure and sent back over the socket

This is the same proven pattern used by [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp) (the most popular Blender MCP implementation) and [poly-mcp/Blender-MCP-Server](https://github.com/poly-mcp/Blender-MCP-Server).

**Confidence: HIGH** -- Verified against [Blender's official bpy.app.timers documentation](https://docs.blender.org/api/current/bpy.app.timers.html) and the [Blender developer forum thread on thread safety](https://devtalk.blender.org/t/thread-safety-with-bpy-api/16468).

### Socket Protocol

```
Command:  {"type": "create_game_object", "params": {"name": "Dragon", "mesh_type": "imported", "file": "dragon.fbx"}}
Response: {"status": "success", "result": {"object_name": "Dragon", "vertex_count": 12500, "bounds": [...]}}
Error:    {"status": "error", "message": "File not found: dragon.fbx"}
```

### Compound Action Tool Design (~8 tools, not 80)

Instead of exposing individual API calls as tools (which would create 80+ tools and severe token bloat), group operations by game development workflow intent:

| Tool | Action Parameter | Operations Covered |
|------|------------------|--------------------|
| `blender_scene` | `create`, `inspect`, `clear`, `configure` | Scene creation, inspection, clearing, render settings |
| `blender_object` | `create`, `modify`, `delete`, `duplicate`, `parent` | Object CRUD, transforms, hierarchy |
| `blender_material` | `create`, `assign`, `modify`, `setup_pbr` | Material creation, PBR setup, texture assignment |
| `blender_mesh` | `edit`, `optimize`, `unwrap_uv`, `decimate` | Mesh editing, UV mapping, LOD generation |
| `blender_rig` | `create_armature`, `auto_weight`, `add_constraint` | Rigging, weight painting, IK setup |
| `blender_export` | `fbx`, `gltf`, `obj` | Game-ready export with per-format presets |
| `blender_viewport` | `screenshot`, `navigate`, `set_shading` | Viewport capture and navigation |
| `blender_execute` | (code string) | Escape hatch: run arbitrary bpy Python |

This compound action pattern (using an `action` parameter to multiplex operations within a single tool) follows the design used by [CoderGamester/mcp-unity](https://github.com/CoderGamester/mcp-unity) which consolidates 80+ operations into ~33 tools using action parameters. The rationale from [Anthropic's engineering blog on code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) confirms that reducing tool count is critical: each tool definition costs 200+ tokens in context, so 26 tools across 3 servers costs ~5,200 tokens vs 200+ tools costing ~40,000+ tokens.

**Confidence: HIGH** -- Token reduction validated by [SEP-1576](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1576) and [Speakeasy's 100x reduction case study](https://www.speakeasy.com/blog/how-we-reduced-token-usage-by-100x-dynamic-toolsets-v2).

## Server 2: asset-pipeline

### Architecture: FastMCP + External API Orchestration

```
AI Host
  |
  | stdio (MCP protocol)
  v
+---------------------------+
| asset-pipeline Server     |
| (Python / FastMCP)        |
|                           |
| @mcp.tool() decorators    |
| API client classes        |
| Local tool wrappers       |
| File I/O utilities        |
+----------+----------------+
           |
           | HTTP / CLI subprocess
           |
     +-----+-----+-----+
     |     |     |     |
     v     v     v     v
  Meshy  Scenario Local  Custom
  API    API     Tools  Scripts
  (3D)   (Tex)  (CLI)  (Python)
```

### Why This Architecture

The asset pipeline server is the simplest architecturally -- it is a pure FastMCP server with no bridge layer needed. It wraps external APIs and local CLI tools behind MCP tool interfaces. Unlike the Blender and Unity servers, there is no application-side addon or bridge; the server directly calls APIs and manipulates files.

The key design decision: all tool outputs are files written to the shared filesystem. Tool responses return file paths, not file contents. This keeps token usage minimal and enables the host to pass paths to other servers.

### Compound Action Tool Design (~8 tools)

| Tool | Action Parameter | Operations Covered |
|------|------------------|--------------------|
| `pipeline_generate_3d` | `from_text`, `from_image`, `check_status`, `download` | AI 3D model generation (Meshy, Tripo, etc.) |
| `pipeline_generate_texture` | `from_text`, `from_image`, `tile`, `pbr_maps` | AI texture generation (Scenario, etc.) |
| `pipeline_optimize_mesh` | `decimate`, `retopology`, `lod_chain`, `validate` | Mesh optimization and LOD generation |
| `pipeline_convert` | `fbx_to_gltf`, `gltf_to_fbx`, `obj_to_fbx`, `resize_textures` | Format conversion and texture resizing |
| `pipeline_validate` | `check_mesh`, `check_textures`, `check_materials`, `full_audit` | Asset validation and quality checks |
| `pipeline_batch` | `process_folder`, `bulk_convert`, `bulk_optimize` | Batch processing operations |
| `pipeline_import_asset` | `from_url`, `from_sketchfab`, `from_polyhaven` | Asset sourcing from marketplaces |
| `pipeline_status` | `list_jobs`, `check_job`, `cancel_job` | Async job tracking for long-running API calls |

### Async Job Pattern

AI generation APIs (Meshy, Tripo, Hunyuan3D) are asynchronous -- you submit a request, get a job ID, and poll for completion. The server should:

1. Submit the generation request, return a job ID immediately
2. The host can call `pipeline_status` to poll
3. When complete, call `pipeline_generate_3d` with action `download` and the job ID
4. The server downloads the result to the shared filesystem and returns the path

This avoids long-running tool calls that time out the MCP connection.

## Server 3: unity-enhanced

### Architecture: Node.js MCP Gateway + C# WebSocket Bridge

```
AI Host
  |
  | stdio (MCP protocol)
  v
+---------------------------+
| unity-enhanced Server     |
| (Node.js / TypeScript)    |
|                           |
| MCP SDK tool handlers     |
| Zod schema validation     |
| WebSocket client          |
+----------+----------------+
           |
           | WebSocket (JSON-RPC)
           | ws://localhost:8090 (configurable)
           |
+----------v----------------+
| Unity Editor Scripts      |
| (C# / Editor assembly)    |
|                           |
| McpWebSocketServer        |  <-- Listens for connections
| McpToolBase subclasses    |  <-- Tool implementations
| McpResourceBase subclasses|  <-- Resource providers
|                           |
| Tool categories:          |
| - Scene management        |
| - GameObject CRUD         |
| - Component manipulation  |
| - Asset database ops      |
| - Prefab operations       |
| - Build & test            |
+---------------------------+
```

### Why This Architecture

Unity's editor scripting API (UnityEditor namespace) runs in a C# environment inside the Unity Editor process. Unlike Blender, Unity cannot directly run a Python MCP server. The established pattern (used by [CoderGamester/mcp-unity](https://github.com/CoderGamester/mcp-unity), [mitchchristow/unity-mcp](https://github.com/mitchchristow/unity-mcp), and [CoplayDev/unity-mcp](https://github.com/CoplayDev/unity-mcp)) is:

1. C# Editor scripts create a WebSocket server inside Unity
2. A Node.js process runs the MCP server (using the official TypeScript MCP SDK)
3. The Node.js server connects to Unity's WebSocket as a client
4. MCP tool calls are translated to WebSocket messages, forwarded to Unity, executed, and results returned

Node.js is the bridge because the official MCP SDK has first-class TypeScript support, stdio transport is trivial in Node.js, and the WebSocket client library ecosystem is mature.

**Confidence: HIGH** -- This is the dominant pattern across all major Unity MCP implementations in 2025-2026.

### Why "Enhanced" (Not a Fork)

The existing mcp-unity implementations are general-purpose editor control. This server should be **game-development-enhanced** with:

- VeilBreakers-specific tools (ScriptableObject editing, brand/path data, combat testing)
- Game asset import with automatic URP material setup
- Prefab creation from imported models with colliders and LOD groups
- Play mode control for testing game flows
- Console log filtering by VeilBreakers subsystem prefixes

### Compound Action Tool Design (~10 tools)

| Tool | Action Parameter | Operations Covered |
|------|------------------|--------------------|
| `unity_scene` | `create`, `load`, `save`, `get_hierarchy`, `get_info` | Scene lifecycle and inspection |
| `unity_gameobject` | `create`, `delete`, `find`, `duplicate`, `set_transform`, `set_parent` | GameObject CRUD and hierarchy |
| `unity_component` | `add`, `remove`, `update`, `get_fields` | Component manipulation |
| `unity_asset` | `import`, `find`, `refresh`, `get_info` | Asset database operations |
| `unity_prefab` | `create`, `instantiate`, `apply_overrides`, `unpack` | Prefab workflow |
| `unity_material` | `create`, `assign`, `set_property`, `setup_urp` | Material and shader setup |
| `unity_build` | `compile`, `run_tests`, `execute_menu_item` | Build and test automation |
| `unity_console` | `get_logs`, `clear`, `filter` | Console log access |
| `unity_selection` | `select`, `get_selected`, `focus` | Editor selection and focus |
| `unity_play` | `enter`, `exit`, `pause`, `step` | Play mode control |

### Extensibility Pattern

Following mcp-unity's pattern, custom tools inherit from `McpToolBase`:

```csharp
// C# side: Unity Editor
public class CreateMonsterTool : McpToolBase
{
    public override string Name => "unity_create_monster";

    public override async Task<McpToolResult> Execute(JObject parameters)
    {
        string monsterId = parameters["monster_id"].Value<string>();
        // Create ScriptableObject, set up prefab, etc.
        return McpToolResult.Success(new { prefab_path = path });
    }
}
```

```typescript
// TypeScript side: Node.js MCP server
server.tool("unity_create_monster", {
    monster_id: z.string(),
    brand: z.enum(["IRON", "SAVAGE", "SURGE", ...]),
}, async (params) => {
    return await unityBridge.execute("unity_create_monster", params);
});
```

## Data Flow

### Primary Pipeline: Blender to Unity

```
1. AUTHOR IN BLENDER
   Host calls: blender_object(action="create", ...)
   Host calls: blender_material(action="setup_pbr", ...)
   Host calls: blender_mesh(action="optimize", target_tris=5000)
   Host calls: blender_export(action="fbx", path="Assets/Art/Models/dragon.fbx")
   Returns:    {"status": "success", "path": "Assets/Art/Models/dragon.fbx", "stats": {...}}

2. PROCESS IN PIPELINE (optional)
   Host calls: pipeline_optimize_mesh(action="lod_chain", input="Assets/Art/Models/dragon.fbx", levels=[1.0, 0.5, 0.25])
   Returns:    {"status": "success", "outputs": ["dragon_LOD0.fbx", "dragon_LOD1.fbx", "dragon_LOD2.fbx"]}

   Host calls: pipeline_generate_texture(action="pbr_maps", input="dragon_albedo.png")
   Returns:    {"status": "success", "outputs": {"normal": "...", "roughness": "...", "metallic": "..."}}

3. IMPORT TO UNITY
   Host calls: unity_asset(action="refresh")  -- triggers AssetDatabase.Refresh()
   Host calls: unity_asset(action="import", path="Assets/Art/Models/dragon.fbx", settings={...})
   Host calls: unity_prefab(action="create", source="Assets/Art/Models/dragon.fbx", add_collider=true, setup_lod=true)
   Host calls: unity_material(action="setup_urp", prefab="Assets/Prefabs/Dragon.prefab")
   Returns:    {"status": "success", "prefab": "Assets/Prefabs/Dragon.prefab"}
```

### Secondary Flow: AI-Generated Assets

```
1. GENERATE
   Host calls: pipeline_generate_3d(action="from_text", prompt="low-poly dragon monster", style="stylized")
   Returns:    {"job_id": "abc123", "status": "processing", "eta_seconds": 120}

2. POLL & DOWNLOAD
   Host calls: pipeline_status(action="check_job", job_id="abc123")
   Returns:    {"status": "complete", "download_url": "https://..."}

   Host calls: pipeline_generate_3d(action="download", job_id="abc123", output="Assets/Art/Models/dragon_gen.glb")
   Returns:    {"status": "success", "path": "Assets/Art/Models/dragon_gen.glb"}

3. PROCESS & IMPORT (same as primary flow steps 2-3)
```

### Tertiary Flow: Texture-Only Pipeline

```
1. Host calls: pipeline_generate_texture(action="from_text", prompt="dark crystal scales", size=1024, tileable=true)
   Returns:    {"path": "Assets/Art/Textures/crystal_scales.png"}

2. Host calls: unity_asset(action="refresh")
3. Host calls: unity_material(action="create", shader="Universal Render Pipeline/Lit", textures={"_BaseMap": "Assets/Art/Textures/crystal_scales.png"})
   Returns:    {"material_path": "Assets/Art/Materials/CrystalScales.mat"}
```

### Data Sources

| Data | Source | Format | Access Pattern |
|------|--------|--------|----------------|
| 3D models (authored) | Blender via blender-gamedev | FBX/glTF export to filesystem | blender_export tool writes to Assets/Art/Models/ |
| 3D models (generated) | AI APIs via asset-pipeline | glTF/GLB download to filesystem | pipeline_generate_3d downloads to Assets/Art/Models/ |
| Textures (generated) | AI APIs via asset-pipeline | PNG/EXR to filesystem | pipeline_generate_texture writes to Assets/Art/Textures/ |
| Processed assets | Local tools via asset-pipeline | Various formats to filesystem | pipeline_optimize_mesh, pipeline_convert write to filesystem |
| Unity scenes/prefabs | Unity Editor via unity-enhanced | Unity native formats | unity_scene, unity_prefab tools operate in-editor |
| ScriptableObjects | Unity Editor via unity-enhanced | .asset files | unity_component tool edits serialized fields |
| Build artifacts | Unity Editor via unity-enhanced | .exe, logs | unity_build tool triggers compilation |

## Patterns to Follow

### Pattern 1: Compound Action Tools

**What:** Each MCP tool covers a domain (e.g., "objects", "materials") and accepts an `action` parameter to select the specific operation. Parameters vary by action.

**When:** Always. This is the primary tool design pattern for the entire toolkit.

**Why:** Token efficiency. Each tool definition costs ~200 tokens in the LLM context window. 26 compound tools across 3 servers = ~5,200 tokens. 200 atomic tools = ~40,000 tokens. The LLM is also better at selecting from a small tool set.

**Example:**
```python
@mcp.tool()
async def blender_object(
    action: Literal["create", "modify", "delete", "duplicate", "parent"],
    name: str = None,
    mesh_type: str = None,
    position: list[float] = None,
    rotation: list[float] = None,
    scale: list[float] = None,
    parent: str = None,
    target: str = None,
) -> dict:
    """Manage Blender objects. Actions: create, modify, delete, duplicate, parent."""
    if action == "create":
        return await blender.send_command("create_object", {"name": name, "mesh_type": mesh_type, ...})
    elif action == "modify":
        return await blender.send_command("modify_object", {"name": name, "position": position, ...})
    # ...
```

**Confidence: HIGH** -- Pattern validated by mcp-unity (33 tools covering 80+ operations) and Anthropic's token efficiency guidance.

### Pattern 2: Filesystem as Integration Bus

**What:** Servers exchange data through the shared project filesystem. Tool responses contain file paths, not file contents. The AI host reads paths from one tool's response and passes them as inputs to the next tool.

**When:** Any cross-server data flow. Blender exports to a path, asset pipeline reads from that path and writes to another, Unity imports from the final path.

**Why:** MCP servers are isolated by design. No direct inter-server communication exists in the protocol. The filesystem is the natural shared resource for game development artifacts (models, textures, configs). File paths are tiny compared to file contents, preserving token budget.

**Example flow:**
```
blender_export(format="fbx", path="Assets/Art/Models/dragon.fbx")
  -> returns {"path": "Assets/Art/Models/dragon.fbx"}

pipeline_optimize_mesh(input="Assets/Art/Models/dragon.fbx", action="decimate", target_ratio=0.5)
  -> returns {"path": "Assets/Art/Models/dragon_optimized.fbx"}

unity_asset(action="import", path="Assets/Art/Models/dragon_optimized.fbx")
  -> returns {"imported": true, "asset_guid": "abc123"}
```

**Confidence: HIGH** -- This follows the MCP specification's isolation principle and mirrors the [Remote MCP Adapter's artifact:// pattern](https://github.com/aakashh242/remote-mcp-adapter).

### Pattern 3: Timer-Bridged Main Thread Execution (Blender)

**What:** Socket commands received on a background thread are dispatched to Blender's main thread via `bpy.app.timers.register(callback, first_interval=0.0)`. The background thread blocks on an Event/condition until the main thread callback completes and stores the result in a shared container.

**When:** Every Blender bpy API call. No exceptions.

**Why:** bpy is not thread-safe. Calling bpy from any thread other than the main thread causes crashes, data corruption, or silent failures. The timer mechanism is Blender's official way to schedule work on the main thread.

**Confidence: HIGH** -- Verified against [Blender Developer Forum](https://devtalk.blender.org/t/thread-safety-with-bpy-api/16468) and [official bpy.app.timers docs](https://docs.blender.org/api/current/bpy.app.timers.html).

### Pattern 4: WebSocket JSON-RPC Bridge (Unity)

**What:** The Node.js MCP server acts as a WebSocket client connecting to a WebSocket server running inside Unity Editor (C# `McpWebSocketServer`). Messages use a JSON-RPC-like format with method name, parameters, and correlation IDs.

**When:** Every Unity Editor operation.

**Why:** Unity's scripting runs in C#. The MCP SDK is TypeScript/Python. A WebSocket bridge connects the two process spaces. The C# side runs in the Editor process with full access to UnityEditor APIs. The Node.js side handles MCP protocol details.

**Message format:**
```json
// Request (Node.js -> Unity)
{"id": "req-001", "method": "unity_gameobject", "params": {"action": "create", "name": "Dragon", "position": [0, 0, 0]}}

// Response (Unity -> Node.js)
{"id": "req-001", "status": "success", "result": {"instance_id": 12345, "path": "/Dragon"}}
```

**Confidence: HIGH** -- This is the exact pattern used by all three major Unity MCP implementations: [CoderGamester/mcp-unity](https://github.com/CoderGamester/mcp-unity), [mitchchristow/unity-mcp](https://github.com/mitchchristow/unity-mcp), [CoplayDev/unity-mcp](https://github.com/CoplayDev/unity-mcp).

### Pattern 5: Async Job Tracking for Long-Running Operations

**What:** For operations that take longer than a few seconds (AI generation, large exports, build compilation), return a job ID immediately. Provide a separate polling tool for status checks. Provide a download/retrieve action for completed jobs.

**When:** AI model generation (30s-5min), AI texture generation (10s-60s), Unity builds (30s+), large Blender exports (10s+).

**Why:** MCP tool calls have implicit timeouts. Long-running synchronous calls risk timeout failures. The async pattern lets the host decide when to poll and handles retries naturally.

**Confidence: MEDIUM** -- Standard async API pattern. Not MCP-specific, but critical for game dev tools where operations are inherently slow.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Direct Server-to-Server Communication

**What people do:** Try to make the asset pipeline server call the Blender server directly, or have Unity call the asset pipeline.

**Why it is wrong:** MCP servers are isolated by design. There is no standard mechanism for server-to-server communication. Building custom bridges between servers creates a brittle dependency graph, bypasses the host's security model, and makes servers untestable in isolation.

**Do this instead:** Let the AI host orchestrate. The host calls Server A, gets a result, and passes relevant data to Server B. The host has the context to make intelligent routing decisions.

### Anti-Pattern 2: One Mega-Server with 200 Tools

**What people do:** Put all Blender, asset pipeline, and Unity tools into a single MCP server to "simplify" configuration.

**Why it is wrong:** Token bloat is the primary cost. Every tool definition loads into the LLM context even if only a few are used. 200 tools at ~200 tokens each = 40,000 tokens wasted. Additionally, a Python server cannot directly call C# Unity APIs -- the language boundary forces separation.

**Do this instead:** Three focused servers with ~8-10 compound tools each. Total tool definitions in context: ~26 tools at ~200 tokens = ~5,200 tokens. The LLM can hold all tool definitions comfortably and select accurately.

### Anti-Pattern 3: Returning File Contents in Tool Responses

**What people do:** Read an entire FBX file or texture and return it as base64 in the tool response.

**Why it is wrong:** A single 3D model can be 5-50MB. Even a texture is 1-10MB. Returning file contents in tool responses wastes enormous amounts of tokens and provides no value -- the LLM cannot meaningfully process binary data.

**Do this instead:** Return file paths. The filesystem is the data bus. Return metadata (vertex count, file size, format) for the LLM to reason about.

### Anti-Pattern 4: Calling bpy from Background Threads

**What people do:** Execute Blender commands directly in the socket handler thread.

**Why it is wrong:** Blender's Python API is not thread-safe. Calling bpy from a non-main thread causes crashes, corrupted scene state, or silently wrong results. This is documented officially and confirmed by community experience.

**Do this instead:** Always use `bpy.app.timers.register()` to schedule execution on the main thread. Block the handler thread until execution completes.

### Anti-Pattern 5: Synchronous Long-Running Tool Calls

**What people do:** Make an AI generation API call and block the tool for 2 minutes waiting for completion.

**Why it is wrong:** MCP tool calls can time out. The host cannot display progress. The user cannot cancel. If the connection drops, the job is lost.

**Do this instead:** Return a job ID immediately. Provide polling and download actions. Let the host manage the wait, show progress to the user, and retry if needed.

## Transport Decisions

### All Three Servers: stdio Transport

**Recommendation:** Use stdio transport for all three servers. The AI host spawns each server as a child process and communicates over stdin/stdout.

**Rationale:**
- All servers run on the same machine as the AI host (local game development)
- stdio eliminates network overhead (microsecond latency vs millisecond)
- No port management, firewall issues, or CORS configuration
- Simpler deployment: just a command in the MCP config file
- This is the recommended transport for local tools per the [MCP specification](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)

**The internal bridges** (Blender TCP socket on 9876, Unity WebSocket on 8090) are separate from the MCP transport. The MCP protocol runs over stdio between host and server. The application bridges run over sockets between the server processes and their respective applications.

**Confidence: HIGH** -- stdio is explicitly recommended for local servers by the MCP specification. SSE is deprecated. Streamable HTTP is for remote/cloud deployment.

## Scalability Considerations

| Concern | Single Developer | Small Team (2-5) | Studio (10+) |
|---------|-----------------|-------------------|---------------|
| Server deployment | Local stdio, spawned by host | Local stdio per developer | Consider shared asset-pipeline server via Streamable HTTP |
| Asset storage | Local project directory | Git LFS for shared assets | Dedicated asset server, pipeline writes to shared NAS |
| API keys | Local .env per developer | Shared .env or secrets manager | Centralized secrets management |
| Blender instances | One per developer | One per developer | Could pool Blender instances for batch processing |
| Unity instances | One per developer | One per developer | One per developer (Editor is inherently single-user) |
| Configuration | Per-project .mcp.json | Per-project .mcp.json in repo | Per-project + team overrides |

## Build Order Implications

Based on dependency analysis and complexity, servers should be built in this order:

### Phase 1: blender-gamedev Server (Foundation)

**Build first because:**
- It produces the artifacts that flow downstream
- The Blender TCP bridge pattern is well-documented with reference implementations
- FastMCP + Python is the simplest server implementation
- Can be tested independently with any MCP host -- no Unity dependency
- The Blender addon pattern is proven (ahujasid/blender-mcp has 5k+ stars)

**Dependencies:** None. Standalone.

**Validates:** TCP socket bridge pattern, compound action tool design, FastMCP project structure, Blender addon architecture.

### Phase 2: asset-pipeline Server (Processing Layer)

**Build second because:**
- It depends on file outputs from blender-gamedev (or can be tested with sample files)
- Pure Python FastMCP -- no bridge layer needed, simplest architecture
- Can wrap APIs incrementally (start with one, add more)
- Validates the filesystem-as-integration-bus pattern with real files from Phase 1

**Dependencies:** Filesystem paths from Phase 1 (or mock files for testing).

**Validates:** Async job pattern, API wrapper design, batch processing, cross-server file passing.

### Phase 3: unity-enhanced Server (Consumption Layer)

**Build third because:**
- It is the most architecturally complex (three languages: TypeScript + C# + JSON protocol)
- It consumes outputs from Phases 1 and 2
- The WebSocket bridge between Node.js and C# requires careful error handling
- Existing mcp-unity implementations provide reference code to build from
- Building this last means the upstream servers are stable and produce real assets to test with

**Dependencies:** Filesystem artifacts from Phases 1-2 for integration testing. Unity Editor running.

**Validates:** WebSocket bridge, C# Editor tool extensibility, full pipeline integration.

### Phase 4: Integration & Orchestration (End-to-End)

**Build last because:**
- Requires all three servers operational
- Focus on the host-side experience: workflow prompts, error recovery, progress reporting
- Build example workflows that chain all three servers
- Write MCP prompt templates for common game dev workflows

**Dependencies:** All three servers operational.

**Validates:** Full Blender-to-Unity pipeline, cross-server orchestration, real game development workflows.

## Integration Points

### MCP Configuration (.mcp.json)

```json
{
  "mcpServers": {
    "blender-gamedev": {
      "command": "uvx",
      "args": ["blender-gamedev-mcp"],
      "env": {
        "BLENDER_PORT": "9876",
        "BLENDER_HOST": "localhost"
      }
    },
    "asset-pipeline": {
      "command": "uvx",
      "args": ["asset-pipeline-mcp"],
      "env": {
        "MESHY_API_KEY": "${MESHY_API_KEY}",
        "SCENARIO_API_KEY": "${SCENARIO_API_KEY}",
        "ASSET_OUTPUT_DIR": "./Assets/Art"
      }
    },
    "unity-enhanced": {
      "command": "npx",
      "args": ["-y", "unity-enhanced-mcp"],
      "env": {
        "UNITY_WS_PORT": "8090"
      }
    }
  }
}
```

### Artifact Exchange Directory Structure

```
project-root/
  Assets/
    Art/
      Models/          <-- Blender exports here, pipeline processes here, Unity imports here
        Raw/           <-- Unprocessed exports from Blender
        Processed/     <-- Pipeline-optimized assets
      Textures/
        Generated/     <-- AI-generated textures from pipeline
        Processed/     <-- Resized/converted textures
      Materials/       <-- Unity materials referencing processed textures
    Prefabs/           <-- Unity prefabs created from imported models
    Resources/         <-- ScriptableObjects (monster data, hero configs, etc.)
  temp/
    pipeline/          <-- Intermediate processing artifacts (not committed to git)
    jobs/              <-- Async job tracking files
```

### Error Propagation

Each tier has its own error domain:

| Server | Error Source | Propagation |
|--------|-------------|-------------|
| blender-gamedev | Blender crashes, bpy exceptions, socket timeout | Caught in addon handler, returned as `{"status": "error", "message": "..."}`, FastMCP returns error to host |
| asset-pipeline | API rate limits, network errors, invalid input | Caught in tool function, returned as MCP tool error with retry guidance |
| unity-enhanced | Unity compilation errors, missing references, WebSocket disconnect | C# catches in McpToolBase, returns error JSON, Node.js propagates to host |
| Cross-server | File not found, wrong format, corrupted asset | Host detects error in tool response, can retry or try alternative approach |

## Sources

- [MCP Architecture Specification (2025-06-18)](https://modelcontextprotocol.io/specification/2025-06-18/architecture) -- HIGH confidence (official spec)
- [MCP Transport Specification](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports) -- HIGH confidence (official spec)
- [Anthropic: Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) -- HIGH confidence (official engineering blog)
- [FastMCP Server Composition](https://gofastmcp.com/servers/composition) -- HIGH confidence (official FastMCP docs)
- [CoderGamester/mcp-unity](https://github.com/CoderGamester/mcp-unity) -- HIGH confidence (reference implementation, MIT license)
- [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp) -- HIGH confidence (reference implementation)
- [ahujasid/blender-mcp DeepWiki](https://deepwiki.com/ahujasid/blender-mcp) -- HIGH confidence (architecture analysis)
- [Blender bpy.app.timers](https://docs.blender.org/api/current/bpy.app.timers.html) -- HIGH confidence (official Blender docs)
- [Blender Thread Safety Forum](https://devtalk.blender.org/t/thread-safety-with-bpy-api/16468) -- MEDIUM confidence (developer forum)
- [SEP-1576: Token Bloat Mitigation](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1576) -- HIGH confidence (official standards proposal)
- [Speakeasy: 100x Token Reduction](https://www.speakeasy.com/blog/how-we-reduced-token-usage-by-100x-dynamic-toolsets-v2) -- MEDIUM confidence (vendor case study)
- [KlavisAI: 4 MCP Design Patterns](https://www.klavis.ai/blog/less-is-more-mcp-design-patterns-for-ai-agents) -- MEDIUM confidence (industry analysis)
- [poly-mcp/Blender-MCP-Server](https://github.com/poly-mcp/Blender-MCP-Server) -- MEDIUM confidence (alternative implementation)
- [mitchchristow/unity-mcp](https://github.com/mitchchristow/unity-mcp) -- MEDIUM confidence (alternative implementation with 80 tools)
- [IBM: MCP Architecture Patterns](https://developer.ibm.com/articles/mcp-architecture-patterns-ai-systems/) -- MEDIUM confidence (vendor analysis)
- [Arcade.dev: 54 MCP Tool Patterns](https://arcade.dev/blog/mcp-tool-patterns) -- MEDIUM confidence (industry analysis)

---
*Architecture research for: Multi-MCP-Server Game Development Toolkit*
*Researched: 2026-03-18*
