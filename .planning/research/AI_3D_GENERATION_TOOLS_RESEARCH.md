# AI 3D Generation Tools - Comprehensive Research

**Researched:** 2026-03-22
**Domain:** AI 3D mesh generation for dark fantasy action RPG (characters, monsters, props, equipment)
**Confidence:** HIGH (multi-source verified, official docs + API documentation + pricing pages)

---

## Summary

The AI 3D generation landscape in 2026 has matured significantly. There are now 15+ viable tools for generating 3D meshes from text or images, with 6-7 being production-quality for game development. The field splits into three tiers: (1) commercial API leaders (Tripo, Meshy, Rodin) with polished pipelines and auto-rigging, (2) open-source powerhouses (Hunyuan3D, TRELLIS.2, SF3D) that can be self-hosted for zero marginal cost, and (3) research/legacy tools (Shap-E, Point-E, DreamFusion) that are outdated for production use.

For VeilBreakers' dark fantasy pipeline, the optimal strategy is a **multi-tool approach**: keep Tripo3D as the primary generator (best topology + auto-rigging + existing integration), add Hunyuan3D 2.1 as a self-hosted secondary (8K PBR textures, open-source, 6GB VRAM), and use Rodin Gen-2 for hero assets requiring maximum quality. All outputs feed through our existing `asset_pipeline cleanup` for repair, retopo, UV, and PBR standardization.

**Primary recommendation:** Upgrade Tripo integration to v3.0, add Hunyuan3D 2.1 as self-hosted secondary generator, and use Rodin Gen-2 via API for hero/boss assets only.

---

## Tool Comparison Matrix

### Tier 1: Production-Ready API Services

| Tool | Quality | Topology | Speed | PBR Output | Auto-Rig | API | Cost/Model | Formats | Dark Fantasy Suitability |
|------|---------|----------|-------|------------|----------|-----|------------|---------|--------------------------|
| **Tripo3D v3.0** | A | Quad + Tri options | 25-100s | Yes (albedo, normal, roughness, metallic) | Yes (1-click) | REST + Python SDK | ~$0.10-0.25 | GLB, FBX, OBJ, USDZ | HIGH - good style control |
| **Rodin Gen-2 (Hyper3D)** | A+ | Quad + Raw modes | 2-3 min | Yes (full PBR) | No | REST | $0.30-1.50+ | GLB, FBX, OBJ, USDZ, STL | HIGH - best quality overall |
| **Meshy 4** | B+ | Tri-dominant | 30-90s | Yes | Yes | REST | ~$0.10-0.40 | GLB, FBX, OBJ | MEDIUM - better for props |
| **CSM (Cube)** | B+ | Tri | Varies | Yes | Yes (animation library) | REST + Unity SDK | ~$0.20 | GLB | MEDIUM - general purpose |
| **Sloyd** | B | Parametric quad | Instant | Yes | Yes | REST + Unity SDK | ~$0.015 | GLB, FBX, OBJ | LOW - procedural/stylized only |

### Tier 2: Open-Source / Self-Hosted

| Tool | Quality | Topology | Speed | PBR Output | Self-Host VRAM | License | Cost/Model | Dark Fantasy Suitability |
|------|---------|----------|-------|------------|----------------|---------|------------|--------------------------|
| **Hunyuan3D 2.1/3.5** | A | Tri + Quad (PolyGen) | 30-60s | Yes (up to 8K!) | 6GB+ | Open (Tencent) | $0 self-hosted | HIGH - excellent detail |
| **TRELLIS.2 (Microsoft)** | A- | Arbitrary topology | 20s-4min | Yes (up to 4K) | ~8GB+ | MIT License | $0 self-hosted | HIGH - handles complex shapes |
| **SF3D (Stability AI)** | B+ | Tri | 0.5s | Partial (delit albedo + material params) | ~8GB | Open | $0 self-hosted | MEDIUM - speed over quality |
| **TripoSR** | B | Tri | 0.5s | No (vertex colors) | ~8GB | MIT License | $0 self-hosted | LOW - no PBR |

### Tier 3: Research / Legacy / Niche

