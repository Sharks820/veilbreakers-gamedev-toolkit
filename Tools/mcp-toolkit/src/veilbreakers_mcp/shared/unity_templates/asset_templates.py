"""C# editor script template generators for Unity asset pipeline operations.

Each function returns a complete C# source string (or JSON for asmdef) that
can be written to a Unity project's Assets/Editor/Generated/Assets/ directory.
When compiled by Unity, the scripts register as MenuItem commands under
"VeilBreakers/Assets/...".

All generated scripts write their result to Temp/vb_result.json so that
the Python MCP server can read back the outcome after execution.

CRITICAL SAFETY RULE: Asset file operations MUST use AssetDatabase APIs
(MoveAsset, RenameAsset, DeleteAsset, CopyAsset, CreateFolder). NEVER use
System.IO File.Move / File.Copy / File.Delete for assets, as that breaks
.meta file GUID tracking.

Exports:
    generate_asset_move_script          -- EDIT-10 + IMP-01: Move asset (GUID-safe)
    generate_asset_rename_script        -- EDIT-10 + IMP-01: Rename asset (GUID-safe)
    generate_asset_delete_script        -- EDIT-10: Delete asset (optional ref scan)
    generate_asset_duplicate_script     -- EDIT-10: Duplicate asset
    generate_create_folder_script       -- EDIT-10: Create folder
    generate_fbx_import_script          -- EDIT-12: FBX ModelImporter settings
    generate_texture_import_script      -- EDIT-13: TextureImporter settings
    generate_material_remap_script      -- EDIT-14 + IMP-02: Material remapping on FBX
    generate_material_auto_generate_script -- EDIT-14 + IMP-02: Auto-generate materials
    generate_asmdef_script              -- EDIT-15: Assembly Definition (JSON, not C#)
    generate_preset_create_script       -- PIPE-09: Create Unity Preset
    generate_preset_apply_script        -- PIPE-09: Apply Unity Preset
    generate_reference_scan_script      -- IMP-01: Scan asset references
    generate_atomic_import_script       -- Combined atomic import sequence

Helpers:
    _sanitize_cs_string                 -- C# string literal escaping
    _sanitize_cs_identifier             -- C# identifier sanitization
"""

from __future__ import annotations

import json
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
# FBX import preset defaults
# ---------------------------------------------------------------------------

_FBX_PRESETS: dict[str, dict] = {
    "hero": {
        "scale": 1.0,
        "mesh_compression": "Off",
        "animation_type": "Humanoid",
        "import_animation": True,
        "optimize": True,
    },
    "monster": {
        "scale": 1.0,
        "mesh_compression": "Off",
        "animation_type": "Humanoid",
        "import_animation": True,
        "optimize": True,
    },
    "weapon": {
        "scale": 1.0,
        "mesh_compression": "Medium",
        "animation_type": "None",
        "import_animation": False,
        "optimize": True,
    },
    "prop": {
        "scale": 1.0,
        "mesh_compression": "Medium",
        "animation_type": "None",
        "import_animation": False,
        "optimize": True,
    },
    "environment": {
        "scale": 1.0,
        "mesh_compression": "Low",
        "animation_type": "None",
        "import_animation": False,
        "optimize": True,
    },
}

# ---------------------------------------------------------------------------
# Texture import preset defaults
# ---------------------------------------------------------------------------

_TEXTURE_PRESETS: dict[str, dict] = {
    "hero": {"max_size": 2048},
    "monster": {"max_size": 1024},
    "weapon": {"max_size": 1024},
    "prop": {"max_size": 512},
    "ui": {"max_size": 1024},
    "environment": {"max_size": 2048},
}

# ---------------------------------------------------------------------------
# Default platform compression for texture presets
# ---------------------------------------------------------------------------

_DEFAULT_PLATFORM_COMPRESSION: dict[str, str] = {
    "Standalone": "DXT5",
    "Android": "ASTC_6x6",
    "iOS": "ASTC_6x6",
}


# ---------------------------------------------------------------------------
# 1. Asset Move
# ---------------------------------------------------------------------------


