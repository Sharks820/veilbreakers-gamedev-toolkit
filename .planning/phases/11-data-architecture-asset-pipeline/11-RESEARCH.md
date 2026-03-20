# Phase 11: Data Architecture & Asset Pipeline - Research

**Researched:** 2026-03-20
**Domain:** Unity data-driven architecture (ScriptableObjects, JSON, Localization), asset pipeline (Git LFS, normal map baking, sprite atlasing, AssetPostprocessor), AAA quality enforcement
**Confidence:** HIGH

## Summary

Phase 11 covers three major domains: (1) data-driven game architecture using ScriptableObjects and JSON configs with localization support, (2) asset pipeline automation including Git LFS, normal map baking, sprite atlasing, and AssetPostprocessor scripts, and (3) AAA quality standards enforcement including albedo de-lighting, polygon budgets, material palette validation, master material libraries, and texture quality validation.

The existing codebase provides strong foundations. Phase 10's `generate_class` already handles ScriptableObject class generation with auto `CreateAssetMenu` attributes. Phase 9's `asset_templates.py` has FBX/texture import presets. The Blender server's `handle_bake_textures` already supports selected-to-active normal map baking with cage extrusion. The VeilBreakers game project uses JSON data in `Assets/Resources/Data/` loaded by `GameDatabase.cs` and has 4 existing `HeroDisplayConfig` ScriptableObject assets demonstrating the SO pattern.

**Primary recommendation:** Create a new `unity_data` compound tool for SO/JSON/localization operations, extend existing Blender tools for enhanced normal map baking workflow, and add AAA quality validation as either a new compound tool or extension to `unity_assets`. Follow the established compound-tool + template-generator pattern with test coverage matching the 3,453 existing tests.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **ScriptableObject Architecture (DATA-02, DATA-04):** Category-based folder structure Assets/Data/{Category}/ with PascalCase naming. Generate both C# SO class definitions AND .asset instances. Generate custom editor windows for batch-creating/editing SO assets. SO architecture should complement JSON (not replace) for data that benefits from Unity references.
- **JSON/XML Configuration (DATA-01):** Generate validators against schemas, properly formatted config files with comments, and runtime loaders that deserialize into typed C# classes complementing existing GameDatabase.
- **Localization (DATA-03):** Unity Localization package with string table setup, locale assets, localized variants. Default locale English (en). Key naming convention matching VeilBreakers patterns (UI.MainMenu.StartGame, Combat.Brand.Iron).
- **AAA Quality Standards (AAA-01 through AAA-04, AAA-06):** Strict enforcement with auto-fix. Albedo de-lighting for Tripo3D output. Per-asset-type poly budgets (hero: 30-50k, mob: 8-15k, weapon: 3-8k, prop: 500-6k, building: 5-15k) with auto-retopo. Dark fantasy palette validation (saturation caps, color temp rules, PBR roughness variation). Master material library (stone, wood, iron, moss, bone, cloth, leather). Texture quality validation (texel density 10.24 px/cm, micro-detail normals, proper M/R/AO channel packing).
- **Asset Pipeline (IMP-03, IMP-04, BUILD-06, TWO-03, PIPE-08):** Git LFS .gitattributes for binary files. Normal map baking high-to-low with cage generation. Sprite atlasing and sprite animation setup. Sprite Editor configuration for custom physics shapes, pivots, 9-slice borders. AssetPostprocessor scripts for auto-import configuration based on folder conventions.

### Claude's Discretion
- JSON schema format (JSON Schema draft or custom)
- Localization key auto-detection from existing UXML/code
- De-lighting algorithm specifics
- Master material library shader graph structure
- Sprite atlas packing algorithm configuration
- TextMeshPro font asset creation details

