# Phase 4: Rigging - Research

**Researched:** 2026-03-19
**Domain:** Blender Python API rigging -- armatures, Rigify, weight painting, IK/FK, shape keys, ragdoll physics, game engine export
**Confidence:** HIGH

## Summary

Phase 4 delivers a complete creature rigging pipeline via Blender handler functions dispatched through the existing MCP bridge. The core approach uses Rigify as the base for 10 creature rig templates, with programmatic metarig generation (not .blend files). Each template is a Python function that creates bones in edit mode, assigns `rigify_type` properties, and calls `rigify.generate.generate_rig()` to produce a full control rig with DEF/MCH/ORG bone layers.

The biggest technical challenge is **Rigify-to-game-engine export**. Rigify splits deformation bones into disconnected chains per module, which breaks FBX export for Unity. The solution is a post-generation cleanup step that re-parents DEF bones into a single connected hierarchy, then exports with "Only Deform Bones" enabled. This is a well-documented workflow with existing community scripts.

**Primary recommendation:** Build handlers in three tiers: (1) core armature/template infrastructure, (2) weight painting and deformation testing with visual proof, (3) advanced features (facial rig, spring bones, ragdoll, retargeting, shape keys). Use the established pure-logic separation pattern for all validation and configuration functions to maximize testability without Blender.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Use Rigify as the base for all 10 creature rig templates (humanoid, quadruped, bird, insect, serpent, floating, dragon, multi-armed, arachnid, amorphous)
- Each template is a Python function that generates Rigify metarig bone layout programmatically (not .blend template files)
- Custom rig builder allows mixing limb types from different templates
- All rig templates produce game-ready control rigs with DEF, MCH, and ORG bone layers
- Facial rig uses bone-based controls (not shape key drivers) for jaw, lips, eyelids, eyebrows, cheeks
- Monster-specific expressions (snarl, hiss, roar) are predefined bone poses stored as pose library entries
- Shape keys are used for expression/damage states that morph mesh geometry (separate from bone-based facial rig)
- Auto weight painting uses Blender's built-in "Automatic Weights" with heat diffusion
- Deformation testing at 8 standard poses: T-pose, A-pose, crouch, reach-up, twist-left, twist-right, extreme-bend, action-pose
- Contact sheet output for deformation test uses existing render_contact_sheet infrastructure
- Spring/jiggle bones use Blender's rigid body constraints or bone constraints with damped track
- Apply to: tails, hair, capes, chains, ears, antennae, tentacles
- Settings are per-bone configurable (stiffness, damping, gravity)
- Rig validation checks: unweighted vertices, weight bleeding across bones, bone roll consistency, symmetry, constraint validity
- Ragdoll auto-setup generates box/capsule colliders per bone segment with hinge/cone joint limits
- Weight mirror uses Blender's built-in mirror with vertex group name pattern (L/R suffix)
- VeilBreakers creatures include humanoid, quadruped, serpent, insect, dragon, floating, multi-armed, arachnid, amorphous types
- Monster facial expressions: snarl, hiss, roar (not standard human expressions)
- Game target is Unity -- rigs must export cleanly to FBX with Unity-compatible bone hierarchy

### Claude's Discretion
All implementation choices are at Claude's discretion -- autonomous execution mode.

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RIG-01 | Mesh analysis for rigging (joint detection, symmetry, proportions, template recommendation) | Pure-logic analyzers using bmesh vertex positions, bounding box ratios, and symmetry scoring (Section: Architecture Patterns) |
| RIG-02 | 10 Rigify-based creature rig templates | Programmatic metarig generation with `arm.edit_bones.new()` + `rigify_type` assignment + `rigify.generate.generate_rig()` (Section: Rigify Generation Pipeline) |
| RIG-03 | Custom creature rig builder (configurable limbs, wings, tail, jaw, appendages) | Mix-and-match limb functions from templates, assembled into single metarig before generation (Section: Architecture Patterns) |
| RIG-04 | Facial rigging system (jaw, lips, eyelids, eyebrows, cheeks -- monster variants) | Bone-based facial rig using Rigify `faces.super_face` or custom bone chains with constraints; pose library for expressions (Section: Facial Rig Architecture) |
| RIG-05 | IK chain setup (2-bone, spline for tails/tentacles, multi-target, rotation limits) | `pose_bone.constraints.new('IK')` for standard IK, `SPLINE_IK` for spline chains, `LimitRotationConstraint` for limits (Section: IK Constraint Setup) |
| RIG-06 | Spring/jiggle bone system for secondary motion | Bone constraints with `DAMPED_TRACK` + spring simulation via frame handler or rigid body constraints (Section: Spring Bone Implementation) |
| RIG-07 | Auto weight painting with immediate deformation testing | `bpy.ops.object.parent_set(type='ARMATURE_AUTO')` for heat diffusion weights + deformation pose test (Section: Weight Painting Pipeline) |
| RIG-08 | Deformation test at 8 standard poses with contact sheet output | Pose bone rotation presets + existing `render_contact_sheet` handler for visual proof (Section: Deformation Testing) |
| RIG-09 | Comprehensive rig validation | Pure-logic validators for unweighted verts, bleeding, bone rolls, symmetry, constraints (Section: Rig Validation) |
| RIG-10 | Weight mirror (L/R) and auto-fix (normalize, clean zeros, smooth) | `bpy.ops.object.vertex_group_mirror()`, `vertex_group_normalize_all()`, `vertex_group_clean()`, `vertex_group_smooth()` (Section: Weight Operations) |
| RIG-11 | Ragdoll auto-setup from existing rig | Create mesh colliders per bone, add rigid body + rigid body constraints with joint limits (Section: Ragdoll Setup) |
| RIG-12 | Rig retargeting between different body types | Bone mapping dictionary + `COPY_ROTATION`/`COPY_LOCATION` constraints with influence scaling (Section: Rig Retargeting) |
| RIG-13 | Shape keys for expressions and damage states | `obj.shape_key_add()` + bmesh vertex manipulation per key block (Section: Shape Key System) |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| bpy (Blender Python API) | 4.x (3.6+ compat) | Armature creation, bone manipulation, constraints, weight painting | Core Blender automation API -- only way to programmatically rig |
| bmesh | 4.x (3.6+ compat) | Mesh analysis for rigging (vertex positions, symmetry, bounding box) | Direct geometry access without operator context; established project pattern |
| rigify | Bundled with Blender | Metarig-to-control-rig generation with DEF/MCH/ORG layers | User decision: all 10 templates use Rigify as base |
| mathutils | 4.x (3.6+ compat) | Vector math, Matrix transforms for bone positioning | Required for bone head/tail placement, rotation calculations |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| math (stdlib) | 3.12 | Trigonometry for bone angle calculations | Bone placement math, proportion calculations |
| json (stdlib) | 3.12 | Structured result serialization | Handler return values, validation reports |
| re (stdlib) | 3.12 | Bone name pattern matching (L/R, DEF-, ORG-, MCH-) | Mirror operations, bone filtering |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Rigify | From-scratch armatures | Rigify provides IK/FK switching, bone widgets, and proven control rig patterns -- building from scratch wastes weeks |
| bpy.ops.object.parent_set (auto weights) | Custom heat diffusion | Blender's built-in is proven and fast; custom would add complexity for marginal improvement |
| Rigid body constraints for ragdoll | Custom physics | Blender's rigid body system integrates with FBX export and Unity physics |

