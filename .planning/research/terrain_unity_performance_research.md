# Unity 6 URP Terrain Performance & Scalability Research

**Researched:** 2026-04-02
**Domain:** Unity 6 Terrain System, URP Rendering, Open World Performance, AAA Scalability
**Confidence:** HIGH (official Unity docs) / MEDIUM (community-verified patterns)
**Target:** VeilBreakers dark fantasy action RPG -- AAA visuals on ANY hardware (low-end laptop to high-end PC)

---

## Summary

Unity 6's terrain system in URP provides a solid foundation for AAA-quality open worlds, but achieving "runs on any machine" requires deliberate architecture around terrain chunking, aggressive LOD management, GPU instancing, and a multi-tier quality settings system. The key insight is that Unity's built-in terrain is CPU-bound by default -- enabling Draw Instanced mode, using the GPU Resident Drawer (new in Unity 6), and keeping splatmap layers to 4 per tile are the highest-impact optimizations. For open worlds, the 3x3 terrain tile streaming pattern with additive scene loading is the proven approach, not Addressables for terrain data.

**Primary recommendation:** Use 1025x1025 heightmap resolution per terrain tile (1km x 1km tiles), 4 terrain layers max per tile, Draw Instanced enabled, GPU Resident Drawer active (Forward+ path), 3x3 streaming grid, and 5 quality presets scaling pixel error (5-50), shadow distance (30-150m), tree distance (100-500m), detail density (0.2-1.0), and LOD bias (0.5-2.0).

---

## 1. Unity Terrain System Optimization

### 1.1 Terrain LOD Settings

| Setting | Description | Default | Low-End | Mid | High-End | Notes |
|---------|-------------|---------|---------|-----|----------|-------|
| **Pixel Error** | Geometry LOD threshold in screen pixels | 5 | 30-50 | 10-15 | 1-5 | Higher = fewer vertices, lower quality. Most impactful single setting. |
| **Base Map Distance** | Distance beyond which low-res composite texture is used | 1000m | 200m | 500m | 1000m+ | Reduces texture sampling cost at distance |
| **Draw Instanced** | GPU-based terrain mesh rendering | Off | ON | ON | ON | **Always enable.** Reduces draw calls 50%+, moves mesh generation to GPU |

**Pixel Error deep dive:** This is the single most important terrain performance knob. It controls how aggressively Unity simplifies terrain mesh patches based on screen-space error. A pixel error of 1 means "perfectly accurate to the heightmap" (expensive). A pixel error of 50 means "allow up to 50 pixels of geometric error" (cheap but blocky at close range). With Draw Instanced enabled, increasing pixel error has fewer visual artifacts because normals come from a normal map texture rather than the mesh geometry.

**Draw Instanced critical insight:** When enabled, Unity uploads the heightmap and splatmaps as GPU textures and uses instanced draw calls with a shared mesh template. This means:
- Normals are stored in a GPU normal map, independent of mesh LOD
- You CAN increase pixel error aggressively (to 10-15) with minimal visual degradation
- CPU terrain mesh generation is eliminated
- Draw calls drop dramatically (50%+ reduction measured)

### 1.2 Heightmap Resolution vs Performance

| Resolution | Actual Size | Vertices per Tile | Draw Calls (approx) | Memory per Tile | Recommendation |
|------------|-------------|-------------------|---------------------|-----------------|----------------|
| 33x33 | Minimal | 1,089 | ~4 | Negligible | Too low for any use |
| 129x129 | Low | 16,641 | ~16 | ~65 KB | Distant/background terrain |
| 257x257 | Medium-Low | 66,049 | ~32 | ~260 KB | Low-end fallback |
| 513x513 | Medium | 263,169 | ~64 | ~1 MB | Good balance, ~2m per pixel at 1km tile |
| 1025x1025 | High | 1,050,625 | ~128 | ~4 MB | **Recommended for AAA.** ~1m per pixel at 1km tile |
| 2049x2049 | Very High | 4,198,401 | ~216+ | ~16 MB | Overkill for most cases |
| 4097x4097 | Extreme | 16,785,409 | ~400+ | ~64 MB | Almost never needed. Memory intensive. |

**Resolution must be power-of-two plus one** (33, 65, 129, 257, 513, 1025, 2049, 4097).

**Recommendation:** 1025x1025 per 1km tile. This gives ~1m resolution which captures most terrain detail. For low-end, use QualitySettings to override pixel error (not heightmap resolution -- that requires reimporting terrain data).

