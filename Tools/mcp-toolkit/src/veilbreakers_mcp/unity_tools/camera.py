"""unity_camera tool handler."""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, _read_unity_result, _handle_dict_template,
)

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
from veilbreakers_mcp.shared.unity_templates.cinematic_templates import (
    generate_cinematic_script,
)




# ===========================================================================
# Compound tool: unity_camera (Camera, Cinematics & Animation -- Phase 14)
# ===========================================================================


@mcp.tool()
async def unity_camera(
    action: Literal[
        "create_virtual_camera",      # CAM-01
        "create_state_driven_camera",  # CAM-01
        "create_camera_shake",        # CAM-04
        "configure_blend",            # CAM-04
        "create_timeline",            # CAM-02
        "create_cutscene",            # CAM-03
        "edit_animation_clip",        # ANIMA-01
        "modify_animator",            # ANIMA-02
        "create_avatar_mask",         # ANIMA-03
        "setup_video_player",         # MEDIA-01
        "cinematic_sequence",         # ANIM3-07: Timeline-based cinematic sequences
    ],
    name: str = "default",
    # camera params
    camera_type: str = "orbital",
    follow_target: str = "",
    look_at_target: str = "",
    priority: int = 10,
    radius: float = 5.0,
    target_offset: list[float] | None = None,
    damping: list[float] | None = None,
    # state-driven params
    states: list[dict] | None = None,
    # shake params
    impulse_force: float = 0.5,
    impulse_duration: float = 0.2,
    add_listener: bool = True,
    # blend params
    default_blend_time: float = 2.0,
    blend_style: str = "EaseInOut",
    custom_blends: list[dict] | None = None,
    # timeline params
    tracks: list[dict] | None = None,
    output_path: str = "Assets/Timelines",
    # cutscene params
    timeline_path: str = "",
    wrap_mode: str = "None",
    play_on_awake: bool = False,
    # animation clip params
    clip_name: str = "CustomClip",
    curves: list[dict] | None = None,
    # animator params
    controller_path: str = "",
    states_to_add: list[str] | None = None,
    transitions: list[dict] | None = None,
    parameters: list[dict] | None = None,
    sub_state_machines: list[str] | None = None,
    # avatar mask params
    mask_name: str = "CustomMask",
    body_parts: dict | None = None,
    transform_paths: list[str] | None = None,
    # video params
    video_source: str = "clip",
    video_path: str = "",
    render_texture_width: int = 1920,
    render_texture_height: int = 1080,
    loop: bool = True,
    # common
    namespace: str = "",
    # cinematic sequence params (ANIM3-07)
    shots: list[dict] | None = None,
) -> str:
    """Camera, cinematics, and animation tools -- Cinemachine 3.x virtual cameras,
    state-driven cameras, camera shake, blend profiles, Timeline, cutscenes,
    animation clip editing, animator modification, avatar masks, video player,
    and cinematic sequences.

    Camera actions (camera_templates.py):
    - create_virtual_camera: Cinemachine 3.x camera with orbital/follow/dolly body (CAM-01)
    - create_state_driven_camera: State-driven camera switching by animator state (CAM-01)
    - create_camera_shake: Cinemachine impulse shake system (CAM-04)
    - configure_blend: Camera blend profile configuration (CAM-04)

    Timeline/Cutscene actions:
    - create_timeline: Timeline asset with configurable tracks (CAM-02)
    - create_cutscene: Cutscene setup with PlayableDirector (CAM-03)

    Animation actions:
    - edit_animation_clip: Create/modify animation clips via AnimationUtility (ANIMA-01)
    - modify_animator: Modify animator controller states/transitions/parameters (ANIMA-02)
    - create_avatar_mask: Create avatar mask for animation layers (ANIMA-03)

    Media actions:
    - setup_video_player: Video player with render texture or camera overlay (MEDIA-01)
    - cinematic_sequence: Create Timeline-based cinematic with shots and character staging (ANIM3-07)

    Args:
        action: The camera/animation action to perform.
        name: Name for the generated system (used in file paths).
        camera_type: Virtual camera body type (orbital/follow/dolly).
        follow_target: Transform path for follow target.
        look_at_target: Transform path for look-at target.
        priority: Camera priority (higher = more important).
        radius: Orbital camera radius.
        target_offset: Target offset [x, y, z].
        damping: Damping values [x, y, z].
        states: State-driven camera state definitions.
        impulse_force: Camera shake impulse force.
        impulse_duration: Camera shake impulse duration.
        add_listener: Whether to add impulse listener.
        default_blend_time: Default camera blend time in seconds.
        blend_style: Blend curve style (EaseInOut/Cut/Linear).
        custom_blends: Custom per-camera-pair blend overrides.
        tracks: Timeline track definitions.
        output_path: Output directory for timeline/animation assets.
        timeline_path: Path to existing timeline asset for cutscene.
        wrap_mode: Cutscene wrap mode (None/Loop/Hold).
        play_on_awake: Whether cutscene plays on awake.
        clip_name: Animation clip name.
        curves: Animation curve definitions.
        controller_path: Path to existing animator controller.
        states_to_add: States to add to animator controller.
        transitions: Animator transitions to add.
        parameters: Animator parameters to add.
        sub_state_machines: Sub-state machines to add.
        mask_name: Avatar mask name.
        body_parts: Body part enable/disable map.
        transform_paths: Transform paths for avatar mask.
        video_source: Video source type (clip/url).
        video_path: Path to video clip or URL.
        render_texture_width: Render texture width.
        render_texture_height: Render texture height.
        loop: Whether video loops.
        namespace: C# namespace override (empty = generator default).
    """
    try:
        ns_kwargs: dict = {}
        if namespace:
            ns_kwargs["namespace"] = namespace

        if action == "create_virtual_camera":
            return await _handle_camera_virtual(
                name, camera_type, follow_target, look_at_target,
                priority, radius, target_offset, damping, ns_kwargs,
            )
        elif action == "create_state_driven_camera":
            return await _handle_camera_state_driven(name, states, ns_kwargs)
        elif action == "create_camera_shake":
            return await _handle_camera_shake(
                impulse_force, impulse_duration, add_listener, ns_kwargs,
            )
        elif action == "configure_blend":
            return await _handle_camera_blend(
                default_blend_time, blend_style, custom_blends, ns_kwargs,
            )
        elif action == "create_timeline":
            return await _handle_camera_timeline(name, tracks, output_path, ns_kwargs)
        elif action == "create_cutscene":
            return await _handle_camera_cutscene(
                name, timeline_path, wrap_mode, play_on_awake, ns_kwargs,
            )
        elif action == "edit_animation_clip":
            return await _handle_camera_animation_clip(
                clip_name, curves, output_path, ns_kwargs,
            )
        elif action == "modify_animator":
            return await _handle_camera_animator_modifier(
                controller_path, states_to_add, transitions,
                parameters, sub_state_machines, ns_kwargs,
            )
        elif action == "create_avatar_mask":
            return await _handle_camera_avatar_mask(
                mask_name, body_parts, transform_paths, output_path, ns_kwargs,
            )
        elif action == "setup_video_player":
            return await _handle_camera_video_player(
                video_source, video_path, render_texture_width,
                render_texture_height, loop, play_on_awake, ns_kwargs,
            )
        elif action == "cinematic_sequence":
            return await _handle_camera_cinematic_sequence(
                name, shots, output_path, namespace,
            )
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})

    except Exception as exc:
        logger.exception("unity_camera action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# Camera action handlers
# ---------------------------------------------------------------------------


async def _handle_camera_virtual(
    name: str, camera_type: str, follow_target: str, look_at_target: str,
    priority: int, radius: float, target_offset: list[float] | None,
    damping: list[float] | None, ns_kwargs: dict,
) -> str:
    """Create Cinemachine 3.x virtual camera (CAM-01)."""
    script = generate_cinemachine_setup_script(
        camera_type=camera_type,
        follow_target=follow_target,
        look_at_target=look_at_target,
        priority=priority,
        radius=radius,
        target_offset=target_offset,
        damping=damping,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/Camera/{name}_CinemachineSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_virtual_camera",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the camera setup",
            f"Execute menu item: VeilBreakers > Camera > Setup {name}",
        ],
    }, indent=2)