**Installation:** No additional packages needed. All libraries are Blender-bundled or Python stdlib.

## Architecture Patterns

### Recommended Project Structure
```
blender_addon/handlers/
    rigging.py          # Core rig handlers (analyze, create armature, apply template)
    rigging_weights.py  # Weight painting, deformation test, weight operations
    rigging_advanced.py # Facial rig, spring bones, ragdoll, retargeting, shape keys
    rigging_templates.py # 10 creature template definitions (metarig bone layouts)
```

### New Files in blender_server.py
```python
# New compound tool: blender_rig
@mcp.tool()
async def blender_rig(
    action: Literal[
        "analyze_mesh",       # RIG-01
        "apply_template",     # RIG-02
        "build_custom",       # RIG-03
        "setup_facial",       # RIG-04
        "setup_ik",           # RIG-05
        "setup_spring_bones", # RIG-06
        "auto_weight",        # RIG-07
        "test_deformation",   # RIG-08
        "validate",           # RIG-09
        "fix_weights",        # RIG-10
        "setup_ragdoll",      # RIG-11
        "retarget",           # RIG-12
        "add_shape_keys",     # RIG-13
    ],
    object_name: str,
    # ... params per action
):
```

### Pattern 1: Rigify Generation Pipeline
**What:** Programmatically create metarig, assign rigify_types, generate control rig
**When to use:** Every creature rig template (RIG-02)
**Example:**
```python
# Source: Blender Developer Docs + BlenderArtists community
import bpy
import rigify

def _create_metarig_humanoid(arm_obj):
    """Create a humanoid metarig programmatically."""
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    arm = arm_obj.data

    # Create spine chain
    spine = arm.edit_bones.new('spine')
    spine.head = (0, 0, 0.9)
    spine.tail = (0, 0, 1.1)
    spine.roll = 0
    spine.use_connect = False

    spine_001 = arm.edit_bones.new('spine.001')
    spine_001.head = spine.tail
    spine_001.tail = (0, 0, 1.3)
    spine_001.parent = spine
    spine_001.use_connect = True

    # ... more bones ...

    bpy.ops.object.mode_set(mode='OBJECT')

    # Assign Rigify types in pose mode
    bpy.ops.object.mode_set(mode='POSE')
    arm_obj.pose.bones['spine'].rigify_type = 'spines.super_spine'
    # ... more rigify_type assignments ...
    bpy.ops.object.mode_set(mode='OBJECT')

def _generate_rig(metarig_obj):
    """Generate the control rig from metarig."""
    bpy.context.view_layer.objects.active = metarig_obj
    rigify.generate.generate_rig(bpy.context, metarig_obj)
    # Returns the generated rig object
    return bpy.context.view_layer.objects.active
```

### Pattern 2: Pure-Logic Mesh Analysis for Rigging
**What:** Analyze mesh proportions, symmetry, and topology for template recommendation
**When to use:** RIG-01 mesh analysis before rigging
**Example:**
```python
# Pure logic -- testable without Blender
def _analyze_proportions(
    bbox_dims: tuple[float, float, float],
    vertex_count: int,
    has_symmetry: bool,
) -> dict:
    """Analyze mesh proportions for rig template recommendation.

    Args:
        bbox_dims: (width, depth, height) bounding box dimensions
        vertex_count: total vertex count
        has_symmetry: whether mesh has X-axis symmetry
    Returns:
        dict with aspect_ratio, recommended_template, confidence
    """
    w, d, h = bbox_dims
    aspect = h / max(w, 0.001)

    if aspect > 2.5:
        template = "humanoid"
        confidence = 0.8
    elif aspect < 0.5 and w > h:
        template = "serpent"
        confidence = 0.7
    elif 1.0 < aspect < 2.0 and d > w * 0.8:
        template = "quadruped"
        confidence = 0.7
    else:
        template = "amorphous"
        confidence = 0.4

    return {
        "aspect_ratio": round(aspect, 2),
        "recommended_template": template,
        "confidence": round(confidence, 2),
        "has_symmetry": has_symmetry,
        "vertex_count": vertex_count,
    }
```

