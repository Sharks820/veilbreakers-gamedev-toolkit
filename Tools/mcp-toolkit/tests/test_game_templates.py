"""Unit tests for Unity core game system C# template generators.

Tests that each generator function produces valid C# source containing
the expected keywords, Unity API calls, and parameter substitutions.
All game system templates generate runtime MonoBehaviour or utility
scripts -- they must NEVER contain 'using UnityEditor;'.
"""

import json

import pytest

from veilbreakers_mcp.shared.unity_templates.game_templates import (
    generate_save_system_script,
    generate_health_system_script,
    generate_character_controller_script,
    generate_input_config_script,
    generate_settings_menu_script,
    generate_http_client_script,
    generate_interactable_script,
)


# ---------------------------------------------------------------------------
# Save system template (GAME-01)
# ---------------------------------------------------------------------------


class TestSaveSystemTemplate:
    """Tests for generate_save_system_script()."""

    def test_contains_class_declaration(self):
        result = generate_save_system_script()
        assert "class VB_SaveSystem" in result

    def test_no_editor_namespace(self):
        result = generate_save_system_script()
        assert "using UnityEditor" not in result

    def test_contains_save_slots(self):
        result = generate_save_system_script()
        assert "SaveSlot" in result

    def test_contains_encryption(self):
        result = generate_save_system_script(use_encryption=True)
        assert "Aes" in result

    def test_no_encryption_when_disabled(self):
        result = generate_save_system_script(use_encryption=False)
        assert "Aes" not in result
        assert "Encrypt" not in result

    def test_contains_migration(self):
        result = generate_save_system_script()
        assert "Migration" in result or "migration" in result

    def test_contains_json_serialization(self):
        result = generate_save_system_script()
        assert "JsonUtility" in result

    def test_custom_slot_count(self):
        result = generate_save_system_script(slot_count=5)
        assert "5" in result

    def test_contains_monobehaviour(self):
        result = generate_save_system_script()
        assert "MonoBehaviour" in result

    def test_contains_atomic_write(self):
        result = generate_save_system_script()
        assert ".tmp" in result

    def test_contains_backup_rotation(self):
        result = generate_save_system_script()
        assert ".bak" in result

    def test_contains_gzip_compression(self):
        result = generate_save_system_script(use_compression=True)
        assert "GZipStream" in result

    def test_no_compression_when_disabled(self):
        result = generate_save_system_script(use_compression=False)
        assert "GZipStream" not in result

    def test_contains_save_data_class(self):
        result = generate_save_system_script()
        assert "GameSystemsSaveData" in result

    def test_contains_version_field(self):
        result = generate_save_system_script()
        assert "version" in result


# ---------------------------------------------------------------------------
# Health system template (GAME-05)
# ---------------------------------------------------------------------------


class TestHealthSystemTemplate:
    """Tests for generate_health_system_script()."""

    def test_contains_class_declaration(self):
        result = generate_health_system_script()
        assert "class VB_HealthComponent" in result

    def test_no_editor_namespace(self):
        result = generate_health_system_script()
        assert "using UnityEditor" not in result

    def test_contains_damage_method(self):
        result = generate_health_system_script()
        assert "TakeDamage" in result

    def test_contains_heal_method(self):
        result = generate_health_system_script()
        assert "Heal" in result

    def test_contains_death_handling(self):
        result = generate_health_system_script()
        assert "Die" in result or "OnDeath" in result

    def test_contains_damage_numbers_when_enabled(self):
        result = generate_health_system_script(use_damage_numbers=True)
        assert "DamageNumber" in result or "TextMeshPro" in result

    def test_contains_respawn_when_enabled(self):
        result = generate_health_system_script(use_respawn=True)
        assert "Respawn" in result

    def test_max_hp_parameter(self):
        result = generate_health_system_script(max_hp=200)
        assert "200" in result

    def test_contains_invincibility_frames(self):
        result = generate_health_system_script()
        assert "iFrame" in result or "Invincib" in result or "_isInvincible" in result

    def test_contains_damage_result_method(self):
        result = generate_health_system_script()
        assert "DamageResult" in result or "TakeDamageFromResult" in result

    def test_contains_shield_reduction(self):
        result = generate_health_system_script()
        assert "ShieldReduction" in result or "ApplyShield" in result

    def test_contains_unity_event(self):
        result = generate_health_system_script()
        assert "UnityEvent" in result


# ---------------------------------------------------------------------------
# Character controller template (GAME-06)
# ---------------------------------------------------------------------------