### Deferred Ideas (OUT OF SCOPE)
None -- auto-mode stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DATA-01 | Create, edit, validate JSON/XML game config files | JSON schema validation pattern, typed C# deserialization, template generator for config loaders |
| DATA-02 | Create ScriptableObject definitions and instantiate .asset files | `generate_class` already supports SO type; extend with .asset instantiation via `AssetDatabase.CreateAsset` |
| DATA-03 | Set up Unity Localization package (string tables, locales) | com.unity.localization@1.5 package, editor script for string table creation, locale asset generation |
| DATA-04 | Generate game data authoring tools (item databases, stat tables as SO assets) | EditorWindow generation from Phase 10, batch SO creation scripts, JSON-to-SO import |
| IMP-03 | Set up Git LFS rules, .gitignore, .gitattributes | File-system level generation, well-established patterns for Unity projects |
| IMP-04 | Configure normal map baking workflow (high-to-low with cage) | Existing `handle_bake_textures` in Blender server, extend with cage mesh generation |
| BUILD-06 | Set up sprite sheet packing, texture atlasing, sprite animation | Unity SpriteAtlas C# API (`UnityEngine.U2D.SpriteAtlas`), TextureImporter sprite settings |
| TWO-03 | Configure Sprite Editor features (physics shapes, pivot, 9-slice) | TextureImporter API: spriteBorder (Vector4), spritePivot (Vector2), spriteAlignment (int) |
| PIPE-08 | Generate AssetPostprocessor scripts for custom import pipelines | `AssetPostprocessor` callbacks: OnPreprocessTexture, OnPreprocessModel, OnPostprocessAllAssets |
| AAA-01 | Albedo de-lighting for AI-generated textures | Python/Pillow or OpenCV approach: Lab color space separation, gaussian blur luminance estimation, division-based de-lighting |
| AAA-02 | Per-asset-type polygon budget enforcement with auto-retopo | Existing `blender_mesh` game_check + retopo actions, extend with per-type budget configs |
| AAA-03 | Dark fantasy material palette validation | HSV analysis of albedo textures, saturation/temperature caps, roughness variation checks in Blender |
| AAA-04 | Master material library generation | Unity Shader Graph or URP Lit material presets, template-based creation via editor scripts |
| AAA-06 | Texture quality validation (texel density, normals, channel packing) | UV texel density analysis in Blender, normal map presence checks, M/R/AO channel verification |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| com.unity.localization | 1.5.x | String tables, locale assets, localized variants | Official Unity package for localization |
| UnityEngine.U2D.SpriteAtlas | Built-in | Sprite atlas creation and management | Unity's built-in sprite packing system |
| UnityEditor.AssetPostprocessor | Built-in | Custom import pipeline automation | Unity's official asset import hook system |
| Git LFS | 3.x | Large binary file tracking | Industry standard for game asset version control |
| Pillow (PIL) | 10.x | Python image processing for de-lighting | Already available in toolkit Python environment |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| TextMeshPro | Built-in (Unity 6) | Font asset creation, rich text | TMP is included in Unity 6 by default |
| Newtonsoft.Json | via Unity package | JSON serialization alternative | When JsonUtility limitations are hit (no Dictionary support) |
| OpenCV (cv2) | Optional | Advanced de-lighting algorithms | If Pillow-based approach is insufficient |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Unity Localization | I2 Localization | Unity official has better long-term support, free |
| JsonUtility | Newtonsoft.Json | JsonUtility is faster but lacks Dictionary/complex type support |
| Pillow de-lighting | Substance Sampler CLI | Substance requires license, not automatable in MCP pipeline |

## Architecture Patterns

### Recommended Project Structure (Unity Side)
```
Assets/
  Data/                       # ScriptableObject assets
    Items/                    # ItemConfig.asset files
    Monsters/                 # MonsterConfig.asset files
    Abilities/                # AbilityConfig.asset files
    Materials/                # Master material library
  Resources/
    Data/                     # Existing JSON (heroes.json, monsters.json, etc.)
  Localization/
    StringTables/             # String table collections
    Locales/                  # Locale assets (en, es, fr, etc.)
  Editor/
    Generated/
      Data/                   # SO authoring EditorWindows
      Pipeline/               # AssetPostprocessor scripts
      Quality/                # AAA validation editor scripts
```

### Recommended Project Structure (Toolkit Side)
```
Tools/mcp-toolkit/
  src/veilbreakers_mcp/
    shared/unity_templates/
      data_templates.py       # SO definition, .asset creation, JSON validators, localization
      pipeline_templates.py   # AssetPostprocessor, Git LFS, sprite atlas
      quality_templates.py    # AAA validation editor scripts, master materials
    shared/
      delight.py              # Albedo de-lighting algorithm (Python/Pillow)
      palette_validator.py    # Dark fantasy palette validation (Python)
      texel_validator.py      # Texel density analysis helper
  tests/
    test_data_templates.py
    test_pipeline_templates.py
    test_quality_templates.py
    test_delight.py
    test_palette_validator.py
```

