"""Functional test covering every Unity MCP tool and action (7 tools, 39 actions).

Since we cannot connect to a live Unity instance, this test verifies:
1. Every tool function exists and is importable
2. Every C# template generator produces valid output with default params
3. Generated C# contains expected Unity API calls and keywords
4. Pure-logic components (WCAG checker, screenshot diff, UXML validation)
   produce correct results with known inputs

Tools:
    1. unity_editor   (6 actions)
    2. unity_vfx      (10 actions)
    3. unity_audio    (10 actions)
    4. unity_ui       (5 actions)
    5. unity_scene    (8 actions)
    6. unity_gameplay (7 actions)
    7. unity_performance (5 actions)
"""

from __future__ import annotations

import json
import os
import struct
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Tool 1: unity_editor (6 actions)
# ---------------------------------------------------------------------------

from veilbreakers_mcp.shared.unity_templates.editor_templates import (
    generate_console_log_script,
    generate_gemini_review_script,
    generate_play_mode_script,
    generate_recompile_script,
    generate_screenshot_script,
)


class TestUnityEditor:
    """Tool 1 -- unity_editor: 6 actions."""

    # -- recompile --

    def test_recompile_returns_string(self):
        cs = generate_recompile_script()
        assert isinstance(cs, str)
        assert len(cs) > 100

    def test_recompile_has_asset_database_refresh(self):
        cs = generate_recompile_script()
        assert "AssetDatabase.Refresh" in cs

    def test_recompile_has_menu_item(self):
        cs = generate_recompile_script()
        assert '[MenuItem("VeilBreakers/' in cs

    def test_recompile_writes_result_json(self):
        cs = generate_recompile_script()
        assert "vb_result.json" in cs

    # -- enter_play_mode --

    def test_enter_play_mode_returns_string(self):
        cs = generate_play_mode_script(enter=True)
        assert isinstance(cs, str)
        assert len(cs) > 100

    def test_enter_play_mode_has_editor_application(self):
        cs = generate_play_mode_script(enter=True)
        assert "EditorApplication.EnterPlaymode" in cs
        assert "EditorApplication.isPlaying" not in cs or "EnterPlaymode" in cs

    def test_enter_play_mode_menu_item(self):
        cs = generate_play_mode_script(enter=True)
        assert "Enter Play Mode" in cs

    # -- exit_play_mode --

    def test_exit_play_mode_returns_string(self):
        cs = generate_play_mode_script(enter=False)
        assert isinstance(cs, str)

    def test_exit_play_mode_has_editor_application(self):
        cs = generate_play_mode_script(enter=False)
        assert "EditorApplication.ExitPlaymode" in cs

    def test_exit_play_mode_menu_item(self):
        cs = generate_play_mode_script(enter=False)
        assert "Exit Play Mode" in cs

    # -- screenshot --

    def test_screenshot_returns_string(self):
        cs = generate_screenshot_script()
        assert isinstance(cs, str)

    def test_screenshot_has_screen_capture(self):
        cs = generate_screenshot_script()
        assert "ScreenCapture.CaptureScreenshot" in cs

    def test_screenshot_default_path(self):
        cs = generate_screenshot_script()
        assert "Screenshots/vb_capture.png" in cs

    def test_screenshot_custom_params(self):
        cs = generate_screenshot_script(output_path="custom/shot.png", supersize=2)
        assert "custom/shot.png" in cs
        assert "int supersizeFactor = 2" in cs

    def test_screenshot_rejects_bad_supersize(self):
        with pytest.raises(ValueError, match="supersize") as exc_info:
            generate_screenshot_script(supersize=0)
        assert "supersize" in str(exc_info.value).lower()

    # -- console_logs --

    def test_console_logs_returns_string(self):
        cs = generate_console_log_script()
        assert isinstance(cs, str)

    def test_console_logs_has_log_message_received(self):
        cs = generate_console_log_script()
        assert "logMessageReceived" in cs

    def test_console_logs_default_filter_all(self):
        cs = generate_console_log_script(filter_type="all")
        assert "true  // No filter" in cs

    def test_console_logs_error_filter(self):
        cs = generate_console_log_script(filter_type="error")
        assert "LogType.Error" in cs

    def test_console_logs_all_filter_types(self):
        for ft in ("all", "error", "warning", "log", "exception", "assert"):
            cs = generate_console_log_script(filter_type=ft)
            assert isinstance(cs, str)
            assert len(cs) > 100

    def test_console_logs_rejects_bad_filter(self):
        with pytest.raises(ValueError, match="filter_type") as exc_info:
            generate_console_log_script(filter_type="invalid")
        assert "filter_type" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    # -- gemini_review --

    def test_gemini_review_returns_string(self):
        cs = generate_gemini_review_script(
            screenshot_path="Screenshots/test.png",
            criteria=["lighting", "composition"],
        )
        assert isinstance(cs, str)

    def test_gemini_review_has_criteria(self):
        cs = generate_gemini_review_script(
            screenshot_path="Screenshots/test.png",
            criteria=["lighting", "composition"],
        )
        assert "lighting" in cs
        assert "composition" in cs

    def test_gemini_review_rejects_empty_criteria(self):
        with pytest.raises(ValueError, match="criteria") as exc_info:
            generate_gemini_review_script(
                screenshot_path="Screenshots/test.png",
                criteria=[],
            )
        assert "criteria" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Tool 2: unity_vfx (10 actions)
# ---------------------------------------------------------------------------

from veilbreakers_mcp.shared.unity_templates.vfx_templates import (
    BRAND_VFX_CONFIGS,
    ENV_VFX_CONFIGS,
    generate_ability_vfx_script,
    generate_aura_vfx_script,
    generate_brand_vfx_script,
    generate_environmental_vfx_script,
    generate_particle_vfx_script,
    generate_post_processing_script,
    generate_screen_effect_script,
    generate_trail_vfx_script,
)
from veilbreakers_mcp.shared.unity_templates.shader_templates import (
    generate_corruption_shader,
    generate_damage_overlay_shader,
    generate_dissolve_shader,
    generate_foliage_shader,
    generate_force_field_shader,
    generate_outline_shader,
    generate_water_shader,
)


