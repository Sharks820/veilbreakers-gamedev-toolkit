# Phase 3: Texturing & Asset Generation - Research

**Researched:** 2026-03-18
**Domain:** PBR Texturing + AI 3D Generation (Tripo3D) + Texture Processing (Pillow/Real-ESRGAN) + Asset Pipeline + Concept Art
**Confidence:** HIGH

## Summary

Phase 3 is the largest and most architecturally diverse phase so far. It spans three distinct execution environments: (1) Blender-side handlers for PBR node trees, texture baking, procedural wear maps, LOD generation, and material setup; (2) MCP server-side Python for Pillow-based texture editing (masking, HSV, seam blending, tiling, validation) and image AI calls (concept art, color palette); and (3) external service integrations via HTTP (Tripo3D API for AI 3D generation) and subprocess (Real-ESRGAN ncnn-vulkan binary for texture upscaling). The existing compound tool architecture from Phases 1-2 (8 tools, ~3000 tokens) must be extended with 2-3 new compound tools without exceeding the ~5200 token budget.

The 20 requirements break into four logical groups: **Texturing** (TEX-01 through TEX-10) covers PBR material creation, surgical texture editing, baking, upscaling, and validation -- all operating on UV-mapped meshes from Phase 2. **Pipeline** (PIPE-01 through PIPE-07) covers AI 3D generation, cleanup automation, LOD chains, export validation, metadata, batch processing, and asset catalog. **Concept Art** (CONC-01 through CONC-03) covers AI image generation, color palette extraction, and style reference boards. The key architectural decision is whether MCP-side operations (Tripo3D, Real-ESRGAN, fal.ai, Pillow texture ops) belong in the existing `blender_server.py` or a new MCP server. Given the compound tool pattern and 26-tool budget, they should be new tools in the same server -- `blender_texture` for all texture operations (Blender-side baking + MCP-side Pillow editing), `asset_pipeline` for Tripo3D + LOD + export + batch + catalog, and `concept_art` for image generation + palette + style boards.

**Primary recommendation:** Add 3 new compound MCP tools (`blender_texture` with ~12 actions, `asset_pipeline` with ~8 actions, `concept_art` with ~4 actions) to the existing `blender_server.py`. Use the portable `realesrgan-ncnn-vulkan.exe` binary (no CUDA/PyTorch dependency) for texture upscaling via subprocess. Use the `tripo3d` Python SDK (v0.3.12) for AI 3D generation. Use `fal-client` for concept art generation via FLUX models. Texture editing (masking, HSV, seam blending, tiling) is pure Pillow on the MCP server side. Texture baking and PBR node trees are Blender-side handlers.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TEX-01 | PBR material from text description (albedo, normal, roughness, metallic, AO) | Blender Principled BSDF node tree with Image Texture nodes per channel; Blender 4.0+ input names verified (Section: PBR Node Tree Construction) |
| TEX-02 | Surgical texture editing -- mask UV/material region | Pillow Image.composite() with L-mode mask from UV coordinates; UV island extraction via bmesh UV layer data (Section: Surgical Texture Masking) |
| TEX-03 | AI texture inpainting on masked region | fal.ai FLUX image-to-image with mask via fal-client SDK; MCP-side async call (Section: AI Texture Inpainting) |
| TEX-04 | HSV adjustment on masked texture regions | Pillow ImageEnhance + convert to HSV mode + mask-based selective application (Section: HSV Adjustment) |
| TEX-05 | Texture seam blending between UV islands | Pillow Gaussian blur on seam edge pixels with distance-weighted falloff; UV seam detection from bmesh edge data (Section: Seam Blending) |
| TEX-06 | Procedural wear/damage map generation | bmesh curvature approximation via edge angle analysis: convex edges = worn, concave = dirty, high-curvature = chipped; baked to vertex colors then to image (Section: Procedural Wear Maps) |
| TEX-07 | Texture baking high-poly to low-poly | bpy.ops.object.bake() with use_selected_to_active=True; Cycles required; types: NORMAL, AO, COMBINED, ROUGHNESS, EMIT; context override pattern (Section: Texture Baking) |
| TEX-08 | AI texture upscaling via Real-ESRGAN | realesrgan-ncnn-vulkan.exe portable binary via subprocess; models: realesrgan-x4plus (textures), realesrgan-x4plus-anime (stylized); 2x/4x scale (Section: Real-ESRGAN Integration) |
| TEX-09 | Seamless tileable texture generation | Pillow cross-fade overlap method: mirror-blend edges to create seamless tiles; also Blender procedural noise with 4D coordinate trick for seamless baking (Section: Tileable Textures) |
| TEX-10 | Texture validation (resolution, format, UV coverage, compression) | Pillow image metadata inspection + UV coverage calculation from bmesh UV layer + power-of-two checks + format/compression recommendations (Section: Texture Validation) |
| PIPE-01 | Tripo3D API integration for AI 3D generation | tripo3d Python SDK v0.3.12; async text_to_model/image_to_model; poll via wait_for_task; download GLB; Bearer token auth (Section: Tripo3D Integration) |
| PIPE-02 | AI model cleanup pipeline (auto-repair + UV + material) | Orchestration of existing blender_mesh(repair) + blender_uv(unwrap) + blender_texture(create_pbr) in sequence; MCP-side pipeline coordinator (Section: Cleanup Pipeline) |
| PIPE-03 | LOD chain generation (LOD0-3) | Blender Decimate modifier with ratios [1.0, 0.5, 0.25, 0.1]; UN_SUBDIVIDE or COLLAPSE mode; preserve UV seams option; duplicate-decimate-rename pattern (Section: LOD Generation) |
| PIPE-04 | Export validation (Unity re-import check) | FBX export + Python fbx-parser validation of scale/orientation/bones/materials; or GLB validation via pygltflib (Section: Export Validation) |
| PIPE-05 | Asset metadata tagging | JSON sidecar files with asset properties (poly count, texture res, LOD count, tags, creator, date); stored alongside exported assets (Section: Asset Metadata) |
| PIPE-06 | Batch processing pipeline | MCP-side async queue: accept list of objects, run pipeline (repair + UV + texture + LOD + export) per object; progress reporting per item (Section: Batch Processing) |
| PIPE-07 | Asset database/catalog | SQLite database with asset entries (name, path, type, tags, poly count, texture res, LODs, status); query/search/filter via MCP tool actions (Section: Asset Catalog) |
| CONC-01 | Concept art from text description | fal-client SDK calling FLUX.1 [dev] or FLUX Pro 1.1; return generated image as MCP Image; environment variable FAL_KEY for auth (Section: Concept Art Generation) |
| CONC-02 | Color palette extraction | Pillow image quantize() or scikit-learn KMeans on pixel data; extract N dominant colors as hex values; return swatch image (Section: Color Palette Extraction) |
| CONC-03 | Style reference board generation | Compose multiple concept art images + color palette + text annotations into single reference board image via Pillow grid layout (Section: Style Reference Board) |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tripo3d | 0.3.12 | AI 3D model generation (text-to-3D, image-to-3D) | Official Tripo Python SDK. Handles auth, async polling, download. User has Tripo3D subscription. |
| fal-client | latest (2026-02) | AI image generation for concept art and texture inpainting | Unified API for FLUX models. Simple async interface. Pay-per-use. |
| Pillow | >=12.1.0 | Texture editing (mask, HSV, blend, tile, validate, palette, compose) | Already in project stack from Phase 1. Handles all image manipulation needs. |
| realesrgan-ncnn-vulkan | latest release | AI texture upscaling 2x/4x | Portable binary, no CUDA/PyTorch needed. Vulkan GPU acceleration. Subprocess call from MCP server. |
| bpy.ops.object.bake | (Blender built-in) | Texture baking (normal, AO, combined, roughness) | Blender's native baking API. Requires Cycles renderer. |
| bmesh | (Blender built-in) | Curvature analysis, UV data extraction, wear map computation | Already used extensively in Phase 2. Direct geometry access. |
| sqlite3 | (Python stdlib) | Asset catalog database | Zero dependencies. Sufficient for single-user asset catalog. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy | (Blender built-in) | Array ops for curvature computation and pixel manipulation | Wear map calculation, texture array operations |
| scikit-learn | optional | KMeans clustering for color palette extraction | Only if Pillow quantize() is insufficient; adds heavy dependency |
| colorsys | (Python stdlib) | HSV color space conversion | HSV adjustment on texture regions |
| aiohttp | (via tripo3d dep) | HTTP client for API calls | Tripo3D SDK uses it internally; also useful for fal.ai if fal-client unavailable |
| pygltflib | optional | GLB/glTF file validation | Export validation of GLB files from Tripo3D; lightweight alternative to full Unity re-import |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| realesrgan-ncnn-vulkan binary | realesrgan pip package (PyTorch) | PyTorch adds 2GB+ dependency, requires CUDA. Binary is 30MB, runs on any GPU via Vulkan. Use binary. |
| fal-client for concept art | Stability AI API, OpenAI DALL-E | fal.ai has FLUX models (state of art), simple SDK, good pricing. Other APIs work but FLUX quality is superior for concept art. |
| sqlite3 for asset catalog | TinyDB, JSON files | sqlite3 is stdlib, supports complex queries, handles concurrent access. JSON files don't scale and lack querying. |
| Pillow for seam blending | OpenCV (cv2) | OpenCV is more powerful for image processing but adds large dependency. Pillow handles the needed operations (blur, composite, crop). Use Pillow. |
| tripo3d SDK | Direct HTTP API calls | SDK handles async polling, retries, auth, file download. No reason to reinvent. |

