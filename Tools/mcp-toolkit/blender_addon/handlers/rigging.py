"""Rigging handlers for mesh analysis, template application, and custom rig building.

Provides three command handlers:
  - handle_analyze_for_rigging: Mesh proportion analysis and rig template recommendation (RIG-01)
  - handle_apply_rig_template: Apply a Rigify creature rig template to a mesh (RIG-02)
  - handle_build_custom_rig: Mix limb types from LIMB_LIBRARY into a custom rig (RIG-03)

Pure-logic functions (_analyze_proportions, _validate_custom_rig_config) are
separated for testability without Blender.
"""

from __future__ import annotations

import math

import bmesh
import bpy

from ._context import get_3d_context_override
from .rigging_templates import (
    LIMB_LIBRARY,
    TEMPLATE_CATALOG,
    _create_template_bones,
    _fix_deform_hierarchy,
    _generate_rig,
)


# ---------------------------------------------------------------------------
# Pure-logic helpers (testable without Blender)
# ---------------------------------------------------------------------------


def _analyze_proportions(
    bbox_dims: tuple[float, float, float],
    vertex_count: int,
    has_symmetry: bool,
) -> dict:
    """Analyze mesh proportions for rig template recommendation.

    Args:
        bbox_dims: (width, depth, height) bounding box dimensions.
        vertex_count: Total vertex count.
        has_symmetry: Whether mesh has X-axis symmetry.

    Returns:
        Dict with aspect_ratio, recommended_template, confidence,
        has_symmetry, vertex_count, all_candidates.
    """
    w, d, h = bbox_dims
    aspect = h / max(w, 0.001)

    candidates: list[dict] = []

    # Tall narrow mesh -> humanoid
    if aspect > 2.5 and has_symmetry:
        candidates.append({"template": "humanoid", "confidence": 0.8})
    elif aspect > 2.5:
        candidates.append({"template": "humanoid", "confidence": 0.6})

    # Flat wide mesh -> serpent
    if aspect < 0.5 and w > h:
        candidates.append({"template": "serpent", "confidence": 0.7})

    # Medium aspect with significant depth -> quadruped
    if 0.3 < aspect < 0.8 and d > w * 0.8:
        candidates.append({"template": "quadruped", "confidence": 0.7})
    elif 0.8 <= aspect <= 2.5 and d > w * 0.8 and has_symmetry:
        candidates.append({"template": "quadruped", "confidence": 0.6})

    # Wide with medium height and symmetry -> possible dragon/bird
    if 0.5 < aspect < 2.0 and w > d * 1.2 and has_symmetry:
        candidates.append({"template": "dragon", "confidence": 0.5})

    # Low profile with lots of width -> possible insect/arachnid
    if 0.3 < aspect < 1.2 and has_symmetry and w > d:
        candidates.append({"template": "insect", "confidence": 0.45})

    # Roughly spherical -> floating
    if 0.7 < aspect < 1.5 and abs(w - d) < max(w, d) * 0.3:
        candidates.append({"template": "floating", "confidence": 0.45})

    # Fallback -> amorphous
    if not candidates:
        candidates.append({"template": "amorphous", "confidence": 0.4})

    # Sort by confidence descending
    candidates.sort(key=lambda c: c["confidence"], reverse=True)

    best = candidates[0]
    return {
        "aspect_ratio": round(aspect, 2),
        "recommended_template": best["template"],
        "confidence": round(best["confidence"], 2),
        "has_symmetry": has_symmetry,
        "vertex_count": vertex_count,
        "all_candidates": candidates,
    }