class TestUnityVFX:
    """Tool 2 -- unity_vfx: 10 actions (particle, 5 brands, 5 env, trail, aura, post, screen, ability + 7 shaders)."""

    # -- particle VFX --

    def test_particle_vfx_returns_string(self):
        cs = generate_particle_vfx_script(name="TestFire")
        assert isinstance(cs, str)
        assert "ParticleSystem" in cs

    def test_particle_vfx_has_emission_config(self):
        cs = generate_particle_vfx_script(name="TestFire")
        assert "rateOverTime" in cs or "startLifetime" in cs

    def test_particle_vfx_prefab_utility(self):
        cs = generate_particle_vfx_script(name="TestFire")
        assert "PrefabUtility.SaveAsPrefabAsset" in cs

    # -- brand VFX (all 5 brands) --

    @pytest.mark.parametrize("brand", list(BRAND_VFX_CONFIGS.keys()))
    def test_brand_vfx_all_brands(self, brand):
        cs = generate_brand_vfx_script(brand)
        assert isinstance(cs, str)
        assert brand in cs
        assert "ParticleSystem" in cs
        assert "DamageVFX" in cs

    def test_brand_vfx_rejects_unknown(self):
        with pytest.raises(ValueError, match="Unknown brand") as exc_info:
            generate_brand_vfx_script("NONEXISTENT")
        assert "NONEXISTENT" in str(exc_info.value)

    # -- environmental VFX (all 5 types) --

    @pytest.mark.parametrize("env_type", list(ENV_VFX_CONFIGS.keys()))
    def test_environmental_vfx_all_types(self, env_type):
        cs = generate_environmental_vfx_script(env_type)
        assert isinstance(cs, str)
        assert "ParticleSystem" in cs
        assert "gravityModifier" in cs

    def test_environmental_vfx_rejects_unknown(self):
        with pytest.raises(ValueError, match="Unknown effect_type") as exc_info:
            generate_environmental_vfx_script("blizzard")
        assert "blizzard" in str(exc_info.value)

    # -- trail VFX --

    def test_trail_vfx_returns_string(self):
        cs = generate_trail_vfx_script(name="SwordTrail")
        assert isinstance(cs, str)
        assert "TrailRenderer" in cs

    def test_trail_vfx_has_gradient(self):
        cs = generate_trail_vfx_script(name="SwordTrail", color=[1.0, 0.0, 0.0, 1.0])
        assert "Gradient" in cs
        assert "widthCurve" in cs

    # -- aura VFX --

    def test_aura_vfx_returns_string(self):
        cs = generate_aura_vfx_script(name="CorruptionGlow")
        assert isinstance(cs, str)
        assert "ParticleSystem" in cs

    def test_aura_vfx_is_looping(self):
        cs = generate_aura_vfx_script(name="CorruptionGlow")
        assert "main.loop = true" in cs

    # -- post-processing --

    def test_post_processing_returns_string(self):
        cs = generate_post_processing_script()
        assert isinstance(cs, str)

    def test_post_processing_has_volume(self):
        cs = generate_post_processing_script()
        assert "Volume" in cs
        assert "VolumeProfile" in cs

    def test_post_processing_has_bloom(self):
        cs = generate_post_processing_script()
        assert "Bloom" in cs
        assert "bloom.intensity" in cs

    def test_post_processing_has_depth_of_field(self):
        cs = generate_post_processing_script()
        assert "DepthOfField" in cs

    def test_post_processing_has_vignette(self):
        cs = generate_post_processing_script()
        assert "Vignette" in cs

    def test_post_processing_has_color_adjustments(self):
        cs = generate_post_processing_script()
        assert "ColorAdjustments" in cs

    # -- screen effects (all 5 types) --

    @pytest.mark.parametrize(
        "effect_type",
        ["camera_shake", "damage_vignette", "low_health_pulse", "poison_overlay", "heal_glow"],
    )
    def test_screen_effects_all_types(self, effect_type):
        cs = generate_screen_effect_script(effect_type)
        assert isinstance(cs, str)
        assert len(cs) > 100

    def test_screen_effect_camera_shake_has_impulse(self):
        cs = generate_screen_effect_script("camera_shake")
        assert "CinemachineImpulseSource" in cs
        assert "GenerateImpulse" in cs

    def test_screen_effect_overlay_has_canvas(self):
        cs = generate_screen_effect_script("damage_vignette")
        assert "Canvas" in cs
        assert "CanvasGroup" in cs

    def test_screen_effect_has_correct_class_names(self):
        cs = generate_screen_effect_script("damage_vignette")
        assert "VeilBreakers_ScreenEffect_DamageVignette" in cs
        cs2 = generate_screen_effect_script("heal_glow")
        assert "VeilBreakers_ScreenEffect_HealGlow" in cs2

    def test_screen_effect_rejects_unknown(self):
        with pytest.raises(ValueError, match="Unknown effect_type") as exc_info:
            generate_screen_effect_script("freeze")
        assert "freeze" in str(exc_info.value)

    # -- ability VFX --

    def test_ability_vfx_returns_string(self):
        cs = generate_ability_vfx_script(ability_name="Fireball")
        assert isinstance(cs, str)
        assert "AnimationEvent" in cs

    def test_ability_vfx_has_animation_utility(self):
        cs = generate_ability_vfx_script(ability_name="Fireball")
        assert "AnimationUtility.SetAnimationEvents" in cs

    # -- shader generators (7 shaders) --

    def test_dissolve_shader(self):
        shader = generate_dissolve_shader()
        assert 'Shader "VeilBreakers/Dissolve"' in shader
        assert "DissolveAmount" in shader
        assert "HLSLPROGRAM" in shader
        assert "clip(" in shader

    def test_force_field_shader(self):
        shader = generate_force_field_shader()
        assert 'Shader "VeilBreakers/ForceField"' in shader
        assert "FresnelPower" in shader
        assert "SampleSceneDepth" in shader

    def test_water_shader(self):
        shader = generate_water_shader()
        assert 'Shader "VeilBreakers/Water"' in shader
        assert "WaveAmplitude" in shader
        assert "positionOS.y +=" in shader

    def test_foliage_shader(self):
        shader = generate_foliage_shader()
        assert 'Shader "VeilBreakers/Foliage"' in shader
        assert "WindStrength" in shader
        assert "_Time" in shader
        assert "sin(" in shader or "cos(" in shader

    def test_outline_shader(self):
        shader = generate_outline_shader()
        assert 'Shader "VeilBreakers/Outline"' in shader
        assert "OutlineWidth" in shader
        assert "Cull Front" in shader
        assert "Cull Back" in shader

    def test_corruption_shader(self):
        shader = generate_corruption_shader()
        assert 'Shader "VeilBreakers/Corruption"' in shader
        assert "CorruptionAmount" in shader
        assert "lerp(" in shader

    def test_damage_overlay_shader(self):
        shader = generate_damage_overlay_shader()
        assert 'Shader "VeilBreakers/DamageOverlay"' in shader
        assert "Intensity" in shader
        assert "Queue" in shader


# ---------------------------------------------------------------------------
# Tool 3: unity_audio (10 actions)
# ---------------------------------------------------------------------------

from veilbreakers_mcp.shared.elevenlabs_client import ElevenLabsAudioClient
from veilbreakers_mcp.shared.unity_templates.audio_templates import (
    generate_adaptive_music_script,
    generate_animation_event_sfx_script,
    generate_audio_mixer_setup_script,
    generate_audio_pool_manager_script,
    generate_audio_zone_script,
    generate_footstep_manager_script,
)


