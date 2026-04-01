# Phase 35: Multi-backend AI Integration - Research

**Researched:** 2026-03-31
**Domain:** Tripo AI pipeline, GLB texture extraction, PBR post-processing, art style validation
**Confidence:** HIGH (all findings from direct codebase inspection)

## Summary

Phase 35 closes the gap between Tripo's raw GLB output and a Unity-ready game asset. The current pipeline downloads up to 4 variants from Tripo Studio, imports them into Blender in a grid, and tells the user to manually pick one and run `asset_pipeline action=cleanup`. That cleanup wires repair -> retopo -> UV -> PBR material, but critically it CREATES a blank new PBR material rather than extracting the textures already embedded in the GLB. The bug noted in STATE.md ("Tripo pipeline overwrites embedded textures with blank images during cleanup") is caused by `pipeline_runner.cleanup_ai_model` calling `texture_create_pbr` unconditionally, which creates a new blank node tree and discards Tripo's painted albedo/normal/roughness/metallic.

Three concrete gaps remain:
1. No GLB texture extraction — embedded maps are discarded rather than saved to disk as standalone PNGs
2. No automated de-lighting applied to the extracted albedo before using it
3. No automated weathering overlay on top of extracted textures; the weathering system (`weathering.py`) exists and is robust but is not wired into the post-generation pipeline
4. Art style validation (`palette_validator.py`, `delight.py`) exists but is not wired into the Tripo pipeline auto-flow
5. Variant quality scoring and auto-selection is absent — the user picks manually

**Primary recommendation:** Build a `glb_texture_extractor` shared module (MCP-side, using `pygltflib` or raw struct parsing), wire it into `pipeline_runner.cleanup_ai_model` so extracted textures are loaded into the Blender PBR node tree instead of a blank material, then extend the pipeline with de-lighting, weathering overlay, palette validation, and quality-gate scoring.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pygltflib | 1.16.x | Parse GLB JSON + binary chunks, extract image buffers | Pure Python, no Blender dependency, already installable alongside other deps |
| Pillow | 10.x | Save extracted image buffers to PNG/JPG | Already used in `delight.py` and `palette_validator.py` |
| numpy | 1.26.x | Pixel-level analysis for quality scoring | Already used in `delight.py` and `palette_validator.py` |
| struct (stdlib) | — | Read GLB binary chunk header as fallback | Already used in `pipeline_runner._validate_glb` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| bpy (Blender handler) | 4.x | Load extracted texture PNGs into image nodes, pack into .blend | Called from blender_addon handler side via send_command |
| httpx | 0.27.x | Download Tripo variants (already in use) | Already wired in tripo_studio_client.py |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pygltflib | Raw struct + json | pygltflib is cleaner and battle-tested; raw struct already works for header validation but is cumbersome for multi-image buffers |
| Pillow for extraction | bpy.ops.image.save | bpy runs inside Blender process; extraction must happen MCP-side before import so textures are on disk before Blender opens the mesh |

**Installation:**
```bash
pip install pygltflib
```

**Version verification:** pygltflib 1.16.x is the current stable release as of 2026-03 (confirmed via PyPI). Pillow and numpy already installed.

## Architecture Patterns

### Recommended Project Structure
```
src/veilbreakers_mcp/shared/
├── glb_texture_extractor.py   # NEW: extract PBR maps from GLB binary
├── tripo_post_processor.py    # NEW: orchestrate extract -> delight -> validate -> score
├── delight.py                 # EXISTS: de-light albedo (Gaussian luminance)
├── palette_validator.py       # EXISTS: validate VB dark fantasy palette
├── pipeline_runner.py         # MODIFY: wire in texture extraction before PBR create
blender_addon/handlers/
├── weathering.py              # EXISTS: edge wear, dirt, moss overlays (vertex color)
├── texture.py                 # EXISTS: PBR node tree builder
```

### Pattern 1: GLB Texture Extraction (MCP-side, before Blender import)
**What:** Parse the GLB binary to extract embedded images into named PNG files on disk before sending the model to Blender. Tripo's PBR GLB embeds albedo, normal, roughness/metallic (sometimes ORM-packed), and AO as base64 or binary-buffered images in the `images` array.
**When to use:** Immediately after download, before `bpy.ops.import_scene.gltf`

