# Asset Pipeline Research: Blender Generation to Unity Game Build

**Researched:** 2026-04-02
**Domain:** Blender-to-Unity asset pipeline, Unity import/build optimization
**Confidence:** HIGH (based on codebase audit + official Unity docs + glTFast docs)

## Summary

The VeilBreakers MCP toolkit has strong capabilities on both ends of the pipeline -- Blender generation/export and Unity import/configuration -- but has significant gaps in the MIDDLE of the pipeline: the automated handoff between Blender export and Unity import, LOD group setup on the Unity side, GLB/glTF import configuration (toolkit only handles FBX), and build optimization orchestration.

The Blender side exports both FBX and glTF/GLB with Unity-optimized settings. The Unity side has FBX import configuration, texture import, material remapping, atomic import sequences, and an AssetPostprocessor generator. However, there is no automated end-to-end flow that takes a Blender-generated asset and produces a game-ready Unity prefab with LODs, colliders, Addressable labels, and correct import settings -- all in one pass.

**Primary recommendation:** Use GLB as the primary export format for PBR assets (direct metallic-roughness mapping to URP Lit), keep FBX for animated/rigged characters (better Mecanim support). Build a unified AssetPostprocessor that auto-configures imports by folder convention, and add missing Unity-side tools for LODGroup setup, Addressable labeling, lightmap/NavMesh bake orchestration, and build size analysis.

## Project Constraints (from CLAUDE.md)

- Pipeline order is LOCKED: repair -> UV -> texture -> rig -> animate -> export
- Always run `blender_mesh action=game_check` before ANY export
- Unity two-step pattern: tool writes C# script, must recompile + execute
- Use seeds for reproducible generation
- Batch when possible
- Visual verification after Blender mutations

---

## 1. Blender to Unity Export Formats

### GLB/glTF vs FBX Comparison

| Feature | GLB/glTF | FBX | Recommendation |
|---------|----------|-----|----------------|
| **PBR Materials** | Native metallic-roughness -- maps directly to URP Lit | Phong/Lambert -- requires manual shader remapping | GLB wins |
| **Vertex Colors** | Fully preserved (export_colors=True in toolkit) | Preserved but may need manual enable | GLB wins |
| **UVs** | Up to 2 UV sets supported by shaders | Multiple UV sets | Tie (2 is enough) |
| **Normal Maps** | Embedded or referenced, tangent space | Embedded, tangent space | Tie |
| **Animations** | Supported via Legacy system; Mecanim import possible but clips not auto-assigned | Full Mecanim/Humanoid support with auto-assignment | FBX wins for animation |
| **Blend Shapes** | Fully supported (morph targets) | Fully supported | Tie |
| **LODs** | NOT in glTF spec -- no native LOD support | NOT native, but naming convention LOD0/LOD1 works with Unity | FBX wins slightly |
| **Mesh Compression** | Draco compression via KHR_draco_mesh_compression | None in format, Unity compresses on import | GLB wins for file size |
| **Unity Import** | Requires glTFast package (com.unity.cloud.gltfast) | Native Unity importer | FBX wins for zero-dependency |
| **Scale/Axis** | Y-up, meters (glTF spec) -- matches Unity directly | Requires axis conversion + scale factor | GLB wins |
| **File Size** | Binary GLB is compact, Draco makes it smaller | Larger files, especially with embedded textures | GLB wins |
| **Embedded Textures** | Binary chunk stores textures efficiently | Textures embedded in FBX are large | GLB wins |

### Decision Matrix

| Asset Type | Recommended Format | Reason |
|------------|-------------------|--------|
| Static props/environment | **GLB** | PBR materials transfer perfectly, smaller files |
| Animated characters | **FBX** | Mecanim/Humanoid auto-setup, animation clip assignment |
| Weapons/equipment | **GLB** | PBR materials, no animation needed |
| Vegetation | **GLB** | PBR, vertex colors for wind, smaller files |
| Buildings/architecture | **GLB** | PBR, large models benefit from Draco compression |
| Rigged NPCs | **FBX** | Animation retargeting needs Mecanim |

### What Metadata Survives Export

**Always preserved (both formats):**
- Mesh geometry (vertices, faces, normals)
- UV coordinates (UV0, UV1)
- Vertex colors
- Material assignments (material slots)
- Tangent space data (when export_tangents/use_tspace enabled -- toolkit does this)

**GLB-specific preservation:**
- PBR metallic-roughness values (baseColorFactor, metallicFactor, roughnessFactor)
- Normal map strength
- Occlusion texture
- Emissive color and texture
- Alpha mode (opaque/mask/blend)
- Double-sided flag

**FBX-specific preservation:**
- Animation clips with keyframes
- Armature/skeleton hierarchy
- Blend shape channels with names
- Custom properties (partial -- Unity reads some)

**NOT preserved (either format):**
- Blender Geometry Nodes (baked to mesh on export)
- Blender particle systems (must bake to mesh)
- Blender-specific modifiers (must apply before export)
- Blender materials/node trees (converted to PBR approximation)
- LOD relationships (must use naming conventions)

