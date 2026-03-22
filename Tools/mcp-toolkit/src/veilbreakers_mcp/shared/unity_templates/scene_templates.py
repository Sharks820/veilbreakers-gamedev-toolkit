"""Scene C# template generators for Unity automation.

Each function returns a complete C# source string that can be written to
a Unity project's Assets/Editor/Generated/Scene/ directory. When compiled
by Unity, the scripts register as MenuItem commands under
"VeilBreakers/Scene/...".

All generated scripts write their result to Temp/vb_result.json so that
the Python MCP server can read back the outcome after execution.

Exports:
    generate_terrain_setup_script        -- SCENE-01: heightmap terrain with splatmaps
    generate_object_scatter_script       -- SCENE-02: density-based object scattering
    generate_lighting_setup_script       -- SCENE-03: lighting, fog, post-processing
    generate_navmesh_bake_script         -- SCENE-04: NavMesh bake with agent settings
    generate_animator_controller_script  -- SCENE-05: Animator Controller with blend trees
    generate_avatar_config_script        -- SCENE-06: avatar/humanoid configuration
    generate_animation_rigging_script    -- SCENE-07: TwoBoneIK, MultiAim constraints
"""

from __future__ import annotations

import re

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier


# ---------------------------------------------------------------------------
# Time-of-day lighting presets
# ---------------------------------------------------------------------------

_TIME_OF_DAY_PRESETS: dict[str, dict] = {
    "dawn": {
        "sun_rotation_x": 10.0,
        "sun_rotation_y": 170.0,
        "sun_color": [1.0, 0.7, 0.4],
        "ambient_color": [0.3, 0.25, 0.35],
        "fog_color": [0.6, 0.5, 0.55],
    },
    "noon": {
        "sun_rotation_x": 60.0,
        "sun_rotation_y": 170.0,
        "sun_color": [1.0, 0.97, 0.9],
        "ambient_color": [0.4, 0.45, 0.5],
        "fog_color": [0.7, 0.75, 0.8],
    },
    "dusk": {
        "sun_rotation_x": 5.0,
        "sun_rotation_y": 350.0,
        "sun_color": [1.0, 0.45, 0.2],
        "ambient_color": [0.25, 0.15, 0.2],
        "fog_color": [0.5, 0.3, 0.25],
    },
    "night": {
        "sun_rotation_x": -30.0,
        "sun_rotation_y": 170.0,
        "sun_color": [0.2, 0.25, 0.4],
        "ambient_color": [0.05, 0.05, 0.1],
        "fog_color": [0.05, 0.05, 0.1],
    },
    "overcast": {
        "sun_rotation_x": 45.0,
        "sun_rotation_y": 170.0,
        "sun_color": [0.7, 0.7, 0.72],
        "ambient_color": [0.35, 0.35, 0.38],
        "fog_color": [0.55, 0.55, 0.58],
    },
}


# ---------------------------------------------------------------------------
# SCENE-01: Terrain setup
# ---------------------------------------------------------------------------


