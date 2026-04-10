# Tripo AI Environmental Pipeline Audit

**Date:** 2026-04-06
**Scope:** `Tools/mcp-toolkit/` — generation, download, import, processing, placement
**Goal:** Make the Tripo AI 3D environmental asset pipeline (rocks, ruins, trees, props, cave entrances, debris) end-to-end working for mass scatter across biomes.

---

## TL;DR

The Tripo pipeline is **~70% built but only ~40% wired**. All the hard parts exist:

- A working dual-auth client (API key + Studio session cookie with JWT auto-refresh)
- Post-processing (GLB texture extraction, de-lighting, palette validation, scoring)
- A curated 44-model environmental catalog with biome-to-scatter mappings
- A persistent model vault with review/reject/selection tracking
- A cleanup/full-pipeline orchestrator that can wire pre-extracted PBR textures

But the catalog and vault are **orphaned** (zero imports outside their own files), the MCP server has **no action** to drive the env library, the scatter handlers **do not accept pre-generated GLB files** at all, and the image-to-3D upload path has a **known API field-name bug** that will 4xx on first use. There is also **no batch driver** — environmental generation is currently "ask the agent to call generate_3d 44 times in a loop", which is not what the user wants.

**Critical blocker (1 line):** add an `asset_pipeline action=build_env_library` action that iterates `EnvModelLibrary.get_missing_models()`, calls `TripoStudioClient.generate_from_text()` in a bounded-concurrency loop, runs post-process, and calls `lib.register_variant()` — then wire scatter handlers to accept the resulting GLBs.

---

## Phase 1 — Inventory: Every Tripo-related file

### Server-side (`Tools/mcp-toolkit/src/veilbreakers_mcp/`)

| File | Role | Status |
|---|---|---|
| `shared/tripo_client.py` | API-credit client wrapping `tripo3d` SDK, text_to_model + image_to_model, retries, download+validate | **Working** |
| `shared/tripo_studio_client.py` | `/v2/web/` client using Studio/subscription credits, JWT auto-refresh via `ory_kratos_session` cookie, 4-variant generation | **Working, 1 bug** |
| `shared/tripo_post_processor.py` | Orchestrates extract GLB textures -> delight albedo -> palette validate -> roughness validate -> 0-100 score | **Working** |
| `shared/glb_texture_extractor.py` | Extract albedo/ORM/normal/AO/emissive PNGs from GLB (pygltflib preferred, struct fallback) | **Working** (dep gap, see below) |
| `shared/delight.py` | Luminance-based albedo de-lighting to remove Tripo's baked lights | **Working** |
| `shared/palette_validator.py` | Validate albedo against dark fantasy palette, validate roughness variance | **Working** |
| `shared/model_validation.py` | File size / format / triangle count sanity checks on downloaded GLBs | **Working** |
| `shared/env_model_library.py` | **44-model environmental catalog** + 16 biome scatter mappings + persistent `ModelVariant` index + scatter-config export | **ORPHANED — never imported** |
| `shared/model_vault.py` | Persistent generation log, select/reject/prune, file-integrity checks | **ORPHANED — never imported** |
| `shared/pipeline_runner.py` | `cleanup_ai_model`, `full_asset_pipeline`, `generate_and_process`, `batch_process` | **Working (per-object)** |
| `blender_server.py` | MCP actions: `generate_3d`, `generate_building`, `generate_prop`, `cleanup`, `import_model`, `import_and_process`, `full_pipeline`, `generate_and_process`, `batch_process` | **Working per-action, no env-library action** |

### Addon-side (`Tools/mcp-toolkit/blender_addon/handlers/`)

| File | Role | Status |
|---|---|---|
| `texture.py` :632 `handle_load_extracted_textures` | Wire pre-extracted albedo/ORM/normal PNGs into Principled BSDF with proper AO multiply + ORM split | **Working** |
| `environment.py` :278 `_TRIPO_ENVIRONMENT_PROMPTS` + `_build_tripo_environment_manifest` :317 | Hardcoded 7-prompt manifest for alpine/mountain-pass biome only; attached to biome preset as `tripo_asset_manifest` field | **Partial — descriptive only, nothing consumes it** |
| `environment_scatter.py` `handle_scatter_vegetation` :1359 | Biome-aware poisson scatter with slope/moisture filtering, creates instances from **procedural templates** only | **No path for GLB templates** |
| `environment_scatter.py` `handle_scatter_props` :1657 | Context-aware prop scatter near buildings — also uses **procedural templates only** | **No path for GLB templates** |

### Config & env

| File | Relevant | Status |
|---|---|---|
| `pyproject.toml` | `tripo3d>=0.3.12`, `httpx>=0.27.0`, `Pillow>=12.1.0`, `numpy>=1.26.0` | OK. **Missing `pygltflib`** — extractor has a struct-based fallback but pygltflib is the preferred path and its absence is undeclared. |
| `src/veilbreakers_mcp/shared/config.py` :25-29 | `tripo_api_key`, `tripo_studio_token`, `tripo_session_cookie` | OK |
| `.env` | Only `TRIPO_SESSION_COOKIE` is set. No `TRIPO_API_KEY`, no `TRIPO_STUDIO_TOKEN` | Expected; user has session cookie (Advanced plan, 8000 credits/month) |
| `docs/AAA_3D_PIPELINE.md` | Documents Stable Fast 3D as local default, Tripo as remote fallback | Out of sync with reality — for environmental assets Tripo is the primary and SF3D is not configured |

### Tests (`Tools/mcp-toolkit/tests/`)