### Pattern 3: Deformation Bone Hierarchy Fix for FBX Export
**What:** Re-parent DEF bones into single hierarchy after Rigify generation
**When to use:** After every rig generation, before FBX export (critical for Unity)
**Example:**
```python
# Source: GitHub trynyty/Rigify_DeformBones + community patterns
def _fix_deform_hierarchy(rig_obj):
    """Re-parent DEF bones into a clean single hierarchy for game export.

    Rigify splits DEF bones into disconnected chains per module.
    This re-parents them into a connected tree with proper parent chain.
    """
    bpy.context.view_layer.objects.active = rig_obj
    bpy.ops.object.mode_set(mode='EDIT')
    arm = rig_obj.data

    # Find the root DEF bone (typically DEF-spine or DEF-hips)
    root_def = None
    for bone in arm.edit_bones:
        if bone.name.startswith('DEF-') and bone.parent is None:
            root_def = bone
            break

    if root_def is None:
        # Find by name convention
        for name in ['DEF-spine', 'DEF-hips', 'DEF-root']:
            if name in arm.edit_bones:
                root_def = arm.edit_bones[name]
                break

    # Re-parent disconnected DEF chains to their logical parent
    for bone in arm.edit_bones:
        if not bone.name.startswith('DEF-'):
            continue
        if bone.parent and bone.parent.name.startswith('DEF-'):
            continue  # Already has DEF parent
        # Find corresponding ORG bone to determine logical parent
        org_name = 'ORG-' + bone.name[4:]  # DEF-xxx -> ORG-xxx
        if org_name in arm.edit_bones:
            org_bone = arm.edit_bones[org_name]
            if org_bone.parent:
                def_parent_name = 'DEF-' + org_bone.parent.name[4:]
                if def_parent_name in arm.edit_bones:
                    bone.parent = arm.edit_bones[def_parent_name]

    bpy.ops.object.mode_set(mode='OBJECT')
```

### Pattern 4: Bone Constraint Setup (IK, Spring, Limits)
**What:** Add constraints to pose bones programmatically
**When to use:** RIG-05 IK setup, RIG-06 spring bones
**Example:**
```python
# Source: Blender Python API docs
def _setup_ik_chain(rig_obj, bone_name, target_obj, target_bone,
                     chain_length=2, pole_target=None, pole_bone=None):
    """Add IK constraint to a pose bone."""
    pbone = rig_obj.pose.bones[bone_name]
    ik = pbone.constraints.new('IK')
    ik.target = target_obj
    if target_bone:
        ik.subtarget = target_bone
    ik.chain_count = chain_length
    ik.iterations = 200
    if pole_target:
        ik.pole_target = pole_target
        if pole_bone:
            ik.pole_subtarget = pole_bone
        ik.pole_angle = 0  # May need adjustment
    return {"constraint": ik.name, "chain_length": chain_length}


def _setup_spline_ik(rig_obj, bone_name, curve_obj, chain_length):
    """Add Spline IK constraint for tails/tentacles."""
    pbone = rig_obj.pose.bones[bone_name]
    spline = pbone.constraints.new('SPLINE_IK')
    spline.target = curve_obj
    spline.chain_count = chain_length
    spline.use_curve_radius = True
    spline.y_scale_mode = 'BONE_ORIGINAL'
    return {"constraint": spline.name, "chain_length": chain_length}
```

### Pattern 5: Weight Painting Automation
**What:** Auto-weight mesh to armature with heat diffusion, then validate
**When to use:** RIG-07 auto weight painting
**Example:**
```python
# Source: Blender Python API docs
def _auto_weight_paint(mesh_obj, armature_obj):
    """Parent mesh to armature with automatic weights (heat diffusion)."""
    # Select mesh, make armature active
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj

    override = get_3d_context_override()
    if override:
        with bpy.context.temp_override(**override):
            bpy.ops.object.parent_set(type='ARMATURE_AUTO', xmirror=True)
    else:
        bpy.ops.object.parent_set(type='ARMATURE_AUTO', xmirror=True)

    # Return weight painting stats
    groups = mesh_obj.vertex_groups
    return {
        "vertex_group_count": len(groups),
        "vertex_groups": [g.name for g in groups],
    }
```