**Installation:**
```bash
# MCP server dependencies (add to pyproject.toml)
cd Tools/mcp-toolkit
uv add "tripo3d>=0.3.12"
uv add "fal-client>=0.5.0"

# Real-ESRGAN portable binary (download once)
# From: https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases
# Place in: Tools/mcp-toolkit/bin/realesrgan-ncnn-vulkan/
# Contains: realesrgan-ncnn-vulkan.exe + models/ directory
```

**Environment variables (.env):**
```
TRIPO_API_KEY=tsk_your_key_here
FAL_KEY=your_fal_key_here
REALESRGAN_PATH=bin/realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan.exe
```

## Architecture Patterns

### Tool Architecture Decision: Three New Compound Tools

**Decision:** Add `blender_texture`, `asset_pipeline`, and `concept_art` as three new compound MCP tools (tools 9, 10, 11 of the ~26 tool budget). All live in the existing `blender_server.py`.

**Rationale:**
1. **Execution environment separation:** `blender_texture` handles operations that touch Blender (PBR node trees, baking, wear maps) AND Pillow (masking, HSV, seam blend, tile, validate, upscale). The MCP server orchestrates both sides. `asset_pipeline` handles external APIs (Tripo3D) and pipeline orchestration. `concept_art` handles AI image generation (fal.ai).
2. **Token budget:** Phase 1-2 has 8 tools at ~3000 tokens. Three new tools add ~1200 tokens (400 each), bringing total to ~4200. This leaves ~1000 tokens for Phases 4-8 (~15 remaining tools).
3. **Domain coherence:** Texture operations (create PBR, edit, bake, upscale, validate) are one domain. Pipeline operations (generate 3D, cleanup, LOD, export, batch, catalog) are another. Concept art is a third.

### New Tool Definitions

```
blender_texture (~12 actions):
  - create_pbr          (TEX-01) -- Blender-side: node tree construction
  - mask_region         (TEX-02) -- MCP-side: Pillow UV mask generation
  - inpaint             (TEX-03) -- MCP-side: fal.ai FLUX inpainting
  - hsv_adjust          (TEX-04) -- MCP-side: Pillow HSV on masked region
  - blend_seams         (TEX-05) -- MCP-side: Pillow seam blending
  - generate_wear       (TEX-06) -- Blender-side: bmesh curvature + bake
  - bake                (TEX-07) -- Blender-side: bpy.ops.object.bake
  - upscale             (TEX-08) -- MCP-side: realesrgan subprocess
  - make_tileable       (TEX-09) -- MCP-side: Pillow cross-fade
  - validate            (TEX-10) -- MCP+Blender: image + UV coverage check

asset_pipeline (~8 actions):
  - generate_3d         (PIPE-01) -- MCP-side: Tripo3D SDK
  - cleanup             (PIPE-02) -- Orchestrate: repair + UV + material
  - generate_lods       (PIPE-03) -- Blender-side: Decimate modifier
  - validate_export     (PIPE-04) -- MCP-side: FBX/GLB file validation
  - tag_metadata        (PIPE-05) -- MCP-side: JSON sidecar write
  - batch_process       (PIPE-06) -- MCP-side: queue + progress
  - catalog_query       (PIPE-07) -- MCP-side: SQLite query
  - catalog_add         (PIPE-07) -- MCP-side: SQLite insert

concept_art (~4 actions):
  - generate            (CONC-01) -- MCP-side: fal.ai FLUX
  - extract_palette     (CONC-02) -- MCP-side: Pillow quantize
  - style_board         (CONC-03) -- MCP-side: Pillow grid compose
  - silhouette_test     (CONC-03) -- MCP-side: Pillow threshold + scale
```

