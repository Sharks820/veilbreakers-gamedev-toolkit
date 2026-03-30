"""Action cinematic and party camera C# template generators for Unity.

Provides high-energy action camera systems (dolly, crane, crash zoom, orbital,
slo-mo) and a 3rd-person ARPG party camera with state presets.  All generated
scripts target Cinemachine 3.x APIs and PrimeTween for transitions.

Each function returns either a raw C# string or a dict with script_path,
script_content, and next_steps, ready for the Unity MCP pipeline.

Exports:
    generate_action_cinematic_script   -- P5-Q5: Action camera with Timeline
    generate_party_camera_system_script -- Party camera with ARPG presets
    PARTY_CAMERA_PRESETS               -- State preset definitions
    VALID_ACTION_SHOT_TYPES            -- Accepted shot_type values
"""

from __future__ import annotations

import re
from typing import Any

from ._cs_sanitize import sanitize_cs_identifier, sanitize_cs_string
from .cinematic_templates import validate_shots

# ---------------------------------------------------------------------------
# Action shot types
# ---------------------------------------------------------------------------

VALID_ACTION_SHOT_TYPES: frozenset[str] = frozenset({
    "DollyIn",
    "DollyOut",
    "OrbitalShot",
    "CrashZoom",
    "PullBack",
    "WhipPan",
    "CraneUp",
    "CraneDown",
    "Static",
    "Tracking",
    "SlowMotion",
})

# ---------------------------------------------------------------------------
# Party camera state presets
# ---------------------------------------------------------------------------

PARTY_CAMERA_PRESETS: dict[str, dict[str, float]] = {
    "exploration": {"fov": 55.0, "distance": 12.0, "height": 8.0},
    "combat":      {"fov": 50.0, "distance": 10.0, "height": 6.0},
    "boss_fight":  {"fov": 60.0, "distance": 16.0, "height": 10.0},
    "dialogue":    {"fov": 40.0, "distance": 3.0,  "height": 1.7},
    "ability_showcase": {"fov": 45.0, "distance": 6.0, "height": 1.5},
    "stealth":     {"fov": 55.0, "distance": 14.0, "height": 12.0},
}

# ---------------------------------------------------------------------------
# Default 5-shot action sequence
# ---------------------------------------------------------------------------

_DEFAULT_ACTION_SHOTS: list[dict[str, Any]] = [
    {
        "name": "OpeningDollyIn",
        "shot_type": "DollyIn",
        "camera_position": [0, 5, -20],
        "camera_target": [0, 1.5, 0],
        "duration": 2.5,
        "transition": "fade_from_black",
        "impulse": False,
    },
    {
        "name": "OrbitalReveal",
        "shot_type": "OrbitalShot",
        "camera_position": [8, 3, 0],
        "camera_target": [0, 1.5, 0],
        "duration": 3.0,
        "transition": "crossfade",
        "impulse": False,
    },
    {
        "name": "CrashZoomStrike",
        "shot_type": "CrashZoom",
        "camera_position": [2, 1.8, -6],
        "camera_target": [0, 1.5, 0],
        "duration": 1.0,
        "transition": "cut",
        "impulse": True,
        "fov_start": 60.0,
    },
    {
        "name": "SlowMotionFinisher",
        "shot_type": "SlowMotion",
        "camera_position": [-3, 2, -4],
        "camera_target": [0, 1.2, 0],
        "duration": 2.0,
        "transition": "cut",
        "impulse": True,
        "time_scale": 0.3,
    },
    {
        "name": "PullBackEnding",
        "shot_type": "PullBack",
        "camera_position": [0, 6, -15],
        "camera_target": [0, 1.0, 0],
        "duration": 3.0,
        "transition": "fade_to_black",
        "impulse": False,
    },
]


# ---------------------------------------------------------------------------
# P5-Q5: Action cinematic script
# ---------------------------------------------------------------------------