### Pattern 1: ScriptableObject .asset File Instantiation
**What:** Generate C# editor scripts that use `ScriptableObject.CreateInstance<T>()` + `AssetDatabase.CreateAsset()` to create populated .asset files
**When to use:** DATA-02, DATA-04 -- creating data-driven game configs that need Unity references (prefab refs, sprites, audio clips)
**Example:**
```csharp
// Source: Unity docs ScriptableObject.CreateInstance + AssetDatabase.CreateAsset
[MenuItem("VeilBreakers/Data/Create Item Config")]
public static void CreateItemConfig()
{
    var asset = ScriptableObject.CreateInstance<ItemConfig>();
    asset.itemName = "New Item";
    asset.rarity = Rarity.Common;

    string path = "Assets/Data/Items/NewItem.asset";
    AssetDatabase.CreateAsset(asset, path);
    AssetDatabase.SaveAssets();
    AssetDatabase.Refresh();

    // Write result for MCP
    File.WriteAllText(
        Path.Combine(Application.dataPath, "../Temp/vb_result.json"),
        JsonUtility.ToJson(new { status = "success", asset_path = path })
    );
}
```

### Pattern 2: AssetPostprocessor Folder-Convention Import
**What:** Scripts that auto-configure imports based on folder path (e.g., assets in `Textures/UI/` get different settings than `Textures/Characters/`)
**When to use:** PIPE-08 -- automating import settings based on project conventions
**Example:**
```csharp
// Source: Unity docs AssetPostprocessor.OnPreprocessTexture
public class VeilBreakersTexturePostprocessor : AssetPostprocessor
{
    // IMPORTANT: Increment when changing processor logic
    public override uint GetVersion() { return 2; }

    void OnPreprocessTexture()
    {
        var importer = (TextureImporter)assetImporter;

        if (assetPath.Contains("/Textures/UI/"))
        {
            importer.textureType = TextureImporterType.Sprite;
            importer.spritePixelsPerUnit = 100;
            importer.filterMode = FilterMode.Bilinear;
            importer.maxTextureSize = 2048;
        }
        else if (assetPath.Contains("/Textures/Characters/"))
        {
            importer.textureType = TextureImporterType.Default;
            importer.sRGBTexture = true;
            importer.maxTextureSize = 4096;
            importer.textureCompression = TextureImporterCompression.CompressedHQ;
        }
    }
}
```

### Pattern 3: JSON Schema Validation
**What:** Generate C# validators that check game config JSON files against expected schemas (field types, ranges, required fields)
**When to use:** DATA-01 -- validating game balance configs before runtime loading
**Example:**
```csharp
// Template-generated validator that checks config structure
[MenuItem("VeilBreakers/Data/Validate Configs")]
public static void ValidateConfigs()
{
    var results = new List<ValidationResult>();

    string json = File.ReadAllText("Assets/Resources/Data/monsters.json");
    var monsters = JsonUtility.FromJson<MonsterDataWrapper>(WrapArray(json));

    foreach (var m in monsters.items)
    {
        if (string.IsNullOrEmpty(m.monster_id))
            results.Add(new ValidationResult("ERROR", $"Monster missing ID"));
        if (m.base_hp <= 0)
            results.Add(new ValidationResult("WARN", $"{m.monster_id}: base_hp <= 0"));
    }

    WriteResult(results);
}
```

### Pattern 4: Albedo De-lighting (Python)
**What:** Remove baked-in lighting from AI-generated textures using luminance channel analysis
**When to use:** AAA-01 -- processing Tripo3D output textures before they enter the game pipeline
**Recommended algorithm:**
1. Convert RGB to Lab color space (separates luminance from chrominance)
2. Extract L channel (luminance)
3. Apply large-radius Gaussian blur to L channel to estimate lighting
4. Divide original L by blurred L and rescale to normalize
5. Recombine with original a,b channels
6. Convert back to RGB
7. Optional: clamp and gamma-correct

### Anti-Patterns to Avoid
- **Replacing GameDatabase JSON loading:** The existing async JSON loader must remain functional. SOs complement JSON for Unity-reference-heavy data, not replace it.
- **Hardcoding import settings in AssetPostprocessor:** Use configurable rules (folder patterns + settings dicts) that can be extended without modifying the processor code.
- **Skipping GetVersion() on AssetPostprocessor:** Without version incrementing, Unity will not re-process already-imported assets when the processor logic changes.
- **Using OnPostprocessTexture to set import settings:** Changes in OnPostprocess don't apply to the current import cycle. Use OnPreprocess callbacks for import configuration.
- **Creating .asset files without Undo registration:** Editor scripts that create assets should use `Undo.RegisterCreatedObjectUndo` for undo support.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Localization | Custom string table system | com.unity.localization package | Smart Strings, locale management, editor UI, pluralization, all handled |
| Sprite packing | Manual texture packing algorithm | Unity SpriteAtlas API | Platform-specific compression, mipmaps, padding handled by Unity |
| Git LFS config | Custom binary tracking | Standard .gitattributes patterns | Well-established community patterns cover 99% of Unity file types |
| JSON deserialization | Custom parser | JsonUtility or Newtonsoft.Json | Edge cases (encoding, escaping, nesting) are fully solved |
| Font atlas generation | Manual glyph rasterization | TextMeshPro Font Asset Creator API | SDF generation, fallback chains, atlas packing all handled |
| ScriptableObject serialization | Custom YAML writer | AssetDatabase.CreateAsset | Unity handles YAML serialization format, GUID assignment, .meta files |
| Normal map tangent space | Custom tangent calculation | Blender bpy.ops.object.bake with TANGENT normal_space | Cycles ray-tracing handles cage projection, tangent space correctly |

