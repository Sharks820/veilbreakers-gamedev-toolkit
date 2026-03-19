"""Tests for WCAG 2.1 AA contrast ratio checker.

Validates that:
- Relative luminance matches W3C spec for known colors
- Contrast ratio is correctly computed (black/white = 21:1)
- WCAG AA check passes/fails at correct thresholds
- USS color parsing handles hex and rgb() formats
- UXML+USS contrast validation finds violations
"""

import pytest

from veilbreakers_mcp.shared.wcag_checker import (
    relative_luminance,
    contrast_ratio,
    check_wcag_aa,
    parse_color,
    validate_uxml_contrast,
)


# ---------------------------------------------------------------------------
# Relative luminance
# ---------------------------------------------------------------------------


class TestRelativeLuminance:
    """Tests for the W3C relative luminance formula."""

    def test_black_luminance_is_zero(self):
        assert relative_luminance(0.0, 0.0, 0.0) == pytest.approx(0.0, abs=1e-6)

    def test_white_luminance_is_one(self):
        assert relative_luminance(1.0, 1.0, 1.0) == pytest.approx(1.0, abs=1e-4)

    def test_pure_red_luminance(self):
        # Red channel only: L = 0.2126 * linearize(1.0)
        result = relative_luminance(1.0, 0.0, 0.0)
        assert result == pytest.approx(0.2126, abs=1e-4)

    def test_pure_green_luminance(self):
        result = relative_luminance(0.0, 1.0, 0.0)
        assert result == pytest.approx(0.7152, abs=1e-4)

    def test_pure_blue_luminance(self):
        result = relative_luminance(0.0, 0.0, 1.0)
        assert result == pytest.approx(0.0722, abs=1e-4)

    def test_mid_gray_luminance(self):
        # sRGB 0.5 is in the > 0.04045 branch
        result = relative_luminance(0.5, 0.5, 0.5)
        assert 0.1 < result < 0.3  # Mid-gray is about 0.214


# ---------------------------------------------------------------------------
# Contrast ratio
# ---------------------------------------------------------------------------


class TestContrastRatio:
    """Tests for contrast ratio computation."""

    def test_black_on_white_is_21(self):
        ratio = contrast_ratio((0, 0, 0), (255, 255, 255))
        assert ratio == pytest.approx(21.0, abs=0.1)

    def test_white_on_black_is_21(self):
        # Order shouldn't matter -- higher luminance is always L1
        ratio = contrast_ratio((255, 255, 255), (0, 0, 0))
        assert ratio == pytest.approx(21.0, abs=0.1)

    def test_same_color_is_1(self):
        ratio = contrast_ratio((128, 128, 128), (128, 128, 128))
        assert ratio == pytest.approx(1.0, abs=0.01)

    def test_known_gray_pair(self):
        # #767676 on white should be approximately 4.54:1 (WCAG reference)
        ratio = contrast_ratio((118, 118, 118), (255, 255, 255))
        assert 4.5 <= ratio <= 4.6

    def test_veilbreakers_text_on_bg(self):
        # #e6e6ff on #1a1a2e
        ratio = contrast_ratio((230, 230, 255), (26, 26, 46))
        # Should be high contrast (dark bg, light text)
        assert ratio > 10.0


# ---------------------------------------------------------------------------
# WCAG AA check
# ---------------------------------------------------------------------------


class TestCheckWcagAa:
    """Tests for WCAG AA pass/fail determination."""

    def test_black_on_white_passes(self):
        assert check_wcag_aa((0, 0, 0), (255, 255, 255)) is True

    def test_same_color_fails(self):
        assert check_wcag_aa((100, 100, 100), (100, 100, 100)) is False

    def test_threshold_4_5_for_normal_text(self):
        # #767676 on white is ~4.54:1 -- should just pass
        assert check_wcag_aa((118, 118, 118), (255, 255, 255)) is True

    def test_below_threshold_for_normal_text(self):
        # #777777 on white is ~4.48:1 -- should just fail
        assert check_wcag_aa((119, 119, 119), (255, 255, 255)) is False

    def test_large_text_uses_3_0_threshold(self):
        # A pair that fails 4.5:1 but passes 3.0:1
        # (148,148,148) on white gives ~3.03:1
        assert check_wcag_aa((148, 148, 148), (255, 255, 255), large_text=False) is False
        assert check_wcag_aa((148, 148, 148), (255, 255, 255), large_text=True) is True

    def test_veilbreakers_palette_passes(self):
        # #e6e6ff on #1a1a2e should pass WCAG AA
        assert check_wcag_aa((230, 230, 255), (26, 26, 46)) is True


# ---------------------------------------------------------------------------
# Color parsing
# ---------------------------------------------------------------------------


class TestParseColor:
    """Tests for CSS/USS color string parsing."""

    def test_hex_6_digit(self):
        assert parse_color("#ff0000") == (255, 0, 0)

    def test_hex_6_digit_mixed_case(self):
        assert parse_color("#FF00ff") == (255, 0, 255)

    def test_hex_3_digit(self):
        assert parse_color("#f00") == (255, 0, 0)

    def test_hex_8_digit_with_alpha(self):
        assert parse_color("#ff0000ff") == (255, 0, 0)

    def test_rgb_function(self):
        assert parse_color("rgb(128, 64, 32)") == (128, 64, 32)

    def test_rgba_function(self):
        assert parse_color("rgba(255, 128, 0, 0.5)") == (255, 128, 0)

    def test_invalid_returns_none(self):
        assert parse_color("not-a-color") is None

    def test_whitespace_handling(self):
        assert parse_color("  #aabbcc  ") == (170, 187, 204)


# ---------------------------------------------------------------------------
# UXML + USS contrast validation
# ---------------------------------------------------------------------------


class TestValidateUxmlContrast:
    """Tests for combined UXML + USS contrast validation."""

    def test_high_contrast_passes(self):
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:VisualElement class="screen-root">
                <ui:Label text="Hello" class="vb-title" />
            </ui:VisualElement>
        </ui:UXML>"""
        uss = """.screen-root { background-color: #1a1a2e; }
.vb-title { color: #e6e6ff; font-size: 36px; }"""
        results = validate_uxml_contrast(uxml, uss)
        # Should find the text element and it should pass
        title_results = [r for r in results if "vb-title" in r["element"]]
        assert len(title_results) > 0
        assert all(r["passes"] for r in title_results)

    def test_low_contrast_fails(self):
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:VisualElement class="dark-bg">
                <ui:Label text="Hard to read" class="dark-text" />
            </ui:VisualElement>
        </ui:UXML>"""
        uss = """.dark-bg { background-color: #333333; }
.dark-text { color: #444444; font-size: 14px; }"""
        results = validate_uxml_contrast(uxml, uss)
        failing = [r for r in results if not r["passes"]]
        assert len(failing) > 0

    def test_returns_ratio_values(self):
        uxml = """<ui:UXML xmlns:ui="UnityEngine.UIElements">
            <ui:VisualElement class="bg">
                <ui:Button text="Click" class="btn" />
            </ui:VisualElement>
        </ui:UXML>"""
        uss = """.bg { background-color: #000000; }
.btn { color: #ffffff; }"""
        results = validate_uxml_contrast(uxml, uss)
        assert len(results) > 0
        for r in results:
            assert "ratio" in r
            assert "foreground" in r
            assert "background" in r
            assert isinstance(r["ratio"], float)

    def test_invalid_uxml_returns_empty(self):
        results = validate_uxml_contrast("<<<invalid>>>", ".a { color: #fff; }")
        assert results == []