class TestUnityAudio:
    """Tool 3 -- unity_audio: 10 actions."""

    # -- footstep manager --

    def test_footstep_manager_returns_string(self):
        cs = generate_footstep_manager_script()
        assert isinstance(cs, str)
        assert "VeilBreakers_FootstepManager" in cs

    def test_footstep_manager_has_surfaces(self):
        cs = generate_footstep_manager_script()
        for surface in ("stone", "wood", "grass", "metal", "water"):
            assert surface in cs

    def test_footstep_manager_has_audio_source(self):
        cs = generate_footstep_manager_script()
        assert "AudioSource" in cs
        assert "PlayOneShot" in cs

    def test_footstep_manager_has_raycast(self):
        cs = generate_footstep_manager_script()
        assert "Physics.Raycast" in cs

    def test_footstep_manager_custom_surfaces(self):
        cs = generate_footstep_manager_script(surfaces=["dirt", "sand"])
        assert "dirt" in cs
        assert "sand" in cs

    # -- adaptive music --

    def test_adaptive_music_returns_string(self):
        cs = generate_adaptive_music_script()
        assert isinstance(cs, str)
        assert "VeilBreakers_AdaptiveMusicManager" in cs

    def test_adaptive_music_has_crossfade(self):
        cs = generate_adaptive_music_script()
        assert "CrossfadeLayers" in cs
        assert "crossfadeDuration" in cs

    def test_adaptive_music_has_game_states(self):
        cs = generate_adaptive_music_script()
        for state in ("Exploration", "Combat", "Boss", "Town", "Stealth"):
            assert state in cs

    def test_adaptive_music_has_audio_source(self):
        cs = generate_adaptive_music_script()
        assert "AudioSource" in cs

    # -- audio zones (all 5 types) --

    @pytest.mark.parametrize("zone_type", ["cave", "outdoor", "indoor", "dungeon", "forest"])
    def test_audio_zone_all_types(self, zone_type):
        cs = generate_audio_zone_script(zone_type=zone_type)
        assert isinstance(cs, str)
        assert "AudioReverbZone" in cs
        assert zone_type.capitalize() in cs

    def test_audio_zone_has_reverb_params(self):
        cs = generate_audio_zone_script(zone_type="cave")
        assert "decayTime" in cs
        assert "reverbDelay" in cs
        assert "minDistance" in cs
        assert "maxDistance" in cs

    # -- mixer setup --

    def test_mixer_setup_returns_string(self):
        cs = generate_audio_mixer_setup_script()
        assert isinstance(cs, str)
        assert "AudioMixer" in cs

    def test_mixer_setup_has_groups(self):
        cs = generate_audio_mixer_setup_script()
        for group in ("Master", "SFX", "Music", "Voice", "Ambient", "UI"):
            assert group in cs

    def test_mixer_setup_has_find_matching_groups(self):
        cs = generate_audio_mixer_setup_script()
        assert "FindMatchingGroups" in cs

    # -- pool manager --

    def test_pool_manager_returns_string(self):
        cs = generate_audio_pool_manager_script()
        assert isinstance(cs, str)
        assert "VeilBreakers_AudioPoolManager" in cs

    def test_pool_manager_has_priority(self):
        cs = generate_audio_pool_manager_script()
        assert "priority" in cs.lower()
        assert "GetAvailableSource" in cs

    def test_pool_manager_has_ducking(self):
        cs = generate_audio_pool_manager_script()
        assert "StartDuck" in cs
        assert "StopDuck" in cs

    def test_pool_manager_custom_sizes(self):
        cs = generate_audio_pool_manager_script(pool_size=32, max_sources=64)
        assert "poolSize = 32" in cs
        assert "maxSources = 64" in cs

    # -- animation event SFX --

    def test_animation_event_sfx_returns_string(self):
        cs = generate_animation_event_sfx_script()
        assert isinstance(cs, str)
        assert "AnimationUtility.SetAnimationEvents" in cs

    def test_animation_event_sfx_has_events(self):
        cs = generate_animation_event_sfx_script()
        assert "AnimationEvent" in cs
        assert "PlayLeftFoot" in cs
        assert "PlayRightFoot" in cs

    # -- ElevenLabs stub mode: generate_sfx returns valid WAV --

    def test_elevenlabs_stub_generate_sfx(self, tmp_path):
        client = ElevenLabsAudioClient(api_key="")
        assert client.stub_mode is True

        output_path = str(tmp_path / "test_sfx.wav")
        result = client.generate_sfx(
            description="sword clash",
            duration_seconds=1.0,
            output_path=output_path,
        )

        assert result["stub"] is True
        assert result["path"] == output_path
        assert os.path.exists(output_path)

        # Verify WAV header
        with open(output_path, "rb") as f:
            data = f.read(44)

        assert data[:4] == b"RIFF"
        assert data[8:12] == b"WAVE"
        assert data[12:16] == b"fmt "
        assert data[36:40] == b"data"

        # Verify PCM format (format code 1)
        fmt_code = struct.unpack("<H", data[20:22])[0]
        assert fmt_code == 1

        # Verify mono channel
        channels = struct.unpack("<H", data[22:24])[0]
        assert channels == 1

        # Verify 44100 Hz sample rate
        sample_rate = struct.unpack("<I", data[24:28])[0]
        assert sample_rate == 44100

    def test_elevenlabs_stub_generate_music_loop(self, tmp_path):
        client = ElevenLabsAudioClient(api_key="")
        output_path = str(tmp_path / "loop.wav")
        result = client.generate_music_loop(
            theme="combat",
            duration_seconds=5.0,
            output_path=output_path,
        )
        assert result["stub"] is True
        assert os.path.exists(output_path)
        with open(output_path, "rb") as f:
            assert f.read(4) == b"RIFF"

    def test_elevenlabs_stub_generate_voice_line(self, tmp_path):
        client = ElevenLabsAudioClient(api_key="")
        output_path = str(tmp_path / "voice.wav")
        result = client.generate_voice_line(
            text="Fear the Veil",
            output_path=output_path,
        )
        assert result["stub"] is True
        assert os.path.exists(output_path)

    def test_elevenlabs_stub_generate_ambient_layers(self, tmp_path):
        client = ElevenLabsAudioClient(api_key="")
        output_dir = str(tmp_path / "ambient")
        result = client.generate_ambient_layers(
            biome="cave",
            output_dir=output_dir,
        )
        assert result["stub"] is True
        assert len(result["layer_paths"]) == 3  # cave has 3 default layers
        for p in result["layer_paths"]:
            assert os.path.exists(p)


# ---------------------------------------------------------------------------
# Tool 4: unity_ui (5 actions)
# ---------------------------------------------------------------------------

from veilbreakers_mcp.shared.unity_templates.ui_templates import (
    generate_responsive_test_script,
    generate_uxml_screen,
    generate_uss_stylesheet,
    validate_uxml_layout,
)
from veilbreakers_mcp.shared.wcag_checker import (
    check_wcag_aa,
    contrast_ratio,
    relative_luminance,
)
from veilbreakers_mcp.shared.screenshot_diff import compare_screenshots


class TestUnityUI:
    """Tool 4 -- unity_ui: 5 actions."""

    # -- generate_uxml_screen --

    def test_uxml_screen_returns_xml(self):
        spec = {
            "title": "Main Menu",
            "elements": [
                {"type": "button", "text": "Play", "name": "btn-play"},
                {"type": "label", "text": "Version 1.0"},
            ],
        }
        uxml = generate_uxml_screen(spec)
        assert '<?xml version="1.0"' in uxml
        assert 'xmlns:ui="UnityEngine.UIElements"' in uxml
        assert "Main Menu" in uxml
        assert "Play" in uxml

    def test_uxml_screen_nested_elements(self):
        spec = {
            "title": "Inventory",
            "elements": [
                {
                    "type": "panel",
                    "name": "container",
                    "children": [
                        {"type": "label", "text": "Slots"},
                        {"type": "button", "text": "Use Item"},
                    ],
                },
            ],
        }
        uxml = generate_uxml_screen(spec)
        assert "container" in uxml
        assert "Slots" in uxml
        assert "Use Item" in uxml

    # -- generate_uss_stylesheet --

    def test_uss_stylesheet_returns_css(self):
        uss = generate_uss_stylesheet()
        assert ".screen-root" in uss
        assert ".vb-button" in uss
        assert ".vb-label" in uss
        assert "background-color:" in uss

    def test_uss_stylesheet_dark_fantasy_theme(self):
        uss = generate_uss_stylesheet(theme="dark_fantasy")
        assert "#1a1a2e" in uss  # primary bg
        assert "#4a0e4e" in uss  # accent

    def test_uss_stylesheet_rejects_unknown_theme(self):
        with pytest.raises(ValueError, match="Unknown theme") as exc_info:
            generate_uss_stylesheet(theme="light")
        assert "light" in str(exc_info.value)

    # -- generate_responsive_test_script --

    def test_responsive_test_returns_string(self):
        cs = generate_responsive_test_script(uxml_path="Assets/UI/MainMenu.uxml")
        assert isinstance(cs, str)
        assert "ScreenCapture" in cs

    def test_responsive_test_has_resolutions(self):
        cs = generate_responsive_test_script(uxml_path="Assets/UI/MainMenu.uxml")
        assert "1920, 1080" in cs
        assert "3840, 2160" in cs
        assert "800, 600" in cs

    def test_responsive_test_custom_resolutions(self):
        cs = generate_responsive_test_script(
            uxml_path="Assets/UI/HUD.uxml",
            resolutions=[(640, 480), (1024, 768)],
        )
        assert "640, 480" in cs
        assert "1024, 768" in cs
        assert "1920, 1080" not in cs

    # -- validate_uxml_layout (functional) --

    def test_validate_uxml_valid_layout(self):
        uxml = """<?xml version="1.0" encoding="utf-8"?>
<ui:UXML xmlns:ui="UnityEngine.UIElements">
    <ui:VisualElement name="root" class="screen-root">
        <ui:Label text="Hello" name="title" />
        <ui:Button text="Click" name="btn-click" />
    </ui:VisualElement>
</ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is True
        assert result["issues"] == []

    def test_validate_uxml_duplicate_name(self):
        uxml = """<?xml version="1.0" encoding="utf-8"?>
