# Studio-Grade AAA Humanoid Rigging: Comprehensive Research Report

**Date:** 2026-03-22
**Purpose:** Best practices compilation from industry-leading platforms, studios, and tools for implementing production-quality humanoid rigs in the VeilBreakers MCP Toolkit.

---

## Table of Contents

1. [Bone Count Standards by Tier](#1-bone-count-standards-by-tier)
2. [Unity Humanoid Avatar System](#2-unity-humanoid-avatar-system)
3. [Unreal Engine / MetaHuman Skeleton](#3-unreal-engine--metahuman-skeleton)
4. [Mixamo Skeleton Standard](#4-mixamo-skeleton-standard)
5. [Rigify (Blender Built-in)](#5-rigify-blender-built-in)
6. [Auto-Rig Pro](#6-auto-rig-pro)
7. [Twist Bone Distribution](#7-twist-bone-distribution)
8. [Weight Painting Best Practices](#8-weight-painting-best-practices)
9. [Corrective Shapes / Pose-Space Deformation](#9-corrective-shapes--pose-space-deformation)
10. [IK/FK Switching for Game Animation](#10-ikfk-switching-for-game-animation)
11. [Root Motion Bone Setup](#11-root-motion-bone-setup)
12. [Facial Rigging and FACS Compliance](#12-facial-rigging-and-facs-compliance)
13. [Dual Quaternion vs Linear Blend Skinning](#13-dual-quaternion-vs-linear-blend-skinning)
14. [FBX Export Settings](#14-fbx-export-settings)
15. [Studio Case Studies](#15-studio-case-studies)
16. [Common Pitfalls](#16-common-pitfalls)
17. [Actionable Recommendations for VeilBreakers](#17-actionable-recommendations-for-veilbreakers)

---

## 1. Bone Count Standards by Tier

### Industry Standard Bone Counts

| Character Tier | Body Bones | Twist Bones | Fingers | Face Bones | Total LOD0 | Total LOD2 |
|---|---|---|---|---|---|---|
| Hero (Player/Boss) | 25-30 | 8-16 | 30 | 30-50 | 90-130 | 30-45 |
| Major NPC | 25-30 | 8 | 30 | 15-20 | 75-90 | 25-35 |
| Minor NPC / Mob | 20-25 | 4-8 | 0-15 | 0-10 | 30-60 | 15-22 |
| Crowd / Distant | 15-20 | 0-2 | 0 | 0 | 15-22 | 15-22 |

### Platform Bone Limits

| Platform | Max Bones Per Mesh | Max Influences/Vertex |
|---|---|---|
| PC / Current-Gen Console | 256 (practical ~130) | 4 (common), 8 (supported) |
| Last-Gen Console (PS4/XB1) | 128 | 4 |
| Mobile (high-end) | 75 | 4 |
| Mobile (low-end) | 32-64 | 2-4 |
| VR | 75-100 | 4 |

### LOD Bone Reduction Strategy

- **LOD0**: Full skeleton - all twist bones, all fingers, full face rig
- **LOD1**: Remove 50% twist bones, reduce fingers to 2 bones each, reduce face to 15 bones
- **LOD2**: Remove all twist bones, remove all fingers (bake to fist/open), remove face rig
- **LOD3**: Minimal skeleton (22-30 bones), spine + limbs only

Bone reduction should strip leaf bones first (fingers, toes), then twist bones, then facial bones. Hero characters that may appear in cutscenes should never go below LOD1.

---

## 2. Unity Humanoid Avatar System

### Required Bones (15 minimum)

Unity requires these bones to create a valid Humanoid Avatar:

```
Hips (0)                    -- ROOT of hierarchy
  Spine (7)
    Chest (8)               -- OPTIONAL but strongly recommended
      [UpperChest (54)]     -- OPTIONAL (added in later Unity versions)
        Neck (9)            -- OPTIONAL but strongly recommended
          Head (10)
            [LeftEye (21)]  -- OPTIONAL
            [RightEye (22)] -- OPTIONAL
            [Jaw (23)]      -- OPTIONAL
        LeftShoulder (11)   -- OPTIONAL
          LeftUpperArm (13) -- REQUIRED
            LeftLowerArm (15) -- REQUIRED
              LeftHand (17) -- REQUIRED
        RightShoulder (12)  -- OPTIONAL
          RightUpperArm (14) -- REQUIRED
            RightLowerArm (16) -- REQUIRED
              RightHand (18) -- REQUIRED
  LeftUpperLeg (1)          -- REQUIRED
    LeftLowerLeg (3)        -- REQUIRED
      LeftFoot (5)          -- REQUIRED
        [LeftToes (19)]     -- OPTIONAL
  RightUpperLeg (2)         -- REQUIRED
    RightLowerLeg (4)       -- REQUIRED
      RightFoot (6)         -- REQUIRED
        [RightToes (20)]    -- OPTIONAL
```

### Complete HumanBodyBones Enum (55 bones)

**Body (24 bones, 15 required):**
Hips, Spine, Chest*, UpperChest*, Neck*, Head, LeftShoulder*, RightShoulder*, LeftUpperArm, RightUpperArm, LeftLowerArm, RightLowerArm, LeftHand, RightHand, LeftUpperLeg, RightUpperLeg, LeftLowerLeg, RightLowerLeg, LeftFoot, RightFoot, LeftToes*, RightToes*, LeftEye*, RightEye*, Jaw*

**Fingers (30 bones, all optional):**
- Left: Thumb (Proximal/Intermediate/Distal), Index (P/I/D), Middle (P/I/D), Ring (P/I/D), Little (P/I/D)
- Right: Same pattern

*Asterisk = optional bone*

### Unity Muscle Definitions

Unity converts bone rotations to a "muscle space" at import time. Each muscle has configurable min/max range:

- **Spine Front-Back**: -40 to 40 degrees
- **Spine Left-Right**: -40 to 40 degrees
- **Upper Arm Down-Front**: -60 to 100 degrees
- **Upper Arm In-Out**: -100 to 100 degrees
- **Lower Arm Stretch**: -10 to 140 degrees (elbow)
- **Hand Down-Front**: -80 to 80 degrees (wrist flex)

Muscle settings affect animation retargeting quality. More optional bones mapped = higher retargeting fidelity.

### Critical Unity Humanoid Constraints

- **Twist bones are NOT natively supported** by Unity Humanoid Avatar mapping. They are treated as "extra bones" outside the humanoid system.
- Extra bones (twist, props, equipment) still animate but do not participate in retargeting.
- For Generic rigs, twist bones work normally but you lose cross-character retargeting.
- The hierarchy must be strictly **Hips-down** with no cycles.

---

## 3. Unreal Engine / MetaHuman Skeleton

### UE5 Mannequin Skeleton Naming

```
root
  pelvis
    spine_01
      spine_02
        spine_03
          spine_04
            spine_05
              neck_01
                neck_02
                  head
              clavicle_l
                upperarm_l
                  upperarm_twist_01_l
                  lowerarm_l
                    lowerarm_twist_01_l
                    hand_l
                      index_01_l / index_02_l / index_03_l
                      middle_01_l / middle_02_l / middle_03_l
                      ring_01_l / ring_02_l / ring_03_l
                      pinky_01_l / pinky_02_l / pinky_03_l
                      thumb_01_l / thumb_02_l / thumb_03_l
              clavicle_r
                [mirror of left arm]
    thigh_l
      thigh_twist_01_l
      calf_l
        calf_twist_01_l
        foot_l
          ball_l
    thigh_r
      [mirror of left leg]
    [ik_foot_root]
      [ik_foot_l / ik_foot_r]
    [ik_hand_root]
      [ik_hand_l / ik_hand_r / ik_hand_gun]
```

### MetaHuman Specifics

- **Body skeleton**: ~100 body bones (5 spine bones, extensive twist chains)
- **Face skeleton**: ~250-300+ facial joints (driven by Rig Logic solver)
- **Total LOD0**: ~400+ bones across body + face
- **Rig Logic**: Runtime FACS-based solver developed by 3Lateral (now Epic)
  - Pruning of extraneous joint deformations per LOD
  - Zero-cost reduction of joint configurations in higher LODs
  - Smart storage and application of corrective expressions
- MetaHuman uses **5 spine bones** (spine_01 through spine_05) vs the mannequin's 3
- Facial rig is FACS-based with corrective expressions baked per LOD
- LOD bone removal has been historically buggy; always validate at runtime

---

## 4. Mixamo Skeleton Standard

### Complete Mixamo Bone Hierarchy

```
mixamorig:Hips
  mixamorig:Spine
    mixamorig:Spine1
      mixamorig:Spine2
        mixamorig:Neck
          mixamorig:Head
            mixamorig:HeadTop_End
            mixamorig:LeftEye
            mixamorig:RightEye
        mixamorig:LeftShoulder
          mixamorig:LeftArm
            mixamorig:LeftForeArm
              mixamorig:LeftHand
                mixamorig:LeftHandThumb1/2/3
                mixamorig:LeftHandIndex1/2/3
                mixamorig:LeftHandMiddle1/2/3
                mixamorig:LeftHandRing1/2/3
                mixamorig:LeftHandPinky1/2/3
        mixamorig:RightShoulder
          [mirror of left arm]
  mixamorig:LeftUpLeg
    mixamorig:LeftLeg
      mixamorig:LeftFoot
        mixamorig:LeftToeBase
          mixamorig:LeftToe_End
  mixamorig:RightUpLeg
    [mirror of left leg]
```

### Mixamo Characteristics

- **Total bones**: ~65 with fingers, ~25 without
- **No twist bones**: Mixamo does not generate twist bones by default
- **Automatic skinning**: ML-based auto-weighting from Stanford research (acquired by Adobe)
- **T-pose required**: Upload mesh must be in T-pose for marker placement
- **Standardized skeleton**: All Mixamo animations use this exact hierarchy, enabling cross-character retargeting
- **Limitations**: No facial rig, no twist bones, no corrective shapes, limited to humanoids

### Mixamo to Unity/Unreal Workflow

1. Export as FBX from Mixamo with skin
2. In Unity: set to Humanoid, automap succeeds immediately (names are well-known)
3. In Unreal: use IK Retargeter to map Mixamo skeleton to UE5 mannequin
4. For Blender: strip "mixamorig:" prefix for mirror modifier compatibility

---

## 5. Rigify (Blender Built-in)

### Bone Naming Convention

Rigify generates four bone categories:
- **DEF-** (Deformation): The only bones that should be exported for game engines. These deform the mesh.
- **MCH-** (Mechanism): Constraint targets and intermediate helpers. Never export.
- **ORG-** (Original): Copies of the metarig bones. Never export.
- **CTRL** (no prefix): Animator controls with custom shapes. Never export.

### Generated Bone Count

A full Rigify human rig generates **~700+ total bones**, but only **~60-80 DEF bones** are deformation bones for export.

### DEF Bone Hierarchy (Exportable)

```
DEF-spine                   (hips)
  DEF-spine.001             (spine)
    DEF-spine.002           (chest)
      DEF-spine.003         (upper chest)
        DEF-spine.004       (neck)
          DEF-spine.005     (head)
        DEF-shoulder.L
          DEF-upper_arm.L      (+ DEF-upper_arm.L.001 twist)
            DEF-forearm.L      (+ DEF-forearm.L.001 twist)
              DEF-hand.L
                DEF-f_index.01.L / .02 / .03
                DEF-f_middle.01.L / .02 / .03
                DEF-f_ring.01.L / .02 / .03
                DEF-f_pinky.01.L / .02 / .03
                DEF-thumb.01.L / .02 / .03
        DEF-shoulder.R
          [mirror of left]
  DEF-thigh.L                 (+ DEF-thigh.L.001 twist)
    DEF-shin.L                (+ DEF-shin.L.001 twist)
      DEF-foot.L
        DEF-toe.L
  DEF-thigh.R
    [mirror of left]
```

### Rigify Strengths

- Free, ships with Blender
- Modular: rig types can be mixed (limbs.arm, spines.basic_spine, limbs.finger, faces.super_face)
- Generates IK/FK switching with snapping out of the box
- B-bone (Bendy Bone) support for smooth deformation
- Face rig is available via `faces.super_face` type
- Well-documented, large community

### Rigify Weaknesses for Game Export

- Exporting only DEF bones requires manual filtering or addons like Game Rig Tools
- No built-in game engine export wizard
- Bone naming does not match any game engine convention by default
- Face rig generates many bones that may exceed game budgets
- No built-in Mixamo retargeting

---

## 6. Auto-Rig Pro

### Why It Surpasses Raw Rigify for Games

| Feature | Rigify | Auto-Rig Pro |
|---|---|---|
| **Price** | Free (bundled) | $40 |
| **Game Export** | Manual DEF filtering | Built-in FBX/GLTF exporter with engine presets |
| **Twist Bones** | 1 per segment (DEF + DEF.001) | Configurable 1-4+ per segment |
| **Unity Preset** | None | One-click Unity Humanoid export |
| **Unreal Preset** | None | One-click UE5 mannequin-compatible export |
| **Mixamo Retarget** | Addon needed | Built-in retargeter |
| **Weight Painting** | Blender default | Enhanced auto-skinning + Voxel Heat Diffuse |
| **Root Motion** | Manual setup | c_traj bone auto-transfers to armature root on export |
| **Facial Rig** | Available but complex | Streamlined facial setup |
| **Bone Picker** | None | Built-in visual bone picker panel |

### Auto-Rig Pro Twist Bone Configuration

- **Configurable per limb**: 1, 2, 3, or 4+ twist bones per segment
- Upper arm twist bone sits near the shoulder
- Forearm twist bone sits near the wrist
- Thigh twist bone sits near the hip
- Calf twist bone sits near the ankle
- **Unity export**: Use 1 twist bone to match Unity Humanoid mapping
- **Unreal export**: Use 3-4 twist bones for optimal deformation
- **Soft-Link feature**: Preserves bone scale=1 while maintaining stretched positions, critical for game engines

### Auto-Rig Pro Export Modes

1. **Humanoid (Unity)**: Exports only deform bones, 1 twist bone, leaf bones stripped
2. **Humanoid (Unreal)**: Exports deform bones with multiple twist bones, UE naming
3. **Generic**: Full deform skeleton, no humanoid constraints
4. **Custom**: Select specific bones to export

---

## 7. Twist Bone Distribution

### The Problem

When a forearm rotates 180 degrees (palm up to palm down), Linear Blend Skinning causes "candy wrapper" collapse at the wrist/elbow because interpolating two rotation matrices introduces unwanted scaling.

### Solution: Twist Bone Distribution

Twist bones split the rotation across multiple joints, each taking a fraction of the total twist.

### Recommended Distribution

| Segment | 1st-Person / Hero Close-up | 3rd-Person Hero | NPC / Mob | Crowd |
|---|---|---|---|---|
| Upper Arm | 2-3 twist bones | 2 twist bones | 1 twist bone | 0 |
| Forearm | 3-4 twist bones | 2 twist bones | 1 twist bone | 0 |
| Thigh | 2 twist bones | 1 twist bone | 1 twist bone | 0 |
| Calf | 1-2 twist bones | 1 twist bone | 0 | 0 |

### Twist Bone Positioning

- **Upper arm twist**: Placed at 25%, 50%, 75% between shoulder and elbow
- **Forearm twist**: Placed at 25%, 50%, 75% between elbow and wrist
- **Weight distribution**: Each twist bone takes `1/N` of the twist rotation
- **Falloff**: Weights should gradient smoothly; the bone nearest the rotating joint takes the most twist influence

### 3-Twist-Bone Setup (AAA Standard for Forearm)

```
UpperArm
  UpperArm_Twist_01  (weight: 0.25 at shoulder end, fades to 0)
  UpperArm_Twist_02  (weight: 0.50 at midpoint)
  LowerArm
    LowerArm_Twist_01  (weight: 0.33 near elbow)
    LowerArm_Twist_02  (weight: 0.66 at midpoint)
    LowerArm_Twist_03  (weight: near wrist, fades from hand weights)
    Hand
```

### Key Insight

With 3 twist joints, higher volume is retained compared to 1 or 2 twist setups. The difference is most visible in first-person views. For third-person cameras, 2 twist bones per forearm is usually sufficient.

---

## 8. Weight Painting Best Practices

### Max Influences Per Vertex

| Platform Target | Max Influences | Notes |
|---|---|---|
| PC / Console | 4 (standard), 8 (supported) | 4 is most common; UE supports 8 with perf cost |
| Mobile | 2-4 | Many mobile GPUs hard-limit to 4 |
| Facial mesh | 6-8 | Exception: facial areas need more for subtle deformation |

### Workflow Rules

1. **Auto Normalize ON**: Always keep this enabled while painting. Ensures weights sum to 1.0 per vertex.
2. **Limit Total**: Use Blender's "Limit Total" operator to clamp to 4 influences after auto-weighting.
3. **Smooth in Pose Mode**: Pose the character to extreme angles (90, 120, 180 degrees) while painting to see real deformation.
4. **Mirror Weights**: For symmetrical anatomy, paint one side and mirror. Rigify/ARP both support this with .L/.R naming.
5. **Gradient Transitions**: Hard weight boundaries create visible creasing. Ensure smooth gradients across joint regions.
6. **Lock & Isolate**: Lock completed vertex groups before painting adjacent ones to prevent weight drift.

### Problem Areas and Solutions

| Area | Problem | Solution |
|---|---|---|
| Shoulder | Collapse when arm goes overhead | Add helper/corrective joint; split clavicle influence |
| Elbow | Volume loss at 120+ degrees | 2 deform bones in forearm chain; corrective blendshape |
| Wrist | Candy wrapper on twist | 2-3 twist bones; or DQS if engine supports |
| Knee | Pointy protrusion at bend | Corrective blendshape; or pole-vector driven helper bone |
| Groin | Inner thigh intersection | Helper joint between thighs; careful weight separation |
| Neck | Stretching on extreme look | Additional neck bone; corrective shapes for extremes |

### Weight Painting Validation Checklist

- [ ] No vertex has more than 4 influences (use Limit Total)
- [ ] No vertex has 0 total weight (unweighted verts = mesh explosion)
- [ ] Symmetry check passes (within 0.001 tolerance)
- [ ] No weights assigned to non-deform bones
- [ ] Test poses: T-pose, A-pose, arms overhead, squat, twist 180

---

## 9. Corrective Shapes / Pose-Space Deformation

### Overview

Corrective blend shapes (aka Pose-Space Deformation / PSD) fire automatically when a joint reaches a specific pose, sculpting the mesh to fix deformation artifacts that bones alone cannot solve.

### How They Work

1. Pose the joint to the problem angle (e.g., elbow at 120 degrees)
2. Sculpt the mesh to fix the deformation (push out collapsed volume, smooth creases)
3. Save as a blend shape/shape key tied to that pose
4. A driver or pose interpolation system activates the corrective shape proportionally as the joint approaches that pose

### Common Corrective Shape Targets

| Joint | Trigger Pose | Correction |
|---|---|---|
| Shoulder | Arm raised 90+ degrees | Push out deltoid volume, fix underarm crease |
| Elbow | Bent 100+ degrees | Bulge inner elbow, prevent volume loss |
| Wrist | Twisted 90+ degrees | Maintain forearm volume cross-section |
| Knee | Bent 90+ degrees | Push out kneecap area, fix back-of-knee crease |
| Hip | Thigh raised 60+ degrees | Fix groin area deformation |
| Spine | Bent forward/back 30+ degrees | Maintain torso volume, fix belly/back crease |

### Game Engine Support

- **Unity**: Blend shapes (morph targets) supported. Drive via Animation Rigging package or custom scripts. Performance cost scales with vertex count and active shape count.
- **Unreal**: Morph targets + PSD system in Control Rig. MetaHuman uses Rig Logic for corrective evaluation at runtime.
- **Performance budget**: 3-5 corrective shapes per joint for hero characters. Each shape costs ~0.1ms per 10K affected vertices on current-gen.

### Implementation in Blender for Export

1. Create shape keys in Blender at problem poses
2. Add drivers linked to bone rotations
3. On FBX export, shapes export as morph targets
4. In Unity/Unreal, recreate the driver logic in engine (Animation Rigging or Control Rig)

---

## 10. IK/FK Switching for Game Animation

### Authoring vs Runtime

**Authoring-Time IK/FK** (in Blender/Maya):
- Animators switch between IK and FK while creating animations
- IK for planted hands/feet (grabbing ledges, footsteps on slopes)
- FK for free-swinging motion (combat swipes, running arms)
- Blend slider (0.0 = FK, 1.0 = IK) with driver on custom property

**Runtime IK** (in game engine):
- Animation is baked as FK keyframes on export
- Engine applies runtime IK layers on top:
  - Foot IK (ground adaptation)
  - Hand IK (weapon gripping, ledge holding)
  - Look-at IK (head tracking)
  - Two-bone IK (aim constraints)

### Blender IK/FK Setup

Rigify generates IK/FK switching automatically:
- Custom property on control bone: `IK_FK` (0.0-1.0)
- FK chain: shoulder -> upper_arm_fk -> forearm_fk -> hand_fk
- IK chain: upper_arm_ik -> forearm_ik -> hand_ik (with pole target)
- Snap buttons: "Snap FK to IK" and "Snap IK to FK" for seamless switching
- All switching happens on control bones; DEF bones follow via constraints

### Export Consideration

On FBX export, only DEF bones are exported. All IK/FK switching is baked to DEF bone transforms. The game engine receives pure FK keyframes per bone per frame. Runtime IK (foot placement, hand IK) is a separate engine-side system.

---

## 11. Root Motion Bone Setup

### The Root Bone

Root motion requires a dedicated bone at the origin that carries the character's world-space movement extracted from the animation.

### Hierarchy

```
Root (at origin, 0,0,0)           -- carries world-space translation/rotation
  Hips (at character pelvis)      -- carries body-relative animation
    [rest of skeleton]
```

### Unity Root Motion

- **Humanoid**: Unity automatically extracts root motion from the Hips bone. No extra root bone needed. Enable "Apply Root Motion" on the Animator component.
- **Generic**: Set the "Root Node" in Animation import settings to the root bone. The root bone must be animated with the character's world-space movement.
- **Bake Into Pose**: Unity can bake Y position (grounding), XZ position (movement), and rotation into the pose or extract as root motion.
- **Root Motion Node**: Can select any bone in the hierarchy as root motion source via Motion > Root Motion Node.

### Unreal Engine Root Motion

- Tick `Enable Root Motion` in Animation Asset Details
- Root motion lives on the `root` bone (NOT pelvis)
- Since UE 4.24+, the Armature object in FBX from Blender is treated as the root
- Auto-Rig Pro: The `c_traj` control bone animation is transferred to the armature object on export

### Auto-Rig Pro Root Motion

Auto-Rig Pro provides a `c_traj` (trajectory) bone that:
1. Sits at the character's feet at origin
2. Animator keys translation/rotation on this bone for root motion
3. On FBX export, its animation transfers to the armature root node
4. Both Unity and Unreal correctly pick up root motion from this

### Best Practice

- Always include a root bone at origin, even if not using root motion (future-proofing)
- Root bone should have NO rotation or scale at bind pose
- Animate root bone on XZ plane (horizontal movement) + Y rotation (facing)
- Y translation on root = optional (for jumps, slopes)

---

## 12. Facial Rigging and FACS Compliance

### Apple ARKit 52 Blendshapes (Industry Standard)

The ARKit 52 blendshapes have become the de facto standard for facial animation in games, especially with face tracking integration.

**Eyes (14 shapes - 7 per eye):**
eyeBlinkLeft, eyeLookDownLeft, eyeLookInLeft, eyeLookOutLeft, eyeLookUpLeft, eyeSquintLeft, eyeWideLeft
(+ Right equivalents)

**Jaw (4 shapes):**
jawForward, jawLeft, jawRight, jawOpen

**Mouth (23 shapes):**
mouthClose, mouthFunnel, mouthPucker, mouthLeft, mouthRight, mouthSmileLeft, mouthSmileRight, mouthFrownLeft, mouthFrownRight, mouthDimpleLeft, mouthDimpleRight, mouthStretchLeft, mouthStretchRight, mouthRollLower, mouthRollUpper, mouthShrugLower, mouthShrugUpper, mouthPressLeft, mouthPressRight, mouthLowerDownLeft, mouthLowerDownRight, mouthUpperUpLeft, mouthUpperUpRight

**Brows (5 shapes):**
browDownLeft, browDownRight, browInnerUp, browOuterUpLeft, browOuterUpRight

**Cheeks (4 shapes):**
cheekPuff, cheekSquintLeft, cheekSquintRight

**Nose (2 shapes):**
noseSneerLeft, noseSneerRight

**Tongue (1 shape):**
tongueOut

### FACS (Facial Action Coding System) Mapping

FACS defines Action Units (AUs) that map to individual muscle groups. ARKit blendshapes are built on FACS:

| ARKit Shape | FACS AU | Muscle |
|---|---|---|
| eyeBlinkLeft | AU45 | Orbicularis oculi |
| browInnerUp | AU1 | Frontalis (inner) |
| browDownLeft | AU4 | Corrugator supercilii |
| mouthSmileLeft | AU6+AU12 | Zygomatic major |
| jawOpen | AU26 | Masseter / pterygoid |
| mouthFunnel | AU22 | Orbicularis oris |
| cheekPuff | AU33 | Buccinator |

### Facial Bone Rig Counts by Tier

| Tier | Bone Count | Blendshape Count | Use Case |
|---|---|---|---|
| MetaHuman (AAA cinematic) | 250-300+ facial joints | 200+ correctives | Cutscenes, hero close-ups |
| AAA game hero | 30-50 facial bones | 52 (ARKit) + 10-20 correctives | Player character, major NPCs |
| Standard game NPC | 10-20 facial bones | 20-30 key expressions | Dialogue NPCs |
| Distant / crowd | 3-5 bones (jaw + eyes) | 5-10 basic expressions | Background characters |

### Bone-Based vs Blendshape-Based Facial Rigs

**Bone-based pros**: Easier to animate procedurally, lower memory, works with skinning pipeline.
**Bone-based cons**: Harder to get subtle detail, more complex weight painting.
**Blendshape pros**: Sculptor-friendly, pixel-perfect control, industry standard for mocap.
**Blendshape cons**: Higher memory (full vertex delta per shape), combinatorial explosion of correctives.
**Best practice**: Hybrid approach - bones for jaw, eyes, tongue + blendshapes for expressions.

---

## 13. Dual Quaternion vs Linear Blend Skinning

### Comparison

| Aspect | Linear Blend (LBS) | Dual Quaternion (DQS) |
|---|---|---|
| Volume preservation | Poor (collapses at twist) | Excellent (guaranteed rotation+translation only) |
| Performance | Baseline | ~5-10% more expensive |
| Artifacts | Candy wrapper, volume loss | Joint bulging (elbow/knee protrusion) |
| Twist handling | Needs 2-4 twist bones | Can work with 1 twist bone |
| Engine support | Universal | UE5: yes / Unity: via shader / Blender: "Preserve Volume" |
| Industry adoption | 90%+ of games | Growing but niche |

### Practical Recommendation

- **Use LBS + twist bones** for maximum compatibility across engines
- DQS can cause unnatural bulging at elbows/knees that is hard to art-direct
- Best of both: some engines allow per-bone LBS/DQS blend (0.0 = LBS, 1.0 = DQS)
- In Blender: **UNCHECK "Preserve Volume"** on armature modifier to preview what the game engine will see (LBS)
- If using DQS in engine, 1-2 twist bones suffice; for LBS, use 2-4

---

## 14. FBX Export Settings

### Blender to Unity (Recommended Settings)

```
Format: FBX Binary
Scale: 1.00
Apply Scaling: "FBX Units Scale"
Forward: -Z Forward
Up: Y Up

Armature:
  Primary Bone Axis: Y
  Secondary Bone Axis: X
  Only Deform Bones: CHECKED
  Add Leaf Bones: UNCHECKED

Bake Animation:
  Key All Bones: CHECKED
  NLA Strips: UNCHECKED (unless using NLA)
  Force Start/End Keying: CHECKED
  Simplify: 0.0 (no simplification for accuracy)

Apply Transform: CHECKED (or Apply Unit + Apply Scalings)
```

**In Unity Import Inspector:**
- Bake Axis Conversion: CHECKED
- Scale Factor: 1 (should be correct with above settings)
- Animation Type: Humanoid
- Avatar Definition: Create From This Model

### Blender to Unreal (Recommended Settings)

```
Format: FBX 2020
Scale: 1.00 (or 100.0 if model is in Blender meters)
Apply Scaling: "FBX All"
Forward: -Y Forward
Up: Z Up

Armature:
  Primary Bone Axis: Y
  Secondary Bone Axis: X
  Only Deform Bones: CHECKED
  Add Leaf Bones: UNCHECKED

Bake Animation:
  Key All Bones: CHECKED
  Simplify: 0.0
```

### Auto-Rig Pro Export (Simplified)

Auto-Rig Pro handles all axis/scale settings automatically per engine:
- Select engine preset (Unity / Unreal / Godot)
- Choose bone count (with/without twist, with/without fingers)
- Enable/disable root motion transfer
- One-click export with correct naming, axis, scale

### Critical Export Rules

1. **Never export MCH/ORG/CTRL bones** - only DEF (deformation) bones
2. **Uncheck "Add Leaf Bones"** - these serve no purpose in game engines and add clutter
3. **Apply all transforms** before export (Ctrl+A > All Transforms in Blender)
4. **Check scale**: Model at origin should be ~1.7-1.8 units tall (1 unit = 1 meter)
5. **Verify bone rolls**: Incorrect bone roll causes twisted limbs in engine
6. **Test with simple animation**: Export a T-pose + walk cycle, verify in engine before full production

---

## 15. Studio Case Studies

### God of War Ragnarok (Santa Monica Studio)

**GDC 2023 - "Joint-Based Skin Deformation in God of War Ragnarok"** by Tenghao Wang (Senior Technical Artist):

- Uses a **systematic joint-based rig designed to fit the curve fiber structure of muscles**
- Volume preservation achieved through muscle-aligned joint placement, not blend shapes
- **Dynamic bone technique** approximates muscle, fat, and skin jiggle at runtime
- Distance-based rig setup enables realistic secondary motion
- Focus on **combat impact feel** - deformation system makes hits look more impactful
- All character deformation is joint-based (no morph targets for body), keeping performance consistent
- Helper joints placed along anatomical muscle fiber directions, not just at midpoints

**Key takeaway**: SMS uses helper joints aligned to real muscle anatomy rather than relying on corrective blend shapes. This is more performant and easier to batch across hundreds of enemy types.

### God of War (2018) - Self-Limiting Rigging Methodology

- Presented at GDC by Axel Grossman (Lead Character Technical Artist)
- Used **MotionBuilder** as primary rigging/animation tool (not Maya)
- "Self-limiting" methodology: rig constraints prevent animators from creating impossible poses
- Reduces iteration time by catching deformation issues at animation time, not in review

### FromSoftware (Elden Ring / Dark Souls)

- **Skeleton reuse across games**: Wire mesh skeletons carry forward between titles
- Example: Omenkiller skeleton still contains Capra Demon's tail bone from Dark Souls
- Animation reuse is a core strategy - shared skeletons allow shared animation libraries
- Runtime skeleton modification system allows per-instance bone scaling/rotation
- Creature rigs favor simplicity and reuse over per-character fidelity
- Non-humanoid creatures use custom skeletons but maintain consistent naming for tools

**Key takeaway**: FromSoftware prioritizes skeleton standardization and reuse across their entire catalog. A shared skeleton means hundreds of animations work across multiple character types.

### Blender Studio (Sprite Fright, Charge)

- Uses **CloudRig** (extension of Rigify) for all character rigs
- **Hybrid procedural approach**: Limbs are fully procedural, faces are manually rigged
- Face rigs use Rigify's Action system for pose-based expressions
- Character Pipeline addon enables parallel work across departments:
  - `char.modeling.blend` -> appended as collection into `char.geometry.blend`
  - Geometry adjustments for rigging are reproducibly automated
- CloudRig features: stretch function for rubber-hose effects, B-bone chains
- **Lattice-based rig elements** used alongside bone-based rigs for extreme deformation
- Production insight: "It's not possible to make the face rig system fully procedural due to the complexity of the elements involved"

**Key takeaway**: Even Blender Studio, experts in Rigify, acknowledges facial rigs need manual artistry. The modular CloudRig approach of procedural limbs + manual faces is a good template.

---

## 16. Common Pitfalls

### Export and Scale Issues

| Pitfall | Symptom | Fix |
|---|---|---|
| 100x scale on import to Unity | Character is giant or tiny | Set Blender FBX scale to 1.0, Apply Scaling = "FBX Units Scale" |
| Flipped character facing | Looks backward in engine | Use correct Forward axis (-Z for Unity, -Y for UE) |
| Bone roll incorrect | Arms/legs twisted in bind pose | Recalculate bone rolls in Blender (Armature > Recalculate Roll) |
| Leaf bones exported | Extra useless bones in hierarchy | Uncheck "Add Leaf Bones" in FBX export |
| Non-deform bones exported | MCH/ORG/CTRL clutter in engine | Check "Only Deform Bones" in FBX export |
| Armature has scale != 1 | Broken animations in engine | Apply All Transforms (Ctrl+A) before export |
| Mesh not parented to armature | Mesh doesn't move with skeleton | Parent mesh to armature with automatic weights |

### Rigging Issues

| Pitfall | Symptom | Fix |
|---|---|---|
| Unweighted vertices | Vertices stay at origin / explode | Select mesh > Vertex Groups > Remove Empty Groups, then re-weight |
| More than 4 influences | Performance issues on mobile | Mesh > Weights > Limit Total (limit=4) |
| Asymmetric weights | One side deforms differently | Paint one side, use Mirror Weights |
| Gimbal lock | Joint rotation breaks at certain angles | Set correct rotation order (usually ZXY or ZYX for limbs) |
| IK pole target missing | Knees/elbows flip randomly | Always set pole target for IK chains; position 30-50cm in front of joint |
| Bone names don't match engine | Humanoid mapping fails in Unity | Use naming convention that matches engine expectations |

### Animation Issues

| Pitfall | Symptom | Fix |
|---|---|---|
| Root motion not exporting | Character slides in place | Ensure root bone is animated; check engine root motion settings |
| NLA strips exporting wrong | Multiple animations merged | Disable NLA export, export actions individually |
| Keyframe simplification | Jittery animation in engine | Set Simplify = 0 in FBX export |
| Missing bind pose | Mesh deforms incorrectly at frame 0 | Set a T-pose or A-pose at frame 0 as rest pose |

---

## 17. Actionable Recommendations for VeilBreakers

### Recommended VeilBreakers Hero Skeleton (Unity Target)

Based on all research, the recommended skeleton for VeilBreakers player characters and bosses:

```
Root                          -- at origin, for root motion
  Hips
    Spine
      Spine1 (Chest)
        Spine2 (UpperChest)
          Neck
            Head
              LeftEye
              RightEye
              Jaw
          LeftShoulder
            LeftUpperArm
              LeftUpperArm_Twist     -- 1 twist bone (Unity Humanoid compatible)
              LeftLowerArm
                LeftLowerArm_Twist   -- 1 twist bone
                LeftHand
                  L_Thumb1 / L_Thumb2 / L_Thumb3
                  L_Index1 / L_Index2 / L_Index3
                  L_Middle1 / L_Middle2 / L_Middle3
                  L_Ring1 / L_Ring2 / L_Ring3
                  L_Pinky1 / L_Pinky2 / L_Pinky3
          RightShoulder
            [mirror of left arm]
    LeftUpperLeg
      LeftUpperLeg_Twist         -- 1 twist bone
      LeftLowerLeg
        LeftLowerLeg_Twist       -- 1 twist bone
        LeftFoot
          LeftToes
    RightUpperLeg
      [mirror of left leg]
```

**Total: ~78 bones** (24 body + 4 twist + 30 fingers + 3 face + 1 root + extras)

### LOD Skeleton Reduction Plan

| LOD | Bones | Changes |
|---|---|---|
| LOD0 | 78 | Full skeleton |
| LOD1 | 48 | Remove twist bones, reduce fingers to 2 per finger |
| LOD2 | 28 | Remove all fingers, remove face bones, spine simplified |
| LOD3 | 18 | Minimal: root + hips + spine + limbs only |

### Rigging Pipeline for MCP Toolkit

1. **Mesh Preparation**: `blender_mesh` action=`game_check` (validate poly count, manifold)
2. **Rig Application**: `blender_rig` action=`apply_template` template=`humanoid` (generates skeleton)
3. **Auto-Weight**: `blender_rig` action=`auto_weight` (initial automatic weights)
4. **Validation**: `blender_rig` action=`validate` (A-F grade check)
5. **Weight Fix**: `blender_rig` action=`fix_weights` operation=`normalize` then `clean` then `smooth`
6. **Deformation Test**: `blender_rig` action=`test_deformation` (8 standard poses, contact sheet)
7. **Export**: `blender_export` format=`fbx` with:
   - Only deform bones
   - No leaf bones
   - Scale 1.0, FBX Units Scale
   - Baked animation
8. **Unity Import**: `unity_scene` action=`configure_avatar` animation_type=`Humanoid`

### Twist Bone Strategy

- **For Unity Humanoid**: 1 twist bone per segment (4 total: upper arms + forearms)
- **For Unity Generic / Unreal**: 2-3 twist bones per segment
- **VeilBreakers default**: 1 twist bone per segment (Unity Humanoid retargeting is more valuable than extra twist fidelity, given 3rd-person camera)

### Facial Rig Strategy

- **Hero characters**: 52 ARKit blendshapes + 3 bones (jaw, left eye, right eye)
- **Major NPCs**: 20 key expression blendshapes + jaw bone
- **Mobs**: No facial rig (baked expressions in texture or single jaw bone)
- Implement as shape keys in Blender, export as morph targets in FBX

### Weight Painting Quality Targets

- Max 4 influences per vertex (enforce with Limit Total)
- Symmetry tolerance: 0.001
- Zero unweighted vertices
- Test at: T-pose, A-pose, arms overhead, full squat, 180-degree forearm twist
- Grade target: A (per `blender_rig` validate action)

---

## Sources

### Official Documentation
- [Blender Rigify Bone Positioning Guide](https://docs.blender.org/manual/en/latest/addons/rigging/rigify/bone_positioning.html)
- [Unity Manual: Configuring the Avatar](https://docs.unity3d.com/Manual/ConfiguringtheAvatar.html)
- [Unity Manual: Avatar Mapping Tab](https://docs.unity3d.com/Manual/class-Avatar.html)
- [Unity Manual: Avatar Muscle & Settings](https://docs.unity3d.com/Manual/MuscleDefinitions.html)
- [Unity Scripting API: HumanBodyBones](https://docs.unity3d.com/ScriptReference/HumanBodyBones.html)
- [Unity Manual: How Root Motion Works](https://docs.unity3d.com/6000.3/Documentation/Manual/RootMotion.html)
- [Unity Manual: Creating Models for Animation](https://docs.unity3d.com/Manual/UsingHumanoidChars.html)
- [Auto-Rig Pro: Game Engine Export Documentation](https://lucky3d.fr/auto-rig-pro/doc/ge_export_doc.html)
- [Auto-Rig Pro: Auto-Rig Documentation](https://www.lucky3d.fr/auto-rig-pro/doc/auto_rig.html)
- [Auto-Rig Pro: Quick Rig Documentation](https://www.lucky3d.fr/auto-rig-pro/doc/quick_rig_doc.html)
- [Auto-Rig Pro: Rig Features](https://www.lucky3d.fr/auto-rig-pro/doc/rig_behaviour_doc.html)
- [Unreal MetaHuman Facial Rig](https://dev.epicgames.com/documentation/en-us/metahuman/using-the-metahuman-facial-rig-in-unreal-engine)
- [Unreal MetaHuman LODs](https://dev.epicgames.com/documentation/en-us/metahuman/controlling-metahuman-levels-of-detail-lods)
- [UE5 Control Rig Documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/controls-bones-and-nulls-in-control-rig-in-unreal-engine)
- [Apple ARKit BlendShapeLocation](https://developer.apple.com/documentation/arkit/arfaceanchor/blendshapelocation)

### Industry Analysis and Comparisons
- [CGDive: Rigify vs Auto-Rig Pro Comparison](https://cgdive.com/rigify-vs-auto-rig-pro-auto-rigging-comparison/)
- [Blender Artists: Rigify vs ARP for Game Export](https://blenderartists.org/t/rigify-vs-auto-rig-pro-which-is-better-for-exporting-to-games/1487645)
- [Motion Forge: Rigify vs Auto Rig Pro](https://www.motionforgepictures.com/rigify-vs-auto-rig-pro-for-blender/)
- [Polycount: Number of Bones in Character Rig](https://polycount.com/discussion/130237/number-of-bones-in-character-rig)
- [Tech-Artists: Next Gen Console Bone Limits](https://www.tech-artists.org/t/next-gen-console-bone-limits/3949)
- [Simplygon: Bone Reduction](https://simplygon.com/features/bonereduction)
- [Enum HumanBodyBones (Complete)](https://stephenhodgson.github.io/UnityCsReference/api/UnityEngine.HumanBodyBones.html)

### Twist Bones and Deformation
- [3D Figgins: Forearm Twist Solution](https://www.3dfiggins.com/writeups/forearmTwist/)
- [Polycount: Forearm Twist Discussion](https://polycount.com/discussion/87716/forearm-twist)
- [Sol Brennan: Methods for Extra Character Deformation in Game Dev](https://sol-g-brennan.medium.com/rigging-tips-methods-for-extra-character-deformation-in-game-dev-e4c0e89e7b00)
- [Kavan et al: Skinning with Dual Quaternions](https://users.cs.utah.edu/~ladislav/kavan07skinning/kavan07skinning.html)

### Facial Rigging
- [ARKit 52 Blendshapes Ultimate Guide](https://pooyadeperson.com/the-ultimate-guide-to-creating-arkits-52-facial-blendshapes/)
- [ARKit to FACS Cheat Sheet](https://melindaozel.com/arkit-to-facs-cheat-sheet/)
- [ARKit Blendshapes Reference](https://arkit-face-blendshapes.com/)
- [Epic: Rig Logic Whitepaper](https://cdn2.unrealengine.com/rig-logic-whitepaper-v2-5c9f23f7e210.pdf)
- [MetaHuman: Tech Behind Face Rigs](https://www.metahuman.com/en-US/learning/the-tech-behind-metahuman-creator-face-rigs)

### Studio Practices
- [GDC Vault: Joint-Based Skin Deformation in God of War Ragnarok](https://gdcvault.com/play/1029203/Joint-Based-Skin-Deformation-in)
- [GDC Vault: Self-Limiting Rigging Methodology Used on God of War](https://www.gdcvault.com/play/1329/Self-Limiting-Rigging-Methodology-Used)
- [Santa Monica Studio GDC 2023 Presentations](https://sms.playstation.com/stories/gdc-2023-presentations)
- [Game Anim: Making of God of War Cinematics & Rigging](https://www.gameanim.com/2018/06/20/making-of-god-of-war-cinematics-rigging/)
- [Blender Studio: Rigging in Sprite Fright](https://studio.blender.org/blog/rigging-sprite-fright-video-introduction/)
- [Blender Studio: One Thing I've Learned - Rigging Edition](https://studio.blender.org/blog/one-thing-ive-learned-sprite-fright-rigging-edition/)
- [Blender Studio: CloudRig Introduction](https://studio.blender.org/training/blender-studio-rigging-tools/introduction/)
- [CloudRig Extension](https://extensions.blender.org/add-ons/cloudrig/)
- [Blender Studio: Sprite Fright Rigging Page](https://studio.blender.org/projects/sprite-fright/rigging/)

### FBX Export and Pipeline
- [BKJam: Exporting FBX from Blender to Unity](https://bkjam.github.io/posts/2024-10-19-blender-to-unity-settings/)
- [Polynook: Export Models from Blender to Unity](https://polynook.com/learn/lesson/how-to-export-models-from-blender-to-unity)
- [Immersive Limit: Blender to Unity Export](https://www.immersivelimit.com/tutorials/blender-to-unity-export-correct-scale-rotation)
- [Blender Manual: FBX Import-Export](https://docs.blender.org/manual/en/2.81/addons/import_export/io_scene_fbx.html)
- [Cascadeur: Twist Bones](https://cascadeur.com/help/rig/advanced_rigging/advanced_rigging_techniques/twist_bones)

### Corrective Shapes
- [Autodesk: Pose Space Deformations (Maya)](https://knowledge.autodesk.com/support/maya/learn-explore/caas/CloudHelp/cloudhelp/2018/ENU/Maya-CharacterAnimation/files/GUID-45D389D6-B8E4-4225-B27B-9927BB61C28D-htm.html)
- [CAVE Academy: Corrective Blendshapes](https://caveacademy.com/wiki/post-production-assets/rigging/rigging-training/introduction-to-rigging-course/11-corrective-blendshapes/)
- [Envato Tuts+: Rigging with Blend Shapes for Games](https://design.tutsplus.com/articles/game-character-creation-series-kila-chapter-8-rigging-with-blend-shapes--cg-32643)

### Mixamo
- [Adobe: Mixamo Rigging and Animation](https://helpx.adobe.com/creative-cloud/help/mixamo-rigging-animation.html)
- [Cascadeur: Using Mixamo Rig](https://cascadeur.com/help/getting_started/import_fbxdae/using_mixamo_rig_in_cascadeur)
- [GitHub: Mixamo Bone Renamer](https://github.com/gegamongy/MixamoBoneRenamer)
