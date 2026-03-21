"""Cinematic sequence C# template generators for Unity Timeline integration.

Each function returns a complete C# source string that can be written to
a Unity project's Assets/Editor/Generated/Cinematic/ directory. When compiled
by Unity, the scripts register as MenuItem commands under
"VeilBreakers/Cinematic/...".

All generated scripts write their result to Temp/vb_result.json so that
the Python MCP server can read back the outcome after execution.

Exports:
    generate_cinematic_script  -- ANIM3-07: Timeline-based cinematic sequences
"""

from __future__ import annotations

import re
from typing import Any


def _sanitize_cs_string(value: str) -> str:
    """Escape a value for safe embedding inside a C# string literal."""
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    return value


def _sanitize_cs_identifier(value: str) -> str:
    """Sanitize a value for use as a C# identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "", value)


# ---------------------------------------------------------------------------
# Shot transition types
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: frozenset[str] = frozenset({
    "cut", "crossfade", "push", "fade_to_black", "fade_from_black",
})

VALID_CHARACTER_ACTIONS: frozenset[str] = frozenset({
    "idle", "walk", "run", "talk", "emote", "fight", "kneel", "sit", "stand",
})

# Default cinematic shots for a dialogue scene
_DEFAULT_SHOTS: list[dict[str, Any]] = [
    {
        "name": "Establishing",
        "camera_position": [0, 3, -8],
        "camera_target": [0, 1.5, 0],
        "duration": 3.0,
        "transition": "fade_from_black",
        "character_actions": [],
    },
    {
        "name": "CloseUp_Speaker",
        "camera_position": [1.5, 1.7, -2],
        "camera_target": [0, 1.6, 0],
        "duration": 4.0,
        "transition": "cut",
        "character_actions": [{"character": "Speaker", "action": "talk"}],
    },
    {
        "name": "Reaction_Listener",
        "camera_position": [-1.5, 1.7, -2],
        "camera_target": [0, 1.6, 0],
        "duration": 2.5,
        "transition": "cut",
        "character_actions": [{"character": "Listener", "action": "idle"}],
    },
    {
        "name": "TwoShot",
        "camera_position": [3, 1.8, -4],
        "camera_target": [0, 1.5, 0],
        "duration": 5.0,
        "transition": "crossfade",
        "character_actions": [
            {"character": "Speaker", "action": "talk"},
            {"character": "Listener", "action": "idle"},
        ],
    },
    {
        "name": "Closing",
        "camera_position": [0, 4, -10],
        "camera_target": [0, 1.0, 0],
        "duration": 3.0,
        "transition": "fade_to_black",
        "character_actions": [],
    },
]


def validate_shots(shots: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate cinematic shot definitions (pure-logic, testable).

    Args:
        shots: List of shot dicts.

    Returns:
        Dict with valid=True/False, errors list, total_duration.
    """
    errors: list[str] = []

    if not shots:
        errors.append("shots list must not be empty")
        return {"valid": False, "errors": errors, "total_duration": 0.0}

    total_duration = 0.0

    for i, shot in enumerate(shots):
        name = shot.get("name", f"Shot_{i}")

        if "camera_position" not in shot:
            errors.append(f"Shot '{name}': missing camera_position")
        elif not isinstance(shot["camera_position"], (list, tuple)) or len(shot["camera_position"]) != 3:
            errors.append(f"Shot '{name}': camera_position must be [x, y, z]")

        if "camera_target" not in shot:
            errors.append(f"Shot '{name}': missing camera_target")
        elif not isinstance(shot["camera_target"], (list, tuple)) or len(shot["camera_target"]) != 3:
            errors.append(f"Shot '{name}': camera_target must be [x, y, z]")

        duration = shot.get("duration", 0)
        if not isinstance(duration, (int, float)) or duration <= 0:
            errors.append(f"Shot '{name}': duration must be > 0")
        else:
            total_duration += duration

        transition = shot.get("transition", "cut")
        if transition not in VALID_TRANSITIONS:
            errors.append(
                f"Shot '{name}': invalid transition '{transition}'. "
                f"Valid: {sorted(VALID_TRANSITIONS)}"
            )

        actions = shot.get("character_actions", [])
        for j, act in enumerate(actions):
            action_type = act.get("action", "")
            if action_type and action_type not in VALID_CHARACTER_ACTIONS:
                errors.append(
                    f"Shot '{name}' action {j}: invalid action '{action_type}'. "
                    f"Valid: {sorted(VALID_CHARACTER_ACTIONS)}"
                )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "total_duration": total_duration,
        "shot_count": len(shots),
    }