**GLB structure for Tripo PBR output:**
```
[GLB Header: magic + version + length]
[JSON Chunk: glTF JSON descriptor]
[BIN Chunk: all binary data (mesh + image buffers)]

glTF JSON layout:
  images: [{uri: null, mimeType: "image/png", bufferView: N}, ...]
  materials[0].pbrMetallicRoughness:
    baseColorTexture.index -> textures[i].source -> images[j]
    metallicRoughnessTexture.index -> textures[i].source -> images[j]
  materials[0].normalTexture.index -> ...
  materials[0].occlusionTexture.index -> ...
```

**Extract algorithm:**
```python
# Source: direct GLB spec + pygltflib pattern
import pygltflib, struct, json

def extract_glb_textures(glb_path: str, out_dir: str) -> dict[str, str]:
    """Returns {channel_name: file_path} for albedo/normal/roughness/metallic/ao."""
    gltf = pygltflib.GLTF2().load(glb_path)
    blob = gltf.binary_blob()  # full BIN chunk bytes

    channel_map = {}
    if not gltf.materials:
        return channel_map

    mat = gltf.materials[0]
    pbr = mat.pbrMetallicRoughness

    def save_image(tex_index: int, name: str) -> str | None:
        if tex_index is None:
            return None
        tex = gltf.textures[tex_index]
        img = gltf.images[tex.source]
        bv = gltf.bufferViews[img.bufferView]
        data = blob[bv.byteOffset: bv.byteOffset + bv.byteLength]
        ext = ".png" if img.mimeType == "image/png" else ".jpg"
        path = os.path.join(out_dir, f"{name}{ext}")
        Path(path).write_bytes(data)
        return path

    if pbr and pbr.baseColorTexture:
        p = save_image(pbr.baseColorTexture.index, "albedo")
        if p: channel_map["albedo"] = p
    if pbr and pbr.metallicRoughnessTexture:
        # ORM-packed: R=occlusion, G=roughness, B=metallic
        p = save_image(pbr.metallicRoughnessTexture.index, "orm")
        if p: channel_map["orm"] = p
    if mat.normalTexture:
        p = save_image(mat.normalTexture.index, "normal")
        if p: channel_map["normal"] = p
    if mat.occlusionTexture:
        idx = mat.occlusionTexture.index
        if idx != (pbr.metallicRoughnessTexture.index if pbr and pbr.metallicRoughnessTexture else None):
            p = save_image(idx, "ao")
            if p: channel_map["ao"] = p
    return channel_map
```

### Pattern 2: Tripo Post-Processor Orchestration
**What:** Single module that runs the complete chain after Tripo download.
**When to use:** After `_poll_and_download_variants` returns verified models, before Blender import.

```python
# tripo_post_processor.py
async def post_process_tripo_model(glb_path: str, out_dir: str, asset_type: str = "prop") -> dict:
    """Extract textures, de-light albedo, validate palette, return channel map + scores."""
    texture_dir = Path(out_dir) / "textures"
    texture_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Extract
    channels = extract_glb_textures(glb_path, str(texture_dir))

    # Step 2: De-light albedo
    if "albedo" in channels:
        delit_path = str(texture_dir / "albedo_delit.png")
        delight_result = delight_albedo(channels["albedo"], delit_path)
        if delight_result.get("correction_applied"):
            channels["albedo_delit"] = delit_path

    # Step 3: Validate palette
    albedo_for_validation = channels.get("albedo_delit") or channels.get("albedo")
    palette_result = {}
    if albedo_for_validation:
        palette_result = validate_palette(albedo_for_validation)

    # Step 4: Score (poly count comes later from Blender; store channel completeness)
    score = _score_channels(channels)

    return {
        "channels": channels,
        "palette_validation": palette_result,
        "channel_score": score,
        "texture_dir": str(texture_dir),
    }
```

### Pattern 3: Blender-side texture wiring after extraction
**What:** After post-processing, import the GLB into Blender, then load extracted PNGs into the material node tree.
**When to use:** In `blender_server.py` generate_3d handler, after post-processing step.

```python
# Blender execute_code snippet to wire extracted textures
code = """
import bpy
mat = bpy.data.objects['{obj}'].active_material
nodes = mat.node_tree.nodes
links = mat.node_tree.links

# Load albedo
img = bpy.data.images.load('{albedo_path}')
img.colorspace_settings.name = 'sRGB'
tex_node = nodes.new('ShaderNodeTexImage')
tex_node.image = img
bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
# (repeat for normal, ORM splits)
"""
```