### 1.3 Detail Resolution & Patches

| Setting | Range | Recommended | Purpose |
|---------|-------|-------------|---------|
| **Detail Resolution** | 0-4048 | 512-1024 | Grid resolution for grass/detail placement. Squared to form grid. |
| **Detail Resolution Per Patch** | 8-128 | **16** (Unity recommended) | Patch size for batching. 16 is the sweet spot. |
| **Detail Distance** | meters | 60-120m | Beyond this, details are culled entirely |
| **Detail Density Scale** | 0.0-1.0 | Scale per quality tier | 0 = no details, 1 = full. Key scalability lever. |

### 1.4 Splatmap / Terrain Layer Limits

**Critical performance rule: 4 layers per terrain tile maximum for best performance.**

| Layers | Splatmaps | Render Passes (URP) | Performance Impact |
|--------|-----------|---------------------|--------------------|
| 1-4 | 1 | 1 pass | Optimal. Single pass rendering. |
| 5-8 | 2 | 2 passes | 2x terrain rendering cost. Avoid unless necessary. |
| 9-12 | 3 | 3 passes | Severe. Never do this. |

Each splatmap is an RGBA texture where each channel stores the weight of one terrain layer. In URP, every 4 layers requires an additional rendering pass over the entire terrain. This is the most common performance mistake with Unity terrain.

**Strategy:** Use 4 carefully chosen layers per tile. Across the whole world, you can have many different layers, but each individual tile should use only 4. Plan layer assignments per biome:
- Dark forest: dirt, grass, moss, rock
- Mountain: rock, snow, gravel, cliff
- Swamp: mud, water-stain, dead-grass, moss

### 1.5 Terrain Shader Performance

**Built-in URP Terrain Lit shader:** Adequate for most cases. Uses standard PBR with normal maps per layer.

**Custom Shader Graph terrain (Unity 6.3+):** Unity 6.3 added Terrain Lit Shader Graph template. Create via: `Create > Shader Graph > URP > Terrain Lit Shader Graph`. Benefits:
- Fix tiling artifacts with distance-based tiling or triplanar on steep surfaces
- Optimize by removing unnecessary features (reduce texture samples)
- Add custom effects (height-based snow, wetness)

**MicroSplat (third-party, $25):** If you need more than 4 layers without multi-pass penalty, or triplanar mapping, or procedural texturing. Supports up to 256 textures in a single pass via texture arrays. Available for Unity 6 URP.

**Performance hierarchy (fastest to slowest):**
1. Built-in URP Terrain Lit, 4 layers, Draw Instanced = fastest
2. Custom Shader Graph terrain, 4 layers = similar, can be optimized further
3. MicroSplat with texture arrays = slightly more GPU cost, but scales better with many layers
4. Built-in URP Terrain Lit, 8+ layers = 2+ passes, avoid

---

## 2. Terrain Streaming for Open Worlds

### 2.1 The 3x3 Tile Streaming Pattern

The proven Unity open-world terrain approach:

```
[D][D][D][D][D]      D = Deactivated (or unloaded)
[D][L][L][L][D]      L = Loaded (low detail at edges)
[D][L][P][L][D]      P = Player tile (full detail)
[D][L][L][L][D]
[D][D][D][D][D]
```

**Implementation:**
1. Divide world into square terrain tiles (500m-1000m per tile)
2. Each tile is a separate Unity Scene
3. Use `SceneManager.LoadSceneAsync(sceneName, LoadSceneMode.Additive)` to stream
4. Track player position, load 3x3 grid around player tile
5. Unload tiles outside the grid with `SceneManager.UnloadSceneAsync()`
6. Use a "buffer zone" (50-100m overlap) before triggering load to prevent pop-in

### 2.2 Recommended Tile Size

| Tile Size | Tiles for 4km World | Active Tiles (3x3) | Memory (9 tiles) | Recommendation |
|-----------|---------------------|---------------------|-------------------|----------------|
| 250m | 16x16 = 256 | 9 | ~36 MB terrain | Too many tiles, loading overhead |
| 500m | 8x8 = 64 | 9 | ~72 MB terrain | Good for dense content |
| **1000m** | 4x4 = 16 | 9 | ~144 MB terrain | **Best balance.** Standard for open world. |
| 2000m | 2x2 = 4 | 4 (all loaded) | ~256 MB terrain | Too few tiles, no streaming benefit |

