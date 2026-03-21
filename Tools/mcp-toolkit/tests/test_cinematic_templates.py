"""Tests for cinematic sequence templates and AI motion generation validation.

Validates ANIM3-06, ANIM3-07 requirements:
- AI motion param validation (pure-logic)
- Cinematic shot validation (pure-logic)
- Cinematic script generation (C# template)
- Shot transitions, character actions, camera positioning

All pure-logic -- no Blender/Unity required.
"""

from __future__ import annotations

import pytest

from blender_addon.handlers.animation_export import (
    VALID_AI_MOTION_MODELS,
    _validate_ai_motion_params,
)
from src.veilbreakers_mcp.shared.unity_templates.cinematic_templates import (
    VALID_CHARACTER_ACTIONS,
    VALID_TRANSITIONS,
    generate_cinematic_script,
    validate_shots,
)


# ---------------------------------------------------------------------------
# TestAIMotionValidation (ANIM3-06)
# ---------------------------------------------------------------------------


class TestAIMotionValidation:
    """Test _validate_ai_motion_params pure-logic validation."""

    def test_valid_params(self):
        result = _validate_ai_motion_params({
            "object_name": "MyRig",
            "prompt": "character walking forward",
        })
        assert result["valid"] is True
        assert result["errors"] == []

    def test_missing_object_name(self):
        result = _validate_ai_motion_params({"prompt": "walk"})
        assert result["valid"] is False
        assert any("object_name" in e for e in result["errors"])

    def test_missing_prompt(self):
        result = _validate_ai_motion_params({"object_name": "Rig"})
        assert result["valid"] is False
        assert any("prompt" in e for e in result["errors"])

    def test_invalid_model(self):
        result = _validate_ai_motion_params({
            "object_name": "Rig",
            "prompt": "walk",
            "model": "invalid_model",
        })
        assert result["valid"] is False
        assert any("model" in e for e in result["errors"])

    @pytest.mark.parametrize("model", VALID_AI_MOTION_MODELS)
    def test_all_valid_models(self, model):
        result = _validate_ai_motion_params({
            "object_name": "Rig",
            "prompt": "walk",
            "model": model,
        })
        assert result["valid"] is True

    def test_invalid_frame_count(self):
        result = _validate_ai_motion_params({
            "object_name": "Rig",
            "prompt": "walk",
            "frame_count": 0,
        })
        assert result["valid"] is False
        assert any("frame_count" in e for e in result["errors"])

    def test_invalid_fps(self):
        result = _validate_ai_motion_params({
            "object_name": "Rig",
            "prompt": "walk",
            "fps": -1,
        })
        assert result["valid"] is False
        assert any("fps" in e for e in result["errors"])

    def test_invalid_style(self):
        result = _validate_ai_motion_params({
            "object_name": "Rig",
            "prompt": "walk",
            "style": "bad_style",
        })
        assert result["valid"] is False
        assert any("style" in e for e in result["errors"])

    @pytest.mark.parametrize("style", ["realistic", "stylized", "exaggerated", "subtle"])
    def test_all_valid_styles(self, style):
        result = _validate_ai_motion_params({
            "object_name": "Rig",
            "prompt": "walk",
            "style": style,
        })
        assert result["valid"] is True

    def test_duration_positive(self):
        result = _validate_ai_motion_params({
            "object_name": "Rig",
            "prompt": "walk",
            "duration": 2.5,
        })
        assert result["valid"] is True
        assert result["duration"] == 2.5

    def test_negative_duration_invalid(self):
        result = _validate_ai_motion_params({
            "object_name": "Rig",
            "prompt": "walk",
            "duration": -1.0,
        })
        assert result["valid"] is False
        assert any("duration" in e for e in result["errors"])

    def test_defaults(self):
        result = _validate_ai_motion_params({
            "object_name": "Rig",
            "prompt": "walk",
        })
        assert result["model"] == "hy-motion"
        assert result["frame_count"] == 48
        assert result["fps"] == 30
        assert result["style"] == "realistic"
        assert result["duration"] is None

    def test_three_valid_models_available(self):
        """Phase 20 adds motiondiffuse model option."""
        assert len(VALID_AI_MOTION_MODELS) == 3
        assert "hy-motion" in VALID_AI_MOTION_MODELS
        assert "motion-gpt" in VALID_AI_MOTION_MODELS
        assert "motiondiffuse" in VALID_AI_MOTION_MODELS


# ---------------------------------------------------------------------------
# TestValidateShots (ANIM3-07)
# ---------------------------------------------------------------------------


