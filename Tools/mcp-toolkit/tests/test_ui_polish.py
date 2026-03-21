"""Unit tests for Phase 22 AAA Dark Fantasy UI/UX Polish template generators.

Tests that each generator function:
1. Returns a dict with script_path, script_content, next_steps
2. Produces valid C# source with balanced braces and proper syntax
3. Contains expected Unity API calls, classes, and parameter substitutions
4. Handles custom parameters correctly

Requirements covered:
    UIPOL-01: Procedural UI frames (generate_procedural_frame_script)
    UIPOL-02: Icon render pipeline (generate_icon_render_pipeline_script)
    UIPOL-03: Cursor system (generate_cursor_system_script)
    UIPOL-04: Tooltip system (generate_tooltip_system_script)
    UIPOL-05: Radial menu (generate_radial_menu_script)
    UIPOL-06: Notification system (generate_notification_system_script)
    UIPOL-07: Loading screen (generate_loading_screen_script)
    UIPOL-08: UI material shaders (generate_ui_material_shaders)
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.ui_polish_templates import (
    generate_procedural_frame_script,
    generate_icon_render_pipeline_script,
    generate_cursor_system_script,
    generate_tooltip_system_script,
    generate_radial_menu_script,
    generate_notification_system_script,
    generate_loading_screen_script,
    generate_ui_material_shaders,
    VB_COLORS,
    RARITY_COLORS,
)


# ---------------------------------------------------------------------------
# Helpers for C# validation
# ---------------------------------------------------------------------------


def _check_balanced_braces(code: str) -> bool:
    """Verify that curly braces are balanced in the generated C# code."""
    count = 0
    for ch in code:
        if ch == "{":
            count += 1
        elif ch == "}":
            count -= 1
        if count < 0:
            return False
    return count == 0


def _check_output_structure(result: dict) -> None:
    """Assert that a generator result has the correct dict structure."""
    assert isinstance(result, dict), "Result must be a dict"
    assert "script_path" in result, "Missing script_path"
    assert "script_content" in result, "Missing script_content"
    assert "next_steps" in result, "Missing next_steps"
    assert isinstance(result["script_path"], str), "script_path must be str"
    assert isinstance(result["script_content"], str), "script_content must be str"
    assert isinstance(result["next_steps"], list), "next_steps must be list"
    assert len(result["next_steps"]) > 0, "next_steps must not be empty"
    assert len(result["script_content"]) > 100, "script_content too short"


def _check_cs_path(result: dict) -> None:
    """Assert that script_path ends with .cs."""
    assert result["script_path"].endswith(".cs"), "script_path must end with .cs"


def _check_shader_path(result: dict) -> None:
    """Assert that script_path ends with .shader."""
    assert result["script_path"].endswith(".shader"), "script_path must end with .shader"


# ===========================================================================
# UIPOL-01: Procedural UI Frames
# ===========================================================================


