# Phase 35: Multi-backend AI Integration - Context

**Created:** 2026-03-31
**Source:** Direct codebase audit

## Existing Code Analysis

### What Exists

#### Tripo Generation (complete, working)
- `src/veilbreakers_mcp/shared/tripo_studio_client.py` — TripoStudioClient with JWT+cookie auth, downloads up to 4 variants (`generate_from_text`, `generate_from_image`). Returns `{models: [{task_id, variant, path, size_bytes, verified}], model_path: first_verified}`.
- `src/veilbreakers_mcp/shared/tripo_client.py` — TripoGenerator (API key fallback, tripo3d SDK). Returns `{model_path, pbr_model_path}`.
- `blender_server.py` generate_3d handler — routes to studio client (preferred) or API client, auto-imports verified variants into Blender in a grid at 3.0m spacing. Prints `next_steps` telling user to pick variant and run cleanup.

#### Post-processing (partial, exists but not wired into Tripo flow)
- `src/veilbreakers_mcp/shared/delight.py` — `delight_albedo(image_path, output_path, blur_radius_pct=0.12, strength=0.75)`. Full Gaussian luminance de-lighting. Returns correction metadata. Exposed as `blender_texture action=delight`.
- `src/veilbreakers_mcp/shared/palette_validator.py` — `validate_palette(image_path)`, `validate_roughness_map(image_path)`. VeilBreakers dark fantasy rules: saturation_cap=0.55, value_range=(0.15, 0.75), cool_bias_target=0.6. Exposed as `blender_texture action=validate_palette`.
- `blender_addon/handlers/weathering.py` — Full weathering system: edge wear, dirt accumulation, moss growth, rain staining, settling, corruption veins. WEATHERING_PRESETS: light/medium/heavy/ancient. Vertex color-based. Exposed as `blender_texture action=generate_wear`.
- `src/veilbreakers_mcp/shared/pipeline_runner.py` — `PipelineRunner.cleanup_ai_model(object_name, poly_budget)` runs repair -> retopo -> UV -> lightmap UV -> `texture_create_pbr` -> validate. The `texture_create_pbr` step creates a blank PBR material, overwriting GLB-embedded textures.

#### Art style validation (partial — Unity side only)
- `src/veilbreakers_mcp/unity_tools/qa.py` — `validate_art_style` action calls `generate_art_style_validator_script` (Unity C# side). This is a Unity-side inspector script, not a Blender-side validation.
- `palette_validator.py` provides Blender-side palette validation (albedo color analysis) but is not wired into the Tripo generation flow.

#### GLB parsing (partial — header-only)
- `pipeline_runner._validate_glb()` — reads GLB header magic, version, and JSON chunk to count scenes/nodes/meshes/materials. Does NOT extract image binary data. Can be used as reference for the binary layout.

#### Quality gate (partial)
- `pipeline_runner.validate_visual_quality()` — renders contact sheet + calls `validate_render_screens()`. Used in cleanup pipeline. Can be applied post-extraction.

### What Does NOT Exist

1. **GLB texture extractor** — No module reads `images[]` + `bufferViews[]` from the GLB JSON chunk and writes image bytes to disk as standalone PNG/JPG files.

2. **Tripo post-processor** — No single orchestration module that runs: extract textures -> delight albedo -> validate palette -> score -> return channel map.

3. **Texture wiring back into Blender node tree** — After extracting PNGs, no handler loads them into the correct Principled BSDF inputs (Base Color, Normal, Roughness/Metallic via ORM split).

4. **Weathering-over-texture compositor** — `weathering.py` writes vertex color layers but there is no handler that creates the `Color Attribute -> Mix Color -> BSDF Base Color` node chain required to composite vertex color wear on top of an existing texture.

5. **Variant quality scoring** — No automated scoring to rank the 4 variants. User picks manually today.

6. **Cleanup texture-awareness flag** — `cleanup_ai_model` has no way to skip `texture_create_pbr` when textures were already extracted and loaded.

### The Core Bug (STATE.md confirmed)

"Tripo pipeline overwrites embedded textures with blank images during cleanup"

Root cause in `pipeline_runner.py`, line ~177:
```python
# Step 7: Create PBR material
pbr_result = await self.blender.send_command(
    "texture_create_pbr",
    {"name": object_name, "object_name": object_name},
)
```

`texture_create_pbr` creates a new Principled BSDF with NO image textures. Any textures that Blender loaded during `bpy.ops.import_scene.gltf` are disconnected from the node tree. The material is effectively reset to blank gray.

### MESH-12 Gap Analysis

MESH-12 requires:
1. `de-lighting -> mesh repair -> retopology -> UV unwrap -> PBR texture EXTRACTION from embedded GLB textures into standalone albedo/normal/roughness/metallic/AO files (not blank images)` — MISSING: extraction step
2. `Smart material overlay applies procedural weathering on TOP of Tripo's extracted textures` — MISSING: weathering overlay compositor
3. `Art style validation compares Tripo output color palette, roughness distribution, and detail density against project standards` — PARTIALLY EXISTS: palette_validator.py does color check; roughness_distribution check needs ORM channel extraction first
4. `4 variants generated per Tripo request, displayed in Blender grid layout` — EXISTS: grid import is working
5. `Best variant selected based on quality scoring (vertex count, UV coverage, material fidelity)` — MISSING: scoring logic

### Pipeline Order (Correct)

```
Tripo download (4 variants)
  |
  v
[MCP-side] Extract GLB textures -> disk PNGs
  |
  v
[MCP-side] De-light albedo PNG
  |
  v
[MCP-side] Validate palette -> flag if fails
  |
  v
[Blender] import_scene.gltf (mesh geometry only)
  |
  v
[Blender] mesh repair -> retopo (if needed) -> UV unwrap
  |
  v
[Blender] Load extracted PNGs into PBR node tree (NOT texture_create_pbr)
  |
  v
[Blender] Weathering overlay (vertex colors + mix node)
  |
  v
[Blender] Quality gate (game_check + visual validation)
  |
  v
[Blender/Export] LOD generation -> FBX export
```

### File Modification Map

| File | Change Type | What Changes |
|------|-------------|-------------|
| `src/veilbreakers_mcp/shared/glb_texture_extractor.py` | CREATE | Extract GLB images to disk |
| `src/veilbreakers_mcp/shared/tripo_post_processor.py` | CREATE | Orchestrate extract + delight + validate + score |
| `src/veilbreakers_mcp/shared/pipeline_runner.py` | MODIFY | Add `has_extracted_textures` param to `cleanup_ai_model` |
| `blender_server.py` generate_3d handler | MODIFY | Call post_process_tripo_model before Blender import; pass texture paths to Blender wiring |
| `blender_addon/handlers/texture.py` | MODIFY | Add `load_extracted_textures` handler |
| `blender_addon/handlers/weathering.py` | MODIFY | Add `mix_weathering_over_texture` node compositor |
| `tests/test_glb_texture_extractor.py` | CREATE | Unit tests for extraction |
| `tests/test_tripo_post_processor.py` | CREATE | Unit tests for post-processing chain |