### Handler Module Structure

```
blender_addon/
  handlers/
    __init__.py              # Extended: add texture_* and pipeline_* handlers
    _context.py              # Existing (unchanged)
    materials.py             # Existing: basic PBR (extended for full node trees)
    texture_pbr.py           # NEW: full PBR node tree with image textures
    texture_bake.py          # NEW: bpy.ops.object.bake wrapper
    texture_wear.py          # NEW: bmesh curvature + wear map bake
    pipeline_lod.py          # NEW: Decimate modifier LOD chain
    objects.py               # Existing (unchanged)
    scene.py                 # Existing (unchanged)
    viewport.py              # Existing (unchanged)
    export.py                # Existing (unchanged)
    execute.py               # Existing (unchanged)
    mesh.py                  # Existing (unchanged)
    uv.py                    # Existing (unchanged)

src/veilbreakers_mcp/
  blender_server.py          # Extended: add 3 new compound tools
  shared/
    texture_ops.py           # NEW: Pillow-based texture editing (mask, HSV, seam, tile)
    texture_validation.py    # NEW: texture format/resolution/coverage checks
    tripo_client.py          # NEW: Tripo3D SDK wrapper with polling
    esrgan_runner.py         # NEW: realesrgan subprocess wrapper
    fal_client.py            # NEW: fal.ai concept art generation
    asset_catalog.py         # NEW: SQLite asset database
    pipeline_runner.py       # NEW: batch processing orchestration
```

### Blender-Side vs MCP-Side Execution Matrix

| Operation | Runs Where | Why |
|-----------|-----------|-----|
| PBR node tree construction | Blender | Requires bpy.data.materials, node_tree API |
| Texture baking | Blender | Requires bpy.ops.object.bake, Cycles renderer |
| Curvature/wear map computation | Blender | Requires bmesh geometry access |
| LOD generation (Decimate) | Blender | Requires bpy.ops.object.modifier_add |
| UV mask generation | MCP server | Pure Pillow -- reads UV coords from Blender, generates mask image |
| HSV adjustment | MCP server | Pure Pillow -- pixel manipulation |
| Seam blending | MCP server | Pure Pillow -- blur/composite along seam edges |
| Tileable texture | MCP server | Pure Pillow -- cross-fade edges |
| Texture validation | Both | MCP reads image metadata; Blender provides UV coverage data |
| Texture upscaling | MCP server | Subprocess call to realesrgan binary |
| Tripo3D generation | MCP server | HTTP API via tripo3d SDK |
| Concept art generation | MCP server | HTTP API via fal-client SDK |
| Color palette extraction | MCP server | Pure Pillow quantize() |
| Asset catalog | MCP server | SQLite database operations |
| Batch processing | MCP server | Orchestration -- dispatches individual Blender commands |

### Pattern: Two-Phase Texture Operations

**What:** Many texture operations require data from both Blender (UV coordinates, mesh geometry) and MCP server (Pillow image processing). The handler extracts data from Blender first, sends it to the MCP server, processes it with Pillow, then optionally sends the result back to Blender.

**When:** TEX-02 (masking), TEX-04 (HSV), TEX-05 (seam blending), TEX-06 (wear maps), TEX-10 (validation).

**Example (UV mask generation for surgical editing):**
```python
# Step 1: Blender handler extracts UV island data for a material slot
# Returns: list of UV polygon coordinates for the target region
def handle_get_uv_region(params: dict) -> dict:
    obj_name = params["object_name"]
    material_index = params["material_index"]
    obj = bpy.data.objects.get(obj_name)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    uv_layer = bm.loops.layers.uv.active

    polygons = []
    for face in bm.faces:
        if face.material_index == material_index:
            poly = [(loop[uv_layer].uv.x, loop[uv_layer].uv.y)
                    for loop in face.loops]
            polygons.append(poly)
    bm.free()
    return {"polygons": polygons, "texture_size": params.get("texture_size", 1024)}

# Step 2: MCP server generates mask image from UV polygons
# Pure Pillow -- no bpy needed
from PIL import Image, ImageDraw

def generate_uv_mask(polygons: list, texture_size: int) -> bytes:
    mask = Image.new("L", (texture_size, texture_size), 0)
    draw = ImageDraw.Draw(mask)
    for poly in polygons:
        # Convert UV (0-1) to pixel coords
        pixel_poly = [(int(u * texture_size), int((1 - v) * texture_size))
                      for u, v in poly]
        draw.polygon(pixel_poly, fill=255)
    buf = io.BytesIO()
    mask.save(buf, format="PNG")
    return buf.getvalue()
```

### Pattern: Async External Service Calls

**What:** Tripo3D and fal.ai calls are async HTTP requests that may take 30-120 seconds. The MCP tool must not block the server.

**When:** PIPE-01 (Tripo3D), CONC-01 (concept art), TEX-03 (inpainting), TEX-08 (upscaling).

**Example (Tripo3D integration):**
```python
# Source: tripo3d Python SDK v0.3.12 API docs
from tripo3d import TripoClient

async def generate_3d_model(prompt: str, output_dir: str) -> dict:
    async with TripoClient(api_key=settings.tripo_api_key) as client:
        task_id = await client.text_to_model(
            prompt=prompt,
            texture=True,
            pbr=True,
            model_version="v2.5-20250123",
        )
        task = await client.wait_for_task(
            task_id,
            timeout=300,
            polling_interval=3.0,
            verbose=False,
        )
        if task.status == "success":
            files = await client.download_task_models(task, output_dir)
            return {
                "status": "success",
                "model_path": files.get("model"),
                "pbr_model_path": files.get("pbr_model"),
                "task_id": task_id,
            }
        return {"status": "failed", "task_id": task_id, "error": str(task.status)}
```

### Anti-Patterns to Avoid