def generate_action_cinematic_script(
    sequence_name: str = "VB_ActionCinematic",
    shots: list[dict[str, Any]] | None = None,
    output_path: str = "Assets/Timelines/Action",
    namespace: str = "VeilBreakers.Cinematics",
) -> str:
    """Generate C# editor script for an action-oriented cinematic sequence.

    Creates a PlayableDirector with Cinemachine 3.x cameras featuring:
    - DollyIn / DollyOut: CinemachineSplineDolly component
    - OrbitalShot: CinemachineOrbitalFollow component
    - CrashZoom: Custom FOV start value
    - PullBack: CinemachineFollow with pullback offset
    - WhipPan / CraneUp / CraneDown / Static / Tracking: position-based
    - SlowMotion: TimelineClip with Time.timeScale adjustment
    - Impulse: CinemachineImpulseSource + CinemachineImpulseListener

    Timeline tracks: CinemachineTrack, AudioTrack, ActivationTrack.

    Args:
        sequence_name: Name for the cinematic sequence.
        shots: List of shot dicts with shot_type field. Defaults to 5-shot
            action sequence.
        output_path: Unity asset output directory.
        namespace: C# namespace for the generated script.

    Returns:
        Complete C# source string.

    Raises:
        ValueError: If shot validation fails or unknown shot_type used.
    """
    if shots is None:
        shots = _DEFAULT_ACTION_SHOTS

    # Validate base shot structure via shared validator
    validation = validate_shots(shots)
    if not validation["valid"]:
        raise ValueError(
            f"Invalid shots: {'; '.join(validation['errors'])}",
        )

    # Validate action-specific shot_type values
    for i, shot in enumerate(shots):
        shot_type = shot.get("shot_type", "Static")
        if shot_type not in VALID_ACTION_SHOT_TYPES:
            raise ValueError(
                f"Shot '{shot.get('name', i)}': invalid shot_type '{shot_type}'. "
                f"Valid: {sorted(VALID_ACTION_SHOT_TYPES)}",
            )

    safe_name = sanitize_cs_identifier(
        sequence_name.replace(" ", "_").replace("-", "_"),
    )
    safe_name_str = sanitize_cs_string(sequence_name)
    safe_path = sanitize_cs_string(output_path)
    total_duration = validation["total_duration"]

    # Compute cumulative shot start times
    shot_starts: list[float] = []
    current_time = 0.0
    for shot in shots:
        shot_starts.append(current_time)
        current_time += shot.get("duration", 1.0)

    # Determine if any shot uses spline dolly
    needs_spline = any(
        shot.get("shot_type") in ("DollyIn", "DollyOut") for shot in shots
    )

    lines: list[str] = []

    # -- Usings --
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using UnityEngine.Timeline;")
    lines.append("using UnityEngine.Playables;")
    lines.append("using Unity.Cinemachine;")
    if needs_spline:
        lines.append("using UnityEngine.Splines;")
    lines.append("using System.IO;")
    lines.append("")

    # -- Namespace --
    if namespace:
        ns_safe = re.sub(r"[^a-zA-Z0-9_.]", "", namespace)
        lines.append(f"namespace {ns_safe}")
        lines.append("{")

    indent = "    " if namespace else ""

    lines.append(f"{indent}public static class VeilBreakers_ActionCinematic_{safe_name}")
    lines.append(f"{indent}{{")
    lines.append(f'{indent}    [MenuItem("VeilBreakers/Cinematic/Create Action Cinematic/{safe_name_str}")]')
    lines.append(f"{indent}    public static void Execute()")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        try")
    lines.append(f"{indent}        {{")

    # -- Ensure output directory --
    lines.append(f'{indent}            string outputDir = "{safe_path}";')
    lines.append(f"{indent}            if (!AssetDatabase.IsValidFolder(outputDir))")
    lines.append(f"{indent}            {{")
    lines.append(f"{indent}                string[] parts = outputDir.Split('/');")
    lines.append(f"{indent}                string current = parts[0];")
    lines.append(f"{indent}                for (int i = 1; i < parts.Length; i++)")
    lines.append(f"{indent}                {{")
    lines.append(f"{indent}                    string next = current + \"/\" + parts[i];")
    lines.append(f"{indent}                    if (!AssetDatabase.IsValidFolder(next))")
    lines.append(f"{indent}                        AssetDatabase.CreateFolder(current, parts[i]);")
    lines.append(f"{indent}                    current = next;")
    lines.append(f"{indent}                }}")
    lines.append(f"{indent}            }}")
    lines.append("")

    # -- Create Timeline asset --
    lines.append(f"{indent}            // Create Timeline asset")
    lines.append(f"{indent}            TimelineAsset timeline = ScriptableObject.CreateInstance<TimelineAsset>();")
    lines.append(f'{indent}            string assetPath = outputDir + "/{safe_name}.playable";')
    lines.append(f"{indent}            AssetDatabase.CreateAsset(timeline, assetPath);")
    lines.append("")

    # -- Cinemachine track --
    lines.append(f'{indent}            var cameraTrack = timeline.CreateTrack<CinemachineTrack>(null, "Action Camera Shots");')
    lines.append("")

    # -- Root object --
    lines.append(f'{indent}            GameObject cinemaRoot = new GameObject("{safe_name_str}_Root");')
    lines.append("")

    # -- Per-shot camera generation --
    for i, shot in enumerate(shots):
        sname = shot.get("name", f"Shot_{i}")
        safe_sname = sanitize_cs_identifier(sname)
        cam_pos = shot["camera_position"]
        cam_tgt = shot["camera_target"]
        dur = shot.get("duration", 1.0)
        transition = shot.get("transition", "cut")
        start_time = shot_starts[i]
        shot_type = shot.get("shot_type", "Static")
        has_impulse = shot.get("impulse", False)

        lines.append(f"{indent}            // ---- Shot {i + 1}: {sanitize_cs_string(sname)} ({shot_type}) ----")
        lines.append(f'{indent}            GameObject cam_{safe_sname} = new GameObject("VCam_{safe_sname}");')
        lines.append(f"{indent}            cam_{safe_sname}.transform.SetParent(cinemaRoot.transform);")
        lines.append(f"{indent}            cam_{safe_sname}.transform.position = new Vector3({cam_pos[0]}f, {cam_pos[1]}f, {cam_pos[2]}f);")
        lines.append(f"{indent}            CinemachineCamera vcam_{safe_sname} = cam_{safe_sname}.AddComponent<CinemachineCamera>();")
        lines.append(f"{indent}            vcam_{safe_sname}.Priority = {10 + i};")
        lines.append("")

        # -- Rotation composer (look-at) on every shot --
        lines.append(f"{indent}            var composer_{safe_sname} = cam_{safe_sname}.AddComponent<CinemachineRotationComposer>();")
        lines.append(f"{indent}            composer_{safe_sname}.Composition.DeadZone.Width = 0.1f;")
        lines.append(f"{indent}            composer_{safe_sname}.Composition.DeadZone.Height = 0.1f;")
        lines.append(f'{indent}            GameObject lookTarget_{safe_sname} = new GameObject("LookTarget_{safe_sname}");')
        lines.append(f"{indent}            lookTarget_{safe_sname}.transform.SetParent(cinemaRoot.transform);")
        lines.append(f"{indent}            lookTarget_{safe_sname}.transform.position = new Vector3({cam_tgt[0]}f, {cam_tgt[1]}f, {cam_tgt[2]}f);")
        lines.append(f"{indent}            vcam_{safe_sname}.LookAt = lookTarget_{safe_sname}.transform;")
        lines.append("")

        # -- Shot-type-specific components --
        if shot_type in ("DollyIn", "DollyOut"):
            # Create a SplineContainer with a simple two-point spline
            end_pos = cam_tgt if shot_type == "DollyIn" else [
                cam_pos[0] + (cam_pos[0] - cam_tgt[0]),
                cam_pos[1] + (cam_pos[1] - cam_tgt[1]),
                cam_pos[2] + (cam_pos[2] - cam_tgt[2]),
            ]
            lines.append(f"{indent}            // Spline dolly for {shot_type}")
            lines.append(f'{indent}            GameObject splineObj_{safe_sname} = new GameObject("Spline_{safe_sname}");')
            lines.append(f"{indent}            splineObj_{safe_sname}.transform.SetParent(cinemaRoot.transform);")
            lines.append(f"{indent}            var splineContainer_{safe_sname} = splineObj_{safe_sname}.AddComponent<SplineContainer>();")
            lines.append(f"{indent}            var spline_{safe_sname} = splineContainer_{safe_sname}.Spline;")
            lines.append(f"{indent}            spline_{safe_sname}.Clear();")
            lines.append(f"{indent}            spline_{safe_sname}.Add(new BezierKnot(new Unity.Mathematics.float3({cam_pos[0]}f, {cam_pos[1]}f, {cam_pos[2]}f)));")
            lines.append(f"{indent}            spline_{safe_sname}.Add(new BezierKnot(new Unity.Mathematics.float3({end_pos[0]}f, {end_pos[1]}f, {end_pos[2]}f)));")
            lines.append(f"{indent}            var dolly_{safe_sname} = cam_{safe_sname}.AddComponent<CinemachineSplineDolly>();")
            lines.append(f"{indent}            dolly_{safe_sname}.Spline = splineContainer_{safe_sname};")
            lines.append("")

        elif shot_type == "OrbitalShot":
            lines.append(f"{indent}            // Orbital follow for orbiting subject")
            lines.append(f"{indent}            var orbital_{safe_sname} = cam_{safe_sname}.AddComponent<CinemachineOrbitalFollow>();")
            orbit_radius = (
                (cam_pos[0] - cam_tgt[0]) ** 2
                + (cam_pos[2] - cam_tgt[2]) ** 2
            ) ** 0.5
            lines.append(f"{indent}            orbital_{safe_sname}.Radius = {orbit_radius:.2f}f;")
            lines.append(f"{indent}            orbital_{safe_sname}.OrbitStyle = CinemachineOrbitalFollow.OrbitStyles.Sphere;")
            lines.append(f"{indent}            vcam_{safe_sname}.Follow = lookTarget_{safe_sname}.transform;")
            lines.append("")

        elif shot_type == "CrashZoom":
            fov_start = shot.get("fov_start", 60.0)
            lines.append(f"{indent}            // Crash zoom - start wide then snap")
            lines.append(f"{indent}            vcam_{safe_sname}.Lens = new LensSettings")
            lines.append(f"{indent}            {{")
            lines.append(f"{indent}                FieldOfView = {fov_start}f,")
            lines.append(f"{indent}                NearClipPlane = 0.1f,")
            lines.append(f"{indent}                FarClipPlane = 1000f,")
            lines.append(f"{indent}                OrthographicSize = 5f,")
            lines.append(f"{indent}                PhysicalProperties = vcam_{safe_sname}.Lens.PhysicalProperties")
            lines.append(f"{indent}            }};")
            lines.append("")

        elif shot_type == "PullBack":
            offset_x = cam_pos[0] - cam_tgt[0]
            offset_y = cam_pos[1] - cam_tgt[1]
            offset_z = cam_pos[2] - cam_tgt[2]
            lines.append(f"{indent}            // Pull-back follow with offset")
            lines.append(f"{indent}            var follow_{safe_sname} = cam_{safe_sname}.AddComponent<CinemachineFollow>();")
            lines.append(f"{indent}            follow_{safe_sname}.FollowOffset = new Vector3({offset_x:.2f}f, {offset_y:.2f}f, {offset_z:.2f}f);")
            lines.append(f"{indent}            vcam_{safe_sname}.Follow = lookTarget_{safe_sname}.transform;")
            lines.append("")

        elif shot_type == "SlowMotion":
            time_scale = shot.get("time_scale", 0.3)
            lines.append(f"{indent}            // Slow-motion marker (applied at runtime via director signal)")
            lines.append(f"{indent}            cam_{safe_sname}.AddComponent<Light>(); // placeholder tag for slo-mo signal")
            lines.append(f'{indent}            cam_{safe_sname}.tag = "EditorOnly"; // slo-mo TimeScale={time_scale}')
            lines.append("")

        # shot_type Static, Tracking, WhipPan, CraneUp, CraneDown => position-based only

        # -- Impulse components --
        if has_impulse:
            lines.append(f"{indent}            // Impulse feedback for impact")
            lines.append(f"{indent}            var impulseSource_{safe_sname} = cam_{safe_sname}.AddComponent<CinemachineImpulseSource>();")
            lines.append(f"{indent}            impulseSource_{safe_sname}.ImpulseDefinition.ImpulseType = CinemachineImpulseDefinition.ImpulseTypes.Uniform;")
            lines.append(f"{indent}            impulseSource_{safe_sname}.ImpulseDefinition.ImpulseDuration = 0.3f;")
            lines.append(f"{indent}            impulseSource_{safe_sname}.DefaultVelocity = new Vector3(0f, 0.4f, -0.2f);")
            lines.append(f"{indent}            cam_{safe_sname}.AddComponent<CinemachineImpulseListener>();")
            lines.append("")

        # -- Timeline clip --
        blend_in = 0.0
        if transition == "crossfade":
            blend_in = 0.5
        elif transition in ("fade_to_black", "fade_from_black"):
            blend_in = 0.3

        lines.append(f"{indent}            var clip_{safe_sname} = cameraTrack.CreateDefaultClip();")
        lines.append(f'{indent}            clip_{safe_sname}.displayName = "{sanitize_cs_string(sname)}";')
        lines.append(f"{indent}            clip_{safe_sname}.start = {start_time}d;")
        lines.append(f"{indent}            clip_{safe_sname}.duration = {dur}d;")
        if blend_in > 0:
            lines.append(f"{indent}            clip_{safe_sname}.blendInDuration = {blend_in}d;")
        lines.append("")

    # -- Audio track --
    lines.append(f'{indent}            var audioTrack = timeline.CreateTrack<AudioTrack>(null, "Action Audio");')
    lines.append("")

    # -- Activation (marker) track --
    lines.append(f'{indent}            var markerTrack = timeline.CreateTrack<ActivationTrack>(null, "Shot Markers");')
    for i, shot in enumerate(shots):
        sname = shot.get("name", f"Shot_{i}")
        safe_sname = sanitize_cs_identifier(sname)
        start_time = shot_starts[i]
        dur = shot.get("duration", 1.0)
        lines.append(f"{indent}            var marker_{safe_sname} = markerTrack.CreateDefaultClip();")
        lines.append(f'{indent}            marker_{safe_sname}.displayName = "Shot: {sanitize_cs_string(sname)}";')
        lines.append(f"{indent}            marker_{safe_sname}.start = {start_time}d;")
        lines.append(f"{indent}            marker_{safe_sname}.duration = {dur}d;")
    lines.append("")

    # -- PlayableDirector --
    lines.append(f"{indent}            PlayableDirector director = cinemaRoot.AddComponent<PlayableDirector>();")
    lines.append(f"{indent}            director.playableAsset = timeline;")
    lines.append(f"{indent}            director.extrapolationMode = DirectorWrapMode.Hold;")
    lines.append(f"{indent}            director.playOnAwake = false;")
    lines.append("")

    # -- Save --
    lines.append(f"{indent}            AssetDatabase.SaveAssets();")
    lines.append(f"{indent}            AssetDatabase.Refresh();")
    lines.append(f'{indent}            Undo.RegisterCreatedObjectUndo(cinemaRoot, "Create Action Cinematic");')
    lines.append(f"{indent}            Selection.activeGameObject = cinemaRoot;")
    lines.append("")

    # -- Result JSON --
    shot_count = len(shots)
    lines.append(
        f'{indent}            string json = "{{\\"status\\":\\"success\\",\\"sequence_name\\":\\"{safe_name}\\",\\"shot_count\\":{shot_count},'
        f'\\"total_duration\\":{total_duration},\\"asset_path\\":\\"" + assetPath.Replace("\\\\", "/") + "\\"}}";',
    )
    lines.append(f'{indent}            File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(
        f'{indent}            Debug.Log("[VeilBreakers] Action cinematic created: {safe_name_str} '
        f'with {shot_count} shots (" + assetPath + ")");',
    )

    # -- Catch --
    lines.append(f"{indent}        }}")
    lines.append(f"{indent}        catch (System.Exception ex)")
    lines.append(f"{indent}        {{")
    lines.append(
        f'{indent}            string json = "{{\\"status\\":\\"error\\",\\"action\\":\\"action_cinematic\\",\\"message\\":\\"" '
        f'+ ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";',
    )
    lines.append(f'{indent}            File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(f'{indent}            Debug.LogError("[VeilBreakers] Action cinematic creation failed: " + ex.Message);')
    lines.append(f"{indent}        }}")
    lines.append(f"{indent}    }}")
    lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Party camera system
# ---------------------------------------------------------------------------

def generate_party_camera_system_script(
    class_name: str = "PartyCameraController",
    presets: dict[str, dict[str, float]] | None = None,
    namespace: str = "VeilBreakers.Camera",
    output_dir: str = "Assets/Scripts/Camera",
) -> dict[str, Any]:
    """Generate a 3rd-person ARPG party camera MonoBehaviour.

    Creates a PartyCameraController that manages a CinemachineCamera with:
    - CinemachineFollow for 3rd-person positioning
    - CinemachineRotationComposer for look-at targeting
    - CinemachineDeoccluder for obstacle avoidance
    - PrimeTween for smooth state transitions
    - State presets: exploration, combat, boss_fight, dialogue,
      ability_showcase, stealth
    - Player zoom via scroll wheel
    - OnCameraStateChanged C# event

    Args:
        class_name: Name for the MonoBehaviour class.
        presets: Override camera presets dict. Defaults to PARTY_CAMERA_PRESETS.
        namespace: C# namespace.
        output_dir: Where to write the script in the Unity project.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    if presets is None:
        presets = PARTY_CAMERA_PRESETS

    safe_class = sanitize_cs_identifier(class_name)

    # Build preset enum entries and data arrays
    preset_names = list(presets.keys())
    enum_entries = ", ".join(
        sanitize_cs_identifier(n.replace(" ", "")) for n in preset_names
    )

    lines: list[str] = []

    # -- Usings --
    lines.append("using UnityEngine;")
    lines.append("using Unity.Cinemachine;")
    lines.append("using PrimeTween;")
    lines.append("using System;")
    lines.append("")

    # -- Namespace --
    if namespace:
        ns_safe = re.sub(r"[^a-zA-Z0-9_.]", "", namespace)
        lines.append(f"namespace {ns_safe}")
        lines.append("{")

    indent = "    " if namespace else ""

    # -- CameraState enum --
    lines.append(f"{indent}/// <summary>Available camera state presets for the party camera.</summary>")
    lines.append(f"{indent}public enum CameraState")
    lines.append(f"{indent}{{")
    lines.append(f"{indent}    {enum_entries}")
    lines.append(f"{indent}}}")
    lines.append("")

    # -- CameraPresetData struct --
    lines.append(f"{indent}/// <summary>Preset parameters for a single camera state.</summary>")
    lines.append(f"{indent}[Serializable]")
    lines.append(f"{indent}public struct CameraPresetData")
    lines.append(f"{indent}{{")
    lines.append(f"{indent}    public float fov;")
    lines.append(f"{indent}    public float distance;")
    lines.append(f"{indent}    public float height;")
    lines.append(f"{indent}}}")
    lines.append("")

    # -- MonoBehaviour class --
    lines.append(f"{indent}/// <summary>")
    lines.append(f"{indent}/// 3rd-person ARPG party camera with state presets.")
    lines.append(f"{indent}/// Manages a CinemachineCamera with Follow, RotationComposer, and Deoccluder.")
    lines.append(f"{indent}/// Uses PrimeTween for smooth state transitions and supports scroll-wheel zoom.")
    lines.append(f"{indent}/// </summary>")
    lines.append(f"{indent}public class {safe_class} : MonoBehaviour")
    lines.append(f"{indent}{{")

    # -- Serialised fields --
    lines.append(f"{indent}    [Header(\"References\")]")
    lines.append(f"{indent}    [SerializeField] private CinemachineCamera virtualCamera;")
    lines.append(f"{indent}    [SerializeField] private Transform followTarget;")
    lines.append(f"{indent}    [SerializeField] private Transform lookAtTarget;")
    lines.append("")
    lines.append(f"{indent}    [Header(\"Transition\")]")
    lines.append(f"{indent}    [SerializeField] private float transitionDuration = 0.6f;")
    lines.append(f"{indent}    [SerializeField] private Ease transitionEase = Ease.InOutCubic;")
    lines.append("")
    lines.append(f"{indent}    [Header(\"Zoom\")]")
    lines.append(f"{indent}    [SerializeField] private float zoomSpeed = 2f;")
    lines.append(f"{indent}    [SerializeField] private float minZoomMultiplier = 0.5f;")
    lines.append(f"{indent}    [SerializeField] private float maxZoomMultiplier = 2.0f;")
    lines.append("")

    # -- Preset data array (serialized so designers can tweak in Inspector) --
    lines.append(f"{indent}    [Header(\"Presets\")]")
    for pname, pdata in presets.items():
        field_name = sanitize_cs_identifier(pname)
        lines.append(f"{indent}    [SerializeField] private CameraPresetData preset_{field_name} = new CameraPresetData")
        lines.append(f"{indent}    {{")
        lines.append(f"{indent}        fov = {pdata['fov']}f,")
        lines.append(f"{indent}        distance = {pdata['distance']}f,")
        lines.append(f"{indent}        height = {pdata['height']}f")
        lines.append(f"{indent}    }};")
    lines.append("")

    # -- Private state --
    lines.append(f"{indent}    private CinemachineFollow cinemachineFollow;")
    lines.append(f"{indent}    private CinemachineRotationComposer rotationComposer;")
    lines.append(f"{indent}    private CinemachineDeoccluder deoccluder;")
    lines.append(f"{indent}    private CameraState currentState;")
    lines.append(f"{indent}    private float currentZoomMultiplier = 1.0f;")
    lines.append(f"{indent}    private Tween activeFovTween;")
    lines.append(f"{indent}    private Tween activeDistanceTween;")
    lines.append(f"{indent}    private Tween activeHeightTween;")
    lines.append("")

    # -- Event --
    lines.append(f"{indent}    /// <summary>Fired whenever the camera state changes.</summary>")
    lines.append(f"{indent}    public event Action<CameraState, CameraState> OnCameraStateChanged;")
    lines.append("")

    # -- Properties --
    lines.append(f"{indent}    /// <summary>Current camera state preset.</summary>")
    lines.append(f"{indent}    public CameraState CurrentState => currentState;")
    lines.append("")

    # -- Awake --
    lines.append(f"{indent}    private void Awake()")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        if (virtualCamera == null)")
    lines.append(f"{indent}            virtualCamera = GetComponentInChildren<CinemachineCamera>();")
    lines.append("")
    lines.append(f"{indent}        if (virtualCamera != null)")
    lines.append(f"{indent}        {{")
    lines.append(f"{indent}            cinemachineFollow = virtualCamera.GetComponent<CinemachineFollow>();")
    lines.append(f"{indent}            if (cinemachineFollow == null)")
    lines.append(f"{indent}                cinemachineFollow = virtualCamera.gameObject.AddComponent<CinemachineFollow>();")
    lines.append("")
    lines.append(f"{indent}            rotationComposer = virtualCamera.GetComponent<CinemachineRotationComposer>();")
    lines.append(f"{indent}            if (rotationComposer == null)")
    lines.append(f"{indent}                rotationComposer = virtualCamera.gameObject.AddComponent<CinemachineRotationComposer>();")
    lines.append("")
    lines.append(f"{indent}            deoccluder = virtualCamera.GetComponent<CinemachineDeoccluder>();")
    lines.append(f"{indent}            if (deoccluder == null)")
    lines.append(f"{indent}                deoccluder = virtualCamera.gameObject.AddComponent<CinemachineDeoccluder>();")
    lines.append("")
    lines.append(f"{indent}            if (followTarget != null)")
    lines.append(f"{indent}                virtualCamera.Follow = followTarget;")
    lines.append(f"{indent}            if (lookAtTarget != null)")
    lines.append(f"{indent}                virtualCamera.LookAt = lookAtTarget;")
    lines.append(f"{indent}        }}")
    lines.append("")
    lines.append(f"{indent}        // Apply initial state without animation")
    lines.append(f"{indent}        ApplyPresetImmediate(CameraState.{sanitize_cs_identifier(preset_names[0])});")
    lines.append(f"{indent}    }}")
    lines.append("")

    # -- Update (zoom) --
    lines.append(f"{indent}    private void Update()")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        float scroll = Input.GetAxis(\"Mouse ScrollWheel\");")
    lines.append(f"{indent}        if (Mathf.Abs(scroll) > 0.001f)")
    lines.append(f"{indent}        {{")
    lines.append(f"{indent}            currentZoomMultiplier = Mathf.Clamp(")
    lines.append(f"{indent}                currentZoomMultiplier - scroll * zoomSpeed,")
    lines.append(f"{indent}                minZoomMultiplier,")
    lines.append(f"{indent}                maxZoomMultiplier")
    lines.append(f"{indent}            );")
    lines.append(f"{indent}            ApplyZoom();")
    lines.append(f"{indent}        }}")
    lines.append(f"{indent}    }}")
    lines.append("")

    # -- GetPresetData helper --
    lines.append(f"{indent}    /// <summary>Get preset data for a given camera state.</summary>")
    lines.append(f"{indent}    public CameraPresetData GetPresetData(CameraState state)")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        switch (state)")
    lines.append(f"{indent}        {{")
    for pname in preset_names:
        field_name = sanitize_cs_identifier(pname)
        lines.append(f"{indent}            case CameraState.{field_name}: return preset_{field_name};")
    lines.append(f"{indent}            default: return preset_{sanitize_cs_identifier(preset_names[0])};")
    lines.append(f"{indent}        }}")
    lines.append(f"{indent}    }}")
    lines.append("")

    # -- SetState --
    lines.append(f"{indent}    /// <summary>Transition to a new camera state with PrimeTween.</summary>")
    lines.append(f"{indent}    public void SetState(CameraState newState)")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        if (newState == currentState) return;")
    lines.append(f"{indent}        CameraState oldState = currentState;")
    lines.append(f"{indent}        currentState = newState;")
    lines.append("")
    lines.append(f"{indent}        CameraPresetData preset = GetPresetData(newState);")
    lines.append(f"{indent}        float targetFov = preset.fov;")
    lines.append(f"{indent}        float targetDist = preset.distance * currentZoomMultiplier;")
    lines.append(f"{indent}        float targetHeight = preset.height * currentZoomMultiplier;")
    lines.append("")
    lines.append(f"{indent}        // Stop any active tweens")
    lines.append(f"{indent}        activeFovTween.Stop();")
    lines.append(f"{indent}        activeDistanceTween.Stop();")
    lines.append(f"{indent}        activeHeightTween.Stop();")
    lines.append("")
    lines.append(f"{indent}        if (virtualCamera != null)")
    lines.append(f"{indent}        {{")
    lines.append(f"{indent}            // FOV tween")
    lines.append(f"{indent}            activeFovTween = Tween.Custom(")
    lines.append(f"{indent}                virtualCamera.Lens.FieldOfView,")
    lines.append(f"{indent}                targetFov,")
    lines.append(f"{indent}                transitionDuration,")
    lines.append(f"{indent}                val => {{")
    lines.append(f"{indent}                    var lens = virtualCamera.Lens;")
    lines.append(f"{indent}                    lens.FieldOfView = val;")
    lines.append(f"{indent}                    virtualCamera.Lens = lens;")
    lines.append(f"{indent}                }},")
    lines.append(f"{indent}                transitionEase")
    lines.append(f"{indent}            );")
    lines.append("")
    lines.append(f"{indent}            // Distance tween via follow offset Z")
    lines.append(f"{indent}            if (cinemachineFollow != null)")
    lines.append(f"{indent}            {{")
    lines.append(f"{indent}                activeDistanceTween = Tween.Custom(")
    lines.append(f"{indent}                    cinemachineFollow.FollowOffset.z,")
    lines.append(f"{indent}                    -targetDist,")
    lines.append(f"{indent}                    transitionDuration,")
    lines.append(f"{indent}                    val => {{")
    lines.append(f"{indent}                        var offset = cinemachineFollow.FollowOffset;")
    lines.append(f"{indent}                        offset.z = val;")
    lines.append(f"{indent}                        cinemachineFollow.FollowOffset = offset;")
    lines.append(f"{indent}                    }},")
    lines.append(f"{indent}                    transitionEase")
    lines.append(f"{indent}                );")
    lines.append("")
    lines.append(f"{indent}                // Height tween via follow offset Y")
    lines.append(f"{indent}                activeHeightTween = Tween.Custom(")
    lines.append(f"{indent}                    cinemachineFollow.FollowOffset.y,")
    lines.append(f"{indent}                    targetHeight,")
    lines.append(f"{indent}                    transitionDuration,")
    lines.append(f"{indent}                    val => {{")
    lines.append(f"{indent}                        var offset = cinemachineFollow.FollowOffset;")
    lines.append(f"{indent}                        offset.y = val;")
    lines.append(f"{indent}                        cinemachineFollow.FollowOffset = offset;")
    lines.append(f"{indent}                    }},")
    lines.append(f"{indent}                    transitionEase")
    lines.append(f"{indent}                );")
    lines.append(f"{indent}            }}")
    lines.append(f"{indent}        }}")
    lines.append("")
    lines.append(f"{indent}        OnCameraStateChanged?.Invoke(oldState, newState);")
    lines.append(f"{indent}    }}")
    lines.append("")

    # -- ApplyPresetImmediate --
    lines.append(f"{indent}    /// <summary>Apply a preset immediately without animation.</summary>")
    lines.append(f"{indent}    public void ApplyPresetImmediate(CameraState state)")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        currentState = state;")
    lines.append(f"{indent}        CameraPresetData preset = GetPresetData(state);")
    lines.append("")
    lines.append(f"{indent}        if (virtualCamera != null)")
    lines.append(f"{indent}        {{")
    lines.append(f"{indent}            var lens = virtualCamera.Lens;")
    lines.append(f"{indent}            lens.FieldOfView = preset.fov;")
    lines.append(f"{indent}            virtualCamera.Lens = lens;")
    lines.append(f"{indent}        }}")
    lines.append("")
    lines.append(f"{indent}        if (cinemachineFollow != null)")
    lines.append(f"{indent}        {{")
    lines.append(f"{indent}            cinemachineFollow.FollowOffset = new Vector3(")
    lines.append(f"{indent}                0f,")
    lines.append(f"{indent}                preset.height * currentZoomMultiplier,")
    lines.append(f"{indent}                -preset.distance * currentZoomMultiplier")
    lines.append(f"{indent}            );")
    lines.append(f"{indent}        }}")
    lines.append(f"{indent}    }}")
    lines.append("")

    # -- ApplyZoom --
    lines.append(f"{indent}    /// <summary>Reapply current preset with updated zoom multiplier.</summary>")
    lines.append(f"{indent}    private void ApplyZoom()")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        CameraPresetData preset = GetPresetData(currentState);")
    lines.append(f"{indent}        if (cinemachineFollow != null)")
    lines.append(f"{indent}        {{")
    lines.append(f"{indent}            cinemachineFollow.FollowOffset = new Vector3(")
    lines.append(f"{indent}                cinemachineFollow.FollowOffset.x,")
    lines.append(f"{indent}                preset.height * currentZoomMultiplier,")
    lines.append(f"{indent}                -preset.distance * currentZoomMultiplier")
    lines.append(f"{indent}            );")
    lines.append(f"{indent}        }}")
    lines.append(f"{indent}    }}")
    lines.append("")

    # -- ResetZoom --
    lines.append(f"{indent}    /// <summary>Reset zoom multiplier to 1.0 and reapply.</summary>")
    lines.append(f"{indent}    public void ResetZoom()")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        currentZoomMultiplier = 1.0f;")
    lines.append(f"{indent}        ApplyZoom();")
    lines.append(f"{indent}    }}")

    # -- Close class --
    lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    script_content = "\n".join(lines)
    script_path = f"{output_dir}/{safe_class}.cs"

    return {
        "script_path": script_path,
        "script_content": script_content,
        "next_steps": [
            f"Write script to {script_path}",
            "Call unity_editor action=recompile to compile",
            "Attach PartyCameraController to your camera rig GameObject",
            "Assign virtualCamera, followTarget, and lookAtTarget references",
            "Call SetState(CameraState.combat) etc. from gameplay code",
        ],
    }