def _validate_custom_rig_config(limb_types: list[str]) -> dict:
    """Validate a custom rig configuration against LIMB_LIBRARY.

    Args:
        limb_types: List of limb type strings to include in the rig.

    Returns:
        Dict with valid (bool), errors (list), limb_count (int),
        bone_estimate (int).
    """
    errors: list[str] = []
    bone_estimate = 0

    if not limb_types:
        errors.append("No limb types provided -- at least one required")
        return {
            "valid": False,
            "errors": errors,
            "limb_count": 0,
            "bone_estimate": 0,
        }

    # Validate each limb type exists
    for lt in limb_types:
        if lt not in LIMB_LIBRARY:
            errors.append(
                f"Unknown limb type: '{lt}'. "
                f"Valid types: {sorted(LIMB_LIBRARY.keys())}"
            )
        else:
            # Estimate bone count from the limb function
            try:
                bones = LIMB_LIBRARY[lt]()
                bone_estimate += len(bones)
            except TypeError:
                # Function might need arguments, estimate 6 bones per limb
                bone_estimate += 6

    # Check for conflicts: multiple spine-connected limbs of the same type
    # (not a hard error, just a warning -- multi_armed is valid)

    # Add spine bones to estimate (always included as root)
    bone_estimate += 4  # base spine chain

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "limb_count": len(limb_types),
        "bone_estimate": bone_estimate,
    }


def _generate_multi_arm_bones(arm_count: int) -> list[dict]:
    """Generate bone definitions for a multi-armed creature.

    Produces arm_count arm pairs (L/R), each with upper_arm, forearm, and hand,
    vertically offset down the spine. arm_count must be >= 2 and <= 6, and even.

    Args:
        arm_count: Total number of arms (must be even, 2-6).

    Returns:
        List of bone definition dicts, each with keys:
        name, head, tail, roll, parent, rigify_type.

    Raises:
        ValueError: If arm_count is invalid (not even, or outside 2-6).
    """
    if not isinstance(arm_count, int) or arm_count < 2 or arm_count > 6 or arm_count % 2 != 0:
        raise ValueError(
            f"arm_count must be an even integer between 2 and 6, got {arm_count}"
        )

    pairs = arm_count // 2
    bones: list[dict] = []

    for pair_idx in range(pairs):
        z_offset = 1.5 - pair_idx * 0.2
        y_offset = pair_idx * 0.02
        suffix = "" if pair_idx == 0 else f"_{pair_idx + 1}"

        for side in ("L", "R"):
            sign = 1.0 if side == "L" else -1.0
            parent_spine = "spine.003" if pair_idx == 0 else f"spine.{(3 - pair_idx):03d}" if pair_idx < 3 else "spine"

            ua_name = f"upper_arm{suffix}.{side}"
            fa_name = f"forearm{suffix}.{side}"
            ha_name = f"hand{suffix}.{side}"

            bones.append({
                "name": ua_name,
                "head": (sign * 0.18, y_offset, z_offset),
                "tail": (sign * 0.4, y_offset, z_offset),
                "roll": 0.0,
                "parent": parent_spine,
                "rigify_type": "limbs.arm",
            })
            bones.append({
                "name": fa_name,
                "head": (sign * 0.4, y_offset, z_offset),
                "tail": (sign * 0.62, y_offset, z_offset),
                "roll": 1.5708 if side == "L" else -1.5708,
                "parent": ua_name,
                "rigify_type": "",
            })
            bones.append({
                "name": ha_name,
                "head": (sign * 0.62, y_offset, z_offset),
                "tail": (sign * 0.72, y_offset, z_offset),
                "roll": 0.0,
                "parent": fa_name,
                "rigify_type": "",
            })

    return bones


# ---------------------------------------------------------------------------
# VeilBreakers-specific rigging data
# ---------------------------------------------------------------------------