| File | Lines | What it covers |
|---|---:|---|
| `test_tripo_client.py` | 121 | 4 tests, all mocked: dispatches with correct params, returns model_path, returns error, rejects empty api_key |
| `test_tripo_studio_client.py` | **13** | 2 tests only: `_parse_jwt_exp` malformed/invalid handling. **No end-to-end flow test.** |
| `test_tripo_post_processor.py` | 287 | 6 tests: all steps present, skips delight when no albedo, partial on extraction failure, score ordering, perfect-model score of 100, palette metrics in output |
| `test_pipeline_integration.py` | ~160 | Tests cleanup path with/without extracted textures, albedo_delit preference, falls-back to create_pbr |
| `test_full_pipeline.py` | ~820 | Mocks Tripo + pipeline, tests generate_and_process flow, material auto-picking, animations, export |

**Test coverage gap:** `test_tripo_studio_client.py` is 13 lines. There are **zero tests** for `generate_from_text`, `generate_from_image`, `_poll_and_download_variants`, `_refresh_jwt`, `create_task`, `wait_for_task`, or `_download_file`. The full studio client codepath is completely untested.

---

## Phase 2 — Current State Documentation

### 2.1 API Client — Auth, Endpoints, Versions

**Two clients, two credit pools (memory: `project_tripo_studio_client.md`, 14 days old):**

1. **`TripoGenerator`** — `tripo_client.py` — uses official `tripo3d` SDK, hits `/v2/openapi/`, consumes **API credits** (paid separately). User has 0 API credits.
2. **`TripoStudioClient`** — `tripo_studio_client.py` — custom httpx client hitting `https://api.tripo3d.ai/v2/web/`, consumes **Studio/subscription credits**. User has 7,700+ studio credits on Advanced plan.

**Studio client auth flow** (`tripo_studio_client.py:86-141`):
- Preferred: `session_cookie` (Kratos `ory_kratos_session`), long-lived (~25 days, current cookie expires 2026-04-17 per memory)
- On each request, `_get_valid_jwt()` checks expiry with 5-minute buffer; if expired, calls `_refresh_jwt()` which loads `https://studio.tripo3d.ai/` with the cookie and regex-extracts a fresh JWT from the Nuxt SSR HTML
- Fallback: direct JWT `session_token` (browser DevTools), 2-hour lifetime, no refresh possible

**Priority order in `blender_server.py:2344-2346`, `:2564-2566`, `:2677-2679`:**
```python
studio_cookie = settings.tripo_session_cookie
studio_token = settings.tripo_studio_token
api_key = settings.tripo_api_key
# if studio_cookie or studio_token -> TripoStudioClient
# elif api_key -> TripoGenerator
# else -> error
```

**Endpoints exercised** (`tripo_studio_client.py`):
- `GET /v2/web/user/profile/payment` — balance check, returns `data.wallet.total_credit`
- `POST /v2/web/task` — create task, returns `data.task_ids` (list of 4 variants)
- `GET /v2/web/task/{id}` — poll status (`queued`/`running`/`success`/`failed`/`banned`/`cancelled`)
- `POST /v2/web/task/upload` — image upload for image-to-model, returns `data.image_token`
- `GET https://studio.tripo3d.ai/` (Nuxt SSR) — JWT refresh side-channel

**Model versions:**
- Studio default: `v3.0-20250812` (tripo_studio_client.py:325, :361)
- API default: `v3.1-20260211` (tripo_client.py:96, :199) — **newer than studio default**; minor inconsistency, not a blocker

### 2.2 Generation Methods Supported

| Method | API Client | Studio Client | Notes |
|---|---|---|---|
| text-to-3D | Yes (`generate_from_text`) | Yes (`generate_from_text`) | Studio returns 4 variants per call |
| image-to-3D | Yes (`generate_from_image`) | Yes (`generate_from_image`) | Studio has known upload field-name bug (see Phase 4) |
| refine | No | No | SDK supports it, not wrapped |
| retexture | No | No | Not wrapped |
| rigging (via Tripo) | No | No | Handled post-download via `rig_apply_template` in Blender |
| multiview | No | No | Tripo v2 supports, not wrapped |

### 2.3 Model Formats Returned

- **`pbr_model`** (GLB) — preferred path, top-level field in Studio task response (`tripo_studio_client.py:280`)
- **`model`** (GLB) — non-PBR fallback (API client only, `tripo_client.py:159-162`)
- Output written to `.glb` extension only; no FBX/OBJ conversion in-client
- Studio client downloads variants as `model_pbr.glb` or `model_v{N}_pbr.glb` (`tripo_studio_client.py:282`)
- Post-cleanup, `full_asset_pipeline` can re-export as `.fbx` or `.glb` via `export_fbx`/`export_gltf` Blender commands

### 2.4 Texturing Support

**From Tripo:** PBR metallic-roughness textures baked into GLB. After `extract_glb_textures` (`glb_texture_extractor.py:220`):
- `albedo` (baseColorTexture, sRGB)
- `orm` (metallicRoughnessTexture, packed R=AO / G=Roughness / B=Metal, Non-Color) — note Tripo typically packs only G+B; the AO channel is often neutral
- `normal` (normalTexture, Non-Color, tangent space)
- `ao` (occlusionTexture, only if separate from ORM)
- `emissive` (emissiveTexture, if present)

**Post-processing** (`tripo_post_processor.py:79-173`):
1. Extract channels -> `textures/` subdir
2. De-light albedo via luminance-based correction (`delight.py:39`) -> `albedo_delit.png`
3. Validate palette against dark-fantasy rules (`palette_validator.validate_palette`)
4. Validate roughness variance
5. Score 0-100 (25 each for albedo/orm/normal, 15 for palette-pass, 10 for roughness-pass)

