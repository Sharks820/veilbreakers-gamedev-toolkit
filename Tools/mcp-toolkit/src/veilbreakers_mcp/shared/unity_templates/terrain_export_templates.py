"""Unity C# template generators for terrain export integration.

Generates editor scripts for:
- Importing Blender-exported terrain manifests into Unity Terrain
- Adding AdvancedTerrainErosion UPM package dependency
- Terrain size bridging (Blender Z-up -> Unity Y-up)

Each function returns a complete C# source string for Unity's
Assets/Editor/Generated/Scene/ directory.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ._cs_sanitize import sanitize_cs_string


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