### 2.3 Additive Scene Loading vs Addressables

**Use additive scene loading for terrain**, not Addressables:
- Terrain data (heightmap, splatmaps, trees, details) is tightly coupled to the Scene
- Addressables add complexity without benefit for terrain tiles
- Additive scenes allow each tile to have its own lighting data, NavMesh, etc.

**Use Addressables for:** props, prefabs, vegetation prefab variants, audio clips -- assets shared across tiles.

### 2.4 Distant Terrain / Impostor Terrain

For terrain beyond the 3x3 grid:
- Pre-render low-poly mesh versions of distant terrain tiles (LOD terrain meshes)
- Load these as simple MeshRenderers (not Terrain components) at 1/16 or 1/32 resolution
- Render with a simple unlit/vertex-color shader for minimal cost
- Swap to real terrain when player approaches

### 2.5 DOTS Terrain

**Status:** Unity does NOT have a DOTS-native terrain system as of Unity 6.3. The built-in Terrain component is a MonoBehaviour-based system. ECS/DOTS entities cannot directly reference Terrain data.

**Workaround:** Convert terrain to mesh at build time for DOTS rendering, but this loses Unity Terrain features (detail painting, tree placement, splatmap blending). Not recommended unless you have a custom terrain engine.

---

## 3. LOD System Best Practices

### 3.1 LOD Group Configuration

| LOD Level | Screen % | Typical Use | Triangle Budget |
|-----------|----------|-------------|-----------------|
| LOD0 | 60-100% | Close/hero | Full mesh (100%) |
| LOD1 | 30-60% | Medium | 50% triangles |
| LOD2 | 15-30% | Far | 25% triangles |
| LOD3 | 5-15% | Very far | 10% triangles |
| Culled | <5% | Invisible | 0 (not rendered) |

### 3.2 Screen-Relative Transition Sizing

The LOD Group percentage represents the ratio of the object's screen-space height to total screen height. Key rules:
- **Trees:** LOD0 at 25%, LOD1 at 10%, LOD2/Billboard at 3%, Cull at 1%
- **Rocks/Boulders:** LOD0 at 15%, LOD1 at 5%, Cull at 1%
- **Buildings:** LOD0 at 30%, LOD1 at 15%, LOD2 at 5%, Cull at 1%
- **Small props:** LOD0 at 10%, Cull at 3%

### 3.3 Cross-Fade vs Instant Transition

**Cross-fade (recommended):**
- Set Fade Mode to "Cross Fade" on LOD Group
- Must enable "LOD Cross Fade" in URP Asset
- Uses `unity_LODFade` shader variable + `LOD_FADE_CROSSFADE` keyword
- Transition Width: 0.3-0.5 (30-50% of LOD range used for blending)
- Both LODs render simultaneously during transition (temporary 2x cost)
- Dither-based crossfade is cheaper than alpha-blend crossfade

**Instant (for low-end):**
- Disable LOD Cross Fade in URP Asset for low quality preset
- Eliminates crossfade shader cost
- Visible popping, but saves GPU

**SpeedTree mode:** For SpeedTree assets (.spm/.st), use "Speed Tree" fade mode which interpolates vertex positions for smoother geometry transitions.

### 3.4 LOD Bias (Quality Settings)

| Quality Tier | LOD Bias | Effect |
|--------------|----------|--------|
| Low | 0.3-0.5 | Aggressive LOD, transitions happen very close |
| Medium | 0.7-1.0 | Balanced |
| High | 1.5 | High-detail LODs kept longer |
| Ultra | 2.0 | Maximum visual quality, LODs transition very late |

`QualitySettings.lodBias` is a global multiplier. Values < 1.0 push transitions closer (better performance), > 1.0 push farther (better quality).

### 3.5 Impostor / Billboard LODs

For vegetation at extreme distance:
- SpeedTree includes built-in billboard LODs
- For custom assets, use tools like Simplygon or Amplify Impostors
- Billboard LODs should use alpha cutout (not alpha blend) for SRP Batcher compatibility
- Enable "Preserve Coverage" on billboard textures to prevent mipmap transparency issues
- Set alpha cutoff to 0.3-0.5 for clean edges

---

## 4. GPU Instancing & Draw Call Reduction

### 4.1 GPU Instancing Setup