class TestCharacterControllerTemplate:
    """Tests for generate_character_controller_script()."""

    def test_contains_class_declaration(self):
        result = generate_character_controller_script()
        assert "class VB_CharacterController" in result

    def test_no_editor_namespace(self):
        result = generate_character_controller_script()
        assert "using UnityEditor" not in result

    def test_uses_character_controller(self):
        result = generate_character_controller_script()
        assert "CharacterController" in result

    def test_no_cinemachine_freelook(self):
        result = generate_character_controller_script()
        assert "CinemachineFreeLook" not in result

    def test_uses_cinemachine_3x(self):
        result = generate_character_controller_script()
        assert "CinemachineCamera" in result

    def test_uses_orbital_follow(self):
        result = generate_character_controller_script()
        assert "CinemachineOrbitalFollow" in result

    def test_third_person_default(self):
        result = generate_character_controller_script(mode="third_person")
        assert "third" in result.lower() or "ThirdPerson" in result

    def test_move_speed_parameter(self):
        result = generate_character_controller_script(move_speed=8.0)
        assert "8" in result

    def test_contains_require_component(self):
        result = generate_character_controller_script()
        assert "RequireComponent" in result

    def test_contains_gravity(self):
        result = generate_character_controller_script()
        assert "gravity" in result.lower()

    def test_contains_jump(self):
        result = generate_character_controller_script()
        assert "Jump" in result or "jump" in result

    def test_contains_slope_handling(self):
        result = generate_character_controller_script()
        assert "slope" in result.lower() or "Slope" in result

    def test_uses_rotation_composer(self):
        result = generate_character_controller_script()
        assert "CinemachineRotationComposer" in result

    def test_contains_camera_setup_class(self):
        result = generate_character_controller_script()
        assert "VB_CameraSetup" in result


# ---------------------------------------------------------------------------
# Input config template (GAME-07)
# ---------------------------------------------------------------------------


class TestInputConfigTemplate:
    """Tests for generate_input_config_script()."""

    def test_returns_tuple(self):
        result = generate_input_config_script()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_json_valid(self):
        input_json, _ = generate_input_config_script()
        parsed = json.loads(input_json)
        assert "maps" in parsed

    def test_json_has_gameplay_map(self):
        input_json, _ = generate_input_config_script()
        parsed = json.loads(input_json)
        map_names = [m["name"] for m in parsed["maps"]]
        assert "Gameplay" in map_names

    def test_json_has_ui_map(self):
        input_json, _ = generate_input_config_script()
        parsed = json.loads(input_json)
        map_names = [m["name"] for m in parsed["maps"]]
        assert "UI" in map_names

    def test_json_has_menu_map(self):
        input_json, _ = generate_input_config_script()
        parsed = json.loads(input_json)
        map_names = [m["name"] for m in parsed["maps"]]
        assert "Menu" in map_names

    def test_json_has_wasd_bindings(self):
        input_json, _ = generate_input_config_script()
        assert "<Keyboard>/w" in input_json

    def test_cs_contains_class(self):
        _, input_cs = generate_input_config_script()
        assert "class VB_InputConfig" in input_cs

    def test_cs_no_editor_namespace(self):
        _, input_cs = generate_input_config_script()
        assert "using UnityEditor" not in input_cs

    def test_cs_contains_rebinding(self):
        _, input_cs = generate_input_config_script(include_rebinding=True)
        assert "SaveBindingOverridesAsJson" in input_cs or "RebindingOperation" in input_cs

    def test_json_has_control_schemes(self):
        input_json, _ = generate_input_config_script()
        parsed = json.loads(input_json)
        assert "controlSchemes" in parsed
        assert len(parsed["controlSchemes"]) > 0

    def test_json_has_gamepad_bindings(self):
        input_json, _ = generate_input_config_script(include_gamepad=True)
        assert "<Gamepad>" in input_json

    def test_cs_contains_action_events(self):
        _, input_cs = generate_input_config_script()
        assert "OnMove" in input_cs
        assert "OnLightAttack" in input_cs

    def test_json_has_unique_guids(self):
        input_json, _ = generate_input_config_script()
        parsed = json.loads(input_json)
        # All action IDs should be unique
        gameplay_map = parsed["maps"][0]
        ids = [a["id"] for a in gameplay_map["actions"]]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Settings menu template (GAME-08)
# ---------------------------------------------------------------------------