**Key insight:** Unity's editor API handles asset creation, import configuration, and serialization. The toolkit generates C# editor scripts that use these APIs -- never try to write .asset YAML or .meta files directly.

## Common Pitfalls

### Pitfall 1: AssetPostprocessor Infinite Reimport Loop
**What goes wrong:** Modifying import settings in OnPostprocess triggers a reimport, which triggers OnPostprocess again, creating an infinite loop.
**Why it happens:** OnPostprocessTexture/Model runs after import; changing the importer there schedules another import.
**How to avoid:** Use OnPRE-process callbacks (OnPreprocessTexture, OnPreprocessModel) for settings changes. Check `assetImporter.importSettingsMissing` to only process first-time imports if needed.
**Warning signs:** Unity hangs or high CPU during import, console shows repeated import messages for same asset.

### Pitfall 2: ScriptableObject .asset Creation Before Class Compilation
**What goes wrong:** Generating a SO C# class and immediately trying to create .asset instances fails because Unity hasn't compiled the class yet.
**Why it happens:** Unity needs to compile C# before `ScriptableObject.CreateInstance<T>()` can find the type.
**How to avoid:** Two-step workflow: (1) generate SO class, recompile, (2) generate asset creation script, recompile + execute. This matches the established two-step pattern.
**Warning signs:** `ScriptableObject.CreateInstance` returns null or throws TypeLoadException.

### Pitfall 3: JsonUtility Cannot Deserialize Dictionaries or Top-Level Arrays
**What goes wrong:** `JsonUtility.FromJson` fails silently on JSON arrays `[...]` or objects with Dictionary fields.
**Why it happens:** JsonUtility only supports Unity serializable types (no Dictionary, no top-level arrays).
**How to avoid:** The VeilBreakers GameDatabase already handles this with wrapper classes (`MonsterDataWrapper`). New config loaders should follow the same pattern. For complex types, use Newtonsoft.Json.
**Warning signs:** Deserialized objects have all default values despite valid JSON.

### Pitfall 4: Git LFS Not Initialized Before .gitattributes
**What goes wrong:** Adding .gitattributes LFS tracking rules without `git lfs install` causes Git to fail on binary files.
**Why it happens:** Git LFS filter/diff/merge commands must be registered before they are referenced.
**How to avoid:** The toolkit should generate both .gitattributes AND instructions/check for git lfs being initialized. Not a Unity tool -- filesystem-level operation.
**Warning signs:** Git errors about "filter 'lfs' not found" or binary files committed as text.

### Pitfall 5: De-lighting Over-Correction
**What goes wrong:** De-lighting algorithm removes too much color variation, making textures look flat and washed out.
**Why it happens:** Gaussian blur radius too large captures actual color variation as "lighting", or division causes extreme values.
**How to avoid:** Use moderate blur radius (proportional to texture size, ~10-15% of dimension). Blend result with original using a configurable strength parameter (default 0.7). Clamp output values. Provide before/after comparison.
**Warning signs:** Textures lose detail, colors become uniform, bright spots appear.

### Pitfall 6: Sprite Atlas V1 vs V2 API Differences
**What goes wrong:** Code written for SpriteAtlas V1 API doesn't work with V2, or saving with wrong extension causes native errors.
**Why it happens:** Unity has two SpriteAtlas versions with different APIs and file extensions (.spriteatlas vs .spriteatlasv2).
**How to avoid:** Use `.spriteatlas` extension (V1) which has the most stable programmatic API. V2 has known issues with code creation per community reports.
**Warning signs:** Native crash when saving atlas, API methods not found.

### Pitfall 7: Localization Package Not Installed
**What goes wrong:** Localization template scripts reference `UnityEngine.Localization` namespace that doesn't exist.
**Why it happens:** com.unity.localization is not a default Unity package; it must be installed via Package Manager.
**How to avoid:** The unity_data tool should check/install the localization package before generating localization scripts. Use the existing `generate_package_install_script` from Phase 9.
**Warning signs:** Compilation errors about missing namespace `UnityEngine.Localization`.

## Code Examples

Verified patterns from official sources and existing codebase:

### ScriptableObject Definition + Asset Creation (Two-Step)
```csharp
// Step 1: SO Class Definition (generated by data_templates.py)
// Source: Existing VeilBreakers HeroDisplayConfig.cs pattern
using UnityEngine;

namespace VeilBreakers.Data
{
    [CreateAssetMenu(menuName = "VeilBreakers/MonsterConfig", fileName = "MonsterConfig")]
    public class MonsterConfig : ScriptableObject
    {
        [Header("Identity")]
        public string monsterId;
        public string displayName;

        [Header("Stats")]
        public int baseHp;
        public int baseAttack;
        public int baseDefense;

        [Header("References")]
        public GameObject prefab;
        public Sprite icon;
        public AudioClip deathSfx;
    }
}
```

```csharp
// Step 2: Asset Instantiation Script (generated after Step 1 compiles)
// Source: Unity docs AssetDatabase.CreateAsset
using UnityEditor;
using UnityEngine;
using VeilBreakers.Data;

public class VeilBreakers_CreateMonsterConfigs
{
    [MenuItem("VeilBreakers/Data/Create Monster Configs")]
    public static void Execute()
    {
        var configs = new[] {
            new { id = "skitter_teeth", name = "Skitter-Teeth", hp = 45, atk = 12, def = 8 },
            new { id = "chainbound", name = "Chainbound", hp = 80, atk = 18, def = 15 },
        };

        foreach (var c in configs)
        {
            var asset = ScriptableObject.CreateInstance<MonsterConfig>();
            asset.monsterId = c.id;
            asset.displayName = c.name;
            asset.baseHp = c.hp;
            asset.baseAttack = c.atk;
            asset.baseDefense = c.def;

            string path = $"Assets/Data/Monsters/{c.id}.asset";
            AssetDatabase.CreateAsset(asset, path);
        }

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
    }
}
```

### AssetPostprocessor with Folder Conventions
```csharp
// Source: Unity docs AssetPostprocessor, OnPreprocessTexture, GetVersion
using UnityEditor;
using UnityEngine;

public class VeilBreakersAssetPostprocessor : AssetPostprocessor
{
    public override uint GetVersion() { return 1; }

    void OnPreprocessTexture()
    {
        var ti = (TextureImporter)assetImporter;

        if (assetPath.StartsWith("Assets/Art/Sprites/"))
        {
            ti.textureType = TextureImporterType.Sprite;
            ti.spritePixelsPerUnit = 100;
            ti.mipmapEnabled = false;
        }
        else if (assetPath.Contains("_Normal") || assetPath.Contains("_normal"))
        {
            ti.textureType = TextureImporterType.NormalMap;
            ti.sRGBTexture = false;
        }
    }

    void OnPreprocessModel()
    {
        var mi = (ModelImporter)assetImporter;

        if (assetPath.Contains("@"))
        {
            // Animation-only FBX files
            mi.importMaterials = false;
            mi.importAnimation = true;
        }
    }
}
```

### SpriteAtlas Creation
```csharp
// Source: Unity docs SpriteAtlas, SpriteAtlasExtensions
using UnityEditor;
using UnityEditor.U2D;
using UnityEngine;
using UnityEngine.U2D;

public class VeilBreakers_CreateSpriteAtlas
{
    [MenuItem("VeilBreakers/Assets/Create UI Atlas")]
    public static void CreateUIAtlas()
    {
        var atlas = new SpriteAtlas();

        // Configure packing settings
        var packSettings = new SpriteAtlasPackingSettings
        {
            padding = 4,
            enableTightPacking = true,
            enableRotation = false,
        };
        atlas.SetPackingSettings(packSettings);

        // Configure texture settings
        var texSettings = new SpriteAtlasTextureSettings
        {
            sRGB = true,
            filterMode = FilterMode.Bilinear,
        };
        atlas.SetTextureSettings(texSettings);

        // Add folder as packable
        var folder = AssetDatabase.LoadAssetAtPath<Object>("Assets/Art/Sprites/UI");
        atlas.Add(new[] { folder });

        AssetDatabase.CreateAsset(atlas, "Assets/Art/Atlases/UIAtlas.spriteatlas");
        AssetDatabase.SaveAssets();
    }
}
```