class TestValidateShots:
    """Test validate_shots pure-logic validation."""

    def test_valid_single_shot(self):
        shots = [{
            "name": "TestShot",
            "camera_position": [0, 2, -5],
            "camera_target": [0, 1, 0],
            "duration": 3.0,
            "transition": "cut",
        }]
        result = validate_shots(shots)
        assert result["valid"] is True
        assert result["total_duration"] == pytest.approx(3.0)

    def test_empty_shots_invalid(self):
        result = validate_shots([])
        assert result["valid"] is False
        assert any("empty" in e for e in result["errors"])

    def test_missing_camera_position(self):
        shots = [{
            "name": "Bad",
            "camera_target": [0, 1, 0],
            "duration": 2.0,
            "transition": "cut",
        }]
        result = validate_shots(shots)
        assert result["valid"] is False
        assert any("camera_position" in e for e in result["errors"])

    def test_missing_camera_target(self):
        shots = [{
            "name": "Bad",
            "camera_position": [0, 2, -5],
            "duration": 2.0,
            "transition": "cut",
        }]
        result = validate_shots(shots)
        assert result["valid"] is False
        assert any("camera_target" in e for e in result["errors"])

    def test_invalid_camera_position_length(self):
        shots = [{
            "name": "Bad",
            "camera_position": [0, 2],
            "camera_target": [0, 1, 0],
            "duration": 2.0,
            "transition": "cut",
        }]
        result = validate_shots(shots)
        assert result["valid"] is False

    def test_zero_duration_invalid(self):
        shots = [{
            "name": "Bad",
            "camera_position": [0, 2, -5],
            "camera_target": [0, 1, 0],
            "duration": 0,
            "transition": "cut",
        }]
        result = validate_shots(shots)
        assert result["valid"] is False

    def test_invalid_transition(self):
        shots = [{
            "name": "Bad",
            "camera_position": [0, 2, -5],
            "camera_target": [0, 1, 0],
            "duration": 2.0,
            "transition": "wipe_left",
        }]
        result = validate_shots(shots)
        assert result["valid"] is False
        assert any("transition" in e for e in result["errors"])

    @pytest.mark.parametrize("transition", sorted(VALID_TRANSITIONS))
    def test_all_valid_transitions(self, transition):
        shots = [{
            "name": "Test",
            "camera_position": [0, 2, -5],
            "camera_target": [0, 1, 0],
            "duration": 2.0,
            "transition": transition,
        }]
        result = validate_shots(shots)
        assert result["valid"] is True

    def test_invalid_character_action(self):
        shots = [{
            "name": "Bad",
            "camera_position": [0, 2, -5],
            "camera_target": [0, 1, 0],
            "duration": 2.0,
            "transition": "cut",
            "character_actions": [{"character": "NPC", "action": "fly_away"}],
        }]
        result = validate_shots(shots)
        assert result["valid"] is False

    @pytest.mark.parametrize("action", sorted(VALID_CHARACTER_ACTIONS))
    def test_all_valid_character_actions(self, action):
        shots = [{
            "name": "Test",
            "camera_position": [0, 2, -5],
            "camera_target": [0, 1, 0],
            "duration": 2.0,
            "transition": "cut",
            "character_actions": [{"character": "Hero", "action": action}],
        }]
        result = validate_shots(shots)
        assert result["valid"] is True

    def test_total_duration_summed(self):
        shots = [
            {"name": "A", "camera_position": [0, 0, 0], "camera_target": [0, 0, 1], "duration": 2.0, "transition": "cut"},
            {"name": "B", "camera_position": [0, 0, 0], "camera_target": [0, 0, 1], "duration": 3.0, "transition": "cut"},
            {"name": "C", "camera_position": [0, 0, 0], "camera_target": [0, 0, 1], "duration": 1.5, "transition": "cut"},
        ]
        result = validate_shots(shots)
        assert result["valid"] is True
        assert result["total_duration"] == pytest.approx(6.5)
        assert result["shot_count"] == 3


# ---------------------------------------------------------------------------
# TestCinematicScript (ANIM3-07)
# ---------------------------------------------------------------------------