# VeilBreakers monster ID to rig template mapping
# Monster-to-template mapping derived from VISUAL ANALYSIS of actual VB concept art.
# Each monster was visually inspected to determine correct body topology.
MONSTER_TEMPLATE_MAP: dict[str, dict] = {
    # --- Humanoid bipedal monsters ---
    "skitter_teeth": {
        "template": "humanoid", "body": "heavy",
        "features": ["oversized_hands", "spine_plates", "hunched_posture"],
        "notes": "Hunched bipedal with massive armored claw-arms, skull face, bone armor",
    },
    "chainbound": {
        "template": "humanoid", "body": "heavy",
        "features": ["chain_spring_bones", "glowing_core", "mechanical_joints"],
        "notes": "Armored humanoid wrapped in chains, glowing ember core in chest",
    },
    "corrodex": {
        "template": "humanoid", "body": "medium",
        "features": ["acid_drip_emitters", "corroded_armor"],
        "notes": "Armored humanoid knight leaking green acid from joints and hands",
    },
    "crackling": {
        "template": "humanoid", "body": "small",
        "features": ["electric_hair_spring", "scale_0.6"],
        "notes": "Small child-like humanoid with electric blue hair, scaled-down rig",
    },
    "ironjaw": {
        "template": "humanoid", "body": "heavy",
        "features": ["hunched_posture", "jaw_extend", "weapon_socket", "spine_plates"],
        "notes": "Bear-like beast-man, bipedal, skull face, holds spiked mace",
    },
    "ravener": {
        "template": "humanoid", "body": "large",
        "features": ["hunched_posture", "digitigrade_legs", "frenzy_morph", "spine_spikes"],
        "notes": "Werewolf beast, bipedal hunched, large claws, spiny back",
    },
    "voltgeist": {
        "template": "humanoid", "body": "medium",
        "features": ["energy_trail_emitters", "electric_arc_bones"],
        "notes": "Sleek humanoid with lightning coursing through cracked body",
    },
    "the_bulwark": {
        "template": "humanoid", "body": "boss",
        "features": ["hunched_posture", "heavy_armor_sockets", "chain_spring_bones", "thorn_protrusions"],
        "notes": "BOSS: Hulking zombie in thorny armor with chains, hunched shambling gait",
    },
    "the_vessel": {
        "template": "humanoid", "body": "boss",
        "features": ["cloth_spring_bones", "halo_bone", "hover_offset", "corruption_morph"],
        "notes": "BOSS: Hooded robed figure with halo, floating/hovering, hands outstretched",
    },
    # --- Humanoid upper body + tentacle/amorphous lower (wraith type) ---
    "bloodshade": {
        "template": "humanoid", "body": "medium",
        "features": ["no_legs_tentacle_base", "tendril_spring_bones", "corruption_morph"],
        "notes": "Dark wraith — humanoid torso with arms, lower body is dark flowing tendrils (no legs)",
    },
    "hollow": {
        "template": "humanoid", "body": "large",
        "features": ["no_legs_tentacle_base", "glowing_core", "void_distortion", "corruption_morph"],
        "notes": "Massive dark humanoid upper body, lower dissolves into writhing tentacle mass",
    },
    # --- Serpent body WITH arms ---
    "grimthorn": {
        "template": "serpent", "body": "medium",
        "features": ["arm_pair_addon", "spike_protrusions", "glowing_eyes"],
        "notes": "Serpentine body with 2 clawed arms, covered in spikes, green glow",
    },
    "needlefang": {
        "template": "serpent", "body": "medium",
        "features": ["arm_pair_addon", "spike_protrusions", "glowing_eyes"],
        "notes": "Serpentine with arms and spike protrusions (similar topology to grimthorn)",
    },
    # --- Quadruped ---
    "sporecaller": {
        "template": "quadruped", "body": "medium",
        "features": ["antler_bones", "growth_sockets", "mushroom_protrusions"],
        "notes": "Corrupted deer/elk quadruped with antlers and mushrooms growing from body",
    },
    # --- Insect (with wings) ---
    "flicker": {
        "template": "insect", "body": "small",
        "features": ["wing_pair_addon", "electric_trail"],
        "notes": "Flying insect-spider hybrid with 4 translucent wings and 6+ legs",
    },
    "the_broodmother": {
        "template": "insect", "body": "boss",
        "features": ["wing_pair_addon", "egg_sac_distension", "spawn_points", "mandible_extend"],
        "notes": "BOSS: Giant insect with wings, translucent egg sac abdomen with larvae, 6 legs",
    },
    # --- Floating/amorphous ---
    "mawling": {
        "template": "floating", "body": "small",
        "features": ["oversized_jaw", "drip_emitters"],
        "notes": "Small floating dark blob with enormous toothy mouth, no limbs",
    },
    "gluttony_polyp": {
        "template": "humanoid", "body": "large",
        "features": ["belly_distension_morph", "transparent_belly"],
        "notes": "Large hunched humanoid with huge transparent belly containing organisms",
    },
    # --- Multi-armed ---
    "the_congregation": {
        "template": "multi_armed", "body": "boss",
        "features": ["arm_count_6", "tentacle_base", "swarm_detach", "corruption_morph"],
        "notes": "BOSS: 6-armed humanoid upper fused into mass of writhing bodies/tentacles",
    },
    # --- Pure amorphous ---
    "the_weeping": {
        "template": "amorphous", "body": "boss",
        "features": ["multi_eye_array", "tendril_spring_bones"],
        "notes": "BOSS: Organic mass covered in 15+ eyeballs and dark tendrils, no humanoid features",
    },
}


