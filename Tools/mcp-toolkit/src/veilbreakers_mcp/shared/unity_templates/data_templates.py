"""C# template generators for data-driven game architecture.

Covers ScriptableObject definitions with .asset instantiation, JSON config
validation and typed loading, Unity Localization string table setup, and game
data authoring EditorWindow tools.

All generated scripts write their result to Temp/vb_result.json so that
the Python MCP server can read back the outcome after execution.

Exports:
    generate_so_definition             -- DATA-02: ScriptableObject class definition
    generate_asset_creation_script     -- DATA-02: .asset file instantiation editor script
    generate_json_validator_script     -- DATA-01: JSON config schema validator
    generate_json_loader_script        -- DATA-01: Typed C# data class + JSON loader
    generate_localization_setup_script -- DATA-03: Unity Localization infrastructure setup
    generate_localization_entries_script -- DATA-03: String table entry population
    generate_data_authoring_window     -- DATA-04: IMGUI EditorWindow for batch SO authoring

Helpers (imported from _cs_sanitize):
    sanitize_cs_string                 -- C# string literal escaping
    sanitize_cs_identifier             -- C# identifier sanitization
"""

from __future__ import annotations

import re

from ._cs_sanitize import sanitize_cs_identifier, sanitize_cs_string

# ---------------------------------------------------------------------------
# C# reserved keywords (for namespace sanitization)
# ---------------------------------------------------------------------------

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
    """Sanitize a C# namespace string.

    Beyond stripping invalid characters, this also handles leading digits
    and C# reserved keywords in namespace segments.
    """
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


# ---------------------------------------------------------------------------
# C# type mapping helpers
# ---------------------------------------------------------------------------

_CS_TYPE_MAP: dict[str, str] = {
    "string": "string",
    "int": "int",
    "float": "float",
    "bool": "bool",
    "double": "double",
    "long": "long",
    "Vector2": "Vector2",
    "Vector3": "Vector3",
    "Vector4": "Vector4",
    "Color": "Color",
    "Sprite": "Sprite",
    "Texture2D": "Texture2D",
    "AudioClip": "AudioClip",
    "GameObject": "GameObject",
    "Material": "Material",
    "AnimationClip": "AnimationClip",
}


def _resolve_cs_type(type_str: str) -> str:
    """Resolve a type string to its C# equivalent."""
    return _CS_TYPE_MAP.get(type_str, type_str)


def _to_camel_case(name: str) -> str:
    """Convert a name to _camelCase for private fields."""
    clean = sanitize_cs_identifier(name)
    if not clean:
        return "_field"
    if clean.startswith("_"):
        return clean
    return f"_{clean[0].lower()}{clean[1:]}"


def _to_pascal_case(name: str) -> str:
    """Convert a name to PascalCase for public fields."""
    clean = sanitize_cs_identifier(name)
    if not clean:
        return "Field"
    return f"{clean[0].upper()}{clean[1:]}"


# ---------------------------------------------------------------------------
# DATA-02: ScriptableObject Definition
# ---------------------------------------------------------------------------


