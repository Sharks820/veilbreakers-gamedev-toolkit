# Local 3D AI Generation on 8GB VRAM -- Research Report

**Date**: 2026-03-22
**Target Hardware**: RTX 4060 Ti (8GB VRAM), Ryzen 7 5700, 32GB RAM
**Goal**: Find 3D AI models that run locally for dark fantasy RPG asset generation

---

## EXECUTIVE SUMMARY

**Your 8GB VRAM is workable but constraining.** Three models can definitely run on your hardware. The best option is **Hunyuan3D 2.0 via the GP (GPU Poor) fork**, which produces the highest quality output with full PBR textures while fitting in 6GB VRAM through model offloading to your 32GB system RAM. The trade-off is speed -- expect 2-5 minutes per asset instead of seconds.

### Quick Rankings (for 8GB VRAM)

| Rank | Model | Fits 8GB? | PBR Textures? | Quality | Speed (est. RTX 4060 Ti) | Best For |
|------|-------|-----------|---------------|---------|--------------------------|----------|
| 1 | **Hunyuan3D 2.0 GP** | YES (profile 4/5) | YES (albedo, normal, roughness, metallic) | A | 2-5 min (with offloading) | Production assets |
| 2 | **Hunyuan3D 2.1 GP** | YES (3GB geo, 6GB tex) | YES (full Disney BRDF PBR) | A+ | 3-8 min (with offloading) | Highest quality PBR |
| 3 | **TRELLIS 1 FP16** | YES (8GB minimum) | YES (base color, roughness, metallic, opacity) | A- | 1-3 min | Complex topology |
| 4 | **SF3D** | YES (6-7GB) | PARTIAL (albedo + normal; single metallic/roughness value) | B+ | ~1 sec | Fast prototyping |
| 5 | **TripoSR** | YES (6GB default) | NO (baked lighting, vertex colors) | B- | <1 sec | Rapid iteration |
| 6 | **TripoSG** | BARELY (8GB minimum) | NO (geometry only) | B+ (geo) | Unknown | Shape foundation |
| 7 | **TRELLIS.2** | NO (needs 16-24GB) | YES (full PBR) | A+ | N/A | Needs GPU upgrade |
| 8 | **InstantMesh** | NO (needs 16GB) | NO | B | N/A | Needs GPU upgrade |

---

## DETAILED MODEL ANALYSIS

### 1. Hunyuan3D 2.0 GP (GPU Poor Fork) -- RECOMMENDED PRIMARY

**Repository**: https://github.com/deepbeepmeep/Hunyuan3D-2GP
**Windows Portable**: https://github.com/YanWenKun/Hunyuan3D-2-WinPortable

**VRAM Usage**:
- Shape generation: 6 GB (stock), 3 GB with MMGP profile 5
- Texture generation: 6 GB with maximum MMGP optimization
- Shape + texture combined: originally 24.5 GB, reduced to ~6 GB with profile 4/5
- **System RAM required**: 24 GB+ (your 32 GB is sufficient)

**How It Works on 8GB**:
The MMGP (Memory Management for Generative Pipelines) module performs intelligent model offloading. Weights are dynamically moved between VRAM and system RAM. Profile 4 targets 6 GB VRAM; Profile 5 targets <6 GB VRAM. Lower profile number = faster but needs more VRAM.

**Quality**:
- Produces full PBR texture maps (albedo, normal, roughness, metallic)
- No quality loss from offloading -- same model weights, just slower loading
- Hunyuan3D 2.0 excels at hard-surface objects (weapons, armor, architecture)
- Produces watertight meshes with proper UV mapping
- Exports OBJ/FBX/GLB with embedded PBR maps

**Speed Estimate on RTX 4060 Ti**:
- Shape only: ~30-60 seconds with profile 4
- Shape + texture: ~2-5 minutes with profile 4/5 (offloading overhead)
- Turbo model variant available for ~2x speedup

**Configuration**:
```
python app.py --profile 4    # 6GB VRAM target
python app.py --profile 5    # <6GB VRAM target (slowest but safest)
```

**Integration**: Python-based, Gradio UI or CLI. Can be wrapped in REST API.

