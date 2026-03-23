"""Camera, cinematics, and animation editing C# template generators for Unity.

Each function returns a complete C# source string that can be written to
a Unity project's Assets/Editor/Generated/Camera/ directory. When compiled
by Unity, the scripts register as MenuItem commands under
"VeilBreakers/Camera/...".

All generated scripts write their result to Temp/vb_result.json so that
the Python MCP server can read back the outcome after execution.

Exports:
    generate_cinemachine_setup_script         -- CAM-01: Virtual camera (orbital/follow/dolly)
    generate_state_driven_camera_script       -- CAM-01: State-driven camera with Animator binding
    generate_camera_shake_script              -- CAM-04: Impulse source + listener
    generate_camera_blend_script              -- CAM-04: CinemachineBrain blend configuration
    generate_timeline_setup_script            -- CAM-02: TimelineAsset with tracks
    generate_cutscene_setup_script            -- CAM-03: PlayableDirector + Timeline binding
    generate_animation_clip_editor_script     -- ANIMA-01: EditorCurveBinding + AnimationUtility
    generate_animator_modifier_script         -- ANIMA-02: AnimatorController states/transitions
    generate_avatar_mask_script               -- ANIMA-03: AvatarMask body part filtering
    generate_video_player_script              -- MEDIA-01: VideoPlayer + RenderTexture
"""

from __future__ import annotations

import re
from typing import Optional

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier


# ---------------------------------------------------------------------------
# C# reserved words (needed for _safe_namespace)
# ---------------------------------------------------------------------------

_CS_RESERVED = frozenset({
    "abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char",
    "checked", "class", "const", "continue", "decimal", "default", "delegate",
    "do", "double", "else", "enum", "event", "explicit", "extern", "false",
    "finally", "fixed", "float", "for", "foreach", "goto", "if", "implicit",
    "in", "int", "interface", "internal", "is", "lock", "long", "namespace",
    "new", "null", "object", "operator", "out", "override", "params", "private",
    "protected", "public", "readonly", "ref", "return", "sbyte", "sealed",
    "short", "sizeof", "stackalloc", "static", "string", "struct", "switch",
    "this", "throw", "true", "try", "typeof", "uint", "ulong", "unchecked",
    "unsafe", "ushort", "using", "virtual", "void", "volatile", "while",
})


def _safe_namespace(ns: str) -> str:
    """Sanitize a C# namespace to prevent code injection."""
    sanitized = re.sub(r"[^a-zA-Z0-9_.]", "", ns)
    sanitized = re.sub(r"\.{2,}", ".", sanitized).strip(".")
    if not sanitized:
        return "Generated"
    segments = sanitized.split(".")
    fixed: list[str] = []
    for seg in segments:
        if not seg:
            continue
        if seg[0].isdigit():
            seg = f"_{seg}"
        if seg in _CS_RESERVED:
            seg = f"@{seg}"
        fixed.append(seg)
    return ".".join(fixed) or "Generated"


__all__ = [
    "generate_cinemachine_setup_script",
    "generate_state_driven_camera_script",
    "generate_camera_shake_script",
    "generate_camera_blend_script",
    "generate_timeline_setup_script",
    "generate_cutscene_setup_script",
    "generate_animation_clip_editor_script",
    "generate_animator_modifier_script",
    "generate_avatar_mask_script",
    "generate_video_player_script",
    "generate_lock_on_camera_script",
]


# ---------------------------------------------------------------------------
# CAM-01: Cinemachine virtual camera setup (3.x API)
# ---------------------------------------------------------------------------