class TestGenerateProceduralFrameScript:
    """Tests for generate_procedural_frame_script() -- UIPOL-01."""

    def test_output_structure(self):
        result = generate_procedural_frame_script()
        _check_output_structure(result)
        _check_cs_path(result)

    def test_balanced_braces(self):
        result = generate_procedural_frame_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces in C#"

    def test_contains_monobehaviour(self):
        result = generate_procedural_frame_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_contains_ui_toolkit_imports(self):
        result = generate_procedural_frame_script()
        assert "UnityEngine.UIElements" in result["script_content"]

    def test_contains_visual_element(self):
        result = generate_procedural_frame_script()
        assert "VisualElement" in result["script_content"]

    def test_default_class_name(self):
        result = generate_procedural_frame_script()
        assert "VB_DarkFantasyFrame" in result["script_content"]

    def test_custom_frame_name(self):
        result = generate_procedural_frame_script(frame_name="InventoryFrame")
        assert "VB_InventoryFrame" in result["script_content"]
        assert "VB_InventoryFrame" in result["script_path"]

    def test_gothic_style(self):
        result = generate_procedural_frame_script(style="gothic")
        assert "gothic" in result["script_content"].lower() or "Gothic" in result["script_content"]

    def test_runic_style(self):
        result = generate_procedural_frame_script(style="runic")
        assert "Runic" in result["script_content"] or "runic" in result["script_content"]

    def test_corrupted_style(self):
        result = generate_procedural_frame_script(style="corrupted")
        assert "Corrupted" in result["script_content"] or "corrupted" in result["script_content"]

    def test_noble_style(self):
        result = generate_procedural_frame_script(style="noble")
        assert "Noble" in result["script_content"] or "noble" in result["script_content"]

    def test_invalid_style_defaults_to_gothic(self):
        result = generate_procedural_frame_script(style="invalid")
        assert "Gothic" in result["script_content"] or "gothic" in result["script_content"]

    def test_custom_border_width(self):
        result = generate_procedural_frame_script(border_width=8)
        assert "8" in result["script_content"]

    def test_corner_style_ornate(self):
        result = generate_procedural_frame_script(corner_style="ornate")
        assert "Ornate" in result["script_content"]

    def test_corner_style_skull(self):
        result = generate_procedural_frame_script(corner_style="skull")
        assert "Skull" in result["script_content"]

    def test_invalid_corner_defaults(self):
        result = generate_procedural_frame_script(corner_style="invalid")
        assert "Ornate" in result["script_content"]

    def test_inner_glow_enabled(self):
        result = generate_procedural_frame_script(inner_glow=True)
        assert "innerGlow" in result["script_content"] or "inner-glow" in result["script_content"]

    def test_inner_glow_disabled(self):
        result = generate_procedural_frame_script(inner_glow=False)
        assert "showInnerGlow = false" in result["script_content"]

    def test_rune_brand_iron(self):
        result = generate_procedural_frame_script(rune_brand="IRON")
        assert "IRON" in result["script_content"]

    def test_rune_brand_void(self):
        result = generate_procedural_frame_script(rune_brand="VOID")
        assert "VOID" in result["script_content"]

    def test_invalid_brand_defaults_to_iron(self):
        result = generate_procedural_frame_script(rune_brand="INVALID")
        assert "IRON" in result["script_content"]

    def test_uss_content_present(self):
        result = generate_procedural_frame_script()
        assert "uss_content" in result
        assert "uss_path" in result
        assert ".uss" in result["uss_path"]

    def test_uss_contains_vb_prefix(self):
        result = generate_procedural_frame_script()
        assert ".vb-frame" in result["uss_content"]

    def test_uss_contains_style_class(self):
        result = generate_procedural_frame_script(style="gothic")
        assert ".vb-frame--gothic" in result["uss_content"]

    def test_uss_contains_dark_fantasy_colors(self):
        result = generate_procedural_frame_script()
        uss = result["uss_content"]
        # Should contain at least one VB color
        assert any(color in uss for color in VB_COLORS.values())

    def test_contains_brand_runes_dictionary(self):
        result = generate_procedural_frame_script()
        assert "BrandRunes" in result["script_content"]
        assert "SAVAGE" in result["script_content"]
        assert "SURGE" in result["script_content"]

    def test_contains_frame_style_enum(self):
        result = generate_procedural_frame_script()
        assert "enum FrameStyle" in result["script_content"]

    def test_contains_corner_style_enum(self):
        result = generate_procedural_frame_script()
        assert "enum CornerStyle" in result["script_content"]

    def test_contains_build_frame_method(self):
        result = generate_procedural_frame_script()
        assert "BuildFrame()" in result["script_content"]

    def test_contains_set_title_method(self):
        result = generate_procedural_frame_script()
        assert "SetTitle" in result["script_content"]

    def test_contains_animation_fields(self):
        result = generate_procedural_frame_script()
        assert "fadeInDuration" in result["script_content"]
        assert "glowPulseSpeed" in result["script_content"]

    def test_next_steps_mentions_recompile(self):
        result = generate_procedural_frame_script()
        assert any("recompile" in s for s in result["next_steps"])


# ===========================================================================
# UIPOL-02: Icon Render Pipeline
# ===========================================================================