---

### 2. Hunyuan3D 2.1 GP -- HIGHEST QUALITY PBR

**Repository**: https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1
**Windows**: https://github.com/lzz19980125/Hunyuan3D-2.1-Windows

**VRAM Usage**:
- Shape generation: 10 GB stock, **3 GB with maximum MMGP optimization**
- Texture generation: 21 GB stock, **6 GB with maximum MMGP optimization**
- Total: 29 GB stock, **6-8 GB with MMGP**
- **System RAM required**: 24 GB+ (your 32 GB is sufficient)

**Quality**:
- Implements Disney Principled BRDF model
- Generates diffuse, metallic, roughness, AND normal maps
- 3D-Aware RoPE for cross-view consistency (better textures than 2.0)
- Captures micro-details like leather grain, brushed aluminum
- The new state-of-the-art for open-source PBR 3D generation
- Drag-and-drop ready for Unity (exports OBJ/FBX/GLB)

**Speed Estimate on RTX 4060 Ti**:
- Shape + texture: ~3-8 minutes with maximum offloading
- Slower than 2.0 due to larger model and PBR synthesis pipeline

**Trade-offs vs 2.0**:
- Higher quality PBR output (2.1 is specifically designed for production-ready PBR)
- Slower generation due to larger models
- More aggressive offloading needed
- Newer, less community testing on low-VRAM setups

**Configuration**: Use `--low_vram_mode` flag. Requires CUDA Toolkit 12.8 and VS Build Tools 2022 for texture generation.

---

### 3. TRELLIS 1 (FP16 Mode) -- BEST FOR COMPLEX TOPOLOGY

**Repository**: https://github.com/microsoft/TRELLIS
**FP16 Fork**: https://github.com/off-by-some/TRELLIS-BOX
**Windows Installer**: https://github.com/IgorAherne/trellis-stable-projectorz

**VRAM Usage**:
- Full precision (FP32): 16 GB
- Half precision (FP16): **8 GB** (exactly fits RTX 4060 Ti)
- FP16 achieves ~50% VRAM reduction with maintained generation quality

**Quality**:
- Outputs PBR materials: base color, roughness, metallic, opacity
- Novel O-Voxel sparse structure handles complex topology
- Handles thin surfaces, holes, complex shapes that break other models
- Good for organic and architectural forms

**Speed Estimate on RTX 4060 Ti**:
- FP16 mode: ~1-3 minutes per asset (12-50 generation steps configurable)
- Default 12 steps for rapid prototyping, 50 steps for maximum quality

**Configuration**:
```
run-fp16.bat           # Windows one-click (StableProjectorz)
# OR
docker with FP16 flag  # TRELLIS-BOX
```

**Caveats**:
- 8GB is the exact minimum -- may OOM on very complex inputs
- Original TRELLIS (v1) only, not TRELLIS.2
- Linux-first; Windows support via community forks
- StableProjectorz installer is the easiest Windows path

---

### 4. SF3D (Stable Fast 3D) -- FASTEST OPTION

**Repository**: https://github.com/Stability-AI/stable-fast-3d
**Windows Portable**: https://github.com/YanWenKun/StableFast3D-WinPortable

**VRAM Usage**:
- ~6-7 GB for standard inference
- **Fits comfortably in 8 GB**

**Quality**:
- UV-unwrapped meshes (not vertex colors -- proper texture maps)
- Outputs: albedo map, normal map
- Metallic and roughness: **single value per object** (not spatially varying maps)
- Illumination disentanglement (delighting) removes baked lighting
- 1.01 billion parameters
- Low-polygon output meshes with high-resolution textures

**Speed**:
- ~0.5 seconds on H100
- Estimated **2-5 seconds on RTX 4060 Ti** (consumer GPU benchmarks suggest similar)
- By far the fastest option

**Limitations for Game Dev**:
- Single metallic/roughness value per object limits material variety
- Lower geometric detail than Hunyuan3D or TRELLIS
- Best as rapid prototyping tool, not final asset pipeline
- No text-to-3D -- image input only

**Integration**: Python, can set `SF3D_USE_CPU=1` for CPU fallback.

