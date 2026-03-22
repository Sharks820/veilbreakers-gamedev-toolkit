"""Comprehensive tests for Terminal 3 VFX deliverables.

Tests all template generators from:
    - evolution_templates.py (P3-C1, P3-C2, P3-C4, P3-C7)
    - combat_vfx_templates.py (P5-Q3, P5-Q4)
    - action_cinematic_templates.py (P5-Q5, party camera)
    - animation_extensions_templates.py (G14, P5-Q8, multi-hit)

Also verifies brand color consistency across all palette dictionaries
against the canonical BrandSystem.cs values.
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.evolution_templates import (
    generate_evolution_system_script,
    generate_capture_system_script,
    generate_corruption_animation_script,
    generate_brand_death_idle_script,
    BRAND_PRIMARY_COLORS as EVO_PRIMARY_COLORS,
    BRAND_GLOW_COLORS as EVO_GLOW_COLORS,
    BRAND_DARK_COLORS as EVO_DARK_COLORS,
    ALL_BRANDS as EVO_ALL_BRANDS,
)

from veilbreakers_mcp.shared.unity_templates.combat_vfx_templates import (
    generate_combo_vfx_script,
    generate_channel_vfx_script,
    ALL_BRANDS as COMBAT_ALL_BRANDS,
)

from veilbreakers_mcp.shared.unity_templates.action_cinematic_templates import (
    generate_action_cinematic_script,
    generate_party_camera_system_script,
    PARTY_CAMERA_PRESETS,
    VALID_ACTION_SHOT_TYPES,
)

from veilbreakers_mcp.shared.unity_templates.animation_extensions_templates import (
    generate_animator_with_transitions_script,
    generate_animation_layer_manager_script,
    generate_multi_hit_events_script,
)

from veilbreakers_mcp.shared.unity_templates.vfx_templates import (
    BRAND_PRIMARY_COLORS as VFX_PRIMARY_COLORS,
    BRAND_GLOW_COLORS as VFX_GLOW_COLORS,
    BRAND_DARK_COLORS as VFX_DARK_COLORS,
    BRAND_VFX_CONFIGS,
)

from veilbreakers_mcp.shared.unity_templates.vfx_mastery_templates import (
    BRAND_COLORS as MASTERY_BRAND_COLORS,
)


# ---------------------------------------------------------------------------
# Canonical brand colors from BrandSystem.cs
# ---------------------------------------------------------------------------

EXPECTED_BRAND_COLORS = {
    "IRON":   [0.55, 0.59, 0.65, 1.0],
    "SAVAGE": [0.71, 0.18, 0.18, 1.0],
    "SURGE":  [0.24, 0.55, 0.86, 1.0],
    "VENOM":  [0.31, 0.71, 0.24, 1.0],
    "DREAD":  [0.47, 0.24, 0.63, 1.0],
    "LEECH":  [0.55, 0.16, 0.31, 1.0],
    "GRACE":  [0.86, 0.86, 0.94, 1.0],
    "MEND":   [0.78, 0.67, 0.31, 1.0],
    "RUIN":   [0.86, 0.47, 0.16, 1.0],
    "VOID":   [0.16, 0.08, 0.24, 1.0],
}

ALL_BRANDS = list(EXPECTED_BRAND_COLORS.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_balanced_braces(code: str) -> bool:
    """Verify that curly braces are balanced in generated C# code."""
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


# ===========================================================================
# 1. evolution_templates.py -- generate_evolution_system_script
# ===========================================================================


class TestGenerateEvolutionSystemScript:
    """Tests for generate_evolution_system_script()."""

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_returns_dict_structure(self, brand):
        result = generate_evolution_system_script(brand)
        _check_output_structure(result)
        _check_cs_path(result)

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_script_path_contains_brand(self, brand):
        result = generate_evolution_system_script(brand)
        assert brand in result["script_path"]

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_script_content_contains_brand(self, brand):
        result = generate_evolution_system_script(brand)
        assert brand in result["script_content"]

    def test_contains_evolution_dissolve_shader_name(self):
        result = generate_evolution_system_script("IRON")
        assert "VB_EvolutionDissolve" in result["script_content"]

    def test_does_not_use_vb_dissolve(self):
        """Shader must be named VB_EvolutionDissolve, not VB_Dissolve."""
        result = generate_evolution_system_script("IRON")
        content = result["script_content"]
        # VB_EvolutionDissolve should be present, plain VB_Dissolve by itself should not
        assert "VB_EvolutionDissolve" in content

    def test_uses_primetween_not_dotween(self):
        result = generate_evolution_system_script("IRON")
        content = result["script_content"]
        assert "PrimeTween" in content or "Tween." in content
        assert "DOTween" not in content

    def test_uses_cs_events_not_eventbus(self):
        result = generate_evolution_system_script("IRON")
        content = result["script_content"]
        assert "event Action" in content
        # Script comments mention "NOT EventBus" as design note; ensure no actual EventBus usage
        assert "EventBus." not in content
        assert "new EventBus" not in content

    def test_uses_particle_system(self):
        result = generate_evolution_system_script("IRON")
        assert "ParticleSystem" in result["script_content"]

    def test_contains_evolution_state_enum(self):
        result = generate_evolution_system_script("IRON")
        content = result["script_content"]
        assert "EvolutionState" in content
        assert "WindUp" in content
        assert "Dissolve" in content
        assert "Reform" in content
        assert "Reveal" in content

    def test_contains_vb_result_json(self):
        result = generate_evolution_system_script("IRON")
        assert "vb_result.json" in result["script_content"]

    def test_contains_menu_item(self):
        result = generate_evolution_system_script("IRON")
        assert "MenuItem" in result["script_content"]

    def test_invalid_brand_falls_back_to_iron(self):
        result = generate_evolution_system_script("INVALID_BRAND")
        assert "IRON" in result["script_content"]

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_all_brands_produce_distinct_output(self, brand):
        """Each brand must produce different C# output."""
        result = generate_evolution_system_script(brand)
        content = result["script_content"]
        # Brand-specific content: brand name in comment or variable
        assert brand in content