**SRP Batcher vs GPU Instancing in URP -- critical distinction:**
- SRP Batcher: batches draw calls for objects sharing the same shader (different materials OK). Default in URP.
- GPU Instancing: batches draw calls for objects sharing the same mesh AND material. Must DISABLE SRP Batcher or use incompatible shaders.
- **In URP, SRP Batcher takes priority.** GPU Instancing only activates if shaders are NOT SRP Batcher compatible.

**For vegetation/props, use the GPU Resident Drawer instead (see 4.3).**

### 4.2 DrawMeshInstancedIndirect

For massive vegetation (grass fields, flower patches):
```csharp
// GPU-driven rendering: upload instance transforms to compute buffer
// Cull on GPU, draw surviving instances in one call
Graphics.DrawMeshInstancedIndirect(mesh, 0, material, bounds, argsBuffer);
```
- Bypasses GameObjects entirely -- pure GPU rendering
- Can render 100,000+ grass blades in 1-2 draw calls
- Requires custom compute shader for frustum/distance culling
- Third-party: GPU Instancer Pro automates this

### 4.3 GPU Resident Drawer (Unity 6 -- KEY FEATURE)

**What:** Unity 6's built-in system that automatically uses BatchRendererGroup API for GPU instancing. This is the most impactful Unity 6 performance feature.

**Setup (4 steps):**
1. Project Settings > Graphics > set "BatchRendererGroup Variants" to "Keep All"
2. URP Asset > enable "SRP Batcher"
3. URP Asset > set "GPU Resident Drawer" to "Instanced Drawing"
4. Universal Renderer > Rendering Path = "Forward+"

**Requirements:**
- Forward+ rendering path (NOT Forward or Deferred)
- Graphics API with compute shader support (DX11, DX12, Vulkan, Metal -- NOT OpenGL ES)
- MeshRenderer components only (not SkinnedMeshRenderer)

**Benefits:**
- Automatic GPU instancing of all static meshes (including SpeedTree vegetation)
- Built-in GPU occlusion culling
- Up to 50% CPU reduction in large scenes
- No per-object setup needed -- it just works once enabled

**Limitations:**
- Longer build times (compiles all BatchRendererGroup shader variants)
- Does NOT work with: skinned meshes, particle systems, terrain geometry itself (terrain details/trees benefit)
- Falls back to standard rendering if requirements not met

### 4.4 Draw Call Reduction Checklist

| Technique | Draw Call Reduction | Effort | Priority |
|-----------|-------------------|--------|----------|
| Enable SRP Batcher | 30-50% | Low | **Do first** |
| Enable GPU Resident Drawer | Additional 30-50% | Low | **Do second** |
| Enable Terrain Draw Instanced | 50%+ terrain draws | Low | **Do third** |
| Texture Atlasing (props) | 20-40% | Medium | Worth it for repeated props |
| Static Batching | Variable | Low | Good for unique statics |
| GPU Instancer Pro (vegetation) | 90%+ vegetation draws | Medium | If built-in insufficient |

---

## 5. Occlusion Culling

### 5.1 Built-in Occlusion Culling (Umbra)

Unity's built-in system uses Umbra middleware. It works by:
1. Baking occlusion data in Editor (Window > Rendering > Occlusion Culling)
2. Dividing scene into cells
3. At runtime, testing which renderers are visible from each cell

**For open worlds -- limited effectiveness:**
- Works BEST in: indoor areas, dungeons, towns with buildings, canyon corridors
- Works POORLY in: open fields, hilltops with panoramic views, flat terrain
- Requires static occluders (marked as "Occluder Static")
- Bake time can be very long for large scenes
- Baked data doesn't work with runtime-loaded scenes (streaming limitation)

### 5.2 GPU Occlusion Culling (Unity 6)

The GPU Resident Drawer includes GPU-based occlusion culling that:
- Works at runtime without baking
- Uses hierarchical Z-buffer for occlusion testing
- Works WITH streaming (no prebake required)
- Automatically culls instances behind large occluders

**This is the recommended solution for VeilBreakers open world.**

### 5.3 Practical Occlusion Strategy

| Environment | Strategy | Expected Savings |
|-------------|----------|------------------|
| Open terrain | Frustum culling + distance culling only | 40-60% |
| Forest/dense vegetation | GPU Resident Drawer occlusion | 50-70% |
| Towns/settlements | Baked Umbra occlusion + GPU occlusion | 60-80% |
| Dungeons/caves | Baked Umbra occlusion (ideal case) | 70-90% |
| Mixed open world | GPU occlusion + LOD + streaming | 50-70% overall |