| Tool | Quality | Status | Recommendation |
|------|---------|--------|----------------|
| **OpenAI Shap-E** | D | Abandoned (2023) | DO NOT USE - low fidelity, no updates |
| **OpenAI Point-E** | D | Abandoned (2022) | DO NOT USE - point clouds only |
| **DreamFusion (Google)** | C | Research only | DO NOT USE - no public API, 40+ min/model |
| **Magic3D (NVIDIA)** | C+ | Research only | DO NOT USE - no public API, no code released |
| **Zero123++** | B- | Component tool | SKIP - used internally by InstantMesh/others |
| **Wonder3D/Wonder3D++** | B | Research + open source | SKIP - superseded by Hunyuan3D and TRELLIS.2 |
| **InstantMesh** | B | Open source | SKIP - superseded by TRELLIS.2 |
| **CRM** | B- | Research | SKIP - limited topology control |

### Character-Specific Tools

| Tool | Type | Quality | API | Cost | Game Suitability | Recommendation |
|------|------|---------|-----|------|------------------|----------------|
| **Ready Player Me** | Avatar creation SDK | B+ | REST + Unity SDK | Free (paid for enterprise) | Casual/social games only | SKIP - wrong style for dark fantasy |
| **Avaturn** | Photo-to-avatar | B+ | REST API | Freemium | Modern human avatars | SKIP - no dark fantasy support |
| **Masterpiece X** | Text-to-3D character | B | REST API | ~$1.00/model | Low-poly indie | SKIP - low-poly, not AAA |
| **Kaedim** | Image-to-3D (human-in-loop) | A | API + plugins | $299+/mo enterprise | Professional quality | CONSIDER - expensive but high quality |
| **Anything World** | Auto-rig + animate | B+ | REST + Unity SDK | Freemium | Rigging/animation only | CONSIDER - for auto-rigging supplement |
| **PIFuHD** | Human from photo | B- | Self-host only | Free | Research quality | SKIP - humans only, no fantasy |
| **ICON/ECON** | Clothed human recon | B | Self-host only | Free | Research quality | SKIP - real humans only |
| **PhoMoH/PHORHUM** | Photo-real human | B+ | Self-host only | Free | Research quality | SKIP - photorealistic humans only |
| **Polycam** | 3D scanning + cleanup | A- | Mobile SDK | Freemium | Scanning real objects | NICHE - for reference scanning only |

---

## Detailed Tool Analysis

### 1. Tripo3D (CURRENT - Keep + Upgrade)

**Confidence: HIGH** (we have working integration, official docs verified)

**Current Integration:** v2.5-20250123 via `tripo3d` Python SDK in `shared/tripo_client.py`

**v3.0 Upgrade Benefits:**
- Sculpture-level precision with up to 2 million polygon output
- Crisper edges, cleaner surfaces, better structural coherence
- Substantially upgraded PBR material pipeline
- Style transforms (LEGO, voxel, cartoon, clay + custom)
- Auto-rigging with 1-click rig + animate
- Smart retopology with quad mesh output option
- Multi-image input for better accuracy

**API Pricing (verified):**
- API credits: $0.01/credit
- 2,000 free credits on signup
- Text-to-3D: ~10-25 credits per generation
- Image-to-3D: ~20-40 credits per generation
- Web subscription: $19.90/mo for 3,000 credits (Professional)

**Output Quality for Dark Fantasy:**
- Good at organic creatures, weapons, armor
- Style control via prompt engineering
- Quad mesh mode specifically designed for animation pipeline
- PBR output: albedo, normal, roughness, metallic as separate channels in GLB

**Integration Effort:** LOW - update `model_version` parameter from `v2.5-20250123` to v3.0 string. SDK API unchanged.

**Limitations:**
- Still struggles with fine detail on faces (mitten-hands common)
- Random topology requires our cleanup pipeline
- No batch API (one model at a time)

---

### 2. Hunyuan3D 2.1 / 3.5 (ADD - Self-Hosted Secondary)

**Confidence: HIGH** (open source, GitHub verified, extensive documentation)

**Why Add This:**
- **8K PBR textures** - highest texture resolution of any generator (8192x8192 albedo, normal, metallic, roughness)
- **Open source** - zero marginal cost per generation, MIT-style license
- **6GB VRAM** - runs on consumer GPU, no cloud costs
- **Blender plugin** - direct integration available
- **Hunyuan3D-PolyGen** - generates clean quad-dominant topology with edge flow (industry first for AI)
- **ComfyUI compatible** - can build complex pipelines