### Git LFS .gitattributes Generation
```
# Generated by VeilBreakers MCP Toolkit
# 3D Models
*.fbx filter=lfs diff=lfs merge=lfs -text
*.obj filter=lfs diff=lfs merge=lfs -text
*.blend filter=lfs diff=lfs merge=lfs -text

# Textures
*.png filter=lfs diff=lfs merge=lfs -text
*.psd filter=lfs diff=lfs merge=lfs -text
*.tga filter=lfs diff=lfs merge=lfs -text
*.tif filter=lfs diff=lfs merge=lfs -text
*.exr filter=lfs diff=lfs merge=lfs -text
*.hdr filter=lfs diff=lfs merge=lfs -text

# Audio
*.wav filter=lfs diff=lfs merge=lfs -text
*.mp3 filter=lfs diff=lfs merge=lfs -text
*.ogg filter=lfs diff=lfs merge=lfs -text

# Fonts
*.ttf filter=lfs diff=lfs merge=lfs -text
*.otf filter=lfs diff=lfs merge=lfs -text

# Video
*.mp4 filter=lfs diff=lfs merge=lfs -text
*.mov filter=lfs diff=lfs merge=lfs -text

# Unity-specific large binary
*.asset filter=lfs diff=lfs merge=lfs -text
*.cubemap filter=lfs diff=lfs merge=lfs -text
*.unitypackage filter=lfs diff=lfs merge=lfs -text

# Unity YAML merge strategy
*.unity merge=unityyamlmerge eol=lf
*.prefab merge=unityyamlmerge eol=lf
*.mat merge=unityyamlmerge eol=lf
*.anim merge=unityyamlmerge eol=lf
*.controller merge=unityyamlmerge eol=lf
*.asset -merge=unityyamlmerge eol=lf
```

### Albedo De-lighting (Python/Pillow)
```python
# Source: Lab color space technique (adapted from Unity Labs De-lighting + Adobe Substance approach)
from PIL import Image, ImageFilter
import numpy as np

def delight_albedo(
    image_path: str,
    output_path: str,
    blur_radius_pct: float = 0.12,
    strength: float = 0.75,
) -> dict:
    """Remove baked-in lighting from an albedo texture.

    Uses Lab color space to separate luminance from color,
    estimates lighting via Gaussian blur, then divides it out.
    """
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img, dtype=np.float32) / 255.0

    # Convert to a simplified Lab-like space
    # Luminance estimate: weighted sum (ITU-R BT.601)
    luminance = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]
    luminance = np.clip(luminance, 0.01, 1.0)  # Avoid division by zero

    # Estimate lighting with large-radius blur
    blur_radius = int(max(img.width, img.height) * blur_radius_pct)
    lum_img = Image.fromarray((luminance * 255).astype(np.uint8), mode="L")
    blurred = lum_img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    lighting = np.array(blurred, dtype=np.float32) / 255.0
    lighting = np.clip(lighting, 0.01, 1.0)

    # Normalize: divide out the lighting estimate
    # Target: uniform mid-gray luminance
    target_luminance = np.mean(luminance)
    correction = target_luminance / lighting

    # Apply correction with strength blending
    result = arr.copy()
    for c in range(3):
        corrected = arr[:,:,c] * correction
        result[:,:,c] = arr[:,:,c] * (1 - strength) + corrected * strength

    result = np.clip(result * 255, 0, 255).astype(np.uint8)
    Image.fromarray(result).save(output_path)

    return {
        "input": image_path,
        "output": output_path,
        "blur_radius": blur_radius,
        "strength": strength,
        "mean_luminance_before": float(np.mean(luminance)),
    }
```

### Dark Fantasy Palette Validation
```python
# Palette validation constants for VeilBreakers dark fantasy aesthetic
PALETTE_RULES = {
    "saturation_cap": 0.55,          # Max HSV saturation (dark fantasy = desaturated)
    "value_range": (0.15, 0.75),     # Min/max brightness (avoid pure black/white)
    "warm_temp_threshold": 0.55,     # Warn if too many warm pixels
    "cool_bias_target": 0.6,         # 60% of pixels should be cool-toned
    "roughness_min_variance": 0.05,  # Roughness must vary (no flat surfaces)
    "metallic_max_mean": 0.3,        # Most surfaces aren't metallic in dark fantasy
}

ASSET_TYPE_BUDGETS = {
    "hero":     {"min": 30000, "max": 50000},
    "mob":      {"min": 8000,  "max": 15000},
    "weapon":   {"min": 3000,  "max": 8000},
    "prop":     {"min": 500,   "max": 6000},
    "building": {"min": 5000,  "max": 15000},
}
```