- **Baking without Cycles:** `bpy.ops.object.bake()` requires Cycles renderer. If EEVEE is active, switch to Cycles before bake, switch back after. Forgetting this produces errors.
- **Non-Color data in sRGB:** Normal maps, roughness maps, metallic maps MUST have color space set to "Non-Color" on the Image Texture node. Using sRGB produces incorrect rendering.
- **Blocking on external APIs:** Tripo3D generation takes 30-120s. Do NOT make this synchronous -- use async/await and report progress.
- **Hardcoding Principled BSDF input names:** Input names changed in Blender 4.0 (e.g., "Specular" became "Specular IOR Level"). Use try/except or version detection when connecting to renamed sockets.
- **Baking without an active image texture node:** The bake target is determined by which Image Texture node is selected (active) in the material. If none is selected, bake fails silently or writes to wrong image.
- **LOD with non-applied modifiers:** Decimate modifier must be applied AFTER other modifiers. Applying in wrong order corrupts geometry.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AI 3D generation | Custom HTTP polling loop | tripo3d SDK (TripoClient) | Handles auth, polling, retries, file download, error handling |
| Texture upscaling | PyTorch Real-ESRGAN pipeline | realesrgan-ncnn-vulkan binary | No CUDA/PyTorch needed, 30MB vs 2GB+, Vulkan GPU accel |
| Concept art generation | Custom image gen API client | fal-client SDK | Unified API, handles auth, supports FLUX/Imagen/Recraft |
| Color palette extraction | Custom k-means from scratch | Pillow Image.quantize(colors=N) | Built-in, fast, no scikit-learn dependency needed |
| PBR node tree | Manual node creation per map | Parameterized builder function | DRY: one function that creates all 5+ image textures and wires to BSDF |
| Asset catalog | Custom file-based index | sqlite3 | SQL queries, concurrent access, zero dependencies |
| Texture format validation | Manual pixel inspection | Pillow Image.info + mode + size | Pillow reports format, bit depth, color space, dimensions |

**Key insight:** This phase has more external-tool integration than any previous phase. The value is in ORCHESTRATION -- chaining Tripo3D output through mesh repair, UV unwrapping, PBR texturing, LOD generation, and export validation. Each step uses an existing library; the custom code is the glue.

## Common Pitfalls

### Pitfall 1: Bake Requires Cycles Renderer (CRITICAL)

**What goes wrong:** `bpy.ops.object.bake()` silently fails or raises an error when the scene render engine is EEVEE (the default for new scenes).
**Why it happens:** Texture baking is a Cycles-only feature in Blender. EEVEE does not support the bake operator.
**How to avoid:** Always check and set `bpy.context.scene.render.engine = 'CYCLES'` before baking. Store the previous engine and restore after bake completes. Set `bpy.context.scene.cycles.device = 'GPU'` for speed if CUDA/OptiX is available.
**Warning signs:** "Bake type not supported" error. Empty/black baked textures. No error but no output.

### Pitfall 2: Bake Target Image Must Be Active Node

**What goes wrong:** Baking writes to the wrong image or fails because no image texture node is selected as the active node in the material.
**Why it happens:** Blender determines the bake target by which Image Texture node has `node.select = True` and is the active node (`mat.node_tree.nodes.active = node`). If the material has multiple Image Texture nodes (one per PBR channel), the wrong one may be active.
**How to avoid:** Before each bake pass, explicitly set the target image texture node as active: `node.select = True; mat.node_tree.nodes.active = node`. Create separate Image Texture nodes per bake type (normal, AO, etc.) and activate the correct one before each pass.
**Warning signs:** All bake passes write to the same image. Bake produces unexpected content.

### Pitfall 3: Principled BSDF Input Name Changes (Blender 4.0+)

**What goes wrong:** `node.inputs["Specular"]` raises KeyError in Blender 4.0+ because the input was renamed to "Specular IOR Level".
**Why it happens:** Blender 4.0 revamped the Principled BSDF to align with OpenPBR Surface. Six inputs were renamed.
**How to avoid:** Use a lookup dictionary that maps semantic names to version-specific socket names:
```python
BSDF_INPUT_MAP = {
    "subsurface": "Subsurface Weight",    # was "Subsurface" pre-4.0
    "specular": "Specular IOR Level",     # was "Specular" pre-4.0
    "transmission": "Transmission Weight", # was "Transmission" pre-4.0
    "coat": "Coat Weight",                # was "Coat" pre-4.0
    "sheen": "Sheen Weight",              # was "Sheen" pre-4.0
    "emission": "Emission Color",         # was "Emission" pre-4.0
    # Unchanged names:
    "base_color": "Base Color",
    "metallic": "Metallic",
    "roughness": "Roughness",
    "ior": "IOR",
    "alpha": "Alpha",
    "normal": "Normal",
}
```
**Warning signs:** KeyError on node.inputs[...]. Material appears to have no effect on rendering.

### Pitfall 4: Normal Map Requires Non-Color Data and Normal Map Node

**What goes wrong:** Normal map appears as purple flat color instead of surface detail. Or normals render with wrong intensity/direction.
**Why it happens:** Two common errors: (1) Image Texture node left in sRGB color space instead of "Non-Color", causing gamma correction to corrupt normal data. (2) Image Texture connected directly to Principled BSDF "Normal" input instead of going through a Normal Map node first.
**How to avoid:** For normal maps: set `image_node.image.colorspace_settings.name = "Non-Color"`. Insert a `ShaderNodeNormalMap` between the Image Texture and the Principled BSDF Normal input. Same applies to roughness, metallic, AO -- all must be Non-Color.
**Warning signs:** Purple-tinted or overly bright normals. Roughness/metallic appearing brighter than expected.

### Pitfall 5: Tripo3D Model Requires Post-Processing

**What goes wrong:** Tripo3D GLB models imported directly into Blender have non-manifold geometry, excessive poly counts, poor UVs, and materials that don't match Blender's Principled BSDF.
**Why it happens:** AI-generated meshes are not game-ready. They need the cleanup pipeline (PIPE-02).
**How to avoid:** Always run the cleanup pipeline after Tripo3D import: (1) import GLB, (2) mesh repair (Phase 2 handler), (3) retopology if over budget, (4) UV unwrap (Phase 2), (5) apply PBR material (Phase 3). Never use Tripo3D output as-is.
**Warning signs:** Topology analysis shows F grade. UV analysis shows overlaps/stretching. Poly count exceeds game budget.

### Pitfall 6: Real-ESRGAN Binary Path and Model Files

**What goes wrong:** subprocess.run() fails with FileNotFoundError or "model not found" error.
**Why it happens:** The portable binary requires the `models/` directory to be in the correct relative path, and the binary itself must be on the system PATH or referenced with absolute path.
**How to avoid:** Bundle the binary and models together in `Tools/mcp-toolkit/bin/realesrgan-ncnn-vulkan/`. Use absolute path in subprocess call. Validate binary exists on first use and return clear error if missing.
**Warning signs:** FileNotFoundError. "ncnn model not found" in stderr. Zero-byte output file.

