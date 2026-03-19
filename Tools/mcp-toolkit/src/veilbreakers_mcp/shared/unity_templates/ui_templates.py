"""UXML + USS template generators for Unity UI Toolkit.

Generates UI screens from text descriptions with VeilBreakers dark fantasy
styling. Supports HUD, inventory, settings, dialog, and shop screen types.

Functions:
    generate_uxml_screen          - Build UXML document from screen spec
    generate_uss_stylesheet       - Generate USS with dark fantasy theme
    generate_responsive_test_script - C# editor script for multi-resolution capture
    validate_uxml_layout          - Static analysis of UXML for layout issues
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

# ---------------------------------------------------------------------------
# Element type -> UXML tag mapping
# ---------------------------------------------------------------------------

_ELEMENT_TAG_MAP: dict[str, str] = {
    "label": "ui:Label",
    "button": "ui:Button",
    "image": "ui:VisualElement",
    "panel": "ui:VisualElement",
    "input": "ui:TextField",
    "slider": "ui:Slider",
    "toggle": "ui:Toggle",
}

# Default class per element type (used when spec doesn't provide one)
_DEFAULT_CLASS_MAP: dict[str, str] = {
    "label": "vb-label",
    "button": "vb-button",
    "image": "vb-image",
    "panel": "vb-panel",
    "input": "vb-input",
    "slider": "vb-slider",
    "toggle": "vb-toggle",
}

# Default 5 responsive test resolutions
DEFAULT_RESOLUTIONS: list[tuple[int, int]] = [
    (1280, 720),
    (1920, 1080),
    (2560, 1440),
    (3840, 2160),
    (800, 600),
]


# ---------------------------------------------------------------------------
# UXML screen generation
# ---------------------------------------------------------------------------


def _build_element(parent: ET.Element, spec: dict[str, Any]) -> None:
    """Recursively build a UXML element from a spec dict.

    Args:
        parent: Parent XML element to append to.
        spec: Element specification with keys: type, text, name, class, children.
    """
    elem_type = spec.get("type", "panel")
    tag = _ELEMENT_TAG_MAP.get(elem_type, "ui:VisualElement")
    default_class = _DEFAULT_CLASS_MAP.get(elem_type, "")

    attribs: dict[str, str] = {}

    # Text attribute (for label, button, input, toggle)
    text = spec.get("text")
    if text and elem_type in ("label", "button", "input", "toggle"):
        attribs["text"] = text

    # Name attribute
    name = spec.get("name")
    if name:
        attribs["name"] = name

    # Class attribute -- use spec class or default
    css_class = spec.get("class", default_class)
    if css_class:
        attribs["class"] = css_class

    # Style attribute (optional, for explicit sizing)
    style = spec.get("style")
    if style:
        attribs["style"] = style

    child_elem = ET.SubElement(parent, tag, attribs)

    # Recurse into children
    for child_spec in spec.get("children", []):
        _build_element(child_elem, child_spec)


def generate_uxml_screen(spec: dict[str, Any]) -> str:
    """Generate a complete UXML document from a screen specification.

    Args:
        spec: Screen specification with keys:
            - title (str): Screen title shown in a label.
            - elements (list[dict]): UI element specs, each with:
                type (str): label|button|image|panel|input|slider|toggle
                text (str): Display text.
                name (str): Element name for code access.
                class (str): CSS class override.
                style (str): Inline style string.
                children (list[dict]): Nested element specs.

    Returns:
        Complete UXML XML string with xmlns declaration.
    """
    root = ET.Element("ui:UXML")
    root.set("xmlns:ui", "UnityEngine.UIElements")
    root.set("xmlns:uie", "UnityEditor.UIElements")

    # Screen root container
    screen_root = ET.SubElement(root, "ui:VisualElement", {"class": "screen-root"})

    # Title element
    title = spec.get("title", "")
    if title:
        ET.SubElement(screen_root, "ui:Label", {
            "text": title,
            "class": "vb-title",
            "name": "screen-title",
        })

    # Build all child elements
    for elem_spec in spec.get("elements", []):
        _build_element(screen_root, elem_spec)

    # Serialize to string with XML declaration
    ET.indent(root, space="    ")
    xml_bytes = ET.tostring(root, encoding="unicode", xml_declaration=False)

    # Prepend proper XML header
    return f'<?xml version="1.0" encoding="utf-8"?>\n{xml_bytes}\n'


# ---------------------------------------------------------------------------
# USS stylesheet generation
# ---------------------------------------------------------------------------

_THEMES: dict[str, dict[str, str]] = {
    "dark_fantasy": {
        "bg_primary": "#1a1a2e",
        "bg_secondary": "#16213e",
        "bg_panel": "#0f3460",
        "text_primary": "#e6e6ff",
        "text_secondary": "#b8b8d4",
        "accent": "#4a0e4e",
        "accent_hover": "#7b2d8e",
        "accent_active": "#9b4dca",
        "border_color": "#4a0e4e",
        "input_bg": "#0d1b2a",
        "slider_bg": "#1b2838",
        "slider_fill": "#4a0e4e",
    },
}


def generate_uss_stylesheet(theme: str = "dark_fantasy") -> str:
    """Generate a USS stylesheet with VeilBreakers theming.

    Args:
        theme: Theme name. Currently supports "dark_fantasy".

    Returns:
        Complete USS stylesheet string.

    Raises:
        ValueError: If theme name is not recognized.
    """
    if theme not in _THEMES:
        raise ValueError(
            f"Unknown theme '{theme}'. Available: {sorted(_THEMES.keys())}"
        )

    t = _THEMES[theme]

    return f"""/* VeilBreakers UI Toolkit Stylesheet -- {theme} theme */