class TestSettingsMenuTemplate:
    """Tests for generate_settings_menu_script()."""

    def test_returns_tuple(self):
        result = generate_settings_menu_script()
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_cs_contains_class(self):
        settings_cs, _, _ = generate_settings_menu_script()
        assert "class VB_SettingsMenu" in settings_cs

    def test_cs_no_editor_namespace(self):
        settings_cs, _, _ = generate_settings_menu_script()
        assert "using UnityEditor" not in settings_cs

    def test_cs_contains_quality_settings(self):
        settings_cs, _, _ = generate_settings_menu_script()
        assert "QualitySettings" in settings_cs

    def test_cs_contains_audio_mixer(self):
        settings_cs, _, _ = generate_settings_menu_script()
        assert "AudioMixer" in settings_cs

    def test_uxml_contains_visual_element(self):
        _, settings_uxml, _ = generate_settings_menu_script()
        assert "VisualElement" in settings_uxml

    def test_uxml_contains_slider(self):
        _, settings_uxml, _ = generate_settings_menu_script()
        assert "SliderInt" in settings_uxml

    def test_uss_contains_styling(self):
        _, _, settings_uss = generate_settings_menu_script()
        assert "#1a1a2e" in settings_uss

    def test_cs_contains_playerprefs(self):
        settings_cs, _, _ = generate_settings_menu_script()
        assert "PlayerPrefs" in settings_cs

    def test_uss_contains_gold_accent(self):
        _, _, settings_uss = generate_settings_menu_script()
        assert "#d4a634" in settings_uss

    def test_cs_contains_settings_data(self):
        settings_cs, _, _ = generate_settings_menu_script()
        assert "SettingsData" in settings_cs

    def test_uxml_contains_foldout(self):
        _, settings_uxml, _ = generate_settings_menu_script()
        assert "Foldout" in settings_uxml

    def test_uxml_contains_buttons(self):
        _, settings_uxml, _ = generate_settings_menu_script()
        assert "apply-button" in settings_uxml
        assert "revert-button" in settings_uxml
        assert "defaults-button" in settings_uxml


# ---------------------------------------------------------------------------
# HTTP client template (MEDIA-02)
# ---------------------------------------------------------------------------


class TestHttpClientTemplate:
    """Tests for generate_http_client_script()."""

    def test_contains_class_declaration(self):
        result = generate_http_client_script()
        assert "class VB_HttpClient" in result

    def test_no_editor_namespace(self):
        result = generate_http_client_script()
        assert "using UnityEditor" not in result

    def test_contains_get_method(self):
        result = generate_http_client_script()
        assert "Get<T>" in result or "Get" in result

    def test_contains_post_method(self):
        result = generate_http_client_script()
        assert "Post<T>" in result or "Post" in result

    def test_contains_put_method(self):
        result = generate_http_client_script()
        assert "Put<T>" in result or "Put" in result

    def test_contains_delete_method(self):
        result = generate_http_client_script()
        assert "Delete<T>" in result or "Delete" in result

    def test_contains_retry_logic(self):
        result = generate_http_client_script()
        assert "retry" in result.lower() or "Retry" in result

    def test_contains_web_request(self):
        result = generate_http_client_script()
        assert "UnityWebRequest" in result

    def test_contains_exponential_backoff(self):
        result = generate_http_client_script()
        assert "backoff" in result.lower() or "delay" in result.lower() or "Pow" in result

    def test_contains_http_response(self):
        result = generate_http_client_script()
        assert "HttpResponse" in result

    def test_contains_timeout(self):
        result = generate_http_client_script()
        assert "timeout" in result.lower()

    def test_contains_auth_header(self):
        result = generate_http_client_script()
        assert "Authorization" in result or "Bearer" in result


# ---------------------------------------------------------------------------
# Interactable template (RPG-03)
# ---------------------------------------------------------------------------


class TestInteractableTemplate:
    """Tests for generate_interactable_script()."""

    def test_contains_class_declaration(self):
        result = generate_interactable_script()
        assert "class VB_Interactable" in result

    def test_no_editor_namespace(self):
        result = generate_interactable_script()
        assert "using UnityEditor" not in result

    def test_contains_state_machine(self):
        result = generate_interactable_script()
        assert "InteractState" in result

    def test_contains_door_type(self):
        result = generate_interactable_script()
        assert "Door" in result

    def test_contains_chest_type(self):
        result = generate_interactable_script()
        assert "Chest" in result

    def test_contains_lever_type(self):
        result = generate_interactable_script()
        assert "Lever" in result

    def test_contains_switch_type(self):
        result = generate_interactable_script()
        assert "Switch" in result

    def test_contains_proximity_trigger(self):
        result = generate_interactable_script()
        assert "OnTriggerEnter" in result or "interactionRadius" in result

    def test_contains_interaction_manager(self):
        result = generate_interactable_script()
        assert "VB_InteractionManager" in result

    def test_contains_lock_unlock(self):
        result = generate_interactable_script()
        assert "Lock" in result
        assert "Unlock" in result

    def test_contains_save_load_state(self):
        result = generate_interactable_script()
        assert "GetSaveState" in result or "LoadSaveState" in result

    def test_contains_unity_events(self):
        result = generate_interactable_script()
        assert "UnityEvent" in result
        assert "OnInteract" in result

    def test_contains_interactable_type_enum(self):
        result = generate_interactable_script()
        assert "enum InteractableType" in result

    def test_interaction_radius_parameter(self):
        result = generate_interactable_script(interaction_radius=3.5)
        assert "3.5" in result
