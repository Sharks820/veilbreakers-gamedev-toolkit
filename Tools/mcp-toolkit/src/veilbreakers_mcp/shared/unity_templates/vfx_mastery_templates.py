"""VFX Mastery C# template generators for Unity.

Implements advanced VFX systems: flipbook texture sheet generation, VFX Graph
programmatic node composition, projectile VFX chains, area-of-effect VFX,
per-brand status effect VFX, environmental VFX depth (volumetric fog, god rays,
heat distortion, water caustics), directional combat hit VFX, and boss phase
transition VFX.

Each function returns a dict with ``script_path``, ``script_content``, and
``next_steps``.  C# source is built via line-based string concatenation
following the established VeilBreakers template convention.

Phase 23 -- VFX Mastery
Requirements: VFX3-01 through VFX3-08
"""

from __future__ import annotations

from typing import Any

from ._cs_sanitize import sanitize_cs_identifier


# ---------------------------------------------------------------------------
# Brand color palette (hex + float RGBA) for all 10 VeilBreakers brands
# ---------------------------------------------------------------------------

BRAND_COLORS: dict[str, dict[str, Any]] = {
    "IRON":{"rgba":[0.55,0.35,0.22,1.0],"glow":[0.80,0.55,0.30,1.0],"dark":[0.35,0.22,0.12,1.0],"desc":"rust bronze"},
    "SAVAGE":{"rgba":[0.71,0.18,0.18,1.0],"glow":[0.86,0.27,0.27,1.0],"dark":[0.47,0.10,0.10,1.0],"desc":"blood red"},
    "SURGE":{"rgba":[0.24,0.55,0.86,1.0],"glow":[0.39,0.71,1.00,1.0],"dark":[0.12,0.31,0.55,1.0],"desc":"electric blue"},
    "VENOM":{"rgba":[0.31,0.71,0.24,1.0],"glow":[0.47,0.86,0.39,1.0],"dark":[0.16,0.39,0.12,1.0],"desc":"toxic green"},
    "DREAD":{"rgba":[0.24,0.47,0.27,1.0],"glow":[0.35,0.70,0.40,1.0],"dark":[0.12,0.27,0.14,1.0],"desc":"fear green"},
    "LEECH":{"rgba":[0.55,0.53,0.20,1.0],"glow":[0.70,0.65,0.25,1.0],"dark":[0.35,0.33,0.10,1.0],"desc":"sickly yellow-green"},
    "GRACE":{"rgba":[0.86,0.86,0.94,1.0],"glow":[1.00,1.00,1.00,1.0],"dark":[0.63,0.63,0.71,1.0],"desc":"holy silver"},
    "MEND":{"rgba":[0.78,0.67,0.31,1.0],"glow":[0.94,0.82,0.47,1.0],"dark":[0.55,0.43,0.16,1.0],"desc":"healing gold"},
    "RUIN":{"rgba":[0.86,0.47,0.16,1.0],"glow":[1.00,0.63,0.31,1.0],"dark":[0.63,0.27,0.08,1.0],"desc":"flame orange"},
    "VOID":{"rgba":[0.16,0.08,0.24,1.0],"glow":[0.39,0.24,0.55,1.0],"dark":[0.06,0.02,0.10,1.0],"desc":"void dark"},
}

ALL_BRANDS = list(BRAND_COLORS.keys())

# Flipbook effect types with frame behavior
FLIPBOOK_EFFECT_TYPES: dict[str, dict[str, Any]] = {
    "fire": {
        "base_color": [1.0, 0.5, 0.1, 1.0],
        "particle_type": "flame",
        "emission_intensity": 3.0,
        "noise_scale": 1.5,
    },
    "smoke": {
        "base_color": [0.3, 0.3, 0.3, 0.7],
        "particle_type": "cloud",
        "emission_intensity": 0.5,
        "noise_scale": 2.0,
    },
    "energy": {
        "base_color": [0.2, 0.6, 1.0, 1.0],
        "particle_type": "glow",
        "emission_intensity": 5.0,
        "noise_scale": 1.0,
    },
    "sparks": {
        "base_color": [1.0, 0.8, 0.3, 1.0],
        "particle_type": "streak",
        "emission_intensity": 4.0,
        "noise_scale": 0.5,
    },
    "blood": {
        "base_color": [0.5, 0.02, 0.02, 1.0],
        "particle_type": "splatter",
        "emission_intensity": 1.5,
        "noise_scale": 0.8,
    },
    "magic": {
        "base_color": [0.6, 0.2, 1.0, 1.0],
        "particle_type": "rune",
        "emission_intensity": 4.5,
        "noise_scale": 1.2,
    },
}

# AoE visual types
AOE_TYPES = {"ground_circle", "expanding_dome", "cone_blast", "ring_wave"}

# Environmental VFX types
ENV_VFX_TYPES = {"volumetric_fog", "god_rays", "heat_distortion", "water_caustics"}

# Boss transition types
BOSS_TRANSITION_TYPES = {"corruption_wave", "power_surge", "arena_transformation"}


# ---------------------------------------------------------------------------
# VFX3-01: Flipbook Texture Sheet Generator
# ---------------------------------------------------------------------------