class TestCinematicScript:
    """Test generate_cinematic_script function."""

    def test_default_returns_string(self):
        result = generate_cinematic_script()
        assert isinstance(result, str)
        assert len(result) > 200

    def test_contains_timeline_creation(self):
        result = generate_cinematic_script()
        assert "TimelineAsset" in result
        assert "CreateAsset" in result

    def test_contains_cinemachine_track(self):
        result = generate_cinematic_script()
        assert "CinemachineTrack" in result
        assert "Camera Shots" in result

    def test_contains_animation_track(self):
        result = generate_cinematic_script()
        assert "AnimationTrack" in result
        assert "Character Actions" in result

    def test_contains_audio_track(self):
        result = generate_cinematic_script()
        assert "AudioTrack" in result

    def test_contains_playable_director(self):
        result = generate_cinematic_script()
        assert "PlayableDirector" in result

    def test_default_shots_have_cameras(self):
        result = generate_cinematic_script()
        assert "VCam_Establishing" in result
        assert "VCam_CloseUp_Speaker" in result
        assert "VCam_Reaction_Listener" in result
        assert "VCam_TwoShot" in result
        assert "VCam_Closing" in result

    def test_custom_sequence_name(self):
        result = generate_cinematic_script(sequence_name="BossIntro")
        assert "BossIntro" in result

    def test_custom_shots(self):
        shots = [
            {
                "name": "Wide",
                "camera_position": [0, 5, -15],
                "camera_target": [0, 0, 0],
                "duration": 4.0,
                "transition": "fade_from_black",
            },
            {
                "name": "Action",
                "camera_position": [2, 2, -3],
                "camera_target": [0, 1, 0],
                "duration": 6.0,
                "transition": "cut",
                "character_actions": [{"character": "Hero", "action": "fight"}],
            },
        ]
        result = generate_cinematic_script(shots=shots)
        assert "VCam_Wide" in result
        assert "VCam_Action" in result
        assert "4d" in result or "4.0d" in result  # duration as double

    def test_crossfade_transition_has_blend(self):
        shots = [{
            "name": "FadeShot",
            "camera_position": [0, 2, -5],
            "camera_target": [0, 1, 0],
            "duration": 3.0,
            "transition": "crossfade",
        }]
        result = generate_cinematic_script(shots=shots)
        assert "blendInDuration" in result

    def test_cut_transition_no_blend(self):
        shots = [{
            "name": "CutShot",
            "camera_position": [0, 2, -5],
            "camera_target": [0, 1, 0],
            "duration": 3.0,
            "transition": "cut",
        }]
        result = generate_cinematic_script(shots=shots)
        assert "blendInDuration" not in result

    def test_invalid_shots_raises(self):
        with pytest.raises(ValueError, match="Invalid shots"):
            generate_cinematic_script(shots=[])

    def test_contains_menu_item(self):
        result = generate_cinematic_script()
        assert "[MenuItem(" in result
        assert "VeilBreakers/Cinematic" in result

    def test_contains_result_json(self):
        result = generate_cinematic_script()
        assert "vb_result.json" in result
        assert "shot_count" in result

    def test_contains_error_handling(self):
        result = generate_cinematic_script()
        assert "catch" in result
        assert "System.Exception" in result

    def test_cs_syntax_brackets_balanced(self):
        result = generate_cinematic_script()
        assert result.count("{") == result.count("}")

    def test_namespace_applied(self):
        result = generate_cinematic_script(namespace="VeilBreakers.Cinematics")
        assert "namespace VeilBreakers.Cinematics" in result

    def test_no_namespace(self):
        result = generate_cinematic_script(namespace="")
        assert "namespace" not in result

    def test_shot_markers_created(self):
        result = generate_cinematic_script()
        assert "Shot Markers" in result
        assert "ActivationTrack" in result

    def test_virtual_camera_components(self):
        result = generate_cinematic_script()
        assert "CinemachineCamera" in result
        assert "CinemachineRotationComposer" in result

    def test_look_targets_created(self):
        result = generate_cinematic_script()
        assert "LookTarget_" in result

    def test_shot_timing_sequential(self):
        """Shot start times should be sequential."""
        shots = [
            {"name": "A", "camera_position": [0, 0, 0], "camera_target": [0, 0, 1], "duration": 2.0, "transition": "cut"},
            {"name": "B", "camera_position": [0, 0, 0], "camera_target": [0, 0, 1], "duration": 3.0, "transition": "cut"},
        ]
        result = generate_cinematic_script(shots=shots)
        # Shot A starts at 0, Shot B starts at 2
        assert "0d" in result or "0.0d" in result
        assert "2d" in result or "2.0d" in result


# ---------------------------------------------------------------------------
# TestValidTransitionsAndActions (data integrity)
# ---------------------------------------------------------------------------


class TestTransitionsAndActions:
    """Test VALID_TRANSITIONS and VALID_CHARACTER_ACTIONS data."""

    def test_five_transitions(self):
        assert len(VALID_TRANSITIONS) == 5

    def test_cut_in_transitions(self):
        assert "cut" in VALID_TRANSITIONS
        assert "crossfade" in VALID_TRANSITIONS

    def test_nine_character_actions(self):
        assert len(VALID_CHARACTER_ACTIONS) == 9

    def test_core_actions_present(self):
        assert "idle" in VALID_CHARACTER_ACTIONS
        assert "walk" in VALID_CHARACTER_ACTIONS
        assert "talk" in VALID_CHARACTER_ACTIONS
        assert "fight" in VALID_CHARACTER_ACTIONS