async def _handle_camera_state_driven(
    name: str, states: list[dict] | None, ns_kwargs: dict,
) -> str:
    """Create state-driven camera (CAM-01)."""
    script = generate_state_driven_camera_script(
        camera_name=f"VB_{name}_StateDrivenCamera",
        states=states,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/Camera/{name}_StateDrivenCamera.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_state_driven_camera",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the state-driven camera",
            f"Execute menu item: VeilBreakers > Camera > Setup {name} State Camera",
        ],
    }, indent=2)


async def _handle_camera_shake(
    impulse_force: float, impulse_duration: float,
    add_listener: bool, ns_kwargs: dict,
) -> str:
    """Create camera shake system (CAM-04)."""
    script = generate_camera_shake_script(
        impulse_force=impulse_force,
        impulse_duration=impulse_duration,
        add_listener=add_listener,
        **ns_kwargs,
    )
    rel_path = "Assets/Editor/Generated/Camera/CameraShakeSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_camera_shake",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the camera shake system",
            "Execute menu item: VeilBreakers > Camera > Setup Shake",
        ],
    }, indent=2)


async def _handle_camera_blend(
    default_blend_time: float, blend_style: str,
    custom_blends: list[dict] | None, ns_kwargs: dict,
) -> str:
    """Configure camera blend profile (CAM-04)."""
    script = generate_camera_blend_script(
        default_blend_time=default_blend_time,
        blend_style=blend_style,
        custom_blends=custom_blends,
        **ns_kwargs,
    )
    rel_path = "Assets/Editor/Generated/Camera/CameraBlendSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "configure_blend",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the blend configuration",
            "Execute menu item: VeilBreakers > Camera > Configure Blends",
        ],
    }, indent=2)