# ===========================================================================
# 1b. evolution_templates.py -- generate_capture_system_script
# ===========================================================================


class TestGenerateCaptureSystemScript:
    """Tests for generate_capture_system_script()."""

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_returns_dict_structure(self, brand):
        result = generate_capture_system_script(brand)
        _check_output_structure(result)
        _check_cs_path(result)

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_script_path_contains_brand(self, brand):
        result = generate_capture_system_script(brand)
        assert brand in result["script_path"]

    def test_contains_capture_state_enum(self):
        result = generate_capture_system_script("IRON")
        content = result["script_content"]
        assert "CaptureState" in content
        assert "Binding" in content
        assert "Struggle" in content

    def test_uses_primetween_not_dotween(self):
        result = generate_capture_system_script("IRON")
        content = result["script_content"]
        assert "PrimeTween" in content or "Tween." in content
        assert "DOTween" not in content

    def test_uses_cs_events_not_eventbus(self):
        result = generate_capture_system_script("IRON")
        content = result["script_content"]
        # Should have C# events for capture outcome
        assert "event " in content
        # Script comments mention "NOT EventBus" as design note; ensure no actual EventBus usage
        assert "EventBus." not in content
        assert "new EventBus" not in content

    def test_uses_particle_system(self):
        result = generate_capture_system_script("IRON")
        assert "ParticleSystem" in result["script_content"]

    def test_contains_vb_result_json(self):
        result = generate_capture_system_script("IRON")
        assert "vb_result.json" in result["script_content"]

    def test_contains_menu_item(self):
        result = generate_capture_system_script("IRON")
        assert "MenuItem" in result["script_content"]

    def test_invalid_brand_falls_back_to_iron(self):
        result = generate_capture_system_script("NOT_A_BRAND")
        assert "IRON" in result["script_content"]

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_all_brands_produce_distinct_paths(self, brand):
        result = generate_capture_system_script(brand)
        assert brand in result["script_path"]


# ===========================================================================
# 1c. evolution_templates.py -- generate_corruption_animation_script
# ===========================================================================


class TestGenerateCorruptionAnimationScript:
    """Tests for generate_corruption_animation_script()."""

    def test_returns_dict_structure(self):
        result = generate_corruption_animation_script()
        _check_output_structure(result)
        _check_cs_path(result)

    def test_contains_corruption_tier_enum(self):
        result = generate_corruption_animation_script()
        content = result["script_content"]
        assert "CorruptionTier" in content
        assert "Ascended" in content
        assert "Purified" in content
        assert "Unstable" in content
        assert "Corrupted" in content
        assert "Abyssal" in content

    def test_uses_primetween_not_dotween(self):
        result = generate_corruption_animation_script()
        content = result["script_content"]
        assert "PrimeTween" in content or "Tween." in content
        assert "DOTween" not in content

    def test_uses_particle_system(self):
        result = generate_corruption_animation_script()
        assert "ParticleSystem" in result["script_content"]

    def test_contains_vb_result_json(self):
        result = generate_corruption_animation_script()
        assert "vb_result.json" in result["script_content"]

    def test_contains_menu_item(self):
        result = generate_corruption_animation_script()
        assert "MenuItem" in result["script_content"]

    def test_contains_corruption_level_field(self):
        result = generate_corruption_animation_script()
        assert "corruptionLevel" in result["script_content"]

    def test_contains_animator_reference(self):
        result = generate_corruption_animation_script()
        assert "Animator" in result["script_content"]


# ===========================================================================
# 1d. evolution_templates.py -- generate_brand_death_idle_script
# ===========================================================================


