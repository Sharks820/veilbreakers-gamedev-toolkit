"""C# editor script template generators for Unity prefab, component, and hierarchy operations.

Each function returns a complete C# source string that can be written to
a Unity project's Assets/Editor/Generated/Prefab/ directory. When compiled
by Unity, the scripts register as MenuItem commands under "VeilBreakers/Prefab/...".

All generated scripts write their result to Temp/vb_result.json so that
the Python MCP server can read back the outcome after execution.

Exports:
    generate_prefab_create_script      -- EDIT-01: Create prefab from profile
    generate_scaffold_prefab_script    -- Ghost scaffolding placeholder
    generate_prefab_variant_script     -- EDIT-01: Create prefab variant
    generate_prefab_modify_script      -- EDIT-01: Modify existing prefab
    generate_prefab_delete_script      -- EDIT-01: Delete prefab
    generate_add_component_script      -- EDIT-02: Add component
    generate_remove_component_script   -- EDIT-02: Remove component
    generate_configure_component_script-- EDIT-02: Configure component
    generate_reflect_component_script  -- EDIT-02: Introspect component
    generate_hierarchy_script          -- EDIT-03: Hierarchy operations
    generate_batch_configure_script    -- Batch configure (same op, many objects)
    generate_variant_matrix_script     -- Variant matrix generator
    generate_joint_setup_script        -- PHYS-01: Physics joints
    generate_navmesh_setup_script      -- PHYS-02: NavMesh config
    generate_bone_socket_script        -- EQUIP-02: Bone socket attachment
    generate_validate_project_script   -- Project integrity check
    generate_job_script                -- Batch scripting (multi-op, one compile)

Helpers:
    _resolve_selector_snippet          -- Deterministic GameObject selector
    _load_auto_wire_profile            -- Load auto-wire JSON profile
    _sanitize_cs_string                -- C# string literal escaping
    _sanitize_cs_identifier            -- C# identifier sanitization
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional


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
# Auto-wire profile loader
# ---------------------------------------------------------------------------


def _load_auto_wire_profile(prefab_type: str) -> dict:
    """Load an auto-wire component profile from JSON.

    Args:
        prefab_type: Profile name (monster, hero, prop, ui).

    Returns:
        Parsed JSON dict with prefab_type, components, etc.

    Raises:
        FileNotFoundError: If profile JSON does not exist.
        ValueError: If prefab_type contains path separators or escapes the
            profiles directory.
    """
    # Reject any prefab_type containing path separators to prevent traversal
    if "/" in prefab_type or "\\" in prefab_type or ".." in prefab_type:
        raise ValueError(
            f"Invalid prefab_type '{prefab_type}': must not contain path separators or '..'"
        )
    profiles_dir = Path(__file__).resolve().parent.parent / "auto_wire_profiles"
    profile_path = (profiles_dir / f"{prefab_type}.json").resolve()
    # Verify the resolved path stays within the profiles directory
    if not profile_path.is_relative_to(profiles_dir.resolve()):
        raise ValueError(
            f"Invalid prefab_type '{prefab_type}': resolved path escapes profiles directory"
        )
    return json.loads(profile_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Selector helper
# ---------------------------------------------------------------------------


def _resolve_selector_snippet(selector: dict | str) -> str:
    """Generate a C# code snippet that resolves a GameObject from a selector.

    Args:
        selector: Either a dict ``{"by": "name"|"path"|"guid"|"regex", "value": str}``
                  or a plain string (backward-compatible shorthand for name lookup).

    Returns:
        Multi-line C# snippet that declares and assigns ``GameObject target``.
    """
    if isinstance(selector, str):
        selector = {"by": "name", "value": selector}

    mode = selector.get("by", "name")
    value = _sanitize_cs_string(selector.get("value", ""))

    if mode == "name":
        return f'''            GameObject target = GameObject.Find("{value}");
            if (target == null)
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"message\\": \\"GameObject not found: {value}\\"}}";
                System.IO.File.WriteAllText("Temp/vb_result.json", errJson);
                return;
            }}'''

    elif mode == "path":
        return f'''            GameObject target = GameObject.Find("/{value}");
            if (target == null)
            {{
                // Fallback: try Transform.Find from scene roots
                foreach (var root in UnityEngine.SceneManagement.SceneManager.GetActiveScene().GetRootGameObjects())
                {{
                    var t = root.transform.Find("{value}");
                    if (t != null) {{ target = t.gameObject; break; }}
                }}
            }}
            if (target == null)
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"message\\": \\"GameObject not found at path: {value}\\"}}";
                System.IO.File.WriteAllText("Temp/vb_result.json", errJson);
                return;
            }}'''

    elif mode == "guid":
        return f'''            GameObject target = null;
            // Try GlobalObjectId for scene objects
            if (UnityEditor.GlobalObjectId.TryParse("{value}", out var gid))
            {{
                var obj = UnityEditor.GlobalObjectId.GlobalObjectIdentifierToObjectSlow(gid);
                if (obj is GameObject go) target = go;
                else if (obj is Component comp) target = comp.gameObject;
            }}
            // Fallback: AssetDatabase GUID lookup
            if (target == null)
            {{
                string assetPath = AssetDatabase.GUIDToAssetPath("{value}");
                if (!string.IsNullOrEmpty(assetPath))
                {{
                    var asset = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
                    if (asset != null) target = asset;
                }}
            }}
            if (target == null)
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"message\\": \\"GameObject not found by GUID: {value}\\"}}";
                System.IO.File.WriteAllText("Temp/vb_result.json", errJson);
                return;
            }}'''

    elif mode == "regex":
        return f'''            GameObject target = null;
            var regexPattern = new System.Text.RegularExpressions.Regex("{value}");
            foreach (var root in UnityEngine.SceneManagement.SceneManager.GetActiveScene().GetRootGameObjects())
            {{
                if (System.Text.RegularExpressions.Regex.IsMatch(root.name, "{value}"))
                {{
                    target = root;
                    break;
                }}
                // Recurse children
                foreach (var child in root.GetComponentsInChildren<Transform>(true))
                {{
                    if (System.Text.RegularExpressions.Regex.IsMatch(child.name, "{value}"))
                    {{
                        target = child.gameObject;
                        break;
                    }}
                }}
                if (target != null) break;
            }}
            if (target == null)
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"message\\": \\"No GameObject matching regex: {value}\\"}}";
                System.IO.File.WriteAllText("Temp/vb_result.json", errJson);
                return;
            }}'''

    else:
        # Default fallback to name
        return _resolve_selector_snippet({"by": "name", "value": selector.get("value", "")})


# ---------------------------------------------------------------------------
# Property value setter snippet helper
# ---------------------------------------------------------------------------


def _property_setter_snippet(prop: dict) -> str:
    """Generate C# code to set a SerializedProperty value based on type.

    Args:
        prop: Dict with keys: property, value, type.

    Returns:
        C# code line setting the property value.
    """
    safe_prop = _sanitize_cs_string(prop["property"])
    safe_val = _sanitize_cs_string(str(prop["value"]))
    prop_type = prop.get("type", "string")

    if prop_type == "float":
        return f'                so.FindProperty("{safe_prop}").floatValue = {safe_val}f;'
    elif prop_type == "int":
        return f'                so.FindProperty("{safe_prop}").intValue = {safe_val};'
    elif prop_type == "bool":
        return f'                so.FindProperty("{safe_prop}").boolValue = {safe_val};'
    elif prop_type == "string":
        return f'                so.FindProperty("{safe_prop}").stringValue = "{safe_val}";'
    elif prop_type == "enum":
        return f'                so.FindProperty("{safe_prop}").enumValueIndex = {safe_val};'
    elif prop_type == "color":
        return f'                so.FindProperty("{safe_prop}").colorValue = new Color({safe_val});'
    elif prop_type == "vector3":
        return f'                so.FindProperty("{safe_prop}").vector3Value = new Vector3({safe_val});'
    elif prop_type == "object_ref":
        return f'                so.FindProperty("{safe_prop}").objectReferenceValue = AssetDatabase.LoadAssetAtPath<UnityEngine.Object>("{safe_val}");'
    else:
        return f'                so.FindProperty("{safe_prop}").stringValue = "{safe_val}";'


# ---------------------------------------------------------------------------
# 1. generate_prefab_create_script
# ---------------------------------------------------------------------------


def generate_prefab_create_script(
    name: str,
    prefab_type: str,
    save_dir: str,
    components: list[dict] | None = None,
) -> str:
    """Generate C# script to create a prefab with auto-wired components.

    Args:
        name: Prefab name.
        prefab_type: Profile type (monster, hero, prop, ui).
        save_dir: Directory to save the prefab asset.
        components: Optional explicit component list; if None, loads from profile.

    Returns:
        Complete C# source string.
    """
    safe_name = _sanitize_cs_identifier(name)
    safe_display_name = _sanitize_cs_string(name)
    safe_dir = _sanitize_cs_string(save_dir)

    if components is None:
        try:
            profile = _load_auto_wire_profile(prefab_type)
            components = profile.get("components", [])
            default_layer = _sanitize_cs_string(profile.get("default_layer", "Default"))
            default_tag = _sanitize_cs_string(profile.get("default_tag", "Untagged"))
        except FileNotFoundError:
            components = []
            default_layer = "Default"
            default_tag = "Untagged"
    else:
        default_layer = "Default"
        default_tag = "Untagged"

    # Build component add lines
    comp_lines = []
    for comp in components:
        comp_type = _sanitize_cs_string(comp["type"])
        # Handle namespaced types
        if "." in comp_type:
            comp_lines.append(f'            Undo.AddComponent(go, typeof({comp_type}));')
        else:
            comp_lines.append(f'            Undo.AddComponent<{comp_type}>(go);')
    comp_code = "\n".join(comp_lines)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_CreatePrefab_{safe_name}
{{
    [MenuItem("VeilBreakers/Prefab/Create Prefab")]
    public static void Execute()
    {{
        var warnings = new List<string>();
        var changedAssets = new List<string>();
        try
        {{
            var go = new GameObject("{safe_display_name}");
            Undo.RegisterCreatedObjectUndo(go, "Create Prefab {safe_display_name}");

            // Set layer and tag
            go.tag = "{default_tag}";
            go.layer = LayerMask.NameToLayer("{default_layer}");

            // Add auto-wired components
{comp_code}

            // Save as prefab
            string dir = "{safe_dir}";
            if (!AssetDatabase.IsValidFolder(dir))
            {{
                string[] parts = dir.Split('/');
                string current = parts[0];
                for (int i = 1; i < parts.Length; i++)
                {{
                    string next = current + "/" + parts[i];
                    if (!AssetDatabase.IsValidFolder(next))
                        AssetDatabase.CreateFolder(current, parts[i]);
                    current = next;
                }}
            }}

            string prefabPath = dir + "/{safe_display_name}.prefab";
            var prefab = PrefabUtility.SaveAsPrefabAsset(go, prefabPath);

            // Cleanup scene object
            Object.DestroyImmediate(go);

            if (prefab == null)
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_prefab\\", \\"message\\": \\"SaveAsPrefabAsset failed for: " + prefabPath + "\\", \\"validation_status\\": \\"failed\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                Debug.LogError("[VeilBreakers] SaveAsPrefabAsset returned null: " + prefabPath);
                return;
            }}

            changedAssets.Add(prefabPath);
            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string warnJson = "[" + string.Join(",", warnings.ConvertAll(w => "\\"" + w.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"create_prefab\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": " + warnJson + ", \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Prefab created: " + prefabPath);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_prefab\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Prefab creation failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 2. generate_scaffold_prefab_script
# ---------------------------------------------------------------------------


def generate_scaffold_prefab_script(name: str, prefab_type: str) -> str:
    """Generate C# script to create a ghost scaffold prefab with placeholder visual.

    Args:
        name: Scaffold name.
        prefab_type: Profile type for auto-wire components.

    Returns:
        Complete C# source string.
    """
    safe_name = _sanitize_cs_identifier(name)
    safe_display_name = _sanitize_cs_string(name)

    try:
        profile = _load_auto_wire_profile(prefab_type)
        components = profile.get("components", [])
    except FileNotFoundError:
        components = []

    comp_lines = []
    for comp in components:
        comp_type = _sanitize_cs_string(comp["type"])
        if "." in comp_type:
            comp_lines.append(f'            Undo.AddComponent(go, typeof({comp_type}));')
        else:
            comp_lines.append(f'            Undo.AddComponent<{comp_type}>(go);')
    comp_code = "\n".join(comp_lines)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_CreateScaffold_{safe_name}
{{
    [MenuItem("VeilBreakers/Prefab/Create Scaffold")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
            // Create ghost scaffold with placeholder capsule
            var go = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            go.name = "{safe_display_name}_Scaffold";
            Undo.RegisterCreatedObjectUndo(go, "Create Scaffold {safe_display_name}");

            // Apply transparent material for ghost visual
            var renderer = go.GetComponent<MeshRenderer>();
            if (renderer != null)
            {{
                Shader shader = Shader.Find("Universal Render Pipeline/Lit")
                    ?? Shader.Find("Standard")
                    ?? Shader.Find("Hidden/InternalErrorShader");
                var mat = new Material(shader);
                mat.SetFloat("_Mode", 3); // Transparent
                mat.SetColor("_Color", new Color(0.5f, 0.8f, 1.0f, 0.3f));
                mat.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
                mat.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
                mat.SetInt("_ZWrite", 0);
                mat.DisableKeyword("_ALPHATEST_ON");
                mat.EnableKeyword("_ALPHABLEND_ON");
                mat.DisableKeyword("_ALPHAPREMULTIPLY_ON");
                mat.renderQueue = 3000;
                renderer.material = mat;
            }}

            // Add auto-wire components from profile
{comp_code}

            changedAssets.Add(go.name);
            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"create_scaffold\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Scaffold created: " + go.name);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_scaffold\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Scaffold creation failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 3. generate_prefab_variant_script
# ---------------------------------------------------------------------------


def generate_prefab_variant_script(
    name: str,
    base_prefab_path: str,
    overrides: dict[str, str] | None = None,
) -> str:
    """Generate C# script to create a prefab variant from an existing base.

    Args:
        name: Variant name.
        base_prefab_path: Path to the base prefab asset.
        overrides: Optional dict of property overrides to apply.

    Returns:
        Complete C# source string.
    """
    safe_name = _sanitize_cs_identifier(name)
    safe_display_name = _sanitize_cs_string(name)
    safe_base = _sanitize_cs_string(base_prefab_path)

    override_lines = ""
    if overrides:
        lines = []
        for prop_name, prop_val in overrides.items():
            sp = _sanitize_cs_string(prop_name)
            sv = _sanitize_cs_string(prop_val)
            lines.append(f'''            var prop_{_sanitize_cs_identifier(prop_name)} = so.FindProperty("{sp}");
            if (prop_{_sanitize_cs_identifier(prop_name)} != null) prop_{_sanitize_cs_identifier(prop_name)}.stringValue = "{sv}";''')
        override_lines = "\n".join(lines)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_CreateVariant_{safe_name}
{{
    [MenuItem("VeilBreakers/Prefab/Create Variant")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
            var basePrefab = AssetDatabase.LoadAssetAtPath<GameObject>("{safe_base}");
            if (basePrefab == null)
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_variant\\", \\"message\\": \\"Base prefab not found: {safe_base}\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                return;
            }}

            var instance = (GameObject)PrefabUtility.InstantiatePrefab(basePrefab);
            instance.name = "{safe_display_name}";
            Undo.RegisterCreatedObjectUndo(instance, "Create Variant {safe_display_name}");

            // Apply overrides via SerializedObject
            var so = new SerializedObject(instance);
{override_lines}
            so.ApplyModifiedProperties();

            // Save as prefab variant
            string dir = System.IO.Path.GetDirectoryName("{safe_base}").Replace("\\\\", "/");
            string variantPath = dir + "/{safe_display_name}.prefab";
            var savedVariant = PrefabUtility.SaveAsPrefabAsset(instance, variantPath);

            Object.DestroyImmediate(instance);

            if (savedVariant == null)
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_variant\\", \\"message\\": \\"SaveAsPrefabAsset failed for: " + variantPath + "\\", \\"validation_status\\": \\"failed\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                Debug.LogError("[VeilBreakers] SaveAsPrefabAsset returned null: " + variantPath);
                return;
            }}

            changedAssets.Add(variantPath);
            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"create_variant\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Variant created: " + variantPath);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_variant\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Variant creation failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 4. generate_prefab_modify_script
# ---------------------------------------------------------------------------


def generate_prefab_modify_script(
    prefab_path: str,
    modifications: list[dict],
) -> str:
    """Generate C# script to modify serialized properties on an existing prefab.

    Args:
        prefab_path: Path to the prefab asset.
        modifications: List of dicts with keys: property, value, type.

    Returns:
        Complete C# source string.
    """
    safe_path = _sanitize_cs_string(prefab_path)

    mod_lines = []
    for mod in modifications:
        mod_lines.append(_property_setter_snippet(mod))
    mod_code = "\n".join(mod_lines)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_ModifyPrefab
{{
    [MenuItem("VeilBreakers/Prefab/Modify Prefab")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>("{safe_path}");
            if (prefab == null)
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"modify_prefab\\", \\"message\\": \\"Prefab not found: {safe_path}\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                return;
            }}

            var so = new SerializedObject(prefab);
            Undo.RecordObject(prefab, "Modify Prefab");
{mod_code}
            so.ApplyModifiedProperties();
            EditorUtility.SetDirty(prefab);
            AssetDatabase.SaveAssets();
            changedAssets.Add("{safe_path}");

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"modify_prefab\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Prefab modified: {safe_path}");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"modify_prefab\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Prefab modification failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 5. generate_prefab_delete_script
# ---------------------------------------------------------------------------


def generate_prefab_delete_script(prefab_path: str) -> str:
    """Generate C# script to delete a prefab asset.

    Args:
        prefab_path: Path to the prefab asset to delete.

    Returns:
        Complete C# source string.
    """
    safe_path = _sanitize_cs_string(prefab_path)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_DeletePrefab
{{
    [MenuItem("VeilBreakers/Prefab/Delete Prefab")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
            Undo.RecordObject(AssetDatabase.LoadAssetAtPath<Object>("{safe_path}"), "Delete Prefab");
            bool deleted = AssetDatabase.DeleteAsset("{safe_path}");
            if (deleted)
            {{
                changedAssets.Add("{safe_path}");
                string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
                string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"delete_prefab\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                Debug.Log("[VeilBreakers] Prefab deleted: {safe_path}");
            }}
            else
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"delete_prefab\\", \\"message\\": \\"Failed to delete: {safe_path}\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
            }}
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"delete_prefab\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Prefab deletion failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 6. generate_add_component_script
# ---------------------------------------------------------------------------


def generate_add_component_script(
    selector: dict | str,
    component_type: str,
    properties: list[dict] | None = None,
) -> str:
    """Generate C# script to add a component to a GameObject.

    Args:
        selector: GameObject selector (dict or string shorthand).
        component_type: Component type to add.
        properties: Optional property configuration.

    Returns:
        Complete C# source string.
    """
    safe_comp = _sanitize_cs_string(component_type)
    selector_code = _resolve_selector_snippet(selector)

    prop_lines = ""
    if properties:
        lines = ["            var so = new SerializedObject(comp);"]
        for prop in properties:
            lines.append(_property_setter_snippet(prop))
        lines.append("            so.ApplyModifiedProperties();")
        prop_lines = "\n".join(lines)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_AddComponent
{{
    [MenuItem("VeilBreakers/Prefab/Add Component")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
{selector_code}

            Undo.RecordObject(target, "Add Component {safe_comp}");
            var comp = Undo.AddComponent(target, typeof({safe_comp}));
            changedAssets.Add(target.name);
{prop_lines}

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"add_component\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Component added: {safe_comp}");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"add_component\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Add component failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 7. generate_remove_component_script
# ---------------------------------------------------------------------------


def generate_remove_component_script(
    selector: dict | str,
    component_type: str,
) -> str:
    """Generate C# script to remove a component from a GameObject.

    Args:
        selector: GameObject selector.
        component_type: Component type to remove.

    Returns:
        Complete C# source string.
    """
    safe_comp = _sanitize_cs_string(component_type)
    selector_code = _resolve_selector_snippet(selector)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_RemoveComponent
{{
    [MenuItem("VeilBreakers/Prefab/Remove Component")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
{selector_code}

            var comp = target.GetComponent(typeof({safe_comp}));
            if (comp != null)
            {{
                Undo.DestroyObjectImmediate(comp);
                changedAssets.Add(target.name);
                string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
                string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"remove_component\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                Debug.Log("[VeilBreakers] Component removed: {safe_comp}");
            }}
            else
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"remove_component\\", \\"message\\": \\"Component not found: {safe_comp}\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
            }}
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"remove_component\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Remove component failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 8. generate_configure_component_script
# ---------------------------------------------------------------------------


def generate_configure_component_script(
    selector: dict | str,
    component_type: str,
    properties: list[dict],
) -> str:
    """Generate C# script to configure component properties via SerializedObject.

    Args:
        selector: GameObject selector.
        component_type: Component type to configure.
        properties: List of dicts with property, value, type.

    Returns:
        Complete C# source string.
    """
    safe_comp = _sanitize_cs_string(component_type)
    selector_code = _resolve_selector_snippet(selector)

    prop_lines = []
    for prop in properties:
        prop_lines.append(_property_setter_snippet(prop))
    prop_code = "\n".join(prop_lines)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_ConfigureComponent
{{
    [MenuItem("VeilBreakers/Prefab/Configure Component")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
{selector_code}

            var comp = target.GetComponent(typeof({safe_comp}));
            if (comp == null)
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"configure_component\\", \\"message\\": \\"Component not found: {safe_comp}\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                return;
            }}

            Undo.RecordObject(comp, "Configure {safe_comp}");
            var so = new SerializedObject(comp);
{prop_code}
            so.ApplyModifiedProperties();
            changedAssets.Add(target.name);

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"configure_component\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Component configured: {safe_comp}");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"configure_component\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Configure component failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 9. generate_reflect_component_script
# ---------------------------------------------------------------------------


def generate_reflect_component_script(
    selector: dict | str,
    component_type: str,
) -> str:
    """Generate C# script to reflect/introspect all serialized fields of a component.

    Args:
        selector: GameObject selector.
        component_type: Component type to introspect.

    Returns:
        Complete C# source string.
    """
    safe_comp = _sanitize_cs_string(component_type)
    selector_code = _resolve_selector_snippet(selector)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_ReflectComponent
{{
    [MenuItem("VeilBreakers/Prefab/Reflect Component")]
    public static void Execute()
    {{
        try
        {{
{selector_code}

            var comp = target.GetComponent(typeof({safe_comp}));
            if (comp == null)
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"reflect_component\\", \\"message\\": \\"Component not found: {safe_comp}\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                return;
            }}

            Undo.RecordObject(comp, "Reflect {safe_comp}");
            var so = new SerializedObject(comp);
            var iter = so.GetIterator();
            var fields = new List<string>();

            while (iter.NextVisible(true))
            {{
                string fieldInfo = "{{\\"name\\": \\"" + iter.name + "\\", \\"type\\": \\"" + iter.propertyType.ToString() + "\\", \\"displayName\\": \\"" + iter.displayName + "\\"}}";
                fields.Add(fieldInfo);
            }}

            string fieldsJson = "[" + string.Join(",", fields) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"reflect_component\\", \\"component\\": \\"{safe_comp}\\", \\"fields\\": " + fieldsJson + ", \\"changed_assets\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Component reflected: {safe_comp} (" + fields.Count + " fields)");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"reflect_component\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Reflect component failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 10. generate_hierarchy_script
# ---------------------------------------------------------------------------


def generate_hierarchy_script(operation: str, **kwargs) -> str:
    """Generate C# script for hierarchy manipulation operations.

    Args:
        operation: One of create_empty, rename, reparent, enable, disable,
                   set_layer, set_tag, duplicate, delete.
        **kwargs: Operation-specific parameters (selector, name, parent_name,
                  new_name, layer, tag).

    Returns:
        Complete C# source string.
    """
    safe_op = _sanitize_cs_identifier(operation)

    if operation == "create_empty":
        obj_name = _sanitize_cs_string(kwargs.get("name", "NewEmpty"))
        return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_Hierarchy_{safe_op}
{{
    [MenuItem("VeilBreakers/Prefab/Hierarchy")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
            var go = new GameObject("{obj_name}");
            Undo.RegisterCreatedObjectUndo(go, "Create Empty {obj_name}");
            changedAssets.Add(go.name);

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"hierarchy\\", \\"operation\\": \\"{operation}\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Empty GameObject created: {obj_name}");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"hierarchy\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Hierarchy operation failed: " + ex.Message);
        }}
    }}
}}
'''

    # All other operations need a selector
    selector = kwargs.get("selector", kwargs.get("name", ""))
    selector_code = _resolve_selector_snippet(selector)

    if operation == "reparent":
        parent = _sanitize_cs_string(kwargs.get("parent_name", ""))
        return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_Hierarchy_{safe_op}
{{
    [MenuItem("VeilBreakers/Prefab/Hierarchy")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
{selector_code}

            var parent = GameObject.Find("{parent}");
            if (parent == null)
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"hierarchy\\", \\"message\\": \\"Parent not found: {parent}\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                return;
            }}

            Undo.RecordObject(target.transform, "Reparent");
            target.transform.SetParent(parent.transform);
            changedAssets.Add(target.name);

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"hierarchy\\", \\"operation\\": \\"reparent\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Reparented to: {parent}");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"hierarchy\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Hierarchy operation failed: " + ex.Message);
        }}
    }}
}}
'''

    elif operation == "set_layer":
        layer_name = _sanitize_cs_string(kwargs.get("layer", "Default"))
        return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_Hierarchy_{safe_op}
{{
    [MenuItem("VeilBreakers/Prefab/Hierarchy")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
{selector_code}

            Undo.RecordObject(target, "Set Layer");
            target.gameObject.layer = LayerMask.NameToLayer("{layer_name}");
            changedAssets.Add(target.name);

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"hierarchy\\", \\"operation\\": \\"set_layer\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Layer set to: {layer_name}");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"hierarchy\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Hierarchy operation failed: " + ex.Message);
        }}
    }}
}}
'''

    elif operation == "set_tag":
        tag_name = _sanitize_cs_string(kwargs.get("tag", "Untagged"))
        return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_Hierarchy_{safe_op}
{{
    [MenuItem("VeilBreakers/Prefab/Hierarchy")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
{selector_code}

            Undo.RecordObject(target, "Set Tag");
            target.gameObject.tag = "{tag_name}";
            changedAssets.Add(target.name);

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"hierarchy\\", \\"operation\\": \\"set_tag\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Tag set to: {tag_name}");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"hierarchy\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Hierarchy operation failed: " + ex.Message);
        }}
    }}
}}
'''

    elif operation in ("enable", "disable"):
        active = "true" if operation == "enable" else "false"
        return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_Hierarchy_{safe_op}
{{
    [MenuItem("VeilBreakers/Prefab/Hierarchy")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
{selector_code}

            Undo.RecordObject(target, "{operation.title()}");
            target.SetActive({active});
            changedAssets.Add(target.name);

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"hierarchy\\", \\"operation\\": \\"{operation}\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] GameObject {operation}d");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"hierarchy\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Hierarchy operation failed: " + ex.Message);
        }}
    }}
}}
'''

    elif operation == "rename":
        new_name = _sanitize_cs_string(kwargs.get("new_name", "Renamed"))
        return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_Hierarchy_{safe_op}
{{
    [MenuItem("VeilBreakers/Prefab/Hierarchy")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
{selector_code}

            Undo.RecordObject(target, "Rename");
            target.name = "{new_name}";
            changedAssets.Add(target.name);

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"hierarchy\\", \\"operation\\": \\"rename\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Renamed to: {new_name}");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"hierarchy\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Hierarchy operation failed: " + ex.Message);
        }}
    }}
}}
'''

    elif operation == "duplicate":
        return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_Hierarchy_{safe_op}
{{
    [MenuItem("VeilBreakers/Prefab/Hierarchy")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
{selector_code}

            var duplicate = Object.Instantiate(target);
            duplicate.name = target.name + "_Copy";
            Undo.RegisterCreatedObjectUndo(duplicate, "Duplicate");
            changedAssets.Add(duplicate.name);

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"hierarchy\\", \\"operation\\": \\"duplicate\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Duplicated: " + duplicate.name);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"hierarchy\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Hierarchy operation failed: " + ex.Message);
        }}
    }}
}}
'''

    elif operation == "delete":
        return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_Hierarchy_{safe_op}
{{
    [MenuItem("VeilBreakers/Prefab/Hierarchy")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
{selector_code}

            changedAssets.Add(target.name);
            Undo.DestroyObjectImmediate(target);

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"hierarchy\\", \\"operation\\": \\"delete\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Deleted GameObject");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"hierarchy\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Hierarchy operation failed: " + ex.Message);
        }}
    }}
}}
'''

    else:
        # Unknown operation fallback
        return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_Hierarchy_Unknown
{{
    [MenuItem("VeilBreakers/Prefab/Hierarchy")]
    public static void Execute()
    {{
        string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"hierarchy\\", \\"message\\": \\"Unknown operation: {operation}\\", \\"changed_assets\\": [], \\"validation_status\\": \\"error\\"}}";
        System.IO.File.WriteAllText("Temp/vb_result.json", json);
    }}
}}
'''


# ---------------------------------------------------------------------------
# 11. generate_batch_configure_script
# ---------------------------------------------------------------------------


def generate_batch_configure_script(
    selector: dict,
    component_type: str,
    properties: list[dict],
) -> str:
    """Generate C# script to batch-configure components on multiple GameObjects.

    Args:
        selector: Batch selector dict with by=tag|layer|name_pattern.
        component_type: Component type to configure.
        properties: Property list to apply.

    Returns:
        Complete C# source string.
    """
    safe_comp = _sanitize_cs_string(component_type)
    mode = selector.get("by", "tag")
    value = _sanitize_cs_string(selector.get("value", ""))

    if mode == "tag":
        find_code = f'            var objects = GameObject.FindGameObjectsWithTag("{value}");'
    elif mode == "layer":
        find_code = f'''            var allObjects = Object.FindObjectsOfType<GameObject>();
            var objectsList = new System.Collections.Generic.List<GameObject>();
            int targetLayer = LayerMask.NameToLayer("{value}");
            foreach (var obj in allObjects)
            {{
                if (obj.layer == targetLayer) objectsList.Add(obj);
            }}
            var objects = objectsList.ToArray();'''
    elif mode == "name_pattern":
        find_code = f'''            var allObjects = Object.FindObjectsOfType<GameObject>();
            var objectsList = new System.Collections.Generic.List<GameObject>();
            var pattern = new System.Text.RegularExpressions.Regex("{value}");
            foreach (var obj in allObjects)
            {{
                if (pattern.IsMatch(obj.name)) objectsList.Add(obj);
            }}
            var objects = objectsList.ToArray();'''
    else:
        find_code = f'            var objects = GameObject.FindGameObjectsWithTag("{value}");'

    prop_lines = []
    for prop in properties:
        prop_lines.append(_property_setter_snippet(prop))
    prop_code = "\n".join(prop_lines)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_BatchConfigure
{{
    [MenuItem("VeilBreakers/Prefab/Batch Configure")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
{find_code}

            foreach (var target in objects)
            {{
                var comp = target.GetComponent(typeof({safe_comp}));
                if (comp == null)
                {{
                    comp = Undo.AddComponent(target, typeof({safe_comp}));
                }}
                Undo.RecordObject(comp, "Batch Configure {safe_comp}");
                var so = new SerializedObject(comp);
{prop_code}
                so.ApplyModifiedProperties();
                changedAssets.Add(target.name);
            }}

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"batch_configure\\", \\"count\\": " + objects.Length + ", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Batch configured " + objects.Length + " objects");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"batch_configure\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Batch configure failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 12. generate_variant_matrix_script
# ---------------------------------------------------------------------------


def generate_variant_matrix_script(
    base_name: str,
    base_prefab_path: str,
    corruption_tiers: list[int],
    brands: list[str],
    output_dir: str = "Assets/Prefabs/Variants",
) -> str:
    """Generate C# script to create a corruption x brand variant matrix.

    Args:
        base_name: Base prefab name.
        base_prefab_path: Path to the base prefab.
        corruption_tiers: List of corruption tier levels.
        brands: List of brand names.
        output_dir: Output directory for variants.

    Returns:
        Complete C# source string.
    """
    safe_base_name = _sanitize_cs_string(base_name)
    safe_base_path = _sanitize_cs_string(base_prefab_path)
    safe_output_dir = _sanitize_cs_string(output_dir)

    tiers_cs = ", ".join(str(t) for t in corruption_tiers)
    brands_cs = ", ".join(f'"{_sanitize_cs_string(b)}"' for b in brands)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_VariantMatrix
{{
    [MenuItem("VeilBreakers/Prefab/Generate Variant Matrix")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
            var basePrefab = AssetDatabase.LoadAssetAtPath<GameObject>("{safe_base_path}");
            if (basePrefab == null)
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"variant_matrix\\", \\"message\\": \\"Base prefab not found: {safe_base_path}\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                return;
            }}

            int[] tiers = new int[] {{ {tiers_cs} }};
            string[] brands = new string[] {{ {brands_cs} }};
            string outputDir = "{safe_output_dir}";

            // Ensure output directory
            if (!AssetDatabase.IsValidFolder(outputDir))
            {{
                string[] parts = outputDir.Split('/');
                string current = parts[0];
                for (int i = 1; i < parts.Length; i++)
                {{
                    string next = current + "/" + parts[i];
                    if (!AssetDatabase.IsValidFolder(next))
                        AssetDatabase.CreateFolder(current, parts[i]);
                    current = next;
                }}
            }}

            AssetDatabase.StartAssetEditing();
            try
            {{
                Undo.IncrementCurrentGroup();
                foreach (int tier in tiers)
                {{
                    foreach (string brand in brands)
                    {{
                        string variantName = "{safe_base_name}_C" + tier + "_" + brand;
                        var instance = (GameObject)PrefabUtility.InstantiatePrefab(basePrefab);
                        instance.name = variantName;
                        Undo.RegisterCreatedObjectUndo(instance, "Create Variant " + variantName);

                        string variantPath = outputDir + "/" + variantName + ".prefab";
                        var savedVariant = PrefabUtility.SaveAsPrefabAsset(instance, variantPath);
                        if (savedVariant != null)
                        {{
                            changedAssets.Add(variantPath);
                        }}
                        else
                        {{
                            Debug.LogWarning("[VeilBreakers] SaveAsPrefabAsset returned null for: " + variantPath);
                        }}
                        Object.DestroyImmediate(instance);
                    }}
                }}
            }}
            finally
            {{
                AssetDatabase.StopAssetEditing();
            }}

            AssetDatabase.Refresh();

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"variant_matrix\\", \\"count\\": " + changedAssets.Count + ", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Variant matrix generated: " + changedAssets.Count + " variants");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"variant_matrix\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Variant matrix failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 13. generate_joint_setup_script
# ---------------------------------------------------------------------------


def generate_joint_setup_script(
    selector: dict | str,
    joint_type: str,
    config: dict,
) -> str:
    """Generate C# script to configure a physics joint on a GameObject.

    Args:
        selector: GameObject selector.
        joint_type: One of HingeJoint, SpringJoint, ConfigurableJoint,
                    CharacterJoint, FixedJoint.
        config: Dict of joint property settings.

    Returns:
        Complete C# source string.
    """
    safe_joint = _sanitize_cs_identifier(joint_type)
    selector_code = _resolve_selector_snippet(selector)

    # Build config lines
    config_lines = []
    for key, val in config.items():
        safe_key = _sanitize_cs_identifier(key)
        safe_val = _sanitize_cs_string(str(val))
        if key == "physics_material":
            config_lines.append(f'''            var physMat = new PhysicMaterial("{safe_val}");
            var col = target.GetComponent<Collider>();
            if (col != null) col.material = physMat;''')
        else:
            config_lines.append(f'            // Config: {safe_key} = {safe_val}')
    config_code = "\n".join(config_lines)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_SetupJoint
{{
    [MenuItem("VeilBreakers/Prefab/Setup Joint")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
{selector_code}

            Undo.RecordObject(target, "Setup {safe_joint}");
            var joint = Undo.AddComponent<{safe_joint}>(target);
{config_code}
            changedAssets.Add(target.name);

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"setup_joint\\", \\"joint_type\\": \\"{safe_joint}\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Joint configured: {safe_joint}");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"setup_joint\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Joint setup failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 14. generate_navmesh_setup_script
# ---------------------------------------------------------------------------


def generate_navmesh_setup_script(
    operation: str,
    selector: dict | str,
    **kwargs,
) -> str:
    """Generate C# script for NavMesh configuration operations.

    Args:
        operation: One of add_obstacle, add_link, configure_area, add_modifier.
        selector: GameObject selector.
        **kwargs: Operation-specific parameters.

    Returns:
        Complete C# source string.
    """
    selector_code = _resolve_selector_snippet(selector)
    safe_op = _sanitize_cs_identifier(operation)

    if operation == "add_obstacle":
        carve = str(kwargs.get("carve", True)).lower()
        return f'''using UnityEngine;
using UnityEditor;
using UnityEngine.AI;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_NavMeshSetup_{safe_op}
{{
    [MenuItem("VeilBreakers/Prefab/NavMesh Setup")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
{selector_code}

            Undo.RecordObject(target, "Add NavMeshObstacle");
            var obstacle = Undo.AddComponent<NavMeshObstacle>(target);
            obstacle.carving = {carve};
            changedAssets.Add(target.name);

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"navmesh_setup\\", \\"operation\\": \\"add_obstacle\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] NavMeshObstacle added");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"navmesh_setup\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] NavMesh setup failed: " + ex.Message);
        }}
    }}
}}
'''

    elif operation == "add_link":
        width = kwargs.get("width", 1.0)
        return f'''using UnityEngine;
using UnityEditor;
using UnityEngine.AI;
using Unity.AI.Navigation;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_NavMeshSetup_{safe_op}
{{
    [MenuItem("VeilBreakers/Prefab/NavMesh Setup")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
{selector_code}

            Undo.RecordObject(target, "Add NavMeshLink");
            var link = Undo.AddComponent<NavMeshLink>(target);
            link.width = {width}f;
            changedAssets.Add(target.name);

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"navmesh_setup\\", \\"operation\\": \\"add_link\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] NavMeshLink added");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"navmesh_setup\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] NavMesh setup failed: " + ex.Message);
        }}
    }}
}}
'''

    elif operation == "configure_area":
        area_index = kwargs.get("area_index", 0)
        cost = kwargs.get("cost", 1.0)
        return f'''using UnityEngine;
using UnityEditor;
using UnityEngine.AI;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_NavMeshSetup_{safe_op}
{{
    [MenuItem("VeilBreakers/Prefab/NavMesh Setup")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
{selector_code}

            Undo.RecordObject(target, "Configure NavMesh Area");
            NavMesh.SetAreaCost({area_index}, {cost}f);
            changedAssets.Add(target.name);

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"navmesh_setup\\", \\"operation\\": \\"configure_area\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] NavMesh area configured");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"navmesh_setup\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] NavMesh setup failed: " + ex.Message);
        }}
    }}
}}
'''

    else:  # add_modifier or unknown
        return f'''using UnityEngine;
using UnityEditor;
using UnityEngine.AI;
using Unity.AI.Navigation;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_NavMeshSetup_{safe_op}
{{
    [MenuItem("VeilBreakers/Prefab/NavMesh Setup")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
{selector_code}

            Undo.RecordObject(target, "Add NavMeshModifier");
            var modifier = Undo.AddComponent<NavMeshModifier>(target);
            changedAssets.Add(target.name);

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"navmesh_setup\\", \\"operation\\": \\"{operation}\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] NavMeshModifier added");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"navmesh_setup\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] NavMesh setup failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 15. generate_bone_socket_script
# ---------------------------------------------------------------------------


_STANDARD_SOCKETS = [
    "weapon_hand_R", "weapon_hand_L", "shield_hand_L",
    "back_weapon", "hip_L", "hip_R", "head", "chest",
    "spell_hand_R", "spell_hand_L",
]

_BONE_MAP = {
    "weapon_hand_R": "RightHand",
    "weapon_hand_L": "LeftHand",
    "shield_hand_L": "LeftHand",
    "back_weapon": "Spine2",
    "hip_L": "LeftUpperLeg",
    "hip_R": "RightUpperLeg",
    "head": "Head",
    "chest": "Chest",
    "spell_hand_R": "RightHand",
    "spell_hand_L": "LeftHand",
}


def generate_bone_socket_script(
    prefab_path: str,
    sockets: list[str] | None = None,
) -> str:
    """Generate C# script to create bone socket attachment points on a character rig.

    Args:
        prefab_path: Path to the character prefab.
        sockets: List of socket names to create. Defaults to all 10 standard.

    Returns:
        Complete C# source string.
    """
    if sockets is None:
        sockets = _STANDARD_SOCKETS

    safe_path = _sanitize_cs_string(prefab_path)

    # Build bone map dictionary entries
    bone_map_entries = []
    for socket_name in _STANDARD_SOCKETS:
        bone_name = _BONE_MAP.get(socket_name, "Hips")
        bone_map_entries.append(f'            {{ "{socket_name}", "{bone_name}" }}')
    bone_map_cs = ",\n".join(bone_map_entries)

    # Build socket list
    socket_list_entries = ", ".join(f'"{_sanitize_cs_string(s)}"' for s in sockets)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_BoneSockets
{{
    static Transform FindDeepChild(Transform parent, string name)
    {{
        foreach (Transform child in parent)
        {{
            if (child.name == name) return child;
            Transform result = FindDeepChild(child, name);
            if (result != null) return result;
        }}
        return null;
    }}

    [MenuItem("VeilBreakers/Prefab/Setup Bone Sockets")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        try
        {{
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>("{safe_path}");
            if (prefab == null)
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"bone_sockets\\", \\"message\\": \\"Prefab not found: {safe_path}\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                return;
            }}

            var instance = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            Undo.RegisterCreatedObjectUndo(instance, "Setup Bone Sockets");

            var animator = instance.GetComponent<Animator>();
            var boneMap = new Dictionary<string, string>
            {{
{bone_map_cs}
            }};

            string[] requestedSockets = new string[] {{ {socket_list_entries} }};

            foreach (string socketName in requestedSockets)
            {{
                if (!boneMap.ContainsKey(socketName)) continue;

                Transform boneTransform = null;

                // Try Humanoid bone lookup first
                if (animator != null && animator.isHuman)
                {{
                    var boneName = boneMap[socketName];
                    System.Enum.TryParse<HumanBodyBones>(boneName, out var humanBone);
                    boneTransform = animator.GetBoneTransform(humanBone);
                }}

                // Fallback: recursive deep search of all descendants
                if (boneTransform == null)
                {{
                    boneTransform = FindDeepChild(instance.transform, boneMap[socketName]);
                }}

                if (boneTransform != null)
                {{
                    var socket = new GameObject("Socket_" + socketName);
                    socket.transform.SetParent(boneTransform);
                    socket.transform.localPosition = Vector3.zero;
                    socket.transform.localRotation = Quaternion.identity;
                    changedAssets.Add("Socket_" + socketName);
                }}
            }}

            var savedPrefab = PrefabUtility.SaveAsPrefabAsset(instance, "{safe_path}");
            Object.DestroyImmediate(instance);

            if (savedPrefab == null)
            {{
                string errJson = "{{\\"status\\": \\"error\\", \\"action\\": \\"bone_sockets\\", \\"message\\": \\"SaveAsPrefabAsset failed for: {safe_path}\\", \\"validation_status\\": \\"failed\\"}}";
                File.WriteAllText("Temp/vb_result.json", errJson);
                Debug.LogError("[VeilBreakers] SaveAsPrefabAsset returned null: {safe_path}");
                return;
            }}

            changedAssets.Add("{safe_path}");

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"bone_sockets\\", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Bone sockets created: " + changedAssets.Count);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"bone_sockets\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Bone socket setup failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# 16. generate_validate_project_script
# ---------------------------------------------------------------------------


def generate_validate_project_script() -> str:
    """Generate C# script to validate project integrity (prefabs, scripts, materials).

    Returns:
        Complete C# source string.
    """
    return '''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_ValidateProject
{
    [MenuItem("VeilBreakers/Prefab/Validate Project Integrity")]
    public static void Execute()
    {
        var changedAssets = new List<string>();
        var warnings = new List<string>();
        try
        {
            string[] guids = AssetDatabase.FindAssets("t:Prefab");
            int totalPrefabs = guids.Length;
            int missingScripts = 0;
            int missingMaterials = 0;

            foreach (string guid in guids)
            {
                string path = AssetDatabase.GUIDToAssetPath(guid);
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                if (prefab == null) continue;

                var components = prefab.GetComponents<Component>();
                foreach (var comp in components)
                {
                    if (comp == null)
                    {
                        missingScripts++;
                        warnings.Add("Missing script on: " + path);
                    }
                }

                var renderers = prefab.GetComponentsInChildren<Renderer>(true);
                foreach (var rend in renderers)
                {
                    if (rend.sharedMaterials != null)
                    {
                        foreach (var mat in rend.sharedMaterials)
                        {
                            if (mat == null)
                            {
                                missingMaterials++;
                                warnings.Add("Missing material on: " + path);
                            }
                        }
                    }
                }

                changedAssets.Add(path);
            }

            string status = (missingScripts == 0 && missingMaterials == 0) ? "ok" : "warnings";
            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string warnJson = "[" + string.Join(",", warnings.ConvertAll(w => "\\"" + w.Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string json = "{\\"status\\": \\"success\\", \\"action\\": \\"validate_project\\", \\"total_prefabs\\": " + totalPrefabs +
                ", \\"missing_scripts\\": " + missingScripts +
                ", \\"missing_materials\\": " + missingMaterials +
                ", \\"changed_assets\\": " + changedJson +
                ", \\"warnings\\": " + warnJson +
                ", \\"validation_status\\": \\"" + status + "\\"}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Project validation complete: " + totalPrefabs + " prefabs scanned");
        }
        catch (System.Exception ex)
        {
            string json = "{\\"status\\": \\"error\\", \\"action\\": \\"validate_project\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Project validation failed: " + ex.Message);
        }
    }
}
'''


# ---------------------------------------------------------------------------
# 17. generate_job_script
# ---------------------------------------------------------------------------


def generate_job_script(operations: list[dict]) -> str:
    """Generate a single C# script that performs multiple operations in one compile cycle.

    Args:
        operations: List of operation dicts, each with 'action' key and
                    action-specific parameters (selector, component_type,
                    properties, operation, etc.).

    Returns:
        Complete C# source string.
    """
    if not operations:
        return '''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_JobScript
{
    [MenuItem("VeilBreakers/Prefab/Execute Job Script")]
    public static void Execute()
    {
        string json = "{\\"status\\": \\"warning\\", \\"action\\": \\"job_script\\", \\"message\\": \\"No operations provided - empty job\\", \\"changed_assets\\": [], \\"validation_status\\": \\"ok\\"}";
        File.WriteAllText("Temp/vb_result.json", json);
        Debug.LogWarning("[VeilBreakers] Job script executed with no operations");
    }
}
'''

    # Build operation code blocks
    step_blocks = []
    for i, op in enumerate(operations):
        action = op.get("action", "")
        step_num = i + 1
        selector = op.get("selector", op.get("object_name", ""))
        comp_type = _sanitize_cs_string(op.get("component_type", ""))
        properties = op.get("properties", [])

        selector_code = _resolve_selector_snippet(selector)
        # Rename 'target' to unique per step to avoid conflicts
        step_target = f"target_{step_num}"
        selector_code = selector_code.replace("GameObject target", f"GameObject {step_target}")
        selector_code = selector_code.replace("target =", f"{step_target} =")
        selector_code = selector_code.replace("target !", f"{step_target} !")
        selector_code = selector_code.replace("if (target", f"if ({step_target}")
        selector_code = selector_code.replace("target.", f"{step_target}.")
        selector_code = selector_code.replace("target)", f"{step_target})")
        # In job context, selector failure should throw instead of return
        # to be caught by step-level try/catch and continue to next step
        selector_code = selector_code.replace(
            'System.IO.File.WriteAllText("Temp/vb_result.json", errJson);\n                return;',
            'throw new System.Exception(errJson);'
        )

        if action == "add_component":
            step_blocks.append(f'''
                // Step {step_num}: Add component {comp_type}
                try
                {{
{selector_code}
                    Undo.RecordObject({step_target}, "Job: Add {comp_type}");
                    var comp_{step_num} = Undo.AddComponent({step_target}, typeof({comp_type}));
                    changedAssets.Add({step_target}.name);
                    steps.Add("{{\\"step\\": {step_num}, \\"action\\": \\"add_component\\", \\"status\\": \\"success\\"}}");
                }}
                catch (System.Exception ex_{step_num})
                {{
                    steps.Add("{{\\"step\\": {step_num}, \\"action\\": \\"add_component\\", \\"status\\": \\"error\\", \\"message\\": \\"" + ex_{step_num}.Message.Replace("\\"", "\\\\\\"") + "\\"}}");
                }}''')

        elif action == "remove_component":
            step_blocks.append(f'''
                // Step {step_num}: Remove component {comp_type}
                try
                {{
{selector_code}
                    var comp_{step_num} = {step_target}.GetComponent(typeof({comp_type}));
                    if (comp_{step_num} != null)
                    {{
                        Undo.DestroyObjectImmediate(comp_{step_num});
                        changedAssets.Add({step_target}.name);
                    }}
                    steps.Add("{{\\"step\\": {step_num}, \\"action\\": \\"remove_component\\", \\"status\\": \\"success\\"}}");
                }}
                catch (System.Exception ex_{step_num})
                {{
                    steps.Add("{{\\"step\\": {step_num}, \\"action\\": \\"remove_component\\", \\"status\\": \\"error\\", \\"message\\": \\"" + ex_{step_num}.Message.Replace("\\"", "\\\\\\"") + "\\"}}");
                }}''')

        elif action == "configure":
            prop_lines = []
            for prop in properties:
                prop_lines.append(_property_setter_snippet(prop))
            prop_code = "\n".join(prop_lines)

            step_blocks.append(f'''
                // Step {step_num}: Configure {comp_type}
                try
                {{
{selector_code}
                    var comp_{step_num} = {step_target}.GetComponent(typeof({comp_type}));
                    if (comp_{step_num} != null)
                    {{
                        Undo.RecordObject(comp_{step_num}, "Job: Configure {comp_type}");
                        var so = new SerializedObject(comp_{step_num});
{prop_code}
                        so.ApplyModifiedProperties();
                        changedAssets.Add({step_target}.name);
                    }}
                    steps.Add("{{\\"step\\": {step_num}, \\"action\\": \\"configure\\", \\"status\\": \\"success\\"}}");
                }}
                catch (System.Exception ex_{step_num})
                {{
                    steps.Add("{{\\"step\\": {step_num}, \\"action\\": \\"configure\\", \\"status\\": \\"error\\", \\"message\\": \\"" + ex_{step_num}.Message.Replace("\\"", "\\\\\\"") + "\\"}}");
                }}''')

        elif action == "hierarchy":
            hier_op = op.get("operation", "create_empty")
            step_blocks.append(f'''
                // Step {step_num}: Hierarchy operation {hier_op}
                try
                {{
{selector_code}
                    Undo.RecordObject({step_target}, "Job: Hierarchy {hier_op}");
                    changedAssets.Add({step_target}.name);
                    steps.Add("{{\\"step\\": {step_num}, \\"action\\": \\"hierarchy\\", \\"status\\": \\"success\\"}}");
                }}
                catch (System.Exception ex_{step_num})
                {{
                    steps.Add("{{\\"step\\": {step_num}, \\"action\\": \\"hierarchy\\", \\"status\\": \\"error\\", \\"message\\": \\"" + ex_{step_num}.Message.Replace("\\"", "\\\\\\"") + "\\"}}");
                }}''')

        elif action == "setup_joints":
            jt = _sanitize_cs_identifier(op.get("joint_type", "HingeJoint"))
            step_blocks.append(f'''
                // Step {step_num}: Setup joint {jt}
                try
                {{
{selector_code}
                    Undo.RecordObject({step_target}, "Job: Setup {jt}");
                    Undo.AddComponent<{jt}>({step_target});
                    changedAssets.Add({step_target}.name);
                    steps.Add("{{\\"step\\": {step_num}, \\"action\\": \\"setup_joints\\", \\"status\\": \\"success\\"}}");
                }}
                catch (System.Exception ex_{step_num})
                {{
                    steps.Add("{{\\"step\\": {step_num}, \\"action\\": \\"setup_joints\\", \\"status\\": \\"error\\", \\"message\\": \\"" + ex_{step_num}.Message.Replace("\\"", "\\\\\\"") + "\\"}}");
                }}''')

        else:
            step_blocks.append(f'''
                // Step {step_num}: Unknown action {action}
                steps.Add("{{\\"step\\": {step_num}, \\"action\\": \\"{action}\\", \\"status\\": \\"skipped\\", \\"message\\": \\"Unknown action\\"}}");''')

    steps_code = "\n".join(step_blocks)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_JobScript
{{
    [MenuItem("VeilBreakers/Prefab/Execute Job Script")]
    public static void Execute()
    {{
        var changedAssets = new List<string>();
        var steps = new List<string>();
        try
        {{
            Undo.IncrementCurrentGroup();
            AssetDatabase.StartAssetEditing();
            try
            {{
{steps_code}
            }}
            finally
            {{
                AssetDatabase.StopAssetEditing();
            }}

            string changedJson = "[" + string.Join(",", changedAssets.ConvertAll(a => "\\"" + a.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"")) + "]";
            string stepsJson = "[" + string.Join(",", steps) + "]";
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"job_script\\", \\"steps\\": " + stepsJson + ", \\"changed_assets\\": " + changedJson + ", \\"warnings\\": [], \\"validation_status\\": \\"ok\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Job script executed: " + steps.Count + " steps");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"job_script\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Job script failed: " + ex.Message);
        }}
    }}
}}
'''