**Key Versions:**
- **Hunyuan3D 2.1**: Full open-source, production-ready PBR, 6GB VRAM minimum
- **Hunyuan3D 3.5**: Cloud API via 3D AI Studio, Pro and Rapid editions, up to 2M faces
- **Hunyuan3D-PolyGen**: Quad mesh autoregressive model, 10K+ face output, tri and quad support

**Output Quality:**
- 500K-600K triangles default (requires retopo for games)
- Polygon count selectable: 50K, 500K, up to 1.5M
- 15% improved face accuracy over v2.0
- Skeletal animation compatibility improvements

**API Options:**
- Self-hosted: Gradio app, diffusers-like Python API
- Cloud: 3D AI Studio REST API (pay-as-you-go, no subscription)

**Integration Effort:** MEDIUM - need to install model weights, create Python wrapper similar to `tripo_client.py`, add as alternative `generate_3d` backend.

**Dark Fantasy Suitability:** HIGH - excellent at detailed organic forms, complex armor, creatures. Quad topology from PolyGen is ideal for rigging.

---

### 3. Rodin Gen-2 (ADD - Hero Asset API)

**Confidence: HIGH** (official API docs at developer.hyper3d.ai verified)

**Why Add This:**
- **10B parameter model** - largest and highest quality 3D generator
- **Native quad mesh mode** - up to 200K quad faces with edge flow
- **Fine poly count control** - 500 to 1,000,000 faces (raw), 1,000 to 200,000 (quad)
- **Full PBR materials** - base color, metallic, normal, roughness
- **Multiple output formats** - GLB, FBX, OBJ, USDZ, STL

**API Details:**
- Gen-2 model via REST API
- Mesh modes: Raw (triangular) or Quad (quadrilateral)
- Quality levels: high (500K raw / 50K quad), medium (150K / 18K), low (20K / 8K), extra-low (2K / 4K)
- Material types: PBR (full), Shaded (baked lighting)
- Recommended: 150K+ faces for best Gen-2 quality

**Pricing:**
- Direct: Business subscription $120/mo minimum, 0.5 credits/generation, +1 credit for HighPack (4K textures)
- Via WaveSpeedAI: $0.30/generation
- Via fal.ai: $0.40/generation

**Use Case:** Boss creatures, hero characters, legendary weapons -- assets worth $0.30-1.50 each for maximum quality. NOT for bulk prop generation.

**Integration Effort:** MEDIUM - REST API wrapper, similar pattern to Tripo client. No Python SDK, need HTTP client.

---

### 4. TRELLIS.2 (CONSIDER - Self-Hosted Backup)

**Confidence: MEDIUM** (open source verified, but newer tool with less production track record)

**Key Features:**
- 4B parameter model (Microsoft, MIT License)
- Novel O-Voxel structure handles complex topologies, sharp features
- Full PBR materials including transparency/translucency
- GLB export with up to 4096x4096 PBR textures
- Text-to-3D and Image-to-3D
- Handles thin geometry and arbitrary topology

**Output:** GLB, OBJ, PLY, Radiance Fields, 3D Gaussians

**Self-Host Requirements:** ~8GB+ VRAM, available on Hugging Face

**Integration Effort:** MEDIUM-HIGH - newer tool, Python API via Hugging Face pipeline

**Dark Fantasy Suitability:** HIGH - excels at complex shapes with sharp features (weapons, armor, architectural elements)

---

### 5. SF3D / TripoSR (SKIP for Production)

**Confidence: HIGH** (Stability AI official, well-documented)

**SF3D** is the fastest generator (0.5 seconds) with UV unwrapping and illumination disentanglement. Based on TripoSR but with better mesh quality and actual UV maps.

**Why Skip:** While incredibly fast, output quality is below Tripo/Hunyuan/Rodin. No full PBR pipeline. Best used for rapid prototyping or concept validation, not production assets.

**Possible Use:** Rapid prototyping step -- generate in 0.5s to validate concept, then regenerate with Tripo/Hunyuan for production quality.

---

### 6. Meshy 4 (ALTERNATIVE to Tripo, Not Recommended to Add)

**Confidence: MEDIUM** (verified features but quality reports mixed)

**Features:**
- Text-to-3D and Image-to-3D with AI texturing
- Auto-rigging and animation
- SOC2 + ISO 27001 certified (enterprise security)
- Unity and Unreal plugins
- Meshy-6 model is latest