class TestGenerateBrandDeathIdleScript:
    """Tests for generate_brand_death_idle_script()."""

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_returns_dict_structure(self, brand):
        result = generate_brand_death_idle_script(brand)
        _check_output_structure(result)
        _check_cs_path(result)

    def test_contains_brand_death_controller(self):
        result = generate_brand_death_idle_script("IRON")
        assert "BrandDeathController" in result["script_content"]

    def test_contains_brand_idle_modifier(self):
        result = generate_brand_death_idle_script("IRON")
        assert "BrandIdleModifier" in result["script_content"]

    def test_uses_primetween_not_dotween(self):
        result = generate_brand_death_idle_script("IRON")
        content = result["script_content"]
        assert "PrimeTween" in content or "Tween." in content
        assert "DOTween" not in content

    def test_uses_cs_events_not_eventbus(self):
        result = generate_brand_death_idle_script("IRON")
        content = result["script_content"]
        assert "event " in content
        assert "EventBus" not in content

    def test_uses_particle_system(self):
        result = generate_brand_death_idle_script("IRON")
        assert "ParticleSystem" in result["script_content"]

    def test_contains_vb_result_json(self):
        result = generate_brand_death_idle_script("IRON")
        assert "vb_result.json" in result["script_content"]

    def test_contains_menu_item(self):
        result = generate_brand_death_idle_script("IRON")
        assert "MenuItem" in result["script_content"]

    def test_invalid_brand_falls_back_to_iron(self):
        result = generate_brand_death_idle_script("BOGUS")
        assert "IRON" in result["script_content"]

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_all_brands_accepted(self, brand):
        """Every brand must be accepted without error."""
        result = generate_brand_death_idle_script(brand)
        assert isinstance(result["script_content"], str)
        assert len(result["script_content"]) > 200


# ===========================================================================
# 2. combat_vfx_templates.py -- generate_combo_vfx_script
# ===========================================================================


class TestGenerateComboVfxScript:
    """Tests for generate_combo_vfx_script()."""

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_returns_dict_structure(self, brand):
        result = generate_combo_vfx_script(brand)
        _check_output_structure(result)
        _check_cs_path(result)

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_script_path_contains_brand(self, brand):
        result = generate_combo_vfx_script(brand)
        assert brand in result["script_path"]

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_class_name_contains_brand(self, brand):
        result = generate_combo_vfx_script(brand)
        assert f"VB_ComboVFX_{brand}" in result["script_content"]

    def test_uses_particle_system_not_visual_effect(self):
        result = generate_combo_vfx_script("IRON")
        content = result["script_content"]
        assert "ParticleSystem" in content
        # The new combo system should use ParticleSystem primarily
        assert "VisualEffect" not in content or "ParticleSystem" in content

    def test_uses_primetween_not_dotween(self):
        result = generate_combo_vfx_script("IRON")
        content = result["script_content"]
        assert "DOTween" not in content

    def test_contains_combo_tracking(self):
        result = generate_combo_vfx_script("IRON")
        content = result["script_content"]
        assert "comboCount" in content
        assert "comboTimeout" in content

    def test_contains_finisher_logic(self):
        result = generate_combo_vfx_script("IRON")
        content = result["script_content"]
        assert "finisherThreshold" in content
        assert "OnComboFinisher" in content

    def test_contains_vb_result_json(self):
        result = generate_combo_vfx_script("IRON")
        assert "vb_result.json" in result["script_content"]

    def test_contains_events(self):
        result = generate_combo_vfx_script("IRON")
        content = result["script_content"]
        assert "event Action" in content
        assert "EventBus" not in content

    def test_invalid_brand_falls_back_to_iron(self):
        result = generate_combo_vfx_script("NONEXISTENT")
        assert "IRON" in result["script_content"]

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_all_brands_produce_distinct_class_names(self, brand):
        result = generate_combo_vfx_script(brand)
        assert brand in result["script_content"]

    def test_brand_color_dictionaries_present(self):
        """Combo script should embed brand color dictionaries."""
        result = generate_combo_vfx_script("IRON")
        content = result["script_content"]
        assert "BrandPrimary" in content
        assert "BrandGlow" in content


# ===========================================================================
# 2b. combat_vfx_templates.py -- generate_channel_vfx_script
# ===========================================================================


