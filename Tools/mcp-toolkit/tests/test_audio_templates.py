"""Unit tests for Unity audio C# template generators.

Tests that each generator function produces valid C# source containing
the expected keywords, Unity API calls, and parameter substitutions.
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.audio_templates import (
    generate_footstep_manager_script,
    generate_adaptive_music_script,
    generate_audio_zone_script,
    generate_audio_mixer_setup_script,
    generate_audio_pool_manager_script,
    generate_animation_event_sfx_script,
)


# ---------------------------------------------------------------------------
# Footstep manager script
# ---------------------------------------------------------------------------


class TestGenerateFootstepManagerScript:
    """Tests for generate_footstep_manager_script()."""

    def test_contains_using_unity_engine(self):
        result = generate_footstep_manager_script()
        assert "using UnityEngine;" in result

    def test_contains_mono_behaviour(self):
        result = generate_footstep_manager_script()
        assert "MonoBehaviour" in result

    def test_contains_scriptable_object(self):
        result = generate_footstep_manager_script()
        assert "ScriptableObject" in result

    def test_contains_play_footstep_method(self):
        result = generate_footstep_manager_script()
        assert "PlayFootstep" in result

    def test_default_surfaces_included(self):
        result = generate_footstep_manager_script()
        for surface in ["stone", "wood", "grass", "metal", "water"]:
            assert surface.lower() in result.lower()

    def test_custom_surfaces(self):
        result = generate_footstep_manager_script(
            surfaces=["sand", "ice", "mud"]
        )
        for surface in ["sand", "ice", "mud"]:
            assert surface.lower() in result.lower()

    def test_contains_audio_clip_reference(self):
        result = generate_footstep_manager_script()
        assert "AudioClip" in result

    def test_contains_audio_source(self):
        result = generate_footstep_manager_script()
        assert "AudioSource" in result


# ---------------------------------------------------------------------------
# Adaptive music script
# ---------------------------------------------------------------------------


class TestGenerateAdaptiveMusicScript:
    """Tests for generate_adaptive_music_script()."""

    def test_contains_using_unity_engine(self):
        result = generate_adaptive_music_script()
        assert "using UnityEngine;" in result

    def test_contains_mono_behaviour(self):
        result = generate_adaptive_music_script()
        assert "MonoBehaviour" in result

    def test_contains_audio_source(self):
        result = generate_adaptive_music_script()
        assert "AudioSource" in result

    def test_contains_crossfade(self):
        result = generate_adaptive_music_script()
        assert "crossfade" in result.lower() or "Crossfade" in result

    def test_contains_game_state_enum(self):
        result = generate_adaptive_music_script()
        assert "GameState" in result or "enum" in result

    def test_default_layers(self):
        result = generate_adaptive_music_script()
        assert "Exploration" in result or "exploration" in result
        assert "Combat" in result or "combat" in result

    def test_custom_layers(self):
        result = generate_adaptive_music_script(
            layers=["stealth", "chase", "victory"]
        )
        assert "stealth" in result.lower() or "Stealth" in result
        assert "chase" in result.lower() or "Chase" in result

    def test_contains_set_game_state(self):
        result = generate_adaptive_music_script()
        assert "SetGameState" in result


# ---------------------------------------------------------------------------
# Audio zone script
# ---------------------------------------------------------------------------


class TestGenerateAudioZoneScript:
    """Tests for generate_audio_zone_script()."""

    def test_contains_using_unity_editor(self):
        result = generate_audio_zone_script()
        assert "using UnityEditor;" in result

    def test_contains_using_unity_engine(self):
        result = generate_audio_zone_script()
        assert "using UnityEngine;" in result

    def test_contains_audio_reverb_zone(self):
        result = generate_audio_zone_script()
        assert "AudioReverbZone" in result

    def test_default_zone_type_cave(self):
        result = generate_audio_zone_script()
        assert "cave" in result.lower() or "Cave" in result

    def test_custom_zone_type(self):
        result = generate_audio_zone_script(zone_type="outdoor")
        assert "outdoor" in result.lower() or "Outdoor" in result

    def test_contains_menu_item(self):
        result = generate_audio_zone_script()
        assert "[MenuItem(" in result

    def test_contains_reverb_preset_values(self):
        result = generate_audio_zone_script(zone_type="cave")
        # Cave should have high reverb settings
        assert "reverbDelay" in result or "decayTime" in result or "reverb" in result.lower()

    def test_multiple_zone_types(self):
        for zone_type in ["cave", "outdoor", "indoor", "dungeon", "forest"]:
            result = generate_audio_zone_script(zone_type=zone_type)
            assert "AudioReverbZone" in result


# ---------------------------------------------------------------------------
# Audio mixer setup script
# ---------------------------------------------------------------------------


class TestGenerateAudioMixerSetupScript:
    """Tests for generate_audio_mixer_setup_script()."""

    def test_contains_using_unity_editor(self):
        result = generate_audio_mixer_setup_script()
        assert "using UnityEditor;" in result

    def test_contains_using_unity_engine(self):
        result = generate_audio_mixer_setup_script()
        assert "using UnityEngine;" in result

    def test_contains_audio_mixer(self):
        result = generate_audio_mixer_setup_script()
        assert "AudioMixer" in result

    def test_default_groups(self):
        result = generate_audio_mixer_setup_script()
        for group in ["Master", "SFX", "Music", "Voice", "Ambient", "UI"]:
            assert group in result

    def test_custom_groups(self):
        result = generate_audio_mixer_setup_script(
            groups=["Main", "Effects", "Dialog"]
        )
        for group in ["Main", "Effects", "Dialog"]:
            assert group in result

    def test_contains_menu_item(self):
        result = generate_audio_mixer_setup_script()
        assert "[MenuItem(" in result

    def test_contains_veilbreakers_mixer_path(self):
        result = generate_audio_mixer_setup_script()
        assert "VeilBreakersMixer" in result or "mixer" in result.lower()


# ---------------------------------------------------------------------------
# Audio pool manager script
# ---------------------------------------------------------------------------


class TestGenerateAudioPoolManagerScript:
    """Tests for generate_audio_pool_manager_script()."""

    def test_contains_using_unity_engine(self):
        result = generate_audio_pool_manager_script()
        assert "using UnityEngine;" in result

    def test_contains_mono_behaviour(self):
        result = generate_audio_pool_manager_script()
        assert "MonoBehaviour" in result

    def test_contains_play_method(self):
        result = generate_audio_pool_manager_script()
        assert "Play(" in result or "PlaySound(" in result or "PlayClip(" in result

    def test_contains_audio_source(self):
        result = generate_audio_pool_manager_script()
        assert "AudioSource" in result

    def test_contains_priority(self):
        result = generate_audio_pool_manager_script()
        assert "priority" in result.lower()

    def test_default_pool_size(self):
        result = generate_audio_pool_manager_script()
        assert "16" in result

    def test_custom_pool_size(self):
        result = generate_audio_pool_manager_script(pool_size=32, max_sources=64)
        assert "32" in result

    def test_contains_ducking(self):
        result = generate_audio_pool_manager_script()
        assert "duck" in result.lower() or "Duck" in result

    def test_contains_pool_recycling(self):
        result = generate_audio_pool_manager_script()
        # Should have some form of pool recycling logic
        assert "pool" in result.lower()


# ---------------------------------------------------------------------------
# Animation event SFX script
# ---------------------------------------------------------------------------


class TestGenerateAnimationEventSfxScript:
    """Tests for generate_animation_event_sfx_script()."""

    def test_contains_using_unity_editor(self):
        result = generate_animation_event_sfx_script()
        assert "using UnityEditor;" in result

    def test_contains_using_unity_engine(self):
        result = generate_animation_event_sfx_script()
        assert "using UnityEngine;" in result

    def test_contains_animation_event(self):
        result = generate_animation_event_sfx_script()
        assert "AnimationEvent" in result

    def test_contains_animation_utility(self):
        result = generate_animation_event_sfx_script()
        assert "AnimationUtility" in result

    def test_contains_set_animation_events(self):
        result = generate_animation_event_sfx_script()
        assert "SetAnimationEvents" in result

    def test_contains_menu_item(self):
        result = generate_animation_event_sfx_script()
        assert "[MenuItem(" in result

    def test_default_events(self):
        result = generate_animation_event_sfx_script()
        # Default events should have at least one event defined
        assert "AnimationEvent" in result

    def test_custom_events(self):
        events = [
            {"frame": 5, "function_name": "PlaySwing", "clip_path": "Audio/SFX/swing.wav"},
            {"frame": 12, "function_name": "PlayImpact", "clip_path": "Audio/SFX/impact.wav"},
        ]
        result = generate_animation_event_sfx_script(events=events)
        assert "PlaySwing" in result
        assert "PlayImpact" in result
        assert "5" in result
        assert "12" in result


# ---------------------------------------------------------------------------
# Cross-cutting template quality checks
# ---------------------------------------------------------------------------


class TestAudioTemplateQuality:
    """Cross-cutting quality checks for all audio templates."""

    def test_all_templates_return_strings(self):
        assert isinstance(generate_footstep_manager_script(), str)
        assert isinstance(generate_adaptive_music_script(), str)
        assert isinstance(generate_audio_zone_script(), str)
        assert isinstance(generate_audio_mixer_setup_script(), str)
        assert isinstance(generate_audio_pool_manager_script(), str)
        assert isinstance(generate_animation_event_sfx_script(), str)

    def test_all_templates_non_empty(self):
        assert len(generate_footstep_manager_script()) > 100
        assert len(generate_adaptive_music_script()) > 100
        assert len(generate_audio_zone_script()) > 100
        assert len(generate_audio_mixer_setup_script()) > 100
        assert len(generate_audio_pool_manager_script()) > 100
        assert len(generate_animation_event_sfx_script()) > 100

    def test_all_templates_contain_veilbreakers(self):
        """All generated scripts should be identifiable as VeilBreakers generated."""
        assert "VeilBreakers" in generate_footstep_manager_script()
        assert "VeilBreakers" in generate_adaptive_music_script()
        assert "VeilBreakers" in generate_audio_zone_script()
        assert "VeilBreakers" in generate_audio_mixer_setup_script()
        assert "VeilBreakers" in generate_audio_pool_manager_script()
        assert "VeilBreakers" in generate_animation_event_sfx_script()
