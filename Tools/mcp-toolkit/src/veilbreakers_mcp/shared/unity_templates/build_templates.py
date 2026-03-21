"""Build & deploy C# template generators for Unity automation.

Each function returns a complete C# source string that can be written to
a Unity project's Assets/Editor/Generated/Build/ directory.  When compiled
by Unity, the scripts register as MenuItem commands under
"VeilBreakers/Build/...".

All generated scripts write their result to Temp/vb_result.json or
Temp/vb_build_results.json so that the Python MCP server can read back the
outcome after execution.

Exports:
    generate_multi_platform_build_script   -- BUILD-01: multi-platform build orchestrator
    generate_addressables_config_script    -- BUILD-02: Addressable group configurator
    generate_platform_config_script        -- BUILD-05: Android/iOS/WebGL config
    generate_shader_stripping_script       -- SHDR-03: IPreprocessShaders implementation

Pure-logic helpers:
    _validate_platforms                    -- validate platform dicts
    _validate_addressable_groups           -- validate addressable group dicts
"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


_CS_RESERVED = frozenset({
    "abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char",
    "checked", "class", "const", "continue", "decimal", "default", "delegate",
    "do", "double", "else", "enum", "event", "explicit", "extern", "false",
    "finally", "fixed", "float", "for", "foreach", "goto", "if", "implicit",
    "in", "int", "interface", "internal", "is", "lock", "long", "namespace",
    "new", "null", "object", "operator", "out", "override", "params", "private",
    "protected", "public", "readonly", "ref", "return", "sbyte", "sealed",
    "short", "sizeof", "stackalloc", "static", "string", "struct", "switch",
    "this", "throw", "true", "try", "typeof", "uint", "ulong", "unchecked",
    "unsafe", "ushort", "using", "virtual", "void", "volatile", "while",
})


def _safe_namespace(ns: str) -> str:
    """Sanitize a C# namespace string."""
    sanitized = re.sub(r"[^a-zA-Z0-9_.]", "", ns)
    sanitized = re.sub(r"\.{2,}", ".", sanitized).strip(".")
    if not sanitized:
        return "Generated"
    segments = sanitized.split(".")
    fixed: list[str] = []
    for seg in segments:
        if not seg:
            continue
        if seg[0].isdigit():
            seg = f"_{seg}"
        if seg in _CS_RESERVED:
            seg = f"@{seg}"
        fixed.append(seg)
    return ".".join(fixed) or "Generated"


def _wrap_namespace(lines: list[str], namespace: str) -> list[str]:
    """Wrap lines in a namespace block if namespace is non-empty."""
    if not namespace:
        return lines
    ns = _safe_namespace(namespace)
    wrapped = [f"namespace {ns}", "{"]
    for line in lines:
        if line.strip():
            wrapped.append(f"    {line}")
        else:
            wrapped.append("")
    wrapped.append("}")
    return wrapped


# ---------------------------------------------------------------------------
# Pure-logic validation helpers
# ---------------------------------------------------------------------------

_VALID_PACKING_MODES = frozenset({
    "PackTogether", "PackSeparately", "PackTogetherByLabel",
})

_REQUIRED_PLATFORM_KEYS = frozenset({"name", "target", "group", "backend"})


def _validate_platforms(platforms: list[dict]) -> bool:
    """Ensure each platform dict has name, target, group, backend keys.

    Args:
        platforms: List of platform configuration dicts.

    Returns:
        True if all dicts contain the required keys, False otherwise.
    """
    if not platforms:
        return False
    for p in platforms:
        if not isinstance(p, dict):
            return False
        if not _REQUIRED_PLATFORM_KEYS.issubset(p.keys()):
            return False
    return True


