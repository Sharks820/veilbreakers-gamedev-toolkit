# Unity 6 Terrain, LOD, and Rendering Optimization Research

**Researched:** 2026-04-02
**Domain:** Unity 6 URP Terrain System, LOD, GPU Instancing, Occlusion Culling, Addressable Streaming
**Confidence:** HIGH (verified against official Unity 6 documentation)

---

## 1. Terrain System Configuration Best Practices

### Heightmap Resolution

Unity requires heightmap resolution to be a **power of two plus one** (e.g., 33, 65, 129, 257, 513, 1025, 2049, 4097). Note: 4097x4097 can cause editor stalls -- use with caution.

**Recommended values by terrain tile size:**

| Tile Size | Resolution | Use Case |
|-----------|------------|----------|
| 250m | 257 | Small detail areas |
| 500m | 513 | Standard terrain tiles |
| 1000m | 1025 | Large open areas |
| 2000m | 2049 | Vast landscapes (performance cost) |

### Pixel Error

Controls terrain mesh LOD simplification. **Lower = more faithful rendering, higher = better performance.**

| Quality Level | Pixel Error | Notes |
|---------------|-------------|-------|
| Ultra | 1 | Maximum fidelity, highest triangle count |
| High | 3-5 | Good balance for desktop |
| Medium | 8-12 | Moderate simplification |
| Low | 20-40 | Aggressive simplification for mobile/low-end |

### Base Map Distance

Distance beyond which terrain switches from full-resolution splatmap rendering to a precomputed low-res composite basemap. **Increasing this improves visual quality at distance but costs more draw calls/texture samples.**

| Quality Level | Base Map Distance | Notes |
|---------------|-------------------|-------|
| Ultra | 1500-2000 | Full splat rendering far out |
| High | 1000 | Good desktop default |
| Medium | 600 | Moderate fallback |
| Low | 300 | Quick fallback to basemap |

### Detail and Tree Settings

| Setting | Description | Recommended Range |
|---------|-------------|-------------------|
| **Detail Distance** | Culling range for grass/detail meshes | 60-250m |
| **Detail Density Scale** | Multiplier (0-1) for detail population | 0.3 (Low) to 1.0 (Ultra) |
| **Detail Resolution** | Splatmap for detail painting (0-4048 squared) | 512-2048 |
| **Detail Resolution Per Patch** | Pixels per detail patch (8-128) | 16-32 |
| **Tree Distance** | Culling range for trees | 2000-5000m |
| **Billboard Start** | Distance where 3D trees become billboards | 50-200m |
| **Fade Length** | Transition distance 3D-to-billboard | 5-20m |
| **Max Mesh Trees** | Max visible 3D trees before forced billboard | 50-500 |

### Texture Resolutions

| Setting | Description | Recommended |
|---------|-------------|-------------|
| **Control Texture Resolution** | Splatmap resolution for texture blending | 512-2048 per tile |
| **Base Texture Resolution** | Composite texture for distant rendering | 1024-2048 |