**Wire into Blender** (`handlers/texture.py:635 handle_load_extracted_textures`):
- Principled BSDF node tree
- Albedo (prefers `albedo_delit_path` over `albedo_path`) -> Base Color
- ORM -> Separate RGB -> G=Roughness, B=Metallic, R=AO multiply before Base Color
- Normal -> Normal Map node -> Normal socket
- This is the **correct PBR wiring** — no bugs observed

**Texture resolution:** whatever Tripo returns (typically 1024 or 2048). Not clamped, not upscaled.

### 2.5 Import Pipeline

`generate_3d` action (`blender_server.py:2299-2503`) — after download, it inlines Python into `blender_client.send_command("execute_code", ...)` to run:
```python
bpy.ops.import_scene.gltf(filepath="<path>", merge_vertices=True)
```
Studio-client path imports **all verified variants** in a 2x2 grid at `(0,0)`, `(-3,0)`, `(3,0)`, `(0,3)`. API-client path imports just one. Post-process runs **per variant** on the studio path.

Standalone import (`action=import_model`, `blender_server.py:3920`) supports `.glb/.gltf/.fbx/.obj` via the appropriate `bpy.ops.*` operator.

### 2.6 Post-Import Processing

`cleanup_ai_model` (`pipeline_runner.py:85-244`) runs 8 steps:
1. `mesh_auto_repair` — remove doubles, fix normals
2. `mesh_check_game_ready` — poly budget validation
3. `mesh_retopologize` — only if over budget
4. `mesh_enhance_geometry` — SubD, bevel, weighted normals (profile-aware)
5. `uv_unwrap_xatlas` — primary UV
6. `uv_generate_lightmap` — UV2 for Unity lightmaps (non-critical)
7. Texture wiring: if `has_extracted_textures + texture_channels`, calls `texture_load_extracted_textures` with pre-extracted PNG paths; otherwise creates blank Principled BSDF
8. `mesh_validate_enhancement` — quality gate

`full_asset_pipeline` (`pipeline_runner.py:826-1118`) chains: import → cleanup → smart material → weathering → autonomous_refine quality gate → rig (riggable types only) → animate → LODs → visual_gate (contact sheet + scoring) → export FBX/glTF → validate_export.

**This is solid — the post-import chain is well-designed.** The gap is not quality, it's automation: nothing drives this loop over an environmental catalog.

### 2.7 Batch Processing

`PipelineRunner.batch_process` (`pipeline_runner.py:462-534`) takes a list of `object_names` **already in the Blender scene** and runs a per-step command map for each. **It does NOT generate anything** — it only post-processes existing Blender objects.

There is **no Tripo batch generator**. `generate_3d` is single-prompt only. The `compose_interior` action builds a `tripo_prop_queue` list (`blender_server.py:3735-3787`) but returns it to the agent as a next-step hint — it's a text plan, not an executed batch.

### 2.8 Configuration / Env Vars

Settings (`shared/config.py:24-29`):
```python
tripo_api_key: str = ""          # TRIPO_API_KEY
tripo_studio_token: str = ""     # TRIPO_STUDIO_TOKEN (2h JWT)
tripo_session_cookie: str = ""   # TRIPO_SESSION_COOKIE (25d Kratos)
```
Env loaded from `.env` then `pipeline.local.env` (`config.py:64-68`). Current `.env` on this machine has only `TRIPO_SESSION_COOKIE` set.

### 2.9 Test Coverage Summary

| Surface | Coverage |
|---|---|
| `TripoGenerator.generate_from_text` | 4 unit tests, mocked SDK |
| `TripoGenerator.generate_from_image` | 0 tests |
| `TripoStudioClient.generate_from_text` | **0 tests** |
| `TripoStudioClient.generate_from_image` | **0 tests** |
| `TripoStudioClient._refresh_jwt` | **0 tests** |
| `_parse_jwt_exp` | 2 tests, malformed handling only |
| `post_process_tripo_model` | 6 tests |
| `cleanup_ai_model` with extracted textures | ~5 tests in `test_pipeline_integration.py` |
| `full_asset_pipeline` generate_and_process flow | ~5 tests in `test_full_pipeline.py`, **mocks `TripoGenerator` only, never the studio client** |
| `EnvModelLibrary` | **0 tests** (module is orphaned) |
| `ModelVault` | **0 tests** (module is orphaned) |

---

## Phase 3 — AAA Pipeline Checklist

Legend: Working / Partial / Missing