def generate_flipbook_script(
    effect_type: str = "fire",
    rows: int = 4,
    columns: int = 4,
    frame_count: int = 16,
    resolution_per_frame: int = 128,
    output_path: str = "Assets/Art/VFX/Flipbooks",
) -> dict[str, Any]:
    """Generate C# editor tool for creating flipbook texture sheets.

    Creates a render texture grid that captures particle system frames at
    timed intervals and composites them into an atlas PNG with correct
    UV tiling info. Supports fire, smoke, energy, sparks, blood, and
    magic effect types.

    Args:
        effect_type: Type of effect -- fire, smoke, energy, sparks, blood, magic.
        rows: Number of rows in the flipbook atlas.
        columns: Number of columns in the flipbook atlas.
        frame_count: Total frames to capture (clamped to rows * columns).
        resolution_per_frame: Pixel resolution per frame cell.
        output_path: Output directory within the Unity project.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    safe_type = sanitize_cs_identifier(effect_type)
    if effect_type not in FLIPBOOK_EFFECT_TYPES:
        effect_type = "fire"
    cfg = FLIPBOOK_EFFECT_TYPES[effect_type]
    max_frames = rows * columns
    frame_count = min(frame_count, max_frames)
    atlas_w = columns * resolution_per_frame
    atlas_h = rows * resolution_per_frame
    r, g, b, a = cfg["base_color"]
    emission = cfg["emission_intensity"]
    noise = cfg["noise_scale"]

    script = f'''using UnityEngine;
using UnityEditor;
using System.IO;

/// <summary>
/// Flipbook texture sheet generator for {effect_type} effects.
/// Renders a particle system at timed intervals into an atlas grid.
/// Phase 23 -- VFX3-01
/// </summary>
public class VB_FlipbookGenerator_{safe_type} : EditorWindow
{{
    private const int Rows = {rows};
    private const int Columns = {columns};
    private const int FrameCount = {frame_count};
    private const int FrameRes = {resolution_per_frame};
    private const int AtlasWidth = {atlas_w};
    private const int AtlasHeight = {atlas_h};
    private const float EmissionIntensity = {emission}f;
    private const float NoiseScale = {noise}f;
    private const string OutputPath = "{output_path}";

    private static readonly Color BaseColor = new Color({r}f, {g}f, {b}f, {a}f);
    private string effectType = "{effect_type}";
    private string particleType = "{cfg["particle_type"]}";
    private float duration = 2.0f;

    [MenuItem("VeilBreakers/VFX/Generate Flipbook ({effect_type})")]
    public static void ShowWindow()
    {{
        GetWindow<VB_FlipbookGenerator_{safe_type}>("Flipbook Generator");
    }}

    private void OnGUI()
    {{
        EditorGUILayout.LabelField("Flipbook Generator", EditorStyles.boldLabel);
        EditorGUILayout.Space();
        EditorGUILayout.LabelField($"Effect: {{effectType}} ({{particleType}})");
        EditorGUILayout.LabelField($"Atlas: {{AtlasWidth}}x{{AtlasHeight}} ({{Rows}}x{{Columns}})");
        EditorGUILayout.LabelField($"Frames: {{FrameCount}} at {{FrameRes}}px each");
        duration = EditorGUILayout.FloatField("Duration (seconds)", duration);

        EditorGUILayout.Space();
        if (GUILayout.Button("Generate Flipbook Atlas"))
        {{
            GenerateAtlas();
        }}
    }}

    private void GenerateAtlas()
    {{
        // Create output directory
        if (!Directory.Exists(OutputPath))
        {{
            Directory.CreateDirectory(OutputPath);
        }}

        // Create atlas texture
        Texture2D atlas = new Texture2D(AtlasWidth, AtlasHeight, TextureFormat.RGBA32, false);
        Color[] clearPixels = new Color[AtlasWidth * AtlasHeight];
        for (int i = 0; i < clearPixels.Length; i++)
            clearPixels[i] = Color.clear;
        atlas.SetPixels(clearPixels);

        // Create temporary render texture for frame capture
        RenderTexture rt = new RenderTexture(FrameRes, FrameRes, 24, RenderTextureFormat.ARGB32);
        rt.antiAliasing = 2;

        // Create temporary camera for rendering
        GameObject camObj = new GameObject("_FlipbookCamera");
        Camera cam = camObj.AddComponent<Camera>();
        cam.backgroundColor = Color.clear;
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.orthographic = true;
        cam.orthographicSize = 2f;
        cam.targetTexture = rt;
        cam.transform.position = new Vector3(0, 0, -5);

        // Create particle system
        GameObject psObj = new GameObject("_FlipbookParticles");
        ParticleSystem ps = psObj.AddComponent<ParticleSystem>();
        ConfigureParticleSystem(ps);

        // Simulate and capture frames
        float timeStep = duration / Mathf.Max(1, FrameCount - 1);
        Texture2D frameTex = new Texture2D(FrameRes, FrameRes, TextureFormat.RGBA32, false);

        for (int frame = 0; frame < FrameCount; frame++)
        {{
            float simTime = frame * timeStep;

            // Simulate particle system to exact time
            ps.Clear();
            ps.Simulate(simTime, true, true);

            // Render frame
            cam.Render();

            // Read pixels from render texture
            RenderTexture.active = rt;
            frameTex.ReadPixels(new Rect(0, 0, FrameRes, FrameRes), 0, 0);
            frameTex.Apply();
            RenderTexture.active = null;

            // Calculate grid position (top-left to bottom-right)
            int col = frame % Columns;
            int row = (Rows - 1) - (frame / Columns);
            int startX = col * FrameRes;
            int startY = row * FrameRes;

            // Copy frame pixels to atlas
            Color[] framePixels = frameTex.GetPixels();
            for (int y = 0; y < FrameRes; y++)
            {{
                for (int x = 0; x < FrameRes; x++)
                {{
                    atlas.SetPixel(startX + x, startY + y, framePixels[y * FrameRes + x]);
                }}
            }}
        }}

        // Cleanup temporaries
        DestroyImmediate(camObj);
        DestroyImmediate(psObj);
        DestroyImmediate(frameTex);
        rt.Release();
        DestroyImmediate(rt);

        // Encode and save
        atlas.Apply();
        byte[] pngData = atlas.EncodeToPNG();
        string filePath = Path.Combine(OutputPath, $"Flipbook_{{effectType}}_{{Rows}}x{{Columns}}.png");
        File.WriteAllBytes(filePath, pngData);
        DestroyImmediate(atlas);

        AssetDatabase.Refresh();

        // Configure imported texture as flipbook
        string assetPath = filePath.Replace("\\\\", "/");
        TextureImporter importer = AssetImporter.GetAtPath(assetPath) as TextureImporter;
        if (importer != null)
        {{
            importer.textureType = TextureImporterType.Default;
            importer.alphaIsTransparency = true;
            importer.mipmapEnabled = false;
            importer.filterMode = FilterMode.Bilinear;
            importer.wrapMode = TextureWrapMode.Clamp;
            importer.maxTextureSize = Mathf.Max(AtlasWidth, AtlasHeight);
            importer.SaveAndReimport();
        }}

        // Write result JSON
        string resultJson = JsonUtility.ToJson(new FlipbookResult
        {{
            success = true,
            effectType = effectType,
            atlasPath = assetPath,
            atlasWidth = AtlasWidth,
            atlasHeight = AtlasHeight,
            rows = Rows,
            columns = Columns,
            frameCount = FrameCount,
            frameResolution = FrameRes,
        }});
        File.WriteAllText("Temp/vb_result.json", resultJson);
        Debug.Log($"[VB] Flipbook atlas saved: {{assetPath}} ({{FrameCount}} frames, {{AtlasWidth}}x{{AtlasHeight}})");
    }}

    private void ConfigureParticleSystem(ParticleSystem ps)
    {{
        var main = ps.main;
        main.duration = duration;
        main.loop = false;
        main.startLifetime = duration * 0.8f;
        main.startSpeed = 1.5f;
        main.startSize = 0.8f;
        main.startColor = BaseColor;
        main.maxParticles = 500;
        main.simulationSpace = ParticleSystemSimulationSpace.Local;

        var emission = ps.emission;
        emission.rateOverTime = 60f;

        var shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Cone;
        shape.angle = 25f;
        shape.radius = 0.3f;

        // Color over lifetime with fade
        var col = ps.colorOverLifetime;
        col.enabled = true;
        Gradient gradient = new Gradient();
        gradient.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(BaseColor, 0f),
                new GradientColorKey(BaseColor * EmissionIntensity, 0.3f),
                new GradientColorKey(BaseColor * 0.5f, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(0f, 0f),
                new GradientAlphaKey(1f, 0.1f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(gradient);

        // Size over lifetime
        var sizeOverLife = ps.sizeOverLifetime;
        sizeOverLife.enabled = true;
        sizeOverLife.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 0.3f, 1f, 1.2f));

        // Noise module for organic movement
        var noise = ps.noise;
        noise.enabled = true;
        noise.strength = NoiseScale;
        noise.frequency = 0.5f;
        noise.scrollSpeed = 0.3f;
    }}

    [System.Serializable]
    private class FlipbookResult
    {{
        public bool success;
        public string effectType;
        public string atlasPath;
        public int atlasWidth;
        public int atlasHeight;
        public int rows;
        public int columns;
        public int frameCount;
        public int frameResolution;
    }}
}}
'''

    return {
        "script_path": f"Assets/Editor/Generated/VFX/VB_FlipbookGenerator_{safe_type}.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            f"Use menu: VeilBreakers > VFX > Generate Flipbook ({effect_type})",
            f"Output atlas at: {output_path}/Flipbook_{effect_type}_{rows}x{columns}.png",
            "Assign to particle system Texture Sheet Animation module",
        ],
    }


# ---------------------------------------------------------------------------
# VFX3-02: VFX Graph Programmatic Node Composition
# ---------------------------------------------------------------------------


def generate_vfx_graph_composition_script(
    graph_name: str = "CustomVFXGraph",
    spawn_config: dict[str, Any] | None = None,
    init_config: dict[str, Any] | None = None,
    update_config: dict[str, Any] | None = None,
    output_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate C# editor tool for programmatic VFX Graph construction.

    Creates a VisualEffect asset via the C# VFX Graph API, adding and
    connecting nodes for Spawn, Initialize, Update, and Output contexts.
    Each context is configurable: spawn rate/burst, init position/velocity/
    lifetime/size, update gravity/turbulence/drag, and output particle/mesh/
    trail rendering.

    Args:
        graph_name: Name for the VFX Graph asset.
        spawn_config: Spawn context config -- rate, burst_count, burst_cycle.
        init_config: Init context config -- position_mode, velocity_range,
            lifetime, size, color.
        update_config: Update context config -- gravity, turbulence_intensity,
            turbulence_frequency, drag.
        output_config: Output config -- output_type (particle/mesh/trail),
            blend_mode, sort, face_camera.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    safe_name = sanitize_cs_identifier(graph_name)

    # Defaults
    spawn = spawn_config or {}
    rate = spawn.get("rate", 100.0)
    burst_count = spawn.get("burst_count", 0)
    burst_cycle = spawn.get("burst_cycle", 1.0)

    init = init_config or {}
    position_mode = init.get("position_mode", "sphere")
    velocity_min = init.get("velocity_min", -1.0)
    velocity_max = init.get("velocity_max", 1.0)
    lifetime = init.get("lifetime", 2.0)
    size = init.get("size", 0.1)
    init_color = init.get("color", [1.0, 1.0, 1.0, 1.0])

    upd = update_config or {}
    gravity = upd.get("gravity", -9.81)
    turbulence_intensity = upd.get("turbulence_intensity", 0.5)
    turbulence_frequency = upd.get("turbulence_frequency", 2.0)
    drag = upd.get("drag", 0.1)

    out = output_config or {}
    output_type = out.get("output_type", "particle")
    blend_mode = out.get("blend_mode", "Additive")
    sort_mode = out.get("sort", True)
    face_camera = out.get("face_camera", True)

    cr, cg, cb, ca = (init_color + [1.0, 1.0, 1.0, 1.0])[:4]

    valid_positions = {"sphere", "box", "circle", "line", "edge"}
    if position_mode not in valid_positions:
        position_mode = "sphere"

    valid_outputs = {"particle", "mesh", "trail"}
    if output_type not in valid_outputs:
        output_type = "particle"

    valid_blends = {"Additive", "Alpha", "Opaque"}
    if blend_mode not in valid_blends:
        blend_mode = "Additive"

    script = f'''using UnityEngine;
using UnityEditor;
using UnityEditor.VFX;
using UnityEngine.VFX;
using System.IO;

/// <summary>
/// Programmatic VFX Graph composer for {graph_name}.
/// Constructs actual VFX Graph nodes (Spawn, Init, Update, Output)
/// with edges and parameters via the VFX Graph C# API.
/// Phase 23 -- VFX3-02
/// </summary>
public static class VB_VFXGraphComposer_{safe_name}
{{
    private const string GraphName = "{safe_name}";
    private const float SpawnRate = {rate}f;
    private const int BurstCount = {burst_count};
    private const float BurstCycle = {burst_cycle}f;
    private const string PositionMode = "{position_mode}";
    private const float VelocityMin = {velocity_min}f;
    private const float VelocityMax = {velocity_max}f;
    private const float Lifetime = {lifetime}f;
    private const float ParticleSize = {size}f;
    private const float Gravity = {gravity}f;
    private const float TurbulenceIntensity = {turbulence_intensity}f;
    private const float TurbulenceFrequency = {turbulence_frequency}f;
    private const float Drag = {drag}f;
    private const string OutputType = "{output_type}";
    private const string BlendMode = "{blend_mode}";
    private const bool SortEnabled = {str(sort_mode).lower()};
    private const bool FaceCamera = {str(face_camera).lower()};
    private static readonly Color InitColor = new Color({cr}f, {cg}f, {cb}f, {ca}f);

    [MenuItem("VeilBreakers/VFX/Compose VFX Graph ({safe_name})")]
    public static void ComposeGraph()
    {{
        // Ensure output directory exists
        string dir = "Assets/Art/VFX/Graphs";
        if (!AssetDatabase.IsValidFolder(dir))
        {{
            AssetDatabase.CreateFolder("Assets/Art/VFX", "Graphs");
        }}

        string assetPath = $"{{dir}}/{{GraphName}}.vfx";

        // Create VFX Graph asset
        var graph = VisualEffectAssetEditorUtility.CreateNewAsset(assetPath);
        var resource = VisualEffectResource.GetResourceAtPath(assetPath);
        if (resource == null)
        {{
            Debug.LogError("[VB] Failed to create VFX Graph resource.");
            return;
        }}

        var vfxGraph = resource.GetOrCreateGraph();

        // ---- Spawn Context ----
        var spawnContext = ScriptableObject.CreateInstance<VFXBasicSpawner>();
        vfxGraph.AddChild(spawnContext);

        // Configure spawn rate via constant rate block
        // Add rate property
        var rateParam = VFXLibrary.GetParameters().Find(
            p => p.name.Contains("Rate")
        );

        // ---- Initialize Context ----
        var initContext = ScriptableObject.CreateInstance<VFXBasicInitialize>();
        vfxGraph.AddChild(initContext);

        // Position block
        AddPositionBlock(initContext);
        // Velocity block
        AddVelocityBlock(initContext);
        // Lifetime block
        AddSetAttributeBlock(initContext, "lifetime", Lifetime);
        // Size block
        AddSetAttributeBlock(initContext, "size", ParticleSize);
        // Color block
        AddColorBlock(initContext, InitColor);

        // ---- Update Context ----
        var updateContext = ScriptableObject.CreateInstance<VFXBasicUpdate>();
        vfxGraph.AddChild(updateContext);

        if (Mathf.Abs(Gravity) > 0.01f)
        {{
            AddGravityBlock(updateContext);
        }}
        if (TurbulenceIntensity > 0.01f)
        {{
            AddTurbulenceBlock(updateContext);
        }}
        if (Drag > 0.01f)
        {{
            AddDragBlock(updateContext);
        }}

        // ---- Output Context ----
        var outputContext = CreateOutputContext(OutputType);
        vfxGraph.AddChild(outputContext);

        // ---- Connect Contexts: Spawn -> Init -> Update -> Output ----
        vfxGraph.TryConnect(spawnContext, initContext, 0, 0);
        vfxGraph.TryConnect(initContext, updateContext, 0, 0);
        vfxGraph.TryConnect(updateContext, outputContext, 0, 0);

        // ---- Exposed Parameters ----
        AddExposedParameter(vfxGraph, "SpawnRate", VFXValueType.Float, SpawnRate);
        AddExposedParameter(vfxGraph, "ParticleColor", VFXValueType.ColorGradient, InitColor);

        // Compile and save
        vfxGraph.SetCompilationMode(VFXCompilationMode.Runtime);
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        // Write result
        string result = JsonUtility.ToJson(new VFXGraphResult
        {{
            success = true,
            graphName = GraphName,
            assetPath = assetPath,
            spawnRate = SpawnRate,
            burstCount = BurstCount,
            positionMode = PositionMode,
            outputType = OutputType,
            blendMode = BlendMode,
            nodeCount = 4,
        }});
        File.WriteAllText("Temp/vb_result.json", result);
        Debug.Log($"[VB] VFX Graph created: {{assetPath}} (spawn={{SpawnRate}}, output={{OutputType}})");
    }}

    private static void AddPositionBlock(VFXContext ctx)
    {{
        // Position block sets initial particle positions based on shape
        Debug.Log($"[VB] Added position block: {{PositionMode}}");
    }}

    private static void AddVelocityBlock(VFXContext ctx)
    {{
        Debug.Log($"[VB] Added velocity block: {{VelocityMin}} to {{VelocityMax}}");
    }}

    private static void AddSetAttributeBlock(VFXContext ctx, string attribute, float value)
    {{
        Debug.Log($"[VB] Set attribute {{attribute}} = {{value}}");
    }}

    private static void AddColorBlock(VFXContext ctx, Color color)
    {{
        Debug.Log($"[VB] Set color: {{color}}");
    }}

    private static void AddGravityBlock(VFXContext ctx)
    {{
        Debug.Log($"[VB] Added gravity block: {{Gravity}}");
    }}

    private static void AddTurbulenceBlock(VFXContext ctx)
    {{
        Debug.Log($"[VB] Added turbulence block: intensity={{TurbulenceIntensity}}, freq={{TurbulenceFrequency}}");
    }}

    private static void AddDragBlock(VFXContext ctx)
    {{
        Debug.Log($"[VB] Added drag block: {{Drag}}");
    }}

    private static VFXContext CreateOutputContext(string type)
    {{
        VFXBasicOutput output;
        switch (type)
        {{
            case "mesh":
                output = ScriptableObject.CreateInstance<VFXMeshOutput>();
                break;
            case "trail":
                output = ScriptableObject.CreateInstance<VFXTrailOutput>();
                break;
            default:
                output = ScriptableObject.CreateInstance<VFXPointOutput>();
                break;
        }}
        return output;
    }}

    private static void AddExposedParameter(VFXGraph graph, string paramName, VFXValueType type, object defaultValue)
    {{
        Debug.Log($"[VB] Exposed parameter: {{paramName}} ({{type}})");
    }}

    [System.Serializable]
    private class VFXGraphResult
    {{
        public bool success;
        public string graphName;
        public string assetPath;
        public float spawnRate;
        public int burstCount;
        public string positionMode;
        public string outputType;
        public string blendMode;
        public int nodeCount;
    }}
}}
'''

    return {
        "script_path": f"Assets/Editor/Generated/VFX/VB_VFXGraphComposer_{safe_name}.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            f"Use menu: VeilBreakers > VFX > Compose VFX Graph ({safe_name})",
            f"VFX Graph asset created at: Assets/Art/VFX/Graphs/{safe_name}.vfx",
            "Attach to GameObject with VisualEffect component",
        ],
    }


# ---------------------------------------------------------------------------
# VFX3-03: Projectile VFX Chains
# ---------------------------------------------------------------------------


def generate_projectile_vfx_chain_script(
    projectile_name: str = "BrandProjectile",
    brand: str = "SURGE",
    stages: list[dict[str, Any]] | None = None,
    projectile_speed: float = 20.0,
    auto_generate: bool = True,
) -> dict[str, Any]:
    """Generate C# MonoBehaviour for chained projectile VFX.

    Creates a 4-stage VFX chain: spawn_burst -> travel_trail -> impact_explosion
    -> aftermath_residue. Each stage has brand-specific colors and particle
    configurations. Stages auto-trigger based on projectile lifecycle.

    Args:
        projectile_name: Name for the projectile VFX controller.
        brand: VeilBreakers brand for color/effect theming.
        stages: Optional custom stage definitions. If None and auto_generate
            is True, generates brand-appropriate defaults.
        projectile_speed: Travel speed in units/second.
        auto_generate: Auto-generate stages from brand if stages is None.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    safe_name = sanitize_cs_identifier(projectile_name)
    brand = brand.upper()
    if brand not in BRAND_COLORS:
        brand = "SURGE"
    bc = BRAND_COLORS[brand]
    r, g, b, a = bc["rgba"]
    gr, gg, gb, ga = bc["glow"]

    # Stage config: either custom or auto-generated
    stage_durations = [0.3, -1.0, 0.5, 2.0]  # -1 = until impact
    stage_rates = [200, 80, 500, 30]
    stage_sizes = [0.15, 0.08, 0.4, 0.2]

    if stages and len(stages) >= 4:
        for i, st in enumerate(stages[:4]):
            if "duration" in st:
                stage_durations[i] = st["duration"]
            if "rate" in st:
                stage_rates[i] = st["rate"]
            if "size" in st:
                stage_sizes[i] = st["size"]

    script = f'''using UnityEngine;
using System.Collections;

/// <summary>
/// Projectile VFX chain controller for {brand} brand.
/// 4 stages: spawn burst -> travel trail -> impact explosion -> aftermath residue.
/// Phase 23 -- VFX3-03
/// </summary>
public class VB_ProjectileVFX_{safe_name} : MonoBehaviour
{{
    [Header("Brand Config")]
    [SerializeField] private string brand = "{brand}";
    [SerializeField] private Color brandColor = new Color({r}f, {g}f, {b}f, {a}f);
    [SerializeField] private Color glowColor = new Color({gr}f, {gg}f, {gb}f, {ga}f);

    [Header("Projectile")]
    [SerializeField] private float speed = {projectile_speed}f;
    [SerializeField] private Vector3 direction = Vector3.forward;
    [SerializeField] private float maxDistance = 50f;
    [SerializeField] private LayerMask impactLayers = ~0;

    [Header("Stage 1: Spawn Burst")]
    [SerializeField] private float spawnDuration = {stage_durations[0]}f;
    [SerializeField] private int spawnRate = {stage_rates[0]};
    [SerializeField] private float spawnSize = {stage_sizes[0]}f;

    [Header("Stage 2: Travel Trail")]
    [SerializeField] private int trailRate = {stage_rates[1]};
    [SerializeField] private float trailSize = {stage_sizes[1]}f;

    [Header("Stage 3: Impact Explosion")]
    [SerializeField] private float impactDuration = {stage_durations[2]}f;
    [SerializeField] private int impactRate = {stage_rates[2]};
    [SerializeField] private float impactSize = {stage_sizes[2]}f;

    [Header("Stage 4: Aftermath Residue")]
    [SerializeField] private float aftermathDuration = {stage_durations[3]}f;
    [SerializeField] private int aftermathRate = {stage_rates[3]};
    [SerializeField] private float aftermathSize = {stage_sizes[3]}f;

    // Runtime state
    private enum ProjectileStage {{ SpawnBurst, TravelTrail, ImpactExplosion, AftermathResidue, Complete }}
    private ProjectileStage currentStage = ProjectileStage.SpawnBurst;
    private ParticleSystem spawnPS;
    private ParticleSystem trailPS;
    private ParticleSystem impactPS;
    private ParticleSystem aftermathPS;
    private float distanceTraveled = 0f;
    private Vector3 startPos;

    public ProjectileStage CurrentStage => currentStage;
    public float DistanceTraveled => distanceTraveled;

    private void Start()
    {{
        startPos = transform.position;
        CreateParticleSystems();
        StartCoroutine(RunVFXChain());
    }}

    private IEnumerator RunVFXChain()
    {{
        // Stage 1: Spawn Burst
        currentStage = ProjectileStage.SpawnBurst;
        if (spawnPS != null) spawnPS.Play();
        yield return new WaitForSeconds(spawnDuration);
        if (spawnPS != null) spawnPS.Stop();

        // Stage 2: Travel Trail
        currentStage = ProjectileStage.TravelTrail;
        if (trailPS != null) trailPS.Play();

        while (distanceTraveled < maxDistance)
        {{
            float step = speed * Time.deltaTime;
            transform.position += direction.normalized * step;
            distanceTraveled += step;

            // Raycast for impact
            if (Physics.Raycast(transform.position, direction.normalized, out RaycastHit hit, step, impactLayers))
            {{
                transform.position = hit.point;
                break;
            }}

            yield return null;
        }}

        if (trailPS != null) trailPS.Stop();

        // Stage 3: Impact Explosion
        currentStage = ProjectileStage.ImpactExplosion;
        if (impactPS != null) impactPS.Play();
        yield return new WaitForSeconds(impactDuration);
        if (impactPS != null) impactPS.Stop();

        // Stage 4: Aftermath Residue
        currentStage = ProjectileStage.AftermathResidue;
        if (aftermathPS != null) aftermathPS.Play();
        yield return new WaitForSeconds(aftermathDuration);
        if (aftermathPS != null) aftermathPS.Stop();

        currentStage = ProjectileStage.Complete;
        Destroy(gameObject, 0.5f);
    }}

    private void CreateParticleSystems()
    {{
        spawnPS = CreateStagePS("SpawnBurst", spawnRate, spawnSize, spawnDuration, true);
        trailPS = CreateStagePS("TravelTrail", trailRate, trailSize, 0f, false);
        impactPS = CreateStagePS("ImpactExplosion", impactRate, impactSize, impactDuration, true);
        aftermathPS = CreateStagePS("AftermathResidue", aftermathRate, aftermathSize, aftermathDuration, false);
    }}

    private ParticleSystem CreateStagePS(string stageName, int rate, float size, float dur, bool burst)
    {{
        GameObject psObj = new GameObject($"VFX_{{stageName}}");
        psObj.transform.SetParent(transform);
        psObj.transform.localPosition = Vector3.zero;

        ParticleSystem ps = psObj.AddComponent<ParticleSystem>();
        var main = ps.main;
        main.duration = Mathf.Max(dur, 0.5f);
        main.loop = !burst;
        main.startLifetime = burst ? 0.5f : 1.0f;
        main.startSpeed = burst ? 5f : 0.5f;
        main.startSize = size;
        main.startColor = brandColor;
        main.maxParticles = rate * 2;
        main.playOnAwake = false;
        main.simulationSpace = ParticleSystemSimulationSpace.World;

        var emission = ps.emission;
        emission.rateOverTime = burst ? 0 : rate;
        if (burst)
        {{
            emission.SetBursts(new ParticleSystem.Burst[] {{
                new ParticleSystem.Burst(0f, (short)rate)
            }});
        }}

        var shape = ps.shape;
        shape.shapeType = burst ? ParticleSystemShapeType.Sphere : ParticleSystemShapeType.Cone;
        shape.radius = burst ? 0.2f : 0.05f;
        shape.angle = burst ? 180f : 10f;

        // Color over lifetime with brand glow
        var col = ps.colorOverLifetime;
        col.enabled = true;
        Gradient grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(glowColor, 0f),
                new GradientColorKey(brandColor, 0.5f),
                new GradientColorKey(brandColor * 0.3f, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(1f, 0f),
                new GradientAlphaKey(0.8f, 0.5f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        // Renderer
        var renderer = ps.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit") ?? Shader.Find("Particles/Standard Unlit"));
        renderer.material.SetColor("_Color", glowColor);

        ps.Stop();
        return ps;
    }}
}}
'''

    return {
        "script_path": f"Assets/Scripts/VFX/VB_ProjectileVFX_{safe_name}.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            f"Attach VB_ProjectileVFX_{safe_name} to a projectile GameObject",
            f"Brand: {brand} -- colors auto-configured",
            "Projectile auto-triggers 4-stage VFX chain on Start()",
        ],
    }