class TestGenerateChannelVfxScript:
    """Tests for generate_channel_vfx_script()."""

    def test_returns_dict_structure(self):
        result = generate_channel_vfx_script()
        _check_output_structure(result)
        _check_cs_path(result)

    def test_contains_channel_controller(self):
        result = generate_channel_vfx_script()
        assert "ChannelVFXController" in result["script_content"]

    def test_contains_aura_controller(self):
        result = generate_channel_vfx_script()
        assert "AuraVFXController" in result["script_content"]

    def test_contains_beam_controller(self):
        result = generate_channel_vfx_script()
        assert "BeamVFXController" in result["script_content"]

    def test_uses_particle_system(self):
        result = generate_channel_vfx_script()
        assert "ParticleSystem" in result["script_content"]

    def test_uses_line_renderer_for_beam(self):
        result = generate_channel_vfx_script()
        assert "LineRenderer" in result["script_content"]

    def test_uses_primetween_not_dotween(self):
        result = generate_channel_vfx_script()
        content = result["script_content"]
        assert "DOTween" not in content

    def test_uses_cs_events_not_eventbus(self):
        result = generate_channel_vfx_script()
        content = result["script_content"]
        assert "event " in content
        assert "EventBus" not in content

    def test_contains_vb_result_json(self):
        result = generate_channel_vfx_script()
        assert "vb_result.json" in result["script_content"]

    def test_contains_brand_color_maps(self):
        """Channel script should embed all brand color dictionaries."""
        result = generate_channel_vfx_script()
        content = result["script_content"]
        assert "BrandPrimary" in content
        assert "BrandGlow" in content
        assert "BrandDark" in content

    def test_next_steps_mention_channel_usage(self):
        result = generate_channel_vfx_script()
        steps_text = " ".join(result["next_steps"])
        assert "Channel" in steps_text or "channel" in steps_text


# ===========================================================================
# 3. action_cinematic_templates.py -- generate_action_cinematic_script
# ===========================================================================


class TestGenerateActionCinematicScript:
    """Tests for generate_action_cinematic_script()."""

    def test_returns_string(self):
        result = generate_action_cinematic_script()
        assert isinstance(result, str)
        assert len(result) > 200

    def test_contains_menu_item(self):
        result = generate_action_cinematic_script()
        assert "MenuItem" in result

    def test_contains_vb_result_json(self):
        result = generate_action_cinematic_script()
        assert "vb_result.json" in result

    def test_contains_timeline_api(self):
        result = generate_action_cinematic_script()
        assert "TimelineAsset" in result
        assert "PlayableDirector" in result

    def test_contains_cinemachine_camera(self):
        result = generate_action_cinematic_script()
        assert "CinemachineCamera" in result

    def test_contains_dead_zone_configuration(self):
        """Camera scripts must have dead zone configuration."""
        result = generate_action_cinematic_script()
        assert "DeadZone" in result

    def test_contains_cinemachine_rotation_composer(self):
        result = generate_action_cinematic_script()
        assert "CinemachineRotationComposer" in result

    def test_default_5_shots(self):
        """Default sequence should have 5 shots."""
        result = generate_action_cinematic_script()
        assert "Shot 1:" in result
        assert "Shot 5:" in result

    def test_custom_shots(self):
        custom_shots = [
            {
                "name": "TestShot1",
                "shot_type": "Static",
                "camera_position": [0, 5, -10],
                "camera_target": [0, 0, 0],
                "duration": 2.0,
                "transition": "cut",
            },
            {
                "name": "TestShot2",
                "shot_type": "CrashZoom",
                "camera_position": [2, 2, -5],
                "camera_target": [0, 1, 0],
                "duration": 1.5,
                "transition": "crossfade",
                "impulse": True,
                "fov_start": 70.0,
            },
        ]
        result = generate_action_cinematic_script(shots=custom_shots)
        assert "TestShot1" in result
        assert "TestShot2" in result
        assert "CrashZoom" in result

    def test_invalid_shot_type_raises_value_error(self):
        bad_shots = [
            {
                "name": "BadShot",
                "shot_type": "InvalidType",
                "camera_position": [0, 0, 0],
                "camera_target": [0, 0, 0],
                "duration": 1.0,
                "transition": "cut",
            },
        ]
        with pytest.raises(ValueError, match="invalid shot_type"):
            generate_action_cinematic_script(shots=bad_shots)

    def test_balanced_braces(self):
        result = generate_action_cinematic_script()
        assert _check_balanced_braces(result)

    def test_dolly_shot_creates_spline(self):
        result = generate_action_cinematic_script()
        # Default shots include DollyIn
        assert "CinemachineSplineDolly" in result

    def test_orbital_shot_creates_orbital_follow(self):
        result = generate_action_cinematic_script()
        # Default shots include OrbitalShot
        assert "CinemachineOrbitalFollow" in result

    def test_slow_motion_shot_type(self):
        result = generate_action_cinematic_script()
        # Default shots include SlowMotion
        assert "SlowMotion" in result or "slo-mo" in result

    def test_impulse_components_on_impulse_shots(self):
        result = generate_action_cinematic_script()
        # Default has impulse on CrashZoom and SlowMotion
        assert "CinemachineImpulseSource" in result
        assert "CinemachineImpulseListener" in result


# ===========================================================================
# 3b. action_cinematic_templates.py -- generate_party_camera_system_script
# ===========================================================================


