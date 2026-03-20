"""C# code generation engine for arbitrary class types, script modification, and editor tool templates.

Exports:
    generate_class         -- Generate any C# class type (MonoBehaviour, ScriptableObject, class, static class, abstract class, interface, enum, struct)
    modify_script          -- Modify existing C# source by inserting usings, fields, properties, methods, attributes
    generate_editor_window -- Generate EditorWindow scaffolding with MenuItem and OnGUI/CreateGUI
    generate_property_drawer -- Generate CustomPropertyDrawer with OnGUI and GetPropertyHeight
    generate_inspector_drawer -- Generate CustomEditor with OnInspectorGUI
    generate_scene_overlay -- Generate SceneView Overlay with CreatePanelContent
    generate_test_class    -- Generate NUnit test class for EditMode or PlayMode (CODE-04)
    generate_service_locator -- Generate static ServiceLocator with Register/Get/TryGet (CODE-06)
    generate_object_pool   -- Generate generic ObjectPool<T> with optional GameObjectPool (CODE-07)
    generate_singleton     -- Generate MonoBehaviour or plain thread-safe singleton (CODE-08)
    generate_state_machine -- Generate IState/StateMachine/BaseState framework (CODE-09)
    generate_so_event_channel -- Generate ScriptableObject event channel system (CODE-10)
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
    if result[0].isdigit():
        result = f"_{result}"
    if result in _CS_RESERVED:
        result = f"@{result}"
    return result


def _safe_type(type_str: str) -> str:
    """Sanitize a C# type expression to prevent code injection.

    Allows valid type characters: alphanumerics, underscores, angle brackets
    (generics), square brackets (arrays), dots (namespaces), commas
    (generic params), and ``?`` (nullable). Spaces are replaced with empty
    string since valid C# type tokens do not require spaces. This prevents
    multi-keyword injection like ``int; public void Exploit() {}``.

    Args:
        type_str: Raw type string (e.g. ``"List<int>"``, ``"float[]"``).

    Returns:
        Sanitized type string.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_<>\[\].,?]", "", type_str)
    return sanitized or "object"


def _safe_default(default: str, type_str: str) -> str:
    """Sanitize a default value expression to prevent code injection.

    For numeric types, validates that the value is a valid numeric literal.
    For string types, wraps in quotes and escapes. For other types, strips
    dangerous characters.

    Args:
        default: Raw default value string.
        type_str: The C# type of the field (used to determine validation).

    Returns:
        Sanitized default value string.
    """
    if not default:
        return default

    clean_type = type_str.strip().rstrip("?")

    # Numeric types: validate as numeric literal (with optional suffix)
    numeric_types = {"int", "float", "double", "long", "short", "byte",
                     "uint", "ulong", "ushort", "sbyte", "decimal"}
    if clean_type in numeric_types:
        # Allow numeric literals with optional suffix (f, d, m, L, etc.)
        if re.match(r'^-?[0-9]*\.?[0-9]+[fFdDmMlLuU]?$', default.strip()):
            return default
        return "0"

    # Bool type
    if clean_type == "bool":
        if default.strip() in ("true", "false"):
            return default
        return "false"

    # String type: ensure properly escaped
    if clean_type == "string":
        inner = default.strip()
        if inner.startswith('"') and inner.endswith('"'):
            return inner
        return f'"{_sanitize_cs_string(inner)}"'

    # For other types: strip semicolons and braces that could inject code
    sanitized = re.sub(r"[;{}]", "", default)
    return sanitized


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
    ftype = _safe_type(field.get("type", "int"))
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

    safe_default = _safe_default(default, ftype) if default else ""
    decl = f"{indent}{access} {ftype} {safe_name}"
    if safe_default:
        decl += f" = {safe_default}"
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
    ptype = _safe_type(prop.get("type", "int"))
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
    ret_type = _safe_type(method.get("return_type", "void"))
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
        inheritance.append(_safe_type(base_class))
    if interfaces:
        inheritance.extend(_safe_type(iface) for iface in interfaces)
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
                rf"^(\s*)(public|internal|private|protected)?\s*(sealed\s+|abstract\s+|static\s+)*(partial\s+)?(class|struct|interface)\s+{re.escape(target_class)}\b",
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
        r"((?:public|internal|private|protected)\s+(?:sealed\s+|abstract\s+|static\s+)*(?:partial\s+)?(?:class|struct|interface)\s+\w+[^{]*\{)",
        source,
        re.MULTILINE,
    )
    if match:
        insert_pos = match.end()
        return source[:insert_pos] + "\n" + code_to_insert + source[insert_pos:]
    raise ValueError("No class/struct/interface declaration found in source for insertion.")


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