**Pricing:**
- Pro: $20/mo, 1,000 credits
- Text-to-3D: 5-20 credits, Texturing: 10 credits
- Image-to-3D: 5-30 credits
- Remesh: 5 credits, Auto-rig: 5 credits

**Why Not Add:** Tripo produces better topology for animation. Meshy excels at props but our cleanup pipeline already handles that. Adding a second commercial API increases cost without proportional quality gain. If Tripo had issues, Meshy would be the fallback.

---

### 7. Sloyd (CONSIDER for Procedural Props Only)

**Confidence: MEDIUM** (verified features and pricing)

**Unique Value:** Procedural parametric generation from handcrafted templates. Buildings, weapons, furniture, vehicles. Unity SDK for runtime generation. **Unlimited generations** at $15/mo.

**Why Consider:** Our gap analysis (3d-modeling-gap-analysis.md) identifies P-01/P-02 as CRITICAL -- furniture and props are placeholder cubes. Sloyd could fill this gap for procedural props generation with parametric control.

**Why Maybe Not:** Output is stylized/low-poly, not AAA photorealistic. Works for grimdark/stylized but may not match our quality bar. The parametric nature means less variety in shapes.

**Integration Effort:** LOW - Unity SDK available, REST API for Blender pipeline.

---

## Best Tool Per Asset Category

| Asset Category | Primary Tool | Secondary Tool | Reasoning |
|----------------|-------------|----------------|-----------|
| **Hero Characters** | Rodin Gen-2 (quad mode) | Tripo v3.0 | Maximum quality for player-visible characters |
| **Boss Monsters** | Rodin Gen-2 | Hunyuan3D 3.5 | Complex organic forms, highest detail |
| **Common Enemies** | Tripo v3.0 | Hunyuan3D 2.1 (self-hosted) | Good quality at scale, auto-rigging |
| **Weapons** | Tripo v3.0 | Sloyd (parametric) | Tripo for unique, Sloyd for variants |
| **Armor/Equipment** | Tripo v3.0 | Hunyuan3D 2.1 | PBR quality, detail preservation |
| **Props (furniture, barrels, etc.)** | Hunyuan3D 2.1 (self-hosted) | Sloyd | Zero cost at scale, 8K textures |
| **Environmental Objects** | Hunyuan3D 2.1 (self-hosted) | TRELLIS.2 | Bulk generation, no per-model cost |
| **Architecture/Buildings** | TRELLIS.2 | Hunyuan3D 2.1 | Sharp features, complex topology |
| **Concept Validation** | SF3D | Tripo v3.0 | 0.5s preview before committing to full generation |

---

## Cost Analysis: 500+ Unique Assets

### Single-Tool Strategy (Tripo Only)
| Asset Type | Count | Credits/Each | Total Credits | Cost |
|------------|-------|-------------|---------------|------|
| Characters | 50 | 25 | 1,250 | $12.50 |
| Monsters | 80 | 25 | 2,000 | $20.00 |
| Weapons | 100 | 20 | 2,000 | $20.00 |
| Armor | 60 | 25 | 1,500 | $15.00 |
| Props | 150 | 15 | 2,250 | $22.50 |
| Environment | 100 | 15 | 1,500 | $15.00 |
| **Total** | **540** | | **10,500** | **$105.00** |

### Multi-Tool Strategy (Recommended)
| Asset Type | Tool | Count | Cost/Each | Total Cost |
|------------|------|-------|-----------|------------|
| Hero Characters | Rodin Gen-2 | 10 | $0.40 | $4.00 |
| Characters | Tripo v3.0 | 40 | $0.20 | $8.00 |
| Boss Monsters | Rodin Gen-2 | 15 | $0.40 | $6.00 |
| Common Enemies | Tripo v3.0 | 65 | $0.20 | $13.00 |
| Weapons (unique) | Tripo v3.0 | 50 | $0.15 | $7.50 |
| Weapons (variants) | Sloyd | 50 | $0.015 | $0.75 |
| Armor | Tripo v3.0 | 60 | $0.20 | $12.00 |
| Props | Hunyuan3D 2.1 (self) | 150 | $0.00 | $0.00 |
| Environment | Hunyuan3D 2.1 (self) | 100 | $0.00 | $0.00 |
| **Total** | | **540** | | **$51.25** |

**Savings:** ~51% cost reduction with multi-tool strategy. Props and environment objects are FREE with self-hosted Hunyuan3D.

