"""Animation extension C# template generators for Unity.

Provides AnimatorController with proper transitions (G14 fix), a runtime
animation layer manager with PrimeTween weight blending, and a multi-hit
AnimationEvent bridge for combat.

These live in a separate file from animation_templates.py to avoid merge
conflicts with parallel terminal work.

Exports:
    generate_animator_with_transitions_script -- G14: AnimatorController
    generate_animation_layer_manager_script   -- P5-Q8: Runtime layer manager
    generate_multi_hit_events_script          -- Multi-hit AnimationEvent bridge
"""

from __future__ import annotations

from typing import Any

from ._cs_sanitize import sanitize_cs_identifier, sanitize_cs_string

# ---------------------------------------------------------------------------
# Default animator data
# ---------------------------------------------------------------------------

_DEFAULT_STATES: list[dict[str, Any]] = [
    {"name": "Idle",   "motion_path": ""},
    {"name": "Walk",   "motion_path": ""},
    {"name": "Run",    "motion_path": ""},
    {"name": "Attack", "motion_path": ""},
]

_DEFAULT_PARAMETERS: list[dict[str, str]] = [
    {"name": "speed",         "type": "Float"},
    {"name": "attackTrigger", "type": "Trigger"},
]

_DEFAULT_TRANSITIONS: list[dict[str, Any]] = [
    {
        "from": "Idle",
        "to": "Walk",
        "conditions": [{"param": "speed", "mode": "Greater", "threshold": 0.1}],
        "duration": 0.15,
        "has_exit_time": False,
    },
    {
        "from": "Walk",
        "to": "Idle",
        "conditions": [{"param": "speed", "mode": "Less", "threshold": 0.1}],
        "duration": 0.15,
        "has_exit_time": False,
    },
    {
        "from": "Walk",
        "to": "Run",
        "conditions": [{"param": "speed", "mode": "Greater", "threshold": 0.6}],
        "duration": 0.2,
        "has_exit_time": False,
    },
    {
        "from": "Run",
        "to": "Walk",
        "conditions": [{"param": "speed", "mode": "Less", "threshold": 0.6}],
        "duration": 0.2,
        "has_exit_time": False,
    },
    {
        "from": "Any",
        "to": "Attack",
        "conditions": [{"param": "attackTrigger", "mode": "Trigger"}],
        "duration": 0.1,
        "has_exit_time": False,
    },
    {
        "from": "Attack",
        "to": "Idle",
        "conditions": [],
        "duration": 0.25,
        "has_exit_time": True,
        "exit_time": 0.9,
    },
]


# ---------------------------------------------------------------------------
# Layer manager presets
# ---------------------------------------------------------------------------

_LAYER_PRESETS: dict[str, dict[str, Any]] = {
    "WalkCast": {
        "description": "Upper body casting while walking",
        "layers": {"UpperBody": 1.0, "BaseLocomotion": 1.0},
    },
    "IdleLook": {
        "description": "Additive look-around on idle",
        "layers": {"HeadLook": 0.8},
    },
    "RunGuard": {
        "description": "Shield guard layer active while running",
        "layers": {"GuardPose": 0.6, "BaseLocomotion": 1.0},
    },
    "AnyHitReaction": {
        "description": "Additive hit reaction on any state",
        "layers": {"HitReaction": 1.0},
    },
}

# ---------------------------------------------------------------------------
# Default multi-hit events
# ---------------------------------------------------------------------------

_DEFAULT_HIT_EVENTS: list[dict[str, Any]] = [
    {"frame": 8, "hit_index": 0, "brand": "IRON", "damage_type": "slash",
     "vfx_intensity": 0.8},
    {"frame": 16, "hit_index": 1, "brand": "SAVAGE", "damage_type": "pierce",
     "vfx_intensity": 1.0},
    {"frame": 24, "hit_index": 2, "brand": "SURGE", "damage_type": "slam",
     "vfx_intensity": 1.2},
]


# ---------------------------------------------------------------------------
# G14: AnimatorController with proper transitions
# ---------------------------------------------------------------------------

