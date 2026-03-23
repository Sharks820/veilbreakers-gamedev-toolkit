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
import defusedxml.ElementTree as _safe_ET  # safe parsing only
from typing import Any

from ._cs_sanitize import sanitize_cs_identifier

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
    safe_screen_name = sanitize_cs_identifier(screen_name) or "Screen"

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

public static class VeilBreakers_ResponsiveTest_{safe_screen_name}
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
        root = _safe_ET.fromstring(uxml_string)
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


# ---------------------------------------------------------------------------
# Combat HUD generation -- Dark Fantasy Action RPG
# ---------------------------------------------------------------------------

# Brand color mapping for ability borders and elemental damage
_BRAND_COLORS: dict[str, str] = {
    "IRON": "#c0c0c0",
    "SAVAGE": "#ff4500",
    "SURGE": "#00bfff",
    "VENOM": "#32cd32",
    "DREAD": "#8b008b",
    "LEECH": "#dc143c",
    "GRACE": "#ffd700",
    "MEND": "#7cfc00",
    "RUIN": "#ff6347",
    "VOID": "#4b0082",
}


def generate_combat_hud_script(
    screen_name: str = "CombatHUD",
    ability_count: int = 4,
    show_minimap: bool = True,
    show_combo_counter: bool = True,
    show_boss_bar: bool = True,
) -> dict[str, Any]:
    """Generate a complete dark fantasy combat HUD with UXML, USS, and C# backing.

    Creates an editor script that generates all three files (UXML layout,
    USS stylesheet, C# MonoBehaviour) for a fully-featured action RPG HUD.

    HUD elements:
        - Player health bar with gradient fill, damage flash, smooth lerp
        - Stamina bar with depletion/regeneration animation
        - Ability bar with cooldown radial overlay and brand-colored borders
        - Boss health bar with phase indicators
        - Status effect icons with duration timers and stacking
        - Combo counter with escalating size/color
        - Damage numbers (white normal, yellow crit, brand-colored elemental)
        - Interaction prompt ("Press E to interact")
        - Circular minimap with fog of war mask

    Args:
        screen_name: Name prefix for generated files.
        ability_count: Number of ability slots (1-8).
        show_minimap: Whether to include the minimap element.
        show_combo_counter: Whether to include the combo counter.
        show_boss_bar: Whether to include the boss health bar.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    safe_name = sanitize_cs_identifier(screen_name) or "CombatHUD"
    class_name = f"VB_{safe_name}_Generator"
    runtime_class = f"VB_{safe_name}"
    ability_count = max(1, min(8, ability_count))

    # -- Build the USS stylesheet content as an embedded string -----------
    uss_content = _build_combat_hud_uss()

    # -- Build the UXML content as an embedded string --------------------
    uxml_content = _build_combat_hud_uxml(
        ability_count=ability_count,
        show_minimap=show_minimap,
        show_combo_counter=show_combo_counter,
        show_boss_bar=show_boss_bar,
    )

    # -- Build the runtime C# MonoBehaviour ------------------------------
    runtime_cs = _build_combat_hud_runtime_cs(
        runtime_class=runtime_class,
        ability_count=ability_count,
        show_minimap=show_minimap,
        show_combo_counter=show_combo_counter,
        show_boss_bar=show_boss_bar,
    )

    # -- Build the editor generator script that writes all three files ----
    script = _build_combat_hud_editor_cs(
        class_name=class_name,
        runtime_class=runtime_class,
        safe_name=safe_name,
        uss_content=uss_content,
        uxml_content=uxml_content,
        runtime_cs=runtime_cs,
    )

    return {
        "script_path": f"Assets/Scripts/Editor/{class_name}.cs",
        "script_content": script,
        "next_steps": [
            "Save the editor script to your Unity project",
            "Call unity_editor action=recompile to compile",
            f"Run VeilBreakers > UI > Generate {safe_name} from the menu bar",
            "UXML, USS, and runtime C# will be generated automatically",
            f"Add {runtime_class} component to a GameObject with UIDocument",
            "Assign the generated UXML as the source asset on UIDocument",
        ],
    }


def _build_combat_hud_uss() -> str:
    """Build the USS stylesheet string for the combat HUD."""
    return r"""/* VeilBreakers Combat HUD -- Dark Fantasy Theme */