---

## Integration Plan for Blender MCP Pipeline

### Architecture: Multi-Backend Generator

```python
# Proposed: shared/model_generator.py

class ModelGenerator:
    """Unified interface for multiple 3D generation backends."""

    BACKENDS = {
        "tripo": TripoBackend,       # Default, best topology
        "hunyuan": HunyuanBackend,   # Self-hosted, free, 8K PBR
        "rodin": RodinBackend,       # Hero assets, max quality
        "trellis": TrellisBackend,   # Self-hosted backup
    }

    async def generate(
        self,
        prompt: str = None,
        image_path: str = None,
        backend: str = "tripo",       # Auto-select or manual
        quality: str = "standard",     # standard | hero | draft
        mesh_mode: str = "quad",       # quad | tri
        target_faces: int = None,      # Override default
        output_dir: str = ".",
    ) -> GenerationResult:
        """Generate 3D model using specified backend."""
        ...
```

### Modified `asset_pipeline generate_3d` Action

```python
# Current parameters (keep):
# - prompt, image_path, output_dir

# New parameters to add:
# - backend: "tripo" | "hunyuan" | "rodin" | "auto"
# - quality: "draft" | "standard" | "hero"
# - mesh_mode: "quad" | "tri"
# - target_faces: int (optional override)

# "auto" backend selection logic:
# - quality="hero" -> rodin
# - quality="standard" -> tripo
# - quality="draft" -> sf3d (if available) or tripo
# - No API key available -> hunyuan (self-hosted)
```

### Pipeline Integration Points

```
1. GENERATE: ModelGenerator.generate() -> raw mesh (GLB/FBX)
2. IMPORT:   blender_execute (import GLB to scene)
3. CLEANUP:  asset_pipeline cleanup (repair + UV + PBR)
4. RETOPO:   blender_mesh retopo (Quadriflow to target faces)
5. UV:       blender_uv unwrap (xatlas)
6. TEXTURE:  blender_texture create_pbr (from generator's PBR maps)
7. RIG:      blender_rig apply_template (humanoid/quadruped/etc.)
8. EXPORT:   blender_export (FBX for Unity)
```

### Environment Variables Required

```bash
# Existing:
TRIPO_API_KEY=...

# New:
RODIN_API_KEY=...          # Hyper3D API key (for hero assets)
HUNYUAN_MODEL_PATH=...     # Local path to Hunyuan3D weights
TRELLIS_MODEL_PATH=...     # Local path to TRELLIS.2 weights
```

---

## AI Texture Generation Tools

### Recommended Stack

| Tool | Purpose | API | Pricing | Integration |
|------|---------|-----|---------|-------------|
| **Scenario.gg** | Game PBR textures (primary) | REST API-first | Custom pricing | Direct pipeline integration |
| **Leonardo.AI** | Concept art + texture (secondary) | REST API | Free tier: 150/day | Good for concept → texture |
| **fal.ai FLUX** (current) | Concept art generation | REST API | Pay-per-use | Already integrated |

**Scenario.gg** is the recommended addition for texture generation because:
- Understands PBR material properties (light interaction, surface types)
- Generates full PBR sets: albedo, normal, roughness, metallic, height, AO
- Custom model training (10-50 images for style consistency)
- Multiple preset models: Realistic 2.0, Hand-Painted, Lineart
- Seamless/tileable output
- Unity and Unreal integration

**Leonardo.AI** is valuable as secondary because:
- 150 free daily generations
- 150+ specialized models
- Custom LoRA training for VeilBreakers art style
- 3D texture generation from OBJ files

**Note:** We already use fal.ai for concept art (FLUX) and texture inpainting. These complement rather than replace it.

---

## AI Animation Tools

### Recommended Stack

| Tool | Purpose | API | Pricing | Integration |
|------|---------|-----|---------|-------------|
| **DeepMotion** | Video-to-mocap (primary) | REST API | $19-59/mo | BVH/FBX output -> Blender |
| **Plask** | Video-to-mocap (secondary) | REST API | $300/year | Browser-based, API available |
| **Rokoko Vision** | Free mocap testing | Free tier | Free basic | Quick validation |
| **Anything World** | Auto-rig + animate library | REST + Unity SDK | Freemium | Supplement our rigging pipeline |

