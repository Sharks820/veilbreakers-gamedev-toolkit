"""C# editor script template generators for Unity project settings automation.

Each function returns a complete C# source string that can be written to
a Unity project's Assets/Editor/Generated/Settings/ directory. When compiled
by Unity, the scripts register as MenuItem commands under
"VeilBreakers/Settings/...".

All generated scripts write their result to Temp/vb_result.json so that
the Python MCP server can read back the outcome after execution.

Exports:
    generate_physics_settings_script      -- EDIT-04: physics layers, collision matrix, gravity
    generate_physics_material_script      -- EDIT-04: create PhysicMaterial asset
    generate_player_settings_script       -- EDIT-05: company, product, scripting backend, color space
    generate_build_settings_script        -- EDIT-06: scene list, platform switch, scripting defines
    generate_quality_settings_script      -- EDIT-07: quality levels (shadow, texture, AA, VSync, LOD)
    generate_package_install_script       -- EDIT-08: install from UPM, OpenUPM, or git
    generate_package_remove_script        -- EDIT-08: remove a package
    generate_tag_layer_script             -- EDIT-09: create tags, layers, sorting layers
    generate_tag_layer_sync_script        -- EDIT-09: sync tags/layers from Constants.cs
    generate_time_settings_script         -- EDIT-11: fixed timestep, max timestep, time scale
    generate_graphics_settings_script     -- EDIT-11: render pipeline asset, fog settings
"""

from __future__ import annotations

import hashlib
import re


def _sanitize_cs_string(value: str) -> str:
    """Escape a value for safe embedding inside a C# string literal.

    Prevents C# code injection by escaping backslashes, quotes, and
    newlines. This is critical for any user-supplied string that will
    appear between double quotes in generated C# code.

    Args:
        value: Raw string value.

    Returns:
        Escaped string safe for C# string literal interpolation.
    """
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    return value


def _sanitize_cs_identifier(value: str) -> str:
    """Sanitize a value for use as a C# identifier (class name, method name).

    Strips all characters that are not alphanumeric or underscore.

    Args:
        value: Raw name string.

    Returns:
        Sanitized identifier safe for C# class/method names.
    """
    return re.sub(r"[^a-zA-Z0-9_]", "", value)


# ---------------------------------------------------------------------------
# EDIT-04: Physics settings
# ---------------------------------------------------------------------------