class TestGenerateIconRenderPipelineScript:
    """Tests for generate_icon_render_pipeline_script() -- UIPOL-02."""

    def test_output_structure(self):
        result = generate_icon_render_pipeline_script()
        _check_output_structure(result)
        _check_cs_path(result)

    def test_balanced_braces(self):
        result = generate_icon_render_pipeline_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces in C#"

    def test_contains_editor_guard(self):
        result = generate_icon_render_pipeline_script()
        assert "#if UNITY_EDITOR" in result["script_content"]
        assert "#endif" in result["script_content"]

    def test_contains_menu_item(self):
        result = generate_icon_render_pipeline_script()
        assert '[MenuItem("VeilBreakers/UI/' in result["script_content"]

    def test_contains_render_texture(self):
        result = generate_icon_render_pipeline_script()
        assert "RenderTexture" in result["script_content"]

    def test_contains_camera_setup(self):
        result = generate_icon_render_pipeline_script()
        assert "Camera" in result["script_content"]
        assert "fieldOfView" in result["script_content"]

    def test_default_icon_size(self):
        result = generate_icon_render_pipeline_script()
        assert "256" in result["script_content"]

    def test_custom_icon_size(self):
        result = generate_icon_render_pipeline_script(icon_size=512)
        assert "512" in result["script_content"]

    def test_front_three_quarter_angle(self):
        result = generate_icon_render_pipeline_script(render_angle="front_three_quarter")
        # Should contain the three-quarter camera position
        assert "45f" in result["script_content"]

    def test_front_angle(self):
        result = generate_icon_render_pipeline_script(render_angle="front")
        # Front angle has 0 Y rotation
        assert "0f, 0f" in result["script_content"] or "15f, 0f" in result["script_content"]

    def test_side_angle(self):
        result = generate_icon_render_pipeline_script(render_angle="side")
        assert "90f" in result["script_content"]

    def test_top_down_angle(self):
        result = generate_icon_render_pipeline_script(render_angle="top_down")
        assert "75f" in result["script_content"]

    def test_invalid_angle_defaults(self):
        result = generate_icon_render_pipeline_script(render_angle="invalid")
        assert "45f" in result["script_content"]  # default to front_three_quarter

    def test_three_point_lighting(self):
        result = generate_icon_render_pipeline_script(light_setup="three_point")
        assert "three_point" in result["script_content"]

    def test_dramatic_lighting(self):
        result = generate_icon_render_pipeline_script(light_setup="dramatic")
        assert "dramatic" in result["script_content"]

    def test_rarity_border_enabled(self):
        result = generate_icon_render_pipeline_script(rarity_border=True)
        assert "ApplyRarityBorder" in result["script_content"]
        assert "RarityColors" in result["script_content"]

    def test_rarity_border_disabled(self):
        result = generate_icon_render_pipeline_script(rarity_border=False)
        assert "ApplyRarityBorder" not in result["script_content"]

    def test_rarity_colors_defined(self):
        result = generate_icon_render_pipeline_script(rarity_border=True)
        content = result["script_content"]
        assert "Common" in content
        assert "Uncommon" in content
        assert "Rare" in content
        assert "Epic" in content
        assert "Legendary" in content
        assert "Corrupted" in content

    def test_background_gradient_enabled(self):
        result = generate_icon_render_pipeline_script(background_gradient=True)
        assert "ApplyBackgroundGradient" in result["script_content"]

    def test_background_gradient_disabled(self):
        result = generate_icon_render_pipeline_script(background_gradient=False)
        assert "ApplyBackgroundGradient" not in result["script_content"]

    def test_png_export(self):
        result = generate_icon_render_pipeline_script()
        assert "EncodeToPNG" in result["script_content"]
        assert ".png" in result["script_content"]

    def test_auto_framing(self):
        result = generate_icon_render_pipeline_script()
        assert "GetCompositeBounds" in result["script_content"]
        assert "Renderer" in result["script_content"]

    def test_output_folder(self):
        result = generate_icon_render_pipeline_script()
        assert "Assets/Art/Icons/Generated" in result["script_content"]

    def test_render_all_rarities_menu(self):
        result = generate_icon_render_pipeline_script()
        assert "Render All Rarity Icons" in result["script_content"]

    def test_cleanup_after_render(self):
        result = generate_icon_render_pipeline_script()
        assert "DestroyImmediate" in result["script_content"]


# ===========================================================================
# UIPOL-03: Cursor System
# ===========================================================================


class TestGenerateCursorSystemScript:
    """Tests for generate_cursor_system_script() -- UIPOL-03."""

    def test_output_structure(self):
        result = generate_cursor_system_script()
        _check_output_structure(result)
        _check_cs_path(result)

    def test_balanced_braces(self):
        result = generate_cursor_system_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces in C#"

    def test_contains_monobehaviour(self):
        result = generate_cursor_system_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_default_cursor_types(self):
        result = generate_cursor_system_script()
        content = result["script_content"]
        assert "Default" in content
        assert "Interact" in content
        assert "Attack" in content
        assert "Loot" in content
        assert "Talk" in content
        assert "Craft" in content

    def test_custom_cursor_types(self):
        result = generate_cursor_system_script(cursor_types=["default", "attack", "loot"])
        content = result["script_content"]
        assert "Default" in content
        assert "Attack" in content
        assert "Loot" in content

    def test_invalid_cursor_types_filtered(self):
        result = generate_cursor_system_script(cursor_types=["default", "invalid", "attack"])
        content = result["script_content"]
        assert "Default" in content
        assert "Attack" in content
        assert "Invalid" not in content

    def test_empty_cursor_types_defaults(self):
        result = generate_cursor_system_script(cursor_types=[])
        content = result["script_content"]
        assert "Default" in content

    def test_contains_cursor_type_enum(self):
        result = generate_cursor_system_script()
        assert "enum CursorType" in result["script_content"]

    def test_contains_raycast_detection(self):
        result = generate_cursor_system_script()
        assert "Raycast" in result["script_content"]
        assert "RaycastHit" in result["script_content"]

    def test_contains_cursor_set(self):
        result = generate_cursor_system_script()
        assert "Cursor.SetCursor" in result["script_content"]

    def test_contains_tag_detection(self):
        result = generate_cursor_system_script()
        content = result["script_content"]
        assert "CompareTag" in content

    def test_tag_mappings_present(self):
        result = generate_cursor_system_script()
        content = result["script_content"]
        assert "Enemy" in content
        assert "Interactable" in content
        assert "Loot" in content

    def test_auto_detect_feature(self):
        result = generate_cursor_system_script()
        assert "autoDetect" in result["script_content"]
        assert "SetAutoDetect" in result["script_content"]

    def test_reset_to_default(self):
        result = generate_cursor_system_script()
        assert "ResetToDefault" in result["script_content"]

    def test_on_disable_cleanup(self):
        result = generate_cursor_system_script()
        assert "OnDisable" in result["script_content"]

    def test_cursor_size_in_next_steps(self):
        result = generate_cursor_system_script(cursor_size=64)
        assert any("64" in s for s in result["next_steps"])

    def test_detection_interval(self):
        result = generate_cursor_system_script()
        assert "detectionInterval" in result["script_content"]

    def test_cursor_hotspot_configured(self):
        result = generate_cursor_system_script()
        assert "Vector2" in result["script_content"]


