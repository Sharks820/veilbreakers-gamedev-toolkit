"""Tests for UXML layout validation.

Validates that:
- Zero-size elements are detected
- Duplicate element names are flagged
- Overflow (child > parent size) is detected
- Valid UXML returns no issues
- Parse errors are reported gracefully
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.ui_templates import (
    generate_uxml_screen,
    validate_uxml_layout,
)


# ---------------------------------------------------------------------------
# Valid UXML -- no issues
# ---------------------------------------------------------------------------


class TestValidUxml:
    """Tests that valid UXML returns clean validation results."""

    def test_simple_valid_uxml(self):
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:VisualElement class="screen-root">
                <ui:Label text="Hello" name="lbl-hello" />
            </ui:VisualElement>
        </ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is True
        assert result["issues"] == []

    def test_generated_uxml_is_valid(self):
        """UXML from generate_uxml_screen should pass validation."""
        spec = {
            "title": "Test",
            "elements": [
                {"type": "button", "text": "OK", "name": "btn-ok"},
                {"type": "label", "text": "Info", "name": "lbl-info"},
            ],
        }
        uxml = generate_uxml_screen(spec)
        # Remove XML declaration for parsing
        body = uxml.split("\n", 1)[1]
        result = validate_uxml_layout(body)
        assert result["valid"] is True

    def test_elements_with_valid_sizes(self):
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:VisualElement style="width: 400px; height: 300px;">
                <ui:Label text="Fits" style="width: 200px; height: 100px;" />
            </ui:VisualElement>
        </ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is True

    def test_no_style_attributes_is_valid(self):
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:VisualElement>
                <ui:Label text="No style" />
                <ui:Button text="Click" />
            </ui:VisualElement>
        </ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# Zero-size detection
# ---------------------------------------------------------------------------


class TestZeroSizeDetection:
    """Tests that zero-size elements are flagged."""

    def test_zero_width_detected(self):
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:VisualElement name="zero-w" style="width: 0px; height: 100px;" />
        </ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is False
        assert any(i["type"] == "zero_size" for i in result["issues"])
        assert any("width=0" in i["details"] for i in result["issues"])

    def test_zero_height_detected(self):
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:VisualElement name="zero-h" style="width: 100px; height: 0px;" />
        </ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is False
        assert any(i["type"] == "zero_size" for i in result["issues"])
        assert any("height=0" in i["details"] for i in result["issues"])

    def test_zero_width_without_unit(self):
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:VisualElement name="no-unit" style="width: 0; height: 50px;" />
        </ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is False
        assert any(i["type"] == "zero_size" for i in result["issues"])

    def test_nonzero_size_passes(self):
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:VisualElement name="ok" style="width: 100px; height: 50px;" />
        </ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# Duplicate name detection
# ---------------------------------------------------------------------------


class TestDuplicateNameDetection:
    """Tests that duplicate element names are flagged."""

    def test_duplicate_name_detected(self):
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:Label text="A" name="my-label" />
            <ui:Label text="B" name="my-label" />
        </ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is False
        assert any(i["type"] == "duplicate_name" for i in result["issues"])
        assert any("my-label" in i["element"] for i in result["issues"])

    def test_unique_names_pass(self):
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:Label text="A" name="label-a" />
            <ui:Label text="B" name="label-b" />
        </ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is True

    def test_triple_duplicate_produces_one_issue(self):
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:Label name="dup" />
            <ui:Label name="dup" />
            <ui:Label name="dup" />
        </ui:UXML>"""
        result = validate_uxml_layout(uxml)
        dup_issues = [i for i in result["issues"] if i["type"] == "duplicate_name"]
        # Should report the duplicate (flagged when seen the 2nd time)
        assert len(dup_issues) >= 1

    def test_no_name_attribute_is_fine(self):
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:Label text="No name" />
            <ui:Label text="Also no name" />
        </ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# Overflow detection
# ---------------------------------------------------------------------------


class TestOverflowDetection:
    """Tests that child > parent explicit sizes are flagged."""

    def test_child_width_exceeds_parent(self):
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:VisualElement name="parent" style="width: 200px; height: 200px;">
                <ui:VisualElement name="child" style="width: 300px; height: 100px;" />
            </ui:VisualElement>
        </ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is False
        assert any(i["type"] == "overflow" for i in result["issues"])
        assert any("width" in i["details"] for i in result["issues"])

    def test_child_height_exceeds_parent(self):
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:VisualElement name="parent" style="width: 200px; height: 200px;">
                <ui:VisualElement name="child" style="width: 100px; height: 500px;" />
            </ui:VisualElement>
        </ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is False
        assert any(i["type"] == "overflow" for i in result["issues"])
        assert any("height" in i["details"] for i in result["issues"])

    def test_child_within_parent_passes(self):
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:VisualElement style="width: 400px; height: 300px;">
                <ui:VisualElement style="width: 200px; height: 150px;" />
            </ui:VisualElement>
        </ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is True

    def test_no_explicit_sizes_no_overflow(self):
        """Without explicit sizes, overflow cannot be detected."""
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:VisualElement>
                <ui:VisualElement />
            </ui:VisualElement>
        </ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# Parse error handling
# ---------------------------------------------------------------------------


class TestParseErrorHandling:
    """Tests that malformed UXML is handled gracefully."""

    def test_invalid_xml_returns_parse_error(self):
        result = validate_uxml_layout("<not valid xml<><>")
        assert result["valid"] is False
        assert any(i["type"] == "parse_error" for i in result["issues"])

    def test_empty_string_returns_parse_error(self):
        result = validate_uxml_layout("")
        assert result["valid"] is False
        assert any(i["type"] == "parse_error" for i in result["issues"])
