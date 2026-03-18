# Technology Stack: AI Game Development MCP Toolkit

**Project:** VeilBreakers 3D - Custom MCP Server Toolkit (Blender + Unity + AI Generation APIs)
**Researched:** 2026-03-18
**Overall Confidence:** HIGH (verified against official PyPI, MCP spec, GitHub repos, and vendor docs)

## Context

This stack research covers building custom MCP servers that bridge three domains into a unified AI-assisted game development toolkit:

1. **Blender** (Python bpy API) -- 3D modeling, materials, scene composition
2. **Unity** (C# Editor scripting) -- game engine integration, asset import, scene management
3. **AI Generation APIs** (REST/Python SDK) -- image generation, 3D model generation, texture synthesis

The project already uses `blender-mcp` (ahujasid) and `mcp-unity` (CoderGamester) as reference implementations. This research informs building custom MCP servers that extend beyond their capabilities, specifically for VeilBreakers' monster/hero asset pipeline.

---

## Recommended Stack

### MCP Server Framework (Python)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Python | 3.12 | Runtime for all custom MCP servers | 3.12 is the sweet spot: fully supported by MCP SDK (>=3.10), supported by Blender 4.x bpy, and has the best performance of the 3.10-3.12 range. Avoid 3.13 for now -- Blender addon compatibility is unverified. | HIGH |
| mcp (official SDK) | 1.26.0 | MCP protocol implementation, transport, lifecycle | The official Python SDK from Anthropic. Includes FastMCP high-level decorator API (`@mcp.tool()`, `@mcp.resource()`), stdio and Streamable HTTP transports, JSON-RPC message handling, and OAuth support. This IS the protocol implementation -- no alternatives exist. | HIGH |
| FastMCP (standalone) | 3.1.1 | Higher-level MCP server framework | FastMCP was originally integrated into the MCP SDK as the `@mcp.tool()` decorator API. The standalone FastMCP 3.x adds composition, proxying, and middleware beyond the built-in SDK FastMCP. Use the built-in SDK FastMCP for simple servers; reach for standalone FastMCP 3.x only if you need server composition (chaining multiple MCP servers). Start with the SDK's built-in FastMCP. | MEDIUM |
| uv | latest | Python package management and virtual environments | The MCP Python SDK officially uses uv. 10-100x faster than pip for dependency resolution. Use `uv init`, `uv add`, `uv sync` for all project setup. Lock files (`uv.lock`) go into version control. This is not optional -- the MCP ecosystem standardized on uv. | HIGH |

**Why Python over TypeScript for custom servers:** The primary integration targets are Blender (Python-only bpy API) and AI generation APIs (Python SDKs are first-class for fal.ai, Replicate, Stability AI, OpenAI). TypeScript SDK exists and is used by mcp-unity's Node.js bridge, but writing Blender integration in TypeScript would require a Python subprocess bridge anyway. Python is the single language that touches all three domains natively.

**Why NOT TypeScript:** The TypeScript MCP SDK v2 is still in pre-alpha (stable v2 anticipated Q1 2026 but not yet released). The v1.x is stable but Python is the better fit for this specific toolkit given Blender's Python API and the AI SDK ecosystem.

### Communication & Transport

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| stdio transport | MCP spec 2025-03-26 | Primary transport for Claude Code / Cursor integration | stdio is the simplest, lowest-latency transport. Claude Code, Cursor, and Codex all launch MCP servers as subprocesses communicating over stdin/stdout. No network stack overhead. Microsecond-level response times. Use this for all local development servers. | HIGH |
| TCP sockets (JSON-RPC) | Python `asyncio` stdlib | Communication between MCP server and Blender addon | Proven pattern from ahujasid/blender-mcp: Blender runs a socket server on localhost:9876, MCP server connects as a client, sends JSON commands, receives JSON responses. Keep this exact pattern -- it works and Blender's Python environment cannot run an MCP server directly (GIL + bpy threading constraints). | HIGH |
| WebSocket (JSON-RPC) | websockets 14.x | Communication between MCP server and Unity Editor | Proven pattern from CoderGamester/mcp-unity: Unity runs a WebSocket server on port 8090, Node.js MCP server connects as client. For a Python MCP server talking to Unity, use the `websockets` library instead of Node.js. Same protocol, different client language. | HIGH |
| Streamable HTTP | MCP spec 2025-03-26 | Future: remote/multi-user MCP server deployment | Only needed if you want to deploy MCP servers as remote services (e.g., team-shared AI generation endpoint). Not needed for local single-developer workflow. Defer implementation until there is a real multi-user requirement. | LOW (defer) |

**Architecture pattern:**

```
Claude Code / Cursor (MCP Client)
       |
       | stdio (JSON-RPC over stdin/stdout)
       |
  [Python MCP Server]  <-- Your custom code lives here
       |          |
       |          +-- TCP socket (JSON) --> [Blender Addon] (bpy API)
       |          |                          localhost:9876
       |          +-- WebSocket (JSON) ---> [Unity Editor] (C# McpUnityServer)
       |          |                          localhost:8090
       |          +-- HTTPS REST ---------> [AI Generation APIs]
       |                                    fal.ai / Replicate / OpenAI / ComfyUI
```

### HTTP Client & Async Runtime

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| httpx | >=0.27.1 | HTTP client for AI API calls | Already a core dependency of the MCP SDK -- do not add a second HTTP library. httpx supports both sync and async, HTTP/1.1 and HTTP/2, and is the MCP team's choice. Use `httpx.AsyncClient` for all outbound API calls. | HIGH |
| anyio | >=4.5 | Async I/O abstraction | Already a core dependency of the MCP SDK. Provides structured concurrency (`anyio.create_task_group`) that works with both asyncio and trio. Use anyio primitives instead of raw asyncio for compatibility with the MCP runtime. | HIGH |
| websockets | 14.x | WebSocket client for Unity bridge | Lightweight, well-maintained, async-native WebSocket library. Used for connecting to Unity's WebSocket server. Do NOT use aiohttp for this -- websockets is purpose-built and simpler. | HIGH |

**Why NOT aiohttp:** aiohttp is async-only and optimized for high-concurrency server workloads. For an MCP server making a handful of concurrent API calls, httpx (already bundled) is sufficient. Adding aiohttp would be a redundant dependency.

**Why NOT requests:** Synchronous-only. The MCP server runtime is async (anyio). Using `requests` would block the event loop. httpx is the async-capable equivalent and is already installed.

### AI Generation APIs

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| fal-client | 0.13.x | Image generation (Stable Diffusion, Flux), 3D model generation (Hunyuan3D v3, Trellis) | fal.ai is the best unified platform for game asset generation in 2026. Single SDK covers both 2D (SDXL, Flux, SD3.5) and 3D (Hunyuan3D v3 with PBR materials, Trellis). Async-native with `subscribe_async`. Pay-per-use, no GPU required locally. Hunyuan3D v3 outputs glTF with PBR textures directly. | HIGH |
| replicate | latest | Fallback/alternative for 3D generation (TripoSR, Hunyuan3D 2) | Replicate hosts the same models as fal.ai but with broader selection. Use as fallback when fal.ai models are unavailable or for models not yet on fal.ai. Python SDK is well-maintained. TripoSR on Replicate is $0.07/generation. | MEDIUM |
| openai | latest | GPT Image (gpt-image-1, gpt-image-1.5) for concept art, reference sheets | OpenAI's GPT Image models replaced DALL-E (deprecated May 2026). Best for high-fidelity concept art, character reference sheets, and UI art. NOT for textures (use Stable Diffusion for that). Use for creative direction and reference image generation. | HIGH |
| Direct REST (via httpx) | N/A | ComfyUI local server API, Stability AI API, any future API | For APIs without a Python SDK or when you want to avoid SDK dependency bloat, use httpx directly with the REST endpoint. ComfyUI exposes a JSON workflow API on localhost -- call it directly rather than adding a ComfyUI Python SDK. | HIGH |

**AI API Strategy:**

| Use Case | Recommended API | Model | Output Format |
|----------|----------------|-------|---------------|
| Monster concept art | OpenAI GPT Image | gpt-image-1.5 | PNG |
| Texture generation (diffuse, normal) | fal.ai | SD3.5 or Flux | PNG |
| Seamless tileable textures | ComfyUI (local) | SD3.5 + ControlNet Tile | PNG |
| 3D monster model (hero quality) | fal.ai | Hunyuan3D v3 | glTF/GLB with PBR |
| 3D prop model (fast iteration) | fal.ai | Trellis | glTF/GLB |
| 3D character (clean topology for rigging) | Tripo3D API | Tripo v3.0 | glTF with quad topology |
| Multi-view reference sheets | OpenAI GPT Image | gpt-image-1 | PNG |

**Why NOT run Stable Diffusion locally:** Running SD locally requires a dedicated GPU, VRAM management, model downloads, and CUDA setup. For a development toolkit, cloud APIs are faster to integrate, always have the latest models, and cost cents per generation. ComfyUI local is the exception -- use it when you need custom pipelines (e.g., ControlNet-guided texture generation) that cloud APIs don't support.

### Image Processing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Pillow | 12.1.x | Image format conversion, texture atlas composition, DDS read/write, resizing, channel manipulation | The standard Python image library. Pillow 12.x reads/writes DDS (DirectX textures), PNG, JPEG, TGA, BMP, EXR (with OpenEXR), and more. Use for: AI output post-processing, texture atlas packing, normal map channel manipulation, format conversion for Unity import. | HIGH |
| numpy | >=1.26 | Pixel-level image manipulation, normal map computation, batch operations | Already a transitive dependency (via Pillow and trimesh). Use for fast pixel operations: normal map generation from height maps, channel splitting/merging, batch color corrections. Avoid Pillow's per-pixel loops -- use numpy arrays. | HIGH |

**Why NOT OpenCV (cv2):** OpenCV is massive (100+ MB), mostly for computer vision tasks (object detection, camera calibration). For game texture processing, Pillow + numpy covers 95% of needs. The remaining 5% (edge detection for normal maps) can use scipy.ndimage which is much lighter. Do not add cv2 unless you need actual computer vision features.

**Why NOT sharp (Node.js):** sharp is excellent but is a Node.js library. All MCP servers are Python. Do not introduce a Node.js subprocess for image processing.

### 3D Mesh Processing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| trimesh | 4.11.x | Mesh loading, format conversion, analysis, simplification | The best Python mesh library. Pure Python core with only numpy as hard dependency. Loads/exports OBJ, glTF/GLB, STL, PLY, 3MF, COLLADA. Has mesh simplification, boolean operations, convex hull, ray casting. Use for: validating AI-generated meshes, format conversion (GLB to FBX via intermediate), polygon count analysis, mesh repair. | HIGH |
| pygltflib | 1.16.x | Direct glTF 2.0 manipulation, PBR material editing, texture embedding | Low-level glTF library for precise control over glTF files. Use when trimesh's glTF support is too abstracted -- e.g., editing PBR material properties, swapping textures in an existing GLB, reading/writing glTF extensions. Complements trimesh, does not replace it. | MEDIUM |
| pymeshlab | 2025.07 | Advanced mesh operations: remeshing, decimation, topology optimization | PyMeshLab wraps the full MeshLab engine. Use for operations trimesh cannot do: isotropic remeshing, Quadric Edge Collapse decimation (better quality than trimesh's simplify), Poisson surface reconstruction, texture parameterization. Heavy dependency (C++ binaries) -- only install in the mesh-processing MCP server, not in all servers. | MEDIUM |

**Mesh processing pipeline for AI-generated assets:**

```
AI API output (GLB/OBJ)
    |
    v
[trimesh] -- Load, validate, inspect polygon count
    |
    v
[pymeshlab] -- Remesh/decimate if needed (target poly budget)
    |
    v
[pygltflib] -- Assign/edit PBR materials, embed textures
    |
    v
[trimesh] -- Export to format Unity can import (FBX via assimp, or GLB)
    |
    v
Unity import via MCP tool call
```

**Why NOT Open3D:** Open3D is focused on point cloud processing and 3D reconstruction (SLAM, depth cameras). It CAN process meshes but is optimized for a different use case. Trimesh + PyMeshLab covers game asset processing better with lighter weight.

**Why NOT Aspose.3D:** Commercial license, expensive, overkill for this use case. Trimesh is MIT-licensed and sufficient.

### Data Validation & Configuration

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| pydantic | >=2.12.0 | Tool input/output validation, config schemas, API response models | Already a core MCP SDK dependency. Use Pydantic models for ALL tool parameters and return types. The MCP SDK uses Pydantic for JSON Schema generation (tool descriptions sent to LLMs). Defining tool inputs as Pydantic models automatically generates correct schemas. | HIGH |
| pydantic-settings | >=2.5.2 | Environment variable and .env file configuration | Already a core MCP SDK dependency. Use for API keys (FAL_KEY, OPENAI_API_KEY, REPLICATE_API_TOKEN), port configuration, file paths. Reads from environment variables and .env files. | HIGH |
| python-dotenv | 1.x | .env file loading for local development | Lightweight .env file loader. pydantic-settings can use it as a backend. Keep API keys in `.env` files, never in code or config committed to git. | HIGH |

### Project Structure & Tooling

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| uv | latest | Package management, virtual environments, project scaffolding | Official MCP ecosystem tool. Replaces pip, pip-tools, poetry, pipenv. 10-100x faster. `uv init` for project setup, `uv add` for dependencies, `uv sync` for reproducible installs. Lock file (`uv.lock`) committed to git. | HIGH |
| pyproject.toml | PEP 621 | Project metadata, dependencies, scripts | Standard Python project configuration. Define MCP server entry points as `[project.scripts]` for `uvx` execution. | HIGH |
| ruff | latest | Linting and formatting | Replaces flake8, black, isort, pylint. Single tool, 10-100x faster (written in Rust). Configure in `pyproject.toml` under `[tool.ruff]`. | HIGH |
| mypy | latest | Static type checking | Critical for MCP tool parameter correctness. Pydantic models + mypy catches type mismatches before runtime. Use strict mode. | MEDIUM |
| pytest | 8.x | Testing | Standard Python testing. Use `pytest-asyncio` for testing async MCP tool handlers. Mock AI API calls with `respx` (httpx mock). | MEDIUM |
| pytest-asyncio | 0.24.x | Async test support | MCP tool handlers are async functions. pytest-asyncio enables `async def test_*()`. | MEDIUM |

### Project Layout (Recommended)

```
Tools/
  mcp-toolkit/                    # Root of the custom MCP toolkit
    pyproject.toml                # uv project config, dependencies, entry points
    uv.lock                       # Locked dependencies (committed to git)
    .env                          # API keys (NOT committed to git)
    .env.example                  # Template for API keys (committed)
    src/
      veilbreakers_mcp/
        __init__.py
        blender_server.py         # MCP server: Blender bridge tools
        unity_server.py           # MCP server: Unity bridge tools
        asset_gen_server.py       # MCP server: AI generation tools
        mesh_pipeline.py          # MCP server: mesh processing tools
        shared/
          __init__.py
          blender_client.py       # TCP socket client for Blender addon
          unity_client.py         # WebSocket client for Unity Editor
          ai_clients.py           # httpx wrappers for AI APIs
          image_utils.py          # Pillow/numpy image processing
          mesh_utils.py           # trimesh/pygltflib utilities
          models.py               # Pydantic models for tool I/O
          config.py               # pydantic-settings configuration
    tests/
      test_blender_tools.py
      test_unity_tools.py
      test_asset_gen.py
      test_mesh_pipeline.py
    blender_addon/
      __init__.py                 # Blender addon registration
      socket_server.py            # TCP socket server running inside Blender
      operators.py                # Blender operators exposed to MCP
```

**Why monorepo (single `Tools/mcp-toolkit/`) over separate repos per server:** All servers share common utilities (clients, image processing, mesh processing, config). Separate repos would duplicate shared code or require a private PyPI package. A monorepo with multiple entry points (`[project.scripts]` in pyproject.toml) is the pragmatic choice for a single-developer project. Each server is a separate entry point but shares the same codebase.

**Why `Tools/mcp-toolkit/` inside the Unity project:** Keeps the MCP toolkit co-located with the game project it serves. The `.mcp.json` can reference it directly. Unity ignores non-Assets directories. If the toolkit grows, it can be extracted to a separate repo later.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| MCP SDK Language | Python (mcp 1.26.0) | TypeScript (MCP SDK v1.x) | Blender API is Python-only. AI SDKs are Python-first. TypeScript SDK v2 is pre-alpha. Would require Python subprocess bridge for Blender anyway. |
| MCP Framework | Built-in SDK FastMCP | FastMCP 3.1.1 standalone | Standalone FastMCP adds complexity (composition, proxying) not needed for first iteration. Built-in decorator API is sufficient. Upgrade later if needed. |
| HTTP Client | httpx (bundled with MCP) | aiohttp | aiohttp is async-only, heavier, and redundant with httpx already installed. httpx handles both sync and async. |
| HTTP Client | httpx (bundled with MCP) | requests | Synchronous-only. Blocks the async MCP event loop. httpx is the async-capable replacement. |
| WebSocket | websockets 14.x | aiohttp WebSocket client | aiohttp's WebSocket client is part of a larger server framework. websockets is focused, lighter, better documented for client-only use. |
| Image Processing | Pillow 12.x + numpy | OpenCV (cv2) | 100+ MB dependency for features not needed. Pillow + numpy handles texture processing without computer vision overhead. |
| Image Processing | Pillow 12.x + numpy | Wand (ImageMagick binding) | ImageMagick is an external system dependency. Pillow is pure Python. Simpler deployment. |
| Mesh Processing | trimesh 4.11.x | Open3D | Open3D focuses on point clouds and reconstruction. Heavier (C++ binaries for features we don't need). Trimesh is focused on triangle mesh operations. |
| Mesh Processing | trimesh + pymeshlab | pyvista | pyvista is a VTK wrapper for scientific visualization. Not optimized for game asset pipelines. |
| 3D API (primary) | fal.ai (fal-client) | Meshy API | Meshy is good but fal.ai has broader model selection (Hunyuan3D v3, Trellis, Flux) under one SDK. Meshy is a fallback option. |
| 3D API (primary) | fal.ai | Replicate | Replicate is the fallback. fal.ai is faster for image/3D gen with better pricing. Replicate has broader model catalog for edge cases. |
| Project management | uv | poetry / pip-tools | MCP ecosystem standardized on uv. 10-100x faster. Better lock file format. Official recommendation from MCP SDK team. |
| Linting | ruff | flake8 + black + isort | Ruff replaces all three in a single tool. 10-100x faster. One config section in pyproject.toml. |
| Package manager | uv | pip | pip is slow, has no lock file, and uv is a drop-in replacement with massive speed improvements. |

---

## Installation

```bash
# Prerequisites: Python 3.12, uv installed
# On Windows:
# pip install uv   (or)   winget install astral-sh.uv

# Initialize project
cd Tools/mcp-toolkit
uv init --python 3.12

# Core MCP SDK
uv add "mcp[cli]>=1.26.0"

# Communication
uv add "websockets>=14.0"

# AI Generation APIs
uv add "fal-client>=0.13.0"
uv add "openai>=1.60.0"
uv add "replicate>=1.0.0"

# Image Processing
uv add "Pillow>=12.1.0"
uv add "numpy>=1.26.0"

# 3D Mesh Processing
uv add "trimesh[easy]>=4.11.0"
uv add "pygltflib>=1.16.0"

# Optional: heavy mesh processing (install only when needed)
uv add "pymeshlab>=2025.7"

# Configuration
uv add "python-dotenv>=1.0.0"

# Dev dependencies
uv add --dev "pytest>=8.0"
uv add --dev "pytest-asyncio>=0.24.0"
uv add --dev "respx>=0.22.0"
uv add --dev "ruff>=0.8.0"
uv add --dev "mypy>=1.13.0"
```

### Entry Points (pyproject.toml)

```toml
[project.scripts]
vb-blender-mcp = "veilbreakers_mcp.blender_server:main"
vb-unity-mcp = "veilbreakers_mcp.unity_server:main"
vb-assetgen-mcp = "veilbreakers_mcp.asset_gen_server:main"
vb-mesh-mcp = "veilbreakers_mcp.mesh_pipeline:main"
```

### .mcp.json Integration

```json
{
  "mcpServers": {
    "vb-blender": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "Tools/mcp-toolkit", "run", "vb-blender-mcp"],
      "env": { "BLENDER_PORT": "9876" }
    },
    "vb-assetgen": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "Tools/mcp-toolkit", "run", "vb-assetgen-mcp"],
      "env": { "FAL_KEY": "${FAL_KEY}", "OPENAI_API_KEY": "${OPENAI_API_KEY}" }
    },
    "vb-mesh": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "Tools/mcp-toolkit", "run", "vb-mesh-mcp"],
      "description": "3D mesh processing, format conversion, validation"
    }
  }
}
```

---

## What NOT to Use

| Technology | Why Not |
|------------|---------|
| TypeScript for Blender integration | Blender's API is Python-only (bpy). A TypeScript server would need to shell out to Python, adding latency and complexity for zero benefit. |
| aiohttp | Redundant with httpx (already in MCP SDK). Adds ~15MB of dependencies for zero additional capability in this context. |
| requests | Synchronous-only. Blocks the async MCP event loop. Use httpx instead. |
| OpenCV (cv2) | 100+ MB. Designed for computer vision, not texture processing. Pillow + numpy is sufficient and 10x lighter. |
| gRPC | Over-engineered for local IPC. MCP already defines JSON-RPC over stdio. Blender/Unity bridges use TCP/WebSocket JSON. Adding gRPC would be a fourth protocol for no benefit. |
| Docker for local development | MCP servers run as local subprocesses. Docker adds startup latency (seconds vs milliseconds) and complicates GPU passthrough for local ComfyUI. Use Docker only if deploying remote Streamable HTTP servers. |
| Flask / Django | The MCP SDK includes Starlette/uvicorn for HTTP transport. Adding another web framework is redundant and creates conflicts. |
| FastAPI | Same issue as Flask/Django. FastAPI is built on Starlette, which is already in the MCP SDK. If you need HTTP endpoints beyond MCP, use Starlette directly from the SDK's dependencies. |
| Poetry / Pipenv | uv is the MCP ecosystem standard. Mixing package managers causes lock file conflicts and confuses contributors. |
| SSE transport (legacy) | SSE transport was deprecated in MCP spec 2025-03-26, replaced by Streamable HTTP. Do not implement SSE servers. |
| Aspose.3D | Commercial license ($999+/year). Trimesh + PyMeshLab covers all game asset mesh operations for free. |
| numpy-stl | Trimesh handles STL plus dozens of other formats. numpy-stl is STL-only. Use trimesh. |

---

## Version Compatibility Matrix

| Component | Required Version | Rationale | Status |
|-----------|-----------------|-----------|--------|
| Python | 3.12.x | MCP SDK >=3.10, Blender 4.x uses 3.11-3.12, best perf/compat balance | INSTALL |
| mcp SDK | >=1.26.0 | Latest stable with Streamable HTTP, OAuth, all transports | INSTALL |
| Blender | 4.x (4.2+ preferred) | bpy API stability, Python 3.11-3.12 embedded | EXTERNAL (user installed) |
| Unity | 6000.3.6f1 | Locked per PROJECT.md constraint. mcp-unity package required in project | EXISTING |
| Node.js | 18+ | Only for mcp-unity bridge server (existing). Not used for custom Python servers | EXISTING |
| fal.ai | Account + FAL_KEY | Pay-per-use API. No local GPU needed | EXTERNAL |
| OpenAI | Account + API key | Pay-per-use API | EXTERNAL |
| ComfyUI | Local install (optional) | Only needed for custom SD pipelines. Not required for cloud-only workflow | OPTIONAL |

---

## MCP Server Minimal Example

```python
"""Minimal MCP server showing the SDK pattern."""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("veilbreakers-assetgen")

@mcp.tool()
async def generate_monster_concept(
    description: str,
    style: str = "dark fantasy",
    width: int = 1024,
    height: int = 1024,
) -> str:
    """Generate concept art for a VeilBreakers monster.

    Args:
        description: Monster description (e.g., 'corrupted wolf with void crystals')
        style: Art style directive
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        Path to the generated image file
    """
    import httpx
    # Use httpx (already in MCP SDK deps) to call fal.ai
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://fal.run/fal-ai/flux/schnell",
            headers={"Authorization": f"Key {get_fal_key()}"},
            json={
                "prompt": f"{description}, {style}, game character concept art",
                "image_size": {"width": width, "height": height},
            },
        )
        result = response.json()
        # Download and save image...
        return f"Generated monster concept: {result['images'][0]['url']}"

@mcp.resource("monsters://brands")
async def get_brand_list() -> str:
    """List all VeilBreakers monster brands."""
    return "IRON, SAVAGE, SURGE, VENOM, DREAD, LEECH, GRACE, MEND, RUIN, VOID"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

---

## Key Architectural Decisions

### Decision 1: Separate MCP Servers per Domain (Not One Monolith)

**Decision:** Four separate MCP server entry points (blender, unity, asset-gen, mesh), sharing a common Python package.

**Rationale:** MCP clients (Claude Code) load each server as a separate subprocess. A monolith with 40+ tools would overwhelm the tool selection heuristic. Separate servers allow:
- Loading only what is needed (e.g., asset-gen without Blender running)
- Independent failure (Blender crash does not kill the mesh processor)
- Clearer tool namespacing in the LLM's tool list

### Decision 2: TCP Sockets for Blender, WebSocket for Unity

**Decision:** Keep the same IPC patterns as the reference implementations (ahujasid/blender-mcp, CoderGamester/mcp-unity).

**Rationale:** These patterns are battle-tested. Blender's bpy API has GIL constraints that make embedding an MCP server inside Blender impractical. The socket server addon pattern works around this. Unity's WebSocket server is already integrated via the mcp-unity package. Changing protocols would break compatibility with the existing Unity package.

### Decision 3: Cloud APIs First, Local ComfyUI as Escape Hatch

**Decision:** Default to fal.ai/OpenAI cloud APIs. ComfyUI local only for custom pipelines.

**Rationale:** Cloud APIs have the latest models (Hunyuan3D v3, GPT Image 1.5, Flux), require no GPU, and cost cents per generation. Local ComfyUI is kept as an option for ControlNet-guided texture generation pipelines that cloud APIs cannot replicate. This avoids forcing GPU requirements on the development setup.

---

## Sources

### Official Documentation (HIGH confidence)
- [MCP Python SDK - GitHub](https://github.com/modelcontextprotocol/python-sdk) -- v1.26.0, FastMCP API, transport details
- [MCP Python SDK - PyPI](https://pypi.org/project/mcp/) -- Version 1.26.0, Python >=3.10
- [MCP Specification - Transports](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports) -- stdio and Streamable HTTP spec
- [MCP TypeScript SDK - GitHub](https://github.com/modelcontextprotocol/typescript-sdk) -- v2 pre-alpha, v1.x stable
- [FastMCP - PyPI](https://pypi.org/project/fastmcp/) -- v3.1.1 standalone
- [MCP SDK Dependencies - DeepWiki](https://deepwiki.com/modelcontextprotocol/python-sdk/1.1-installation-and-dependencies) -- Full dependency list with version constraints
- [MCP Transport Comparison - AWS Builder](https://builder.aws.com/content/35A0IphCeLvYzly9Sw40G1dVNzc/mcp-transport-mechanisms-stdio-vs-streamable-http) -- stdio vs Streamable HTTP analysis
- [trimesh - PyPI](https://pypi.org/project/trimesh/) -- v4.11.4, format support, dependencies
- [Pillow - PyPI](https://pypi.org/project/pillow/) -- v12.1.1, DDS support details
- [Pillow DDS Format](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html) -- DDS read/write capabilities
- [fal.ai 3D Models](https://fal.ai/3d-models) -- Hunyuan3D v3, Trellis API
- [fal-client PyPI](https://pypi.org/project/fal-client/) -- v0.13.x
- [OpenAI Image Generation](https://platform.openai.com/docs/guides/image-generation) -- GPT Image models, DALL-E deprecation
- [pygltflib - PyPI](https://pypi.org/project/pygltflib/) -- glTF 2.0 manipulation
- [uv Documentation](https://docs.astral.sh/uv/guides/projects/) -- Project setup, dependency management

### Reference Implementations (HIGH confidence)
- [blender-mcp (ahujasid)](https://github.com/ahujasid/blender-mcp) -- TCP socket architecture, Blender addon pattern
- [mcp-unity (CoderGamester)](https://github.com/CoderGamester/mcp-unity) -- WebSocket bridge, Unity C# server, Node.js MCP client
- [mcp-game-asset-gen (Flux159)](https://github.com/Flux159/mcp-game-asset-gen) -- TypeScript game asset generation MCP, fal.ai/OpenAI integration

### Ecosystem Research (MEDIUM confidence)
- [MCP Transport Future - Blog](https://blog.modelcontextprotocol.io/posts/2025-12-19-mcp-transport-future/) -- Transport evolution direction
- [PyMeshLab - GitHub](https://github.com/cnr-isti-vclab/PyMeshLab) -- v2025.07 release
- [3D API Comparison 2026](https://www.3daistudio.com/blog/best-3d-model-generation-apis-2026) -- Meshy, Tripo, Rodin, fal.ai comparison
- [httpx vs aiohttp vs requests](https://www.speakeasy.com/blog/python-http-clients-requests-vs-httpx-vs-aiohttp) -- HTTP client comparison
- [MCP Game Development Servers](https://mcpmarket.com/categories/game-development) -- Ecosystem overview
- [ComfyUI API Guide](https://comfyui.org/en/programmatic-image-generation-api-workflow) -- Programmatic workflow execution