def _validate_addressable_groups(groups: list[dict]) -> bool:
    """Ensure each group dict has a name key and valid packing mode.

    Args:
        groups: List of addressable group configuration dicts.

    Returns:
        True if valid, False otherwise.
    """
    if not groups:
        return False
    for g in groups:
        if not isinstance(g, dict):
            return False
        if "name" not in g:
            return False
        packing = g.get("packing", "PackSeparately")
        if packing not in _VALID_PACKING_MODES:
            return False
    return True


# ---------------------------------------------------------------------------
# Default platform configurations
# ---------------------------------------------------------------------------

_DEFAULT_PLATFORMS: list[dict] = [
    {"name": "Windows", "target": "StandaloneWindows64", "group": "Standalone", "backend": "IL2CPP", "extension": ".exe"},
    {"name": "Mac", "target": "StandaloneOSX", "group": "Standalone", "backend": "IL2CPP", "extension": ""},
    {"name": "Linux", "target": "StandaloneLinux64", "group": "Standalone", "backend": "IL2CPP", "extension": ""},
    {"name": "Android", "target": "Android", "group": "Android", "backend": "IL2CPP", "extension": ".apk"},
    {"name": "iOS", "target": "iOS", "group": "iOS", "backend": "IL2CPP", "extension": ""},
    {"name": "WebGL", "target": "WebGL", "group": "WebGL", "backend": "Mono2x", "extension": ""},
]


# ---------------------------------------------------------------------------
# BUILD-01: Multi-platform build orchestrator
# ---------------------------------------------------------------------------

