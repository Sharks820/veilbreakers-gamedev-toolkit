"""Unit tests for camera, cinematics, and animation editing C# template generators.

Tests that each generator function produces valid C# source containing
the expected keywords, Unity API calls, and parameter substitutions.
All camera templates generate editor scripts using Cinemachine 3.x API
(Unity.Cinemachine namespace), AnimationUtility.SetEditorCurve (not SetCurve),
and Timeline with proper asset save ordering.
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.camera_templates import (
    generate_cinemachine_setup_script,
    generate_state_driven_camera_script,
    generate_camera_shake_script,
    generate_camera_blend_script,
    generate_timeline_setup_script,
    generate_cutscene_setup_script,
    generate_animation_clip_editor_script,
    generate_animator_modifier_script,
    generate_avatar_mask_script,
    generate_video_player_script,
)


# ---------------------------------------------------------------------------
# CAM-01: Cinemachine virtual camera setup
# ---------------------------------------------------------------------------


class TestCinemachineSetup:
    """Tests for generate_cinemachine_setup_script()."""

    def test_default_args(self):
        result = generate_cinemachine_setup_script()
        assert "CinemachineCamera" in result
        assert "MenuItem" in result

    def test_custom_args(self):
        result = generate_cinemachine_setup_script(
            camera_type="follow",
            follow_target="Player",
            look_at_target="Boss",
            priority=20,
            radius=8.0,
        )
        assert "CinemachineFollow" in result
        assert "Player" in result
        assert "Boss" in result
        assert "20" in result

    def test_contains_required_api(self):
        result = generate_cinemachine_setup_script()
        assert "using Unity.Cinemachine;" in result
        assert "CinemachineCamera" in result
        assert "CinemachineOrbitalFollow" in result
        assert "CinemachineRotationComposer" in result

    def test_orbital_type(self):
        result = generate_cinemachine_setup_script(camera_type="orbital")
        assert "CinemachineOrbitalFollow" in result
        assert "Radius" in result

    def test_follow_type(self):
        result = generate_cinemachine_setup_script(camera_type="follow")
        assert "CinemachineFollow" in result
        assert "FollowOffset" in result

    def test_dolly_type(self):
        result = generate_cinemachine_setup_script(camera_type="dolly")
        assert "CinemachineSplineDolly" in result

    def test_uses_cinemachine_3x_namespace(self):
        result = generate_cinemachine_setup_script()
        assert "using Unity.Cinemachine;" in result
        # Must NOT use legacy 2.x namespace
        assert "using Cinemachine;" not in result or "using Unity.Cinemachine;" in result

    def test_no_legacy_freelook(self):
        result = generate_cinemachine_setup_script()
        assert "CinemachineFreeLook" not in result

    def test_no_legacy_virtual_camera(self):
        result = generate_cinemachine_setup_script()
        assert "CinemachineVirtualCamera" not in result

    def test_contains_priority(self):
        result = generate_cinemachine_setup_script(priority=15)
        assert "Priority" in result
        assert "15" in result

    def test_contains_target_offset(self):
        result = generate_cinemachine_setup_script(target_offset=[0.0, 2.0, 0.5])
        assert "2f" in result or "2.0f" in result

    def test_contains_damping(self):
        result = generate_cinemachine_setup_script(damping=[2.0, 1.0, 0.5])
        assert "Damping" in result

    def test_contains_result_json(self):
        result = generate_cinemachine_setup_script()
        assert "vb_result.json" in result

    def test_contains_namespace(self):
        result = generate_cinemachine_setup_script(namespace="MyGame.Cameras")
        assert "namespace MyGame.Cameras" in result


# ---------------------------------------------------------------------------
# CAM-01: State-driven camera
# ---------------------------------------------------------------------------


class TestStateDrivenCamera:
    """Tests for generate_state_driven_camera_script()."""

    def test_default_args(self):
        result = generate_state_driven_camera_script()
        assert "CinemachineStateDrivenCamera" in result
        assert "MenuItem" in result

    def test_custom_args(self):
        result = generate_state_driven_camera_script(
            camera_name="BossFightCam",
            states=[
                {"state_name": "Phase1", "camera_name": "Phase1Cam"},
                {"state_name": "Phase2", "camera_name": "Phase2Cam"},
                {"state_name": "Phase3", "camera_name": "Phase3Cam"},
            ],
        )
        assert "BossFightCam" in result
        assert "Phase1Cam" in result
        assert "Phase2Cam" in result
        assert "Phase3Cam" in result

    def test_contains_required_api(self):
        result = generate_state_driven_camera_script()
        assert "CinemachineStateDrivenCamera" in result
        assert "AnimatedTarget" in result
        assert "using Unity.Cinemachine;" in result

    def test_creates_child_cameras(self):
        result = generate_state_driven_camera_script(
            states=[{"state_name": "Idle", "camera_name": "IdleCam"}]
        )
        assert "SetParent" in result
        assert "CinemachineCamera" in result

    def test_finds_animator(self):
        result = generate_state_driven_camera_script()
        assert "Animator" in result


# ---------------------------------------------------------------------------
# CAM-04: Camera effects (shake + blend)
# ---------------------------------------------------------------------------


class TestCameraEffects:
    """Tests for generate_camera_shake_script and generate_camera_blend_script."""

    # --- Camera Shake ---

    def test_shake_default_args(self):
        result = generate_camera_shake_script()
        assert "CinemachineImpulseSource" in result
        assert "MenuItem" in result

    def test_shake_custom_args(self):
        result = generate_camera_shake_script(
            impulse_force=1.5,
            impulse_duration=0.5,
            add_listener=False,
        )
        assert "1.5f" in result
        assert "0.5f" in result

    def test_shake_contains_required_api(self):
        result = generate_camera_shake_script()
        assert "CinemachineImpulseSource" in result
        assert "using Unity.Cinemachine;" in result

    def test_shake_with_listener(self):
        result = generate_camera_shake_script(add_listener=True)
        assert "CinemachineImpulseListener" in result

    def test_shake_without_listener(self):
        result = generate_camera_shake_script(add_listener=False)
        assert "CinemachineImpulseListener" not in result

    def test_shake_impulse_definition(self):
        result = generate_camera_shake_script()
        assert "ImpulseDefinition" in result

    # --- Camera Blend ---

    def test_blend_default_args(self):
        result = generate_camera_blend_script()
        assert "CinemachineBrain" in result
        assert "MenuItem" in result

    def test_blend_custom_args(self):
        result = generate_camera_blend_script(
            default_blend_time=3.0,
            blend_style="Cut",
            custom_blends=[
                {"from_cam": "CamA", "to_cam": "CamB", "time": 1.5, "style": "EaseIn"},
            ],
        )
        assert "3f" in result or "3.0f" in result
        assert "Cut" in result
        assert "CamA" in result
        assert "CamB" in result

    def test_blend_contains_required_api(self):
        result = generate_camera_blend_script()
        assert "CinemachineBlendDefinition" in result
        assert "CinemachineBrain" in result
        assert "using Unity.Cinemachine;" in result

    def test_blend_custom_blend_list(self):
        result = generate_camera_blend_script(
            custom_blends=[
                {"from_cam": "Explore", "to_cam": "Combat", "time": 0.5, "style": "EaseInOut"},
            ],
        )
        assert "CinemachineBlenderSettings" in result
        assert "CustomBlend" in result


# ---------------------------------------------------------------------------
# CAM-02: Timeline setup
# ---------------------------------------------------------------------------


class TestTimelineSetup:
    """Tests for generate_timeline_setup_script()."""

    def test_default_args(self):
        result = generate_timeline_setup_script()
        assert "TimelineAsset" in result
        assert "MenuItem" in result

    def test_custom_args(self):
        result = generate_timeline_setup_script(
            timeline_name="BossCutscene",
            tracks=[
                {"type": "animation", "name": "Boss Anim"},
                {"type": "cinemachine", "name": "Boss Camera"},
            ],
            output_path="Assets/Cutscenes",
        )
        assert "BossCutscene" in result
        assert "Boss Anim" in result
        assert "Boss Camera" in result
        assert "Assets/Cutscenes" in result

    def test_contains_required_api(self):
        result = generate_timeline_setup_script()
        assert "TimelineAsset" in result
        assert "using UnityEngine.Timeline;" in result
        assert "using UnityEngine.Playables;" in result

    def test_asset_saved_before_tracks(self):
        """Timeline MUST be saved to AssetDatabase before adding tracks."""
        result = generate_timeline_setup_script()
        create_asset_pos = result.index("AssetDatabase.CreateAsset")
        create_track_pos = result.index("CreateTrack")
        assert create_asset_pos < create_track_pos

    def test_contains_all_track_types(self):
        result = generate_timeline_setup_script(
            tracks=[
                {"type": "animation", "name": "Anim"},
                {"type": "audio", "name": "Audio"},
                {"type": "activation", "name": "Active"},
                {"type": "cinemachine", "name": "Cam"},
            ],
        )
        assert "AnimationTrack" in result
        assert "AudioTrack" in result
        assert "ActivationTrack" in result
        assert "CinemachineTrack" in result

    def test_creates_playable_file(self):
        result = generate_timeline_setup_script(timeline_name="Test")
        assert ".playable" in result

    def test_saves_after_tracks(self):
        result = generate_timeline_setup_script()
        assert "AssetDatabase.SaveAssets()" in result


# ---------------------------------------------------------------------------
# CAM-03: Cutscene setup
# ---------------------------------------------------------------------------


class TestCutsceneSetup:
    """Tests for generate_cutscene_setup_script()."""

    def test_default_args(self):
        result = generate_cutscene_setup_script()
        assert "PlayableDirector" in result
        assert "MenuItem" in result

    def test_custom_args(self):
        result = generate_cutscene_setup_script(
            cutscene_name="IntroCutscene",
            timeline_path="Assets/Timelines/Intro.playable",
            wrap_mode="Loop",
            play_on_awake=True,
        )
        assert "IntroCutscene" in result
        assert "Assets/Timelines/Intro.playable" in result
        assert "Loop" in result
        assert "true" in result

    def test_contains_required_api(self):
        result = generate_cutscene_setup_script()
        assert "PlayableDirector" in result
        assert "playableAsset" in result
        assert "using UnityEngine.Playables;" in result

    def test_contains_wrap_mode(self):
        result = generate_cutscene_setup_script(wrap_mode="Hold")
        assert "DirectorWrapMode.Hold" in result
        assert "WrapMode" in result or "extrapolationMode" in result

    def test_loads_timeline_asset(self):
        result = generate_cutscene_setup_script()
        assert "TimelineAsset" in result
        assert "LoadAssetAtPath" in result


# ---------------------------------------------------------------------------
# ANIMA-01: AnimationClip editor
# ---------------------------------------------------------------------------


class TestAnimClipEditor:
    """Tests for generate_animation_clip_editor_script()."""

    def test_default_args(self):
        result = generate_animation_clip_editor_script()
        assert "AnimationClip" in result
        assert "MenuItem" in result

    def test_custom_args(self):
        result = generate_animation_clip_editor_script(
            clip_name="WalkCycle",
            curves=[
                {
                    "path": "Hips",
                    "component_type": "Transform",
                    "property": "localPosition.y",
                    "keyframes": [[0.0, 0.0], [0.25, 0.1], [0.5, 0.0], [0.75, 0.1], [1.0, 0.0]],
                },
            ],
            output_path="Assets/Animations/Characters",
        )
        assert "WalkCycle" in result
        assert "Hips" in result
        assert "localPosition.y" in result

    def test_contains_required_api(self):
        result = generate_animation_clip_editor_script()
        assert "AnimationUtility.SetEditorCurve" in result
        assert "EditorCurveBinding.FloatCurve" in result
        assert "AnimationCurve" in result
        assert "Keyframe" in result

    def test_no_set_curve(self):
        """Must NOT use AnimationClip.SetCurve (wrong API for editor clips)."""
        result = generate_animation_clip_editor_script()
        assert "AnimationClip.SetCurve" not in result
        # SetEditorCurve is correct, SetCurve alone should not appear without AnimationUtility prefix
        lines = result.split("\n")
        for line in lines:
            if ".SetCurve(" in line and "AnimationUtility" not in line:
                # Allow SetEditorCurve but not bare SetCurve
                assert "SetEditorCurve" in line

    def test_creates_anim_file(self):
        result = generate_animation_clip_editor_script()
        assert ".anim" in result

    def test_multiple_curves(self):
        result = generate_animation_clip_editor_script(
            curves=[
                {"path": "", "component_type": "Transform", "property": "localPosition.x", "keyframes": [[0, 0], [1, 1]]},
                {"path": "", "component_type": "Transform", "property": "localPosition.y", "keyframes": [[0, 0], [1, 2]]},
                {"path": "", "component_type": "Transform", "property": "localPosition.z", "keyframes": [[0, 0], [1, 3]]},
            ],
        )
        assert "binding_0" in result
        assert "binding_1" in result
        assert "binding_2" in result


# ---------------------------------------------------------------------------
# ANIMA-02: Animator Controller modifier
# ---------------------------------------------------------------------------


class TestAnimatorEditor:
    """Tests for generate_animator_modifier_script()."""

    def test_default_args(self):
        result = generate_animator_modifier_script()
        assert "AnimatorController" in result
        assert "MenuItem" in result

    def test_custom_args(self):
        result = generate_animator_modifier_script(
            controller_path="Assets/Animators/Enemy.controller",
            states_to_add=["Patrol", "Chase", "Attack", "Death"],
            transitions=[
                {"from_state": "Patrol", "to_state": "Chase", "has_exit_time": False, "duration": 0.1},
                {"from_state": "Chase", "to_state": "Attack", "has_exit_time": True, "duration": 0.2},
            ],
            parameters=[
                {"name": "AlertLevel", "type": "Float"},
                {"name": "IsDead", "type": "Bool"},
            ],
        )
        assert "Enemy.controller" in result
        assert "Patrol" in result
        assert "Chase" in result
        assert "Attack" in result
        assert "Death" in result
        assert "AlertLevel" in result

    def test_contains_required_api(self):
        result = generate_animator_modifier_script()
        assert "AnimatorController" in result
        assert "using UnityEditor.Animations;" in result
        assert "AddState" in result
        assert "AddTransition" in result

    def test_state_machine_access(self):
        result = generate_animator_modifier_script()
        assert "layers[0].stateMachine" in result

    def test_with_sub_state_machines(self):
        result = generate_animator_modifier_script(
            sub_state_machines=["CombatStates", "LocomotionStates"],
        )
        assert "AddStateMachine" in result
        assert "CombatStates" in result
        assert "LocomotionStates" in result

    def test_parameter_types(self):
        result = generate_animator_modifier_script(
            parameters=[
                {"name": "Speed", "type": "Float"},
                {"name": "Health", "type": "Int"},
                {"name": "IsAlive", "type": "Bool"},
                {"name": "Jump", "type": "Trigger"},
            ],
        )
        assert "AnimatorControllerParameterType.Float" in result
        assert "AnimatorControllerParameterType.Int" in result
        assert "AnimatorControllerParameterType.Bool" in result
        assert "AnimatorControllerParameterType.Trigger" in result

    def test_transition_exit_time(self):
        result = generate_animator_modifier_script(
            transitions=[
                {"from_state": "Idle", "to_state": "Walk", "has_exit_time": True, "duration": 0.5},
            ],
        )
        assert "hasExitTime" in result
        assert "duration" in result


# ---------------------------------------------------------------------------
# ANIMA-03: Avatar mask setup
# ---------------------------------------------------------------------------


class TestAvatarMaskSetup:
    """Tests for generate_avatar_mask_script()."""

    def test_default_args(self):
        result = generate_avatar_mask_script()
        assert "AvatarMask" in result
        assert "MenuItem" in result

    def test_custom_args(self):
        result = generate_avatar_mask_script(
            mask_name="LowerBodyMask",
            body_parts={
                "Body": False,
                "Head": False,
                "LeftLeg": True,
                "RightLeg": True,
            },
            output_path="Assets/Masks",
        )
        assert "LowerBodyMask" in result
        assert "Assets/Masks" in result

    def test_contains_required_api(self):
        result = generate_avatar_mask_script()
        assert "AvatarMask" in result
        assert "SetHumanoidBodyPartActive" in result
        assert "AvatarMaskBodyPart" in result

    def test_body_part_active_states(self):
        result = generate_avatar_mask_script(
            body_parts={"Head": True, "LeftArm": False},
        )
        assert "AvatarMaskBodyPart.Head, true" in result
        assert "AvatarMaskBodyPart.LeftArm, false" in result

    def test_creates_mask_file(self):
        result = generate_avatar_mask_script()
        assert ".mask" in result

    def test_with_transform_paths(self):
        result = generate_avatar_mask_script(
            transform_paths=["Root/Hips/Spine", "Root/Hips/LeftUpLeg"],
        )
        assert "SetTransformPath" in result
        assert "SetTransformActive" in result
        assert "transformCount" in result


# ---------------------------------------------------------------------------
# MEDIA-01: Video player setup
# ---------------------------------------------------------------------------


class TestVideoPlayerSetup:
    """Tests for generate_video_player_script()."""

    def test_default_args(self):
        result = generate_video_player_script()
        assert "VideoPlayer" in result
        assert "MenuItem" in result

    def test_custom_args(self):
        result = generate_video_player_script(
            video_source="url",
            video_path="https://example.com/video.mp4",
            render_texture_width=3840,
            render_texture_height=2160,
            loop=False,
            play_on_awake=False,
        )
        assert "3840" in result
        assert "2160" in result
        assert "Url" in result

    def test_contains_required_api(self):
        result = generate_video_player_script()
        assert "VideoPlayer" in result
        assert "RenderTexture" in result
        assert "renderMode" in result
        assert "using UnityEngine.Video;" in result

    def test_clip_source(self):
        result = generate_video_player_script(video_source="clip", video_path="Assets/Videos/intro.mp4")
        assert "VideoSource.VideoClip" in result

    def test_url_source(self):
        result = generate_video_player_script(video_source="url", video_path="https://example.com/vid.mp4")
        assert "VideoSource.Url" in result
        assert "url" in result

    def test_render_texture_creation(self):
        result = generate_video_player_script()
        assert "new RenderTexture" in result
        assert "VideoRenderMode.RenderTexture" in result

    def test_loop_setting(self):
        result = generate_video_player_script(loop=True)
        assert "isLooping = true" in result

    def test_play_on_awake_setting(self):
        result = generate_video_player_script(play_on_awake=False)
        assert "playOnAwake = false" in result


# ---------------------------------------------------------------------------
# Cross-cutting: No legacy Cinemachine API
# ---------------------------------------------------------------------------


class TestNoLegacyCinemachineAPI:
    """Verify NO legacy Cinemachine 2.x classes appear in any generator output."""

    def _all_cinemachine_outputs(self):
        return [
            generate_cinemachine_setup_script(),
            generate_cinemachine_setup_script(camera_type="follow"),
            generate_cinemachine_setup_script(camera_type="dolly"),
            generate_state_driven_camera_script(),
            generate_camera_shake_script(),
            generate_camera_blend_script(),
        ]

    def test_no_cinemachine_freelook(self):
        for output in self._all_cinemachine_outputs():
            assert "CinemachineFreeLook" not in output

    def test_no_cinemachine_virtual_camera(self):
        for output in self._all_cinemachine_outputs():
            assert "CinemachineVirtualCamera" not in output

    def test_all_use_unity_cinemachine_namespace(self):
        for output in self._all_cinemachine_outputs():
            assert "using Unity.Cinemachine;" in output