### Localization String Table Setup
```csharp
// Source: Unity Localization docs, string table API
using UnityEditor;
using UnityEditor.Localization;
using UnityEngine.Localization;
using UnityEngine.Localization.Tables;

public class VeilBreakers_SetupLocalization
{
    [MenuItem("VeilBreakers/Data/Setup Localization")]
    public static void Execute()
    {
        // Create locale
        var locale = Locale.CreateLocale(SystemLanguage.English);
        AssetDatabase.CreateAsset(locale, "Assets/Localization/Locales/en.asset");

        // Create string table collection
        var collection = LocalizationEditorSettings.CreateStringTableCollection(
            "VeilBreakers_UI",
            "Assets/Localization/StringTables"
        );

        // Add entries
        var table = collection.GetTable("en") as StringTable;
        table.AddEntry("UI.MainMenu.StartGame", "Start Game");
        table.AddEntry("UI.MainMenu.Settings", "Settings");
        table.AddEntry("UI.MainMenu.Quit", "Quit");
        table.AddEntry("Combat.Brand.Iron", "Iron");
        table.AddEntry("Combat.Brand.Venom", "Venom");

        EditorUtility.SetDirty(table);
        AssetDatabase.SaveAssets();
    }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual JSON editing | Schema-validated JSON with typed C# loaders | Standard practice | Catches config errors at edit-time |
| Unity built-in localization strings | com.unity.localization package | Unity 2020+ | Smart Strings, plural rules, async loading |
| Manual texture import settings | AssetPostprocessor scripts | Long-standing | Consistent project-wide import standards |
| SpriteAtlas V1 (.spriteatlas) | SpriteAtlas V2 (.spriteatlasv2) in newer Unity | Unity 2020.2+ | V2 has scriptability limitations -- V1 API more stable for code creation |
| Manual albedo cleanup in Photoshop | Automated de-lighting algorithms | 2023+ | AI-generated models need automated cleanup pipeline |
| Per-model poly count checks | Per-asset-type budget enforcement | AAA pipeline standard | Asset type determines acceptable poly range |

**Deprecated/outdated:**
- **SpriteAtlas V2 programmatic creation:** Community reports native crashes; use V1 API (.spriteatlas) for code-generated atlases
- **JsonUtility for complex types:** Lacks Dictionary support, no polymorphic deserialization; Newtonsoft.Json preferred for complex configs

## Open Questions

1. **De-lighting Algorithm Tuning**
   - What we know: Lab color space separation + Gaussian blur works for general cases
   - What's unclear: Optimal blur radius and strength for Tripo3D output specifically
   - Recommendation: Implement with configurable parameters (blur_radius_pct, strength), provide before/after preview via viewport screenshot. Start with conservative defaults (strength=0.7) and let user adjust.

2. **Master Material Library Shader Complexity**
   - What we know: Need stone, wood, iron, moss, bone, cloth, leather base materials
   - What's unclear: Whether to use URP Lit materials with property presets or custom Shader Graph materials
   - Recommendation: Generate URP Lit materials with carefully tuned PBR properties (roughness, metallic, normal intensity) as the default. Can extend to Shader Graph later if needed. This avoids shader compilation overhead and works universally.

3. **SpriteAtlas V1 vs V2 for Unity 6**
   - What we know: V1 has stable code creation API, V2 has reported issues
   - What's unclear: Unity 6 default atlas version behavior
   - Recommendation: Target V1 (.spriteatlas extension) since it has proven programmatic creation support. If V2 is detected as default in the project, document manual migration path.

4. **Localization Package Version Compatibility**
   - What we know: com.unity.localization 1.5.x is latest stable
   - What's unclear: Exact API differences between 1.4 and 1.5
   - Recommendation: Target 1.5.x, use stable APIs (LocalizationEditorSettings, StringTable, Locale). The core string table API has been stable since 1.0.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | Tools/mcp-toolkit/pyproject.toml |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_data_templates.py tests/test_pipeline_templates.py tests/test_quality_templates.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | JSON config creation + schema validation | unit | `pytest tests/test_data_templates.py::TestJsonConfig -x` | Wave 0 |
| DATA-02 | SO definition + .asset instantiation scripts | unit | `pytest tests/test_data_templates.py::TestScriptableObjectAssets -x` | Wave 0 |
| DATA-03 | Localization string table setup scripts | unit | `pytest tests/test_data_templates.py::TestLocalization -x` | Wave 0 |
| DATA-04 | Game data authoring EditorWindow scripts | unit | `pytest tests/test_data_templates.py::TestDataAuthoring -x` | Wave 0 |
| IMP-03 | Git LFS .gitattributes + .gitignore generation | unit | `pytest tests/test_pipeline_templates.py::TestGitLfs -x` | Wave 0 |
| IMP-04 | Normal map baking workflow enhancement | unit | `pytest tests/test_pipeline_templates.py::TestNormalMapBake -x` | Wave 0 |
| BUILD-06 | Sprite atlas creation + sprite animation | unit | `pytest tests/test_pipeline_templates.py::TestSpriteAtlas -x` | Wave 0 |
| TWO-03 | Sprite Editor physics shape/pivot/9-slice | unit | `pytest tests/test_pipeline_templates.py::TestSpriteEditor -x` | Wave 0 |
| PIPE-08 | AssetPostprocessor script generation | unit | `pytest tests/test_pipeline_templates.py::TestAssetPostprocessor -x` | Wave 0 |
| AAA-01 | Albedo de-lighting algorithm | unit | `pytest tests/test_delight.py -x` | Wave 0 |
| AAA-02 | Per-asset-type poly budget enforcement | unit | `pytest tests/test_quality_templates.py::TestPolyBudget -x` | Wave 0 |
| AAA-03 | Dark fantasy palette validation | unit | `pytest tests/test_palette_validator.py -x` | Wave 0 |
| AAA-04 | Master material library generation | unit | `pytest tests/test_quality_templates.py::TestMasterMaterials -x` | Wave 0 |
| AAA-06 | Texture quality validation (texel density, channels) | unit | `pytest tests/test_quality_templates.py::TestTextureQuality -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/test_data_templates.py tests/test_pipeline_templates.py tests/test_quality_templates.py tests/test_delight.py tests/test_palette_validator.py -x -q`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green (3,453+ existing tests + new tests) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_data_templates.py` -- covers DATA-01, DATA-02, DATA-03, DATA-04
- [ ] `tests/test_pipeline_templates.py` -- covers IMP-03, IMP-04, BUILD-06, TWO-03, PIPE-08
- [ ] `tests/test_quality_templates.py` -- covers AAA-02, AAA-04, AAA-06
- [ ] `tests/test_delight.py` -- covers AAA-01
- [ ] `tests/test_palette_validator.py` -- covers AAA-03

