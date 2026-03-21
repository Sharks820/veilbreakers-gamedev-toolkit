"""Tests for Unity animation blend tree and additive layer template generators.

Validates ANIM3-03, ANIM3-04 requirements:
- Blend tree script generation (directional_8way, speed_blend, directional_speed)
- Additive layer script generation (HitReactions, Breathing, custom)
- C# syntax correctness (brackets, escaping, identifiers)
- Parameter configuration
- Avatar mask setup

All pure-logic -- no Unity required.
"""

from __future__ import annotations

import pytest

from src.veilbreakers_mcp.shared.unity_templates.animation_templates import (
    _DIRECTIONAL_8WAY_POSITIONS,
    _SPEED_THRESHOLDS,
    generate_additive_layer_script,
    generate_blend_tree_script,
)


# ---------------------------------------------------------------------------
# TestBlendTreeScript (ANIM3-03)
# ---------------------------------------------------------------------------


class TestBlendTreeScript:
    """Test generate_blend_tree_script function."""

    def test_directional_8way_returns_string(self):
        result = generate_blend_tree_script(blend_type="directional_8way")
        assert isinstance(result, str)
        assert len(result) > 100

    def test_directional_8way_contains_parameters(self):
        result = generate_blend_tree_script(blend_type="directional_8way")
        assert '"moveX"' in result
        assert '"moveY"' in result

    def test_directional_8way_blend_type(self):
        result = generate_blend_tree_script(blend_type="directional_8way")
        assert "FreeformDirectional2D" in result

    def test_directional_8way_has_all_positions(self):
        result = generate_blend_tree_script(blend_type="directional_8way")
        for pos in _DIRECTIONAL_8WAY_POSITIONS:
            assert pos["name"] in result

    def test_speed_blend_returns_string(self):
        result = generate_blend_tree_script(blend_type="speed_blend")
        assert isinstance(result, str)
        assert len(result) > 100

    def test_speed_blend_contains_speed_param(self):
        result = generate_blend_tree_script(blend_type="speed_blend")
        assert '"speed"' in result

    def test_speed_blend_type_1d(self):
        result = generate_blend_tree_script(blend_type="speed_blend")
        assert "Simple1D" in result

    def test_speed_blend_has_thresholds(self):
        result = generate_blend_tree_script(blend_type="speed_blend")
        for t in _SPEED_THRESHOLDS:
            assert t["name"] in result

    def test_directional_speed_returns_string(self):
        result = generate_blend_tree_script(blend_type="directional_speed")
        assert isinstance(result, str)

    def test_directional_speed_three_params(self):
        result = generate_blend_tree_script(blend_type="directional_speed")
        assert '"moveX"' in result
        assert '"moveY"' in result
        assert '"speed"' in result

    def test_directional_speed_cartesian(self):
        result = generate_blend_tree_script(blend_type="directional_speed")
        assert "FreeformCartesian2D" in result

    def test_invalid_blend_type_raises(self):
        with pytest.raises(ValueError, match="Unknown blend_type"):
            generate_blend_tree_script(blend_type="invalid")

    def test_custom_controller_name(self):
        result = generate_blend_tree_script(
            blend_type="speed_blend",
            controller_name="MyLocomotion",
        )
        assert "MyLocomotion" in result

    def test_custom_states_used(self):
        states = [
            {"name": "Stand", "motion_path": "Assets/Anims/Stand.anim"},
            {"name": "Jog", "motion_path": "Assets/Anims/Jog.anim"},
        ]
        result = generate_blend_tree_script(
            blend_type="speed_blend",
            states=states,
        )
        assert "Stand" in result
        assert "Jog" in result
        assert "Assets/Anims/Stand.anim" in result

    def test_motion_clips_mapped(self):
        clips = {"Forward": "Assets/Anims/WalkForward.anim"}
        result = generate_blend_tree_script(
            blend_type="directional_8way",
            motion_clips=clips,
        )
        assert "Assets/Anims/WalkForward.anim" in result

    def test_cs_syntax_brackets_balanced(self):
        result = generate_blend_tree_script(blend_type="directional_8way")
        assert result.count("{") == result.count("}")

    def test_contains_menu_item(self):
        result = generate_blend_tree_script(blend_type="speed_blend")
        assert "[MenuItem(" in result
        assert "VeilBreakers/Animation" in result

    def test_contains_result_json(self):
        result = generate_blend_tree_script(blend_type="directional_8way")
        assert "vb_result.json" in result
        assert "blend_tree" in result

    def test_contains_error_handling(self):
        result = generate_blend_tree_script(blend_type="speed_blend")
        assert "catch" in result
        assert "System.Exception" in result

    def test_controller_create_at_path(self):
        result = generate_blend_tree_script(blend_type="directional_8way")
        assert "AnimatorController.CreateAnimatorControllerAtPath" in result

    def test_all_three_types_produce_valid_scripts(self):
        """All blend types should produce scripts that compile (basic syntax check)."""
        for bt in ("directional_8way", "speed_blend", "directional_speed"):
            result = generate_blend_tree_script(blend_type=bt)
            assert "public static class" in result
            assert "void Execute()" in result
            assert result.count("{") == result.count("}")


# ---------------------------------------------------------------------------
# TestAdditiveLayerScript (ANIM3-04)
# ---------------------------------------------------------------------------