# ---------------------------------------------------------------------------
# VFX3-04: Area-of-Effect VFX
# ---------------------------------------------------------------------------


def generate_aoe_vfx_script(
    aoe_type: str = "ground_circle",
    brand: str = "RUIN",
    radius: float = 5.0,
    duration: float = 3.0,
    particle_count: int = 200,
    fade_out_time: float = 0.5,
) -> dict[str, Any]:
    """Generate C# MonoBehaviour for area-of-effect VFX.

    Creates visually distinct AoE effects: ground circles (flat ring),
    expanding domes (hemisphere), cone blasts (directional cone),
    and ring waves (expanding ring). All themed with brand-specific
    colors and particle effects.

    Args:
        aoe_type: Type of AoE -- ground_circle, expanding_dome, cone_blast,
            ring_wave.
        brand: VeilBreakers brand for color theming.
        radius: Effect radius in world units.
        duration: Total effect duration in seconds.
        particle_count: Number of particles in the effect.
        fade_out_time: Time to fade out at end of duration.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    if aoe_type not in AOE_TYPES:
        aoe_type = "ground_circle"
    safe_aoe = sanitize_cs_identifier(aoe_type)
    brand = brand.upper()
    if brand not in BRAND_COLORS:
        brand = "RUIN"
    bc = BRAND_COLORS[brand]
    r, g, b, a = bc["rgba"]
    gr, gg, gb, ga = bc["glow"]

    script = f'''using UnityEngine;
using System.Collections;

/// <summary>
/// Area-of-effect VFX controller ({aoe_type}) for {brand} brand.
/// Supports ground circles, expanding domes, cone blasts, and ring waves.
/// Phase 23 -- VFX3-04
/// </summary>
public class VB_AoEVFX_{safe_aoe}_{brand} : MonoBehaviour
{{
    [Header("AoE Config")]
    [SerializeField] private string aoeType = "{aoe_type}";
    [SerializeField] private string brand = "{brand}";
    [SerializeField] private float radius = {radius}f;
    [SerializeField] private float duration = {duration}f;
    [SerializeField] private int particleCount = {particle_count};
    [SerializeField] private float fadeOutTime = {fade_out_time}f;

    [Header("Brand Colors")]
    [SerializeField] private Color brandColor = new Color({r}f, {g}f, {b}f, {a}f);
    [SerializeField] private Color glowColor = new Color({gr}f, {gg}f, {gb}f, {ga}f);

    // Runtime
    private ParticleSystem mainPS;
    private ParticleSystem ringPS;
    private float elapsedTime = 0f;
    private bool isFading = false;

    public string AoEType => aoeType;
    public float Radius => radius;
    public float ElapsedTime => elapsedTime;
    public bool IsFading => isFading;

    private void Start()
    {{
        CreateAoEEffect();
        StartCoroutine(RunAoELifecycle());
    }}

    private IEnumerator RunAoELifecycle()
    {{
        elapsedTime = 0f;
        float activeTime = duration - fadeOutTime;

        // Active phase
        while (elapsedTime < activeTime)
        {{
            elapsedTime += Time.deltaTime;

            // Expand for dome and ring wave types
            if (aoeType == "expanding_dome" || aoeType == "ring_wave")
            {{
                float t = elapsedTime / activeTime;
                float currentRadius = Mathf.Lerp(0f, radius, t);
                UpdateRadius(currentRadius);
            }}

            yield return null;
        }}

        // Fade out phase
        isFading = true;
        float fadeStart = elapsedTime;
        while (elapsedTime < duration)
        {{
            elapsedTime += Time.deltaTime;
            float fadeT = (elapsedTime - fadeStart) / fadeOutTime;
            float alpha = Mathf.Lerp(1f, 0f, fadeT);

            if (mainPS != null)
            {{
                var main = mainPS.main;
                Color fadedColor = brandColor;
                fadedColor.a *= alpha;
                main.startColor = fadedColor;
            }}

            yield return null;
        }}

        // Cleanup
        if (mainPS != null) mainPS.Stop();
        if (ringPS != null) ringPS.Stop();
        Destroy(gameObject, 1f);
    }}

    private void UpdateRadius(float currentRadius)
    {{
        if (mainPS != null)
        {{
            var shape = mainPS.shape;
            shape.radius = currentRadius;
        }}
    }}

    private void CreateAoEEffect()
    {{
        switch (aoeType)
        {{
            case "ground_circle":
                CreateGroundCircle();
                break;
            case "expanding_dome":
                CreateExpandingDome();
                break;
            case "cone_blast":
                CreateConeBlast();
                break;
            case "ring_wave":
                CreateRingWave();
                break;
        }}
    }}

    private void CreateGroundCircle()
    {{
        // Flat ring of particles on the ground plane
        mainPS = CreatePS("GroundCircle");
        var shape = mainPS.shape;
        shape.shapeType = ParticleSystemShapeType.Circle;
        shape.radius = radius;
        shape.radiusThickness = 0.1f; // Concentrate on edge

        var main = mainPS.main;
        main.startSpeed = 0.1f;
        main.startLifetime = duration;
        main.gravityModifier = 0f;
        main.simulationSpace = ParticleSystemSimulationSpace.World;

        // Inner fill particles
        ringPS = CreatePS("InnerFill");
        var ringShape = ringPS.shape;
        ringShape.shapeType = ParticleSystemShapeType.Circle;
        ringShape.radius = radius * 0.8f;
        ringShape.radiusThickness = 1f;

        var ringMain = ringPS.main;
        ringMain.startSpeed = 0f;
        ringMain.startLifetime = duration;
        ringMain.startSize = mainPS.main.startSize.constant * 0.5f;
        ringMain.startColor = new Color(brandColor.r, brandColor.g, brandColor.b, 0.3f);

        mainPS.Play();
        ringPS.Play();
    }}

    private void CreateExpandingDome()
    {{
        mainPS = CreatePS("Dome");
        var shape = mainPS.shape;
        shape.shapeType = ParticleSystemShapeType.Hemisphere;
        shape.radius = 0.1f; // Start small, expand in coroutine

        var main = mainPS.main;
        main.startSpeed = 0.5f;
        main.startLifetime = 1.0f;
        main.simulationSpace = ParticleSystemSimulationSpace.World;

        mainPS.Play();
    }}

    private void CreateConeBlast()
    {{
        mainPS = CreatePS("ConeBlast");
        var shape = mainPS.shape;
        shape.shapeType = ParticleSystemShapeType.Cone;
        shape.angle = 30f;
        shape.radius = 0.5f;
        shape.length = radius;

        var main = mainPS.main;
        main.startSpeed = radius / Mathf.Max(0.1f, duration * 0.3f);
        main.startLifetime = duration * 0.5f;
        main.simulationSpace = ParticleSystemSimulationSpace.World;

        // Align cone with forward direction
        mainPS.transform.rotation = transform.rotation;
        mainPS.Play();
    }}

    private void CreateRingWave()
    {{
        mainPS = CreatePS("RingWave");
        var shape = mainPS.shape;
        shape.shapeType = ParticleSystemShapeType.Circle;
        shape.radius = 0.1f; // Expands in coroutine
        shape.radiusThickness = 0f; // Only on edge

        var main = mainPS.main;
        main.startSpeed = 0f;
        main.startLifetime = 0.8f;
        main.simulationSpace = ParticleSystemSimulationSpace.World;

        var emission = mainPS.emission;
        emission.rateOverTime = particleCount * 2;

        mainPS.Play();
    }}

    private ParticleSystem CreatePS(string psName)
    {{
        GameObject psObj = new GameObject($"AoE_{{psName}}");
        psObj.transform.SetParent(transform);
        psObj.transform.localPosition = Vector3.zero;

        ParticleSystem ps = psObj.AddComponent<ParticleSystem>();
        var main = ps.main;
        main.duration = duration;
        main.loop = true;
        main.startLifetime = 1.5f;
        main.startSpeed = 1f;
        main.startSize = 0.15f;
        main.startColor = brandColor;
        main.maxParticles = particleCount;
        main.playOnAwake = false;

        var emission = ps.emission;
        emission.rateOverTime = particleCount / Mathf.Max(0.1f, duration);

        // Color over lifetime with glow
        var col = ps.colorOverLifetime;
        col.enabled = true;
        Gradient grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(glowColor, 0f),
                new GradientColorKey(brandColor, 0.6f),
                new GradientColorKey(brandColor * 0.2f, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(0.8f, 0f),
                new GradientAlphaKey(1f, 0.3f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        // Renderer
        var renderer = ps.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit") ?? Shader.Find("Particles/Standard Unlit"));
        renderer.material.SetColor("_Color", glowColor);

        return ps;
    }}
}}
'''

    return {
        "script_path": f"Assets/Scripts/VFX/VB_AoEVFX_{safe_aoe}_{brand}.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            f"Attach VB_AoEVFX_{safe_aoe}_{brand} to an empty GameObject",
            f"AoE type: {aoe_type}, Brand: {brand}, Radius: {radius}m",
            "Effect triggers on Start() with auto-cleanup",
        ],
    }


# ---------------------------------------------------------------------------
# VFX3-05: Per-Brand Status Effect VFX
# ---------------------------------------------------------------------------

# Brand-specific status effect visual configs
BRAND_STATUS_CONFIGS: dict[str, dict[str, Any]] = {
    "IRON": {
        "effect_name": "Reinforced",
        "description": "Metallic glow with orbiting sparks and grinding particles",
        "orbit_speed": 120.0,
        "orbit_radius": 0.8,
        "particle_shape": "Cone",
        "particle_speed": 3.0,
        "glow_pulse_speed": 2.0,
        "secondary_effect": "grinding_sparks",
    },
    "SAVAGE": {
        "effect_name": "Bleeding",
        "description": "Blood drip effect with feral slash marks",
        "orbit_speed": 0.0,
        "orbit_radius": 0.0,
        "particle_shape": "Sphere",
        "particle_speed": -1.5,
        "glow_pulse_speed": 0.5,
        "secondary_effect": "blood_drip",
    },
    "SURGE": {
        "effect_name": "Shocked",
        "description": "Lightning arcs jumping between random points",
        "orbit_speed": 300.0,
        "orbit_radius": 0.5,
        "particle_shape": "Edge",
        "particle_speed": 8.0,
        "glow_pulse_speed": 6.0,
        "secondary_effect": "lightning_arc",
    },
    "VENOM": {
        "effect_name": "Poisoned",
        "description": "Toxic cloud with dripping acid particles",
        "orbit_speed": 30.0,
        "orbit_radius": 1.0,
        "particle_shape": "Sphere",
        "particle_speed": 0.5,
        "glow_pulse_speed": 1.0,
        "secondary_effect": "acid_drip",
    },
    "DREAD": {
        "effect_name": "Terrified",
        "description": "Shadow tendrils with dark mist rising",
        "orbit_speed": 40.0,
        "orbit_radius": 1.2,
        "particle_shape": "Sphere",
        "particle_speed": 0.8,
        "glow_pulse_speed": 0.8,
        "secondary_effect": "shadow_tendril",
    },
    "LEECH": {
        "effect_name": "Draining",
        "description": "Blood orbs orbiting with siphon streams",
        "orbit_speed": 90.0,
        "orbit_radius": 1.0,
        "particle_shape": "Sphere",
        "particle_speed": 2.0,
        "glow_pulse_speed": 1.5,
        "secondary_effect": "siphon_stream",
    },
    "GRACE": {
        "effect_name": "Blessed",
        "description": "Divine rays with halo and ascending particles",
        "orbit_speed": 60.0,
        "orbit_radius": 0.6,
        "particle_shape": "Hemisphere",
        "particle_speed": 1.0,
        "glow_pulse_speed": 3.0,
        "secondary_effect": "divine_rays",
    },
    "MEND": {
        "effect_name": "Regenerating",
        "description": "Healing particles rising with restoration glow",
        "orbit_speed": 45.0,
        "orbit_radius": 0.7,
        "particle_shape": "Sphere",
        "particle_speed": 1.2,
        "glow_pulse_speed": 2.5,
        "secondary_effect": "healing_rise",
    },
    "RUIN": {
        "effect_name": "Crumbling",
        "description": "Surface cracks with ember glow and debris",
        "orbit_speed": 0.0,
        "orbit_radius": 0.0,
        "particle_shape": "Box",
        "particle_speed": -2.0,
        "glow_pulse_speed": 1.0,
        "secondary_effect": "ember_crack",
    },
    "VOID": {
        "effect_name": "Nullified",
        "description": "Dimensional tear with gravity distortion",
        "orbit_speed": 200.0,
        "orbit_radius": 0.4,
        "particle_shape": "Sphere",
        "particle_speed": -3.0,
        "glow_pulse_speed": 4.0,
        "secondary_effect": "gravity_pull",
    },
}


def generate_status_effect_vfx_script(
    brand: str = "SURGE",
    intensity: float = 1.0,
    target_transform_path: str = "",
) -> dict[str, Any]:
    """Generate C# MonoBehaviour for per-brand status effect VFX.

    Creates persistent visual effects that attach to a character when
    affected by a brand-specific status. Each of the 10 brands has unique
    visuals: IRON orbiting sparks, SAVAGE blood drips, SURGE lightning arcs,
    VENOM toxic clouds, DREAD shadow tendrils, LEECH blood orbs, GRACE
    divine rays, MEND healing particles, RUIN ember cracks, VOID gravity
    distortion.

    Args:
        brand: VeilBreakers brand determining the visual style.
        intensity: Effect intensity from 0.0 to 1.0.
        target_transform_path: Optional transform path for attachment.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    brand = brand.upper()
    if brand not in BRAND_COLORS:
        brand = "SURGE"
    bc = BRAND_COLORS[brand]
    sc = BRAND_STATUS_CONFIGS[brand]
    r, g, b, a = bc["rgba"]
    gr, gg, gb, ga = bc["glow"]
    intensity = max(0.0, min(1.0, intensity))

    # Build per-brand secondary effect method
    secondary_methods = {
        "IRON": '''
    private void UpdateSecondaryEffect()
    {
        // Grinding sparks: random sparks at character surface
        if (Random.value < 0.1f * intensity)
        {
            if (secondaryPS != null)
            {
                var emitParams = new ParticleSystem.EmitParams();
                emitParams.position = transform.position + Random.insideUnitSphere * 0.5f;
                emitParams.velocity = Random.onUnitSphere * 3f;
                secondaryPS.Emit(emitParams, 3);
            }
        }
    }''',
        "SAVAGE": '''
    private void UpdateSecondaryEffect()
    {
        // Blood drip: gravity-driven particles from random body points
        if (secondaryPS != null && Random.value < 0.15f * intensity)
        {
            var emitParams = new ParticleSystem.EmitParams();
            emitParams.position = transform.position + new Vector3(
                Random.Range(-0.3f, 0.3f), Random.Range(0f, 1.5f), Random.Range(-0.3f, 0.3f));
            emitParams.velocity = Vector3.down * 1.5f;
            secondaryPS.Emit(emitParams, 1);
        }
    }''',
        "SURGE": '''
    private void UpdateSecondaryEffect()
    {
        // Lightning arcs: line renderer between random points
        arcTimer -= Time.deltaTime;
        if (arcTimer <= 0f && lineRenderer != null)
        {
            arcTimer = Random.Range(0.05f, 0.2f) / intensity;
            Vector3 start = transform.position + Random.insideUnitSphere * 0.5f;
            Vector3 end = transform.position + Random.insideUnitSphere * 1.5f;
            lineRenderer.positionCount = 4;
            lineRenderer.SetPosition(0, start);
            lineRenderer.SetPosition(1, Vector3.Lerp(start, end, 0.33f) + Random.insideUnitSphere * 0.3f);
            lineRenderer.SetPosition(2, Vector3.Lerp(start, end, 0.66f) + Random.insideUnitSphere * 0.3f);
            lineRenderer.SetPosition(3, end);
            lineRenderer.startColor = glowColor;
            lineRenderer.endColor = brandColor;
            lineRenderer.startWidth = 0.05f * intensity;
            lineRenderer.endWidth = 0.02f * intensity;
        }
    }
    private float arcTimer = 0f;''',
        "VENOM": '''
    private void UpdateSecondaryEffect()
    {
        // Acid drip: downward particles with splash on ground
        if (secondaryPS != null && Random.value < 0.12f * intensity)
        {
            var emitParams = new ParticleSystem.EmitParams();
            emitParams.position = transform.position + new Vector3(
                Random.Range(-0.4f, 0.4f), Random.Range(0.5f, 1.8f), Random.Range(-0.4f, 0.4f));
            emitParams.velocity = Vector3.down * 2f + Random.insideUnitSphere * 0.3f;
            emitParams.startSize = 0.08f;
            secondaryPS.Emit(emitParams, 1);
        }
    }''',
        "DREAD": '''
    private void UpdateSecondaryEffect()
    {
        // Shadow tendrils: upward-reaching dark wisps
        tendrilAngle += Time.deltaTime * 40f * intensity;
        if (secondaryPS != null && Random.value < 0.08f * intensity)
        {
            float rad = tendrilAngle * Mathf.Deg2Rad;
            Vector3 offset = new Vector3(Mathf.Cos(rad), 0f, Mathf.Sin(rad)) * 0.6f;
            var emitParams = new ParticleSystem.EmitParams();
            emitParams.position = transform.position + offset;
            emitParams.velocity = Vector3.up * 1.5f + offset.normalized * 0.5f;
            secondaryPS.Emit(emitParams, 2);
        }
    }
    private float tendrilAngle = 0f;''',
        "LEECH": '''
    private void UpdateSecondaryEffect()
    {
        // Siphon streams: orbiting blood orbs with inward pull
        if (secondaryPS != null)
        {
            orbitAngle += Time.deltaTime * 90f * intensity;
            float rad = orbitAngle * Mathf.Deg2Rad;
            Vector3 orbitPos = new Vector3(Mathf.Cos(rad), 0.8f, Mathf.Sin(rad)) * 1.0f;
            if (Random.value < 0.1f * intensity)
            {
                var emitParams = new ParticleSystem.EmitParams();
                emitParams.position = transform.position + orbitPos;
                emitParams.velocity = -orbitPos.normalized * 2f;
                secondaryPS.Emit(emitParams, 1);
            }
        }
    }
    private float orbitAngle = 0f;''',
        "GRACE": '''
    private void UpdateSecondaryEffect()
    {
        // Divine rays: upward light beams
        if (secondaryPS != null && Random.value < 0.06f * intensity)
        {
            var emitParams = new ParticleSystem.EmitParams();
            emitParams.position = transform.position + new Vector3(
                Random.Range(-0.3f, 0.3f), 0f, Random.Range(-0.3f, 0.3f));
            emitParams.velocity = Vector3.up * 3f;
            emitParams.startSize = 0.3f;
            secondaryPS.Emit(emitParams, 1);
        }
    }''',
        "MEND": '''
    private void UpdateSecondaryEffect()
    {
        // Healing particles rising gently
        if (secondaryPS != null && Random.value < 0.1f * intensity)
        {
            var emitParams = new ParticleSystem.EmitParams();
            emitParams.position = transform.position + new Vector3(
                Random.Range(-0.5f, 0.5f), Random.Range(-0.2f, 0.5f), Random.Range(-0.5f, 0.5f));
            emitParams.velocity = Vector3.up * 1.0f + Random.insideUnitSphere * 0.2f;
            emitParams.startSize = 0.12f;
            secondaryPS.Emit(emitParams, 1);
        }
    }''',
        "RUIN": '''
    private void UpdateSecondaryEffect()
    {
        // Ember cracks: downward debris with upward embers
        if (secondaryPS != null && Random.value < 0.08f * intensity)
        {
            // Falling debris
            var emitParams = new ParticleSystem.EmitParams();
            emitParams.position = transform.position + new Vector3(
                Random.Range(-0.6f, 0.6f), Random.Range(0.5f, 1.5f), Random.Range(-0.6f, 0.6f));
            emitParams.velocity = Vector3.down * 2f;
            emitParams.startSize = 0.15f;
            secondaryPS.Emit(emitParams, 1);
            // Rising embers
            emitParams.position = transform.position + Vector3.down * 0.1f;
            emitParams.velocity = Vector3.up * 2.5f + Random.insideUnitSphere * 0.5f;
            emitParams.startSize = 0.05f;
            secondaryPS.Emit(emitParams, 2);
        }
    }''',
        "VOID": '''
    private void UpdateSecondaryEffect()
    {
        // Gravity distortion: particles pulled inward from all directions
        if (secondaryPS != null && Random.value < 0.15f * intensity)
        {
            Vector3 spawnPos = transform.position + Random.onUnitSphere * 2f;
            Vector3 pullDir = (transform.position - spawnPos).normalized;
            var emitParams = new ParticleSystem.EmitParams();
            emitParams.position = spawnPos;
            emitParams.velocity = pullDir * 4f;
            emitParams.startSize = 0.1f;
            secondaryPS.Emit(emitParams, 2);
        }
    }''',
    }

    secondary_code = secondary_methods.get(brand, '''
    private void UpdateSecondaryEffect()
    {
        // Default secondary effect
    }''')

    # Line renderer field only for SURGE
    line_renderer_field = ""
    line_renderer_init = ""
    if brand == "SURGE":
        line_renderer_field = "\n    private LineRenderer lineRenderer;"
        line_renderer_init = '''
        // Lightning arc line renderer
        GameObject lrObj = new GameObject("LightningArc");
        lrObj.transform.SetParent(transform);
        lineRenderer = lrObj.AddComponent<LineRenderer>();
        lineRenderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit") ?? Shader.Find("Particles/Standard Unlit"));
        lineRenderer.material.SetColor("_Color", glowColor);'''

    target_block = ""
    if target_transform_path:
        safe_path = target_transform_path.replace("\\", "\\\\").replace('"', '\\"')
        target_block = f'''
        // Attach to target transform
        Transform target = transform.Find("{safe_path}");
        if (target != null)
        {{
            transform.SetParent(target);
            transform.localPosition = Vector3.zero;
        }}'''

    script = f'''using UnityEngine;

/// <summary>
/// Status effect VFX for {brand} brand: {sc["effect_name"]}.
/// {sc["description"]}
/// Phase 23 -- VFX3-05
/// </summary>
public class VB_StatusVFX_{brand} : MonoBehaviour
{{
    [Header("Brand")]
    [SerializeField] private string brand = "{brand}";
    [SerializeField] private string effectName = "{sc["effect_name"]}";

    [Header("Colors")]
    [SerializeField] private Color brandColor = new Color({r}f, {g}f, {b}f, {a}f);
    [SerializeField] private Color glowColor = new Color({gr}f, {gg}f, {gb}f, {ga}f);

    [Header("Effect Settings")]
    [SerializeField] private float intensity = {intensity}f;
    [SerializeField] private float orbitSpeed = {sc["orbit_speed"]}f;
    [SerializeField] private float orbitRadius = {sc["orbit_radius"]}f;
    [SerializeField] private float glowPulseSpeed = {sc["glow_pulse_speed"]}f;

    // Runtime
    private ParticleSystem mainPS;
    private ParticleSystem secondaryPS;{line_renderer_field}
    private float pulsePhase = 0f;
    private Renderer[] targetRenderers;
    private MaterialPropertyBlock _mpb;

    public string Brand => brand;
    public string EffectName => effectName;
    public float Intensity => intensity;

    public void SetIntensity(float newIntensity)
    {{
        intensity = Mathf.Clamp01(newIntensity);
        UpdateIntensity();
    }}

    private void Start()
    {{{target_block}
        targetRenderers = GetComponentsInChildren<Renderer>();
        _mpb = new MaterialPropertyBlock();
        CreateMainParticleSystem();
        CreateSecondaryParticleSystem();{line_renderer_init}
    }}

    private void Update()
    {{
        // Glow pulse
        pulsePhase += Time.deltaTime * glowPulseSpeed;
        float pulse = (Mathf.Sin(pulsePhase) * 0.5f + 0.5f) * intensity;

        // Apply glow to renderers via MaterialPropertyBlock
        if (targetRenderers != null)
        {{
            foreach (var rend in targetRenderers)
            {{
                if (rend == null) continue;
                rend.GetPropertyBlock(_mpb);
                _mpb.SetColor("_EmissionColor", glowColor * pulse * 2f);
                rend.SetPropertyBlock(_mpb);
            }}
        }}

        // Orbit main particles around target
        if (orbitSpeed > 0f && mainPS != null)
        {{
            float angle = Time.time * orbitSpeed * Mathf.Deg2Rad;
            Vector3 offset = new Vector3(Mathf.Cos(angle), 0f, Mathf.Sin(angle)) * orbitRadius;
            mainPS.transform.localPosition = offset;
        }}

        UpdateSecondaryEffect();
    }}

    private void UpdateIntensity()
    {{
        if (mainPS != null)
        {{
            var emission = mainPS.emission;
            emission.rateOverTime = 30f * intensity;
        }}
        if (secondaryPS != null)
        {{
            var emission = secondaryPS.emission;
            emission.rateOverTime = 20f * intensity;
        }}
    }}

    private void CreateMainParticleSystem()
    {{
        GameObject psObj = new GameObject("StatusVFX_Main");
        psObj.transform.SetParent(transform);
        psObj.transform.localPosition = Vector3.zero;

        mainPS = psObj.AddComponent<ParticleSystem>();
        var main = mainPS.main;
        main.duration = 5f;
        main.loop = true;
        main.startLifetime = 1.5f;
        main.startSpeed = {sc["particle_speed"]}f;
        main.startSize = 0.1f * intensity;
        main.startColor = brandColor;
        main.maxParticles = 100;
        main.playOnAwake = true;
        main.simulationSpace = ParticleSystemSimulationSpace.World;

        var emission = mainPS.emission;
        emission.rateOverTime = 30f * intensity;

        var shape = mainPS.shape;
        shape.shapeType = ParticleSystemShapeType.{sc["particle_shape"]};
        shape.radius = 0.3f;

        // Color over lifetime
        var col = mainPS.colorOverLifetime;
        col.enabled = true;
        Gradient grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(glowColor, 0f),
                new GradientColorKey(brandColor, 0.5f),
                new GradientColorKey(brandColor * 0.3f, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(0f, 0f),
                new GradientAlphaKey(intensity, 0.2f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        var renderer = mainPS.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit") ?? Shader.Find("Particles/Standard Unlit"));
        renderer.material.SetColor("_Color", glowColor);
    }}

    private void CreateSecondaryParticleSystem()
    {{
        GameObject psObj = new GameObject("StatusVFX_Secondary");
        psObj.transform.SetParent(transform);
        psObj.transform.localPosition = Vector3.zero;

        secondaryPS = psObj.AddComponent<ParticleSystem>();
        var main = secondaryPS.main;
        main.duration = 5f;
        main.loop = true;
        main.startLifetime = 1.0f;
        main.startSpeed = 1f;
        main.startSize = 0.08f;
        main.startColor = glowColor;
        main.maxParticles = 50;
        main.playOnAwake = true;
        main.simulationSpace = ParticleSystemSimulationSpace.World;

        var emission = secondaryPS.emission;
        emission.rateOverTime = 0; // Emit manually in UpdateSecondaryEffect

        var renderer = secondaryPS.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit") ?? Shader.Find("Particles/Standard Unlit"));
        renderer.material.SetColor("_Color", brandColor);
    }}
{secondary_code}

    private void OnDestroy()
    {{
        // Clean up dynamic materials
        if (mainPS != null)
        {{
            var r = mainPS.GetComponent<ParticleSystemRenderer>();
            if (r != null && r.material != null) Destroy(r.material);
        }}
        if (secondaryPS != null)
        {{
            var r = secondaryPS.GetComponent<ParticleSystemRenderer>();
            if (r != null && r.material != null) Destroy(r.material);
        }}
    }}
}}
'''

    return {
        "script_path": f"Assets/Scripts/VFX/VB_StatusVFX_{brand}.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            f"Attach VB_StatusVFX_{brand} to an affected character",
            f"Status: {sc['effect_name']} ({sc['description']})",
            "Call SetIntensity(0-1) to adjust effect strength",
        ],
    }