def generate_physics_settings_script(
    collision_matrix: dict[str, list[str]] | None = None,
    gravity: list[float] | None = None,
) -> str:
    """Generate C# editor script for configuring physics layers and collision matrix.

    Args:
        collision_matrix: Dict mapping layer name to list of layers it should
            collide with. Pairs NOT in the matrix will have collisions ignored.
        gravity: Optional [x, y, z] gravity vector override.

    Returns:
        Complete C# source string.
    """
    # Build collision matrix configuration code
    collision_code = ""
    if collision_matrix:
        # Build the set of layer names involved
        layer_names: set[str] = set()
        for layer, targets in collision_matrix.items():
            layer_names.add(layer)
            for t in targets:
                layer_names.add(t)

        safe_layers = sorted(layer_names)
        # Build C# code to resolve layers and set collision
        layer_resolves = ""
        for name in safe_layers:
            safe_name = _sanitize_cs_identifier(name)
            safe_str = _sanitize_cs_string(name)
            layer_resolves += f'            int layer_{safe_name} = LayerMask.NameToLayer("{safe_str}");\n'
            layer_resolves += f'            if (layer_{safe_name} == -1) {{ warnings.Add("Layer not found: {safe_str}"); }}\n'

        # Build collision enable/disable pairs
        collision_pairs = ""
        for i, name_a in enumerate(safe_layers):
            for name_b in safe_layers[i:]:
                safe_a = _sanitize_cs_identifier(name_a)
                safe_b = _sanitize_cs_identifier(name_b)
                # Check if this pair should collide
                a_collides_b = name_b in collision_matrix.get(name_a, [])
                b_collides_a = name_a in collision_matrix.get(name_b, [])
                should_collide = a_collides_b or b_collides_a
                ignore = "false" if should_collide else "true"
                collision_pairs += f'            if (layer_{safe_a} != -1 && layer_{safe_b} != -1) Physics.IgnoreLayerCollision(layer_{safe_a}, layer_{safe_b}, {ignore});\n'

        collision_code = f"""
            var warnings = new System.Collections.Generic.List<string>();
            // Resolve layer indices
{layer_resolves}
            // Configure collision matrix
{collision_pairs}
            configuredLayers = {len(safe_layers)};"""

    gravity_code = ""
    if gravity and len(gravity) >= 3:
        gravity_code = f"""
            // Set custom gravity (static setting, no undo target needed)
            Physics.gravity = new Vector3({gravity[0]}f, {gravity[1]}f, {gravity[2]}f);"""

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_ConfigurePhysics
{{
    [MenuItem("VeilBreakers/Settings/Configure Physics")]
    public static void Execute()
    {{
        try
        {{
            int configuredLayers = 0;
            Undo.SetCurrentGroupName("VeilBreakers Configure Physics");
{collision_code}
{gravity_code}

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"configure_physics\\", "
                + "\\"configured_layers\\": " + configuredLayers + ", "
                + "\\"changed_assets\\": [\\"ProjectSettings/Physics2DSettings.asset\\", \\"ProjectSettings/DynamicsManager.asset\\"], "
                + "\\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Physics configuration completed. Layers configured: " + configuredLayers);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"configure_physics\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Physics configuration failed: " + ex.Message);
        }}
    }}
}}
'''


def generate_physics_material_script(
    name: str,
    friction: float = 0.5,
    bounciness: float = 0.0,
    friction_combine: str = "Average",
    bounce_combine: str = "Average",
) -> str:
    """Generate C# editor script to create a PhysicMaterial asset.

    Args:
        name: Material name.
        friction: Dynamic friction coefficient (0-1).
        bounciness: Bounciness coefficient (0-1).
        friction_combine: Friction combine mode (Average/Minimum/Multiply/Maximum).
        bounce_combine: Bounce combine mode (Average/Minimum/Multiply/Maximum).

    Returns:
        Complete C# source string.
    """
    safe_name = _sanitize_cs_string(name)
    safe_id = _sanitize_cs_identifier(name)
    safe_friction_combine = _sanitize_cs_identifier(friction_combine)
    safe_bounce_combine = _sanitize_cs_identifier(bounce_combine)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_CreatePhysicsMaterial_{safe_id}
{{
    [MenuItem("VeilBreakers/Settings/Create Physics Material")]
    public static void Execute()
    {{
        try
        {{
            // Create the PhysicMaterial
            var material = new PhysicMaterial("{safe_name}");
            material.dynamicFriction = {friction}f;
            material.staticFriction = {friction}f;
            material.bounciness = {bounciness}f;
            material.frictionCombine = PhysicMaterialCombine.{safe_friction_combine};
            material.bounceCombine = PhysicMaterialCombine.{safe_bounce_combine};

            // Ensure directory exists
            string dir = "Assets/Physics Materials";
            if (!AssetDatabase.IsValidFolder(dir))
            {{
                AssetDatabase.CreateFolder("Assets", "Physics Materials");
            }}

            // Save as asset
            string assetPath = dir + "/{safe_name}.physicMaterial";
            AssetDatabase.CreateAsset(material, assetPath);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            Undo.RegisterCreatedObjectUndo(material, "Create PhysicMaterial {safe_name}");

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"create_physics_material\\", "
                + "\\"material_name\\": \\"{safe_name}\\", "
                + "\\"asset_path\\": \\"" + assetPath + "\\", "
                + "\\"changed_assets\\": [\\"" + assetPath + "\\"], "
                + "\\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] PhysicMaterial created: " + assetPath);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_physics_material\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] PhysicMaterial creation failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# EDIT-05: Player Settings
# ---------------------------------------------------------------------------


def generate_player_settings_script(
    company: str = "",
    product: str = "",
    color_space: str = "",
    scripting_backend: str = "",
    api_level: str = "",
    icon_path: str = "",
    splash_path: str = "",
    default_screen_width: int = 0,
    default_screen_height: int = 0,
) -> str:
    """Generate C# editor script to configure Unity Player Settings.

    Only sets non-empty/non-zero parameters. Skips empty strings and zero ints.

    Args:
        company: Company name.
        product: Product name.
        color_space: "Linear" or "Gamma".
        scripting_backend: "IL2CPP" or "Mono2x".
        api_level: "NET_Standard" or "NET_Unity_4_8".
        icon_path: Path to icon texture asset.
        splash_path: Path to splash screen logo asset.
        default_screen_width: Default screen width (0 = skip).
        default_screen_height: Default screen height (0 = skip).

    Returns:
        Complete C# source string.
    """
    settings_lines = []
    changed_assets = ['"ProjectSettings/ProjectSettings.asset"']

    if company:
        safe = _sanitize_cs_string(company)
        settings_lines.append(f'            PlayerSettings.companyName = "{safe}";')

    if product:
        safe = _sanitize_cs_string(product)
        settings_lines.append(f'            PlayerSettings.productName = "{safe}";')

    if color_space:
        safe = _sanitize_cs_identifier(color_space)
        settings_lines.append(f'            PlayerSettings.colorSpace = ColorSpace.{safe};')

    if scripting_backend:
        safe = _sanitize_cs_identifier(scripting_backend)
        settings_lines.append(
            f'            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Standalone, ScriptingImplementation.{safe});'
        )

    if api_level:
        safe = _sanitize_cs_identifier(api_level)
        settings_lines.append(
            f'            PlayerSettings.SetApiCompatibilityLevel(BuildTargetGroup.Standalone, ApiCompatibilityLevel.{safe});'
        )

    if icon_path:
        safe = _sanitize_cs_string(icon_path)
        settings_lines.append(
            f'            var icon = AssetDatabase.LoadAssetAtPath<Texture2D>("{safe}");'
        )
        settings_lines.append(
            '            if (icon != null) PlayerSettings.SetIconsForTargetGroup(BuildTargetGroup.Unknown, new Texture2D[] { icon });'
        )

    if splash_path:
        safe = _sanitize_cs_string(splash_path)
        settings_lines.append(
            f'            // Load sprite from asset path (persistent) instead of creating non-persistent Sprite'
        )
        settings_lines.append(
            f'            var splashSprite = AssetDatabase.LoadAssetAtPath<Sprite>("{safe}");'
        )
        settings_lines.append(
            f'            if (splashSprite == null)'
        )
        settings_lines.append(
            '            {'
        )
        settings_lines.append(
            f'                // Ensure TextureImporter has sprite mode enabled so we can load as Sprite'
        )
        settings_lines.append(
            f'                var texImporter = AssetImporter.GetAtPath("{safe}") as TextureImporter;'
        )
        settings_lines.append(
            '                if (texImporter != null && texImporter.textureType != TextureImporterType.Sprite)'
        )
        settings_lines.append(
            '                {'
        )
        settings_lines.append(
            '                    texImporter.textureType = TextureImporterType.Sprite;'
        )
        settings_lines.append(
            '                    texImporter.SaveAndReimport();'
        )
        settings_lines.append(
            f'                    splashSprite = AssetDatabase.LoadAssetAtPath<Sprite>("{safe}");'
        )
        settings_lines.append(
            '                }'
        )
        settings_lines.append(
            '            }'
        )
        settings_lines.append(
            '            if (splashSprite != null)'
        )
        settings_lines.append(
            '            {'
        )
        settings_lines.append(
            '                var logo = UnityEditor.PlayerSettings.SplashScreen.logos;'
        )
        settings_lines.append(
            '                var logoList = new System.Collections.Generic.List<UnityEditor.PlayerSettings.SplashScreenLogo>(logo);'
        )
        settings_lines.append(
            '                logoList.Add(UnityEditor.PlayerSettings.SplashScreenLogo.Create(2.0f, splashSprite));'
        )
        settings_lines.append(
            '                UnityEditor.PlayerSettings.SplashScreen.logos = logoList.ToArray();'
        )
        settings_lines.append(
            '            }'
        )

    if default_screen_width > 0:
        settings_lines.append(
            f'            PlayerSettings.defaultScreenWidth = {default_screen_width};'
        )

    if default_screen_height > 0:
        settings_lines.append(
            f'            PlayerSettings.defaultScreenHeight = {default_screen_height};'
        )

    settings_block = "\n".join(settings_lines) if settings_lines else "            // No settings to configure (all parameters empty/zero)"

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_PlayerSettings
{{
    [MenuItem("VeilBreakers/Settings/Configure Player Settings")]
    public static void Execute()
    {{
        try
        {{
            Undo.SetCurrentGroupName("VeilBreakers Configure Player Settings");

{settings_block}

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"configure_player\\", "
                + "\\"changed_assets\\": [{", ".join(changed_assets)}], "
                + "\\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Player Settings configured successfully.");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"configure_player\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Player Settings configuration failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# EDIT-06: Build Settings
# ---------------------------------------------------------------------------

_PLATFORM_MAP: dict[str, tuple[str, str]] = {
    "StandaloneWindows64": ("Standalone", "StandaloneWindows64"),
    "StandaloneWindows": ("Standalone", "StandaloneWindows"),
    "StandaloneOSX": ("Standalone", "StandaloneOSX"),
    "StandaloneLinux64": ("Standalone", "StandaloneLinux64"),
    "Android": ("Android", "Android"),
    "iOS": ("iOS", "iPhone"),
    "WebGL": ("WebGL", "WebGL"),
}


def generate_build_settings_script(
    scenes: list[str] | None = None,
    platform: str = "",
    defines: list[str] | None = None,
) -> str:
    """Generate C# editor script to configure Unity Build Settings.

    Args:
        scenes: List of scene asset paths for the build.
        platform: Target platform name (e.g. "StandaloneWindows64").
        defines: List of scripting define symbols.

    Returns:
        Complete C# source string.
    """
    settings_lines = []

    if scenes:
        scene_array_items = ", ".join(
            f'new EditorBuildSettingsScene("{_sanitize_cs_string(s)}", true)' for s in scenes
        )
        settings_lines.append(
            f'            EditorBuildSettings.scenes = new EditorBuildSettingsScene[] {{ {scene_array_items} }};'
        )
        settings_lines.append(
            f'            Debug.Log("[VeilBreakers] Set {len(scenes)} scene(s) in build settings.");'
        )

    if platform:
        group, target = _PLATFORM_MAP.get(platform, ("Standalone", platform))
        settings_lines.append(
            f'            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.{group}, BuildTarget.{_sanitize_cs_identifier(target)});'
        )
        settings_lines.append(
            f'            Debug.Log("[VeilBreakers] Switched platform to {_sanitize_cs_string(platform)}.");'
        )

    if defines:
        defines_str = ";".join(_sanitize_cs_string(d) for d in defines)
        defines_group = _PLATFORM_MAP.get(platform, ("Standalone", platform))[0] if platform else "Standalone"
        settings_lines.append(
            f'            PlayerSettings.SetScriptingDefineSymbolsForGroup(BuildTargetGroup.{_sanitize_cs_identifier(defines_group)}, "{defines_str}");'
        )
        settings_lines.append(
            f'            Debug.Log("[VeilBreakers] Set scripting defines: {defines_str}");'
        )

    settings_block = "\n".join(settings_lines) if settings_lines else "            // No build settings to configure"

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_BuildSettings
{{
    [MenuItem("VeilBreakers/Settings/Configure Build Settings")]
    public static void Execute()
    {{
        try
        {{
            Undo.SetCurrentGroupName("VeilBreakers Configure Build Settings");

{settings_block}

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"configure_build\\", "
                + "\\"changed_assets\\": [\\"ProjectSettings/EditorBuildSettings.asset\\"], "
                + "\\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Build Settings configured successfully.");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"configure_build\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Build Settings configuration failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# EDIT-07: Quality Settings
# ---------------------------------------------------------------------------


def generate_quality_settings_script(
    levels: list[dict] | None = None,
) -> str:
    """Generate C# editor script to configure Unity Quality Settings.

    Uses SerializedObject on QualitySettings.asset to configure quality levels.

    Args:
        levels: List of quality level dicts. Each can have: name, shadow_distance,
            texture_quality, anti_aliasing, vsync, lod_bias, shadow_resolution.

    Returns:
        Complete C# source string.
    """
    if not levels:
        levels = []

    # Build per-level configuration code
    level_configs = ""
    for i, level in enumerate(levels):
        name = _sanitize_cs_string(level.get("name", f"Level_{i}"))
        shadow_dist = level.get("shadow_distance", 150)
        tex_quality = level.get("texture_quality", 0)
        aa = level.get("anti_aliasing", 0)
        vsync_val = level.get("vsync", 0)
        lod_bias = level.get("lod_bias", 1.0)
        shadow_res = _sanitize_cs_identifier(level.get("shadow_resolution", "High"))

        level_configs += f"""
            // Quality Level {i}: {name}
            QualitySettings.SetQualityLevel({i}, false);
            QualitySettings.shadowDistance = {shadow_dist}f;
            QualitySettings.globalTextureMipmapLimit = {tex_quality};
            QualitySettings.antiAliasing = {aa};
            QualitySettings.vSyncCount = {vsync_val};
            QualitySettings.lodBias = {lod_bias}f;
            QualitySettings.shadowResolution = ShadowResolution.{shadow_res};
            Debug.Log("[VeilBreakers] Configured quality level {i}: {name}");
"""

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_QualitySettings
{{
    [MenuItem("VeilBreakers/Settings/Configure Quality Settings")]
    public static void Execute()
    {{
        try
        {{
            Undo.SetCurrentGroupName("VeilBreakers Configure Quality Settings");

            // Access QualitySettings via SerializedObject for full control
            var qualityAsset = AssetDatabase.LoadMainAssetAtPath("ProjectSettings/QualitySettings.asset");
            var serializedQuality = new SerializedObject(qualityAsset);
{level_configs}
            // Restore default quality level
            if ({len(levels)} > 0)
                QualitySettings.SetQualityLevel({len(levels)} - 1, true);

            serializedQuality.ApplyModifiedProperties();

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"configure_quality\\", "
                + "\\"levels_configured\\": {len(levels)}, "
                + "\\"changed_assets\\": [\\"ProjectSettings/QualitySettings.asset\\"], "
                + "\\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Quality Settings configured: {len(levels)} level(s).");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"configure_quality\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Quality Settings configuration failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# EDIT-08: Package management
# ---------------------------------------------------------------------------


def generate_package_install_script(
    package_id: str,
    version: str = "",
    source: str = "upm",
    registry_url: str = "",
    scopes: list[str] | None = None,
) -> str:
    """Generate C# editor script to install a Unity package.

    Args:
        package_id: Package identifier or git URL.
        version: Package version (for UPM source).
        source: Installation source: "upm", "openupm", or "git".
        registry_url: OpenUPM registry URL (for openupm source).
        scopes: OpenUPM scopes list (for openupm source).

    Returns:
        Complete C# source string.
    """
    safe_package_id = _sanitize_cs_string(package_id)

    if source == "openupm":
        # OpenUPM: edit manifest.json to add scoped registry
        safe_url = _sanitize_cs_string(registry_url or "https://package.openupm.com")
        scopes_list = scopes or [package_id.rsplit(".", 1)[0]] if "." in package_id else [package_id]
        scopes_cs = ", ".join(f'\\"{_sanitize_cs_string(s)}\\"' for s in scopes_list)

        return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_InstallPackage
{{
    [MenuItem("VeilBreakers/Settings/Install Package")]
    public static void Execute()
    {{
        try
        {{
            // Read manifest.json
            string manifestPath = Path.Combine(Application.dataPath, "..", "Packages", "manifest.json");
            string manifestContent = File.ReadAllText(manifestPath);

            // Add scoped registry if not present
            if (!manifestContent.Contains("{safe_url}"))
            {{
                string newRegistry = "{{\\n      \\"name\\": \\"{safe_package_id}\\",\\n      \\"url\\": \\"{safe_url}\\",\\n      \\"scopes\\": [{scopes_cs}]\\n    }}";
                // Find scopedRegistries array or create it
                if (manifestContent.Contains("\\"scopedRegistries\\""))
                {{
                    // Handle both empty [] and populated arrays
                    // Check if scopedRegistries is an empty array []
                    int srIdx = manifestContent.IndexOf("\\"scopedRegistries\\"");
                    int srBracket = manifestContent.IndexOf("[", srIdx);
                    string afterBracket = manifestContent.Substring(srBracket + 1).TrimStart();
                    if (afterBracket.StartsWith("]"))
                    {{
                        // Empty array case: replace [] with [<registry>]
                        int closeBracket = manifestContent.IndexOf("]", srBracket);
                        manifestContent = manifestContent.Substring(0, srBracket + 1)
                            + "\\n    " + newRegistry + "\\n  "
                            + manifestContent.Substring(closeBracket);
                    }}
                    else
                    {{
                        // Non-empty array: insert after opening bracket
                        manifestContent = manifestContent.Insert(srBracket + 1, "\\n    " + newRegistry + ",");
                    }}
                }}
                else
                {{
                    // Add scopedRegistries before dependencies
                    int depIdx = manifestContent.IndexOf("\\"dependencies\\"");
                    string registryBlock = "\\"scopedRegistries\\": [\\n    " + newRegistry + "\\n  ],\\n  ";
                    manifestContent = manifestContent.Insert(depIdx, registryBlock);
                }}
            }}

            // Add package to dependencies
            if (!manifestContent.Contains("{safe_package_id}"))
            {{
                string packageEntry = "\\"" + "{safe_package_id}" + "\\": \\"latest\\"";
                // Handle both empty {{}} and populated dependencies
                int dIdx = manifestContent.IndexOf("\\"dependencies\\"");
                int dBrace = manifestContent.IndexOf("{{", dIdx);
                string afterBrace = manifestContent.Substring(dBrace + 1).TrimStart();
                if (afterBrace.StartsWith("}}"))
                {{
                    // Empty object case: replace {{}} with {{<entry>}}
                    int closeBrace = manifestContent.IndexOf("}}", dBrace);
                    manifestContent = manifestContent.Substring(0, dBrace + 1)
                        + "\\n    " + packageEntry + "\\n  "
                        + manifestContent.Substring(closeBrace);
                }}
                else
                {{
                    // Non-empty object: insert after opening brace
                    manifestContent = manifestContent.Insert(dBrace + 1, "\\n    " + packageEntry + ",");
                }}
            }}

            File.WriteAllText(manifestPath, manifestContent);
            AssetDatabase.Refresh();

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"install_package\\", "
                + "\\"package_id\\": \\"{safe_package_id}\\", "
                + "\\"source\\": \\"openupm\\", "
                + "\\"changed_assets\\": [\\"Packages/manifest.json\\"], "
                + "\\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Package installed via OpenUPM: {safe_package_id}");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"install_package\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Package installation failed: " + ex.Message);
        }}
    }}
}}
'''

    elif source == "git":
        # Git URL: use Client.Add with full URL
        return f'''using UnityEngine;
using UnityEditor;
using UnityEditor.PackageManager;
using System.IO;

public static class VeilBreakers_InstallPackage
{{
    [MenuItem("VeilBreakers/Settings/Install Package")]
    public static void Execute()
    {{
        try
        {{
            var request = Client.Add("{safe_package_id}");

            // Use EditorApplication.update callback to avoid blocking the main thread
            EditorApplication.update += OnUpdate;

            void OnUpdate()
            {{
                if (!request.IsCompleted) return;
                EditorApplication.update -= OnUpdate;

                if (request.Status == StatusCode.Success)
                {{
                    string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"install_package\\", "
                        + "\\"package_id\\": \\"{safe_package_id}\\", "
                        + "\\"source\\": \\"git\\", "
                        + "\\"changed_assets\\": [\\"Packages/manifest.json\\"], "
                        + "\\"validation_status\\": \\"ok\\"}}";
                    File.WriteAllText("Temp/vb_result.json", json);
                    Debug.Log("[VeilBreakers] Package installed via git: {safe_package_id}");
                }}
                else
                {{
                    string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"install_package\\", "
                        + "\\"message\\": \\"" + request.Error.message.Replace("\\"", "\\\\\\"") + "\\"}}";
                    File.WriteAllText("Temp/vb_result.json", json);
                    Debug.LogError("[VeilBreakers] Package installation failed: " + request.Error.message);
                }}
            }}
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"install_package\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Package installation failed: " + ex.Message);
        }}
    }}
}}
'''

    else:
        # UPM: standard registry install
        version_suffix = f"@{_sanitize_cs_string(version)}" if version else ""
        return f'''using UnityEngine;
using UnityEditor;
using UnityEditor.PackageManager;
using System.IO;

public static class VeilBreakers_InstallPackage
{{
    [MenuItem("VeilBreakers/Settings/Install Package")]
    public static void Execute()
    {{
        try
        {{
            var request = Client.Add("{safe_package_id}{version_suffix}");

            // Use EditorApplication.update callback to avoid blocking the main thread
            EditorApplication.update += OnUpdate;

            void OnUpdate()
            {{
                if (!request.IsCompleted) return;
                EditorApplication.update -= OnUpdate;

                if (request.Status == StatusCode.Success)
                {{
                    string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"install_package\\", "
                        + "\\"package_id\\": \\"{safe_package_id}\\", "
                        + "\\"version\\": \\"{_sanitize_cs_string(version)}\\", "
                        + "\\"source\\": \\"upm\\", "
                        + "\\"changed_assets\\": [\\"Packages/manifest.json\\"], "
                        + "\\"validation_status\\": \\"ok\\"}}";
                    File.WriteAllText("Temp/vb_result.json", json);
                    Debug.Log("[VeilBreakers] Package installed: {safe_package_id}{version_suffix}");
                }}
                else
                {{
                    string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"install_package\\", "
                        + "\\"message\\": \\"" + request.Error.message.Replace("\\"", "\\\\\\"") + "\\"}}";
                    File.WriteAllText("Temp/vb_result.json", json);
                    Debug.LogError("[VeilBreakers] Package installation failed: " + request.Error.message);
                }}
            }}
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"install_package\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Package installation failed: " + ex.Message);
        }}
    }}
}}
'''