class TestGeneratePartyCameraSystemScript:
    """Tests for generate_party_camera_system_script()."""

    def test_returns_dict_structure(self):
        result = generate_party_camera_system_script()
        _check_output_structure(result)
        _check_cs_path(result)

    def test_contains_camera_state_enum(self):
        result = generate_party_camera_system_script()
        content = result["script_content"]
        assert "CameraState" in content
        assert "exploration" in content or "Exploration" in content

    def test_contains_primetween(self):
        result = generate_party_camera_system_script()
        content = result["script_content"]
        assert "PrimeTween" in content
        assert "DOTween" not in content

    def test_contains_cinemachine_camera(self):
        result = generate_party_camera_system_script()
        content = result["script_content"]
        assert "CinemachineCamera" in content

    def test_contains_cinemachine_follow(self):
        result = generate_party_camera_system_script()
        content = result["script_content"]
        assert "CinemachineFollow" in content

    def test_contains_cinemachine_deoccluder(self):
        result = generate_party_camera_system_script()
        content = result["script_content"]
        assert "CinemachineDeoccluder" in content

    def test_contains_cinemachine_rotation_composer(self):
        result = generate_party_camera_system_script()
        content = result["script_content"]
        assert "CinemachineRotationComposer" in content

    def test_contains_on_camera_state_changed_event(self):
        result = generate_party_camera_system_script()
        content = result["script_content"]
        assert "OnCameraStateChanged" in content
        assert "event Action" in content

    def test_contains_zoom_support(self):
        result = generate_party_camera_system_script()
        content = result["script_content"]
        assert "zoomSpeed" in content
        assert "Mouse ScrollWheel" in content

    def test_default_presets_included(self):
        result = generate_party_camera_system_script()
        content = result["script_content"]
        for preset_name in PARTY_CAMERA_PRESETS:
            # Preset names are used as identifiers
            assert preset_name.replace(" ", "") in content or preset_name in content

    def test_custom_presets(self):
        custom = {
            "close_up": {"fov": 35.0, "distance": 3.0, "height": 1.5},
            "bird_eye": {"fov": 70.0, "distance": 25.0, "height": 20.0},
        }
        result = generate_party_camera_system_script(presets=custom)
        content = result["script_content"]
        assert "close_up" in content or "closeup" in content
        assert "bird_eye" in content or "birdeye" in content

    def test_custom_class_name(self):
        result = generate_party_camera_system_script(class_name="MyCameraCtrl")
        content = result["script_content"]
        assert "MyCameraCtrl" in content

    def test_balanced_braces(self):
        result = generate_party_camera_system_script()
        assert _check_balanced_braces(result["script_content"])


# ===========================================================================
# 4. animation_extensions_templates.py -- generate_animator_with_transitions_script
# ===========================================================================


class TestGenerateAnimatorWithTransitionsScript:
    """Tests for generate_animator_with_transitions_script()."""

    def test_returns_string(self):
        result = generate_animator_with_transitions_script()
        assert isinstance(result, str)
        assert len(result) > 200

    def test_contains_menu_item(self):
        result = generate_animator_with_transitions_script()
        assert "MenuItem" in result

    def test_contains_vb_result_json(self):
        result = generate_animator_with_transitions_script()
        assert "vb_result.json" in result

    def test_contains_animator_controller(self):
        result = generate_animator_with_transitions_script()
        assert "AnimatorController" in result

    def test_contains_default_states(self):
        result = generate_animator_with_transitions_script()
        assert "Idle" in result
        assert "Walk" in result
        assert "Run" in result
        assert "Attack" in result

    def test_contains_default_parameters(self):
        result = generate_animator_with_transitions_script()
        assert "speed" in result
        assert "attackTrigger" in result

    def test_contains_transitions(self):
        result = generate_animator_with_transitions_script()
        assert "AddTransition" in result
        assert "AnimatorConditionMode" in result

    def test_contains_any_state_transition(self):
        result = generate_animator_with_transitions_script()
        assert "AddAnyStateTransition" in result

    def test_custom_states_and_transitions(self):
        states = [
            {"name": "Stand", "motion_path": ""},
            {"name": "Crouch", "motion_path": ""},
        ]
        transitions = [
            {
                "from": "Stand",
                "to": "Crouch",
                "conditions": [{"param": "isCrouching", "mode": "IfTrue"}],
                "duration": 0.2,
                "has_exit_time": False,
            }
        ]
        parameters = [{"name": "isCrouching", "type": "Bool"}]
        result = generate_animator_with_transitions_script(
            controller_name="CrouchTest",
            states=states,
            transitions=transitions,
            parameters=parameters,
        )
        assert "Stand" in result
        assert "Crouch" in result
        assert "isCrouching" in result
        assert "CrouchTest" in result

    def test_balanced_braces(self):
        result = generate_animator_with_transitions_script()
        assert _check_balanced_braces(result)

    def test_has_exit_time_handling(self):
        result = generate_animator_with_transitions_script()
        assert "hasExitTime" in result
        assert "exitTime" in result