def generate_multi_platform_build_script(
    platforms: list[dict] | None = None,
    development: bool = False,
    namespace: str = "",
) -> str:
    """Generate C# editor script for multi-platform build orchestration.

    Iterates over platform targets, switches active build target, sets
    scripting backend, builds with BuildPipeline.BuildPlayer, collects
    per-platform results, and writes a JSON summary.

    Args:
        platforms: List of platform dicts with keys: name, target, group,
            backend, extension.  Defaults to 6 standard platforms.
        development: If True, adds BuildOptions.Development flag.
        namespace: Optional C# namespace to wrap the class in.

    Returns:
        Complete C# source string.
    """
    plats = platforms or _DEFAULT_PLATFORMS

    build_options_str = "BuildOptions.Development" if development else "BuildOptions.None"

    # Build the using block
    lines: list[str] = [
        "using UnityEditor;",
        "using UnityEditor.Build.Reporting;",
        "using UnityEngine;",
        "using System.IO;",
        "using System.Collections.Generic;",
        "using System.Text;",
        "",
        "public static class VeilBreakers_MultiPlatformBuild",
        "{",
        '    [MenuItem("VeilBreakers/Build/Multi-Platform Build")]',
        "    public static void Execute()",
        "    {",
        "        var results = new List<string>();",
        "        int succeeded = 0;",
        "        int failed = 0;",
        "",
        "        // Get scenes from Build Settings",
        "        var scenesList = new List<string>();",
        "        foreach (var scene in EditorBuildSettings.scenes)",
        "        {",
        "            if (scene.enabled)",
        "                scenesList.Add(scene.path);",
        "        }",
        "        string[] buildScenes = scenesList.ToArray();",
        "",
        "        if (buildScenes.Length == 0)",
        "        {",
        '            string errJson = "{\\"status\\": \\"error\\", \\"action\\": \\"build_multi_platform\\", \\"message\\": \\"No scenes configured for build\\"}";',
        '            File.WriteAllText("Temp/vb_build_results.json", errJson);',
        '            Debug.LogError("[VeilBreakers] No scenes configured for build.");',
        "            return;",
        "        }",
        "",
    ]

    # Generate per-platform build blocks
    for plat in plats:
        safe_name = _sanitize_cs_identifier(plat["name"])
        safe_target = _sanitize_cs_identifier(plat["target"])
        safe_group = _sanitize_cs_identifier(plat["group"])
        safe_backend = _sanitize_cs_identifier(plat["backend"])
        extension = _sanitize_cs_string(plat.get("extension", ""))

        lines.append(f"        // --- {safe_name} ---")
        lines.append("        try")
        lines.append("        {")
        lines.append(f'            Debug.Log("[VeilBreakers] Building {safe_name}...");')
        lines.append(f"            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.{safe_group}, BuildTarget.{safe_target});")
        lines.append(f"            PlayerSettings.SetScriptingBackend(NamedBuildTarget.FromBuildTargetGroup(BuildTargetGroup.{safe_group}), ScriptingBackend.{safe_backend});")
        lines.append("")
        lines.append("            var options = new BuildPlayerOptions")
        lines.append("            {")
        lines.append("                scenes = buildScenes,")
        lines.append(f'                locationPathName = "Builds/{safe_name}/Game{extension}",')
        lines.append(f"                target = BuildTarget.{safe_target},")
        lines.append(f"                options = {build_options_str},")
        lines.append("            };")
        lines.append("")
        lines.append("            BuildReport report = BuildPipeline.BuildPlayer(options);")
        lines.append("")
        lines.append("            if (report.summary.result == BuildResult.Succeeded)")
        lines.append("            {")
        lines.append("                long totalSize = (long)report.summary.totalSize;")
        lines.append("                double totalTime = report.summary.totalTime.TotalSeconds;")
        lines.append(f'                results.Add("{{\\"name\\": \\"{safe_name}\\", \\"result\\": \\"Succeeded\\", \\"totalSize\\": " + totalSize + ", \\"totalTime\\": " + totalTime.ToString("F2") + "}}");')
        lines.append("                succeeded++;")
        lines.append(f'                Debug.Log("[VeilBreakers] {safe_name} build succeeded. Size: " + (totalSize / (1024f * 1024f)).ToString("F1") + " MB");')
        lines.append("            }")
        lines.append("            else")
        lines.append("            {")
        lines.append(f'                results.Add("{{\\"name\\": \\"{safe_name}\\", \\"result\\": \\"" + report.summary.result.ToString() + "\\", \\"totalSize\\": 0, \\"totalTime\\": 0}}");')
        lines.append("                failed++;")
        lines.append(f'                Debug.LogError("[VeilBreakers] {safe_name} build failed: " + report.summary.result);')
        lines.append("            }")
        lines.append("        }")
        lines.append("        catch (System.Exception ex)")
        lines.append("        {")
        lines.append(f'            results.Add("{{\\"name\\": \\"{safe_name}\\", \\"result\\": \\"Exception\\", \\"totalSize\\": 0, \\"totalTime\\": 0}}");')
        lines.append("            failed++;")
        lines.append(f'            Debug.LogError("[VeilBreakers] {safe_name} build exception: " + ex.Message);')
        lines.append("        }")
        lines.append("")

    # JSON summary
    lines.append("        // Write summary JSON")
    lines.append("        var sb = new StringBuilder();")
    lines.append('        sb.Append("{\\"status\\": \\"success\\", \\"action\\": \\"build_multi_platform\\", ");')
    lines.append('        sb.Append("\\"succeeded\\": " + succeeded + ", \\"failed\\": " + failed + ", ");')
    lines.append('        sb.Append("\\"platforms\\": [");')
    lines.append("        for (int i = 0; i < results.Count; i++)")
    lines.append("        {")
    lines.append("            sb.Append(results[i]);")
    lines.append('            if (i < results.Count - 1) sb.Append(", ");')
    lines.append("        }")
    lines.append('        sb.Append("]}");')
    lines.append('        File.WriteAllText("Temp/vb_build_results.json", sb.ToString());')
    lines.append('        Debug.Log("[VeilBreakers] Multi-platform build complete. Succeeded: " + succeeded + ", Failed: " + failed);')
    lines.append("    }")
    lines.append("}")

    lines = _wrap_namespace(lines, namespace)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# BUILD-02: Addressable Asset Group configurator