---

## 6. Scalability / Quality Settings

### 6.1 Quality Presets

Define 5 presets using `QualitySettings`:

| Setting | Low | Medium | High | Ultra | Epic |
|---------|-----|--------|------|-------|------|
| **Pixel Error** | 50 | 20 | 10 | 5 | 1 |
| **Shadow Distance** | 30m | 60m | 100m | 150m | 200m |
| **Shadow Cascades** | 1 | 2 | 4 | 4 | 4 |
| **Shadow Resolution** | 512 | 1024 | 2048 | 4096 | 4096 |
| **LOD Bias** | 0.3 | 0.7 | 1.0 | 1.5 | 2.0 |
| **Tree Distance** | 100m | 200m | 350m | 500m | 800m |
| **Billboard Start** | 30m | 60m | 100m | 150m | 250m |
| **Detail Distance** | 40m | 60m | 80m | 120m | 150m |
| **Detail Density** | 0.2 | 0.4 | 0.7 | 1.0 | 1.0 |
| **Base Map Distance** | 200m | 400m | 600m | 1000m | 1500m |
| **Max Mesh Trees** | 25 | 50 | 100 | 200 | 500 |
| **Texture Mipmap Limit** | Quarter (2) | Half (1) | Full (0) | Full (0) | Full (0) |
| **LOD Cross Fade** | OFF | OFF | ON | ON | ON |
| **MSAA** | OFF | 2x | 4x | 4x | 8x |
| **Render Scale** | 0.7 | 0.85 | 1.0 | 1.0 | 1.0 |

### 6.2 What to Scale (Priority Order)

Highest performance impact first:
1. **Shadow Distance + Cascades** -- biggest single GPU cost reduction
2. **LOD Bias** -- controls how many triangles are on screen
3. **Detail Density + Distance** -- grass/small detail culling
4. **Tree Distance + Billboard Start** -- vegetation render cost
5. **Pixel Error** -- terrain geometry complexity
6. **Texture Quality (Mipmap Limit)** -- VRAM and bandwidth
7. **Render Scale** -- nuclear option, reduces internal resolution
8. **MSAA** -- post-process cost
9. **Post-processing effects** -- bloom, AO, volumetrics

### 6.3 Dynamic Resolution

Unity provides infrastructure but not the scaling logic. Implement:
```csharp
// In a MonoBehaviour on the main camera:
void Update() {
    float gpuMs = FrameTimingManager.GetLatestTimings().gpuFrameTime;
    float targetMs = 1000f / targetFPS; // e.g., 33.3ms for 30fps
    
    if (gpuMs > targetMs * 1.1f) {
        // Scale down immediately
        currentScale = Mathf.Max(minScale, currentScale - 0.05f);
    } else if (gpuMs < targetMs * 0.8f) {
        // Scale up gradually (over multiple frames)
        currentScale = Mathf.Min(1.0f, currentScale + 0.01f);
    }
    
    ScalableBufferManager.ResizeBuffers(currentScale, currentScale);
}
```

Unity's official DynamicResolutionSample on GitHub provides a production-ready script.

### 6.4 Auto-Detect Hardware

```csharp
public static int DetectQualityLevel() {
    int vram = SystemInfo.graphicsMemorySize; // MB
    int sysRam = SystemInfo.systemMemorySize; // MB
    int processorCount = SystemInfo.processorCount;
    
    if (vram >= 6000 && sysRam >= 16000) return 4; // Ultra
    if (vram >= 4000 && sysRam >= 12000) return 3; // High
    if (vram >= 2000 && sysRam >= 8000)  return 2;  // Medium
    if (vram >= 1000 && sysRam >= 4000)  return 1;  // Low
    return 0; // Minimum
}

// Call at startup:
void Start() {
    int level = DetectQualityLevel();
    QualitySettings.SetQualityLevel(level, true);
    ApplyTerrainOverrides(level); // Apply terrain-specific settings
}
```

### 6.5 Terrain Quality Overrides

Quality Settings has dedicated terrain overrides:
- `Terrain Setting Overrides` section in Quality Settings inspector
- Override per-tier: Pixel Error, Base Map Distance, Detail Density Scale, Detail Distance, Tree Distance, Billboard Start, Fade Length, Max Mesh Trees
- These override individual terrain component settings globally