/* Auto-generated by veilbreakers-mcp ui_templates */

/* ---- Root ---- */
.combat-hud-root {
    position: absolute;
    left: 0; top: 0; right: 0; bottom: 0;
    flex-direction: column;
    -unity-font-style: bold;
}

/* ---- Player Vitals (top-left) ---- */
.player-vitals {
    position: absolute;
    left: 24px;
    top: 24px;
    width: 320px;
}

/* Health bar */
.health-bar-frame {
    height: 32px;
    background-color: #0d0d0d;
    border-color: #5a5a5a;
    border-width: 2px;
    border-radius: 3px;
    margin-bottom: 6px;
    overflow: hidden;
    /* Metallic rivet effect via border image */
    border-top-color: #8a8a8a;
    border-left-color: #7a7a7a;
    border-bottom-color: #3a3a3a;
    border-right-color: #4a4a4a;
}

.health-bar-fill {
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 100%;
    background-color: #8b1a1a;
    transition-duration: 0.4s;
    transition-property: width;
    border-radius: 1px;
}

.health-bar-damage-flash {
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 100%;
    background-color: #ff4444;
    opacity: 0;
    transition-duration: 0.6s;
    transition-property: width, opacity;
}

.health-text {
    position: absolute;
    left: 0; top: 0; right: 0; bottom: 0;
    -unity-text-align: middle-center;
    color: #e6e6e6;
    font-size: 14px;
    text-shadow: 1px 1px 2px #000000;
}

/* Stamina bar */
.stamina-bar-frame {
    height: 18px;
    background-color: #0d0d0d;
    border-color: #4a4a4a;
    border-width: 1px;
    border-radius: 2px;
    overflow: hidden;
    border-top-color: #6a6a6a;
    border-left-color: #5a5a5a;
    border-bottom-color: #2a2a2a;
    border-right-color: #3a3a3a;
}

.stamina-bar-fill {
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 100%;
    background-color: #daa520;
    transition-duration: 0.3s;
    transition-property: width;
    border-radius: 1px;
}

.stamina-regen-pulse {
    position: absolute;
    left: 0; top: 0; right: 0; bottom: 0;
    background-color: #ffd700;
    opacity: 0;
}

/* ---- Ability Bar (bottom-center) ---- */
.ability-bar {
    position: absolute;
    bottom: 48px;
    left: 50%;
    translate: -50% 0;
    flex-direction: row;
    align-items: flex-end;
}

.ability-slot {
    width: 64px;
    height: 64px;
    margin: 0 4px;
    background-color: #1a1a1a;
    border-color: #5a5a5a;
    border-width: 2px;
    /* Gothic arch framing via border radius */
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    border-bottom-left-radius: 3px;
    border-bottom-right-radius: 3px;
    overflow: hidden;
}

.ability-slot:hover {
    border-color: #daa520;
}

.ability-icon {
    position: absolute;
    left: 0; top: 0; right: 0; bottom: 0;
}

.ability-cooldown-overlay {
    position: absolute;
    left: 0; top: 0; right: 0; bottom: 0;
    background-color: rgba(0, 0, 0, 0.65);
    opacity: 0;
}

.ability-cooldown-text {
    position: absolute;
    left: 0; top: 0; right: 0; bottom: 0;
    -unity-text-align: middle-center;
    color: #ffffff;
    font-size: 18px;
    text-shadow: 1px 1px 2px #000000;
    opacity: 0;
}

.ability-key-label {
    position: absolute;
    bottom: 2px;
    right: 4px;
    color: #b0b0b0;
    font-size: 11px;
    text-shadow: 1px 1px 1px #000000;
}