# ---------------------------------------------------------------------------

_DEFAULT_GROUPS: list[dict] = [
    {"name": "Default", "packing": "PackSeparately", "local": True},
]


def generate_addressables_config_script(
    groups: list[dict] | None = None,
    build_remote: bool = False,
    namespace: str = "",
) -> str:
    """Generate C# editor script for Addressable Asset Group configuration.

    Creates or configures Addressable groups with BundledAssetGroupSchema
    and ContentUpdateGroupSchema.  Optionally triggers a full content build.

    Args:
        groups: List of group dicts with keys: name (str), packing
            (PackTogether/PackSeparately/PackTogetherByLabel), local (bool).
            Defaults to a single Default group.
        build_remote: If True, calls BuildPlayerContent after configuration.
        namespace: Optional C# namespace to wrap the class in.

    Returns:
        Complete C# source string.
    """
    grps = groups or _DEFAULT_GROUPS

    lines: list[str] = [
        "using UnityEditor;",
        "using UnityEditor.AddressableAssets;",
        "using UnityEditor.AddressableAssets.Settings;",
        "using UnityEditor.AddressableAssets.Settings.GroupSchemas;",
        "using UnityEngine;",
        "using System.IO;",
        "using System.Collections.Generic;",
        "",
        "public static class VeilBreakers_AddressablesConfig",
        "{",
        '    [MenuItem("VeilBreakers/Build/Configure Addressables")]',
        "    public static void Execute()",
        "    {",
        "        try",
        "        {",
        "            // Get or create AddressableAssetSettings",
        "            var settings = AddressableAssetSettingsDefaultObject.Settings;",
        "            if (settings == null)",
        "            {",
        "                settings = AddressableAssetSettings.Create(",
        "                    AddressableAssetSettings.kDefaultConfigFolder,",
        "                    AddressableAssetSettings.kDefaultConfigAssetName, true, true);",
        "                AddressableAssetSettingsDefaultObject.Settings = settings;",
        "            }",
        "",
        "            int groupsCreated = 0;",
        "            int groupsConfigured = 0;",
        "",
    ]

    for grp in grps:
        safe_name = _sanitize_cs_string(grp["name"])
        packing = grp.get("packing", "PackSeparately")
        is_local = grp.get("local", True)

        if packing not in _VALID_PACKING_MODES:
            packing = "PackSeparately"

        if is_local:
            build_path_var = "AddressableAssetSettings.kLocalBuildPath"
            load_path_var = "AddressableAssetSettings.kLocalLoadPath"
        else:
            build_path_var = "AddressableAssetSettings.kRemoteBuildPath"
            load_path_var = "AddressableAssetSettings.kRemoteLoadPath"

        lines.append(f"            // --- Group: {safe_name} ---")
        lines.append("            {")
        lines.append(f'                string groupName = "{safe_name}";')
        lines.append("                var existingGroup = settings.FindGroup(groupName);")
        lines.append("                AddressableAssetGroup group;")
        lines.append("                if (existingGroup != null)")
        lines.append("                {")
        lines.append("                    group = existingGroup;")
        lines.append("                    groupsConfigured++;")
        lines.append("                }")
        lines.append("                else")
        lines.append("                {")
        lines.append("                    group = settings.CreateGroup(groupName, false, false, true, null,")
        lines.append("                        typeof(BundledAssetGroupSchema), typeof(ContentUpdateGroupSchema));")
        lines.append("                    groupsCreated++;")
        lines.append("                }")
        lines.append("")
        lines.append("                var schema = group.GetSchema<BundledAssetGroupSchema>();")
        lines.append("                if (schema != null)")
        lines.append("                {")
        lines.append(f"                    schema.BuildPath.SetVariableByName(settings, {build_path_var});")
        lines.append(f"                    schema.LoadPath.SetVariableByName(settings, {load_path_var});")
        lines.append(f"                    schema.BundleMode = BundledAssetGroupSchema.BundlePackingMode.{packing};")
        lines.append("                }")
        lines.append(f'                Debug.Log("[VeilBreakers] Configured group: " + groupName);')
        lines.append("            }")
        lines.append("")

    if build_remote:
        lines.append("            // Build Addressables content")
        lines.append("            AddressableAssetSettings.BuildPlayerContent();")
        lines.append('            Debug.Log("[VeilBreakers] Addressable content built.");')
        lines.append("")

    lines.append('            string json = "{\\"status\\": \\"success\\", \\"action\\": \\"configure_addressables\\", "')
    lines.append('                + "\\"groups_created\\": " + groupsCreated + ", "')
    lines.append('                + "\\"groups_configured\\": " + groupsConfigured + "}";')
    lines.append('            File.WriteAllText("Temp/vb_result.json", json);')
    lines.append('            Debug.Log("[VeilBreakers] Addressables configured. Created: " + groupsCreated + ", Updated: " + groupsConfigured);')
    lines.append("        }")
    lines.append("        catch (System.Exception ex)")
    lines.append("        {")
    lines.append('            string json = "{\\"status\\": \\"error\\", \\"action\\": \\"configure_addressables\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}";')
    lines.append('            File.WriteAllText("Temp/vb_result.json", json);')
    lines.append('            Debug.LogError("[VeilBreakers] Addressables configuration failed: " + ex.Message);')
    lines.append("        }")
    lines.append("    }")
    lines.append("}")

    lines = _wrap_namespace(lines, namespace)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# BUILD-05: Platform-specific configuration
