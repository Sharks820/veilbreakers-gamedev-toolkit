"""Build & deploy template generators for Unity automation.

C# generators return complete source strings for Unity editor scripts.
Non-C# generators (CI/CD YAML, store metadata markdown) return plain text
for direct file write.

Exports:
    generate_multi_platform_build_script   -- BUILD-01: multi-platform build orchestrator
    generate_addressables_config_script    -- BUILD-02: Addressable group configurator
    generate_github_actions_workflow       -- BUILD-03: GitHub Actions YAML with GameCI v4
    generate_gitlab_ci_config              -- BUILD-03: GitLab CI YAML with GameCI Docker
    generate_version_management_script     -- BUILD-04: SemVer version bump C# editor script
    generate_changelog                     -- BUILD-04: git log -> CHANGELOG.md C# script
    generate_platform_config_script        -- BUILD-05: Android/iOS/WebGL config
    generate_shader_stripping_script       -- SHDR-03: IPreprocessShaders implementation
    generate_store_metadata                -- ACC-02: store description/ratings/privacy markdown

Pure-logic helpers:
    _validate_platforms                    -- validate platform dicts
    _validate_addressable_groups           -- validate addressable group dicts
"""

from __future__ import annotations

import re

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier


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
        safe_name = sanitize_cs_identifier(plat["name"])
        safe_target = sanitize_cs_identifier(plat["target"])
        safe_group = sanitize_cs_identifier(plat["group"])
        safe_backend = sanitize_cs_identifier(plat["backend"])
        extension = sanitize_cs_string(plat.get("extension", ""))

        lines.append(f"        // --- {safe_name} ---")
        lines.append("        try")
        lines.append("        {")
        lines.append(f'            Debug.Log("[VeilBreakers] Building {safe_name}...");')
        lines.append(f"            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.{safe_group}, BuildTarget.{safe_target});")
        lines.append(f"            PlayerSettings.SetScriptingBackend(NamedBuildTarget.FromBuildTargetGroup(BuildTargetGroup.{safe_group}), ScriptingImplementation.{safe_backend});")
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
        safe_name = sanitize_cs_string(grp["name"])
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
        lines.append('                Debug.Log("[VeilBreakers] Configured group: " + groupName);')
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
        safe_perm = sanitize_cs_string(perm)
        perm_xml_lines += f'    <uses-permission android:name=\\"{safe_perm}\\" />\\n'

    # Build feature XML lines
    feat_xml_lines = ""
    for feat in feats:
        safe_feat = sanitize_cs_string(feat)
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
        '            string json = "{\\"status\\": \\"success\\", \\"action\\": \\"configure_android\\", \\"manifest_path\\": \\"" + manifestPath.Replace("\\\\", "/") + "\\"}";',
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
        safe_key = sanitize_cs_string(entry["key"])
        safe_value = sanitize_cs_string(entry["value"])
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
        safe_kw = sanitize_cs_string(kw)
        keyword_entries.append(f'        new ShaderKeyword("{safe_kw}")')

    keyword_array = ",\n".join(keyword_entries)

    lines: list[str] = [
        "using UnityEditor.Build;",
        "using UnityEditor.Build.Reporting;",
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


# ---------------------------------------------------------------------------
# BUILD-03: CI/CD pipeline configuration -- GitHub Actions
# ---------------------------------------------------------------------------

_DEFAULT_CI_PLATFORMS: list[str] = [
    "StandaloneWindows64",
    "StandaloneOSX",
    "StandaloneLinux64",
    "Android",
    "iOS",
    "WebGL",
]

_ALLOWED_CI_PLATFORMS: set[str] = {
    "StandaloneWindows64",
    "StandaloneWindows",
    "StandaloneOSX",
    "StandaloneLinux64",
    "Android",
    "iOS",
    "WebGL",
    "tvOS",
    "PS4",
    "PS5",
    "XboxOne",
    "GameCoreXboxOne",
    "GameCoreXboxSeries",
    "Switch",
    "Stadia",
    "LinuxHeadlessSimulation",
    "EmbeddedLinux",
    "QNX",
    "VisionOS",
}


def _validate_ci_platforms(platforms: list[str]) -> list[str]:
    """Validate and return sanitised CI platform strings.

    Raises ``ValueError`` for any platform not in the known allowlist.
    All returned values are plain alphanumeric identifiers safe for YAML
    embedding.
    """
    validated: list[str] = []
    for plat in platforms:
        if not isinstance(plat, str):
            raise ValueError(f"CI platform must be a string, got {type(plat).__name__}")
        stripped = plat.strip()
        if stripped not in _ALLOWED_CI_PLATFORMS:
            raise ValueError(
                f"Unknown CI platform: '{stripped}'. "
                f"Allowed: {sorted(_ALLOWED_CI_PLATFORMS)}"
            )
        validated.append(stripped)
    return validated


def generate_github_actions_workflow(
    unity_version: str = "6000.0.0f1",
    platforms: list[str] | None = None,
    run_tests: bool = True,
    namespace: str = "",
) -> str:
    """Generate GitHub Actions workflow YAML for Unity CI/CD pipeline.

    Returns a complete YAML string (NOT C#) suitable for writing to
    ``.github/workflows/unity-build.yml``.  Uses GameCI v4 actions for
    test running and building, with matrix strategy across platforms.

    Args:
        unity_version: Unity editor version string (e.g. "6000.0.0f1").
        platforms: List of Unity BuildTarget platform names for the build
            matrix.  Defaults to all 6 standard platforms.
        run_tests: If True, includes a test job using
            ``game-ci/unity-test-runner@v4`` that the build job depends on.
        namespace: Unused -- kept for API consistency with other generators.

    Returns:
        Complete YAML string for the GitHub Actions workflow.
    """
    plats = _validate_ci_platforms(platforms or list(_DEFAULT_CI_PLATFORMS))

    lines: list[str] = []
    lines.append("name: Unity Build Pipeline")
    lines.append("")
    lines.append("on:")
    lines.append("  push:")
    lines.append("    branches: [main, develop]")
    lines.append("  pull_request:")
    lines.append("    branches: [main]")
    lines.append("  workflow_dispatch: {}")
    lines.append("")
    lines.append("env:")
    lines.append("  UNITY_LICENSE: ${{ secrets.UNITY_LICENSE }}")
    lines.append("  UNITY_EMAIL: ${{ secrets.UNITY_EMAIL }}")
    lines.append("  UNITY_PASSWORD: ${{ secrets.UNITY_PASSWORD }}")
    lines.append("")
    lines.append("jobs:")

    # -- Test job --
    if run_tests:
        lines.append("  test:")
        lines.append("    name: Run Tests")
        lines.append("    runs-on: ubuntu-latest")
        lines.append("    steps:")
        lines.append("      - uses: actions/checkout@v4")
        lines.append("        with:")
        lines.append("          lfs: true")
        lines.append("      - uses: actions/cache@v3")
        lines.append("        with:")
        lines.append("          path: Library")
        lines.append("          key: Library-Test-${{ hashFiles('Assets/**', 'Packages/**', 'ProjectSettings/**') }}")
        lines.append("          restore-keys: |")
        lines.append("            Library-Test-")
        lines.append("      - uses: game-ci/unity-test-runner@v4")
        lines.append("        env:")
        lines.append("          UNITY_LICENSE: ${{ secrets.UNITY_LICENSE }}")
        lines.append("          UNITY_EMAIL: ${{ secrets.UNITY_EMAIL }}")
        lines.append("          UNITY_PASSWORD: ${{ secrets.UNITY_PASSWORD }}")
        lines.append("        with:")
        lines.append(f"          unityVersion: {unity_version}")
        lines.append("          testMode: all")
        lines.append("          githubToken: ${{ secrets.GITHUB_TOKEN }}")
        lines.append("      - uses: actions/upload-artifact@v4")
        lines.append("        if: always()")
        lines.append("        with:")
        lines.append("          name: Test-Results")
        lines.append("          path: artifacts")
        lines.append("")

    # -- Build job --
    lines.append("  build:")
    lines.append("    name: Build (${{ matrix.targetPlatform }})")
    if run_tests:
        lines.append("    needs: test")
    lines.append("    runs-on: ubuntu-latest")
    lines.append("    strategy:")
    lines.append("      fail-fast: false")
    lines.append("      matrix:")
    lines.append("        targetPlatform:")
    for plat in plats:
        lines.append(f'          - "{plat}"')
    lines.append("    steps:")
    lines.append("      - uses: actions/checkout@v4")
    lines.append("        with:")
    lines.append("          lfs: true")
    lines.append("      - uses: actions/cache@v3")
    lines.append("        with:")
    lines.append("          path: Library")
    lines.append("          key: Library-${{ matrix.targetPlatform }}-${{ hashFiles('Assets/**', 'Packages/**', 'ProjectSettings/**') }}")
    lines.append("          restore-keys: |")
    lines.append("            Library-${{ matrix.targetPlatform }}-")
    lines.append("      - uses: game-ci/unity-builder@v4")
    lines.append("        env:")
    lines.append("          UNITY_LICENSE: ${{ secrets.UNITY_LICENSE }}")
    lines.append("          UNITY_EMAIL: ${{ secrets.UNITY_EMAIL }}")
    lines.append("          UNITY_PASSWORD: ${{ secrets.UNITY_PASSWORD }}")
    lines.append("        with:")
    lines.append(f"          unityVersion: {unity_version}")
    lines.append("          targetPlatform: ${{ matrix.targetPlatform }}")
    lines.append("          buildName: VeilBreakers")
    lines.append("      - uses: actions/upload-artifact@v4")
    lines.append("        with:")
    lines.append("          name: Build-${{ matrix.targetPlatform }}")
    lines.append("          path: build/${{ matrix.targetPlatform }}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# BUILD-03: CI/CD pipeline configuration -- GitLab CI
# ---------------------------------------------------------------------------

def generate_gitlab_ci_config(
    unity_version: str = "6000.0.0f1",
    platforms: list[str] | None = None,
    namespace: str = "",
) -> str:
    """Generate GitLab CI configuration YAML for Unity CI/CD pipeline.

    Returns a complete YAML string (NOT C#) suitable for writing to
    ``.gitlab-ci.yml``.  Uses GameCI Docker images for Unity builds.

    Args:
        unity_version: Unity editor version string (e.g. "6000.0.0f1").
        platforms: List of Unity BuildTarget platform names.  Defaults to
            all 6 standard platforms.
        namespace: Unused -- kept for API consistency with other generators.

    Returns:
        Complete YAML string for the GitLab CI configuration.
    """
    plats = _validate_ci_platforms(platforms or list(_DEFAULT_CI_PLATFORMS))

    # Map Unity target platform names to lowercase image suffixes
    _PLATFORM_IMAGE_MAP: dict[str, str] = {
        "StandaloneWindows64": "windows-mono",
        "StandaloneWindows": "windows-mono",
        "StandaloneOSX": "mac-mono",
        "StandaloneLinux64": "linux-il2cpp",
        "Android": "android",
        "iOS": "ios",
        "WebGL": "webgl",
        "tvOS": "appletv",
        "PS4": "ps4",
        "PS5": "ps5",
        "XboxOne": "xboxone",
        "GameCoreXboxOne": "xboxone",
        "GameCoreXboxSeries": "xboxseries",
        "Switch": "switch",
        "Stadia": "stadia",
        "LinuxHeadlessSimulation": "linux-il2cpp",
        "EmbeddedLinux": "linux-il2cpp",
        "QNX": "qnx",
        "VisionOS": "visionos",
    }

    lines: list[str] = []
    lines.append("stages:")
    lines.append("  - test")
    lines.append("  - build")
    lines.append("")
    lines.append("variables:")
    lines.append(f"  UNITY_VERSION: \"{unity_version}\"")
    lines.append("  IMAGE_VERSION: \"3\"")
    lines.append("")
    lines.append("# Cache the Library folder to speed up builds")
    lines.append("cache:")
    lines.append("  key: \"$CI_COMMIT_REF_SLUG\"")
    lines.append("  paths:")
    lines.append("    - Library/")
    lines.append("")
    lines.append(".unity_before_script: &unity_before_script")
    lines.append("  before_script:")
    lines.append("    - echo \"Activating Unity license...\"")
    lines.append("    - unity-editor -quit -batchmode -nographics -logFile /dev/stdout")
    lines.append("      -manualLicenseFile \"$UNITY_LICENSE_CONTENT\" || true")
    lines.append("")

    # -- Test job --
    lines.append("test:")
    lines.append("  stage: test")
    lines.append(f"  image: unityci/editor:ubuntu-{unity_version}-linux-il2cpp-${{IMAGE_VERSION}}")
    lines.append("  <<: *unity_before_script")
    lines.append("  script:")
    lines.append("    - unity-editor -runTests -batchmode -nographics -logFile /dev/stdout")
    lines.append("      -projectPath . -testResults results.xml -testPlatform EditMode")
    lines.append("    - unity-editor -runTests -batchmode -nographics -logFile /dev/stdout")
    lines.append("      -projectPath . -testResults results-play.xml -testPlatform PlayMode")
    lines.append("  artifacts:")
    lines.append("    paths:")
    lines.append("      - results.xml")
    lines.append("      - results-play.xml")
    lines.append("    reports:")
    lines.append("      junit: results.xml")
    lines.append("")

    # -- Build jobs (one per platform) --
    for plat in plats:
        image_suffix = _PLATFORM_IMAGE_MAP.get(plat, plat.lower())
        safe_job_name = plat.lower().replace("standalone", "build_")
        if safe_job_name.startswith("build_"):
            job_name = safe_job_name
        else:
            job_name = f"build_{safe_job_name}"

        lines.append(f"{job_name}:")
        lines.append("  stage: build")
        lines.append(f"  image: unityci/editor:ubuntu-{unity_version}-{image_suffix}-${{IMAGE_VERSION}}")
        lines.append("  <<: *unity_before_script")
        lines.append("  script:")
        lines.append("    - unity-editor -quit -batchmode -nographics -logFile /dev/stdout")
        lines.append(f'      -projectPath . -buildTarget "{plat}"')
        lines.append(f'      -customBuildPath "./build/{plat}"')
        lines.append("  artifacts:")
        lines.append("    paths:")
        lines.append(f'      - "./build/{plat}"')
        lines.append("  needs:")
        lines.append("    - test")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# BUILD-04: Version management
# ---------------------------------------------------------------------------

def generate_version_management_script(
    version: str = "1.0.0",
    auto_increment: str = "patch",
    update_android: bool = True,
    update_ios: bool = True,
    namespace: str = "",
) -> str:
    """Generate C# editor script for version management.

    Reads the current ``PlayerSettings.bundleVersion``, parses SemVer
    components, increments the specified component, and writes the new
    version back.  Optionally updates Android ``bundleVersionCode`` and
    iOS ``buildNumber``.

    Args:
        version: Initial/fallback version string if bundleVersion is empty.
        auto_increment: Which SemVer component to bump ("major", "minor",
            or "patch").
        update_android: If True, increments
            ``PlayerSettings.Android.bundleVersionCode``.
        update_ios: If True, sets
            ``PlayerSettings.iOS.buildNumber`` to the new version string.
        namespace: Optional C# namespace to wrap the class in.

    Returns:
        Complete C# source string.
    """
    safe_version = sanitize_cs_string(version)

    # Map auto_increment to the array index to bump
    increment_map = {"major": 0, "minor": 1, "patch": 2}
    inc_index = increment_map.get(auto_increment.lower(), 2)

    lines: list[str] = [
        "using UnityEditor;",
        "using UnityEngine;",
        "using System.IO;",
        "",
        "public static class VeilBreakers_VersionManager",
        "{",
        '    [MenuItem("VeilBreakers/Build/Bump Version")]',
        "    public static void Execute()",
        "    {",
        "        try",
        "        {",
        "            string currentVersion = PlayerSettings.bundleVersion;",
        "            if (string.IsNullOrEmpty(currentVersion))",
        f'                currentVersion = "{safe_version}";',
        "",
        "            string[] parts = currentVersion.Split('.');",
        "            int major = 0;",
        "            int minor = 0;",
        "            int patch = 0;",
        "",
        "            if (parts.Length >= 1) int.TryParse(parts[0], out major);",
        "            if (parts.Length >= 2) int.TryParse(parts[1], out minor);",
        "            if (parts.Length >= 3) int.TryParse(parts[2], out patch);",
        "",
        "            string oldVersion = major + \".\" + minor + \".\" + patch;",
        "",
    ]

    # Increment logic
    if inc_index == 0:
        lines.append("            major++;")
        lines.append("            minor = 0;")
        lines.append("            patch = 0;")
    elif inc_index == 1:
        lines.append("            minor++;")
        lines.append("            patch = 0;")
    else:
        lines.append("            patch++;")

    lines.append("")
    lines.append('            string newVersion = major + "." + minor + "." + patch;')
    lines.append("            PlayerSettings.bundleVersion = newVersion;")
    lines.append("")

    if update_android:
        lines.append("            // Increment Android version code")
        lines.append("            PlayerSettings.Android.bundleVersionCode++;")
        lines.append('            Debug.Log("[VeilBreakers] Android bundleVersionCode: " + PlayerSettings.Android.bundleVersionCode);')
        lines.append("")

    if update_ios:
        lines.append("            // Update iOS build number")
        lines.append("            PlayerSettings.iOS.buildNumber = newVersion;")
        lines.append('            Debug.Log("[VeilBreakers] iOS buildNumber: " + newVersion);')
        lines.append("")

    lines.append('            Debug.Log("[VeilBreakers] Version bumped: " + oldVersion + " -> " + newVersion);')
    lines.append("")
    lines.append('            string json = "{\\"status\\": \\"success\\", \\"action\\": \\"bump_version\\", "')
    lines.append('                + "\\"old_version\\": \\"" + oldVersion + "\\", "')
    lines.append('                + "\\"new_version\\": \\"" + newVersion + "\\"}";')
    lines.append('            File.WriteAllText("Temp/vb_result.json", json);')
    lines.append("        }")
    lines.append("        catch (System.Exception ex)")
    lines.append("        {")
    lines.append('            string json = "{\\"status\\": \\"error\\", \\"action\\": \\"bump_version\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}";')
    lines.append('            File.WriteAllText("Temp/vb_result.json", json);')
    lines.append('            Debug.LogError("[VeilBreakers] Version bump failed: " + ex.Message);')
    lines.append("        }")
    lines.append("    }")
    lines.append("}")

    lines = _wrap_namespace(lines, namespace)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# BUILD-04: Changelog generation
# ---------------------------------------------------------------------------

def generate_changelog(
    project_name: str = "VeilBreakers",
    version: str = "1.0.0",
    namespace: str = "",
) -> str:
    """Generate C# editor script that creates a CHANGELOG.md from git log.

    Uses ``System.Diagnostics.Process`` to run ``git log`` and
    ``git describe`` commands, parses conventional commit prefixes,
    and writes a grouped markdown changelog to the project root.

    Args:
        project_name: Name used in the changelog header.
        version: Current release version string for the heading.
        namespace: Optional C# namespace to wrap the class in.

    Returns:
        Complete C# source string.
    """
    safe_project = sanitize_cs_string(project_name)
    safe_version = sanitize_cs_string(version)

    lines: list[str] = [
        "using UnityEditor;",
        "using UnityEngine;",
        "using System;",
        "using System.Diagnostics;",
        "using System.IO;",
        "using System.Text;",
        "using System.Collections.Generic;",
        "",
        "public static class VeilBreakers_ChangelogGenerator",
        "{",
        '    [MenuItem("VeilBreakers/Build/Generate Changelog")]',
        "    public static void Execute()",
        "    {",
        "        try",
        "        {",
        "            // Discover the previous tag",
        '            string previousTag = RunGit("describe --tags --abbrev=0 HEAD~1").Trim();',
        "            if (string.IsNullOrEmpty(previousTag))",
        '                previousTag = "";',
        "",
        "            // Get commits since previous tag (or all commits)",
        '            string range = string.IsNullOrEmpty(previousTag) ? "HEAD" : previousTag + "..HEAD";',
        '            string logOutput = RunGit("log --pretty=format:\\"%h %s\\" --no-merges " + range);',
        "",
        "            // Group commits by conventional prefix",
        "            var features = new List<string>();",
        "            var fixes = new List<string>();",
        "            var docs = new List<string>();",
        "            var other = new List<string>();",
        "",
        "            string[] commitLines = logOutput.Split(new[] { '\\n' }, StringSplitOptions.RemoveEmptyEntries);",
        "            foreach (string line in commitLines)",
        "            {",
        "                string trimmed = line.Trim().TrimStart('\"').TrimEnd('\"');",
        "                if (string.IsNullOrEmpty(trimmed)) continue;",
        "",
        "                string lower = trimmed.ToLower();",
        '                if (lower.Contains("feat:") || lower.Contains("feat("))',
        "                    features.Add(trimmed);",
        '                else if (lower.Contains("fix:") || lower.Contains("fix("))',
        "                    fixes.Add(trimmed);",
        '                else if (lower.Contains("docs:") || lower.Contains("doc("))',
        "                    docs.Add(trimmed);",
        "                else",
        "                    other.Add(trimmed);",
        "            }",
        "",
        "            // Build the markdown",
        "            var sb = new StringBuilder();",
        f'            sb.AppendLine("# {safe_project} Changelog");',
        "            sb.AppendLine();",
        f'            sb.AppendLine("## [{safe_version}] - " + DateTime.Now.ToString("yyyy-MM-dd"));',
        "            sb.AppendLine();",
        "",
        '            AppendSection(sb, "Features", features);',
        '            AppendSection(sb, "Bug Fixes", fixes);',
        '            AppendSection(sb, "Documentation", docs);',
        '            AppendSection(sb, "Other Changes", other);',
        "",
        "            int commitCount = features.Count + fixes.Count + docs.Count + other.Count;",
        "",
        '            string changelogPath = Path.Combine(Application.dataPath, "..", "CHANGELOG.md");',
        "            File.WriteAllText(changelogPath, sb.ToString());",
        "",
        '            UnityEngine.Debug.Log("[VeilBreakers] Changelog written to " + changelogPath + " with " + commitCount + " commits.");',
        "",
        '            string json = "{\\"status\\": \\"success\\", \\"action\\": \\"generate_changelog\\", "',
        '                + "\\"commit_count\\": " + commitCount + ", "',
        f'                + "\\"version\\": \\"{safe_version}\\"" + "}}";',
        '            File.WriteAllText("Temp/vb_result.json", json);',
        "        }",
        "        catch (Exception ex)",
        "        {",
        '            string json = "{\\"status\\": \\"error\\", \\"action\\": \\"generate_changelog\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}";',
        '            File.WriteAllText("Temp/vb_result.json", json);',
        '            UnityEngine.Debug.LogError("[VeilBreakers] Changelog generation failed: " + ex.Message);',
        "        }",
        "    }",
        "",
        "    private static void AppendSection(StringBuilder sb, string heading, List<string> items)",
        "    {",
        "        if (items.Count == 0) return;",
        '        sb.AppendLine("### " + heading);',
        "        sb.AppendLine();",
        "        foreach (string item in items)",
        '            sb.AppendLine("- " + item);',
        "        sb.AppendLine();",
        "    }",
        "",
        "    private static string RunGit(string arguments)",
        "    {",
        "        var psi = new ProcessStartInfo",
        "        {",
        '            FileName = "git",',
        "            Arguments = arguments,",
        "            RedirectStandardOutput = true,",
        "            RedirectStandardError = true,",
        "            UseShellExecute = false,",
        "            CreateNoWindow = true,",
        '            WorkingDirectory = Path.Combine(Application.dataPath, "..")',
        "        };",
        "        using (var process = Process.Start(psi))",
        "        {",
        "            string output = process.StandardOutput.ReadToEnd();",
        "            process.WaitForExit();",
        "            return output;",
        "        }",
        "    }",
        "}",
    ]

    lines = _wrap_namespace(lines, namespace)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# ACC-02: Store publishing metadata
# ---------------------------------------------------------------------------

def generate_store_metadata(
    game_title: str = "VeilBreakers",
    genre: str = "Action RPG",
    has_iap: bool = False,
    has_ads: bool = False,
    collects_data: bool = False,
    namespace: str = "",
) -> str:
    """Generate store publishing metadata as a markdown document.

    Returns a multi-section markdown string with store description,
    content rating questionnaire answers, privacy policy template, and
    screenshot specifications.  This is plain text -- not C#.

    Args:
        game_title: Name of the game for the store listing.
        genre: Game genre for the description section.
        has_iap: Whether the game has in-app purchases.
        has_ads: Whether the game shows advertisements.
        collects_data: Whether the game collects user data.
        namespace: Unused -- kept for API consistency with other generators.

    Returns:
        Markdown string with all store metadata sections.
    """
    safe_title = game_title.replace("\\", "").replace('"', "")
    safe_genre = genre.replace("\\", "").replace('"', "")

    sections: list[str] = []

    # ---- Section 1: Store Description ----
    sections.append(f"# {safe_title} -- Store Publishing Metadata")
    sections.append("")
    sections.append("---")
    sections.append("")
    sections.append("## 1. Store Description")
    sections.append("")
    sections.append(f"**Title:** {safe_title}")
    sections.append(f"**Genre:** {safe_genre}")
    sections.append("")
    sections.append("### Short Description")
    sections.append("")
    sections.append(f"Dive into the dark fantasy world of {safe_title} -- a visceral {safe_genre}")
    sections.append("where every choice shapes your destiny and corruption lurks in every shadow.")
    sections.append("")
    sections.append("### Feature Highlights")
    sections.append("")
    sections.append("- **Intense Combat System** -- Master a deep combo-based combat system with")
    sections.append("  10 unique Brand powers and devastating synergy attacks.")
    sections.append("- **Dark Fantasy World** -- Explore a richly detailed world filled with")
    sections.append("  corrupted landscapes, ancient ruins, and hidden secrets.")
    sections.append("- **Deep Character Progression** -- Customize your playstyle with extensive")
    sections.append("  skill trees, equipment crafting, and Brand mastery.")
    sections.append("- **Challenging Boss Encounters** -- Face off against fearsome bosses with")
    sections.append("  multi-phase AI and unique mechanics.")
    sections.append("- **Dynamic World Events** -- Participate in world events that reshape the")
    sections.append("  environment and unlock new content.")
    sections.append("")
    sections.append("### System Requirements")
    sections.append("")
    sections.append("| | Minimum | Recommended |")
    sections.append("|---|---------|-------------|")
    sections.append("| OS | Windows 10 64-bit | Windows 11 64-bit |")
    sections.append("| CPU | Intel i5-6600 / AMD Ryzen 3 1200 | Intel i7-9700 / AMD Ryzen 5 3600 |")
    sections.append("| RAM | 8 GB | 16 GB |")
    sections.append("| GPU | GTX 1050 Ti / RX 570 | RTX 2060 / RX 5700 XT |")
    sections.append("| Storage | 20 GB | 30 GB SSD |")
    sections.append("| DirectX | Version 11 | Version 12 |")
    sections.append("")
    sections.append("**Age Rating:** See Content Rating Questionnaire below.")
    sections.append("")

    # ---- Section 2: Content Rating Questionnaire ----
    sections.append("---")
    sections.append("")
    sections.append("## 2. Content Rating Questionnaire")
    sections.append("")
    sections.append("> **REVIEW BEFORE SUBMISSION** -- These are pre-filled defaults for a dark")
    sections.append("> fantasy action RPG. Review and adjust all answers based on your game's")
    sections.append("> actual content before submitting to any rating authority.")
    sections.append("")
    sections.append("### ESRB (Entertainment Software Rating Board)")
    sections.append("")
    sections.append("| Category | Answer | Notes |")
    sections.append("|----------|--------|-------|")
    sections.append("| Violence | Frequent (Fantasy) | Combat is core gameplay; fantasy/stylized |")
    sections.append("| Blood | Stylized/Fantasy | Non-realistic blood effects |")
    sections.append("| Gore | Mild | Defeated enemies dissolve/fade |")
    sections.append("| Language | Mild | Occasional mild language in dialogue |")
    sections.append("| Suggestive Themes | None | No suggestive content |")
    sections.append("| Sexual Content | None | No sexual content |")
    sections.append("| Nudity | None | No nudity |")
    sections.append("| Substances | None | No alcohol, tobacco, or drug use |")
    sections.append("| Gambling | None | No real-money gambling mechanics |")
    sections.append(f"| In-App Purchases | {'Yes' if has_iap else 'No'} | {'Digital items/currency' if has_iap else 'No microtransactions'} |")
    sections.append("| User Interaction | Online features | Online multiplayer/leaderboards |")
    sections.append("")
    sections.append("**Expected Rating:** T (Teen) or M (Mature 17+)")
    sections.append("")
    sections.append("### PEGI (Pan European Game Information)")
    sections.append("")
    sections.append("| Category | Answer | Notes |")
    sections.append("|----------|--------|-------|")
    sections.append("| Violence | Yes | Fantasy combat with weapons and magic |")
    sections.append("| Fear | Yes | Dark fantasy atmosphere, horror elements |")
    sections.append("| Bad Language | Mild | Occasional mild language |")
    sections.append("| Sex | No | No sexual content |")
    sections.append("| Drugs | No | No drug references |")
    sections.append("| Discrimination | No | No discriminatory content |")
    sections.append("| Gambling | No | No gambling mechanics |")
    sections.append(f"| In-App Purchases | {'Yes' if has_iap else 'No'} | {'Contains optional purchases' if has_iap else 'No in-app purchases'} |")
    sections.append("")
    sections.append("**Expected Rating:** PEGI 16")
    sections.append("")
    sections.append("### IARC (International Age Rating Coalition)")
    sections.append("")
    sections.append("Complete the IARC questionnaire at https://www.globalratings.com/ using")
    sections.append("the answers above as guidance. IARC provides a unified rating across")
    sections.append("multiple territories.")
    sections.append("")

    # ---- Section 3: Privacy Policy Template ----
    sections.append("---")
    sections.append("")
    sections.append("## 3. Privacy Policy Template")
    sections.append("")
    sections.append("> **THIS IS A TEMPLATE -- CONSULT A LAWYER BEFORE USE.**")
    sections.append("> This template is provided as a starting point only. Laws vary by")
    sections.append("> jurisdiction. You must have this reviewed by qualified legal counsel.")
    sections.append("")
    sections.append(f"### Privacy Policy for {safe_title}")
    sections.append("")
    sections.append("**Last Updated:** [DATE]")
    sections.append("")
    sections.append(f"This Privacy Policy describes how {safe_title} (\"we\", \"us\", or \"our\")")
    sections.append("collects, uses, and shares information when you use our game.")
    sections.append("")

    # Information Collected
    sections.append("#### Information We Collect")
    sections.append("")
    if collects_data:
        sections.append("We collect the following types of information:")
        sections.append("")
        sections.append("- **Account Information:** Email address and username when you create an account.")
        sections.append("- **Gameplay Data:** Game progress, achievements, and play statistics.")
        sections.append("- **Device Information:** Device type, operating system, and hardware identifiers.")
        sections.append("- **Analytics Data:** App usage patterns and crash reports to improve the game.")
    else:
        sections.append("We collect minimal information necessary for the game to function:")
        sections.append("")
        sections.append("- **Gameplay Data:** Game progress and settings stored locally on your device.")
        sections.append("- **Crash Reports:** Anonymous crash data to improve game stability.")
    sections.append("")

    # How Information Is Used
    sections.append("#### How We Use Information")
    sections.append("")
    sections.append("We use collected information to:")
    sections.append("")
    sections.append("- Provide and maintain the game experience.")
    sections.append("- Fix bugs and improve game performance.")
    if collects_data:
        sections.append("- Personalize your gaming experience.")
        sections.append("- Communicate with you about updates and features.")
    sections.append("")

    # Third-Party Services
    sections.append("#### Third-Party Services")
    sections.append("")
    if has_ads:
        sections.append("We use the following third-party services that may collect information:")
        sections.append("")
        sections.append("- **Advertising Partners:** We display ads through third-party ad networks")
        sections.append("  that may use cookies and similar technologies to serve personalized ads.")
        sections.append("- **Analytics Providers:** We use analytics services to understand game usage.")
    else:
        sections.append("We do not display third-party advertisements. We may use analytics services")
        sections.append("to understand game usage and improve performance. These services collect")
        sections.append("anonymous, aggregated data only.")
    sections.append("")

    # In-App Purchases
    if has_iap:
        sections.append("#### In-App Purchases")
        sections.append("")
        sections.append("Our game offers optional in-app purchases. All transactions are processed")
        sections.append("through the platform's official payment system (Apple App Store, Google Play,")
        sections.append("or Steam). We do not directly collect or store payment information.")
        sections.append("")

    # Children's Privacy
    sections.append("#### Children's Privacy")
    sections.append("")
    sections.append("This game is not directed at children under 13 years of age. We do not")
    sections.append("knowingly collect personal information from children under 13. If you")
    sections.append("believe we have collected information from a child under 13, please contact")
    sections.append("us immediately so we can delete it. (COPPA compliance note)")
    sections.append("")

    # Contact
    sections.append("#### Contact Information")
    sections.append("")
    sections.append("For questions about this Privacy Policy, please contact:")
    sections.append("")
    sections.append("- **Email:** [YOUR_PRIVACY_EMAIL]")
    sections.append("- **Website:** [YOUR_WEBSITE_URL]")
    sections.append("- **Address:** [YOUR_BUSINESS_ADDRESS]")
    sections.append("")

    # ---- Section 4: Screenshot Specifications ----
    sections.append("---")
    sections.append("")
    sections.append("## 4. Screenshot Specifications")
    sections.append("")
    sections.append("### iOS (App Store)")
    sections.append("")
    sections.append("| Device | Size | Required |")
    sections.append("|--------|------|----------|")
    sections.append('| iPhone 6.7" (14 Pro Max) | 1290 x 2796 | Yes |')
    sections.append('| iPhone 6.5" (11 Pro Max) | 1242 x 2688 | Yes |')
    sections.append('| iPhone 5.5" (8 Plus) | 1242 x 2208 | Yes |')
    sections.append('| iPad Pro 12.9" | 2048 x 2732 | If supporting iPad |')
    sections.append("")
    sections.append("### Android (Google Play)")
    sections.append("")
    sections.append("| Type | Size | Required |")
    sections.append("|------|------|----------|")
    sections.append("| Phone screenshot | 1080 x 1920 (min) | Yes (2-8 screenshots) |")
    sections.append('| 7" Tablet screenshot | 1200 x 1920 | If supporting tablets |')
    sections.append('| 10" Tablet screenshot | 1600 x 2560 | If supporting tablets |')
    sections.append("| Feature graphic | 1024 x 500 | Yes |")
    sections.append("")
    sections.append("### Steam")
    sections.append("")
    sections.append("| Type | Size | Required |")
    sections.append("|------|------|----------|")
    sections.append("| Screenshot | 1920 x 1080 (minimum) | Yes (5+ recommended) |")
    sections.append("| Header capsule | 460 x 215 | Yes |")
    sections.append("| Small capsule | 231 x 87 | Yes |")
    sections.append("| Large capsule | 467 x 181 | Yes |")
    sections.append("| Hero graphic | 3840 x 1240 | Recommended |")
    sections.append("| Library capsule | 600 x 900 | Yes |")
    sections.append("")
    sections.append("**Format:** PNG or JPG, no alpha channel, no letterboxing.")
    sections.append("Capture at the highest resolution possible and downscale as needed.")
    sections.append("")

    return "\n".join(sections)