def generate_so_definition(
    class_name: str,
    namespace: str = "VeilBreakers.Data",
    fields: list[dict] | None = None,
    summary: str = "",
    menu_name: str = "",
    file_name: str = "",
) -> str:
    """Generate a complete C# ScriptableObject class definition.

    Produces a class that inherits from ScriptableObject with a
    CreateAssetMenu attribute for easy asset creation in Unity's
    Project window.

    Args:
        class_name: Name of the ScriptableObject class.
        namespace: C# namespace (default VeilBreakers.Data).
        fields: List of field dicts with keys: name, type, header,
            tooltip, default, attributes. Public fields use the name
            as-is; prefix with _ for private.
        summary: XML summary comment for the class.
        menu_name: CreateAssetMenu menuName (auto-derived if empty).
        file_name: CreateAssetMenu fileName (auto-derived if empty).

    Returns:
        Complete C# source string.
    """
    safe_class = sanitize_cs_identifier(class_name)
    if not safe_class:
        safe_class = "GeneratedConfig"

    safe_menu = sanitize_cs_string(menu_name or safe_class)
    safe_file = sanitize_cs_string(file_name or safe_class)

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("")

    # Namespace
    safe_ns = _safe_namespace(namespace)
    if safe_ns:
        lines.append(f"namespace {safe_ns}")
        lines.append("{")

    indent = "    " if safe_ns else ""

    # Summary
    if summary:
        lines.append(f"{indent}/// <summary>")
        lines.append(f"{indent}/// {sanitize_cs_string(summary)}")
        lines.append(f"{indent}/// </summary>")

    # CreateAssetMenu attribute
    lines.append(
        f'{indent}[CreateAssetMenu(menuName = "VeilBreakers/{safe_menu}", '
        f'fileName = "{safe_file}")]',
    )
    lines.append(f"{indent}public class {safe_class} : ScriptableObject")
    lines.append(f"{indent}{{")

    # Fields
    if fields:
        current_header = None
        for field in fields:
            fname = field.get("name", "")
            ftype = _resolve_cs_type(field.get("type", "string"))
            header = field.get("header", "")
            tooltip = field.get("tooltip", "")
            default = field.get("default", None)
            extra_attrs = field.get("attributes", [])
            if isinstance(extra_attrs, str):
                extra_attrs = [extra_attrs]

            safe_name = sanitize_cs_identifier(fname)
            if not safe_name:
                continue

            # Header grouping
            if header and header != current_header:
                if current_header is not None:
                    lines.append("")
                lines.append(
                    f'{indent}    [Header("{sanitize_cs_string(header)}")]',
                )
                current_header = header

            # Tooltip
            if tooltip:
                lines.append(
                    f'{indent}    [Tooltip("{sanitize_cs_string(tooltip)}")]',
                )

            # Extra attributes
            for attr in extra_attrs:
                lines.append(f"{indent}    [{sanitize_cs_string(attr)}]")

            # Field declaration
            default_str = ""
            if default is not None:
                if ftype == "string":
                    default_str = f' = "{sanitize_cs_string(str(default))}"'
                elif ftype == "bool":
                    default_str = (
                        f" = {str(default).lower()}"
                        if isinstance(default, bool)
                        else f" = {default}"
                    )
                else:
                    default_str = f" = {default}"

            # Determine access: private fields start with _
            if safe_name.startswith("_"):
                field_case = safe_name
                access = "private"
                lines.append(
                    f"{indent}    [SerializeField]",
                )
                lines.append(
                    f"{indent}    {access} {ftype} {field_case}{default_str};",
                )
            else:
                field_case = safe_name
                access = "public"
                lines.append(
                    f"{indent}    {access} {ftype} {field_case}{default_str};",
                )

    lines.append(f"{indent}}}")

    if safe_ns:
        lines.append("}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# DATA-02: Asset Creation Script
# ---------------------------------------------------------------------------


def generate_asset_creation_script(
    so_class_name: str,
    namespace: str = "VeilBreakers.Data",
    assets: list[dict] | None = None,
    output_folder: str = "Assets/Data",
    category: str = "",
    menu_path: str = "",
) -> str:
    """Generate a C# editor script that instantiates .asset files.

    Uses ScriptableObject.CreateInstance<T>() and AssetDatabase.CreateAsset()
    to create populated .asset files in the project.

    Args:
        so_class_name: The ScriptableObject class name to instantiate.
        namespace: C# namespace of the SO class.
        assets: List of dicts mapping field names to values.
        output_folder: Base output folder for assets.
        category: Subfolder name (e.g. "Items", "Monsters").
        menu_path: MenuItem path (auto-derived if empty).

    Returns:
        Complete C# editor script source string.
    """
    safe_class = sanitize_cs_identifier(so_class_name)
    if not safe_class:
        safe_class = "GeneratedConfig"

    safe_ns = _safe_namespace(namespace)
    safe_category = sanitize_cs_identifier(category) if category else ""
    safe_folder = sanitize_cs_string(output_folder)

    if safe_category:
        asset_folder = f"{safe_folder}/{safe_category}"
    else:
        asset_folder = safe_folder

    safe_menu = sanitize_cs_string(
        menu_path or f"Create {safe_category or safe_class} Configs",
    )
    script_class = f"VeilBreakers_Create{safe_category or safe_class}Configs"

    lines: list[str] = []
    lines.append("using UnityEditor;")
    lines.append("using UnityEngine;")
    lines.append("using System.IO;")
    lines.append("using System.Collections.Generic;")
    if safe_ns:
        lines.append(f"using {safe_ns};")
    lines.append("")
    lines.append(f"public class {script_class}")
    lines.append("{")
    lines.append(
        f'    [MenuItem("VeilBreakers/Data/{safe_menu}")]',
    )
    lines.append("    public static void Execute()")
    lines.append("    {")

    # Ensure output folder exists
    lines.append(f'        string outputFolder = "{sanitize_cs_string(asset_folder)}";')
    lines.append("        if (!AssetDatabase.IsValidFolder(outputFolder))")
    lines.append("        {")
    lines.append("            string[] parts = outputFolder.Split('/');")
    lines.append("            string current = parts[0];")
    lines.append("            for (int i = 1; i < parts.Length; i++)")
    lines.append("            {")
    lines.append("                string next = current + \"/\" + parts[i];")
    lines.append("                if (!AssetDatabase.IsValidFolder(next))")
    lines.append("                    AssetDatabase.CreateFolder(current, parts[i]);")
    lines.append("                current = next;")
    lines.append("            }")
    lines.append("        }")
    lines.append("")

    # Result tracking
    lines.append("        var createdPaths = new List<string>();")
    lines.append("")

    if assets:
        for i, asset_data in enumerate(assets):
            var_name = f"asset{i}"
            lines.append(
                f"        var {var_name} = ScriptableObject.CreateInstance<{safe_class}>();",
            )
            lines.append(
                f'        Undo.RegisterCreatedObjectUndo({var_name}, "Create {safe_class}");',
            )

            # Set fields
            for field_name, field_value in asset_data.items():
                safe_field = sanitize_cs_identifier(field_name)
                if not safe_field:
                    continue
                if isinstance(field_value, str):
                    lines.append(
                        f'        {var_name}.{safe_field} = "{sanitize_cs_string(field_value)}";',
                    )
                elif isinstance(field_value, bool):
                    lines.append(
                        f"        {var_name}.{safe_field} = {str(field_value).lower()};",
                    )
                elif isinstance(field_value, (int, float)):
                    val = f"{field_value}f" if isinstance(field_value, float) else str(field_value)
                    lines.append(f"        {var_name}.{safe_field} = {val};")

            # Determine asset file name from first string field or index
            first_str = None
            for fk, fv in asset_data.items():
                if isinstance(fv, str):
                    first_str = fv
                    break
            asset_file = sanitize_cs_identifier(first_str) if first_str else f"Asset{i}"
            asset_path = f"{asset_folder}/{asset_file}.asset"
            lines.append(
                f'        string path{i} = "{sanitize_cs_string(asset_path)}";',
            )
            lines.append(
                f"        AssetDatabase.CreateAsset({var_name}, path{i});",
            )
            lines.append(f"        createdPaths.Add(path{i});")
            lines.append("")
    else:
        # No pre-defined assets; create a single default
        lines.append(
            f"        var asset = ScriptableObject.CreateInstance<{safe_class}>();",
        )
        lines.append(
            f'        Undo.RegisterCreatedObjectUndo(asset, "Create {safe_class}");',
        )
        lines.append(
            f'        string path = outputFolder + "/New{safe_class}.asset";',
        )
        lines.append("        AssetDatabase.CreateAsset(asset, path);")
        lines.append("        createdPaths.Add(path);")
        lines.append("")

    lines.append("        AssetDatabase.SaveAssets();")
    lines.append("        AssetDatabase.Refresh();")
    lines.append("")

    # Write result JSON
    lines.append("        // Write result for MCP")
    lines.append(
        '        string resultJson = "{ \\"status\\": \\"success\\", '
        '\\"created_count\\": " + createdPaths.Count + ", '
        '\\"created_paths\\": [" + string.Join(", ", '
        'createdPaths.ConvertAll(p => "\\"" + p + "\\"")) + "] }";',
    )
    lines.append(
        "        File.WriteAllText(",
    )
    lines.append(
        '            Path.Combine(Application.dataPath, "../Temp/vb_result.json"),',
    )
    lines.append("            resultJson")
    lines.append("        );")

    lines.append(
        f'        Debug.Log("[VeilBreakers] Created " + createdPaths.Count '
        f'+ " {safe_class} assets");',
    )
    lines.append("    }")
    lines.append("}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# DATA-01: JSON Validator Script
# ---------------------------------------------------------------------------


def generate_json_validator_script(
    config_name: str,
    json_path: str,
    schema: dict | None = None,
    wrapper_class: str = "",
) -> str:
    """Generate a C# editor script that validates JSON configs against a schema.

    Reads a JSON file and checks each record for required fields, type
    correctness, range constraints, and regex pattern matches.

    Args:
        config_name: Name of the config (e.g. "MonsterData").
        json_path: Path relative to Assets/ (e.g. "Resources/Data/monsters.json").
        schema: Dict mapping field names to validation rules:
            {field_name: {type, required, min, max, pattern}}.
        wrapper_class: Wrapper class name for top-level JSON arrays.

    Returns:
        Complete C# editor script source string.
    """
    safe_name = sanitize_cs_identifier(config_name)
    if not safe_name:
        safe_name = "ConfigData"

    safe_path = sanitize_cs_string(json_path)
    # Auto-generate wrapper class name if schema is provided but no wrapper specified
    if wrapper_class:
        safe_wrapper = sanitize_cs_identifier(wrapper_class)
    elif schema:
        safe_wrapper = f"{safe_name}Wrapper"
    else:
        safe_wrapper = ""
    script_class = f"VeilBreakers_Validate{safe_name}"

    lines: list[str] = []
    lines.append("using UnityEditor;")
    lines.append("using UnityEngine;")
    lines.append("using System.IO;")
    lines.append("using System.Collections.Generic;")
    lines.append("using System.Text.RegularExpressions;")
    lines.append("")

    # Validation result struct
    lines.append("[System.Serializable]")
    lines.append("public class VB_ValidationResult")
    lines.append("{")
    lines.append("    public string level;")
    lines.append("    public string message;")
    lines.append("}")
    lines.append("")

    # Wrapper list for JSON serialization
    lines.append("[System.Serializable]")
    lines.append("public class VB_ValidationResultList")
    lines.append("{")
    lines.append("    public List<VB_ValidationResult> results = new List<VB_ValidationResult>();")
    lines.append("}")
    lines.append("")

    if safe_wrapper:
        lines.append("[System.Serializable]")
        lines.append(f"public class {safe_wrapper}")
        lines.append("{")
        lines.append(f"    public List<{safe_name}Entry> items;")
        lines.append("}")
        lines.append("")
        lines.append("[System.Serializable]")
        lines.append(f"public class {safe_name}Entry")
        lines.append("{")
        if schema:
            for field_name, rules in schema.items():
                safe_field = sanitize_cs_identifier(field_name)
                ftype = rules.get("type", "string")
                cs_type = _resolve_cs_type(ftype)
                lines.append(f"    public {cs_type} {safe_field};")
        lines.append("}")
        lines.append("")

    lines.append(f"public class {script_class}")
    lines.append("{")
    lines.append(f'    [MenuItem("VeilBreakers/Data/Validate {sanitize_cs_string(safe_name)}")]')
    lines.append("    public static void Execute()")
    lines.append("    {")
    lines.append("        var results = new List<VB_ValidationResult>();")
    lines.append("")
    lines.append(f'        string filePath = Path.Combine(Application.dataPath, "{safe_path}");')
    lines.append("        if (!File.Exists(filePath))")
    lines.append("        {")
    lines.append('            results.Add(new VB_ValidationResult { level = "ERROR", '
                 'message = "File not found: " + filePath });')
    lines.append("            WriteResults(results);")
    lines.append("            return;")
    lines.append("        }")
    lines.append("")
    lines.append("        string jsonText = File.ReadAllText(filePath);")
    lines.append("")

    if schema:
        if safe_wrapper:
            # Wrap top-level array for JsonUtility
            lines.append('        // Wrap top-level array for JsonUtility')
            lines.append(
                '        string wrappedJson = "{ \\"items\\": " + jsonText + " }";',
            )
            lines.append(
                f"        var data = JsonUtility.FromJson<{safe_wrapper}>(wrappedJson);",
            )
            lines.append("        if (data == null || data.items == null)")
            lines.append("        {")
            lines.append(
                '            results.Add(new VB_ValidationResult { level = "ERROR", '
                'message = "Failed to parse JSON" });',
            )
            lines.append("            WriteResults(results);")
            lines.append("            return;")
            lines.append("        }")
            lines.append("")
            lines.append("        int index = 0;")
            lines.append("        foreach (var entry in data.items)")
            lines.append("        {")

            for field_name, rules in schema.items():
                safe_field = sanitize_cs_identifier(field_name)
                ftype = rules.get("type", "string")
                required = rules.get("required", False)
                min_val = rules.get("min")
                max_val = rules.get("max")
                pattern = rules.get("pattern")

                if required:
                    if ftype == "string":
                        lines.append(
                            f"            if (string.IsNullOrEmpty(entry.{safe_field}))",
                        )
                        lines.append(
                            f'                results.Add(new VB_ValidationResult {{ level = "ERROR", '
                            f'message = $"Item [{{index}}]: {safe_field} is required" }});',
                        )
                    else:
                        lines.append(
                            f"            // {safe_field} is required (non-default check)",
                        )

                if min_val is not None and ftype in ("int", "float", "double", "long"):
                    lines.append(
                        f"            if (entry.{safe_field} < {min_val})",
                    )
                    lines.append(
                        f'                results.Add(new VB_ValidationResult {{ level = "ERROR", '
                        f'message = $"Item [{{index}}]: {safe_field} must be >= {min_val}, got {{entry.{safe_field}}}" }});',
                    )

                if max_val is not None and ftype in ("int", "float", "double", "long"):
                    lines.append(
                        f"            if (entry.{safe_field} > {max_val})",
                    )
                    lines.append(
                        f'                results.Add(new VB_ValidationResult {{ level = "WARNING", '
                        f'message = $"Item [{{index}}]: {safe_field} exceeds {max_val}, got {{entry.{safe_field}}}" }});',
                    )

                if pattern and ftype == "string":
                    # For @"..." verbatim strings, only escape double quotes (as "")
                    verbatim_pattern = pattern.replace('"', '""')
                    # For display in interpolated string, escape backslashes then quotes
                    display_pattern = pattern.replace("\\", "\\\\").replace('"', '\\"')
                    lines.append(
                        f'            if (!string.IsNullOrEmpty(entry.{safe_field}) '
                        f'&& !Regex.IsMatch(entry.{safe_field}, @"{verbatim_pattern}"))',
                    )
                    lines.append(
                        f'                results.Add(new VB_ValidationResult {{ level = "WARNING", '
                        f'message = $"Item [{{index}}]: {safe_field} does not match pattern {display_pattern}" }});',
                    )

            lines.append("            index++;")
            lines.append("        }")
            lines.append("")
            lines.append(
                '        results.Add(new VB_ValidationResult { level = "INFO", '
                'message = $"Validated {data.items.Count} entries, {results.Count} issues found" });',
            )
        else:
            # Direct JSON without wrapper
            lines.append("        // Direct validation (no wrapper)")
            lines.append(
                "        if (string.IsNullOrEmpty(jsonText))",
            )
            lines.append("        {")
            lines.append(
                '            results.Add(new VB_ValidationResult { level = "ERROR", '
                'message = "JSON file is empty" });',
            )
            lines.append("        }")
    else:
        # No schema -- basic structure check
        lines.append("        // No schema provided -- basic structure check")
        lines.append("        if (string.IsNullOrEmpty(jsonText))")
        lines.append("        {")
        lines.append(
            '            results.Add(new VB_ValidationResult { level = "ERROR", '
            'message = "JSON file is empty" });',
        )
        lines.append("        }")
        lines.append("        else")
        lines.append("        {")
        lines.append(
            '            results.Add(new VB_ValidationResult { level = "INFO", '
            'message = "JSON file loaded successfully (" + jsonText.Length + " chars)" });',
        )
        lines.append("        }")

    lines.append("")
    lines.append("        WriteResults(results);")
    lines.append("    }")
    lines.append("")

    # WriteResults helper
    lines.append("    private static void WriteResults(List<VB_ValidationResult> results)")
    lines.append("    {")
    lines.append("        var wrapper = new VB_ValidationResultList();")
    lines.append("        wrapper.results = results;")
    lines.append("        string json = JsonUtility.ToJson(wrapper, true);")
    lines.append(
        "        File.WriteAllText(",
    )
    lines.append(
        '            Path.Combine(Application.dataPath, "../Temp/vb_result.json"),',
    )
    lines.append("            json")
    lines.append("        );")
    lines.append(
        f'        Debug.Log("[VeilBreakers] {safe_name} validation: " + results.Count + " results");',
    )
    lines.append("    }")
    lines.append("}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# DATA-01: JSON Loader Script
# ---------------------------------------------------------------------------


def generate_json_loader_script(
    class_name: str,
    namespace: str = "VeilBreakers.Data",
    fields: list[dict] | None = None,
    json_path: str = "",
    is_array: bool = True,
) -> str:
    """Generate a typed C# data class and JSON loader.

    Creates a serializable data class and a static loader that reads
    from Resources using JsonUtility. Complements (does not replace)
    the existing GameDatabase pattern.

    Args:
        class_name: Data class name (e.g. "MonsterData").
        namespace: C# namespace for the class.
        fields: List of field dicts with keys: name, type.
        json_path: Resources path without extension for Resources.Load.
        is_array: Whether the JSON is a top-level array (needs wrapper).

    Returns:
        Complete C# source string.
    """
    safe_class = sanitize_cs_identifier(class_name)
    if not safe_class:
        safe_class = "GameData"

    safe_ns = _safe_namespace(namespace)
    safe_path = sanitize_cs_string(json_path)

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using System.Collections.Generic;")
    lines.append("")

    if safe_ns:
        lines.append(f"namespace {safe_ns}")
        lines.append("{")

    indent = "    " if safe_ns else ""

    # Data class
    lines.append(f"{indent}[System.Serializable]")
    lines.append(f"{indent}public class {safe_class}")
    lines.append(f"{indent}{{")

    if fields:
        for field in fields:
            fname = sanitize_cs_identifier(field.get("name", ""))
            ftype = _resolve_cs_type(field.get("type", "string"))
            if fname:
                lines.append(f"{indent}    public {ftype} {fname};")

    lines.append(f"{indent}}}")
    lines.append("")

    # Wrapper class for top-level arrays
    if is_array:
        wrapper_name = f"{safe_class}Wrapper"
        lines.append(f"{indent}[System.Serializable]")
        lines.append(f"{indent}public class {wrapper_name}")
        lines.append(f"{indent}{{")
        lines.append(f"{indent}    public List<{safe_class}> items;")
        lines.append(f"{indent}}}")
        lines.append("")

    # Static loader
    lines.append(f"{indent}public static class {safe_class}Loader")
    lines.append(f"{indent}{{")

    if is_array:
        lines.append(
            f"{indent}    public static List<{safe_class}> Load(string resourcePath = "
            f'"{safe_path}")',
        )
        lines.append(f"{indent}    {{")
        lines.append(
            f'{indent}        var textAsset = Resources.Load<TextAsset>(resourcePath);',
        )
        lines.append(f"{indent}        if (textAsset == null)")
        lines.append(f"{indent}        {{")
        lines.append(
            f'{indent}            Debug.LogError("[VeilBreakers] Failed to load: " + resourcePath);',
        )
        lines.append(f"{indent}            return new List<{safe_class}>();")
        lines.append(f"{indent}        }}")
        lines.append("")
        lines.append(
            f'{indent}        string wrappedJson = "{{ \\"items\\": " + textAsset.text + " }}";',
        )
        lines.append(
            f"{indent}        var wrapper = JsonUtility.FromJson<{wrapper_name}>(wrappedJson);",
        )
        lines.append(
            f"{indent}        return wrapper != null && wrapper.items != null "
            f"? wrapper.items : new List<{safe_class}>();",
        )
        lines.append(f"{indent}    }}")
    else:
        lines.append(
            f"{indent}    public static {safe_class} Load(string resourcePath = "
            f'"{safe_path}")',
        )
        lines.append(f"{indent}    {{")
        lines.append(
            f'{indent}        var textAsset = Resources.Load<TextAsset>(resourcePath);',
        )
        lines.append(f"{indent}        if (textAsset == null)")
        lines.append(f"{indent}        {{")
        lines.append(
            f'{indent}            Debug.LogError("[VeilBreakers] Failed to load: " + resourcePath);',
        )
        lines.append(f"{indent}            return null;")
        lines.append(f"{indent}        }}")
        lines.append("")
        lines.append(
            f"{indent}        return JsonUtility.FromJson<{safe_class}>(textAsset.text);",
        )
        lines.append(f"{indent}    }}")

    lines.append(f"{indent}}}")

    if safe_ns:
        lines.append("}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# DATA-03: Localization Setup Script
# ---------------------------------------------------------------------------


def generate_localization_setup_script(
    default_locale: str = "en",
    locales: list[str] | None = None,
    table_name: str = "VeilBreakers_UI",
    output_dir: str = "Assets/Localization",
) -> str:
    """Generate a C# editor script that sets up Unity Localization infrastructure.

    Creates locale assets, string table collections, and output
    directories. Requires the com.unity.localization package.

    Args:
        default_locale: Default locale code (e.g. "en").
        locales: Additional locale codes (e.g. ["es", "fr", "de"]).
        table_name: String table collection name.
        output_dir: Base output directory for localization assets.

    Returns:
        Complete C# editor script source string.
    """
    safe_table = sanitize_cs_string(table_name)
    safe_dir = sanitize_cs_string(output_dir)
    sanitize_cs_string(default_locale)

    all_locales = [default_locale]
    if locales:
        for loc in locales:
            if loc not in all_locales:
                all_locales.append(loc)

    lines: list[str] = []
    lines.append("#if UNITY_EDITOR")
    lines.append("using UnityEditor;")
    lines.append("using UnityEditor.Localization;")
    lines.append("using UnityEngine;")
    lines.append("using UnityEngine.Localization;")
    lines.append("using System.IO;")
    lines.append("using System.Collections.Generic;")
    lines.append("")
    lines.append("public class VeilBreakers_SetupLocalization")
    lines.append("{")
    lines.append('    [MenuItem("VeilBreakers/Data/Setup Localization")]')
    lines.append("    public static void Execute()")
    lines.append("    {")

    # Create output directories
    lines.append(f'        string outputDir = "{safe_dir}";')
    lines.append("        if (!AssetDatabase.IsValidFolder(outputDir))")
    lines.append("        {")
    lines.append("            string[] parts = outputDir.Split('/');")
    lines.append("            string current = parts[0];")
    lines.append("            for (int i = 1; i < parts.Length; i++)")
    lines.append("            {")
    lines.append("                string next = current + \"/\" + parts[i];")
    lines.append("                if (!AssetDatabase.IsValidFolder(next))")
    lines.append("                    AssetDatabase.CreateFolder(current, parts[i]);")
    lines.append("                current = next;")
    lines.append("            }")
    lines.append("        }")
    lines.append("")
    lines.append(
        '        string localesDir = outputDir + "/Locales";',
    )
    lines.append("        if (!AssetDatabase.IsValidFolder(localesDir))")
    lines.append('            AssetDatabase.CreateFolder(outputDir, "Locales");')
    lines.append("")
    lines.append(
        '        string tablesDir = outputDir + "/StringTables";',
    )
    lines.append("        if (!AssetDatabase.IsValidFolder(tablesDir))")
    lines.append('            AssetDatabase.CreateFolder(outputDir, "StringTables");')
    lines.append("")

    # Create locale assets
    lines.append("        var createdLocales = new List<Locale>();")
    for loc in all_locales:
        safe_loc = sanitize_cs_string(loc)
        lines.append(f'        // Create locale: {safe_loc}')
        lines.append("        {")
        lines.append(
            f'            var locale = Locale.CreateLocale(new UnityEngine.Localization.LocaleIdentifier("{safe_loc}"));',
        )
        lines.append(
            f'            string localePath = localesDir + "/{safe_loc}.asset";',
        )
        lines.append(
            "            AssetDatabase.CreateAsset(locale, localePath);",
        )
        lines.append("            createdLocales.Add(locale);")
        lines.append("        }")
        lines.append("")

    # Create string table collection
    lines.append("        // Create string table collection")
    lines.append(
        "        var collection = LocalizationEditorSettings.CreateStringTableCollection(",
    )
    lines.append(f'            "{safe_table}",')
    lines.append("            tablesDir,")
    lines.append("            createdLocales")
    lines.append("        );")
    lines.append("")

    lines.append("        AssetDatabase.SaveAssets();")
    lines.append("        AssetDatabase.Refresh();")
    lines.append("")

    # Write result JSON
    lines.append("        // Write result for MCP")
    lines.append(
        '        string resultJson = "{ \\"status\\": \\"success\\", '
        f'\\"table_name\\": \\"{safe_table}\\", '
        '\\"locale_count\\": " + createdLocales.Count + " }";',
    )
    lines.append("        File.WriteAllText(")
    lines.append(
        '            System.IO.Path.Combine(Application.dataPath, "../Temp/vb_result.json"),',
    )
    lines.append("            resultJson")
    lines.append("        );")
    lines.append(
        f'        Debug.Log("[VeilBreakers] Localization setup complete: '
        f'{safe_table} with " + createdLocales.Count + " locales");',
    )
    lines.append("    }")
    lines.append("}")
    lines.append("#endif")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# DATA-03: Localization Entries Script
# ---------------------------------------------------------------------------


def generate_localization_entries_script(
    table_name: str = "VeilBreakers_UI",
    entries: dict[str, str] | None = None,
    locale: str = "en",
) -> str:
    """Generate a C# editor script that adds string table entries.

    Loads an existing StringTableCollection by name and adds entries
    to the specified locale's string table.

    Args:
        table_name: Name of the existing string table collection.
        entries: Dict mapping localization keys to values.
        locale: Locale code to add entries to.

    Returns:
        Complete C# editor script source string.
    """
    safe_table = sanitize_cs_string(table_name)
    safe_locale = sanitize_cs_string(locale)

    lines: list[str] = []
    lines.append("#if UNITY_EDITOR")
    lines.append("using UnityEditor;")
    lines.append("using UnityEditor.Localization;")
    lines.append("using UnityEngine;")
    lines.append("using UnityEngine.Localization;")
    lines.append("using UnityEngine.Localization.Tables;")
    lines.append("using System.IO;")
    lines.append("using System.Collections.Generic;")
    lines.append("")
    lines.append("public class VeilBreakers_AddLocalizationEntries")
    lines.append("{")
    lines.append(
        '    [MenuItem("VeilBreakers/Data/Add Localization Entries")]',
    )
    lines.append("    public static void Execute()")
    lines.append("    {")
    lines.append("        int added = 0;")
    lines.append("        int skipped = 0;")
    lines.append("        int failed = 0;")
    lines.append("")

    # Find the string table collection
    lines.append("        // Find string table collection")
    lines.append(
        '        var collections = LocalizationEditorSettings.GetStringTableCollections();',
    )
    lines.append("        StringTableCollection targetCollection = null;")
    lines.append("        foreach (var c in collections)")
    lines.append("        {")
    lines.append(f'            if (c.TableCollectionName == "{safe_table}")')
    lines.append("            {")
    lines.append("                targetCollection = c;")
    lines.append("                break;")
    lines.append("            }")
    lines.append("        }")
    lines.append("")
    lines.append("        if (targetCollection == null)")
    lines.append("        {")
    lines.append(
        f'            Debug.LogError("[VeilBreakers] String table collection '
        f"not found: {safe_table}\");",
    )
    lines.append("            return;")
    lines.append("        }")
    lines.append("")

    # Get the locale's string table
    lines.append("        // Get string table for locale")
    lines.append(
        f'        var localeId = new UnityEngine.Localization.LocaleIdentifier("{safe_locale}");',
    )
    lines.append("        var table = targetCollection.GetTable(localeId) as StringTable;")
    lines.append("        if (table == null)")
    lines.append("        {")
    lines.append(
        f'            Debug.LogError("[VeilBreakers] StringTable not found for locale: {safe_locale}");',
    )
    lines.append("            return;")
    lines.append("        }")
    lines.append("")

    # Add entries
    if entries:
        for key, value in entries.items():
            safe_key = sanitize_cs_string(key)
            safe_value = sanitize_cs_string(value)
            lines.append("        try")
            lines.append("        {")
            lines.append(
                f'            var existing = table.GetEntry("{safe_key}");',
            )
            lines.append("            if (existing != null)")
            lines.append("            {")
            lines.append("                skipped++;")
            lines.append("            }")
            lines.append("            else")
            lines.append("            {")
            lines.append(
                f'                table.AddEntry("{safe_key}", "{safe_value}");',
            )
            lines.append("                added++;")
            lines.append("            }")
            lines.append("        }")
            lines.append("        catch (System.Exception e)")
            lines.append("        {")
            lines.append(
                f'            Debug.LogWarning("[VeilBreakers] Failed to add entry '
                f'{safe_key}: " + e.Message);',
            )
            lines.append("            failed++;")
            lines.append("        }")
            lines.append("")

    lines.append("        EditorUtility.SetDirty(table);")
    lines.append("        AssetDatabase.SaveAssets();")
    lines.append("")

    # Write result JSON
    lines.append("        // Write result for MCP")
    lines.append(
        '        string resultJson = "{ \\"status\\": \\"success\\", '
        '\\"added\\": " + added + ", '
        '\\"skipped\\": " + skipped + ", '
        '\\"failed\\": " + failed + " }";',
    )
    lines.append("        File.WriteAllText(")
    lines.append(
        '            System.IO.Path.Combine(Application.dataPath, "../Temp/vb_result.json"),',
    )
    lines.append("            resultJson")
    lines.append("        );")
    lines.append(
        '        Debug.Log($"[VeilBreakers] Localization entries: {added} added, '
        '{skipped} skipped, {failed} failed");',
    )
    lines.append("    }")
    lines.append("}")
    lines.append("#endif")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# DATA-04: Data Authoring EditorWindow
# ---------------------------------------------------------------------------


def generate_data_authoring_window(
    window_name: str,
    so_class_name: str,
    namespace: str = "VeilBreakers.Data",
    fields: list[dict] | None = None,
    menu_path: str = "",
    data_folder: str = "Assets/Data",
    category: str = "",
) -> str:
    """Generate a custom EditorWindow for batch-creating and editing SO assets.

    Creates an IMGUI-based EditorWindow that lists existing assets of the
    given ScriptableObject type, allows creating new ones, and provides
    inline editing with save support.

    Args:
        window_name: EditorWindow class name (e.g. "ItemDatabaseEditor").
        so_class_name: The ScriptableObject class to author.
        namespace: C# namespace of the SO class.
        fields: List of field dicts with keys: name, type, label.
        menu_path: MenuItem path (auto-derived if empty).
        data_folder: Base folder for asset storage.
        category: Subfolder within data_folder.

    Returns:
        Complete C# editor script source string.
    """
    safe_window = sanitize_cs_identifier(window_name)
    if not safe_window:
        safe_window = "DataEditorWindow"

    safe_so = sanitize_cs_identifier(so_class_name)
    if not safe_so:
        safe_so = "GameConfig"

    safe_ns = _safe_namespace(namespace)
    safe_category = sanitize_cs_identifier(category) if category else ""
    safe_folder = sanitize_cs_string(data_folder)
    safe_menu = sanitize_cs_string(menu_path or safe_window)

    if safe_category:
        asset_folder = f"{safe_folder}/{safe_category}"
    else:
        asset_folder = safe_folder

    lines: list[str] = []
    lines.append("using UnityEditor;")
    lines.append("using UnityEngine;")
    lines.append("using System.Collections.Generic;")
    lines.append("using System.IO;")
    if safe_ns:
        lines.append(f"using {safe_ns};")
    lines.append("")
    lines.append(f"public class {safe_window} : EditorWindow")
    lines.append("{")

    # Fields for window state
    lines.append(f"    private List<{safe_so}> _assets = new List<{safe_so}>();")
    lines.append("    private Vector2 _scrollPosition;")
    lines.append("    private bool _showCreateSection = true;")
    lines.append("")

    # New asset fields for creation
    if fields:
        for field in fields:
            fname = sanitize_cs_identifier(field.get("name", ""))
            ftype = _resolve_cs_type(field.get("type", "string"))
            if fname:
                lines.append(f"    private {ftype} _new{_to_pascal_case(fname)};")
        lines.append("")

    # MenuItem
    lines.append(
        f'    [MenuItem("VeilBreakers/Tools/{safe_menu}")]',
    )
    lines.append("    public static void ShowWindow()")
    lines.append("    {")
    lines.append(
        f'        GetWindow<{safe_window}>("{sanitize_cs_string(safe_window)}");',
    )
    lines.append("    }")
    lines.append("")

    # OnEnable - load assets
    lines.append("    private void OnEnable()")
    lines.append("    {")
    lines.append("        RefreshAssets();")
    lines.append("    }")
    lines.append("")

    # RefreshAssets
    lines.append("    private void RefreshAssets()")
    lines.append("    {")
    lines.append("        _assets.Clear();")
    lines.append(
        f'        string[] guids = AssetDatabase.FindAssets("t:{safe_so}");',
    )
    lines.append("        foreach (string guid in guids)")
    lines.append("        {")
    lines.append("            string path = AssetDatabase.GUIDToAssetPath(guid);")
    lines.append(
        f"            var asset = AssetDatabase.LoadAssetAtPath<{safe_so}>(path);",
    )
    lines.append("            if (asset != null)")
    lines.append("                _assets.Add(asset);")
    lines.append("        }")
    lines.append("    }")
    lines.append("")

    # OnGUI
    lines.append("    private void OnGUI()")
    lines.append("    {")
    lines.append(
        f'        GUILayout.Label("{sanitize_cs_string(safe_window)}", EditorStyles.boldLabel);',
    )
    lines.append("        EditorGUILayout.Space();")
    lines.append("")

    # Create section
    lines.append('        _showCreateSection = EditorGUILayout.Foldout(_showCreateSection, "Create New Asset");')
    lines.append("        if (_showCreateSection)")
    lines.append("        {")
    lines.append("            EditorGUI.indentLevel++;")

    if fields:
        for field in fields:
            fname = sanitize_cs_identifier(field.get("name", ""))
            ftype = _resolve_cs_type(field.get("type", "string"))
            label = field.get("label", fname)
            safe_label = sanitize_cs_string(label)
            if not fname:
                continue

            pname = f"_new{_to_pascal_case(fname)}"
            if ftype == "string":
                lines.append(
                    f'            {pname} = EditorGUILayout.TextField("{safe_label}", {pname});',
                )
            elif ftype == "int":
                lines.append(
                    f'            {pname} = EditorGUILayout.IntField("{safe_label}", {pname});',
                )
            elif ftype == "float":
                lines.append(
                    f'            {pname} = EditorGUILayout.FloatField("{safe_label}", {pname});',
                )
            elif ftype == "bool":
                lines.append(
                    f'            {pname} = EditorGUILayout.Toggle("{safe_label}", {pname});',
                )
            elif ftype == "Vector2":
                lines.append(
                    f'            {pname} = EditorGUILayout.Vector2Field("{safe_label}", {pname});',
                )
            elif ftype == "Vector3":
                lines.append(
                    f'            {pname} = EditorGUILayout.Vector3Field("{safe_label}", {pname});',
                )
            elif ftype == "Vector4":
                lines.append(
                    f'            {pname} = EditorGUILayout.Vector4Field("{safe_label}", {pname});',
                )
            elif ftype == "Color":
                lines.append(
                    f'            {pname} = EditorGUILayout.ColorField("{safe_label}", {pname});',
                )
            elif ftype == "Rect":
                lines.append(
                    f'            {pname} = EditorGUILayout.RectField("{safe_label}", {pname});',
                )
            else:
                lines.append(
                    f'            {pname} = ({ftype})EditorGUILayout.ObjectField("{safe_label}", '
                    f"{pname}, typeof({ftype}), false);",
                )

    lines.append("")
    lines.append(
        '            if (GUILayout.Button("Create Asset"))',
    )
    lines.append("            {")
    lines.append("                CreateNewAsset();")
    lines.append("            }")
    lines.append("            EditorGUI.indentLevel--;")
    lines.append("        }")
    lines.append("")

    # Existing assets section
    lines.append("        EditorGUILayout.Space();")
    lines.append(
        '        GUILayout.Label("Existing Assets (" + _assets.Count + ")", EditorStyles.boldLabel);',
    )
    lines.append("")
    lines.append("        if (GUILayout.Button(\"Refresh\"))")
    lines.append("            RefreshAssets();")
    lines.append("")
    lines.append("        _scrollPosition = EditorGUILayout.BeginScrollView(_scrollPosition);")
    lines.append("")
    lines.append(f"        {safe_so} toDelete = null;")
    lines.append("        foreach (var asset in _assets)")
    lines.append("        {")
    lines.append("            EditorGUILayout.BeginHorizontal();")
    lines.append(
        "            EditorGUILayout.ObjectField(asset, typeof("
        f"{safe_so}), false);",
    )
    lines.append("")
    lines.append("            // Inline editing via SerializedObject")
    lines.append("            var so = new SerializedObject(asset);")
    lines.append("            so.Update();")

    if fields:
        for field in fields:
            fname = sanitize_cs_identifier(field.get("name", ""))
            if fname:
                lines.append(
                    f'            EditorGUILayout.PropertyField(so.FindProperty("{fname}"));',
                )

    lines.append("            if (so.hasModifiedProperties)")
    lines.append("            {")
    lines.append("                so.ApplyModifiedProperties();")
    lines.append("                EditorUtility.SetDirty(asset);")
    lines.append("            }")
    lines.append("")
    lines.append(
        '            if (GUILayout.Button("Delete", GUILayout.Width(60)))',
    )
    lines.append("                toDelete = asset;")
    lines.append("")
    lines.append("            EditorGUILayout.EndHorizontal();")
    lines.append("        }")
    lines.append("")
    lines.append("        EditorGUILayout.EndScrollView();")
    lines.append("")

    # Handle deletion
    lines.append("        if (toDelete != null)")
    lines.append("        {")
    lines.append("            string deletePath = AssetDatabase.GetAssetPath(toDelete);")
    lines.append(
        '            if (EditorUtility.DisplayDialog("Delete Asset", '
        '"Delete " + deletePath + "?", "Delete", "Cancel"))',
    )
    lines.append("            {")
    lines.append("                AssetDatabase.DeleteAsset(deletePath);")
    lines.append("                RefreshAssets();")
    lines.append("            }")
    lines.append("        }")
    lines.append("")

    # Save all
    lines.append(
        '        if (GUILayout.Button("Save All Changes"))',
    )
    lines.append("        {")
    lines.append("            AssetDatabase.SaveAssets();")
    lines.append("        }")
    lines.append("    }")
    lines.append("")

    # CreateNewAsset method
    lines.append("    private void CreateNewAsset()")
    lines.append("    {")
    lines.append(
        f'        string folder = "{sanitize_cs_string(asset_folder)}";',
    )
    lines.append("        if (!AssetDatabase.IsValidFolder(folder))")
    lines.append("        {")
    lines.append("            string[] parts = folder.Split('/');")
    lines.append("            string current = parts[0];")
    lines.append("            for (int i = 1; i < parts.Length; i++)")
    lines.append("            {")
    lines.append("                string next = current + \"/\" + parts[i];")
    lines.append("                if (!AssetDatabase.IsValidFolder(next))")
    lines.append("                    AssetDatabase.CreateFolder(current, parts[i]);")
    lines.append("                current = next;")
    lines.append("            }")
    lines.append("        }")
    lines.append("")
    lines.append(
        f"        var asset = ScriptableObject.CreateInstance<{safe_so}>();",
    )

    if fields:
        for field in fields:
            fname = sanitize_cs_identifier(field.get("name", ""))
            if fname:
                pname = f"_new{_to_pascal_case(fname)}"
                lines.append(f"        asset.{fname} = {pname};")

    lines.append("")

    # Use a name field if available, otherwise use timestamp
    name_field = None
    if fields:
        for field in fields:
            if field.get("type", "") == "string":
                name_field = sanitize_cs_identifier(field.get("name", ""))
                break

    if name_field:
        lines.append(
            f'        string assetName = string.IsNullOrEmpty(_new{_to_pascal_case(name_field)}) '
            f'? "New{safe_so}" : _new{_to_pascal_case(name_field)};',
        )
    else:
        lines.append(
            f'        string assetName = "New{safe_so}_" + System.DateTime.Now.Ticks;',
        )

    lines.append(
        '        string assetPath = folder + "/" + assetName + ".asset";',
    )
    lines.append("        AssetDatabase.CreateAsset(asset, assetPath);")
    lines.append("        AssetDatabase.SaveAssets();")
    lines.append("        RefreshAssets();")
    lines.append(
        f'        Debug.Log("[VeilBreakers] Created {safe_so} at " + assetPath);',
    )
    lines.append("    }")
    lines.append("}")

    return "\n".join(lines) + "\n"