<ui:UXML xmlns:ui="UnityEngine.UIElements">
    <ui:VisualElement name="root">
        <ui:Label text="A" name="dup" />
        <ui:Label text="B" name="dup" />
    </ui:VisualElement>
</ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is False
        dup_issues = [i for i in result["issues"] if i["type"] == "duplicate_name"]
        assert len(dup_issues) == 1
        assert dup_issues[0]["element"] == "dup"

    def test_validate_uxml_zero_size(self):
        uxml = """<?xml version="1.0" encoding="utf-8"?>
<ui:UXML xmlns:ui="UnityEngine.UIElements">
    <ui:VisualElement name="root">
        <ui:VisualElement name="empty" style="width: 0; height: 50px" />
    </ui:VisualElement>
</ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is False
        zero_issues = [i for i in result["issues"] if i["type"] == "zero_size"]
        assert len(zero_issues) >= 1

    def test_validate_uxml_overflow(self):
        uxml = """<?xml version="1.0" encoding="utf-8"?>
<ui:UXML xmlns:ui="UnityEngine.UIElements">
    <ui:VisualElement name="parent" style="width: 100px; height: 100px">
        <ui:VisualElement name="child" style="width: 200px; height: 50px" />
    </ui:VisualElement>
</ui:UXML>"""
        result = validate_uxml_layout(uxml)
        assert result["valid"] is False
        overflow_issues = [i for i in result["issues"] if i["type"] == "overflow"]
        assert len(overflow_issues) >= 1
        assert "200" in overflow_issues[0]["details"]

    def test_validate_uxml_malformed(self):
        result = validate_uxml_layout("<not valid xml")
        assert result["valid"] is False
        assert result["issues"][0]["type"] == "parse_error"

    # -- wcag_checker (functional) --

    def test_wcag_contrast_ratio_black_white(self):
        ratio = contrast_ratio((0, 0, 0), (255, 255, 255))
        assert ratio == pytest.approx(21.0, rel=0.01)

    def test_wcag_contrast_ratio_same_color(self):
        ratio = contrast_ratio((128, 128, 128), (128, 128, 128))
        assert ratio == pytest.approx(1.0, rel=0.01)

    def test_wcag_contrast_ratio_symmetric(self):
        ratio_a = contrast_ratio((50, 100, 200), (200, 200, 200))
        ratio_b = contrast_ratio((200, 200, 200), (50, 100, 200))
        assert ratio_a == pytest.approx(ratio_b)

    def test_wcag_check_aa_pass(self):
        # White on black should pass
        assert check_wcag_aa((255, 255, 255), (0, 0, 0)) is True

    def test_wcag_check_aa_fail(self):
        # Gray-on-gray with low contrast should fail
        assert check_wcag_aa((180, 180, 180), (200, 200, 200)) is False

    def test_wcag_check_aa_large_text_threshold(self):
        # Large text has lower threshold (3.0 vs 4.5)
        fg = (150, 150, 150)
        bg = (255, 255, 255)
        ratio = contrast_ratio(fg, bg)
        # This particular combo: ratio ~= 1.98, fails both
        # Use a combo that passes 3.0 but fails 4.5
        fg2 = (100, 100, 100)
        bg2 = (255, 255, 255)
        ratio2 = contrast_ratio(fg2, bg2)
        assert ratio2 > 3.0
        # Check large_text=True passes, normal text might not
        assert check_wcag_aa(fg2, bg2, large_text=True) is True

    def test_wcag_relative_luminance_bounds(self):
        assert relative_luminance(0, 0, 0) == pytest.approx(0.0, abs=0.001)
        assert relative_luminance(1, 1, 1) == pytest.approx(1.0, abs=0.001)

    # -- screenshot_diff (functional) --

    def test_screenshot_diff_identical_images(self, tmp_path):
        from PIL import Image

        img = Image.new("RGB", (100, 100), (128, 64, 32))
        ref_path = str(tmp_path / "ref.png")
        cur_path = str(tmp_path / "cur.png")
        img.save(ref_path)
        img.save(cur_path)
        img.close()

        result = compare_screenshots(ref_path, cur_path)
        assert result["match"] is True
        assert result["diff_percentage"] == 0.0
        assert result["diff_image_path"] is None

    def test_screenshot_diff_different_images(self, tmp_path):
        from PIL import Image

        ref_img = Image.new("RGB", (100, 100), (0, 0, 0))
        cur_img = Image.new("RGB", (100, 100), (255, 255, 255))
        ref_path = str(tmp_path / "ref.png")
        cur_path = str(tmp_path / "cur.png")
        ref_img.save(ref_path)
        cur_img.save(cur_path)
        ref_img.close()
        cur_img.close()

        result = compare_screenshots(ref_path, cur_path)
        assert result["match"] is False
        assert result["diff_percentage"] > 0.5
        assert result["diff_image_path"] is not None
        assert os.path.exists(result["diff_image_path"])

    def test_screenshot_diff_different_sizes(self, tmp_path):
        from PIL import Image

        ref_img = Image.new("RGB", (100, 100), (128, 128, 128))
        cur_img = Image.new("RGB", (200, 200), (128, 128, 128))
        ref_path = str(tmp_path / "ref.png")
        cur_path = str(tmp_path / "cur.png")
        ref_img.save(ref_path)
        cur_img.save(cur_path)
        ref_img.close()
        cur_img.close()

        result = compare_screenshots(ref_path, cur_path)
        assert result["reference_size"] == (100, 100)
        assert result["current_size"] == (200, 200)
        # Resized same-color images should still match
        assert result["match"] is True


# ---------------------------------------------------------------------------
# Tool 5: unity_scene (8 actions)
# ---------------------------------------------------------------------------

from veilbreakers_mcp.shared.unity_templates.scene_templates import (
    generate_animation_rigging_script,
    generate_animator_controller_script,
    generate_avatar_config_script,
    generate_lighting_setup_script,
    generate_navmesh_bake_script,
    generate_object_scatter_script,
    generate_terrain_setup_script,
    generate_tiled_terrain_setup_script,
)


class TestUnityScene:
    """Tool 5 -- unity_scene: 8 actions."""

    # -- terrain --

    def test_terrain_returns_string(self):
        cs = generate_terrain_setup_script(heightmap_path="Assets/Heightmaps/test.raw")
        assert isinstance(cs, str)

    def test_terrain_has_terrain_data(self):
        cs = generate_terrain_setup_script(heightmap_path="Assets/Heightmaps/test.raw")
        assert "TerrainData" in cs
        assert "heightmapResolution" in cs

    def test_terrain_has_set_heights(self):
        cs = generate_terrain_setup_script(heightmap_path="Assets/Heightmaps/test.raw")
        assert "SetHeights" in cs

    def test_terrain_custom_size(self):
        cs = generate_terrain_setup_script(
            heightmap_path="Assets/Heightmaps/test.raw",
            size=(2000, 800, 2000),
            resolution=1025,
        )
        assert "2000" in cs
        assert "800" in cs
        assert "1025" in cs

    def test_terrain_has_alphamap_path(self):
        layers = [
            {"texture_path": "Assets/Textures/grass.png", "tiling": 10.0},
            {"texture_path": "Assets/Textures/rock.png", "tiling": 5.0},
            {"texture_path": "Assets/Textures/dirt.png", "tiling": 8.0},
            {"texture_path": "Assets/Textures/snow.png", "tiling": 12.0},
        ]
        cs = generate_terrain_setup_script(
            heightmap_path="Assets/Heightmaps/test.raw",
            splatmap_layers=layers,
            alphamap_path="Assets/Heightmaps/test_alphamap.raw",
        )
        assert "test_alphamap.raw" in cs
        assert "File.Exists(alphamapPath)" in cs

    def test_tiled_terrain_returns_string(self):
        cs = generate_tiled_terrain_setup_script(
            tiles=[{"heightmap_path": "Assets/Heightmaps/tile_0.raw", "grid_x": 0, "grid_y": 0}]
        )
        assert isinstance(cs, str)

    def test_tiled_terrain_has_parent(self):
        cs = generate_tiled_terrain_setup_script(
            tiles=[{"heightmap_path": "Assets/Heightmaps/tile_0.raw", "grid_x": 0, "grid_y": 0}],
            parent_name="VB_TerrainRoot",
        )
        assert "VB_TerrainRoot" in cs
        assert "Setup Tiled Terrain" in cs
        assert "SetNeighbors" in cs
        assert ".GetComponent<Terrain>()" in cs

    @pytest.mark.asyncio
    async def test_setup_tiled_terrain_action(self):
        from veilbreakers_mcp.unity_tools import scene as scene_tool

        with patch.object(scene_tool, "_write_to_unity", return_value="/tmp/VeilBreakers_TiledTerrainSetup.cs"):
            result = await scene_tool.unity_scene(
                action="setup_tiled_terrain",
                terrain_tiles=[{"heightmap_path": "Assets/Heightmaps/tile_0.raw", "grid_x": 0, "grid_y": 0}],
                terrain_size=[1000, 600, 1000],
                terrain_resolution=513,
            )

        data = json.loads(result)
        assert data["status"] == "success"
        assert data["action"] == "setup_tiled_terrain"
        assert data["tile_count"] == 1

    @pytest.mark.asyncio
    async def test_setup_terrain_action_with_alphamap(self):
        from veilbreakers_mcp.unity_tools import scene as scene_tool

        layers = [
            {"texture_path": "Assets/Textures/grass.png", "tiling": 10.0},
            {"texture_path": "Assets/Textures/rock.png", "tiling": 5.0},
            {"texture_path": "Assets/Textures/dirt.png", "tiling": 8.0},
            {"texture_path": "Assets/Textures/snow.png", "tiling": 12.0},
        ]

        with patch.object(scene_tool, "_write_to_unity", return_value="/tmp/VeilBreakers_TerrainSetup.cs"):
            result = await scene_tool.unity_scene(
                action="setup_terrain",
                heightmap_path="Assets/Heightmaps/test.raw",
                alphamap_path="Assets/Heightmaps/test_alphamap.raw",
                splatmap_layers=layers,
                terrain_size=[1000, 600, 1000],
                terrain_resolution=513,
            )

        data = json.loads(result)
        assert data["status"] == "success"
        assert data["action"] == "setup_terrain"

    # -- object scatter --

    def test_scatter_returns_string(self):
        cs = generate_object_scatter_script(prefab_paths=["Assets/Prefabs/Tree.prefab"])
        assert isinstance(cs, str)

    def test_scatter_has_instantiate(self):
        cs = generate_object_scatter_script(prefab_paths=["Assets/Prefabs/Tree.prefab"])
        assert "InstantiatePrefab" in cs

    def test_scatter_has_terrain_sampling(self):
        cs = generate_object_scatter_script(prefab_paths=["Assets/Prefabs/Tree.prefab"])
        assert "SampleHeight" in cs
        assert "GetInterpolatedNormal" in cs

    def test_scatter_rejects_empty_prefabs(self):
        with pytest.raises(ValueError, match="prefab_paths") as exc_info:
            generate_object_scatter_script(prefab_paths=[])
        assert "prefab" in str(exc_info.value).lower()

    # -- lighting --

    def test_lighting_returns_string(self):
        cs = generate_lighting_setup_script()
        assert isinstance(cs, str)

    def test_lighting_has_render_settings(self):
        cs = generate_lighting_setup_script()
        assert "RenderSettings" in cs
        assert "RenderSettings.ambientLight" in cs
        assert "RenderSettings.fog" in cs

    def test_lighting_has_directional_light(self):
        cs = generate_lighting_setup_script()
        assert "LightType.Directional" in cs

    def test_lighting_has_volume(self):
        cs = generate_lighting_setup_script()
        assert "Volume" in cs
        assert "VolumeProfile" in cs

    def test_lighting_time_of_day_presets(self):
        for tod in ("dawn", "noon", "dusk", "night", "overcast"):
            cs = generate_lighting_setup_script(time_of_day=tod)
            assert isinstance(cs, str)
            assert len(cs) > 100

    # -- navmesh --

    def test_navmesh_returns_string(self):
        cs = generate_navmesh_bake_script()
        assert isinstance(cs, str)

    def test_navmesh_has_surface(self):
        cs = generate_navmesh_bake_script()
        assert "NavMeshSurface" in cs

    def test_navmesh_has_build(self):
        cs = generate_navmesh_bake_script()
        assert "BuildNavMesh" in cs

    def test_navmesh_has_agent_settings(self):
        cs = generate_navmesh_bake_script()
        assert "agentRadius" in cs
        assert "agentHeight" in cs

    def test_navmesh_custom_agent(self):
        cs = generate_navmesh_bake_script(
            agent_radius=0.8, agent_height=3.0, max_slope=35.0
        )
        assert "0.8f" in cs
        assert "3.0f" in cs or "3f" in cs
        assert "35" in cs

    # -- animator controller --

    def test_animator_returns_string(self):
        cs = generate_animator_controller_script(
            name="MobAnimator",
            states=[{"name": "Idle"}, {"name": "Walk"}, {"name": "Attack"}],
            transitions=[
                {"from_state": "Idle", "to_state": "Walk", "conditions": [], "has_exit_time": False},
            ],
            parameters=[{"name": "Speed", "type": "float"}],
        )
        assert isinstance(cs, str)

    def test_animator_has_controller(self):
        cs = generate_animator_controller_script(
            name="MobAnimator",
            states=[{"name": "Idle"}],
            transitions=[],
            parameters=[],
        )
        assert "AnimatorController" in cs

    def test_animator_has_state_machine(self):
        cs = generate_animator_controller_script(
            name="MobAnimator",
            states=[{"name": "Idle"}, {"name": "Run"}],
            transitions=[],
            parameters=[],
        )
        assert "stateMachine" in cs
        assert "AddState" in cs

    def test_animator_rejects_empty_states(self):
        with pytest.raises(ValueError, match="states") as exc_info:
            generate_animator_controller_script(
                name="Empty",
                states=[],
                transitions=[],
                parameters=[],
            )
        assert "state" in str(exc_info.value).lower()

    # -- avatar config --

    def test_avatar_returns_string(self):
        cs = generate_avatar_config_script(fbx_path="Assets/Models/Character.fbx")
        assert isinstance(cs, str)

    def test_avatar_has_model_importer(self):
        cs = generate_avatar_config_script(fbx_path="Assets/Models/Character.fbx")
        assert "ModelImporter" in cs
        assert "animationType" in cs

    def test_avatar_humanoid_type(self):
        cs = generate_avatar_config_script(
            fbx_path="Assets/Models/Character.fbx",
            animation_type="Humanoid",
        )
        assert "ModelImporterAnimationType.Human" in cs

    def test_avatar_generic_type(self):
        cs = generate_avatar_config_script(
            fbx_path="Assets/Models/Monster.fbx",
            animation_type="Generic",
        )
        assert "ModelImporterAnimationType.Generic" in cs

    def test_avatar_has_reimport(self):
        cs = generate_avatar_config_script(fbx_path="Assets/Models/Character.fbx")
        assert "SaveAndReimport" in cs

    # -- animation rigging --

    def test_rigging_returns_string(self):
        cs = generate_animation_rigging_script(
            rig_name="ArmIK",
            constraints=[
                {
                    "type": "two_bone_ik",
                    "target_path": "IKTarget",
                    "root_path": "UpperArm",
                    "mid_path": "Forearm",
                    "tip_path": "Hand",
                },
            ],
        )
        assert isinstance(cs, str)

    def test_rigging_has_rig_builder(self):
        cs = generate_animation_rigging_script(
            rig_name="ArmIK",
            constraints=[{"type": "two_bone_ik"}],
        )
        assert "RigBuilder" in cs
        assert "Rig" in cs

    def test_rigging_two_bone_ik(self):
        cs = generate_animation_rigging_script(
            rig_name="ArmIK",
            constraints=[{"type": "two_bone_ik"}],
        )
        assert "TwoBoneIKConstraint" in cs

    def test_rigging_multi_aim(self):
        cs = generate_animation_rigging_script(
            rig_name="HeadAim",
            constraints=[
                {
                    "type": "multi_aim",
                    "target_path": "Head",
                    "source_paths": ["LookTarget"],
                    "weight": 0.8,
                },
            ],
        )
        assert "MultiAimConstraint" in cs

    def test_rigging_rejects_empty_constraints(self):
        with pytest.raises(ValueError, match="constraints") as exc_info:
            generate_animation_rigging_script(rig_name="Empty", constraints=[])
        assert "constraint" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Tool 6: unity_gameplay (7 actions)
# ---------------------------------------------------------------------------

from veilbreakers_mcp.shared.unity_templates.gameplay_templates import (
    generate_aggro_system_script,
    generate_behavior_tree_script,
    generate_combat_ability_script,
    generate_mob_controller_script,
    generate_patrol_route_script,
    generate_projectile_script,
    generate_spawn_system_script,
)


class TestUnityGameplay:
    """Tool 6 -- unity_gameplay: 7 actions."""

    # -- mob controller --

    def test_mob_controller_returns_string(self):
        cs = generate_mob_controller_script(name="Skeleton")
        assert isinstance(cs, str)

    def test_mob_controller_has_nav_mesh_agent(self):
        cs = generate_mob_controller_script(name="Skeleton")
        assert "NavMeshAgent" in cs

    def test_mob_controller_has_state_machine(self):
        cs = generate_mob_controller_script(name="Skeleton")
        assert "MobState" in cs
        assert "switch (currentState)" in cs or "switch(currentState)" in cs

    def test_mob_controller_all_states(self):
        cs = generate_mob_controller_script(name="Skeleton")
        for state in ("Patrol", "Aggro", "Chase", "Attack", "Flee", "ReturnToPatrol"):
            assert state in cs

    def test_mob_controller_has_set_destination(self):
        cs = generate_mob_controller_script(name="Skeleton")
        assert "SetDestination" in cs

    # -- aggro system --

    def test_aggro_system_returns_string(self):
        cs = generate_aggro_system_script(name="ZombieAggro")
        assert isinstance(cs, str)

    def test_aggro_system_has_overlap_sphere(self):
        cs = generate_aggro_system_script(name="ZombieAggro")
        assert "OverlapSphereNonAlloc" in cs

    def test_aggro_system_has_threat_table(self):
        cs = generate_aggro_system_script(name="ZombieAggro")
        assert "threatTable" in cs
        assert "GetHighestThreat" in cs

    def test_aggro_system_has_leash(self):
        cs = generate_aggro_system_script(name="ZombieAggro")
        assert "leashDistance" in cs
        assert "ReturnToPatrol" in cs

    # -- patrol route --

    def test_patrol_returns_string(self):
        cs = generate_patrol_route_script(name="GuardPatrol")
        assert isinstance(cs, str)

    def test_patrol_has_set_destination(self):
        cs = generate_patrol_route_script(name="GuardPatrol")
        assert "SetDestination" in cs

    def test_patrol_has_waypoints(self):
        cs = generate_patrol_route_script(name="GuardPatrol")
        assert "waypoints" in cs
        assert "currentWaypointIndex" in cs

    def test_patrol_has_dwell_time(self):
        cs = generate_patrol_route_script(name="GuardPatrol")
        assert "dwellTime" in cs or "defaultDwellTime" in cs

    # -- spawn system --

    def test_spawn_system_returns_string(self):
        cs = generate_spawn_system_script(name="Arena")
        assert isinstance(cs, str)

    def test_spawn_system_has_instantiate(self):
        cs = generate_spawn_system_script(name="Arena")
        assert "Instantiate" in cs

    def test_spawn_system_has_spawn_wave(self):
        cs = generate_spawn_system_script(name="Arena")
        assert "SpawnWave" in cs

    def test_spawn_system_has_max_alive(self):
        cs = generate_spawn_system_script(name="Arena")
        assert "maxAlive" in cs
        assert "GetAliveCount" in cs

    def test_spawn_system_has_respawn_timer(self):
        cs = generate_spawn_system_script(name="Arena")
        assert "respawnTimer" in cs

    # -- behavior tree --

    def test_behavior_tree_returns_string(self):
        cs = generate_behavior_tree_script(name="MobAI")
        assert isinstance(cs, str)

    def test_behavior_tree_has_bt_node(self):
        cs = generate_behavior_tree_script(name="MobAI")
        assert "BT_Node" in cs

    def test_behavior_tree_has_evaluate(self):
        cs = generate_behavior_tree_script(name="MobAI")
        assert "Evaluate" in cs

    def test_behavior_tree_has_sequence_selector(self):
        cs = generate_behavior_tree_script(name="MobAI")
        assert "BT_Sequence" in cs
        assert "BT_Selector" in cs

    def test_behavior_tree_has_runner(self):
        cs = generate_behavior_tree_script(name="MobAI")
        assert "BehaviorTreeRunner" in cs

    def test_behavior_tree_custom_nodes(self):
        cs = generate_behavior_tree_script(
            name="MobAI", node_types=["CheckHealth", "FindEnemy"]
        )
        assert "BT_CheckHealth" in cs
        assert "BT_FindEnemy" in cs

    # -- combat ability --

    def test_combat_ability_returns_string(self):
        cs = generate_combat_ability_script(name="ShadowStrike")
        assert isinstance(cs, str)

    def test_combat_ability_has_scriptable_object(self):
        cs = generate_combat_ability_script(name="ShadowStrike")
        assert "CombatAbility" in cs
        assert "ScriptableObject" in cs

    def test_combat_ability_has_executor(self):
        cs = generate_combat_ability_script(name="ShadowStrike")
        assert "AbilityExecutor" in cs

    def test_combat_ability_has_cooldown(self):
        cs = generate_combat_ability_script(name="ShadowStrike")
        assert "cooldown" in cs
        assert "cooldownTimers" in cs

    def test_combat_ability_has_damage(self):
        cs = generate_combat_ability_script(name="ShadowStrike", damage=50.0)
        assert "damage = 50" in cs

    # -- projectile --

    def test_projectile_returns_string(self):
        cs = generate_projectile_script(name="Fireball")
        assert isinstance(cs, str)

    def test_projectile_has_trajectory_enum(self):
        cs = generate_projectile_script(name="Fireball")
        assert "TrajectoryType" in cs
        assert "Straight" in cs
        assert "Arc" in cs
        assert "Homing" in cs

    def test_projectile_straight(self):
        cs = generate_projectile_script(name="Arrow", trajectory="straight")
        assert "TrajectoryType.Straight" in cs
        assert "transform.Translate" in cs

    def test_projectile_arc(self):
        cs = generate_projectile_script(name="Boulder", trajectory="arc")
        assert "TrajectoryType.Arc" in cs
        assert "AddForce" in cs

    def test_projectile_homing(self):
        cs = generate_projectile_script(name="Seeker", trajectory="homing")
        assert "TrajectoryType.Homing" in cs
        assert "homingTarget" in cs
        assert "Slerp" in cs

    def test_projectile_has_trail(self):
        cs = generate_projectile_script(name="Fireball")
        assert "TrailRenderer" in cs
        assert "trailWidth" in cs

    def test_projectile_has_impact(self):
        cs = generate_projectile_script(name="Fireball")
        assert "OnTriggerEnter" in cs
        assert "impactVFXPrefab" in cs


# ---------------------------------------------------------------------------
# Tool 7: unity_performance (5 actions)
# ---------------------------------------------------------------------------

from veilbreakers_mcp.shared.unity_templates.performance_templates import (
    _analyze_profile_thresholds,
    _classify_asset_issues,
    _validate_lod_screen_percentages,
    generate_asset_audit_script,
    generate_build_automation_script,
    generate_lightmap_bake_script,
    generate_lod_setup_script,
    generate_scene_profiler_script,
)


class TestUnityPerformance:
    """Tool 7 -- unity_performance: 5 actions."""

    # -- scene profiler --

    def test_profiler_returns_string(self):
        cs = generate_scene_profiler_script()
        assert isinstance(cs, str)

    def test_profiler_has_frame_time(self):
        cs = generate_scene_profiler_script()
        assert "Time.unscaledDeltaTime" in cs or "deltaTime" in cs

    def test_profiler_has_draw_calls(self):
        cs = generate_scene_profiler_script()
        assert "UnityStats.drawCalls" in cs

    def test_profiler_has_memory(self):
        cs = generate_scene_profiler_script()
        assert "Profiler.GetTotalAllocatedMemoryLong" in cs

    def test_profiler_has_triangles(self):
        cs = generate_scene_profiler_script()
        assert "UnityStats.triangles" in cs

    def test_profiler_has_budgets(self):
        cs = generate_scene_profiler_script()
        assert "frameTimeBudget" in cs
        assert "drawCallsBudget" in cs

    def test_profiler_custom_budgets(self):
        cs = generate_scene_profiler_script(budgets={"frame_time": 8.3, "draw_calls": 500})
        assert "8.3" in cs
        assert "500" in cs

    # -- LOD setup --

    def test_lod_setup_returns_string(self):
        cs = generate_lod_setup_script()
        assert isinstance(cs, str)

    def test_lod_setup_has_lod_group(self):
        cs = generate_lod_setup_script()
        assert "LODGroup" in cs

    def test_lod_setup_has_set_lods(self):
        cs = generate_lod_setup_script()
        assert "SetLODs" in cs
        assert "RecalculateBounds" in cs

    def test_lod_setup_has_occlusion(self):
        cs = generate_lod_setup_script()
        assert "OccludeeStatic" in cs or "OccluderStatic" in cs

    def test_lod_setup_custom_percentages(self):
        cs = generate_lod_setup_script(screen_percentages=[0.7, 0.4, 0.1])
        assert "0.7f" in cs
        assert "0.4f" in cs
        assert "0.1f" in cs

    def test_lod_setup_rejects_invalid_percentages(self):
        with pytest.raises(ValueError, match="strictly descending") as exc_info:
            generate_lod_setup_script(screen_percentages=[0.3, 0.5])  # ascending
        assert "descending" in str(exc_info.value).lower()

    # -- lightmap bake --

    def test_lightmap_bake_returns_string(self):
        cs = generate_lightmap_bake_script()
        assert isinstance(cs, str)

    def test_lightmap_bake_has_lightmapping(self):
        cs = generate_lightmap_bake_script()
        assert "Lightmapping" in cs
        assert "BakeAsync" in cs

    def test_lightmap_bake_has_gi_workflow(self):
        cs = generate_lightmap_bake_script()
        assert "GIWorkflowMode" in cs or "giWorkflowMode" in cs

    def test_lightmap_bake_has_resolution(self):
        cs = generate_lightmap_bake_script(resolution=64)
        assert "bakeResolution" in cs
        assert "64" in cs

    # -- asset audit --

    def test_asset_audit_returns_string(self):
        cs = generate_asset_audit_script()
        assert isinstance(cs, str)

    def test_asset_audit_has_find_assets(self):
        cs = generate_asset_audit_script()
        assert "GetAllAssetPaths" in cs

    def test_asset_audit_has_texture_check(self):
        cs = generate_asset_audit_script()
        assert "TextureImporter" in cs
        assert "maxTextureSize" in cs

    def test_asset_audit_has_audio_check(self):
        cs = generate_asset_audit_script()
        assert "AudioImporter" in cs
        assert "compressionFormat" in cs

    def test_asset_audit_has_unused_detection(self):
        cs = generate_asset_audit_script()
        assert "GetDependencies" in cs

    def test_asset_audit_custom_max_texture(self):
        cs = generate_asset_audit_script(max_texture_size=1024)
        assert "1024" in cs

    # -- build automation --

    def test_build_automation_returns_string(self):
        cs = generate_build_automation_script()
        assert isinstance(cs, str)

    def test_build_automation_has_build_pipeline(self):
        cs = generate_build_automation_script()
        assert "BuildPipeline.BuildPlayer" in cs

    def test_build_automation_has_build_report(self):
        cs = generate_build_automation_script()
        assert "BuildReport" in cs
        assert "BuildResult.Succeeded" in cs

    def test_build_automation_has_packed_assets(self):
        cs = generate_build_automation_script()
        assert "packedAssets" in cs

    def test_build_automation_custom_target(self):
        cs = generate_build_automation_script(target="Android")
        assert "BuildTarget.Android" in cs

    def test_build_automation_custom_scenes(self):
        cs = generate_build_automation_script(
            scenes=["Assets/Scenes/Main.unity", "Assets/Scenes/Level1.unity"]
        )
        assert "Main.unity" in cs
        assert "Level1.unity" in cs

    # -- pure-logic helpers --

    def test_analyze_profile_thresholds_no_violations(self):
        data = {"frame_time": 10.0, "draw_calls": 500}
        budgets = {"frame_time": 16.6, "draw_calls": 2000}
        violations = _analyze_profile_thresholds(data, budgets)
        assert violations == []

    def test_analyze_profile_thresholds_with_violations(self):
        data = {"frame_time": 33.0, "draw_calls": 5000}
        budgets = {"frame_time": 16.6, "draw_calls": 2000}
        violations = _analyze_profile_thresholds(data, budgets)
        assert len(violations) == 2
        metrics = {v["metric"] for v in violations}
        assert "frame_time" in metrics
        assert "draw_calls" in metrics

    def test_analyze_profile_thresholds_severity(self):
        # 2x budget = critical
        data = {"frame_time": 40.0}
        budgets = {"frame_time": 16.6}
        violations = _analyze_profile_thresholds(data, budgets)
        assert violations[0]["severity"] == "critical"

        # 1.5x budget = warning
        data2 = {"frame_time": 20.0}
        violations2 = _analyze_profile_thresholds(data2, budgets)
        assert violations2[0]["severity"] == "warning"

    def test_classify_asset_issues(self):
        assets = [
            {"type": "texture", "path": "a.png"},
            {"type": "texture", "path": "b.png"},
            {"type": "audio", "path": "c.wav"},
            {"type": "unused", "path": "d.fbx"},
            {"type": "duplicate_material", "path": "e.mat"},
        ]
        result = _classify_asset_issues(assets)
        assert result["oversized_textures"]["count"] == 2
        assert result["uncompressed_audio"]["count"] == 1
        assert result["unused_assets"]["count"] == 1
        assert result["duplicate_materials"]["count"] == 1

    def test_classify_asset_issues_empty(self):
        result = _classify_asset_issues([])
        for key in ("oversized_textures", "uncompressed_audio", "unused_assets", "duplicate_materials"):
            assert result[key]["count"] == 0

    def test_validate_lod_screen_percentages_valid(self):
        assert _validate_lod_screen_percentages([0.6, 0.3, 0.15]) is True
        assert _validate_lod_screen_percentages([0.5]) is True

    def test_validate_lod_screen_percentages_invalid(self):
        assert _validate_lod_screen_percentages([]) is False
        assert _validate_lod_screen_percentages([0.3, 0.5]) is False  # ascending
        assert _validate_lod_screen_percentages([0.5, 0.5]) is False  # equal
        assert _validate_lod_screen_percentages([0.5, 0]) is False    # zero
        assert _validate_lod_screen_percentages([0.5, -0.1]) is False  # negative


# ---------------------------------------------------------------------------
# Cross-tool: Import verification
# ---------------------------------------------------------------------------


class TestAllImportsExist:
    """Verify that every function referenced in the test is importable."""

    def test_editor_templates_importable(self):
        from veilbreakers_mcp.shared.unity_templates import editor_templates
        fns = [
            "generate_recompile_script",
            "generate_play_mode_script",
            "generate_screenshot_script",
            "generate_console_log_script",
            "generate_gemini_review_script",
        ]
        for fn_name in fns:
            assert hasattr(editor_templates, fn_name), f"Missing: editor_templates.{fn_name}"

    def test_vfx_templates_importable(self):
        from veilbreakers_mcp.shared.unity_templates import vfx_templates
        fns = [
            "generate_particle_vfx_script",
            "generate_brand_vfx_script",
            "generate_environmental_vfx_script",
            "generate_trail_vfx_script",
            "generate_aura_vfx_script",
            "generate_post_processing_script",
            "generate_screen_effect_script",
            "generate_ability_vfx_script",
        ]
        for fn_name in fns:
            assert hasattr(vfx_templates, fn_name), f"Missing: vfx_templates.{fn_name}"

    def test_shader_templates_importable(self):
        from veilbreakers_mcp.shared.unity_templates import shader_templates
        fns = [
            "generate_dissolve_shader",
            "generate_force_field_shader",
            "generate_water_shader",
            "generate_foliage_shader",
            "generate_outline_shader",
            "generate_corruption_shader",
            "generate_damage_overlay_shader",
        ]
        for fn_name in fns:
            assert hasattr(shader_templates, fn_name), f"Missing: shader_templates.{fn_name}"

    def test_audio_templates_importable(self):
        from veilbreakers_mcp.shared.unity_templates import audio_templates
        fns = [
            "generate_footstep_manager_script",
            "generate_adaptive_music_script",
            "generate_audio_zone_script",
            "generate_audio_mixer_setup_script",
            "generate_audio_pool_manager_script",
            "generate_animation_event_sfx_script",
        ]
        for fn_name in fns:
            assert hasattr(audio_templates, fn_name), f"Missing: audio_templates.{fn_name}"

    def test_ui_templates_importable(self):
        from veilbreakers_mcp.shared.unity_templates import ui_templates
        fns = [
            "generate_uxml_screen",
            "generate_uss_stylesheet",
            "generate_responsive_test_script",
            "validate_uxml_layout",
        ]
        for fn_name in fns:
            assert hasattr(ui_templates, fn_name), f"Missing: ui_templates.{fn_name}"

    def test_scene_templates_importable(self):
        from veilbreakers_mcp.shared.unity_templates import scene_templates
        fns = [
            "generate_terrain_setup_script",
            "generate_tiled_terrain_setup_script",
            "generate_object_scatter_script",
            "generate_lighting_setup_script",
            "generate_navmesh_bake_script",
            "generate_animator_controller_script",
            "generate_avatar_config_script",
            "generate_animation_rigging_script",
        ]
        for fn_name in fns:
            assert hasattr(scene_templates, fn_name), f"Missing: scene_templates.{fn_name}"

    def test_gameplay_templates_importable(self):
        from veilbreakers_mcp.shared.unity_templates import gameplay_templates
        fns = [
            "generate_mob_controller_script",
            "generate_aggro_system_script",
            "generate_patrol_route_script",
            "generate_spawn_system_script",
            "generate_behavior_tree_script",
            "generate_combat_ability_script",
            "generate_projectile_script",
        ]
        for fn_name in fns:
            assert hasattr(gameplay_templates, fn_name), f"Missing: gameplay_templates.{fn_name}"

    def test_performance_templates_importable(self):
        from veilbreakers_mcp.shared.unity_templates import performance_templates
        fns = [
            "generate_scene_profiler_script",
            "generate_lod_setup_script",
            "generate_lightmap_bake_script",
            "generate_asset_audit_script",
            "generate_build_automation_script",
        ]
        for fn_name in fns:
            assert hasattr(performance_templates, fn_name), f"Missing: performance_templates.{fn_name}"

    def test_wcag_checker_importable(self):
        from veilbreakers_mcp.shared import wcag_checker
        for fn_name in ("relative_luminance", "contrast_ratio", "check_wcag_aa"):
            assert hasattr(wcag_checker, fn_name), f"Missing: wcag_checker.{fn_name}"

    def test_screenshot_diff_importable(self):
        from veilbreakers_mcp.shared import screenshot_diff
        for fn_name in ("compare_screenshots", "generate_diff_image"):
            assert hasattr(screenshot_diff, fn_name), f"Missing: screenshot_diff.{fn_name}"

    def test_elevenlabs_client_importable(self):
        from veilbreakers_mcp.shared import elevenlabs_client
        assert hasattr(elevenlabs_client, "ElevenLabsAudioClient")
