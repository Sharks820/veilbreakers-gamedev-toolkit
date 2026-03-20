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
        assert "BLAZE" in result

    def test_damage_numbers_all_10_brands(self):
        result = generate_damage_numbers_script("DmgNum")
        for brand in ["IRON", "VENOM", "SURGE", "DREAD", "BLAZE",
                       "FROST", "VOID", "HOLY", "NATURE", "SHADOW"]:
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