# ---------------------------------------------------------------------------

def generate_platform_config_script(
    platform: str = "android",
    permissions: list[str] | None = None,
    features: list[str] | None = None,
    plist_entries: list[dict] | None = None,
    webgl_memory_mb: int = 256,
    namespace: str = "",
) -> str:
    """Generate C# editor script for platform-specific build configuration.

    Supports three platforms:
    - android: Generates AndroidManifest.xml with permissions and features
    - ios: Generates PostProcessBuild callback with PlistDocument and PBXProject
    - webgl: Sets PlayerSettings.WebGL properties

    Args:
        platform: Target platform ("android", "ios", or "webgl").
        permissions: Android permissions list. Defaults to ["android.permission.INTERNET"].
        features: Android features list. Defaults to ["android.hardware.touchscreen"].
        plist_entries: iOS plist entries as list of dicts with key, value, type.
        webgl_memory_mb: WebGL memory size in MB. Default 256.
        namespace: Optional C# namespace to wrap the class in.

    Returns:
        Complete C# source string.
    """
    platform_lower = platform.lower()

    if platform_lower == "android":
        return _generate_android_config(permissions, features, namespace)
    elif platform_lower == "ios":
        return _generate_ios_config(plist_entries, namespace)
    elif platform_lower == "webgl":
        return _generate_webgl_config(webgl_memory_mb, namespace)
    else:
        raise ValueError(f"Unsupported platform: {platform}. Use 'android', 'ios', or 'webgl'.")