def _add_animator_parameters(
    lines: list[str], parameters: list[dict[str, str]],
) -> None:
    """Add animator parameters to the C# code generation."""
    for param in parameters:
        pname = sanitize_cs_string(param["name"])
        ptype = param.get("type", "Float")
        type_map = {
            "Float": "Float",
            "Int": "Int",
            "Bool": "Bool",
            "Trigger": "Trigger",
        }
        cs_type = type_map.get(ptype, "Float")
        lines.append(f'            controller.AddParameter("{pname}", AnimatorControllerParameterType.{cs_type});')
    lines.append("")


def _add_animator_states(
    lines: list[str],
    states: list[dict[str, Any]],
    safe_name_str: str,
) -> dict[str, str]:
    """Add animator states and return state variable mapping."""
    state_var_map: dict[str, str] = {}
    for i, state in enumerate(states):
        sname = state["name"]
        safe_sname = sanitize_cs_identifier(sname)
        var_name = f"state_{safe_sname}"
        state_var_map[sname] = var_name
        motion_path = state.get("motion_path", "")

        x_pos = 250 + (i % 3) * 250
        y_pos = 100 + (i // 3) * 80
        lines.append(f'            var {var_name} = rootSM.AddState("{sanitize_cs_string(sname)}", new Vector3({x_pos}, {y_pos}, 0));')
        if motion_path:
            lines.append(f'            var clip_{safe_sname} = AssetDatabase.LoadAssetAtPath<AnimationClip>("{sanitize_cs_string(motion_path)}");')
            lines.append(f"            if (clip_{safe_sname} != null) {var_name}.motion = clip_{safe_sname};")
        if i == 0:
            lines.append(f"            rootSM.defaultState = {var_name};")
    lines.append("")
    return state_var_map


def _add_transition_conditions(
    lines: list[str], trans_var: str, conditions: list[dict[str, Any]],
) -> None:
    """Add transition conditions to the C# code generation."""
    for cond in conditions:
        cparam = sanitize_cs_string(cond["param"])
        cmode = cond.get("mode", "Greater")
        cthreshold = cond.get("threshold", 0.0)

        if cmode == "Trigger":
            lines.append(f'            {trans_var}.AddCondition(AnimatorConditionMode.If, 0f, "{cparam}");')
        elif cmode == "Greater":
            lines.append(f'            {trans_var}.AddCondition(AnimatorConditionMode.Greater, {cthreshold}f, "{cparam}");')
        elif cmode == "Less":
            lines.append(f'            {trans_var}.AddCondition(AnimatorConditionMode.Less, {cthreshold}f, "{cparam}");')
        elif cmode == "Equals":
            lines.append(f'            {trans_var}.AddCondition(AnimatorConditionMode.Equals, {cthreshold}f, "{cparam}");')
        elif cmode == "NotEqual":
            lines.append(f'            {trans_var}.AddCondition(AnimatorConditionMode.NotEqual, {cthreshold}f, "{cparam}");')
        elif cmode == "IfTrue":
            lines.append(f'            {trans_var}.AddCondition(AnimatorConditionMode.If, 0f, "{cparam}");')
        elif cmode == "IfFalse":
            lines.append(f'            {trans_var}.AddCondition(AnimatorConditionMode.IfNot, 0f, "{cparam}");')


def _add_animator_transitions(
    lines: list[str],
    transitions: list[dict[str, Any]],
    state_var_map: dict[str, str],
) -> None:
    """Add animator transitions to the C# code generation."""
    for t_idx, trans in enumerate(transitions):
        from_state = trans["from"]
        to_state = trans["to"]
        conditions = trans.get("conditions", [])
        duration = trans.get("duration", 0.25)
        has_exit_time = trans.get("has_exit_time", False)
        exit_time = trans.get("exit_time", 1.0)

        to_var = state_var_map.get(to_state)
        if to_var is None:
            continue

        trans_var = f"trans_{t_idx}"

        if from_state == "Any":
            lines.append(f"            // Transition: AnyState -> {sanitize_cs_string(to_state)}")
            lines.append(f"            var {trans_var} = rootSM.AddAnyStateTransition({to_var});")
        else:
            from_var = state_var_map.get(from_state)
            if from_var is None:
                continue
            lines.append(f"            // Transition: {sanitize_cs_string(from_state)} -> {sanitize_cs_string(to_state)}")
            lines.append(f"            var {trans_var} = {from_var}.AddTransition({to_var});")

        lines.append(f"            {trans_var}.duration = {duration}f;")
        lines.append(f"            {trans_var}.hasExitTime = {str(has_exit_time).lower()};")
        if has_exit_time:
            lines.append(f"            {trans_var}.exitTime = {exit_time}f;")
        lines.append(f"            {trans_var}.hasFixedDuration = true;")

        _add_transition_conditions(lines, trans_var, conditions)
        lines.append("")


def generate_animator_with_transitions_script(
    controller_name: str = "VB_CombatAnimator",
    states: list[dict[str, Any]] | None = None,
    transitions: list[dict[str, Any]] | None = None,
    parameters: list[dict[str, str]] | None = None,
) -> str:
    """Generate C# editor script that creates an AnimatorController with transitions.

    Unlike the basic blend tree generator, this creates a full state machine
    with explicit AnimatorStateTransition objects, conditions (Greater, Less,
    Equals, NotEqual, Trigger), exit times, and durations.

    Args:
        controller_name: Name for the AnimatorController asset.
        states: List of state dicts with ``name`` and optional ``motion_path``.
            Defaults to Idle/Walk/Run/Attack.
        transitions: List of transition dicts with ``from``, ``to``,
            ``conditions`` list, ``duration``, ``has_exit_time``, ``exit_time``.
            "from" can be "Any" for AnyState transitions.
        parameters: List of parameter dicts with ``name`` and ``type``
            (Float, Int, Bool, Trigger). Defaults to speed + attackTrigger.

    Returns:
        Complete C# source string.
    """
    if states is None:
        states = _DEFAULT_STATES
    if transitions is None:
        transitions = _DEFAULT_TRANSITIONS
    if parameters is None:
        parameters = _DEFAULT_PARAMETERS

    safe_name = sanitize_cs_identifier(
        controller_name.replace(" ", "_").replace("-", "_"),
    )
    safe_name_str = sanitize_cs_string(controller_name)

    lines: list[str] = []

    # -- Usings --
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using UnityEditor.Animations;")
    lines.append("using System.IO;")
    lines.append("")
    lines.append(f"public static class VeilBreakers_AnimatorTransitions_{safe_name}")
    lines.append("{")
    lines.append(f'    [MenuItem("VeilBreakers/Animation/Create Animator/{safe_name_str}")]')
    lines.append("    public static void Execute()")
    lines.append("    {")
    lines.append("        try")
    lines.append("        {")

    # -- Create controller asset --
    lines.append(f'            string controllerPath = "Assets/Animations/{safe_name_str}.controller";')
    lines.append('            string dir = Path.GetDirectoryName(controllerPath);')
    lines.append("            if (!AssetDatabase.IsValidFolder(dir))")
    lines.append("            {")
    lines.append('                Directory.CreateDirectory(Path.Combine(Application.dataPath, "..", dir));')
    lines.append("                AssetDatabase.Refresh();")
    lines.append("            }")
    lines.append("")
    lines.append("            var controller = AnimatorController.CreateAnimatorControllerAtPath(controllerPath);")
    lines.append("            var rootSM = controller.layers[0].stateMachine;")
    lines.append("")

    # -- Add parameters --
    _add_animator_parameters(lines, parameters)

    # -- Create states --
    state_var_map = _add_animator_states(lines, states, safe_name_str)

    # -- Create transitions --
    _add_animator_transitions(lines, transitions, state_var_map)

    # -- Save and result --
    lines.append("            AssetDatabase.SaveAssets();")
    lines.append("")

    state_count = len(states)
    trans_count = len(transitions)
    param_count = len(parameters)
    lines.append(
        '            string json = "{\\"status\\":\\"success\\",\\"action\\":\\"animator_transitions\\",'
        f'\\"controller\\":\\"" + controllerPath + "\\",\\"states\\":{state_count},'
        f'\\"transitions\\":{trans_count},\\"parameters\\":{param_count}}}";',
    )
    lines.append('            File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(
        '            Debug.Log("[VeilBreakers] AnimatorController created with '
        f'{state_count} states and {trans_count} transitions: " + controllerPath);',
    )

    # -- Catch --
    lines.append("        }")
    lines.append("        catch (System.Exception ex)")
    lines.append("        {")
    lines.append(
        '            string json = "{\\"status\\":\\"error\\",\\"action\\":\\"animator_transitions\\",'
        '\\"message\\":\\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}";',
    )
    lines.append('            File.WriteAllText("Temp/vb_result.json", json);')
    lines.append('            Debug.LogError("[VeilBreakers] AnimatorController creation failed: " + ex.Message);')
    lines.append("        }")
    lines.append("    }")
    lines.append("}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# P5-Q8: Runtime animation layer manager
# ---------------------------------------------------------------------------

def generate_animation_layer_manager_script(
    class_name: str = "AnimationLayerManager",
    presets: dict[str, dict[str, Any]] | None = None,
    namespace: str = "VeilBreakers.Animation",
    output_dir: str = "Assets/Scripts/Animation",
) -> dict[str, Any]:
    """Generate a runtime animation layer weight manager MonoBehaviour.

    Creates an AnimationLayerManager that:
    - Discovers Animator layers at Awake via layer name lookup
    - Blends layer weights using PrimeTween for smooth transitions
    - Provides named presets (WalkCast, IdleLook, RunGuard, AnyHitReaction)
    - API: SetLayerActive, SetLayerInactive, ActivatePreset, DeactivatePreset

    Args:
        class_name: Name for the MonoBehaviour class.
        presets: Override preset definitions. Defaults to built-in presets.
        namespace: C# namespace.
        output_dir: Where to write the script in the Unity project.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    if presets is None:
        presets = _LAYER_PRESETS

    safe_class = sanitize_cs_identifier(class_name)

    lines: list[str] = []

    # -- Usings --
    lines.append("using UnityEngine;")
    lines.append("using PrimeTween;")
    lines.append("using System;")
    lines.append("using System.Collections.Generic;")
    lines.append("")

    # -- Namespace --
    indent = ""
    if namespace:
        ns_safe = "".join(c for c in namespace if c.isalnum() or c in "._")
        lines.append(f"namespace {ns_safe}")
        lines.append("{")
        indent = "    "

    # -- Preset enum --
    preset_names = list(presets.keys())
    enum_entries = ", ".join(sanitize_cs_identifier(n) for n in preset_names)
    lines.append(f"{indent}/// <summary>Named layer blend presets.</summary>")
    lines.append(f"{indent}public enum LayerPreset")
    lines.append(f"{indent}{{")
    lines.append(f"{indent}    {enum_entries}")
    lines.append(f"{indent}}}")
    lines.append("")

    # -- Class --
    lines.append(f"{indent}/// <summary>")
    lines.append(f"{indent}/// Runtime animation layer weight manager.")
    lines.append(f"{indent}/// Blends Animator layer weights via PrimeTween and provides named presets.")
    lines.append(f"{indent}/// </summary>")
    lines.append(f"{indent}public class {safe_class} : MonoBehaviour")
    lines.append(f"{indent}{{")

    # -- Fields --
    lines.append(f"{indent}    [Header(\"References\")]")
    lines.append(f"{indent}    [SerializeField] private Animator animator;")
    lines.append("")
    lines.append(f"{indent}    [Header(\"Blend Settings\")]")
    lines.append(f"{indent}    [SerializeField] private float blendDuration = 0.3f;")
    lines.append(f"{indent}    [SerializeField] private Ease blendEase = Ease.InOutQuad;")
    lines.append("")

    # -- Private state --
    lines.append(f"{indent}    private Dictionary<string, int> layerIndexCache = new Dictionary<string, int>();")
    lines.append(f"{indent}    private Dictionary<string, Tween> activeTweens = new Dictionary<string, Tween>();")
    lines.append(f"{indent}    private HashSet<LayerPreset> activePresets = new HashSet<LayerPreset>();")
    lines.append("")

    # -- Awake --
    lines.append(f"{indent}    private void Awake()")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        if (animator == null)")
    lines.append(f"{indent}            animator = GetComponent<Animator>();")
    lines.append("")
    lines.append(f"{indent}        if (animator == null)")
    lines.append(f"{indent}        {{")
    lines.append(f'{indent}            Debug.LogError("[VeilBreakers] AnimationLayerManager: No Animator found on " + gameObject.name);')
    lines.append(f"{indent}            return;")
    lines.append(f"{indent}        }}")
    lines.append("")
    lines.append(f"{indent}        // Cache layer name -> index mapping")
    lines.append(f"{indent}        for (int i = 0; i < animator.layerCount; i++)")
    lines.append(f"{indent}        {{")
    lines.append(f"{indent}            string layerName = animator.GetLayerName(i);")
    lines.append(f"{indent}            layerIndexCache[layerName] = i;")
    lines.append(f"{indent}        }}")
    lines.append(f"{indent}    }}")
    lines.append("")

    # -- SetLayerActive --
    lines.append(f"{indent}    /// <summary>Blend a layer to a target weight over time.</summary>")
    lines.append(f"{indent}    public void SetLayerActive(string layerName, float targetWeight = 1.0f, float duration = -1f)")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        if (duration < 0f) duration = blendDuration;")
    lines.append(f"{indent}        if (animator == null || !layerIndexCache.TryGetValue(layerName, out int layerIndex))")
    lines.append(f"{indent}        {{")
    lines.append(f'{indent}            Debug.LogWarning("[VeilBreakers] AnimationLayerManager: Layer not found: " + layerName);')
    lines.append(f"{indent}            return;")
    lines.append(f"{indent}        }}")
    lines.append("")
    lines.append(f"{indent}        StopTweenForLayer(layerName);")
    lines.append("")
    lines.append(f"{indent}        float current = animator.GetLayerWeight(layerIndex);")
    lines.append(f"{indent}        if (Mathf.Approximately(current, targetWeight)) return;")
    lines.append("")
    lines.append(f"{indent}        var tween = Tween.Custom(")
    lines.append(f"{indent}            current,")
    lines.append(f"{indent}            targetWeight,")
    lines.append(f"{indent}            duration,")
    lines.append(f"{indent}            val => animator.SetLayerWeight(layerIndex, val),")
    lines.append(f"{indent}            blendEase")
    lines.append(f"{indent}        );")
    lines.append(f"{indent}        activeTweens[layerName] = tween;")
    lines.append(f"{indent}    }}")
    lines.append("")

    # -- SetLayerInactive --
    lines.append(f"{indent}    /// <summary>Blend a layer weight to 0 over time.</summary>")
    lines.append(f"{indent}    public void SetLayerInactive(string layerName, float duration = -1f)")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        SetLayerActive(layerName, 0f, duration);")
    lines.append(f"{indent}    }}")
    lines.append("")

    # -- ActivatePreset --
    lines.append(f"{indent}    /// <summary>Activate a named layer preset, blending all its layers to target weights.</summary>")
    lines.append(f"{indent}    public void ActivatePreset(LayerPreset preset, float duration = -1f)")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        if (duration < 0f) duration = blendDuration;")
    lines.append(f"{indent}        activePresets.Add(preset);")
    lines.append("")
    lines.append(f"{indent}        switch (preset)")
    lines.append(f"{indent}        {{")
    for pname, pdata in presets.items():
        safe_pname = sanitize_cs_identifier(pname)
        layers = pdata.get("layers", {})
        lines.append(f"{indent}            case LayerPreset.{safe_pname}:")
        for layer_name, weight in layers.items():
            safe_lname = sanitize_cs_string(layer_name)
            lines.append(f'{indent}                SetLayerActive("{safe_lname}", {weight}f, duration);')
        lines.append(f"{indent}                break;")
    lines.append(f"{indent}        }}")
    lines.append(f"{indent}    }}")
    lines.append("")

    # -- DeactivatePreset --
    lines.append(f"{indent}    /// <summary>Deactivate a named layer preset, blending all its layers to 0.</summary>")
    lines.append(f"{indent}    public void DeactivatePreset(LayerPreset preset, float duration = -1f)")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        if (duration < 0f) duration = blendDuration;")
    lines.append(f"{indent}        activePresets.Remove(preset);")
    lines.append("")
    lines.append(f"{indent}        switch (preset)")
    lines.append(f"{indent}        {{")
    for pname, pdata in presets.items():
        safe_pname = sanitize_cs_identifier(pname)
        layers = pdata.get("layers", {})
        lines.append(f"{indent}            case LayerPreset.{safe_pname}:")
        for layer_name in layers:
            safe_lname = sanitize_cs_string(layer_name)
            lines.append(f'{indent}                SetLayerInactive("{safe_lname}", duration);')
        lines.append(f"{indent}                break;")
    lines.append(f"{indent}        }}")
    lines.append(f"{indent}    }}")
    lines.append("")

    # -- DeactivateAll --
    lines.append(f"{indent}    /// <summary>Deactivate all active presets.</summary>")
    lines.append(f"{indent}    public void DeactivateAll(float duration = -1f)")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        var copy = new List<LayerPreset>(activePresets);")
    lines.append(f"{indent}        foreach (var preset in copy)")
    lines.append(f"{indent}            DeactivatePreset(preset, duration);")
    lines.append(f"{indent}    }}")
    lines.append("")

    # -- IsPresetActive --
    lines.append(f"{indent}    /// <summary>Check if a preset is currently active.</summary>")
    lines.append(f"{indent}    public bool IsPresetActive(LayerPreset preset)")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        return activePresets.Contains(preset);")
    lines.append(f"{indent}    }}")
    lines.append("")

    # -- GetLayerWeight --
    lines.append(f"{indent}    /// <summary>Get the current weight of a layer by name.</summary>")
    lines.append(f"{indent}    public float GetLayerWeight(string layerName)")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        if (animator != null && layerIndexCache.TryGetValue(layerName, out int idx))")
    lines.append(f"{indent}            return animator.GetLayerWeight(idx);")
    lines.append(f"{indent}        return 0f;")
    lines.append(f"{indent}    }}")
    lines.append("")

    # -- StopTweenForLayer (private) --
    lines.append(f"{indent}    private void StopTweenForLayer(string layerName)")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        if (activeTweens.TryGetValue(layerName, out Tween tween))")
    lines.append(f"{indent}        {{")
    lines.append(f"{indent}            tween.Stop();")
    lines.append(f"{indent}            activeTweens.Remove(layerName);")
    lines.append(f"{indent}        }}")
    lines.append(f"{indent}    }}")
    lines.append("")

    # -- OnDestroy --
    lines.append(f"{indent}    private void OnDestroy()")
    lines.append(f"{indent}    {{")
    lines.append(f"{indent}        foreach (var kvp in activeTweens)")
    lines.append(f"{indent}            kvp.Value.Stop();")
    lines.append(f"{indent}        activeTweens.Clear();")
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
            "Attach AnimationLayerManager to your character GameObject",
            "Ensure Animator component with named layers is present",
            "Call ActivatePreset(LayerPreset.WalkCast) etc. from gameplay code",
        ],
    }


# ---------------------------------------------------------------------------
# Multi-hit AnimationEvent bridge
# ---------------------------------------------------------------------------

def generate_multi_hit_events_script(
    clip_name: str = "VB_ComboAttack",
    hit_events: list[dict[str, Any]] | None = None,
    frame_rate: float = 30.0,
) -> str:
    """Generate C# editor script that adds multi-hit AnimationEvents to a clip.

    Creates AnimationEvent entries at specified frames with OnCombatHit as the
    function name.  Each event encodes brand and damage_type in the
    stringParameter as ``"brand|damage_type"`` and hit_index + vfx_intensity
    in intParameter and floatParameter respectively.

    Args:
        clip_name: Name of the animation clip asset to modify.
        hit_events: List of hit event dicts with ``frame``, ``hit_index``,
            ``brand``, ``damage_type``, ``vfx_intensity``.
            Defaults to a 3-hit combo at frames 8, 16, 24.
        frame_rate: Frame rate for converting frame numbers to time.

    Returns:
        Complete C# source string.
    """
    if hit_events is None:
        hit_events = _DEFAULT_HIT_EVENTS

    safe_name = sanitize_cs_identifier(
        clip_name.replace(" ", "_").replace("-", "_"),
    )
    safe_name_str = sanitize_cs_string(clip_name)

    lines: list[str] = []

    # -- Usings --
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using System.IO;")
    lines.append("using System.Collections.Generic;")
    lines.append("")
    lines.append(f"public static class VeilBreakers_MultiHitEvents_{safe_name}")
    lines.append("{")
    lines.append(f'    [MenuItem("VeilBreakers/Animation/Add Multi-Hit Events/{safe_name_str}")]')
    lines.append("    public static void Execute()")
    lines.append("    {")
    lines.append("        try")
    lines.append("        {")

    # -- Find the clip --
    lines.append('            // Find the animation clip by name')
    lines.append(f'            string[] guids = AssetDatabase.FindAssets("t:AnimationClip {safe_name_str}");')
    lines.append("            AnimationClip clip = null;")
    lines.append("            foreach (string guid in guids)")
    lines.append("            {")
    lines.append("                string path = AssetDatabase.GUIDToAssetPath(guid);")
    lines.append("                var candidate = AssetDatabase.LoadAssetAtPath<AnimationClip>(path);")
    lines.append(f'                if (candidate != null && candidate.name == "{safe_name_str}")')
    lines.append("                {")
    lines.append("                    clip = candidate;")
    lines.append("                    break;")
    lines.append("                }")
    lines.append("            }")
    lines.append("")
    lines.append("            // If not found, create a placeholder clip")
    lines.append("            if (clip == null)")
    lines.append("            {")
    lines.append('                string animDir = "Assets/Animations/Clips";')
    lines.append("                if (!AssetDatabase.IsValidFolder(animDir))")
    lines.append("                {")
    lines.append('                    if (!AssetDatabase.IsValidFolder("Assets/Animations"))')
    lines.append('                        AssetDatabase.CreateFolder("Assets", "Animations");')
    lines.append('                    AssetDatabase.CreateFolder("Assets/Animations", "Clips");')
    lines.append("                }")
    lines.append(f'                clip = new AnimationClip {{ name = "{safe_name_str}" }};')
    lines.append(f'                AssetDatabase.CreateAsset(clip, animDir + "/{safe_name_str}.anim");')
    lines.append("            }")
    lines.append("")

    # -- Build events list --
    lines.append("            // Build multi-hit animation events")
    lines.append("            var events = new List<AnimationEvent>();")
    lines.append("")

    for i, evt in enumerate(hit_events):
        frame = evt.get("frame", 0)
        hit_index = evt.get("hit_index", i)
        brand = sanitize_cs_string(str(evt.get("brand", "IRON")))
        damage_type = sanitize_cs_string(str(evt.get("damage_type", "slash")))
        vfx_intensity = evt.get("vfx_intensity", 1.0)
        time_value = frame / frame_rate

        lines.append(f"            // Hit {hit_index}: frame {frame} ({time_value:.4f}s) - {brand}|{damage_type}")
        lines.append("            events.Add(new AnimationEvent")
        lines.append("            {")
        lines.append(f"                time = {time_value:.4f}f,")
        lines.append('                functionName = "OnCombatHit",')
        lines.append(f'                stringParameter = "{brand}|{damage_type}",')
        lines.append(f"                intParameter = {hit_index},")
        lines.append(f"                floatParameter = {vfx_intensity}f")
        lines.append("            });")
        lines.append("")

    # -- Apply events --
    lines.append("            AnimationUtility.SetAnimationEvents(clip, events.ToArray());")
    lines.append("            EditorUtility.SetDirty(clip);")
    lines.append("            AssetDatabase.SaveAssets();")
    lines.append("")

    # -- Result JSON --
    event_count = len(hit_events)
    lines.append(
        '            string clipPath = AssetDatabase.GetAssetPath(clip);',
    )
    lines.append(
        f'            string json = "{{\\"status\\":\\"success\\",\\"action\\":\\"multi_hit_events\\",'
        f'\\"clip_name\\":\\"{safe_name_str}\\",\\"event_count\\":{event_count},'
        f'\\"clip_path\\":\\"" + clipPath.Replace("\\\\", "/") + "\\"}}";',
    )
    lines.append('            File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(
        f'            Debug.Log("[VeilBreakers] Added {event_count} multi-hit events to clip: '
        f'{safe_name_str} (" + clipPath + ")");',
    )

    # -- Catch --
    lines.append("        }")
    lines.append("        catch (System.Exception ex)")
    lines.append("        {")
    lines.append(
        '            string json = "{\\"status\\":\\"error\\",\\"action\\":\\"multi_hit_events\\",'
        '\\"message\\":\\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}";',
    )
    lines.append('            File.WriteAllText("Temp/vb_result.json", json);')
    lines.append('            Debug.LogError("[VeilBreakers] Multi-hit event creation failed: " + ex.Message);')
    lines.append("        }")
    lines.append("    }")
    lines.append("}")

    return "\n".join(lines)