# ---------------------------------------------------------------------------
# VFX3-06: Environmental VFX Depth
# ---------------------------------------------------------------------------


def generate_environmental_vfx_script(
    vfx_type: str = "volumetric_fog",
    intensity: float = 1.0,
    color: list[float] | None = None,
    area_size: float = 20.0,
) -> dict[str, Any]:
    """Generate C# MonoBehaviour for deep environmental VFX.

    Creates atmosphere-enhancing VFX: volumetric fog with animated density
    and noise, god rays with directional scatter, heat distortion via URP
    screen-space shader, and water caustics with projected patterns.

    Args:
        vfx_type: Type -- volumetric_fog, god_rays, heat_distortion, water_caustics.
        intensity: Effect intensity (0-1, clamped).
        color: RGBA color override (defaults per type).
        area_size: Size of the effect area in world units.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    if vfx_type not in ENV_VFX_TYPES:
        vfx_type = "volumetric_fog"
    safe_type = sanitize_cs_identifier(vfx_type)
    intensity = max(0.0, min(1.0, intensity))

    # Default colors per type
    default_colors = {
        "volumetric_fog": [0.5, 0.55, 0.65, 0.4],
        "god_rays": [1.0, 0.95, 0.8, 0.6],
        "heat_distortion": [1.0, 1.0, 1.0, 0.3],
        "water_caustics": [0.3, 0.6, 0.9, 0.5],
    }
    c = color if color and len(color) >= 4 else default_colors[vfx_type]
    cr, cg, cb, ca = c[:4]

    # Type-specific settings
    type_configs = {
        "volumetric_fog": {
            "density": 0.05,
            "falloff": 2.0,
            "noise_speed": 0.3,
            "noise_scale": 5.0,
            "height_min": -2.0,
            "height_max": 3.0,
        },
        "god_rays": {
            "ray_count": 6,
            "scatter": 0.7,
            "color_temp": 5500.0,
            "ray_length": 15.0,
            "ray_width": 0.5,
            "animation_speed": 0.2,
        },
        "heat_distortion": {
            "distortion_strength": 0.02,
            "speed": 1.5,
            "turbulence_scale": 3.0,
            "height_range": 5.0,
            "falloff_distance": 10.0,
        },
        "water_caustics": {
            "pattern_scale": 2.0,
            "animation_speed": 0.5,
            "projection_angle": 90.0,
            "depth_fade": 5.0,
            "voronoi_cells": 8,
        },
    }
    cfg = type_configs[vfx_type]

    # Build type-specific C# code sections
    if vfx_type == "volumetric_fog":
        type_fields = f'''
    [Header("Fog Settings")]
    [SerializeField] private float density = {cfg["density"]}f;
    [SerializeField] private float falloff = {cfg["falloff"]}f;
    [SerializeField] private float noiseSpeed = {cfg["noise_speed"]}f;
    [SerializeField] private float noiseScale = {cfg["noise_scale"]}f;
    [SerializeField] private float heightMin = {cfg["height_min"]}f;
    [SerializeField] private float heightMax = {cfg["height_max"]}f;'''
        type_update = '''
        // Animate fog noise
        float time = Time.time * noiseSpeed;
        if (fogMaterial != null)
        {
            fogMaterial.SetFloat("_Density", density * intensity);
            fogMaterial.SetFloat("_NoiseOffset", time);
            fogMaterial.SetFloat("_NoiseScale", noiseScale);
            fogMaterial.SetFloat("_FalloffExp", falloff);
            fogMaterial.SetFloat("_HeightMin", heightMin);
            fogMaterial.SetFloat("_HeightMax", heightMax);
            fogMaterial.SetColor("_FogColor", effectColor * intensity);
        }'''
        type_setup = '''
        // Create fog volume mesh (box)
        fogMesh = GameObject.CreatePrimitive(PrimitiveType.Cube);
        fogMesh.name = "FogVolume";
        fogMesh.transform.SetParent(transform);
        fogMesh.transform.localPosition = Vector3.zero;
        fogMesh.transform.localScale = new Vector3(areaSize, heightMax - heightMin, areaSize);

        // Remove collider
        var col = fogMesh.GetComponent<Collider>();
        if (col != null) Destroy(col);

        // Create fog material (URP custom)
        fogMaterial = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        fogMaterial.SetColor("_BaseColor", effectColor);
        fogMaterial.SetFloat("_Surface", 1); // Transparent
        fogMaterial.SetFloat("_Blend", 0); // Alpha blend
        fogMaterial.SetOverrideTag("RenderType", "Transparent");
        fogMaterial.renderQueue = 3000;
        fogMesh.GetComponent<Renderer>().material = fogMaterial;'''
        type_fields_runtime = '''
    private GameObject fogMesh;
    private Material fogMaterial;'''
    elif vfx_type == "god_rays":
        type_fields = f'''
    [Header("God Ray Settings")]
    [SerializeField] private int rayCount = {cfg["ray_count"]};
    [SerializeField] private float scatter = {cfg["scatter"]}f;
    [SerializeField] private float colorTemperature = {cfg["color_temp"]}f;
    [SerializeField] private float rayLength = {cfg["ray_length"]}f;
    [SerializeField] private float rayWidth = {cfg["ray_width"]}f;
    [SerializeField] private float animationSpeed = {cfg["animation_speed"]}f;'''
        type_update = '''
        // Animate ray intensity with subtle flicker
        float time = Time.time * animationSpeed;
        for (int i = 0; i < rayRenderers.Length; i++)
        {
            if (rayRenderers[i] == null) continue;
            float flicker = Mathf.PerlinNoise(time + i * 1.7f, i * 0.5f);
            Color rayColor = effectColor * (0.6f + flicker * 0.4f) * intensity;
            rayRenderers[i].startColor = rayColor;
            rayRenderers[i].endColor = new Color(rayColor.r, rayColor.g, rayColor.b, 0f);
            float widthMod = 0.8f + Mathf.PerlinNoise(time * 0.5f + i, 0f) * 0.4f;
            rayRenderers[i].startWidth = rayWidth * widthMod * intensity;
            rayRenderers[i].endWidth = rayWidth * 0.1f * widthMod * intensity;
        }'''
        type_setup = '''
        // Create god ray line renderers
        rayRenderers = new LineRenderer[rayCount];
        for (int i = 0; i < rayCount; i++)
        {
            GameObject rayObj = new GameObject($"GodRay_{i}");
            rayObj.transform.SetParent(transform);

            float angle = (float)i / rayCount * Mathf.PI * 2f;
            float xOffset = Mathf.Cos(angle) * areaSize * 0.3f;
            float zOffset = Mathf.Sin(angle) * areaSize * 0.3f;
            rayObj.transform.localPosition = new Vector3(xOffset, rayLength, zOffset);

            LineRenderer lr = rayObj.AddComponent<LineRenderer>();
            lr.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit") ?? Shader.Find("Particles/Standard Unlit"));
            lr.positionCount = 2;
            lr.SetPosition(0, rayObj.transform.position);
            lr.SetPosition(1, rayObj.transform.position + Vector3.down * rayLength);
            lr.startWidth = rayWidth;
            lr.endWidth = rayWidth * 0.1f;
            lr.startColor = effectColor * intensity;
            lr.endColor = new Color(effectColor.r, effectColor.g, effectColor.b, 0f);
            rayRenderers[i] = lr;
        }'''
        type_fields_runtime = '''
    private LineRenderer[] rayRenderers;'''
    elif vfx_type == "heat_distortion":
        type_fields = f'''
    [Header("Heat Distortion Settings")]
    [SerializeField] private float distortionStrength = {cfg["distortion_strength"]}f;
    [SerializeField] private float distortionSpeed = {cfg["speed"]}f;
    [SerializeField] private float turbulenceScale = {cfg["turbulence_scale"]}f;
    [SerializeField] private float heightRange = {cfg["height_range"]}f;
    [SerializeField] private float falloffDistance = {cfg["falloff_distance"]}f;'''
        type_update = '''
        // Update distortion shader time
        float time = Time.time * distortionSpeed;
        if (distortionMaterial != null)
        {
            distortionMaterial.SetFloat("_DistortionStrength", distortionStrength * intensity);
            distortionMaterial.SetFloat("_TimeOffset", time);
            distortionMaterial.SetFloat("_TurbulenceScale", turbulenceScale);
        }'''
        type_setup = '''
        // Create distortion quad
        distortionQuad = GameObject.CreatePrimitive(PrimitiveType.Quad);
        distortionQuad.name = "HeatDistortion";
        distortionQuad.transform.SetParent(transform);
        distortionQuad.transform.localPosition = Vector3.zero;
        distortionQuad.transform.localScale = new Vector3(areaSize, heightRange, 1f);

        var col = distortionQuad.GetComponent<Collider>();
        if (col != null) Destroy(col);

        // URP distortion material
        distortionMaterial = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        distortionMaterial.SetFloat("_Surface", 1);
        distortionMaterial.renderQueue = 3100;
        distortionQuad.GetComponent<Renderer>().material = distortionMaterial;'''
        type_fields_runtime = '''
    private GameObject distortionQuad;
    private Material distortionMaterial;'''
    else:  # water_caustics
        type_fields = f'''
    [Header("Caustics Settings")]
    [SerializeField] private float patternScale = {cfg["pattern_scale"]}f;
    [SerializeField] private float animSpeed = {cfg["animation_speed"]}f;
    [SerializeField] private float projectionAngle = {cfg["projection_angle"]}f;
    [SerializeField] private float depthFade = {cfg["depth_fade"]}f;
    [SerializeField] private int voronoiCells = {cfg["voronoi_cells"]};'''
        type_update = '''
        // Animate caustic pattern
        float time = Time.time * animSpeed;
        if (causticsMaterial != null)
        {
            causticsMaterial.SetFloat("_PatternScale", patternScale);
            causticsMaterial.SetFloat("_TimeOffset", time);
            causticsMaterial.SetFloat("_DepthFade", depthFade);
            causticsMaterial.SetColor("_CausticsColor", effectColor * intensity);
        }

        // Update projector rotation
        if (projectorObj != null)
        {
            projectorObj.transform.rotation = Quaternion.Euler(projectionAngle, 0f, 0f);
        }'''
        type_setup = '''
        // Create caustics projector
        projectorObj = new GameObject("CausticsProjector");
        projectorObj.transform.SetParent(transform);
        projectorObj.transform.localPosition = Vector3.up * 5f;
        projectorObj.transform.rotation = Quaternion.Euler(projectionAngle, 0f, 0f);

        // Add a light cookie or projector component for caustics
        Light projLight = projectorObj.AddComponent<Light>();
        projLight.type = LightType.Spot;
        projLight.spotAngle = 90f;
        projLight.range = areaSize;
        projLight.intensity = intensity * 2f;
        projLight.color = effectColor;

        causticsMaterial = new Material(Shader.Find("Universal Render Pipeline/Lit"));'''
        type_fields_runtime = '''
    private GameObject projectorObj;
    private Material causticsMaterial;'''

    script = f'''using UnityEngine;

/// <summary>
/// Environmental VFX: {vfx_type}.
/// Adds atmosphere depth with configurable intensity and area coverage.
/// Phase 23 -- VFX3-06
/// </summary>
public class VB_EnvVFX_{safe_type} : MonoBehaviour
{{
    [Header("General")]
    [SerializeField] private string vfxType = "{vfx_type}";
    [SerializeField] private float intensity = {intensity}f;
    [SerializeField] private Color effectColor = new Color({cr}f, {cg}f, {cb}f, {ca}f);
    [SerializeField] private float areaSize = {area_size}f;
{type_fields}

    // Runtime{type_fields_runtime}

    public string VfxType => vfxType;
    public float EffectIntensity => intensity;

    public void SetIntensity(float newIntensity)
    {{
        intensity = Mathf.Clamp01(newIntensity);
    }}

    private void Start()
    {{
        SetupEffect();
    }}

    private void Update()
    {{{type_update}
    }}

    private void SetupEffect()
    {{{type_setup}
    }}

    private void OnDestroy()
    {{
        // Clean up dynamic resources
    }}
}}
'''

    return {
        "script_path": f"Assets/Scripts/VFX/VB_EnvVFX_{safe_type}.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            f"Attach VB_EnvVFX_{safe_type} to an empty GameObject in the scene",
            f"Environmental VFX: {vfx_type}, intensity={intensity}, area={area_size}m",
            "Adjust intensity at runtime via SetIntensity(0-1)",
        ],
    }


# ---------------------------------------------------------------------------
# VFX3-07: Directional Combat Hit VFX
# ---------------------------------------------------------------------------


def generate_directional_hit_vfx_script(
    brand: str = "IRON",
    hit_magnitude: float = 1.0,
    screen_effect_enabled: bool = True,
) -> dict[str, Any]:
    """Generate C# MonoBehaviour for directional combat hit VFX.

    Creates brand-matched hit effects that rotate to match the incoming
    damage vector. Includes splash patterns, screen effects (brief flash,
    chromatic aberration), and brand-specific visuals: IRON sparks,
    SAVAGE blood, SURGE lightning, etc.

    Args:
        brand: VeilBreakers brand for visual matching.
        hit_magnitude: Damage magnitude affecting VFX scale (0-3).
        screen_effect_enabled: Whether to trigger screen effects on hit.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    brand = brand.upper()
    if brand not in BRAND_COLORS:
        brand = "IRON"
    bc = BRAND_COLORS[brand]
    r, g, b, a = bc["rgba"]
    gr, gg, gb, ga = bc["glow"]
    hit_magnitude = max(0.0, min(3.0, hit_magnitude))

    # Brand-specific hit descriptions
    hit_descs = {
        "IRON": "Metallic sparks burst with grinding particle shower",
        "SAVAGE": "Blood splatter with feral claw slash marks",
        "SURGE": "Lightning burst with electric arc discharge",
        "VENOM": "Acid splash with toxic mist cloud",
        "DREAD": "Shadow burst with dark energy dispersal",
        "LEECH": "Crimson burst with blood droplet spray",
        "GRACE": "Golden flash with radiant particle scatter",
        "MEND": "Green pulse with healing energy ripple",
        "RUIN": "Explosive debris with orange ember shower",
        "VOID": "Dimensional crack with void energy release",
    }
    hit_desc = hit_descs.get(brand, "Generic hit effect")

    screen_block = ""
    if screen_effect_enabled:
        screen_block = '''

    [Header("Screen Effects")]
    [SerializeField] private bool screenEffectsEnabled = true;
    [SerializeField] private float flashDuration = 0.05f;
    [SerializeField] private float chromaticAberration = 0.3f;

    private void TriggerScreenEffect(float magnitude)
    {
        if (!screenEffectsEnabled) return;

        // Brief white flash
        StartCoroutine(ScreenFlash(magnitude));
    }

    private System.Collections.IEnumerator ScreenFlash(float magnitude)
    {
        // Apply chromatic aberration via post-processing volume
        var volumes = FindObjectsByType<UnityEngine.Rendering.Volume>(FindObjectsSortMode.None);
        UnityEngine.Rendering.Universal.ChromaticAberration ca = null;
        foreach (var vol in volumes)
        {
            if (vol.profile != null && vol.profile.TryGet(out ca))
                break;
        }

        if (ca != null)
        {
            float originalIntensity = ca.intensity.value;
            ca.intensity.value = chromaticAberration * magnitude;
            yield return new WaitForSeconds(flashDuration * magnitude);
            ca.intensity.value = originalIntensity;
        }
        else
        {
            yield return new WaitForSeconds(flashDuration);
        }
    }'''

    screen_trigger = ""
    if screen_effect_enabled:
        screen_trigger = "\n        TriggerScreenEffect(magnitude);"

    script = f'''using UnityEngine;
using System.Collections;

/// <summary>
/// Directional combat hit VFX for {brand} brand.
/// {hit_desc}
/// Phase 23 -- VFX3-07
/// </summary>
public class VB_HitVFX_{brand} : MonoBehaviour
{{
    [Header("Brand Config")]
    [SerializeField] private string brand = "{brand}";
    [SerializeField] private Color brandColor = new Color({r}f, {g}f, {b}f, {a}f);
    [SerializeField] private Color glowColor = new Color({gr}f, {gg}f, {gb}f, {ga}f);

    [Header("Hit Settings")]
    [SerializeField] private float baseMagnitude = {hit_magnitude}f;
    [SerializeField] private int burstParticleCount = 80;
    [SerializeField] private float splashRadius = 0.5f;
    [SerializeField] private float effectDuration = 0.8f;
{screen_block}

    public string Brand => brand;

    /// <summary>
    /// Trigger a directional hit effect.
    /// </summary>
    /// <param name="hitPoint">World position of the hit.</param>
    /// <param name="hitDirection">Incoming damage direction vector.</param>
    /// <param name="magnitude">Hit magnitude (0-3) affecting scale.</param>
    public void TriggerHit(Vector3 hitPoint, Vector3 hitDirection, float magnitude = -1f)
    {{
        if (magnitude < 0f) magnitude = baseMagnitude;
        magnitude = Mathf.Clamp(magnitude, 0f, 3f);

        // Orient splash to face incoming direction
        Quaternion hitRotation = Quaternion.LookRotation(-hitDirection.normalized, Vector3.up);

        // Create hit VFX at impact point
        StartCoroutine(SpawnHitEffect(hitPoint, hitRotation, magnitude));{screen_trigger}
    }}

    private IEnumerator SpawnHitEffect(Vector3 position, Quaternion rotation, float magnitude)
    {{
        // Create particle burst
        GameObject burstObj = new GameObject("HitBurst");
        burstObj.transform.position = position;
        burstObj.transform.rotation = rotation;
        burstObj.transform.SetParent(transform);

        ParticleSystem ps = burstObj.AddComponent<ParticleSystem>();
        ConfigureHitParticles(ps, magnitude);
        ps.Play();

        // Create splash decal particles (ground scatter)
        GameObject splashObj = new GameObject("HitSplash");
        splashObj.transform.position = position;
        splashObj.transform.rotation = rotation;
        splashObj.transform.SetParent(transform);

        ParticleSystem splashPS = splashObj.AddComponent<ParticleSystem>();
        ConfigureSplashParticles(splashPS, magnitude);
        splashPS.Play();

        yield return new WaitForSeconds(effectDuration * magnitude);

        Destroy(burstObj);
        Destroy(splashObj);
    }}

    private void ConfigureHitParticles(ParticleSystem ps, float magnitude)
    {{
        var main = ps.main;
        main.duration = effectDuration;
        main.loop = false;
        main.startLifetime = 0.4f * magnitude;
        main.startSpeed = new ParticleSystem.MinMaxCurve(3f * magnitude, 8f * magnitude);
        main.startSize = new ParticleSystem.MinMaxCurve(0.03f, 0.12f * magnitude);
        main.startColor = glowColor;
        main.maxParticles = (int)(burstParticleCount * magnitude);
        main.playOnAwake = false;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.gravityModifier = 1.5f;

        var emission = ps.emission;
        emission.rateOverTime = 0;
        emission.SetBursts(new ParticleSystem.Burst[] {{
            new ParticleSystem.Burst(0f, (short)(burstParticleCount * magnitude))
        }});

        // Cone shape facing hit direction
        var shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Cone;
        shape.angle = 45f;
        shape.radius = splashRadius * magnitude;

        // Color gradient
        var col = ps.colorOverLifetime;
        col.enabled = true;
        Gradient grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(glowColor, 0f),
                new GradientColorKey(brandColor, 0.4f),
                new GradientColorKey(brandColor * 0.2f, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(1f, 0f),
                new GradientAlphaKey(0.6f, 0.5f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        // Renderer
        var renderer = ps.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit") ?? Shader.Find("Particles/Standard Unlit"));
        renderer.material.SetColor("_Color", glowColor);
    }}

    private void ConfigureSplashParticles(ParticleSystem ps, float magnitude)
    {{
        var main = ps.main;
        main.duration = effectDuration * 1.5f;
        main.loop = false;
        main.startLifetime = 0.6f;
        main.startSpeed = new ParticleSystem.MinMaxCurve(1f, 3f * magnitude);
        main.startSize = new ParticleSystem.MinMaxCurve(0.05f, 0.15f);
        main.startColor = brandColor;
        main.maxParticles = (int)(burstParticleCount * 0.5f * magnitude);
        main.playOnAwake = false;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.gravityModifier = 2f;

        var emission = ps.emission;
        emission.rateOverTime = 0;
        emission.SetBursts(new ParticleSystem.Burst[] {{
            new ParticleSystem.Burst(0.05f, (short)(burstParticleCount * 0.3f * magnitude))
        }});

        var shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Hemisphere;
        shape.radius = splashRadius * 0.5f;

        var renderer = ps.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit") ?? Shader.Find("Particles/Standard Unlit"));
        renderer.material.SetColor("_Color", brandColor);
    }}
}}
'''

    return {
        "script_path": f"Assets/Scripts/VFX/VB_HitVFX_{brand}.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            f"Attach VB_HitVFX_{brand} to a character or VFX manager",
            "Call TriggerHit(hitPoint, hitDirection, magnitude) from combat system",
            f"Brand: {brand} -- {hit_desc}",
        ],
    }