---

## 7. Memory Budgets

### 7.1 VRAM Budget Per Quality Tier

| Tier | Target VRAM | Terrain Budget | Vegetation Budget | Props Budget | Shadows/RT | Remaining |
|------|-------------|----------------|-------------------|-------------|------------|-----------|
| **Low (1-2 GB)** | 1.5 GB | 128 MB | 128 MB | 256 MB | 128 MB | ~860 MB UI/shader/system |
| **Medium (2-4 GB)** | 3 GB | 256 MB | 256 MB | 512 MB | 256 MB | ~1.7 GB |
| **High (4-6 GB)** | 5 GB | 384 MB | 512 MB | 1 GB | 512 MB | ~2.6 GB |
| **Ultra (6-8+ GB)** | 7 GB | 512 MB | 768 MB | 1.5 GB | 1 GB | ~3.2 GB |

### 7.2 Texture Memory Breakdown

| Asset Type | Size Per (2K) | Size Per (1K) | Size Per (512) | Count (typical) | Budget Impact |
|------------|---------------|---------------|----------------|-----------------|---------------|
| Terrain Layer (Albedo+Normal+Mask) | ~16 MB | ~4 MB | ~1 MB | 4-8 per tile | 16-128 MB |
| Tree Texture Atlas | ~16 MB | ~4 MB | ~1 MB | 5-10 species | 20-160 MB |
| Grass/Detail | ~4 MB | ~1 MB | ~256 KB | 3-6 types | 1.5-24 MB |
| Rock/Prop Atlas | ~16 MB | ~4 MB | ~1 MB | 10-20 types | 40-320 MB |

### 7.3 Terrain Mesh Memory (9 active tiles)

| Heightmap Res | Per Tile | 9 Tiles | Notes |
|---------------|----------|---------|-------|
| 513x513 | ~1 MB | ~9 MB | Lightweight |
| 1025x1025 | ~4 MB | ~36 MB | **Recommended** |
| 2049x2049 | ~16 MB | ~144 MB | Heavy |

### 7.4 Texture Streaming

**Critical limitation:** Unity does NOT support Texture Streaming on Terrain Textures. Terrain splatmap textures and terrain layer textures are always fully loaded in VRAM because they are blended across the entire terrain surface.

**Implication:** Use texture streaming for props, characters, and environment objects, but budget terrain textures as always-resident. This makes keeping terrain layers to 4 per tile even more important.

**Mipmap Streaming settings (for non-terrain):**
- `QualitySettings.streamingMipmapsMemoryBudget` = 512 MB (default)
- `QualitySettings.streamingMipmapsMaxLevelReduction` = 2 (default)
- Scale budget per quality tier: Low=256MB, Med=384MB, High=512MB, Ultra=768MB

---

## 8. Unity 6 URP-Specific Features

### 8.1 GPU Resident Drawer (detailed in Section 4.3)

The headline Unity 6 feature for terrain-heavy scenes. Automatically instances static meshes and performs GPU occlusion culling. Requires Forward+ rendering path.

### 8.2 Terrain Lit Shader Graph (Unity 6.3)

New in Unity 6.3 LTS:
- Create via: `Create > Shader Graph > URP > Terrain Lit Shader Graph`
- Customize terrain materials without writing HLSL
- Fix common issues: tiling artifacts, visible layer transitions, steep-surface stretching
- Can optimize for mobile by removing unnecessary texture samples
- Supports Terrain Holes (optional, disable for performance)

### 8.3 Render Graph (Unity 6)

Unity 6 uses Render Graph API for URP rendering:
- Automatic resource management (render textures allocated/freed per frame)
- Better GPU memory usage
- Custom render passes can be inserted for terrain-specific effects
- No terrain-specific Render Graph features, but the system benefits terrain scenes through better resource management

### 8.4 Shader Compilation Improvements

Unity 6.3 reduces shader compilation time by up to 45% in URP. This benefits terrain because:
- Terrain shaders with multiple layers compile faster
- Build times reduced when using GPU Resident Drawer (which compiles all BRG variants)

### 8.5 Forward+ Rendering Path

Required by GPU Resident Drawer. Also benefits terrain scenes:
- No per-object light limit (unlike Forward which caps at ~8 additional lights)
- Better for open worlds with many light sources
- Depth prepass improves overdraw handling in vegetation-heavy scenes

---

## 9. Recommended Architecture for VeilBreakers