# ===========================================================================
# UIPOL-04: Tooltip System
# ===========================================================================


class TestGenerateTooltipSystemScript:
    """Tests for generate_tooltip_system_script() -- UIPOL-04."""

    def test_output_structure(self):
        result = generate_tooltip_system_script()
        _check_output_structure(result)
        _check_cs_path(result)

    def test_balanced_braces(self):
        result = generate_tooltip_system_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces in C#"

    def test_contains_monobehaviour(self):
        result = generate_tooltip_system_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_contains_ui_toolkit(self):
        result = generate_tooltip_system_script()
        assert "UIElements" in result["script_content"]
        assert "VisualElement" in result["script_content"]

    def test_rarity_colors_defined(self):
        result = generate_tooltip_system_script()
        content = result["script_content"]
        assert "RarityColors" in content
        assert "Common" in content
        assert "Legendary" in content
        assert "Corrupted" in content

    def test_item_tooltip_data_class(self):
        result = generate_tooltip_system_script()
        assert "ItemTooltipData" in result["script_content"]

    def test_show_tooltip_method(self):
        result = generate_tooltip_system_script()
        assert "ShowTooltip" in result["script_content"]

    def test_hide_tooltip_method(self):
        result = generate_tooltip_system_script()
        assert "HideTooltip" in result["script_content"]

    def test_comparison_enabled(self):
        result = generate_tooltip_system_script(show_comparison=True)
        assert "ShowComparison" in result["script_content"]
        assert "stat-delta" in result["script_content"] or "stat_delta" in result["script_content"]

    def test_comparison_disabled(self):
        result = generate_tooltip_system_script(show_comparison=False)
        assert "ShowComparison" not in result["script_content"]

    def test_comparison_arrows(self):
        result = generate_tooltip_system_script(show_comparison=True)
        content = result["script_content"]
        # Unicode arrows for better/worse stats
        assert "25B2" in content or "arrow" in content.lower()

    def test_lore_enabled(self):
        result = generate_tooltip_system_script(show_lore=True)
        assert "loreText" in result["script_content"] or "ShowLoreText" in result["script_content"]

    def test_lore_disabled(self):
        result = generate_tooltip_system_script(show_lore=False)
        assert "ShowLoreText" not in result["script_content"]

    def test_fade_duration_custom(self):
        result = generate_tooltip_system_script(fade_duration=0.5)
        assert "0.5" in result["script_content"]

    def test_max_width_custom(self):
        result = generate_tooltip_system_script(max_width=400)
        assert "400" in result["script_content"]

    def test_smart_positioning(self):
        result = generate_tooltip_system_script()
        content = result["script_content"]
        # Should have screen boundary clamping
        assert "Screen.width" in content or "Screen.height" in content

    def test_cursor_follow(self):
        result = generate_tooltip_system_script()
        assert "mousePosition" in result["script_content"] or "Input.mousePosition" in result["script_content"]

    def test_uss_content_present(self):
        result = generate_tooltip_system_script()
        assert "uss_content" in result
        assert ".vb-tooltip" in result["uss_content"]

    def test_uss_contains_dark_fantasy_colors(self):
        result = generate_tooltip_system_script()
        assert VB_COLORS["rich_gold"] in result["uss_content"]

    def test_is_visible_method(self):
        result = generate_tooltip_system_script()
        assert "IsVisible" in result["script_content"]

    def test_stat_color_coding(self):
        result = generate_tooltip_system_script(show_comparison=True)
        content = result["script_content"]
        # Green for better stats
        assert "0.18f, 0.8f, 0.44f" in content or "Green" in content
        # Red for worse stats
        assert "0.91f, 0.3f, 0.24f" in content or "Red" in content