### Pitfall 7: Selected-to-Active Baking Context

**What goes wrong:** Baking from high-poly to low-poly produces black or garbled textures.
**Why it happens:** `use_selected_to_active=True` requires the HIGH-poly mesh to be SELECTED and the LOW-poly mesh to be the ACTIVE object. This is counterintuitive. Also, cage_extrusion and max_ray_distance must be set correctly for the ray cast to find the high-poly surface.
**How to avoid:** Explicitly set selection state before baking:
```python
bpy.ops.object.select_all(action='DESELECT')
high_poly.select_set(True)
low_poly.select_set(True)
bpy.context.view_layer.objects.active = low_poly
bpy.ops.object.bake(type='NORMAL', use_selected_to_active=True,
                     cage_extrusion=0.1, max_ray_distance=0.0)
```
**Warning signs:** Black baked texture. "No active object" error. Baked normals appear inverted or flat.

## Code Examples

### PBR Node Tree Construction (Blender Handler)

```python
# Source: Blender Python API docs + Blender 4.0 release notes
import bpy
import os

def handle_create_pbr_material(params: dict) -> dict:
    """Create full PBR material with image textures for each channel."""
    name = params.get("name", "PBR_Material")
    texture_dir = params.get("texture_dir")  # Directory with texture files
    texture_size = params.get("texture_size", 1024)

    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Clear default nodes
    nodes.clear()

    # Create output and Principled BSDF
    output_node = nodes.new("ShaderNodeOutputMaterial")
    output_node.location = (300, 0)

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    links.new(bsdf.outputs["BSDF"], output_node.inputs["Surface"])

    # Channel map: (file_suffix, bsdf_input_name, color_space, needs_normal_map_node)
    channels = {
        "albedo":    ("_albedo",    "Base Color",  "sRGB",      False),
        "metallic":  ("_metallic",  "Metallic",    "Non-Color", False),
        "roughness": ("_roughness", "Roughness",   "Non-Color", False),
        "normal":    ("_normal",    "Normal",      "Non-Color", True),
        "ao":        ("_ao",        None,          "Non-Color", False),  # Mixed via MixRGB
    }

    created_nodes = {}
    x_offset = -600

    for channel_name, (suffix, input_name, colorspace, needs_normal) in channels.items():
        # Create image texture node
        tex_node = nodes.new("ShaderNodeTexImage")
        tex_node.location = (x_offset, len(created_nodes) * -300)
        tex_node.label = channel_name.capitalize()

        # Load or create image
        if texture_dir:
            # Try common file extensions
            for ext in (".png", ".jpg", ".tga", ".exr"):
                filepath = os.path.join(texture_dir, f"{name}{suffix}{ext}")
                if os.path.exists(filepath):
                    tex_node.image = bpy.data.images.load(filepath)
                    break

        if tex_node.image is None:
            # Create blank image for baking target
            img = bpy.data.images.new(
                f"{name}{suffix}", texture_size, texture_size, alpha=False
            )
            tex_node.image = img

        # Set color space
        tex_node.image.colorspace_settings.name = colorspace

        # Connect to BSDF
        if needs_normal:
            normal_node = nodes.new("ShaderNodeNormalMap")
            normal_node.location = (x_offset + 300, len(created_nodes) * -300)
            links.new(tex_node.outputs["Color"], normal_node.inputs["Color"])
            links.new(normal_node.outputs["Normal"], bsdf.inputs["Normal"])
        elif input_name:
            links.new(tex_node.outputs["Color"], bsdf.inputs[input_name])

        created_nodes[channel_name] = tex_node.name

    return {
        "material_name": mat.name,
        "channels": created_nodes,
        "texture_size": texture_size,
    }
```

### Texture Baking (Blender Handler)

```python
# Source: Blender bpy.ops.object.bake docs + BakeSettings API
import bpy
from ._context import get_3d_context_override

def handle_bake_textures(params: dict) -> dict:
    """Bake texture maps from high-poly to low-poly or self-bake."""
    object_name = params.get("object_name")
    bake_type = params.get("bake_type", "NORMAL")  # NORMAL, AO, COMBINED, ROUGHNESS, EMIT
    source_name = params.get("source_object")  # High-poly for selected-to-active
    image_name = params.get("image_name")
    margin = params.get("margin", 16)
    cage_extrusion = params.get("cage_extrusion", 0.1)

    obj = bpy.data.objects.get(object_name)
    if not obj:
        raise ValueError(f"Object not found: {object_name}")

    # CRITICAL: Switch to Cycles for baking
    prev_engine = bpy.context.scene.render.engine
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.samples = params.get("samples", 32)

    try:
        # Set active image on the target material for bake output
        if image_name:
            for mat_slot in obj.material_slots:
                mat = mat_slot.material
                if mat and mat.use_nodes:
                    for node in mat.node_tree.nodes:
                        if node.type == 'TEX_IMAGE' and node.image and node.image.name == image_name:
                            node.select = True
                            mat.node_tree.nodes.active = node
                        else:
                            node.select = False

        # Setup selection for selected-to-active baking
        use_s2a = source_name is not None
        if use_s2a:
            source = bpy.data.objects.get(source_name)
            if not source:
                raise ValueError(f"Source object not found: {source_name}")
            bpy.ops.object.select_all(action='DESELECT')
            source.select_set(True)
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
        else:
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj

        override = get_3d_context_override()
        bake_kwargs = {
            "type": bake_type,
            "use_selected_to_active": use_s2a,
            "margin": margin,
            "margin_type": 'EXTEND',
        }
        if use_s2a:
            bake_kwargs["cage_extrusion"] = cage_extrusion
            bake_kwargs["max_ray_distance"] = 0.0  # No limit

        if bake_type == "NORMAL":
            bake_kwargs["normal_space"] = 'TANGENT'

        if override:
            with bpy.context.temp_override(**override):
                bpy.ops.object.bake(**bake_kwargs)
        else:
            bpy.ops.object.bake(**bake_kwargs)

        return {
            "baked": True,
            "bake_type": bake_type,
            "object": object_name,
            "source": source_name,
            "image": image_name,
        }
    finally:
        bpy.context.scene.render.engine = prev_engine
```

### LOD Chain Generation (Blender Handler)