def generate_asset_move_script(old_path: str, new_path: str) -> str:
    """Generate C# editor script to move an asset via AssetDatabase.MoveAsset.

    NEVER uses File.Move -- always AssetDatabase.MoveAsset to preserve GUID.

    Args:
        old_path: Current asset path (e.g. "Assets/Old/model.fbx").
        new_path: Destination asset path (e.g. "Assets/New/model.fbx").

    Returns:
        Complete C# source string.
    """
    safe_old = _sanitize_cs_string(old_path)
    safe_new = _sanitize_cs_string(new_path)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_MoveAsset
{{
    [MenuItem("VeilBreakers/Assets/Move Asset")]
    public static void Execute()
    {{
        try
        {{
            string oldPath = "{safe_old}";
            string newPath = "{safe_new}";

            // Ensure destination directory exists
            string destDir = Path.GetDirectoryName(newPath).Replace("\\\\", "/");
            if (!string.IsNullOrEmpty(destDir) && !AssetDatabase.IsValidFolder(destDir))
            {{
                string[] parts = destDir.Split('/');
                string current = parts[0];
                for (int i = 1; i < parts.Length; i++)
                {{
                    string next = current + "/" + parts[i];
                    if (!AssetDatabase.IsValidFolder(next))
                    {{
                        AssetDatabase.CreateFolder(current, parts[i]);
                    }}
                    current = next;
                }}
            }}

            string guid = AssetDatabase.AssetPathToGUID(oldPath);
            string result = AssetDatabase.MoveAsset(oldPath, newPath);

            if (string.IsNullOrEmpty(result))
            {{
                string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"move_asset\\", \\"old_path\\": \\"" + oldPath.Replace("\\\\", "/") + "\\", \\"new_path\\": \\"" + newPath.Replace("\\\\", "/") + "\\", \\"guid\\": \\"" + guid + "\\", \\"changed_assets\\": [\\"" + newPath.Replace("\\\\", "/") + "\\"], \\"validation_status\\": \\"ok\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                Debug.Log("[VeilBreakers] Asset moved: " + oldPath + " -> " + newPath);
            }}
            else
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"move_asset\\", \\"message\\": \\"" + result.Replace("\\"", "\\\\\\"") + "\\", \\"validation_status\\": \\"failed\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                Debug.LogError("[VeilBreakers] Move failed: " + result);
            }}
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"move_asset\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\", \\"validation_status\\": \\"failed\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Move asset failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 2. Asset Rename
# ---------------------------------------------------------------------------


def generate_asset_rename_script(asset_path: str, new_name: str) -> str:
    """Generate C# editor script to rename an asset via AssetDatabase.RenameAsset.

    NEVER uses File.Move -- always AssetDatabase.RenameAsset to preserve GUID.

    Args:
        asset_path: Current asset path (e.g. "Assets/Models/old_name.fbx").
        new_name: New name for the asset (without path or extension).

    Returns:
        Complete C# source string.
    """
    safe_path = _sanitize_cs_string(asset_path)
    safe_name = _sanitize_cs_string(new_name)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_RenameAsset
{{
    [MenuItem("VeilBreakers/Assets/Rename Asset")]
    public static void Execute()
    {{
        try
        {{
            string assetPath = "{safe_path}";
            string newName = "{safe_name}";

            string guid = AssetDatabase.AssetPathToGUID(assetPath);
            string result = AssetDatabase.RenameAsset(assetPath, newName);

            if (string.IsNullOrEmpty(result))
            {{
                string dir = Path.GetDirectoryName(assetPath).Replace("\\\\", "/");
                string ext = Path.GetExtension(assetPath);
                string newPath = dir + "/" + newName + ext;
                string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"rename_asset\\", \\"old_path\\": \\"" + assetPath.Replace("\\\\", "/") + "\\", \\"new_name\\": \\"" + newName + "\\", \\"new_path\\": \\"" + newPath + "\\", \\"guid\\": \\"" + guid + "\\", \\"changed_assets\\": [\\"" + newPath + "\\"], \\"validation_status\\": \\"ok\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                Debug.Log("[VeilBreakers] Asset renamed: " + assetPath + " -> " + newName);
            }}
            else
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"rename_asset\\", \\"message\\": \\"" + result.Replace("\\"", "\\\\\\"") + "\\", \\"validation_status\\": \\"failed\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                Debug.LogError("[VeilBreakers] Rename failed: " + result);
            }}
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"rename_asset\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\", \\"validation_status\\": \\"failed\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Rename asset failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 3. Asset Delete
# ---------------------------------------------------------------------------


def generate_asset_delete_script(
    asset_path: str, safe_delete: bool = True
) -> str:
    """Generate C# editor script to delete an asset via AssetDatabase.DeleteAsset.

    If safe_delete is True, scans for references first and blocks deletion
    if any references are found (returns validation_status="blocked_by_references").

    Args:
        asset_path: Asset path to delete (e.g. "Assets/Old/model.fbx").
        safe_delete: If True, scan for references before deleting.

    Returns:
        Complete C# source string.
    """
    safe_path = _sanitize_cs_string(asset_path)

    if safe_delete:
        ref_scan_block = '''
            // Safe delete: scan for references first
            string targetGuid = AssetDatabase.AssetPathToGUID(assetPath);
            var allAssets = AssetDatabase.GetAllAssetPaths();
            var referencingAssets = new System.Collections.Generic.List<string>();

            foreach (string ap in allAssets)
            {
                if (ap == assetPath) continue;
                if (!ap.StartsWith("Assets/")) continue;
                string[] deps = AssetDatabase.GetDependencies(ap, false);
                foreach (string dep in deps)
                {
                    if (dep == assetPath)
                    {
                        referencingAssets.Add(ap);
                        break;
                    }
                }
            }

            if (referencingAssets.Count > 0)
            {
                string refs = "";
                for (int i = 0; i < referencingAssets.Count; i++)
                {
                    if (i > 0) refs += ", ";
                    refs += "\\"" + referencingAssets[i].Replace("\\\\", "/") + "\\"";
                }
                string json = "{\\"status\\": \\"warning\\", \\"action\\": \\"delete_asset\\", \\"message\\": \\"Asset has " + referencingAssets.Count + " references. Delete blocked.\\", \\"referencing_assets\\": [" + refs + "], \\"validation_status\\": \\"blocked_by_references\\"}";
                File.WriteAllText("Temp/vb_result.json", json);
                Debug.LogWarning("[VeilBreakers] Delete blocked: " + referencingAssets.Count + " references found for " + assetPath);
                return;
            }
'''
    else:
        ref_scan_block = ""

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_DeleteAsset
{{
    [MenuItem("VeilBreakers/Assets/Delete Asset")]
    public static void Execute()
    {{
        try
        {{
            string assetPath = "{safe_path}";
{ref_scan_block}
            bool deleted = AssetDatabase.DeleteAsset(assetPath);

            if (deleted)
            {{
                string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"delete_asset\\", \\"deleted_path\\": \\"" + assetPath.Replace("\\\\", "/") + "\\", \\"changed_assets\\": [\\"" + assetPath.Replace("\\\\", "/") + "\\"], \\"validation_status\\": \\"ok\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                Debug.Log("[VeilBreakers] Asset deleted: " + assetPath);
            }}
            else
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"delete_asset\\", \\"message\\": \\"Failed to delete asset\\", \\"validation_status\\": \\"failed\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                Debug.LogError("[VeilBreakers] Delete failed: " + assetPath);
            }}
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"delete_asset\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\", \\"validation_status\\": \\"failed\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Delete asset failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 4. Asset Duplicate
# ---------------------------------------------------------------------------


def generate_asset_duplicate_script(source_path: str, dest_path: str) -> str:
    """Generate C# editor script to duplicate an asset via AssetDatabase.CopyAsset.

    Args:
        source_path: Source asset path.
        dest_path: Destination asset path.

    Returns:
        Complete C# source string.
    """
    safe_source = _sanitize_cs_string(source_path)
    safe_dest = _sanitize_cs_string(dest_path)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_DuplicateAsset
{{
    [MenuItem("VeilBreakers/Assets/Duplicate Asset")]
    public static void Execute()
    {{
        try
        {{
            string sourcePath = "{safe_source}";
            string destPath = "{safe_dest}";

            bool success = AssetDatabase.CopyAsset(sourcePath, destPath);

            if (success)
            {{
                string newGuid = AssetDatabase.AssetPathToGUID(destPath);
                string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"duplicate_asset\\", \\"source_path\\": \\"" + sourcePath.Replace("\\\\", "/") + "\\", \\"dest_path\\": \\"" + destPath.Replace("\\\\", "/") + "\\", \\"new_guid\\": \\"" + newGuid + "\\", \\"changed_assets\\": [\\"" + destPath.Replace("\\\\", "/") + "\\"], \\"validation_status\\": \\"ok\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                Debug.Log("[VeilBreakers] Asset duplicated: " + sourcePath + " -> " + destPath);
            }}
            else
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"duplicate_asset\\", \\"message\\": \\"CopyAsset failed\\", \\"validation_status\\": \\"failed\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                Debug.LogError("[VeilBreakers] Duplicate failed: " + sourcePath);
            }}
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"duplicate_asset\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\", \\"validation_status\\": \\"failed\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Duplicate asset failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 5. Create Folder
# ---------------------------------------------------------------------------


def generate_create_folder_script(folder_path: str) -> str:
    """Generate C# editor script to create a folder via AssetDatabase.CreateFolder.

    Splits the path and creates each level as needed.

    Args:
        folder_path: Full folder path (e.g. "Assets/Prefabs/Monsters").

    Returns:
        Complete C# source string.
    """
    safe_path = _sanitize_cs_string(folder_path)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_CreateFolder
{{
    [MenuItem("VeilBreakers/Assets/Create Folder")]
    public static void Execute()
    {{
        try
        {{
            string folderPath = "{safe_path}";
            string[] parts = folderPath.Split('/');

            string current = parts[0]; // "Assets"
            for (int i = 1; i < parts.Length; i++)
            {{
                string next = current + "/" + parts[i];
                if (!AssetDatabase.IsValidFolder(next))
                {{
                    AssetDatabase.CreateFolder(current, parts[i]);
                }}
                current = next;
            }}

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"create_folder\\", \\"folder_path\\": \\"" + folderPath.Replace("\\\\", "/") + "\\", \\"changed_assets\\": [\\"" + folderPath.Replace("\\\\", "/") + "\\"], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Folder created: " + folderPath);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_folder\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\", \\"validation_status\\": \\"failed\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Create folder failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 6. FBX Import Configuration
# ---------------------------------------------------------------------------


def generate_fbx_import_script(
    asset_path: str,
    scale: float = 1.0,
    mesh_compression: str = "Off",
    animation_type: str = "None",
    import_animation: bool = False,
    normals_mode: str = "Import",
    import_blend_shapes: bool = True,
    optimize: bool = True,
    is_readable: bool = False,
    preset_type: str = "",
) -> str:
    """Generate C# editor script to configure FBX import via ModelImporter.

    If preset_type is provided, overrides defaults with type-specific values.

    Args:
        asset_path: FBX asset path.
        scale: Global scale factor.
        mesh_compression: Off, Low, Medium, High.
        animation_type: None, Legacy, Generic, Humanoid.
        import_animation: Whether to import animation clips.
        normals_mode: Import, Calculate, None.
        import_blend_shapes: Whether to import blend shapes.
        optimize: Whether to optimize mesh.
        is_readable: Whether mesh is CPU-readable.
        preset_type: hero, monster, weapon, prop, environment (auto-sets defaults).

    Returns:
        Complete C# source string.
    """
    # Apply preset defaults if provided
    if preset_type and preset_type in _FBX_PRESETS:
        preset = _FBX_PRESETS[preset_type]
        scale = preset["scale"]
        mesh_compression = preset["mesh_compression"]
        animation_type = preset["animation_type"]
        import_animation = preset["import_animation"]
        optimize = preset["optimize"]

    safe_path = _sanitize_cs_string(asset_path)
    safe_compression = _sanitize_cs_identifier(mesh_compression)
    safe_anim_type = _sanitize_cs_identifier(animation_type)
    safe_normals = _sanitize_cs_identifier(normals_mode)

    import_anim_str = "true" if import_animation else "false"
    blend_shapes_str = "true" if import_blend_shapes else "false"
    optimize_str = "true" if optimize else "false"
    readable_str = "true" if is_readable else "false"

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_ConfigureFBX
{{
    [MenuItem("VeilBreakers/Assets/Configure FBX Import")]
    public static void Execute()
    {{
        try
        {{
            string assetPath = "{safe_path}";

            ModelImporter importer = AssetImporter.GetAtPath(assetPath) as ModelImporter;
            if (importer == null)
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"configure_fbx\\", \\"message\\": \\"Not a valid model asset: {safe_path}\\", \\"validation_status\\": \\"failed\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                return;
            }}

            Undo.RecordObject(importer, "VeilBreakers Configure FBX");

            importer.globalScale = {scale}f;
            importer.meshCompression = ModelImporterMeshCompression.{safe_compression};
            importer.animationType = ModelImporterAnimationType.{safe_anim_type};
            importer.importAnimation = {import_anim_str};
            importer.importNormals = ModelImporterNormals.{safe_normals};
            importer.importBlendShapes = {blend_shapes_str};
            importer.isReadable = {readable_str};
            importer.optimizeMeshPolygons = {optimize_str};
            importer.optimizeMeshVertices = {optimize_str};

            importer.SaveAndReimport();

            string resultJson = "{{\\"status\\": \\"success\\", \\"action\\": \\"configure_fbx\\", \\"asset_path\\": \\"" + assetPath.Replace("\\\\", "/") + "\\", \\"scale\\": {scale}, \\"animation_type\\": \\"{safe_anim_type}\\", \\"changed_assets\\": [\\"" + assetPath.Replace("\\\\", "/") + "\\"], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", resultJson);
            Debug.Log("[VeilBreakers] FBX import configured: " + assetPath);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"configure_fbx\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\", \\"validation_status\\": \\"failed\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Configure FBX failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 7. Texture Import Configuration
# ---------------------------------------------------------------------------


def generate_texture_import_script(
    asset_path: str,
    max_size: int = 2048,
    srgb: bool = True,
    mipmap: bool = True,
    filter_mode: str = "Bilinear",
    wrap_mode: str = "Repeat",
    sprite_mode: str = "",
    platform_overrides: dict[str, dict] | None = None,
    preset_type: str = "",
    auto_detect_srgb: bool = False,
) -> str:
    """Generate C# editor script to configure texture import via TextureImporter.

    Args:
        asset_path: Texture asset path.
        max_size: Maximum texture size.
        srgb: Whether texture is sRGB.
        mipmap: Whether to generate mipmaps.
        filter_mode: Bilinear, Trilinear, Point.
        wrap_mode: Repeat, Clamp, Mirror, MirrorOnce.
        sprite_mode: If non-empty, sets texture type to Sprite.
        platform_overrides: Per-platform settings dict.
        preset_type: hero, monster, weapon, prop, ui (auto-sets max_size).
        auto_detect_srgb: Auto-detect sRGB from texture name.

    Returns:
        Complete C# source string.
    """
    # Apply preset defaults
    if preset_type and preset_type in _TEXTURE_PRESETS:
        preset = _TEXTURE_PRESETS[preset_type]
        max_size = preset["max_size"]
        # Apply default platform compression for preset types
        if platform_overrides is None:
            platform_overrides = {
                k: {"format": v, "max_size": max_size}
                for k, v in _DEFAULT_PLATFORM_COMPRESSION.items()
            }

    safe_path = _sanitize_cs_string(asset_path)
    safe_filter = _sanitize_cs_identifier(filter_mode)
    safe_wrap = _sanitize_cs_identifier(wrap_mode)

    srgb_str = "true" if srgb else "false"
    mipmap_str = "true" if mipmap else "false"

    # Auto-detect sRGB block
    if auto_detect_srgb:
        srgb_detection = '''
            // Auto-detect sRGB from texture name
            string fileName = Path.GetFileNameWithoutExtension(assetPath).ToLowerInvariant();
            if (fileName.Contains("normal") || fileName.Contains("roughness") ||
                fileName.Contains("metallic") || fileName.Contains("ao") ||
                fileName.Contains("height"))
            {
                importer.sRGBTexture = false;
            }
            else
            {
                importer.sRGBTexture = true;
            }
'''
    else:
        srgb_detection = f'''
            importer.sRGBTexture = {srgb_str};
'''

    # Sprite mode block
    if sprite_mode:
        safe_sprite = _sanitize_cs_identifier(sprite_mode)
        sprite_block = f'''
            importer.textureType = TextureImporterType.Sprite;
            importer.spriteImportMode = SpriteImportMode.{safe_sprite};
'''
    else:
        sprite_block = ""

    # Platform override blocks
    platform_blocks = ""
    if platform_overrides:
        for plat_name, plat_settings in platform_overrides.items():
            safe_plat = _sanitize_cs_string(plat_name)
            fmt = plat_settings.get("format", "Automatic")
            safe_fmt = _sanitize_cs_identifier(fmt)
            plat_max = plat_settings.get("max_size", max_size)
            platform_blocks += f'''
            {{
                var platSettings = importer.GetPlatformTextureSettings("{safe_plat}");
                platSettings.overridden = true;
                platSettings.format = TextureImporterFormat.{safe_fmt};
                platSettings.maxTextureSize = {plat_max};
                importer.SetPlatformTextureSettings(platSettings);
            }}
'''

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_ConfigureTexture
{{
    [MenuItem("VeilBreakers/Assets/Configure Texture Import")]
    public static void Execute()
    {{
        try
        {{
            string assetPath = "{safe_path}";

            TextureImporter importer = AssetImporter.GetAtPath(assetPath) as TextureImporter;
            if (importer == null)
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"configure_texture\\", \\"message\\": \\"Not a valid texture asset: {safe_path}\\", \\"validation_status\\": \\"failed\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                return;
            }}

            Undo.RecordObject(importer, "VeilBreakers Configure Texture");

            importer.maxTextureSize = {max_size};
{srgb_detection}
            importer.mipmapEnabled = {mipmap_str};
            importer.filterMode = FilterMode.{safe_filter};
            importer.wrapMode = TextureWrapMode.{safe_wrap};
{sprite_block}{platform_blocks}
            importer.SaveAndReimport();

            string resultJson = "{{\\"status\\": \\"success\\", \\"action\\": \\"configure_texture\\", \\"asset_path\\": \\"" + assetPath.Replace("\\\\", "/") + "\\", \\"max_size\\": {max_size}, \\"changed_assets\\": [\\"" + assetPath.Replace("\\\\", "/") + "\\"], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", resultJson);
            Debug.Log("[VeilBreakers] Texture import configured: " + assetPath);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"configure_texture\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\", \\"validation_status\\": \\"failed\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Configure texture failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 8. Material Remap
# ---------------------------------------------------------------------------


def generate_material_remap_script(
    fbx_path: str, remappings: dict[str, str]
) -> str:
    """Generate C# editor script to remap materials on an FBX import.

    Args:
        fbx_path: FBX model asset path.
        remappings: Maps FBX material name to project material asset path.

    Returns:
        Complete C# source string.
    """
    safe_fbx = _sanitize_cs_string(fbx_path)

    remap_lines = ""
    for mat_name, mat_path in remappings.items():
        safe_mat_name = _sanitize_cs_string(mat_name)
        safe_mat_path = _sanitize_cs_string(mat_path)
        remap_lines += f'''
            {{
                Material targetMat = AssetDatabase.LoadAssetAtPath<Material>("{safe_mat_path}");
                if (targetMat != null)
                {{
                    importer.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), "{safe_mat_name}"), targetMat);
                    remappedCount++;
                }}
                else
                {{
                    warnings.Add("Material not found: {safe_mat_path}");
                }}
            }}
'''

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_RemapMaterials
{{
    [MenuItem("VeilBreakers/Assets/Remap Materials")]
    public static void Execute()
    {{
        try
        {{
            string fbxPath = "{safe_fbx}";

            ModelImporter importer = AssetImporter.GetAtPath(fbxPath) as ModelImporter;
            if (importer == null)
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"remap_materials\\", \\"message\\": \\"Not a valid model asset: {safe_fbx}\\", \\"validation_status\\": \\"failed\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                return;
            }}

            Undo.RecordObject(importer, "VeilBreakers Remap Materials");

            importer.materialImportMode = ModelImporterMaterialImportMode.ImportViaMaterialDescription;

            int remappedCount = 0;
            List<string> warnings = new List<string>();
{remap_lines}
            importer.SaveAndReimport();

            string warningsJson = "";
            for (int i = 0; i < warnings.Count; i++)
            {{
                if (i > 0) warningsJson += ", ";
                warningsJson += "\\"" + warnings[i].Replace("\\"", "\\\\\\"") + "\\"";
            }}

            string resultJson = "{{\\"status\\": \\"success\\", \\"action\\": \\"remap_materials\\", \\"fbx_path\\": \\"" + fbxPath.Replace("\\\\", "/") + "\\", \\"remapped_count\\": " + remappedCount + ", \\"warnings\\": [" + warningsJson + "], \\"changed_assets\\": [\\"" + fbxPath.Replace("\\\\", "/") + "\\"], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", resultJson);
            Debug.Log("[VeilBreakers] Materials remapped on: " + fbxPath);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"remap_materials\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\", \\"validation_status\\": \\"failed\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Remap materials failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 9. Material Auto Generate
# ---------------------------------------------------------------------------


def generate_material_auto_generate_script(
    fbx_path: str,
    texture_dir: str,
    shader_name: str = "Universal Render Pipeline/Lit",
) -> str:
    """Generate C# editor script to auto-generate PBR materials from textures.

    Scans texture_dir for PBR textures, creates a Material, assigns textures
    to URP Lit properties, and remaps the FBX to use the generated material.

    Args:
        fbx_path: FBX model asset path.
        texture_dir: Directory containing PBR textures.
        shader_name: Shader to use (default: URP Lit).

    Returns:
        Complete C# source string.
    """
    safe_fbx = _sanitize_cs_string(fbx_path)
    safe_tex_dir = _sanitize_cs_string(texture_dir)
    safe_shader = _sanitize_cs_string(shader_name)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Linq;

public static class VeilBreakers_AutoMaterials
{{
    [MenuItem("VeilBreakers/Assets/Auto Generate Materials")]
    public static void Execute()
    {{
        try
        {{
            string fbxPath = "{safe_fbx}";
            string textureDir = "{safe_tex_dir}";
            string shaderName = "{safe_shader}";

            // Find textures by naming convention
            string[] texGUIDs = AssetDatabase.FindAssets("t:Texture2D", new[] {{ textureDir }});
            Texture2D albedoTex = null, normalTex = null, metallicTex = null, aoTex = null;

            foreach (string guid in texGUIDs)
            {{
                string path = AssetDatabase.GUIDToAssetPath(guid);
                string name = Path.GetFileNameWithoutExtension(path).ToLowerInvariant();

                if (name.Contains("albedo") || name.Contains("basecolor") || name.Contains("_base"))
                    albedoTex = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
                else if (name.Contains("normal"))
                    normalTex = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
                else if (name.Contains("metallic") || name.Contains("metallicsmoothness"))
                    metallicTex = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
                else if (name.Contains("ao") || name.Contains("occlusion"))
                    aoTex = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            }}

            // Create material
            Shader shader = Shader.Find(shaderName);
            if (shader == null)
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"auto_materials\\", \\"message\\": \\"Shader not found: {safe_shader}\\", \\"validation_status\\": \\"failed\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                return;
            }}

            string matName = Path.GetFileNameWithoutExtension(fbxPath) + "_AutoMat";
            Material mat = new Material(shader);
            Undo.RegisterCreatedObjectUndo(mat, "VeilBreakers Auto Material");

            if (albedoTex != null) mat.SetTexture("_BaseMap", albedoTex);
            if (normalTex != null)
            {{
                mat.SetTexture("_BumpMap", normalTex);
                mat.EnableKeyword("_NORMALMAP");
            }}
            if (metallicTex != null) mat.SetTexture("_MetallicGlossMap", metallicTex);
            if (aoTex != null) mat.SetTexture("_OcclusionMap", aoTex);

            // Save material
            string matDir = "Assets/Materials";
            if (!AssetDatabase.IsValidFolder(matDir))
                AssetDatabase.CreateFolder("Assets", "Materials");
            string matPath = matDir + "/" + matName + ".mat";
            AssetDatabase.CreateAsset(mat, matPath);

            // Remap FBX to use generated material
            ModelImporter importer = AssetImporter.GetAtPath(fbxPath) as ModelImporter;
            if (importer != null)
            {{
                importer.materialImportMode = ModelImporterMaterialImportMode.ImportViaMaterialDescription;
                importer.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), "defaultMat"), mat);
                importer.SaveAndReimport();
            }}

            string resultJson = "{{\\"status\\": \\"success\\", \\"action\\": \\"auto_materials\\", \\"material_path\\": \\"" + matPath.Replace("\\\\", "/") + "\\", \\"fbx_path\\": \\"" + fbxPath.Replace("\\\\", "/") + "\\", \\"changed_assets\\": [\\"" + matPath.Replace("\\\\", "/") + "\\", \\"" + fbxPath.Replace("\\\\", "/") + "\\"], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", resultJson);
            Debug.Log("[VeilBreakers] Auto materials generated: " + matPath);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"auto_materials\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\", \\"validation_status\\": \\"failed\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Auto materials failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 10. Assembly Definition (JSON, not C#)
# ---------------------------------------------------------------------------


def generate_asmdef_script(
    name: str,
    root_dir: str,
    root_namespace: str = "",
    references: list[str] | None = None,
    platforms: list[str] | None = None,
    defines: list[str] | None = None,
    allow_unsafe: bool = False,
    auto_referenced: bool = True,
) -> str:
    """Generate a Unity Assembly Definition file (.asmdef) as JSON content.

    NOTE: This returns JSON, NOT C#. The .asmdef format is plain JSON.

    Args:
        name: Assembly name (e.g. "VeilBreakers.Runtime").
        root_dir: Root directory for the assembly (used by handler, not in output).
        root_namespace: Root namespace (defaults to name if empty).
        references: List of assembly references.
        platforms: List of included platforms (empty = all platforms).
        defines: List of scripting define constraints.
        allow_unsafe: Whether to allow unsafe code.
        auto_referenced: Whether auto-referenced by other assemblies.

    Returns:
        JSON string (NOT C# source).
    """
    if not root_namespace:
        root_namespace = name

    asmdef = {
        "name": name,
        "rootNamespace": root_namespace,
        "references": references or [],
        "includePlatforms": platforms or [],
        "excludePlatforms": [],
        "allowUnsafeCode": allow_unsafe,
        "overrideReferences": False,
        "precompiledReferences": [],
        "autoReferenced": auto_referenced,
        "defineConstraints": defines or [],
        "versionDefines": [],
        "noEngineReferences": False,
    }

    return json.dumps(asmdef, indent=4)


# ---------------------------------------------------------------------------
# 11. Preset Create
# ---------------------------------------------------------------------------


def generate_preset_create_script(
    preset_name: str,
    source_asset_path: str,
    save_dir: str = "Assets/Editor/Presets",
) -> str:
    """Generate C# editor script to create a Unity Preset from an existing asset.

    Args:
        preset_name: Name for the preset (without extension).
        source_asset_path: Path to the source asset/importer.
        save_dir: Directory to save the preset.

    Returns:
        Complete C# source string.
    """
    safe_name = _sanitize_cs_string(preset_name)
    safe_source = _sanitize_cs_string(source_asset_path)
    safe_dir = _sanitize_cs_string(save_dir)

    return f'''using UnityEngine;
using UnityEditor;
using UnityEditor.Presets;
using System.IO;

public static class VeilBreakers_CreatePreset
{{
    [MenuItem("VeilBreakers/Assets/Create Preset")]
    public static void Execute()
    {{
        try
        {{
            string sourcePath = "{safe_source}";
            string saveDir = "{safe_dir}";
            string presetName = "{safe_name}";

            // Load the source importer or object
            AssetImporter importer = AssetImporter.GetAtPath(sourcePath);
            Object source = importer != null ? (Object)importer : AssetDatabase.LoadMainAssetAtPath(sourcePath);

            if (source == null)
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_preset\\", \\"message\\": \\"Source asset not found: {safe_source}\\", \\"validation_status\\": \\"failed\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                return;
            }}

            Preset preset = new Preset(source);

            // Ensure save directory exists
            if (!AssetDatabase.IsValidFolder(saveDir))
            {{
                string[] parts = saveDir.Split('/');
                string current = parts[0];
                for (int i = 1; i < parts.Length; i++)
                {{
                    string next = current + "/" + parts[i];
                    if (!AssetDatabase.IsValidFolder(next))
                        AssetDatabase.CreateFolder(current, parts[i]);
                    current = next;
                }}
            }}

            string presetPath = saveDir + "/" + presetName + ".preset";
            AssetDatabase.CreateAsset(preset, presetPath);

            string resultJson = "{{\\"status\\": \\"success\\", \\"action\\": \\"create_preset\\", \\"preset_path\\": \\"" + presetPath.Replace("\\\\", "/") + "\\", \\"source_path\\": \\"" + sourcePath.Replace("\\\\", "/") + "\\", \\"changed_assets\\": [\\"" + presetPath.Replace("\\\\", "/") + "\\"], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", resultJson);
            Debug.Log("[VeilBreakers] Preset created: " + presetPath);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_preset\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\", \\"validation_status\\": \\"failed\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Create preset failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 12. Preset Apply
# ---------------------------------------------------------------------------


def generate_preset_apply_script(preset_path: str, target_path: str) -> str:
    """Generate C# editor script to apply a Unity Preset to an asset.

    Args:
        preset_path: Path to the .preset file.
        target_path: Path to the target asset to apply preset to.

    Returns:
        Complete C# source string.
    """
    safe_preset = _sanitize_cs_string(preset_path)
    safe_target = _sanitize_cs_string(target_path)

    return f'''using UnityEngine;
using UnityEditor;
using UnityEditor.Presets;
using System.IO;

public static class VeilBreakers_ApplyPreset
{{
    [MenuItem("VeilBreakers/Assets/Apply Preset")]
    public static void Execute()
    {{
        try
        {{
            string presetPath = "{safe_preset}";
            string targetPath = "{safe_target}";

            Preset preset = AssetDatabase.LoadAssetAtPath<Preset>(presetPath);
            if (preset == null)
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"apply_preset\\", \\"message\\": \\"Preset not found: {safe_preset}\\", \\"validation_status\\": \\"failed\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                return;
            }}

            // Load target (importer or main asset)
            AssetImporter importer = AssetImporter.GetAtPath(targetPath);
            Object target = importer != null ? (Object)importer : AssetDatabase.LoadMainAssetAtPath(targetPath);

            if (target == null)
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"apply_preset\\", \\"message\\": \\"Target not found: {safe_target}\\", \\"validation_status\\": \\"failed\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                return;
            }}

            Undo.RecordObject(target, "VeilBreakers Apply Preset");
            bool applied = preset.ApplyTo(target);

            if (importer != null)
            {{
                importer.SaveAndReimport();
            }}

            if (applied)
            {{
                string resultJson = "{{\\"status\\": \\"success\\", \\"action\\": \\"apply_preset\\", \\"preset_path\\": \\"" + presetPath.Replace("\\\\", "/") + "\\", \\"target_path\\": \\"" + targetPath.Replace("\\\\", "/") + "\\", \\"changed_assets\\": [\\"" + targetPath.Replace("\\\\", "/") + "\\"], \\"validation_status\\": \\"ok\\"}}";
                File.WriteAllText("Temp/vb_result.json", resultJson);
                Debug.Log("[VeilBreakers] Preset applied: " + presetPath + " -> " + targetPath);
            }}
            else
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"apply_preset\\", \\"message\\": \\"Preset could not be applied to target\\", \\"validation_status\\": \\"failed\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
            }}
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"apply_preset\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\", \\"validation_status\\": \\"failed\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Apply preset failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 13. Reference Scan
# ---------------------------------------------------------------------------


def generate_reference_scan_script(asset_path: str) -> str:
    """Generate C# editor script to scan for all assets referencing a target.

    Finds the GUID of the target asset and searches all project assets
    for dependencies on it.

    Args:
        asset_path: Path to the asset to find references for.

    Returns:
        Complete C# source string.
    """
    safe_path = _sanitize_cs_string(asset_path)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_ScanReferences
{{
    [MenuItem("VeilBreakers/Assets/Scan References")]
    public static void Execute()
    {{
        try
        {{
            string assetPath = "{safe_path}";
            string targetGUID = AssetDatabase.AssetPathToGUID(assetPath);

            if (string.IsNullOrEmpty(targetGUID))
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"scan_references\\", \\"message\\": \\"Asset not found or has no GUID: {safe_path}\\", \\"validation_status\\": \\"failed\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                return;
            }}

            string[] allAssets = AssetDatabase.GetAllAssetPaths();
            List<string> referencingAssets = new List<string>();

            foreach (string ap in allAssets)
            {{
                if (ap == assetPath) continue;
                if (!ap.StartsWith("Assets/")) continue;

                string[] deps = AssetDatabase.GetDependencies(ap, false);
                foreach (string dep in deps)
                {{
                    if (dep == assetPath)
                    {{
                        referencingAssets.Add(ap);
                        break;
                    }}
                }}
            }}

            // Build result JSON
            string refs = "";
            for (int i = 0; i < referencingAssets.Count; i++)
            {{
                if (i > 0) refs += ", ";
                refs += "\\"" + referencingAssets[i].Replace("\\\\", "/") + "\\"";
            }}

            string resultJson = "{{\\"status\\": \\"success\\", \\"action\\": \\"scan_references\\", \\"asset_path\\": \\"" + assetPath.Replace("\\\\", "/") + "\\", \\"guid\\": \\"" + targetGUID + "\\", \\"reference_count\\": " + referencingAssets.Count + ", \\"referencing_assets\\": [" + refs + "], \\"changed_assets\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", resultJson);
            Debug.Log("[VeilBreakers] Reference scan complete: " + referencingAssets.Count + " references found for " + assetPath);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"scan_references\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\", \\"validation_status\\": \\"failed\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Reference scan failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 14. Atomic Import
# ---------------------------------------------------------------------------


def generate_atomic_import_script(
    texture_paths: list[str],
    material_name: str,
    fbx_path: str,
    shader_name: str = "Universal Render Pipeline/Lit",
    remappings: dict[str, str] | None = None,
) -> str:
    """Generate C# editor script for an atomic import sequence.

    Enforces the locked-decision import order:
    1. Texture import (configure TextureImporter settings)
    2. Material creation (from textures with shader)
    3. FBX import (configure ModelImporter settings)
    4. Material remapping (remap FBX materials to created material)

    Wrapped in AssetDatabase.StartAssetEditing / StopAssetEditing.

    Args:
        texture_paths: List of texture asset paths.
        material_name: Name for the generated material.
        fbx_path: FBX model asset path.
        shader_name: Shader name for the material.
        remappings: Optional dict mapping FBX material names to the generated material.

    Returns:
        Complete C# source string.
    """
    safe_fbx = _sanitize_cs_string(fbx_path)
    safe_mat_name = _sanitize_cs_string(material_name)
    safe_shader = _sanitize_cs_string(shader_name)

    # Build texture path array
    tex_entries = ", ".join(
        f'"{_sanitize_cs_string(tp)}"' for tp in texture_paths
    )

    # Build remap block
    remap_block = ""
    if remappings:
        for mat_key, mat_val in remappings.items():
            safe_key = _sanitize_cs_string(mat_key)
            safe_val = _sanitize_cs_string(mat_val)
            remap_block += f'''
                modelImporter.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), "{safe_key}"), createdMat);
'''

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_AtomicImport
{{
    [MenuItem("VeilBreakers/Assets/Atomic Import")]
    public static void Execute()
    {{
        List<string> changedAssets = new List<string>();

        try
        {{
            AssetDatabase.StartAssetEditing();

            string[] texturePaths = new string[] {{ {tex_entries} }};
            string materialName = "{safe_mat_name}";
            string fbxPath = "{safe_fbx}";
            string shaderName = "{safe_shader}";

            // ================================================================
            // Step 1: Configure TextureImporter settings
            // ================================================================
            foreach (string texPath in texturePaths)
            {{
                TextureImporter texImporter = AssetImporter.GetAtPath(texPath) as TextureImporter;
                if (texImporter != null)
                {{
                    // Auto-detect sRGB from name
                    string fileName = Path.GetFileNameWithoutExtension(texPath).ToLowerInvariant();
                    if (fileName.Contains("normal") || fileName.Contains("roughness") ||
                        fileName.Contains("metallic") || fileName.Contains("ao") ||
                        fileName.Contains("height"))
                    {{
                        texImporter.sRGBTexture = false;
                    }}
                    else
                    {{
                        texImporter.sRGBTexture = true;
                    }}
                    texImporter.mipmapEnabled = true;
                    texImporter.SaveAndReimport();
                    changedAssets.Add(texPath);
                }}
            }}

            // ================================================================
            // Step 2: Create Material(shader) with textures
            // ================================================================
            Shader shader = Shader.Find(shaderName);
            if (shader == null)
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"atomic_import\\", "
                    + "\\"message\\": \\"Shader not found: " + shaderName + "\\", "
                    + "\\"changed_assets\\": [" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a + "\\"")) + "], "
                    + "\\"validation_status\\": \\"error\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                Debug.LogError("[VeilBreakers] Shader not found: " + shaderName);
                return;
            }}
            Material createdMat = new Material(shader);
            Undo.RegisterCreatedObjectUndo(createdMat, "VeilBreakers Atomic Material");

            // Assign textures by naming convention
            foreach (string texPath in texturePaths)
            {{
                string name = Path.GetFileNameWithoutExtension(texPath).ToLowerInvariant();
                Texture2D tex = AssetDatabase.LoadAssetAtPath<Texture2D>(texPath);
                if (tex == null) continue;

                if (name.Contains("albedo") || name.Contains("basecolor") || name.Contains("_base"))
                    createdMat.SetTexture("_BaseMap", tex);
                else if (name.Contains("normal"))
                {{
                    createdMat.SetTexture("_BumpMap", tex);
                    createdMat.EnableKeyword("_NORMALMAP");
                }}
                else if (name.Contains("metallic"))
                    createdMat.SetTexture("_MetallicGlossMap", tex);
                else if (name.Contains("ao") || name.Contains("occlusion"))
                    createdMat.SetTexture("_OcclusionMap", tex);
            }}

            string matDir = "Assets/Materials";
            if (!AssetDatabase.IsValidFolder(matDir))
                AssetDatabase.CreateFolder("Assets", "Materials");
            string matPath = matDir + "/" + materialName + ".mat";
            AssetDatabase.CreateAsset(createdMat, matPath);
            changedAssets.Add(matPath);

            // ================================================================
            // Step 3: Configure ModelImporter on FBX
            // ================================================================
            ModelImporter modelImporter = AssetImporter.GetAtPath(fbxPath) as ModelImporter;
            if (modelImporter != null)
            {{
                Undo.RecordObject(modelImporter, "VeilBreakers Atomic FBX Config");
                modelImporter.globalScale = 1.0f;
                modelImporter.meshCompression = ModelImporterMeshCompression.Off;
                modelImporter.importNormals = ModelImporterNormals.Import;

                // ================================================================
                // Step 4: Material remapping
                // ================================================================
                modelImporter.materialImportMode = ModelImporterMaterialImportMode.ImportViaMaterialDescription;
{remap_block}
                modelImporter.SaveAndReimport();
                changedAssets.Add(fbxPath);
            }}
        }}
        finally
        {{
            AssetDatabase.StopAssetEditing();
        }}

        // Build result JSON
        string assets = "";
        for (int i = 0; i < changedAssets.Count; i++)
        {{
            if (i > 0) assets += ", ";
            assets += "\\"" + changedAssets[i].Replace("\\\\", "/") + "\\"";
        }}

        string resultJson = "{{\\"status\\": \\"success\\", \\"action\\": \\"atomic_import\\", \\"material_name\\": \\"{safe_mat_name}\\", \\"fbx_path\\": \\"" + "{safe_fbx}" + "\\", \\"changed_assets\\": [" + assets + "], \\"validation_status\\": \\"ok\\"}}";
        File.WriteAllText("Temp/vb_result.json", resultJson);
        Debug.Log("[VeilBreakers] Atomic import complete for: {safe_fbx}");
    }}
}}
'''
