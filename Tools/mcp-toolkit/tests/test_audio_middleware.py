"""Unit tests for Phase 21 audio middleware C# template generators.

Tests that each generator function:
1. Returns a dict with script_path, script_content, next_steps
2. Produces valid C# source with balanced braces and proper syntax
3. Contains expected Unity API calls, classes, and parameter substitutions
4. Handles custom parameters correctly

Requirements covered:
    AUDM-01: Spatial audio (generate_spatial_audio_script)
    AUDM-02: Layered sound (generate_layered_sound_script)
    AUDM-03: Audio event chains (generate_audio_event_chain_script)
    AUDM-04: Dynamic music (generate_dynamic_music_script)
    AUDM-05: Portal audio (generate_portal_audio_script)
    AUDM-06: Audio LOD (generate_audio_lod_script)
    AUDM-07: VO pipeline (generate_vo_pipeline_script)
    AUDM-08: Procedural foley (generate_procedural_foley_script)
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.audio_middleware_templates import (
    generate_spatial_audio_script,
    generate_audio_lod_script,
    generate_layered_sound_script,
    generate_audio_event_chain_script,
    generate_procedural_foley_script,
    generate_dynamic_music_script,
    generate_portal_audio_script,
    generate_vo_pipeline_script,
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
    assert result["script_path"].endswith(".cs"), "script_path must end with .cs"


# ===========================================================================
# AUDM-01: Spatial Audio System
# ===========================================================================


class TestGenerateSpatialAudioScript:
    """Tests for generate_spatial_audio_script() -- AUDM-01."""

    def test_output_structure(self):
        result = generate_spatial_audio_script()
        _check_output_structure(result)

    def test_contains_monobehaviour(self):
        result = generate_spatial_audio_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_contains_unity_engine(self):
        result = generate_spatial_audio_script()
        assert "using UnityEngine;" in result["script_content"]

    def test_contains_audio_source(self):
        result = generate_spatial_audio_script()
        assert "AudioSource" in result["script_content"]

    def test_spatial_blend_set_to_3d(self):
        result = generate_spatial_audio_script()
        assert "spatialBlend = 1.0f" in result["script_content"]

    def test_contains_require_component(self):
        result = generate_spatial_audio_script()
        assert "[RequireComponent(typeof(AudioSource))]" in result["script_content"]

    def test_occlusion_enabled_by_default(self):
        result = generate_spatial_audio_script()
        content = result["script_content"]
        assert "occlusionEnabled" in content
        assert "Physics.RaycastAll" in content
        assert "AudioLowPassFilter" in content

    def test_occlusion_disabled(self):
        result = generate_spatial_audio_script(occlusion_enabled=False)
        content = result["script_content"]
        assert "occlusionEnabled" not in content
        assert "RaycastAll" not in content

    def test_custom_distances(self):
        result = generate_spatial_audio_script(min_distance=5.0, max_distance=100.0)
        content = result["script_content"]
        assert "5" in content
        assert "100" in content

    def test_custom_rolloff_mode(self):
        result = generate_spatial_audio_script(rolloff_mode="Linear")
        assert "AudioRolloffMode.Linear" in result["script_content"]

    def test_custom_source_name(self):
        result = generate_spatial_audio_script(source_name="BossRoar")
        assert "VeilBreakers_BossRoar" in result["script_content"]
        assert "BossRoar" in result["script_path"]

    def test_doppler_level(self):
        result = generate_spatial_audio_script(doppler_level=1.5)
        assert "1.5" in result["script_content"]

    def test_spread_angle(self):
        result = generate_spatial_audio_script(spread_angle=120.0)
        assert "120" in result["script_content"]

    def test_play_clip_method(self):
        result = generate_spatial_audio_script()
        assert "PlayClip" in result["script_content"]

    def test_play_one_shot_method(self):
        result = generate_spatial_audio_script()
        assert "PlayOneShot" in result["script_content"]

    def test_distance_to_listener(self):
        result = generate_spatial_audio_script()
        assert "GetDistanceToListener" in result["script_content"]

    def test_balanced_braces(self):
        result = generate_spatial_audio_script()
        assert _check_balanced_braces(result["script_content"]), \
            "Unbalanced braces in spatial audio script"

    def test_balanced_braces_no_occlusion(self):
        result = generate_spatial_audio_script(occlusion_enabled=False)
        assert _check_balanced_braces(result["script_content"]), \
            "Unbalanced braces in spatial audio script (no occlusion)"

    def test_veilbreakers_identifier(self):
        result = generate_spatial_audio_script()
        assert "VeilBreakers" in result["script_content"]

    def test_custom_rolloff_curve(self):
        result = generate_spatial_audio_script(rolloff_mode="Custom")
        content = result["script_content"]
        assert "AudioRolloffMode.Custom" in content
        assert "customRolloffCurve" in content
        assert "SetCustomCurve" in content


# ===========================================================================
# AUDM-06: Audio LOD System
# ===========================================================================


class TestGenerateAudioLODScript:
    """Tests for generate_audio_lod_script() -- AUDM-06."""

    def test_output_structure(self):
        result = generate_audio_lod_script()
        _check_output_structure(result)

    def test_contains_monobehaviour(self):
        result = generate_audio_lod_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_contains_unity_engine(self):
        result = generate_audio_lod_script()
        assert "using UnityEngine;" in result["script_content"]

    def test_contains_lod_tier_enum(self):
        result = generate_audio_lod_script()
        content = result["script_content"]
        assert "AudioLODTier" in content
        assert "Full" in content
        assert "Reduced" in content
        assert "Minimal" in content
        assert "Culled" in content

    def test_default_distances(self):
        result = generate_audio_lod_script()
        content = result["script_content"]
        assert "15" in content  # reduced
        assert "30" in content  # minimal
        assert "50" in content  # culled

    def test_custom_distances(self):
        result = generate_audio_lod_script(lod_distances=[10.0, 25.0, 40.0])
        content = result["script_content"]
        assert "10" in content
        assert "25" in content
        assert "40" in content

    def test_channel_reduction_enabled(self):
        result = generate_audio_lod_script(channel_reduction=True)
        assert "ApplyChannelReduction" in result["script_content"]

    def test_channel_reduction_disabled(self):
        result = generate_audio_lod_script(channel_reduction=False)
        assert "ApplyChannelReduction" not in result["script_content"]

    def test_priority_scaling_enabled(self):
        result = generate_audio_lod_script(priority_scaling=True)
        assert "ApplyPriorityScaling" in result["script_content"]

    def test_priority_scaling_disabled(self):
        result = generate_audio_lod_script(priority_scaling=False)
        assert "ApplyPriorityScaling" not in result["script_content"]

    def test_culled_disables_source(self):
        result = generate_audio_lod_script()
        assert "enabled = false" in result["script_content"]

    def test_calculate_tier_method(self):
        result = generate_audio_lod_script()
        assert "CalculateTier" in result["script_content"]

    def test_force_set_tier_method(self):
        result = generate_audio_lod_script()
        assert "ForceSetTier" in result["script_content"]

    def test_balanced_braces(self):
        result = generate_audio_lod_script()
        assert _check_balanced_braces(result["script_content"]), \
            "Unbalanced braces in audio LOD script"

    def test_balanced_braces_no_features(self):
        result = generate_audio_lod_script(
            channel_reduction=False, priority_scaling=False)
        assert _check_balanced_braces(result["script_content"]), \
            "Unbalanced braces in audio LOD script (no features)"

    def test_require_component(self):
        result = generate_audio_lod_script()
        assert "[RequireComponent(typeof(AudioSource))]" in result["script_content"]

    def test_update_interval(self):
        result = generate_audio_lod_script()
        assert "updateInterval" in result["script_content"]

    def test_set_distances_method(self):
        result = generate_audio_lod_script()
        assert "SetDistances" in result["script_content"]

    def test_veilbreakers_identifier(self):
        result = generate_audio_lod_script()
        assert "VeilBreakers" in result["script_content"]


# ===========================================================================
# AUDM-02: Layered Sound Design
# ===========================================================================


class TestGenerateLayeredSoundScript:
    """Tests for generate_layered_sound_script() -- AUDM-02."""

    def test_output_structure(self):
        result = generate_layered_sound_script()
        _check_output_structure(result)

    def test_contains_monobehaviour(self):
        result = generate_layered_sound_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_contains_scriptable_object(self):
        result = generate_layered_sound_script()
        assert "ScriptableObject" in result["script_content"]

    def test_contains_sound_layer_class(self):
        result = generate_layered_sound_script()
        assert "VB_SoundLayer" in result["script_content"]

    def test_contains_create_asset_menu(self):
        result = generate_layered_sound_script()
        assert "[CreateAssetMenu" in result["script_content"]

    def test_custom_sound_name(self):
        result = generate_layered_sound_script(sound_name="SwordImpact")
        content = result["script_content"]
        assert "SwordImpact" in content

    def test_default_layers_comment(self):
        result = generate_layered_sound_script()
        content = result["script_content"]
        # Default layers should mention metal_clang
        assert "metal_clang" in content

    def test_custom_layers(self):
        layers = [
            {"clip_path": "Audio/SFX/boom", "volume": 1.0, "pitch": 0.8,
             "delay": 0.0, "random_pitch": 0.2, "random_volume": 0.1},
        ]
        result = generate_layered_sound_script(layers=layers)
        content = result["script_content"]
        assert "boom" in content

    def test_play_method(self):
        result = generate_layered_sound_script()
        assert "public void Play()" in result["script_content"]

    def test_play_layered_sound_method(self):
        result = generate_layered_sound_script()
        assert "PlayLayeredSound" in result["script_content"]

    def test_random_pitch_volume(self):
        result = generate_layered_sound_script()
        content = result["script_content"]
        assert "randomPitch" in content
        assert "randomVolume" in content

    def test_coroutine_delayed_play(self):
        result = generate_layered_sound_script()
        content = result["script_content"]
        assert "WaitForSeconds" in content
        assert "StartCoroutine" in content

    def test_balanced_braces(self):
        result = generate_layered_sound_script()
        assert _check_balanced_braces(result["script_content"]), \
            "Unbalanced braces in layered sound script"

    def test_veilbreakers_identifier(self):
        result = generate_layered_sound_script()
        assert "VeilBreakers" in result["script_content"]


# ===========================================================================
# AUDM-03: Audio Event Chains
# ===========================================================================


class TestGenerateAudioEventChainScript:
    """Tests for generate_audio_event_chain_script() -- AUDM-03."""

    def test_output_structure(self):
        result = generate_audio_event_chain_script()
        _check_output_structure(result)

    def test_contains_scriptable_object(self):
        result = generate_audio_event_chain_script()
        assert "ScriptableObject" in result["script_content"]

    def test_contains_monobehaviour(self):
        result = generate_audio_event_chain_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_contains_audio_event_class(self):
        result = generate_audio_event_chain_script()
        assert "VB_AudioEvent" in result["script_content"]

    def test_contains_create_asset_menu(self):
        result = generate_audio_event_chain_script()
        assert "[CreateAssetMenu" in result["script_content"]

    def test_default_chain_events(self):
        result = generate_audio_event_chain_script()
        content = result["script_content"]
        assert "impact" in content.lower()
        assert "reverb" in content.lower()
        assert "debris" in content.lower()

    def test_custom_chain_name(self):
        result = generate_audio_event_chain_script(chain_name="ExplosionSequence")
        content = result["script_content"]
        assert "ExplosionSequence" in content

    def test_custom_events(self):
        events = [
            {"clip_path": "Audio/SFX/boom", "delay_ms": 0, "volume": 1.0,
             "condition": ""},
            {"clip_path": "Audio/SFX/echo", "delay_ms": 500, "volume": 0.5,
             "condition": "outdoor"},
        ]
        result = generate_audio_event_chain_script(events=events)
        content = result["script_content"]
        assert "boom" in content
        assert "echo" in content

    def test_trigger_chain_method(self):
        result = generate_audio_event_chain_script()
        assert "TriggerChain" in result["script_content"]

    def test_cooldown_system(self):
        result = generate_audio_event_chain_script()
        assert "cooldown" in result["script_content"].lower()

    def test_condition_system(self):
        result = generate_audio_event_chain_script()
        content = result["script_content"]
        assert "condition" in content.lower()
        assert "SetCondition" in content

    def test_interruptible_flag(self):
        result = generate_audio_event_chain_script()
        assert "interruptible" in result["script_content"]

    def test_stop_all_chains(self):
        result = generate_audio_event_chain_script()
        assert "StopAllChains" in result["script_content"]

    def test_delay_ms_to_seconds(self):
        result = generate_audio_event_chain_script()
        # Should convert ms to seconds: delayMs / 1000f
        assert "1000f" in result["script_content"]

    def test_balanced_braces(self):
        result = generate_audio_event_chain_script()
        assert _check_balanced_braces(result["script_content"]), \
            "Unbalanced braces in audio event chain script"

    def test_veilbreakers_identifier(self):
        result = generate_audio_event_chain_script()
        assert "VeilBreakers" in result["script_content"]


# ===========================================================================
# AUDM-08: Procedural Foley
# ===========================================================================


class TestGenerateProceduralFoleyScript:
    """Tests for generate_procedural_foley_script() -- AUDM-08."""

    def test_output_structure(self):
        result = generate_procedural_foley_script()
        _check_output_structure(result)

    def test_contains_monobehaviour(self):
        result = generate_procedural_foley_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_contains_surface_material_enum(self):
        result = generate_procedural_foley_script()
        content = result["script_content"]
        assert "SurfaceMaterial" in content
        assert "Stone" in content
        assert "Wood" in content

    def test_contains_armor_type_enum(self):
        result = generate_procedural_foley_script()
        content = result["script_content"]
        assert "ArmorFoleyType" in content
        assert "Plate" in content
        assert "Leather" in content
        assert "Cloth" in content
        assert "Chain" in content

    def test_contains_movement_speed_enum(self):
        result = generate_procedural_foley_script()
        content = result["script_content"]
        assert "MovementSpeed" in content
        assert "Idle" in content
        assert "Walk" in content
        assert "Run" in content
        assert "Sprint" in content

    def test_default_surfaces(self):
        result = generate_procedural_foley_script()
        content = result["script_content"]
        for surface in ["stone", "wood", "metal", "dirt", "grass", "water", "snow"]:
            assert surface.lower() in content.lower()

    def test_custom_surfaces(self):
        result = generate_procedural_foley_script(
            surface_materials=["sand", "ice", "mud"])
        content = result["script_content"]
        assert "Sand" in content
        assert "Ice" in content
        assert "Mud" in content

    def test_custom_armor_type(self):
        result = generate_procedural_foley_script(armor_type="leather")
        assert "Leather" in result["script_content"]

    def test_custom_character_name(self):
        result = generate_procedural_foley_script(character_name="DarkKnight")
        assert "DarkKnight" in result["script_content"]

    def test_surface_detection_raycast(self):
        result = generate_procedural_foley_script()
        content = result["script_content"]
        assert "Physics.Raycast" in content
        assert "sharedMaterial" in content

    def test_animation_event_methods(self):
        result = generate_procedural_foley_script()
        content = result["script_content"]
        assert "OnFootstep" in content
        assert "OnClothRustle" in content
        assert "OnArmorClink" in content

    def test_speed_thresholds(self):
        result = generate_procedural_foley_script()
        content = result["script_content"]
        assert "walkSpeedThreshold" in content
        assert "runSpeedThreshold" in content
        assert "sprintSpeedThreshold" in content

    def test_volume_scaling(self):
        result = generate_procedural_foley_script()
        content = result["script_content"]
        assert "walkVolumeScale" in content
        assert "runVolumeScale" in content
        assert "sprintVolumeScale" in content

    def test_update_movement_speed(self):
        result = generate_procedural_foley_script()
        assert "UpdateMovementSpeed" in result["script_content"]

    def test_set_armor_type_method(self):
        result = generate_procedural_foley_script()
        assert "SetArmorType" in result["script_content"]

    def test_foley_surface_bank(self):
        result = generate_procedural_foley_script()
        assert "VB_FoleySurfaceBank" in result["script_content"]

    def test_foley_armor_bank(self):
        result = generate_procedural_foley_script()
        assert "VB_FoleyArmorBank" in result["script_content"]

    def test_balanced_braces(self):
        result = generate_procedural_foley_script()
        assert _check_balanced_braces(result["script_content"]), \
            "Unbalanced braces in procedural foley script"

    def test_balanced_braces_custom_surfaces(self):
        result = generate_procedural_foley_script(
            surface_materials=["sand", "ice"])
        assert _check_balanced_braces(result["script_content"]), \
            "Unbalanced braces in procedural foley script (custom surfaces)"

    def test_veilbreakers_identifier(self):
        result = generate_procedural_foley_script()
        assert "VeilBreakers" in result["script_content"]


# ===========================================================================
# AUDM-04: Dynamic Music System
# ===========================================================================


class TestGenerateDynamicMusicScript:
    """Tests for generate_dynamic_music_script() -- AUDM-04."""

    def test_output_structure(self):
        result = generate_dynamic_music_script()
        _check_output_structure(result)

    def test_contains_monobehaviour(self):
        result = generate_dynamic_music_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_contains_music_section_enum(self):
        result = generate_dynamic_music_script()
        content = result["script_content"]
        assert "MusicSection" in content
        assert "Intro" in content
        assert "Combat" in content

    def test_contains_music_stem_enum(self):
        result = generate_dynamic_music_script()
        content = result["script_content"]
        assert "MusicStem" in content
        assert "Drums" in content
        assert "Bass" in content
        assert "Melody" in content

    def test_contains_stinger_enum(self):
        result = generate_dynamic_music_script()
        content = result["script_content"]
        assert "StingerEvent" in content
        assert "EnemySpotted" in content
        assert "BossPhaseChange" in content

    def test_custom_sections(self):
        result = generate_dynamic_music_script(
            sections=["Calm", "Danger", "Battle"])
        content = result["script_content"]
        assert "Calm" in content
        assert "Danger" in content
        assert "Battle" in content

    def test_custom_stems(self):
        result = generate_dynamic_music_script(
            stems=["Choir", "Strings", "Horns"])
        content = result["script_content"]
        assert "Choir" in content
        assert "Strings" in content
        assert "Horns" in content

    def test_custom_stingers(self):
        result = generate_dynamic_music_script(
            stingers=["Ambush", "Victory"])
        content = result["script_content"]
        assert "Ambush" in content
        assert "Victory" in content

    def test_crossfade_duration(self):
        result = generate_dynamic_music_script(crossfade_duration=3.5)
        assert "3.5" in result["script_content"]

    def test_transition_to_section(self):
        result = generate_dynamic_music_script()
        assert "TransitionToSection" in result["script_content"]

    def test_play_stinger(self):
        result = generate_dynamic_music_script()
        assert "PlayStinger" in result["script_content"]

    def test_set_stem_volume(self):
        result = generate_dynamic_music_script()
        assert "SetStemVolume" in result["script_content"]

    def test_horizontal_resequencing(self):
        result = generate_dynamic_music_script()
        content = result["script_content"]
        assert "sectionClips" in content
        assert "CrossfadeSection" in content

    def test_vertical_layering(self):
        result = generate_dynamic_music_script()
        content = result["script_content"]
        assert "stemClips" in content
        assert "FadeStemVolume" in content

    def test_stem_mix_data(self):
        result = generate_dynamic_music_script()
        content = result["script_content"]
        assert "VB_StemMix" in content
        assert "stemVolumes" in content

    def test_transition_rules(self):
        result = generate_dynamic_music_script()
        content = result["script_content"]
        assert "VB_MusicTransition" in content
        assert "waitForBar" in content

    def test_singleton_pattern(self):
        result = generate_dynamic_music_script()
        content = result["script_content"]
        assert "DontDestroyOnLoad" in content
        assert "_instance" in content

    def test_balanced_braces(self):
        result = generate_dynamic_music_script()
        assert _check_balanced_braces(result["script_content"]), \
            "Unbalanced braces in dynamic music script"

    def test_balanced_braces_custom(self):
        result = generate_dynamic_music_script(
            sections=["A", "B"], stems=["X", "Y"], stingers=["Z"])
        assert _check_balanced_braces(result["script_content"]), \
            "Unbalanced braces in dynamic music script (custom)"

    def test_veilbreakers_identifier(self):
        result = generate_dynamic_music_script()
        assert "VeilBreakers" in result["script_content"]


# ===========================================================================
# AUDM-05: Portal Audio Propagation
# ===========================================================================


class TestGeneratePortalAudioScript:
    """Tests for generate_portal_audio_script() -- AUDM-05."""

    def test_output_structure(self):
        result = generate_portal_audio_script()
        _check_output_structure(result)

    def test_contains_monobehaviour(self):
        result = generate_portal_audio_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_contains_audio_room_class(self):
        result = generate_portal_audio_script()
        assert "VeilBreakers_AudioRoom" in result["script_content"]

    def test_contains_audio_portal_class(self):
        result = generate_portal_audio_script()
        assert "VeilBreakers_AudioPortal" in result["script_content"]

    def test_contains_door_state_enum(self):
        result = generate_portal_audio_script()
        content = result["script_content"]
        assert "PortalDoorState" in content
        assert "Open" in content
        assert "PartiallyOpen" in content
        assert "Closed" in content

    def test_contains_reverb_zone(self):
        result = generate_portal_audio_script()
        assert "AudioReverbZone" in result["script_content"]

    def test_contains_low_pass_filter(self):
        result = generate_portal_audio_script()
        assert "AudioLowPassFilter" in result["script_content"]

    def test_custom_attenuation(self):
        result = generate_portal_audio_script(
            attenuation_closed=0.95, attenuation_open=0.05)
        content = result["script_content"]
        assert "0.95" in content
        assert "0.05" in content

    def test_set_door_state(self):
        result = generate_portal_audio_script()
        assert "SetDoorState" in result["script_content"]

    def test_set_door_openness(self):
        result = generate_portal_audio_script()
        assert "SetDoorOpenness" in result["script_content"]

    def test_get_current_attenuation(self):
        result = generate_portal_audio_script()
        assert "GetCurrentAttenuation" in result["script_content"]

    def test_room_source_registration(self):
        result = generate_portal_audio_script()
        assert "RegisterSource" in result["script_content"]

    def test_get_room_sources(self):
        result = generate_portal_audio_script()
        assert "GetRoomSources" in result["script_content"]

    def test_listener_room_tracking(self):
        result = generate_portal_audio_script()
        content = result["script_content"]
        assert "GetListenerRoom" in content
        assert "_listenerRoom" in content

    def test_ambient_clip_support(self):
        result = generate_portal_audio_script()
        assert "ambientClip" in result["script_content"]

    def test_balanced_braces(self):
        result = generate_portal_audio_script()
        assert _check_balanced_braces(result["script_content"]), \
            "Unbalanced braces in portal audio script"

    def test_veilbreakers_identifier(self):
        result = generate_portal_audio_script()
        assert "VeilBreakers" in result["script_content"]


# ===========================================================================
# AUDM-07: Dialogue/VO Pipeline
# ===========================================================================


class TestGenerateVOPipelineScript:
    """Tests for generate_vo_pipeline_script() -- AUDM-07."""

    def test_output_structure(self):
        result = generate_vo_pipeline_script()
        _check_output_structure(result)

    def test_contains_monobehaviour(self):
        result = generate_vo_pipeline_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_contains_scriptable_object(self):
        result = generate_vo_pipeline_script()
        assert "ScriptableObject" in result["script_content"]

    def test_contains_vo_entry_class(self):
        result = generate_vo_pipeline_script()
        assert "VB_VOEntry" in result["script_content"]

    def test_contains_vo_database_class(self):
        result = generate_vo_pipeline_script()
        assert "VeilBreakers_VODatabase" in result["script_content"]

    def test_contains_vo_player_class(self):
        result = generate_vo_pipeline_script()
        assert "VeilBreakers_VOPlayer" in result["script_content"]

    def test_contains_emotion_enum(self):
        result = generate_vo_pipeline_script()
        content = result["script_content"]
        assert "VOEmotion" in content
        assert "Neutral" in content
        assert "Aggressive" in content
        assert "Despair" in content

    def test_contains_viseme_markers(self):
        result = generate_vo_pipeline_script()
        content = result["script_content"]
        assert "VB_VisemeMarker" in content
        assert "visemeIndex" in content
        assert "OnViseme" in content

    def test_contains_subtitle_events(self):
        result = generate_vo_pipeline_script()
        content = result["script_content"]
        assert "OnSubtitleStart" in content
        assert "OnSubtitleEnd" in content

    def test_contains_localization(self):
        result = generate_vo_pipeline_script()
        content = result["script_content"]
        assert "VB_LocalizedVO" in content
        assert "locale" in content
        assert "SetLocale" in content

    def test_contains_queue_system(self):
        result = generate_vo_pipeline_script()
        content = result["script_content"]
        assert "QueueVO" in content
        assert "Queue<" in content

    def test_contains_priority_interruption(self):
        result = generate_vo_pipeline_script()
        content = result["script_content"]
        assert "priority" in content
        assert "StopCurrentVO" in content

    def test_contains_create_asset_menu(self):
        result = generate_vo_pipeline_script()
        assert "[CreateAssetMenu" in result["script_content"]

    def test_custom_database_name(self):
        result = generate_vo_pipeline_script(database_name="NPCDialogue")
        content = result["script_content"]
        assert "NPCDialogue" in content

    def test_custom_entries(self):
        entries = [
            {"id": "hello", "subtitle": "Hello there!",
             "emotion": "joy", "duration": 1.5},
        ]
        result = generate_vo_pipeline_script(entries=entries)
        content = result["script_content"]
        assert "hello" in content

    def test_play_vo_method(self):
        result = generate_vo_pipeline_script()
        assert "PlayVO" in result["script_content"]

    def test_is_playing_method(self):
        result = generate_vo_pipeline_script()
        assert "IsPlaying" in result["script_content"]

    def test_clear_queue_method(self):
        result = generate_vo_pipeline_script()
        assert "ClearQueue" in result["script_content"]

    def test_emotion_change_event(self):
        result = generate_vo_pipeline_script()
        assert "OnEmotionChange" in result["script_content"]

    def test_balanced_braces(self):
        result = generate_vo_pipeline_script()
        assert _check_balanced_braces(result["script_content"]), \
            "Unbalanced braces in VO pipeline script"

    def test_veilbreakers_identifier(self):
        result = generate_vo_pipeline_script()
        assert "VeilBreakers" in result["script_content"]


# ===========================================================================
# Cross-cutting template quality checks
# ===========================================================================


class TestAudioMiddlewareTemplateQuality:
    """Cross-cutting quality checks for all audio middleware templates."""

    ALL_GENERATORS = [
        generate_spatial_audio_script,
        generate_audio_lod_script,
        generate_layered_sound_script,
        generate_audio_event_chain_script,
        generate_procedural_foley_script,
        generate_dynamic_music_script,
        generate_portal_audio_script,
        generate_vo_pipeline_script,
    ]

    def test_all_return_dicts(self):
        for gen in self.ALL_GENERATORS:
            result = gen()
            assert isinstance(result, dict), f"{gen.__name__} must return dict"

    def test_all_have_script_path(self):
        for gen in self.ALL_GENERATORS:
            result = gen()
            assert "script_path" in result, f"{gen.__name__} missing script_path"
            assert result["script_path"].endswith(".cs"), \
                f"{gen.__name__} script_path must end with .cs"

    def test_all_have_script_content(self):
        for gen in self.ALL_GENERATORS:
            result = gen()
            assert "script_content" in result, \
                f"{gen.__name__} missing script_content"
            assert len(result["script_content"]) > 200, \
                f"{gen.__name__} script_content too short"

    def test_all_have_next_steps(self):
        for gen in self.ALL_GENERATORS:
            result = gen()
            assert "next_steps" in result, f"{gen.__name__} missing next_steps"
            assert len(result["next_steps"]) >= 3, \
                f"{gen.__name__} should have at least 3 next_steps"

    def test_all_contain_veilbreakers(self):
        for gen in self.ALL_GENERATORS:
            result = gen()
            assert "VeilBreakers" in result["script_content"], \
                f"{gen.__name__} must contain VeilBreakers identifier"

    def test_all_contain_using_unity(self):
        for gen in self.ALL_GENERATORS:
            result = gen()
            assert "using UnityEngine;" in result["script_content"], \
                f"{gen.__name__} must contain using UnityEngine"

    def test_all_balanced_braces(self):
        for gen in self.ALL_GENERATORS:
            result = gen()
            assert _check_balanced_braces(result["script_content"]), \
                f"{gen.__name__} has unbalanced braces"

    def test_all_scripts_no_editor_import(self):
        """Middleware scripts are runtime -- they should NOT use UnityEditor."""
        for gen in self.ALL_GENERATORS:
            result = gen()
            assert "using UnityEditor;" not in result["script_content"], \
                f"{gen.__name__} should not import UnityEditor (runtime scripts)"

    def test_no_empty_class_bodies(self):
        """All generated classes should have method implementations."""
        for gen in self.ALL_GENERATORS:
            result = gen()
            content = result["script_content"]
            # Check there are actual method bodies (contain "void" or "public")
            assert "void " in content or "public " in content, \
                f"{gen.__name__} appears to have empty class bodies"

    def test_all_have_auto_generated_comment(self):
        for gen in self.ALL_GENERATORS:
            result = gen()
            assert "Auto-Generated" in result["script_content"], \
                f"{gen.__name__} should have Auto-Generated comment"
