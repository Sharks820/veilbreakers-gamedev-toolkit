"""Unit tests for UX C# template generators.

Tests that each generator function produces valid C# source containing
the expected keywords, Unity API calls, PrimeTween usage, and parameter
substitutions. Validates no DOTween contamination across all generators.
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.ux_templates import (
    generate_minimap_script,
    generate_damage_numbers_script,
    generate_interaction_prompts_script,
    generate_primetween_sequence_script,
    generate_tmp_font_asset_script,
    generate_tmp_component_script,
    generate_tutorial_system_script,
    generate_accessibility_script,
    generate_character_select_script,
    generate_world_map_script,
    generate_rarity_vfx_script,
    generate_corruption_vfx_script,
)


# ---------------------------------------------------------------------------
# UIX-01: Minimap with orthographic camera + RenderTexture
# ---------------------------------------------------------------------------


class TestMinimap:
    """Tests for generate_minimap_script()."""

    def test_minimap_produces_orthographic_camera(self):
        editor_cs, runtime_cs = generate_minimap_script("TestMap")
        assert "orthographic = true" in runtime_cs

    def test_minimap_produces_render_texture(self):
        editor_cs, runtime_cs = generate_minimap_script("TestMap")
        assert "RenderTexture" in editor_cs

    def test_minimap_follows_player_position(self):
        editor_cs, runtime_cs = generate_minimap_script("TestMap")
        assert "target.x" in runtime_cs
        assert "target.z" in runtime_cs

    def test_minimap_uses_culling_mask(self):
        editor_cs, runtime_cs = generate_minimap_script("TestMap")
        assert "cullingMask" in runtime_cs or "LayerMask" in runtime_cs

    def test_minimap_top_down_rotation(self):
        editor_cs, runtime_cs = generate_minimap_script("TestMap")
        assert "Euler(90" in editor_cs or "Euler(90" in runtime_cs

    def test_minimap_world_markers(self):
        editor_cs, runtime_cs = generate_minimap_script("TestMap")
        assert "Dictionary<string, Transform>" in runtime_cs
        assert "_trackedMarkers" in runtime_cs

    def test_minimap_returns_tuple(self):
        result = generate_minimap_script("TestMap")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_minimap_custom_zoom(self):
        editor_cs, runtime_cs = generate_minimap_script("TestMap", zoom=100.0)
        assert "100" in runtime_cs
        assert "orthographicSize" in runtime_cs

    def test_minimap_compass(self):
        editor_cs, runtime_cs = generate_minimap_script("TestMap", compass_enabled=True)
        assert "compassRing" in runtime_cs or "_compassRing" in runtime_cs
        assert "localRotation" in runtime_cs

    def test_minimap_editor_creates_camera(self):
        editor_cs, runtime_cs = generate_minimap_script("TestMap")
        assert "AddComponent<Camera>" in editor_cs

    def test_minimap_editor_creates_raw_image(self):
        editor_cs, runtime_cs = generate_minimap_script("TestMap")
        assert "RawImage" in editor_cs

    def test_minimap_custom_layers(self):
        editor_cs, runtime_cs = generate_minimap_script(
            "TestMap", culling_layers=["UI", "Characters"]
        )
        assert "UI" in runtime_cs
        assert "Characters" in runtime_cs

    def test_minimap_camera_height(self):
        editor_cs, runtime_cs = generate_minimap_script("TestMap")
        assert "100f" in editor_cs or "_cameraHeight" in runtime_cs

    def test_minimap_update_interval(self):
        editor_cs, runtime_cs = generate_minimap_script("TestMap", update_interval=5)
        assert "5" in runtime_cs
        assert "_updateInterval" in runtime_cs

    def test_minimap_viewport_conversion(self):
        editor_cs, runtime_cs = generate_minimap_script("TestMap")
        assert "WorldToViewportPoint" in runtime_cs

    def test_minimap_class_names(self):
        editor_cs, runtime_cs = generate_minimap_script("TestMap")
        assert "class TestMapSetup" in editor_cs
        assert "class TestMapController" in runtime_cs

    def test_minimap_namespace(self):
        editor_cs, runtime_cs = generate_minimap_script("TestMap", namespace="VB.UX")
        assert "namespace VB.UX" in editor_cs
        assert "namespace VB.UX" in runtime_cs


# ---------------------------------------------------------------------------
# UIX-03: Floating damage numbers with PrimeTween + ObjectPool
# ---------------------------------------------------------------------------


class TestDamageNumbers:
    """Tests for generate_damage_numbers_script()."""

    def test_damage_numbers_uses_primetween(self):
        result = generate_damage_numbers_script("DmgNum")
        assert "Tween." in result
        assert "DOTween" not in result

    def test_damage_numbers_uses_object_pool(self):
        result = generate_damage_numbers_script("DmgNum")
        assert "ObjectPool" in result

    def test_damage_numbers_brand_colors(self):
        result = generate_damage_numbers_script("DmgNum")
        assert "IRON" in result
        assert "VENOM" in result
        assert "SURGE" in result
        assert "DREAD" in result
        assert "SAVAGE" in result

    def test_damage_numbers_all_10_brands(self):
        result = generate_damage_numbers_script("DmgNum")
        for brand in ["IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
                       "LEECH", "GRACE", "MEND", "RUIN", "VOID"]:
            assert brand in result, f"Missing brand color: {brand}"

    def test_damage_numbers_crit_scaling(self):
        result = generate_damage_numbers_script("DmgNum", crit_scale=2.0)
        assert "critScale" in result or "_critScale" in result
        assert "isCrit" in result

    def test_damage_numbers_show_method(self):
        result = generate_damage_numbers_script("DmgNum")
        assert "ShowDamage" in result
        assert "Vector3 worldPos" in result
        assert "float amount" in result
        assert "string damageType" in result
        assert "bool isCrit" in result

    def test_damage_numbers_sequence_create(self):
        result = generate_damage_numbers_script("DmgNum")
        assert "Sequence.Create" in result

    def test_damage_numbers_float_animation(self):
        result = generate_damage_numbers_script("DmgNum")
        assert "Tween.UIAnchoredPosition" in result
        assert "Tween.Alpha" in result

    def test_damage_numbers_pool_prewarm(self):
        result = generate_damage_numbers_script("DmgNum", pool_size=30)
        assert "30" in result
        assert "_poolSize" in result

    def test_damage_numbers_random_x_offset(self):
        result = generate_damage_numbers_script("DmgNum")
        assert "randomX" in result or "Random.Range" in result

    def test_damage_numbers_return_to_pool(self):
        result = generate_damage_numbers_script("DmgNum")
        assert "ReturnToPool" in result
        assert "Release" in result

    def test_damage_numbers_class_name(self):
        result = generate_damage_numbers_script("DmgNum")
        assert "class DmgNumManager" in result

    def test_damage_numbers_using_tmpro(self):
        result = generate_damage_numbers_script("DmgNum")
        assert "using TMPro;" in result
        assert "TextMeshProUGUI" in result

    def test_damage_numbers_namespace(self):
        result = generate_damage_numbers_script("DmgNum", namespace="VB.Combat")
        assert "namespace VB.Combat" in result

    def test_damage_numbers_ease_curves(self):
        result = generate_damage_numbers_script("DmgNum")
        assert "Ease.OutCubic" in result
        assert "Ease.InQuad" in result


# ---------------------------------------------------------------------------
# UIX-04: Context-sensitive interaction prompts
# ---------------------------------------------------------------------------


class TestInteractionPrompts:
    """Tests for generate_interaction_prompts_script()."""

    def test_prompts_uses_trigger(self):
        result = generate_interaction_prompts_script("Prompt")
        assert "OnTriggerEnter" in result
        assert "OnTriggerExit" in result

    def test_prompts_uses_input_rebind(self):
        result = generate_interaction_prompts_script("Prompt")
        assert "GetBindingDisplayString" in result

    def test_prompts_uses_primetween(self):
        result = generate_interaction_prompts_script("Prompt")
        assert "Tween.Alpha" in result
        assert "DOTween" not in result

    def test_prompts_billboard(self):
        result = generate_interaction_prompts_script("Prompt")
        assert "LookAt" in result

    def test_prompts_sphere_collider(self):
        result = generate_interaction_prompts_script("Prompt")
        assert "SphereCollider" in result
        assert "isTrigger" in result

    def test_prompts_canvas_group(self):
        result = generate_interaction_prompts_script("Prompt")
        assert "CanvasGroup" in result

    def test_prompts_custom_radius(self):
        result = generate_interaction_prompts_script("Prompt", trigger_radius=5.0)
        assert "5.0f" in result or "5f" in result

    def test_prompts_custom_action_text(self):
        result = generate_interaction_prompts_script("Prompt", prompt_text="Open Door")
        assert "Open Door" in result

    def test_prompts_input_action_reference(self):
        result = generate_interaction_prompts_script("Prompt")
        assert "InputActionReference" in result

    def test_prompts_fade_duration(self):
        result = generate_interaction_prompts_script("Prompt", fade_duration=0.5)
        assert "0.5f" in result or "_fadeDuration" in result

    def test_prompts_using_input_system(self):
        result = generate_interaction_prompts_script("Prompt")
        assert "using UnityEngine.InputSystem;" in result

    def test_prompts_class_name(self):
        result = generate_interaction_prompts_script("Prompt")
        assert "class Prompt" in result

    def test_prompts_namespace(self):
        result = generate_interaction_prompts_script("Prompt", namespace="VB.UX")
        assert "namespace VB.UX" in result

    def test_prompts_rebind_callback(self):
        result = generate_interaction_prompts_script("Prompt")
        assert "OnRebindComplete" in result


# ---------------------------------------------------------------------------
# SHDR-04: PrimeTween UI animation sequences
# ---------------------------------------------------------------------------


class TestPrimeTweenSequence:
    """Tests for generate_primetween_sequence_script()."""

    def test_primetween_uses_correct_api(self):
        result = generate_primetween_sequence_script()
        assert "using PrimeTween;" in result

    def test_primetween_no_dotween(self):
        result = generate_primetween_sequence_script()
        assert "DOTween" not in result
        assert "DG.Tweening" not in result

    def test_primetween_sequence_create(self):
        result = generate_primetween_sequence_script()
        assert "Sequence.Create" in result

    def test_primetween_chain_group(self):
        result = generate_primetween_sequence_script()
        assert "Chain" in result
        assert "Group" in result

    def test_primetween_ease_curves(self):
        result = generate_primetween_sequence_script()
        assert "Ease." in result
        assert "Ease.OutBack" in result
        assert "Ease.OutCubic" in result

    def test_primetween_tween_scale(self):
        result = generate_primetween_sequence_script()
        assert "Tween.Scale" in result or "Tween.PunchLocalScale" in result

    def test_primetween_multiple_types_panel_entrance(self):
        result = generate_primetween_sequence_script(sequence_type="panel_entrance")
        assert "PanelEntrance" in result

    def test_primetween_multiple_types_panel_exit(self):
        result = generate_primetween_sequence_script(sequence_type="panel_exit")
        assert "PanelExit" in result

    def test_primetween_multiple_types_button_hover(self):
        result = generate_primetween_sequence_script(sequence_type="button_hover")
        assert "ButtonHover" in result

    def test_primetween_multiple_types_screen_shake(self):
        result = generate_primetween_sequence_script(sequence_type="screen_shake")
        assert "ScreenShake" in result
        assert "ShakeLocalPosition" in result

    def test_primetween_multiple_types_damage_flash(self):
        result = generate_primetween_sequence_script(sequence_type="damage_flash")
        assert "DamageFlash" in result

    def test_primetween_multiple_types_item_pickup(self):
        result = generate_primetween_sequence_script(sequence_type="item_pickup")
        assert "ItemPickup" in result

    def test_primetween_multiple_types_level_up(self):
        result = generate_primetween_sequence_script(sequence_type="level_up")
        assert "LevelUp" in result

    def test_primetween_static_class(self):
        result = generate_primetween_sequence_script()
        assert "static class" in result

    def test_primetween_static_methods(self):
        result = generate_primetween_sequence_script()
        assert "public static Sequence" in result
        assert "public static Tween" in result

    def test_primetween_custom_name(self):
        result = generate_primetween_sequence_script(name="Combat")
        assert "VB_CombatAnimations" in result

    def test_primetween_default_name(self):
        result = generate_primetween_sequence_script()
        assert "VB_UIAnimations" in result

    def test_primetween_namespace(self):
        result = generate_primetween_sequence_script(namespace="VB.UI")
        assert "namespace VB.UI" in result

    def test_primetween_punch_and_shake(self):
        result = generate_primetween_sequence_script()
        assert "Tween.PunchLocalScale" in result
        assert "Tween.ShakeLocalPosition" in result

    def test_primetween_alpha_usage(self):
        result = generate_primetween_sequence_script()
        assert "Tween.Alpha" in result

    def test_primetween_ui_anchored_position(self):
        result = generate_primetween_sequence_script()
        assert "Tween.UIAnchoredPosition" in result

    def test_primetween_all_methods_present(self):
        result = generate_primetween_sequence_script()
        for method in ["PanelEntrance", "PanelExit", "ButtonHover",
                        "NotificationPopup", "ScreenShake", "DamageFlash",
                        "ItemPickup", "LevelUp"]:
            assert method in result, f"Missing method: {method}"


# ---------------------------------------------------------------------------
# PIPE-10: TMP font asset creation
# ---------------------------------------------------------------------------


class TestTMPFontAsset:
    """Tests for generate_tmp_font_asset_script()."""

    def test_tmp_creates_font_asset(self):
        result = generate_tmp_font_asset_script()
        assert "TMP_FontAsset.CreateFontAsset" in result

    def test_tmp_uses_sdfaa(self):
        result = generate_tmp_font_asset_script()
        assert "SDFAA" in result

    def test_tmp_character_set(self):
        result = generate_tmp_font_asset_script()
        assert "characterSet" in result
        assert "TryAddCharacters" in result

    def test_tmp_menu_item(self):
        result = generate_tmp_font_asset_script()
        assert "MenuItem" in result
        assert "VeilBreakers/Fonts" in result

    def test_tmp_fallback_chain(self):
        result = generate_tmp_font_asset_script()
        assert "fallbackFontAssetTable" in result
        assert "_fallbackFonts" in result

    def test_tmp_custom_atlas_size(self):
        result = generate_tmp_font_asset_script(atlas_width=2048, atlas_height=2048)
        assert "2048" in result

    def test_tmp_custom_sampling_size(self):
        result = generate_tmp_font_asset_script(sampling_size=64)
        assert "64" in result

    def test_tmp_save_asset(self):
        result = generate_tmp_font_asset_script()
        assert "AssetDatabase.CreateAsset" in result
        assert "AssetDatabase.SaveAssets" in result

    def test_tmp_editor_namespace(self):
        result = generate_tmp_font_asset_script()
        assert "using UnityEditor;" in result

    def test_tmp_custom_font_path(self):
        result = generate_tmp_font_asset_script(font_path="Assets/Fonts/Custom.otf")
        assert "Custom.otf" in result

    def test_tmp_namespace(self):
        result = generate_tmp_font_asset_script(namespace="VB.Fonts")
        assert "namespace VB.Fonts" in result


# ---------------------------------------------------------------------------
# PIPE-10: TMP component setup
# ---------------------------------------------------------------------------


class TestTMPComponent:
    """Tests for generate_tmp_component_script()."""

    def test_tmp_component_setup(self):
        result = generate_tmp_component_script()
        assert "TextMeshProUGUI" in result

    def test_tmp_font_size(self):
        result = generate_tmp_component_script(font_size=48)
        assert "48" in result
        assert "fontSize" in result

    def test_tmp_rich_text(self):
        result = generate_tmp_component_script()
        assert "richText" in result

    def test_tmp_auto_sizing(self):
        result = generate_tmp_component_script(auto_sizing=True)
        assert "enableAutoSizing" in result
        assert "fontSizeMin" in result
        assert "fontSizeMax" in result

    def test_tmp_component_menu_item(self):
        result = generate_tmp_component_script()
        assert "MenuItem" in result
        assert "VeilBreakers/UI/Setup TMP Components" in result

    def test_tmp_component_color(self):
        result = generate_tmp_component_script(color=[0.8, 0.2, 0.1, 1.0])
        assert "0.8f" in result

    def test_tmp_component_alignment(self):
        result = generate_tmp_component_script()
        assert "TextAlignmentOptions" in result

    def test_tmp_component_overflow(self):
        result = generate_tmp_component_script()
        assert "TextOverflowModes" in result
        assert "overflowMode" in result

    def test_tmp_component_word_wrapping(self):
        result = generate_tmp_component_script()
        assert "enableWordWrapping" in result or "wordWrapping" in result

    def test_tmp_component_undo(self):
        result = generate_tmp_component_script()
        assert "Undo" in result

    def test_tmp_component_selection(self):
        result = generate_tmp_component_script()
        assert "Selection.gameObjects" in result

    def test_tmp_component_fallback_fonts(self):
        result = generate_tmp_component_script()
        assert "fallbackFontAssetTable" in result

    def test_tmp_component_editor_namespace(self):
        result = generate_tmp_component_script()
        assert "using UnityEditor;" in result

    def test_tmp_component_namespace(self):
        result = generate_tmp_component_script(namespace="VB.UI")
        assert "namespace VB.UI" in result


# ===================================================================
# Plan 02 tests: Tutorial, Accessibility, Character Select, World Map,
#                Rarity VFX, Corruption VFX
# ===================================================================


# ---------------------------------------------------------------------------
# UIX-02: Tutorial System
# ---------------------------------------------------------------------------


class TestTutorialSystem:
    """Tests for generate_tutorial_system_script()."""

    def test_tutorial_returns_4_tuple(self):
        result = generate_tutorial_system_script()
        assert isinstance(result, tuple) and len(result) == 4

    def test_tutorial_has_so_data(self):
        data_so, _, _, _ = generate_tutorial_system_script()
        assert "ScriptableObject" in data_so
        assert "CreateAssetMenu" in data_so

    def test_tutorial_step_state_machine(self):
        _, manager, _, _ = generate_tutorial_system_script()
        assert "StartTutorial" in manager
        assert "AdvanceStep" in manager
        assert "SkipTutorial" in manager

    def test_tutorial_highlight_overlay(self):
        _, manager, _, _ = generate_tutorial_system_script()
        assert "_tooltipContainer" in manager
        assert "_highlightFrame" in manager

    def test_tutorial_primetween(self):
        _, manager, _, _ = generate_tutorial_system_script()
        assert "Tween." in manager
        assert "DOTween" not in manager

    def test_tutorial_uxml(self):
        _, _, uxml, _ = generate_tutorial_system_script()
        assert "ui:UXML" in uxml
        assert "VisualElement" in uxml

    def test_tutorial_uss(self):
        _, _, _, uss = generate_tutorial_system_script()
        assert ".tutorial" in uss
        assert "font-size" in uss

    def test_tutorial_step_data_fields(self):
        data_so, _, _, _ = generate_tutorial_system_script()
        assert "stepTitle" in data_so
        assert "stepDescription" in data_so
        assert "highlightRect" in data_so
        assert "requiredAction" in data_so
        assert "isOptional" in data_so

    def test_tutorial_events(self):
        _, manager, _, _ = generate_tutorial_system_script()
        assert "OnTutorialComplete" in manager
        assert "OnStepChanged" in manager

    def test_tutorial_custom_name(self):
        data_so, manager, _, _ = generate_tutorial_system_script(name="Onboarding")
        assert "OnboardingStepData" in data_so
        assert "OnboardingManager" in manager

    def test_tutorial_namespace(self):
        data_so, manager, _, _ = generate_tutorial_system_script(namespace="Game.Tutorial")
        assert "Game.Tutorial" in data_so
        assert "Game.Tutorial" in manager


# ---------------------------------------------------------------------------
# ACC-01: Accessibility
# ---------------------------------------------------------------------------


class TestAccessibility:
    """Tests for generate_accessibility_script()."""

    def test_accessibility_returns_3_tuple(self):
        result = generate_accessibility_script()
        assert isinstance(result, tuple) and len(result) == 3

    def test_accessibility_colorblind_modes(self):
        settings, shader, _ = generate_accessibility_script()
        assert "Protanopia" in settings
        assert "Deuteranopia" in settings
        assert "Tritanopia" in settings
        assert "Protanopia" in shader
        assert "Deuteranopia" in shader
        assert "Tritanopia" in shader

    def test_accessibility_shader_matrices(self):
        _, shader, _ = generate_accessibility_script()
        assert "0.170556992" in shader
        assert "0.33066007" in shader
        assert "0.1273989" in shader

    def test_accessibility_subtitle_scaling(self):
        settings, _, _ = generate_accessibility_script()
        assert "_subtitleScale" in settings

    def test_accessibility_screen_reader(self):
        settings, _, _ = generate_accessibility_script()
        assert "ScreenReaderEnabled" in settings

    def test_accessibility_motor(self):
        settings, _, _ = generate_accessibility_script()
        assert "ToggleInsteadOfHold" in settings
        assert "InputTimingMultiplier" in settings

    def test_accessibility_renderer_feature(self):
        _, _, renderer_feature = generate_accessibility_script()
        assert "ScriptableRendererFeature" in renderer_feature
        assert "RecordRenderGraph" in renderer_feature

    def test_accessibility_playerprefs(self):
        settings, _, _ = generate_accessibility_script()
        assert "PlayerPrefs" in settings

    def test_accessibility_no_dotween(self):
        settings, shader, feature = generate_accessibility_script()
        assert "DOTween" not in settings
        assert "DOTween" not in shader
        assert "DOTween" not in feature

    def test_accessibility_srgb_conversion(self):
        _, shader, _ = generate_accessibility_script()
        assert "SRGBToLinear" in shader
        assert "LinearToSRGB" in shader

    def test_accessibility_urp_shader(self):
        _, shader, _ = generate_accessibility_script()
        assert "UniversalPipeline" in shader
        assert "HLSLPROGRAM" in shader

    def test_accessibility_colorblind_mode_enum(self):
        settings, _, _ = generate_accessibility_script()
        assert "enum ColorblindMode" in settings
        assert "None = 0" in settings

    def test_accessibility_custom_name(self):
        settings, _, feature = generate_accessibility_script(name="A11y")
        assert "A11ySettings" in settings
        assert "A11yColorblindFeature" in feature

    def test_accessibility_namespace(self):
        settings, _, feature = generate_accessibility_script(namespace="Game.Settings")
        assert "Game.Settings" in settings
        assert "Game.Settings" in feature


# ---------------------------------------------------------------------------
# VB-09: Character Select
# ---------------------------------------------------------------------------


class TestCharacterSelect:
    """Tests for generate_character_select_script()."""

    def test_character_select_returns_4_tuple(self):
        result = generate_character_select_script()
        assert isinstance(result, tuple) and len(result) == 4

    def test_character_select_hero_paths(self):
        _, manager, _, _ = generate_character_select_script()
        assert "IRONBOUND" in manager
        assert "FANGBORN" in manager
        assert "VOIDTOUCHED" in manager

    def test_character_select_all_4_paths(self):
        _, manager, _, _ = generate_character_select_script()
        assert "UNCHAINED" in manager
        assert "IRONBOUND" in manager

    def test_character_select_carousel(self):
        _, manager, _, _ = generate_character_select_script()
        assert "NavigatePrevious" in manager
        assert "NavigateNext" in manager

    def test_character_select_name_entry(self):
        _, manager, _, _ = generate_character_select_script()
        assert "ValidateName" in manager
        assert "3" in manager
        assert "20" in manager

    def test_character_select_embark(self):
        _, manager, _, _ = generate_character_select_script()
        assert "OnCharacterCreated" in manager

    def test_character_select_primetween(self):
        _, manager, _, _ = generate_character_select_script()
        assert "Sequence.Create" in manager

    def test_character_select_uxml_uss(self):
        _, _, uxml, uss = generate_character_select_script()
        assert "ui:UXML" in uxml
        assert "font-size" in uss

    def test_character_select_so_data(self):
        data_so, _, _, _ = generate_character_select_script()
        assert "CreateAssetMenu" in data_so
        assert "pathName" in data_so
        assert "baseStrength" in data_so

    def test_character_select_appearance(self):
        _, manager, _, _ = generate_character_select_script()
        assert "SkinColor" in manager
        assert "HairStyle" in manager
        assert "ArmorTint" in manager

    def test_character_select_custom_paths(self):
        _, manager, _, _ = generate_character_select_script(hero_paths=["A", "B", "C"])
        assert '"A"' in manager
        assert '"B"' in manager
        assert '"C"' in manager

    def test_character_select_no_dotween(self):
        _, manager, _, _ = generate_character_select_script()
        assert "DOTween" not in manager

    def test_character_select_namespace(self):
        data_so, manager, _, _ = generate_character_select_script(namespace="Game.UI")
        assert "Game.UI" in data_so
        assert "Game.UI" in manager


# ---------------------------------------------------------------------------
# RPG-08: World Map
# ---------------------------------------------------------------------------


class TestWorldMap:
    """Tests for generate_world_map_script()."""

    def test_world_map_returns_2_tuple(self):
        result = generate_world_map_script()
        assert isinstance(result, tuple) and len(result) == 2

    def test_world_map_terrain_data(self):
        editor, _ = generate_world_map_script()
        assert "terrainData" in editor
        assert "GetHeights" in editor

    def test_world_map_fog_of_war(self):
        _, runtime = generate_world_map_script()
        assert "_fogMask" in runtime

    def test_world_map_player_position(self):
        _, runtime = generate_world_map_script()
        assert "WorldToMapUV" in runtime

    def test_world_map_location_markers(self):
        _, runtime = generate_world_map_script()
        assert "MapLocation" in runtime
        assert "AddLocation" in runtime

    def test_world_map_menu_item(self):
        editor, _ = generate_world_map_script()
        assert "MenuItem" in editor

    def test_world_map_heightmap_color_mapping(self):
        editor, _ = generate_world_map_script()
        assert "waterLevel" in editor
        assert "Color.Lerp" in editor

    def test_world_map_zoom_pan(self):
        _, runtime = generate_world_map_script()
        assert "SetZoom" in runtime
        assert "Pan" in runtime

    def test_world_map_custom_resolution(self):
        editor, runtime = generate_world_map_script(map_resolution=1024, fog_resolution=512)
        assert "1024" in editor
        assert "512" in runtime

    def test_world_map_primetween(self):
        _, runtime = generate_world_map_script()
        assert "Tween." in runtime

    def test_world_map_no_dotween(self):
        editor, runtime = generate_world_map_script()
        assert "DOTween" not in editor
        assert "DOTween" not in runtime

    def test_world_map_namespace(self):
        editor, runtime = generate_world_map_script(namespace="Game.Map")
        assert "Game.Map" in editor
        assert "Game.Map" in runtime


# ---------------------------------------------------------------------------
# EQUIP-07: Rarity VFX
# ---------------------------------------------------------------------------


class TestRarityVFX:
    """Tests for generate_rarity_vfx_script()."""

    def test_rarity_5_tiers(self):
        cs = generate_rarity_vfx_script()
        assert "Common" in cs
        assert "Uncommon" in cs
        assert "Rare" in cs
        assert "Epic" in cs
        assert "Legendary" in cs

    def test_rarity_particle_system(self):
        cs = generate_rarity_vfx_script()
        assert "ParticleSystem" in cs

    def test_rarity_emission_glow(self):
        cs = generate_rarity_vfx_script()
        assert "_EmissionColor" in cs
        assert "GlowIntensities" in cs

    def test_rarity_set_rarity_method(self):
        cs = generate_rarity_vfx_script()
        assert "SetRarity" in cs

    def test_rarity_colors(self):
        cs = generate_rarity_vfx_script()
        assert "0.5f, 0.5f, 0.5f" in cs  # gray
        assert "0.2f, 0.8f, 0.2f" in cs  # green
        assert "0.2f, 0.4f, 1.0f" in cs  # blue
        assert "0.6f, 0.2f, 0.9f" in cs  # purple
        assert "1.0f, 0.8f, 0.1f" in cs  # gold

    def test_rarity_enum(self):
        cs = generate_rarity_vfx_script()
        assert "enum ItemRarity" in cs
        assert "Common = 0" in cs
        assert "Legendary = 4" in cs

    def test_rarity_legendary_sparkle(self):
        cs = generate_rarity_vfx_script()
        assert "_legendarySparkleSystem" in cs

    def test_rarity_material_property_block(self):
        cs = generate_rarity_vfx_script()
        assert "MaterialPropertyBlock" in cs
        assert "SetPropertyBlock" in cs

    def test_rarity_particle_rates(self):
        cs = generate_rarity_vfx_script()
        assert "ParticleRates" in cs

    def test_rarity_no_dotween(self):
        cs = generate_rarity_vfx_script()
        assert "DOTween" not in cs

    def test_rarity_namespace(self):
        cs = generate_rarity_vfx_script(namespace="Game.VFX")
        assert "Game.VFX" in cs


# ---------------------------------------------------------------------------
# EQUIP-08: Corruption VFX
# ---------------------------------------------------------------------------


class TestCorruptionVFX:
    """Tests for generate_corruption_vfx_script()."""

    def test_corruption_amount_property(self):
        cs = generate_corruption_vfx_script()
        assert "_CorruptionAmount" in cs

    def test_corruption_vein_intensity(self):
        cs = generate_corruption_vfx_script()
        assert "_VeinIntensity" in cs

    def test_corruption_color_shift(self):
        cs = generate_corruption_vfx_script()
        assert "Color.Lerp" in cs
        assert "_corruptionColor" in cs

    def test_corruption_particle_scaling(self):
        cs = generate_corruption_vfx_script()
        assert "_corruptionParticles" in cs
        assert "rateOverTime" in cs
        assert "_maxParticleRate" in cs

    def test_corruption_threshold_effects(self):
        cs = generate_corruption_vfx_script()
        assert "0.25f" in cs
        assert "0.5f" in cs
        assert "0.75f" in cs

    def test_corruption_set_method(self):
        cs = generate_corruption_vfx_script()
        assert "SetCorruption" in cs

    def test_corruption_primetween_pulse(self):
        cs = generate_corruption_vfx_script()
        assert "Tween.Custom" in cs
        assert "Ease.InOutSine" in cs
        assert "CycleMode.Yoyo" in cs

    def test_corruption_emission_glow(self):
        cs = generate_corruption_vfx_script()
        assert "_EmissionColor" in cs
        assert "corruption * 2f" in cs

    def test_corruption_vein_threshold(self):
        cs = generate_corruption_vfx_script()
        assert "corruption * 1.5f" in cs

    def test_corruption_pulse_at_100(self):
        cs = generate_corruption_vfx_script()
        assert "corruption >= 1.0f" in cs
        assert "_pulseTween" in cs

    def test_corruption_clamp(self):
        cs = generate_corruption_vfx_script()
        assert "Mathf.Clamp01" in cs

    def test_corruption_no_dotween(self):
        cs = generate_corruption_vfx_script()
        assert "DOTween" not in cs

    def test_corruption_namespace(self):
        cs = generate_corruption_vfx_script(namespace="Game.Equipment")
        assert "Game.Equipment" in cs

    def test_corruption_burst_config(self):
        cs = generate_corruption_vfx_script()
        assert "SetBursts" in cs
        assert "ParticleSystem.Burst" in cs