**Current State:** We already have procedural animation generation (`blender_animation`) and AI motion via `generate_ai_motion`. Adding video-to-mocap would fill the gap for realistic human animation that procedural systems cannot match.

**DeepMotion Animate3D** is the recommended primary because:
- Best accuracy for complex poses
- REST API with BVH/FBX output
- Processes uploaded video files
- Multiple skeleton formats
- $19/mo starter is cost-effective

**Integration:** Output BVH/FBX from DeepMotion -> import to Blender -> `blender_animation retarget_mixamo` -> apply to our rig

---

## AI Voice Tools

### Current + Recommended Stack

| Tool | Purpose | API | Pricing | Quality |
|------|---------|-----|---------|---------|
| **ElevenLabs** (current) | SFX generation, voice | REST API | Credit-based | A+ (best polish) |
| **Coqui XTTS v2.5** | Voice cloning (open source) | Self-hosted | Free | A (matches ElevenLabs clarity) |
| **Bark** | Expressive speech | Self-hosted | Free | A- (beats ElevenLabs for expressiveness) |
| **Piper** | Real-time / edge TTS | Self-hosted | Free | B+ (fastest, lowest resource) |

**Current State:** We use ElevenLabs for `generate_sfx` and `generate_voice_line`.

**Recommendation:** Add XTTS v2.5 as self-hosted alternative for bulk NPC dialogue (2000+ lines would cost hundreds via ElevenLabs vs. free self-hosted). Keep ElevenLabs for hero character voices and SFX where polish matters most.

**Bark** is uniquely valuable for dark fantasy because it handles non-verbal sounds (laughter, gasps, grunts, screams) that are critical for combat barks and monster vocalization.

---

## Post-Processing Requirements by Tool

| Generator | Retopo Needed? | UV Needed? | PBR Remap? | Rig Ready? | Our Pipeline Step |
|-----------|---------------|------------|------------|------------|-------------------|
| Tripo v3.0 (quad) | Light (already quad) | Re-unwrap for quality | Minor (good PBR) | After retopo | cleanup -> retopo(light) -> UV -> PBR |
| Tripo v3.0 (tri) | Yes (random topology) | Yes | Minor | After retopo | cleanup -> retopo -> UV -> PBR |
| Rodin Gen-2 (quad) | Minimal | Minor | No (excellent PBR) | After retopo | cleanup -> UV touchup |
| Rodin Gen-2 (raw) | Yes | Yes | No | After retopo | cleanup -> retopo -> UV -> PBR |
| Hunyuan3D 2.1 | Yes (500K+ tris default) | Yes | No (8K PBR) | After retopo | cleanup -> retopo(aggressive) -> UV -> PBR |
| Hunyuan3D PolyGen | Light (quad output) | Minor | No | After retopo | cleanup -> UV touchup |
| TRELLIS.2 | Yes | Yes | Minor | After retopo | cleanup -> retopo -> UV -> PBR |
| SF3D | Yes | No (has UV) | Yes (partial PBR) | After retopo | cleanup -> retopo -> PBR remap |
| Meshy 4 | Yes | Yes | Minor | After retopo | cleanup -> retopo -> UV -> PBR |

**Key Insight:** Every generator's output requires our existing `asset_pipeline cleanup` step. The cleanup -> retopo -> UV -> PBR pipeline is tool-agnostic and remains the quality gate regardless of source.

---

## Common Pitfalls

### Pitfall 1: Topology Quality Overconfidence
**What goes wrong:** Developers assume AI-generated "quad" mesh is animation-ready without retopology.
**Why it happens:** AI quad mesh has proper face types but random edge flow -- it does not follow muscle/joint deformation directions.
**How to avoid:** Always run `blender_mesh retopo` even on quad output. Set lower target_faces for game budgets (5K-15K for characters).
**Warning signs:** Deformation artifacts during rig testing, collapsing geometry at joints.

### Pitfall 2: PBR Channel Mismatch
**What goes wrong:** Different generators use different PBR conventions (metal/rough vs spec/gloss, different normal map spaces).
**Why it happens:** No universal PBR standard across generators.
**How to avoid:** Our `blender_texture create_pbr` node tree should normalize all inputs. Add validation step to check normal map direction (OpenGL vs DirectX).
**Warning signs:** Materials look wrong in Unity despite looking correct in Blender viewport.