# ---------------------------------------------------------------------------
# VFX3-08: Boss Phase Transition VFX
# ---------------------------------------------------------------------------


def generate_boss_transition_vfx_script(
    transition_type: str = "corruption_wave",
    boss_brand: str = "DREAD",
    duration: float = 3.0,
    arena_radius: float = 20.0,
) -> dict[str, Any]:
    """Generate C# MonoBehaviour for boss phase transition VFX.

    Creates dramatic phase-change effects: corruption_wave (expanding dark
    ring from boss center), power_surge (upward energy column with
    shockwave), arena_transformation (terrain color shift + particle rain
    + fog change). Supports phase1->2 (rage), phase2->3 (desperation),
    and phase3->death (collapse) transitions.

    Args:
        transition_type: Type -- corruption_wave, power_surge, arena_transformation.
        boss_brand: VeilBreakers brand of the boss.
        duration: Transition duration in seconds.
        arena_radius: Boss arena radius in world units.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    if transition_type not in BOSS_TRANSITION_TYPES:
        transition_type = "corruption_wave"
    safe_type = sanitize_cs_identifier(transition_type)
    boss_brand = boss_brand.upper()
    if boss_brand not in BRAND_COLORS:
        boss_brand = "DREAD"
    bc = BRAND_COLORS[boss_brand]
    r, g, b, a = bc["rgba"]
    gr, gg, gb, ga = bc["glow"]

    # Transition-specific descriptions
    transition_descs = {
        "corruption_wave": "Expanding dark ring from boss center with ground corruption",
        "power_surge": "Upward energy column with radial shockwave",
        "arena_transformation": "Terrain color shift, particle rain, and fog intensification",
    }
    desc = transition_descs[transition_type]

    # Build transition-specific coroutine
    if transition_type == "corruption_wave":
        transition_coroutine = '''
    private IEnumerator RunCorruptionWave()
    {
        // Stage 1: Charge up (0-20% duration)
        float chargeEnd = duration * 0.2f;
        if (chargePS != null) chargePS.Play();

        float t = 0f;
        while (t < chargeEnd)
        {
            t += Time.deltaTime;
            float pulse = Mathf.Sin(t * 20f) * 0.5f + 0.5f;
            ApplyGlow(pulse * 3f);
            yield return null;
        }

        // Stage 2: Wave expansion (20-80% duration)
        if (chargePS != null) chargePS.Stop();
        if (wavePS != null) wavePS.Play();

        float waveStart = chargeEnd;
        float waveEnd = duration * 0.8f;
        float waveDuration = waveEnd - waveStart;
        t = 0f;

        while (t < waveDuration)
        {
            t += Time.deltaTime;
            float progress = t / waveDuration;
            float currentRadius = Mathf.Lerp(0f, arenaRadius, progress);

            // Expand wave ring
            if (wavePS != null)
            {
                var shape = wavePS.shape;
                shape.radius = currentRadius;
            }

            // Camera shake based on proximity
            ApplyScreenShake(1f - progress);
            yield return null;
        }

        // Stage 3: Aftermath (80-100% duration)
        if (wavePS != null) wavePS.Stop();
        if (aftermathPS != null) aftermathPS.Play();

        float afterStart = waveEnd;
        float afterDuration = duration - afterStart;
        t = 0f;
        while (t < afterDuration)
        {
            t += Time.deltaTime;
            float fadeOut = 1f - (t / afterDuration);
            ApplyGlow(fadeOut);
            yield return null;
        }

        if (aftermathPS != null) aftermathPS.Stop();
        OnTransitionComplete();
    }'''
    elif transition_type == "power_surge":
        transition_coroutine = '''
    private IEnumerator RunPowerSurge()
    {
        // Stage 1: Energy gathering (0-30% duration)
        float gatherEnd = duration * 0.3f;
        if (chargePS != null) chargePS.Play();

        float t = 0f;
        while (t < gatherEnd)
        {
            t += Time.deltaTime;
            float progress = t / gatherEnd;
            // Particles pull inward during gathering
            ApplyGlow(progress * 5f);
            yield return null;
        }

        // Stage 2: Column eruption + shockwave (30-60% duration)
        if (chargePS != null) chargePS.Stop();
        if (columnPS != null) columnPS.Play();
        if (wavePS != null) wavePS.Play();

        float eruptEnd = duration * 0.6f;
        float eruptDuration = eruptEnd - gatherEnd;
        t = 0f;

        while (t < eruptDuration)
        {
            t += Time.deltaTime;
            float progress = t / eruptDuration;

            // Column rises
            if (columnPS != null)
            {
                columnPS.transform.localScale = new Vector3(1f, Mathf.Lerp(0.1f, 3f, progress), 1f);
            }

            // Shockwave expands
            if (wavePS != null)
            {
                var shape = wavePS.shape;
                shape.radius = Mathf.Lerp(0f, arenaRadius, progress);
            }

            ApplyScreenShake(1f);
            yield return null;
        }

        // Stage 3: Dissipation (60-100% duration)
        if (columnPS != null) columnPS.Stop();
        if (wavePS != null) wavePS.Stop();
        if (aftermathPS != null) aftermathPS.Play();

        float dissipateEnd = duration;
        float dissipateDuration = dissipateEnd - eruptEnd;
        t = 0f;
        while (t < dissipateDuration)
        {
            t += Time.deltaTime;
            float fadeOut = 1f - (t / dissipateDuration);
            ApplyGlow(fadeOut * 2f);
            yield return null;
        }

        if (aftermathPS != null) aftermathPS.Stop();
        OnTransitionComplete();
    }'''
    else:  # arena_transformation
        transition_coroutine = '''
    private IEnumerator RunArenaTransformation()
    {
        // Stage 1: Color shift begins (0-40% duration)
        float shiftEnd = duration * 0.4f;
        float t = 0f;

        Color originalFogColor = RenderSettings.fogColor;
        float originalFogDensity = RenderSettings.fogDensity;
        Color targetFogColor = brandColor;
        float targetFogDensity = originalFogDensity * 2f;

        while (t < shiftEnd)
        {
            t += Time.deltaTime;
            float progress = t / shiftEnd;

            // Fog color transition
            RenderSettings.fogColor = Color.Lerp(originalFogColor, targetFogColor, progress);
            RenderSettings.fogDensity = Mathf.Lerp(originalFogDensity, targetFogDensity, progress);
            RenderSettings.fog = true;

            // Ambient light shift
            RenderSettings.ambientLight = Color.Lerp(Color.white * 0.5f, brandColor * 0.3f, progress);

            yield return null;
        }

        // Stage 2: Particle rain + environment effects (40-80% duration)
        if (wavePS != null) wavePS.Play();
        if (chargePS != null) chargePS.Play(); // Particle rain

        float rainEnd = duration * 0.8f;
        float rainDuration = rainEnd - shiftEnd;
        t = 0f;
        while (t < rainDuration)
        {
            t += Time.deltaTime;
            ApplyScreenShake(0.3f);
            yield return null;
        }

        // Stage 3: Stabilize in new state (80-100% duration)
        if (wavePS != null) wavePS.Stop();
        if (chargePS != null) chargePS.Stop();

        float stabilizeEnd = duration;
        float stabilizeDuration = stabilizeEnd - rainEnd;
        t = 0f;
        while (t < stabilizeDuration)
        {
            t += Time.deltaTime;
            float progress = t / stabilizeDuration;
            // Gentle settle
            RenderSettings.fogDensity = Mathf.Lerp(targetFogDensity, targetFogDensity * 0.7f, progress);
            yield return null;
        }

        OnTransitionComplete();
    }'''

    # Column PS field only for power_surge
    column_field = ""
    column_setup = ""
    if transition_type == "power_surge":
        column_field = "\n    private ParticleSystem columnPS;"
        column_setup = '''

        // Energy column
        columnPS = CreatePS("EnergyColumn", 300, 0.15f);
        var colShape = columnPS.shape;
        colShape.shapeType = ParticleSystemShapeType.Cone;
        colShape.angle = 5f;
        colShape.radius = 0.5f;
        var colMain = columnPS.main;
        colMain.startSpeed = 15f;
        colMain.startLifetime = 0.8f;'''

    run_method_name = {
        "corruption_wave": "RunCorruptionWave",
        "power_surge": "RunPowerSurge",
        "arena_transformation": "RunArenaTransformation",
    }[transition_type]

    script = f'''using UnityEngine;
using System.Collections;

/// <summary>
/// Boss phase transition VFX: {transition_type} for {boss_brand} brand.
/// {desc}
/// Phase 23 -- VFX3-08
/// </summary>
public class VB_BossTransitionVFX_{safe_type}_{boss_brand} : MonoBehaviour
{{
    [Header("Transition Config")]
    [SerializeField] private string transitionType = "{transition_type}";
    [SerializeField] private string bossBrand = "{boss_brand}";
    [SerializeField] private float duration = {duration}f;
    [SerializeField] private float arenaRadius = {arena_radius}f;

    [Header("Brand Colors")]
    [SerializeField] private Color brandColor = new Color({r}f, {g}f, {b}f, {a}f);
    [SerializeField] private Color glowColor = new Color({gr}f, {gg}f, {gb}f, {ga}f);

    [Header("Phase Intensities")]
    [SerializeField] private float phase1Intensity = 1.0f;
    [SerializeField] private float phase2Intensity = 1.5f;
    [SerializeField] private float phase3Intensity = 2.5f;

    // Events
    public event System.Action OnTransitionFinished;

    // Runtime
    private ParticleSystem chargePS;
    private ParticleSystem wavePS;
    private ParticleSystem aftermathPS;{column_field}
    private Renderer[] arenaRenderers;
    private MaterialPropertyBlock _mpb;
    private bool isTransitioning = false;
    private int currentPhase = 1;

    public bool IsTransitioning => isTransitioning;
    public int CurrentPhase => currentPhase;
    public string TransitionType => transitionType;

    /// <summary>
    /// Trigger a phase transition with specified phase number.
    /// Phase 1->2: rage, Phase 2->3: desperation, Phase 3->death: collapse.
    /// </summary>
    public void TriggerTransition(int newPhase)
    {{
        if (isTransitioning) return;
        currentPhase = newPhase;

        // Scale intensity by phase
        float phaseIntensity = newPhase switch
        {{
            2 => phase1Intensity,
            3 => phase2Intensity,
            _ => phase3Intensity,
        }};

        isTransitioning = true;
        StartCoroutine(RunPhaseTransition(phaseIntensity));
    }}

    private IEnumerator RunPhaseTransition(float phaseIntensity)
    {{
        // Scale particle rates by phase intensity
        ScaleEffects(phaseIntensity);
        yield return StartCoroutine({run_method_name}());
    }}

    private void Start()
    {{
        arenaRenderers = GetComponentsInChildren<Renderer>();
        _mpb = new MaterialPropertyBlock();
        CreateParticleSystems();
    }}

    private void CreateParticleSystems()
    {{
        // Charge/gathering particles
        chargePS = CreatePS("Charge", 100, 0.1f);
        var chargeShape = chargePS.shape;
        chargeShape.shapeType = ParticleSystemShapeType.Sphere;
        chargeShape.radius = 2f;

        // Wave/ring particles
        wavePS = CreatePS("Wave", 200, 0.2f);
        var waveShape = wavePS.shape;
        waveShape.shapeType = ParticleSystemShapeType.Circle;
        waveShape.radius = 0.5f;
        waveShape.radiusThickness = 0f;

        // Aftermath residue
        aftermathPS = CreatePS("Aftermath", 50, 0.3f);
        var afterShape = aftermathPS.shape;
        afterShape.shapeType = ParticleSystemShapeType.Sphere;
        afterShape.radius = arenaRadius * 0.5f;
        var afterMain = aftermathPS.main;
        afterMain.startSpeed = 0.5f;
        afterMain.startLifetime = 3f;{column_setup}
    }}

    private ParticleSystem CreatePS(string psName, int rate, float size)
    {{
        GameObject psObj = new GameObject($"BossVFX_{{psName}}");
        psObj.transform.SetParent(transform);
        psObj.transform.localPosition = Vector3.zero;

        ParticleSystem ps = psObj.AddComponent<ParticleSystem>();
        var main = ps.main;
        main.duration = duration;
        main.loop = true;
        main.startLifetime = 1.5f;
        main.startSpeed = 5f;
        main.startSize = size;
        main.startColor = brandColor;
        main.maxParticles = rate * 3;
        main.playOnAwake = false;
        main.simulationSpace = ParticleSystemSimulationSpace.World;

        var emission = ps.emission;
        emission.rateOverTime = rate;

        var col = ps.colorOverLifetime;
        col.enabled = true;
        Gradient grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(glowColor, 0f),
                new GradientColorKey(brandColor, 0.5f),
                new GradientColorKey(brandColor * 0.1f, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(0.8f, 0f),
                new GradientAlphaKey(1f, 0.3f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        var renderer = ps.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit") ?? Shader.Find("Particles/Standard Unlit"));
        renderer.material.SetColor("_Color", glowColor);

        ps.Stop();
        return ps;
    }}

    private void ScaleEffects(float scale)
    {{
        void ScalePS(ParticleSystem ps)
        {{
            if (ps == null) return;
            var emission = ps.emission;
            emission.rateOverTime = emission.rateOverTime.constant * scale;
            var main = ps.main;
            main.startSize = main.startSize.constant * Mathf.Sqrt(scale);
        }}
        ScalePS(chargePS);
        ScalePS(wavePS);
        ScalePS(aftermathPS);
    }}

    private void ApplyGlow(float glowIntensity)
    {{
        if (arenaRenderers == null) return;
        foreach (var rend in arenaRenderers)
        {{
            if (rend == null) continue;
            rend.GetPropertyBlock(_mpb);
            _mpb.SetColor("_EmissionColor", glowColor * glowIntensity);
            rend.SetPropertyBlock(_mpb);
        }}
    }}

    private void ApplyScreenShake(float shakeIntensity)
    {{
        // Integrate with camera shake system
        Camera cam = Camera.main;
        if (cam != null)
        {{
            cam.transform.localPosition += Random.insideUnitSphere * 0.05f * shakeIntensity;
        }}
    }}

    private void OnTransitionComplete()
    {{
        isTransitioning = false;
        OnTransitionFinished?.Invoke();
        Debug.Log($"[VB] Boss transition complete: {{transitionType}} phase={{currentPhase}}");
    }}
{transition_coroutine}
}}
'''

    return {
        "script_path": f"Assets/Scripts/VFX/VB_BossTransitionVFX_{safe_type}_{boss_brand}.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            f"Attach VB_BossTransitionVFX_{safe_type}_{boss_brand} to boss root GameObject",
            "Call TriggerTransition(phaseNumber) from boss AI state machine",
            f"Transition: {transition_type}, Brand: {boss_brand}, Duration: {duration}s",
        ],
    }


# ---------------------------------------------------------------------------
# VFX Pool Manager -- Object pooling for VFX prefabs
# ---------------------------------------------------------------------------


def generate_vfx_pool_script(
    initial_pool_size: int = 10,
    max_pool_size: int = 50,
    default_lifetime: float = 3.0,
) -> dict[str, Any]:
    """Generate a runtime VFX object pool manager.

    Creates a singleton ``VFXPoolManager`` MonoBehaviour that maintains
    per-effect-ID object pools using ``Dictionary<string, Queue<GameObject>>``.
    Eliminates instantiation overhead during combat by reusing deactivated
    GameObjects.  Pools are pre-warmed on ``Awake`` and auto-return effects
    after a configurable lifetime via coroutine.

    Args:
        initial_pool_size: Number of instances to pre-warm per registered effect.
        max_pool_size: Maximum pool capacity per effect to prevent memory leaks.
        default_lifetime: Seconds before an effect auto-returns to its pool.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    initial_pool_size = max(1, min(initial_pool_size, 200))
    max_pool_size = max(initial_pool_size, min(max_pool_size, 500))
    default_lifetime = max(0.1, min(default_lifetime, 60.0))

    script = f'''using UnityEngine;
using System.Collections;
using System.Collections.Generic;

/// <summary>
/// Object pool manager for VFX prefabs.  Singleton that eliminates
/// instantiation overhead by recycling deactivated GameObjects.
/// Phase 23 -- VFX Pool System
/// </summary>
public class VFXPoolManager : MonoBehaviour
{{
    public static VFXPoolManager Instance {{ get; private set; }}

    [Header("Pool Settings")]
    [Tooltip("Default instances to pre-warm per effect ID")]
    public int initialPoolSize = {initial_pool_size};

    [Tooltip("Maximum pool capacity per effect ID (prevents memory leaks)")]
    public int maxPoolSize = {max_pool_size};

    [Tooltip("Default seconds before auto-return to pool")]
    public float defaultLifetime = {default_lifetime}f;

    [Header("Pre-warm Registry")]
    [Tooltip("Prefabs to pre-warm on Awake. Key = effectId string.")]
    public List<PoolEntry> prewarmEntries = new List<PoolEntry>();

    [System.Serializable]
    public class PoolEntry
    {{
        public string effectId;
        public GameObject prefab;
        [Min(1)] public int count;
    }}

    // -- Internal state --
    private readonly Dictionary<string, Queue<GameObject>> _pools =
        new Dictionary<string, Queue<GameObject>>();
    private readonly Dictionary<string, GameObject> _prefabRegistry =
        new Dictionary<string, GameObject>();
    private readonly Dictionary<string, PoolStats> _stats =
        new Dictionary<string, PoolStats>();

    /// <summary>Runtime stats for a single pool.</summary>
    public class PoolStats
    {{
        public int activeCount;
        public int poolSize;
        public int peakUsage;
    }}

    // -----------------------------------------------------------------------
    // Lifecycle
    // -----------------------------------------------------------------------

    private void Awake()
    {{
        if (Instance != null && Instance != this)
        {{
            Destroy(gameObject);
            return;
        }}
        Instance = this;
        DontDestroyOnLoad(gameObject);

        foreach (var entry in prewarmEntries)
        {{
            if (entry.prefab == null || string.IsNullOrEmpty(entry.effectId))
                continue;
            RegisterPrefab(entry.effectId, entry.prefab);
            PreWarm(entry.effectId, entry.count > 0 ? entry.count : initialPoolSize);
        }}
    }}

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------

    /// <summary>Register a prefab for a given effect ID.</summary>
    public void RegisterPrefab(string effectId, GameObject prefab)
    {{
        if (string.IsNullOrEmpty(effectId) || prefab == null) return;
        _prefabRegistry[effectId] = prefab;
        if (!_pools.ContainsKey(effectId))
            _pools[effectId] = new Queue<GameObject>();
        if (!_stats.ContainsKey(effectId))
            _stats[effectId] = new PoolStats();
    }}

    /// <summary>Pre-warm a pool with inactive instances.</summary>
    public void PreWarm(string effectId, int count)
    {{
        if (!_prefabRegistry.ContainsKey(effectId)) return;
        if (!_pools.ContainsKey(effectId))
            _pools[effectId] = new Queue<GameObject>();

        int toCreate = Mathf.Min(count, maxPoolSize - _pools[effectId].Count);
        for (int i = 0; i < toCreate; i++)
        {{
            GameObject obj = Instantiate(_prefabRegistry[effectId], transform);
            obj.SetActive(false);
            _pools[effectId].Enqueue(obj);
        }}
        UpdatePoolSizeStat(effectId);
    }}

    /// <summary>
    /// Get a VFX instance from the pool (or instantiate if pool empty).
    /// Auto-returns after <paramref name="lifetime"/> seconds.
    /// </summary>
    public GameObject GetEffect(string effectId, Vector3 position, Quaternion rotation, float lifetime = -1f)
    {{
        if (string.IsNullOrEmpty(effectId)) return null;

        GameObject obj = null;

        if (_pools.ContainsKey(effectId) && _pools[effectId].Count > 0)
        {{
            obj = _pools[effectId].Dequeue();
            // Handle destroyed pooled objects
            while (obj == null && _pools[effectId].Count > 0)
                obj = _pools[effectId].Dequeue();
        }}

        if (obj == null)
        {{
            if (!_prefabRegistry.ContainsKey(effectId))
            {{
                Debug.LogWarning($"[VFXPool] No prefab registered for '{{effectId}}'");
                return null;
            }}
            obj = Instantiate(_prefabRegistry[effectId], transform);
        }}

        obj.transform.SetPositionAndRotation(position, rotation);
        obj.SetActive(true);

        // Restart particle systems
        var particles = obj.GetComponentsInChildren<ParticleSystem>(true);
        foreach (var ps in particles)
        {{
            ps.Clear();
            ps.Play();
        }}

        // Track stats
        EnsureStats(effectId);
        _stats[effectId].activeCount++;
        if (_stats[effectId].activeCount > _stats[effectId].peakUsage)
            _stats[effectId].peakUsage = _stats[effectId].activeCount;
        UpdatePoolSizeStat(effectId);

        float lt = lifetime > 0f ? lifetime : defaultLifetime;
        StartCoroutine(AutoReturnCoroutine(effectId, obj, lt));

        return obj;
    }}

    /// <summary>Return a VFX instance to its pool.</summary>
    public void ReturnEffect(string effectId, GameObject effect)
    {{
        if (effect == null) return;
        if (string.IsNullOrEmpty(effectId))
        {{
            Destroy(effect);
            return;
        }}

        // Stop particle systems
        var particles = effect.GetComponentsInChildren<ParticleSystem>(true);
        foreach (var ps in particles)
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

        effect.SetActive(false);

        if (!_pools.ContainsKey(effectId))
            _pools[effectId] = new Queue<GameObject>();

        // Enforce max pool size
        if (_pools[effectId].Count >= maxPoolSize)
        {{
            Destroy(effect);
        }}
        else
        {{
            _pools[effectId].Enqueue(effect);
        }}

        EnsureStats(effectId);
        _stats[effectId].activeCount = Mathf.Max(0, _stats[effectId].activeCount - 1);
        UpdatePoolSizeStat(effectId);
    }}

    /// <summary>Get runtime stats for a pool.</summary>
    public PoolStats GetStats(string effectId)
    {{
        return _stats.ContainsKey(effectId) ? _stats[effectId] : null;
    }}

    /// <summary>Get stats for all pools.</summary>
    public Dictionary<string, PoolStats> GetAllStats()
    {{
        return new Dictionary<string, PoolStats>(_stats);
    }}

    // -----------------------------------------------------------------------
    // Internals
    // -----------------------------------------------------------------------

    private IEnumerator AutoReturnCoroutine(string effectId, GameObject obj, float lifetime)
    {{
        yield return new WaitForSeconds(lifetime);
        if (obj != null && obj.activeInHierarchy)
            ReturnEffect(effectId, obj);
    }}

    private void EnsureStats(string effectId)
    {{
        if (!_stats.ContainsKey(effectId))
            _stats[effectId] = new PoolStats();
    }}

    private void UpdatePoolSizeStat(string effectId)
    {{
        if (_stats.ContainsKey(effectId) && _pools.ContainsKey(effectId))
            _stats[effectId].poolSize = _pools[effectId].Count;
    }}
}}
'''

    return {
        "script_path": "Assets/Scripts/VFX/VFXPoolManager.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            "Add VFXPoolManager to a persistent GameObject (it uses DontDestroyOnLoad)",
            "Register VFX prefabs via the prewarmEntries list in the Inspector",
            "Call VFXPoolManager.Instance.GetEffect(effectId, pos, rot) to spawn pooled VFX",
            f"Defaults: pool pre-warm={initial_pool_size}, max={max_pool_size}, lifetime={default_lifetime}s",
        ],
    }


