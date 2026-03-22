"""WCAG 2.1 AA contrast ratio checker for UI colors.

Implements the W3C relative luminance and contrast ratio formulas from
https://www.w3.org/TR/WCAG21/#dfn-contrast-ratio

Functions:
    relative_luminance  - W3C relative luminance from linear RGB (0-1)
    contrast_ratio      - Contrast ratio between two RGB colors (0-255)
    check_wcag_aa       - Pass/fail against WCAG AA thresholds
    validate_uxml_contrast - Check all text elements in UXML+USS pair
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# W3C Relative Luminance (sRGB)
# ---------------------------------------------------------------------------


def _linearize(c: float) -> float:
    """Convert an sRGB channel value (0-1) to linear RGB.

    Uses the sRGB transfer function as specified by W3C:
    - If c <= 0.04045: c / 12.92
    - Otherwise: ((c + 0.055) / 1.055) ** 2.4

    Args:
        c: sRGB channel value in [0, 1].

    Returns:
        Linear RGB value.
    """
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(r: float, g: float, b: float) -> float:
    """Calculate the relative luminance of a color.

    Uses the W3C formula:
        L = 0.2126 * R_lin + 0.7152 * G_lin + 0.0722 * B_lin

    Args:
        r: Red channel, 0-1 range.
        g: Green channel, 0-1 range.
        b: Blue channel, 0-1 range.

    Returns:
        Relative luminance value in [0, 1].
    """
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


# ---------------------------------------------------------------------------
# Contrast Ratio
# ---------------------------------------------------------------------------


def contrast_ratio(fg_rgb: tuple[int, int, int], bg_rgb: tuple[int, int, int]) -> float:
    """Calculate the contrast ratio between two colors.

    Formula: (L1 + 0.05) / (L2 + 0.05) where L1 >= L2.

    Args:
        fg_rgb: Foreground color as (R, G, B) with values 0-255.
        bg_rgb: Background color as (R, G, B) with values 0-255.

    Returns:
        Contrast ratio as a float >= 1.0 (e.g. 21.0 for black on white).
    """
    l1 = relative_luminance(fg_rgb[0] / 255, fg_rgb[1] / 255, fg_rgb[2] / 255)
    l2 = relative_luminance(bg_rgb[0] / 255, bg_rgb[1] / 255, bg_rgb[2] / 255)

    # Ensure L1 is the lighter color
    if l2 > l1:
        l1, l2 = l2, l1

    return (l1 + 0.05) / (l2 + 0.05)


# ---------------------------------------------------------------------------
# WCAG AA Check
# ---------------------------------------------------------------------------


def check_wcag_aa(
    fg: tuple[int, int, int],
    bg: tuple[int, int, int],
    large_text: bool = False,
) -> bool:
    """Check if a foreground/background color pair meets WCAG 2.1 AA.

    WCAG AA thresholds:
    - Normal text: contrast ratio >= 4.5:1
    - Large text (>= 18pt or >= 14pt bold): contrast ratio >= 3.0:1

    Args:
        fg: Foreground (text) color as (R, G, B) with values 0-255.
        bg: Background color as (R, G, B) with values 0-255.
        large_text: True if the text is large (>= 18pt or >= 14pt bold).

    Returns:
        True if the color pair meets WCAG AA requirements.
    """
    ratio = contrast_ratio(fg, bg)
    threshold = 3.0 if large_text else 4.5
    return ratio >= threshold


# ---------------------------------------------------------------------------
# USS Color Parsing
# ---------------------------------------------------------------------------

_HEX_COLOR_3 = re.compile(r"^#([0-9a-fA-F])([0-9a-fA-F])([0-9a-fA-F])$")
_HEX_COLOR_6 = re.compile(r"^#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$")
_HEX_COLOR_8 = re.compile(r"^#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})[0-9a-fA-F]{2}$")
_RGBA_PATTERN = re.compile(
    r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*[\d.]+\s*)?\)"
)


def parse_color(color_str: str) -> tuple[int, int, int] | None:
    """Parse a CSS/USS color string to (R, G, B) tuple.

    Supports: #RGB, #RRGGBB, #RRGGBBAA, rgb(r,g,b), rgba(r,g,b,a).

    Args:
        color_str: Color string.

    Returns:
        (R, G, B) tuple with values 0-255, or None if unparseable.
    """
    color_str = color_str.strip()

    # #RRGGBB
    m = _HEX_COLOR_6.match(color_str)
    if m:
        return (int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16))

    # #RRGGBBAA
    m = _HEX_COLOR_8.match(color_str)
    if m:
        return (int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16))

    # #RGB
    m = _HEX_COLOR_3.match(color_str)
    if m:
        return (
            int(m.group(1) * 2, 16),
            int(m.group(2) * 2, 16),
            int(m.group(3) * 2, 16),
        )

    # rgb() / rgba()
    m = _RGBA_PATTERN.match(color_str)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))

    return None


# ---------------------------------------------------------------------------
# USS Rule Parsing
# ---------------------------------------------------------------------------

_USS_RULE_PATTERN = re.compile(
    r"([^{]+?)\s*\{([^}]*)\}",
    re.DOTALL,
)

_COLOR_PROP_PATTERN = re.compile(
    r"(?:^|;)\s*color\s*:\s*([^;]+?)\s*(?:;|$)",
    re.MULTILINE,
)

_BG_COLOR_PROP_PATTERN = re.compile(
    r"(?:^|;)\s*background-color\s*:\s*([^;]+?)\s*(?:;|$)",
    re.MULTILINE,
)


def _parse_uss_rules(uss_string: str) -> dict[str, dict[str, Any]]:
    """Parse USS rules into a dict of selector -> properties.

    Returns:
        Dict mapping selector string to dict with optional 'color' and
        'background-color' keys as parsed (R,G,B) tuples.
    """
    rules: dict[str, dict[str, Any]] = {}

    for match in _USS_RULE_PATTERN.finditer(uss_string):
        selector = match.group(1).strip()
        body = match.group(2)

        props: dict[str, Any] = {}

        # Extract color
        color_match = _COLOR_PROP_PATTERN.search(body)
        if color_match:
            parsed = parse_color(color_match.group(1))
            if parsed:
                props["color"] = parsed

        # Extract background-color
        bg_match = _BG_COLOR_PROP_PATTERN.search(body)
        if bg_match:
            parsed = parse_color(bg_match.group(1))
            if parsed:
                props["background-color"] = parsed

        if props:
            rules[selector] = props

    return rules


# ---------------------------------------------------------------------------
# UXML + USS contrast validation
# ---------------------------------------------------------------------------


def validate_uxml_contrast(
    uxml_string: str,
    uss_string: str,
) -> list[dict[str, Any]]:
    """Validate contrast ratios for text elements in a UXML + USS pair.

    Extracts text colors and background colors from USS rules, matches
    them to UXML elements by class, and checks each pair against WCAG AA.

    Args:
        uxml_string: Complete UXML document string.
        uss_string: Complete USS stylesheet string.

    Returns:
        List of violation dicts, each with:
            element (str): Element identifier (name or class).
            foreground (tuple): (R, G, B) text color.
            background (tuple): (R, G, B) background color.
            ratio (float): Computed contrast ratio.
            required (float): Required minimum ratio.
            passes (bool): Whether it meets WCAG AA.
    """
    import defusedxml.ElementTree as ET

    violations: list[dict[str, Any]] = []

    # Parse USS rules
    rules = _parse_uss_rules(uss_string)

    # Parse UXML
    try:
        root = ET.fromstring(uxml_string)
    except ET.ParseError:
        return violations

    # Build a class -> colors mapping from USS
    class_colors: dict[str, dict[str, tuple[int, int, int]]] = {}
    for selector, props in rules.items():
        # Extract class name from selector (e.g., ".vb-button" -> "vb-button")
        # Skip pseudo-selectors like :hover
        if ":" in selector:
            continue
        class_name = selector.lstrip(".")
        if class_name:
            class_colors[class_name] = {}
            if "color" in props:
                class_colors[class_name]["color"] = props["color"]
            if "background-color" in props:
                class_colors[class_name]["background-color"] = props["background-color"]

    # Text element local names (after namespace expansion, tags become
    # e.g., "{UnityEngine.UIElements}Label" -- we match on the local part)
    _text_local_names = {"Label", "Button", "TextField", "Toggle"}

    def _local_name(tag: str) -> str:
        """Strip XML namespace URI from a tag, returning the local name."""
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    # Parse font-size from USS for large-text determination
    _font_size_re = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)\s*(px)?", re.IGNORECASE)
    class_font_sizes: dict[str, float] = {}
    for selector, _props in rules.items():
        if ":" in selector:
            continue
        cls_name = selector.lstrip(".")
        # Search the raw USS for font-size in this rule's body
        for rule_match in _USS_RULE_PATTERN.finditer(uss_string):
            if rule_match.group(1).strip() == selector:
                fs_match = _font_size_re.search(rule_match.group(2))
                if fs_match:
                    class_font_sizes[cls_name] = float(fs_match.group(1))

    # Walk all elements and check text elements
    def _walk(elem: ET.Element, inherited_bg: tuple[int, int, int] | None = None) -> None:
        classes = elem.get("class", "").split()
        name = elem.get("name", "")

        # Determine this element's background color (for children to inherit)
        current_bg = inherited_bg
        for cls in classes:
            if cls in class_colors and "background-color" in class_colors[cls]:
                current_bg = class_colors[cls]["background-color"]

        # Check if this is a text element (using local name)
        local = _local_name(elem.tag)
        if local in _text_local_names:
            fg_color = None
            for cls in classes:
                if cls in class_colors and "color" in class_colors[cls]:
                    fg_color = class_colors[cls]["color"]

            if fg_color and current_bg:
                ratio = contrast_ratio(fg_color, current_bg)

                # Determine if large text (font-size >= 24px ~= 18pt)
                is_large = False
                for cls in classes:
                    if cls in class_font_sizes and class_font_sizes[cls] >= 24:
                        is_large = True
                        break

                passes = check_wcag_aa(fg_color, current_bg, large_text=is_large)
                elem_id = name or " ".join(classes) or local

                violations.append({
                    "element": elem_id,
                    "foreground": fg_color,
                    "background": current_bg,
                    "ratio": round(ratio, 2),
                    "required": 3.0 if is_large else 4.5,
                    "passes": passes,
                })

        # Recurse
        for child in elem:
            _walk(child, current_bg)

    _walk(root)

    return violations