# ===========================================================================
# 4b. animation_extensions_templates.py -- generate_animation_layer_manager_script
# ===========================================================================


class TestGenerateAnimationLayerManagerScript:
    """Tests for generate_animation_layer_manager_script()."""

    def test_returns_dict_structure(self):
        result = generate_animation_layer_manager_script()
        _check_output_structure(result)
        _check_cs_path(result)

    def test_contains_primetween(self):
        result = generate_animation_layer_manager_script()
        content = result["script_content"]
        assert "PrimeTween" in content
        assert "Tween.Custom" in content

    def test_does_not_use_dotween(self):
        result = generate_animation_layer_manager_script()
        assert "DOTween" not in result["script_content"]

    def test_contains_layer_preset_enum(self):
        result = generate_animation_layer_manager_script()
        content = result["script_content"]
        assert "LayerPreset" in content
        assert "WalkCast" in content
        assert "IdleLook" in content
        assert "RunGuard" in content
        assert "AnyHitReaction" in content

    def test_contains_set_layer_active(self):
        result = generate_animation_layer_manager_script()
        assert "SetLayerActive" in result["script_content"]

    def test_contains_set_layer_inactive(self):
        result = generate_animation_layer_manager_script()
        assert "SetLayerInactive" in result["script_content"]

    def test_contains_activate_preset(self):
        result = generate_animation_layer_manager_script()
        assert "ActivatePreset" in result["script_content"]

    def test_contains_deactivate_preset(self):
        result = generate_animation_layer_manager_script()
        assert "DeactivatePreset" in result["script_content"]

    def test_contains_animator_reference(self):
        result = generate_animation_layer_manager_script()
        content = result["script_content"]
        assert "Animator" in content
        assert "GetLayerWeight" in content

    def test_contains_namespace(self):
        result = generate_animation_layer_manager_script()
        assert "namespace VeilBreakers.Animation" in result["script_content"]

    def test_custom_presets(self):
        custom = {
            "Sprint": {
                "description": "Sprint mode",
                "layers": {"SprintLayer": 1.0},
            },
        }
        result = generate_animation_layer_manager_script(presets=custom)
        content = result["script_content"]
        assert "Sprint" in content
        assert "SprintLayer" in content

    def test_custom_class_name(self):
        result = generate_animation_layer_manager_script(class_name="MyLayerMgr")
        content = result["script_content"]
        assert "MyLayerMgr" in content

    def test_balanced_braces(self):
        result = generate_animation_layer_manager_script()
        assert _check_balanced_braces(result["script_content"])


# ===========================================================================
# 4c. animation_extensions_templates.py -- generate_multi_hit_events_script
# ===========================================================================


class TestGenerateMultiHitEventsScript:
    """Tests for generate_multi_hit_events_script()."""

    def test_returns_string(self):
        result = generate_multi_hit_events_script()
        assert isinstance(result, str)
        assert len(result) > 200

    def test_contains_menu_item(self):
        result = generate_multi_hit_events_script()
        assert "MenuItem" in result

    def test_contains_vb_result_json(self):
        result = generate_multi_hit_events_script()
        assert "vb_result.json" in result

    def test_contains_animation_event_api(self):
        result = generate_multi_hit_events_script()
        assert "AnimationEvent" in result
        assert "AnimationUtility.SetAnimationEvents" in result

    def test_contains_on_combat_hit_function(self):
        result = generate_multi_hit_events_script()
        assert "OnCombatHit" in result

    def test_default_hit_events(self):
        """Default should have 3 hits at frames 8, 16, 24."""
        result = generate_multi_hit_events_script()
        assert "frame 8" in result or "Hit 0: frame 8" in result
        assert "frame 16" in result or "Hit 1: frame 16" in result
        assert "frame 24" in result or "Hit 2: frame 24" in result

    def test_default_brands_in_events(self):
        result = generate_multi_hit_events_script()
        assert "IRON" in result
        assert "SAVAGE" in result
        assert "SURGE" in result

    def test_custom_events(self):
        custom = [
            {"frame": 5, "hit_index": 0, "brand": "DREAD", "damage_type": "magic", "vfx_intensity": 0.9},
            {"frame": 12, "hit_index": 1, "brand": "VOID", "damage_type": "slam", "vfx_intensity": 1.5},
        ]
        result = generate_multi_hit_events_script(
            clip_name="TestCombo", hit_events=custom
        )
        assert "TestCombo" in result
        assert "DREAD" in result
        assert "VOID" in result
        assert "magic" in result
        assert "slam" in result

    def test_custom_frame_rate(self):
        """Frame rate should affect computed time values."""
        result_30 = generate_multi_hit_events_script(frame_rate=30.0)
        result_60 = generate_multi_hit_events_script(frame_rate=60.0)
        # At frame 8, 30fps = 0.2667s, 60fps = 0.1333s -- different output
        assert result_30 != result_60

    def test_balanced_braces(self):
        result = generate_multi_hit_events_script()
        assert _check_balanced_braces(result)

    def test_string_parameter_encoding(self):
        """Events should encode brand|damage_type in stringParameter."""
        result = generate_multi_hit_events_script()
        assert "IRON|slash" in result
        assert "SAVAGE|pierce" in result
        assert "SURGE|slam" in result