```python
# Source: Blender Decimate Modifier docs + LOD generation patterns
import bpy

def handle_generate_lods(params: dict) -> dict:
    """Generate LOD chain using Decimate modifier."""
    object_name = params.get("object_name")
    ratios = params.get("ratios", [1.0, 0.5, 0.25, 0.1])  # LOD0-3

    obj = bpy.data.objects.get(object_name)
    if not obj or obj.type != 'MESH':
        raise ValueError(f"Mesh object not found: {object_name}")

    original_face_count = len(obj.data.polygons)
    lod_objects = []

    for i, ratio in enumerate(ratios):
        if ratio >= 1.0:
            # LOD0 is the original
            lod_name = f"{object_name}_LOD0"
            obj.name = lod_name
            obj.data.name = lod_name
            lod_objects.append({
                "name": lod_name,
                "lod_level": 0,
                "ratio": 1.0,
                "face_count": original_face_count,
            })
            continue

        # Duplicate for this LOD level
        new_obj = obj.copy()
        new_obj.data = obj.data.copy()
        bpy.context.collection.objects.link(new_obj)

        lod_name = f"{object_name}_LOD{i}"
        new_obj.name = lod_name
        new_obj.data.name = lod_name

        # Add and configure Decimate modifier
        mod = new_obj.modifiers.new(name="Decimate_LOD", type='DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = ratio
        mod.use_collapse_triangulate = False

        # Apply modifier
        override = {"object": new_obj, "active_object": new_obj}
        with bpy.context.temp_override(**override):
            bpy.ops.object.modifier_apply(modifier=mod.name)

        face_count = len(new_obj.data.polygons)
        lod_objects.append({
            "name": lod_name,
            "lod_level": i,
            "ratio": ratio,
            "face_count": face_count,
            "reduction": round((1 - face_count / original_face_count) * 100, 1),
        })

    return {
        "source": object_name,
        "lod_count": len(lod_objects),
        "lods": lod_objects,
    }
```

### Real-ESRGAN Texture Upscaling (MCP Server)

```python
# Source: realesrgan-ncnn-vulkan GitHub README
import subprocess
import tempfile
import os
from pathlib import Path

async def upscale_texture(
    input_path: str,
    scale: int = 4,
    model: str = "realesrgan-x4plus",
    esrgan_path: str | None = None,
) -> dict:
    """Upscale texture using Real-ESRGAN ncnn-vulkan binary."""
    if esrgan_path is None:
        esrgan_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "bin",
            "realesrgan-ncnn-vulkan", "realesrgan-ncnn-vulkan.exe"
        )

    if not os.path.isfile(esrgan_path):
        raise FileNotFoundError(
            f"Real-ESRGAN binary not found at {esrgan_path}. "
            "Download from https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases"
        )

    output_path = input_path.replace(".", f"_x{scale}.")

    cmd = [
        esrgan_path,
        "-i", input_path,
        "-o", output_path,
        "-s", str(scale),
        "-n", model,
        "-f", "png",
    ]

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=120
    )

    if result.returncode != 0:
        raise RuntimeError(f"Real-ESRGAN failed: {result.stderr}")

    return {
        "input": input_path,
        "output": output_path,
        "scale": scale,
        "model": model,
        "success": os.path.isfile(output_path),
    }
```

### Concept Art Generation (MCP Server)

```python
# Source: fal-client PyPI docs + fal.ai FLUX model API
import fal_client
import aiohttp
import os

async def generate_concept_art(
    prompt: str,
    style: str = "concept art",
    width: int = 1024,
    height: int = 1024,
    output_dir: str = "/tmp",
) -> dict:
    """Generate concept art using fal.ai FLUX model."""
    full_prompt = f"{style}, {prompt}, high quality, detailed, professional"

    result = await fal_client.run_async(
        "fal-ai/flux/dev",
        arguments={
            "prompt": full_prompt,
            "image_size": {"width": width, "height": height},
            "num_images": 1,
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
        },
    )

    # Download the generated image
    image_url = result["images"][0]["url"]
    filename = f"concept_{prompt[:30].replace(' ', '_')}.png"
    filepath = os.path.join(output_dir, filename)

    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as resp:
            with open(filepath, "wb") as f:
                f.write(await resp.read())

    return {
        "filepath": filepath,
        "prompt": full_prompt,
        "width": width,
        "height": height,
    }
```

### Color Palette Extraction (MCP Server)

```python
# Source: Pillow docs Image.quantize()
from PIL import Image
import io

def extract_color_palette(
    image_path: str,
    num_colors: int = 8,
    swatch_size: int = 64,
) -> dict:
    """Extract dominant colors from an image and generate a swatch."""
    img = Image.open(image_path).convert("RGB")

    # Quantize to N colors
    quantized = img.quantize(colors=num_colors, method=Image.Quantize.MEDIANCUT)
    palette_data = quantized.getpalette()

    # Extract RGB triples
    colors = []
    for i in range(num_colors):
        r, g, b = palette_data[i*3], palette_data[i*3+1], palette_data[i*3+2]
        colors.append({
            "rgb": [r, g, b],
            "hex": f"#{r:02x}{g:02x}{b:02x}",
        })

    # Generate swatch image
    swatch_width = swatch_size * num_colors
    swatch = Image.new("RGB", (swatch_width, swatch_size))
    for i, color in enumerate(colors):
        for x in range(swatch_size):
            for y in range(swatch_size):
                swatch.putpixel((i * swatch_size + x, y), tuple(color["rgb"]))

    buf = io.BytesIO()
    swatch.save(buf, format="PNG")

    return {
        "colors": colors,
        "num_colors": num_colors,
        "swatch_bytes": buf.getvalue(),
    }
```

### Procedural Wear Map via Curvature (Blender Handler)