def _generate_android_config(
    permissions: list[str] | None = None,
    features: list[str] | None = None,
    namespace: str = "",
) -> str:
    """Generate Android manifest configuration script."""
    perms = permissions or ["android.permission.INTERNET"]
    feats = features or ["android.hardware.touchscreen"]

    # Build permission XML lines
    perm_xml_lines = ""
    for perm in perms:
        safe_perm = _sanitize_cs_string(perm)
        perm_xml_lines += f'    <uses-permission android:name=\\"{safe_perm}\\" />\\n'

    # Build feature XML lines
    feat_xml_lines = ""
    for feat in feats:
        safe_feat = _sanitize_cs_string(feat)
        feat_xml_lines += f'    <uses-feature android:name=\\"{safe_feat}\\" android:required=\\"true\\" />\\n'

    lines: list[str] = [
        "using UnityEditor;",
        "using UnityEngine;",
        "using System.IO;",
        "",
        "public static class VeilBreakers_AndroidConfig",
        "{",
        '    [MenuItem("VeilBreakers/Build/Configure Android")]',
        "    public static void Execute()",
        "    {",
        "        try",
        "        {",
        '            string manifestDir = "Assets/Plugins/Android";',
        "            if (!Directory.Exists(manifestDir))",
        "                Directory.CreateDirectory(manifestDir);",
        "",
        '            string manifestContent = "<?xml version=\\"1.0\\" encoding=\\"utf-8\\"?>\\n"',
        '                + "<manifest xmlns:android=\\"http://schemas.android.com/apk/res/android\\"\\n"',
        '                + "    xmlns:tools=\\"http://schemas.android.com/tools\\"\\n"',
        '                + "    package=\\"com.company.product\\">\\n"',
        '                + "\\n"',
        f'                + "{perm_xml_lines}"',
        f'                + "{feat_xml_lines}"',
        '                + "\\n"',
        '                + "    <application android:label=\\"@string/app_name\\"\\n"',
        '                + "                 tools:node=\\"merge\\">\\n"',
        '                + "        <activity android:name=\\"com.unity3d.player.UnityPlayerActivity\\"\\n"',
        '                + "                  android:screenOrientation=\\"landscape\\">\\n"',
        '                + "            <intent-filter>\\n"',
        '                + "                <action android:name=\\"android.intent.action.MAIN\\" />\\n"',
        '                + "                <category android:name=\\"android.intent.category.LAUNCHER\\" />\\n"',
        '                + "            </intent-filter>\\n"',
        '                + "        </activity>\\n"',
        '                + "    </application>\\n"',
        '                + "</manifest>\\n";',
        "",
        '            string manifestPath = Path.Combine(manifestDir, "AndroidManifest.xml");',
        "            File.WriteAllText(manifestPath, manifestContent);",
        "",
        f'            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"configure_android\\", \\"manifest_path\\": \\"" + manifestPath.Replace("\\\\", "/") + "\\"}}";',
        '            File.WriteAllText("Temp/vb_result.json", json);',
        '            Debug.Log("[VeilBreakers] Android manifest written to " + manifestPath);',
        "            AssetDatabase.Refresh();",
        "        }",
        "        catch (System.Exception ex)",
        "        {",
        '            string json = "{\\"status\\": \\"error\\", \\"action\\": \\"configure_android\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}";',
        '            File.WriteAllText("Temp/vb_result.json", json);',
        '            Debug.LogError("[VeilBreakers] Android config failed: " + ex.Message);',
        "        }",
        "    }",
        "}",
    ]

    lines = _wrap_namespace(lines, namespace)
    return "\n".join(lines) + "\n"