### 9.1 World Structure

```
World (4km x 4km)
├── Terrain Grid (4x4 = 16 tiles, 1km each)
│   ├── Tile_0_0 (Scene: Terrain + Trees + Details + Props)
│   ├── Tile_0_1
│   ├── ...
│   └── Tile_3_3
├── Distant Terrain (low-poly mesh impostor ring)
├── Global Lighting (separate scene, always loaded)
└── Player/UI (separate scene, always loaded)
```

### 9.2 Per-Tile Configuration

```
Terrain Tile (1km x 1km):
  Heightmap: 1025x1025
  Terrain Layers: 4 max (1 splatmap)
  Detail Resolution: 1024
  Detail Patch Size: 16
  Draw Instanced: ON
  Terrain Holes: OFF (unless needed)
  Tree Instances: SpeedTree with 3 LODs + billboard
  Detail Objects: GPU instanced grass/flowers
```

### 9.3 Rendering Pipeline Settings

```
URP Asset:
  Rendering Path: Forward+
  SRP Batcher: ON
  GPU Resident Drawer: Instanced Drawing
  LOD Cross Fade: ON (High+), OFF (Low/Medium)
  Dynamic Resolution: ON
  Shadow Cascades: Scale per quality tier
  SSAO: ON (High+), OFF (Low/Medium)
```

### 9.4 Streaming Manager Pseudocode

```csharp
public class TerrainStreamingManager : MonoBehaviour {
    public int gridSize = 4; // 4x4 world
    public float tileSize = 1000f; // 1km
    public int loadRadius = 1; // 3x3 grid
    
    private HashSet<Vector2Int> loadedTiles = new();
    
    void Update() {
        Vector2Int playerTile = WorldToTile(player.position);
        HashSet<Vector2Int> needed = GetTilesInRadius(playerTile, loadRadius);
        
        // Unload tiles no longer needed
        foreach (var tile in loadedTiles.Except(needed))
            SceneManager.UnloadSceneAsync($"Terrain_{tile.x}_{tile.y}");
        
        // Load new tiles
        foreach (var tile in needed.Except(loadedTiles))
            SceneManager.LoadSceneAsync($"Terrain_{tile.x}_{tile.y}", 
                LoadSceneMode.Additive);
        
        loadedTiles = needed;
    }
}
```

---

## 10. Common Pitfalls

### Pitfall 1: Too Many Terrain Layers
**What goes wrong:** Adding 8+ terrain layers causes 2-3 render passes per terrain tile, doubling/tripling GPU cost.
**How to avoid:** Enforce 4-layer maximum per tile. Plan biome palettes early.

### Pitfall 2: Forgetting Draw Instanced
**What goes wrong:** CPU spends massive time generating terrain meshes every frame.
**How to avoid:** Always enable Draw Instanced on every terrain component. Check via script at build time.

### Pitfall 3: Detail Density Not Scaled
**What goes wrong:** Low-end machines render millions of grass blades, destroying framerate.
**How to avoid:** Use QualitySettings terrain overrides to set Detail Density Scale to 0.2 on Low.

### Pitfall 4: Terrain Textures Not Streamable
**What goes wrong:** Assuming texture streaming handles terrain textures. It does not.
**How to avoid:** Budget terrain layer textures as always-resident VRAM. Use 1K textures on Low quality.

### Pitfall 5: LOD Cross-Fade Enabled on Low-End
**What goes wrong:** Cross-fade renders both LOD levels simultaneously, doubling draw calls during transitions.
**How to avoid:** Disable LOD Cross Fade in the Low/Medium URP Asset variants.

### Pitfall 6: Not Using Forward+ with GPU Resident Drawer
**What goes wrong:** GPU Resident Drawer silently falls back to standard rendering.
**How to avoid:** Verify Forward+ is set on the Universal Renderer, not just Forward.

### Pitfall 7: Occlusion Culling Bake on Open Terrain
**What goes wrong:** Baking Umbra occlusion for open terrain produces massive data with minimal benefit.
**How to avoid:** Only bake occlusion for indoor/town areas. Use GPU occlusion culling for open world.

### Pitfall 8: Heightmap Resolution Confusion
**What goes wrong:** Setting heightmap to 4097x4097 "for quality" when 1025 is sufficient, wasting 16x memory.
**How to avoid:** 1025x1025 for 1km tiles gives ~1m resolution. Only go higher for tiny hero terrain pieces.