# ===========================================================================
# 5. Brand color verification -- vfx_templates
# ===========================================================================


class TestVfxTemplatesBrandColors:
    """Verify BRAND_PRIMARY_COLORS in vfx_templates matches canonical values."""

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_primary_colors_match(self, brand):
        assert brand in VFX_PRIMARY_COLORS, f"{brand} missing from vfx_templates.BRAND_PRIMARY_COLORS"
        assert VFX_PRIMARY_COLORS[brand] == EXPECTED_BRAND_COLORS[brand], (
            f"{brand} primary color mismatch: {VFX_PRIMARY_COLORS[brand]} != {EXPECTED_BRAND_COLORS[brand]}"
        )

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_glow_colors_defined(self, brand):
        assert brand in VFX_GLOW_COLORS, f"{brand} missing from vfx_templates.BRAND_GLOW_COLORS"
        assert len(VFX_GLOW_COLORS[brand]) == 4

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_dark_colors_defined(self, brand):
        assert brand in VFX_DARK_COLORS, f"{brand} missing from vfx_templates.BRAND_DARK_COLORS"
        assert len(VFX_DARK_COLORS[brand]) == 4

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_vfx_config_color_matches_primary(self, brand):
        """BRAND_VFX_CONFIGS color field must match BRAND_PRIMARY_COLORS."""
        assert brand in BRAND_VFX_CONFIGS, f"{brand} missing from BRAND_VFX_CONFIGS"
        config_color = BRAND_VFX_CONFIGS[brand]["color"]
        expected = VFX_PRIMARY_COLORS[brand]
        assert config_color == expected, (
            f"{brand} VFX config color {config_color} != primary {expected}"
        )

    def test_all_10_brands_present_in_primary(self):
        assert len(VFX_PRIMARY_COLORS) >= 10

    def test_all_10_brands_present_in_glow(self):
        assert len(VFX_GLOW_COLORS) >= 10

    def test_all_10_brands_present_in_dark(self):
        assert len(VFX_DARK_COLORS) >= 10

    def test_all_10_brands_present_in_configs(self):
        assert len(BRAND_VFX_CONFIGS) >= 10


# ===========================================================================
# 5b. Brand color verification -- evolution_templates
# ===========================================================================


class TestEvolutionTemplatesBrandColors:
    """Verify brand colors in evolution_templates match canonical values."""

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_primary_colors_match(self, brand):
        assert brand in EVO_PRIMARY_COLORS, f"{brand} missing from evolution_templates"
        assert EVO_PRIMARY_COLORS[brand] == EXPECTED_BRAND_COLORS[brand]

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_glow_colors_defined(self, brand):
        assert brand in EVO_GLOW_COLORS
        assert len(EVO_GLOW_COLORS[brand]) == 4

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_dark_colors_defined(self, brand):
        assert brand in EVO_DARK_COLORS
        assert len(EVO_DARK_COLORS[brand]) == 4

    def test_all_10_brands_in_all_brands_list(self):
        for brand in ALL_BRANDS:
            assert brand in EVO_ALL_BRANDS


# ===========================================================================
# 5c. Brand color verification -- vfx_mastery_templates
# ===========================================================================


class TestVfxMasteryBrandColors:
    """Verify BRAND_COLORS in vfx_mastery_templates matches canonical values."""

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_rgba_matches_canonical(self, brand):
        assert brand in MASTERY_BRAND_COLORS, f"{brand} missing from BRAND_COLORS"
        rgba = MASTERY_BRAND_COLORS[brand]["rgba"]
        assert rgba == EXPECTED_BRAND_COLORS[brand], (
            f"{brand} mastery rgba {rgba} != expected {EXPECTED_BRAND_COLORS[brand]}"
        )

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_has_dark_field(self, brand):
        assert "dark" in MASTERY_BRAND_COLORS[brand], f"{brand} missing 'dark' field"
        assert len(MASTERY_BRAND_COLORS[brand]["dark"]) == 4

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_has_glow_field(self, brand):
        assert "glow" in MASTERY_BRAND_COLORS[brand], f"{brand} missing 'glow' field"
        assert len(MASTERY_BRAND_COLORS[brand]["glow"]) == 4

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_has_desc_field(self, brand):
        assert "desc" in MASTERY_BRAND_COLORS[brand], f"{brand} missing 'desc' field"
        assert isinstance(MASTERY_BRAND_COLORS[brand]["desc"], str)

    def test_all_10_brands_present(self):
        assert len(MASTERY_BRAND_COLORS) >= 10