/* Brand-colored borders */
.ability-slot--iron   { border-color: #c0c0c0; }
.ability-slot--savage { border-color: #ff4500; }
.ability-slot--surge  { border-color: #00bfff; }
.ability-slot--venom  { border-color: #32cd32; }
.ability-slot--dread  { border-color: #8b008b; }
.ability-slot--leech  { border-color: #dc143c; }
.ability-slot--grace  { border-color: #ffd700; }
.ability-slot--mend   { border-color: #7cfc00; }
.ability-slot--ruin   { border-color: #ff6347; }
.ability-slot--void   { border-color: #4b0082; }

/* ---- Boss Health Bar (top-center) ---- */
.boss-bar-container {
    position: absolute;
    top: 24px;
    left: 50%;
    translate: -50% 0;
    width: 500px;
    align-items: center;
    opacity: 0;
    transition-duration: 0.5s;
    transition-property: opacity;
}

.boss-bar-container--visible {
    opacity: 1;
}

.boss-name {
    color: #daa520;
    font-size: 20px;
    -unity-text-align: middle-center;
    margin-bottom: 4px;
    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.8);
    -unity-font-style: bold;
}

.boss-bar-frame {
    width: 100%;
    height: 24px;
    background-color: #0d0d0d;
    border-color: #daa520;
    border-width: 2px;
    border-radius: 2px;
    overflow: hidden;
}

.boss-bar-fill {
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 100%;
    background-color: #8b1a1a;
    transition-duration: 0.5s;
    transition-property: width;
}

.boss-phase-indicators {
    flex-direction: row;
    justify-content: center;
    margin-top: 4px;
}

.boss-phase-pip {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background-color: #3a3a3a;
    border-color: #daa520;
    border-width: 1px;
    margin: 0 3px;
}

.boss-phase-pip--active {
    background-color: #daa520;
}

/* ---- Status Effects (below player vitals) ---- */
.status-effects-row {
    position: absolute;
    left: 24px;
    top: 96px;
    flex-direction: row;
    flex-wrap: wrap;
    max-width: 320px;
}

.status-icon-slot {
    width: 36px;
    height: 36px;
    margin: 2px;
    background-color: #1a1a1a;
    border-color: #4a4a4a;
    border-width: 1px;
    border-radius: 4px;
    overflow: hidden;
    align-items: center;
    justify-content: flex-end;
}

.status-icon-image {
    position: absolute;
    left: 0; top: 0; right: 0; bottom: 0;
}

.status-duration-text {
    color: #ffffff;
    font-size: 10px;
    text-shadow: 1px 1px 1px #000000;
    -unity-text-align: lower-center;
}

.status-stack-count {
    position: absolute;
    top: 0;
    right: 1px;
    color: #ffd700;
    font-size: 10px;
    text-shadow: 1px 1px 1px #000000;
    -unity-font-style: bold;
}

/* ---- Combo Counter (center-right) ---- */
.combo-container {
    position: absolute;
    right: 120px;
    top: 40%;
    align-items: center;
    opacity: 0;
    transition-duration: 0.3s;
    transition-property: opacity;
}

.combo-container--visible {
    opacity: 1;
}

.combo-count {
    color: #daa520;
    font-size: 48px;
    -unity-font-style: bold;
    text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.9);
    transition-duration: 0.15s;
    transition-property: font-size, color;
}

.combo-label {
    color: #b0b0b0;
    font-size: 14px;
    -unity-text-align: middle-center;
    text-shadow: 1px 1px 2px #000000;
}

/* ---- Interaction Prompt (bottom-center) ---- */
.interaction-prompt {
    position: absolute;
    bottom: 140px;
    left: 50%;
    translate: -50% 0;
    background-color: rgba(13, 13, 13, 0.85);
    border-color: #5a5a5a;
    border-width: 1px;
    border-radius: 6px;
    padding: 8px 20px;
    opacity: 0;
    transition-duration: 0.25s;
    transition-property: opacity;
}

.interaction-prompt--visible {
    opacity: 1;
}

.interaction-prompt-text {
    color: #e6e6e6;
    font-size: 16px;
    -unity-text-align: middle-center;
    text-shadow: 1px 1px 2px #000000;
}

.interaction-key {
    color: #daa520;
    font-size: 18px;
    -unity-font-style: bold;
}

/* ---- Minimap (top-right) ---- */
.minimap-container {
    position: absolute;
    right: 24px;
    top: 24px;
    width: 180px;
    height: 180px;
    border-radius: 50%;
    overflow: hidden;
    border-color: #5a5a5a;
    border-width: 2px;
    background-color: #0d0d0d;
    border-top-color: #8a8a8a;
    border-left-color: #7a7a7a;
    border-bottom-color: #3a3a3a;
    border-right-color: #4a4a4a;
}

.minimap-render {
    position: absolute;
    left: 0; top: 0; right: 0; bottom: 0;
}

.minimap-fog-mask {
    position: absolute;
    left: 0; top: 0; right: 0; bottom: 0;
    opacity: 0.6;
}

.minimap-player-marker {
    position: absolute;
    left: 50%;
    top: 50%;
    translate: -50% -50%;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #daa520;
    border-color: #ffffff;
    border-width: 1px;
}

.minimap-frame-ornament {
    position: absolute;
    left: -2px; top: -2px; right: -2px; bottom: -2px;
    border-radius: 50%;
    border-color: #daa52060;
    border-width: 1px;
}

/* ---- Damage Numbers (floating) ---- */
.damage-number-container {
    position: absolute;
    left: 0; top: 0; right: 0; bottom: 0;
}

.damage-number {
    position: absolute;
    color: #ffffff;
    font-size: 22px;
    -unity-font-style: bold;
    text-shadow: 2px 2px 3px rgba(0, 0, 0, 0.9);
    opacity: 1;
    transition-duration: 0.8s;
    transition-property: translate, opacity, font-size;
}

.damage-number--crit {
    color: #ffd700;
    font-size: 30px;
}

.damage-number--iron   { color: #c0c0c0; }
.damage-number--savage { color: #ff4500; }
.damage-number--surge  { color: #00bfff; }
.damage-number--venom  { color: #32cd32; }
.damage-number--dread  { color: #8b008b; }
.damage-number--leech  { color: #dc143c; }
.damage-number--grace  { color: #ffd700; }
.damage-number--mend   { color: #7cfc00; }
.damage-number--ruin   { color: #ff6347; }
.damage-number--void   { color: #4b0082; }

/* ---- Active glow effect ---- */
.glow-active {
    border-color: #daa520;
    transition-duration: 0.5s;
    transition-property: border-color;
}
"""


def _build_combat_hud_uxml(
    ability_count: int = 4,
    show_minimap: bool = True,
    show_combo_counter: bool = True,
    show_boss_bar: bool = True,
) -> str:
    """Build the UXML layout string for the combat HUD."""
    ability_slots = ""
    default_keys = ["Q", "W", "E", "R", "1", "2", "3", "4"]
    for i in range(ability_count):
        key = default_keys[i] if i < len(default_keys) else str(i + 1)
        ability_slots += f"""
            <ui:VisualElement name="ability-slot-{i}" class="ability-slot">
                <ui:VisualElement name="ability-icon-{i}" class="ability-icon" />
                <ui:VisualElement name="ability-cooldown-{i}" class="ability-cooldown-overlay" />
                <ui:Label name="ability-cd-text-{i}" class="ability-cooldown-text" text="" />
                <ui:Label name="ability-key-{i}" class="ability-key-label" text="{key}" />
            </ui:VisualElement>"""

    boss_bar_uxml = ""
    if show_boss_bar:
        boss_bar_uxml = """
        <!-- Boss Health Bar -->
        <ui:VisualElement name="boss-bar-container" class="boss-bar-container">
            <ui:Label name="boss-name" class="boss-name" text="" />
            <ui:VisualElement name="boss-bar-frame" class="boss-bar-frame">
                <ui:VisualElement name="boss-bar-fill" class="boss-bar-fill" />
            </ui:VisualElement>
            <ui:VisualElement name="boss-phase-indicators" class="boss-phase-indicators" />
        </ui:VisualElement>"""

    combo_uxml = ""
    if show_combo_counter:
        combo_uxml = """
        <!-- Combo Counter -->
        <ui:VisualElement name="combo-container" class="combo-container">
            <ui:Label name="combo-count" class="combo-count" text="0" />
            <ui:Label name="combo-label" class="combo-label" text="HITS" />
        </ui:VisualElement>"""

    minimap_uxml = ""
    if show_minimap:
        minimap_uxml = """
        <!-- Minimap -->
        <ui:VisualElement name="minimap-container" class="minimap-container">
            <ui:VisualElement name="minimap-render" class="minimap-render" />
            <ui:VisualElement name="minimap-fog-mask" class="minimap-fog-mask" />
            <ui:VisualElement name="minimap-player-marker" class="minimap-player-marker" />
            <ui:VisualElement name="minimap-frame-ornament" class="minimap-frame-ornament" />
        </ui:VisualElement>"""

    return f"""<?xml version="1.0" encoding="utf-8"?>
<ui:UXML xmlns:ui="UnityEngine.UIElements" xmlns:uie="UnityEditor.UIElements">
    <ui:VisualElement name="combat-hud-root" class="combat-hud-root">

        <!-- Player Vitals -->
        <ui:VisualElement name="player-vitals" class="player-vitals">
            <!-- Health Bar -->
            <ui:VisualElement name="health-bar-frame" class="health-bar-frame">
                <ui:VisualElement name="health-bar-damage-flash" class="health-bar-damage-flash" />
                <ui:VisualElement name="health-bar-fill" class="health-bar-fill" />
                <ui:Label name="health-text" class="health-text" text="100 / 100" />
            </ui:VisualElement>
            <!-- Stamina Bar -->
            <ui:VisualElement name="stamina-bar-frame" class="stamina-bar-frame">
                <ui:VisualElement name="stamina-bar-fill" class="stamina-bar-fill" />
                <ui:VisualElement name="stamina-regen-pulse" class="stamina-regen-pulse" />
            </ui:VisualElement>
        </ui:VisualElement>

        <!-- Status Effects -->
        <ui:VisualElement name="status-effects-row" class="status-effects-row" />
{boss_bar_uxml}

        <!-- Ability Bar -->
        <ui:VisualElement name="ability-bar" class="ability-bar">{ability_slots}
        </ui:VisualElement>
{combo_uxml}

        <!-- Interaction Prompt -->
        <ui:VisualElement name="interaction-prompt" class="interaction-prompt">
            <ui:Label name="interaction-prompt-text" class="interaction-prompt-text" text="" />
        </ui:VisualElement>
{minimap_uxml}

        <!-- Damage Numbers Container -->
        <ui:VisualElement name="damage-number-container" class="damage-number-container" />

    </ui:VisualElement>
</ui:UXML>
"""


def _build_combat_hud_runtime_cs(
    runtime_class: str,
    ability_count: int = 4,
    show_minimap: bool = True,
    show_combo_counter: bool = True,
    show_boss_bar: bool = True,
) -> str:
    """Build the runtime C# MonoBehaviour for the combat HUD."""
    # Build ability field queries
    ability_queries = ""
    for i in range(ability_count):
        ability_queries += f"""
        _abilitySlots[{i}] = root.Q(\\"ability-slot-{i}\\");
        _abilityCooldowns[{i}] = root.Q(\\"ability-cooldown-{i}\\");
        _abilityCdTexts[{i}] = root.Q<Label>(\\"ability-cd-text-{i}\\");"""

    boss_fields = ""
    boss_init = ""
    boss_methods = ""
    if show_boss_bar:
        boss_fields = """
    private VisualElement _bossBarContainer;
    private Label _bossNameLabel;
    private VisualElement _bossBarFill;
    private VisualElement _bossPhaseIndicators;"""
        boss_init = """
        _bossBarContainer = root.Q(\\"boss-bar-container\\");
        _bossNameLabel = root.Q<Label>(\\"boss-name\\");
        _bossBarFill = root.Q(\\"boss-bar-fill\\");
        _bossPhaseIndicators = root.Q(\\"boss-phase-indicators\\");"""
        boss_methods = r"""
    public void ShowBossHealth(string bossName, float healthPercent, int phase)
    {
        if (_bossBarContainer == null) return;
        _bossBarContainer.AddToClassList(\"boss-bar-container--visible\");
        if (_bossNameLabel != null) _bossNameLabel.text = bossName;
        float clamped = Mathf.Clamp01(healthPercent);
        if (_bossBarFill != null)
            _bossBarFill.style.width = new StyleLength(new Length(clamped * 100f, LengthUnit.Percent));
        // Update phase pips
        if (_bossPhaseIndicators != null)
        {
            _bossPhaseIndicators.Clear();
            for (int i = 0; i < Mathf.Max(phase, 1); i++)
            {
                var pip = new VisualElement();
                pip.AddToClassList(\"boss-phase-pip\");
                if (i < phase) pip.AddToClassList(\"boss-phase-pip--active\");
                _bossPhaseIndicators.Add(pip);
            }
        }
    }

    public void HideBossHealth()
    {
        if (_bossBarContainer != null)
            _bossBarContainer.RemoveFromClassList(\"boss-bar-container--visible\");
    }
"""

    combo_fields = ""
    combo_init = ""
    combo_methods = ""
    if show_combo_counter:
        combo_fields = """
    private VisualElement _comboContainer;
    private Label _comboCount;
    private float _comboTimer;"""
        combo_init = """
        _comboContainer = root.Q(\\"combo-container\\");
        _comboCount = root.Q<Label>(\\"combo-count\\");"""
        combo_methods = r"""
    public void UpdateComboCount(int count)
    {
        if (_comboContainer == null || _comboCount == null) return;
        if (count > 0)
        {
            _comboContainer.AddToClassList(\"combo-container--visible\");
            _comboCount.text = count.ToString();
            // Escalate size: base 48, +2 per hit, cap at 72
            int fontSize = Mathf.Min(48 + count * 2, 72);
            _comboCount.style.fontSize = fontSize;
            // Escalate color: gold -> red at 20+ hits
            float t = Mathf.Clamp01(count / 20f);
            Color c = Color.Lerp(new Color(0.855f, 0.647f, 0.125f), Color.red, t);
            _comboCount.style.color = c;
            _comboTimer = 3f;
        }
        else
        {
            _comboContainer.RemoveFromClassList(\"combo-container--visible\");
            _comboTimer = 0f;
        }
    }
"""

    minimap_fields = ""
    minimap_init = ""
    if show_minimap:
        minimap_fields = """
    private VisualElement _minimapContainer;
    private VisualElement _minimapRender;
    private VisualElement _minimapFogMask;"""
        minimap_init = """
        _minimapContainer = root.Q(\\"minimap-container\\");
        _minimapRender = root.Q(\\"minimap-render\\");
        _minimapFogMask = root.Q(\\"minimap-fog-mask\\");"""

    return f"""using UnityEngine;
using UnityEngine.UIElements;

[RequireComponent(typeof(UIDocument))]
public class {runtime_class} : MonoBehaviour
{{
    // ---- Cached references ----
    private VisualElement _root;

    // Health
    private VisualElement _healthBarFill;
    private VisualElement _healthBarDamageFlash;
    private Label _healthText;
    private float _displayedHealth;
    private float _targetHealth;
    private float _maxHealth = 100f;
    private float _damageFlashTimer;

    // Stamina
    private VisualElement _staminaBarFill;
    private VisualElement _staminaRegenPulse;
    private float _displayedStamina;
    private float _targetStamina;
    private float _maxStamina = 100f;
    private bool _isRegenerating;

    // Abilities
    private VisualElement[] _abilitySlots = new VisualElement[{ability_count}];
    private VisualElement[] _abilityCooldowns = new VisualElement[{ability_count}];
    private Label[] _abilityCdTexts = new Label[{ability_count}];
{boss_fields}
{combo_fields}
{minimap_fields}

    // Status effects
    private VisualElement _statusEffectsRow;

    // Interaction prompt
    private VisualElement _interactionPrompt;
    private Label _interactionPromptText;

    // Damage numbers
    private VisualElement _damageNumberContainer;

    private void OnEnable()
    {{
        var doc = GetComponent<UIDocument>();
        if (doc == null || doc.rootVisualElement == null) return;
        var root = doc.rootVisualElement;
        _root = root;

        // Health
        _healthBarFill = root.Q(\\"health-bar-fill\\");
        _healthBarDamageFlash = root.Q(\\"health-bar-damage-flash\\");
        _healthText = root.Q<Label>(\\"health-text\\");
        _displayedHealth = _maxHealth;
        _targetHealth = _maxHealth;

        // Stamina
        _staminaBarFill = root.Q(\\"stamina-bar-fill\\");
        _staminaRegenPulse = root.Q(\\"stamina-regen-pulse\\");
        _displayedStamina = _maxStamina;
        _targetStamina = _maxStamina;

        // Abilities{ability_queries}
{boss_init}
{combo_init}
{minimap_init}

        // Status effects
        _statusEffectsRow = root.Q(\\"status-effects-row\\");

        // Interaction
        _interactionPrompt = root.Q(\\"interaction-prompt\\");
        _interactionPromptText = root.Q<Label>(\\"interaction-prompt-text\\");

        // Damage numbers
        _damageNumberContainer = root.Q(\\"damage-number-container\\");
    }}

    private void Update()
    {{
        float dt = Time.deltaTime;

        // Smooth health lerp
        if (Mathf.Abs(_displayedHealth - _targetHealth) > 0.1f)
        {{
            _displayedHealth = Mathf.Lerp(_displayedHealth, _targetHealth, dt * 8f);
            ApplyHealthVisual();
        }}

        // Damage flash decay
        if (_damageFlashTimer > 0f)
        {{
            _damageFlashTimer -= dt;
            if (_healthBarDamageFlash != null)
                _healthBarDamageFlash.style.opacity = Mathf.Max(0f, _damageFlashTimer / 0.6f);
        }}

        // Smooth stamina lerp
        if (Mathf.Abs(_displayedStamina - _targetStamina) > 0.1f)
        {{
            _displayedStamina = Mathf.Lerp(_displayedStamina, _targetStamina, dt * 10f);
            ApplyStaminaVisual();
        }}

        // Stamina regen pulse
        if (_isRegenerating && _staminaRegenPulse != null)
        {{
            float pulse = (Mathf.Sin(Time.time * 4f) + 1f) * 0.15f;
            _staminaRegenPulse.style.opacity = pulse;
        }}
    }}

    // ---- Public API ----

    public void UpdateHealth(float current, float max)
    {{
        _maxHealth = Mathf.Max(max, 1f);
        float prev = _targetHealth;
        _targetHealth = Mathf.Clamp(current, 0f, _maxHealth);

        // Trigger damage flash on health loss
        if (_targetHealth < prev && _healthBarDamageFlash != null)
        {{
            _healthBarDamageFlash.style.width =
                new StyleLength(new Length((prev / _maxHealth) * 100f, LengthUnit.Percent));
            _healthBarDamageFlash.style.opacity = 1f;
            _damageFlashTimer = 0.6f;
        }}

        ApplyHealthVisual();
    }}

    public void UpdateStamina(float current, float max)
    {{
        _maxStamina = Mathf.Max(max, 1f);
        float prev = _targetStamina;
        _targetStamina = Mathf.Clamp(current, 0f, _maxStamina);
        _isRegenerating = _targetStamina > prev;

        if (!_isRegenerating && _staminaRegenPulse != null)
            _staminaRegenPulse.style.opacity = 0f;

        ApplyStaminaVisual();
    }}

    public void SetAbilityCooldown(int slot, float remaining, float total)
    {{
        if (slot < 0 || slot >= _abilityCooldowns.Length) return;
        var overlay = _abilityCooldowns[slot];
        var cdText = _abilityCdTexts[slot];
        if (overlay == null) return;

        if (remaining <= 0f || total <= 0f)
        {{
            overlay.style.opacity = 0f;
            if (cdText != null) {{ cdText.style.opacity = 0f; cdText.text = \\"\\"; }}
        }}
        else
        {{
            float ratio = Mathf.Clamp01(remaining / total);
            overlay.style.opacity = 1f;
            overlay.style.height = new StyleLength(new Length(ratio * 100f, LengthUnit.Percent));
            if (cdText != null)
            {{
                cdText.style.opacity = 1f;
                cdText.text = Mathf.CeilToInt(remaining).ToString();
            }}
        }}
    }}
{boss_methods}{combo_methods}
    public void AddStatusIcon(Sprite icon, float duration, int stacks)
    {{
        if (_statusEffectsRow == null) return;

        var slot = new VisualElement();
        slot.AddToClassList(\\"status-icon-slot\\");

        var img = new VisualElement();
        img.AddToClassList(\\"status-icon-image\\");
        if (icon != null && icon.texture != null)
            img.style.backgroundImage = new StyleBackground(icon.texture);
        slot.Add(img);

        if (duration > 0f)
        {{
            var dur = new Label();
            dur.AddToClassList(\\"status-duration-text\\");
            dur.text = Mathf.CeilToInt(duration).ToString();
            slot.Add(dur);
        }}

        if (stacks > 1)
        {{
            var sc = new Label();
            sc.AddToClassList(\\"status-stack-count\\");
            sc.text = stacks.ToString();
            slot.Add(sc);
        }}

        _statusEffectsRow.Add(slot);
    }}

    public void ShowInteractionPrompt(string text)
    {{
        if (_interactionPrompt == null) return;
        _interactionPrompt.AddToClassList(\\"interaction-prompt--visible\\");
        if (_interactionPromptText != null) _interactionPromptText.text = text;
    }}

    public void HideInteractionPrompt()
    {{
        if (_interactionPrompt != null)
            _interactionPrompt.RemoveFromClassList(\\"interaction-prompt--visible\\");
    }}

    // ---- Internal ----

    private void ApplyHealthVisual()
    {{
        if (_healthBarFill == null) return;
        float pct = (_maxHealth > 0f) ? _displayedHealth / _maxHealth : 0f;
        _healthBarFill.style.width = new StyleLength(new Length(pct * 100f, LengthUnit.Percent));

        // Gradient: green -> yellow -> red
        Color barColor;
        if (pct > 0.5f)
            barColor = Color.Lerp(new Color(0.8f, 0.8f, 0f), new Color(0.2f, 0.8f, 0.2f), (pct - 0.5f) * 2f);
        else
            barColor = Color.Lerp(new Color(0.545f, 0.102f, 0.102f), new Color(0.8f, 0.8f, 0f), pct * 2f);

        _healthBarFill.style.backgroundColor = barColor;

        if (_healthText != null)
            _healthText.text = $\\"{{Mathf.CeilToInt(_displayedHealth)}} / {{Mathf.CeilToInt(_maxHealth)}}\\";
    }}

    private void ApplyStaminaVisual()
    {{
        if (_staminaBarFill == null) return;
        float pct = (_maxStamina > 0f) ? _displayedStamina / _maxStamina : 0f;
        _staminaBarFill.style.width = new StyleLength(new Length(pct * 100f, LengthUnit.Percent));
    }}
}}
"""


def _build_combat_hud_editor_cs(
    class_name: str,
    runtime_class: str,
    safe_name: str,
    uss_content: str,
    uxml_content: str,
    runtime_cs: str,
) -> str:
    """Build the editor C# script that generates UXML + USS + runtime C#."""
    # Escape the embedded content for C# verbatim strings
    # In verbatim strings, double-quotes are escaped as ""
    uss_escaped = uss_content.replace('"', '""')
    uxml_escaped = uxml_content.replace('"', '""')
    runtime_escaped = runtime_cs.replace('"', '""')

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class {class_name}
{{
    [MenuItem("VeilBreakers/UI/Generate {safe_name}")]
    public static void Execute()
    {{
        // ---- Paths ----
        string ussDir = "Assets/UI/Styles";
        string uxmlDir = "Assets/UI/Layouts";
        string runtimeDir = "Assets/Scripts/Runtime/UI";

        string ussPath = Path.Combine(ussDir, "{safe_name}.uss");
        string uxmlPath = Path.Combine(uxmlDir, "{safe_name}.uxml");
        string runtimePath = Path.Combine(runtimeDir, "{runtime_class}.cs");

        // ---- Ensure directories ----
        foreach (var dir in new[] {{ ussDir, uxmlDir, runtimeDir }})
        {{
            if (!Directory.Exists(dir))
                Directory.CreateDirectory(dir);
        }}

        // ---- Write USS ----
        string ussContent = @"{uss_escaped}";
        File.WriteAllText(ussPath, ussContent);
        Debug.Log($"[VeilBreakers] Generated USS: {{ussPath}}");

        // ---- Write UXML ----
        string uxmlContent = @"{uxml_escaped}";
        File.WriteAllText(uxmlPath, uxmlContent);
        Debug.Log($"[VeilBreakers] Generated UXML: {{uxmlPath}}");

        // ---- Write Runtime C# ----
        string runtimeContent = @"{runtime_escaped}";
        File.WriteAllText(runtimePath, runtimeContent);
        Debug.Log($"[VeilBreakers] Generated Runtime script: {{runtimePath}}");

        AssetDatabase.Refresh();

        // ---- Result JSON ----
        string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"generate_combat_hud\\", "
            + "\\"uss_path\\": \\"" + ussPath.Replace("\\\\", "/") + "\\", "
            + "\\"uxml_path\\": \\"" + uxmlPath.Replace("\\\\", "/") + "\\", "
            + "\\"runtime_path\\": \\"" + runtimePath.Replace("\\\\", "/") + "\\"}}";
        File.WriteAllText("Temp/vb_result.json", json);
        Debug.Log("[VeilBreakers] Combat HUD generation complete.");
    }}
}}
'''