# Rig feature flags that indicate special bone/morph requirements
# beyond what the base template provides
RIG_FEATURE_DEFINITIONS: dict[str, dict] = {
    "no_legs_tentacle_base": {
        "description": "Replace leg bones with tentacle chain (wraith-type lower body)",
        "removes": ["thigh.L", "thigh.R", "shin.L", "shin.R", "foot.L", "foot.R"],
        "adds": ["tentacle_base", "tentacle_base.001", "tentacle_base.002"],
    },
    "arm_pair_addon": {
        "description": "Add humanoid arm pair to a non-humanoid template (e.g. serpent)",
        "adds": ["upper_arm.L", "forearm.L", "hand.L", "upper_arm.R", "forearm.R", "hand.R"],
    },
    "wing_pair_addon": {
        "description": "Add wing bones to insect template for flying creatures",
        "adds": ["wing_upper.L", "wing_lower.L", "wing_upper.R", "wing_lower.R"],
    },
    "oversized_jaw": {
        "description": "Add jaw bone to floating template for mouth creatures",
        "adds": ["jaw", "jaw.001"],
    },
    "antler_bones": {
        "description": "Add antler/horn bone chains for deer/elk/horned creatures",
        "adds": ["antler.L", "antler.L.001", "antler.R", "antler.R.001"],
    },
    "weapon_socket": {
        "description": "Add weapon hold bone in hand for weapon-wielding creatures",
        "adds": ["weapon_hold.R"],
    },
    "multi_eye_array": {
        "description": "Multiple independent eye bones for eye-covered creatures",
        "adds": [f"eye_{i}" for i in range(8)],
    },
    "hunched_posture": {
        "description": "Modify spine curve for hunched/beast-man stance",
        "modifies": ["spine.002", "spine.003"],
    },
    "digitigrade_legs": {
        "description": "Extra joint in leg chain for digitigrade (toe-walking) stance",
        "adds": ["metatarsal.L", "metatarsal.R"],
    },
    "chain_spring_bones": {
        "description": "Spring bone chains for dangling chains/accessories",
        "adds": ["chain_1", "chain_1.001", "chain_2", "chain_2.001"],
    },
    "cloth_spring_bones": {
        "description": "Spring bone mesh for robes/capes/cloth simulation",
        "adds": ["cloth_front", "cloth_front.001", "cloth_back", "cloth_back.001"],
    },
    "belly_distension_morph": {
        "description": "Blend shape for belly expansion (gluttony/egg sac)",
        "morph_target": "belly_expand",
    },
    "egg_sac_distension": {
        "description": "Pulsing/expanding egg sac with larva movement",
        "morph_target": "egg_sac_pulse",
        "adds": ["egg_sac", "egg_sac.001"],
    },
    "corruption_morph": {
        "description": "4-stage corruption blend shapes (25/50/75/100%)",
        "morph_targets": ["corruption_stage_1", "corruption_stage_2",
                          "corruption_stage_3", "corruption_stage_4"],
    },
    "halo_bone": {
        "description": "Floating halo/crown bone above head",
        "adds": ["halo"],
    },
    "hover_offset": {
        "description": "Root bone offset for floating/hovering creatures",
        "modifies": ["spine"],
    },
    "spine_plates": {
        "description": "Armor plate bones along spine for armored creatures",
        "adds": ["plate_1", "plate_2", "plate_3"],
    },
    "growth_sockets": {
        "description": "Attachment points for organic growths (mushrooms, barnacles)",
        "adds": ["growth_socket_1", "growth_socket_2", "growth_socket_3", "growth_socket_4"],
    },
}

