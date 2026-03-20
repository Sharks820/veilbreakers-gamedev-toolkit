"""C# editor script template generators for AAA quality enforcement.

Generates Unity editor scripts that validate and enforce AAA quality
standards for VeilBreakers game assets: polygon budgets, master material
library, texture quality, and combined quality auditing.

All generated scripts write their result to Temp/vb_result.json so that
the Python MCP server can read back the outcome after execution.

Exports:
    generate_poly_budget_check_script      -- AAA-02: Per-asset-type polygon budget check
    generate_master_material_script        -- AAA-04: Master material library generation
    generate_texture_quality_check_script  -- AAA-06: Texture quality validation
    generate_aaa_validation_script         -- Combined AAA quality audit

Helpers:
    _sanitize_cs_string                    -- C# string literal escaping
    _sanitize_cs_identifier                -- C# identifier sanitization
"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Sanitization helpers (each template module has its own copy)
# ---------------------------------------------------------------------------


def _sanitize_cs_string(value: str) -> str:
    """Escape a value for safe embedding inside a C# string literal.

    Prevents C# code injection by escaping backslashes, quotes, and
    newlines.
    """
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    return value


def _sanitize_cs_identifier(value: str) -> str:
    """Sanitize a value for use as a C# identifier (class name, method name)."""
    return re.sub(r"[^a-zA-Z0-9_]", "", value)


# ---------------------------------------------------------------------------
# Default master material definitions
# ---------------------------------------------------------------------------

_DEFAULT_MATERIALS: list[dict] = [
    {
        "name": "stone",
        "color_hex": "6B6B6B",
        "metallic": 0.0,
        "roughness": 0.85,
        "normal_strength": 1.2,
    },
    {
        "name": "wood",
        "color_hex": "4A3728",
        "metallic": 0.0,
        "roughness": 0.7,
        "normal_strength": 0.8,
    },
    {
        "name": "iron",
        "color_hex": "3D3D3D",
        "metallic": 0.9,
        "roughness": 0.4,
        "normal_strength": 1.0,
    },
    {
        "name": "moss",
        "color_hex": "2D4A2D",
        "metallic": 0.0,
        "roughness": 0.9,
        "normal_strength": 0.6,
    },
    {
        "name": "bone",
        "color_hex": "C8B89A",
        "metallic": 0.0,
        "roughness": 0.6,
        "normal_strength": 0.7,
    },
    {
        "name": "cloth",
        "color_hex": "3D2B2B",
        "metallic": 0.0,
        "roughness": 0.8,
        "normal_strength": 0.5,
    },
    {
        "name": "leather",
        "color_hex": "5C3A1E",
        "metallic": 0.0,
        "roughness": 0.65,
        "normal_strength": 0.9,
    },
]

# ---------------------------------------------------------------------------
# Per-asset-type polygon budgets (mirrors palette_validator.ASSET_TYPE_BUDGETS)
# ---------------------------------------------------------------------------

_BUDGET_MAP: dict[str, tuple[int, int]] = {
    "hero":     (30000, 50000),
    "mob":      (8000,  15000),
    "weapon":   (3000,  8000),
    "prop":     (500,   6000),
    "building": (5000,  15000),
}


# ---------------------------------------------------------------------------
# AAA-02: Polygon Budget Check
# ---------------------------------------------------------------------------


