"""Tests for UXML/USS generators and responsive test script generation.

Validates that:
- UXML generation produces valid XML parseable by xml.etree
- USS contains expected selectors and dark fantasy colors
- Responsive test script contains resolution values and C# structure
"""

import xml.etree.ElementTree as ET

import pytest

from veilbreakers_mcp.shared.unity_templates.ui_templates import (
    generate_uxml_screen,
    generate_uss_stylesheet,
    generate_responsive_test_script,
    DEFAULT_RESOLUTIONS,
)


# ---------------------------------------------------------------------------
# UXML screen generation
# ---------------------------------------------------------------------------


class TestGenerateUxmlScreen:
    """Tests for generate_uxml_screen()."""

    def test_produces_valid_xml(self):
        spec = {"title": "Test Screen", "elements": []}
        result = generate_uxml_screen(spec)
        # Should parse without error
        ET.fromstring(result.split("\n", 1)[1])  # skip XML declaration line

    def test_contains_xml_declaration(self):
        result = generate_uxml_screen({"title": "Test", "elements": []})
        assert '<?xml version="1.0"' in result

    def test_contains_xmlns_declaration(self):
        result = generate_uxml_screen({"title": "Test", "elements": []})
        assert 'xmlns:ui="UnityEngine.UIElements"' in result

    def test_contains_screen_root_class(self):
        result = generate_uxml_screen({"title": "Test", "elements": []})
        assert 'class="screen-root"' in result

    def test_contains_title_label(self):
        result = generate_uxml_screen({"title": "My HUD", "elements": []})
        assert 'text="My HUD"' in result
        assert 'class="vb-title"' in result

    def test_no_title_when_empty(self):
        result = generate_uxml_screen({"title": "", "elements": []})
        assert "vb-title" not in result

    def test_button_element(self):
        spec = {
            "title": "Menu",
            "elements": [
                {"type": "button", "text": "Start Game", "name": "btn-start"},
            ],
        }
        result = generate_uxml_screen(spec)
        assert 'text="Start Game"' in result
        assert 'name="btn-start"' in result
        assert "ui:Button" in result

    def test_label_element(self):
        spec = {
            "title": "",
            "elements": [
                {"type": "label", "text": "Health: 100", "name": "lbl-health"},
            ],
        }
        result = generate_uxml_screen(spec)
        assert "ui:Label" in result
        assert 'text="Health: 100"' in result

    def test_panel_element(self):
        spec = {
            "title": "",
            "elements": [{"type": "panel", "name": "main-panel"}],
        }
        result = generate_uxml_screen(spec)
        assert 'name="main-panel"' in result

    def test_input_element(self):
        spec = {
            "title": "",
            "elements": [{"type": "input", "text": "Enter name", "name": "txt-name"}],
        }
        result = generate_uxml_screen(spec)
        assert "ui:TextField" in result
        assert 'text="Enter name"' in result

    def test_slider_element(self):
        spec = {
            "title": "",
            "elements": [{"type": "slider", "name": "sld-volume"}],
        }
        result = generate_uxml_screen(spec)
        assert "ui:Slider" in result
        assert 'name="sld-volume"' in result

    def test_toggle_element(self):
        spec = {
            "title": "",
            "elements": [{"type": "toggle", "text": "Enable VSync", "name": "tgl-vsync"}],
        }
        result = generate_uxml_screen(spec)
        assert "ui:Toggle" in result
        assert 'text="Enable VSync"' in result

    def test_nested_children(self):
        spec = {
            "title": "",
            "elements": [
                {
                    "type": "panel",
                    "name": "parent",
                    "children": [
                        {"type": "label", "text": "Child Label"},
                        {"type": "button", "text": "Child Button"},
                    ],
                }
            ],
        }
        result = generate_uxml_screen(spec)
        assert 'name="parent"' in result
        assert 'text="Child Label"' in result
        assert 'text="Child Button"' in result

    def test_custom_class_override(self):
        spec = {
            "title": "",
            "elements": [
                {"type": "button", "text": "Custom", "class": "my-custom-class"},
            ],
        }
        result = generate_uxml_screen(spec)
        assert 'class="my-custom-class"' in result

    def test_default_class_applied(self):
        spec = {
            "title": "",
            "elements": [{"type": "button", "text": "Default"}],
        }
        result = generate_uxml_screen(spec)
        assert 'class="vb-button"' in result

    def test_complex_screen_valid_xml(self):
        """Full HUD-like screen parses as valid XML."""
        spec = {
            "title": "VeilBreakers HUD",
            "elements": [
                {
                    "type": "panel",
                    "name": "top-bar",
                    "children": [
                        {"type": "label", "text": "HP: 100/100", "name": "hp"},
                        {"type": "label", "text": "MP: 50/50", "name": "mp"},
                    ],
                },
                {"type": "button", "text": "Inventory", "name": "btn-inv"},
                {"type": "slider", "name": "sld-audio"},
                {"type": "toggle", "text": "Fullscreen", "name": "tgl-fs"},
            ],
        }
        result = generate_uxml_screen(spec)
        # Parse the UXML body (skip XML declaration)
        body = result.split("\n", 1)[1]
        root = ET.fromstring(body)
        # Should have a screen-root child
        screen_root = root.find(".//{http://unity3d.com/ns}VisualElement")
        # Just verify it parsed at all
        assert root is not None

    def test_empty_elements_list(self):
        result = generate_uxml_screen({"title": "Empty", "elements": []})
        assert "ui:UXML" in result
        assert 'text="Empty"' in result