| Requirement | Status | Notes |
|---|---|---|
| Text-to-3D via Tripo API | **Working** | Both clients implement it; studio client returns 4 variants; has auto-import + post-process + screenshot. `blender_server.py:2299-2503` |
| Image-to-3D (reference image) | **Partial — bug** | Implemented but Studio client has a field-name inconsistency: upload returns `image_token` (`tripo_studio_client.py:389`), task payload sends `"file_token": image_token` (`:395`). The Studio web API may expect `image_token` as the key name. This has **never been tested live** (0 unit tests) |
| PBR texturing (not vertex colors) | **Working** | `extract_glb_textures` pulls albedo/ORM/normal; `handle_load_extracted_textures` wires them correctly with AO multiply and ORM split |
| Refine / upscale pass | **Missing** | Tripo API supports `refine_model` action; not wrapped in either client |
| Retopology for game-ready topology | **Working** | `mesh_retopologize` runs in `cleanup_ai_model` step 3 when over poly budget |
| UV unwrap after import | **Working** | `uv_unwrap_xatlas` step 5 in cleanup; UV2 lightmap step 6 |
| Material auto-assignment | **Working** | `texture_load_extracted_textures` if channels extracted; `material_create_procedural` smart-material fallback in `full_asset_pipeline` |
| Batch mode (N assets parallel) | **Missing** | `batch_process` only operates on already-imported Blender objects. There is no "generate 44 prompts in parallel" driver. `generate_3d` is one prompt at a time |
| Asset library (save/load generated) | **Partial — orphaned** | `EnvModelLibrary` (44 models, 16 biomes, `ModelVariant` dataclass, atomic JSON save, `register_variant`, `get_biome_scatter_set`, `export_for_unity`) exists in `env_model_library.py` but **nothing imports it**. `ModelVault` also exists and is orphaned. |
| Environmental prompt templates | **Working (orphaned)** | `ENV_MODEL_CATALOG` in `env_model_library.py:36-88` has 44 models across rocks/foliage/trees/ground_cover/grass/water_edge/underwater/detail with per-model prompts, target tris, and scale ranges. Prefixed with `"dark fantasy medieval weathered Gothic, "`. **Never referenced by the server.** A second, smaller hardcoded list exists in `environment.py:278` (7 models, alpine-biome-only) that is also never consumed. |
| Quality validation (poly/UV/material) | **Working** | `mesh_check_game_ready`, `mesh_validate_enhancement`, palette + roughness validators in post-processor |
| LOD generation post-import | **Working** | `pipeline_generate_lods` step 8 in `full_asset_pipeline`; `asset_pipeline action=generate_lods` standalone |
| Automatic scene placement | **Partial** | `generate_3d` imports to grid position at `(0,0)` + offsets. There is no "place this newly-generated rock on the terrain at scatter position" logic |
| Scatter integration with Geometry Nodes | **Missing** | `handle_scatter_vegetation` / `handle_scatter_props` in `environment_scatter.py` only use **procedural template generators** (`PROP_GENERATOR_MAP`) + cube fallback. No parameter accepts a list of GLB paths. The `tripo_asset_manifest` attached to biome presets (`environment.py:395`) is descriptive only and never read |
| Tripo Studio vs Tripo API | **Working — Studio preferred** | `generate_3d`, `generate_building`, `generate_prop` all try `studio_cookie` -> `studio_token` -> `api_key`. Matches the `project_tripo_studio_client.md` memory intent |

---

## Phase 4 — Does it actually work?

### 4.1 Happy-path probability

**Text-to-3D via Studio client (happy path): ~85% likely to work today**
- Session cookie is set
- Auth refresh logic is sound
- Post-download chain has real test coverage via `test_tripo_post_processor.py`
- The cleanup path has integration tests in `test_pipeline_integration.py`

**Image-to-3D via Studio client: likely broken**
- Field-name mismatch between upload response and task creation payload (see Bug 1 below)
- Zero live tests

**Batch environmental generation: completely absent**
- No action, no driver, no loop

### 4.2 Confirmed bugs and issues

**Bug 1 — Studio image upload field-name mismatch (Critical if image-to-3D is used)**

`src/veilbreakers_mcp/shared/tripo_studio_client.py:389-395`
```python
image_token = upload_data["data"]["image_token"]
# ...
task_data = {
    "type": "image_to_model",
    "file": {"type": _img_type, "file_token": image_token},
    ...
}
```
The variable `image_token` is correctly pulled from the upload response, but the task payload wraps it as `"file_token"`. Per the Tripo Studio web API conventions (and what the browser does), the task payload field should match what the upload returned. This is almost certainly a rename bug that will cause a 400 "invalid file token" error the first time it runs.

**Fix:**
```python
task_data = {
    "type": "image_to_model",
    "file": {"type": _img_type, "file_token": image_token},  # or "image_token" depending on server
    ...
}
```
**Action:** test live against the actual API or inspect browser network logs to confirm the correct key. The memory file says "POST to create" but does not document the exact field name.

**Bug 2 — Missing `pygltflib` dependency (Medium — degraded extraction)**

`src/veilbreakers_mcp/shared/glb_texture_extractor.py:252-254`
```python
if _HAS_PYGLTFLIB:
    return _extract_with_pygltflib(glb_path, out_dir)
return _extract_with_struct(glb_path, out_dir)
```
`pyproject.toml:7-20` does not list `pygltflib`. The struct fallback exists but is less robust (fewer format fallbacks, no multi-material handling). Post-processor `channel_score` will be lower if pygltflib is not installed.

**Fix:** add `"pygltflib>=1.16"` to `pyproject.toml` dependencies.

**Bug 3 — `EnvModelLibrary` and `ModelVault` are orphaned modules (Critical for env pipeline)**

`grep -r "env_model_library\|EnvModelLibrary\|model_vault\|ModelVault"` across the entire repo returns hits only in the two source files themselves (their own docstrings).

- `blender_server.py` does not import either module
- `pipeline_runner.py` does not use the library or vault
- No MCP action writes to the vault or reads from the library
- The Studio client's 4-variant download **does not register in the vault** despite it being designed exactly for that purpose (`model_vault.py:61 register_generation(prompt, task_ids, models, ...)`)
- Scatter handlers do not consult the library for template sources

These are two fully-written modules (~640 lines `env_model_library.py`, ~296 lines `model_vault.py`, with dataclasses, persistence, biome mappings, atomic writes) that nobody calls. They are the backbone for the user's "environmental pipeline" request and they need **wiring**, not writing.