# ===========================================================================
# UIPOL-05: Radial Menu
# ===========================================================================


class TestGenerateRadialMenuScript:
    """Tests for generate_radial_menu_script() -- UIPOL-05."""

    def test_output_structure(self):
        result = generate_radial_menu_script()
        _check_output_structure(result)
        _check_cs_path(result)

    def test_balanced_braces(self):
        result = generate_radial_menu_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces in C#"

    def test_contains_monobehaviour(self):
        result = generate_radial_menu_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_contains_ui_toolkit(self):
        result = generate_radial_menu_script()
        assert "UIElements" in result["script_content"]

    def test_default_segment_count(self):
        result = generate_radial_menu_script()
        assert "segmentCount = 8" in result["script_content"]

    def test_custom_segment_count(self):
        result = generate_radial_menu_script(segment_count=6)
        assert "segmentCount = 6" in result["script_content"]

    def test_segment_count_clamped_min(self):
        result = generate_radial_menu_script(segment_count=2)
        assert "segmentCount = 4" in result["script_content"]

    def test_segment_count_clamped_max(self):
        result = generate_radial_menu_script(segment_count=20)
        assert "segmentCount = 12" in result["script_content"]

    def test_custom_radius(self):
        result = generate_radial_menu_script(radius=200.0)
        assert "200" in result["script_content"]

    def test_menu_type_ability(self):
        result = generate_radial_menu_script(menu_type="ability")
        assert "ability" in result["script_content"]

    def test_menu_type_item(self):
        result = generate_radial_menu_script(menu_type="item")
        assert "item" in result["script_content"]

    def test_menu_type_spell(self):
        result = generate_radial_menu_script(menu_type="spell")
        assert "spell" in result["script_content"]

    def test_invalid_menu_type_defaults(self):
        result = generate_radial_menu_script(menu_type="invalid")
        assert "ability" in result["script_content"]

    def test_trigger_key(self):
        result = generate_radial_menu_script(trigger_key="Q")
        assert "KeyCode.Q" in result["script_content"]

    def test_radial_segment_data_class(self):
        result = generate_radial_menu_script()
        assert "RadialSegment" in result["script_content"]

    def test_mouse_direction_selection(self):
        result = generate_radial_menu_script()
        assert "Atan2" in result["script_content"] or "atan2" in result["script_content"]

    def test_keyboard_shortcuts(self):
        result = generate_radial_menu_script()
        assert "Alpha1" in result["script_content"]

    def test_open_close_methods(self):
        result = generate_radial_menu_script()
        content = result["script_content"]
        assert "OpenMenu" in content
        assert "CloseMenu" in content

    def test_events_defined(self):
        result = generate_radial_menu_script()
        content = result["script_content"]
        assert "OnSegmentSelected" in content
        assert "OnMenuOpened" in content
        assert "OnMenuClosed" in content

    def test_hover_detection(self):
        result = generate_radial_menu_script()
        assert "SetHoveredIndex" in result["script_content"] or "_hoveredIndex" in result["script_content"]

    def test_set_segment_method(self):
        result = generate_radial_menu_script()
        assert "SetSegment" in result["script_content"]

    def test_is_open_method(self):
        result = generate_radial_menu_script()
        assert "IsOpen" in result["script_content"]

    def test_dark_fantasy_colors(self):
        result = generate_radial_menu_script()
        content = result["script_content"]
        # Gold accent color
        assert "0.79f, 0.66f, 0.3f" in content

    def test_circular_layout(self):
        result = generate_radial_menu_script()
        content = result["script_content"]
        assert "Cos" in content or "cos" in content
        assert "Sin" in content or "sin" in content


# ===========================================================================
# UIPOL-06: Notification System
# ===========================================================================