def _generate_ios_config(
    plist_entries: list[dict] | None = None,
    namespace: str = "",
) -> str:
    """Generate iOS PostProcessBuild configuration script."""
    entries = plist_entries or [
        {"key": "ITSAppUsesNonExemptEncryption", "value": "false", "type": "boolean"},
        {"key": "UIRequiresFullScreen", "value": "true", "type": "boolean"},
    ]

    lines: list[str] = [
        "using UnityEditor;",
        "using UnityEditor.Callbacks;",
        "using UnityEditor.iOS.Xcode;",
        "using System.IO;",
        "",
        "public class VeilBreakers_iOSPostProcess",
        "{",
        "    [PostProcessBuild]",
        "    public static void OnPostProcessBuild(BuildTarget target, string path)",
        "    {",
        "        if (target != BuildTarget.iOS) return;",
        "",
        '        string plistPath = Path.Combine(path, "Info.plist");',
        "        PlistDocument plist = new PlistDocument();",
        "        plist.ReadFromFile(plistPath);",
        "        PlistElementDict root = plist.root;",
        "",
    ]

    for entry in entries:
        safe_key = _sanitize_cs_string(entry["key"])
        safe_value = _sanitize_cs_string(entry["value"])
        entry_type = entry.get("type", "string")

        if entry_type == "boolean":
            bool_val = "true" if safe_value.lower() in ("true", "1", "yes") else "false"
            lines.append(f'        root.SetBoolean("{safe_key}", {bool_val});')
        else:
            lines.append(f'        root.SetString("{safe_key}", "{safe_value}");')

    lines.append("")
    lines.append("        plist.WriteToFile(plistPath);")
    lines.append("")
    lines.append("        // Add capabilities via PBXProject")
    lines.append('        string projPath = PBXProject.GetPBXProjectPath(path);')
    lines.append("        var proj = new PBXProject();")
    lines.append("        proj.ReadFromFile(projPath);")
    lines.append("        string targetGuid = proj.GetUnityMainTargetGuid();")
    lines.append("        proj.AddCapability(targetGuid, PBXCapabilityType.GameCenter);")
    lines.append("        proj.WriteToFile(projPath);")
    lines.append("")
    lines.append('        string resultPath = Path.Combine(path, "vb_ios_config_result.json");')
    lines.append('        string json = "{\\"status\\": \\"success\\", \\"action\\": \\"configure_ios\\", \\"plist_entries\\": " + ' + str(len(entries)) + ' + "}";')
    lines.append("        File.WriteAllText(resultPath, json);")
    lines.append('        Debug.Log("[VeilBreakers] iOS post-process build completed.");')
    lines.append("    }")
    lines.append("}")

    lines = _wrap_namespace(lines, namespace)
    return "\n".join(lines) + "\n"


def _generate_webgl_config(
    webgl_memory_mb: int = 256,
    namespace: str = "",
) -> str:
    """Generate WebGL configuration editor script."""
    lines: list[str] = [
        "using UnityEditor;",
        "using UnityEngine;",
        "using System.IO;",
        "",
        "public static class VeilBreakers_WebGLConfig",
        "{",
        '    [MenuItem("VeilBreakers/Build/Configure WebGL")]',
        "    public static void Execute()",
        "    {",
        "        try",
        "        {",
        f"            PlayerSettings.WebGL.memorySize = {webgl_memory_mb};",
        "            PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Brotli;",
        "            PlayerSettings.WebGL.linkerTarget = WebGLLinkerTarget.Wasm;",
        "            PlayerSettings.WebGL.template = \"APPLICATION:Default\";",
        "",
        f'            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"configure_webgl\\", \\"memorySize\\": {webgl_memory_mb}, \\"compressionFormat\\": \\"Brotli\\"}}";',
        '            File.WriteAllText("Temp/vb_result.json", json);',
        f'            Debug.Log("[VeilBreakers] WebGL configured: memory={webgl_memory_mb}MB, compression=Brotli");',
        "        }",
        "        catch (System.Exception ex)",
        "        {",
        '            string json = "{\\"status\\": \\"error\\", \\"action\\": \\"configure_webgl\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}";',
        '            File.WriteAllText("Temp/vb_result.json", json);',
        '            Debug.LogError("[VeilBreakers] WebGL config failed: " + ex.Message);',
        "        }",
        "    }",
        "}",
    ]

    lines = _wrap_namespace(lines, namespace)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# SHDR-03: Shader variant stripping
# ---------------------------------------------------------------------------