def generate_cinematic_script(
    sequence_name: str = "VB_Cinematic",
    shots: list[dict[str, Any]] | None = None,
    output_path: str = "Assets/Timelines",
    namespace: str = "VeilBreakers.Cinematics",
) -> str:
    """Generate C# editor script for Timeline-based cinematic sequence.

    Creates a PlayableDirector with:
    - Cinemachine track with virtual cameras per shot (camera cuts + blends)
    - Animation tracks for character actions
    - Signal/marker track for shot boundaries
    - Audio track placeholder

    Each shot defines camera position, target, duration, transition type,
    and character actions for staging.

    Args:
        sequence_name: Name for the cinematic sequence.
        shots: List of shot dicts. If None, uses default dialogue scene.
        output_path: Unity asset output directory.
        namespace: C# namespace for the generated script.

    Returns:
        Complete C# source string.

    Raises:
        ValueError: If shots validation fails.
    """
    if shots is None:
        shots = _DEFAULT_SHOTS

    validation = validate_shots(shots)
    if not validation["valid"]:
        raise ValueError(
            f"Invalid shots: {'; '.join(validation['errors'])}"
        )

    safe_name = _sanitize_cs_identifier(sequence_name.replace(" ", "_").replace("-", "_"))
    safe_name_str = _sanitize_cs_string(sequence_name)
    safe_path = _sanitize_cs_string(output_path)
    total_duration = validation["total_duration"]

    # Compute cumulative shot start times
    shot_starts: list[float] = []
    current_time = 0.0
    for shot in shots:
        shot_starts.append(current_time)
        current_time += shot.get("duration", 1.0)

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using UnityEngine.Timeline;")
    lines.append("using UnityEngine.Playables;")
    lines.append("using Unity.Cinemachine;")
    lines.append("using System.IO;")
    lines.append("")

    if namespace:
        ns_safe = re.sub(r"[^a-zA-Z0-9_.]", "", namespace)
        lines.append(f"namespace {ns_safe}")
        lines.append("{")

    indent = "    " if namespace else ""
    lines.append(f"{indent}public static class VeilBreakers_Cinematic_{safe_name}")
    lines.append(f"{indent}{{")
    lines.append(f'{indent}    [MenuItem("VeilBreakers/Cinematic/Create {safe_name_str}")]')
    lines.append(f"{indent}    public static void Execute()")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        try")
    lines.append(f"{indent}        {{")

    # Ensure output directory
    lines.append(f'{indent}            string outputDir = "{safe_path}";')
    lines.append(f"{indent}            if (!AssetDatabase.IsValidFolder(outputDir))")
    lines.append(f"{indent}            {{")
    lines.append(f'{indent}                string[] parts = outputDir.Split(\'/\');')
    lines.append(f'{indent}                string current = parts[0];')
    lines.append(f"{indent}                for (int i = 1; i < parts.Length; i++)")
    lines.append(f"{indent}                {{")
    lines.append(f"{indent}                    string next = current + \"/\" + parts[i];")
    lines.append(f"{indent}                    if (!AssetDatabase.IsValidFolder(next))")
    lines.append(f"{indent}                        AssetDatabase.CreateFolder(current, parts[i]);")
    lines.append(f"{indent}                    current = next;")
    lines.append(f"{indent}                }}")
    lines.append(f"{indent}            }}")
    lines.append("")

    # Create Timeline asset
    lines.append(f"{indent}            // Create Timeline asset")
    lines.append(f"{indent}            TimelineAsset timeline = ScriptableObject.CreateInstance<TimelineAsset>();")
    lines.append(f'{indent}            string assetPath = outputDir + "/{safe_name}.playable";')
    lines.append(f"{indent}            AssetDatabase.CreateAsset(timeline, assetPath);")
    lines.append("")

    # Create Cinemachine track for camera cuts
    lines.append(f'{indent}            // Cinemachine track for camera cuts')
    lines.append(f'{indent}            var cameraTrack = timeline.CreateTrack<CinemachineTrack>(null, "Camera Shots");')
    lines.append("")

    # Create virtual cameras and clips for each shot
    lines.append(f"{indent}            // Create virtual cameras for each shot")
    lines.append(f'{indent}            GameObject cinemaRoot = new GameObject("{safe_name_str}_Root");')
    lines.append("")

    for i, shot in enumerate(shots):
        sname = shot.get("name", f"Shot_{i}")
        safe_sname = _sanitize_cs_identifier(sname)
        cam_pos = shot["camera_position"]
        cam_tgt = shot["camera_target"]
        dur = shot.get("duration", 1.0)
        transition = shot.get("transition", "cut")
        start_time = shot_starts[i]

        lines.append(f"{indent}            // Shot {i + 1}: {_sanitize_cs_string(sname)}")
        lines.append(f'{indent}            GameObject cam_{safe_sname} = new GameObject("VCam_{safe_sname}");')
        lines.append(f"{indent}            cam_{safe_sname}.transform.SetParent(cinemaRoot.transform);")
        lines.append(f"{indent}            cam_{safe_sname}.transform.position = new Vector3({cam_pos[0]}f, {cam_pos[1]}f, {cam_pos[2]}f);")
        lines.append(f"{indent}            CinemachineCamera vcam_{safe_sname} = cam_{safe_sname}.AddComponent<CinemachineCamera>();")
        lines.append(f"{indent}            vcam_{safe_sname}.Priority.Value = {10 + i};")

        # Look-at target using RotationComposer
        lines.append(f"{indent}            CinemachineRotationComposer composer_{safe_sname} = cam_{safe_sname}.AddComponent<CinemachineRotationComposer>();")
        lines.append(f'{indent}            GameObject lookTarget_{safe_sname} = new GameObject("LookTarget_{safe_sname}");')
        lines.append(f"{indent}            lookTarget_{safe_sname}.transform.SetParent(cinemaRoot.transform);")
        lines.append(f"{indent}            lookTarget_{safe_sname}.transform.position = new Vector3({cam_tgt[0]}f, {cam_tgt[1]}f, {cam_tgt[2]}f);")
        lines.append(f"{indent}            vcam_{safe_sname}.LookAt = lookTarget_{safe_sname}.transform;")
        lines.append("")

        # Add clip to Cinemachine track
        blend_in = 0.0
        if transition == "crossfade":
            blend_in = 0.5
        elif transition == "fade_to_black" or transition == "fade_from_black":
            blend_in = 0.3

        lines.append(f"{indent}            var clip_{safe_sname} = cameraTrack.CreateDefaultClip();")
        lines.append(f"{indent}            clip_{safe_sname}.displayName = \"{_sanitize_cs_string(sname)}\";")
        lines.append(f"{indent}            clip_{safe_sname}.start = {start_time}d;")
        lines.append(f"{indent}            clip_{safe_sname}.duration = {dur}d;")
        if blend_in > 0:
            lines.append(f"{indent}            clip_{safe_sname}.blendInDuration = {blend_in}d;")
        lines.append("")

    # Add Animation track for character staging
    lines.append(f'{indent}            // Animation track for character actions')
    lines.append(f'{indent}            var animTrack = timeline.CreateTrack<AnimationTrack>(null, "Character Actions");')
    lines.append("")

    # Add markers at shot boundaries
    lines.append(f"{indent}            // Signal track for shot markers")
    lines.append(f'{indent}            var markerTrack = timeline.CreateTrack<ActivationTrack>(null, "Shot Markers");')
    for i, shot in enumerate(shots):
        sname = shot.get("name", f"Shot_{i}")
        safe_sname = _sanitize_cs_identifier(sname)
        start_time = shot_starts[i]
        dur = shot.get("duration", 1.0)
        lines.append(f"{indent}            var marker_{safe_sname} = markerTrack.CreateDefaultClip();")
        lines.append(f'{indent}            marker_{safe_sname}.displayName = "Shot: {_sanitize_cs_string(sname)}";')
        lines.append(f"{indent}            marker_{safe_sname}.start = {start_time}d;")
        lines.append(f"{indent}            marker_{safe_sname}.duration = {dur}d;")
    lines.append("")

    # Audio track placeholder
    lines.append(f'{indent}            var audioTrack = timeline.CreateTrack<AudioTrack>(null, "Dialogue Audio");')
    lines.append("")

    # Create PlayableDirector
    lines.append(f"{indent}            // PlayableDirector to play the timeline")
    lines.append(f"{indent}            PlayableDirector director = cinemaRoot.AddComponent<PlayableDirector>();")
    lines.append(f"{indent}            director.playableAsset = timeline;")
    lines.append(f"{indent}            director.extrapolationMode = DirectorWrapMode.Hold;")
    lines.append(f"{indent}            director.playOnAwake = false;")
    lines.append("")

    # Save
    lines.append(f"{indent}            AssetDatabase.SaveAssets();")
    lines.append(f"{indent}            AssetDatabase.Refresh();")
    lines.append(f"{indent}            Undo.RegisterCreatedObjectUndo(cinemaRoot, \"Create Cinematic\");")
    lines.append(f"{indent}            Selection.activeGameObject = cinemaRoot;")
    lines.append("")

    # Result JSON
    shot_count = len(shots)
    lines.append(f'{indent}            string json = "{{\\"status\\":\\"success\\",\\"sequence_name\\":\\"{safe_name}\\",\\"shot_count\\":{shot_count},\\"total_duration\\":{total_duration},\\"asset_path\\":\\"" + assetPath.Replace("\\\\", "/") + "\\"}}";')
    lines.append(f'{indent}            File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(f'{indent}            Debug.Log("[VeilBreakers] Cinematic sequence created: {safe_name_str} with {shot_count} shots (" + assetPath + ")");')

    lines.append(f"{indent}        }}")
    lines.append(f"{indent}        catch (System.Exception ex)")
    lines.append(f"{indent}        {{")
    lines.append(f'{indent}            string json = "{{\\"status\\":\\"error\\",\\"action\\":\\"cinematic\\",\\"message\\":\\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";')
    lines.append(f'{indent}            File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(f'{indent}            Debug.LogError("[VeilBreakers] Cinematic creation failed: " + ex.Message);')
    lines.append(f"{indent}        }}")
    lines.append(f"{indent}    }}")
    lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    return "\n".join(lines)