# ---------------------------------------------------------------------------
# CODE-04: Test class generator
# ---------------------------------------------------------------------------


def generate_test_class(
    class_name: str,
    test_mode: str = "EditMode",
    namespace: str = "",
    target_class: str = "",
    test_methods: list[dict] | None = None,
    setup_body: str = "",
    teardown_body: str = "",
) -> str:
    """Generate an NUnit test class for Unity EditMode or PlayMode tests.

    Args:
        class_name: Name of the test fixture class.
        test_mode: ``"EditMode"`` or ``"PlayMode"``.
        namespace: Optional namespace wrapper.
        target_class: If provided, creates a ``_sut`` field and instantiates it in SetUp.
        test_methods: List of dicts with keys: ``name``, ``body`` (optional),
                      ``is_unity_test`` (optional bool for ``[UnityTest]``).
        setup_body: Custom body for the ``[SetUp]`` method.
        teardown_body: Custom body for the ``[TearDown]`` method.

    Returns:
        Complete C# NUnit test class source string.
    """
    safe_name = _safe_identifier(class_name)

    lines: list[str] = []

    # Using statements
    usings_set: set[str] = set()
    usings_ordered: list[str] = []

    def _add_using(u: str) -> None:
        if u not in usings_set:
            usings_set.add(u)
            usings_ordered.append(u)

    _add_using("NUnit.Framework")
    _add_using("UnityEngine")
    if test_mode == "PlayMode":
        _add_using("UnityEngine.TestTools")
    # Check if any test method is a UnityTest (needs TestTools even in EditMode)
    if test_methods and any(m.get("is_unity_test") for m in test_methods):
        _add_using("UnityEngine.TestTools")
        _add_using("System.Collections")

    for u in usings_ordered:
        lines.append(f"using {u};")
    lines.append("")

    indent = ""
    if namespace:
        lines.append(f"namespace {namespace}")
        lines.append("{")
        indent = "    "

    body_indent = indent + "    "
    body_indent2 = body_indent + "    "

    lines.append(f"{indent}[TestFixture]")
    lines.append(f"{indent}public class {safe_name}")
    lines.append(f"{indent}{{")

    # Target class field
    if target_class:
        safe_target = _safe_identifier(target_class)
        lines.append(f"{body_indent}private {safe_target} _sut;")
        lines.append("")

    # SetUp
    if setup_body or target_class:
        lines.append(f"{body_indent}[SetUp]")
        lines.append(f"{body_indent}public void SetUp()")
        lines.append(f"{body_indent}{{")
        if target_class:
            safe_target = _safe_identifier(target_class)
            lines.append(f"{body_indent2}_sut = new {safe_target}();")
        if setup_body:
            for bline in setup_body.split("\n"):
                lines.append(f"{body_indent2}{bline}")
        lines.append(f"{body_indent}}}")
        lines.append("")

    # TearDown
    if teardown_body:
        lines.append(f"{body_indent}[TearDown]")
        lines.append(f"{body_indent}public void TearDown()")
        lines.append(f"{body_indent}{{")
        for bline in teardown_body.split("\n"):
            lines.append(f"{body_indent2}{bline}")
        lines.append(f"{body_indent}}}")
        lines.append("")

    # Test methods
    if test_methods:
        for i, method in enumerate(test_methods):
            m_name = _safe_identifier(method.get("name", f"Test{i + 1}"))
            m_body = method.get("body", "")
            is_unity = method.get("is_unity_test", False)

            if is_unity:
                lines.append(f"{body_indent}[UnityTest]")
                lines.append(f"{body_indent}public IEnumerator {m_name}()")
            else:
                lines.append(f"{body_indent}[Test]")
                lines.append(f"{body_indent}public void {m_name}()")
            lines.append(f"{body_indent}{{")
            if m_body:
                for bline in m_body.split("\n"):
                    lines.append(f"{body_indent2}{bline}")
            else:
                if is_unity:
                    lines.append(f"{body_indent2}yield return null;")
                else:
                    lines.append(f"{body_indent2}Assert.Pass();")
            lines.append(f"{body_indent}}}")
            if i < len(test_methods) - 1:
                lines.append("")
    else:
        # Default test method
        lines.append(f"{body_indent}[Test]")
        lines.append(f"{body_indent}public void TestPlaceholder()")
        lines.append(f"{body_indent}{{")
        lines.append(f"{body_indent2}Assert.Pass();")
        lines.append(f"{body_indent}}}")

    lines.append(f"{indent}}}")
    if namespace:
        lines.append("}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CODE-06: Service locator generator
# ---------------------------------------------------------------------------


def generate_service_locator(
    namespace: str = "VeilBreakers.Patterns",
    include_scene_persistent: bool = True,
) -> str:
    """Generate a static ServiceLocator class with type-based service registry.

    Args:
        namespace: Namespace wrapper (default ``VeilBreakers.Patterns``).
        include_scene_persistent: If True, adds ``ServiceLocatorInitializer``
            MonoBehaviour with ``[RuntimeInitializeOnLoadMethod]`` to auto-clear
            on scene load.

    Returns:
        Complete C# source string.
    """
    lines: list[str] = []

    lines.append("using System;")
    lines.append("using System.Collections.Generic;")
    lines.append("using UnityEngine;")
    lines.append("")

    indent = ""
    if namespace:
        lines.append(f"namespace {namespace}")
        lines.append("{")
        indent = "    "

    body_indent = indent + "    "
    body_indent2 = body_indent + "    "

    # ServiceLocator class
    lines.append(f"{indent}/// <summary>")
    lines.append(f"{indent}/// Static service locator for dependency injection.")
    lines.append(f"{indent}/// </summary>")
    lines.append(f"{indent}public static class ServiceLocator")
    lines.append(f"{indent}{{")
    lines.append(f"{body_indent}private static readonly Dictionary<Type, object> _services = new();")
    lines.append("")

    # Register<T>
    lines.append(f"{body_indent}public static void Register<T>(T service) where T : class")
    lines.append(f"{body_indent}{{")
    lines.append(f"{body_indent2}_services[typeof(T)] = service;")
    lines.append(f"{body_indent}}}")
    lines.append("")

    # Get<T>
    lines.append(f"{body_indent}public static T Get<T>() where T : class")
    lines.append(f"{body_indent}{{")
    lines.append(f"{body_indent2}if (_services.TryGetValue(typeof(T), out var service))")
    lines.append(f"{body_indent2}    return (T)service;")
    lines.append(f'{body_indent2}throw new InvalidOperationException($"Service {{typeof(T).Name}} not registered.");')
    lines.append(f"{body_indent}}}")
    lines.append("")

    # TryGet<T>
    lines.append(f"{body_indent}public static bool TryGet<T>(out T service) where T : class")
    lines.append(f"{body_indent}{{")
    lines.append(f"{body_indent2}if (_services.TryGetValue(typeof(T), out var obj))")
    lines.append(f"{body_indent2}{{")
    lines.append(f"{body_indent2}    service = (T)obj;")
    lines.append(f"{body_indent2}    return true;")
    lines.append(f"{body_indent2}}}")
    lines.append(f"{body_indent2}service = null;")
    lines.append(f"{body_indent2}return false;")
    lines.append(f"{body_indent}}}")
    lines.append("")

    # Unregister<T>
    lines.append(f"{body_indent}public static void Unregister<T>() where T : class")
    lines.append(f"{body_indent}{{")
    lines.append(f"{body_indent2}_services.Remove(typeof(T));")
    lines.append(f"{body_indent}}}")
    lines.append("")

    # Clear
    lines.append(f"{body_indent}public static void Clear()")
    lines.append(f"{body_indent}{{")
    lines.append(f"{body_indent2}_services.Clear();")
    lines.append(f"{body_indent}}}")

    lines.append(f"{indent}}}")

    # ServiceLocatorInitializer
    if include_scene_persistent:
        lines.append("")
        lines.append(f"{indent}/// <summary>")
        lines.append(f"{indent}/// Auto-clears ServiceLocator on scene load to prevent stale references.")
        lines.append(f"{indent}/// </summary>")
        lines.append(f"{indent}public class ServiceLocatorInitializer : MonoBehaviour")
        lines.append(f"{indent}{{")
        lines.append(f"{body_indent}[RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]")
        lines.append(f"{body_indent}private static void Init()")
        lines.append(f"{body_indent}{{")
        lines.append(f"{body_indent2}ServiceLocator.Clear();")
        lines.append(f"{body_indent}}}")
        lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CODE-07: Object pool generator
# ---------------------------------------------------------------------------


def generate_object_pool(
    namespace: str = "VeilBreakers.Patterns",
    include_gameobject_pool: bool = True,
) -> str:
    """Generate a generic ObjectPool<T> with optional GameObjectPool specialisation.

    Args:
        namespace: Namespace wrapper (default ``VeilBreakers.Patterns``).
        include_gameobject_pool: If True, adds a ``GameObjectPool`` subclass
            using ``Instantiate``/``SetActive`` for GameObjects.

    Returns:
        Complete C# source string.
    """
    lines: list[str] = []

    lines.append("using System;")
    lines.append("using System.Collections.Generic;")
    lines.append("using UnityEngine;")
    lines.append("")

    indent = ""
    if namespace:
        lines.append(f"namespace {namespace}")
        lines.append("{")
        indent = "    "

    body_indent = indent + "    "
    body_indent2 = body_indent + "    "
    body_indent3 = body_indent2 + "    "

    # ObjectPool<T>
    lines.append(f"{indent}/// <summary>")
    lines.append(f"{indent}/// Generic object pool with configurable create, get, and release callbacks.")
    lines.append(f"{indent}/// </summary>")
    lines.append(f"{indent}public class ObjectPool<T> where T : class")
    lines.append(f"{indent}{{")
    lines.append(f"{body_indent}private readonly Stack<T> _available;")
    lines.append(f"{body_indent}private readonly Func<T> _createFunc;")
    lines.append(f"{body_indent}private readonly Action<T> _onGet;")
    lines.append(f"{body_indent}private readonly Action<T> _onRelease;")
    lines.append(f"{body_indent}private readonly int _maxSize;")
    lines.append("")
    lines.append(f"{body_indent}public int CountActive {{ get; private set; }}")
    lines.append(f"{body_indent}public int CountInactive => _available.Count;")
    lines.append("")

    # Constructor
    lines.append(f"{body_indent}public ObjectPool(")
    lines.append(f"{body_indent2}Func<T> createFunc,")
    lines.append(f"{body_indent2}Action<T> onGet = null,")
    lines.append(f"{body_indent2}Action<T> onRelease = null,")
    lines.append(f"{body_indent2}int initialSize = 10,")
    lines.append(f"{body_indent2}int maxSize = 100)")
    lines.append(f"{body_indent}{{")
    lines.append(f"{body_indent2}_createFunc = createFunc ?? throw new ArgumentNullException(nameof(createFunc));")
    lines.append(f"{body_indent2}_onGet = onGet;")
    lines.append(f"{body_indent2}_onRelease = onRelease;")
    lines.append(f"{body_indent2}_maxSize = maxSize;")
    lines.append(f"{body_indent2}_available = new Stack<T>(initialSize);")
    lines.append("")
    lines.append(f"{body_indent2}// Warm up pool")
    lines.append(f"{body_indent2}for (int i = 0; i < initialSize; i++)")
    lines.append(f"{body_indent2}    _available.Push(_createFunc());")
    lines.append(f"{body_indent}}}")
    lines.append("")

    # Get
    lines.append(f"{body_indent}public T Get()")
    lines.append(f"{body_indent}{{")
    lines.append(f"{body_indent2}T item = _available.Count > 0 ? _available.Pop() : _createFunc();")
    lines.append(f"{body_indent2}_onGet?.Invoke(item);")
    lines.append(f"{body_indent2}CountActive++;")
    lines.append(f"{body_indent2}return item;")
    lines.append(f"{body_indent}}}")
    lines.append("")

    # Release
    lines.append(f"{body_indent}public void Release(T item)")
    lines.append(f"{body_indent}{{")
    lines.append(f"{body_indent2}_onRelease?.Invoke(item);")
    lines.append(f"{body_indent2}CountActive--;")
    lines.append(f"{body_indent2}if (_available.Count < _maxSize)")
    lines.append(f"{body_indent2}    _available.Push(item);")
    lines.append(f"{body_indent}}}")

    lines.append(f"{indent}}}")

    # GameObjectPool
    if include_gameobject_pool:
        lines.append("")
        lines.append(f"{indent}/// <summary>")
        lines.append(f"{indent}/// Specialised pool for GameObjects using Instantiate/SetActive pattern.")
        lines.append(f"{indent}/// </summary>")
        lines.append(f"{indent}public class GameObjectPool")
        lines.append(f"{indent}{{")
        lines.append(f"{body_indent}private readonly ObjectPool<GameObject> _pool;")
        lines.append(f"{body_indent}private readonly GameObject _prefab;")
        lines.append("")

        # Constructor
        lines.append(f"{body_indent}public GameObjectPool(GameObject prefab, int initialSize = 10, int maxSize = 100)")
        lines.append(f"{body_indent}{{")
        lines.append(f"{body_indent2}_prefab = prefab;")
        lines.append(f"{body_indent2}_pool = new ObjectPool<GameObject>(")
        lines.append(f"{body_indent3}createFunc: () => UnityEngine.Object.Instantiate(_prefab),")
        lines.append(f"{body_indent3}onGet: obj => obj.SetActive(true),")
        lines.append(f"{body_indent3}onRelease: obj => obj.SetActive(false),")
        lines.append(f"{body_indent3}initialSize: initialSize,")
        lines.append(f"{body_indent3}maxSize: maxSize")
        lines.append(f"{body_indent2});")
        lines.append(f"{body_indent}}}")
        lines.append("")

        lines.append(f"{body_indent}public GameObject Get() => _pool.Get();")
        lines.append(f"{body_indent}public void Release(GameObject obj) => _pool.Release(obj);")
        lines.append(f"{body_indent}public int CountActive => _pool.CountActive;")
        lines.append(f"{body_indent}public int CountInactive => _pool.CountInactive;")

        lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CODE-08: Singleton generator
# ---------------------------------------------------------------------------


def generate_singleton(
    class_name: str,
    singleton_type: str = "MonoBehaviour",
    namespace: str = "VeilBreakers.Patterns",
    persistent: bool = True,
) -> str:
    """Generate a singleton pattern class.

    Args:
        class_name: Name of the singleton class.
        singleton_type: ``"MonoBehaviour"`` for Unity singleton or ``"Plain"``
            for a thread-safe non-MonoBehaviour singleton.
        namespace: Namespace wrapper.
        persistent: If True (and MonoBehaviour type), adds ``DontDestroyOnLoad``.

    Returns:
        Complete C# source string.
    """
    safe_name = _safe_identifier(class_name)

    lines: list[str] = []

    if singleton_type == "MonoBehaviour":
        lines.append("using UnityEngine;")
    else:
        lines.append("using System;")
    lines.append("")

    indent = ""
    if namespace:
        lines.append(f"namespace {namespace}")
        lines.append("{")
        indent = "    "

    body_indent = indent + "    "
    body_indent2 = body_indent + "    "

    lines.append(f"{indent}/// <summary>")
    lines.append(f"{indent}/// Singleton implementation for {safe_name}.")
    lines.append(f"{indent}/// Compatible with VeilBreakers.Core.SingletonMonoBehaviour&lt;T&gt; pattern")
    lines.append(f"{indent}/// </summary>")

    if singleton_type == "MonoBehaviour":
        lines.append(f"{indent}public class {safe_name} : MonoBehaviour")
        lines.append(f"{indent}{{")
        lines.append(f"{body_indent}private static {safe_name} _instance;")
        lines.append("")

        # Instance property with lazy find fallback
        lines.append(f"{body_indent}public static {safe_name} Instance")
        lines.append(f"{body_indent}{{")
        lines.append(f"{body_indent2}get")
        lines.append(f"{body_indent2}{{")
        lines.append(f"{body_indent2}    if (_instance == null)")
        lines.append(f"{body_indent2}        _instance = FindAnyObjectByType<{safe_name}>();")
        lines.append(f"{body_indent2}    return _instance;")
        lines.append(f"{body_indent2}}}")
        lines.append(f"{body_indent}}}")
        lines.append("")

        # Awake
        lines.append(f"{body_indent}private void Awake()")
        lines.append(f"{body_indent}{{")
        lines.append(f"{body_indent2}if (_instance != null && _instance != this)")
        lines.append(f"{body_indent2}{{")
        lines.append(f"{body_indent2}    Destroy(gameObject);")
        lines.append(f"{body_indent2}    return;")
        lines.append(f"{body_indent2}}}")
        lines.append(f"{body_indent2}_instance = this;")
        if persistent:
            lines.append(f"{body_indent2}DontDestroyOnLoad(gameObject);")
        lines.append(f"{body_indent}}}")

        lines.append(f"{indent}}}")

    else:
        # Plain thread-safe singleton
        lines.append(f"{indent}public class {safe_name}")
        lines.append(f"{indent}{{")
        lines.append(f"{body_indent}private static readonly Lazy<{safe_name}> _instance = new(() => new {safe_name}());")
        lines.append("")
        lines.append(f"{body_indent}public static {safe_name} Instance => _instance.Value;")
        lines.append("")
        lines.append(f"{body_indent}private {safe_name}() {{ }}")

        lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CODE-09: State machine generator
# ---------------------------------------------------------------------------


def generate_state_machine(
    namespace: str = "VeilBreakers.Patterns",
) -> str:
    """Generate a generic state machine framework with IState, StateMachine, and BaseState.

    Args:
        namespace: Namespace wrapper (default ``VeilBreakers.Patterns``).

    Returns:
        Complete C# source string containing IState interface, StateMachine class,
        and BaseState abstract class.
    """
    lines: list[str] = []

    lines.append("using System;")
    lines.append("using System.Collections.Generic;")
    lines.append("")

    indent = ""
    if namespace:
        lines.append(f"namespace {namespace}")
        lines.append("{")
        indent = "    "

    body_indent = indent + "    "
    body_indent2 = body_indent + "    "

    # IState interface
    lines.append(f"{indent}/// <summary>")
    lines.append(f"{indent}/// Interface for state machine states.")
    lines.append(f"{indent}/// </summary>")
    lines.append(f"{indent}public interface IState")
    lines.append(f"{indent}{{")
    lines.append(f"{body_indent}void Enter();")
    lines.append(f"{body_indent}void Exit();")
    lines.append(f"{body_indent}void Update();")
    lines.append(f"{body_indent}void FixedUpdate();")
    lines.append(f"{indent}}}")
    lines.append("")

    # StateMachine class
    lines.append(f"{indent}/// <summary>")
    lines.append(f"{indent}/// Generic state machine that manages state transitions.")
    lines.append(f"{indent}/// </summary>")
    lines.append(f"{indent}public class StateMachine")
    lines.append(f"{indent}{{")
    lines.append(f"{body_indent}private IState _currentState;")
    lines.append(f"{body_indent}private readonly Dictionary<Type, IState> _states = new();")
    lines.append("")
    lines.append(f"{body_indent}public IState CurrentState => _currentState;")
    lines.append("")

    # AddState
    lines.append(f"{body_indent}public void AddState(IState state)")
    lines.append(f"{body_indent}{{")
    lines.append(f"{body_indent2}_states[state.GetType()] = state;")
    lines.append(f"{body_indent}}}")
    lines.append("")

    # ChangeState<T>
    lines.append(f"{body_indent}public void ChangeState<T>() where T : IState")
    lines.append(f"{body_indent}{{")
    lines.append(f"{body_indent2}if (!_states.TryGetValue(typeof(T), out var newState))")
    lines.append(f'{body_indent2}    throw new InvalidOperationException($"State {{typeof(T).Name}} not registered.");')
    lines.append(f"{body_indent2}_currentState?.Exit();")
    lines.append(f"{body_indent2}_currentState = newState;")
    lines.append(f"{body_indent2}_currentState.Enter();")
    lines.append(f"{body_indent}}}")
    lines.append("")

    # Update
    lines.append(f"{body_indent}public void Update()")
    lines.append(f"{body_indent}{{")
    lines.append(f"{body_indent2}_currentState?.Update();")
    lines.append(f"{body_indent}}}")
    lines.append("")

    # FixedUpdate
    lines.append(f"{body_indent}public void FixedUpdate()")
    lines.append(f"{body_indent}{{")
    lines.append(f"{body_indent2}_currentState?.FixedUpdate();")
    lines.append(f"{body_indent}}}")

    lines.append(f"{indent}}}")
    lines.append("")

    # BaseState abstract class
    lines.append(f"{indent}/// <summary>")
    lines.append(f"{indent}/// Abstract base state with virtual empty implementations.")
    lines.append(f"{indent}/// </summary>")
    lines.append(f"{indent}public abstract class BaseState : IState")
    lines.append(f"{indent}{{")
    lines.append(f"{body_indent}public virtual void Enter() {{ }}")
    lines.append(f"{body_indent}public virtual void Exit() {{ }}")
    lines.append(f"{body_indent}public virtual void Update() {{ }}")
    lines.append(f"{body_indent}public virtual void FixedUpdate() {{ }}")
    lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CODE-10: ScriptableObject event channel generator
# ---------------------------------------------------------------------------


def generate_so_event_channel(
    event_name: str = "",
    has_parameter: bool = False,
    parameter_type: str = "int",
    namespace: str = "VeilBreakers.Events.Channels",
) -> str:
    """Generate ScriptableObject-based event channel system.

    When ``event_name`` is empty, generates the base classes (``GameEvent``,
    ``GameEvent<T>``, ``GameEventListener``). When ``event_name`` is provided,
    generates a specific typed event subclass.

    This system is complementary to the existing ``VeilBreakers.Core.EventBus``.

    Args:
        event_name: If empty, generates base classes. If provided, generates a
            specific event subclass (e.g. ``PlayerDeathEvent``).
        has_parameter: Whether the event carries a parameter value.
        parameter_type: C# type of the parameter (e.g. ``"float"``, ``"int"``).
        namespace: Namespace (default ``VeilBreakers.Events.Channels``).

    Returns:
        Complete C# source string.
    """
    lines: list[str] = []

    lines.append("using System;")
    lines.append("using UnityEngine;")
    if not event_name:
        lines.append("using UnityEngine.Events;")
    lines.append("")

    indent = ""
    if namespace:
        lines.append(f"namespace {namespace}")
        lines.append("{")
        indent = "    "

    body_indent = indent + "    "
    body_indent2 = body_indent + "    "

    if not event_name:
        # --- Base GameEvent (no parameter) ---
        lines.append(f'{indent}[CreateAssetMenu(menuName = "VeilBreakers/Events/Game Event", fileName = "NewGameEvent")]')
        lines.append(f"{indent}public class GameEvent : ScriptableObject")
        lines.append(f"{indent}{{")
        lines.append(f"{body_indent}private Action _onRaise;")
        lines.append("")
        lines.append(f"{body_indent}public void RegisterListener(Action listener) => _onRaise += listener;")
        lines.append(f"{body_indent}public void UnregisterListener(Action listener) => _onRaise -= listener;")
        lines.append("")
        lines.append(f"{body_indent}public void Raise()")
        lines.append(f"{body_indent}{{")
        lines.append(f"{body_indent2}_onRaise?.Invoke();")
        lines.append(f"{body_indent2}#if UNITY_EDITOR")
        lines.append(f'{body_indent2}Debug.Log($"[GameEvent] {{name}} raised");')
        lines.append(f"{body_indent2}#endif")
        lines.append(f"{body_indent}}}")
        lines.append(f"{indent}}}")
        lines.append("")

        # --- Base GameEvent<T> (typed parameter) ---
        lines.append(f"{indent}public class GameEvent<T> : ScriptableObject")
        lines.append(f"{indent}{{")
        lines.append(f"{body_indent}private Action<T> _onRaise;")
        lines.append("")
        lines.append(f"{body_indent}public void RegisterListener(Action<T> listener) => _onRaise += listener;")
        lines.append(f"{body_indent}public void UnregisterListener(Action<T> listener) => _onRaise -= listener;")
        lines.append("")
        lines.append(f"{body_indent}public void Raise(T value)")
        lines.append(f"{body_indent}{{")
        lines.append(f"{body_indent2}_onRaise?.Invoke(value);")
        lines.append(f"{body_indent2}#if UNITY_EDITOR")
        lines.append(f'{body_indent2}Debug.Log($"[GameEvent<{{typeof(T).Name}}>] {{name}} raised with {{value}}");')
        lines.append(f"{body_indent2}#endif")
        lines.append(f"{body_indent}}}")
        lines.append(f"{indent}}}")
        lines.append("")

        # --- GameEventListener MonoBehaviour ---
        lines.append(f"{indent}/// <summary>")
        lines.append(f"{indent}/// MonoBehaviour listener that subscribes to a GameEvent and invokes a UnityEvent response.")
        lines.append(f"{indent}/// </summary>")
        lines.append(f"{indent}public class GameEventListener : MonoBehaviour")
        lines.append(f"{indent}{{")
        lines.append(f"{body_indent}[SerializeField] private GameEvent _event;")
        lines.append(f"{body_indent}[SerializeField] private UnityEvent _response;")
        lines.append("")
        lines.append(f"{body_indent}private void OnEnable()")
        lines.append(f"{body_indent}{{")
        lines.append(f"{body_indent2}if (_event != null)")
        lines.append(f"{body_indent2}    _event.RegisterListener(OnEventRaised);")
        lines.append(f"{body_indent}}}")
        lines.append("")
        lines.append(f"{body_indent}private void OnDisable()")
        lines.append(f"{body_indent}{{")
        lines.append(f"{body_indent2}if (_event != null)")
        lines.append(f"{body_indent2}    _event.UnregisterListener(OnEventRaised);")
        lines.append(f"{body_indent}}}")
        lines.append("")
        lines.append(f"{body_indent}private void OnEventRaised()")
        lines.append(f"{body_indent}{{")
        lines.append(f"{body_indent2}_response?.Invoke();")
        lines.append(f"{body_indent}}}")
        lines.append(f"{indent}}}")

    else:
        # --- Specific typed event ---
        safe_event = _safe_identifier(event_name)
        if has_parameter:
            safe_param = _sanitize_cs_string(parameter_type)
            lines.append(f"{indent}/// <summary>")
            lines.append(f"{indent}/// {safe_event} event channel carrying a {safe_param} parameter.")
            lines.append(f"{indent}/// </summary>")
            lines.append(f'{indent}[CreateAssetMenu(menuName = "VeilBreakers/Events/{safe_event} Event", fileName = "{safe_event}Event")]')
            lines.append(f"{indent}public class {safe_event}Event : GameEvent<{parameter_type}>")
            lines.append(f"{indent}{{")
            lines.append(f"{indent}}}")
        else:
            lines.append(f"{indent}/// <summary>")
            lines.append(f"{indent}/// {safe_event} event channel (no parameter).")
            lines.append(f"{indent}/// </summary>")
            lines.append(f'{indent}[CreateAssetMenu(menuName = "VeilBreakers/Events/{safe_event} Event", fileName = "{safe_event}Event")]')
            lines.append(f"{indent}public class {safe_event}Event : GameEvent")
            lines.append(f"{indent}{{")
            lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    return "\n".join(lines) + "\n"