### Pitfall 3: Scale Inconsistency Between Generators
**What goes wrong:** A character from Tripo is 2m tall, from Hunyuan is 0.5m, from Rodin is 10m.
**Why it happens:** Each generator has different default scale assumptions.
**How to avoid:** Normalize scale during import. Add scale reference parameter (e.g., `expected_height=1.8` for humanoids).
**Warning signs:** Objects appear tiny or enormous after import.

### Pitfall 4: Hidden Geometry and Internal Faces
**What goes wrong:** AI-generated meshes contain internal geometry, overlapping faces, and non-manifold edges that waste polygons and cause rendering issues.
**Why it happens:** Neural networks generate volumetric representations converted to meshes, often creating internal artifacts.
**How to avoid:** `asset_pipeline cleanup` already handles this with `remove_doubles` and `fix_normals`. Ensure `blender_mesh repair` is always run.
**Warning signs:** Higher-than-expected poly counts, z-fighting in rendered view.

### Pitfall 5: API Rate Limits and Timeouts
**What goes wrong:** Batch generation of 50+ assets hits API rate limits, causing failures mid-pipeline.
**Why it happens:** Commercial APIs have per-minute/per-hour generation limits not always documented.
**How to avoid:** Implement exponential backoff in generator clients. Use self-hosted Hunyuan for bulk operations. Queue generations with retry logic.
**Warning signs:** Increasing 429/503 errors, partial batch completions.

### Pitfall 6: Cost Overruns on Hero-Asset Tool
**What goes wrong:** Using Rodin Gen-2 ($0.30-1.50/model) for ALL assets instead of just hero assets.
**Why it happens:** Higher quality is addictive. "Let's use the best tool for everything."
**How to avoid:** Enforce backend selection in tool params. Auto-select based on quality tier. Budget alerts.
**Warning signs:** Monthly API bill exceeding projections by 5-10x.

---

## Multi-Tool Strategy Recommendation

### Phase 1: Upgrade Existing (Effort: LOW)
1. Update `tripo_client.py` to support v3.0 model version
2. Add `mesh_mode` parameter (quad/tri) to `generate_3d`
3. Add `backend` parameter to `generate_3d` (default: "tripo")
4. Update model_version string in generate_from_text/image

### Phase 2: Add Hunyuan3D Self-Hosted (Effort: MEDIUM)
1. Install Hunyuan3D 2.1 model weights (~6GB download)
2. Create `hunyuan_client.py` with same interface as `tripo_client.py`
3. Wire into `asset_pipeline generate_3d` as backend="hunyuan"
4. Use for props, environment, bulk generation (zero cost)

### Phase 3: Add Rodin API (Effort: MEDIUM)
1. Create `rodin_client.py` with HTTP client (no SDK)
2. Wire into `asset_pipeline generate_3d` as backend="rodin"
3. Configure quad mode, 150K+ faces, PBR material
4. Reserve for hero characters, bosses, key weapons (quality="hero")

### Phase 4: Add Quality-Based Auto-Selection (Effort: LOW)
1. Add `quality` parameter: "draft" | "standard" | "hero"
2. Auto-select backend based on quality tier
3. Draft -> SF3D (0.5s) or Tripo, Standard -> Tripo, Hero -> Rodin
4. Fallback to self-hosted if API keys not configured

---

## State of the Art

| Old Approach (2024) | Current Approach (2026) | Impact |
|---------------------|------------------------|--------|
| Single generator (Tripo/Meshy) | Multi-backend with auto-selection | 2-5x quality range coverage |
| Tri-only output | Quad mesh generation (Rodin, Hunyuan PolyGen) | Rigging quality dramatically improved |
| 2K textures maximum | 8K PBR textures (Hunyuan3D) | Texture quality matches hand-authored |
| Cloud-only, per-model cost | Self-hosted open-source (Hunyuan, TRELLIS.2) | Bulk generation at zero marginal cost |
| No auto-rigging | 1-click auto-rig (Tripo, Meshy, Anything World) | Rigging bottleneck reduced |
| 30-60s generation | 0.5s (SF3D) to 3min (Rodin) spectrum | Real-time iteration possible |
| Text-only prompts | Multi-image input, concept art to 3D | Much better accuracy from reference art |

**Deprecated/outdated:**
- **Shap-E / Point-E**: Completely superseded by every tool listed above
- **DreamFusion / Magic3D**: Research-only, never shipped public APIs
- **TripoSR**: Superseded by SF3D (same team, better output)
- **Single-tool strategies**: The quality gap between tools makes multi-tool mandatory for AAA