def generate_poly_budget_check_script(
    asset_type: str = "prop",
    target_path: str = "",
    auto_flag: bool = True,
) -> str:
    """Generate a C# editor script that checks mesh poly counts against budgets.

    Args:
        asset_type: Asset type to check against (hero, mob, weapon, prop, building).
        target_path: Specific asset path or folder to scan. Empty = all Assets.
        auto_flag: If True, tag over-budget assets for retopo.

    Returns:
        Complete C# source string for a Unity editor script.
    """
    safe_type = _sanitize_cs_identifier(asset_type)
    safe_path = _sanitize_cs_string(target_path or "Assets")
    budget_min, budget_max = _BUDGET_MAP.get(asset_type, (500, 6000))

    auto_flag_block = ""
    if auto_flag:
        auto_flag_block = (
            '                    if (status == "over_budget")\n'
            "                    {\n"
            "                        var labels = new System.Collections.Generic.List<string>"
            "(AssetDatabase.GetLabels(AssetDatabase.LoadAssetAtPath<Object>(assetPath)));\n"
            '                        if (!labels.Contains("vb_needs_retopo"))\n'
            "                        {\n"
            '                            labels.Add("vb_needs_retopo");\n'
            "                            AssetDatabase.SetLabels("
            "AssetDatabase.LoadAssetAtPath<Object>(assetPath), labels.ToArray());\n"
            "                        }\n"
            "                    }\n"
        )

    lines = [
        "using UnityEngine;",
        "using UnityEditor;",
        "using System.IO;",
        "using System.Collections.Generic;",
        "",
        "public class VeilBreakers_PolyBudgetCheck_" + safe_type,
        "{",
        "    private const int BudgetMin = " + str(budget_min) + ";",
        "    private const int BudgetMax = " + str(budget_max) + ";",
        '    private const string AssetType = "' + _sanitize_cs_string(asset_type) + '";',
        "",
        '    [MenuItem("VeilBreakers/Quality/Check Poly Budget")]',
        "    public static void CheckPolyBudget()",
        "    {",
        '        string searchPath = "' + safe_path + '";',
        '        string[] guids = AssetDatabase.FindAssets("t:Mesh", new[] { searchPath });',
        "",
        "        var results = new List<Dictionary<string, object>>();",
        "        int overCount = 0;",
        "        int underCount = 0;",
        "        int okCount = 0;",
        "",
        "        foreach (string guid in guids)",
        "        {",
        "            string assetPath = AssetDatabase.GUIDToAssetPath(guid);",
        "            Mesh mesh = AssetDatabase.LoadAssetAtPath<Mesh>(assetPath);",
        "",
        "            if (mesh == null) continue;",
        "            if (!mesh.isReadable) { Debug.LogWarning(\"Mesh '\" + assetPath + \"' is not readable. Enable Read/Write in import settings.\"); continue; }",
        "",
        "            int triCount = mesh.triangles.Length / 3;",
        "            string status;",
        "",
        "            if (triCount > BudgetMax)",
        "            {",
        '                status = "over_budget";',
        "                overCount++;",
        "            }",
        "            else if (triCount < BudgetMin)",
        "            {",
        '                status = "under_budget";',
        "                underCount++;",
        "            }",
        "            else",
        "            {",
        '                status = "ok";',
        "                okCount++;",
        "            }",
        "",
        auto_flag_block,
        "            var entry = new Dictionary<string, object>",
        "            {",
        '                { "name", mesh.name },',
        '                { "path", assetPath },',
        '                { "tri_count", triCount },',
        '                { "budget_min", BudgetMin },',
        '                { "budget_max", BudgetMax },',
        '                { "asset_type", AssetType },',
        '                { "status", status }',
        "            };",
        "            results.Add(entry);",
        "        }",
        "",
        "        // Write result to vb_result.json",
        "        var sb = new System.Text.StringBuilder();",
        '        sb.Append("{");',
        '        sb.Append("\\"tool\\": \\"poly_budget_check\\", ");',
        '        sb.AppendFormat("\\"asset_type\\": \\"{0}\\", ", AssetType);',
        '        sb.AppendFormat("\\"budget_min\\": {0}, ", BudgetMin);',
        '        sb.AppendFormat("\\"budget_max\\": {0}, ", BudgetMax);',
        '        sb.AppendFormat("\\"total_checked\\": {0}, ", results.Count);',
        '        sb.AppendFormat("\\"over_budget\\": {0}, ", overCount);',
        '        sb.AppendFormat("\\"under_budget\\": {0}, ", underCount);',
        '        sb.AppendFormat("\\"within_budget\\": {0}, ", okCount);',
        '        sb.Append("\\"status\\": \\"success\\"");',
        '        sb.Append("}");',
        "",
        '        string resultPath = Path.Combine(Application.dataPath, "../Temp/vb_result.json");',
        "        File.WriteAllText(resultPath, sb.ToString());",
        "",
        '        Debug.Log("[VeilBreakers] Poly Budget Check (" + AssetType + "): " + okCount + " OK, " + overCount + " over, " + underCount + " under out of " + results.Count + " meshes");',
        "    }",
        "}",
    ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# AAA-04: Master Material Library
# ---------------------------------------------------------------------------


def _hex_to_color_cs(hex_str: str) -> str:
    """Convert hex color string to C# Color constructor args."""
    hex_str = hex_str.lstrip("#")
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    return "%.3ff, %.3ff, %.3ff, 1.0f" % (r, g, b)


def generate_master_material_script(
    output_folder: str = "Assets/Data/Materials/MasterLibrary",
    materials: list[dict] | None = None,
) -> str:
    """Generate a C# editor script that creates the master material library.

    Uses URP Lit material properties (not Shader Graph) per VeilBreakers
    dark fantasy aesthetic.

    Args:
        output_folder: Unity folder for generated materials.
        materials: Optional list of material dicts. Each dict must have:
            name (str), color_hex (str), metallic (float),
            roughness (float), normal_strength (float).
            If None, uses the 7 default dark fantasy materials.

    Returns:
        Complete C# source string for a Unity editor script.
    """
    mats = materials or _DEFAULT_MATERIALS
    safe_folder = _sanitize_cs_string(output_folder)

    # Generate material creation code blocks
    mat_blocks = []
    for mat in mats:
        name = _sanitize_cs_string(mat["name"])
        safe_id = _sanitize_cs_identifier(mat["name"])
        color_hex = mat.get("color_hex", "808080")
        metallic = mat.get("metallic", 0.0)
        roughness = mat.get("roughness", 0.5)
        smoothness = 1.0 - roughness
        normal_strength = mat.get("normal_strength", 1.0)
        color_cs = _hex_to_color_cs(color_hex)

        block = [
            "            // " + name,
            "            {",
            '                Material mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));',
            '                mat.name = "VB_Master_' + safe_id + '";',
            '                mat.SetColor("_BaseColor", new Color(' + color_cs + '));',
            '                mat.SetFloat("_Metallic", ' + ("%.2ff" % metallic) + ");",
            '                mat.SetFloat("_Smoothness", ' + ("%.2ff" % smoothness) + ");",
            '                mat.SetFloat("_BumpScale", ' + ("%.2ff" % normal_strength) + ");",
            "",
            '                string matPath = folderPath + "/VB_Master_' + safe_id + '.mat";',
            "                AssetDatabase.CreateAsset(mat, matPath);",
            '                createdMats.Add("' + name + '");',
            "            }",
        ]
        mat_blocks.append("\n".join(block))

    mat_code = "\n\n".join(mat_blocks)

    lines = [
        "using UnityEngine;",
        "using UnityEditor;",
        "using System.IO;",
        "using System.Collections.Generic;",
        "",
        "public class VeilBreakers_MasterMaterials",
        "{",
        '    private const string OutputFolder = "' + safe_folder + '";',
        "",
        '    [MenuItem("VeilBreakers/Quality/Generate Master Material Library")]',
        "    public static void GenerateMasterMaterials()",
        "    {",
        "        string folderPath = OutputFolder;",
        "",
        "        // Create folder hierarchy if needed",
        "        string[] parts = folderPath.Split('/');",
        '        string currentPath = parts[0]; // "Assets"',
        "        for (int i = 1; i < parts.Length; i++)",
        "        {",
        '            string nextPath = currentPath + "/" + parts[i];',
        "            if (!AssetDatabase.IsValidFolder(nextPath))",
        "            {",
        "                AssetDatabase.CreateFolder(currentPath, parts[i]);",
        "            }",
        "            currentPath = nextPath;",
        "        }",
        "",
        "        var createdMats = new List<string>();",
        "",
        mat_code,
        "",
        "        AssetDatabase.SaveAssets();",
        "        AssetDatabase.Refresh();",
        "",
        "        // Write result to vb_result.json",
        "        var sb = new System.Text.StringBuilder();",
        '        sb.Append("{");',
        '        sb.Append("\\"tool\\": \\"master_material_library\\", ");',
        '        sb.AppendFormat("\\"output_folder\\": \\"{0}\\", ", OutputFolder);',
        '        sb.AppendFormat("\\"materials_created\\": {0}, ", createdMats.Count);',
        '        sb.Append("\\"materials\\": [");',
        "        for (int i = 0; i < createdMats.Count; i++)",
        "        {",
        '            if (i > 0) sb.Append(", ");',
        '            sb.AppendFormat("\\"{0}\\"", createdMats[i]);',
        "        }",
        '        sb.Append("], ");',
        '        sb.Append("\\"status\\": \\"success\\"");',
        '        sb.Append("}");',
        "",
        '        string resultPath = Path.Combine(Application.dataPath, "../Temp/vb_result.json");',
        "        File.WriteAllText(resultPath, sb.ToString());",
        "",
        '        Debug.Log("[VeilBreakers] Created " + createdMats.Count + " master materials in " + OutputFolder);',
        "    }",
        "}",
    ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# AAA-06: Texture Quality Check
# ---------------------------------------------------------------------------


def generate_texture_quality_check_script(
    target_folder: str = "Assets",
    target_texel_density: float = 10.24,
    check_normal_maps: bool = True,
    check_channel_packing: bool = True,
) -> str:
    """Generate a C# editor script that validates texture quality standards.

    Checks:
        - Texel density against target (px/cm)
        - Normal map presence for models with albedo textures
        - M/R/AO channel packing correctness

    Args:
        target_folder: Unity folder to scan for textures.
        target_texel_density: Target texel density in px/cm (default 10.24).
        check_normal_maps: Whether to verify normal map presence.
        check_channel_packing: Whether to verify M/R/AO channel packing.

    Returns:
        Complete C# source string for a Unity editor script.
    """
    safe_folder = _sanitize_cs_string(target_folder)
    texel_str = "%.2ff" % target_texel_density

    normal_check_block = ""
    if check_normal_maps:
        normal_check_block = "\n".join([
            "",
            "        // --- Normal Map Presence Check ---",
            '        string[] modelGuids = AssetDatabase.FindAssets("t:Model", new[] { searchPath });',
            "        foreach (string mGuid in modelGuids)",
            "        {",
            "            string modelPath = AssetDatabase.GUIDToAssetPath(mGuid);",
            '            string modelDir = Path.GetDirectoryName(modelPath).Replace("\\\\", "/");',
            "            string modelName = Path.GetFileNameWithoutExtension(modelPath);",
            "",
            "            // Check for corresponding albedo texture",
            '            string[] albedoSearch = AssetDatabase.FindAssets(modelName + "_Albedo t:Texture2D", new[] { modelDir });',
            "            if (albedoSearch.Length == 0)",
            '                albedoSearch = AssetDatabase.FindAssets(modelName + "_BaseColor t:Texture2D", new[] { modelDir });',
            "",
            "            if (albedoSearch.Length > 0)",
            "            {",
            "                // Has albedo, check for normal map",
            '                string[] normalSearch = AssetDatabase.FindAssets(modelName + "_Normal t:Texture2D", new[] { modelDir });',
            "                if (normalSearch.Length == 0)",
            "                {",
            "                    issueCount++;",
            "                    warningCount++;",
            "                }",
            "            }",
            "        }",
        ])

    channel_packing_block = ""
    if check_channel_packing:
        channel_packing_block = "\n".join([
            "",
            "        // --- Channel Packing Check (M/R/AO) ---",
            "        foreach (string guid in texGuids)",
            "        {",
            "            string texPath = AssetDatabase.GUIDToAssetPath(guid);",
            "            string texName = Path.GetFileNameWithoutExtension(texPath);",
            "",
            "            // Check for MRA or ORM packed textures",
            '            if (texName.EndsWith("_MRA") || texName.EndsWith("_ORM") ||',
            '                texName.EndsWith("_MaskMap") || texName.EndsWith("_PackedMap"))',
            "            {",
            "                TextureImporter importer = AssetImporter.GetAtPath(texPath) as TextureImporter;",
            "                if (importer != null && importer.sRGBTexture)",
            "                {",
            "                    // Packed maps should be linear, not sRGB",
            "                    packingIssues++;",
            "                    issueCount++;",
            "                }",
            "                packedTexCount++;",
            "            }",
            "        }",
        ])

    lines = [
        "using UnityEngine;",
        "using UnityEditor;",
        "using System.IO;",
        "using System.Collections.Generic;",
        "",
        "public class VeilBreakers_TextureQualityCheck",
        "{",
        "    private const float TargetTexelDensity = " + texel_str + "; // px/cm",
        '    private const string SearchFolder = "' + safe_folder + '";',
        "",
        '    [MenuItem("VeilBreakers/Quality/Check Texture Quality")]',
        "    public static void CheckTextureQuality()",
        "    {",
        "        string searchPath = SearchFolder;",
        '        string[] texGuids = AssetDatabase.FindAssets("t:Texture2D", new[] { searchPath });',
        "",
        "        int totalTextures = texGuids.Length;",
        "        int issueCount = 0;",
        "        int warningCount = 0;",
        "        int packedTexCount = 0;",
        "        int packingIssues = 0;",
        "",
        "        // --- Texel Density Check ---",
        '        string[] meshGuids = AssetDatabase.FindAssets("t:Mesh", new[] { searchPath });',
        "        int densityChecked = 0;",
        "        int densityPassed = 0;",
        "",
        "        foreach (string mGuid in meshGuids)",
        "        {",
        "            string meshPath = AssetDatabase.GUIDToAssetPath(mGuid);",
        "            Mesh mesh = AssetDatabase.LoadAssetAtPath<Mesh>(meshPath);",
        "            if (mesh == null || mesh.uv == null || mesh.uv.Length == 0) continue;",
        "            if (!mesh.isReadable) { Debug.LogWarning(\"Mesh '\" + meshPath + \"' is not readable. Enable Read/Write in import settings.\"); continue; }",
        "",
        "            // Find associated texture",
        '            string meshDir = Path.GetDirectoryName(meshPath).Replace("\\\\", "/");',
        "            string meshName = Path.GetFileNameWithoutExtension(meshPath);",
        '            string[] albedoGuids = AssetDatabase.FindAssets(meshName + "_Albedo t:Texture2D", new[] { meshDir });',
        "            if (albedoGuids.Length == 0) continue;",
        "",
        "            string albedoPath = AssetDatabase.GUIDToAssetPath(albedoGuids[0]);",
        "            Texture2D tex = AssetDatabase.LoadAssetAtPath<Texture2D>(albedoPath);",
        "            if (tex == null) continue;",
        "",
        "            // Estimate texel density: texture_resolution / sqrt(surface_area_cm2)",
        "            float surfaceArea = 0f;",
        "            Vector3[] verts = mesh.vertices;",
        "            int[] tris = mesh.triangles;",
        "            for (int i = 0; i < tris.Length; i += 3)",
        "            {",
        "                Vector3 a = verts[tris[i]];",
        "                Vector3 b = verts[tris[i + 1]];",
        "                Vector3 c = verts[tris[i + 2]];",
        "                surfaceArea += Vector3.Cross(b - a, c - a).magnitude * 0.5f;",
        "            }",
        "",
        "            if (surfaceArea > 0.0001f)",
        "            {",
        "                float surfaceAreaCm2 = surfaceArea * 10000f;",
        "                float texelDensity = tex.width / Mathf.Sqrt(surfaceAreaCm2);",
        "                densityChecked++;",
        "",
        "                if (texelDensity >= TargetTexelDensity * 0.5f)",
        "                {",
        "                    densityPassed++;",
        "                }",
        "                else",
        "                {",
        "                    issueCount++;",
        "                }",
        "            }",
        "        }",
        normal_check_block,
        channel_packing_block,
        "",
        "        // Write result to vb_result.json",
        "        var sb = new System.Text.StringBuilder();",
        '        sb.Append("{");',
        '        sb.Append("\\"tool\\": \\"texture_quality_check\\", ");',
        '        sb.AppendFormat("\\"target_folder\\": \\"{0}\\", ", SearchFolder);',
        '        sb.AppendFormat("\\"target_texel_density\\": {0}, ", TargetTexelDensity);',
        '        sb.AppendFormat("\\"total_textures\\": {0}, ", totalTextures);',
        '        sb.AppendFormat("\\"density_checked\\": {0}, ", densityChecked);',
        '        sb.AppendFormat("\\"density_passed\\": {0}, ", densityPassed);',
        '        sb.AppendFormat("\\"packed_textures\\": {0}, ", packedTexCount);',
        '        sb.AppendFormat("\\"packing_issues\\": {0}, ", packingIssues);',
        '        sb.AppendFormat("\\"total_issues\\": {0}, ", issueCount);',
        '        sb.AppendFormat("\\"warnings\\": {0}, ", warningCount);',
        '        sb.Append("\\"status\\": \\"success\\"");',
        '        sb.Append("}");',
        "",
        '        string resultPath = Path.Combine(Application.dataPath, "../Temp/vb_result.json");',
        "        File.WriteAllText(resultPath, sb.ToString());",
        "",
        '        Debug.Log("[VeilBreakers] Texture Quality: " + totalTextures + " textures, " + issueCount + " issues, " + warningCount + " warnings");',
        "    }",
        "}",
    ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Combined AAA Validation
# ---------------------------------------------------------------------------


def generate_aaa_validation_script(
    target_folder: str = "Assets",
    asset_type: str = "prop",
    check_poly: bool = True,
    check_textures: bool = True,
    check_materials: bool = True,
) -> str:
    """Generate a combined C# editor script that runs all AAA quality checks.

    Aggregates polygon budget, texture quality, and material library
    validation into a single audit pass with unified reporting.

    Args:
        target_folder: Unity folder to audit.
        asset_type: Asset type for poly budget check.
        check_poly: Whether to run polygon budget checks.
        check_textures: Whether to run texture quality checks.
        check_materials: Whether to check material references.

    Returns:
        Complete C# source string for a Unity editor script.
    """
    safe_folder = _sanitize_cs_string(target_folder)
    safe_type = _sanitize_cs_identifier(asset_type)
    budget_min, budget_max = _BUDGET_MAP.get(asset_type, (500, 6000))

    poly_block = ""
    if check_poly:
        poly_block = "\n".join([
            "",
            "        // --- Polygon Budget Check ---",
            '        string[] meshGuids = AssetDatabase.FindAssets("t:Mesh", new[] { searchPath });',
            "        int polyTotal = 0;",
            "        int polyOver = 0;",
            "        int polyUnder = 0;",
            "        int polyOk = 0;",
            "",
            "        foreach (string guid in meshGuids)",
            "        {",
            "            string meshPath = AssetDatabase.GUIDToAssetPath(guid);",
            "            Mesh mesh = AssetDatabase.LoadAssetAtPath<Mesh>(meshPath);",
            "            if (mesh == null) continue;",
            "            if (!mesh.isReadable) { Debug.LogWarning(\"Mesh '\" + meshPath + \"' is not readable. Enable Read/Write in import settings.\"); continue; }",
            "",
            "            int triCount = mesh.triangles.Length / 3;",
            "            polyTotal++;",
            "",
            "            if (triCount > " + str(budget_max) + ")",
            "            {",
            "                polyOver++;",
            "                failCount++;",
            "            }",
            "            else if (triCount < " + str(budget_min) + ")",
            "            {",
            "                polyUnder++;",
            "                warnCount++;",
            "            }",
            "            else",
            "            {",
            "                polyOk++;",
            "                passCount++;",
            "            }",
            "        }",
        ])

    texture_block = ""
    if check_textures:
        texture_block = "\n".join([
            "",
            "        // --- Texture Quality Check ---",
            '        string[] texGuids = AssetDatabase.FindAssets("t:Texture2D", new[] { searchPath });',
            "        int texTotal = texGuids.Length;",
            "        int texIssues = 0;",
            "",
            "        foreach (string guid in texGuids)",
            "        {",
            "            string texPath = AssetDatabase.GUIDToAssetPath(guid);",
            "            string texName = Path.GetFileNameWithoutExtension(texPath);",
            "",
            "            // Check channel packing sRGB",
            '            if (texName.EndsWith("_MRA") || texName.EndsWith("_ORM"))',
            "            {",
            "                TextureImporter importer = AssetImporter.GetAtPath(texPath) as TextureImporter;",
            "                if (importer != null && importer.sRGBTexture)",
            "                {",
            "                    texIssues++;",
            "                    failCount++;",
            "                }",
            "            }",
            "        }",
            "        passCount += (texTotal - texIssues);",
        ])

    material_block = ""
    if check_materials:
        material_block = "\n".join([
            "",
            "        // --- Material Reference Check ---",
            '        string[] matGuids = AssetDatabase.FindAssets("t:Material", new[] { searchPath });',
            "        int matTotal = matGuids.Length;",
            "        int matMasterCount = 0;",
            "",
            "        foreach (string guid in matGuids)",
            "        {",
            "            string matPath = AssetDatabase.GUIDToAssetPath(guid);",
            "            Material mat = AssetDatabase.LoadAssetAtPath<Material>(matPath);",
            "            if (mat == null) continue;",
            "",
            '            if (mat.name.StartsWith("VB_Master_"))',
            "            {",
            "                matMasterCount++;",
            "                passCount++;",
            "            }",
            "            else",
            "            {",
            "                warnCount++;",
            "            }",
            "        }",
        ])

    lines = [
        "using UnityEngine;",
        "using UnityEditor;",
        "using System.IO;",
        "using System.Collections.Generic;",
        "",
        "public class VeilBreakers_AAAValidation_" + safe_type,
        "{",
        '    [MenuItem("VeilBreakers/Quality/Full AAA Audit")]',
        "    public static void RunFullAudit()",
        "    {",
        '        string searchPath = "' + safe_folder + '";',
        "        int passCount = 0;",
        "        int failCount = 0;",
        "        int warnCount = 0;",
        poly_block,
        texture_block,
        material_block,
        "",
        "        int totalChecks = passCount + failCount + warnCount;",
        "",
        "        // Write result to vb_result.json",
        "        var sb = new System.Text.StringBuilder();",
        '        sb.Append("{");',
        '        sb.AppendFormat("\\"tool\\": \\"aaa_validation\\", ");',
        '        sb.AppendFormat("\\"target_folder\\": \\"' + safe_folder + '\\", ");',
        '        sb.AppendFormat("\\"asset_type\\": \\"' + _sanitize_cs_string(asset_type) + '\\", ");',
        '        sb.AppendFormat("\\"total_checks\\": {0}, ", totalChecks);',
        '        sb.AppendFormat("\\"passed\\": {0}, ", passCount);',
        '        sb.AppendFormat("\\"failed\\": {0}, ", failCount);',
        '        sb.AppendFormat("\\"warnings\\": {0}, ", warnCount);',
        '        sb.Append("\\"status\\": \\"success\\"");',
        '        sb.Append("}");',
        "",
        '        string resultPath = Path.Combine(Application.dataPath, "../Temp/vb_result.json");',
        "        File.WriteAllText(resultPath, sb.ToString());",
        "",
        '        string result = (failCount == 0) ? "PASSED" : "FAILED";',
        '        Debug.Log("[VeilBreakers] AAA Audit: " + result + " - " + passCount + " pass, " + failCount + " fail, " + warnCount + " warn");',
        "    }",
        "}",
    ]

    return "\n".join(lines) + "\n"