class TestAdditiveLayerScript:
    """Test generate_additive_layer_script function."""

    def test_default_returns_string(self):
        result = generate_additive_layer_script()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_default_has_three_layers(self):
        """Default config: 1 base + 2 additive = 3 layers."""
        result = generate_additive_layer_script()
        assert "layer_count" in result
        assert "3" in result  # 1 base + 2 additive

    def test_contains_additive_blend_mode(self):
        result = generate_additive_layer_script()
        assert "AnimatorLayerBlendingMode.Additive" in result

    def test_hit_reactions_upper_body_mask(self):
        result = generate_additive_layer_script()
        assert "AvatarMaskBodyPart.LeftLeg" in result
        assert "false" in result  # legs disabled for upper body

    def test_breathing_full_body_mask(self):
        result = generate_additive_layer_script()
        assert "LastBodyPart" in result  # full body loop

    def test_weight_parameters_added(self):
        result = generate_additive_layer_script()
        assert "hitReactionWeight" in result
        assert "breathingWeight" in result

    def test_custom_controller_name(self):
        result = generate_additive_layer_script(controller_name="CombatController")
        assert "CombatController" in result

    def test_custom_base_layer_name(self):
        result = generate_additive_layer_script(base_layer_name="Movement")
        assert "Movement" in result

    def test_custom_base_states(self):
        states = [
            {"name": "Stand"},
            {"name": "Crouch"},
        ]
        result = generate_additive_layer_script(base_states=states)
        assert "Stand" in result
        assert "Crouch" in result

    def test_custom_additive_layers(self):
        layers = [
            {
                "name": "Flinch",
                "blend_mode": "Additive",
                "default_weight": 0.0,
                "weight_param": "flinchWeight",
                "avatar_mask": "upper_body",
                "states": [
                    {"name": "NoFlinch", "is_default": True},
                    {"name": "FlinchHeavy"},
                ],
            },
        ]
        result = generate_additive_layer_script(additive_layers=layers)
        assert "Flinch" in result
        assert "flinchWeight" in result
        assert "FlinchHeavy" in result

    def test_cs_syntax_brackets_balanced(self):
        result = generate_additive_layer_script()
        assert result.count("{") == result.count("}")

    def test_contains_menu_item(self):
        result = generate_additive_layer_script()
        assert "[MenuItem(" in result
        assert "VeilBreakers/Animation" in result

    def test_contains_result_json(self):
        result = generate_additive_layer_script()
        assert "vb_result.json" in result

    def test_contains_error_handling(self):
        result = generate_additive_layer_script()
        assert "catch" in result

    def test_default_states_hit_reactions(self):
        """HitReactions layer should have directional hit states."""
        result = generate_additive_layer_script()
        assert "HitFront" in result
        assert "HitBack" in result
        assert "HitLeft" in result
        assert "HitRight" in result

    def test_default_state_set(self):
        """Default states should be marked as default in the state machine."""
        result = generate_additive_layer_script()
        assert "defaultState" in result

    def test_override_blend_mode_supported(self):
        layers = [
            {
                "name": "OverrideLayer",
                "blend_mode": "Override",
                "default_weight": 1.0,
                "weight_param": "overrideWeight",
                "avatar_mask": "full_body",
                "states": [{"name": "OverrideState", "is_default": True}],
            },
        ]
        result = generate_additive_layer_script(additive_layers=layers)
        assert "AnimatorLayerBlendingMode.Override" in result

    def test_motion_path_loaded(self):
        layers = [
            {
                "name": "TestLayer",
                "blend_mode": "Additive",
                "default_weight": 0.5,
                "weight_param": "testWeight",
                "avatar_mask": "full_body",
                "states": [
                    {"name": "TestState", "is_default": True, "motion_path": "Assets/Anims/Test.anim"},
                ],
            },
        ]
        result = generate_additive_layer_script(additive_layers=layers)
        assert "Assets/Anims/Test.anim" in result
        assert "LoadAssetAtPath" in result

    def test_base_state_with_motion(self):
        states = [
            {"name": "Walk", "motion_path": "Assets/Anims/Walk.anim"},
        ]
        result = generate_additive_layer_script(base_states=states)
        assert "Assets/Anims/Walk.anim" in result


# ---------------------------------------------------------------------------
# TestDirectionalPositions (data integrity)
# ---------------------------------------------------------------------------


class TestDirectionalPositions:
    """Test _DIRECTIONAL_8WAY_POSITIONS data integrity."""

    def test_nine_positions(self):
        assert len(_DIRECTIONAL_8WAY_POSITIONS) == 9

    def test_idle_at_origin(self):
        idle = _DIRECTIONAL_8WAY_POSITIONS[0]
        assert idle["name"] == "Idle"
        assert idle["x"] == 0.0
        assert idle["y"] == 0.0

    def test_cardinal_directions(self):
        names = {p["name"] for p in _DIRECTIONAL_8WAY_POSITIONS}
        assert "Forward" in names
        assert "Backward" in names
        assert "Left" in names
        assert "Right" in names

    def test_diagonal_directions(self):
        names = {p["name"] for p in _DIRECTIONAL_8WAY_POSITIONS}
        assert "ForwardL" in names
        assert "ForwardR" in names
        assert "BackwardL" in names
        assert "BackwardR" in names


class TestSpeedThresholds:
    """Test _SPEED_THRESHOLDS data integrity."""

    def test_four_speeds(self):
        assert len(_SPEED_THRESHOLDS) == 4

    def test_ascending_thresholds(self):
        thresholds = [t["threshold"] for t in _SPEED_THRESHOLDS]
        assert thresholds == sorted(thresholds)

    def test_idle_at_zero(self):
        assert _SPEED_THRESHOLDS[0]["name"] == "Idle"
        assert _SPEED_THRESHOLDS[0]["threshold"] == 0.0