class TestGenerateNotificationSystemScript:
    """Tests for generate_notification_system_script() -- UIPOL-06."""

    def test_output_structure(self):
        result = generate_notification_system_script()
        _check_output_structure(result)
        _check_cs_path(result)

    def test_balanced_braces(self):
        result = generate_notification_system_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces in C#"

    def test_contains_monobehaviour(self):
        result = generate_notification_system_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_contains_ui_toolkit(self):
        result = generate_notification_system_script()
        assert "UIElements" in result["script_content"]

    def test_toast_type_enum(self):
        result = generate_notification_system_script()
        assert "enum ToastType" in result["script_content"]

    def test_toast_priority_enum(self):
        result = generate_notification_system_script()
        assert "enum ToastPriority" in result["script_content"]

    def test_default_toast_types(self):
        result = generate_notification_system_script()
        content = result["script_content"]
        assert "QuestUpdate" in content
        assert "ItemPickup" in content
        assert "LevelUp" in content
        assert "Achievement" in content

    def test_custom_toast_types(self):
        result = generate_notification_system_script(
            toast_types=["quest_update", "item_pickup"]
        )
        content = result["script_content"]
        assert "QuestUpdate" in content
        assert "ItemPickup" in content

    def test_max_visible_default(self):
        result = generate_notification_system_script()
        assert "maxVisible = 5" in result["script_content"]

    def test_max_visible_custom(self):
        result = generate_notification_system_script(max_visible=3)
        assert "maxVisible = 3" in result["script_content"]

    def test_auto_dismiss_default(self):
        result = generate_notification_system_script()
        assert "4.0f" in result["script_content"] or "autoDismissSeconds = 4" in result["script_content"]

    def test_auto_dismiss_custom(self):
        result = generate_notification_system_script(auto_dismiss_seconds=6.0)
        assert "6.0f" in result["script_content"]

    def test_position_top_right(self):
        result = generate_notification_system_script(position="top_right")
        assert "right" in result["script_content"]

    def test_position_top_left(self):
        result = generate_notification_system_script(position="top_left")
        assert "left" in result["script_content"]

    def test_invalid_position_defaults(self):
        result = generate_notification_system_script(position="invalid")
        assert "right" in result["script_content"]

    def test_show_toast_method(self):
        result = generate_notification_system_script()
        assert "ShowToast" in result["script_content"]

    def test_dismiss_all_method(self):
        result = generate_notification_system_script()
        assert "DismissAll" in result["script_content"]

    def test_queue_system(self):
        result = generate_notification_system_script()
        content = result["script_content"]
        assert "Queue" in content
        assert "_pendingQueue" in content

    def test_priority_handling(self):
        result = generate_notification_system_script()
        content = result["script_content"]
        assert "Critical" in content
        assert "High" in content

    def test_auto_dismiss_timer(self):
        result = generate_notification_system_script()
        content = result["script_content"]
        assert "timestamp" in content
        assert "displayTime" in content

    def test_type_colors_defined(self):
        result = generate_notification_system_script()
        assert "GetTypeColor" in result["script_content"]

    def test_get_active_count(self):
        result = generate_notification_system_script()
        assert "GetActiveCount" in result["script_content"]

    def test_get_pending_count(self):
        result = generate_notification_system_script()
        assert "GetPendingCount" in result["script_content"]

    def test_slide_in_animation(self):
        result = generate_notification_system_script()
        assert "slideInDuration" in result["script_content"]


# ===========================================================================
# UIPOL-07: Loading Screen System
# ===========================================================================


class TestGenerateLoadingScreenScript:
    """Tests for generate_loading_screen_script() -- UIPOL-07."""

    def test_output_structure(self):
        result = generate_loading_screen_script()
        _check_output_structure(result)
        _check_cs_path(result)

    def test_balanced_braces(self):
        result = generate_loading_screen_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces in C#"

    def test_contains_monobehaviour(self):
        result = generate_loading_screen_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_contains_scene_management(self):
        result = generate_loading_screen_script()
        assert "SceneManagement" in result["script_content"]
        assert "AsyncOperation" in result["script_content"]

    def test_contains_coroutine(self):
        result = generate_loading_screen_script()
        assert "IEnumerator" in result["script_content"]
        assert "StartCoroutine" in result["script_content"]

    def test_progress_bar(self):
        result = generate_loading_screen_script()
        content = result["script_content"]
        assert "_progressBarFill" in content
        assert "_currentProgress" in content

    def test_tips_enabled(self):
        result = generate_loading_screen_script(show_tips=True)
        content = result["script_content"]
        assert "gameplayTips" in content
        assert "UpdateTips" in content

    def test_tips_disabled(self):
        result = generate_loading_screen_script(show_tips=False)
        content = result["script_content"]
        assert "gameplayTips" not in content

    def test_lore_enabled(self):
        result = generate_loading_screen_script(show_lore=True)
        content = result["script_content"]
        assert "loreTexts" in content
        assert "typewriterSpeed" in content

    def test_lore_disabled(self):
        result = generate_loading_screen_script(show_lore=False)
        content = result["script_content"]
        assert "loreTexts" not in content

    def test_typewriter_effect(self):
        result = generate_loading_screen_script(show_lore=True)
        content = result["script_content"]
        assert "UpdateTypewriter" in content
        assert "_loreCharIndex" in content

    def test_art_enabled(self):
        result = generate_loading_screen_script(show_art=True)
        content = result["script_content"]
        assert "conceptArtImages" in content
        assert "UpdateConceptArt" in content

    def test_art_disabled(self):
        result = generate_loading_screen_script(show_art=False)
        content = result["script_content"]
        assert "conceptArtImages" not in content

    def test_art_crossfade(self):
        result = generate_loading_screen_script(show_art=True)
        assert "artCrossfadeDuration" in result["script_content"]

    def test_custom_tip_interval(self):
        result = generate_loading_screen_script(show_tips=True, tip_interval=3.0)
        assert "3.0" in result["script_content"]

    def test_progress_style(self):
        result = generate_loading_screen_script(progress_style="bar")
        assert "bar" in result["script_content"]

    def test_start_loading_method(self):
        result = generate_loading_screen_script()
        assert "StartLoading" in result["script_content"]

    def test_show_manual_method(self):
        result = generate_loading_screen_script()
        assert "ShowManual" in result["script_content"]

    def test_set_progress_method(self):
        result = generate_loading_screen_script()
        assert "SetProgress" in result["script_content"]

    def test_hide_method(self):
        result = generate_loading_screen_script()
        assert "Hide" in result["script_content"]

    def test_is_loading_method(self):
        result = generate_loading_screen_script()
        assert "IsLoading" in result["script_content"]

    def test_smooth_progress_interpolation(self):
        result = generate_loading_screen_script()
        assert "Lerp" in result["script_content"]

    def test_async_scene_loading(self):
        result = generate_loading_screen_script()
        content = result["script_content"]
        assert "LoadSceneAsync" in content
        assert "allowSceneActivation" in content

    def test_dark_fantasy_colors(self):
        result = generate_loading_screen_script()
        content = result["script_content"]
        # Gold accent
        assert "0.79f, 0.66f, 0.3f" in content

    def test_veilbreakers_tips_content(self):
        result = generate_loading_screen_script(show_tips=True)
        content = result["script_content"]
        # Should have VeilBreakers-specific tips
        assert "brand" in content.lower() or "corruption" in content.lower()