/* Auto-generated by veilbreakers-mcp ui_templates */

.screen-root {{
    background-color: {t['bg_primary']};
    flex-grow: 1;
    padding: 16px;
    align-items: center;
    justify-content: flex-start;
}}

.vb-title {{
    color: {t['text_primary']};
    font-size: 36px;
    -unity-text-align: middle-center;
    margin-bottom: 24px;
    -unity-font-style: bold;
    text-shadow: 2px 2px 4px rgba(74, 14, 78, 0.8);
}}

.vb-label {{
    color: {t['text_secondary']};
    font-size: 18px;
    -unity-text-align: middle-left;
    margin: 4px 0;
}}

.vb-button {{
    background-color: {t['accent']};
    color: {t['text_primary']};
    border-color: {t['border_color']};
    border-width: 2px;
    border-radius: 4px;
    padding: 8px 24px;
    font-size: 18px;
    -unity-text-align: middle-center;
    margin: 4px;
    min-width: 120px;
    min-height: 40px;
    transition-duration: 0.2s;
}}

.vb-button:hover {{
    background-color: {t['accent_hover']};
    border-color: {t['accent_active']};
    scale: 1.05;
}}

.vb-button:active {{
    background-color: {t['accent_active']};
    scale: 0.98;
}}

.vb-panel {{
    background-color: {t['bg_secondary']};
    border-color: {t['border_color']};
    border-width: 1px;
    border-radius: 8px;
    padding: 16px;
    margin: 8px;
    flex-grow: 0;
    flex-shrink: 0;
}}

.vb-image {{
    background-color: {t['bg_panel']};
    border-radius: 4px;
    min-width: 64px;
    min-height: 64px;
}}

.vb-input {{
    background-color: {t['input_bg']};
    color: {t['text_primary']};
    border-color: {t['border_color']};
    border-width: 1px;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 16px;
    margin: 4px;
    min-height: 32px;
}}

.vb-input:focus {{
    border-color: {t['accent_hover']};
    border-width: 2px;
}}

.vb-slider {{
    margin: 8px;
    min-width: 200px;
}}

.vb-slider #unity-tracker {{
    background-color: {t['slider_bg']};
    border-radius: 4px;
    height: 6px;
}}