---

### 5. TripoSR -- FASTEST BUT LOWEST QUALITY

**Repository**: https://github.com/VAST-AI-Research/TripoSR

**VRAM Usage**:
- ~6 GB default at 256 resolution
- 8GB+ for higher resolutions
- `--half-precision` flag cuts VRAM by 40%
- Reduce `chunk_size` (8192 -> 4096) if OOM

**Quality**:
- Feed-forward transformer (no diffusion -- hence the speed)
- **Bakes lighting into texture** -- assets look wrong under different lighting
- Vertex colors, not proper UV-mapped PBR textures
- Acceptable for placeholder/prototype assets only

**Speed**:
- 0.45 seconds at 512^2 on A100
- Estimated **2-5 seconds on RTX 4060 Ti**

**Limitations**:
- No PBR maps -- deal-breaker for production use in dark fantasy RPG
- Baked lighting makes re-lighting impossible
- Image input only (no text-to-3D)

**CPU Fallback**: Technically supports CPU inference (auto-detected if no GPU). Speed unknown but likely 30-60+ seconds.

---

### 6. TripoSG -- GEOMETRY ONLY

**Repository**: https://github.com/VAST-AI-Research/TripoSG

**VRAM Usage**: Minimum 8 GB (stated in repo). Tight fit on RTX 4060 Ti.

**Quality**: High-fidelity geometry using large-scale rectified flow models. Excellent shape synthesis but **no texture generation** -- geometry only.

**Use Case**: Could serve as shape-only generator, then texture with Hunyuan3D-Paint or manual PBR workflow. Adds complexity to pipeline.

---

### 7. TRELLIS.2 -- DOES NOT FIT (Reference Only)

**Repository**: https://github.com/microsoft/TRELLIS.2

**VRAM**: Requires 16-24 GB minimum. 4 billion parameters. The quality leader with 1536^3 resolution and full PBR (base color, roughness, metallic, transparency). **Cannot run on 8GB.**

### 8. InstantMesh -- DOES NOT FIT

**VRAM**: 16 GB for inference (mesh-large config). **Cannot run on 8GB.**

---

## RECOMMENDED SETUP FOR YOUR HARDWARE

### Primary Pipeline (Quality-First)

```
Input Image/Concept Art
    |
    v
Hunyuan3D 2.0 GP (profile 4) -- Shape + PBR Texture
    |                             (~2-5 min per asset)
    v                             (32GB RAM handles offloading)
.OBJ/.FBX with PBR maps
    |
    v
Blender (MCP toolkit) -- Cleanup, retopo, UV refinement
    |
    v
Unity Import
```

### Secondary Pipeline (Speed-First for Prototyping)

```
Input Image
    |
    v
SF3D -- Quick 3D preview (~2-5 sec)
    |
    v
Review shape/proportions
    |
    v
If approved -> Hunyuan3D 2.0 GP for production quality
```

### Upgrade Path (When Budget Allows)

For Hunyuan3D 2.1 at full speed + TRELLIS.2 access:

| GPU | VRAM | Price (2026) | Unlocks |
|-----|------|-------------|---------|
| RTX 4060 Ti 16GB | 16GB | ~$350 used | Full Hunyuan3D 2.0 speed, TRELLIS 1 FP32 |
| RTX 5060 Ti 16GB | 16GB | ~$450 new | Same + 15-25% faster |
| RTX 4070 | 12GB | ~$400 used | Good middle ground |
| RTX 3090 | 24GB | ~$600 used | Everything runs natively |
| RTX 5070 | 12GB | ~$550 new | Modern arch, fast FP16 |
| RTX 5070 Ti | 16GB | ~$750 new | Future-proof sweet spot |

**Best value upgrade**: Used RTX 3090 (~$600) gives 24GB VRAM, runs everything natively at full speed.

---

## INTEGRATION PLAN FOR MCP TOOLKIT

The current `asset_pipeline` tool uses Tripo3D cloud API (`generate_3d` action). To add local generation:

1. **Install Hunyuan3D 2.0 GP** as a local service (Gradio or custom REST wrapper)
2. **Install SF3D** for fast preview mode
3. **Add new action** to `asset_pipeline`: `generate_3d_local`
   - `engine` param: `hunyuan3d` | `sf3d` | `triposr`
   - `quality` param: `production` (Hunyuan3D) | `preview` (SF3D)
   - Falls back to Tripo3D cloud API if local fails
4. **CUDA PyTorch** must be installed first (currently CPU-only PyTorch)

### CUDA Setup Required

Your system has PyTorch 2.10.0+cpu. You need:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```
(CUDA 12.8 for RTX 4060 Ti with driver 595.79)

---

## HONEST QUALITY ASSESSMENT

For a **dark fantasy action RPG**, the reality:

- **Hunyuan3D 2.0/2.1 GP** produces genuinely usable game assets with PBR. Quality is good for props, weapons, environmental objects. Characters and organic creatures still need significant manual cleanup.
- **SF3D** is excellent for blocking out shapes but the single metallic/roughness value means every surface looks the same material. Not production-ready without manual PBR painting.
- **TripoSR** bakes lighting and produces vertex colors -- fundamentally incompatible with dynamic game lighting. Prototype only.
- **TRELLIS 1 FP16** is solid for hard-surface and architectural assets with complex topology but sits right at your VRAM limit, making it less reliable.
- **No local model** currently matches cloud services (Tripo3D API, Meshy) for consistent quality. The cloud API remains the reliability backstop.

**Bottom line**: Hunyuan3D 2.0 GP is your best bet. It runs on your hardware, produces PBR textures, and the community fork is actively maintained. Expect 2-5 minute generation times and plan your workflow around that. Use SF3D for quick shape previews, then run the keeper through Hunyuan3D for production quality.

---

## Sources

- [Hunyuan3D-2GP (deepbeepmeep)](https://github.com/deepbeepmeep/Hunyuan3D-2GP)
- [Hunyuan3D-2GP README](https://github.com/deepbeepmeep/Hunyuan3D-2GP/blob/main/README.md)
- [Hunyuan3D-2 WinPortable](https://github.com/YanWenKun/Hunyuan3D-2-WinPortable)
- [Hunyuan3D-2 WinPortable Memory Optimization](https://deepwiki.com/YanWenKun/Hunyuan3D-2-WinPortable/4-memory-optimization)
- [Hunyuan3D 2.1 Official](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1)
- [Hunyuan3D 2.1 Paper](https://arxiv.org/html/2506.15442v1)
- [TRELLIS-BOX FP16](https://github.com/off-by-some/TRELLIS-BOX)
- [TRELLIS StableProjectorz (8GB)](https://digialps.com/8gb-gpus-rejoice-trellis-stableprojectorz-now-make-3d-mesh-generation-accessible-to-everyone/)
- [TRELLIS StableProjectorz Installer](https://github.com/IgorAherne/trellis-stable-projectorz)
- [TRELLIS.2 Official](https://github.com/microsoft/TRELLIS.2)
- [SF3D Official](https://github.com/Stability-AI/stable-fast-3d)
- [SF3D Paper](https://stable-fast-3d.github.io/)
- [SF3D WinPortable](https://github.com/YanWenKun/StableFast3D-WinPortable)
- [TripoSR Official](https://github.com/VAST-AI-Research/TripoSR)
- [TripoSR vs SF3D Comparison](https://www.triposrai.com/posts/triposr-vs-sf3d-comparison-2025/)
- [TripoSG Official](https://github.com/VAST-AI-Research/TripoSG)
- [InstantMesh VRAM Discussion](https://github.com/TencentARC/InstantMesh/issues/132)
- [3D Model Generation APIs 2026 Comparison](https://www.3daistudio.com/blog/best-3d-model-generation-apis-2026)
- [Comparing Generative 3D Models (Scenario)](https://help.scenario.com/en/articles/comparing-generative-3d-models/)
- [TRELLIS.2 vs Meshy vs Hunyuan3D](https://trellis-2.com/blog/trellis-2-vs-meshy-vs-hunyuan-3d-comparison)
- [RTX 3060 vs 4060 for AI](https://www.bestgpusforai.com/gpu-comparison/3060-vs-4060)