### Anti-Patterns to Avoid
- **Calling `texture_create_pbr` before extracting GLB textures:** This creates blank images that overwrite Tripo's painted maps. Always extract first, then load extracted maps into the node tree.
- **Splitting ORM channels in Python before Blender import:** Do channel splitting (ORM -> R=AO, G=roughness, B=metallic) inside Blender using Separate RGB nodes in the shader graph, not as separate image files — reduces disk I/O and is the standard game engine approach.
- **De-lighting normal maps or roughness maps:** Apply `delight_albedo` only to the albedo/base color channel. Normal and roughness maps do not have baked lighting.
- **Running palette validation on ORM maps:** The palette validator is designed for albedo (RGB, sRGB). Running it on a packed ORM map will produce meaningless results.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| GLB binary parsing | Custom struct reader | pygltflib | GLB spec has alignment padding, buffer view offsets, base64 vs binary fallbacks — edge cases that pygltflib handles |
| Image format detection | Manual magic bytes check | Pillow Image.open + img.format | Tripo emits both JPEG and PNG depending on content; Pillow detects correctly |
| ORM channel splitting | Numpy slice + save | Blender Separate RGB node in shader | Splitting on disk doubles storage; in-shader splitting is zero-cost and is Unity's expected workflow |
| Roughness variance check | Custom std-dev | `validate_roughness_map` in palette_validator.py | Already exists and tested |
| Albedo de-lighting | Custom luminance | `delight_albedo` in delight.py | Already exists, tested, configurable strength |
| Palette validation | Custom HSV check | `validate_palette` in palette_validator.py | Already exists, tested, VB rules defined |

**Key insight:** The extraction gap is the only missing piece — all downstream processing (delight, validate, weathering, quality gate) already exists as tested modules. Phase 35 is primarily about wiring, not new algorithms.

## Common Pitfalls

### Pitfall 1: GLB image buffer offset alignment
**What goes wrong:** GLB binary chunk requires 4-byte alignment padding. A buffer view's `byteOffset + byteLength` may not equal the next buffer view's `byteOffset` — there are padding bytes in between. Reading raw bytes without respecting `byteOffset` + `byteLength` from the `bufferViews` array produces corrupt image data.
**Why it happens:** The GLB BIN chunk is a single flat byte array with all buffers concatenated. Each bufferView has `byteOffset` and `byteLength` that slice it correctly.
**How to avoid:** Always use `bv.byteOffset` and `bv.byteLength` from the parsed `bufferViews` array to slice the binary blob. Do not assume images are contiguous.
**Warning signs:** Corrupt PNG headers, Pillow raises `PIL.UnidentifiedImageError` on extracted files.

### Pitfall 2: Tripo ORM packing convention
**What goes wrong:** Assuming separate roughness/metallic textures exist. Tripo packages metallic and roughness into a single ORM (occlusion/roughness/metallic) image where R=AO, G=roughness, B=metallic.
**Why it happens:** glTF 2.0 spec defines `metallicRoughnessTexture` as a packed texture where G=roughness and B=metallic. Tripo follows this spec.
**How to avoid:** When extracting, save the combined ORM and note it in `channel_map["orm"]`. Use Blender's Separate RGB shader node to route channels at import time.
**Warning signs:** "metallic" texture appears uniformly gray or solid blue if incorrectly treated as separate.

### Pitfall 3: cleanup_ai_model overwrites extracted textures
**What goes wrong:** Calling `cleanup_ai_model` on a Tripo-imported object calls `texture_create_pbr`, which creates a brand-new Principled BSDF with no image inputs — discarding any textures Blender loaded from the GLB import.
**Why it happens:** `cleanup_ai_model` was designed for procedural geometry, not pre-textured AI imports.
**How to avoid:** Add an `has_extracted_textures: bool` parameter to `cleanup_ai_model`. When True, skip the `texture_create_pbr` step and instead wire extracted texture paths into the existing material node tree.
**Warning signs:** Object renders as gray/white after cleanup despite Tripo generating visible textures.