# ===========================================================================
# UIPOL-08: UI Material Shaders
# ===========================================================================


class TestGenerateUIMaterialShaders:
    """Tests for generate_ui_material_shaders() -- UIPOL-08."""

    def test_output_structure(self):
        result = generate_ui_material_shaders()
        _check_output_structure(result)
        _check_shader_path(result)

    def test_balanced_braces(self):
        result = generate_ui_material_shaders()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces in shader"

    def test_contains_shader_declaration(self):
        result = generate_ui_material_shaders()
        assert "Shader" in result["script_content"]
        assert "SubShader" in result["script_content"]

    def test_contains_hlsl(self):
        result = generate_ui_material_shaders()
        assert "HLSLPROGRAM" in result["script_content"]
        assert "ENDHLSL" in result["script_content"]

    def test_contains_urp_include(self):
        result = generate_ui_material_shaders()
        assert "com.unity.render-pipelines.universal" in result["script_content"]

    def test_transparent_rendering(self):
        result = generate_ui_material_shaders()
        content = result["script_content"]
        assert "Transparent" in content
        assert "Blend SrcAlpha OneMinusSrcAlpha" in content

    def test_default_all_effects(self):
        result = generate_ui_material_shaders()
        assert "effects_included" in result
        effects = result["effects_included"]
        assert "gold_leaf" in effects
        assert "blood_stain" in effects
        assert "rune_glow" in effects
        assert "corruption_ripple" in effects

    def test_custom_effects_subset(self):
        result = generate_ui_material_shaders(effects=["gold_leaf", "rune_glow"])
        effects = result["effects_included"]
        assert "gold_leaf" in effects
        assert "rune_glow" in effects
        assert "blood_stain" not in effects

    def test_invalid_effects_filtered(self):
        result = generate_ui_material_shaders(effects=["gold_leaf", "invalid", "rune_glow"])
        effects = result["effects_included"]
        assert "gold_leaf" in effects
        assert "rune_glow" in effects
        assert "invalid" not in effects

    def test_empty_effects_defaults_to_gold_leaf(self):
        result = generate_ui_material_shaders(effects=[])
        assert "gold_leaf" in result["effects_included"]

    def test_gold_leaf_properties(self):
        result = generate_ui_material_shaders(effects=["gold_leaf"])
        content = result["script_content"]
        assert "_GoldLeafEnabled" in content
        assert "_GoldLeafSpeed" in content
        assert "_GoldLeafWidth" in content
        assert "_GoldLeafIntensity" in content
        assert "_GoldLeafColor" in content

    def test_gold_leaf_sweep_effect(self):
        result = generate_ui_material_shaders(effects=["gold_leaf"])
        content = result["script_content"]
        assert "sweepPos" in content or "sweep" in content.lower()
        assert "shine" in content

    def test_blood_stain_properties(self):
        result = generate_ui_material_shaders(effects=["blood_stain"])
        content = result["script_content"]
        assert "_BloodEnabled" in content
        assert "_BloodAmount" in content
        assert "_BloodColor" in content
        assert "_BloodNoiseScale" in content

    def test_blood_stain_noise(self):
        result = generate_ui_material_shaders(effects=["blood_stain"])
        content = result["script_content"]
        assert "noise" in content.lower()
        assert "smoothstep" in content

    def test_rune_glow_properties(self):
        result = generate_ui_material_shaders(effects=["rune_glow"])
        content = result["script_content"]
        assert "_RuneGlowEnabled" in content
        assert "_RuneGlowColor" in content
        assert "_RuneGlowSpeed" in content
        assert "_RuneGlowIntensity" in content
        assert "_RuneMask" in content

    def test_rune_glow_pulse(self):
        result = generate_ui_material_shaders(effects=["rune_glow"])
        content = result["script_content"]
        assert "pulse" in content or "sin" in content

    def test_corruption_ripple_properties(self):
        result = generate_ui_material_shaders(effects=["corruption_ripple"])
        content = result["script_content"]
        assert "_CorruptionEnabled" in content
        assert "_CorruptionAmount" in content
        assert "_CorruptionSpeed" in content
        assert "_CorruptionFrequency" in content
        assert "_CorruptionDistortion" in content

    def test_corruption_distortion_effect(self):
        result = generate_ui_material_shaders(effects=["corruption_ripple"])
        content = result["script_content"]
        assert "ripple" in content
        assert "distortion" in content.lower() or "Distortion" in content

    def test_custom_shader_name(self):
        result = generate_ui_material_shaders(shader_name="MyCustomShader")
        assert "MyCustomShader" in result["script_content"]
        assert "MyCustomShader" in result["script_path"]

    def test_shader_path_in_veilbreakers_namespace(self):
        result = generate_ui_material_shaders()
        assert "VeilBreakers/UI/" in result["script_content"]

    def test_vertex_shader_present(self):
        result = generate_ui_material_shaders()
        assert "vert" in result["script_content"]
        assert "Attributes" in result["script_content"]
        assert "Varyings" in result["script_content"]

    def test_fragment_shader_present(self):
        result = generate_ui_material_shaders()
        assert "frag" in result["script_content"]
        assert "SV_Target" in result["script_content"]

    def test_instancing_support(self):
        result = generate_ui_material_shaders()
        assert "multi_compile_instancing" in result["script_content"]

    def test_fallback_shader(self):
        result = generate_ui_material_shaders()
        assert "Fallback" in result["script_content"]

    def test_time_based_animation(self):
        result = generate_ui_material_shaders()
        assert "_Time" in result["script_content"]