def generate_cinemachine_setup_script(
    camera_type: str = "orbital",
    follow_target: str = "",
    look_at_target: str = "",
    priority: int = 10,
    radius: float = 5.0,
    target_offset: Optional[list[float]] = None,
    damping: Optional[list[float]] = None,
    namespace: str = "VeilBreakers.CameraSystems",
) -> str:
    """Generate C# editor script for Cinemachine 3.x camera setup.

    Creates a CinemachineCamera with OrbitalFollow and RotationComposer
    components using the Unity.Cinemachine namespace (3.x API).
    """
    if target_offset is None:
        target_offset = [0.0, 1.5, 0.0]
    if damping is None:
        damping = [1.0, 0.5, 0.0]

    safe_cam_type = sanitize_cs_identifier(camera_type)
    safe_follow = sanitize_cs_string(follow_target)
    safe_look = sanitize_cs_string(look_at_target)
    safe_ns = sanitize_cs_identifier(namespace.replace(".", ""))

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using Unity.Cinemachine;")
    lines.append("using System.IO;")
    lines.append("")

    if namespace:
        lines.append(f"namespace {_safe_namespace(namespace)}")
        lines.append("{")

    indent = "    " if namespace else ""
    lines.append(f"{indent}public static class VeilBreakers_CinemachineSetup")
    lines.append(f"{indent}{{")
    lines.append(f'{indent}    [MenuItem("VeilBreakers/Camera/Setup Virtual Camera")]')
    lines.append(f"{indent}    public static void Execute()")
    lines.append(f"{indent}    {{")

    # Create camera GameObject
    lines.append(f'{indent}        GameObject camGo = new GameObject("VB_CinemachineCamera_{safe_cam_type}");')
    lines.append(f"{indent}        CinemachineCamera cm = camGo.AddComponent<CinemachineCamera>();")
    lines.append(f"{indent}        cm.Priority.Value = {priority};")
    lines.append("")

    # Follow / LookAt targets
    if follow_target:
        lines.append(f'{indent}        GameObject followObj = GameObject.Find("{safe_follow}");')
        lines.append(f"{indent}        if (followObj != null) cm.Follow = followObj.transform;")
    if look_at_target:
        lines.append(f'{indent}        GameObject lookObj = GameObject.Find("{safe_look}");')
        lines.append(f"{indent}        if (lookObj != null) cm.LookAt = lookObj.transform;")
    lines.append("")

    # Camera type specific components
    if camera_type == "orbital":
        lines.append(f"{indent}        // OrbitalFollow for third-person orbit")
        lines.append(f"{indent}        CinemachineOrbitalFollow orbital = camGo.AddComponent<CinemachineOrbitalFollow>();")
        lines.append(f"{indent}        orbital.Radius = {radius}f;")
        lines.append(f"{indent}        orbital.OrbitOffset = new Vector3({target_offset[0]}f, {target_offset[1]}f, {target_offset[2]}f);")
        lines.append("")
        lines.append(f"{indent}        // RotationComposer for look-at tracking")
        lines.append(f"{indent}        CinemachineRotationComposer composer = camGo.AddComponent<CinemachineRotationComposer>();")
        lines.append(f"{indent}        composer.Damping = new Vector2({damping[0]}f, {damping[1]}f);")
        lines.append(f"{indent}        composer.Composition.DeadZone.Width = 0.1f;")
        lines.append(f"{indent}        composer.Composition.DeadZone.Height = 0.08f;")
        lines.append(f"{indent}        composer.Composition.SoftZone.Width = 0.8f;")
        lines.append(f"{indent}        composer.Composition.SoftZone.Height = 0.8f;")
    elif camera_type == "follow":
        lines.append(f"{indent}        // Follow for follow camera")
        lines.append(f"{indent}        CinemachineFollow follow = camGo.AddComponent<CinemachineFollow>();")
        lines.append(f"{indent}        follow.FollowOffset = new Vector3({target_offset[0]}f, {target_offset[1]}f, -{radius}f);")
        lines.append(f"{indent}        follow.TrackerSettings.PositionDamping = new Vector3({damping[0]}f, {damping[1]}f, {damping[2]}f);")
        lines.append("")
        lines.append(f"{indent}        // RotationComposer for look-at tracking")
        lines.append(f"{indent}        CinemachineRotationComposer composer = camGo.AddComponent<CinemachineRotationComposer>();")
        lines.append(f"{indent}        composer.Damping = new Vector2({damping[0]}f, {damping[1]}f);")
        lines.append(f"{indent}        composer.Composition.DeadZone.Width = 0.1f;")
        lines.append(f"{indent}        composer.Composition.DeadZone.Height = 0.08f;")
        lines.append(f"{indent}        composer.Composition.SoftZone.Width = 0.8f;")
        lines.append(f"{indent}        composer.Composition.SoftZone.Height = 0.8f;")
    elif camera_type == "dolly":
        lines.append(f"{indent}        // SplineDolly for dolly camera")
        lines.append(f"{indent}        CinemachineSplineDolly dolly = camGo.AddComponent<CinemachineSplineDolly>();")
        lines.append(f"{indent}        dolly.Damping.Value = {damping[0]}f;")
        lines.append("")
        lines.append(f"{indent}        // RotationComposer for look-at tracking")
        lines.append(f"{indent}        CinemachineRotationComposer composer = camGo.AddComponent<CinemachineRotationComposer>();")
        lines.append(f"{indent}        composer.Damping = new Vector3({damping[0]}f, {damping[1]}f, {damping[2]}f);")
        lines.append(f"{indent}        composer.Composition.DeadZone.Width = 0.1f;")
        lines.append(f"{indent}        composer.Composition.DeadZone.Height = 0.08f;")
        lines.append(f"{indent}        composer.Composition.SoftZone.Width = 0.8f;")
        lines.append(f"{indent}        composer.Composition.SoftZone.Height = 0.8f;")
    lines.append("")

    lines.append(f"{indent}        Undo.RegisterCreatedObjectUndo(camGo, \"Create Cinemachine Camera\");")
    lines.append(f"{indent}        Selection.activeGameObject = camGo;")
    lines.append("")

    # Result JSON
    lines.append(f"{indent}        // Write result")
    lines.append(f'{indent}        string json = "{{\\"status\\":\\"success\\",\\"camera_type\\":\\"{safe_cam_type}\\",\\"priority\\":{priority}}}";')
    lines.append(f'{indent}        File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(f'{indent}        Debug.Log("[VeilBreakers] Cinemachine camera created: VB_CinemachineCamera_{safe_cam_type}");')

    lines.append(f"{indent}    }}")
    lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CAM-01: State-driven camera
# ---------------------------------------------------------------------------


def generate_state_driven_camera_script(
    camera_name: str = "VB_StateDrivenCamera",
    states: Optional[list[dict]] = None,
    namespace: str = "VeilBreakers.CameraSystems",
) -> str:
    """Generate C# editor script for CinemachineStateDrivenCamera.

    Creates a CinemachineStateDrivenCamera with Animator binding and
    instructions for child camera creation per state.
    """
    if states is None:
        states = [
            {"state_name": "Idle", "camera_name": "IdleCamera"},
            {"state_name": "Combat", "camera_name": "CombatCamera"},
        ]

    safe_name = sanitize_cs_identifier(camera_name)

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using Unity.Cinemachine;")
    lines.append("using System.IO;")
    lines.append("")

    if namespace:
        lines.append(f"namespace {_safe_namespace(namespace)}")
        lines.append("{")

    indent = "    " if namespace else ""
    lines.append(f"{indent}public static class VeilBreakers_StateDrivenCamera")
    lines.append(f"{indent}{{")
    lines.append(f'{indent}    [MenuItem("VeilBreakers/Camera/Setup State-Driven Camera")]')
    lines.append(f"{indent}    public static void Execute()")
    lines.append(f"{indent}    {{")

    lines.append(f'{indent}        GameObject sdGo = new GameObject("{sanitize_cs_string(camera_name)}");')
    lines.append(f"{indent}        CinemachineStateDrivenCamera sdc = sdGo.AddComponent<CinemachineStateDrivenCamera>();")
    lines.append("")

    lines.append(f"{indent}        // Assign Animator for state detection")
    lines.append(f"{indent}        // Find target Animator in scene")
    lines.append(f"{indent}        Animator animator = Object.FindFirstObjectByType<Animator>();")
    lines.append(f"{indent}        if (animator != null)")
    lines.append(f"{indent}        {{")
    lines.append(f"{indent}            sdc.AnimatedTarget = animator;")
    lines.append(f"{indent}        }}")
    lines.append("")

    # Create child cameras for each state
    lines.append(f"{indent}        // Create child cameras for each state")
    for state_info in states:
        s_name = sanitize_cs_string(state_info.get("state_name", "Default"))
        c_name = sanitize_cs_string(state_info.get("camera_name", "Camera"))
        lines.append(f'{indent}        GameObject child_{sanitize_cs_identifier(s_name)} = new GameObject("{c_name}");')
        lines.append(f"{indent}        child_{sanitize_cs_identifier(s_name)}.transform.SetParent(sdGo.transform);")
        lines.append(f"{indent}        CinemachineCamera cm_{sanitize_cs_identifier(s_name)} = child_{sanitize_cs_identifier(s_name)}.AddComponent<CinemachineCamera>();")
    lines.append("")

    # Populate Instructions array to map animation states to child cameras
    lines.append(f"{indent}        // Map animation states to child cameras via Instructions")
    lines.append(f"{indent}        var instructions = new System.Collections.Generic.List<CinemachineStateDrivenCamera.Instruction>();")
    for state_info in states:
        s_name = sanitize_cs_string(state_info.get("state_name", "Default"))
        lines.append(f"{indent}        instructions.Add(new CinemachineStateDrivenCamera.Instruction")
        lines.append(f"{indent}        {{")
        lines.append(f'{indent}            FullHash = Animator.StringToHash("{s_name}"),')
        lines.append(f"{indent}            Camera = cm_{sanitize_cs_identifier(s_name)}")
        lines.append(f"{indent}        }});")
    lines.append(f"{indent}        sdc.Instructions = instructions.ToArray();")
    lines.append("")

    lines.append(f"{indent}        Undo.RegisterCreatedObjectUndo(sdGo, \"Create State-Driven Camera\");")
    lines.append(f"{indent}        Selection.activeGameObject = sdGo;")
    lines.append("")

    lines.append(f"{indent}        // Write result")
    lines.append(f'{indent}        string json = "{{\\"status\\":\\"success\\",\\"camera_name\\":\\"{sanitize_cs_string(camera_name)}\\",\\"state_count\\":{len(states)}}}";')
    lines.append(f'{indent}        File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(f'{indent}        Debug.Log("[VeilBreakers] State-driven camera created with {len(states)} states");')

    lines.append(f"{indent}    }}")
    lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CAM-04: Camera shake (impulse)
# ---------------------------------------------------------------------------


def generate_camera_shake_script(
    impulse_force: float = 0.5,
    impulse_duration: float = 0.2,
    add_listener: bool = True,
    namespace: str = "VeilBreakers.CameraSystems",
) -> str:
    """Generate C# editor script for CinemachineImpulseSource setup.

    Creates a CinemachineImpulseSource on the selected object and optionally
    adds a CinemachineImpulseListener to the main camera.
    """
    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using Unity.Cinemachine;")
    lines.append("using System.IO;")
    lines.append("")

    if namespace:
        lines.append(f"namespace {_safe_namespace(namespace)}")
        lines.append("{")

    indent = "    " if namespace else ""
    lines.append(f"{indent}public static class VeilBreakers_CameraShake")
    lines.append(f"{indent}{{")
    lines.append(f'{indent}    [MenuItem("VeilBreakers/Camera/Setup Camera Shake")]')
    lines.append(f"{indent}    public static void Execute()")
    lines.append(f"{indent}    {{")

    lines.append(f"{indent}        // Create impulse source")
    lines.append(f'{indent}        GameObject impulseGo = Selection.activeGameObject ?? new GameObject("VB_ImpulseSource");')
    lines.append(f"{indent}        CinemachineImpulseSource impulse = impulseGo.GetComponent<CinemachineImpulseSource>();")
    lines.append(f"{indent}        if (impulse == null)")
    lines.append(f"{indent}            impulse = impulseGo.AddComponent<CinemachineImpulseSource>();")
    lines.append("")
    lines.append(f"{indent}        // Configure impulse force and duration")
    lines.append(f"{indent}        impulse.DefaultVelocity = new Vector3(0f, {impulse_force}f, 0f);")
    lines.append(f"{indent}        impulse.ImpulseDefinition.ImpulseDuration = {impulse_duration}f;")
    lines.append("")

    if add_listener:
        lines.append(f"{indent}        // Add listener to CinemachineCamera (not the physical camera)")
        lines.append(f"{indent}        CinemachineCamera cmCam = Object.FindFirstObjectByType<CinemachineCamera>();")
        lines.append(f"{indent}        if (cmCam != null)")
        lines.append(f"{indent}        {{")
        lines.append(f"{indent}            CinemachineImpulseListener listener = cmCam.GetComponent<CinemachineImpulseListener>();")
        lines.append(f"{indent}            if (listener == null)")
        lines.append(f"{indent}                listener = cmCam.gameObject.AddComponent<CinemachineImpulseListener>();")
        lines.append(f"{indent}        }}")
        lines.append("")

    lines.append(f"{indent}        Undo.RegisterCreatedObjectUndo(impulseGo, \"Setup Camera Shake\");")
    lines.append("")

    lines.append(f"{indent}        // Write result")
    listener_str = "true" if add_listener else "false"
    lines.append(f'{indent}        string json = "{{\\"status\\":\\"success\\",\\"impulse_force\\":{impulse_force},\\"listener_added\\":{listener_str}}}";')
    lines.append(f'{indent}        File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(f'{indent}        Debug.Log("[VeilBreakers] Camera shake configured");')

    lines.append(f"{indent}    }}")
    lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CAM-04: Camera blend configuration
# ---------------------------------------------------------------------------


def generate_camera_blend_script(
    default_blend_time: float = 2.0,
    blend_style: str = "EaseInOut",
    custom_blends: Optional[list[dict]] = None,
    namespace: str = "VeilBreakers.CameraSystems",
) -> str:
    """Generate C# editor script for CinemachineBrain blend configuration.

    Configures the default blend and custom camera-to-camera blend definitions
    on the CinemachineBrain component.
    """
    if custom_blends is None:
        custom_blends = []

    safe_style = sanitize_cs_identifier(blend_style)

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using Unity.Cinemachine;")
    lines.append("using System.IO;")
    lines.append("")

    if namespace:
        lines.append(f"namespace {_safe_namespace(namespace)}")
        lines.append("{")

    indent = "    " if namespace else ""
    lines.append(f"{indent}public static class VeilBreakers_CameraBlend")
    lines.append(f"{indent}{{")
    lines.append(f'{indent}    [MenuItem("VeilBreakers/Camera/Configure Blend")]')
    lines.append(f"{indent}    public static void Execute()")
    lines.append(f"{indent}    {{")

    lines.append(f"{indent}        // Find or add CinemachineBrain on main camera")
    lines.append(f"{indent}        Camera mainCam = Camera.main;")
    lines.append(f"{indent}        if (mainCam == null)")
    lines.append(f"{indent}        {{")
    lines.append(f'{indent}            Debug.LogError("[VeilBreakers] No main camera found");')
    lines.append(f"{indent}            return;")
    lines.append(f"{indent}        }}")
    lines.append("")
    lines.append(f"{indent}        CinemachineBrain brain = mainCam.GetComponent<CinemachineBrain>();")
    lines.append(f"{indent}        if (brain == null)")
    lines.append(f"{indent}            brain = mainCam.gameObject.AddComponent<CinemachineBrain>();")
    lines.append("")

    lines.append(f"{indent}        // Configure default blend")
    lines.append(f"{indent}        brain.DefaultBlend = new CinemachineBlendDefinition(")
    lines.append(f"{indent}            CinemachineBlendDefinition.Styles.{safe_style},")
    lines.append(f"{indent}            {default_blend_time}f")
    lines.append(f"{indent}        );")
    lines.append("")

    if custom_blends:
        lines.append(f"{indent}        // Configure custom blends")
        lines.append(f"{indent}        CinemachineBlenderSettings blenderSettings = ScriptableObject.CreateInstance<CinemachineBlenderSettings>();")
        lines.append(f"{indent}        CinemachineBlenderSettings.CustomBlend[] blends = new CinemachineBlenderSettings.CustomBlend[{len(custom_blends)}];")
        for i, blend in enumerate(custom_blends):
            from_cam = sanitize_cs_string(blend.get("from_cam", ""))
            to_cam = sanitize_cs_string(blend.get("to_cam", ""))
            btime = blend.get("time", 1.0)
            bstyle = sanitize_cs_identifier(blend.get("style", "EaseInOut"))
            lines.append(f"{indent}        blends[{i}] = new CinemachineBlenderSettings.CustomBlend")
            lines.append(f"{indent}        {{")
            lines.append(f'{indent}            From = "{from_cam}",')
            lines.append(f'{indent}            To = "{to_cam}",')
            lines.append(f"{indent}            Blend = new CinemachineBlendDefinition(")
            lines.append(f"{indent}                CinemachineBlendDefinition.Styles.{bstyle},")
            lines.append(f"{indent}                {btime}f")
            lines.append(f"{indent}            )")
            lines.append(f"{indent}        }};")
        lines.append(f"{indent}        blenderSettings.CustomBlends = blends;")
        lines.append(f"{indent}        brain.CustomBlends = blenderSettings;")
    lines.append("")

    lines.append(f"{indent}        EditorUtility.SetDirty(brain);")
    lines.append("")

    lines.append(f"{indent}        // Write result")
    lines.append(f'{indent}        string json = "{{\\"status\\":\\"success\\",\\"default_blend_time\\":{default_blend_time},\\"blend_style\\":\\"{safe_style}\\"}}";')
    lines.append(f'{indent}        File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(f'{indent}        Debug.Log("[VeilBreakers] Camera blend configured");')

    lines.append(f"{indent}    }}")
    lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CAM-02: Timeline setup
# ---------------------------------------------------------------------------


def generate_timeline_setup_script(
    timeline_name: str = "VB_Cutscene",
    tracks: Optional[list[dict]] = None,
    output_path: str = "Assets/Timelines",
    namespace: str = "VeilBreakers.CameraSystems",
) -> str:
    """Generate C# editor script for Timeline asset creation.

    Creates a TimelineAsset, saves it to AssetDatabase FIRST, then adds
    tracks. This ordering is critical -- tracks are sub-assets that require
    the parent asset to be persisted before creation.
    """
    if tracks is None:
        tracks = [
            {"type": "animation", "name": "Character Animation"},
            {"type": "audio", "name": "Dialogue Audio"},
            {"type": "activation", "name": "Props"},
            {"type": "cinemachine", "name": "Camera Cuts"},
        ]

    safe_name = sanitize_cs_identifier(timeline_name)
    safe_path = sanitize_cs_string(output_path)

    # Map track types to C# types
    track_type_map = {
        "animation": "AnimationTrack",
        "audio": "AudioTrack",
        "activation": "ActivationTrack",
        "cinemachine": "CinemachineTrack",
    }

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using UnityEngine.Timeline;")
    lines.append("using UnityEngine.Playables;")
    lines.append("using Unity.Cinemachine;")
    lines.append("using System.IO;")
    lines.append("")

    if namespace:
        lines.append(f"namespace {_safe_namespace(namespace)}")
        lines.append("{")

    indent = "    " if namespace else ""
    lines.append(f"{indent}public static class VeilBreakers_TimelineSetup")
    lines.append(f"{indent}{{")
    lines.append(f'{indent}    [MenuItem("VeilBreakers/Camera/Create Timeline")]')
    lines.append(f"{indent}    public static void Execute()")
    lines.append(f"{indent}    {{")

    # Ensure output directory exists
    lines.append(f'{indent}        string outputDir = "{safe_path}";')
    lines.append(f"{indent}        if (!AssetDatabase.IsValidFolder(outputDir))")
    lines.append(f"{indent}        {{")
    lines.append(f'{indent}            string[] parts = outputDir.Split(\'/\');')
    lines.append(f'{indent}            string current = parts[0];')
    lines.append(f"{indent}            for (int i = 1; i < parts.Length; i++)")
    lines.append(f"{indent}            {{")
    lines.append(f"{indent}                string next = current + \"/\" + parts[i];")
    lines.append(f"{indent}                if (!AssetDatabase.IsValidFolder(next))")
    lines.append(f"{indent}                    AssetDatabase.CreateFolder(current, parts[i]);")
    lines.append(f"{indent}                current = next;")
    lines.append(f"{indent}            }}")
    lines.append(f"{indent}        }}")
    lines.append("")

    # Create TimelineAsset and save to AssetDatabase BEFORE adding tracks
    lines.append(f"{indent}        // Create TimelineAsset")
    lines.append(f"{indent}        TimelineAsset timeline = ScriptableObject.CreateInstance<TimelineAsset>();")
    lines.append(f'{indent}        string assetPath = outputDir + "/{safe_name}.playable";')
    lines.append("")
    lines.append(f"{indent}        // CRITICAL: Save to AssetDatabase BEFORE adding tracks")
    lines.append(f"{indent}        AssetDatabase.CreateAsset(timeline, assetPath);")
    lines.append("")

    # Add tracks after save
    lines.append(f"{indent}        // Add tracks (after asset is persisted)")
    for track_info in tracks:
        ttype = track_info.get("type", "animation")
        tname = sanitize_cs_string(track_info.get("name", "Track"))
        cs_type = track_type_map.get(ttype, "AnimationTrack")
        lines.append(f'{indent}        timeline.CreateTrack<{cs_type}>(null, "{tname}");')
    lines.append("")

    lines.append(f"{indent}        AssetDatabase.SaveAssets();")
    lines.append(f"{indent}        AssetDatabase.Refresh();")
    lines.append("")

    lines.append(f"{indent}        // Write result")
    lines.append(f'{indent}        string json = "{{\\"status\\":\\"success\\",\\"timeline_name\\":\\"{safe_name}\\",\\"track_count\\":{len(tracks)},\\"asset_path\\":\\"" + assetPath.Replace("\\\\", "/") + "\\"}}";')
    lines.append(f'{indent}        File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(f'{indent}        Debug.Log("[VeilBreakers] Timeline created at " + assetPath + " with {len(tracks)} tracks");')

    lines.append(f"{indent}    }}")
    lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CAM-03: Cutscene setup (PlayableDirector)
# ---------------------------------------------------------------------------


def generate_cutscene_setup_script(
    cutscene_name: str = "VB_Cutscene",
    timeline_path: str = "Assets/Timelines/VB_Cutscene.playable",
    wrap_mode: str = "None",
    play_on_awake: bool = False,
    namespace: str = "VeilBreakers.CameraSystems",
) -> str:
    """Generate C# editor script for PlayableDirector + Timeline binding.

    Creates a PlayableDirector on the selected or new GameObject, assigns
    the specified Timeline asset, and configures wrap mode and play-on-awake.
    """
    safe_name = sanitize_cs_identifier(cutscene_name)
    safe_timeline = sanitize_cs_string(timeline_path)
    safe_wrap = sanitize_cs_identifier(wrap_mode)
    poa = "true" if play_on_awake else "false"

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using UnityEngine.Playables;")
    lines.append("using UnityEngine.Timeline;")
    lines.append("using System.IO;")
    lines.append("")

    if namespace:
        lines.append(f"namespace {_safe_namespace(namespace)}")
        lines.append("{")

    indent = "    " if namespace else ""
    lines.append(f"{indent}public static class VeilBreakers_CutsceneSetup")
    lines.append(f"{indent}{{")
    lines.append(f'{indent}    [MenuItem("VeilBreakers/Camera/Setup Cutscene")]')
    lines.append(f"{indent}    public static void Execute()")
    lines.append(f"{indent}    {{")

    lines.append(f'{indent}        // Create or use selected GameObject')
    lines.append(f'{indent}        GameObject cutsceneGo = Selection.activeGameObject ?? new GameObject("{sanitize_cs_string(cutscene_name)}");')
    lines.append("")

    lines.append(f"{indent}        // Add PlayableDirector")
    lines.append(f"{indent}        PlayableDirector director = cutsceneGo.GetComponent<PlayableDirector>();")
    lines.append(f"{indent}        if (director == null)")
    lines.append(f"{indent}            director = cutsceneGo.AddComponent<PlayableDirector>();")
    lines.append("")

    lines.append(f"{indent}        // Load and assign Timeline asset")
    lines.append(f'{indent}        TimelineAsset timeline = AssetDatabase.LoadAssetAtPath<TimelineAsset>("{safe_timeline}");')
    lines.append(f"{indent}        if (timeline != null)")
    lines.append(f"{indent}        {{")
    lines.append(f"{indent}            director.playableAsset = timeline;")
    lines.append(f"{indent}        }}")
    lines.append(f"{indent}        else")
    lines.append(f"{indent}        {{")
    lines.append(f'{indent}            Debug.LogWarning("[VeilBreakers] Timeline asset not found at: {safe_timeline}");')
    lines.append(f"{indent}        }}")
    lines.append("")

    lines.append(f"{indent}        // Configure wrap mode and play-on-awake")
    lines.append(f"{indent}        director.extrapolationMode = DirectorWrapMode.{safe_wrap};")
    lines.append(f"{indent}        director.playOnAwake = {poa};")
    lines.append("")

    lines.append(f"{indent}        Undo.RegisterCreatedObjectUndo(cutsceneGo, \"Setup Cutscene\");")
    lines.append(f"{indent}        EditorUtility.SetDirty(director);")
    lines.append("")

    lines.append(f"{indent}        // Write result")
    lines.append(f'{indent}        string json = "{{\\"status\\":\\"success\\",\\"cutscene_name\\":\\"{safe_name}\\",\\"wrap_mode\\":\\"{safe_wrap}\\",\\"play_on_awake\\":{poa}}}";')
    lines.append(f'{indent}        File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(f'{indent}        Debug.Log("[VeilBreakers] Cutscene configured: {sanitize_cs_string(cutscene_name)}");')

    lines.append(f"{indent}    }}")
    lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ANIMA-01: AnimationClip editor (EditorCurveBinding API)
# ---------------------------------------------------------------------------


def generate_animation_clip_editor_script(
    clip_name: str = "VB_CustomClip",
    curves: Optional[list[dict]] = None,
    output_path: str = "Assets/Animations",
    namespace: str = "VeilBreakers.CameraSystems",
) -> str:
    """Generate C# editor script for AnimationClip curve editing.

    Uses EditorCurveBinding.FloatCurve and AnimationUtility.SetEditorCurve
    (NOT AnimationClip.SetCurve which only works at runtime for legacy clips).
    """
    if curves is None:
        curves = [
            {
                "path": "",
                "component_type": "Transform",
                "property": "localPosition.x",
                "keyframes": [[0.0, 0.0], [0.5, 2.0], [1.0, 0.0]],
            },
        ]

    safe_name = sanitize_cs_identifier(clip_name)
    safe_path = sanitize_cs_string(output_path)

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using System.IO;")
    lines.append("")

    if namespace:
        lines.append(f"namespace {_safe_namespace(namespace)}")
        lines.append("{")

    indent = "    " if namespace else ""
    lines.append(f"{indent}public static class VeilBreakers_AnimClipEditor")
    lines.append(f"{indent}{{")
    lines.append(f'{indent}    [MenuItem("VeilBreakers/Camera/Edit Animation Clip")]')
    lines.append(f"{indent}    public static void Execute()")
    lines.append(f"{indent}    {{")

    # Ensure directory
    lines.append(f'{indent}        string outputDir = "{safe_path}";')
    lines.append(f"{indent}        if (!AssetDatabase.IsValidFolder(outputDir))")
    lines.append(f"{indent}        {{")
    lines.append(f'{indent}            string[] parts = outputDir.Split(\'/\');')
    lines.append(f'{indent}            string current = parts[0];')
    lines.append(f"{indent}            for (int i = 1; i < parts.Length; i++)")
    lines.append(f"{indent}            {{")
    lines.append(f"{indent}                string next = current + \"/\" + parts[i];")
    lines.append(f"{indent}                if (!AssetDatabase.IsValidFolder(next))")
    lines.append(f"{indent}                    AssetDatabase.CreateFolder(current, parts[i]);")
    lines.append(f"{indent}                current = next;")
    lines.append(f"{indent}            }}")
    lines.append(f"{indent}        }}")
    lines.append("")

    # Create clip
    lines.append(f"{indent}        // Create animation clip")
    lines.append(f"{indent}        AnimationClip clip = new AnimationClip();")
    lines.append(f'{indent}        clip.name = "{safe_name}";')
    lines.append("")

    # Add curves using EditorCurveBinding API
    for i, curve_info in enumerate(curves):
        c_path = sanitize_cs_string(curve_info.get("path", ""))
        c_type = sanitize_cs_identifier(curve_info.get("component_type", "Transform"))
        c_prop = sanitize_cs_string(curve_info.get("property", "localPosition.x"))
        keyframes = curve_info.get("keyframes", [[0.0, 0.0]])

        lines.append(f"{indent}        // Curve {i}: {c_prop}")
        lines.append(f"{indent}        EditorCurveBinding binding_{i} = EditorCurveBinding.FloatCurve(")
        lines.append(f'{indent}            "{c_path}",')
        lines.append(f"{indent}            typeof({c_type}),")
        lines.append(f'{indent}            "{c_prop}"')
        lines.append(f"{indent}        );")
        lines.append(f"{indent}        Keyframe[] keys_{i} = new Keyframe[]")
        lines.append(f"{indent}        {{")
        for kf in keyframes:
            t = kf[0] if len(kf) > 0 else 0.0
            v = kf[1] if len(kf) > 1 else 0.0
            lines.append(f"{indent}            new Keyframe({t}f, {v}f),")
        lines.append(f"{indent}        }};")
        lines.append(f"{indent}        AnimationCurve curve_{i} = new AnimationCurve(keys_{i});")
        lines.append(f"{indent}        AnimationUtility.SetEditorCurve(clip, binding_{i}, curve_{i});")
        lines.append("")

    # Save
    lines.append(f'{indent}        string clipPath = outputDir + "/{safe_name}.anim";')
    lines.append(f"{indent}        AssetDatabase.CreateAsset(clip, clipPath);")
    lines.append(f"{indent}        AssetDatabase.SaveAssets();")
    lines.append("")

    lines.append(f"{indent}        // Write result")
    lines.append(f'{indent}        string json = "{{\\"status\\":\\"success\\",\\"clip_name\\":\\"{safe_name}\\",\\"curve_count\\":{len(curves)},\\"asset_path\\":\\"" + clipPath.Replace("\\\\", "/") + "\\"}}";')
    lines.append(f'{indent}        File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(f'{indent}        Debug.Log("[VeilBreakers] Animation clip created at " + clipPath);')

    lines.append(f"{indent}    }}")
    lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ANIMA-02: Animator Controller modifier
# ---------------------------------------------------------------------------


def generate_animator_modifier_script(
    controller_path: str = "Assets/Animations/VB_Controller.controller",
    states_to_add: Optional[list[str]] = None,
    transitions: Optional[list[dict]] = None,
    parameters: Optional[list[dict]] = None,
    sub_state_machines: Optional[list[str]] = None,
    namespace: str = "VeilBreakers.CameraSystems",
) -> str:
    """Generate C# editor script for AnimatorController modification.

    Uses AnimatorController from UnityEditor.Animations to add states,
    transitions, parameters, and sub-state machines.
    """
    if states_to_add is None:
        states_to_add = ["Idle", "Walk", "Run"]
    if transitions is None:
        transitions = [
            {"from_state": "Idle", "to_state": "Walk", "has_exit_time": False, "duration": 0.25},
            {"from_state": "Walk", "to_state": "Run", "has_exit_time": False, "duration": 0.1},
        ]
    if parameters is None:
        parameters = [
            {"name": "Speed", "type": "Float"},
            {"name": "IsGrounded", "type": "Bool"},
        ]
    if sub_state_machines is None:
        sub_state_machines = []

    safe_path = sanitize_cs_string(controller_path)

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using UnityEditor.Animations;")
    lines.append("using System.IO;")
    lines.append("using System.Collections.Generic;")
    lines.append("")

    if namespace:
        lines.append(f"namespace {_safe_namespace(namespace)}")
        lines.append("{")

    indent = "    " if namespace else ""
    lines.append(f"{indent}public static class VeilBreakers_AnimatorModifier")
    lines.append(f"{indent}{{")
    lines.append(f'{indent}    [MenuItem("VeilBreakers/Camera/Modify Animator")]')
    lines.append(f"{indent}    public static void Execute()")
    lines.append(f"{indent}    {{")

    # Load or create controller
    lines.append(f'{indent}        string controllerPath = "{safe_path}";')
    lines.append(f"{indent}        AnimatorController controller = AssetDatabase.LoadAssetAtPath<AnimatorController>(controllerPath);")
    lines.append(f"{indent}        if (controller == null)")
    lines.append(f"{indent}        {{")
    lines.append(f"{indent}            controller = AnimatorController.CreateAnimatorControllerAtPath(controllerPath);")
    lines.append(f"{indent}        }}")
    lines.append("")

    # Add parameters
    lines.append(f"{indent}        // Add parameters")
    for param in parameters:
        p_name = sanitize_cs_string(param.get("name", "Param"))
        p_type = sanitize_cs_identifier(param.get("type", "Float"))
        lines.append(f'{indent}        controller.AddParameter("{p_name}", AnimatorControllerParameterType.{p_type});')
    lines.append("")

    # Get root state machine
    lines.append(f"{indent}        // Get root state machine")
    lines.append(f"{indent}        AnimatorStateMachine sm = controller.layers[0].stateMachine;")
    lines.append("")

    # Add sub-state machines
    if sub_state_machines:
        lines.append(f"{indent}        // Add sub-state machines")
        for ssm_name in sub_state_machines:
            safe_ssm = sanitize_cs_string(ssm_name)
            safe_ssm_id = sanitize_cs_identifier(ssm_name)
            lines.append(f'{indent}        AnimatorStateMachine ssm_{safe_ssm_id} = sm.AddStateMachine("{safe_ssm}");')
        lines.append("")

    # Add states
    lines.append(f"{indent}        // Add states")
    lines.append(f"{indent}        Dictionary<string, AnimatorState> stateMap = new Dictionary<string, AnimatorState>();")
    for state_name in states_to_add:
        safe_state = sanitize_cs_string(state_name)
        safe_state_id = sanitize_cs_identifier(state_name)
        lines.append(f'{indent}        stateMap["{safe_state}"] = sm.AddState("{safe_state}");')
    lines.append("")

    # Add transitions
    lines.append(f"{indent}        // Add transitions")
    for trans in transitions:
        from_s = sanitize_cs_string(trans.get("from_state", ""))
        to_s = sanitize_cs_string(trans.get("to_state", ""))
        has_exit = "true" if trans.get("has_exit_time", False) else "false"
        duration = trans.get("duration", 0.25)
        lines.append(f'{indent}        if (stateMap.ContainsKey("{from_s}") && stateMap.ContainsKey("{to_s}"))')
        lines.append(f"{indent}        {{")
        lines.append(f'{indent}            AnimatorStateTransition t = stateMap["{from_s}"].AddTransition(stateMap["{to_s}"]);')
        lines.append(f"{indent}            t.hasExitTime = {has_exit};")
        lines.append(f"{indent}            t.duration = {duration}f;")
        lines.append(f"{indent}        }}")
    lines.append("")

    lines.append(f"{indent}        EditorUtility.SetDirty(controller);")
    lines.append(f"{indent}        AssetDatabase.SaveAssets();")
    lines.append("")

    lines.append(f"{indent}        // Write result")
    lines.append(f'{indent}        string json = "{{\\"status\\":\\"success\\",\\"states_added\\":{len(states_to_add)},\\"transitions_added\\":{len(transitions)},\\"parameters_added\\":{len(parameters)}}}";')
    lines.append(f'{indent}        File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(f'{indent}        Debug.Log("[VeilBreakers] Animator controller modified: {len(states_to_add)} states, {len(transitions)} transitions");')

    lines.append(f"{indent}    }}")
    lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ANIMA-03: Avatar mask creation
# ---------------------------------------------------------------------------


def generate_avatar_mask_script(
    mask_name: str = "VB_UpperBodyMask",
    body_parts: Optional[dict[str, bool]] = None,
    transform_paths: Optional[list[str]] = None,
    output_path: str = "Assets/Animations",
    namespace: str = "VeilBreakers.CameraSystems",
) -> str:
    """Generate C# editor script for AvatarMask creation.

    Uses AvatarMask.SetHumanoidBodyPartActive for body part filtering
    and optionally sets transform active states for non-humanoid masks.
    """
    if body_parts is None:
        body_parts = {
            "Body": True,
            "Head": True,
            "LeftArm": True,
            "RightArm": True,
            "LeftLeg": False,
            "RightLeg": False,
            "LeftFingers": True,
            "RightFingers": True,
            "LeftFootIK": False,
            "RightFootIK": False,
            "LeftHandIK": True,
            "RightHandIK": True,
        }
    if transform_paths is None:
        transform_paths = []

    safe_name = sanitize_cs_identifier(mask_name)
    safe_path = sanitize_cs_string(output_path)

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using System.IO;")
    lines.append("")

    if namespace:
        lines.append(f"namespace {_safe_namespace(namespace)}")
        lines.append("{")

    indent = "    " if namespace else ""
    lines.append(f"{indent}public static class VeilBreakers_AvatarMaskSetup")
    lines.append(f"{indent}{{")
    lines.append(f'{indent}    [MenuItem("VeilBreakers/Camera/Create Avatar Mask")]')
    lines.append(f"{indent}    public static void Execute()")
    lines.append(f"{indent}    {{")

    # Ensure directory
    lines.append(f'{indent}        string outputDir = "{safe_path}";')
    lines.append(f"{indent}        if (!AssetDatabase.IsValidFolder(outputDir))")
    lines.append(f"{indent}        {{")
    lines.append(f'{indent}            string[] parts = outputDir.Split(\'/\');')
    lines.append(f'{indent}            string current = parts[0];')
    lines.append(f"{indent}            for (int i = 1; i < parts.Length; i++)")
    lines.append(f"{indent}            {{")
    lines.append(f"{indent}                string next = current + \"/\" + parts[i];")
    lines.append(f"{indent}                if (!AssetDatabase.IsValidFolder(next))")
    lines.append(f"{indent}                    AssetDatabase.CreateFolder(current, parts[i]);")
    lines.append(f"{indent}                current = next;")
    lines.append(f"{indent}            }}")
    lines.append(f"{indent}        }}")
    lines.append("")

    lines.append(f"{indent}        AvatarMask mask = new AvatarMask();")
    lines.append(f'{indent}        mask.name = "{safe_name}";')
    lines.append("")

    # Set humanoid body parts
    lines.append(f"{indent}        // Configure humanoid body parts")
    for part_name, active in body_parts.items():
        safe_part = sanitize_cs_identifier(part_name)
        val = "true" if active else "false"
        lines.append(f"{indent}        mask.SetHumanoidBodyPartActive(AvatarMaskBodyPart.{safe_part}, {val});")
    lines.append("")

    # Optional transform paths for non-humanoid
    if transform_paths:
        lines.append(f"{indent}        // Configure transform paths (non-humanoid)")
        lines.append(f"{indent}        mask.transformCount = {len(transform_paths)};")
        for i, tpath in enumerate(transform_paths):
            safe_tpath = sanitize_cs_string(tpath)
            lines.append(f'{indent}        mask.SetTransformPath({i}, "{safe_tpath}");')
            lines.append(f"{indent}        mask.SetTransformActive({i}, true);")
        lines.append("")

    # Save
    lines.append(f'{indent}        string maskPath = outputDir + "/{safe_name}.mask";')
    lines.append(f"{indent}        AssetDatabase.CreateAsset(mask, maskPath);")
    lines.append(f"{indent}        AssetDatabase.SaveAssets();")
    lines.append("")

    lines.append(f"{indent}        // Write result")
    lines.append(f'{indent}        string json = "{{\\"status\\":\\"success\\",\\"mask_name\\":\\"{safe_name}\\",\\"body_parts\\":{len(body_parts)},\\"asset_path\\":\\"" + maskPath.Replace("\\\\", "/") + "\\"}}";')
    lines.append(f'{indent}        File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(f'{indent}        Debug.Log("[VeilBreakers] Avatar mask created at " + maskPath);')

    lines.append(f"{indent}    }}")
    lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MEDIA-01: Video player setup
# ---------------------------------------------------------------------------


def generate_video_player_script(
    video_source: str = "clip",
    video_path: str = "",
    render_texture_width: int = 1920,
    render_texture_height: int = 1080,
    loop: bool = True,
    play_on_awake: bool = True,
    namespace: str = "VeilBreakers.CameraSystems",
) -> str:
    """Generate C# editor script for VideoPlayer + RenderTexture setup.

    Creates a VideoPlayer component with RenderTexture output, configured
    for either clip-based or URL-based video sources.
    """
    safe_path = sanitize_cs_string(video_path)
    loop_str = "true" if loop else "false"
    poa_str = "true" if play_on_awake else "false"

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using UnityEngine.Video;")
    lines.append("using System.IO;")
    lines.append("")

    if namespace:
        lines.append(f"namespace {_safe_namespace(namespace)}")
        lines.append("{")

    indent = "    " if namespace else ""
    lines.append(f"{indent}public static class VeilBreakers_VideoPlayerSetup")
    lines.append(f"{indent}{{")
    lines.append(f'{indent}    [MenuItem("VeilBreakers/Camera/Setup Video Player")]')
    lines.append(f"{indent}    public static void Execute()")
    lines.append(f"{indent}    {{")

    lines.append(f'{indent}        // Create VideoPlayer GameObject')
    lines.append(f'{indent}        GameObject vpGo = Selection.activeGameObject ?? new GameObject("VB_VideoPlayer");')
    lines.append("")

    lines.append(f"{indent}        // Add VideoPlayer component")
    lines.append(f"{indent}        VideoPlayer vp = vpGo.GetComponent<VideoPlayer>();")
    lines.append(f"{indent}        if (vp == null)")
    lines.append(f"{indent}            vp = vpGo.AddComponent<VideoPlayer>();")
    lines.append("")

    lines.append(f"{indent}        // Create RenderTexture for output")
    lines.append(f"{indent}        RenderTexture renderTexture = new RenderTexture({render_texture_width}, {render_texture_height}, 0);")
    lines.append(f'{indent}        renderTexture.name = "VB_VideoRenderTexture";')
    lines.append(f"{indent}        renderTexture.Create();")
    lines.append("")

    lines.append(f"{indent}        // Configure render mode")
    lines.append(f"{indent}        vp.renderMode = VideoRenderMode.RenderTexture;")
    lines.append(f"{indent}        vp.targetTexture = renderTexture;")
    lines.append("")

    # Source type
    if video_source == "url":
        lines.append(f"{indent}        // URL source")
        lines.append(f"{indent}        vp.source = VideoSource.Url;")
        if video_path:
            lines.append(f'{indent}        vp.url = "{safe_path}";')
    else:
        lines.append(f"{indent}        // Clip source")
        lines.append(f"{indent}        vp.source = VideoSource.VideoClip;")
        if video_path:
            lines.append(f'{indent}        VideoClip clip = AssetDatabase.LoadAssetAtPath<VideoClip>("{safe_path}");')
            lines.append(f"{indent}        if (clip != null) vp.clip = clip;")
    lines.append("")

    lines.append(f"{indent}        // Playback settings")
    lines.append(f"{indent}        vp.isLooping = {loop_str};")
    lines.append(f"{indent}        vp.playOnAwake = {poa_str};")
    lines.append("")

    # Ensure output directory exists and save RenderTexture as asset
    lines.append(f'{indent}        if (!AssetDatabase.IsValidFolder("Assets/RenderTextures"))')
    lines.append(f'{indent}            AssetDatabase.CreateFolder("Assets", "RenderTextures");')
    lines.append(f'{indent}        AssetDatabase.CreateAsset(renderTexture, "Assets/RenderTextures/VB_VideoRT.renderTexture");')
    lines.append("")

    lines.append(f"{indent}        Undo.RegisterCreatedObjectUndo(vpGo, \"Setup Video Player\");")
    lines.append(f"{indent}        EditorUtility.SetDirty(vp);")
    lines.append("")

    lines.append(f"{indent}        // Write result")
    lines.append(f'{indent}        string json = "{{\\"status\\":\\"success\\",\\"video_source\\":\\"{video_source}\\",\\"resolution\\":\\"{render_texture_width}x{render_texture_height}\\",\\"loop\\":{loop_str}}}";')
    lines.append(f'{indent}        File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(f'{indent}        Debug.Log("[VeilBreakers] Video player configured: {render_texture_width}x{render_texture_height}");')

    lines.append(f"{indent}    }}")
    lines.append(f"{indent}}}")

    if namespace:
        lines.append("}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CM-02: Lock-On Camera System (Souls-like targeting)
# ---------------------------------------------------------------------------


def generate_lock_on_camera_script(
    max_lock_distance: float = 20.0,
    view_cone_angle: float = 90.0,
    orbit_damping: float = 5.0,
    target_switch_cooldown: float = 0.25,
    los_break_time: float = 1.5,
    soft_lock_weight: float = 0.5,
    max_targets_buffer: int = 16,
    namespace: str = "VeilBreakers.CameraSystems",
) -> tuple[str, str]:
    """Generate C# for a Souls-like lock-on targeting camera.

    Creates a runtime VB_LockOnCamera MonoBehaviour that handles target
    acquisition via OverlapSphereNonAlloc + view cone filtering, target
    cycling, and camera orbit around the player-target midpoint.  Also
    generates an editor helper script to set up the system.

    Args:
        max_lock_distance: Maximum distance to acquire/keep a lock target.
        view_cone_angle: Forward cone half-angle for target acquisition.
        orbit_damping: Smoothing factor for camera follow during lock-on.
        target_switch_cooldown: Minimum seconds between target cycle inputs.
        los_break_time: Seconds of blocked LoS before lock is dropped.
        soft_lock_weight: Blend weight for soft-lock mode (0 = free, 1 = hard).
        max_targets_buffer: Size of the pre-allocated NonAlloc results buffer.
        namespace: C# namespace for generated code.

    Returns:
        (editor_cs, runtime_cs) tuple.
    """
    ns = _safe_namespace(namespace)

    # -- Runtime MonoBehaviour ------------------------------------------------
    rt: list[str] = []
    rt.append("using System;")
    rt.append("using System.Collections.Generic;")
    rt.append("using UnityEngine;")
    rt.append("using UnityEngine.Events;")
    rt.append("")
    rt.append("namespace " + ns)
    rt.append("{")

    # --- LockOnMode enum ---
    rt.append("    /// <summary>Lock-on behaviour mode.</summary>")
    rt.append("    public enum LockOnMode { SoftLock, HardLock }")
    rt.append("")

    # --- VB_LockOnCamera class ---
    rt.append("    /// <summary>")
    rt.append("    /// Souls-like lock-on targeting camera.")
    rt.append("    /// Generated by VeilBreakers MCP toolkit (CM-02).")
    rt.append("    /// </summary>")
    rt.append("    [DisallowMultipleComponent]")
    rt.append("    public class VB_LockOnCamera : MonoBehaviour")
    rt.append("    {")

    # Serialized fields
    rt.append("        [Header(\"Target Acquisition\")]")
    rt.append("        [SerializeField] private float _maxLockDistance = " + f"{max_lock_distance}f;")
    rt.append("        [SerializeField] private float _viewConeAngle = " + f"{view_cone_angle}f;")
    rt.append("        [SerializeField] private LayerMask _targetLayer = ~0;")
    rt.append("        [SerializeField] private string _targetTag = \"Enemy\";")
    rt.append("")
    rt.append("        [Header(\"Camera Behaviour\")]")
    rt.append("        [SerializeField] private LockOnMode _lockOnMode = LockOnMode.HardLock;")
    rt.append("        [SerializeField] private float _orbitDamping = " + f"{orbit_damping}f;")
    rt.append("        [SerializeField] private float _softLockWeight = " + f"{soft_lock_weight}f;")
    rt.append("        [SerializeField] private Vector3 _cameraOffset = new Vector3(0f, 2f, -4f);")
    rt.append("        [SerializeField] private float _midpointBias = 0.35f;")
    rt.append("")
    rt.append("        [Header(\"Target Lost Conditions\")]")
    rt.append("        [SerializeField] private float _losBreakTime = " + f"{los_break_time}f;")
    rt.append("        [SerializeField] private LayerMask _losBlockLayers = ~0;")
    rt.append("")
    rt.append("        [Header(\"Input\")]")
    rt.append("        [SerializeField] private KeyCode _lockOnToggleKey = KeyCode.Mouse2;")
    rt.append("        [SerializeField] private KeyCode _cycleLeftKey = KeyCode.Q;")
    rt.append("        [SerializeField] private KeyCode _cycleRightKey = KeyCode.E;")
    rt.append("        [SerializeField] private float _targetSwitchCooldown = " + f"{target_switch_cooldown}f;")
    rt.append("")
    rt.append("        [Header(\"Target Indicator\")]")
    rt.append("        [SerializeField] private GameObject _targetIndicatorPrefab;")
    rt.append("        [SerializeField] private Vector3 _indicatorOffset = new Vector3(0f, 2.2f, 0f);")
    rt.append("")
    rt.append("        [Header(\"Events\")]")
    rt.append("        public UnityEvent<Transform> OnTargetAcquired;")
    rt.append("        public UnityEvent OnTargetLost;")
    rt.append("        public UnityEvent<Transform> OnTargetChanged;")
    rt.append("")

    # Private state
    rt.append("        // Internal state")
    rt.append("        private Transform _player;")
    rt.append("        private Camera _mainCam;")
    rt.append("        private Transform _currentTarget;")
    rt.append("        private GameObject _indicatorInstance;")
    rt.append("        private bool _isLockedOn;")
    rt.append("        private float _lastSwitchTime;")
    rt.append("        private float _losBlockedTimer;")
    rt.append("        private readonly Collider[] _overlapBuffer = new Collider[" + str(max_targets_buffer) + "];")
    rt.append("        private readonly List<Transform> _validTargets = new List<Transform>();")
    rt.append("")

    # Properties
    rt.append("        /// <summary>Whether the camera is currently locked onto a target.</summary>")
    rt.append("        public bool IsLockedOn => _isLockedOn;")
    rt.append("        /// <summary>Current lock-on target (null if none).</summary>")
    rt.append("        public Transform CurrentTarget => _currentTarget;")
    rt.append("        /// <summary>Current lock mode.</summary>")
    rt.append("        public LockOnMode Mode { get => _lockOnMode; set => _lockOnMode = value; }")
    rt.append("")

    # Awake
    rt.append("        private void Awake()")
    rt.append("        {")
    rt.append("            _mainCam = Camera.main;")
    rt.append("        }")
    rt.append("")

    # SetPlayer
    rt.append("        /// <summary>Assign the player transform the camera follows.</summary>")
    rt.append("        public void SetPlayer(Transform player)")
    rt.append("        {")
    rt.append("            _player = player;")
    rt.append("        }")
    rt.append("")

    # Update
    rt.append("        private void Update()")
    rt.append("        {")
    rt.append("            if (_player == null) return;")
    rt.append("")
    rt.append("            // Toggle lock-on")
    rt.append("            if (Input.GetKeyDown(_lockOnToggleKey))")
    rt.append("            {")
    rt.append("                if (_isLockedOn) ReleaseLock();")
    rt.append("                else TryAcquireTarget();")
    rt.append("            }")
    rt.append("")
    rt.append("            // Cycle targets")
    rt.append("            if (_isLockedOn && Time.time - _lastSwitchTime > _targetSwitchCooldown)")
    rt.append("            {")
    rt.append("                if (Input.GetKeyDown(_cycleLeftKey)) { CycleTarget(-1); _lastSwitchTime = Time.time; }")
    rt.append("                if (Input.GetKeyDown(_cycleRightKey)) { CycleTarget(1); _lastSwitchTime = Time.time; }")
    rt.append("            }")
    rt.append("")
    rt.append("            // Validate current target")
    rt.append("            if (_isLockedOn) ValidateTarget();")
    rt.append("        }")
    rt.append("")

    # LateUpdate -- camera positioning
    rt.append("        private void LateUpdate()")
    rt.append("        {")
    rt.append("            if (_player == null) return;")
    rt.append("")
    rt.append("            if (_isLockedOn && _currentTarget != null)")
    rt.append("            {")
    rt.append("                // Compute midpoint between player and target")
    rt.append("                Vector3 midpoint = Vector3.Lerp(_player.position, _currentTarget.position, _midpointBias);")
    rt.append("                Vector3 desiredPos = midpoint + _cameraOffset;")
    rt.append("                Vector3 lookTarget = midpoint + Vector3.up * 1.2f;")
    rt.append("")
    rt.append("                if (_lockOnMode == LockOnMode.HardLock)")
    rt.append("                {")
    rt.append("                    transform.position = Vector3.Lerp(transform.position, desiredPos, Time.deltaTime * _orbitDamping);")
    rt.append("                    Quaternion desiredRot = Quaternion.LookRotation(lookTarget - transform.position);")
    rt.append("                    transform.rotation = Quaternion.Slerp(transform.rotation, desiredRot, Time.deltaTime * _orbitDamping);")
    rt.append("                }")
    rt.append("                else // SoftLock")
    rt.append("                {")
    rt.append("                    Vector3 softPos = Vector3.Lerp(transform.position, desiredPos, _softLockWeight * Time.deltaTime * _orbitDamping);")
    rt.append("                    transform.position = softPos;")
    rt.append("                    Quaternion softRot = Quaternion.LookRotation(lookTarget - transform.position);")
    rt.append("                    transform.rotation = Quaternion.Slerp(transform.rotation, softRot, _softLockWeight * Time.deltaTime * _orbitDamping);")
    rt.append("                }")
    rt.append("")
    rt.append("                // Update indicator position")
    rt.append("                if (_indicatorInstance != null)")
    rt.append("                    _indicatorInstance.transform.position = _currentTarget.position + _indicatorOffset;")
    rt.append("            }")
    rt.append("        }")
    rt.append("")

    # TryAcquireTarget
    rt.append("        /// <summary>Scan for the best lock-on target in view cone.</summary>")
    rt.append("        public void TryAcquireTarget()")
    rt.append("        {")
    rt.append("            GatherValidTargets();")
    rt.append("            if (_validTargets.Count == 0) return;")
    rt.append("")
    rt.append("            // Select closest to screen center")
    rt.append("            Transform best = null;")
    rt.append("            float bestDist = float.MaxValue;")
    rt.append("            Vector2 screenCenter = new Vector2(Screen.width * 0.5f, Screen.height * 0.5f);")
    rt.append("")
    rt.append("            foreach (Transform t in _validTargets)")
    rt.append("            {")
    rt.append("                if (_mainCam == null) break;")
    rt.append("                Vector3 sp = _mainCam.WorldToScreenPoint(t.position);")
    rt.append("                if (sp.z < 0f) continue; // Behind camera")
    rt.append("                float d = Vector2.Distance(new Vector2(sp.x, sp.y), screenCenter);")
    rt.append("                if (d < bestDist) { bestDist = d; best = t; }")
    rt.append("            }")
    rt.append("")
    rt.append("            if (best != null) SetTarget(best);")
    rt.append("        }")
    rt.append("")

    # GatherValidTargets
    rt.append("        private void GatherValidTargets()")
    rt.append("        {")
    rt.append("            _validTargets.Clear();")
    rt.append("            int count = Physics.OverlapSphereNonAlloc(_player.position, _maxLockDistance, _overlapBuffer, _targetLayer);")
    rt.append("")
    rt.append("            for (int i = 0; i < count; i++)")
    rt.append("            {")
    rt.append("                Collider col = _overlapBuffer[i];")
    rt.append("                if (col == null) continue;")
    rt.append("                if (!string.IsNullOrEmpty(_targetTag) && !col.CompareTag(_targetTag)) continue;")
    rt.append("")
    rt.append("                Transform t = col.transform;")
    rt.append("                Vector3 dir = (t.position - _player.position).normalized;")
    rt.append("                float angle = Vector3.Angle(_player.forward, dir);")
    rt.append("                if (angle > _viewConeAngle * 0.5f) continue;")
    rt.append("")
    rt.append("                _validTargets.Add(t);")
    rt.append("            }")
    rt.append("        }")
    rt.append("")

    # SetTarget
    rt.append("        private void SetTarget(Transform target)")
    rt.append("        {")
    rt.append("            bool changed = _currentTarget != target;")
    rt.append("            _currentTarget = target;")
    rt.append("            _isLockedOn = true;")
    rt.append("            _losBlockedTimer = 0f;")
    rt.append("")
    rt.append("            // Spawn indicator")
    rt.append("            if (_indicatorInstance == null && _targetIndicatorPrefab != null)")
    rt.append("                _indicatorInstance = Instantiate(_targetIndicatorPrefab);")
    rt.append("            if (_indicatorInstance != null)")
    rt.append("                _indicatorInstance.SetActive(true);")
    rt.append("")
    rt.append("            if (changed)")
    rt.append("            {")
    rt.append("                OnTargetAcquired?.Invoke(target);")
    rt.append("                OnTargetChanged?.Invoke(target);")
    rt.append("            }")
    rt.append("        }")
    rt.append("")

    # ReleaseLock
    rt.append("        /// <summary>Release the current lock-on target.</summary>")
    rt.append("        public void ReleaseLock()")
    rt.append("        {")
    rt.append("            _isLockedOn = false;")
    rt.append("            _currentTarget = null;")
    rt.append("            _losBlockedTimer = 0f;")
    rt.append("            if (_indicatorInstance != null)")
    rt.append("                _indicatorInstance.SetActive(false);")
    rt.append("            OnTargetLost?.Invoke();")
    rt.append("        }")
    rt.append("")

    # CycleTarget
    rt.append("        /// <summary>Cycle to the next/prev valid target.</summary>")
    rt.append("        public void CycleTarget(int direction)")
    rt.append("        {")
    rt.append("            GatherValidTargets();")
    rt.append("            if (_validTargets.Count <= 1) return;")
    rt.append("")
    rt.append("            // Sort by screen-space X position for left/right cycling")
    rt.append("            if (_mainCam != null)")
    rt.append("            {")
    rt.append("                _validTargets.Sort((a, b) =>")
    rt.append("                {")
    rt.append("                    float ax = _mainCam.WorldToScreenPoint(a.position).x;")
    rt.append("                    float bx = _mainCam.WorldToScreenPoint(b.position).x;")
    rt.append("                    return ax.CompareTo(bx);")
    rt.append("                });")
    rt.append("            }")
    rt.append("")
    rt.append("            int currentIdx = _validTargets.IndexOf(_currentTarget);")
    rt.append("            if (currentIdx < 0) currentIdx = 0;")
    rt.append("            int nextIdx = (currentIdx + direction + _validTargets.Count) % _validTargets.Count;")
    rt.append("            SetTarget(_validTargets[nextIdx]);")
    rt.append("        }")
    rt.append("")

    # ValidateTarget
    rt.append("        private void ValidateTarget()")
    rt.append("        {")
    rt.append("            if (_currentTarget == null || !_currentTarget.gameObject.activeInHierarchy)")
    rt.append("            {")
    rt.append("                ReleaseLock();")
    rt.append("                return;")
    rt.append("            }")
    rt.append("")
    rt.append("            // Distance check")
    rt.append("            float dist = Vector3.Distance(_player.position, _currentTarget.position);")
    rt.append("            if (dist > _maxLockDistance * 1.2f)")
    rt.append("            {")
    rt.append("                ReleaseLock();")
    rt.append("                return;")
    rt.append("            }")
    rt.append("")
    rt.append("            // Line of sight check")
    rt.append("            Vector3 origin = _player.position + Vector3.up * 1.5f;")
    rt.append("            Vector3 dir = (_currentTarget.position + Vector3.up * 1f) - origin;")
    rt.append("            if (Physics.Raycast(origin, dir.normalized, dir.magnitude, _losBlockLayers))")
    rt.append("            {")
    rt.append("                _losBlockedTimer += Time.deltaTime;")
    rt.append("                if (_losBlockedTimer >= _losBreakTime)")
    rt.append("                    ReleaseLock();")
    rt.append("            }")
    rt.append("            else")
    rt.append("            {")
    rt.append("                _losBlockedTimer = 0f;")
    rt.append("            }")
    rt.append("        }")
    rt.append("")

    # OnDestroy
    rt.append("        private void OnDestroy()")
    rt.append("        {")
    rt.append("            if (_indicatorInstance != null)")
    rt.append("                Destroy(_indicatorInstance);")
    rt.append("        }")
    rt.append("")

    # OnDrawGizmosSelected
    rt.append("        private void OnDrawGizmosSelected()")
    rt.append("        {")
    rt.append("            Gizmos.color = new Color(1f, 0.3f, 0.3f, 0.15f);")
    rt.append("            Gizmos.DrawWireSphere(transform.position, _maxLockDistance);")
    rt.append("            if (_currentTarget != null)")
    rt.append("            {")
    rt.append("                Gizmos.color = Color.red;")
    rt.append("                Gizmos.DrawLine(transform.position, _currentTarget.position);")
    rt.append("            }")
    rt.append("        }")

    rt.append("    }")
    rt.append("}")
    runtime_cs = "\n".join(rt)

    # -- Editor helper script -------------------------------------------------
    ed: list[str] = []
    ed.append("using UnityEngine;")
    ed.append("using UnityEditor;")
    ed.append("using System.IO;")
    ed.append("")
    ed.append("public static class VeilBreakers_LockOnCameraSetup")
    ed.append("{")
    ed.append("    [MenuItem(\"VeilBreakers/Camera/Setup Lock-On Camera\")]")
    ed.append("    public static void Execute()")
    ed.append("    {")
    ed.append("        GameObject go = new GameObject(\"VB_LockOnCamera\");")
    ed.append("        var cam = go.AddComponent<" + ns + ".VB_LockOnCamera>();")
    ed.append("        Camera mainCam = Camera.main;")
    ed.append("        if (mainCam != null)")
    ed.append("            go.transform.position = mainCam.transform.position;")
    ed.append("        Undo.RegisterCreatedObjectUndo(go, \"Setup Lock-On Camera\");")
    ed.append("        Selection.activeGameObject = go;")
    ed.append("")
    ed.append("        string json = \"{\\\"status\\\":\\\"success\\\",\\\"system\\\":\\\"lock_on_camera\\\",\\\"mode\\\":\\\"HardLock\\\"}\";")
    ed.append("        File.WriteAllText(\"Temp/vb_result.json\", json);")
    ed.append("        Debug.Log(\"[VeilBreakers] Lock-on camera system created.\");")
    ed.append("    }")
    ed.append("}")
    editor_cs = "\n".join(ed)

    return (editor_cs, runtime_cs)