```python
# Source: bmesh docs + edge angle analysis for curvature approximation
import bpy
import bmesh
import math

def handle_generate_wear_map(params: dict) -> dict:
    """Generate procedural wear/damage map from mesh curvature."""
    obj_name = params.get("object_name")
    texture_size = params.get("texture_size", 1024)

    obj = bpy.data.objects.get(obj_name)
    if not obj or obj.type != 'MESH':
        raise ValueError(f"Mesh object not found: {obj_name}")

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    # Compute per-vertex curvature via edge angle analysis
    # Convex edges (positive angle) -> worn/light areas
    # Concave edges (negative angle) -> dirty/dark areas
    # High curvature -> chipped/damaged
    curvature = {}
    for vert in bm.verts:
        angles = []
        for edge in vert.link_edges:
            if len(edge.link_faces) == 2:
                f1, f2 = edge.link_faces
                # Angle between face normals
                angle = f1.normal.angle(f2.normal)
                # Determine convexity: cross product with edge direction
                edge_vec = edge.other_vert(vert).co - vert.co
                cross = f1.normal.cross(f2.normal)
                sign = 1.0 if cross.dot(edge_vec) > 0 else -1.0
                angles.append(angle * sign)

        if angles:
            avg_curvature = sum(angles) / len(angles)
            curvature[vert.index] = avg_curvature
        else:
            curvature[vert.index] = 0.0

    # Store as vertex color layer for baking
    if "WearMap" not in bm.loops.layers.color:
        color_layer = bm.loops.layers.color.new("WearMap")
    else:
        color_layer = bm.loops.layers.color["WearMap"]

    # Normalize curvature to 0-1 range
    min_c = min(curvature.values()) if curvature else 0
    max_c = max(curvature.values()) if curvature else 1
    range_c = max_c - min_c if max_c != min_c else 1.0

    for face in bm.faces:
        for loop in face.loops:
            c = (curvature[loop.vert.index] - min_c) / range_c
            # Convex = bright (worn), concave = dark (dirty)
            loop[color_layer] = (c, c, c, 1.0)

    bm.to_mesh(obj.data)
    bm.free()

    return {
        "object": obj_name,
        "vertex_color_layer": "WearMap",
        "min_curvature": min_c,
        "max_curvature": max_c,
        "ready_to_bake": True,
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Substance Painter for PBR textures | AI-generated PBR (CHORD, fal.ai) + Blender node trees | 2024-2025 | Faster iteration; lower quality ceiling but sufficient for rapid prototyping |
| Manual 3D modeling | AI 3D generation (Tripo3D v2.5+) + cleanup pipeline | 2024-2025 | Tripo produces usable base meshes in ~30s; still needs retopo + UV + material |
| Photoshop texture editing | Pillow + AI inpainting (FLUX) | 2024-2025 | Programmatic, scriptable, integrable into pipeline |
| Manual LOD creation | Blender Decimate modifier automation | Always available | Decimate with UV seam preservation produces acceptable LODs |
| Topaz/Waifu2x upscaling | Real-ESRGAN (ncnn-vulkan) | 2022-2023 | Better quality, faster, portable binary, no CUDA needed |
| Principled BSDF pre-4.0 socket names | Blender 4.0+ renamed 6 sockets to align with OpenPBR | Blender 4.0 (2023-11) | MUST use new names or version-aware lookup |

**Deprecated/outdated:**
- `bgl` module: Removed in Blender 4.0. Use `gpu` module for any GPU operations.
- Principled BSDF old input names ("Specular", "Subsurface", "Transmission", "Coat", "Sheen", "Emission"): Renamed in Blender 4.0.
- SSE transport for MCP: Deprecated in spec. Use stdio.

## Open Questions

1. **Tripo3D output format quality**
   - What we know: Tripo3D outputs GLB with PBR textures. The SDK supports downloading model, base_model, and pbr_model variants.
   - What's unclear: What quality level are the PBR textures? Are they 1K, 2K, 4K? Do they need upscaling? Is the GLB mesh always manifold?
   - Recommendation: Import a test model, run mesh analysis and texture validation, document the typical quality. Build the cleanup pipeline to handle worst-case.

2. **fal.ai vs direct FLUX for texture inpainting**
   - What we know: fal.ai supports FLUX.1 [dev] with image-to-image mode. It accepts masks for inpainting.
   - What's unclear: Is the inpainting quality sufficient for texture detail work (belt buckles, armor trim)? What resolution inputs does it accept?
   - Recommendation: Prototype with fal.ai FLUX inpainting. If quality is insufficient, explore Stability AI or ComfyUI as alternatives. Keep the interface abstract so the backend can be swapped.

3. **Real-ESRGAN binary distribution**
   - What we know: The ncnn-vulkan binary is ~30MB with models. It can be downloaded from GitHub releases.
   - What's unclear: Should we bundle it in the repo or download on first use? License implications?
   - Recommendation: Do NOT bundle in git (binary + models = ~100MB). Download on first use to `Tools/mcp-toolkit/bin/` with a setup/download command. The MIT license permits redistribution.

4. **Batch processing parallelism**
   - What we know: Blender is single-threaded for bpy operations. Tripo3D API calls are async.
   - What's unclear: Can we parallelize Tripo3D generation while Blender processes previous models? Or must everything be serial?
   - Recommendation: Tripo3D generation (HTTP) can be parallelized. Blender processing must be serial (one command at a time via queue). Pipeline: submit N Tripo3D tasks in parallel, process completed models through Blender sequentially.

5. **Texture seam blending algorithm**
   - What we know: Pillow can blur and composite. UV seam edges can be detected from bmesh.
   - What's unclear: The exact pixel-level algorithm for professional seam blending. Simple Gaussian blur on seam edges may leave artifacts.
   - Recommendation: Start with distance-weighted Gaussian blur along seam edges (3-8 pixel radius). If quality is insufficient, implement Poisson blending or use Blender's texture paint mode with clone brush as fallback.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio |
| Config file | `Tools/mcp-toolkit/pyproject.toml` (implicit) |
| Quick run command | `cd Tools/mcp-toolkit && uv run pytest tests/ -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && uv run pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEX-01 | PBR node tree has correct nodes/links for all channels | unit (mock bpy) | `uv run pytest tests/test_texture_pbr.py -x` | No -- Wave 0 |
| TEX-02 | UV mask generation produces correct L-mode image from polygon data | unit | `uv run pytest tests/test_texture_ops.py::test_mask_generation -x` | No -- Wave 0 |
| TEX-04 | HSV adjustment modifies only masked pixels | unit | `uv run pytest tests/test_texture_ops.py::test_hsv_adjust -x` | No -- Wave 0 |
| TEX-05 | Seam blending produces smooth transition along seam edges | unit | `uv run pytest tests/test_texture_ops.py::test_seam_blend -x` | No -- Wave 0 |
| TEX-08 | Real-ESRGAN subprocess wrapper returns upscaled image path | unit (mock subprocess) | `uv run pytest tests/test_esrgan_runner.py -x` | No -- Wave 0 |
| TEX-09 | Tileable texture edges match when tiled 2x2 | unit | `uv run pytest tests/test_texture_ops.py::test_make_tileable -x` | No -- Wave 0 |
| TEX-10 | Texture validation detects non-power-of-two, wrong format, low coverage | unit | `uv run pytest tests/test_texture_validation.py -x` | No -- Wave 0 |
| PIPE-01 | Tripo3D client creates task, polls, downloads model | unit (mock HTTP) | `uv run pytest tests/test_tripo_client.py -x` | No -- Wave 0 |
| PIPE-03 | LOD generation produces correct number of levels with decreasing face counts | unit (mock bpy) | `uv run pytest tests/test_pipeline_lod.py -x` | No -- Wave 0 |
| PIPE-05 | Asset metadata JSON contains required fields | unit | `uv run pytest tests/test_asset_metadata.py -x` | No -- Wave 0 |
| PIPE-07 | Asset catalog SQLite insert/query/filter works | unit | `uv run pytest tests/test_asset_catalog.py -x` | No -- Wave 0 |
| CONC-01 | Concept art generation returns image path | unit (mock fal_client) | `uv run pytest tests/test_concept_art.py -x` | No -- Wave 0 |
| CONC-02 | Color palette extraction returns N colors with hex values | unit | `uv run pytest tests/test_concept_art.py::test_extract_palette -x` | No -- Wave 0 |
| TEX-03 | AI inpainting produces modified image in masked region | manual-only | N/A (requires live fal.ai API) | N/A |
| TEX-06 | Wear map has bright values on convex edges | manual-only | N/A (requires Blender with mesh) | N/A |
| TEX-07 | Baked normal map matches high-poly surface detail | manual-only | N/A (requires Blender with Cycles) | N/A |
| PIPE-02 | Cleanup pipeline produces game-ready mesh from raw AI model | integration | N/A (requires Blender + Tripo3D) | N/A |
| PIPE-04 | Export validation detects scale/orientation issues | unit | `uv run pytest tests/test_export_validation.py -x` | No -- Wave 0 |
| PIPE-06 | Batch processing completes all items with progress | integration | N/A (requires Blender) | N/A |
| CONC-03 | Style board contains images + palette + annotations | unit | `uv run pytest tests/test_concept_art.py::test_style_board -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && uv run pytest tests/ -x -q`
- **Per wave merge:** `cd Tools/mcp-toolkit && uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_texture_ops.py` -- covers TEX-02, TEX-04, TEX-05, TEX-09 (Pillow texture operations)
- [ ] `tests/test_texture_validation.py` -- covers TEX-10
- [ ] `tests/test_texture_pbr.py` -- covers TEX-01 (mock bpy node tree)
- [ ] `tests/test_esrgan_runner.py` -- covers TEX-08 (mock subprocess)
- [ ] `tests/test_tripo_client.py` -- covers PIPE-01 (mock HTTP)
- [ ] `tests/test_pipeline_lod.py` -- covers PIPE-03 (mock bpy)
- [ ] `tests/test_asset_metadata.py` -- covers PIPE-05
- [ ] `tests/test_asset_catalog.py` -- covers PIPE-07
- [ ] `tests/test_export_validation.py` -- covers PIPE-04
- [ ] `tests/test_concept_art.py` -- covers CONC-01, CONC-02, CONC-03 (mock fal_client)