### Anti-Patterns to Avoid
- **Storing edit bone references after mode switch:** Blender invalidates all EditBone references when leaving edit mode. Always re-fetch bones after `mode_set()`. Accessing stale references crashes Blender.
- **Setting rigify_type in edit mode:** `rigify_type` is a PoseBone property. Must switch to pose or object mode to assign it.
- **Exporting full Rigify rig to FBX:** Never export MCH/ORG bones to game engine. Always use "Only Deform Bones" + hierarchy fix.
- **Using bpy.ops without context override from timer:** All operator calls from the addon's timer-dispatched handlers must use `temp_override()` or the `get_3d_context_override()` helper.
- **Calling rigify.generate without active metarig:** The metarig must be the active object in the view layer before calling `generate_rig()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| IK/FK control rig | Custom IK solver + FK chain + switching | Rigify `limbs.super_limb` | IK/FK snapping, pole vectors, rubber hose, stretch -- years of testing |
| Bone widgets (control shapes) | Custom bone shape meshes | Rigify auto-generated widgets | Consistent visual language, proper scaling, community standard |
| Automatic weight painting | Custom heat diffusion algorithm | `bpy.ops.object.parent_set(type='ARMATURE_AUTO')` | Blender's implementation handles edge cases (enclosed volumes, thin geometry) |
| Weight normalization | Manual vertex group iteration | `bpy.ops.object.vertex_group_normalize_all()` | Handles edge cases: locked groups, zero-weight verts, limit-total |
| Weight mirroring | Custom L/R vertex matching | `bpy.ops.object.vertex_group_mirror()` | Topology-aware matching, name pattern detection built-in |
| Spline IK for tails | Custom curve-following constraint | `SPLINE_IK` constraint type | Handles chain length, curve radius, Y-scale modes natively |

**Key insight:** Blender's rigging tools are mature and battle-tested. The handlers should orchestrate existing Blender operations, not reimplement them. Custom code should only exist for: (1) creature template bone layouts, (2) validation logic, (3) game-export hierarchy fixes, and (4) glue code between operations.

## Common Pitfalls

### Pitfall 1: EditBone Reference Invalidation
**What goes wrong:** Code stores an EditBone reference, switches to Object mode, then tries to read the stored reference -- Blender crashes with segfault.
**Why it happens:** EditBone objects are temporary C structs only valid in Edit mode. Blender does not Python-guard them.
**How to avoid:** Never store EditBone references across mode switches. Collect all bone data (names, positions) as Python dicts/lists before switching modes.
**Warning signs:** Any `bone = arm.edit_bones['name']` followed by `bpy.ops.object.mode_set()` without using `bone` exclusively before the mode switch.

### Pitfall 2: Rigify DEF Bone Disconnection for Game Export
**What goes wrong:** Exported FBX has broken bone hierarchy in Unity. Animations don't retarget. Mecanim avatar setup fails.
**Why it happens:** Rigify generates DEF bones as disconnected chains per rig module (arms, legs, spine are separate chains). FBX "Only Deform Bones" export preserves this disconnection.
**How to avoid:** Post-generation step that re-parents all DEF bones into a single connected hierarchy using ORG bone parentage as reference. Always run before FBX export.
**Warning signs:** `DEF-upper_arm.L` has no parent, or its parent is an MCH bone instead of `DEF-spine.003`.

### Pitfall 3: Rigify Type Assignment in Wrong Mode
**What goes wrong:** `rigify_type` property is silently ignored or raises AttributeError.
**Why it happens:** `rigify_type` is a custom property on PoseBone, not EditBone. Setting it in Edit mode does nothing because PoseBones don't exist in Edit mode.
**How to avoid:** Create bones in Edit mode, switch to Object mode (or Pose mode), then assign `rigify_type` via `obj.pose.bones[name].rigify_type = '...'`.
**Warning signs:** Bones created but Rigify generation produces no rig or wrong rig type.

### Pitfall 4: Auto Weights "Bone Heat Weighting Failed"
**What goes wrong:** `parent_set(type='ARMATURE_AUTO')` raises "Bone Heat Weighting: failed to find solution for one or more bones".
**Why it happens:** Non-manifold geometry, zero-thickness surfaces, bones outside mesh volume, or very thin mesh sections that the heat diffusion solver can't resolve.
**How to avoid:** Run mesh analysis/repair (Phase 2 handlers) before auto-weighting. Check that all bones are inside or touching the mesh volume. Provide fallback to envelope weights or manual vertex group creation.
**Warning signs:** Non-manifold edges > 0 in topology analysis, bones positioned outside mesh bounding box.

### Pitfall 5: Context Override Missing for Operator Calls
**What goes wrong:** `RuntimeError: Operator bpy.ops.object.parent_set.poll() failed` from timer-dispatched handler.
**Why it happens:** Timer callbacks run outside normal 3D viewport context. Operators require area/region context.
**How to avoid:** Always use `get_3d_context_override()` + `temp_override()` for all bpy.ops calls. This is the established project pattern from Phase 1/2/3.
**Warning signs:** Any `bpy.ops.*` call in a handler function without `temp_override`.

### Pitfall 6: Bone Name Collisions Between Templates
**What goes wrong:** Custom rig builder that mixes limb types creates duplicate bone names, causing Blender to auto-rename (e.g., `upper_arm.L.001`).
**Why it happens:** Different templates may use the same base bone names. Blender silently appends `.001` suffix.
**How to avoid:** Use namespaced prefixes for mixed templates (e.g., `wing_upper_arm.L` vs `arm_upper_arm.L`), or validate uniqueness before creation.
**Warning signs:** Bone names containing `.001`, `.002` suffixes that weren't intentional.

### Pitfall 7: Rigify Not Enabled in Blender
**What goes wrong:** `import rigify` raises ImportError, or `generate_rig()` fails.
**Why it happens:** Rigify is a bundled addon but not always enabled by default.
**How to avoid:** Check if Rigify is enabled at handler registration time. If not, enable it programmatically: `bpy.ops.preferences.addon_enable(module='rigify')`.
**Warning signs:** ImportError on `import rigify` in any handler.

## Code Examples

### Rigify Rig Types Reference (for template assignment)
```python
# Source: Blender Manual Rig Types + Blender Developer Documentation
# These are the rigify_type strings assigned to metarig pose bones

RIGIFY_TYPES = {
    # Basic
    "basic.copy_chain": "Copies a bone chain as-is",
    "basic.pivot": "Creates a pivot control",
    "basic.raw_copy": "Raw bone duplication",
    "basic.super_copy": "Flexible bone copy with options",

    # Spines
    "spines.super_spine": "Spine with optional head/neck and tail",
    "spines.basic_tail": "Simple tail chain",

    # Limbs
    "limbs.super_limb": "Full IK/FK arm or leg with twist",
    "limbs.arm": "Arm-specific (inherits super_limb)",
    "limbs.leg": "Leg-specific (inherits super_limb)",
    "limbs.paw": "Generic paw",
    "limbs.front_paw": "Front paw variant",
    "limbs.rear_paw": "Rear paw variant",
    "limbs.super_finger": "Finger with curl controls",
    "limbs.super_palm": "Palm/hand structure",
    "limbs.simple_tentacle": "Flexible tentacle chain",

    # Face
    "faces.super_face": "Full facial rig system",
    "face.skin_eye": "Eye rigging",
    "face.skin_jaw": "Jaw movement",
    "face.basic_tongue": "Tongue articulation",

    # Skin (deformation)
    "skin.basic_chain": "Simple deformation chain",
    "skin.stretchy_chain": "Stretching deformation chain",
    "skin.anchor": "Attachment point",
    "skin.glue": "Binding mechanism",
}
```

### Creature Template Bone Layout Pattern
```python
# Source: Blender Python API docs + Rigify architecture
# Each template function creates metarig bones and assigns rigify_types