def generate_terrain_setup_script(
    heightmap_path: str,
    size: tuple[float, float, float] = (1000, 600, 1000),
    resolution: int = 513,
    splatmap_layers: list[dict] | None = None,
) -> str:
    """Generate C# editor script that creates terrain from a RAW heightmap.

    Creates TerrainData with configurable resolution and size, reads a RAW
    heightmap, sets heights, optionally configures splatmap layers, and
    creates a Terrain GameObject.

    Args:
        heightmap_path: Path to the RAW heightmap file (relative to Unity project).
        size: Terrain size as (width, height, length).
        resolution: Heightmap resolution (e.g. 513, 1025).
        splatmap_layers: Optional list of dicts with "texture_path" and "tiling".

    Returns:
        Complete C# source string.
    """
    safe_heightmap_path = sanitize_cs_string(heightmap_path)

    splatmap_code = ""
    if splatmap_layers:
        layer_loads = ""
        for i, layer in enumerate(splatmap_layers):
            tex_path = sanitize_cs_string(layer.get("texture_path", ""))
            tiling = layer.get("tiling", 15.0)
            layer_loads += f"""
            var tex{i} = AssetDatabase.LoadAssetAtPath<Texture2D>("{tex_path}");
            var layer{i} = new TerrainLayer();
            layer{i}.diffuseTexture = tex{i};
            layer{i}.tileSize = new Vector2({tiling}f, {tiling}f);
            terrainLayers[{i}] = layer{i};"""

        splatmap_code = f"""
            // Splatmap layer configuration
            var terrainLayers = new TerrainLayer[{len(splatmap_layers)}];
            {layer_loads}
            terrainData.terrainLayers = terrainLayers;

            // Set default alphamaps (first layer covers everything)
            int alphaW = terrainData.alphamapWidth;
            int alphaH = terrainData.alphamapHeight;
            float[,,] alphamaps = new float[alphaW, alphaH, {len(splatmap_layers)}];
            for (int ay = 0; ay < alphaH; ay++)
                for (int ax = 0; ax < alphaW; ax++)
                    alphamaps[ay, ax, 0] = 1f;
            terrainData.SetAlphamaps(0, 0, alphamaps);"""

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_TerrainSetup
{{
    [MenuItem("VeilBreakers/Scene/Setup Terrain")]
    public static void Execute()
    {{
        try
        {{
            // Create TerrainData
            var terrainData = new TerrainData();
            terrainData.heightmapResolution = {resolution};
            terrainData.size = new Vector3({size[0]}f, {size[1]}f, {size[2]}f);

            // Load RAW heightmap
            string heightmapPath = Path.Combine(Application.dataPath, "{safe_heightmap_path}".Replace("Assets/", ""));
            if (File.Exists(heightmapPath))
            {{
                byte[] rawBytes = File.ReadAllBytes(heightmapPath);
                int res = {resolution};
                float[,] heights = new float[res, res];
                int byteIndex = 0;
                for (int y = 0; y < res; y++)
                {{
                    for (int x = 0; x < res; x++)
                    {{
                        if (byteIndex + 1 < rawBytes.Length)
                        {{
                            ushort value = (ushort)(rawBytes[byteIndex] | (rawBytes[byteIndex + 1] << 8));
                            heights[y, x] = value / 65535f;
                            byteIndex += 2;
                        }}
                    }}
                }}
                terrainData.SetHeights(0, 0, heights);
            }}
            else
            {{
                Debug.LogWarning("[VeilBreakers] Heightmap not found at: " + heightmapPath + ". Creating flat terrain.");
            }}
            {splatmap_code}

            // Create Terrain GameObject
            var terrainObj = Terrain.CreateTerrainGameObject(terrainData);
            terrainObj.name = "VB_Terrain";

            // Save TerrainData as asset
            string assetPath = "Assets/Terrain/Generated/VB_TerrainData.asset";
            string dir = Path.GetDirectoryName(assetPath);
            if (!AssetDatabase.IsValidFolder(dir))
            {{
                Directory.CreateDirectory(Path.Combine(Application.dataPath, "..", dir));
                AssetDatabase.Refresh();
            }}
            AssetDatabase.CreateAsset(terrainData, assetPath);
            AssetDatabase.SaveAssets();

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"setup_terrain\\", \\"terrain_name\\": \\"VB_Terrain\\", \\"resolution\\": {resolution}, \\"size\\": \\"{size[0]}x{size[1]}x{size[2]}\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Terrain setup completed.");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"setup_terrain\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Terrain setup failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# SCENE-02: Object scatter
# ---------------------------------------------------------------------------


def generate_object_scatter_script(
    prefab_paths: list[str],
    density: float = 0.5,
    min_slope: float = 0.0,
    max_slope: float = 45.0,
    min_altitude: float = 0.0,
    max_altitude: float = 1000.0,
    seed: int = 42,
) -> str:
    """Generate C# editor script for density-based object scattering on terrain.

    Uses grid-with-jitter sampling filtered by terrain slope and altitude.
    Instantiates prefabs with random rotation and scale variation, grouped
    under a parent GameObject.

    Args:
        prefab_paths: Paths to prefab assets to scatter.
        density: Scatter density (0.0 to 1.0). Controls grid spacing.
        min_slope: Minimum terrain slope in degrees (filter out flatter areas).
        max_slope: Maximum terrain slope in degrees (filter out steep areas).
        min_altitude: Minimum terrain height for placement.
        max_altitude: Maximum terrain height for placement.
        seed: Random seed for reproducible scattering.

    Returns:
        Complete C# source string.

    Raises:
        ValueError: If prefab_paths is empty.
    """
    if not prefab_paths:
        raise ValueError("prefab_paths must not be empty")

    prefab_array = ", ".join(f'"{p}"' for p in prefab_paths)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_ObjectScatter
{{
    [MenuItem("VeilBreakers/Scene/Scatter Objects")]
    public static void Execute()
    {{
        try
        {{
            string[] prefabPaths = new string[] {{ {prefab_array} }};
            float density = {density}f;
            float minSlope = {min_slope}f;
            float maxSlope = {max_slope}f;
            float minAltitude = {min_altitude}f;
            float maxAltitude = {max_altitude}f;
            int seed = {seed};

            // Find active terrain
            var terrain = Terrain.activeTerrain;
            if (terrain == null)
            {{
                Debug.LogError("[VeilBreakers] No active terrain found. Setup terrain first.");
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"scatter_objects\\", \\"message\\": \\"No active terrain found\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                return;
            }}

            var terrainData = terrain.terrainData;
            var terrainPos = terrain.transform.position;
            float terrainWidth = terrainData.size.x;
            float terrainLength = terrainData.size.z;

            // Load prefabs
            var prefabs = new GameObject[prefabPaths.Length];
            for (int i = 0; i < prefabPaths.Length; i++)
            {{
                prefabs[i] = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPaths[i]);
                if (prefabs[i] == null)
                    Debug.LogWarning("[VeilBreakers] Prefab not found: " + prefabPaths[i]);
            }}

            // Create parent container
            var parent = new GameObject("VB_ScatteredObjects");
            Undo.RegisterCreatedObjectUndo(parent, "Scatter Objects");

            // Grid-with-jitter sampling
            Random.InitState(seed);
            float spacing = Mathf.Lerp(20f, 2f, density);
            int placed = 0;

            for (float gx = 0; gx < terrainWidth; gx += spacing)
            {{
                for (float gz = 0; gz < terrainLength; gz += spacing)
                {{
                    float jitterX = Random.Range(-spacing * 0.4f, spacing * 0.4f);
                    float jitterZ = Random.Range(-spacing * 0.4f, spacing * 0.4f);
                    float wx = terrainPos.x + gx + jitterX;
                    float wz = terrainPos.z + gz + jitterZ;
                    Vector3 worldPos = new Vector3(wx, 0, wz);

                    // Sample height and slope
                    float height = terrain.SampleHeight(worldPos);
                    worldPos.y = height + terrainPos.y;

                    float nx = (wx - terrainPos.x) / terrainWidth;
                    float nz = (wz - terrainPos.z) / terrainLength;
                    nx = Mathf.Clamp01(nx);
                    nz = Mathf.Clamp01(nz);
                    Vector3 normal = terrainData.GetInterpolatedNormal(nx, nz);
                    float slopeDeg = Vector3.Angle(normal, Vector3.up);

                    // Filter by slope and altitude
                    if (slopeDeg < minSlope || slopeDeg > maxSlope) continue;
                    if (height < minAltitude || height > maxAltitude) continue;

                    // Pick random prefab
                    int prefabIdx = Random.Range(0, prefabs.Length);
                    if (prefabs[prefabIdx] == null) continue;

                    var instance = (GameObject)PrefabUtility.InstantiatePrefab(prefabs[prefabIdx]);
                    instance.transform.position = worldPos;
                    instance.transform.rotation = Quaternion.Euler(0, Random.Range(0f, 360f), 0);
                    float scale = Random.Range(0.8f, 1.2f);
                    instance.transform.localScale = Vector3.one * scale;
                    instance.transform.SetParent(parent.transform);
                    placed++;
                }}
            }}

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"scatter_objects\\", \\"objects_placed\\": " + placed + ", \\"density\\": {density}, \\"seed\\": {seed}}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Object scatter completed. Placed " + placed + " objects.");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"scatter_objects\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Object scatter failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# SCENE-03: Lighting setup
# ---------------------------------------------------------------------------


def generate_lighting_setup_script(
    sun_color: list[float] | None = None,
    sun_intensity: float = 1.0,
    ambient_color: list[float] | None = None,
    fog_enabled: bool = True,
    fog_color: list[float] | None = None,
    fog_density: float = 0.01,
    skybox_material: str = "",
    time_of_day: str = "noon",
) -> str:
    """Generate C# editor script for scene lighting, fog, and post-processing.

    Creates/configures a directional light (sun), sets RenderSettings for
    ambient light, fog, and skybox, and creates a Volume with dark fantasy
    post-processing (Bloom, Vignette, ColorAdjustments).

    Args:
        sun_color: RGB sun color as [r, g, b]. Overrides time_of_day preset.
        sun_intensity: Sun light intensity.
        ambient_color: RGB ambient color as [r, g, b]. Overrides time_of_day preset.
        fog_enabled: Whether to enable fog.
        fog_color: RGB fog color as [r, g, b]. Overrides time_of_day preset.
        fog_density: Fog density.
        skybox_material: Path to skybox material asset.
        time_of_day: Preset name: dawn, noon, dusk, night, overcast.

    Returns:
        Complete C# source string.
    """
    preset = _TIME_OF_DAY_PRESETS.get(time_of_day, _TIME_OF_DAY_PRESETS["noon"])

    sc = sun_color or preset["sun_color"]
    ac = ambient_color or preset["ambient_color"]
    fc = fog_color or preset["fog_color"]
    sun_rot_x = preset["sun_rotation_x"]
    sun_rot_y = preset["sun_rotation_y"]

    skybox_code = ""
    if skybox_material:
        skybox_code = f"""
            // Skybox
            var skyMat = AssetDatabase.LoadAssetAtPath<Material>("{skybox_material}");
            if (skyMat != null)
                RenderSettings.skybox = skyMat;"""

    return f'''using UnityEngine;
using UnityEditor;
using UnityEngine.Rendering;
using System.IO;
#if USING_URP
using UnityEngine.Rendering.Universal;
#elif USING_HDRP
using UnityEngine.Rendering.HighDefinition;
#endif

public static class VeilBreakers_LightingSetup
{{
    [MenuItem("VeilBreakers/Scene/Setup Lighting")]
    public static void Execute()
    {{
        try
        {{
            // Directional light (sun)
            var sunObj = new GameObject("VB_DirectionalLight");
            var light = sunObj.AddComponent<Light>();
            light.type = LightType.Directional;
            light.color = new Color({sc[0]}f, {sc[1]}f, {sc[2]}f);
            light.intensity = {sun_intensity}f;
            sunObj.transform.rotation = Quaternion.Euler({sun_rot_x}f, {sun_rot_y}f, 0f);

            // RenderSettings
            RenderSettings.ambientLight = new Color({ac[0]}f, {ac[1]}f, {ac[2]}f);
            RenderSettings.fog = {str(fog_enabled).lower()};
            RenderSettings.fogColor = new Color({fc[0]}f, {fc[1]}f, {fc[2]}f);
            RenderSettings.fogDensity = {fog_density}f;
            RenderSettings.fogMode = FogMode.ExponentialSquared;
            {skybox_code}

            // Post-processing Volume (dark fantasy preset)
            var volumeObj = new GameObject("VB_PostProcessVolume");
            var volume = volumeObj.AddComponent<Volume>();
            volume.isGlobal = true;
            volume.priority = 1;
            var profile = ScriptableObject.CreateInstance<VolumeProfile>();
            volume.profile = profile;

            // Bloom
            var bloom = profile.Add<Bloom>();
            bloom.active = true;
            bloom.intensity.Override(1.2f);
            bloom.threshold.Override(0.9f);
            bloom.scatter.Override(0.7f);

            // Vignette
            var vignette = profile.Add<Vignette>();
            vignette.active = true;
            vignette.intensity.Override(0.35f);
            vignette.smoothness.Override(0.3f);

            // ColorAdjustments (dark fantasy tone)
            var colorAdj = profile.Add<ColorAdjustments>();
            colorAdj.active = true;
            colorAdj.contrast.Override(15f);
            colorAdj.saturation.Override(-10f);

            // Save profile
            string profilePath = "Assets/Settings/Generated/VB_LightingProfile.asset";
            string dir = Path.GetDirectoryName(profilePath);
            if (!AssetDatabase.IsValidFolder(dir))
            {{
                Directory.CreateDirectory(Path.Combine(Application.dataPath, "..", dir));
                AssetDatabase.Refresh();
            }}
            AssetDatabase.CreateAsset(profile, profilePath);
            AssetDatabase.SaveAssets();

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"setup_lighting\\", \\"time_of_day\\": \\"{time_of_day}\\", \\"fog_enabled\\": {str(fog_enabled).lower()}, \\"fog_density\\": {fog_density}}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Lighting setup completed ({time_of_day}).");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"setup_lighting\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Lighting setup failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# SCENE-04: NavMesh bake
# ---------------------------------------------------------------------------


def generate_navmesh_bake_script(
    agent_radius: float = 0.5,
    agent_height: float = 2.0,
    max_slope: float = 45.0,
    step_height: float = 0.4,
    nav_links: list[dict] | None = None,
) -> str:
    """Generate C# editor script that bakes NavMesh with agent settings.

    Adds NavMeshSurface to the scene, configures agent parameters, calls
    BuildNavMesh(), and optionally creates NavMeshLinks.

    Args:
        agent_radius: Agent radius for NavMesh baking.
        agent_height: Agent height for NavMesh baking.
        max_slope: Maximum walkable slope in degrees.
        step_height: Maximum step height the agent can climb.
        nav_links: Optional list of dicts with "start", "end", "width" keys.

    Returns:
        Complete C# source string.
    """
    link_code = ""
    if nav_links:
        link_entries = ""
        for i, link in enumerate(nav_links):
            s = link.get("start", [0, 0, 0])
            e = link.get("end", [0, 0, 0])
            w = link.get("width", 1.0)
            link_entries += f"""
            var linkObj{i} = new GameObject("VB_NavLink_{i}");
            var navLink{i} = linkObj{i}.AddComponent<NavMeshLink>();
            navLink{i}.startPoint = new Vector3({s[0]}f, {s[1]}f, {s[2]}f);
            navLink{i}.endPoint = new Vector3({e[0]}f, {e[1]}f, {e[2]}f);
            navLink{i}.width = {w}f;"""

        link_code = f"""
            // NavMesh Links
            {link_entries}"""

    return f'''using UnityEngine;
using UnityEditor;
using UnityEngine.AI;
using Unity.AI.Navigation;
using System.IO;

public static class VeilBreakers_NavMeshBake
{{
    [MenuItem("VeilBreakers/Scene/Bake NavMesh")]
    public static void Execute()
    {{
        try
        {{
            // Find terrain or scene root for NavMesh surface
            GameObject navTarget = null;
            var terrain = Terrain.activeTerrain;
            if (terrain != null)
                navTarget = terrain.gameObject;
            else
            {{
                navTarget = new GameObject("VB_NavMeshRoot");
            }}

            // Add or get NavMeshSurface
            var surface = navTarget.GetComponent<NavMeshSurface>();
            if (surface == null)
                surface = navTarget.AddComponent<NavMeshSurface>();

            // Create custom agent settings (NavMeshBuildSettings is a struct;
            // GetSettingsByID returns a copy, so we must create a new entry
            // and assign its agentTypeID back to the surface).
            var settings = NavMesh.CreateSettings();
            settings.agentRadius = {agent_radius}f;
            settings.agentHeight = {agent_height}f;
            settings.agentSlope = {max_slope}f;
            settings.agentClimb = {step_height}f;
            surface.agentTypeID = settings.agentTypeID;

            // Build NavMesh
            surface.BuildNavMesh();
            {link_code}

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"bake_navmesh\\", \\"agent_radius\\": {agent_radius}, \\"agent_height\\": {agent_height}, \\"max_slope\\": {max_slope}}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] NavMesh bake completed.");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"bake_navmesh\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] NavMesh bake failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# SCENE-05: Animator Controller
# ---------------------------------------------------------------------------


def generate_animator_controller_script(
    name: str,
    states: list[dict],
    transitions: list[dict],
    parameters: list[dict],
    blend_trees: list[dict] | None = None,
) -> str:
    """Generate C# editor script that creates an Animator Controller.

    Builds a complete AnimatorController with states, transitions, parameters,
    and optional blend trees.

    Args:
        name: Controller name (used for file path and asset name).
        states: List of dicts with "name" and optional "motion_path".
        transitions: List of dicts with "from_state", "to_state", "conditions",
                     and "has_exit_time".
        parameters: List of dicts with "name" and "type" (float/int/bool/trigger).
        blend_trees: Optional list of dicts with "name", "blend_param", and
                     "children" (list of {"motion_path", "threshold"}).

    Returns:
        Complete C# source string.

    Raises:
        ValueError: If states list is empty.
    """
    if not states:
        raise ValueError("states must not be empty -- at least one state is required")

    # Build parameter addition code
    param_code = ""
    param_type_map = {
        "float": "AnimatorControllerParameterType.Float",
        "int": "AnimatorControllerParameterType.Int",
        "bool": "AnimatorControllerParameterType.Bool",
        "trigger": "AnimatorControllerParameterType.Trigger",
    }
    for param in parameters:
        p_name = param["name"]
        p_type = param_type_map.get(param.get("type", "float"), "AnimatorControllerParameterType.Float")
        param_code += f"""
            controller.AddParameter("{p_name}", {p_type});"""

    # Build state creation code
    state_code = ""
    for i, state in enumerate(states):
        s_name = state["name"]
        motion_path = state.get("motion_path", "")
        state_code += f"""
            var state_{i} = rootStateMachine.AddState("{s_name}");"""
        if motion_path:
            state_code += f"""
            var motion_{i} = AssetDatabase.LoadAssetAtPath<AnimationClip>("{motion_path}");
            if (motion_{i} != null) state_{i}.motion = motion_{i};"""

    # Build state name-to-index lookup
    state_index = {s["name"]: i for i, s in enumerate(states)}

    # Build transition code
    trans_code = ""
    for t in transitions:
        from_s = t.get("from_state", "")
        to_s = t.get("to_state", "")
        has_exit = "true" if t.get("has_exit_time", True) else "false"
        from_idx = state_index.get(from_s)
        to_idx = state_index.get(to_s)
        if from_idx is not None and to_idx is not None:
            safe_from = sanitize_cs_identifier(from_s)
            safe_to = sanitize_cs_identifier(to_s)
            trans_code += f"""
            var trans_{safe_from}_{safe_to} = state_{from_idx}.AddTransition(state_{to_idx});
            trans_{safe_from}_{safe_to}.hasExitTime = {has_exit};"""
            for cond in t.get("conditions", []):
                c_param = cond.get("param", "")
                c_mode = cond.get("mode", "Greater")
                c_thresh = cond.get("threshold", 0)
                trans_code += f"""
            trans_{safe_from}_{safe_to}.AddCondition(AnimatorConditionMode.{c_mode}, {c_thresh}f, "{c_param}");"""

    # Build blend tree code
    bt_code = ""
    if blend_trees:
        for bt in blend_trees:
            bt_name = bt["name"]
            bt_param = bt["blend_param"]
            children = bt.get("children", [])
            bt_code += f"""
            // Blend tree: {bt_name}
            BlendTree blendTree_{bt_name};
            controller.CreateBlendTreeInController("{bt_name}", out blendTree_{bt_name});
            blendTree_{bt_name}.blendParameter = "{bt_param}";"""
            for child in children:
                m_path = child.get("motion_path", "")
                thresh = child.get("threshold", 0.0)
                bt_code += f"""
            var btMotion_{bt_name}_{thresh} = AssetDatabase.LoadAssetAtPath<AnimationClip>("{m_path}");
            if (btMotion_{bt_name}_{thresh} != null)
                blendTree_{bt_name}.AddChild(btMotion_{bt_name}_{thresh}, {thresh}f);"""

    safe_ctrl_name = sanitize_cs_identifier(name.replace(" ", "_").replace("-", "_"))

    return f'''using UnityEngine;
using UnityEditor;
using UnityEditor.Animations;
using System.IO;

public static class VeilBreakers_AnimatorController_{safe_ctrl_name}
{{
    [MenuItem("VeilBreakers/Scene/Create Animator/{sanitize_cs_string(name)}")]
    public static void Execute()
    {{
        try
        {{
            string controllerPath = "Assets/Animations/{sanitize_cs_string(name)}.controller";
            string dir = Path.GetDirectoryName(controllerPath);
            if (!AssetDatabase.IsValidFolder(dir))
            {{
                Directory.CreateDirectory(Path.Combine(Application.dataPath, "..", dir));
                AssetDatabase.Refresh();
            }}

            var controller = AnimatorController.CreateAnimatorControllerAtPath(controllerPath);

            // Add parameters
            {param_code}

            // State machine
            var rootStateMachine = controller.layers[0].stateMachine;

            // Add states
            {state_code}

            // Add transitions
            {trans_code}

            // Blend trees
            {bt_code}

            AssetDatabase.SaveAssets();

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"create_animator\\", \\"name\\": \\"{sanitize_cs_string(name)}\\", \\"controller_path\\": \\"" + controllerPath + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Animator controller '{sanitize_cs_string(name)}' created at: " + controllerPath);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_animator\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Animator controller creation failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# SCENE-06: Avatar configuration
# ---------------------------------------------------------------------------


def generate_avatar_config_script(
    fbx_path: str,
    animation_type: str = "Humanoid",
    bone_mapping: dict | None = None,
) -> str:
    """Generate C# editor script to configure avatar/animation type on an FBX.

    Sets ModelImporter.animationType to Humanoid or Generic, optionally
    configures bone mapping for Humanoid avatars.

    Args:
        fbx_path: Path to FBX file (relative to Unity project).
        animation_type: "Humanoid" or "Generic".
        bone_mapping: Optional dict mapping Unity bone names to model bone names.

    Returns:
        Complete C# source string.
    """
    anim_type_enum = "ModelImporterAnimationType.Human" if animation_type == "Humanoid" else "ModelImporterAnimationType.Generic"
    safe_fbx_path = sanitize_cs_string(fbx_path)

    bone_code = ""
    if bone_mapping and animation_type == "Humanoid":
        bone_entries = ""
        for unity_bone, model_bone in bone_mapping.items():
            safe_ub = sanitize_cs_string(unity_bone)
            safe_mb = sanitize_cs_string(model_bone)
            bone_entries += f"""
                new HumanBone {{ humanName = "{safe_ub}", boneName = "{safe_mb}", limit = new HumanLimit {{ useDefaultValues = true }} }},"""

        bone_code = f"""
            // Configure bone mapping
            var humanDescription = importer.humanDescription;
            humanDescription.human = new HumanBone[]
            {{
                {bone_entries}
            }};
            importer.humanDescription = humanDescription;"""

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_AvatarConfig
{{
    [MenuItem("VeilBreakers/Scene/Configure Avatar")]
    public static void Execute()
    {{
        try
        {{
            string fbxPath = "{safe_fbx_path}";
            var importer = AssetImporter.GetAtPath(fbxPath) as ModelImporter;

            if (importer == null)
            {{
                Debug.LogError("[VeilBreakers] ModelImporter not found at: " + fbxPath);
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"configure_avatar\\", \\"message\\": \\"ModelImporter not found at: " + fbxPath + "\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                return;
            }}

            // Set animation type
            importer.animationType = {anim_type_enum};
            {bone_code}

            // Apply and reimport
            importer.SaveAndReimport();

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"configure_avatar\\", \\"fbx_path\\": \\"{safe_fbx_path}\\", \\"animation_type\\": \\"{animation_type}\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Avatar configured: {safe_fbx_path} as {animation_type}");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"configure_avatar\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Avatar configuration failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# SCENE-07: Animation Rigging
# ---------------------------------------------------------------------------


def generate_animation_rigging_script(
    rig_name: str,
    constraints: list[dict],
) -> str:
    """Generate C# editor script to set up Animation Rigging constraints.

    Creates a RigBuilder, Rig, and constraint components (TwoBoneIKConstraint,
    MultiAimConstraint) with full source/target configuration.

    Args:
        rig_name: Name for the rig GameObject.
        constraints: List of constraint dicts. Each must have "type" key:
            - "two_bone_ik": requires target_path, root_path, mid_path, tip_path
            - "multi_aim": requires target_path, source_paths, weight

    Returns:
        Complete C# source string.

    Raises:
        ValueError: If constraints list is empty.
    """
    if not constraints:
        raise ValueError("constraints must not be empty -- at least one constraint is required")

    constraint_code = ""
    for i, c in enumerate(constraints):
        c_type = c.get("type", "")
        if c_type == "two_bone_ik":
            target = c.get("target_path", "IKTarget")
            root = c.get("root_path", "UpperArm")
            mid = c.get("mid_path", "Forearm")
            tip = c.get("tip_path", "Hand")
            constraint_code += f"""
            // TwoBoneIK constraint #{i}
            var ikObj_{i} = new GameObject("IK_{i}");
            ikObj_{i}.transform.SetParent(rigObj.transform);
            var ik_{i} = ikObj_{i}.AddComponent<TwoBoneIKConstraint>();
            ik_{i}.data.root = FindTransformRecursive(targetRoot, "{root}");
            ik_{i}.data.mid = FindTransformRecursive(targetRoot, "{mid}");
            ik_{i}.data.tip = FindTransformRecursive(targetRoot, "{tip}");
            var ikTarget_{i} = new GameObject("{target}");
            ikTarget_{i}.transform.SetParent(rigObj.transform);
            ik_{i}.data.target = ikTarget_{i}.transform;"""

        elif c_type == "multi_aim":
            target = c.get("target_path", "Head")
            sources = c.get("source_paths", [])
            weight = c.get("weight", 1.0)
            constraint_code += f"""
            // MultiAim constraint #{i}
            var aimObj_{i} = new GameObject("Aim_{i}");
            aimObj_{i}.transform.SetParent(rigObj.transform);
            var aim_{i} = aimObj_{i}.AddComponent<MultiAimConstraint>();
            aim_{i}.data.constrainedObject = FindTransformRecursive(targetRoot, "{target}");
            var sources_{i} = new WeightedTransformArray();"""
            for src in sources:
                constraint_code += f"""
            var srcObj_{i}_{src} = new GameObject("{src}");
            srcObj_{i}_{src}.transform.SetParent(rigObj.transform);
            sources_{i}.Add(new WeightedTransform(srcObj_{i}_{src}.transform, {weight}f));"""
            constraint_code += f"""
            aim_{i}.data.sourceObjects = sources_{i};"""

    return f'''using UnityEngine;
using UnityEditor;
using UnityEngine.Animations.Rigging;
using System.IO;

public static class VeilBreakers_AnimationRigging_{sanitize_cs_identifier(rig_name.replace(" ", "_").replace("-", "_"))}
{{
    [MenuItem("VeilBreakers/Scene/Setup Animation Rigging/{sanitize_cs_string(rig_name)}")]
    public static void Execute()
    {{
        try
        {{
            // Find selected or first root object
            var targetRoot = Selection.activeGameObject;
            if (targetRoot == null)
            {{
                Debug.LogError("[VeilBreakers] Select a GameObject to add rigging to.");
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"setup_animation_rigging\\", \\"message\\": \\"No GameObject selected\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                return;
            }}

            // Add RigBuilder to root
            var rigBuilder = targetRoot.GetComponent<RigBuilder>();
            if (rigBuilder == null)
                rigBuilder = targetRoot.AddComponent<RigBuilder>();

            // Create Rig child object
            var rigObj = new GameObject("{rig_name}");
            rigObj.transform.SetParent(targetRoot.transform);
            var rig = rigObj.AddComponent<Rig>();
            rigBuilder.layers.Add(new RigLayer(rig));

            // Add constraints
            {constraint_code}

            // Rebuild
            rigBuilder.Build();

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"setup_animation_rigging\\", \\"rig_name\\": \\"{rig_name}\\", \\"constraint_count\\": {len(constraints)}}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Animation rigging '{rig_name}' setup completed with {len(constraints)} constraint(s).");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"setup_animation_rigging\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Animation rigging setup failed: " + ex.Message);
        }}
    }}

    private static Transform FindTransformRecursive(GameObject root, string name)
    {{
        if (root.name == name) return root.transform;
        foreach (Transform child in root.GetComponentsInChildren<Transform>())
        {{
            if (child.name == name) return child;
        }}
        Debug.LogWarning("[VeilBreakers] Transform not found: " + name);
        return null;
    }}
}}
'''