---

## Open Questions

1. **Hunyuan3D-PolyGen availability**
   - What we know: Announced with quad mesh autoregressive generation, 10K+ faces
   - What's unclear: Whether PolyGen weights are included in open-source release or separate
   - Recommendation: Check GitHub repo releases, may need to download separately

2. **Rodin Gen-2 batch API**
   - What we know: REST API supports single generation
   - What's unclear: Whether batch/queue endpoints exist for submitting multiple jobs
   - Recommendation: Test API, implement client-side batching with rate limiting

3. **TRELLIS.2 production readiness**
   - What we know: MIT licensed, 4B params, impressive demos
   - What's unclear: Real-world stability, memory requirements under load, edge cases
   - Recommendation: Evaluate as Phase 4 addition after Hunyuan and Rodin proven

4. **Dark fantasy style consistency across generators**
   - What we know: Each generator has different style tendencies
   - What's unclear: Can prompt engineering achieve consistent dark fantasy aesthetic across all backends?
   - Recommendation: Create a style prompt template library tested across each generator

---

## Sources

### Primary (HIGH confidence)
- [Tripo3D Official Docs](https://platform.tripo3d.ai/docs/changelog) - API changelog, billing
- [Tripo3D API](https://www.tripo3d.ai/api) - Features, pricing
- [Hyper3D Rodin Gen-2 API Docs](https://developer.hyper3d.ai/api-specification/rodin-generation-gen2) - Full API specification
- [Hunyuan3D-2.1 GitHub](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1) - Source code, model weights, documentation
- [TRELLIS.2 GitHub](https://github.com/microsoft/TRELLIS.2) - MIT license, model weights
- [SF3D GitHub](https://github.com/Stability-AI/stable-fast-3d) - Source code, benchmarks
- [Meshy API Docs](https://docs.meshy.ai/en/api/pricing) - Credit pricing per task type
- [Scenario.gg](https://www.scenario.com/features/generate-textures) - PBR texture generation
- [DeepMotion Pricing](https://www.deepmotion.com/pricing) - Mocap API pricing

### Secondary (MEDIUM confidence)
- [3DAI Studio API Comparison 2026](https://www.3daistudio.com/blog/best-3d-model-generation-apis-2026) - Cross-verified pricing and quality
- [Sloyd Pricing Comparison](https://www.sloyd.ai/blog/3d-ai-price-comparison) - Credit cost comparison
- [Tripo v3.0 Guide](https://swiftwand.com/en/tripo-v3-ultra-ai-3d-model-generation-text-to-3d-blender-integration-monetization-2026/) - v3.0 features
- [WaveSpeedAI Rodin Pricing](https://wavespeed.ai/blog/posts/introducing-hyper3d-rodin-v2-text-to-3d-on-wavespeedai/) - $0.30/generation verified
- [ElevenLabs Gaming](https://elevenlabs.io/use-cases/gaming) - Voice for games
- [Ready Player Me Docs](https://docs.readyplayer.me/) - Avatar SDK

### Tertiary (LOW confidence)
- [Hunyuan3D-PolyGen announcement](https://www.blenderloop.com/2025/07/hunyuan3d-polygen-ai-now-generates.html) - Quad mesh claims need validation
- [Kaedim pricing](https://www.kaedim3d.com/pricing) - Enterprise-only, no public rates
- [CSM acquisition status](https://www.csm.ai/) - Google acquisition rumored, API future uncertain

---

## Metadata

**Confidence breakdown:**
- Tripo3D (current tool): HIGH - we have working code, official docs verified
- Hunyuan3D: HIGH - open source, GitHub verified, multiple sources confirm capabilities
- Rodin Gen-2: HIGH - official API docs fully specify parameters and pricing
- TRELLIS.2: MEDIUM - open source verified but less production track record
- Pricing data: MEDIUM-HIGH - cross-verified across multiple sources, may fluctuate
- Dark fantasy suitability: MEDIUM - based on general capability assessment, not VeilBreakers-specific testing
- Animation/Voice tools: MEDIUM - secondary research, verified features but not hands-on tested

**Research date:** 2026-03-22
**Valid until:** 2026-04-22 (30 days -- this field moves fast, revalidate monthly)