# Standard bone positions for a quadruped metarig (simplified)
QUADRUPED_BONES = {
    "spine": {"head": (0, 0, 0.8), "tail": (0, -0.15, 0.85), "roll": 0,
              "parent": None, "rigify_type": "spines.super_spine"},
    "spine.001": {"head": (0, -0.15, 0.85), "tail": (0, -0.3, 0.9), "roll": 0,
                  "parent": "spine", "rigify_type": ""},
    "spine.002": {"head": (0, -0.3, 0.9), "tail": (0, -0.4, 0.95), "roll": 0,
                  "parent": "spine.001", "rigify_type": ""},
    # Front legs
    "upper_arm.L": {"head": (0.15, -0.05, 0.7), "tail": (0.15, 0.0, 0.4), "roll": 0,
                    "parent": "spine", "rigify_type": "limbs.front_paw"},
    "forearm.L": {"head": (0.15, 0.0, 0.4), "tail": (0.15, 0.02, 0.1), "roll": 0,
                  "parent": "upper_arm.L", "rigify_type": ""},
    "hand.L": {"head": (0.15, 0.02, 0.1), "tail": (0.15, 0.02, 0.0), "roll": 0,
               "parent": "forearm.L", "rigify_type": ""},
    # ... rear legs, tail, neck, head bones ...
}

def _create_template_bones(arm_obj, bone_defs: dict):
    """Create metarig bones from a template definition dict."""
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    arm = arm_obj.data

    # First pass: create all bones
    for name, props in bone_defs.items():
        bone = arm.edit_bones.new(name)
        bone.head = props["head"]
        bone.tail = props["tail"]
        bone.roll = props["roll"]

    # Second pass: set parents (bones must exist first)
    for name, props in bone_defs.items():
        if props["parent"]:
            arm.edit_bones[name].parent = arm.edit_bones[props["parent"]]
            arm.edit_bones[name].use_connect = True

    bpy.ops.object.mode_set(mode='OBJECT')

    # Third pass: assign rigify types (must be in object/pose mode)
    for name, props in bone_defs.items():
        if props.get("rigify_type"):
            arm_obj.pose.bones[name].rigify_type = props["rigify_type"]
```

### Deformation Testing at 8 Poses
```python
# Source: Standard rigging QA practice
DEFORMATION_POSES = {
    "t_pose": {},  # Default rest pose
    "a_pose": {
        "DEF-upper_arm.L": (0, 0, -0.785),  # -45 deg Z
        "DEF-upper_arm.R": (0, 0, 0.785),
    },
    "crouch": {
        "DEF-thigh.L": (-1.2, 0, 0),
        "DEF-thigh.R": (-1.2, 0, 0),
        "DEF-shin.L": (1.0, 0, 0),
        "DEF-shin.R": (1.0, 0, 0),
    },
    "reach_up": {
        "DEF-upper_arm.L": (0, 0, 2.6),
        "DEF-upper_arm.R": (0, 0, -2.6),
    },
    "twist_left": {
        "DEF-spine.001": (0, 0.7, 0),
        "DEF-spine.002": (0, 0.7, 0),
    },
    "twist_right": {
        "DEF-spine.001": (0, -0.7, 0),
        "DEF-spine.002": (0, -0.7, 0),
    },
    "extreme_bend": {
        "DEF-forearm.L": (-2.0, 0, 0),
        "DEF-forearm.R": (-2.0, 0, 0),
    },
    "action_pose": {
        "DEF-thigh.L": (-0.8, 0, 0),
        "DEF-thigh.R": (-0.3, 0, 0.3),
        "DEF-upper_arm.L": (0.5, 0, 1.5),
        "DEF-upper_arm.R": (-0.3, 0, -0.8),
    },
}
```

### Rig Validation (Pure Logic)
```python
# Pure logic -- testable without Blender
def _validate_rig_report(
    vertex_count: int,
    vertex_group_names: list[str],
    unweighted_vertex_indices: list[int],
    weight_sums: dict[int, float],  # vertex_index -> total weight
    bone_names: list[str],
    bone_rolls: dict[str, float],
    bone_parents: dict[str, str | None],
) -> dict:
    """Validate rig quality from extracted data. Pure function."""
    issues = []

    # Check unweighted vertices
    unweighted_pct = len(unweighted_vertex_indices) / max(vertex_count, 1) * 100
    if unweighted_pct > 0:
        issues.append(f"{len(unweighted_vertex_indices)} unweighted vertices "
                      f"({unweighted_pct:.1f}%)")

    # Check weight normalization
    non_normalized = [
        idx for idx, total in weight_sums.items()
        if abs(total - 1.0) > 0.01 and total > 0
    ]
    if non_normalized:
        issues.append(f"{len(non_normalized)} vertices with non-normalized weights")

    # Check symmetry (L/R bone pairs)
    left_bones = {n for n in bone_names if n.endswith('.L')}
    right_bones = {n for n in bone_names if n.endswith('.R')}
    left_without_right = {n for n in left_bones
                          if n[:-2] + '.R' not in right_bones}
    if left_without_right:
        issues.append(f"Asymmetric bones missing R counterpart: "
                      f"{sorted(left_without_right)}")

    # Check bone roll consistency
    roll_issues = []
    for name, roll in bone_rolls.items():
        if name.endswith('.L'):
            mirror = name[:-2] + '.R'
            if mirror in bone_rolls:
                if abs(bone_rolls[mirror] + roll) > 0.01:
                    roll_issues.append(f"{name} roll mismatch with {mirror}")
    if roll_issues:
        issues.extend(roll_issues)

    return {
        "vertex_count": vertex_count,
        "bone_count": len(bone_names),
        "unweighted_vertices": len(unweighted_vertex_indices),
        "unweighted_percentage": round(unweighted_pct, 1),
        "non_normalized_vertices": len(non_normalized),
        "symmetry_issues": len(left_without_right),
        "roll_issues": len(roll_issues),
        "issues": issues,
        "grade": _compute_rig_grade(unweighted_pct, len(non_normalized),
                                     len(left_without_right), len(roll_issues)),
    }