## Sources

### Primary (HIGH confidence)
- Unity docs: [AssetPostprocessor](https://docs.unity3d.com/ScriptReference/AssetPostprocessor.html) -- OnPreprocessTexture, OnPreprocessModel, GetVersion
- Unity docs: [ScriptableObject](https://docs.unity3d.com/6000.2/Documentation/ScriptReference/ScriptableObject.html) -- CreateInstance, AssetDatabase.CreateAsset
- Unity docs: [SpriteAtlas](https://docs.unity3d.com/ScriptReference/U2D.SpriteAtlas.html) -- Programmatic creation, SpriteAtlasExtensions
- Unity docs: [TextureImporter](https://docs.unity3d.com/ScriptReference/TextureImporter.html) -- spriteBorder, spritePivot, spriteAlignment
- Unity docs: [Localization 1.5](https://docs.unity3d.com/Packages/com.unity.localization@1.5/changelog/CHANGELOG.html) -- StringTable API
- Existing codebase: `code_templates.py` generate_class with ScriptableObject support
- Existing codebase: `asset_templates.py` FBX/texture import presets
- Existing codebase: `texture.py` handle_bake_textures (Blender bake handler)
- Existing codebase: `HeroDisplayConfig.cs` (VeilBreakers SO pattern)
- Existing codebase: `GameDatabase.cs` (VeilBreakers JSON loading pattern)

### Secondary (MEDIUM confidence)
- [Texel Density Deep Dive](https://www.beyondextent.com/deep-dives/deepdive-texeldensity) -- 10.24 px/cm standard
- [.gitattributes for Unity](https://gist.github.com/nemotoo/b8a1c3a0f1225bb9231979f389fd4f3f) -- Community-standard LFS patterns
- [Adobe Substance Delighter](https://helpx.adobe.com/substance-3d-sampler/filters/tools/delight-ai-powered.html) -- De-lighting approach reference
- [Unity Labs De-lighting](https://www.cgchannel.com/2017/07/download-unity-labs-free-texture-de-lighting-tool/) -- Lab color space technique inspiration

### Tertiary (LOW confidence)
- SpriteAtlas V2 code creation limitations -- based on community forum reports, not official docs
- TMP_FontAsset programmatic creation specifics -- limited official documentation on scripted font atlas generation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- Unity built-in APIs well-documented, existing codebase patterns clear
- Architecture: HIGH -- Follows established compound-tool + template-generator pattern from 11 existing template modules
- Pitfalls: HIGH -- Based on Unity official docs warnings and existing codebase patterns
- De-lighting algorithm: MEDIUM -- Well-known technique but Tripo3D-specific tuning not validated
- SpriteAtlas V2: MEDIUM -- Community reports of issues, but V1 API is stable and recommended
- Palette validation: MEDIUM -- Custom implementation needed, but HSV analysis is straightforward

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable APIs, 30-day validity)
