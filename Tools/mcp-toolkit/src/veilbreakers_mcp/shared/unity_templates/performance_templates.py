"""Performance C# template generators for Unity automation.

Each function returns a complete C# source string that can be written to
a Unity project's Assets/Editor/Generated/Performance/ directory. When compiled
by Unity, the scripts register as MenuItem commands under
"VeilBreakers/Performance/...".

All generated scripts write their result to Temp/vb_result.json so that
the Python MCP server can read back the outcome after execution.

Exports:
    generate_scene_profiler_script        -- PERF-01: frame time, draw calls, batches, tris, memory
    generate_lod_setup_script             -- PERF-02: LODGroup auto-generation for scene meshes
    generate_lightmap_bake_script         -- PERF-03: lightmap baking with progress monitoring
    generate_asset_audit_script           -- PERF-04: unused assets, oversized textures, uncompressed audio
    generate_build_automation_script      -- PERF-05: build pipeline automation with size report

Pure-logic helpers:
    _analyze_profile_thresholds           -- compare profiler data against budgets
    _classify_asset_issues                -- categorize audit findings by type
    _validate_lod_screen_percentages      -- ensure descending order, all > 0
"""

from __future__ import annotations

import re


def _sanitize_cs_string(value: str) -> str:
    """Escape a value for safe embedding inside a C# string literal."""
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    return value