### Current Toolkit Export Settings (from export.py)

**FBX export settings (Unity-optimized):**
```python
{
    "apply_unit_scale": True,
    "apply_scale_options": "FBX_SCALE_ALL",
    "bake_space_transform": True,
    "axis_forward": "-Z",
    "axis_up": "Y",
    "add_leaf_bones": False,         # Clean skeleton hierarchy
    "mesh_smooth_type": "FACE",
    "use_tspace": True,              # Tangent space for normal maps
    "use_armature_deform_only": True, # Skip non-deform bones
}
```

**glTF/GLB export settings:**
```python
{
    "export_format": "GLB",
    "export_tangents": True,
    "export_materials": "EXPORT",
    "export_colors": True,           # Vertex colors
    "export_image_format": "AUTO",
    "export_yup": True,              # Y-up matches Unity
}
```

### GAP: Missing Export Options
The current `blender_export` tool is minimal -- it lacks:
- **LOD export**: No naming convention enforcement (LOD0, LOD1, LOD2 suffixes)
- **Draco compression**: Not enabled for GLB export
- **Custom property export**: Not passing through Blender custom props
- **Batch export**: No multi-object export to separate files
- **Texture bake before export**: No auto-bake of procedural textures
- **Collision mesh export**: No separate collision mesh handling (UCX_ prefix)

---

## 2. Unity Asset Import Pipeline

### Unity Import Settings That Matter

**Model Import (ModelImporter):**