**Bug 4 — `generate_3d` post-process crash safety (Low, but annoying)**

`blender_server.py:2434`
```python
_imported_name = imported_names[0] if imported_names else None
```
This line is inside `if verified:` but references `imported_names` outside the `for i, m in enumerate(verified):` loop. If `verified` is non-empty but **every** variant's `execute_code` import fails, `imported_names` is empty list and `_imported_name` is `None`, which is fine. If `verified` is empty, the `imported_names` variable is never defined, and line 2434 is still reached — **NameError**. Wrapping in `imported_names = []` above the loop would fix it.

**Bug 5 — `generate_and_process` calls legacy API client when Studio credentials present (Medium)**

`pipeline_runner.py:1218-1226`
```python
elif studio_cookie or studio_token:
    from veilbreakers_mcp.shared.tripo_studio_client import TripoStudioClient
    gen = TripoStudioClient(
        session_cookie=studio_cookie,
        session_token=studio_token,
    )
else:
    from veilbreakers_mcp.shared.tripo_client import TripoGenerator
    gen = TripoGenerator(api_key=api_key)
```
This looks correct — but the Studio client returns `{"models": [...], "model_path": "first verified"}` while the API client returns `{"model_path": ..., "pbr_model_path": ...}`. Downstream at `pipeline_runner.py:1262`:
```python
model_path = gen_result.get("pbr_model_path") or gen_result.get("model_path", "")
```
Studio client never sets `pbr_model_path` — the key is `model_path` holding the first verified variant. So it works, but **only one variant is used** in `generate_and_process` — the other 3 downloaded variants are discarded. This is a waste of studio credits (15 credits per unused variant = 45 credits wasted per call).

**Bug 6 — AAA_3D_PIPELINE.md documentation is out of sync (Doc only)**

`docs/AAA_3D_PIPELINE.md` says Stable Fast 3D is the default. Actual behavior: `generate_3d` uses Tripo unconditionally; `generate_and_process` tries SF3D only when `image_path` is given AND `stable_fast3d_repo_path` is set (not set on this machine), so it falls through to Tripo. Documentation should be updated or the fallback logic should match the docs.

### 4.3 Stubs / TODOs / FIXMEs

A grep for `TODO|FIXME|XXX|stub` across the Tripo files produced no hits. The code is complete as written; the problem is that the completed code isn't wired together.

---

## Phase 5 — Prioritized Fix Plan

### CRITICAL — Pipeline is broken without these

#### C1. Add `asset_pipeline action=build_env_library` — batch environmental generation driver

**What's missing:** No action drives the `EnvModelLibrary` over an entire biome or the full catalog.

**Where to add:** `blender_server.py` — new action branch, probably after `generate_prop` (around line 2722).

**Proposed action:**
```python
elif action == "build_env_library":
    # params: biome: str | None, category: str | None, max_models: int = 10,
    #         max_concurrent: int = 3, library_dir: str | None = None
    from veilbreakers_mcp.shared.env_model_library import (
        EnvModelLibrary, ModelVariant,
    )
    from veilbreakers_mcp.shared.tripo_studio_client import TripoStudioClient
    from veilbreakers_mcp.shared.tripo_post_processor import (
        post_process_tripo_model, score_variants,
    )
    import asyncio, time
    from datetime import datetime, timezone

    lib_dir = library_dir or str(
        Path(settings.unity_project_path or ".")
        / "Assets/Art/3D_Models/EnvLibrary"
    )
    lib = EnvModelLibrary(lib_dir)

    # Pick work set
    if biome:
        needed_names = lib.get_biome_missing(biome)
        work = [
            {
                "name": n,
                "category": lib.get_catalog_entry(n)["category"],
                "prompt": lib.get_generation_prompt(n),
                "target_tris": lib.get_catalog_entry(n)["target_tris"],
                "scale_range": lib.get_catalog_entry(n)["scale_range"],
                "missing_variants": lib.VARIANTS_PER_MODEL
                    - len(lib.get_variants(n)),
            }
            for n in needed_names
        ]
    else:
        work = lib.get_missing_models()
        if category:
            work = [w for w in work if w["category"] == category]

    work = work[:max_models]

    studio_cookie = settings.tripo_session_cookie
    studio_token = settings.tripo_studio_token
    if not (studio_cookie or studio_token):
        return json.dumps({
            "status": "failed",
            "error": "TRIPO_SESSION_COOKIE or TRIPO_STUDIO_TOKEN required",
        })

    sem = asyncio.Semaphore(max_concurrent)
    results = {"generated": [], "failed": [], "skipped": []}

    async def gen_one(item):
        async with sem:
            gen = TripoStudioClient(
                session_cookie=studio_cookie,
                session_token=studio_token,
            )
            try:
                out_dir = str(
                    Path(lib_dir) / "_raw" / item["name"]
                )
                r = await gen.generate_from_text(
                    item["prompt"], out_dir,
                    max_variants=lib.VARIANTS_PER_MODEL,
                )
                if r.get("status") != "success":
                    results["failed"].append({
                        "name": item["name"], "error": r.get("error"),
                    })
                    return

                for i, m in enumerate(r.get("models", [])):
                    if not m.get("verified"):
                        continue
                    post = await post_process_tripo_model(
                        m["path"],
                        str(Path(m["path"]).parent / f"variant_{i}_textures"),
                        asset_type="prop",
                    )
                    # Copy GLB into library structure
                    dest = lib.expected_file_path(item["name"], i)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(m["path"], dest)
                    variant = ModelVariant(
                        variant_id=i,
                        model_name=item["name"],
                        category=item["category"],
                        file_path=str(dest),
                        target_tris=item["target_tris"],
                        actual_tris=0,  # fill from mesh validation later
                        scale_range=tuple(item["scale_range"]),
                        generation_prompt=item["prompt"],
                        texture_score=float(post.get("channel_score", 0)),
                        created_at=datetime.now(timezone.utc).isoformat(),
                    )
                    lib.register_variant(variant)
                    results["generated"].append({
                        "name": item["name"], "variant": i,
                        "score": post.get("channel_score", 0),
                    })
            finally:
                await gen.close()

    await asyncio.gather(*(gen_one(w) for w in work))
    results["library_state"] = lib.to_dict()
    results["library_dir"] = lib_dir
    return json.dumps(results, indent=2, default=str)
```