def _compute_rig_grade(
    unweighted_pct: float,
    non_normalized: int,
    symmetry_issues: int,
    roll_issues: int,
) -> str:
    """Compute A-F rig quality grade."""
    if unweighted_pct > 10 or non_normalized > 100:
        return "F"
    if unweighted_pct > 5 or non_normalized > 50 or symmetry_issues > 5:
        return "D"
    if unweighted_pct > 1 or non_normalized > 10 or symmetry_issues > 2:
        return "C"
    if unweighted_pct > 0 or non_normalized > 0 or roll_issues > 2:
        return "B"
    return "A"
```

### Facial Rig Architecture
```python
# Bone-based facial rig layout (per CONTEXT.md decision)
FACIAL_BONES = {
    # Jaw
    "jaw": {"head": (0, 0.02, 1.6), "tail": (0, 0.08, 1.55), "parent": "head"},
    # Lips (upper/lower, left/right corners)
    "lip_upper": {"head": (0, 0.08, 1.6), "tail": (0, 0.1, 1.6), "parent": "head"},
    "lip_lower": {"head": (0, 0.08, 1.58), "tail": (0, 0.1, 1.58), "parent": "jaw"},
    "lip_corner.L": {"head": (0.03, 0.07, 1.59), "tail": (0.03, 0.09, 1.59),
                      "parent": "head"},
    "lip_corner.R": {"head": (-0.03, 0.07, 1.59), "tail": (-0.03, 0.09, 1.59),
                      "parent": "head"},
    # Eyelids
    "eyelid_upper.L": {"head": (0.03, 0.06, 1.65), "tail": (0.03, 0.07, 1.66),
                         "parent": "head"},
    "eyelid_lower.L": {"head": (0.03, 0.06, 1.64), "tail": (0.03, 0.07, 1.63),
                         "parent": "head"},
    # ... R side mirrors ...
    # Eyebrows
    "brow_inner.L": {"head": (0.015, 0.06, 1.67), "tail": (0.015, 0.07, 1.68),
                      "parent": "head"},
    "brow_mid.L": {"head": (0.035, 0.06, 1.68), "tail": (0.035, 0.07, 1.69),
                    "parent": "head"},
    "brow_outer.L": {"head": (0.055, 0.05, 1.67), "tail": (0.055, 0.06, 1.68),
                      "parent": "head"},
    # Cheeks
    "cheek.L": {"head": (0.04, 0.05, 1.6), "tail": (0.04, 0.07, 1.6),
                 "parent": "head"},
}

# Monster expression presets (bone rotation/location offsets)
MONSTER_EXPRESSIONS = {
    "snarl": {
        "lip_upper": {"location": (0, 0, 0.005)},
        "lip_corner.L": {"rotation": (0, 0, 0.3)},
        "lip_corner.R": {"rotation": (0, 0, -0.3)},
        "brow_inner.L": {"location": (0, 0, 0.003)},
        "brow_inner.R": {"location": (0, 0, 0.003)},
    },
    "hiss": {
        "jaw": {"rotation": (-0.3, 0, 0)},
        "lip_upper": {"location": (0, 0, 0.003)},
        "lip_lower": {"location": (0, 0, -0.003)},
    },
    "roar": {
        "jaw": {"rotation": (-0.8, 0, 0)},
        "lip_upper": {"location": (0, 0, 0.008)},
        "lip_corner.L": {"rotation": (0, 0, 0.5)},
        "lip_corner.R": {"rotation": (0, 0, -0.5)},
        "brow_inner.L": {"location": (0, 0, 0.005)},
        "brow_inner.R": {"location": (0, 0, 0.005)},
        "cheek.L": {"location": (0, 0, 0.003)},
        "cheek.R": {"location": (0, 0, 0.003)},
    },
}
```

### Shape Key Creation
```python
# Source: Blender Python API docs
def _create_shape_key(obj, name, vertex_offsets):
    """Create a shape key with specified vertex offsets.

    Args:
        obj: Blender mesh object
        name: Shape key name (e.g., "damage_heavy")
        vertex_offsets: dict of {vertex_index: (dx, dy, dz)}
    """
    # Ensure basis exists
    if obj.data.shape_keys is None:
        obj.shape_key_add(name="Basis")

    # Add new shape key
    sk = obj.shape_key_add(name=name)
    sk.value = 0.0

    # Apply offsets
    for idx, (dx, dy, dz) in vertex_offsets.items():
        if idx < len(sk.data):
            sk.data[idx].co.x += dx
            sk.data[idx].co.y += dy
            sk.data[idx].co.z += dz

    return {
        "shape_key": name,
        "vertices_modified": len(vertex_offsets),
        "total_shape_keys": len(obj.data.shape_keys.key_blocks),
    }
```

### Spring Bone Setup
```python
# Source: Blender Python API docs + Wiggle addon patterns
def _setup_spring_chain(rig_obj, bone_names, stiffness=0.5, damping=0.7, gravity=1.0):
    """Set up spring bone chain using bone constraints.

    Uses DAMPED_TRACK + COPY_ROTATION with reduced influence to create
    spring-like secondary motion that can be baked to keyframes.
    """
    results = []
    for i, bone_name in enumerate(bone_names):
        pbone = rig_obj.pose.bones[bone_name]

        # Add damped track for goal following
        dt = pbone.constraints.new('DAMPED_TRACK')
        dt.name = f"spring_track_{i}"
        dt.influence = stiffness

        # Add copy rotation from parent with reduced influence for lag
        if pbone.parent:
            cr = pbone.constraints.new('COPY_ROTATION')
            cr.name = f"spring_follow_{i}"
            cr.target = rig_obj
            cr.subtarget = pbone.parent.name
            cr.influence = damping * (1.0 - i * 0.1)  # Decreasing influence down chain
            cr.mix_mode = 'ADD'

        # Store spring parameters as custom properties
        pbone["spring_stiffness"] = stiffness
        pbone["spring_damping"] = damping
        pbone["spring_gravity"] = gravity

        results.append(bone_name)

    return {
        "spring_bones": results,
        "stiffness": stiffness,
        "damping": damping,
        "gravity": gravity,
    }