# ---------------------------------------------------------------------------
# USS stylesheet generation
# ---------------------------------------------------------------------------


class TestGenerateUssStylesheet:
    """Tests for generate_uss_stylesheet()."""

    def test_contains_screen_root_selector(self):
        result = generate_uss_stylesheet()
        assert ".screen-root" in result

    def test_contains_vb_title_selector(self):
        result = generate_uss_stylesheet()
        assert ".vb-title" in result

    def test_contains_vb_button_selector(self):
        result = generate_uss_stylesheet()
        assert ".vb-button" in result

    def test_contains_button_hover_selector(self):
        result = generate_uss_stylesheet()
        assert ".vb-button:hover" in result

    def test_contains_vb_label_selector(self):
        result = generate_uss_stylesheet()
        assert ".vb-label" in result

    def test_contains_vb_panel_selector(self):
        result = generate_uss_stylesheet()
        assert ".vb-panel" in result

    def test_contains_vb_input_selector(self):
        result = generate_uss_stylesheet()
        assert ".vb-input" in result

    def test_contains_vb_slider_selector(self):
        result = generate_uss_stylesheet()
        assert ".vb-slider" in result

    def test_contains_vb_toggle_selector(self):
        result = generate_uss_stylesheet()
        assert ".vb-toggle" in result

    def test_dark_fantasy_background_color(self):
        result = generate_uss_stylesheet(theme="dark_fantasy")
        assert "#1a1a2e" in result

    def test_dark_fantasy_text_color(self):
        result = generate_uss_stylesheet(theme="dark_fantasy")
        assert "#e6e6ff" in result

    def test_dark_fantasy_accent_color(self):
        result = generate_uss_stylesheet(theme="dark_fantasy")
        assert "#4a0e4e" in result

    def test_dark_fantasy_hover_glow_color(self):
        result = generate_uss_stylesheet(theme="dark_fantasy")
        assert "#7b2d8e" in result

    def test_unknown_theme_raises(self):
        with pytest.raises(ValueError, match="Unknown theme"):
            generate_uss_stylesheet(theme="neon_cyberpunk")

    def test_output_is_nonempty_string(self):
        result = generate_uss_stylesheet()
        assert isinstance(result, str)
        assert len(result) > 100


# ---------------------------------------------------------------------------
# Responsive test script
# ---------------------------------------------------------------------------


class TestGenerateResponsiveTestScript:
    """Tests for generate_responsive_test_script()."""

    def test_contains_csharp_class(self):
        result = generate_responsive_test_script("Assets/UI/hud.uxml")
        assert "public static class" in result

    def test_contains_menu_item(self):
        result = generate_responsive_test_script("Assets/UI/hud.uxml")
        assert "[MenuItem(" in result
        assert "VeilBreakers/UI/Responsive Test" in result

    def test_contains_default_resolutions(self):
        result = generate_responsive_test_script("Assets/UI/hud.uxml")
        for w, h in DEFAULT_RESOLUTIONS:
            assert f"new Vector2Int({w}, {h})" in result

    def test_contains_screen_capture(self):
        result = generate_responsive_test_script("Assets/UI/hud.uxml")
        assert "ScreenCapture.CaptureScreenshot" in result

    def test_screen_name_in_output(self):
        result = generate_responsive_test_script("Assets/UI/inventory.uxml")
        assert "inventory" in result

    def test_custom_resolutions(self):
        custom = [(640, 480), (1024, 768)]
        result = generate_responsive_test_script("Assets/UI/test.uxml", resolutions=custom)
        assert "new Vector2Int(640, 480)" in result
        assert "new Vector2Int(1024, 768)" in result
        # Default resolutions should NOT appear
        assert "new Vector2Int(3840, 2160)" not in result

    def test_contains_using_statements(self):
        result = generate_responsive_test_script("Assets/UI/hud.uxml")
        assert "using UnityEditor;" in result
        assert "using UnityEngine;" in result

    def test_contains_result_json(self):
        result = generate_responsive_test_script("Assets/UI/hud.uxml")
        assert "vb_result.json" in result

    def test_screenshot_directory_creation(self):
        result = generate_responsive_test_script("Assets/UI/hud.uxml")
        assert "Assets/Screenshots/Responsive" in result