**Also add action to the Literal type in `asset_pipeline` signature:** `"build_env_library"`, and add params `biome: str | None = None`, `category: str | None = None`, `max_models: int = 10`, `max_concurrent: int = 3`, `library_dir: str | None = None`.

**Smoke test (one-line):**
```
asset_pipeline action=build_env_library biome=thornwood_forest max_models=3
```

#### C2. Wire scatter handlers to accept GLB template paths from the env library

**What's missing:** `handle_scatter_vegetation` and `handle_scatter_props` only instance procedural templates.

**Where to fix:** `blender_addon/handlers/environment_scatter.py:1359` (`handle_scatter_vegetation`) and `:1657` (`handle_scatter_props`).

**What to change:** accept an optional `template_glb_paths: dict[str, list[str]]` param. If set, for each needed vegetation type, import the GLB files, create a master template, and use that as the data source instead of calling `_create_vegetation_template`/`_create_prop_template`.

**Minimal patch sketch (pseudocode):**
```python
def handle_scatter_vegetation(params):
    ...
    template_glb_paths = params.get("template_glb_paths", {})
    ...
    for vt in veg_types_needed:
        if vt in template_glb_paths and template_glb_paths[vt]:
            # Import first variant as master; cache by mesh data for instancing
            templates[vt] = _import_glb_as_template(
                template_glb_paths[vt][0], vt, template_coll,
            )
        else:
            templates[vt] = _create_vegetation_template(vt, template_coll)
```
Where `_import_glb_as_template` runs `bpy.ops.import_scene.gltf(filepath=...)`, links to `template_coll`, hides from render, and returns the mesh object.

For **variation** across placements, extend the loop that creates instances (currently `instance = bpy.data.objects.new(..., template.data)`) to pick a round-robin variant mesh if multiple are provided:
```python
if vt in template_glb_paths and len(template_glb_paths[vt]) > 1:
    variant_idx = placement_index % len(template_glb_paths[vt])
    mesh_data = variant_meshes[vt][variant_idx]
else:
    mesh_data = template.data
```

**Server-side call-site update:** `asset_pipeline action=compose_map` (around `blender_server.py:3300+`) should call `lib.get_biome_scatter_set(biome)` to build `template_glb_paths` and pass it through to `env_scatter_vegetation`.

#### C3. Fix Studio client image upload field name (Bug 1)

**File:** `src/veilbreakers_mcp/shared/tripo_studio_client.py:395`

**Current:**
```python
task_data = {
    "type": "image_to_model",
    "file": {"type": _img_type, "file_token": image_token},
    ...
}
```

**Diagnosis step first:** the memory `project_tripo_studio_client.md` documents `pbr_model` as a top-level field for output but does not document the exact upload schema. Before patching blindly, capture a browser DevTools network log of a real studio image-to-model request. If the server expects `file_token`, the current code is fine. If it expects `image_token` (more likely, since the upload response uses that name), change it.

**Also:** add an integration test that runs the upload path against a 1x1 PNG and asserts the task creation does not 4xx.

#### C4. Guard against NameError in generate_3d import loop (Bug 4)

**File:** `src/veilbreakers_mcp/blender_server.py:2375` (just before the `for i, m in enumerate(verified):` loop)

**Current:**
```python
if verified:
    spacing = 3.0
    positions = [...]
    imported_names = []
    for i, m in enumerate(verified):
        ...
    result["imported_to_blender"] = len(imported_names)
    ...
_imported_name = imported_names[0] if imported_names else None
```

**Fix:** initialize `imported_names = []` outside the `if verified:` block so it's always defined when line 2434 runs.

### HIGH VALUE — Unlocks workflows

#### H1. Hook `ModelVault` into `generate_3d` / `generate_building` / `generate_prop`

**What's missing:** Every call currently downloads 4 variants, imports them to Blender, and forgets them. The user cannot review older generations or re-use them.

**Where to fix:** `blender_server.py:2430-2435` (studio path) and `:2494-2496` (API path), and equivalent for `generate_building` / `generate_prop`.

**What to do:**
```python
from veilbreakers_mcp.shared.model_vault import ModelVault

vault = ModelVault(project_root=settings.unity_project_path or ".")
gen_id = vault.register_generation(
    prompt=prompt,
    task_ids=result.get("all_task_ids", []),
    models=result.get("models", []),
    action="generate_3d",
    asset_type=asset_type or "prop",
)
result["vault_generation_id"] = gen_id
```

**Also add new actions:** `vault_list`, `vault_unreviewed`, `vault_select`, `vault_reject` that thin-wrap `ModelVault` methods.

#### H2. Add `TripoStudioClient` end-to-end integration test

**File:** create `tests/test_tripo_studio_client_integration.py`