# Bone sockets where status effect VFX should attach per body type
STATUS_EFFECT_SOCKETS: dict[str, dict[str, str]] = {
    "head": {
        "humanoid": "spine.005",
        "quadruped": "spine.004",
        "arachnid": "spine.002",
        "floating": "spine.002",
        "insect": "spine.002",
        "dragon": "spine.006",
    },
    "chest": {
        "humanoid": "spine.002",
        "quadruped": "spine.001",
        "arachnid": "spine.001",
        "floating": "spine.001",
        "insect": "spine.001",
        "dragon": "spine.002",
    },
    "root": {
        "humanoid": "spine",
        "quadruped": "spine",
        "arachnid": "spine",
        "floating": "spine",
        "insect": "spine",
        "dragon": "spine",
    },
    "left_hand": {
        "humanoid": "hand.L",
        "quadruped": "hand.L",
        "dragon": "hand.L",
    },
    "right_hand": {
        "humanoid": "hand.R",
        "quadruped": "hand.R",
        "dragon": "hand.R",
    },
    "overhead": {
        "humanoid": "spine.005",
        "quadruped": "spine.004",
        "floating": "spine.002",
        "dragon": "spine.006",
    },
}


def _get_status_effect_socket(
    template_name: str,
    socket_name: str,
) -> str | None:
    """Get the bone name for a status effect VFX attachment point.

    Args:
        template_name: Creature template (humanoid, quadruped, etc.)
        socket_name: Socket location (head, chest, root, left_hand, etc.)

    Returns:
        Bone name string, or None if socket not available for this template.
    """
    socket_map = STATUS_EFFECT_SOCKETS.get(socket_name, {})
    return socket_map.get(template_name)


# Corruption progression blend shape stages (0-100%)
CORRUPTION_MORPH_STAGES: list[dict] = [
    {
        "name": "corruption_stage_1",
        "threshold_pct": 25.0,
        "description": "Subtle dark veins, slight color desaturation",
        "affected_regions": ["torso", "arms"],
        "morph_intensity": 0.3,
    },
    {
        "name": "corruption_stage_2",
        "threshold_pct": 50.0,
        "description": "Visible corruption tendrils, skin discoloration",
        "affected_regions": ["torso", "arms", "legs", "neck"],
        "morph_intensity": 0.6,
    },
    {
        "name": "corruption_stage_3",
        "threshold_pct": 75.0,
        "description": "Heavy mutation, bone protrusions, glowing cracks",
        "affected_regions": ["full_body"],
        "morph_intensity": 0.85,
    },
    {
        "name": "corruption_stage_4",
        "threshold_pct": 100.0,
        "description": "Full corruption, transformed silhouette, void emanation",
        "affected_regions": ["full_body"],
        "morph_intensity": 1.0,
    },
]


def _get_corruption_stage(corruption_pct: float) -> dict | None:
    """Get the corruption morph stage for a given corruption percentage.

    Args:
        corruption_pct: Corruption level 0-100.

    Returns:
        Stage dict or None if below first threshold.
    """
    if corruption_pct < 0 or corruption_pct > 100:
        return None
    result = None
    for stage in CORRUPTION_MORPH_STAGES:
        if corruption_pct >= stage["threshold_pct"]:
            result = stage
    return result