.vb-slider #unity-dragger {{
    background-color: {t['accent']};
    border-radius: 50%;
    width: 16px;
    height: 16px;
}}

.vb-slider #unity-dragger:hover {{
    background-color: {t['accent_hover']};
}}

.vb-toggle {{
    margin: 4px;
    color: {t['text_secondary']};
    font-size: 16px;
}}

.vb-toggle > .unity-toggle__checkmark {{
    background-color: {t['input_bg']};
    border-color: {t['border_color']};
    border-width: 2px;
    border-radius: 4px;
    width: 24px;
    height: 24px;
}}

.vb-toggle:checked > .unity-toggle__checkmark {{
    background-color: {t['accent']};
    border-color: {t['accent_hover']};
}}
"""


# ---------------------------------------------------------------------------
# Responsive test C# script generation
# ---------------------------------------------------------------------------


def generate_responsive_test_script(
    uxml_path: str,
    resolutions: list[tuple[int, int]] | None = None,
) -> str:
    """Generate a C# editor script that captures screenshots at multiple resolutions.

    The script uses Unity's internal GameView API via reflection to resize
    the game view, waits one frame, and captures a screenshot for each resolution.

    Args:
        uxml_path: Path to the UXML file (relative to Unity project), used
            to derive the screen name for output filenames.
        resolutions: List of (width, height) tuples. Defaults to
            [(1280,720), (1920,1080), (2560,1440), (3840,2160), (800,600)].

    Returns:
        Complete C# editor script source string.
    """
    if resolutions is None:
        resolutions = DEFAULT_RESOLUTIONS

    # Extract screen name from UXML path for filenames
    screen_name = uxml_path.replace("\\", "/").split("/")[-1].replace(".uxml", "")

    # Build the resolution array initializer
    res_entries = []
    for w, h in resolutions:
        res_entries.append(f"            new Vector2Int({w}, {h})")
    res_array = ",\n".join(res_entries)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections;
using System.Reflection;

public static class VeilBreakers_ResponsiveTest_{screen_name.replace("-", "_")}
{{
    private static readonly Vector2Int[] Resolutions = new Vector2Int[]
    {{
{res_array}
    }};

    [MenuItem("VeilBreakers/UI/Responsive Test {screen_name}")]
    public static void Execute()
    {{
        string outputDir = "Assets/Screenshots/Responsive";
        if (!Directory.Exists(outputDir))
        {{
            Directory.CreateDirectory(outputDir);
        }}

        var results = new System.Collections.Generic.List<string>();

        foreach (var res in Resolutions)
        {{
            try
            {{
                SetGameViewSize(res.x, res.y);

                // Force a repaint so the layout updates
                EditorApplication.QueuePlayerLoopUpdate();

                string filename = $"{screen_name}_{{res.x}}x{{res.y}}.png";
                string path = Path.Combine(outputDir, filename);
                ScreenCapture.CaptureScreenshot(path, 1);

                results.Add($"  \\\"{{res.x}}x{{res.y}}\\\": \\\"{{path}}\\\"");
                Debug.Log($"[VeilBreakers] Captured responsive screenshot: {{path}}");
            }}
            catch (System.Exception ex)
            {{
                results.Add($"  \\\"{{res.x}}x{{res.y}}\\\": \\\"ERROR: {{ex.Message}}\\\"");
                Debug.LogWarning($"[VeilBreakers] Failed to capture at {{res.x}}x{{res.y}}: {{ex.Message}}");
            }}
        }}

        string json = "{{\\\"status\\\": \\\"success\\\", \\\"action\\\": \\\"responsive_test\\\", \\\"screen\\\": \\\"{screen_name}\\\", \\\"captures\\\": {{" + string.Join(", ", results) + "}}}}";
        File.WriteAllText("Temp/vb_result.json", json);
        Debug.Log("[VeilBreakers] Responsive test complete for {screen_name}.");
    }}

    private static void SetGameViewSize(int width, int height)
    {{
        // Access internal GameView API via reflection
        var gameViewType = System.Type.GetType("UnityEditor.GameView, UnityEditor");
        if (gameViewType == null)
        {{
            Debug.LogWarning("[VeilBreakers] Cannot access GameView type via reflection.");
            return;
        }}

        var window = EditorWindow.GetWindow(gameViewType);
        var positionProp = gameViewType.GetProperty("position",
            BindingFlags.Public | BindingFlags.Instance);

        if (positionProp != null)
        {{
            positionProp.SetValue(window, new Rect(0, 0, width, height));
        }}

        window.Repaint();
    }}
}}
'''


# ---------------------------------------------------------------------------
# UXML layout validation (pure string/XML parsing)
# ---------------------------------------------------------------------------

_SIZE_PATTERN = re.compile(
    r"(?:^|;)\s*(?:width|height)\s*:\s*(\d+(?:\.\d+)?)(px|%)?\s*",
    re.IGNORECASE,
)


def _parse_style_sizes(style: str) -> dict[str, float]:
    """Extract width/height values from an inline style string.

    Returns:
        Dict with 'width' and/or 'height' if found, values in pixels.
    """
    sizes: dict[str, float] = {}
    for prop in ("width", "height"):
        match = re.search(
            rf"(?:^|;)\s*{prop}\s*:\s*(\d+(?:\.\d+)?)\s*(px|%)?\s*",
            style,
            re.IGNORECASE,
        )
        if match:
            sizes[prop] = float(match.group(1))
    return sizes


def validate_uxml_layout(uxml_string: str) -> dict[str, Any]:
    """Validate a UXML document for common layout issues.

    Checks performed:
    - Zero-size elements (explicit width=0 or height=0 in style attributes)
    - Duplicate element names
    - Overflow detection (child explicit size > parent explicit size)

    Args:
        uxml_string: Complete UXML document string.

    Returns:
        Dict with keys:
            valid (bool): True if no issues found.
            issues (list[dict]): Each issue has type, element, details.
    """
    issues: list[dict[str, str]] = []

    try:
        root = ET.fromstring(uxml_string)
    except ET.ParseError as exc:
        return {
            "valid": False,
            "issues": [
                {
                    "type": "parse_error",
                    "element": "root",
                    "details": f"Failed to parse UXML: {exc}",
                }
            ],
        }

    # Track names for duplicate detection
    seen_names: dict[str, int] = {}

    def _walk(elem: ET.Element, parent_sizes: dict[str, float] | None = None) -> None:
        # Check name duplicates
        name = elem.get("name", "")
        if name:
            seen_names[name] = seen_names.get(name, 0) + 1
            if seen_names[name] == 2:
                issues.append({
                    "type": "duplicate_name",
                    "element": name,
                    "details": f"Duplicate element name '{name}' found",
                })

        # Parse inline style for size info
        style = elem.get("style", "")
        sizes = _parse_style_sizes(style) if style else {}

        # Zero-size check
        for dim in ("width", "height"):
            if dim in sizes and sizes[dim] == 0:
                elem_id = name or elem.tag
                issues.append({
                    "type": "zero_size",
                    "element": elem_id,
                    "details": f"Element has {dim}=0",
                })

        # Overflow check: child explicit size > parent explicit size
        if parent_sizes:
            for dim in ("width", "height"):
                if dim in sizes and dim in parent_sizes:
                    if sizes[dim] > parent_sizes[dim]:
                        elem_id = name or elem.tag
                        issues.append({
                            "type": "overflow",
                            "element": elem_id,
                            "details": (
                                f"Child {dim} ({sizes[dim]}px) exceeds "
                                f"parent {dim} ({parent_sizes[dim]}px)"
                            ),
                        })

        # Recurse into children with current element's sizes as parent
        for child in elem:
            _walk(child, sizes if sizes else parent_sizes)

    _walk(root)

    return {
        "valid": len(issues) == 0,
        "issues": issues,
    }