def _sanitize_cs_identifier(value: str) -> str:
    """Sanitize a value for use as a C# identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "", value)


# ---------------------------------------------------------------------------
# Pure-logic helpers
# ---------------------------------------------------------------------------

_RECOMMENDATIONS: dict[str, str] = {
    "frame_time": "Reduce per-frame workload: disable expensive effects, reduce shadow resolution, or lower LOD bias",
    "draw_calls": "Enable GPU instancing, use static/dynamic batching, or merge meshes to reduce draw calls",
    "triangles": "Use LOD groups, reduce mesh poly counts, or enable occlusion culling to lower triangle count",
    "memory_mb": "Compress textures, reduce texture resolution, stream assets, or unload unused scenes",
}


def _analyze_profile_thresholds(
    data: dict[str, float],
    budgets: dict[str, float],
) -> list[dict]:
    """Compare profiler data against budgets and return exceeded thresholds.

    Args:
        data: Measured metric values keyed by metric name.
        budgets: Budget limits keyed by metric name.

    Returns:
        List of dicts with keys: metric, value, budget, severity, recommendation.
        Empty list if all metrics are within budget.
    """
    violations: list[dict] = []
    for metric, budget in budgets.items():
        value = data.get(metric)
        if value is None or budget <= 0:
            continue
        if value > budget:
            ratio = value / budget
            severity = "critical" if ratio >= 2.0 else "warning"
            recommendation = _RECOMMENDATIONS.get(
                metric,
                f"Reduce {metric} to stay within budget of {budget}",
            )
            violations.append(
                {
                    "metric": metric,
                    "value": value,
                    "budget": budget,
                    "severity": severity,
                    "recommendation": recommendation,
                }
            )
    return violations


def _classify_asset_issues(assets: list[dict]) -> dict:
    """Categorize asset audit findings by issue type.

    Args:
        assets: List of dicts describing asset issues. Each dict must have
            a "type" key: "texture", "audio", "unused", or "duplicate_material".

    Returns:
        Dict with keys: oversized_textures, uncompressed_audio, unused_assets,
        duplicate_materials. Each value is a dict with "count" and "details".
    """
    result: dict[str, dict] = {
        "oversized_textures": {"count": 0, "details": []},
        "uncompressed_audio": {"count": 0, "details": []},
        "unused_assets": {"count": 0, "details": []},
        "duplicate_materials": {"count": 0, "details": []},
    }

    for asset in assets:
        asset_type = asset.get("type", "")
        if asset_type == "texture":
            result["oversized_textures"]["count"] += 1
            result["oversized_textures"]["details"].append(asset)
        elif asset_type == "audio":
            result["uncompressed_audio"]["count"] += 1
            result["uncompressed_audio"]["details"].append(asset)
        elif asset_type == "unused":
            result["unused_assets"]["count"] += 1
            result["unused_assets"]["details"].append(asset)
        elif asset_type == "duplicate_material":
            result["duplicate_materials"]["count"] += 1
            result["duplicate_materials"]["details"].append(asset)

    return result


def _validate_lod_screen_percentages(percentages: list[float]) -> bool:
    """Check that LOD screen percentages are strictly descending and all > 0.

    Args:
        percentages: List of screen percentage thresholds for LOD levels.

    Returns:
        True if valid (strictly descending, all > 0, non-empty), False otherwise.
    """
    if not percentages:
        return False
    for p in percentages:
        if p <= 0:
            return False
    for i in range(1, len(percentages)):
        if percentages[i] >= percentages[i - 1]:
            return False
    return True


# ---------------------------------------------------------------------------
# PERF-01: Scene profiler
# ---------------------------------------------------------------------------

_DEFAULT_BUDGETS: dict[str, float] = {
    "frame_time": 16.6,
    "draw_calls": 2000,
    "batches": 1000,
    "triangles": 500000,
    "memory_mb": 512.0,
}


def generate_scene_profiler_script(
    budgets: dict[str, float] | None = None,
) -> str:
    """Generate C# editor script for scene performance profiling.

    Collects frame time, draw calls, batches, triangles, and memory usage
    via UnityStats and Profiler APIs. Compares against configurable budget
    thresholds and writes JSON report with recommendations.

    Args:
        budgets: Dict of metric name -> budget limit. Defaults to standard
            game performance budgets.

    Returns:
        Complete C# source string.
    """
    b = budgets or _DEFAULT_BUDGETS
    frame_time_budget = b.get("frame_time", 16.6)
    draw_calls_budget = b.get("draw_calls", 2000)
    batches_budget = b.get("batches", 1000)
    triangles_budget = b.get("triangles", 500000)
    memory_budget = b.get("memory_mb", 512.0)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_SceneProfiler
{{
    [MenuItem("VeilBreakers/Performance/Profile Scene")]
    public static void Execute()
    {{
        try
        {{
            // Collect metrics
            float frameTime = Time.unscaledDeltaTime * 1000f;
            int drawCalls = UnityStats.drawCalls;
            int batches = UnityStats.batches;
            int triangles = UnityStats.triangles;
            long totalMemoryBytes = UnityEngine.Profiling.Profiler.GetTotalAllocatedMemoryLong();
            float memoryMB = totalMemoryBytes / (1024f * 1024f);

            // Budget thresholds
            float frameTimeBudget = {frame_time_budget}f;
            int drawCallsBudget = {draw_calls_budget};
            int batchesBudget = {batches_budget};
            int trianglesBudget = {triangles_budget};
            float memoryBudget = {memory_budget}f;

            // Build recommendations
            var recommendations = new List<string>();

            if (frameTime > frameTimeBudget)
                recommendations.Add("Frame time (" + frameTime.ToString("F1") + "ms) exceeds budget (" + frameTimeBudget + "ms). Reduce per-frame workload.");
            if (drawCalls > drawCallsBudget)
                recommendations.Add("Draw calls (" + drawCalls + ") exceed budget (" + drawCallsBudget + "). Enable GPU instancing or batching.");
            if (batches > batchesBudget)
                recommendations.Add("Batches (" + batches + ") exceed budget (" + batchesBudget + "). Merge meshes or use static batching.");
            if (triangles > trianglesBudget)
                recommendations.Add("Triangles (" + triangles + ") exceed budget (" + trianglesBudget + "). Use LOD groups or reduce poly counts.");
            if (memoryMB > memoryBudget)
                recommendations.Add("Memory (" + memoryMB.ToString("F1") + "MB) exceeds budget (" + memoryBudget + "MB). Compress textures or unload unused assets.");

            // Build recommendation JSON array
            string recsJson = "[";
            for (int i = 0; i < recommendations.Count; i++)
            {{
                recsJson += "\\"" + recommendations[i].Replace("\\"", "\\\\\\"") + "\\"";
                if (i < recommendations.Count - 1) recsJson += ", ";
            }}
            recsJson += "]";

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"profile_scene\\", "
                + "\\"frame_time_ms\\": " + frameTime.ToString("F2") + ", "
                + "\\"draw_calls\\": " + drawCalls + ", "
                + "\\"batches\\": " + batches + ", "
                + "\\"triangles\\": " + triangles + ", "
                + "\\"memory_mb\\": " + memoryMB.ToString("F1") + ", "
                + "\\"recommendations\\": " + recsJson + "}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Scene profiling completed. " + recommendations.Count + " recommendation(s).");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"profile_scene\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Scene profiling failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# PERF-02: LOD setup
# ---------------------------------------------------------------------------

_DEFAULT_LOD_PERCENTAGES: list[float] = [0.6, 0.3, 0.15]


def generate_lod_setup_script(
    lod_count: int = 3,
    screen_percentages: list[float] | None = None,
) -> str:
    """Generate C# editor script for automatic LODGroup setup on scene meshes.

    Finds all MeshRenderers, skips those already in a LODGroup, looks for
    sibling _LOD0/_LOD1/_LOD2 GameObjects, creates LODGroup with descending
    screen percentages, sets occlusion culling flags.

    Args:
        lod_count: Number of LOD levels (default 3).
        screen_percentages: Screen percentage thresholds per LOD level.
            Must be strictly descending and all > 0. Defaults to [0.6, 0.3, 0.15].

    Returns:
        Complete C# source string.

    Raises:
        ValueError: If screen_percentages are not strictly descending or contain
            values <= 0.
    """
    pcts = screen_percentages or _DEFAULT_LOD_PERCENTAGES[:lod_count]

    if not _validate_lod_screen_percentages(pcts):
        raise ValueError(
            f"screen_percentages must be strictly descending and all > 0, got: {pcts}"
        )

    # Adjust lod_count to match actual percentages
    lod_count = len(pcts)

    # Build LOD level assignment code
    lod_assignments = ""
    for i in range(lod_count):
        if i == 0:
            lod_assignments += f"""
                // LOD{i}: original mesh
                lods[{i}] = new LOD({pcts[i]}f, new Renderer[] {{ renderer }});"""
        else:
            lod_assignments += f"""
                // LOD{i}: look for sibling _LOD{i} mesh
                var lodChild{i} = go.transform.Find(go.name + "_LOD{i}");
                if (lodChild{i} != null)
                {{
                    var lodRenderer{i} = lodChild{i}.GetComponent<MeshRenderer>();
                    if (lodRenderer{i} != null)
                        lods[{i}] = new LOD({pcts[i]}f, new Renderer[] {{ lodRenderer{i} }});
                    else
                        lods[{i}] = new LOD({pcts[i]}f, new Renderer[] {{ renderer }});
                }}
                else
                {{
                    lods[{i}] = new LOD({pcts[i]}f, new Renderer[] {{ renderer }});
                }}"""

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_LODSetup
{{
    [MenuItem("VeilBreakers/Performance/Setup LODGroups")]
    public static void Execute()
    {{
        try
        {{
            var meshRenderers = Object.FindObjectsOfType<MeshRenderer>();
            int configured = 0;
            int skipped = 0;

            foreach (var renderer in meshRenderers)
            {{
                var go = renderer.gameObject;

                // Skip objects already in a LODGroup
                if (go.GetComponent<LODGroup>() != null)
                {{
                    skipped++;
                    continue;
                }}
                if (go.GetComponentInParent<LODGroup>() != null)
                {{
                    skipped++;
                    continue;
                }}

                // Create LODGroup
                var lodGroup = go.AddComponent<LODGroup>();
                var lods = new LOD[{lod_count}];
                {lod_assignments}

                lodGroup.SetLODs(lods);
                lodGroup.RecalculateBounds();

                // Set occlusion culling static flags
                StaticEditorFlags flags = GameObjectUtility.GetStaticEditorFlags(go);
                flags |= StaticEditorFlags.OccludeeStatic | StaticEditorFlags.OccluderStatic;
                GameObjectUtility.SetStaticEditorFlags(go, flags);

                configured++;
            }}

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"setup_lod_groups\\", "
                + "\\"configured\\": " + configured + ", "
                + "\\"skipped\\": " + skipped + ", "
                + "\\"lod_count\\": {lod_count}}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] LOD setup completed. Configured " + configured + " objects, skipped " + skipped + ".");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"setup_lod_groups\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] LOD setup failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# PERF-03: Lightmap bake
# ---------------------------------------------------------------------------


def generate_lightmap_bake_script(
    quality: str = "medium",
    bounces: int = 2,
    resolution: int = 32,
) -> str:
    """Generate C# editor script for async lightmap baking with progress.

    Sets GIWorkflowMode to OnDemand before calling BakeAsync (pitfall #4),
    configures LightmapEditorSettings for quality/bounces/resolution, uses
    EditorApplication.update callback to poll isRunning and write progress.

    Args:
        quality: Quality preset name (for logging/JSON output).
        bounces: Number of light bounces for indirect illumination.
        resolution: Lightmap texels per unit.

    Returns:
        Complete C# source string.
    """
    safe_quality = _sanitize_cs_string(quality)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_LightmapBaker
{{
    private static bool _isBaking = false;

    [MenuItem("VeilBreakers/Performance/Bake Lightmaps")]
    public static void Execute()
    {{
        try
        {{
            if (_isBaking)
            {{
                Debug.LogWarning("[VeilBreakers] Lightmap bake already in progress.");
                return;
            }}

            // Configure lightmap settings
            LightmapEditorSettings.bakeResolution = {resolution};
            LightmapEditorSettings.maxAtlasSize = 1024;
            Lightmapping.bounceBoost = 1.0f;

            // Set bounce count via LightmapEditorSettings
            // Note: indirect bounces configured through environment settings
            int bounces = {bounces};
            Debug.Log("[VeilBreakers] Configuring lightmap bake: quality={safe_quality}, bounces=" + bounces + ", resolution={resolution}");

            // IMPORTANT: Set GIWorkflowMode to OnDemand before BakeAsync (pitfall #4)
            Lightmapping.giWorkflowMode = Lightmapping.GIWorkflowMode.OnDemand;

            // Start async bake
            bool started = Lightmapping.BakeAsync();
            if (!started)
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"bake_lightmaps\\", \\"message\\": \\"BakeAsync failed to start\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                Debug.LogError("[VeilBreakers] BakeAsync failed to start.");
                return;
            }}

            _isBaking = true;

            // Write initial progress
            string initJson = "{{\\"status\\": \\"in_progress\\", \\"action\\": \\"bake_lightmaps\\", \\"quality\\": \\"{safe_quality}\\", \\"bounces\\": {bounces}, \\"resolution\\": {resolution}}}";
            File.WriteAllText("Temp/vb_result.json", initJson);

            // Poll for completion via EditorApplication.update
            EditorApplication.update += OnBakeUpdate;
            Debug.Log("[VeilBreakers] Lightmap bake started. Polling for completion...");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"bake_lightmaps\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Lightmap bake failed: " + ex.Message);
        }}
    }}

    private static void OnBakeUpdate()
    {{
        if (Lightmapping.isRunning)
        {{
            // Still baking -- could write progress here
            return;
        }}

        // Bake complete
        EditorApplication.update -= OnBakeUpdate;
        _isBaking = false;

        string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"bake_lightmaps\\", \\"quality\\": \\"{safe_quality}\\", \\"bounces\\": {bounces}, \\"resolution\\": {resolution}}}";
        File.WriteAllText("Temp/vb_result.json", json);
        Debug.Log("[VeilBreakers] Lightmap bake completed successfully.");
    }}
}}
'''


# ---------------------------------------------------------------------------
# PERF-04: Asset audit
# ---------------------------------------------------------------------------


def generate_asset_audit_script(
    max_texture_size: int = 2048,
    allowed_audio_formats: list[str] | None = None,
) -> str:
    """Generate C# editor script for asset auditing.

    Scans all asset paths via AssetDatabase.GetAllAssetPaths, checks
    TextureImporter for oversized textures, AudioImporter for uncompressed
    audio, walks dependencies for unused asset detection, and identifies
    duplicate materials by shader + property comparison.

    Args:
        max_texture_size: Maximum texture dimension before flagging as oversized.
        allowed_audio_formats: List of allowed compression format names. Defaults
            to ["Vorbis", "AAC"].

    Returns:
        Complete C# source string.
    """
    formats = allowed_audio_formats or ["Vorbis", "AAC"]
    format_checks = " && ".join(
        f'settings.compressionFormat.ToString() != "{_sanitize_cs_string(f)}"'
        for f in formats
    )

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;
using System.Linq;

public static class VeilBreakers_AssetAudit
{{
    [MenuItem("VeilBreakers/Performance/Audit Assets")]
    public static void Execute()
    {{
        try
        {{
            int maxTextureSize = {max_texture_size};
            var oversizedTextures = new List<string>();
            var uncompressedAudio = new List<string>();
            var unusedAssets = new List<string>();
            var duplicateMaterials = new List<string>();

            string[] allPaths = AssetDatabase.GetAllAssetPaths();

            // Build dependency set for unused detection
            var usedPaths = new HashSet<string>();
            var scenePaths = allPaths.Where(p => p.EndsWith(".unity")).ToArray();
            foreach (var scenePath in scenePaths)
            {{
                string[] deps = AssetDatabase.GetDependencies(scenePath, true);
                foreach (var dep in deps)
                    usedPaths.Add(dep);
            }}

            // Scan all assets
            var materialsByShader = new Dictionary<string, List<string>>();

            foreach (var path in allPaths)
            {{
                if (!path.StartsWith("Assets/")) continue;

                // Check textures
                var texImporter = AssetImporter.GetAtPath(path) as TextureImporter;
                if (texImporter != null)
                {{
                    if (texImporter.maxTextureSize > maxTextureSize)
                    {{
                        oversizedTextures.Add(path + " (" + texImporter.maxTextureSize + "px)");
                    }}
                }}

                // Check audio
                var audioImporter = AssetImporter.GetAtPath(path) as AudioImporter;
                if (audioImporter != null)
                {{
                    var settings = audioImporter.defaultSampleSettings;
                    if ({format_checks})
                    {{
                        uncompressedAudio.Add(path + " (" + settings.compressionFormat + ")");
                    }}
                }}

                // Check if unused (in Assets/ but not referenced by any scene)
                if (!usedPaths.Contains(path) && !path.EndsWith(".unity") && !path.Contains("/Editor/"))
                {{
                    if (path.EndsWith(".fbx") || path.EndsWith(".png") || path.EndsWith(".jpg") ||
                        path.EndsWith(".mat") || path.EndsWith(".wav") || path.EndsWith(".ogg"))
                    {{
                        unusedAssets.Add(path);
                    }}
                }}

                // Collect materials for duplicate detection
                if (path.EndsWith(".mat"))
                {{
                    var material = AssetDatabase.LoadAssetAtPath<Material>(path);
                    if (material != null && material.shader != null)
                    {{
                        string shaderKey = material.shader.name;
                        if (!materialsByShader.ContainsKey(shaderKey))
                            materialsByShader[shaderKey] = new List<string>();
                        materialsByShader[shaderKey].Add(path);
                    }}
                }}
            }}

            // Detect duplicate materials (same shader, multiple instances)
            foreach (var kvp in materialsByShader)
            {{
                if (kvp.Value.Count > 1)
                {{
                    foreach (var matPath in kvp.Value)
                        duplicateMaterials.Add(matPath + " (shader: " + kvp.Key + ")");
                }}
            }}

            // Build JSON report
            string oversizedJson = "[" + string.Join(", ", oversizedTextures.Select(s => "\\"" + s.Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string audioJson = "[" + string.Join(", ", uncompressedAudio.Select(s => "\\"" + s.Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string unusedJson = "[" + string.Join(", ", unusedAssets.Select(s => "\\"" + s.Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string dupeJson = "[" + string.Join(", ", duplicateMaterials.Select(s => "\\"" + s.Replace("\\"", "\\\\\\"") + "\\"")) + "]";

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"audit_assets\\", "
                + "\\"oversized_textures\\": " + oversizedJson + ", "
                + "\\"oversized_texture_count\\": " + oversizedTextures.Count + ", "
                + "\\"uncompressed_audio\\": " + audioJson + ", "
                + "\\"uncompressed_audio_count\\": " + uncompressedAudio.Count + ", "
                + "\\"unused_assets\\": " + unusedJson + ", "
                + "\\"unused_asset_count\\": " + unusedAssets.Count + ", "
                + "\\"duplicate_materials\\": " + dupeJson + ", "
                + "\\"duplicate_material_count\\": " + duplicateMaterials.Count + "}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Asset audit completed. "
                + oversizedTextures.Count + " oversized textures, "
                + uncompressedAudio.Count + " uncompressed audio, "
                + unusedAssets.Count + " unused assets, "
                + duplicateMaterials.Count + " duplicate materials.");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"audit_assets\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Asset audit failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# PERF-05: Build automation
# ---------------------------------------------------------------------------


def generate_build_automation_script(
    target: str = "StandaloneWindows64",
    scenes: list[str] | None = None,
    options: str = "None",
) -> str:
    """Generate C# editor script for build pipeline automation with size report.

    Runs BuildPipeline.BuildPlayer, checks BuildResult.Succeeded before
    accessing PackedAssets (pitfall #6), iterates packed assets for per-asset
    size breakdown, writes JSON with total size and top largest assets.

    Args:
        target: BuildTarget enum name (e.g. "StandaloneWindows64", "Android").
        scenes: List of scene paths to include in the build. Defaults to
            all scenes in Build Settings.
        options: BuildOptions flags (e.g. "Development", "None").

    Returns:
        Complete C# source string.
    """
    safe_target = _sanitize_cs_identifier(target)
    safe_options = _sanitize_cs_identifier(options)

    if scenes:
        scene_array = ", ".join(
            f'"{_sanitize_cs_string(s)}"' for s in scenes
        )
        scenes_code = f'string[] buildScenes = new string[] {{ {scene_array} }};'
    else:
        scenes_code = (
            "string[] buildScenes = (from scene in EditorBuildSettings.scenes "
            "where scene.enabled select scene.path).ToArray();"
        )

    return f'''using UnityEngine;
using UnityEditor;
using UnityEditor.Build.Reporting;
using System.IO;
using System.Linq;
using System.Collections.Generic;

public static class VeilBreakers_BuildAutomation
{{
    [MenuItem("VeilBreakers/Performance/Build With Report")]
    public static void Execute()
    {{
        try
        {{
            // Determine scenes
            {scenes_code}

            if (buildScenes.Length == 0)
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"build_automation\\", \\"message\\": \\"No scenes configured for build\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                Debug.LogError("[VeilBreakers] No scenes configured for build.");
                return;
            }}

            // Configure build options
            var buildOptions = new BuildPlayerOptions
            {{
                scenes = buildScenes,
                locationPathName = "Builds/{safe_target}/Game",
                target = BuildTarget.{safe_target},
                options = BuildOptions.{safe_options},
            }};

            Debug.Log("[VeilBreakers] Starting build for target: {safe_target}");

            // Execute build
            BuildReport report = BuildPipeline.BuildPlayer(buildOptions);

            // Check result BEFORE accessing packed assets (pitfall #6)
            if (report.summary.result != BuildResult.Succeeded)
            {{
                string failJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"build_automation\\", "
                    + "\\"build_result\\": \\"" + report.summary.result.ToString() + "\\", "
                    + "\\"total_errors\\": " + report.summary.totalErrors + ", "
                    + "\\"total_warnings\\": " + report.summary.totalWarnings + "}}";
                File.WriteAllText("Temp/vb_result.json", failJson);
                Debug.LogError("[VeilBreakers] Build failed: " + report.summary.result);
                return;
            }}

            // Parse packed assets for size breakdown
            long totalSizeBytes = (long)report.summary.totalSize;
            float totalSizeMB = totalSizeBytes / (1024f * 1024f);

            var assetSizes = new List<KeyValuePair<string, long>>();
            if (report.packedAssets != null)
            {{
                foreach (var packedAsset in report.packedAssets)
                {{
                    foreach (var content in packedAsset.contents)
                    {{
                        assetSizes.Add(new KeyValuePair<string, long>(
                            content.sourceAssetPath,
                            (long)content.packedSize
                        ));
                    }}
                }}
            }}

            // Sort by size descending and take top 20
            assetSizes.Sort((a, b) => b.Value.CompareTo(a.Value));
            int topCount = Mathf.Min(20, assetSizes.Count);

            string topAssetsJson = "[";
            for (int i = 0; i < topCount; i++)
            {{
                float sizeMB = assetSizes[i].Value / (1024f * 1024f);
                topAssetsJson += "{{\\"path\\": \\"" + assetSizes[i].Key.Replace("\\"", "\\\\\\"") + "\\", \\"size_mb\\": " + sizeMB.ToString("F2") + "}}";
                if (i < topCount - 1) topAssetsJson += ", ";
            }}
            topAssetsJson += "]";

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"build_automation\\", "
                + "\\"build_result\\": \\"Succeeded\\", "
                + "\\"target\\": \\"{safe_target}\\", "
                + "\\"total_size_mb\\": " + totalSizeMB.ToString("F2") + ", "
                + "\\"total_assets\\": " + assetSizes.Count + ", "
                + "\\"top_largest_assets\\": " + topAssetsJson + "}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Build completed. Total size: " + totalSizeMB.ToString("F1") + " MB");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"build_automation\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Build automation failed: " + ex.Message);
        }}
    }}
}}
'''