# ===========================================================================
# Module-level tests
# ===========================================================================


class TestModuleConstants:
    """Tests for module-level constants."""

    def test_vb_colors_defined(self):
        assert len(VB_COLORS) >= 5
        assert "deep_black" in VB_COLORS
        assert "rich_gold" in VB_COLORS
        assert "crimson_red" in VB_COLORS

    def test_vb_colors_are_hex(self):
        for name, color in VB_COLORS.items():
            assert color.startswith("#"), f"{name} should start with #"
            assert len(color) in (7, 9), f"{name} should be #RRGGBB or #RRGGBBAA"

    def test_rarity_colors_defined(self):
        assert len(RARITY_COLORS) == 6
        assert "Common" in RARITY_COLORS
        assert "Uncommon" in RARITY_COLORS
        assert "Rare" in RARITY_COLORS
        assert "Epic" in RARITY_COLORS
        assert "Legendary" in RARITY_COLORS
        assert "Corrupted" in RARITY_COLORS

    def test_rarity_colors_are_hex(self):
        for name, color in RARITY_COLORS.items():
            assert color.startswith("#"), f"{name} should start with #"


class TestSanitizeIdentifier:
    """Tests for sanitize_cs_identifier helper (shared module)."""

    def test_normal_name(self):
        from veilbreakers_mcp.shared.unity_templates._cs_sanitize import sanitize_cs_identifier
        assert sanitize_cs_identifier("MyFrame") == "MyFrame"

    def test_with_spaces(self):
        from veilbreakers_mcp.shared.unity_templates._cs_sanitize import sanitize_cs_identifier
        assert sanitize_cs_identifier("My Frame") == "MyFrame"

    def test_with_special_chars(self):
        from veilbreakers_mcp.shared.unity_templates._cs_sanitize import sanitize_cs_identifier
        assert sanitize_cs_identifier("My-Frame!@#") == "MyFrame"

    def test_starts_with_digit(self):
        from veilbreakers_mcp.shared.unity_templates._cs_sanitize import sanitize_cs_identifier
        assert sanitize_cs_identifier("123Frame") == "_123Frame"

    def test_empty_string(self):
        from veilbreakers_mcp.shared.unity_templates._cs_sanitize import sanitize_cs_identifier
        assert sanitize_cs_identifier("") == "_unnamed"

    def test_only_special_chars(self):
        from veilbreakers_mcp.shared.unity_templates._cs_sanitize import sanitize_cs_identifier
        assert sanitize_cs_identifier("@#$") == "_unnamed"