Source: [Unity 6.3 Terrain Settings Reference](https://docs.unity3d.com/6000.3/Documentation/Manual/terrain-OtherSettings.html)

---

## 2. Terrain Shader Layers and Performance Limits

### URP Terrain Layer Limits

**Critical rule: 4 layers per texture pass in URP.** Each additional pass beyond 4 layers doubles the terrain rendering cost for that tile.

| Render Pipeline | Layers Per Pass | Total Layers | Notes |
|-----------------|-----------------|--------------|-------|
| **URP** | 4 | Unlimited (multi-pass) | Each pass adds a full terrain redraw |
| **HDRP** | 8 | 8 max per tile | Single pass, layers beyond 8 render as black |
| **Built-in** | 4 | Unlimited (multi-pass) | Same as URP |

**Best practice for VeilBreakers (URP):** Limit to **4 terrain layers per tile** to stay in a single pass. If more variety is needed, use vertex-blended detail meshes or decals on top rather than adding terrain layers.

### Terrain Layer Texture Channels

Each terrain layer supports:

| Texture | Channels | Purpose |
|---------|----------|---------|
| **Diffuse** | RGB + A | Base color; Alpha = smoothness (URP) or density (if Mask Map assigned) |
| **Normal Map** | RGB | Surface normals; Normal Scale controls strength |
| **Mask Map** | R=Metallic, G=AO, B=Height, A=Smoothness | Full PBR channel packing |

**Performance note:** Mask Maps enable height-based blending between layers (visually superior) but add texture samples. Use only on High/Ultra quality.

### URP Terrain Shader Compatibility

**Important:** URP Terrain shaders are **NOT SRP Batcher compatible**. This means terrain draw calls cannot be batched with the SRP Batcher. This is a known limitation -- terrain batching relies on its own internal chunking system instead.

**Unity 6.3 addition:** Terrain Shaders in Shader Graph are now available, allowing custom terrain shaders. This is a significant new feature for visual customization.

Source: [Unity Terrain Layers Manual](https://docs.unity3d.com/Manual/class-TerrainLayer.html)

---

## 3. LOD Group Settings and Screen-Relative Transitions

### LOD Group Component Configuration

The LOD Group component controls mesh LOD switching based on **screen-relative height** -- the percentage of the screen height the object's bounding box occupies.

| Setting | Description |
|---------|-------------|
| **Screen Relative Transition Height** | Percentage (0-1) of screen height where LOD activates |
| **Fade Mode** | None, Cross Fade, or SpeedTree |
| **Animate Cross-fading** | Unified transition duration across all LODs |
| **Fade Transition Width** | Per-LOD transition width (when Animate Cross-fading is off) |

### Recommended LOD Transition Percentages

| LOD Level | Screen Height % | Description |
|-----------|-----------------|-------------|
| **LOD 0** | 60-100% | Full detail, object fills >60% screen height |
| **LOD 1** | 30-60% | High detail |
| **LOD 2** | 15-30% | Medium detail |
| **LOD 3** | 5-15% | Low detail |
| **Culled** | <1-5% | Object too small to see, removed entirely |

### Fade Mode Options

| Mode | Use Case | Notes |
|------|----------|-------|
| **None** | Best performance | Hard pop between LODs -- visible on large objects |
| **Cross Fade** | General use | Smooth dithered transition; uses alpha testing (GPU cost) |
| **SpeedTree** | SpeedTree models only | Vertex position interpolation (.spm/.st files) |

### LOD Bias (Quality Settings)

`QualitySettings.lodBias` scales all LOD transition distances:

| LOD Bias | Effect | Use For |
|----------|--------|---------|
| 0.3-0.5 | Aggressively uses lower LODs | Mobile / Low quality |
| 1.0 | Default transitions | Medium quality |
| 1.5-2.0 | Maintains higher LODs longer | High / Ultra quality |

### Maximum LOD Level (Quality Settings)

`QualitySettings.maximumLODLevel` excludes LOD levels from builds entirely:

| Value | Effect |
|-------|--------|
| 0 | All LOD levels included (default) |
| 1 | LOD0 excluded (never shows highest detail) |
| 2 | LOD0 and LOD1 excluded |

**Use case:** Set to 1 on mobile to save memory by excluding the highest-detail meshes from the build.

Source: [Unity LOD Group Manual](https://docs.unity3d.com/Manual/class-LODGroup.html)

---

## 4. GPU Instancing Setup for Vegetation

### Enabling GPU Instancing

GPU instancing renders multiple instances of the same mesh+material in a single draw call. **Critical for vegetation, rocks, and repeated props.**

**Setup steps:**
1. Select the Material in the Inspector
2. Check **Enable GPU Instancing** checkbox
3. Ensure the shader supports instancing (most standard shaders do)

### Terrain Detail Instancing

For terrain grass and detail meshes, use **Instanced Mesh** render mode:

| Render Mode | GPU Instancing | Wind | Lighting | Notes |
|-------------|----------------|------|----------|-------|
| **Vertex Lit** | No | No | Simplified | Solid unlit objects |
| **Grass** | Yes | Yes | Simplified | Meshes with wind animation |
| **Grass Texture** | Yes | Yes | Simplified | Billboard quads from textures |
| **Instanced Mesh** | Yes | Via shader | Full shader | **Recommended** -- uses prefab's shader and material |

**Instanced Mesh** is the recommended mode because:
- Uses persistent constant buffers for better CPU/GPU performance
- Supports custom shaders and Shader Graph
- Generates random size/color variation via Perlin noise automatically
- Batches up to **1,023 instances per draw call**

### GPU Instancing Limitations

| Limitation | Details |
|------------|---------|
| Skinned Mesh Renderers | Not supported -- only Mesh Renderers |
| Light Probes | Not supported for instanced terrain details |
| Lightmaps | Not supported for instanced terrain details |
| SRP Batcher conflict | GPU Instancing and SRP Batcher are mutually exclusive per shader |
| Platform requirement | Target must support compute/instancing |
| Batch size | Max 1,023 instances per batch |

### SRP Batcher vs GPU Instancing

**In URP, the SRP Batcher and GPU Instancing are mutually exclusive on a per-shader basis:**

| Technique | Best For | How It Works |
|-----------|----------|--------------|
| **SRP Batcher** | Many different meshes, same shader variant | Persistent CBUFFER, reduces CPU setup between draw calls |
| **GPU Instancing** | Many identical meshes (vegetation, rocks) | Single draw call for all instances of same mesh+material |

**Strategy for VeilBreakers:**
- Use **SRP Batcher** for general scene objects (buildings, props, characters)
- Use **GPU Instancing** for vegetation, terrain details, and repeated environmental objects
- Make vegetation shaders SRP Batcher-incompatible so they fall through to GPU Instancing

Source: [Unity GPU Instancing Manual](https://docs.unity3d.com/Manual/GPUInstancing.html), [Unity Terrain Grass Manual](https://docs.unity3d.com/Manual/terrain-Grass.html)

---

## 5. Draw Call Batching (SRP Batcher, Static/Dynamic)

### SRP Batcher (Primary Batching in URP)

**Enable:** URP Asset Inspector > Rendering > SRP Batcher (checkbox)

The SRP Batcher does NOT reduce draw calls -- it reduces **CPU setup time between draw calls** by making material data persistent in GPU memory. This is the primary batching mechanism in URP.

**Compatibility requirements:**
- Shader must declare all material properties in a single CBUFFER named `UnityPerMaterial`
- Shader must declare all built-in engine properties in a single CBUFFER named `UnityPerDraw`
- All URP Lit/Unlit/SimpleLit shaders are compatible by default

**Verification:** In Frame Debugger (Window > Analysis > Frame Debugger), compatible batches show "SRP Batch" in the batch cause.

**Terrain note:** URP Terrain shaders are NOT SRP Batcher compatible. Terrain uses its own internal batching via chunked rendering.

### Static Batching

Combines static meshes sharing the same material into larger meshes at build time. **Still works in URP alongside SRP Batcher**, but SRP Batcher typically provides better results.

**When to use static batching:**
- Many small identical meshes that never move (decorative rocks, fence posts)
- When combined mesh vertex count stays under 65,535 (or 32-bit index buffer limit)

**Enable:** Player Settings > Other Settings > Static Batching (checkbox)
Mark objects as Batching Static in Inspector.

### Dynamic Batching

**Generally NOT recommended in URP.** The SRP Batcher replaces its use case. Dynamic batching has strict vertex count limits (300 attributes) and CPU overhead.

**Enable only if:** Targeting very low-end hardware without SRP Batcher support.

Source: [Unity SRP Batcher Manual](https://docs.unity3d.com/6000.3/Documentation/Manual/SRPBatcher-Enable.html)

---

## 6. Occlusion Culling Configuration

### Setup Process

1. **Mark Static Occluders:** Select large solid objects (walls, buildings, terrain) > Inspector > Static dropdown > check **Occluder Static**
2. **Mark Static Occludees:** Select objects that can be hidden > check **Occludee Static**
3. **Enable on Camera:** Inspector > Camera component > Occlusion Culling = enabled
4. **Bake:** Window > Rendering > Occlusion Culling > Bake tab > Bake

### Bake Settings

| Setting | Description | Recommended |
|---------|-------------|-------------|
| **Smallest Occluder** | Minimum size of objects that block visibility | 5-10m for large worlds |
| **Smallest Hole** | Minimum gap size the system considers | 0.25-0.5m |
| **Backface Threshold** | Percentage of backfaces before removal | 100 (default) |

### Best Practices for Terrain

| Guideline | Details |
|-----------|---------|
| Terrain as Occluder | Terrain with Terrain Renderer is a valid Static Occluder |
| LOD0 for Occlusion | Unity uses LOD0 silhouette for occlusion calculations |
| Silhouette consistency | If LOD0 and LOD3 differ significantly in shape, object may not occlude well |
| Large buildings | Best occluders -- mark as Occluder Static |
| Vegetation | Generally NOT good occluders (too many gaps) -- mark as Occludee Static only |
| Dynamic objects | Cannot be occluders, only occludees if marked static |

### Occlusion Culling + LOD Interaction

- Unity evaluates occlusion against LOD0 geometry
- If an object's LOD0 is large enough to occlude, all LOD levels benefit from the occlusion data
- Occluded objects skip ALL rendering (including LOD evaluation), saving both CPU and GPU

Source: [Unity 6 Occlusion Culling Setup](https://docs.unity3d.com/6000.6/Documentation/Manual/occlusion-culling-getting-started.html)

---

## 7. Quality Settings Scaling (Low/Med/High/Ultra Presets)

### Creating Quality Presets

**Path:** Edit > Project Settings > Quality

Create presets by duplicating and renaming. Assign different URP Asset per quality level for full render pipeline control.

### Recommended Quality Preset Configuration

#### Terrain-Specific Quality Overrides (Unity 6 Feature)

Unity 6 added **Terrain Quality Overrides** in Quality Settings, allowing per-quality-level terrain configuration. Terrains with "Ignore Quality Settings" disabled will automatically adopt these values.

| Setting | Low | Medium | High | Ultra |
|---------|-----|--------|------|-------|
| Pixel Error | 30 | 12 | 5 | 1 |
| Base Map Distance | 300 | 600 | 1000 | 2000 |
| Detail Density Scale | 0.3 | 0.5 | 0.8 | 1.0 |
| Detail Distance | 60 | 100 | 180 | 250 |
| Tree Distance | 1500 | 3000 | 5000 | 5000 |
| Billboard Start | 30 | 80 | 150 | 200 |
| Fade Length | 5 | 10 | 15 | 20 |
| Max Mesh Trees | 50 | 150 | 300 | 500 |

#### LOD Settings Per Quality Level

| Setting | Low | Medium | High | Ultra |
|---------|-----|--------|------|-------|
| LOD Bias | 0.4 | 0.7 | 1.0 | 2.0 |
| Maximum LOD Level | 2 | 1 | 0 | 0 |
| LOD Cross Fade | Off | Off | On | On |

#### Texture Settings Per Quality Level

| Setting | Low | Medium | High | Ultra |
|---------|-----|--------|------|-------|
| Global Mipmap Limit | Quarter Res | Half Res | Full Res | Full Res |
| Anisotropic Textures | Disabled | Per Texture | Forced On | Forced On |
| Texture Streaming | On (256MB) | On (512MB) | On (1024MB) | Off |

#### Shadow Settings Per Quality Level

| Setting | Low | Medium | High | Ultra |
|---------|-----|--------|------|-------|
| Shadow Distance | 50 | 100 | 150 | 250 |
| Shadow Cascades | 1 | 2 | 4 | 4 |
| Shadow Resolution | Low | Medium | High | Very High |

#### URP Asset Per Quality Level

Create separate URP Assets (e.g., `URP_Low`, `URP_Med`, `URP_High`, `URP_Ultra`) and assign each to its quality level. This controls:
- Anti-aliasing (None / 2x / 4x / 8x MSAA)
- Render scale (0.5 / 0.75 / 1.0 / 1.0)
- Additional lights count
- Shadow atlas resolution
- Post-processing features

### Runtime Quality Switching (C# API)

```csharp
// Switch quality level at runtime
// index = quality level index, applyExpensiveChanges = true for full switch
QualitySettings.SetQualityLevel(int index, bool applyExpensiveChanges = true);

// Get current level
int current = QualitySettings.GetQualityLevel();

// Get available quality level names
string[] names = QualitySettings.names;

// IMPORTANT: Quality level indices may differ between platforms
// because unused levels are stripped from builds.
// Always query available levels rather than hardcoding indices.

// Individual terrain property overrides at runtime:
QualitySettings.terrainPixelError = 5f;
QualitySettings.terrainDetailDensityScale = 0.8f;
QualitySettings.terrainDetailDistance = 180f;
QualitySettings.terrainTreeDistance = 5000f;
QualitySettings.terrainBillboardStart = 150f;
QualitySettings.terrainFadeLength = 15f;
QualitySettings.terrainMaxMeshTrees = 300;

// LOD overrides:
QualitySettings.lodBias = 1.0f;
QualitySettings.maximumLODLevel = 0;

// For URP-specific settings, swap the render pipeline asset:
// QualitySettings already handles this via the assigned URP Asset per level
```

**Performance tip:** Pass `applyExpensiveChanges: false` for frequent runtime adjustments (e.g., dynamic quality scaling). Use `true` only for deliberate user-initiated quality changes.

Source: [Unity Quality Settings Reference](https://docs.unity3d.com/6000.0/Documentation/Manual/class-QualitySettings.html), [QualitySettings API](https://docs.unity3d.com/ScriptReference/QualitySettings.SetQualityLevel.html)

---

## 8. Texture Streaming (Mipmap Streaming) Setup

### Global Enable

**Path:** Edit > Project Settings > Quality > Textures > Mipmap Streaming

| Setting | Description | Recommended |
|---------|-------------|-------------|
| **Mipmap Streaming** | Master toggle | Enabled for open-world games |
| **Add All Cameras** | Auto-stream for all cameras | Enabled (disable per-camera if needed) |
| **Memory Budget** | Max GPU memory for streaming textures (MB) | 512-1024 MB desktop, 256 MB mobile |
| **Max Level Reduction** | Limits how aggressively mips are reduced | 2 (never go below mip level 2) |

### Per-Texture Configuration

In the Texture Import Settings:
1. Check **Streaming Mipmaps** on each texture
2. Set **Mip Map Priority** (higher = loads sooner at full resolution)

Terrain textures should have **high priority** since they are always visible.

### Per-Camera Control via Streaming Controller

Add a `StreamingController` component to cameras for fine-grained control:

| Property | Description |
|----------|-------------|
| **Mipmap Bias** | Offset added to computed mip level (higher = lower res) |
| **Enabled** | Toggle streaming for this camera |

### Memory Budget Estimation

```csharp
// At runtime, measure actual texture demand:
float desiredMemory = Texture.desiredTextureMemory;
// Set budget slightly above this value

// Monitor streaming status:
float currentMemory = Texture.currentTextureMemory;
bool isStreaming = Texture.streamingTextureCount > 0;
```

### Performance Recommendations

| Tip | Details |
|-----|---------|
| Budget headroom | Set budget 10-20% above `desiredTextureMemory` to avoid popping |
| Terrain textures | High mip priority -- always visible, popping is very noticeable |
| Distant objects | Lower priority acceptable -- LOD transition masks mip changes |
| Loading screens | Pre-warm by activating cameras at loading positions |

Source: [Unity 6 Mipmap Streaming Configuration](https://docs.unity3d.com/6000.2/Documentation/Manual/TextureStreaming-configure.html)

---

## 9. Addressable Asset Loading for Open World Streaming

### Architecture: Scene-Based Terrain Chunks

The recommended approach for open world terrain streaming uses **additive scene loading** with Addressables:

```
WorldRoot (persistent scene)
  +-- TerrainChunk_0_0 (additive scene)
  +-- TerrainChunk_0_1 (additive scene)
  +-- TerrainChunk_1_0 (additive scene)
  ...loaded/unloaded based on player distance
```

### Addressables Scene Loading API

```csharp
using UnityEngine.AddressableAssets;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceProviders;
using UnityEngine.SceneManagement;

// Load a terrain chunk scene additively
AsyncOperationHandle<SceneInstance> handle = Addressables.LoadSceneAsync(
    "TerrainChunk_0_0",           // address or AssetReference
    LoadSceneMode.Additive,        // additive loading
    activateOnLoad: true,          // activate immediately
    priority: 100                  // higher = loads sooner
);

// Wait for completion
handle.Completed += (op) => {
    if (op.Status == AsyncOperationStatus.Succeeded) {
        // Chunk loaded and active
        SceneInstance scene = op.Result;
    }
};

// Unload a terrain chunk
Addressables.UnloadSceneAsync(handle);
```

### Using AssetReference for Inspector-Driven Loading

```csharp
[System.Serializable]
public class TerrainChunkRef
{
    public AssetReference sceneRef;
    public Vector2Int gridPosition;
    public float loadDistance = 600f;
    public float unloadDistance = 1200f;
}

// In your WorldStreamingManager:
public TerrainChunkRef[] chunks;

// Load via AssetReference:
AsyncOperationHandle<SceneInstance> handle = chunks[i].sceneRef.LoadSceneAsync(
    LoadSceneMode.Additive, activateOnLoad: true);
```

### Streaming Strategy: Distance-Based Loading

| Zone | Distance | Action | Content |
|------|----------|--------|---------|
| **Active** | 0-600m | Full scene loaded | Full terrain + details + trees + objects |
| **Near** | 600-1200m | LOD impostor scene | Low-poly terrain mesh + billboard trees |
| **Far** | 1200-2500m | Distant impostor | Baked terrain mesh, atlas texture, no details |
| **Culled** | >2500m | Unloaded | Nothing in memory |

### Practical Loading Pattern (3x3 Grid)

```csharp
// Load a 3x3 grid of chunks around the player's current cell
Vector2Int playerCell = WorldToCell(player.position);

for (int x = -1; x <= 1; x++)
{
    for (int z = -1; z <= 1; z++)
    {
        Vector2Int cell = playerCell + new Vector2Int(x, z);
        if (!IsChunkLoaded(cell))
            LoadChunk(cell);
    }
}

// Unload chunks beyond the 3x3 grid
foreach (var loadedChunk in loadedChunks)
{
    if (Vector2Int.Distance(loadedChunk.gridPos, playerCell) > 2)
        UnloadChunk(loadedChunk);
}
```

### Distant Cell Impostors

For terrain visible beyond the active loading range:
1. **Bake terrain heightmap to low-poly mesh** at build time
2. **Pack splatmaps into texture atlas** (single material for all distant terrains)
3. **Generate tree billboards** as part of the distant cell prefab
4. Load these as lightweight prefabs (not full scenes)

### Performance Considerations

| Concern | Solution |
|---------|----------|
| Loading hitches | Use `activateOnLoad: false`, then activate over multiple frames |
| Memory spikes | Limit concurrent loads (max 2-3 chunks loading simultaneously) |
| Terrain seams | Set neighbor terrains via `Terrain.SetNeighbors()` after loading |
| Asset duplication | Use shared Addressable groups for common terrain layers/materials |
| Build size | Pack terrain chunks into separate Addressable groups per region |

**Important:** Setting `activateOnLoad: false` blocks the entire Addressables async operation queue until the scene is manually activated. Use this intentionally with a loading manager that activates scenes in order.

Source: [Unity Addressables LoadSceneAsync](https://docs.unity3d.com/Packages/com.unity.addressables@2.0/manual/LoadingScenes.html), [Ardenfall Open World Streaming](https://ardenfall.com/blog/world-streaming-in-unity)

---

## 10. Combined Optimization Strategy for VeilBreakers

### Draw Call Reduction Priority

1. **SRP Batcher** (enabled globally via URP Asset) -- handles all standard scene objects
2. **GPU Instancing** (per-material) -- handles vegetation, terrain details, repeated props
3. **Static Batching** (per-object flag) -- handles small static decorative elements
4. **Occlusion Culling** (baked) -- eliminates hidden objects entirely

### Terrain-Specific Pipeline

```
Terrain Tile Setup:
  1. Max 4 layers per tile (single-pass URP)
  2. Use Mask Maps for height-blend on High/Ultra only
  3. Terrain details use Instanced Mesh mode
  4. Detail scatter mode = Coverage (not Instance Count)
  5. Enable GPU Instancing on detail prefab materials
  6. Bake occlusion culling with terrain as Occluder Static
  7. Set quality overrides in Quality Settings for terrain params
```

### Memory Budget Guidelines

| Platform | Texture Streaming Budget | Notes |
|----------|--------------------------|-------|
| Desktop (8GB+ VRAM) | 1024-2048 MB | Ultra quality, no streaming if VRAM allows |
| Desktop (4GB VRAM) | 512-1024 MB | High quality with streaming |
| Desktop (2GB VRAM) | 256-512 MB | Medium quality, aggressive streaming |
| Mobile / Low-end | 128-256 MB | Low quality, aggressive mip reduction |

### Unity 6 New Features Relevant to Terrain

| Feature | Status | Impact |
|---------|--------|--------|
| Terrain Shaders in Shader Graph (6.3) | New | Custom terrain shaders without hand-coded HLSL |
| Terrain Quality Overrides in QualitySettings | New in 6 | Per-quality-level terrain params without scripting |
| GPU Resident Drawer | New in 6 | GPU-driven rendering for massive instance counts |
| Ray Tracing on Terrain | New in 6 | Reflections/GI on terrain (HDRP/URP+) |
| Motion Vectors for Animated Trees | New in 6 | Better motion blur on SpeedTree vegetation |

---

## Sources

### Primary (HIGH confidence)
- [Unity 6.3 Terrain Settings Reference](https://docs.unity3d.com/6000.3/Documentation/Manual/terrain-OtherSettings.html)
- [Unity Terrain Layers Manual](https://docs.unity3d.com/Manual/class-TerrainLayer.html)
- [Unity LOD Group Manual](https://docs.unity3d.com/Manual/class-LODGroup.html)
- [Unity GPU Instancing Manual](https://docs.unity3d.com/Manual/GPUInstancing.html)
- [Unity Terrain Grass/Details Manual](https://docs.unity3d.com/Manual/terrain-Grass.html)
- [Unity 6 Occlusion Culling Setup](https://docs.unity3d.com/6000.6/Documentation/Manual/occlusion-culling-getting-started.html)
- [Unity 6 Quality Settings Reference](https://docs.unity3d.com/6000.0/Documentation/Manual/class-QualitySettings.html)
- [Unity 6 Mipmap Streaming Configuration](https://docs.unity3d.com/6000.2/Documentation/Manual/TextureStreaming-configure.html)
- [Unity SRP Batcher Enable (URP)](https://docs.unity3d.com/6000.3/Documentation/Manual/SRPBatcher-Enable.html)
- [Unity Addressables LoadSceneAsync](https://docs.unity3d.com/Packages/com.unity.addressables@2.0/manual/LoadingScenes.html)
- [Unity QualitySettings.SetQualityLevel API](https://docs.unity3d.com/ScriptReference/QualitySettings.SetQualityLevel.html)

### Secondary (MEDIUM confidence)
- [URP Performance Optimization Guide](https://docs.unity3d.com/6000.1/Documentation/Manual/urp/configure-for-better-performance.html)
- [Ardenfall Open World Streaming](https://ardenfall.com/blog/world-streaming-in-unity) -- practical implementation reference
- [Unity Performance Optimization Guide 2025](https://generalistprogrammer.com/tutorials/unity-performance-optimization-complete-technical-guide-2025)

### Tertiary (LOW confidence -- community sources)
- [Unity Discussions: Terrain texture layer performance](https://discussions.unity.com/t/terrain-texture-layer-performance/887411)
- [Unity Discussions: LOD + Occlusion Culling](https://discussions.unity.com/t/lod-occlusion-culling/674002)
- [Unity Discussions: Best approach for large open world terrain streaming](https://discussions.unity.com/t/best-approach-for-handling-large-open-world-terrain-streaming/1710438)