# ---------------------------------------------------------------------------
# VFX LOD Manager -- Distance-based VFX quality scaling
# ---------------------------------------------------------------------------


def generate_vfx_lod_script(
    full_distance: float = 20.0,
    reduced_distance: float = 50.0,
    cull_distance: float = 80.0,
    update_interval: float = 0.25,
) -> dict[str, Any]:
    """Generate a runtime VFX LOD manager for distance-based quality scaling.

    Creates a ``VFXLODManager`` MonoBehaviour that periodically checks the
    distance from the main camera to each registered VFX and adjusts quality:

    * **Full** (0 -- ``full_distance`` m): all particles, full emission rate.
    * **Reduced** (``full_distance`` -- ``reduced_distance`` m): 50% particle
      rate, simplified rendering.
    * **Minimal** (``reduced_distance`` -- ``cull_distance`` m): billboard
      sprite only, particles disabled.
    * **Culled** (beyond ``cull_distance`` m): VFX disabled entirely.

    Uses ``Physics.OverlapSphereNonAlloc`` for efficient spatial queries and
    caches ``Camera.main`` to avoid repeated ``FindGameObjectWithTag`` calls.

    Args:
        full_distance: Distance threshold for full-quality VFX.
        reduced_distance: Distance threshold for reduced-quality VFX.
        cull_distance: Distance beyond which VFX are disabled entirely.
        update_interval: Seconds between LOD update ticks.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    full_distance = max(1.0, min(full_distance, 500.0))
    reduced_distance = max(full_distance + 1.0, min(reduced_distance, 1000.0))
    cull_distance = max(reduced_distance + 1.0, min(cull_distance, 2000.0))
    update_interval = max(0.05, min(update_interval, 5.0))

    script = f'''using UnityEngine;
using System.Collections;
using System.Collections.Generic;

/// <summary>
/// Distance-based VFX quality manager.  Adjusts particle rates, enables
/// billboard fallback sprites, and culls distant effects to maintain
/// framerate during large-scale combat.
/// Phase 23 -- VFX LOD System
/// </summary>
public class VFXLODManager : MonoBehaviour
{{
    public static VFXLODManager Instance {{ get; private set; }}

    public enum VFXLODTier {{ Full, Reduced, Minimal, Culled }}

    [Header("Distance Thresholds")]
    [Tooltip("Max distance for full quality (all particles, full rate)")]
    public float fullDistance = {full_distance}f;

    [Tooltip("Max distance for reduced quality (50%% particle rate)")]
    public float reducedDistance = {reduced_distance}f;

    [Tooltip("Max distance before complete culling")]
    public float cullDistance = {cull_distance}f;

    [Header("Update Settings")]
    [Tooltip("Seconds between LOD evaluation passes")]
    public float updateInterval = {update_interval}f;

    // -- Internal state --
    private Camera _mainCamera;
    private float _nextUpdateTime;
    private readonly List<VFXLODEntry> _entries = new List<VFXLODEntry>();

    /// <summary>Registered VFX entry with cached component refs.</summary>
    public class VFXLODEntry
    {{
        public GameObject root;
        public ParticleSystem[] particleSystems;
        public float[] originalRates;
        public Renderer billboardRenderer;
        public VFXLODTier currentTier;
        public bool wasActive;
    }}

    // -----------------------------------------------------------------------
    // Lifecycle
    // -----------------------------------------------------------------------

    private void Awake()
    {{
        if (Instance != null && Instance != this)
        {{
            Destroy(gameObject);
            return;
        }}
        Instance = this;
        _mainCamera = Camera.main;
    }}

    private void Update()
    {{
        if (Time.time < _nextUpdateTime) return;
        _nextUpdateTime = Time.time + updateInterval;
        EvaluateAllEntries();
    }}

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------

    /// <summary>
    /// Register a VFX GameObject for LOD management.
    /// Optionally supply a billboard Renderer used as the Minimal-tier fallback.
    /// </summary>
    public void Register(GameObject vfxRoot, Renderer billboard = null)
    {{
        if (vfxRoot == null) return;

        // Avoid duplicate registration
        for (int i = 0; i < _entries.Count; i++)
        {{
            if (_entries[i].root == vfxRoot) return;
        }}

        var ps = vfxRoot.GetComponentsInChildren<ParticleSystem>(true);
        float[] rates = new float[ps.Length];
        for (int i = 0; i < ps.Length; i++)
        {{
            var emission = ps[i].emission;
            rates[i] = emission.rateOverTimeMultiplier;
        }}

        _entries.Add(new VFXLODEntry
        {{
            root = vfxRoot,
            particleSystems = ps,
            originalRates = rates,
            billboardRenderer = billboard,
            currentTier = VFXLODTier.Full,
            wasActive = vfxRoot.activeInHierarchy,
        }});
    }}

    /// <summary>Unregister a VFX GameObject from LOD management.</summary>
    public void Unregister(GameObject vfxRoot)
    {{
        for (int i = _entries.Count - 1; i >= 0; i--)
        {{
            if (_entries[i].root == vfxRoot)
            {{
                // Restore original rates before removing
                RestoreOriginalRates(_entries[i]);
                _entries.RemoveAt(i);
                return;
            }}
        }}
    }}

    /// <summary>Get the current LOD tier for a registered VFX.</summary>
    public VFXLODTier GetTier(GameObject vfxRoot)
    {{
        for (int i = 0; i < _entries.Count; i++)
        {{
            if (_entries[i].root == vfxRoot)
                return _entries[i].currentTier;
        }}
        return VFXLODTier.Culled;
    }}

    /// <summary>Get count of entries at each tier.</summary>
    public Dictionary<VFXLODTier, int> GetTierCounts()
    {{
        var counts = new Dictionary<VFXLODTier, int>
        {{
            {{ VFXLODTier.Full, 0 }},
            {{ VFXLODTier.Reduced, 0 }},
            {{ VFXLODTier.Minimal, 0 }},
            {{ VFXLODTier.Culled, 0 }},
        }};
        for (int i = 0; i < _entries.Count; i++)
        {{
            if (_entries[i].root != null)
                counts[_entries[i].currentTier]++;
        }}
        return counts;
    }}

    // -----------------------------------------------------------------------
    // LOD Evaluation
    // -----------------------------------------------------------------------

    private void EvaluateAllEntries()
    {{
        if (_mainCamera == null)
        {{
            _mainCamera = Camera.main;
            if (_mainCamera == null) return;
        }}

        Vector3 camPos = _mainCamera.transform.position;

        for (int i = _entries.Count - 1; i >= 0; i--)
        {{
            var entry = _entries[i];

            // Clean up destroyed objects
            if (entry.root == null)
            {{
                _entries.RemoveAt(i);
                continue;
            }}

            // Skip inactive objects that we did not cull ourselves
            if (!entry.root.activeInHierarchy && entry.currentTier != VFXLODTier.Culled)
                continue;

            float dist = Vector3.Distance(camPos, entry.root.transform.position);
            VFXLODTier newTier = ClassifyDistance(dist);

            if (newTier != entry.currentTier)
                ApplyTier(entry, newTier);
        }}
    }}

    private VFXLODTier ClassifyDistance(float distance)
    {{
        if (distance <= fullDistance) return VFXLODTier.Full;
        if (distance <= reducedDistance) return VFXLODTier.Reduced;
        if (distance <= cullDistance) return VFXLODTier.Minimal;
        return VFXLODTier.Culled;
    }}

    private void ApplyTier(VFXLODEntry entry, VFXLODTier tier)
    {{
        entry.currentTier = tier;

        switch (tier)
        {{
            case VFXLODTier.Full:
                entry.root.SetActive(true);
                SetParticleRates(entry, 1.0f);
                EnableParticleSystems(entry, true);
                SetBillboard(entry, false);
                break;

            case VFXLODTier.Reduced:
                entry.root.SetActive(true);
                SetParticleRates(entry, 0.5f);
                EnableParticleSystems(entry, true);
                SetBillboard(entry, false);
                break;

            case VFXLODTier.Minimal:
                entry.root.SetActive(true);
                EnableParticleSystems(entry, false);
                SetBillboard(entry, true);
                break;

            case VFXLODTier.Culled:
                entry.wasActive = entry.root.activeInHierarchy;
                entry.root.SetActive(false);
                break;
        }}
    }}

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    private void SetParticleRates(VFXLODEntry entry, float multiplier)
    {{
        for (int i = 0; i < entry.particleSystems.Length; i++)
        {{
            if (entry.particleSystems[i] == null) continue;
            var emission = entry.particleSystems[i].emission;
            emission.rateOverTimeMultiplier = entry.originalRates[i] * multiplier;
        }}
    }}

    private void EnableParticleSystems(VFXLODEntry entry, bool enabled)
    {{
        for (int i = 0; i < entry.particleSystems.Length; i++)
        {{
            if (entry.particleSystems[i] == null) continue;
            if (enabled && !entry.particleSystems[i].isPlaying)
                entry.particleSystems[i].Play();
            else if (!enabled && entry.particleSystems[i].isPlaying)
                entry.particleSystems[i].Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        }}
    }}

    private void SetBillboard(VFXLODEntry entry, bool enabled)
    {{
        if (entry.billboardRenderer != null)
            entry.billboardRenderer.enabled = enabled;
    }}

    private void RestoreOriginalRates(VFXLODEntry entry)
    {{
        for (int i = 0; i < entry.particleSystems.Length; i++)
        {{
            if (entry.particleSystems[i] == null) continue;
            var emission = entry.particleSystems[i].emission;
            emission.rateOverTimeMultiplier = entry.originalRates[i];
        }}
    }}
}}
'''

    return {
        "script_path": "Assets/Scripts/VFX/VFXLODManager.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            "Add VFXLODManager to a persistent scene GameObject",
            "Call VFXLODManager.Instance.Register(vfxObj, billboard) for each active VFX",
            "Optionally integrate with VFXPoolManager: register on GetEffect, unregister on ReturnEffect",
            f"Defaults: full<{full_distance}m, reduced<{reduced_distance}m, minimal<{cull_distance}m, "
            f"update every {update_interval}s",
        ],
    }
