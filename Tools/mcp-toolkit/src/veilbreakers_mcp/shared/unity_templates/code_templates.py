"""C# code generation engine for arbitrary class types, script modification, and editor tool templates.

Exports:
    generate_class         -- Generate any C# class type (MonoBehaviour, ScriptableObject, class, static class, abstract class, interface, enum, struct)
    modify_script          -- Modify existing C# source by inserting usings, fields, properties, methods, attributes
    generate_editor_window -- Generate EditorWindow scaffolding with MenuItem and OnGUI/CreateGUI
    generate_property_drawer -- Generate CustomPropertyDrawer with OnGUI and GetPropertyHeight
    generate_inspector_drawer -- Generate CustomEditor with OnInspectorGUI
    generate_scene_overlay -- Generate SceneView Overlay with CreatePanelContent
    _build_cs_class        -- Low-level section-based class builder (also exported for advanced use)
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Sanitization helpers (local copies per established codebase pattern)
# ---------------------------------------------------------------------------


def _sanitize_cs_string(value: str) -> str:
    """Escape a value for safe embedding inside a C# string literal.

    Prevents C# code injection by escaping backslashes, quotes, and
    newlines.

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
# C# reserved words
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


def _safe_identifier(name: str) -> str:
    """Sanitize a name for use as a C# identifier.

    Strips invalid characters, prefixes with ``@`` if the result is a
    reserved word, and rejects empty results.

    Args:
        name: Raw identifier string.

    Returns:
        Safe C# identifier.

    Raises:
        ValueError: If the sanitized result is empty.
    """
    result = _sanitize_cs_identifier(name)
    if not result:
        raise ValueError(f"Identifier is empty after sanitization: {name!r}")
    if result in _CS_RESERVED:
        result = f"@{result}"
    return result


# ---------------------------------------------------------------------------
# Internal: field / property / method formatting helpers
# ---------------------------------------------------------------------------


def _format_field(field: dict, indent: str) -> list[str]:
    """Format a single field declaration.

    Args:
        field: Dict with keys: access, type, name, default (optional),
               attributes (optional), summary (optional).
        indent: Indentation string for the field.

    Returns:
        List of lines for the field declaration.
    """
    lines: list[str] = []
    access = field.get("access", "private")
    ftype = field.get("type", "int")
    raw_name = field.get("name", "value")
    default = field.get("default", "")
    attrs = field.get("attributes", [])
    summary = field.get("summary", "")

    safe_name = _safe_identifier(raw_name)
    # VeilBreakers convention: private fields use _camelCase
    if access == "private" and not safe_name.startswith("_") and not safe_name.startswith("@"):
        safe_name = f"_{safe_name[0].lower()}{safe_name[1:]}" if len(safe_name) > 1 else f"_{safe_name.lower()}"

    if summary:
        lines.append(f"{indent}/// <summary>{_sanitize_cs_string(summary)}</summary>")

    for attr in attrs:
        lines.append(f"{indent}[{attr}]")

    decl = f"{indent}{access} {ftype} {safe_name}"
    if default:
        decl += f" = {default}"
    decl += ";"
    lines.append(decl)
    return lines


def _format_property(prop: dict, indent: str) -> list[str]:
    """Format a single property declaration.

    Args:
        prop: Dict with keys: access, type, name, getter (optional),
              setter (optional), backing_field (optional), summary (optional).
        indent: Indentation string.

    Returns:
        List of lines for the property.
    """
    lines: list[str] = []
    access = prop.get("access", "public")
    ptype = prop.get("type", "int")
    raw_name = prop.get("name", "Value")
    getter = prop.get("getter", "")
    setter = prop.get("setter", "")
    summary = prop.get("summary", "")

    safe_name = _safe_identifier(raw_name)

    if summary:
        lines.append(f"{indent}/// <summary>{_sanitize_cs_string(summary)}</summary>")

    if getter or setter:
        # Custom getter/setter
        lines.append(f"{indent}{access} {ptype} {safe_name}")
        lines.append(f"{indent}{{")
        if getter:
            lines.append(f"{indent}    get {{ {getter} }}")
        else:
            lines.append(f"{indent}    get;")
        if setter:
            lines.append(f"{indent}    set {{ {setter} }}")
        else:
            lines.append(f"{indent}    set;")
        lines.append(f"{indent}}}")
    else:
        # Auto-property
        lines.append(f"{indent}{access} {ptype} {safe_name} {{ get; set; }}")

    return lines


