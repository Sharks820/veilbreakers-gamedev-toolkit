"""Animation C# template generators for Unity blend trees and additive layers.

Each function returns a complete C# source string that can be written to
a Unity project's Assets/Editor/Generated/Animation/ directory. When compiled
by Unity, the scripts register as MenuItem commands under
"VeilBreakers/Animation/...".

All generated scripts write their result to Temp/vb_result.json so that
the Python MCP server can read back the outcome after execution.

Exports:
    generate_blend_tree_script          -- ANIM3-03: Directional/speed blend trees
    generate_additive_layer_script      -- ANIM3-04: Additive animation layers
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
    result = re.sub(r"[^a-zA-Z0-9_]", "", value)
    if not result:
        return "_unnamed"
    if result[0].isdigit():
        result = "_" + result
    return result


# ---------------------------------------------------------------------------
# ANIM3-03: Blend tree generation
# ---------------------------------------------------------------------------

# 8-way directional states for movement blend trees
_DIRECTIONAL_8WAY_POSITIONS: list[dict[str, Any]] = [
    {"name": "Idle",      "x":  0.0, "y":  0.0},
    {"name": "Forward",   "x":  0.0, "y":  1.0},
    {"name": "Backward",  "x":  0.0, "y": -1.0},
    {"name": "Left",      "x": -1.0, "y":  0.0},
    {"name": "Right",     "x":  1.0, "y":  0.0},
    {"name": "ForwardL",  "x": -0.7, "y":  0.7},
    {"name": "ForwardR",  "x":  0.7, "y":  0.7},
    {"name": "BackwardL", "x": -0.7, "y": -0.7},
    {"name": "BackwardR", "x":  0.7, "y": -0.7},
]

# Speed blend thresholds
_SPEED_THRESHOLDS: list[dict[str, Any]] = [
    {"name": "Idle",   "threshold": 0.0},
    {"name": "Walk",   "threshold": 0.5},
    {"name": "Run",    "threshold": 1.0},
    {"name": "Sprint", "threshold": 1.5},
]


def generate_blend_tree_script(
    blend_type: str = "directional_8way",
    controller_name: str = "VB_Locomotion",
    states: list[dict[str, str]] | None = None,
    parameters: list[dict[str, str]] | None = None,
    motion_clips: dict[str, str] | None = None,
) -> str:
    """Generate C# editor script for Animator blend tree setup.

    Creates an AnimatorController with a blend tree root state configured
    for one of three blend types:
      - directional_8way: 2D Freeform Directional with moveX/moveY
      - speed_blend: 1D blend by speed parameter (Idle->Walk->Run->Sprint)
      - directional_speed: Combined 2D Freeform Cartesian (moveX, moveY + speed)

    Args:
        blend_type: Type of blend tree to create.
        controller_name: Name for the AnimatorController asset.
        states: Optional list of state dicts with "name" and "motion_path".
            If None, default states for the blend_type are used.
        parameters: Optional list of param dicts with "name" and "type".
            If None, default parameters for the blend_type are used.
        motion_clips: Optional dict mapping state names to clip paths.

    Returns:
        Complete C# source string.

    Raises:
        ValueError: If blend_type is unknown.
    """
    valid_types = ("directional_8way", "speed_blend", "directional_speed")
    if blend_type not in valid_types:
        raise ValueError(
            f"Unknown blend_type: {blend_type!r}. Valid: {valid_types}"
        )

    safe_name = _sanitize_cs_identifier(controller_name.replace(" ", "_").replace("-", "_"))
    safe_name_str = _sanitize_cs_string(controller_name)

    if motion_clips is None:
        motion_clips = {}

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using UnityEditor.Animations;")
    lines.append("using System.IO;")
    lines.append("")
    lines.append(f"public static class VeilBreakers_BlendTree_{safe_name}")
    lines.append("{")
    lines.append(f'    [MenuItem("VeilBreakers/Animation/Create Blend Tree/{safe_name_str}")]')
    lines.append("    public static void Execute()")
    lines.append("    {")
    lines.append("        try")
    lines.append("        {")

    # Create controller
    lines.append(f'            string controllerPath = "Assets/Animations/{safe_name_str}.controller";')
    lines.append('            string dir = Path.GetDirectoryName(controllerPath);')
    lines.append('            if (!AssetDatabase.IsValidFolder(dir))')
    lines.append("            {")
    lines.append('                Directory.CreateDirectory(Path.Combine(Application.dataPath, "..", dir));')
    lines.append("                AssetDatabase.Refresh();")
    lines.append("            }")
    lines.append("")
    lines.append("            var controller = AnimatorController.CreateAnimatorControllerAtPath(controllerPath);")
    lines.append("")

    # Add parameters based on blend type
    if blend_type == "directional_8way":
        lines.append('            controller.AddParameter("moveX", AnimatorControllerParameterType.Float);')
        lines.append('            controller.AddParameter("moveY", AnimatorControllerParameterType.Float);')
        lines.append("")
        lines.append("            // Create 2D Freeform Directional blend tree")
        lines.append("            BlendTree blendTree;")
        lines.append(f'            controller.CreateBlendTreeInController("{safe_name_str}", out blendTree);')
        lines.append("            blendTree.blendType = BlendTreeType.FreeformDirectional2D;")
        lines.append('            blendTree.blendParameter = "moveX";')
        lines.append('            blendTree.blendParameterY = "moveY";')
        lines.append("")

        # Add 8-way positions
        positions = _DIRECTIONAL_8WAY_POSITIONS
        if states:
            # Use custom states but keep positions
            for i, state in enumerate(states):
                sname = state.get("name", f"State_{i}")
                clip_path = motion_clips.get(sname, state.get("motion_path", ""))
                pos = positions[i] if i < len(positions) else {"x": 0.0, "y": 0.0}
                safe_sname = _sanitize_cs_identifier(sname)
                if clip_path:
                    lines.append(f'            var clip_{safe_sname} = AssetDatabase.LoadAssetAtPath<AnimationClip>("{_sanitize_cs_string(clip_path)}");')
                    lines.append(f"            if (clip_{safe_sname} != null)")
                    lines.append(f"                blendTree.AddChild(clip_{safe_sname}, new Vector2({pos['x']}f, {pos['y']}f));")
                    lines.append(f"            else")
                    lines.append(f'                blendTree.AddChild(new AnimationClip {{ name = "{_sanitize_cs_string(sname)}" }}, new Vector2({pos["x"]}f, {pos["y"]}f));')
                else:
                    lines.append(f'            blendTree.AddChild(new AnimationClip {{ name = "{_sanitize_cs_string(sname)}" }}, new Vector2({pos["x"]}f, {pos["y"]}f));')
        else:
            for pos in positions:
                pname = pos["name"]
                clip_path = motion_clips.get(pname, "")
                safe_pname = _sanitize_cs_identifier(pname)
                if clip_path:
                    lines.append(f'            var clip_{safe_pname} = AssetDatabase.LoadAssetAtPath<AnimationClip>("{_sanitize_cs_string(clip_path)}");')
                    lines.append(f"            if (clip_{safe_pname} != null)")
                    lines.append(f"                blendTree.AddChild(clip_{safe_pname}, new Vector2({pos['x']}f, {pos['y']}f));")
                    lines.append(f"            else")
                    lines.append(f'                blendTree.AddChild(new AnimationClip {{ name = "{_sanitize_cs_string(pname)}" }}, new Vector2({pos["x"]}f, {pos["y"]}f));')
                else:
                    lines.append(f'            blendTree.AddChild(new AnimationClip {{ name = "{_sanitize_cs_string(pname)}" }}, new Vector2({pos["x"]}f, {pos["y"]}f));')

    elif blend_type == "speed_blend":
        lines.append('            controller.AddParameter("speed", AnimatorControllerParameterType.Float);')
        lines.append("")
        lines.append("            // Create 1D speed blend tree")
        lines.append("            BlendTree blendTree;")
        lines.append(f'            controller.CreateBlendTreeInController("{safe_name_str}", out blendTree);')
        lines.append("            blendTree.blendType = BlendTreeType.Simple1D;")
        lines.append('            blendTree.blendParameter = "speed";')
        lines.append("")

        thresholds = _SPEED_THRESHOLDS
        if states:
            for i, state in enumerate(states):
                sname = state.get("name", f"Speed_{i}")
                clip_path = motion_clips.get(sname, state.get("motion_path", ""))
                thresh = thresholds[i]["threshold"] if i < len(thresholds) else float(i)
                safe_sname = _sanitize_cs_identifier(sname)
                if clip_path:
                    lines.append(f'            var clip_{safe_sname} = AssetDatabase.LoadAssetAtPath<AnimationClip>("{_sanitize_cs_string(clip_path)}");')
                    lines.append(f"            if (clip_{safe_sname} != null)")
                    lines.append(f"                blendTree.AddChild(clip_{safe_sname}, {thresh}f);")
                    lines.append(f"            else")
                    lines.append(f'                blendTree.AddChild(new AnimationClip {{ name = "{_sanitize_cs_string(sname)}" }}, {thresh}f);')
                else:
                    lines.append(f'            blendTree.AddChild(new AnimationClip {{ name = "{_sanitize_cs_string(sname)}" }}, {thresh}f);')
        else:
            for t in thresholds:
                tname = t["name"]
                clip_path = motion_clips.get(tname, "")
                safe_tname = _sanitize_cs_identifier(tname)
                if clip_path:
                    lines.append(f'            var clip_{safe_tname} = AssetDatabase.LoadAssetAtPath<AnimationClip>("{_sanitize_cs_string(clip_path)}");')
                    lines.append(f"            if (clip_{safe_tname} != null)")
                    lines.append(f'                blendTree.AddChild(clip_{safe_tname}, {t["threshold"]}f);')
                    lines.append(f"            else")
                    lines.append(f'                blendTree.AddChild(new AnimationClip {{ name = "{_sanitize_cs_string(tname)}" }}, {t["threshold"]}f);')
                else:
                    lines.append(f'            blendTree.AddChild(new AnimationClip {{ name = "{_sanitize_cs_string(tname)}" }}, {t["threshold"]}f);')

    elif blend_type == "directional_speed":
        lines.append('            controller.AddParameter("moveX", AnimatorControllerParameterType.Float);')
        lines.append('            controller.AddParameter("moveY", AnimatorControllerParameterType.Float);')
        lines.append('            controller.AddParameter("speed", AnimatorControllerParameterType.Float);')
        lines.append("")
        lines.append("            // Create 2D Freeform Cartesian blend tree for combined directional+speed")
        lines.append("            BlendTree blendTree;")
        lines.append(f'            controller.CreateBlendTreeInController("{safe_name_str}", out blendTree);')
        lines.append("            blendTree.blendType = BlendTreeType.FreeformCartesian2D;")
        lines.append('            blendTree.blendParameter = "moveX";')
        lines.append('            blendTree.blendParameterY = "moveY";')
        lines.append("")

        # For directional_speed, add all 8-way positions as children
        for pos in _DIRECTIONAL_8WAY_POSITIONS:
            pname = pos["name"]
            clip_path = motion_clips.get(pname, "")
            safe_pname = _sanitize_cs_identifier(pname)
            if clip_path:
                lines.append(f'            var clip_{safe_pname} = AssetDatabase.LoadAssetAtPath<AnimationClip>("{_sanitize_cs_string(clip_path)}");')
                lines.append(f"            if (clip_{safe_pname} != null)")
                lines.append(f"                blendTree.AddChild(clip_{safe_pname}, new Vector2({pos['x']}f, {pos['y']}f));")
                lines.append(f"            else")
                lines.append(f'                blendTree.AddChild(new AnimationClip {{ name = "{_sanitize_cs_string(pname)}" }}, new Vector2({pos["x"]}f, {pos["y"]}f));')
            else:
                lines.append(f'            blendTree.AddChild(new AnimationClip {{ name = "{_sanitize_cs_string(pname)}" }}, new Vector2({pos["x"]}f, {pos["y"]}f));')

    lines.append("")
    lines.append("            AssetDatabase.SaveAssets();")
    lines.append("")
    lines.append(f'            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"blend_tree\\", \\"blend_type\\": \\"{blend_type}\\", \\"controller\\": \\"" + controllerPath + "\\"}}";')
    lines.append('            File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(f'            Debug.Log("[VeilBreakers] Blend tree controller created: " + controllerPath);')
    lines.append("        }")
    lines.append("        catch (System.Exception ex)")
    lines.append("        {")
    lines.append('            string json = "{\\"status\\": \\"error\\", \\"action\\": \\"blend_tree\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}";')
    lines.append('            File.WriteAllText("Temp/vb_result.json", json);')
    lines.append('            Debug.LogError("[VeilBreakers] Blend tree creation failed: " + ex.Message);')
    lines.append("        }")
    lines.append("    }")
    lines.append("}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ANIM3-04: Additive animation layers
# ---------------------------------------------------------------------------

# Default layer configurations
_DEFAULT_ADDITIVE_LAYERS: list[dict[str, Any]] = [
    {
        "name": "HitReactions",
        "blend_mode": "Additive",
        "default_weight": 0.0,
        "weight_param": "hitReactionWeight",
        "avatar_mask": "upper_body",
        "states": [
            {"name": "NoReaction", "is_default": True},
            {"name": "HitFront", "motion_path": ""},
            {"name": "HitBack", "motion_path": ""},
            {"name": "HitLeft", "motion_path": ""},
            {"name": "HitRight", "motion_path": ""},
        ],
    },
    {
        "name": "Breathing",
        "blend_mode": "Additive",
        "default_weight": 1.0,
        "weight_param": "breathingWeight",
        "avatar_mask": "full_body",
        "states": [
            {"name": "IdleBreathing", "is_default": True, "motion_path": ""},
        ],
    },
]


def generate_additive_layer_script(
    controller_name: str = "VB_Combat",
    base_layer_name: str = "Locomotion",
    additive_layers: list[dict[str, Any]] | None = None,
    base_states: list[dict[str, str]] | None = None,
) -> str:
    """Generate C# editor script for additive animation layers.

    Creates an AnimatorController with a base locomotion layer and one or
    more additive layers. Each additive layer has:
    - Blend mode set to Additive
    - Weight controlled by a float parameter
    - Avatar mask (upper_body or full_body)
    - States with transitions

    Args:
        controller_name: Name for the AnimatorController asset.
        base_layer_name: Name for the base locomotion layer.
        additive_layers: List of layer config dicts. If None, uses default
            HitReactions + Breathing layers.
        base_states: Optional list of base layer states.

    Returns:
        Complete C# source string.
    """
    if additive_layers is None:
        additive_layers = _DEFAULT_ADDITIVE_LAYERS

    if base_states is None:
        base_states = [
            {"name": "Idle"},
            {"name": "Walk"},
            {"name": "Run"},
        ]

    safe_name = _sanitize_cs_identifier(controller_name.replace(" ", "_").replace("-", "_"))
    safe_name_str = _sanitize_cs_string(controller_name)
    safe_base_layer = _sanitize_cs_string(base_layer_name)

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using UnityEditor.Animations;")
    lines.append("using System.IO;")
    lines.append("")
    lines.append(f"public static class VeilBreakers_AdditiveLayers_{safe_name}")
    lines.append("{")
    lines.append(f'    [MenuItem("VeilBreakers/Animation/Create Additive Layers/{safe_name_str}")]')
    lines.append("    public static void Execute()")
    lines.append("    {")
    lines.append("        try")
    lines.append("        {")

    # Create controller
    lines.append(f'            string controllerPath = "Assets/Animations/{safe_name_str}.controller";')
    lines.append('            string dir = Path.GetDirectoryName(controllerPath);')
    lines.append('            if (!AssetDatabase.IsValidFolder(dir))')
    lines.append("            {")
    lines.append('                Directory.CreateDirectory(Path.Combine(Application.dataPath, "..", dir));')
    lines.append("                AssetDatabase.Refresh();")
    lines.append("            }")
    lines.append("")
    lines.append("            var controller = AnimatorController.CreateAnimatorControllerAtPath(controllerPath);")
    lines.append("")

    # Configure base layer
    lines.append(f'            // Base layer: {safe_base_layer} (Override, weight=1.0)')
    lines.append(f"            var allLayers = controller.layers;")
    lines.append(f'            allLayers[0].name = "{safe_base_layer}";')
    lines.append(f"            controller.layers = allLayers;")
    lines.append("            var baseSM = controller.layers[0].stateMachine;")
    lines.append("")

    # Add base states
    for i, state in enumerate(base_states):
        sname = _sanitize_cs_string(state["name"])
        safe_sname = _sanitize_cs_identifier(state["name"])
        motion_path = state.get("motion_path", "")
        lines.append(f'            var baseState_{safe_sname} = baseSM.AddState("{sname}");')
        if motion_path:
            lines.append(f'            var baseClip_{safe_sname} = AssetDatabase.LoadAssetAtPath<AnimationClip>("{_sanitize_cs_string(motion_path)}");')
            lines.append(f"            if (baseClip_{safe_sname} != null) baseState_{safe_sname}.motion = baseClip_{safe_sname};")

    lines.append("")

    # Add weight parameters for additive layers
    for layer in additive_layers:
        weight_param = layer.get("weight_param", f"{layer['name']}Weight")
        lines.append(f'            controller.AddParameter("{_sanitize_cs_string(weight_param)}", AnimatorControllerParameterType.Float);')
    lines.append("")

    # Add additive layers
    for layer_idx, layer in enumerate(additive_layers):
        layer_name = layer["name"]
        safe_layer = _sanitize_cs_string(layer_name)
        safe_layer_id = _sanitize_cs_identifier(layer_name)
        blend_mode = layer.get("blend_mode", "Additive")
        default_weight = layer.get("default_weight", 0.0)
        mask_type = layer.get("avatar_mask", "full_body")
        layer_states = layer.get("states", [])

        lines.append(f"            // Additive layer: {safe_layer}")
        lines.append(f"            controller.AddLayer(\"{safe_layer}\");")
        if layer_idx == 0:
            lines.append(f"            var additiveLayers = controller.layers;")
        else:
            lines.append(f"            additiveLayers = controller.layers;")
        lines.append(f"            var layer_{safe_layer_id} = additiveLayers[{layer_idx + 1}];")
        lines.append(f"            layer_{safe_layer_id}.defaultWeight = {default_weight}f;")

        if blend_mode == "Additive":
            lines.append(f"            layer_{safe_layer_id}.blendingMode = AnimatorLayerBlendingMode.Additive;")
        else:
            lines.append(f"            layer_{safe_layer_id}.blendingMode = AnimatorLayerBlendingMode.Override;")

        # Avatar mask
        lines.append(f"            // Create avatar mask for {safe_layer}")
        lines.append(f'            var mask_{safe_layer_id} = new AvatarMask();')

        if mask_type == "upper_body":
            lines.append(f"            // Upper body mask: enable head, arms, torso; disable legs")
            lines.append(f"            mask_{safe_layer_id}.SetHumanoidBodyPartActive(AvatarMaskBodyPart.Root, false);")
            lines.append(f"            mask_{safe_layer_id}.SetHumanoidBodyPartActive(AvatarMaskBodyPart.Body, true);")
            lines.append(f"            mask_{safe_layer_id}.SetHumanoidBodyPartActive(AvatarMaskBodyPart.Head, true);")
            lines.append(f"            mask_{safe_layer_id}.SetHumanoidBodyPartActive(AvatarMaskBodyPart.LeftLeg, false);")
            lines.append(f"            mask_{safe_layer_id}.SetHumanoidBodyPartActive(AvatarMaskBodyPart.RightLeg, false);")
            lines.append(f"            mask_{safe_layer_id}.SetHumanoidBodyPartActive(AvatarMaskBodyPart.LeftArm, true);")
            lines.append(f"            mask_{safe_layer_id}.SetHumanoidBodyPartActive(AvatarMaskBodyPart.RightArm, true);")
            lines.append(f"            mask_{safe_layer_id}.SetHumanoidBodyPartActive(AvatarMaskBodyPart.LeftFingers, true);")
            lines.append(f"            mask_{safe_layer_id}.SetHumanoidBodyPartActive(AvatarMaskBodyPart.RightFingers, true);")
            lines.append(f"            mask_{safe_layer_id}.SetHumanoidBodyPartActive(AvatarMaskBodyPart.LeftFootIK, false);")
            lines.append(f"            mask_{safe_layer_id}.SetHumanoidBodyPartActive(AvatarMaskBodyPart.RightFootIK, false);")
            lines.append(f"            mask_{safe_layer_id}.SetHumanoidBodyPartActive(AvatarMaskBodyPart.LeftHandIK, true);")
            lines.append(f"            mask_{safe_layer_id}.SetHumanoidBodyPartActive(AvatarMaskBodyPart.RightHandIK, true);")
        else:
            lines.append(f"            // Full body mask: enable all parts")
            lines.append(f"            for (int i = 0; i < (int)AvatarMaskBodyPart.LastBodyPart; i++)")
            lines.append(f"                mask_{safe_layer_id}.SetHumanoidBodyPartActive((AvatarMaskBodyPart)i, true);")

        lines.append(f"            layer_{safe_layer_id}.avatarMask = mask_{safe_layer_id};")
        lines.append(f"            additiveLayers[{layer_idx + 1}] = layer_{safe_layer_id};")
        lines.append(f"            controller.layers = additiveLayers;")
        lines.append("")

        # Add states to additive layer
        lines.append(f"            var sm_{safe_layer_id} = controller.layers[{layer_idx + 1}].stateMachine;")
        for si, state in enumerate(layer_states):
            sname = _sanitize_cs_string(state["name"])
            safe_sname = _sanitize_cs_identifier(state["name"])
            lines.append(f'            var state_{safe_layer_id}_{safe_sname} = sm_{safe_layer_id}.AddState("{sname}");')
            mpath = state.get("motion_path", "")
            if mpath:
                lines.append(f'            var clip_{safe_layer_id}_{safe_sname} = AssetDatabase.LoadAssetAtPath<AnimationClip>("{_sanitize_cs_string(mpath)}");')
                lines.append(f"            if (clip_{safe_layer_id}_{safe_sname} != null) state_{safe_layer_id}_{safe_sname}.motion = clip_{safe_layer_id}_{safe_sname};")
            if state.get("is_default", False):
                lines.append(f"            sm_{safe_layer_id}.defaultState = state_{safe_layer_id}_{safe_sname};")

        lines.append("")

    # Save and result
    lines.append("            AssetDatabase.SaveAssets();")
    lines.append("")

    layer_count = len(additive_layers) + 1  # +1 for base layer
    lines.append(f'            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"additive_layers\\", \\"controller\\": \\"" + controllerPath + "\\", \\"layer_count\\": {layer_count}}}";')
    lines.append('            File.WriteAllText("Temp/vb_result.json", json);')
    lines.append(f'            Debug.Log("[VeilBreakers] Additive layer controller created with {layer_count} layers: " + controllerPath);')
    lines.append("        }")
    lines.append("        catch (System.Exception ex)")
    lines.append("        {")
    lines.append('            string json = "{\\"status\\": \\"error\\", \\"action\\": \\"additive_layers\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}";')
    lines.append('            File.WriteAllText("Temp/vb_result.json", json);')
    lines.append('            Debug.LogError("[VeilBreakers] Additive layer creation failed: " + ex.Message);')
    lines.append("        }")
    lines.append("    }")
    lines.append("}")

    return "\n".join(lines)