def generate_package_remove_script(package_id: str) -> str:
    """Generate C# editor script to remove a Unity package.

    Args:
        package_id: Package identifier to remove.

    Returns:
        Complete C# source string.
    """
    safe_package_id = _sanitize_cs_string(package_id)

    return f'''using UnityEngine;
using UnityEditor;
using UnityEditor.PackageManager;
using System.IO;

public static class VeilBreakers_RemovePackage
{{
    [MenuItem("VeilBreakers/Settings/Remove Package")]
    public static void Execute()
    {{
        try
        {{
            var request = Client.Remove("{safe_package_id}");

            // Use EditorApplication.update callback to avoid blocking the main thread
            EditorApplication.update += OnUpdate;

            void OnUpdate()
            {{
                if (!request.IsCompleted) return;
                EditorApplication.update -= OnUpdate;

                if (request.Status == StatusCode.Success)
                {{
                    string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"remove_package\\", "
                        + "\\"package_id\\": \\"{safe_package_id}\\", "
                        + "\\"changed_assets\\": [\\"Packages/manifest.json\\"], "
                        + "\\"validation_status\\": \\"ok\\"}}";
                    File.WriteAllText("Temp/vb_result.json", json);
                    Debug.Log("[VeilBreakers] Package removed: {safe_package_id}");
                }}
                else
                {{
                    string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"remove_package\\", "
                        + "\\"message\\": \\"" + request.Error.message.Replace("\\"", "\\\\\\"") + "\\"}}";
                    File.WriteAllText("Temp/vb_result.json", json);
                    Debug.LogError("[VeilBreakers] Package removal failed: " + request.Error.message);
                }}
            }}
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"remove_package\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Package removal failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# EDIT-09: Tags, Layers, Sorting Layers
# ---------------------------------------------------------------------------


def generate_tag_layer_script(
    tags: list[str] | None = None,
    layers: list[str] | None = None,
    sorting_layers: list[str] | None = None,
) -> str:
    """Generate C# editor script to create tags, layers, and sorting layers.

    Uses SerializedObject on TagManager.asset for safe modification.

    Args:
        tags: List of tag names to add.
        layers: List of layer names to add (indices 8-31).
        sorting_layers: List of sorting layer names to add.

    Returns:
        Complete C# source string.
    """
    # Build tag addition code
    tag_code = ""
    if tags:
        tag_entries = ""
        for tag in tags:
            safe = _sanitize_cs_string(tag)
            tag_entries += f"""
                // Add tag: {safe}
                bool tagExists_{_sanitize_cs_identifier(tag)} = false;
                for (int i = 0; i < tagsProp.arraySize; i++)
                {{
                    if (tagsProp.GetArrayElementAtIndex(i).stringValue == "{safe}")
                    {{
                        tagExists_{_sanitize_cs_identifier(tag)} = true;
                        break;
                    }}
                }}
                if (!tagExists_{_sanitize_cs_identifier(tag)})
                {{
                    tagsProp.InsertArrayElementAtIndex(tagsProp.arraySize);
                    tagsProp.GetArrayElementAtIndex(tagsProp.arraySize - 1).stringValue = "{safe}";
                    tagsAdded++;
                }}
"""
        tag_code = f"""
            // === TAGS ===
            var tagsProp = tagManager.FindProperty("tags");
            int tagsAdded = 0;
{tag_entries}"""

    # Build layer addition code
    layer_code = ""
    if layers:
        layer_entries = ""
        for layer in layers:
            safe = _sanitize_cs_string(layer)
            layer_entries += f"""
                // Add layer: {safe}
                bool layerAdded_{_sanitize_cs_identifier(layer)} = false;
                for (int i = 8; i <= 31; i++)
                {{
                    var layerProp = layersProp.GetArrayElementAtIndex(i);
                    if (string.IsNullOrEmpty(layerProp.stringValue))
                    {{
                        layerProp.stringValue = "{safe}";
                        layerAdded_{_sanitize_cs_identifier(layer)} = true;
                        layersAdded++;
                        break;
                    }}
                    if (layerProp.stringValue == "{safe}")
                    {{
                        layerAdded_{_sanitize_cs_identifier(layer)} = true;
                        break;
                    }}
                }}
                if (!layerAdded_{_sanitize_cs_identifier(layer)})
                {{
                    warnings.Add("No empty slot for layer: {safe}");
                }}
"""
        layer_code = f"""
            // === LAYERS ===
            var layersProp = tagManager.FindProperty("layers");
            int layersAdded = 0;
{layer_entries}"""

    # Build sorting layer addition code
    sorting_code = ""
    if sorting_layers:
        sorting_entries = ""
        for sl in sorting_layers:
            safe = _sanitize_cs_string(sl)
            sorting_entries += f"""
                // Add sorting layer: {safe}
                bool sortingExists_{_sanitize_cs_identifier(sl)} = false;
                for (int i = 0; i < sortingLayersProp.arraySize; i++)
                {{
                    var entry = sortingLayersProp.GetArrayElementAtIndex(i);
                    if (entry.FindPropertyRelative("name").stringValue == "{safe}")
                    {{
                        sortingExists_{_sanitize_cs_identifier(sl)} = true;
                        break;
                    }}
                }}
                if (!sortingExists_{_sanitize_cs_identifier(sl)})
                {{
                    sortingLayersProp.InsertArrayElementAtIndex(sortingLayersProp.arraySize);
                    var newEntry = sortingLayersProp.GetArrayElementAtIndex(sortingLayersProp.arraySize - 1);
                    newEntry.FindPropertyRelative("name").stringValue = "{safe}";
                    newEntry.FindPropertyRelative("uniqueID").intValue = {int(hashlib.md5(sl.encode()).hexdigest()[:8], 16) & 0x7FFFFFFF};
                    sortingLayersAdded++;
                }}
"""
        sorting_code = f"""
            // === SORTING LAYERS ===
            var sortingLayersProp = tagManager.FindProperty("m_SortingLayers");
            int sortingLayersAdded = 0;
{sorting_entries}"""

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_TagsLayers
{{
    [MenuItem("VeilBreakers/Settings/Manage Tags & Layers")]
    public static void Execute()
    {{
        try
        {{
            var tagManagerAsset = AssetDatabase.LoadMainAssetAtPath("ProjectSettings/TagManager.asset");
            var tagManager = new SerializedObject(tagManagerAsset);
            var warnings = new List<string>();

            Undo.RecordObject(tagManagerAsset, "VeilBreakers Manage Tags & Layers");
{tag_code}
{layer_code}
{sorting_code}

            tagManager.ApplyModifiedProperties();

            // Build warnings JSON
            string warningsJson = "[";
            for (int i = 0; i < warnings.Count; i++)
            {{
                warningsJson += "\\"" + warnings[i].Replace("\\"", "\\\\\\"") + "\\"";
                if (i < warnings.Count - 1) warningsJson += ", ";
            }}
            warningsJson += "]";

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"manage_tags_layers\\", "
                + "\\"changed_assets\\": [\\"ProjectSettings/TagManager.asset\\"], "
                + "\\"warnings\\": " + warningsJson + ", "
                + "\\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Tags & Layers configured.");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"manage_tags_layers\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Tags & Layers configuration failed: " + ex.Message);
        }}
    }}
}}
'''