def generate_shader_stripping_script(
    keywords_to_strip: list[str] | None = None,
    log_stripping: bool = True,
    namespace: str = "",
) -> str:
    """Generate C# IPreprocessShaders implementation for shader variant stripping.

    Creates a class that strips shader variants containing specified keywords
    during the build process.  Optionally logs per-shader stripping statistics
    and writes a summary to Temp/vb_shader_strip_results.json via
    IPostprocessBuildWithReport.

    Args:
        keywords_to_strip: Shader keyword names to strip. Defaults to
            ["DEBUG", "_EDITOR"].
        log_stripping: If True, logs stripped variant counts per shader.
        namespace: Optional C# namespace to wrap the class in.

    Returns:
        Complete C# source string.
    """
    keywords = keywords_to_strip or ["DEBUG", "_EDITOR"]

    # Build keyword array initializer
    keyword_entries = []
    for kw in keywords:
        safe_kw = _sanitize_cs_string(kw)
        keyword_entries.append(f'        new ShaderKeyword("{safe_kw}")')

    keyword_array = ",\n".join(keyword_entries)

    lines: list[str] = [
        "using UnityEditor.Build;",
        "using UnityEditor.Rendering;",
        "using UnityEngine;",
        "using UnityEngine.Rendering;",
        "using System.Collections.Generic;",
        "",
        "public class VeilBreakers_ShaderStripper : IPreprocessShaders",
        "{",
        "    private static readonly ShaderKeyword[] _keywordsToStrip = new ShaderKeyword[]",
        "    {",
        f"{keyword_array}",
        "    };",
        "",
        "    public int callbackOrder { get { return 0; } }",
        "",
    ]

    if log_stripping:
        lines.append("    private static int _totalStripped = 0;")
        lines.append("    private static int _totalProcessed = 0;")
        lines.append("    private static readonly Dictionary<string, int> _strippedPerShader = new Dictionary<string, int>();")
        lines.append("")

    lines.append("    public void OnProcessShader(Shader shader, ShaderSnippetData snippet, IList<ShaderCompilerData> data)")
    lines.append("    {")
    lines.append("        int beforeCount = data.Count;")
    lines.append("        for (int i = data.Count - 1; i >= 0; i--)")
    lines.append("        {")
    lines.append("            foreach (var keyword in _keywordsToStrip)")
    lines.append("            {")
    lines.append("                if (data[i].shaderKeywordSet.IsEnabled(keyword))")
    lines.append("                {")
    lines.append("                    data.RemoveAt(i);")
    lines.append("                    break;")
    lines.append("                }")
    lines.append("            }")
    lines.append("        }")

    if log_stripping:
        lines.append("        int stripped = beforeCount - data.Count;")
        lines.append("        if (stripped > 0)")
        lines.append("        {")
        lines.append('            Debug.Log("[VeilBreakers] Stripped " + stripped + "/" + beforeCount + " variants from " + shader.name);')
        lines.append("            _totalStripped += stripped;")
        lines.append("            if (_strippedPerShader.ContainsKey(shader.name))")
        lines.append("                _strippedPerShader[shader.name] += stripped;")
        lines.append("            else")
        lines.append("                _strippedPerShader[shader.name] = stripped;")
        lines.append("        }")
        lines.append("        _totalProcessed += beforeCount;")

    lines.append("    }")
    lines.append("")

    # Add IPostprocessBuildWithReport for summary JSON
    lines.append("}")
    lines.append("")
    lines.append("public class VeilBreakers_ShaderStripReport : IPostprocessBuildWithReport")
    lines.append("{")
    lines.append("    public int callbackOrder { get { return 0; } }")
    lines.append("")
    lines.append("    public void OnPostprocessBuild(UnityEditor.Build.Reporting.BuildReport report)")
    lines.append("    {")
    lines.append('        string json = "{\\"status\\": \\"success\\", \\"action\\": \\"shader_stripping\\", \\"build_complete\\": true}";')
    lines.append('        System.IO.File.WriteAllText("Temp/vb_shader_strip_results.json", json);')
    lines.append('        Debug.Log("[VeilBreakers] Shader stripping report written.");')
    lines.append("    }")
    lines.append("}")

    lines = _wrap_namespace(lines, namespace)
    return "\n".join(lines) + "\n"
