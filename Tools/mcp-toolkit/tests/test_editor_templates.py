"""Unit tests for Unity editor C# template generators.

Tests that each generator function produces valid C# source containing
the expected keywords, API calls, and parameter substitutions.
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.editor_templates import (
    generate_recompile_script,
    generate_play_mode_script,
    generate_screenshot_script,
    generate_console_log_script,
    generate_gemini_review_script,
)


# ---------------------------------------------------------------------------
# Recompile script
# ---------------------------------------------------------------------------


class TestGenerateRecompileScript:
    """Tests for generate_recompile_script()."""

    def test_contains_asset_database_refresh(self):
        result = generate_recompile_script()
        assert "AssetDatabase.Refresh" in result

    def test_contains_using_unity_editor(self):
        result = generate_recompile_script()
        assert "using UnityEditor;" in result

    def test_contains_using_unity_engine(self):
        result = generate_recompile_script()
        assert "using UnityEngine;" in result

    def test_contains_menu_item_attribute(self):
        result = generate_recompile_script()
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json_output(self):
        result = generate_recompile_script()
        assert "vb_result.json" in result

    def test_contains_force_update(self):
        result = generate_recompile_script()
        assert "ImportAssetOptions.ForceUpdate" in result


# ---------------------------------------------------------------------------
# Play mode script
# ---------------------------------------------------------------------------


class TestGeneratePlayModeScript:
    """Tests for generate_play_mode_script()."""

    def test_enter_play_mode_contains_enter(self):
        result = generate_play_mode_script(enter=True)
        assert "EnterPlaymode" in result or "isPlaying = true" in result

    def test_exit_play_mode_contains_exit(self):
        result = generate_play_mode_script(enter=False)
        assert "ExitPlaymode" in result or "isPlaying = false" in result

    def test_contains_using_statements(self):
        result = generate_play_mode_script(enter=True)
        assert "using UnityEditor;" in result
        assert "using UnityEngine;" in result

    def test_contains_menu_item(self):
        result = generate_play_mode_script(enter=True)
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json_output(self):
        result = generate_play_mode_script(enter=True)
        assert "vb_result.json" in result

    def test_enter_and_exit_produce_different_output(self):
        enter = generate_play_mode_script(enter=True)
        exit_ = generate_play_mode_script(enter=False)
        assert enter != exit_


# ---------------------------------------------------------------------------
# Screenshot script
# ---------------------------------------------------------------------------


class TestGenerateScreenshotScript:
    """Tests for generate_screenshot_script()."""

    def test_contains_screen_capture(self):
        result = generate_screenshot_script()
        assert "ScreenCapture.CaptureScreenshot" in result

    def test_default_path_in_output(self):
        result = generate_screenshot_script()
        assert "Screenshots/vb_capture.png" in result

    def test_custom_path_in_output(self):
        result = generate_screenshot_script(output_path="MyShots/test.png")
        assert "MyShots/test.png" in result

    def test_custom_supersize(self):
        result = generate_screenshot_script(supersize=4)
        assert "4" in result

    def test_contains_using_statements(self):
        result = generate_screenshot_script()
        assert "using UnityEditor;" in result
        assert "using UnityEngine;" in result

    def test_contains_menu_item(self):
        result = generate_screenshot_script()
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json_output(self):
        result = generate_screenshot_script()
        assert "vb_result.json" in result

    def test_supersize_less_than_1_raises(self):
        with pytest.raises(ValueError, match="supersize"):
            generate_screenshot_script(supersize=0)

    def test_supersize_negative_raises(self):
        with pytest.raises(ValueError, match="supersize"):
            generate_screenshot_script(supersize=-1)


# ---------------------------------------------------------------------------
# Console log script
# ---------------------------------------------------------------------------


class TestGenerateConsoleLogScript:
    """Tests for generate_console_log_script()."""

    def test_contains_log_type_error_for_error_filter(self):
        result = generate_console_log_script(filter_type="error")
        assert "LogType.Error" in result

    def test_contains_log_type_warning_for_warning_filter(self):
        result = generate_console_log_script(filter_type="warning")
        assert "LogType.Warning" in result

    def test_all_filter_includes_all_types(self):
        result = generate_console_log_script(filter_type="all")
        # "all" filter should not filter by type -- collects everything
        assert "vb_result.json" in result

    def test_count_parameter_appears(self):
        result = generate_console_log_script(count=25)
        assert "25" in result

    def test_default_count_is_50(self):
        result = generate_console_log_script()
        assert "50" in result

    def test_contains_using_statements(self):
        result = generate_console_log_script()
        assert "using UnityEditor;" in result
        assert "using UnityEngine;" in result

    def test_contains_menu_item(self):
        result = generate_console_log_script()
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json_output(self):
        result = generate_console_log_script()
        assert "vb_result.json" in result

    def test_invalid_filter_type_raises(self):
        with pytest.raises(ValueError, match="filter_type"):
            generate_console_log_script(filter_type="invalid")


# ---------------------------------------------------------------------------
# Gemini review script
# ---------------------------------------------------------------------------


class TestGenerateGeminiReviewScript:
    """Tests for generate_gemini_review_script()."""

    def test_contains_screenshot_path(self):
        result = generate_gemini_review_script(
            screenshot_path="Screenshots/test.png",
            criteria=["lighting", "composition"],
        )
        assert "Screenshots/test.png" in result

    def test_contains_criteria(self):
        result = generate_gemini_review_script(
            screenshot_path="test.png",
            criteria=["lighting", "composition"],
        )
        # The criteria should appear in the output for documentation
        assert "lighting" in result
        assert "composition" in result

    def test_contains_using_statements(self):
        result = generate_gemini_review_script(
            screenshot_path="test.png",
            criteria=["quality"],
        )
        assert "using UnityEditor;" in result
        assert "using UnityEngine;" in result

    def test_contains_menu_item(self):
        result = generate_gemini_review_script(
            screenshot_path="test.png",
            criteria=["quality"],
        )
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json_output(self):
        result = generate_gemini_review_script(
            screenshot_path="test.png",
            criteria=["quality"],
        )
        assert "vb_result.json" in result

    def test_empty_criteria_raises(self):
        with pytest.raises(ValueError, match="criteria"):
            generate_gemini_review_script(
                screenshot_path="test.png",
                criteria=[],
            )