| Setting | Default | Recommended for Props | Recommended for Characters |
|---------|---------|----------------------|---------------------------|
| Scale Factor | 1.0 | 1.0 (if Blender exports at correct scale) | 1.0 |
| Import Normals | Import | Import (use Blender normals) | Import |
| Import Tangents | Calculate Mikktspace | Calculate Mikktspace | Calculate Mikktspace |
| Mesh Compression | Off | Low or Medium | Off (preserve quality) |
| Read/Write Enabled | false | false (saves memory) | false unless runtime deformation |
| Optimize Mesh | true | true | true |
| Import BlendShapes | false | false (props don't need) | true |
| Import Animation | false | false | true |
| Animation Type | None | None | Generic or Humanoid |
| Material Import Mode | None (remap manually) | None | None |

**Texture Import (TextureImporter):**

| Setting | Albedo/Diffuse | Normal Map | Metallic/Roughness/AO | UI Sprites |
|---------|---------------|------------|----------------------|------------|
| sRGB | true | false | false | true |
| Max Size | 2048 | 2048 | 1024 | 512 |
| Mipmaps | true | true | true | false |
| Filter Mode | Bilinear | Bilinear | Bilinear | Point or Bilinear |
| Wrap Mode | Repeat | Repeat | Repeat | Clamp |
| Compression | Normal Quality | Normal Quality | Normal Quality | High Quality |

**Platform-Specific Texture Compression:**

| Platform | Albedo Format | Normal Format | Mask Format |
|----------|--------------|---------------|-------------|
| PC/Standalone | BC7 (DXT5 fallback) | BC5 (DXT5nm) | BC4 |
| Android | ASTC 6x6 | ASTC 4x4 | ASTC 6x6 |
| iOS | ASTC 6x6 | ASTC 4x4 | ASTC 6x6 |
| WebGL | DXT5 | DXT5 | DXT1 |

### What the Toolkit Already Has

1. **`unity_assets configure_fbx`** -- Configures ModelImporter settings with presets (hero, monster, weapon, prop, environment). Handles scale, compression, animation type, normals mode, blend shapes, optimization, readability. **SOLID.**

2. **`unity_assets configure_texture`** -- Configures TextureImporter with auto-detect sRGB from filename, platform overrides, presets. **SOLID.**

3. **`unity_assets remap_materials`** -- Remaps FBX materials to existing Unity materials. **SOLID.**

4. **`unity_assets auto_materials`** -- Auto-generates URP Lit materials from texture directory with convention-based mapping. **SOLID.**

5. **`unity_assets atomic_import`** -- Full import sequence: textures -> material -> FBX -> remap, wrapped in StartAssetEditing/StopAssetEditing. **SOLID.**

6. **`unity_pipeline create_asset_postprocessor`** -- Generates AssetPostprocessor with folder-based rules for textures, models, audio. Uses OnPreprocess (not OnPostprocess) to avoid reimport loops. Includes GetVersion(). **SOLID.**

### GAPs in Unity Import Pipeline

| Gap | Description | Impact |
|-----|-------------|--------|
| **No GLB import configuration** | `configure_fbx` only handles FBX. No equivalent for GLB/glTF import settings via glTFast | Cannot configure GLB imports programmatically |
| **No LODGroup setup** | LOD chain generated in Blender but no Unity tool sets up LODGroup component | LODs from Blender are imported as separate meshes, never used as LODs |
| **No automatic prefab generation from import** | Atomic import creates material + configures import but does not create a prefab | Must manually create prefab after every import |
| **No collider auto-setup** | No tool adds MeshCollider/BoxCollider based on asset type | Every imported asset needs manual collider setup |
| **No Addressable label assignment** | `unity_build configure_addressables` creates groups but no tool labels individual assets | Assets imported but never added to Addressable groups |
| **No import validation/verification** | No post-import check that materials mapped correctly, scale is right, normals look correct | Silent import failures go undetected |
| **No batch import** | atomic_import handles one asset at a time, no folder-wide batch | Importing 50 assets requires 50 separate tool calls |

### ScriptedImporter for GLB

Unity's glTFast package (com.unity.cloud.gltfast) registers as the default ScriptedImporter for .gltf and .glb extensions. Key facts:

- **Package ID:** `com.unity.cloud.gltfast`
- **Latest version:** 6.8.0
- **Import behavior:** Creates native Unity prefab in asset database
- **Material handling:** Auto-creates URP Lit materials from glTF PBR data
- **Draco support:** Via `com.unity.cloud.draco` package
- **meshopt support:** Via `com.unity.meshopt.decompress` package
- **Limitation:** Animation clips importable as Mecanim-compatible but NOT auto-assigned to Animator
- **Limitation:** Only 2 UV sets supported by shaders
- **Limitation:** No LOD support in glTF spec

### AssetPostprocessor Best Practices

The toolkit's `create_asset_postprocessor` generates correct code but needs enhancement:

1. **Use OnPreprocessModel** (not OnPostprocessModel) for ModelImporter changes -- toolkit does this correctly
2. **Include GetVersion()** -- toolkit does this correctly
3. **Thread safety for parallel import** -- code must be self-contained, no Editor state changes
4. **Folder convention enforcement** -- needs standard folder -> settings mapping for VeilBreakers

Recommended folder conventions for the postprocessor:

```
Assets/Art/Characters/    -> animation_type=Humanoid, import_animation=true, mesh_compression=Off
Assets/Art/Props/         -> animation_type=None, mesh_compression=Low, is_readable=false
Assets/Art/Environment/   -> animation_type=None, mesh_compression=Medium, is_readable=false
Assets/Art/Weapons/       -> animation_type=None, mesh_compression=Off
Assets/Art/VFX/Textures/  -> max_size=512, srgb depends on name
Assets/Art/UI/            -> max_size=512, sprite_mode=Single, mipmap=false
```

---

## 3. Asset Organization

### Recommended Unity Folder Structure for VeilBreakers

```
Assets/
  _VeilBreakers/                    # Underscore prefix keeps it at top
    Art/
      Characters/
        Heroes/                     # Player characters
          {CharName}/
            Models/                 # FBX files
            Textures/               # PBR texture sets
            Materials/              # Generated URP Lit materials
            Animations/             # Animation clips
            Prefabs/                # Character prefabs
        Monsters/
          {MonsterName}/
        NPCs/
          {NPCName}/
      Props/
        Furniture/
        Containers/
        Interactive/
        Decorative/
      Environment/
        Buildings/
        Terrain/
        Vegetation/
        Water/
        Roads/
      Weapons/
        Melee/
        Ranged/
        Magical/
      VFX/
        Textures/
        Materials/
        Prefabs/
      UI/
        Icons/
        Frames/
        Fonts/
    Audio/
      Music/
      SFX/
      Ambience/
      Voice/
    Data/
      ScriptableObjects/
      Configs/
      Localization/
    Scenes/
      Levels/
      Additive/
      UI/
    Scripts/
      Runtime/
      Editor/
    Shaders/
      URP/
      Includes/
    Prefabs/
      Gameplay/
      UI/
      Systems/
  Editor/
    Generated/                      # MCP toolkit output (current location)
      Assets/
      Build/
      Pipeline/
  StreamingAssets/
  Resources/                        # MINIMIZE -- prefer Addressables
  Plugins/
  SpriteAtlases/
```

### Naming Conventions

| Asset Type | Pattern | Example |
|------------|---------|---------|
| Models | `{Name}_{LOD}.fbx` | `Barrel_LOD0.fbx`, `Barrel_LOD1.fbx` |
| Textures | `{Name}_{Channel}.png` | `Barrel_Albedo.png`, `Barrel_Normal.png` |
| Materials | `M_{Name}.mat` | `M_Barrel.mat` |
| Prefabs | `{Name}.prefab` | `Barrel.prefab` |
| Animations | `{Name}_{Action}.anim` | `Hero_Idle.anim`, `Hero_Attack01.anim` |
| ScriptableObjects | `SO_{Name}.asset` | `SO_SwordStats.asset` |
| Shaders | `VB_{Name}.shader` | `VB_WaterSurface.shader` |

### Addressable Asset Groups

| Group | Content | Load Strategy |
|-------|---------|---------------|
| `Core` | Player character, essential UI, core systems | Always loaded |
| `Level_{Name}` | Per-level environment, props, lighting | Load on level transition |
| `Monsters_{Biome}` | Monster models/anims per biome | Load when entering biome |
| `Weapons` | All weapon models/materials | Load on equip or preload |
| `VFX` | Particle prefabs, VFX textures | Load on demand |
| `Audio` | Music, SFX, ambience | Stream or preload per level |
| `UI` | UI prefabs, icons, fonts | Preload on game start |

---

## 4. Build Pipeline

### Build Size Optimization

| Technique | Impact | How |
|-----------|--------|-----|
| **Texture compression** | 50-80% texture size reduction | Platform-specific formats (BC7/ASTC) |
| **Mesh compression** | 10-30% mesh size reduction | ModelImporter.meshCompression |
| **Shader variant stripping** | Can save 100s of MB | Strip unused keywords, use shader_features |
| **Managed code stripping** | 10-50% code size reduction | IL2CPP + High stripping level |
| **Asset deduplication** | Varies | Addressables shared bundles |
| **Texture atlas packing** | 20-40% fewer draw calls, smaller textures | SpriteAtlas for UI, texture atlases for 3D |
| **Audio compression** | 50-90% audio size reduction | Vorbis for music, ADPCM for SFX |
| **Draco mesh compression** | 80-90% GLB file reduction | Enable in glTFast import |

### IL2CPP vs Mono

| Aspect | IL2CPP | Mono |
|--------|--------|------|
| **Runtime performance** | 2-3x faster | Baseline |
| **Build time** | 5-10x slower | Fast |
| **Build size** | Larger base but strips better | Smaller base |
| **Platform support** | Required for iOS, WebGL, consoles | PC/Android only |
| **Code stripping** | Aggressive (link.xml for exceptions) | Limited |
| **Debugging** | Harder (C++ output) | Standard C# debugging |
| **Recommendation** | **Use for release builds** | Use for development iteration |

### Managed Code Stripping Levels

| Level | What It Removes | Risk |
|-------|----------------|------|
| Minimal | Unused code that's trivially detectable | None |
| Low | Unreachable code via static analysis | Low |
| Medium | Unreachable code + unused type members | Medium -- may break reflection |
| High | Aggressive removal of everything unreachable | High -- must use link.xml for reflection |

**Recommendation:** Use `Medium` for development, `High` for release with link.xml preserving:
- Any type loaded via `Type.GetType()` or `Activator.CreateInstance()`
- Serialization types (JsonUtility targets)
- Addressables internal types

### Shader Variant Stripping

The toolkit already has `unity_build setup_shader_stripping` which generates a shader stripper. Key keywords to strip for a dark fantasy RPG:

```csharp
// Strip these unused URP keywords for VeilBreakers:
"_DETAIL_MULX2",           // Detail maps (not used)
"_PARALLAXMAP",            // Parallax mapping (if not used)
"_ALPHATEST_ON",           // Only if no alpha-tested materials
"LIGHTMAP_ON",             // Only if no lightmaps
"DIRLIGHTMAP_COMBINED",    // Only if no directional lightmaps
"_ADDITIONAL_LIGHT_SHADOWS",// If no additional light shadows
```

### Platform-Specific Build Settings

Already handled by `unity_build configure_platform` for Android/iOS/WebGL. Missing: **PC/Standalone** configuration (the primary platform for a dark fantasy action RPG).

---

## 5. Continuous Integration

### Current Toolkit CI Support

`unity_build generate_ci_pipeline` generates GitHub Actions or GitLab CI YAML. Supports:
- Multi-platform builds
- Unity test runner integration
- CI secrets configuration (UNITY_LICENSE, UNITY_EMAIL, UNITY_PASSWORD)

### GAPs in CI

| Gap | Description |
|-----|-------------|
| **No build size tracking** | No CI step compares build size between commits |
| **No asset validation in CI** | No check that all assets import correctly |
| **No performance regression** | No automated performance benchmarks |
| **No screenshot comparison** | No visual regression testing of scenes |
| **No Addressable build** | CI builds app but doesn't build Addressable bundles |

### Recommended CI Pipeline Stages

```
1. Asset Validation
   - Import all assets (check for errors)
   - Validate material references
   - Check for missing textures
   - Verify prefab integrity

2. Code Quality
   - Run Unity Test Framework (EditMode + PlayMode)
   - Code analysis (the toolkit's code reviewer)
   - Compile check

3. Build
   - Build Addressable bundles
   - Build player (IL2CPP, High stripping)
   - Record build size

4. Post-Build Verification
   - Launch build headless
   - Run smoke tests
   - Compare build size to threshold
   - Archive artifacts
```

---

## 6. Missing Pipeline Steps

### Lightmap Baking Workflow

**API:** `Lightmapping.BakeAsync()` / `Lightmapping.Bake()`
**Current toolkit support:** NONE
**What's needed:**
- Set objects as Static (lightmap static specifically)
- Configure Lightmap Parameters (resolution, samples)
- Trigger bake via editor script
- Handle multi-scene baking
- Store lightmap data per-level in Addressable groups

### Occlusion Culling Bake

**API:** `StaticOcclusionCulling.Compute()` / `StaticOcclusionCulling.GenerateInBackground()`
**Current toolkit support:** Mentioned in next_steps output of compose_interior but no actual tool
**What's needed:**
- Mark occluders and occludees
- Configure cell size and smallest occluder
- Trigger bake
- Verify bake quality

### NavMesh Bake

**API:** `UnityEditor.AI.NavMeshBuilder.BuildNavMesh()` or runtime `NavMeshSurface.BuildNavMesh()`
**Current toolkit support:** `unity_prefab setup_navmesh` exists (generates navmesh setup script)
**Status:** Partially covered -- needs verification that it actually triggers bake

### Audio Import Settings

**Current toolkit support:** AssetPostprocessor supports audio_rules for folder-based auto-configuration
**Recommended settings:**

| Audio Type | Load Type | Compression | Sample Rate | Channels |
|-----------|-----------|-------------|-------------|----------|
| Music | Streaming | Vorbis, Quality 70% | 44100 | Stereo |
| SFX | Decompress On Load | ADPCM | 22050 | Mono |
| Ambience | Compressed In Memory | Vorbis, Quality 50% | 44100 | Stereo |
| Voice/Dialog | Streaming | Vorbis, Quality 80% | 22050 | Mono |
| UI Sounds | Decompress On Load | PCM | 22050 | Mono |

### Video/Cutscene Import

Unity uses VideoPlayer component with .mp4 (H.264) or .webm (VP8) formats.
**Current toolkit support:** NONE
**Recommendation:** Low priority for VeilBreakers -- cutscenes can use in-engine cinematics (toolkit has cinematic templates).

### Font/UI Asset Pipeline

**Current toolkit support:** UI templates exist, sprite atlas creation exists
**Gap:** No font import configuration (TextMeshPro SDF font generation)

### Localization Pipeline

**Current toolkit support:** NONE
**Recommendation:** Use Unity Localization package (com.unity.localization) -- low priority until game has text content

---

## 7. Version Control for Unity

### What the Toolkit Already Has

`unity_pipeline configure_git_lfs` generates:
- `.gitattributes` with LFS tracking for binary files
- `.gitignore` with Unity-standard exclusions
- Optional Unity YAML SmartMerge configuration

### .gitignore Essentials (already in toolkit's template)

```
/[Ll]ibrary/
/[Tt]emp/
/[Oo]bj/
/[Bb]uild/
/[Bb]uilds/
/[Ll]ogs/
/[Uu]ser[Ss]ettings/
*.csproj
*.sln
*.suo
*.user
*.pidb
*.booproj
/Assets/Plugins/Editor/JetBrains*
.vs/
```

### Git LFS Extensions (already in toolkit)

```
*.fbx filter=lfs diff=lfs merge=lfs -text
*.obj filter=lfs diff=lfs merge=lfs -text
*.glb filter=lfs diff=lfs merge=lfs -text
*.png filter=lfs diff=lfs merge=lfs -text
*.jpg filter=lfs diff=lfs merge=lfs -text
*.tga filter=lfs diff=lfs merge=lfs -text
*.psd filter=lfs diff=lfs merge=lfs -text
*.wav filter=lfs diff=lfs merge=lfs -text
*.mp3 filter=lfs diff=lfs merge=lfs -text
*.ogg filter=lfs diff=lfs merge=lfs -text
*.mp4 filter=lfs diff=lfs merge=lfs -text
*.exr filter=lfs diff=lfs merge=lfs -text
*.hdr filter=lfs diff=lfs merge=lfs -text
*.tif filter=lfs diff=lfs merge=lfs -text
```

### Scene/Prefab Merge Conflict Mitigation

| Strategy | Description |
|----------|-------------|
| **Force Text Serialization** | Edit > Project Settings > Editor > Asset Serialization > Force Text |
| **Unity SmartMerge** | Configure as merge tool in .gitconfig (toolkit generates this) |
| **Scene per feature** | Use additive scenes -- one per gameplay feature/area |
| **Prefab modularity** | Small prefabs composed into larger ones via nesting |
| **Prefab Variants** | Override changes via variants, not direct edits |
| **Lock critical files** | Use Git LFS file locking for scenes being actively edited |

---

## 8. Complete Pipeline Gap Analysis

### Current Pipeline Flow (what exists)

```
[Blender Generation] --> [Pipeline: repair->UV->texture->rig->animate]
         |
         v
[game_check validation] --> [blender_export (FBX or GLB)]
         |
         v
[Manual file copy to Unity Assets folder]     <-- GAP: No automated transfer
         |
         v
[unity_assets configure_fbx OR atomic_import]
         |
         v
[unity_assets auto_materials / remap_materials]
         |
         v
[Manual prefab creation, component setup]      <-- GAP: No automated prefab gen
         |
         v
[Manual LODGroup, collider, Addressable setup] <-- GAP: Partially covered
         |
         v
[unity_build for CI/platform/shader stripping]
```

### Gaps Ranked by Severity

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 1 | **No Blender-to-Unity file transfer** | CRITICAL | Export goes to temp dir, no auto-copy to Unity Assets/ |
| 2 | **No GLB import configuration** | HIGH | Only FBX import settings configurable; GLB via glTFast has no MCP tool |
| 3 | **No LODGroup auto-setup** | HIGH | LOD chain generated in Blender, but Unity LODGroup never created |
| 4 | **No automated prefab creation from imported model** | HIGH | Every imported model needs manual prefab creation |
| 5 | **No collision mesh auto-setup** | HIGH | No MeshCollider/BoxCollider added based on asset type |
| 6 | **No Addressable asset labeling tool** | MEDIUM | Groups configurable but individual asset labeling missing |
| 7 | **No lightmap bake orchestration** | MEDIUM | No tool to mark static + configure + trigger bake |
| 8 | **No occlusion culling bake tool** | MEDIUM | Mentioned in outputs but no actual tool |
| 9 | **No build size analysis tool** | MEDIUM | No way to track/report build size programmatically |
| 10 | **No batch import pipeline** | MEDIUM | atomic_import is single-asset, no folder-scan batch |
| 11 | **No import validation/verification** | MEDIUM | No post-import check for correctness |
| 12 | **No Draco compression toggle** | LOW | GLB export doesn't enable Draco even though glTFast supports it |
| 13 | **No LOD naming convention enforcement** | LOW | Blender export doesn't enforce _LOD0/_LOD1 suffixes |
| 14 | **No PC/Standalone platform config** | LOW | Platform config only handles Android/iOS/WebGL |

### Recommended New Tools/Actions

**Blender side (blender_export enhancement):**
```
blender_export_pipeline:
  - export_to_unity: Export + copy to correct Unity Assets/ subfolder
  - export_lod_chain: Export all LODs with naming convention
  - export_collision: Export separate collision mesh with UCX_ prefix
  - export_batch: Export multiple selected objects to individual files
```

**Unity side (new actions needed):**
```
unity_assets:
  - configure_glb: GLB/glTF import settings via glTFast API
  - batch_import: Scan folder, apply presets by convention, import all
  - validate_import: Post-import verification (materials, scale, normals)

unity_prefab (new actions):
  - setup_lod_group: Create LODGroup from LOD0-LOD3 meshes
  - setup_colliders: Add appropriate collider based on asset type
  - create_from_model: Full prefab creation from imported model

unity_build (new actions):
  - analyze_build_size: Generate build report with asset breakdown
  - bake_lightmaps: Configure + trigger lightmap bake
  - bake_occlusion: Configure + trigger occlusion culling
  - configure_standalone: PC/Standalone build settings
  - label_addressable: Add Addressable label/group to asset

unity_pipeline (new actions):
  - setup_glTFast: Install/configure glTFast package
  - full_asset_import: End-to-end: copy file + import + configure + prefab + label
```

---

## 9. Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| glTF/GLB import | Custom glTF parser | Unity glTFast (com.unity.cloud.gltfast@6.8) | Spec-complete, Unity-maintained, handles extensions |
| Mesh compression | Custom compression | Draco (com.unity.cloud.draco) | Google-maintained, 80-90% size reduction |
| Mesh optimization | Custom vertex cache optimization | meshoptimizer (com.unity.meshopt.decompress) | Industry standard, Arseny Kapoulkine authored |
| Asset bundles | Raw AssetBundle API | Addressables (com.unity.addressables) | Higher-level API, handles dependencies, caching |
| Material conversion | Manual PBR property mapping | glTFast material import | Auto-maps glTF PBR to URP Lit |
| Scene merge | Custom merge scripts | Unity SmartMerge (built-in YAML merge) | Understands Unity serialization format |
| Build reporting | Manual file counting | BuildReport API (UnityEditor.Build.Reporting) | Official API, gives per-asset breakdown |

---

## 10. Common Pitfalls

### Pitfall 1: Scale Mismatch Between Blender and Unity
**What goes wrong:** Models appear 100x too large or small in Unity
**Why it happens:** Blender defaults to meters but FBX exporter may apply unit conversion
**How to avoid:** The toolkit's FBX export uses `apply_scale_options="FBX_SCALE_ALL"` + `apply_unit_scale=True` which is correct. GLB export uses `export_yup=True` which is also correct. Always verify with `game_check` before export.
**Warning signs:** Objects not matching reference cube in Unity

### Pitfall 2: Normal Map Import as Regular Texture
**What goes wrong:** Normal maps look washed out, lighting is wrong
**Why it happens:** Unity imports all textures as sRGB by default; normal maps must be linear
**How to avoid:** The toolkit's auto_detect_srgb checks filename for "normal", "roughness", "metallic", "ao", "height" and sets sRGB=false. Ensure texture naming conventions are followed.
**Warning signs:** Blue-ish tint visible on models, incorrect specular highlights

### Pitfall 3: GLB Materials Don't Map to URP
**What goes wrong:** Pink/magenta materials on imported GLB models
**Why it happens:** glTFast not installed, or URP not configured, or shader mapping fails
**How to avoid:** Ensure com.unity.cloud.gltfast is installed. The package auto-maps glTF PBR to URP Lit if URP is the active pipeline.
**Warning signs:** Pink materials immediately after import

### Pitfall 4: Read/Write Enabled Doubling Memory
**What goes wrong:** Textures and meshes use 2x expected memory
**Why it happens:** Read/Write enabled creates CPU + GPU copies
**How to avoid:** The toolkit's configure_fbx defaults is_readable=false. Only enable for runtime mesh deformation (cloth, procedural).
**Warning signs:** Profiler showing high texture memory, memory warnings

### Pitfall 5: AssetPostprocessor Infinite Reimport Loop
**What goes wrong:** Unity endlessly reimports the same asset
**Why it happens:** Using OnPostprocess* to modify import settings triggers another import
**How to avoid:** The toolkit correctly uses OnPreprocess* callbacks. Always use GetVersion() to track processor version.
**Warning signs:** Unity editor freezing during import, "Importing..." progress bar stuck

### Pitfall 6: Addressable Build Not Included in CI
**What goes wrong:** Player build works locally but crashes on asset load in CI builds
**Why it happens:** Addressable content not built as part of CI pipeline
**How to avoid:** Add `AddressableAssetSettings.BuildPlayerContent()` call before `BuildPipeline.BuildPlayer()`
**Warning signs:** "Exception: ... not found" errors at runtime for Addressable assets

### Pitfall 7: LOD Meshes Imported but Never Grouped
**What goes wrong:** All LODs render simultaneously or only LOD0 renders
**Why it happens:** LOD meshes imported as separate GameObjects, no LODGroup component created
**How to avoid:** After import, create LODGroup component and assign renderers. Use naming convention (_LOD0, _LOD1) so automation can detect them.
**Warning signs:** Frame rate doesn't improve with distance, or quality doesn't degrade

---

## 11. Code Examples

### End-to-End Asset Import (what should exist)

```csharp
// Source: Pattern derived from Unity docs + toolkit templates
// This is what a unified import pipeline tool should generate:

using UnityEngine;
using UnityEditor;
using System.IO;
using System.Linq;

public static class VB_FullAssetImport
{
    [MenuItem("VeilBreakers/Pipeline/Full Asset Import")]
    public static void Execute()
    {
        string modelPath = "Assets/Art/Props/Barrel/Models/Barrel.glb";
        string textureDir = "Assets/Art/Props/Barrel/Textures/";
        string prefabDir = "Assets/Art/Props/Barrel/Prefabs/";
        
        AssetDatabase.StartAssetEditing();
        try
        {
            // 1. Configure texture imports
            foreach (string texPath in Directory.GetFiles(textureDir, "*.png"))
            {
                string assetPath = texPath.Replace("\\", "/");
                TextureImporter ti = AssetImporter.GetAtPath(assetPath) as TextureImporter;
                if (ti != null)
                {
                    string name = Path.GetFileNameWithoutExtension(assetPath).ToLower();
                    ti.sRGBTexture = !name.Contains("normal") && !name.Contains("roughness") 
                                   && !name.Contains("metallic") && !name.Contains("ao");
                    ti.mipmapEnabled = true;
                    ti.maxTextureSize = 2048;
                    // Platform overrides
                    var standalone = ti.GetPlatformTextureSettings("Standalone");
                    standalone.overridden = true;
                    standalone.format = TextureImporterFormat.BC7;
                    ti.SetPlatformTextureSettings(standalone);
                    ti.SaveAndReimport();
                }
            }
            
            // 2. Import model (glTFast handles GLB automatically)
            AssetDatabase.ImportAsset(modelPath, ImportAssetOptions.ForceUpdate);
            
            // 3. Create prefab from imported model
            GameObject modelObj = AssetDatabase.LoadAssetAtPath<GameObject>(modelPath);
            if (modelObj != null)
            {
                GameObject instance = PrefabUtility.InstantiatePrefab(modelObj) as GameObject;
                
                // 4. Add collider
                MeshFilter mf = instance.GetComponentInChildren<MeshFilter>();
                if (mf != null)
                {
                    MeshCollider mc = instance.AddComponent<MeshCollider>();
                    mc.convex = true;
                }
                
                // 5. Setup LODGroup if LOD meshes exist
                SetupLODGroup(instance);
                
                // 6. Make it static for batching
                instance.isStatic = true;
                
                // 7. Save as prefab
                string prefabPath = prefabDir + instance.name + ".prefab";
                Directory.CreateDirectory(Path.GetDirectoryName(prefabPath));
                PrefabUtility.SaveAsPrefabAsset(instance, prefabPath);
                Object.DestroyImmediate(instance);
            }
        }
        finally
        {
            AssetDatabase.StopAssetEditing();
            AssetDatabase.Refresh();
        }
    }
    
    static void SetupLODGroup(GameObject root)
    {
        var renderers = root.GetComponentsInChildren<MeshRenderer>();
        var lodGroups = renderers
            .Where(r => r.name.Contains("_LOD"))
            .GroupBy(r => r.name.Split("_LOD")[0])
            .ToList();
        
        if (lodGroups.Count == 0) return;
        
        LODGroup lodGroup = root.AddComponent<LODGroup>();
        LOD[] lods = new LOD[4];  // Up to LOD0-LOD3
        
        for (int i = 0; i < 4; i++)
        {
            string suffix = "_LOD" + i;
            var matching = renderers.Where(r => r.name.EndsWith(suffix)).ToArray();
            float screenPercent = i switch
            {
                0 => 0.6f,
                1 => 0.3f,
                2 => 0.1f,
                _ => 0.01f
            };
            lods[i] = new LOD(screenPercent, matching);
        }
        
        lodGroup.SetLODs(lods.Where(l => l.renderers.Length > 0).ToArray());
        lodGroup.RecalculateBounds();
    }
}
```

### Build Report Analysis (what should exist)

```csharp
// Source: Unity BuildReport API
using UnityEditor;
using UnityEditor.Build.Reporting;
using System.IO;
using System.Text;

public static class VB_BuildAnalysis
{
    public static void AnalyzeLastBuild(BuildReport report)
    {
        StringBuilder sb = new StringBuilder();
        sb.AppendLine($"Build Size: {report.summary.totalSize / (1024 * 1024)} MB");
        sb.AppendLine($"Build Time: {report.summary.totalTime}");
        sb.AppendLine($"Errors: {report.summary.totalErrors}");
        sb.AppendLine($"Warnings: {report.summary.totalWarnings}");
        
        // Asset breakdown
        var packedAssets = report.packedAssets;
        foreach (var pack in packedAssets)
        {
            sb.AppendLine($"\nBundle: {pack.shortPath}");
            foreach (var asset in pack.contents.OrderByDescending(a => a.packedSize).Take(20))
            {
                sb.AppendLine($"  {asset.sourceAssetPath}: {asset.packedSize / 1024} KB");
            }
        }
        
        File.WriteAllText("Temp/vb_build_report.json", sb.ToString());
    }
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FBX for everything | GLB for static PBR, FBX for animated | 2024 (glTFast matured) | Better material fidelity, smaller files |
| Resources.Load() | Addressables | 2020+ | Async loading, content updates, smaller builds |
| Built-in render pipeline | URP | 2020+ | Better performance, mobile support |
| Manual texture compression | Platform-specific overrides in importer | Always available | Optimal per-platform quality |
| Asset Bundles (manual) | Addressables (managed) | 2020+ | Dependency resolution, caching |
| Occlusion culling | GPU-driven rendering | Unity 6 (experimental) | May replace traditional occlusion |

---

## Open Questions

1. **glTFast import settings API**
   - What we know: glTFast registers as ScriptedImporter and auto-configures
   - What's unclear: Can we programmatically override glTFast import settings per-asset (like we do with ModelImporter for FBX)?
   - Recommendation: Test glTFast's ScriptedImporter settings API, may need custom editor script

2. **LOD chain from Blender to Unity**
   - What we know: Blender LOD pipeline generates LOD0-LOD3 meshes with correct ratios
   - What's unclear: Does the toolkit export them as separate objects? Does naming convention survive?
   - Recommendation: Verify export naming, build LODGroup setup tool on Unity side

3. **Draco compression in pipeline**
   - What we know: glTFast supports Draco import; Blender can export with Draco
   - What's unclear: Whether the toolkit enables Draco in the GLB export settings
   - Recommendation: Add `export_draco=True` option to blender_export gltf path

---

## Sources

### Primary (HIGH confidence)
- VeilBreakers codebase: `blender_addon/handlers/export.py` -- actual export implementation
- VeilBreakers codebase: `unity_tools/assets.py`, `unity_tools/pipeline.py`, `unity_tools/build.py` -- Unity tool implementations
- VeilBreakers codebase: `shared/unity_templates/asset_templates.py` -- FBX/texture import C# generators
- [Unity glTFast 6.8.0 Features](https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.8/manual/features.html) -- GLB feature matrix
- [Unity AssetPostprocessor API](https://docs.unity3d.com/ScriptReference/AssetPostprocessor.html) -- Import hook API
- [Unity ScriptedImporter Manual](https://docs.unity3d.com/Manual/ScriptedImporters.html) -- Custom importer docs

### Secondary (MEDIUM confidence)
- [Unity Project Configuration Guide](https://unity.com/how-to/project-configuration-and-assets) -- Build optimization
- [Unity Project Organization Guide](https://unity.com/how-to/organizing-your-project) -- Folder structure
- [GitHub Unity .gitignore](https://github.com/github/gitignore/blob/main/Unity.gitignore) -- Standard ignore patterns
- [InnoGames Custom Asset Pipeline](https://blog.innogames.com/building-a-custom-asset-pipeline-for-a-unity-project/) -- Pipeline patterns
- [IL2CPP Build Size Optimizations](https://support.unity.com/hc/en-us/articles/208412186-IL2CPP-build-size-optimizations) -- Code stripping

### Tertiary (LOW confidence)
- WebSearch results for Unity 6 specific features -- not all verified against current docs

---

## Metadata

**Confidence breakdown:**
- Export format comparison: HIGH -- based on codebase + official glTFast docs
- Unity import pipeline: HIGH -- based on codebase audit + Unity API docs
- Build optimization: MEDIUM -- general best practices, not all verified for Unity 6 specifically
- Gap analysis: HIGH -- direct codebase inspection
- CI pipeline: MEDIUM -- general patterns, not VeilBreakers-specific tested

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (30 days -- stable domain)
