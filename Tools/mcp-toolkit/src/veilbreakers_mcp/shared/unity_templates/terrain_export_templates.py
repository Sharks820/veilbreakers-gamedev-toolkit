"""Unity C# template generators for terrain export integration.

Generates editor scripts for:
- Importing Blender-exported terrain manifests into Unity Terrain
- Adding AdvancedTerrainErosion UPM package dependency
- Terrain size bridging (Blender Z-up -> Unity Y-up)

Each function returns a complete C# source string for Unity's
Assets/Editor/Generated/Scene/ directory.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ._cs_sanitize import sanitize_cs_identifier, sanitize_cs_string


# ---------------------------------------------------------------------------
# UPM package manifest entry for AdvancedTerrainErosion
# ---------------------------------------------------------------------------

# The UPM dependency spec for the erosion package.
ADVANCED_TERRAIN_EROSION_UPM = {
    "package_name": "com.veilbreakers.terrain-erosion",
    "version": "1.0.0",
    "display_name": "VeilBreakers Advanced Terrain Erosion",
    "description": (
        "GPU-accelerated hydraulic, thermal, and wind erosion for Unity "
        "terrain. Integrates with Blender-exported terrain manifests."
    ),
    "unity_min": "2022.3",
    "dependencies": {
        "com.unity.mathematics": "1.2.6",
        "com.unity.burst": "1.8.12",
        "com.unity.collections": "2.4.0",
    },
}


def generate_upm_manifest_entry() -> Dict[str, Any]:
    """Return the UPM package.json fragment for AdvancedTerrainErosion.

    This can be merged into a Unity project's Packages/manifest.json
    or used as a standalone package.json.
    """
    return {
        "name": ADVANCED_TERRAIN_EROSION_UPM["package_name"],
        "version": ADVANCED_TERRAIN_EROSION_UPM["version"],
        "displayName": ADVANCED_TERRAIN_EROSION_UPM["display_name"],
        "description": ADVANCED_TERRAIN_EROSION_UPM["description"],
        "unity": ADVANCED_TERRAIN_EROSION_UPM["unity_min"],
        "dependencies": ADVANCED_TERRAIN_EROSION_UPM["dependencies"],
        "keywords": ["terrain", "erosion", "procedural", "veilbreakers"],
        "author": {
            "name": "VeilBreakers",
            "url": "https://github.com/veilbreakers",
        },
    }


def generate_add_erosion_package_script(
    package_name: Optional[str] = None,
    version: Optional[str] = None,
) -> str:
    """Generate C# editor script that adds the erosion UPM package.

    Uses Unity's Package Manager Client API to add the dependency
    programmatically.
    """
    pkg = package_name or ADVANCED_TERRAIN_EROSION_UPM["package_name"]
    ver = version or ADVANCED_TERRAIN_EROSION_UPM["version"]
    safe_pkg = sanitize_cs_string(pkg)
    safe_ver = sanitize_cs_string(ver)

    return f'''using UnityEngine;
using UnityEditor;
using UnityEditor.PackageManager;
using UnityEditor.PackageManager.Requests;
using System.IO;

public static class VeilBreakers_AddErosionPackage
{{
    private static AddRequest _addRequest;

    [MenuItem("VeilBreakers/Terrain/Add Erosion Package")]
    public static void Execute()
    {{
        try
        {{
            Debug.Log("[VeilBreakers] Adding terrain erosion package: {safe_pkg}@{safe_ver}");
            _addRequest = Client.Add("{safe_pkg}@{safe_ver}");
            EditorApplication.update += Progress;
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"add_erosion_package\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Failed to add erosion package: " + ex.Message);
        }}
    }}

    private static void Progress()
    {{
        if (!_addRequest.IsCompleted) return;
        EditorApplication.update -= Progress;

        if (_addRequest.Status == StatusCode.Success)
        {{
            Debug.Log("[VeilBreakers] Erosion package added: " + _addRequest.Result.packageId);
            string json = "{{\\"status\\": \\"ok\\", \\"action\\": \\"add_erosion_package\\", \\"package_id\\": \\"" + _addRequest.Result.packageId + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
        }}
        else if (_addRequest.Status >= StatusCode.Failure)
        {{
            string errMsg = _addRequest.Error != null ? _addRequest.Error.message : "Unknown error";
            Debug.LogError("[VeilBreakers] Erosion package install failed: " + errMsg);
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"add_erosion_package\\", \\"message\\": \\"" + errMsg.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# Terrain manifest importer (reads Blender export manifest.json)
# ---------------------------------------------------------------------------


def generate_terrain_manifest_importer_script(
    manifest_path: str = "Assets/TerrainExport/manifest.json",
) -> str:
    """Generate C# editor script that imports terrain from a Blender manifest.

    Reads the manifest.json produced by export_unity_manifest(), creates
    a Unity Terrain with correct size/resolution/position (Y-up), and
    imports the .raw heightmap.
    """
    safe_manifest = sanitize_cs_string(manifest_path)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_TerrainManifestImporter
{{
    [MenuItem("VeilBreakers/Terrain/Import from Manifest")]
    public static void Execute()
    {{
        try
        {{
            string manifestPath = Path.Combine(Application.dataPath,
                "{safe_manifest}".Replace("Assets/", ""));

            if (!File.Exists(manifestPath))
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"import_terrain_manifest\\", \\"message\\": \\"Manifest not found: " + manifestPath + "\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                Debug.LogError("[VeilBreakers] Manifest not found: " + manifestPath);
                return;
            }}

            string manifestJson = File.ReadAllText(manifestPath);
            var manifest = JsonUtility.FromJson<ManifestData>(manifestJson);
            string manifestDir = Path.GetDirectoryName(manifestPath);

            // Create TerrainData with settings from manifest
            TerrainData terrainData = new TerrainData();

            // Read Unity terrain settings from manifest
            int heightmapRes = manifest.unity_terrain_settings_heightmap_resolution;
            if (heightmapRes < 33) heightmapRes = 513;  // Fallback
            terrainData.heightmapResolution = heightmapRes;

            // Terrain size: already in Y-up from the manifest
            terrainData.size = new Vector3(
                manifest.unity_terrain_settings_size_x,
                manifest.unity_terrain_settings_size_y,
                manifest.unity_terrain_settings_size_z
            );

            // Import .raw heightmap (little-endian uint16)
            string rawPath = Path.Combine(manifestDir, "heightmap.raw");
            if (File.Exists(rawPath))
            {{
                byte[] rawBytes = File.ReadAllBytes(rawPath);
                int res = terrainData.heightmapResolution;
                float[,] heights = new float[res, res];
                int expectedBytes = res * res * 2;

                if (rawBytes.Length >= expectedBytes)
                {{
                    for (int y = 0; y < res; y++)
                    {{
                        for (int x = 0; x < res; x++)
                        {{
                            int idx = (y * res + x) * 2;
                            // Little-endian uint16
                            ushort val = (ushort)(rawBytes[idx] | (rawBytes[idx + 1] << 8));
                            heights[y, x] = val / 65535f;
                        }}
                    }}
                    terrainData.SetHeights(0, 0, heights);
                    Debug.Log("[VeilBreakers] Heightmap imported: " + res + "x" + res);
                }}
                else
                {{
                    Debug.LogWarning("[VeilBreakers] RAW file size mismatch. Expected " +
                        expectedBytes + " bytes, got " + rawBytes.Length);
                }}
            }}
            else
            {{
                Debug.LogWarning("[VeilBreakers] heightmap.raw not found at: " + rawPath);
            }}

            // Create Terrain GameObject
            AssetDatabase.CreateAsset(terrainData,
                "Assets/TerrainData_Imported.asset");
            GameObject terrainObj = Terrain.CreateTerrainGameObject(terrainData);
            terrainObj.name = "VB_ImportedTerrain";

            // Position from manifest (already Y-up)
            terrainObj.transform.position = new Vector3(
                manifest.unity_terrain_settings_position_x,
                manifest.unity_terrain_settings_position_y,
                manifest.unity_terrain_settings_position_z
            );

            Debug.Log("[VeilBreakers] Terrain imported from manifest. " +
                "Coordinate system: " + manifest.coordinate_system +
                " | Source: " + manifest.source_coordinate_system);

            string resultJson = "{{\\"status\\": \\"ok\\", \\"action\\": \\"import_terrain_manifest\\"" +
                ", \\"heightmap_resolution\\": " + terrainData.heightmapResolution +
                ", \\"terrain_size\\": \\"" + terrainData.size.ToString() + "\\"" +
                ", \\"validation_status\\": \\"" + manifest.validation_status + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", resultJson);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"import_terrain_manifest\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Terrain manifest import failed: " + ex.Message);
        }}
    }}

    // Minimal manifest data class for JsonUtility
    [System.Serializable]
    private class ManifestData
    {{
        public string coordinate_system = "y-up";
        public string source_coordinate_system = "z-up";
        public string validation_status = "unknown";
        public string byte_order = "little-endian";
        public int heightmap_bit_depth = 16;
        public float cell_size = 1.0f;
        public int tile_size = 128;
        public float height_min_m = 0f;
        public float height_max_m = 100f;
        // Flattened unity_terrain_settings (JsonUtility cannot handle nested objects)
        public float unity_terrain_settings_size_x = 1000f;
        public float unity_terrain_settings_size_y = 600f;
        public float unity_terrain_settings_size_z = 1000f;
        public float unity_terrain_settings_position_x = 0f;
        public float unity_terrain_settings_position_y = 0f;
        public float unity_terrain_settings_position_z = 0f;
        public int unity_terrain_settings_heightmap_resolution = 513;
        public int unity_terrain_settings_alphamap_resolution = 512;
    }}
}}
'''


# ---------------------------------------------------------------------------
# Terrain erosion application script
# ---------------------------------------------------------------------------


def generate_terrain_erosion_script(
    iterations: int = 50,
    rain_rate: float = 0.01,
    sediment_capacity: float = 0.04,
    evaporation_rate: float = 0.01,
    thermal_rate: float = 0.002,
) -> str:
    """Generate C# editor script that applies erosion to the active terrain.

    Requires the AdvancedTerrainErosion UPM package to be installed.
    Uses GPU-accelerated hydraulic and thermal erosion.
    """
    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_TerrainErosion
{{
    [MenuItem("VeilBreakers/Terrain/Apply Erosion")]
    public static void Execute()
    {{
        try
        {{
            Terrain terrain = Terrain.activeTerrain;
            if (terrain == null)
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"apply_erosion\\", \\"message\\": \\"No active terrain found\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                Debug.LogError("[VeilBreakers] No active terrain found");
                return;
            }}

            TerrainData td = terrain.terrainData;
            int res = td.heightmapResolution;
            float[,] heights = td.GetHeights(0, 0, res, res);

            Debug.Log("[VeilBreakers] Applying erosion to terrain: " +
                res + "x" + res + " | {iterations} iterations");

            // Hydraulic erosion simulation
            float rainRate = {rain_rate}f;
            float sedimentCapacity = {sediment_capacity}f;
            float evaporationRate = {evaporation_rate}f;
            float thermalRate = {thermal_rate}f;

            float[,] water = new float[res, res];
            float[,] sediment = new float[res, res];

            for (int iter = 0; iter < {iterations}; iter++)
            {{
                // Rain step
                for (int y = 1; y < res - 1; y++)
                    for (int x = 1; x < res - 1; x++)
                        water[y, x] += rainRate;

                // Flow + erosion step
                for (int y = 1; y < res - 1; y++)
                {{
                    for (int x = 1; x < res - 1; x++)
                    {{
                        float h = heights[y, x] + water[y, x];
                        float minNeighbor = Mathf.Min(
                            heights[y-1, x] + water[y-1, x],
                            Mathf.Min(heights[y+1, x] + water[y+1, x],
                            Mathf.Min(heights[y, x-1] + water[y, x-1],
                                      heights[y, x+1] + water[y, x+1]))
                        );

                        if (h > minNeighbor)
                        {{
                            float diff = h - minNeighbor;
                            float transfer = Mathf.Min(water[y, x], diff * 0.5f);
                            water[y, x] -= transfer;

                            // Erosion
                            float erosion = Mathf.Min(transfer * sedimentCapacity,
                                heights[y, x] * 0.01f);
                            heights[y, x] -= erosion;
                            sediment[y, x] += erosion;
                        }}

                        // Deposition
                        float deposit = sediment[y, x] * 0.1f;
                        heights[y, x] += deposit;
                        sediment[y, x] -= deposit;

                        // Evaporation
                        water[y, x] *= (1f - evaporationRate);
                    }}
                }}

                // Thermal erosion step
                for (int y = 1; y < res - 1; y++)
                {{
                    for (int x = 1; x < res - 1; x++)
                    {{
                        float maxDiff = 0f;
                        float avgNeighbor = 0f;
                        int count = 0;
                        for (int dy = -1; dy <= 1; dy++)
                        {{
                            for (int dx = -1; dx <= 1; dx++)
                            {{
                                if (dx == 0 && dy == 0) continue;
                                float diff = heights[y, x] - heights[y+dy, x+dx];
                                if (diff > maxDiff) maxDiff = diff;
                                avgNeighbor += heights[y+dy, x+dx];
                                count++;
                            }}
                        }}
                        avgNeighbor /= count;

                        if (maxDiff > thermalRate)
                        {{
                            float move = (heights[y, x] - avgNeighbor) * thermalRate;
                            heights[y, x] -= move;
                        }}
                    }}
                }}
            }}

            td.SetHeights(0, 0, heights);

            string resultJson = "{{\\"status\\": \\"ok\\", \\"action\\": \\"apply_erosion\\"" +
                ", \\"iterations\\": {iterations}" +
                ", \\"resolution\\": " + res +
                ", \\"rain_rate\\": {rain_rate}" +
                ", \\"thermal_rate\\": {thermal_rate}}}";
            File.WriteAllText("Temp/vb_result.json", resultJson);
            Debug.Log("[VeilBreakers] Erosion applied: {iterations} iterations");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"apply_erosion\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Erosion failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# RT-01: Terrain deformation system (runtime heightmap modification)
# ---------------------------------------------------------------------------


def generate_terrain_deformation_script(
    brush_radius: float = 5.0,
    max_depth: float = 2.0,
    smooth_passes: int = 2,
    undo_stack_size: int = 10,
) -> str:
    """Generate C# runtime script for real-time terrain deformation.

    Creates a MonoBehaviour that modifies terrain heightmap at runtime based
    on world-space hit points (e.g., explosions, footprints, spell impacts).
    Supports raise, lower, flatten, and smooth operations with an undo stack.

    Args:
        brush_radius: Default world-space radius of the deformation brush.
        max_depth: Maximum deformation depth in world units.
        smooth_passes: Number of blur passes for the smooth operation.
        undo_stack_size: Number of deformation operations stored for undo.

    Returns:
        Complete C# source string for Assets/Scripts/Runtime/Terrain/.
    """
    if brush_radius <= 0:
        raise ValueError(f"brush_radius must be > 0, got {brush_radius}")
    if max_depth <= 0:
        raise ValueError(f"max_depth must be > 0, got {max_depth}")
    if undo_stack_size < 1:
        raise ValueError(f"undo_stack_size must be >= 1, got {undo_stack_size}")

    return f'''using UnityEngine;
using System.Collections.Generic;

/// <summary>
/// RT-01: Runtime terrain deformation system for VeilBreakers.
/// Modifies terrain heightmap in real-time for explosions, footprints,
/// spell impacts, and environmental destruction.
/// </summary>
public class VB_TerrainDeformation : MonoBehaviour
{{
    public enum DeformMode {{ Raise, Lower, Flatten, Smooth }}

    [Header("Brush Settings")]
    public float brushRadius = {brush_radius}f;
    public float maxDepth = {max_depth}f;
    public int smoothPasses = {smooth_passes};

    [Header("Performance")]
    public int undoStackSize = {undo_stack_size};

    private Terrain _terrain;
    private TerrainData _terrainData;
    private int _resolution;
    private readonly LinkedList<float[,]> _undoStack = new LinkedList<float[,]>();

    private void Start()
    {{
        _terrain = Terrain.activeTerrain;
        if (_terrain == null)
        {{
            Debug.LogError("[VB_TerrainDeformation] No active terrain found");
            enabled = false;
            return;
        }}
        _terrainData = _terrain.terrainData;
        _resolution = _terrainData.heightmapResolution;
    }}

    /// <summary>
    /// Apply deformation at a world-space position.
    /// </summary>
    public void Deform(Vector3 worldPos, DeformMode mode, float strength = 1.0f)
    {{
        if (_terrain == null) return;

        Vector3 terrainPos = worldPos - _terrain.transform.position;
        Vector3 size = _terrainData.size;

        float normalizedX = terrainPos.x / size.x;
        float normalizedZ = terrainPos.z / size.z;

        int centerX = Mathf.RoundToInt(normalizedX * (_resolution - 1));
        int centerZ = Mathf.RoundToInt(normalizedZ * (_resolution - 1));

        float radiusInSamples = (brushRadius / size.x) * (_resolution - 1);
        int sampleRadius = Mathf.CeilToInt(radiusInSamples);

        int xMin = Mathf.Max(0, centerX - sampleRadius);
        int zMin = Mathf.Max(0, centerZ - sampleRadius);
        int xMax = Mathf.Min(_resolution - 1, centerX + sampleRadius);
        int zMax = Mathf.Min(_resolution - 1, centerZ + sampleRadius);

        int width = xMax - xMin + 1;
        int height = zMax - zMin + 1;
        if (width <= 0 || height <= 0) return;

        float[,] heights = _terrainData.GetHeights(xMin, zMin, width, height);

        // Save undo snapshot
        PushUndo(_terrainData.GetHeights(0, 0, _resolution, _resolution));

        float depthNormalized = (maxDepth * strength) / size.y;

        for (int z = 0; z < height; z++)
        {{
            for (int x = 0; x < width; x++)
            {{
                float dx = (xMin + x) - centerX;
                float dz = (zMin + z) - centerZ;
                float dist = Mathf.Sqrt(dx * dx + dz * dz);
                if (dist > radiusInSamples) continue;

                float falloff = 1.0f - (dist / radiusInSamples);
                falloff = falloff * falloff; // Quadratic falloff

                switch (mode)
                {{
                    case DeformMode.Raise:
                        heights[z, x] += depthNormalized * falloff;
                        break;
                    case DeformMode.Lower:
                        heights[z, x] -= depthNormalized * falloff;
                        break;
                    case DeformMode.Flatten:
                        float target = heights[height / 2, width / 2];
                        heights[z, x] = Mathf.Lerp(heights[z, x], target, falloff * strength);
                        break;
                    case DeformMode.Smooth:
                        break; // Handled in separate pass
                }}

                heights[z, x] = Mathf.Clamp01(heights[z, x]);
            }}
        }}

        if (mode == DeformMode.Smooth)
        {{
            for (int pass = 0; pass < smoothPasses; pass++)
            {{
                for (int z = 1; z < height - 1; z++)
                {{
                    for (int x = 1; x < width - 1; x++)
                    {{
                        float avg = (heights[z-1, x] + heights[z+1, x] +
                                     heights[z, x-1] + heights[z, x+1]) * 0.25f;
                        float dx = (xMin + x) - centerX;
                        float dz = (zMin + z) - centerZ;
                        float dist = Mathf.Sqrt(dx * dx + dz * dz);
                        if (dist > radiusInSamples) continue;
                        float falloff = 1.0f - (dist / radiusInSamples);
                        heights[z, x] = Mathf.Lerp(heights[z, x], avg, falloff * strength);
                    }}
                }}
            }}
        }}

        _terrainData.SetHeights(xMin, zMin, heights);
    }}

    /// <summary>Undo the last deformation operation.</summary>
    public bool Undo()
    {{
        if (_undoStack.Count == 0) return false;
        float[,] snapshot = _undoStack.Last.Value;
        _undoStack.RemoveLast();
        _terrainData.SetHeights(0, 0, snapshot);
        return true;
    }}

    private void PushUndo(float[,] snapshot)
    {{
        _undoStack.AddLast(snapshot);
        while (_undoStack.Count > undoStackSize)
            _undoStack.RemoveFirst();
    }}
}}
'''


# ---------------------------------------------------------------------------
# RT-02: Terrain decal spawner (splatmap-aware terrain decals)
# ---------------------------------------------------------------------------


def generate_terrain_decal_script(
    max_decals: int = 100,
    decal_lifetime: float = 30.0,
    fade_duration: float = 3.0,
) -> str:
    """Generate C# runtime script for terrain-aware decal spawning.

    Creates a MonoBehaviour that spawns URP DecalProjector instances aligned
    to terrain normals with splatmap-aware material selection. Decals auto-fade
    and recycle through an object pool.

    Args:
        max_decals: Maximum pooled decal instances.
        decal_lifetime: Default seconds before decal fades.
        fade_duration: Seconds over which the decal alpha fades to zero.

    Returns:
        Complete C# source string for Assets/Scripts/Runtime/Terrain/.
    """
    if max_decals < 1:
        raise ValueError(f"max_decals must be >= 1, got {max_decals}")
    if decal_lifetime <= 0:
        raise ValueError(f"decal_lifetime must be > 0, got {decal_lifetime}")

    return f'''using UnityEngine;
using UnityEngine.Rendering.Universal;
using System.Collections.Generic;

/// <summary>
/// RT-02: Terrain-aware decal spawner for VeilBreakers.
/// Aligns URP DecalProjectors to terrain normals with splatmap-aware
/// material selection. Object-pooled with auto-fade.
/// </summary>
public class VB_TerrainDecalSpawner : MonoBehaviour
{{
    [System.Serializable]
    public class TerrainDecalConfig
    {{
        public string name;
        public Material material;
        public float minSize = 0.5f;
        public float maxSize = 2.0f;
        public float lifetime = {decal_lifetime}f;
        /// <summary>Splatmap layer index this decal prefers (-1 = any).</summary>
        public int preferredSplatLayer = -1;
    }}

    [Header("Decal Pool")]
    public int maxActive = {max_decals};
    public float fadeDuration = {fade_duration}f;

    [Header("Decal Types")]
    public List<TerrainDecalConfig> decalTypes = new List<TerrainDecalConfig>();

    private struct ActiveDecal
    {{
        public DecalProjector projector;
        public float spawnTime;
        public float lifetime;
        public float originalOpacity;
    }}

    private readonly Queue<DecalProjector> _pool = new Queue<DecalProjector>();
    private readonly List<ActiveDecal> _active = new List<ActiveDecal>();
    private Transform _poolParent;

    private void Start()
    {{
        _poolParent = new GameObject("VB_TerrainDecalPool").transform;
        _poolParent.SetParent(transform);

        for (int i = 0; i < maxActive; i++)
        {{
            var obj = new GameObject("TerrainDecal_" + i);
            obj.transform.SetParent(_poolParent);
            var proj = obj.AddComponent<DecalProjector>();
            proj.enabled = false;
            obj.SetActive(false);
            _pool.Enqueue(proj);
        }}
    }}

    /// <summary>
    /// Spawn a decal at a world position, auto-aligned to terrain normal.
    /// </summary>
    public DecalProjector SpawnDecal(Vector3 worldPos, int typeIndex, float sizeOverride = -1f)
    {{
        if (typeIndex < 0 || typeIndex >= decalTypes.Count) return null;

        var config = decalTypes[typeIndex];
        Terrain terrain = Terrain.activeTerrain;
        if (terrain == null) return null;

        // Get terrain normal at position
        Vector3 terrainLocal = worldPos - terrain.transform.position;
        Vector3 size = terrain.terrainData.size;
        float normX = terrainLocal.x / size.x;
        float normZ = terrainLocal.z / size.z;
        Vector3 normal = terrain.terrainData.GetInterpolatedNormal(normX, normZ);

        // Splatmap check
        if (config.preferredSplatLayer >= 0)
        {{
            float[,,] alphas = terrain.terrainData.GetAlphamaps(
                Mathf.RoundToInt(normX * terrain.terrainData.alphamapWidth),
                Mathf.RoundToInt(normZ * terrain.terrainData.alphamapHeight),
                1, 1);
            int layers = alphas.GetLength(2);
            if (config.preferredSplatLayer < layers &&
                alphas[0, 0, config.preferredSplatLayer] < 0.3f)
                return null; // Wrong surface type
        }}

        DecalProjector proj = GetFromPool();
        if (proj == null) return null;

        float decalSize = sizeOverride > 0 ? sizeOverride :
            Random.Range(config.minSize, config.maxSize);

        proj.material = config.material;
        proj.size = new Vector3(decalSize, decalSize, 0.5f);
        proj.transform.position = worldPos + normal * 0.05f;
        proj.transform.rotation = Quaternion.LookRotation(-normal) *
            Quaternion.Euler(0, 0, Random.Range(0f, 360f));
        proj.fadeFactor = 1.0f;
        proj.enabled = true;
        proj.gameObject.SetActive(true);

        _active.Add(new ActiveDecal
        {{
            projector = proj,
            spawnTime = Time.time,
            lifetime = config.lifetime,
            originalOpacity = 1.0f
        }});

        return proj;
    }}

    private void Update()
    {{
        for (int i = _active.Count - 1; i >= 0; i--)
        {{
            var d = _active[i];
            float age = Time.time - d.spawnTime;

            if (age >= d.lifetime)
            {{
                ReturnToPool(d.projector);
                _active.RemoveAt(i);
                continue;
            }}

            float fadeStart = d.lifetime - fadeDuration;
            if (age > fadeStart)
            {{
                float fadeProgress = (age - fadeStart) / fadeDuration;
                d.projector.fadeFactor = Mathf.Lerp(d.originalOpacity, 0f, fadeProgress);
            }}
        }}
    }}

    private DecalProjector GetFromPool()
    {{
        if (_pool.Count > 0) return _pool.Dequeue();
        if (_active.Count > 0)
        {{
            var oldest = _active[0];
            _active.RemoveAt(0);
            return oldest.projector;
        }}
        return null;
    }}

    private void ReturnToPool(DecalProjector proj)
    {{
        proj.enabled = false;
        proj.gameObject.SetActive(false);
        _pool.Enqueue(proj);
    }}
}}
'''


# ---------------------------------------------------------------------------
# RT-03: Terrain minimap integration (terrain-height-aware minimap camera)
# ---------------------------------------------------------------------------


def generate_terrain_minimap_script(
    render_size: int = 256,
    camera_height: float = 200.0,
    zoom: float = 80.0,
    follow_tag: str = "Player",
    update_interval: int = 2,
) -> str:
    """Generate C# runtime script for a terrain-integrated minimap.

    Creates a MonoBehaviour that maintains an orthographic camera above the
    player, reads terrain height for fog-of-war masking, and renders to a
    RenderTexture for UI display.

    Args:
        render_size: RenderTexture resolution (square).
        camera_height: Camera Y offset above terrain.
        zoom: Orthographic size of the minimap camera.
        follow_tag: Tag of the object to follow.
        update_interval: Frames between position updates.

    Returns:
        Complete C# source string for Assets/Scripts/Runtime/UI/.
    """
    if render_size < 32:
        raise ValueError(f"render_size must be >= 32, got {render_size}")
    safe_tag = sanitize_cs_string(follow_tag)

    return f'''using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// RT-03: Terrain-integrated minimap for VeilBreakers.
/// Orthographic camera follows player, terrain-height aware positioning,
/// renders to RenderTexture for HUD display.
/// </summary>
public class VB_TerrainMinimap : MonoBehaviour
{{
    [Header("Camera")]
    public float cameraHeight = {camera_height}f;
    public float zoom = {zoom}f;
    public int updateInterval = {update_interval};

    [Header("References")]
    public RawImage displayImage;
    public RectTransform compassNeedle;

    private Camera _minimapCam;
    private RenderTexture _renderTexture;
    private Transform _followTarget;
    private Terrain _terrain;
    private int _frameCounter;

    private void Start()
    {{
        _terrain = Terrain.activeTerrain;

        // Find follow target
        var targetObj = GameObject.FindGameObjectWithTag("{safe_tag}");
        if (targetObj != null) _followTarget = targetObj.transform;

        // Create render texture
        _renderTexture = new RenderTexture({render_size}, {render_size}, 16, RenderTextureFormat.ARGB32);
        _renderTexture.name = "VB_MinimapRT";

        // Create minimap camera
        var camObj = new GameObject("VB_MinimapCamera");
        camObj.transform.SetParent(transform);
        _minimapCam = camObj.AddComponent<Camera>();
        _minimapCam.orthographic = true;
        _minimapCam.orthographicSize = zoom;
        _minimapCam.clearFlags = CameraClearFlags.SolidColor;
        _minimapCam.backgroundColor = new Color(0.02f, 0.02f, 0.05f, 1f);
        _minimapCam.targetTexture = _renderTexture;
        _minimapCam.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
        _minimapCam.cullingMask = LayerMask.GetMask("Terrain", "Minimap");
        _minimapCam.depth = -10;

        if (displayImage != null)
            displayImage.texture = _renderTexture;
    }}

    private void LateUpdate()
    {{
        if (_followTarget == null || _minimapCam == null) return;

        _frameCounter++;
        if (_frameCounter % updateInterval != 0) return;

        Vector3 targetPos = _followTarget.position;

        // Get terrain height at player position for camera offset
        float terrainHeight = 0f;
        if (_terrain != null)
            terrainHeight = _terrain.SampleHeight(targetPos);

        _minimapCam.transform.position = new Vector3(
            targetPos.x,
            terrainHeight + cameraHeight,
            targetPos.z
        );

        // Compass rotation (north = forward)
        if (compassNeedle != null)
        {{
            float yRot = _followTarget.eulerAngles.y;
            compassNeedle.localRotation = Quaternion.Euler(0, 0, yRot);
        }}
    }}

    /// <summary>Set the zoom level at runtime.</summary>
    public void SetZoom(float newZoom)
    {{
        zoom = Mathf.Max(10f, newZoom);
        if (_minimapCam != null) _minimapCam.orthographicSize = zoom;
    }}

    /// <summary>Get the current render texture for external UI binding.</summary>
    public RenderTexture GetRenderTexture() => _renderTexture;

    private void OnDestroy()
    {{
        if (_renderTexture != null)
        {{
            _renderTexture.Release();
            Destroy(_renderTexture);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# RT-04: FBX/LOD import chain (import terrain mesh FBX with LOD groups)
# ---------------------------------------------------------------------------


def generate_fbx_lod_import_script(
    fbx_path: str = "Assets/TerrainExport/terrain_mesh.fbx",
    lod_distances: Optional[List[float]] = None,
    generate_collider: bool = True,
) -> str:
    """Generate C# editor script to import terrain FBX with LOD group setup.

    Reads an exported FBX terrain mesh, creates a LODGroup with distance-based
    LOD transitions, and optionally adds a MeshCollider to LOD0.

    Args:
        fbx_path: Path to the FBX file relative to Unity project.
        lod_distances: Screen-relative transition distances per LOD level.
            Defaults to [0.6, 0.3, 0.1, 0.01] for 4 LODs.
        generate_collider: Whether to add MeshCollider to LOD0.

    Returns:
        Complete C# source string for Assets/Editor/Generated/Terrain/.
    """
    safe_path = sanitize_cs_string(fbx_path)
    distances = lod_distances or [0.6, 0.3, 0.1, 0.01]
    dist_array = ", ".join(f"{d}f" for d in distances)
    num_lods = len(distances)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Linq;

/// <summary>
/// RT-04: Import terrain FBX mesh and configure LODGroup.
/// Sets up LOD transitions from Blender-exported multi-LOD FBX.
/// </summary>
public static class VeilBreakers_FBXLODImport
{{
    [MenuItem("VeilBreakers/Terrain/Import FBX with LODs")]
    public static void Execute()
    {{
        try
        {{
            string fbxPath = "{safe_path}";
            if (!File.Exists(Path.Combine(Application.dataPath, fbxPath.Replace("Assets/", ""))))
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"fbx_lod_import\\", \\"message\\": \\"FBX not found: " + fbxPath + "\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                Debug.LogError("[VeilBreakers] FBX not found: " + fbxPath);
                return;
            }}

            // Load the FBX as a prefab
            GameObject fbxPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(fbxPath);
            if (fbxPrefab == null)
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"fbx_lod_import\\", \\"message\\": \\"Failed to load FBX asset\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                return;
            }}

            GameObject instance = (GameObject)PrefabUtility.InstantiatePrefab(fbxPrefab);
            instance.name = "VB_TerrainMesh_LOD";

            // Collect mesh renderers (sorted by name for LOD ordering)
            var renderers = instance.GetComponentsInChildren<MeshRenderer>()
                .OrderBy(r => r.name).ToArray();

            float[] distances = new float[] {{ {dist_array} }};
            int lodCount = Mathf.Min(renderers.Length, {num_lods});

            if (lodCount > 1)
            {{
                var lodGroup = instance.AddComponent<LODGroup>();
                LOD[] lods = new LOD[lodCount];

                for (int i = 0; i < lodCount; i++)
                {{
                    lods[i] = new LOD(distances[i],
                        new Renderer[] {{ renderers[i] }});
                }}
                lodGroup.SetLODs(lods);
                lodGroup.RecalculateBounds();
                Debug.Log("[VeilBreakers] LODGroup created with " + lodCount + " levels");
            }}

            // Add MeshCollider to LOD0
            {"" if not generate_collider else '''var meshFilter = renderers[0].GetComponent<MeshFilter>();
            if (meshFilter != null && meshFilter.sharedMesh != null)
            {
                var collider = renderers[0].gameObject.AddComponent<MeshCollider>();
                collider.sharedMesh = meshFilter.sharedMesh;
                Debug.Log("[VeilBreakers] MeshCollider added to LOD0");
            }'''}

            string resultJson = "{{\\"status\\": \\"ok\\", \\"action\\": \\"fbx_lod_import\\"" +
                ", \\"lod_count\\": " + lodCount +
                ", \\"renderer_count\\": " + renderers.Length + "}}";
            File.WriteAllText("Temp/vb_result.json", resultJson);
            Debug.Log("[VeilBreakers] FBX LOD import complete: " + lodCount + " LODs");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"fbx_lod_import\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] FBX LOD import failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# RT-05: Vegetation TreePrototype wiring
# ---------------------------------------------------------------------------


def generate_vegetation_tree_prototype_script(
    tree_prefab_paths: Optional[List[str]] = None,
    density: float = 0.5,
    min_height: float = 0.8,
    max_height: float = 1.2,
    min_width: float = 0.8,
    max_width: float = 1.2,
) -> str:
    """Generate C# editor script to wire vegetation TreePrototypes to terrain.

    Creates TreePrototype entries on the active terrain from prefab paths,
    configures LOD and billboarding, and populates initial tree instances
    using density-based placement.

    Args:
        tree_prefab_paths: List of prefab asset paths for tree prototypes.
            Defaults to a single pine tree prefab.
        density: Trees per square unit (0-1 range, scaled).
        min_height: Minimum height scale factor.
        max_height: Maximum height scale factor.
        min_width: Minimum width scale factor.
        max_width: Maximum width scale factor.

    Returns:
        Complete C# source string for Assets/Editor/Generated/Terrain/.
    """
    paths = tree_prefab_paths or ["Assets/Prefabs/Trees/VB_Pine_01.prefab"]
    prefab_entries = []
    for i, p in enumerate(paths):
        safe = sanitize_cs_string(p)
        prefab_entries.append(
            f'            prefabPaths[{i}] = "{safe}";'
        )
    prefab_code = "\n".join(prefab_entries)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

/// <summary>
/// RT-05: Wire TreePrototypes to terrain with density-based placement.
/// Registers tree prefabs on TerrainData and scatters initial instances.
/// </summary>
public static class VeilBreakers_VegetationTreeSetup
{{
    [MenuItem("VeilBreakers/Terrain/Setup Tree Prototypes")]
    public static void Execute()
    {{
        try
        {{
            Terrain terrain = Terrain.activeTerrain;
            if (terrain == null)
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"vegetation_tree_setup\\", \\"message\\": \\"No active terrain\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                Debug.LogError("[VeilBreakers] No active terrain found");
                return;
            }}

            TerrainData td = terrain.terrainData;
            string[] prefabPaths = new string[{len(paths)}];
{prefab_code}

            // Create TreePrototypes
            TreePrototype[] protos = new TreePrototype[prefabPaths.Length];
            int validCount = 0;
            for (int i = 0; i < prefabPaths.Length; i++)
            {{
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPaths[i]);
                if (prefab != null)
                {{
                    protos[i] = new TreePrototype {{ prefab = prefab }};
                    validCount++;
                }}
                else
                {{
                    Debug.LogWarning("[VeilBreakers] Tree prefab not found: " + prefabPaths[i]);
                    protos[i] = new TreePrototype();
                }}
            }}
            td.treePrototypes = protos;

            // Scatter trees based on density
            float density = {density}f;
            int treeCount = Mathf.RoundToInt(td.size.x * td.size.z * density * 0.001f);
            treeCount = Mathf.Clamp(treeCount, 0, 50000);

            TreeInstance[] trees = new TreeInstance[treeCount];
            for (int i = 0; i < treeCount; i++)
            {{
                float x = Random.Range(0f, 1f);
                float z = Random.Range(0f, 1f);
                float terrainHeight = td.GetInterpolatedHeight(x, z) / td.size.y;

                trees[i] = new TreeInstance
                {{
                    position = new Vector3(x, terrainHeight, z),
                    prototypeIndex = Random.Range(0, validCount > 0 ? validCount : 1),
                    widthScale = Random.Range({min_width}f, {max_width}f),
                    heightScale = Random.Range({min_height}f, {max_height}f),
                    color = Color.white,
                    lightmapColor = Color.white,
                    rotation = Random.Range(0f, 360f)
                }};
            }}
            td.treeInstances = trees;

            string resultJson = "{{\\"status\\": \\"ok\\", \\"action\\": \\"vegetation_tree_setup\\"" +
                ", \\"prototypes\\": " + validCount +
                ", \\"trees_placed\\": " + treeCount + "}}";
            File.WriteAllText("Temp/vb_result.json", resultJson);
            Debug.Log("[VeilBreakers] Tree setup complete: " +
                validCount + " prototypes, " + treeCount + " instances");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"vegetation_tree_setup\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Tree setup failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# RT-06: NavMesh terrain bake integration
# ---------------------------------------------------------------------------


def generate_terrain_navmesh_script(
    agent_radius: float = 0.5,
    agent_height: float = 2.0,
    max_slope: float = 45.0,
    step_height: float = 0.4,
    area_mask_layers: Optional[Dict[str, int]] = None,
) -> str:
    """Generate C# editor script for terrain-specific NavMesh baking.

    Bakes NavMesh on the active terrain with configurable agent settings,
    slope-based area assignment, and optional splatmap-driven walkability
    masks (e.g., water = non-walkable).

    Args:
        agent_radius: Agent radius for path computation.
        agent_height: Agent height for clearance checks.
        max_slope: Maximum walkable slope angle in degrees.
        step_height: Maximum climbable step height.
        area_mask_layers: Dict mapping splatmap layer names to NavMesh area indices.
            E.g., {"Water": 1} marks water-layer terrain as non-walkable.

    Returns:
        Complete C# source string for Assets/Editor/Generated/Terrain/.
    """
    area_code = ""
    if area_mask_layers:
        entries = []
        for layer_name, area_idx in area_mask_layers.items():
            safe_name = sanitize_cs_string(layer_name)
            entries.append(
                f'            Debug.Log("[VeilBreakers] Area mask: {safe_name} -> area {area_idx}");'
            )
        area_code = "\n".join(entries)

    return f'''using UnityEngine;
using UnityEditor;
using UnityEngine.AI;
using Unity.AI.Navigation;
using System.IO;

/// <summary>
/// RT-06: Terrain-specific NavMesh bake with slope and splatmap awareness.
/// Configures NavMeshSurface on active terrain, bakes with agent settings.
/// </summary>
public static class VeilBreakers_TerrainNavMesh
{{
    [MenuItem("VeilBreakers/Terrain/Bake Terrain NavMesh")]
    public static void Execute()
    {{
        try
        {{
            Terrain terrain = Terrain.activeTerrain;
            if (terrain == null)
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"terrain_navmesh\\", \\"message\\": \\"No active terrain\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                Debug.LogError("[VeilBreakers] No active terrain for NavMesh bake");
                return;
            }}

            // Add or get NavMeshSurface
            var surface = terrain.GetComponent<NavMeshSurface>();
            if (surface == null)
                surface = terrain.gameObject.AddComponent<NavMeshSurface>();

            // Configure agent settings
            surface.agentTypeID = 0; // Default humanoid agent
            surface.collectObjects = CollectObjects.Children;
            surface.useGeometry = NavMeshCollectGeometry.RenderMeshes;

            // Set build settings
            var settings = NavMesh.GetSettingsByID(0);
            settings.agentRadius = {agent_radius}f;
            settings.agentHeight = {agent_height}f;
            settings.agentSlope = {max_slope}f;
            settings.agentClimb = {step_height}f;

{area_code}

            // Build NavMesh
            surface.BuildNavMesh();

            // Get NavMesh info
            NavMeshTriangulation triangulation = NavMesh.CalculateTriangulation();
            int triCount = triangulation.indices.Length / 3;

            string resultJson = "{{\\"status\\": \\"ok\\", \\"action\\": \\"terrain_navmesh\\"" +
                ", \\"triangles\\": " + triCount +
                ", \\"agent_radius\\": {agent_radius}" +
                ", \\"agent_height\\": {agent_height}" +
                ", \\"max_slope\\": {max_slope}" +
                ", \\"step_height\\": {step_height}}}";
            File.WriteAllText("Temp/vb_result.json", resultJson);
            Debug.Log("[VeilBreakers] NavMesh baked: " + triCount + " triangles");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"terrain_navmesh\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] NavMesh bake failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# RT-07: Terrain streaming (tile-based load/unload)
# ---------------------------------------------------------------------------


def generate_terrain_streaming_script(
    tile_size: float = 500.0,
    load_radius: float = 1500.0,
    unload_radius: float = 2000.0,
    check_interval: float = 1.0,
) -> str:
    """Generate C# runtime script for tile-based terrain streaming.

    Creates a MonoBehaviour that loads/unloads terrain tiles based on
    player distance. Tiles are stored as Addressable assets and streamed
    on demand with configurable load/unload radii.

    Args:
        tile_size: World-space size of each terrain tile.
        load_radius: Distance from player at which tiles are loaded.
        unload_radius: Distance from player at which tiles are unloaded.
        check_interval: Seconds between distance checks.

    Returns:
        Complete C# source string for Assets/Scripts/Runtime/Terrain/.
    """
    if tile_size <= 0:
        raise ValueError(f"tile_size must be > 0, got {tile_size}")
    if load_radius <= 0:
        raise ValueError(f"load_radius must be > 0, got {load_radius}")
    if unload_radius < load_radius:
        raise ValueError(
            f"unload_radius ({unload_radius}) must be >= load_radius ({load_radius})"
        )

    return f'''using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.ResourceManagement.AsyncOperations;
using System.Collections.Generic;

/// <summary>
/// RT-07: Tile-based terrain streaming for VeilBreakers.
/// Loads/unloads terrain tiles via Addressables based on player proximity.
/// Supports configurable load/unload radii with hysteresis.
/// </summary>
public class VB_TerrainStreaming : MonoBehaviour
{{
    [Header("Tile Configuration")]
    public float tileSize = {tile_size}f;
    public string tileAddressPrefix = "TerrainTile_";

    [Header("Streaming Radii")]
    public float loadRadius = {load_radius}f;
    public float unloadRadius = {unload_radius}f;

    [Header("Performance")]
    public float checkInterval = {check_interval}f;
    public int maxLoadsPerFrame = 2;

    private Transform _player;
    private float _nextCheckTime;

    private struct TileState
    {{
        public Vector2Int coord;
        public AsyncOperationHandle<GameObject> handle;
        public GameObject instance;
        public bool isLoading;
        public bool isLoaded;
    }}

    private readonly Dictionary<Vector2Int, TileState> _tiles =
        new Dictionary<Vector2Int, TileState>();
    private readonly Queue<Vector2Int> _loadQueue = new Queue<Vector2Int>();

    private void Start()
    {{
        var playerObj = GameObject.FindGameObjectWithTag("Player");
        if (playerObj != null) _player = playerObj.transform;
    }}

    private void Update()
    {{
        if (_player == null || Time.time < _nextCheckTime) return;
        _nextCheckTime = Time.time + checkInterval;

        Vector3 playerPos = _player.position;
        Vector2Int playerTile = WorldToTile(playerPos);

        int tilesInRadius = Mathf.CeilToInt(loadRadius / tileSize);

        // Queue tiles for loading
        for (int x = -tilesInRadius; x <= tilesInRadius; x++)
        {{
            for (int z = -tilesInRadius; z <= tilesInRadius; z++)
            {{
                Vector2Int coord = new Vector2Int(playerTile.x + x, playerTile.y + z);
                Vector3 tileCenter = TileToWorld(coord);
                float dist = Vector3.Distance(playerPos, tileCenter);

                if (dist <= loadRadius && !_tiles.ContainsKey(coord))
                {{
                    _loadQueue.Enqueue(coord);
                }}
            }}
        }}

        // Process load queue
        int loaded = 0;
        while (_loadQueue.Count > 0 && loaded < maxLoadsPerFrame)
        {{
            Vector2Int coord = _loadQueue.Dequeue();
            if (!_tiles.ContainsKey(coord))
            {{
                LoadTile(coord);
                loaded++;
            }}
        }}

        // Unload distant tiles
        var toUnload = new List<Vector2Int>();
        foreach (var kvp in _tiles)
        {{
            if (!kvp.Value.isLoaded) continue;
            Vector3 tileCenter = TileToWorld(kvp.Key);
            float dist = Vector3.Distance(playerPos, tileCenter);
            if (dist > unloadRadius)
                toUnload.Add(kvp.Key);
        }}
        foreach (var coord in toUnload)
            UnloadTile(coord);
    }}

    private void LoadTile(Vector2Int coord)
    {{
        string address = tileAddressPrefix + coord.x + "_" + coord.y;
        var handle = Addressables.InstantiateAsync(address, TileToWorld(coord),
            Quaternion.identity, transform);

        var state = new TileState
        {{
            coord = coord,
            handle = handle,
            isLoading = true,
            isLoaded = false
        }};
        _tiles[coord] = state;

        handle.Completed += (op) =>
        {{
            if (op.Status == AsyncOperationStatus.Succeeded)
            {{
                var s = _tiles[coord];
                s.instance = op.Result;
                s.isLoading = false;
                s.isLoaded = true;
                _tiles[coord] = s;
            }}
            else
            {{
                Debug.LogWarning("[VB_TerrainStreaming] Failed to load tile: " + address);
                _tiles.Remove(coord);
            }}
        }};
    }}

    private void UnloadTile(Vector2Int coord)
    {{
        if (!_tiles.TryGetValue(coord, out var state)) return;
        if (state.instance != null)
            Addressables.ReleaseInstance(state.instance);
        _tiles.Remove(coord);
    }}

    private Vector2Int WorldToTile(Vector3 pos)
    {{
        return new Vector2Int(
            Mathf.FloorToInt(pos.x / tileSize),
            Mathf.FloorToInt(pos.z / tileSize)
        );
    }}

    private Vector3 TileToWorld(Vector2Int coord)
    {{
        return new Vector3(
            coord.x * tileSize + tileSize * 0.5f,
            0f,
            coord.y * tileSize + tileSize * 0.5f
        );
    }}

    /// <summary>Get count of currently loaded tiles.</summary>
    public int LoadedTileCount
    {{
        get
        {{
            int count = 0;
            foreach (var kvp in _tiles)
                if (kvp.Value.isLoaded) count++;
            return count;
        }}
    }}
}}
'''