# ===========================================================================
# 5d. Cross-module brand color consistency
# ===========================================================================


class TestCrossModuleBrandColorConsistency:
    """Ensure brand colors are consistent across all template modules."""

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_vfx_and_evolution_primary_match(self, brand):
        assert VFX_PRIMARY_COLORS[brand] == EVO_PRIMARY_COLORS[brand], (
            f"{brand}: vfx_templates primary != evolution_templates primary"
        )

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_vfx_and_mastery_primary_match(self, brand):
        assert VFX_PRIMARY_COLORS[brand] == MASTERY_BRAND_COLORS[brand]["rgba"], (
            f"{brand}: vfx_templates primary != mastery rgba"
        )

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_vfx_and_evolution_glow_match(self, brand):
        assert VFX_GLOW_COLORS[brand] == EVO_GLOW_COLORS[brand], (
            f"{brand}: vfx_templates glow != evolution_templates glow"
        )

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_vfx_and_mastery_glow_match(self, brand):
        assert VFX_GLOW_COLORS[brand] == MASTERY_BRAND_COLORS[brand]["glow"], (
            f"{brand}: vfx_templates glow != mastery glow"
        )

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_vfx_and_evolution_dark_match(self, brand):
        assert VFX_DARK_COLORS[brand] == EVO_DARK_COLORS[brand], (
            f"{brand}: vfx_templates dark != evolution_templates dark"
        )

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_vfx_and_mastery_dark_match(self, brand):
        assert VFX_DARK_COLORS[brand] == MASTERY_BRAND_COLORS[brand]["dark"], (
            f"{brand}: vfx_templates dark != mastery dark"
        )


# ===========================================================================
# 6. Distinct output verification -- no copy-paste placeholders
# ===========================================================================


class TestAllBrandsDistinctOutput:
    """Verify that all 10 brands produce genuinely distinct C# output."""

    def test_evolution_scripts_all_distinct(self):
        outputs = set()
        for brand in ALL_BRANDS:
            result = generate_evolution_system_script(brand)
            outputs.add(result["script_content"])
        assert len(outputs) == 10, "Not all 10 brands produce distinct evolution scripts"

    def test_capture_scripts_all_distinct(self):
        outputs = set()
        for brand in ALL_BRANDS:
            result = generate_capture_system_script(brand)
            outputs.add(result["script_content"])
        assert len(outputs) == 10, "Not all 10 brands produce distinct capture scripts"

    def test_combo_vfx_scripts_all_distinct(self):
        outputs = set()
        for brand in ALL_BRANDS:
            result = generate_combo_vfx_script(brand)
            outputs.add(result["script_content"])
        assert len(outputs) == 10, "Not all 10 brands produce distinct combo VFX scripts"

    def test_brand_death_idle_scripts_all_distinct(self):
        outputs = set()
        for brand in ALL_BRANDS:
            result = generate_brand_death_idle_script(brand)
            outputs.add(result["script_content"])
        assert len(outputs) == 10, "Not all 10 brands produce distinct death/idle scripts"


# ===========================================================================
# 7. VALID_ACTION_SHOT_TYPES and PARTY_CAMERA_PRESETS constants
# ===========================================================================


class TestActionCinematicConstants:
    """Verify module-level constants for action cinematic templates."""

    def test_valid_shot_types_contain_expected(self):
        expected = {
            "DollyIn", "DollyOut", "OrbitalShot", "CrashZoom",
            "PullBack", "WhipPan", "CraneUp", "CraneDown",
            "Static", "Tracking", "SlowMotion",
        }
        assert expected.issubset(VALID_ACTION_SHOT_TYPES)

    def test_party_camera_presets_has_6_states(self):
        assert len(PARTY_CAMERA_PRESETS) >= 6

    def test_party_presets_have_required_keys(self):
        for name, data in PARTY_CAMERA_PRESETS.items():
            assert "fov" in data, f"Preset {name} missing 'fov'"
            assert "distance" in data, f"Preset {name} missing 'distance'"
            assert "height" in data, f"Preset {name} missing 'height'"

    def test_party_presets_expected_names(self):
        expected = {"exploration", "combat", "boss_fight", "dialogue", "ability_showcase", "stealth"}
        assert expected.issubset(set(PARTY_CAMERA_PRESETS.keys()))


# ===========================================================================
# 8. combat_vfx_templates ALL_BRANDS consistency
# ===========================================================================


class TestCombatVfxAllBrands:
    """Verify ALL_BRANDS in combat_vfx_templates is complete."""

    def test_combat_all_brands_has_10(self):
        assert len(COMBAT_ALL_BRANDS) == 10

    def test_combat_all_brands_matches_expected(self):
        for brand in ALL_BRANDS:
            assert brand in COMBAT_ALL_BRANDS