### Pitfall 4: Weathering vertex colors conflict with texture UVs
**What goes wrong:** `weathering.py` writes per-vertex color layers. If the mesh's UV layout changes during retopology (step 3 of cleanup), the vertex colors are baked to wrong positions.
**Why it happens:** Retopology remeshes the geometry, reassigning vertex indices. Vertex colors from the original mesh do not transfer.
**How to avoid:** Apply weathering AFTER retopology and UV unwrap steps, not before. The pipeline order must be: extract textures -> import -> repair -> retopo -> UV -> wire textures -> weathering overlay.
**Warning signs:** Weathering appears as random noise rather than edge-aligned wear patterns.

### Pitfall 5: 4-variant timeout budget
**What goes wrong:** `_poll_and_download_variants` polls all 4 task IDs sequentially with a 300s total timeout. If variants 1+2 are slow, variants 3+4 may time out.
**Why it happens:** The current implementation uses one shared timeout counter across all variants.
**How to avoid:** Per-variant timeout (e.g., 240s each), with graceful partial success. The quality gate can select the best from 2+ variants even if all 4 don't complete.
**Warning signs:** `"downloaded": 1` in result when 4 were expected.

## Code Examples

### GLB texture count check (using existing _validate_glb pattern)
```python
# Source: pipeline_runner.py _validate_glb — existing pattern to extend
with open(filepath, "rb") as f:
    header = f.read(12)
    magic = struct.unpack("<I", header[0:4])[0]
    # ... read JSON chunk ...
    gltf = json.loads(json_data)
    image_count = len(gltf.get("images", []))
    material_count = len(gltf.get("materials", []))
```

### Palette validation call (existing API)
```python
# Source: palette_validator.py validate_palette
from veilbreakers_mcp.shared.palette_validator import validate_palette, validate_roughness_map

result = validate_palette("albedo_delit.png")
# result: {passed: bool, issues: [...], stats: {mean_saturation, cool_ratio, ...}}

roughness_result = validate_roughness_map("orm.png")  # checks G channel variance
```

### De-lighting call (existing API)
```python
# Source: delight.py delight_albedo
from veilbreakers_mcp.shared.delight import delight_albedo

result = delight_albedo(
    image_path="albedo.png",
    output_path="albedo_delit.png",
    blur_radius_pct=0.12,
    strength=0.75,
)
# result: {correction_applied: bool, mean_luminance_before, mean_luminance_after, ...}
```