def _format_method(method: dict, indent: str, is_interface: bool = False) -> list[str]:
    """Format a single method declaration.

    Args:
        method: Dict with keys: access, return_type, name, params (optional),
                body (optional), attributes (optional), summary (optional).
        indent: Indentation string.
        is_interface: If True, emit signature only (no body).

    Returns:
        List of lines for the method.
    """
    lines: list[str] = []
    access = method.get("access", "public")
    ret_type = method.get("return_type", "void")
    raw_name = method.get("name", "DoSomething")
    params = method.get("params", "")
    body = method.get("body", "")
    attrs = method.get("attributes", [])
    summary = method.get("summary", "")

    safe_name = _safe_identifier(raw_name)

    if summary:
        lines.append(f"{indent}/// <summary>{_sanitize_cs_string(summary)}</summary>")

    for attr in attrs:
        lines.append(f"{indent}[{attr}]")

    if is_interface:
        lines.append(f"{indent}{ret_type} {safe_name}({params});")
    else:
        lines.append(f"{indent}{access} {ret_type} {safe_name}({params})")
        lines.append(f"{indent}{{")
        if body:
            for bline in body.split("\n"):
                lines.append(f"{indent}    {bline}")
        else:
            if ret_type != "void":
                lines.append(f"{indent}    throw new System.NotImplementedException();")
        lines.append(f"{indent}}}")

    return lines


# ---------------------------------------------------------------------------
# CODE-01: Core class builder
# ---------------------------------------------------------------------------