**What to cover:**
- `_refresh_jwt` extracts a JWT from HTML (use fixture HTML file)
- `create_task` parses `data.task_ids` list correctly
- `create_task` falls back to `data.task_id` singular
- `wait_for_task` polls until success
- `wait_for_task` raises on banned/failed/cancelled
- `_download_file` downloads and validates
- `_poll_and_download_variants` returns correct shape with `models`, `model_path`, verification flags
- `generate_from_text` full happy path with httpx mock
- `generate_from_image` full happy path including upload (this is where Bug 1 surfaces)

Uses `respx` or `httpx.MockTransport` to avoid real network calls.

#### H3. Add `pygltflib` dependency

**File:** `pyproject.toml:7-20`

**Change:** add `"pygltflib>=1.16",` to `dependencies`.

**Why:** current fallback is struct-based and handles fewer edge cases. Post-processor scoring silently degrades when pygltflib is absent.

#### H4. Make `generate_and_process` use all 4 Studio variants

**File:** `src/veilbreakers_mcp/shared/pipeline_runner.py:1262-1283`

**Current:** picks the first verified variant and discards the other 3.

**Change:** Score variants via `score_variants(post_results)`, pick the highest-scoring one for the full pipeline, and save the others to the model vault for later review. This gets real value out of the 60 credits spent per studio call.

#### H5. Merge `_TRIPO_ENVIRONMENT_PROMPTS` into `ENV_MODEL_CATALOG`

**Files:** `blender_addon/handlers/environment.py:278` (delete or reference) and `src/veilbreakers_mcp/shared/env_model_library.py:36`.

**Why:** two independent hardcoded prompt dicts is exactly the "one unified place" the `feedback_one_reviewer_not_ten.md` memory objects to. Kill the duplicate.

**Also:** the environment.py version has extra fields (`suggested_max_vertices`, `asset_class`) that aren't in `env_model_library.py`. Port those into `ENV_MODEL_CATALOG` so the richer metadata survives.

### POLISH — Quality improvements

#### P1. Wrap Tripo refine / retexture actions

Tripo's API supports `refine_model` and `retexture_model` task types. Neither is wrapped. For environmental assets this is less critical (scatter rarely needs the absolute best topology) but useful for hero props.

#### P2. Expose `max_variants` as a `generate_3d` parameter

Currently hardcoded to 4 in the studio client (`tripo_studio_client.py:327`). Expose it so the user can save credits by requesting only 1-2 variants for low-priority assets.

#### P3. Add prompt template catalog for cave entrances, ruins, debris piles

`ENV_MODEL_CATALOG` has rocks/foliage/trees/ground_cover/grass/water_edge/underwater/detail. It does **not** have `ruins`, `cave_entrances`, or `debris`. The user explicitly asked for these in the original request. Add a new category:
```python
"ruins": [
    {"name": "broken_wall", "prompt": "dark fantasy crumbling stone wall section, 2m, moss covered", "target_tris": 600, "scale_range": (1.0, 2.5)},
    {"name": "fallen_column", "prompt": "dark fantasy fallen stone column piece, 1.5m, weathered", "target_tris": 400, "scale_range": (0.8, 2.0)},
    {"name": "rubble_pile", "prompt": "dark fantasy rubble pile, 1m, broken masonry and debris", "target_tris": 500, "scale_range": (0.5, 1.5)},
    {"name": "arch_broken", "prompt": "dark fantasy broken gothic arch, half-collapsed, 2m", "target_tris": 800, "scale_range": (1.0, 2.0)},
],
"cave_entrances": [
    {"name": "small_cave_mouth", "prompt": "dark fantasy small cave entrance, jagged rock opening, 2m wide", "target_tris": 1500, "scale_range": (1.0, 1.5)},
    {"name": "dungeon_arch", "prompt": "dark fantasy dungeon entrance archway, carved stone, iron reinforcement, 2.5m", "target_tris": 1200, "scale_range": (1.0, 1.5)},
],
"debris": [
    {"name": "broken_crate", "prompt": "dark fantasy broken wooden crate, splintered planks, 50cm", "target_tris": 300, "scale_range": (0.3, 0.6)},
    {"name": "barrel_broken", "prompt": "dark fantasy broken barrel, staves scattered, iron bands rusted, 70cm", "target_tris": 350, "scale_range": (0.4, 0.7)},
    {"name": "wagon_wreck", "prompt": "dark fantasy wrecked wagon, broken wheels, splintered frame, 2m", "target_tris": 700, "scale_range": (1.0, 2.0)},
],
```

Add corresponding entries to `BIOME_SCATTER_MAPPING` so `ruined_fortress`, `abandoned_village`, `battlefield`, `cemetery`, `veil_crack_zone` biomes pull from them.

#### P4. `EnvModelLibrary` stores LOD chain paths

`ModelVariant` currently has a single `file_path`. When LODs are generated (step 8 in `full_asset_pipeline`), they should be stored as `lod_paths: list[str]` on the variant so Unity import can wire LOD groups. Extend the dataclass and the `to_dict`/`from_dict` serialization (versioned index file).

#### P5. Sync `AAA_3D_PIPELINE.md` with reality

Update `docs/AAA_3D_PIPELINE.md` to state that Tripo Studio is the primary path for environmental and architectural assets, Stable Fast 3D is experimental/optional, and the `build_env_library` action is the canonical entry point for batch environmental generation.

#### P6. Expose `vault_prune` as an MCP action

`ModelVault.prune_old_generations` exists but has no MCP entry point. Add it so agents can keep the vault from growing unbounded after hundreds of generations.

#### P7. Real Tripo balance check MCP action