## Sources

### Primary (HIGH confidence)
- [Blender BakeSettings API](https://docs.blender.org/api/current/bpy.types.BakeSettings.html) -- bake types, settings, pass filters
- [Blender bpy.ops.object.bake](https://docs.blender.org/api/current/bpy.ops.object.html) -- bake operator signature and parameters
- [Blender 4.0 Python API Changes](https://developer.blender.org/docs/release_notes/4.0/python_api/) -- Principled BSDF socket renaming
- [Blender Principled BSDF Manual](https://docs.blender.org/manual/en/latest/render/shader_nodes/shader/principled.html) -- input descriptions, OpenPBR alignment
- [tripo3d Python SDK v0.3.12](https://pypi.org/project/tripo3d/) -- Python SDK, async API, task workflow
- [tripo3d SDK API Reference](https://github.com/VAST-AI-Research/tripo-python-sdk/blob/master/docs/API.md) -- TripoClient methods, parameters, return types
- [Tripo3D API Quick Start](https://platform.tripo3d.ai/docs/quick-start) -- REST endpoints, auth, task creation
- [Real-ESRGAN ncnn-vulkan](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan) -- CLI binary, arguments, models
- [Pillow Image.composite()](https://pillow.readthedocs.io/en/stable/reference/Image.html) -- mask-based image compositing
- [fal-client PyPI](https://pypi.org/project/fal-client/) -- Python SDK for fal.ai models
- [Blender Decimate Modifier Manual](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/decimate.html) -- ratio, UV seam preservation

### Secondary (MEDIUM confidence)
- [Apidog: Tripo 3D API Guide](https://apidog.com/blog/how-to-use-tripo-3d-api/) -- REST API workflow, endpoints, JSON examples
- [Blender Artists: Bake Sequence](https://blenderartists.org/t/b3-2-automatic-bake-sequence/1416420) -- Python bake automation patterns
- [CG-Wire: Blender Shaders 2026](https://blog.cg-wire.com/blender-shaders-explained/) -- Principled BSDF scripting examples
- [colorsys Python stdlib](https://docs.python.org/3/library/colorsys.html) -- HSV color space conversion

### Tertiary (LOW confidence)
- Seam blending algorithm (Gaussian blur on seam edges) -- based on general image processing knowledge, not verified against a specific implementation
- Wear map curvature approximation (edge angle analysis) -- mathematical approach is sound but production quality needs validation on real game meshes
- fal.ai FLUX inpainting quality for game textures -- untested, may need alternative

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- tripo3d SDK, fal-client, Pillow, Real-ESRGAN all verified against official sources
- Architecture (tool split): HIGH -- follows compound tool pattern from Phases 1-2, stays within token budget
- Blender texture baking: HIGH -- bpy.ops.object.bake API documented, Cycles requirement verified
- PBR node trees: HIGH -- Principled BSDF inputs verified including 4.0+ renaming
- LOD generation: HIGH -- Decimate modifier well-documented, UV preservation option confirmed
- Tripo3D integration: HIGH -- SDK v0.3.12 verified, async workflow documented
- Real-ESRGAN integration: MEDIUM -- binary exists and CLI documented, but bundling/distribution strategy unverified
- Surgical texture editing: MEDIUM -- Pillow masking pattern is sound, but pixel-level quality for game textures needs validation
- Seam blending: LOW -- algorithm approach is reasonable but no production-tested implementation found
- Concept art generation: MEDIUM -- fal.ai FLUX works, but quality for game concept art is unverified

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable domain for Blender/Pillow; watch for Tripo3D API version changes and fal.ai model updates)