### Weathering trigger via send_command (existing pattern)
```python
# Source: blender_server.py compose_interior handler pattern
await blender.send_command("apply_weathering", {
    "object_name": obj_name,
    "preset": "medium",  # light/medium/heavy/ancient
})
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single Tripo API key (tripo3d SDK) | TripoStudioClient (JWT + session cookie, subscription credits) | v6.0 | Up to 4 variants per request; no per-request credit cost |
| Manual post-processing guidance | Auto-import grid in Blender + next_steps instructions | v6.0 | Reduces manual steps but extraction still missing |
| Blank PBR material on cleanup | Needs fix this phase | — | Root cause of "blank textures" STATE.md bug |

**Deprecated/outdated:**
- `TripoGenerator` (tripo3d SDK client): Still present as fallback when no studio cookie/token, but studio client is preferred for variant generation.
- `cleanup_ai_model` without texture awareness: Current implementation discards GLB-embedded textures; must be extended this phase.

## Open Questions

1. **Does Tripo always produce ORM-packed textures or sometimes separate?**
   - What we know: glTF 2.0 spec uses `metallicRoughnessTexture` for combined G=roughness/B=metallic. Tripo's PBR output follows the spec.
   - What's unclear: Whether Tripo ever emits an emissive or opacity map in addition to ORM.
   - Recommendation: Build the extractor to handle emissive/opacity maps gracefully (skip if absent), based on presence in `material.emissiveTexture` / `material.alphaMode`.

2. **Quality scoring: what constitutes "best" variant automatically?**
   - What we know: Variants differ in topology, UV coverage, texture quality. No automated selection exists today.
   - What's unclear: Whether vertex count, UV coverage, or texture variance is the best proxy for "quality."
   - Recommendation: Score = weighted sum of (1 - retopo_needed_ratio) + uv_coverage + palette_passed + texture_channel_count. Contact sheet visual review by Claude is the final arbiter; auto-score just filters obvious failures.

3. **Weathering overlay on AI textures vs replacing them:**
   - What we know: MESH-12 says "Smart material overlay applies weathering on TOP of Tripo's extracted textures — AI textures enhanced, not replaced."
   - What's unclear: Weathering.py writes vertex color layers, which modulate base color in Blender but require a Color Attribute -> Mix Shader node setup to composite over texture.
   - Recommendation: Add a `mix_weathering_over_texture` Blender handler that creates the correct Color Attribute -> Mix Color node between the albedo texture and the BSDF Base Color input.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pygltflib | GLB texture extraction | Check at import time | 1.16.x | Raw struct reader (slower, more fragile) |
| Pillow | Image save/load | Already installed | 10.x | — |
| numpy | Palette/delight analysis | Already installed | 1.26.x | — |
| Blender TCP bridge | Texture wiring in scene | Already running in dev | 4.x | — |
| Tripo Studio session | Variant generation | Configured via env | v3.0 client | API key fallback |

**Missing dependencies with no fallback:**
- None that block core functionality. pygltflib can be soft-fallback to struct reader.

**Missing dependencies with fallback:**
- `pygltflib`: If not installed, fall back to existing `_validate_glb` struct-reader approach plus direct binary slice with bufferView offsets.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | Tools/mcp-toolkit/pyproject.toml |
| Quick run command | `cd Tools/mcp-toolkit && pytest tests/test_glb_texture_extractor.py -x` |
| Full suite command | `cd Tools/mcp-toolkit && pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MESH-12 | GLB texture extraction produces albedo/normal/orm on disk | unit | `pytest tests/test_glb_texture_extractor.py -x` | Wave 0 |
| MESH-12 | De-lighted albedo has lower mean luminance variance | unit | `pytest tests/test_tripo_post_processor.py::test_delight_applied -x` | Wave 0 |
| MESH-12 | Palette validation flags over-saturated AI textures | unit | `pytest tests/test_tripo_post_processor.py::test_palette_validation -x` | Wave 0 |
| MESH-12 | cleanup_ai_model preserves extracted textures (not blank) | unit | `pytest tests/test_pipeline_runner.py::test_cleanup_preserves_textures -x` | Wave 0 |
| MESH-12 | Weathering composites over texture (not replaces) | unit | `pytest tests/test_weathering_overlay.py -x` | Wave 0 |
| MESH-12 | 4 variants imported in grid, quality scored | unit | `pytest tests/test_tripo_post_processor.py::test_variant_scoring -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** quick test file for that task's module
- **Per wave merge:** `cd Tools/mcp-toolkit && pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_glb_texture_extractor.py` — covers GLB extraction logic (REQ MESH-12)
- [ ] `tests/test_tripo_post_processor.py` — covers post-processing chain (REQ MESH-12)
- [ ] `tests/test_weathering_overlay.py` — covers mix-over-texture node wiring (REQ MESH-12)
- [ ] `src/veilbreakers_mcp/shared/glb_texture_extractor.py` — new module
- [ ] `src/veilbreakers_mcp/shared/tripo_post_processor.py` — new module

## Sources

### Primary (HIGH confidence)
- Direct inspection: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/tripo_studio_client.py` — variant download, polling
- Direct inspection: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/pipeline_runner.py` — cleanup_ai_model flow, texture_create_pbr call
- Direct inspection: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/delight.py` — delight API confirmed
- Direct inspection: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/palette_validator.py` — validate_palette API confirmed
- Direct inspection: `Tools/mcp-toolkit/blender_addon/handlers/weathering.py` — weathering presets confirmed
- Direct inspection: `.planning/STATE.md` — "Tripo pipeline overwrites embedded textures with blank images during cleanup" bug confirmed
- Direct inspection: `.planning/ROADMAP.md` Phase 35 success criteria (5 criteria verified)
- Direct inspection: `.planning/REQUIREMENTS.md` MESH-12 requirement text

### Secondary (MEDIUM confidence)
- glTF 2.0 spec knowledge: ORM packing convention (G=roughness, B=metallic) — standard spec, confirmed by inspecting tripo_studio_client pbr_model download path

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries either already installed or trivially installable
- Architecture: HIGH — gaps and existing code directly inspected; patterns derived from actual code
- Pitfalls: HIGH — blank texture bug explicitly documented in STATE.md; ORM convention from spec
- Extraction algorithm: MEDIUM — pygltflib API pattern is standard; exact Tripo image layout to be confirmed against a real downloaded GLB at implementation time

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (stable domain; Tripo API changes could affect variant structure)