---

## 11. Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Terrain LOD | Custom mesh decimation | Unity's built-in terrain LOD + pixel error | Handles patch-based LOD with distance automatically |
| Vegetation instancing | Custom instancing system | GPU Resident Drawer + terrain detail system | Unity 6 handles this natively with GPU occlusion |
| Grass rendering | Custom grass compute shader | Terrain detail objects + Draw Instanced | Unless you need millions of blades, built-in is sufficient |
| Scene streaming | Custom async loader | SceneManager.LoadSceneAsync (Additive) | Battle-tested, handles dependencies |
| Quality presets | Custom settings file | QualitySettings + Terrain Setting Overrides | Built-in system with per-tier terrain overrides |
| Shadow cascading | Custom cascade logic | URP shadow cascade settings | Configured in URP Asset, scales per quality tier |
| Dynamic resolution | Custom render target scaling | ScalableBufferManager + Unity DynamicResolutionSample | Official Unity approach with proven scaling logic |

---

## Sources

### Primary (HIGH confidence)
- [Unity 6.3 Terrain Settings Reference](https://docs.unity3d.com/6000.3/Documentation/Manual/terrain-OtherSettings.html) - Heightmap resolution, detail settings, tree settings
- [Unity 6.3 URP Performance Guide](https://docs.unity3d.com/6000.3/Documentation/Manual/urp/configure-for-better-performance.html) - SRP Batcher, LOD cross fade, terrain holes
- [Unity 6 GPU Resident Drawer (URP)](https://docs.unity3d.com/6000.0/Documentation/Manual/urp/gpu-resident-drawer.html) - Setup, requirements, limitations
- [Unity Quality Settings Reference](https://docs.unity3d.com/Manual/class-QualitySettings.html) - All quality tier settings including terrain overrides
- [Unity LOD Transitions (6.3)](https://docs.unity3d.com/6000.3/Documentation/Manual/lod/lod-transitions-lod-group.html) - Cross-fade modes, transition width
- [Unity GPU Instancing Manual](https://docs.unity3d.com/Manual/GPUInstancing.html) - SRP Batcher interaction, URP compatibility
- [Unity Terrain Layers Manual](https://docs.unity3d.com/Manual/class-TerrainLayer.html) - Splatmap limits per render pipeline
- [Unity Terrain Shader Graph (6.3)](https://docs.unity3d.com/6000.3/Documentation/Manual/terrain-shader-graph.html) - Custom terrain materials in Shader Graph

### Secondary (MEDIUM confidence)
- [Unity Discussions: Terrain Streaming](https://discussions.unity.com/t/best-approach-for-handling-large-open-world-terrain-streaming/1710438) - Community patterns for 3x3 streaming
- [Unity Discussions: Heightmap Performance](https://discussions.unity.com/t/terrain-heightmap-resolution-performance/17686) - Resolution vs draw call measurements
- [Unity Discussions: Terrain Optimization 2023](https://discussions.unity.com/t/unity-terrain-is-still-poorly-optimized-in-2023/922092) - Current state of terrain performance
- [Unity DynamicResolutionSample (GitHub)](https://github.com/Unity-Technologies/DynamicResolutionSample) - Official dynamic resolution script
- [MicroSplat URP for Unity 6](https://assetstore.unity.com/packages/tools/terrain/microsplat-urp-for-unity-6-280883) - Third-party terrain shader solution
- [Ardenfall: Open World Streaming](https://ardenfall.com/blog/world-streaming-in-unity) - Practical streaming implementation

### Tertiary (LOW confidence -- needs validation)
- VRAM budget tiers are estimates based on general game development practice, not Unity-specific official guidance
- Draw call reduction percentages are approximate ranges from community benchmarks, not controlled tests
- Some Unity 6.3 features (Shader Graph terrain template) may have changed since documentation was written

---

## Metadata

**Confidence breakdown:**
- Terrain settings/configuration: HIGH - directly from Unity 6.3 official docs
- GPU Resident Drawer: HIGH - official Unity 6 docs
- Quality presets/values: MEDIUM - community-verified patterns, not official Unity presets
- VRAM budgets: LOW-MEDIUM - general industry practice, not Unity-specific data
- Streaming architecture: MEDIUM - community-proven patterns, no official Unity guide
- Splatmap layer limits: HIGH - official docs per render pipeline

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (30 days -- Unity 6 terrain system is stable)