def _validate_monster_rig_config(monster_id: str) -> dict:
    """Validate and return rig configuration for a VeilBreakers monster.

    Args:
        monster_id: Monster ID from monsters.json.

    Returns:
        Dict with valid, template, features, body, errors.
    """
    errors = []
    if monster_id not in MONSTER_TEMPLATE_MAP:
        errors.append(f"Unknown monster_id: '{monster_id}'. Valid: {sorted(MONSTER_TEMPLATE_MAP.keys())}")
        return {"valid": False, "template": None, "features": [], "body": None, "errors": errors}

    config = MONSTER_TEMPLATE_MAP[monster_id]
    template = config["template"]

    # Verify template exists
    from .rigging_templates import TEMPLATE_CATALOG
    if template not in TEMPLATE_CATALOG:
        errors.append(f"Template '{template}' not in TEMPLATE_CATALOG")

    return {
        "valid": len(errors) == 0,
        "template": template,
        "features": config["features"],
        "body": config["body"],
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Blender-dependent handlers
# ---------------------------------------------------------------------------


def handle_analyze_for_rigging(params: dict) -> dict:
    """Analyze a mesh for rigging: proportions, symmetry, template recommendation (RIG-01).

    Params:
        object_name: Name of the Blender mesh object to analyze.

    Returns dict with proportion analysis and recommended creature template.
    """
    name = params.get("object_name")
    if not name:
        raise ValueError("'object_name' is required")

    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    # Extract mesh data via bmesh
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()

        vertex_count = len(bm.verts)

        # Compute bounding box dimensions
        if vertex_count == 0:
            bbox_dims = (0.0, 0.0, 0.0)
            has_symmetry = False
        else:
            xs = [v.co.x for v in bm.verts]
            ys = [v.co.y for v in bm.verts]
            zs = [v.co.z for v in bm.verts]
            bbox_dims = (
                max(xs) - min(xs),  # width (X)
                max(ys) - min(ys),  # depth (Y)
                max(zs) - min(zs),  # height (Z)
            )

            # Check X-axis symmetry: compare mirrored vertex positions
            tolerance = max(bbox_dims) * 0.02  # 2% of largest dim
            sym_matches = 0
            for v in bm.verts:
                mirror_x = -v.co.x
                for v2 in bm.verts:
                    if (
                        abs(v2.co.x - mirror_x) < tolerance
                        and abs(v2.co.y - v.co.y) < tolerance
                        and abs(v2.co.z - v.co.z) < tolerance
                    ):
                        sym_matches += 1
                        break
            has_symmetry = sym_matches > vertex_count * 0.7
    finally:
        bm.free()

    analysis = _analyze_proportions(bbox_dims, vertex_count, has_symmetry)
    analysis["object_name"] = name
    analysis["bbox_dims"] = {
        "width": round(bbox_dims[0], 4),
        "depth": round(bbox_dims[1], 4),
        "height": round(bbox_dims[2], 4),
    }
    return analysis


def handle_apply_rig_template(params: dict) -> dict:
    """Apply a Rigify creature rig template to a mesh object (RIG-02).

    Params:
        object_name: Name of the mesh object to rig.
        template: Template name from TEMPLATE_CATALOG.
        generate: Whether to generate the control rig (default True).

    Returns dict with rig_name, bone_count, template, def_bone_count.
    """
    name = params.get("object_name")
    template_name = params.get("template")

    if not name:
        raise ValueError("'object_name' is required")
    if not template_name:
        raise ValueError("'template' is required")

    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    template_bones = TEMPLATE_CATALOG.get(template_name)
    if template_bones is None:
        raise ValueError(
            f"Unknown template: '{template_name}'. "
            f"Valid: {sorted(TEMPLATE_CATALOG.keys())}"
        )

    should_generate = params.get("generate", True)

    # Create armature object
    arm_data = bpy.data.armatures.new(f"{name}_metarig")
    arm_obj = bpy.data.objects.new(f"{name}_metarig", arm_data)
    bpy.context.collection.objects.link(arm_obj)
    arm_obj.location = obj.location

    # Apply template bones
    _create_template_bones(arm_obj, template_bones)
    bone_count = len(arm_data.bones)

    result = {
        "metarig_name": arm_obj.name,
        "bone_count": bone_count,
        "template": template_name,
    }

    if should_generate:
        rig_obj = _generate_rig(arm_obj)
        reparented = _fix_deform_hierarchy(rig_obj)
        def_bone_count = sum(
            1 for b in rig_obj.data.bones if b.name.startswith("DEF-")
        )
        result["rig_name"] = rig_obj.name
        result["def_bone_count"] = def_bone_count
        result["def_reparented"] = reparented
    else:
        result["rig_name"] = arm_obj.name
        result["def_bone_count"] = 0
        result["def_reparented"] = 0

    return result


def handle_build_custom_rig(params: dict) -> dict:
    """Build a custom rig by mixing limb types from LIMB_LIBRARY (RIG-03).

    Params:
        object_name: Name of the mesh object to rig (optional, for positioning).
        limb_types: List of limb type strings from LIMB_LIBRARY.
        generate: Whether to generate the control rig (default True).

    Returns dict with rig_name, bone_count, limbs_used, def_bone_count.
    """
    name = params.get("object_name")
    limb_types = params.get("limb_types", [])
    should_generate = params.get("generate", True)

    # Validate configuration
    validation = _validate_custom_rig_config(limb_types)
    if not validation["valid"]:
        raise ValueError(
            f"Invalid custom rig config: {'; '.join(validation['errors'])}"
        )

    # Always include a spine as root
    merged_bones: dict[str, dict] = {
        "spine": {
            "head": (0.0, 0.0, 0.95),
            "tail": (0.0, 0.0, 1.1),
            "roll": 0.0,
            "parent": None,
            "rigify_type": "spines.super_spine",
        },
        "spine.001": {
            "head": (0.0, 0.0, 1.1),
            "tail": (0.0, 0.0, 1.25),
            "roll": 0.0,
            "parent": "spine",
            "rigify_type": "",
        },
        "spine.002": {
            "head": (0.0, 0.0, 1.25),
            "tail": (0.0, 0.0, 1.4),
            "roll": 0.0,
            "parent": "spine.001",
            "rigify_type": "",
        },
        "spine.003": {
            "head": (0.0, 0.0, 1.4),
            "tail": (0.0, 0.0, 1.55),
            "roll": 0.0,
            "parent": "spine.002",
            "rigify_type": "",
        },
    }

    # Merge limb bones from library
    for lt in limb_types:
        limb_fn = LIMB_LIBRARY[lt]
        limb_bones = limb_fn()
        merged_bones.update(limb_bones)

    # Create armature
    rig_name = "custom_rig"
    if name:
        obj = bpy.data.objects.get(name)
        if obj:
            rig_name = f"{name}_custom_rig"

    arm_data = bpy.data.armatures.new(rig_name)
    arm_obj = bpy.data.objects.new(rig_name, arm_data)
    bpy.context.collection.objects.link(arm_obj)

    if name:
        obj = bpy.data.objects.get(name)
        if obj:
            arm_obj.location = obj.location

    # Apply merged bones
    _create_template_bones(arm_obj, merged_bones)
    bone_count = len(arm_data.bones)

    result = {
        "metarig_name": arm_obj.name,
        "bone_count": bone_count,
        "limbs_used": limb_types,
    }

    if should_generate:
        rig_obj = _generate_rig(arm_obj)
        reparented = _fix_deform_hierarchy(rig_obj)
        def_bone_count = sum(
            1 for b in rig_obj.data.bones if b.name.startswith("DEF-")
        )
        result["rig_name"] = rig_obj.name
        result["def_bone_count"] = def_bone_count
        result["def_reparented"] = reparented
    else:
        result["rig_name"] = arm_obj.name
        result["def_bone_count"] = 0
        result["def_reparented"] = 0

    return result