async def _handle_camera_timeline(
    name: str, tracks: list[dict] | None, output_path: str, ns_kwargs: dict,
) -> str:
    """Create timeline asset (CAM-02)."""
    script = generate_timeline_setup_script(
        timeline_name=f"VB_{name}_Timeline",
        tracks=tracks,
        output_path=output_path,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/Camera/{name}_TimelineSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_timeline",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the timeline setup",
            f"Execute menu item: VeilBreakers > Camera > Create {name} Timeline",
        ],
    }, indent=2)


async def _handle_camera_cutscene(
    name: str, timeline_path: str, wrap_mode: str,
    play_on_awake: bool, ns_kwargs: dict,
) -> str:
    """Create cutscene setup (CAM-03)."""
    script = generate_cutscene_setup_script(
        cutscene_name=f"VB_{name}_Cutscene",
        timeline_path=timeline_path or f"Assets/Timelines/VB_{name}_Timeline.playable",
        wrap_mode=wrap_mode,
        play_on_awake=play_on_awake,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/Camera/{name}_CutsceneSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_cutscene",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the cutscene setup",
            f"Execute menu item: VeilBreakers > Camera > Setup {name} Cutscene",
        ],
    }, indent=2)


async def _handle_camera_animation_clip(
    clip_name: str, curves: list[dict] | None,
    output_path: str, ns_kwargs: dict,
) -> str:
    """Create/edit animation clip (ANIMA-01)."""
    script = generate_animation_clip_editor_script(
        clip_name=clip_name,
        curves=curves,
        output_path=output_path,
        **ns_kwargs,
    )
    safe_name = clip_name.replace(" ", "_")
    rel_path = f"Assets/Editor/Generated/Camera/{safe_name}_ClipEditor.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "edit_animation_clip",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the clip editor",
            f"Execute menu item: VeilBreakers > Animation > Create {clip_name}",
        ],
    }, indent=2)


async def _handle_camera_animator_modifier(
    controller_path: str, states_to_add: list[str] | None,
    transitions: list[dict] | None, parameters: list[dict] | None,
    sub_state_machines: list[str] | None, ns_kwargs: dict,
) -> str:
    """Modify animator controller (ANIMA-02)."""
    script = generate_animator_modifier_script(
        controller_path=controller_path or "Assets/Animations/VB_Controller.controller",
        states_to_add=states_to_add,
        transitions=transitions,
        parameters=parameters,
        sub_state_machines=sub_state_machines,
        **ns_kwargs,
    )
    rel_path = "Assets/Editor/Generated/Camera/AnimatorModifier.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "modify_animator",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the animator modifier",
            "Execute menu item: VeilBreakers > Animation > Modify Controller",
        ],
    }, indent=2)


async def _handle_camera_avatar_mask(
    mask_name: str, body_parts: dict | None,
    transform_paths: list[str] | None, output_path: str, ns_kwargs: dict,
) -> str:
    """Create avatar mask (ANIMA-03)."""
    script = generate_avatar_mask_script(
        mask_name=mask_name,
        body_parts=body_parts,
        transform_paths=transform_paths,
        output_path=output_path,
        **ns_kwargs,
    )
    safe_name = mask_name.replace(" ", "_")
    rel_path = f"Assets/Editor/Generated/Camera/{safe_name}_MaskSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_avatar_mask",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the mask setup",
            f"Execute menu item: VeilBreakers > Animation > Create {mask_name}",
        ],
    }, indent=2)


async def _handle_camera_video_player(
    video_source: str, video_path: str, render_texture_width: int,
    render_texture_height: int, loop: bool, play_on_awake: bool,
    ns_kwargs: dict,
) -> str:
    """Setup video player (MEDIA-01)."""
    script = generate_video_player_script(
        video_source=video_source,
        video_path=video_path,
        render_texture_width=render_texture_width,
        render_texture_height=render_texture_height,
        loop=loop,
        play_on_awake=play_on_awake,
        **ns_kwargs,
    )
    rel_path = "Assets/Editor/Generated/Camera/VideoPlayerSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "setup_video_player",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the video player setup",
            "Execute menu item: VeilBreakers > Media > Setup Video Player",
        ],
    }, indent=2)


async def _handle_camera_cinematic_sequence(
    name: str, shots: list[dict] | None, output_path: str, namespace: str,
) -> str:
    """Create Timeline-based cinematic sequence (ANIM3-07)."""
    ns = namespace or "VeilBreakers.Cinematics"
    script = generate_cinematic_script(
        sequence_name=name,
        shots=shots,
        output_path=output_path,
        namespace=ns,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Editor/Generated/Cinematic/VeilBreakers_Cinematic_{safe_name}.cs"
    try:
        abs_path = _write_to_unity(script, rel_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "cinematic_sequence", "message": str(exc)})
    return json.dumps({
        "status": "success",
        "action": "cinematic_sequence",
        "sequence_name": name,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the cinematic script",
            f"Execute menu item: VeilBreakers > Cinematic > Create {name}",
            f"Timeline asset will be saved to: {output_path}/{name}.playable",
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)