def generate_tag_layer_sync_script(constants_cs_path: str) -> str:
    """Generate C# editor script to sync tags/layers from Constants.cs.

    Reads the Constants.cs file, extracts TAG_ and LAYER_ constant definitions
    via regex, and ensures they exist in TagManager.

    Args:
        constants_cs_path: Path to Constants.cs within the Unity project.

    Returns:
        Complete C# source string.
    """
    safe_path = _sanitize_cs_string(constants_cs_path)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Text.RegularExpressions;
using System.Collections.Generic;

public static class VeilBreakers_SyncTagsLayers
{{
    [MenuItem("VeilBreakers/Settings/Sync Tags & Layers from Code")]
    public static void Execute()
    {{
        try
        {{
            string constantsPath = "{safe_path}";
            string fullPath = Path.GetFullPath(constantsPath).Replace("\\\\", "/");

            // Verify path stays within the Unity project Assets folder
            if (!fullPath.StartsWith(Application.dataPath.Replace("\\\\", "/")))
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"sync_tags_layers\\", "
                    + "\\"message\\": \\"Path escapes project boundary: {safe_path}\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                Debug.LogError("[VeilBreakers] Path escapes project: " + fullPath);
                return;
            }}

            if (!File.Exists(fullPath))
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"sync_tags_layers\\", "
                    + "\\"message\\": \\"Constants.cs not found at: {safe_path}\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                Debug.LogError("[VeilBreakers] Constants.cs not found: " + fullPath);
                return;
            }}

            string fileContent = File.ReadAllText(fullPath);

            // Extract TAG_ constants: public const string TAG_PLAYER = "Player";
            var tagRegex = new Regex(@"public\\s+const\\s+string\\s+TAG_\\w+\\s*=\\s*""([^""]+)""");
            var tagMatches = tagRegex.Matches(fileContent);

            // Extract LAYER_ constants: public static readonly int LAYER_PLAYER = 8;
            var layerRegex = new Regex(@"public\\s+static\\s+readonly\\s+int\\s+LAYER_(\\w+)\\s*=\\s*(\\d+)");
            var layerMatches = layerRegex.Matches(fileContent);

            // Open TagManager
            var tagManagerAsset = AssetDatabase.LoadMainAssetAtPath("ProjectSettings/TagManager.asset");
            var tagManager = new SerializedObject(tagManagerAsset);
            Undo.RecordObject(tagManagerAsset, "VeilBreakers Sync Tags & Layers");

            var tagsProp = tagManager.FindProperty("tags");
            var layersProp = tagManager.FindProperty("layers");

            int tagsAdded = 0;
            int tagsDrift = 0;
            int layersSet = 0;
            int layersDrift = 0;
            var driftReport = new List<string>();

            // Sync tags
            foreach (Match m in tagMatches)
            {{
                string tagName = m.Groups[1].Value;
                bool exists = false;
                for (int i = 0; i < tagsProp.arraySize; i++)
                {{
                    if (tagsProp.GetArrayElementAtIndex(i).stringValue == tagName)
                    {{
                        exists = true;
                        break;
                    }}
                }}
                if (!exists)
                {{
                    tagsProp.InsertArrayElementAtIndex(tagsProp.arraySize);
                    tagsProp.GetArrayElementAtIndex(tagsProp.arraySize - 1).stringValue = tagName;
                    tagsAdded++;
                    driftReport.Add("TAG added: " + tagName);
                }}
            }}

            // Sync layers
            foreach (Match m in layerMatches)
            {{
                string layerName = m.Groups[1].Value;
                int layerIndex = int.Parse(m.Groups[2].Value);

                if (layerIndex >= 0 && layerIndex <= 31)
                {{
                    var layerProp = layersProp.GetArrayElementAtIndex(layerIndex);
                    string currentValue = layerProp.stringValue;

                    if (currentValue != layerName)
                    {{
                        if (!string.IsNullOrEmpty(currentValue))
                        {{
                            layersDrift++;
                            driftReport.Add("LAYER drift at " + layerIndex + ": TagManager='" + currentValue + "' vs Constants='" + layerName + "'");
                        }}
                        layerProp.stringValue = layerName;
                        layersSet++;
                    }}
                }}
            }}

            // Check for tags in TagManager not in Constants.cs
            var codeTagNames = new HashSet<string>();
            foreach (Match m in tagMatches)
                codeTagNames.Add(m.Groups[1].Value);

            for (int i = 0; i < tagsProp.arraySize; i++)
            {{
                string existingTag = tagsProp.GetArrayElementAtIndex(i).stringValue;
                if (!string.IsNullOrEmpty(existingTag) && !codeTagNames.Contains(existingTag))
                {{
                    tagsDrift++;
                    driftReport.Add("TAG in TagManager not in Constants.cs: " + existingTag);
                }}
            }}

            tagManager.ApplyModifiedProperties();

            // Build drift report JSON
            string driftJson = "[";
            for (int i = 0; i < driftReport.Count; i++)
            {{
                driftJson += "\\"" + driftReport[i].Replace("\\"", "\\\\\\"") + "\\"";
                if (i < driftReport.Count - 1) driftJson += ", ";
            }}
            driftJson += "]";

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"sync_tags_layers\\", "
                + "\\"tags_added\\": " + tagsAdded + ", "
                + "\\"layers_set\\": " + layersSet + ", "
                + "\\"tags_drift\\": " + tagsDrift + ", "
                + "\\"layers_drift\\": " + layersDrift + ", "
                + "\\"drift_report\\": " + driftJson + ", "
                + "\\"changed_assets\\": [\\"ProjectSettings/TagManager.asset\\"], "
                + "\\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Tag/Layer sync completed. Tags added: " + tagsAdded + ", Layers set: " + layersSet);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"sync_tags_layers\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Tag/Layer sync failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# EDIT-11: Time Settings
# ---------------------------------------------------------------------------


def generate_time_settings_script(
    fixed_timestep: float = 0.02,
    maximum_timestep: float = 0.1,
    time_scale: float = 1.0,
) -> str:
    """Generate C# editor script to configure Unity Time Settings.

    Args:
        fixed_timestep: Fixed physics update interval (seconds).
        maximum_timestep: Maximum allowed timestep (seconds).
        time_scale: Time scale multiplier.

    Returns:
        Complete C# source string.
    """
    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_TimeSettings
{{
    [MenuItem("VeilBreakers/Settings/Configure Time Settings")]
    public static void Execute()
    {{
        try
        {{
            Undo.SetCurrentGroupName("VeilBreakers Configure Time Settings");

            // Configure time settings
            Time.fixedDeltaTime = {fixed_timestep}f;
            Time.maximumDeltaTime = {maximum_timestep}f;
            Time.timeScale = {time_scale}f;

            Debug.Log("[VeilBreakers] Time settings configured: fixedDeltaTime={fixed_timestep}, maximumDeltaTime={maximum_timestep}, timeScale={time_scale}");

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"configure_time\\", "
                + "\\"fixed_timestep\\": {fixed_timestep}, "
                + "\\"maximum_timestep\\": {maximum_timestep}, "
                + "\\"time_scale\\": {time_scale}, "
                + "\\"changed_assets\\": [\\"ProjectSettings/TimeManager.asset\\"], "
                + "\\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Time Settings configured successfully.");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"configure_time\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Time Settings configuration failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# EDIT-11: Graphics Settings
# ---------------------------------------------------------------------------


def generate_graphics_settings_script(
    render_pipeline_path: str = "",
    fog_mode: str = "",
    fog_color: list[float] | None = None,
    fog_density: float = 0.0,
) -> str:
    """Generate C# editor script to configure Unity Graphics Settings.

    Args:
        render_pipeline_path: Path to RenderPipelineAsset to assign.
        fog_mode: Fog mode: "Linear", "Exponential", "ExponentialSquared", or empty.
        fog_color: Fog color [r, g, b, a].
        fog_density: Fog density for exponential modes.

    Returns:
        Complete C# source string.
    """
    settings_lines = []

    if render_pipeline_path:
        safe = _sanitize_cs_string(render_pipeline_path)
        settings_lines.append(
            f'            var pipelineAsset = AssetDatabase.LoadAssetAtPath<UnityEngine.Rendering.RenderPipelineAsset>("{safe}");'
        )
        settings_lines.append(
            '            if (pipelineAsset != null)'
        )
        settings_lines.append(
            '            {'
        )
        settings_lines.append(
            '                UnityEngine.Rendering.GraphicsSettings.defaultRenderPipeline = pipelineAsset;'
        )
        settings_lines.append(
            '                QualitySettings.renderPipeline = pipelineAsset;'
        )
        settings_lines.append(
            f'                Debug.Log("[VeilBreakers] Render pipeline set to: {safe}");'
        )
        settings_lines.append(
            '            }'
        )
        settings_lines.append(
            '            else'
        )
        settings_lines.append(
            '            {'
        )
        settings_lines.append(
            f'                Debug.LogWarning("[VeilBreakers] RenderPipelineAsset not found at: {safe}");'
        )
        settings_lines.append(
            '            }'
        )

    if fog_mode:
        fog_mode_map: dict[str, str] = {
            "Linear": "FogMode.Linear",
            "Exponential": "FogMode.Exponential",
            "ExponentialSquared": "FogMode.ExponentialSquared",
        }
        cs_fog_mode = fog_mode_map.get(fog_mode, f"FogMode.{_sanitize_cs_identifier(fog_mode)}")
        settings_lines.append(f'            RenderSettings.fog = true;')
        settings_lines.append(f'            RenderSettings.fogMode = {cs_fog_mode};')

    if fog_color and len(fog_color) >= 3:
        r, g, b = fog_color[0], fog_color[1], fog_color[2]
        a = fog_color[3] if len(fog_color) >= 4 else 1.0
        settings_lines.append(
            f'            RenderSettings.fogColor = new Color({r}f, {g}f, {b}f, {a}f);'
        )

    if fog_density > 0:
        settings_lines.append(
            f'            RenderSettings.fogDensity = {fog_density}f;'
        )

    settings_block = "\n".join(settings_lines) if settings_lines else "            // No graphics settings to configure"

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_GraphicsSettings
{{
    [MenuItem("VeilBreakers/Settings/Configure Graphics Settings")]
    public static void Execute()
    {{
        try
        {{
            Undo.SetCurrentGroupName("VeilBreakers Configure Graphics Settings");

{settings_block}

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"configure_graphics\\", "
                + "\\"changed_assets\\": [\\"ProjectSettings/GraphicsSettings.asset\\"], "
                + "\\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Graphics Settings configured successfully.");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"configure_graphics\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Graphics Settings configuration failed: " + ex.Message);
        }}
    }}
}}
'''
