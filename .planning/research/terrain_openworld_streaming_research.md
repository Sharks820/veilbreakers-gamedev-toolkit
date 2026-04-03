# Open World Streaming, LOD, and Performance Optimization Research

**Researched:** 2026-04-02
**Domain:** Open world streaming architecture, level-of-detail systems, scalable quality, draw call optimization, memory budgets, vegetation/terrain performance
**Confidence:** HIGH (cross-verified with official docs, GDC references, Unity documentation, and existing toolkit code)

## Summary

This document covers the full spectrum of techniques AAA open-world games use to run across hardware tiers from 2GB VRAM integrated GPUs to 16GB+ enthusiast cards. The core architecture is cell-based world streaming (as pioneered by Bethesda's Creation Engine and used by CDPR/FromSoftware), combined with hierarchical LOD systems, aggressive draw call batching, and per-tier quality scaling.

VeilBreakers already has strong foundations: terrain chunking with bilinear LOD downsampling, silhouette-preserving LOD pipelines with per-asset presets, per-biome vegetation with Poisson disk placement, and Unity C# template generators for quality settings. This research focuses on the runtime Unity-side patterns needed to make these Blender-authored assets stream efficiently in an open world.

**Primary recommendation:** Implement a cell-based streaming manager (3x3 active grid + distant cell impostors), enable GPU Resident Drawer for foliage instancing (43K draw calls to 128), and build a 4-tier quality preset system that scales shadows, LOD bias, vegetation density, and render resolution independently.

---

## 1. Open World Streaming Architecture

### 1.1 Cell-Based World Loading (The Industry Standard)

**How AAA games do it:**

| Game | Engine | Cell System | Cell Size | Active Grid |
|------|--------|-------------|-----------|-------------|
| Skyrim/Starfield | Creation Engine | Uniform grid, XY coordinates | 4096 units (~58.5m) per cell | 5x5 default (uGridsToLoad=5), buffer = (grids+1)^2 |
| Witcher 3 | REDengine 3 | Sector-based streaming | Variable sectors (~64m tiles) | Distance-ring based, ~200m active |
| Elden Ring | FromSoftware Engine | Map tile grid | ~256m tiles | Distance-based with seamless transitions |
| Ghost of Tsushima | Sucker Punch Engine | Fine-grained streaming cells | Small cells in quadtree | Distance + priority based |

**Confidence:** HIGH -- Skyrim cell system verified via Creation Kit wiki, dimensions confirmed (4096 units = 58.5m per cell). Ghost of Tsushima streaming architecture from GDC 2021 "Zen of Streaming" talk.

### 1.2 Streaming Architecture Pattern

```
World (ScriptableObject)
  |-- Map (ScriptableObject, contains cell grid metadata)
       |-- Cell[0,0] (Scene or Addressable)
       |-- Cell[0,1]
       |-- Cell[1,0]
       ...
```

**Active streaming zone:** 3x3 cell grid centered on player position (9 cells loaded simultaneously).

**Loading strategy:**
1. **Immediate ring (1x1):** Player's current cell -- always fully loaded, highest priority
2. **Adjacent ring (3x3):** 8 surrounding cells -- loaded asynchronously as player approaches border
3. **Distant ring (5x5 to 7x7):** Low-detail impostors only -- simplified prefabs with no colliders, no shadows, no gameplay logic
4. **Beyond distant:** Skybox/fog blend, nothing loaded

**Pre-loading triggers:**
- Player velocity vector predicts next cell crossing 2-3 seconds ahead
- Movement direction weights adjacent cells (cells in front loaded first)
- Fast travel / teleport pre-loads destination + neighbors before fade-out completes

### 1.3 Async Loading Patterns

```csharp
// Unity Addressables async loading pattern
public async void LoadCell(Vector2Int gridPos)
{
    string key = $"Cell_{gridPos.x}_{gridPos.y}";
    var handle = Addressables.LoadSceneAsync(key, LoadSceneMode.Additive);
    handle.Completed += op => {
        if (op.Status == AsyncOperationStatus.Succeeded)
            _loadedCells[gridPos] = op.Result;
    };
}

public void UnloadCell(Vector2Int gridPos)
{
    if (_loadedCells.TryGetValue(gridPos, out var instance))
    {
        Addressables.UnloadSceneAsync(instance);
        _loadedCells.Remove(gridPos);
    }
}
```

**Race condition prevention:**
- Maintain a `_pendingLoads` dictionary to prevent duplicate load requests
- Cancel pending loads for cells that become irrelevant (player changed direction)
- Never unload a cell that hasn't finished loading -- track state machine: `Unloaded -> Loading -> Loaded -> Unloading -> Unloaded`

### 1.4 Memory Pool Management

**Pool strategy:**
- Pre-allocate a fixed memory pool per cell slot (9 slots for 3x3 grid)
- Reuse pool slots when cells swap (unload old, load new into same slot)
- Budget: each cell should fit within 50-80MB for a 16GB RAM target
- Total active memory: 9 cells x 60MB = ~540MB base terrain/geometry budget

**Texture streaming pool:**
- Unity's `QualitySettings.streamingMipmapMemoryBudget` controls the global texture streaming pool
- Low tier: 256MB pool, Medium: 512MB, High: 1024MB, Ultra: 2048MB
- Textures beyond budget automatically drop to lower mip levels

---

## 2. Scalable Quality Settings

### 2.1 Four-Tier Quality Preset System

| Setting | Low | Medium | High | Ultra |
|---------|-----|--------|------|-------|
| **Render Scale** | 0.5x (dynamic 0.5-0.7) | 0.75x (dynamic 0.7-0.85) | 1.0x (dynamic 0.85-1.0) | 1.0x native |
| **Shadow Distance** | 20m | 50m | 100m | 200m |
| **Shadow Cascades** | 1 | 2 | 4 | 4 |
| **Shadow Resolution** | 512 | 1024 | 2048 | 4096 |
| **LOD Bias** | 0.5 (aggressive cull) | 1.0 (default) | 1.5 (relaxed) | 2.0 (maximum detail) |
| **Draw Distance** | 150m | 300m | 600m | 1200m |
| **Vegetation Density** | 0.25x | 0.5x | 0.75x | 1.0x |
| **Grass Render Distance** | 30m | 60m | 100m | 150m |
| **Texture Resolution** | Half-res (1024 max) | Full (2048 max) | Full (2048) | Full (4096) |
| **Texture Filtering** | Bilinear | Trilinear | Aniso x8 | Aniso x16 |
| **Post-Processing: AO** | Off | SSAO half-res | SSAO full | HBAO+ |
| **Post-Processing: SSR** | Off | Off | Half-res | Full-res |
| **Post-Processing: Bloom** | Off | Low quality | Medium | High |
| **Post-Processing: DoF** | Off | Off | Bokeh low | Bokeh high |
| **Terrain Detail** | Low (no tessellation) | Medium | High | Ultra (tessellation) |
| **Terrain Pixel Error** | 16 | 8 | 4 | 2 |
| **Anti-Aliasing** | FXAA | SMAA Low | SMAA High | TAA + SMAA |
| **Particle Count** | 0.25x | 0.5x | 0.75x | 1.0x |
| **Reflection Probes** | Off | Low (64px) | Medium (256px) | High (512px) |

**Confidence:** HIGH -- values derived from Unity documentation quality settings reference + analysis of shipping AAA titles' settings menus.

### 2.2 Dynamic Resolution Scaling

Unity supports dynamic resolution natively through `ScalableBufferManager`:

```csharp
// Automatic DRS based on frame time
void UpdateDynamicResolution()
{
    float currentFrameTime = Time.unscaledDeltaTime;
    float targetFrameTime = 1f / targetFPS; // e.g., 60fps = 16.67ms

    if (currentFrameTime > targetFrameTime * 1.15f) // 15% over budget
        currentScale = Mathf.Max(minScale, currentScale - 0.05f);
    else if (currentFrameTime < targetFrameTime * 0.85f) // 15% under budget
        currentScale = Mathf.Min(maxScale, currentScale + 0.02f);

    ScalableBufferManager.ResizeBuffers(currentScale, currentScale);
}
```

**Key detail:** Scale DOWN fast (0.05 per frame), scale UP slow (0.02 per frame) to prevent oscillation.

### 2.3 Adaptive Quality (Auto-Detect Hardware)

**Initial detection strategy:**
1. Read `SystemInfo.graphicsMemorySize` (VRAM in MB)
2. Read `SystemInfo.systemMemorySize` (RAM in MB)
3. Run a quick GPU benchmark (render a stress scene for 100 frames, measure avg frame time)
4. Map results to quality tier:

```csharp
QualityTier DetectHardwareTier()
{
    int vram = SystemInfo.graphicsMemorySize;
    int ram = SystemInfo.systemMemorySize;

    if (vram >= 8192 && ram >= 16384) return QualityTier.Ultra;
    if (vram >= 4096 && ram >= 16384) return QualityTier.High;
    if (vram >= 2048 && ram >= 8192)  return QualityTier.Medium;
    return QualityTier.Low;
}
```

**Runtime adaptation:** If average FPS drops below target for 5+ seconds, automatically reduce quality one tier. If sustained above target for 30+ seconds with headroom, offer to increase.

---

## 3. Draw Call Optimization

### 3.1 Unity 6 Rendering Pipeline Priority

| Technique | When to Use | Draw Call Reduction | Setup |
|-----------|-------------|---------------------|-------|
| **GPU Resident Drawer** | Scenes with 1000+ objects, especially foliage | 43,500 to 128 draw calls (99.7% reduction) | Forward+ path, SRP Batcher ON, BRG Variants: Keep All |
| **SRP Batcher** | Always ON in URP/HDRP | Reduces render state changes 50-70% | Automatic with compatible shaders |
| **GPU Instancing** | 8+ identical meshes visible simultaneously | Renders all instances in 1 draw call | Enable on material, use instanced properties |
| **Static Batching** | Immovable props, buildings, terrain decorations | Combines into single mesh per material | Mark objects as Static in inspector |
| **HLOD** | Dense outdoor environments, cities, forests | 83% draw call reduction, 51% triangle reduction | Unity HLOD System package, quadtree splitter |

**Confidence:** HIGH -- GPU Resident Drawer numbers from Unity 6 documentation (35K foliage objects benchmark). HLOD numbers from Unity Technologies' HLODSystem GitHub.

### 3.2 GPU Resident Drawer Setup (Unity 6 URP)

**Requirements:**
1. Rendering Path: Forward+
2. SRP Batcher: Enabled
3. GPU Resident Drawer: Instanced Drawing
4. BatchRendererGroup Variants: Keep All (in Project Settings > Graphics)
5. Shaders must support DOTS instancing
6. Objects must use Mesh Renderer (not Skinned Mesh Renderer)

**Restrictions:**
- No MaterialPropertyBlock API usage
- Light Probes cannot use Proxy Volume mode
- Objects cannot move between camera renders (static only for GRD)
- ~100MB additional memory overhead

**Performance proven:** 43,500 draw calls -> 128 draw calls in 35K foliage scene.

### 3.3 HLOD (Hierarchical Level of Detail)

**How it works:**
1. Scene divided into spatial regions via quadtree partitioning
2. Simplified mesh generated for each region (polygon reduction + texture atlas baking)
3. At runtime, distant regions swap to simplified combined meshes
4. Three states per node: Release (unloaded) -> Low (simplified) -> High (full detail)

**Configuration:**
- Chunk Size: controls quadtree granularity (smaller = more nodes, finer control)
- LOD Distance: threshold for high-to-low switch
- Cull Distance: distance beyond which the node is released entirely
- Batcher: SimpleBatcher (fastest) or MaterialPreservingBatcher (better visual quality)
- Streaming: Default (direct references) or Addressable (async loading, better memory)

**Integration with streaming:** Use AddressableHLODController for cells that load/unload. Each cell generates its own HLOD tree at build time.

### 3.4 Texture Atlasing

**When to atlas:**
- Props sharing similar materials (wooden crates, barrels, furniture)
- Terrain decorations (rocks, stumps, debris)
- Vegetation (combine leaf/bark/branch textures)

**Atlas sizes:**
- Low tier: 2048x2048 atlases
- High tier: 4096x4096 atlases
- Use BC7 compression on desktop, ASTC 6x6 on mobile

**Rule:** Each atlas should cover 8-32 unique props to maximize batch efficiency without wasting texture space.

### 3.5 Mesh Merging for Distant Objects

Beyond HLOD, manual mesh merging is appropriate for:
- Village clusters: merge all buildings within a 50m radius into single mesh at LOD3
- Rock formations: merge scattered rocks into single mesh
- Fence/wall runs: merge contiguous wall segments

**Implementation:** `CombineMeshes()` in editor, export as single FBX. Only for objects that are always viewed together at distance.

---

## 4. Memory Budget Strategies

### 4.1 VRAM Tier Budgets

| Tier | VRAM | Target Resolution | Texture Budget | Mesh Budget | Framebuffer Budget | Overhead |
|------|------|-------------------|---------------|-------------|-------------------|----------|
| **Low** | 2GB | 720p-1080p (DRS) | 800MB | 200MB | 400MB | 600MB |
| **Medium** | 4GB | 1080p | 1.5GB | 400MB | 800MB | 1.3GB |
| **High** | 8GB | 1440p | 3GB | 800MB | 1.5GB | 2.7GB |
| **Ultra** | 12-16GB | 4K | 6GB | 1.5GB | 3GB | 5.5GB |

### 4.2 RAM Tier Budgets

| Tier | RAM | Active Cells | Texture Streaming Pool | Audio Pool | Gameplay/AI |
|------|-----|-------------|----------------------|------------|-------------|
| **Minimum** (8GB) | 8GB | 3x3 (9 cells) | 256MB | 64MB | 128MB |
| **Recommended** (16GB) | 16GB | 5x5 (25 cells) | 512MB | 128MB | 256MB |
| **Enthusiast** (32GB) | 32GB | 7x7 (49 cells) | 1024MB | 256MB | 512MB |

### 4.3 Texture Streaming Configuration

```csharp
// Per quality tier texture streaming setup
void ConfigureTextureStreaming(QualityTier tier)
{
    QualitySettings.streamingMipmapsActive = true;
    QualitySettings.streamingMipmapsAddAllCameras = true;

    switch (tier)
    {
        case QualityTier.Low:
            QualitySettings.streamingMipmapMemoryBudget = 256;  // MB
            QualitySettings.streamingMipmapsMaxLevelReduction = 3; // Drop 3 mip levels
            break;
        case QualityTier.Medium:
            QualitySettings.streamingMipmapMemoryBudget = 512;
            QualitySettings.streamingMipmapsMaxLevelReduction = 2;
            break;
        case QualityTier.High:
            QualitySettings.streamingMipmapMemoryBudget = 1024;
            QualitySettings.streamingMipmapsMaxLevelReduction = 1;
            break;
        case QualityTier.Ultra:
            QualitySettings.streamingMipmapMemoryBudget = 2048;
            QualitySettings.streamingMipmapsMaxLevelReduction = 0; // Full quality
            break;
    }
}
```

### 4.4 Texture Compression Formats

| Platform | Format | Quality | Size vs Uncompressed |
|----------|--------|---------|---------------------|
| Desktop | BC7 | Best quality, slow compress | 25% |
| Desktop (normals) | BC5 | Two-channel, high quality | 25% |
| Desktop (fast) | BC1/DXT1 | Acceptable, fast compress | 12.5% |
| Mobile | ASTC 6x6 | Good quality/size balance | ~17% |
| Mobile (fast) | ASTC 8x8 | Smaller, some quality loss | ~10% |
| Fallback | ETC2 | Broad compatibility | 12.5% |

### 4.5 LOD Memory Savings

Typical memory reduction per LOD level:

| LOD | Triangle Ratio | VRAM Usage | Visual Impact |
|-----|---------------|------------|---------------|
| LOD0 | 100% | 100% | Full detail |
| LOD1 | 50% | ~55% | Minor reduction, unnoticeable at distance |
| LOD2 | 25% | ~30% | Visible on close inspection only |
| LOD3 | 10% | ~15% | Silhouette-only, far distance |
| Billboard | ~0.01% | ~5% (texture only) | Flat card, extreme distance |

---

## 5. Vegetation-Specific Performance

### 5.1 Grass Rendering Techniques (Best to Worst Performance)

| Technique | Draw Calls per 100K blades | VRAM | Visual Quality | Best For |
|-----------|---------------------------|------|---------------|----------|
| **GPU Instanced Mesh** | 1-4 (via GPU Resident Drawer) | Low | Good | Unity 6 URP, large open areas |
| **Mesh Shader / Compute Shader** | 1 dispatch | Low | Excellent | Custom pipeline, next-gen |
| **Geometry Shader** | 1 per patch | Medium | Good | Legacy pipelines |
| **Pre-placed Billboard Quads** | Batched via static batch | Very Low | Fair | Low-end fallback |
| **Terrain Detail System** | Instanced per-patch | Medium | Good | Unity terrain integration |

**Recommendation for VeilBreakers:** Use Unity's terrain detail system with GPU instancing enabled for grass. For custom vegetation beyond terrain (swamp roots, mushroom clusters), use GPU Resident Drawer with instanced mesh renderers.

### 5.2 Tree Impostor Systems

**LOD chain for trees:**
1. **LOD0 (0-30m):** Full 3D mesh, ~5000 tris, wind via vertex shader
2. **LOD1 (30-80m):** Simplified mesh, ~2500 tris, simplified wind
3. **LOD2 (80-200m):** Cross-billboard (2-3 intersecting quads), ~8-12 tris
4. **LOD3 (200m+):** Single billboard facing camera, 2 tris

**Octahedral impostors** (advanced technique used in Fortnite):
- Pre-render the tree from multiple angles into a texture atlas
- At runtime, sample the atlas based on camera angle for parallax-correct view
- Much better visual quality than flat billboards
- Popularized by Ryan Brucks (Epic Games), widely adopted in UE5 and available for Unity via Amplify Impostors

**Cross-quad impostors** (simpler alternative):
- 2-3 intersecting quads with alpha-cutout textures
- Each quad shows the tree from a different angle
- Works well for dense forests where individual tree quality matters less
- Very cheap: 4-6 triangles per tree

**Confidence:** HIGH -- octahedral impostor technique verified via multiple sources including Simplygon, InstaLOD documentation, and open-source implementations.

### 5.3 Wind Animation

**Vertex shader wind (NOT skeletal animation):**
```hlsl
// Vertex shader wind -- applied in object space before world transform
float3 ApplyWind(float3 vertexPos, float3 objectPos, float time)
{
    float heightFactor = saturate(vertexPos.y / _TreeHeight); // 0 at base, 1 at top
    heightFactor = heightFactor * heightFactor; // Quadratic falloff (base doesn't move)

    // Primary sway (large, slow)
    float primaryWave = sin(time * _WindSpeed + objectPos.x * 0.1) * _WindStrength;

    // Secondary flutter (small, fast, per-branch)
    float secondaryWave = sin(time * _WindSpeed * 3.7 + vertexPos.x * 2.3) * _FlutterStrength;

    float3 windOffset = float3(primaryWave + secondaryWave, 0, primaryWave * 0.5) * heightFactor;
    return vertexPos + windOffset;
}
```

**Key principle:** Wind animation uses vertex colors to encode sway weight:
- R channel: trunk sway weight (0 at base, 1 at top)
- G channel: branch flutter weight
- B channel: leaf flutter weight

The existing VeilBreakers vegetation system already computes wind vertex colors -- this maps directly to Unity shader consumption.

### 5.4 Vegetation Fade-In (Pop-In Prevention)

**Dithered fade transitions:**
```hlsl
// Alpha dithering for LOD transitions -- prevents hard pop-in
float DitherFade(float2 screenPos, float fadeAmount)
{
    // 4x4 Bayer matrix dither pattern
    float4x4 bayerMatrix = float4x4(
        0/16.0, 8/16.0, 2/16.0, 10/16.0,
        12/16.0, 4/16.0, 14/16.0, 6/16.0,
        3/16.0, 11/16.0, 1/16.0, 9/16.0,
        15/16.0, 7/16.0, 13/16.0, 5/16.0
    );
    int2 pixel = int2(fmod(screenPos, 4));
    float threshold = bayerMatrix[pixel.x][pixel.y];
    clip(fadeAmount - threshold);
    return 1;
}
```

**Unity LODGroup cross-fade:** Enable `LODGroup.crossFadeAnimated = true` with `LODGroup.animateCrossFading = true` for built-in dithered cross-fade between LOD levels.

---

## 6. Terrain-Specific Performance

### 6.1 Terrain LOD Algorithms

| Algorithm | Pros | Cons | Best For |
|-----------|------|------|----------|
| **Geometry Clipmaps** | Simple, predictable, steady frame rate, smooth transitions | Fixed resolution rings, can't adapt to terrain complexity | Large flat/rolling terrains |
| **CDLOD (Continuous Distance-Dependent LOD)** | Quadtree adapts to terrain complexity, GPU-friendly, no skirts needed, SM3.0+ | More complex implementation | Complex terrains with varying detail |
| **ROAM** | Adapts to terrain features | CPU-heavy, poor GPU utilization | Legacy/educational only |
| **Unity Built-in Terrain** | Zero implementation effort, paint tools, detail layers | Limited customization, max 4 layers per pass | Production games on Unity |

**Recommendation:** Use Unity's built-in terrain system with Terrain Pixel Error tuned per quality tier. For VeilBreakers' dark fantasy terrain, the built-in system is sufficient with proper heightmap resolution and material layering.

**Confidence:** HIGH -- Geometry clipmaps verified via NVIDIA GPU Gems 2 (Hoppe 2004), CDLOD via Strugar's implementation papers.

### 6.2 Terrain Configuration Per Quality Tier

```csharp
void ConfigureTerrain(Terrain terrain, QualityTier tier)
{
    switch (tier)
    {
        case QualityTier.Low:
            terrain.heightmapPixelError = 16;      // Aggressive simplification
            terrain.detailObjectDistance = 30;       // Grass only very close
            terrain.detailObjectDensity = 0.25f;    // Quarter density
            terrain.treeDistance = 200;              // Trees disappear at 200m
            terrain.treeBillboardDistance = 80;      // Billboard at 80m
            terrain.treeCrossFadeLength = 20;        // 20m fade zone
            terrain.treeMaximumFullLODCount = 25;    // Only 25 full-detail trees
            terrain.basemapDistance = 100;            // Base texture at 100m
            break;
        case QualityTier.Ultra:
            terrain.heightmapPixelError = 2;        // Minimal simplification
            terrain.detailObjectDistance = 150;
            terrain.detailObjectDensity = 1.0f;
            terrain.treeDistance = 2000;
            terrain.treeBillboardDistance = 400;
            terrain.treeCrossFadeLength = 50;
            terrain.treeMaximumFullLODCount = 200;
            terrain.basemapDistance = 1000;
            break;
    }
}
```

### 6.3 Virtual Texturing for Terrain

**What it solves:** Terrain with many material layers (rock, dirt, grass, mud, snow, sand) generates massive textures. Virtual texturing streams only the visible tiles.

**Unity approach:**
- Streaming Virtual Texturing (SVT) available in HDRP
- For URP: use terrain splatmap with max 4 layers per pass (each additional 4 layers = another pass)
- Limit to 8 total terrain layers (2 passes) for performance
- Use terrain layer blending with height-based mixing for visual quality without extra layers

**Indirection texture:** A small (64x64) texture maps screen tiles to physical texture pages. Only visible pages are loaded into a texture cache.

### 6.4 Heightmap Resolution vs Visual Quality

| World Size | Heightmap Resolution | Meters per Sample | Visual Result |
|------------|---------------------|-------------------|---------------|
| 1km x 1km | 513x513 | ~1.95m | Adequate for rolling terrain |
| 1km x 1km | 1025x1025 | ~0.98m | Good detail for cliffs/ridges |
| 2km x 2km | 2049x2049 | ~0.98m | Good detail, large world |
| 4km x 4km | 4097x4097 | ~0.98m | Maximum quality, heavy memory |

**Rule of thumb:** ~1 meter per sample is the sweet spot for dark fantasy terrain with cliffs and rocky features. Below 0.5m/sample is wasteful for most terrain.

### 6.5 Terrain Normal Maps for Cheap Lighting Detail

**Technique:** Generate a high-frequency normal map from the heightmap to add micro-detail (rock cracks, erosion channels, soil texture) without increasing mesh resolution.

```
1. Take full-resolution heightmap (e.g., 4097x4097)
2. Generate normal map from height derivatives
3. Tile a detail normal map (rock/soil pattern) at higher frequency
4. Blend world-space normal + detail normal in shader
5. Result: terrain looks detailed even at LOD2/LOD3 mesh resolution
```

The existing VeilBreakers `_terrain_depth.py` and `terrain_materials.py` handlers already compute terrain normals -- these should be exported as normal map textures for Unity terrain shader consumption.

---

## 7. Existing Toolkit Alignment

### What VeilBreakers Already Has (Blender Side)

| Component | File | Status |
|-----------|------|--------|
| Terrain chunking + LOD | `handlers/terrain_chunking.py` | Complete -- bilinear downsampling, overlap borders, neighbor refs, streaming distances |
| Silhouette-preserving LOD | `handlers/lod_pipeline.py` | Complete -- per-asset presets (hero, mob, building, prop, vegetation, weapon, furniture) |
| Blender LOD chain generation | `handlers/pipeline_lod.py` | Complete -- vertex group weighted Decimate |
| Character-aware LOD | `handlers/_character_lod.py` | Complete -- face/hand preservation |
| Per-biome vegetation | `handlers/vegetation_system.py` | Complete -- 14 biomes, Poisson disk, wind vertex colors |
| Terrain noise/erosion | `handlers/_terrain_noise.py`, `_terrain_erosion.py` | Complete |
| Scatter engine | `handlers/_scatter_engine.py` | Complete -- density-based placement |

### What Needs to Be Built (Unity Side)

| Component | Template Location | Status |
|-----------|------------------|--------|
| World streaming manager | `unity_templates/world_templates.py` | Partial -- scene creation/transitions exist, no cell streaming manager |
| Quality presets system | `unity_templates/settings_templates.py` | Partial -- `generate_quality_settings_script` exists but basic |
| GPU Resident Drawer setup | `unity_templates/performance_templates.py` | Missing -- needs auto-configuration script |
| HLOD generator | NEW | Missing -- needs editor script for HLOD processing |
| Dynamic resolution | NEW | Missing -- needs runtime MonoBehaviour |
| Terrain tier configurator | `unity_templates/world_templates.py` | Partial -- terrain detail painting exists, no quality scaling |
| Vegetation LOD/impostor | NEW | Missing -- needs impostor baker integration |

---

## 8. Common Pitfalls

### Pitfall 1: Loading Stutter from Synchronous Operations
**What goes wrong:** Player crosses cell boundary, game hitches for 200ms+ while loading adjacent cell.
**Why it happens:** Any synchronous disk I/O or asset instantiation on the main thread.
**How to avoid:** ALL cell loading must be async (Addressables.LoadSceneAsync). Pre-load cells 2-3 seconds before player reaches boundary. Never instantiate heavy prefabs synchronously.
**Warning signs:** Frame time spikes at regular spatial intervals.

### Pitfall 2: Memory Leaks from Unloaded Cells
**What goes wrong:** RAM usage grows continuously as player explores.
**Why it happens:** Unloaded cells leave orphaned textures, meshes, or GameObjects. References held by singletons or event systems prevent GC.
**How to avoid:** Use Addressables reference counting. Call `Resources.UnloadUnusedAssets()` after cell unloads (but not every frame -- expensive). Audit singleton references to scene objects.
**Warning signs:** Memory profiler shows increasing "Other" allocations over time.

### Pitfall 3: LOD Pop-In
**What goes wrong:** Objects visibly "pop" between LOD levels, breaking immersion.
**Why it happens:** LOD transitions are instant, no cross-fade or dithering.
**How to avoid:** Enable LODGroup cross-fade. Use dithered alpha transitions. Make LOD2->LOD3 transitions happen at distances where player won't notice (100m+).
**Warning signs:** Player reports "flickering" or "shimmering" objects.

### Pitfall 4: Draw Call Explosion from Unique Materials
**What goes wrong:** 1000 unique materials = 1000 draw calls minimum, even with batching.
**Why it happens:** Each prop/building has its own unique material instead of sharing atlased materials.
**How to avoid:** Material atlas policy: groups of related props share one atlas material. Max 50-100 unique materials in a cell. Use material property blocks for color variation (but note: incompatible with GPU Resident Drawer).
**Warning signs:** Frame debugger shows SetPass calls close to total object count.

### Pitfall 5: Terrain Layer Overdraw
**What goes wrong:** Terrain rendering takes 2-3x expected time.
**Why it happens:** More than 4 terrain layers per tile forces additional rendering passes. Each pass re-renders the entire terrain geometry.
**How to avoid:** Limit to 4 layers per terrain tile in URP. Use vertex color blending or height-based blending to reduce layer count. Split visually distinct biomes into separate terrain tiles.
**Warning signs:** GPU profiler shows multiple terrain passes per frame.

### Pitfall 6: Vegetation Overdraw
**What goes wrong:** Transparent grass/leaves cause massive overdraw (same pixel drawn 10x+).
**Why it happens:** Alpha-blended vegetation layers stack.
**How to avoid:** Use alpha-test (cutout) instead of alpha-blend for vegetation. Set render queue correctly. Use LOD to reduce grass density at distance. Limit grass to 2-3 layers of overlap maximum.
**Warning signs:** GPU profiler Overdraw view shows hot spots in vegetated areas.

---

## 9. Architecture Patterns

### 9.1 Recommended Streaming Architecture

```
Assets/
  Scripts/
    Runtime/
      WorldStreaming/
        WorldStreamingManager.cs      -- Main controller, tracks player position
        CellLoader.cs                  -- Async Addressable cell loading
        CellState.cs                   -- State machine (Unloaded/Loading/Loaded/Unloading)
        DistantCellRenderer.cs         -- Impostor/simplified mesh for far cells
        StreamingConfig.cs             -- ScriptableObject with distances/budgets
      QualityScaling/
        QualityTierManager.cs          -- Hardware detection + preset application
        DynamicResolutionController.cs -- Frame-time-based DRS
        AdaptiveQualityMonitor.cs      -- Runtime FPS monitoring + auto-adjust
      Performance/
        HLODSetup.cs                   -- Editor script for HLOD generation
        DrawCallMonitor.cs             -- Runtime draw call budget tracking
  Editor/
    Generated/
      World/                           -- MCP-generated world setup scripts
      Performance/                     -- MCP-generated perf scripts
```

### 9.2 Cell State Machine

```
                    LoadAsync()
  [Unloaded] ───────────────────> [Loading]
      ^                               |
      |                               | OnComplete()
      |         UnloadAsync()         v
  [Unloading] <─────────────────── [Loaded]
      |                               |
      +───────> [Unloaded]            |
       OnComplete()                   |
                                      +──> Active gameplay
```

---

## 10. Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| World streaming | Custom scene manager | Unity Addressables + cell-based loader | Reference counting, async, memory management built-in |
| HLOD generation | Manual mesh merging | Unity HLOD System package | Quadtree spatial splitting, automatic simplification |
| Draw call batching | Custom mesh combiner | GPU Resident Drawer (Unity 6) | 99.7% reduction automatic, GPU occlusion culling included |
| Texture streaming | Manual mip management | QualitySettings.streamingMipmaps | Built into Unity, budget-aware, per-camera |
| LOD transitions | Custom fade scripts | LODGroup cross-fade | Native, dithered, smooth, zero overhead |
| Dynamic resolution | Custom render texture scaling | ScalableBufferManager | Native, no extra render target allocation |
| Impostor baking | Custom billboard renderer | Amplify Impostors or octahedral bake tool | Proven tech, handles parallax, normals, specular |

---

## Sources

### Primary (HIGH confidence)
- Unity 6 Manual: GPU Resident Drawer -- setup, requirements, performance numbers (43.5K to 128 draw calls)
- Unity 6 Manual: Quality Settings, Dynamic Resolution, Terrain, Grass and Details
- Unity Technologies HLODSystem GitHub -- architecture, 83% draw call reduction, 51% triangle reduction
- NVIDIA GPU Gems 2, Ch. 2: Geometry Clipmaps (Hoppe 2004)
- Creation Kit Wiki: Exterior Cells -- Skyrim cell dimensions (4096 units = 58.5m)
- GDC Vault: "Zen of Streaming: Building and Loading Ghost of Tsushima" (2021)
- AMD GPUOpen: Mesh Shaders Procedural Grass Rendering

### Secondary (MEDIUM confidence)
- Ardenfall blog: Open World Streaming in Unity -- 3x3 cell grid, distant cell system
- TheKnightsOfU: GPU Resident Drawer guide with benchmark numbers
- GeneralistProgrammer: Unity Performance Optimization Guide 2025
- Simplygon: Vegetation impostor rendering documentation
- InstaLOD: Optimizing Foliage at Scale (2025)
- Strugar: CDLOD terrain implementation papers

### Tertiary (LOW confidence)
- Community discussions on VRAM tier recommendations (consensus: 8GB minimum for 2025 games)
- Various GameDev.net forum discussions on open world streaming patterns

---

## Metadata

**Confidence breakdown:**
- Streaming architecture: HIGH -- verified against shipping AAA titles, GDC talks, Unity docs
- Quality scaling: HIGH -- derived from Unity documentation + AAA game settings analysis
- Draw call optimization: HIGH -- GPU Resident Drawer numbers from Unity official benchmarks
- Memory budgets: MEDIUM -- VRAM tiers based on community consensus and hardware analysis
- Vegetation techniques: HIGH -- verified via AMD GPUOpen, NVIDIA GPU Gems, Unity docs
- Terrain LOD: HIGH -- verified via academic papers and Unity terrain documentation

**Research date:** 2026-04-02
**Valid until:** 2026-07-02 (3 months -- stable domain, techniques don't change rapidly)