def _build_cs_class(
    class_name: str,
    class_type: str = "class",
    namespace: str = "",
    base_class: str = "",
    interfaces: list[str] | None = None,
    usings: list[str] | None = None,
    attributes: list[str] | None = None,
    fields: list[dict] | None = None,
    properties: list[dict] | None = None,
    methods: list[dict] | None = None,
    enum_values: list[str] | None = None,
    summary: str = "",
) -> str:
    """Build a complete C# source file from structured sections.

    This is the low-level builder. For most use cases, prefer
    :func:`generate_class` which maps high-level class types
    (MonoBehaviour, ScriptableObject, etc.) to appropriate defaults.

    Args:
        class_name: Name of the class/struct/interface/enum.
        class_type: One of "class", "static class", "abstract class",
                    "struct", "interface", "enum".
        namespace: Optional namespace wrapper.
        base_class: Optional base class to inherit from.
        interfaces: Optional list of interface names to implement.
        usings: Using statements (without ``using`` prefix or semicolon).
        attributes: Class-level attributes (without brackets).
        fields: List of field dicts (see :func:`_format_field`).
        properties: List of property dicts (see :func:`_format_property`).
        methods: List of method dicts (see :func:`_format_method`).
        enum_values: List of enum member names (only for enum class_type).
        summary: Optional XML summary comment for the class.

    Returns:
        Complete C# source string.
    """
    lines: list[str] = []

    # 1. Using statements
    using_list = usings if usings is not None else []
    for u in using_list:
        lines.append(f"using {u};")
    if using_list:
        lines.append("")

    # 2. Namespace open
    indent = ""
    if namespace:
        lines.append(f"namespace {namespace}")
        lines.append("{")
        indent = "    "

    # 3. XML summary comment
    if summary:
        lines.append(f"{indent}/// <summary>")
        lines.append(f"{indent}/// {_sanitize_cs_string(summary)}")
        lines.append(f"{indent}/// </summary>")

    # 4. Class attributes
    for attr in (attributes or []):
        lines.append(f"{indent}[{attr}]")

    # 5. Class declaration with inheritance
    decl = f"{indent}public {class_type} {class_name}"
    inheritance: list[str] = []
    if base_class:
        inheritance.append(base_class)
    if interfaces:
        inheritance.extend(interfaces)
    if inheritance:
        decl += " : " + ", ".join(inheritance)
    lines.append(decl)
    lines.append(f"{indent}{{")

    body_indent = indent + "    "
    is_interface = class_type == "interface"

    # 6. Enum values
    if class_type == "enum" and enum_values:
        for i, val in enumerate(enum_values):
            safe_val = _safe_identifier(val)
            suffix = "," if i < len(enum_values) - 1 else ""
            lines.append(f"{body_indent}{safe_val}{suffix}")
    else:
        # 7. Fields
        if fields:
            for field in fields:
                lines.extend(_format_field(field, body_indent))
            lines.append("")

        # 8. Properties
        if properties:
            for prop in properties:
                lines.extend(_format_property(prop, body_indent))
            lines.append("")

        # 9. Methods
        if methods:
            for i, method in enumerate(methods):
                lines.extend(_format_method(method, body_indent, is_interface=is_interface))
                if i < len(methods) - 1:
                    lines.append("")

    # 10. Close braces
    lines.append(f"{indent}}}")
    if namespace:
        lines.append("}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CODE-01: Public wrapper
# ---------------------------------------------------------------------------


def generate_class(
    class_name: str,
    class_type: str = "MonoBehaviour",
    namespace: str = "",
    usings: list[str] | None = None,
    base_class: str = "",
    interfaces: list[str] | None = None,
    attributes: list[str] | None = None,
    fields: list[dict] | None = None,
    properties: list[dict] | None = None,
    methods: list[dict] | None = None,
    enum_values: list[str] | None = None,
    summary: str = "",
) -> str:
    """Generate a complete C# class source file.

    Maps high-level class types to appropriate base classes and using
    statements. Sanitizes all identifiers.

    Args:
        class_name: Name of the class.
        class_type: One of "MonoBehaviour", "ScriptableObject", "class",
                    "static class", "abstract class", "interface", "enum",
                    "struct".
        namespace: Optional namespace.
        usings: Additional using statements (merged with defaults).
        base_class: Explicit base class override.
        interfaces: Interfaces to implement.
        attributes: Class-level attributes.
        fields: Field definitions.
        properties: Property definitions.
        methods: Method definitions.
        enum_values: Enum member names (only for enum type).
        summary: XML summary comment.

    Returns:
        Complete C# source string.
    """
    safe_name = _safe_identifier(class_name)
    extra_usings = list(usings) if usings else []

    # Map high-level class_type to _build_cs_class parameters
    if class_type == "MonoBehaviour":
        resolved_base = base_class or "MonoBehaviour"
        default_usings = ["UnityEngine"]
        build_type = "class"
    elif class_type == "ScriptableObject":
        resolved_base = base_class or "ScriptableObject"
        default_usings = ["UnityEngine"]
        # Add CreateAssetMenu attribute if not already present
        attrs = list(attributes) if attributes else []
        has_cam = any("CreateAssetMenu" in a for a in attrs)
        if not has_cam:
            menu_name = _sanitize_cs_string(safe_name)
            attrs.insert(0, f'CreateAssetMenu(menuName = "VeilBreakers/{menu_name}", fileName = "{menu_name}")')
        attributes = attrs
        build_type = "class"
    elif class_type in ("class", "static class", "abstract class", "struct"):
        resolved_base = base_class
        default_usings = []
        build_type = class_type
    elif class_type == "interface":
        resolved_base = ""
        default_usings = []
        build_type = "interface"
    elif class_type == "enum":
        resolved_base = ""
        default_usings = []
        build_type = "enum"
    else:
        # Unknown type -- treat as plain class
        resolved_base = base_class
        default_usings = []
        build_type = "class"

    # Merge usings (defaults + extras, deduplicated, ordered)
    merged_usings: list[str] = []
    seen: set[str] = set()
    for u in default_usings + extra_usings:
        if u not in seen:
            merged_usings.append(u)
            seen.add(u)

    # Sanitize field/property/method names
    safe_fields = _sanitize_member_list(fields) if fields else None
    safe_properties = _sanitize_member_list(properties) if properties else None
    safe_methods = _sanitize_member_list(methods) if methods else None

    return _build_cs_class(
        class_name=safe_name,
        class_type=build_type,
        namespace=namespace,
        base_class=resolved_base,
        interfaces=interfaces,
        usings=merged_usings,
        attributes=attributes,
        fields=safe_fields,
        properties=safe_properties,
        methods=safe_methods,
        enum_values=enum_values,
        summary=summary,
    )


def _sanitize_member_list(members: list[dict]) -> list[dict]:
    """Sanitize names in a list of member dicts (fields, properties, methods)."""
    result = []
    for m in members:
        clean = dict(m)
        if "name" in clean:
            clean["name"] = _sanitize_cs_identifier(clean["name"])
        result.append(clean)
    return result


# ---------------------------------------------------------------------------
# CODE-02: Script modification
# ---------------------------------------------------------------------------


def modify_script(
    source: str,
    add_usings: list[str] | None = None,
    add_fields: list[dict] | None = None,
    add_properties: list[dict] | None = None,
    add_methods: list[dict] | None = None,
    add_attributes: list[dict] | None = None,
) -> tuple[str, list[str]]:
    """Modify existing C# source by inserting code at correct locations.

    This function is non-destructive: it only adds code, never removes
    or replaces existing code.

    Args:
        source: Existing C# source code string.
        add_usings: Using statements to add (e.g. ``["System.Linq"]``).
        add_fields: Field dicts to insert (see :func:`_format_field`).
        add_properties: Property dicts to insert.
        add_methods: Method dicts to insert.
        add_attributes: Attribute dicts with ``target_class`` and ``attribute`` keys.

    Returns:
        Tuple of (modified_source, list_of_changes_made).

    Raises:
        ValueError: If the modified source has unbalanced braces.
    """
    changes: list[str] = []
    result = source

    if not any([add_usings, add_fields, add_properties, add_methods, add_attributes]):
        return result, changes

    # Detect indentation style
    indent_str = _detect_indent(result)
    body_indent = indent_str * 2  # class body is typically 2 levels deep if namespaced

    # Detect if file has namespace (1 level) or not (0 levels)
    has_namespace = bool(re.search(r"^\s*namespace\s+", result, re.MULTILINE))
    if has_namespace:
        body_indent = indent_str * 2
    else:
        body_indent = indent_str

    # 1. Add usings
    if add_usings:
        for using in add_usings:
            using_line = f"using {using};"
            if using_line in result:
                continue  # Skip duplicates
            # Find last using statement
            last_using_match = None
            for m in re.finditer(r"^using\s+[^;]+;\s*$", result, re.MULTILINE):
                last_using_match = m
            if last_using_match:
                insert_pos = last_using_match.end()
                result = result[:insert_pos] + "\n" + using_line + result[insert_pos:]
            else:
                # No existing usings -- add at top
                result = using_line + "\n" + result
            changes.append(f"Added using {using}")

    # 2. Add attributes to class declarations
    if add_attributes:
        for attr_spec in add_attributes:
            target_class = attr_spec.get("target_class", "")
            attribute = attr_spec.get("attribute", "")
            if not target_class or not attribute:
                continue
            # Find class declaration line
            class_pattern = re.compile(
                rf"^(\s*)(public|internal|private|protected)?\s*(sealed\s+|abstract\s+|static\s+)*(class|struct|interface)\s+{re.escape(target_class)}\b",
                re.MULTILINE,
            )
            match = class_pattern.search(result)
            if match:
                class_indent = match.group(1) or ""
                attr_line = f"{class_indent}[{attribute}]\n"
                result = result[:match.start()] + attr_line + result[match.start():]
                changes.append(f"Added [{attribute}] to {target_class}")

    # 3. Add fields
    if add_fields:
        for field in add_fields:
            field_lines = _format_field(field, body_indent)
            field_text = "\n".join(field_lines)
            # Insert after the opening brace of the class
            result = _insert_after_class_open(result, field_text)
            field_name = field.get("name", "unknown")
            changes.append(f"Added field {field_name}")

    # 4. Add properties
    if add_properties:
        for prop in add_properties:
            prop_lines = _format_property(prop, body_indent)
            prop_text = "\n".join(prop_lines)
            # Insert before the last closing brace of the class
            result = _insert_before_class_close(result, prop_text)
            prop_name = prop.get("name", "unknown")
            changes.append(f"Added property {prop_name}")

    # 5. Add methods
    if add_methods:
        for method in add_methods:
            method_lines = _format_method(method, body_indent)
            method_text = "\n".join(method_lines)
            # Insert before the last closing brace of the class
            result = _insert_before_class_close(result, method_text)
            method_name = method.get("name", "unknown")
            changes.append(f"Added method {method_name}")

    # 6. Validate balanced braces
    open_count = result.count("{")
    close_count = result.count("}")
    if open_count != close_count:
        raise ValueError(
            f"Unbalanced braces after modification: {{ = {open_count}, }} = {close_count}"
        )

    return result, changes


def _detect_indent(source: str) -> str:
    """Detect the indentation style used in a C# source file.

    Returns the detected indent unit string (e.g. "    " for 4-space,
    "\\t" for tabs).
    """
    # Check for tabs first
    if re.search(r"^\t", source, re.MULTILINE):
        return "\t"

    # Look for leading spaces on indented lines
    indent_counts: dict[int, int] = {}
    for line in source.split("\n"):
        stripped = line.lstrip(" ")
        if stripped and stripped != line:
            spaces = len(line) - len(stripped)
            if spaces > 0:
                indent_counts[spaces] = indent_counts.get(spaces, 0) + 1

    if indent_counts:
        # Find the minimum non-zero indent that appears frequently
        min_indent = min(indent_counts.keys())
        return " " * min_indent

    # Default to 4 spaces
    return "    "


def _insert_after_class_open(source: str, code_to_insert: str) -> str:
    """Insert code after the opening brace of the first class/struct body."""
    # Find class/struct declaration followed by {
    match = re.search(
        r"((?:public|internal|private|protected)\s+(?:sealed\s+|abstract\s+|static\s+)*(?:class|struct|interface)\s+\w+[^{]*\{)",
        source,
        re.MULTILINE,
    )
    if match:
        insert_pos = match.end()
        return source[:insert_pos] + "\n" + code_to_insert + source[insert_pos:]
    return source


def _insert_before_class_close(source: str, code_to_insert: str) -> str:
    """Insert code before the closing brace of the outermost class body.

    For namespaced files, the class close is the second-to-last ``}``.
    For non-namespaced files, it is the last ``}``.
    """
    # Find all closing brace positions
    close_positions: list[int] = []
    for m in re.finditer(r"^\s*\}\s*$", source, re.MULTILINE):
        close_positions.append(m.start())

    has_namespace = bool(re.search(r"^\s*namespace\s+", source, re.MULTILINE))

    if has_namespace and len(close_positions) >= 2:
        # Insert before the second-to-last closing brace
        insert_pos = close_positions[-2]
    elif close_positions:
        # Insert before the last closing brace
        insert_pos = close_positions[-1]
    else:
        # Fallback: append at end
        return source + "\n" + code_to_insert

    return source[:insert_pos] + code_to_insert + "\n" + source[insert_pos:]


# ---------------------------------------------------------------------------
# CODE-03: Editor tool generators
# ---------------------------------------------------------------------------


def generate_editor_window(
    window_name: str,
    menu_path: str,
    namespace: str = "VeilBreakers.Editor",
    fields: list[dict] | None = None,
    on_gui_body: str = "",
    use_ui_toolkit: bool = False,
) -> str:
    """Generate an EditorWindow C# script.

    Args:
        window_name: Name of the EditorWindow class.
        menu_path: MenuItem path (e.g. "VeilBreakers/Tools/Debug").
        namespace: Namespace for the window class.
        fields: Optional list of field dicts for serialized state.
        on_gui_body: Custom OnGUI body code. If empty, generates a default.
        use_ui_toolkit: If True, generate CreateGUI instead of OnGUI.

    Returns:
        Complete C# source string.
    """
    safe_name = _safe_identifier(window_name)
    safe_menu = _sanitize_cs_string(menu_path)

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    if use_ui_toolkit:
        lines.append("using UnityEngine.UIElements;")
    lines.append("")

    indent = ""
    if namespace:
        lines.append(f"namespace {namespace}")
        lines.append("{")
        indent = "    "

    body_indent = indent + "    "
    body_indent2 = body_indent + "    "

    lines.append(f"{indent}public class {safe_name} : EditorWindow")
    lines.append(f"{indent}{{")

    # Serialized fields
    if fields:
        for field in fields:
            field_lines = _format_field(field, body_indent)
            lines.extend(field_lines)
        lines.append("")

    # MenuItem + Show method
    lines.append(f'{body_indent}[MenuItem("{safe_menu}")]')
    lines.append(f"{body_indent}public static void ShowWindow()")
    lines.append(f"{body_indent}{{")
    lines.append(f'{body_indent2}var window = GetWindow<{safe_name}>();')
    lines.append(f'{body_indent2}window.titleContent = new GUIContent("{safe_name}");')
    lines.append(f"{body_indent2}window.Show();")
    lines.append(f"{body_indent}}}")
    lines.append("")

    if use_ui_toolkit:
        # CreateGUI approach
        lines.append(f"{body_indent}public void CreateGUI()")
        lines.append(f"{body_indent}{{")
        lines.append(f"{body_indent2}var root = rootVisualElement;")
        lines.append(f'{body_indent2}root.Add(new Label("{safe_name}"));')
        if on_gui_body:
            for bline in on_gui_body.split("\n"):
                lines.append(f"{body_indent2}{bline}")
        lines.append(f"{body_indent}}}")
    else:
        # OnGUI approach (IMGUI -- default per CONTEXT.md)
        lines.append(f"{body_indent}private void OnGUI()")
        lines.append(f"{body_indent}{{")
        if on_gui_body:
            for bline in on_gui_body.split("\n"):
                lines.append(f"{body_indent2}{bline}")
        else:
            lines.append(f'{body_indent2}GUILayout.Label("{safe_name}", EditorStyles.boldLabel);')
        lines.append(f"{body_indent}}}")

    lines.append(f"{indent}}}")
    if namespace:
        lines.append("}")

    return "\n".join(lines) + "\n"


def generate_property_drawer(
    target_type: str,
    namespace: str = "VeilBreakers.Editor",
    drawer_body: str = "",
) -> str:
    """Generate a CustomPropertyDrawer C# script.

    Args:
        target_type: The type this drawer handles (e.g. "HealthRange").
        menu_path: Not used; kept for consistency.
        namespace: Namespace for the drawer class.
        drawer_body: Custom OnGUI body code for the drawer.

    Returns:
        Complete C# source string.
    """
    safe_type = _safe_identifier(target_type)
    drawer_name = f"{safe_type}Drawer"

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("")

    indent = ""
    if namespace:
        lines.append(f"namespace {namespace}")
        lines.append("{")
        indent = "    "

    body_indent = indent + "    "
    body_indent2 = body_indent + "    "

    lines.append(f"{indent}[CustomPropertyDrawer(typeof({safe_type}))]")
    lines.append(f"{indent}public class {drawer_name} : PropertyDrawer")
    lines.append(f"{indent}{{")

    # OnGUI
    lines.append(f"{body_indent}public override void OnGUI(Rect position, SerializedProperty property, GUIContent label)")
    lines.append(f"{body_indent}{{")
    lines.append(f"{body_indent2}EditorGUI.BeginProperty(position, label, property);")
    if drawer_body:
        for bline in drawer_body.split("\n"):
            lines.append(f"{body_indent2}{bline}")
    else:
        lines.append(f"{body_indent2}EditorGUI.PropertyField(position, property, label, true);")
    lines.append(f"{body_indent2}EditorGUI.EndProperty();")
    lines.append(f"{body_indent}}}")
    lines.append("")

    # GetPropertyHeight
    lines.append(f"{body_indent}public override float GetPropertyHeight(SerializedProperty property, GUIContent label)")
    lines.append(f"{body_indent}{{")
    lines.append(f"{body_indent2}return EditorGUI.GetPropertyHeight(property, label, true);")
    lines.append(f"{body_indent}}}")

    lines.append(f"{indent}}}")
    if namespace:
        lines.append("}")

    return "\n".join(lines) + "\n"


def generate_inspector_drawer(
    target_type: str,
    namespace: str = "VeilBreakers.Editor",
    fields_to_draw: list[str] | None = None,
) -> str:
    """Generate a CustomEditor (Inspector drawer) C# script.

    Args:
        target_type: The MonoBehaviour/SO type to create a custom inspector for.
        namespace: Namespace for the editor class.
        fields_to_draw: Specific serialized field names to draw. If None,
                        uses DrawDefaultInspector().

    Returns:
        Complete C# source string.
    """
    safe_type = _safe_identifier(target_type)
    editor_name = f"{safe_type}Editor"

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("")

    indent = ""
    if namespace:
        lines.append(f"namespace {namespace}")
        lines.append("{")
        indent = "    "

    body_indent = indent + "    "
    body_indent2 = body_indent + "    "

    lines.append(f"{indent}[CustomEditor(typeof({safe_type}))]")
    lines.append(f"{indent}public class {editor_name} : Editor")
    lines.append(f"{indent}{{")

    # OnInspectorGUI
    lines.append(f"{body_indent}public override void OnInspectorGUI()")
    lines.append(f"{body_indent}{{")
    lines.append(f"{body_indent2}serializedObject.Update();")
    lines.append("")

    if fields_to_draw:
        for field_name in fields_to_draw:
            safe_field = _sanitize_cs_string(field_name)
            lines.append(f'{body_indent2}EditorGUILayout.PropertyField(serializedObject.FindProperty("{safe_field}"));')
    else:
        lines.append(f"{body_indent2}DrawDefaultInspector();")

    lines.append("")
    lines.append(f"{body_indent2}serializedObject.ApplyModifiedProperties();")
    lines.append(f"{body_indent}}}")

    lines.append(f"{indent}}}")
    if namespace:
        lines.append("}")

    return "\n".join(lines) + "\n"


def generate_scene_overlay(
    overlay_name: str,
    display_name: str,
    namespace: str = "VeilBreakers.Editor",
    panel_body: str = "",
) -> str:
    """Generate a SceneView Overlay C# script.

    Uses the Unity 2022.1+ Overlay API with ITransientOverlay.

    Args:
        overlay_name: Class name for the overlay.
        display_name: Display name shown in the overlay header.
        namespace: Namespace for the overlay class.
        panel_body: Custom code for CreatePanelContent body.

    Returns:
        Complete C# source string.
    """
    safe_name = _safe_identifier(overlay_name)
    safe_display = _sanitize_cs_string(display_name)

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using UnityEditor.Overlays;")
    lines.append("using UnityEngine.UIElements;")
    lines.append("")

    indent = ""
    if namespace:
        lines.append(f"namespace {namespace}")
        lines.append("{")
        indent = "    "

    body_indent = indent + "    "
    body_indent2 = body_indent + "    "

    lines.append(f'{indent}[Overlay(typeof(SceneView), "{_sanitize_cs_string(safe_name)}", "{safe_display}")]')
    lines.append(f"{indent}public class {safe_name} : Overlay, ITransientOverlay")
    lines.append(f"{indent}{{")

    # ITransientOverlay.visible
    lines.append(f"{body_indent}public bool visible => true;")
    lines.append("")

    # CreatePanelContent
    lines.append(f"{body_indent}public override VisualElement CreatePanelContent()")
    lines.append(f"{body_indent}{{")
    lines.append(f"{body_indent2}var root = new VisualElement();")
    if panel_body:
        for bline in panel_body.split("\n"):
            lines.append(f"{body_indent2}{bline}")
    else:
        lines.append(f'{body_indent2}root.Add(new Label("{safe_display}"));')
    lines.append(f"{body_indent2}return root;")
    lines.append(f"{body_indent}}}")

    lines.append(f"{indent}}}")
    if namespace:
        lines.append("}")

    return "\n".join(lines) + "\n"