```

### Ragdoll Auto-Setup
```python
# Source: Blender Python API docs
def _setup_ragdoll(rig_obj, bone_collider_map):
    """Create ragdoll colliders and constraints from rig bones.

    Args:
        rig_obj: Armature object
        bone_collider_map: dict mapping bone names to collider specs
            e.g., {"DEF-spine": {"shape": "CAPSULE", "radius": 0.1, "length": 0.3}}
    """
    colliders = []

    for bone_name, spec in bone_collider_map.items():
        pbone = rig_obj.pose.bones.get(bone_name)
        if not pbone:
            continue

        # Create collider mesh
        shape = spec.get("shape", "BOX")
        if shape == "CAPSULE":
            bpy.ops.mesh.primitive_cylinder_add(
                radius=spec.get("radius", 0.05),
                depth=spec.get("length", 0.2),
            )
        else:  # BOX
            bpy.ops.mesh.primitive_cube_add(
                size=spec.get("size", 0.1),
            )

        collider = bpy.context.active_object
        collider.name = f"ragdoll_{bone_name}"

        # Position at bone location
        bone_matrix = rig_obj.matrix_world @ pbone.matrix
        collider.matrix_world = bone_matrix

        # Add rigid body
        bpy.ops.rigidbody.object_add()
        collider.rigid_body.type = 'ACTIVE'
        collider.rigid_body.mass = spec.get("mass", 1.0)
        collider.rigid_body.collision_shape = shape

        # Parent to bone
        collider.parent = rig_obj
        collider.parent_bone = bone_name
        collider.parent_type = 'BONE'

        colliders.append(collider.name)

    # Add rigid body constraints between adjacent colliders
    for bone_name, spec in bone_collider_map.items():
        pbone = rig_obj.pose.bones.get(bone_name)
        if not pbone or not pbone.parent:
            continue
        parent_name = pbone.parent.name
        if parent_name not in bone_collider_map:
            continue

        # Create empty for constraint
        bpy.ops.object.empty_add(type='PLAIN_AXES')
        constraint_obj = bpy.context.active_object
        constraint_obj.name = f"ragdoll_joint_{bone_name}"

        bpy.ops.rigidbody.constraint_add()
        rbc = constraint_obj.rigid_body_constraint
        rbc.type = spec.get("joint_type", "GENERIC")
        rbc.object1 = bpy.data.objects.get(f"ragdoll_{parent_name}")
        rbc.object2 = bpy.data.objects.get(f"ragdoll_{bone_name}")

        # Set limits
        if rbc.type == 'GENERIC':
            rbc.use_limit_ang_x = True
            rbc.limit_ang_x_lower = spec.get("ang_x_min", -0.5)
            rbc.limit_ang_x_upper = spec.get("ang_x_max", 0.5)
            rbc.use_limit_ang_y = True
            rbc.limit_ang_y_lower = spec.get("ang_y_min", -0.3)
            rbc.limit_ang_y_upper = spec.get("ang_y_max", 0.3)
            rbc.use_limit_ang_z = True
            rbc.limit_ang_z_lower = spec.get("ang_z_min", -0.3)
            rbc.limit_ang_z_upper = spec.get("ang_z_max", 0.3)

    return {"colliders": colliders, "joint_count": len(colliders) - 1}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Rigify pitchipoy rig types | New naming (limbs.super_limb, spines.super_spine) | Blender 2.80 | Use new type names exclusively |
| bpy.context.copy() for operator override | bpy.context.temp_override() | Blender 3.2+ | Project already uses temp_override pattern |
| Old Pose Library (Action-based) | Asset-based Pose Library | Blender 3.0+ | Use `bpy.ops.poselib.create_pose_asset()` for expression presets |
| `bgl` module for GPU drawing | `gpu` module | Blender 4.0 | bgl removed entirely |
| Rigify old rig names (pitchipoy.*) | New rig names (limbs.*, spines.*, faces.*) | Blender 2.80+ | Always use current names |

**Deprecated/outdated:**
- `bpy.ops.poselib.action_sanitize()`: Old pose library system, removed in recent Blender versions
- `pitchipoy.super_limb`: Old Rigify type names, replaced by `limbs.super_limb`
- `bone.layers[]` array: Replaced by bone collections in Blender 4.0+

## Open Questions

1. **Rigify version compatibility across Blender 3.6-5.x**
   - What we know: Rigify is bundled with Blender and generally backward-compatible. The generation API (`rigify.generate.generate_rig()`) has been stable.
   - What's unclear: Whether `faces.super_face` rig type works identically across 3.6 and 4.x. Bone collection API changed in 4.0.
   - Recommendation: Use `faces.super_face` for the facial rig if available, fall back to custom bone chains if import fails. Test on user's actual Blender version.

2. **Bone collection vs bone layers API**
   - What we know: Blender 4.0+ replaced `bone.layers[]` with bone collections. Rigify handles this internally for generated rigs.
   - What's unclear: Whether our post-generation DEF hierarchy fix needs to account for bone collections.
   - Recommendation: Let Rigify manage its own bone organization. Our handlers only interact with bone names and parenting, not collections/layers.

3. **Spring bone baking for FBX export**
   - What we know: Spring bone constraints create real-time secondary motion in Blender but don't export to FBX directly.
   - What's unclear: Whether spring motion needs to be baked to keyframes before export, or if Unity handles it with its own physics.
   - Recommendation: Provide spring bone setup as Blender-side preview. Document that Unity will need its own spring bone/physics system (e.g., Dynamic Bone asset) for runtime. Optionally provide a bake-to-keyframes action.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio |
| Config file | `Tools/mcp-toolkit/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd Tools/mcp-toolkit && uv run pytest tests/test_rigging_handlers.py -x` |
| Full suite command | `cd Tools/mcp-toolkit && uv run pytest tests/ -x` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RIG-01 | Mesh proportion analysis, template recommendation | unit | `uv run pytest tests/test_rigging_handlers.py::TestMeshAnalysis -x` | -- Wave 0 |
| RIG-02 | Template bone definitions (counts, names, rigify types) | unit | `uv run pytest tests/test_rigging_handlers.py::TestTemplateDefinitions -x` | -- Wave 0 |
| RIG-03 | Custom rig builder limb mixing validation | unit | `uv run pytest tests/test_rigging_handlers.py::TestCustomRigBuilder -x` | -- Wave 0 |
| RIG-04 | Facial bone definitions, expression preset structure | unit | `uv run pytest tests/test_rigging_handlers.py::TestFacialRig -x` | -- Wave 0 |
| RIG-05 | IK chain parameter validation | unit | `uv run pytest tests/test_rigging_handlers.py::TestIKSetup -x` | -- Wave 0 |
| RIG-06 | Spring bone parameter validation | unit | `uv run pytest tests/test_rigging_handlers.py::TestSpringBones -x` | -- Wave 0 |
| RIG-07 | Weight painting result validation | unit | `uv run pytest tests/test_rigging_handlers.py::TestAutoWeight -x` | -- Wave 0 |
| RIG-08 | Deformation pose definitions (8 poses, bone rotations) | unit | `uv run pytest tests/test_rigging_handlers.py::TestDeformationTest -x` | -- Wave 0 |
| RIG-09 | Rig validation grading (pure logic) | unit | `uv run pytest tests/test_rigging_handlers.py::TestRigValidation -x` | -- Wave 0 |
| RIG-10 | Weight fix parameter validation | unit | `uv run pytest tests/test_rigging_handlers.py::TestWeightFix -x` | -- Wave 0 |
| RIG-11 | Ragdoll collider spec validation | unit | `uv run pytest tests/test_rigging_handlers.py::TestRagdoll -x` | -- Wave 0 |
| RIG-12 | Retarget bone mapping validation | unit | `uv run pytest tests/test_rigging_handlers.py::TestRetarget -x` | -- Wave 0 |
| RIG-13 | Shape key parameter validation | unit | `uv run pytest tests/test_rigging_handlers.py::TestShapeKeys -x` | -- Wave 0 |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && uv run pytest tests/test_rigging_handlers.py -x`
- **Per wave merge:** `cd Tools/mcp-toolkit && uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_rigging_handlers.py` -- covers RIG-01 through RIG-13 pure-logic functions
- [ ] `tests/test_rigging_templates.py` -- covers template bone definitions, rigify type assignments, creature bone counts

## Sources

### Primary (HIGH confidence)
- [Blender Python API - Armature](https://docs.blender.org/api/current/bpy.types.Armature.html) -- armature data type, bone access
- [Blender Python API - EditBone](https://docs.blender.org/api/current/bpy.types.EditBone.html) -- bone creation in edit mode
- [Blender Python API - KinematicConstraint](https://docs.blender.org/api/current/bpy.types.KinematicConstraint.html) -- IK constraint properties
- [Blender Python API - PoseBoneConstraints](https://docs.blender.org/api/current/bpy.types.PoseBoneConstraints.html) -- constraint addition
- [Blender Python API - RigidBodyConstraint](https://docs.blender.org/api/current/bpy.types.RigidBodyConstraint.html) -- ragdoll joint types
- [Blender Python API - ShapeKey](https://docs.blender.org/api/current/bpy.types.ShapeKey.html) -- shape key data
- [Blender Python API - Bones & Armatures Gotchas](https://docs.blender.org/api/current/info_gotchas_armatures_and_bones.html) -- critical EditBone invalidation warning
- [Blender Manual - Rigify Rig Types](https://docs.blender.org/manual/en/3.6/addons/rigging/rigify/rig_types/index.html) -- all available rigify_type strings
- [Blender Developer Docs - Rigify Add-on API](https://developer.blender.org/docs/features/animation/rigify/) -- generation pipeline, BaseRig class

### Secondary (MEDIUM confidence)
- [Rigify DeepWiki](https://deepwiki.com/blender/blender-addons/5.1-rigify) -- architecture overview, generation stages, bone collections
- [BlenderArtists - Rigify Generate from Script](https://blenderartists.org/t/rigify-using-python-to-run-the-generate-rig-operation/1517713) -- `rigify.generate.generate_rig()` call pattern verified by community
- [GitHub - Rigify_DeformBones](https://github.com/trynyty/Rigify_DeformBones) -- DEF bone hierarchy fix for Unity export
- [Blender Developer Docs - Main Generator Engine](https://developer.blender.org/docs/features/animation/rigify/generator/) -- Generator class properties and methods
- [Blender Bug T57536](https://developer.blender.org/T57536) -- Rigify rigs don't export well to game engines (confirmed issue)

### Tertiary (LOW confidence)
- Spring bone constraint approach (DAMPED_TRACK chain) -- inferred from community addon patterns (Wiggle, BoneDynamics), not officially documented as a rigging pattern
- Rig retargeting via constraint mapping -- standard technique but no official Blender API guidance on best approach

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries are Blender-bundled, verified against official API docs
- Architecture: HIGH -- follows established project patterns (handler functions, compound tools, pure-logic separation)
- Rigify generation: HIGH -- `rigify.generate.generate_rig()` confirmed by multiple sources including developer docs and community
- Rigify FBX export fix: MEDIUM -- well-documented community workaround, but no official Blender solution
- Spring bone implementation: MEDIUM -- constraint-based approach is standard, but specific stiffness/damping values need runtime tuning
- Ragdoll setup: MEDIUM -- Blender rigid body API is documented, but ragdoll-from-rig is a custom workflow
- Pitfalls: HIGH -- EditBone invalidation, context override requirements, and rigify_type mode are documented Blender gotchas

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (Blender rigging API is very stable; 30 days is conservative)