`TripoStudioClient.get_balance` already exists (`tripo_studio_client.py:181`). Wire it into an MCP action `asset_pipeline action=tripo_balance` so the agent can check credits before kicking off a 44-model batch that would need ~2,640 credits (44 models × 4 variants × 15 credits).

---

## Concrete fix ordering (do-this-next list)

1. **C4** — 1-line NameError guard in `generate_3d`. Trivial, prevents a sporadic crash.
2. **H3** — add `pygltflib` to `pyproject.toml`. 1 line, removes silent quality degradation.
3. **C3 (diagnose)** — capture a browser network log of a real Tripo Studio image-to-model call and confirm the correct field name. 5 minutes of work, unblocks image-to-3D.
4. **C1** — add `build_env_library` MCP action. ~150 lines. This is the user's actual request. After this the user can run `asset_pipeline action=build_env_library biome=thornwood_forest` and get 44 GLBs on disk, cataloged, scored.
5. **C2** — wire scatter handlers to accept GLB template paths. ~80 lines. Makes the generated library actually appear in scattered scenes.
6. **P3** — add ruins/cave_entrances/debris categories to `ENV_MODEL_CATALOG`. 30 lines of data. Closes the explicit request in the original ask.
7. **H1** — hook `ModelVault` into `generate_3d`. ~20 lines. Now generations are reviewable across sessions.
8. **H2** — add integration tests for `TripoStudioClient`. 200+ lines. Catches regressions in the auth refresh and upload paths.
9. **H4** — score all 4 variants in `generate_and_process`. ~30 lines. Stops wasting credits.
10. **H5** — consolidate the duplicate prompt catalogs. 30 lines.
11. **P1 / P2 / P4-P7** — polish pass.

---

## Key file paths (absolute)

Every file referenced in this audit, for the parent agent:

- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\src\veilbreakers_mcp\blender_server.py` — main server, `asset_pipeline` tool at line 2192, `generate_3d` branch at 2299, `generate_building` at 2505, `generate_prop` at 2617, `cleanup` at 3791, `batch_process` at 3830, `import_model` at 3920, `full_pipeline` at 4033, `generate_and_process` at 4051
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\src\veilbreakers_mcp\shared\tripo_client.py` — API-credit client
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\src\veilbreakers_mcp\shared\tripo_studio_client.py` — Studio-credit client (preferred), image upload bug at line 395
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\src\veilbreakers_mcp\shared\tripo_post_processor.py` — extract + delight + validate + score
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\src\veilbreakers_mcp\shared\glb_texture_extractor.py` — GLB -> PNG PBR maps
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\src\veilbreakers_mcp\shared\delight.py` — albedo de-lighting
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\src\veilbreakers_mcp\shared\palette_validator.py` — palette + roughness validation
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\src\veilbreakers_mcp\shared\env_model_library.py` — **ORPHANED** 44-model catalog, 16-biome mapping, `EnvModelLibrary`
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\src\veilbreakers_mcp\shared\model_vault.py` — **ORPHANED** persistent generation log
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\src\veilbreakers_mcp\shared\pipeline_runner.py` — `cleanup_ai_model` at 85, `full_asset_pipeline` at 826, `generate_and_process` at 1120, `batch_process` at 462
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\src\veilbreakers_mcp\shared\config.py` — Tripo settings at 25-29
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\blender_addon\handlers\texture.py` — `handle_load_extracted_textures` at 635
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\blender_addon\handlers\environment.py` — duplicate `_TRIPO_ENVIRONMENT_PROMPTS` at 278, `_build_tripo_environment_manifest` at 317
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\blender_addon\handlers\environment_scatter.py` — `handle_scatter_vegetation` at 1359, `handle_scatter_props` at 1657 (both need GLB template wiring)
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\tests\test_tripo_client.py` — 4 mocked tests
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\tests\test_tripo_studio_client.py` — **13 lines**, JWT parsing only
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\tests\test_tripo_post_processor.py` — 6 tests
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\tests\test_pipeline_integration.py` — cleanup path tests
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\tests\test_full_pipeline.py` — `generate_and_process` with mocked Tripo (API client only)
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\pyproject.toml` — deps, missing `pygltflib`
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\docs\AAA_3D_PIPELINE.md` — out of sync
- `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\mcp-toolkit\.env` — only `TRIPO_SESSION_COOKIE` set

---

## What "working" looks like after the fixes

After C1-C4 + H1, the user should be able to:

```
# 1. Check balance
asset_pipeline action=tripo_balance
# -> {"credits": 7702}

# 2. Build the forest biome library (44 models x 4 variants = ~240 GLBs, ~2640 credits)
asset_pipeline action=build_env_library biome=thornwood_forest max_concurrent=3
# -> streams progress, saves to Assets/Art/3D_Models/EnvLibrary/
# -> library_index.json with 44 models registered

# 3. Build a terrain and scatter using the library
asset_pipeline action=compose_map map_spec='{
  "name": "Thornveil",
  "terrain": {"preset": "hills", "size": 200},
  "biome": "thornwood_forest",
  "vegetation": {"density": 0.5, "use_env_library": true}
}'
# -> Now the terrain is scattered with real Tripo-generated low-poly meshes,
#    not procedural cube-fallbacks.

# 4. Review and reject bad variants
asset_pipeline action=vault_unreviewed
asset_pipeline action=vault_reject generation_id=gen_... variant_tag=v2 reason="bad topology"

# 5. Export for Unity
asset_pipeline action=env_library_export_unity
```

This is what the user means by "the tripo 3d environmental pipeline going and working". Today the individual pieces exist, but steps 2, 3, 4, and 5 all have missing glue.
