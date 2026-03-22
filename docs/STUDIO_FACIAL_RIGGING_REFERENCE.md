# Studio-Grade Facial Rigging & Weight Painting Reference

Comprehensive technical reference for implementing AAA-quality facial rigging, weight painting, lip sync, corrective shapes, and FBX export pipelines. All numbers, bone names, and settings are sourced from industry standards and engine documentation.

---

## Table of Contents

1. [Apple ARKit 52 Blendshapes](#1-apple-arkit-52-blendshapes)
2. [FACS Action Units](#2-facs-action-units)
3. [ARKit-to-FACS Mapping](#3-arkit-to-facs-mapping)
4. [MetaHuman Facial Rig](#4-metahuman-facial-rig)
5. [Bone-Based vs Blendshape vs Hybrid Rigs](#5-bone-based-vs-blendshape-vs-hybrid-rigs)
6. [Facial Bone Layout (Game-Ready)](#6-facial-bone-layout-game-ready)
7. [Jaw Collision Prevention](#7-jaw-collision-prevention)
8. [Eye Tracking Rig](#8-eye-tracking-rig)
9. [Wrinkle Map System](#9-wrinkle-map-system)
10. [Viseme / Lip Sync Standards](#10-viseme--lip-sync-standards)
11. [Coarticulation & JALI](#11-coarticulation--jali)
12. [Weight Painting Best Practices](#12-weight-painting-best-practices)
13. [Heat Diffusion vs Envelope Weighting](#13-heat-diffusion-vs-envelope-weighting)
14. [4-Influence Limit Enforcement](#14-4-influence-limit-enforcement)
15. [Dual Quaternion Skinning](#15-dual-quaternion-skinning)
16. [Corrective Shapes / Pose-Space Deformation](#16-corrective-shapes--pose-space-deformation)
17. [RBF Drivers](#17-rbf-drivers)
18. [Skinning Quality Metrics](#18-skinning-quality-metrics)
19. [Deformation Test Poses](#19-deformation-test-poses)
20. [Weight Transfer Between Rigs](#20-weight-transfer-between-rigs)
21. [FBX Export for Unity Humanoid](#21-fbx-export-for-unity-humanoid)
22. [Unity HumanBodyBones Reference](#22-unity-humanbodybones-reference)

---

## 1. Apple ARKit 52 Blendshapes

ARKit facial tracking outputs 52 blendshape coefficients, each ranging 0.0 to 1.0 (neutral to maximum). These are the industry-standard target shapes for real-time facial capture and Live Link.

### Complete List (grouped by region)

**Eyes Left (7):**
| # | Name | Description |
|---|------|-------------|
| 0 | `eyeBlinkLeft` | Closes the left eyelid |
| 1 | `eyeLookDownLeft` | Rotates left eye to look down |
| 2 | `eyeLookInLeft` | Rotates left eye toward nose (medial) |
| 3 | `eyeLookOutLeft` | Rotates left eye away from nose (lateral) |
| 4 | `eyeLookUpLeft` | Rotates left eye to look up |
| 5 | `eyeSquintLeft` | Squints the left eye |
| 6 | `eyeWideLeft` | Widens the left eye |

**Eyes Right (7):**
| # | Name | Description |
|---|------|-------------|
| 7 | `eyeBlinkRight` | Closes the right eyelid |
| 8 | `eyeLookDownRight` | Rotates right eye to look down |
| 9 | `eyeLookInRight` | Rotates right eye toward nose |
| 10 | `eyeLookOutRight` | Rotates right eye away from nose |
| 11 | `eyeLookUpRight` | Rotates right eye to look up |
| 12 | `eyeSquintRight` | Squints the right eye |
| 13 | `eyeWideRight` | Widens the right eye |

**Jaw (4):**
| # | Name | Description |
|---|------|-------------|
| 14 | `jawForward` | Moves jaw forward (protrusion) |
| 15 | `jawLeft` | Moves jaw to the left |
| 16 | `jawRight` | Moves jaw to the right |
| 17 | `jawOpen` | Opens the jaw |

**Mouth (23):**
| # | Name | Description |
|---|------|-------------|
| 18 | `mouthClose` | Closes lips together over open jaw |
| 19 | `mouthFunnel` | Funnels lips into an "O" shape |
| 20 | `mouthPucker` | Purses/puckers lips |
| 21 | `mouthLeft` | Shifts mouth to the left |
| 22 | `mouthRight` | Shifts mouth to the right |
| 23 | `mouthSmileLeft` | Raises left mouth corner (zygomatic) |
| 24 | `mouthSmileRight` | Raises right mouth corner |
| 25 | `mouthFrownLeft` | Lowers left mouth corner (depressor) |
| 26 | `mouthFrownRight` | Lowers right mouth corner |
| 27 | `mouthDimpleLeft` | Deepens left mouth corner crease |
| 28 | `mouthDimpleRight` | Deepens right mouth corner crease |
| 29 | `mouthStretchLeft` | Stretches left mouth corner laterally |
| 30 | `mouthStretchRight` | Stretches right mouth corner laterally |
| 31 | `mouthRollLower` | Rolls lower lip inward |
| 32 | `mouthRollUpper` | Rolls upper lip inward |
| 33 | `mouthShrugLower` | Pushes lower lip outward/upward |
| 34 | `mouthShrugUpper` | Pushes upper lip outward/upward |
| 35 | `mouthPressLeft` | Presses left lips together tightly |
| 36 | `mouthPressRight` | Presses right lips together tightly |
| 37 | `mouthLowerDownLeft` | Pulls lower-left lip down |
| 38 | `mouthLowerDownRight` | Pulls lower-right lip down |
| 39 | `mouthUpperUpLeft` | Raises upper-left lip |
| 40 | `mouthUpperUpRight` | Raises upper-right lip |

**Brows (5):**
| # | Name | Description |
|---|------|-------------|
| 41 | `browDownLeft` | Lowers left brow (corrugator) |
| 42 | `browDownRight` | Lowers right brow |
| 43 | `browInnerUp` | Raises inner brows (frontalis medial) |
| 44 | `browOuterUpLeft` | Raises outer left brow (frontalis lateral) |
| 45 | `browOuterUpRight` | Raises outer right brow |

**Cheeks (4):**
| # | Name | Description |
|---|------|-------------|
| 46 | `cheekPuff` | Puffs both cheeks |
| 47 | `cheekSquintLeft` | Squints/raises left cheek |
| 48 | `cheekSquintRight` | Squints/raises right cheek |

**Nose (2):**
| # | Name | Description |
|---|------|-------------|
| 49 | `noseSneerLeft` | Wrinkles left side of nose |
| 50 | `noseSneerRight` | Wrinkles right side of nose |

**Tongue (1):**
| # | Name | Description |
|---|------|-------------|
| 51 | `tongueOut` | Extends the tongue |

> **Note**: ARKit also outputs head rotation (pitch/yaw/roll) and eye gaze direction as separate transforms, not blendshapes. Total facial data = 52 blendshapes + 6 rotation values.

---

## 2. FACS Action Units

The Facial Action Coding System (Ekman & Friesen, 1978) defines 46 Action Units. Each AU maps to specific facial muscle contractions. Intensity is graded A (trace) through E (maximum).

### Main Action Units

**Upper Face:**
| AU | Name | Muscle(s) |
|----|------|-----------|
| AU1 | Inner Brow Raiser | Frontalis, pars medialis |
| AU2 | Outer Brow Raiser | Frontalis, pars lateralis |
| AU4 | Brow Lowerer | Corrugator supercilii, depressor supercilii, procerus |
| AU5 | Upper Lid Raiser | Levator palpebrae superioris |
| AU6 | Cheek Raiser | Orbicularis oculi, pars orbitalis |
| AU7 | Lid Tightener | Orbicularis oculi, pars palpebralis |

**Lower Face:**
| AU | Name | Muscle(s) |
|----|------|-----------|
| AU9 | Nose Wrinkler | Levator labii superioris alaeque nasi |
| AU10 | Upper Lip Raiser | Levator labii superioris |
| AU11 | Nasolabial Deepener | Zygomaticus minor |
| AU12 | Lip Corner Puller | Zygomaticus major |
| AU13 | Sharp Lip Puller | Levator anguli oris (caninus) |
| AU14 | Dimpler | Buccinator |
| AU15 | Lip Corner Depressor | Depressor anguli oris (triangularis) |
| AU16 | Lower Lip Depressor | Depressor labii inferioris |
| AU17 | Chin Raiser | Mentalis |
| AU18 | Lip Puckerer | Incisivii labii superioris and inferioris |
| AU20 | Lip Stretcher | Risorius with platysma |
| AU22 | Lip Funneler | Orbicularis oris |
| AU23 | Lip Tightener | Orbicularis oris |
| AU24 | Lip Pressor | Orbicularis oris |
| AU25 | Lips Part | Depressor labii inferioris, mentalis |
| AU26 | Jaw Drop | Masseter, internal pterygoid, lateral pterygoid |
| AU27 | Mouth Stretch | Pterygoids, digastric |
| AU28 | Lip Suck | Mentalis |

**Miscellaneous/Head:**
| AU | Name | Description |
|----|------|-------------|
| AU29 | Jaw Thrust | Lateral pterygoid |
| AU30 | Jaw Sideways | Internal/external pterygoid |
| AU31 | Jaw Clencher | Masseter, temporalis |
| AU32 | Lip Bite | — (non-muscular) |
| AU33 | Cheek Blow | Buccinator |
| AU34 | Cheek Puff | — |
| AU35 | Cheek Suck | Buccinator |
| AU36 | Tongue Bulge | Tongue muscles |
| AU37 | Lip Wipe | — |
| AU38 | Nostril Dilator | Nasalis, pars alaris |
| AU39 | Nostril Compressor | Nasalis, pars transversa |
| AU41 | Lid Droop | Levator palpebrae superioris relaxation |
| AU42 | Slit | Orbicularis oculi |
| AU43 | Eyes Closed | Orbicularis oculi relaxation |
| AU44 | Squint | Orbicularis oculi, corrugator |
| AU45 | Blink | Orbicularis oculi |
| AU46 | Wink | Orbicularis oculi |

---

## 3. ARKit-to-FACS Mapping

Key correspondences between ARKit blendshapes and FACS action units:

| ARKit Blendshape | FACS AU | Notes |
|------------------|---------|-------|
| `browInnerUp` | AU1 | Inner Brow Raiser |
| `browOuterUpLeft/Right` | AU2 | Outer Brow Raiser |
| `browDownLeft/Right` | AU4 | Brow Lowerer |
| `eyeWideLeft/Right` | AU5 | Upper Lid Raiser |
| `cheekSquintLeft/Right` | AU6 | Cheek Raiser |
| `eyeSquintLeft/Right` | AU7 | Lid Tightener (often confused with AU6) |
| `noseSneerLeft/Right` | AU9 | Nose Wrinkler |
| `mouthUpperUpLeft/Right` | AU10 | Upper Lip Raiser |
| `mouthSmileLeft/Right` | AU12 | Lip Corner Puller |
| `mouthDimpleLeft/Right` | AU14 | Dimpler |
| `mouthFrownLeft/Right` | AU15 | Lip Corner Depressor |
| `mouthLowerDownLeft/Right` | AU16 | Lower Lip Depressor |
| `mouthShrugLower` | AU17 | Chin Raiser |
| `mouthPucker` | AU18 | Lip Puckerer |
| `mouthStretchLeft/Right` | AU20 | Lip Stretcher |
| `mouthFunnel` | AU22 | Lip Funneler |
| `mouthPressLeft/Right` | AU23/24 | Lip Tightener/Pressor |
| `jawOpen` | AU26/27 | Jaw Drop / Mouth Stretch |
| `mouthRollLower/Upper` | AU28 | Lip Suck variant |
| `jawForward` | AU29 | Jaw Thrust |
| `jawLeft/Right` | AU30 | Jaw Sideways |
| `cheekPuff` | AU33/34 | Cheek Blow/Puff |
| `eyeBlinkLeft/Right` | AU45 | Blink |
| `tongueOut` | AU19 | Tongue Show (supplemental) |

> **Caution**: Many online ARKit-to-FACS maps confuse AU6 (cheek raiser / orbicularis oculi pars orbitalis) with AU7 (lid tightener / pars palpebralis). ARKit `cheekSquint` = AU6; ARKit `eyeSquint` = AU7.

---

## 4. MetaHuman Facial Rig

Based on Epic Games / 3Lateral's Rig Logic whitepaper:

### Key Specifications
| Parameter | Value |
|-----------|-------|
| Facial joints | ~800 |
| Expression controls | 200+ |
| Corrective expressions | 1,000+ |
| Blendshapes | 72+ (per LOD) |
| Target framerate | 30+ fps real-time evaluation |
| DNA file format | MetaHuman DNA (geometry-independent) |

### Rig Logic Architecture (4 Layers)
1. **Descriptor Layer**: Metadata (name, archetype, gender, age, LOD count)
2. **Definition Layer**: Joint names, hierarchy, bind pose matrices
3. **Behavior Layer**: Math logic driving real-time joint transforms; contains:
   - Conditional expressions
   - PSD (Pose-Space Deformation) correctives
   - Joint cluster deformers
   - Animated texture maps (wrinkle maps)
4. **Geometry Layer**: Per-LOD mesh data; can be swapped independently

### Key Innovation
MetaHuman DNA files are geometry-independent. The same DNA can drive multiple characters of different shapes/sizes. Rig Logic prunes extraneous joint deformations per-LOD for zero-cost reduction.

---

## 5. Bone-Based vs Blendshape vs Hybrid Rigs

### Comparison Table

| Factor | Bone-Based | Blendshape | Hybrid |
|--------|-----------|------------|--------|
| **Memory** | Low (transform data only) | High (full vertex deltas per shape) | Medium |
| **CPU cost** | Low (bone transforms on CPU, skinning on GPU) | Higher (CPU computes per-vertex offsets) | Medium |
| **Precision** | Limited by bone count; struggles with subtle expressions | Exact vertex positions; pixel-perfect results | Best of both |
| **Animator control** | Rotation/translation curves | Direct shape sliders | Layered control |
| **Mocap compatibility** | Requires retargeting | Direct 1:1 from ARKit/FACS | Best compatibility |
| **Combinatorial expressions** | Automatic blending via skeletal | Combinatorial explosion risk | Bones handle base, shapes handle combos |
| **Setup time** | Fast (auto-weights) | Slow (sculpt each shape) | Medium |
| **LOD scaling** | Trivial (reduce bones) | Must regenerate per LOD | Bones scale well, shapes need per-LOD |

### Recommendation for Games

**Use hybrid rigs.** Bones handle structural movement (jaw open, eye rotation, brow raise). Blendshapes add polish for close-ups (smile creases, lip compression, nasolabial folds). This is the approach used by:
- Naughty Dog (The Last of Us, Uncharted)
- CD Projekt RED (Cyberpunk 2077)
- Epic Games (MetaHuman)
- Santa Monica Studio (God of War)

### Typical Bone Budget (Game Facial Rig)

| Quality Tier | Facial Bones | Blendshapes | Total Body Bones |
|-------------|-------------|-------------|-----------------|
| Mobile/Indie | 20-30 | 15-25 | 40-60 |
| Mid-tier | 40-60 | 40-52 | 80-120 |
| AAA Hero | 80-120 | 52-100+ | 150-250 |
| AAA Cinematic | 200+ | 200+ | 300-800 |

---

## 6. Facial Bone Layout (Game-Ready)

### Recommended ~50-Bone Facial Rig

**Forehead / Brows (12):**
```
brow_inner_L, brow_inner_R
brow_mid_L, brow_mid_R
brow_outer_L, brow_outer_R
forehead_inner_L, forehead_inner_R
forehead_mid_L, forehead_mid_R
forehead_outer_L, forehead_outer_R
```

**Eyes (8):**
```
eyelid_upper_L, eyelid_upper_R
eyelid_lower_L, eyelid_lower_R
eye_L, eye_R                      (aim-constrained to look target)
eyelid_upper_outer_L, eyelid_upper_outer_R  (optional: for squint)
```

**Nose (4):**
```
nose_L, nose_R                    (nostril flare)
nose_bridge, nose_tip
```

**Cheeks (4):**
```
cheek_L, cheek_R
cheek_lower_L, cheek_lower_R
```

**Upper Lip (8):**
```
lip_upper_mid
lip_upper_L, lip_upper_R
lip_upper_outer_L, lip_upper_outer_R
lip_corner_L, lip_corner_R
lip_upper_inner                    (for mouthClose)
```

**Lower Lip + Chin (11):**
```
lip_lower_mid
lip_lower_L, lip_lower_R
lip_lower_outer_L, lip_lower_outer_R
chin_mid
chin_L, chin_R
jaw                                (rotation pivot near ear)
tongue_base, tongue_tip
```

**Hierarchy:**
```
head
  +-- jaw
  |     +-- lip_lower_* (all lower lip bones)
  |     +-- chin_*
  |     +-- tongue_base
  |           +-- tongue_tip
  +-- brow_* (all brow bones)
  +-- forehead_* (all forehead bones)
  +-- eyelid_* (all eyelid bones)
  +-- eye_L, eye_R (aim-constrained independently)
  +-- nose_*
  +-- cheek_*
  +-- lip_upper_* (upper lip stays with head, NOT jaw)
  +-- lip_corner_L, lip_corner_R
```

> **Critical**: Upper lip bones must be parented to head, NOT jaw. Lower lip bones parent to jaw. Lip corners need dual influence (head + jaw) via constraints or corrective shapes.

---

## 7. Jaw Collision Prevention

### Problem
When the jaw closes, the lower lip can intersect through the upper lip mesh.

### Solutions

**1. Lips Retain Value (Rigify / Auto-Rig Pro approach):**
- A "Lips Retain" property on the jaw controller (0.0 = lips follow jaw freely, 1.0 = lips stay sealed)
- Implemented as a Transformation constraint on lower lip bones:
  - Input: jaw rotation (X axis)
  - Output: counter-rotation on lower lip bones
  - Mapped so lips remain sealed until jaw opens beyond a threshold

**2. Clamped Driver Setup (Blender):**
```python
# Driver on lower_lip bones Y location:
# When jaw rotation < threshold, lip follows jaw
# When jaw closes past neutral, lip stops at collision plane
var = jaw_bone.rotation_euler.x
influence = max(0, var / max_jaw_open) * lips_retain_factor
```

**3. Collision Bone Method:**
- Place an invisible "collision plane" bone at the lip seal line
- Lower lip bones use a "Floor" constraint referencing this bone
- Lower lip cannot pass above the collision plane regardless of jaw position

**4. Corrective Shape Key:**
- Sculpt a `jaw_closed_lip_fix` shape key
- Drive it with jaw rotation approaching 0 (closed)
- Shape key pushes lower lip vertices downward to prevent intersection

### Bone Positioning Rules
- Jaw pivot bone: positioned near the ear (TMJ joint location)
- Upper and lower lip bones: must NOT be too close together (causes weight paint "sewing")
- Minimum gap: ~2mm at bind pose between upper and lower lip bone positions

---

## 8. Eye Tracking Rig

### Basic Setup (Blender)

**Bones Required:**
```
eye_L            (inside eye mesh, centered on iris)
eye_R            (inside eye mesh, centered on iris)
eye_target       (floating in front of face, shared look target)
eye_target_L     (optional: individual per-eye targets, parented to eye_target)
eye_target_R     (optional: individual per-eye targets)
eyelid_upper_L   (arc bone above eye)
eyelid_lower_L   (arc bone below eye)
eyelid_upper_R
eyelid_lower_R
```

**Constraints:**
1. `eye_L` and `eye_R`: **Track To** constraint targeting `eye_target`
   - Track Axis: -Z (or whichever axis points forward from the eye)
   - Up Axis: Y
   - Influence: 1.0

2. Eyelid follow (upper lid follows eye up/down):
   - **Transformation** constraint on `eyelid_upper_L`:
     - Source: `eye_L` rotation X
     - Map From: -15 deg to +25 deg (eye down to eye up)
     - Map To: -8 deg to +15 deg (lid follows ~60% of eye rotation)
   - Lower lid follows ~30% of eye movement

3. Eye movement clamping:
   - **Limit Rotation** on `eye_L` / `eye_R`:
     - Left/Right: +/- 35 degrees
     - Up: 25 degrees
     - Down: 30 degrees

### Eyelid Follow Ratios
| Eye Direction | Upper Lid Follow | Lower Lid Follow |
|---------------|-----------------|-----------------|
| Look Up | 60% of rotation | 20% of rotation |
| Look Down | 40% of rotation | 30% of rotation |
| Blink (override) | 100% closed | 100% closed |
| Squint | Independent | 50% influence |

---

## 9. Wrinkle Map System

### Overview
Wrinkle maps are additional normal/roughness/AO textures blended in at runtime based on expression intensity. They add micro-detail that bones and blendshapes alone cannot achieve.

### 13 Standard Facial Wrinkle Regions
| # | Region | Triggered By | Channel |
|---|--------|-------------|---------|
| 1 | Forehead horizontal lines | AU1+AU2 (brow raise) | R channel, Map A |
| 2 | Glabella / "11" lines | AU4 (brow furrow) | G channel, Map A |
| 3 | Crow's feet left | AU6+AU12 L (smile/squint) | B channel, Map A |
| 4 | Crow's feet right | AU6+AU12 R (smile/squint) | R channel, Map B |
| 5 | Nose bridge | AU9 (nose wrinkle) | G channel, Map B |
| 6 | Nasolabial L | AU12 L (smile) | B channel, Map B |
| 7 | Nasolabial R | AU12 R (smile) | R channel, Map C |
| 8 | Upper lip curl | AU10+AU25 | G channel, Map C |
| 9 | Lower lip / chin | AU17 (chin raise) | B channel, Map C |
| 10 | Cheek compression L | AU14 L (dimple) | Additional map |
| 11 | Cheek compression R | AU14 R (dimple) | Additional map |
| 12 | Neck platysma | AU20 (lip stretch) | Additional map |
| 13 | Under-eye bags | AU7 (lid tight) | Additional map |

### Channel Packing (3 maps, RGB = 9 regions)
- **WrinkleMap_A.tga**: R=forehead, G=glabella, B=crow_L
- **WrinkleMap_B.tga**: R=crow_R, G=nose, B=nasolabial_L
- **WrinkleMap_C.tga**: R=nasolabial_R, G=upper_lip, B=chin

### Shader Implementation (Unity URP/HDRP)
```hlsl
// In fragment shader:
float3 wrinkleA = SAMPLE_TEXTURE2D(_WrinkleMapA, sampler_WrinkleMapA, uv).rgb;
float3 wrinkleB = SAMPLE_TEXTURE2D(_WrinkleMapB, sampler_WrinkleMapB, uv).rgb;
float3 wrinkleC = SAMPLE_TEXTURE2D(_WrinkleMapC, sampler_WrinkleMapC, uv).rgb;

// Blend based on expression weights (0-1 from blendshape/bone driver)
float3 wrinkleNormal = baseNormal;
wrinkleNormal = lerp(wrinkleNormal, foreheadWrinkleNormal, wrinkleA.r * _BrowRaiseWeight);
wrinkleNormal = lerp(wrinkleNormal, glabellaWrinkleNormal, wrinkleA.g * _BrowFurrowWeight);
wrinkleNormal = lerp(wrinkleNormal, crowFeetLNormal, wrinkleA.b * _SmileLWeight);
// ... continue for all regions

// Use BlendAngleCorrectedNormals for proper normal map compositing
wrinkleNormal = BlendAngleCorrectedNormals(baseNormal, wrinkleNormal);
```

### Texture Specifications
| Property | Recommended Value |
|----------|------------------|
| Resolution | 2048x2048 (hero), 1024x1024 (NPC) |
| Format | BC5 (normal), BC7 (packed masks) |
| Wrinkle map channels | Per-region masks in RGB |
| Diffuse wrinkle overlay | Redness/darkness in separate texture |
| AO wrinkle overlay | Cavity darkening per region |

---

## 10. Viseme / Lip Sync Standards

### Oculus Lipsync 15 Visemes (Industry Standard)

| Index | Viseme | Phonemes (IPA) | Mouth Description |
|-------|--------|----------------|-------------------|
| 0 | `sil` | (silence) | Neutral/closed mouth |
| 1 | `PP` | /p/, /b/, /m/ | Lips pressed together (bilabial) |
| 2 | `FF` | /f/, /v/ | Lower lip tucked under upper teeth (labiodental) |
| 3 | `TH` | /T/, /D/ (th) | Tongue between teeth (interdental) |
| 4 | `DD` | /t/, /d/, /n/, /l/ | Tongue tip at upper teeth ridge (alveolar) |
| 5 | `kk` | /k/, /g/, /N/ (ng) | Back of tongue raised (velar) |
| 6 | `CH` | /tS/, /dZ/, /S/, /Z/ | Lips forward, teeth together (postalveolar) |
| 7 | `SS` | /s/, /z/ | Teeth together, lips slightly open (sibilant) |
| 8 | `nn` | /n/, /l/ (alt) | Tongue at ridge, mouth slightly open |
| 9 | `RR` | /r/ | Lips slightly rounded, tongue pulled back |
| 10 | `aa` | /A:/, /aI/, /aU/ | Mouth wide open (open vowel) |
| 11 | `E` | /E/, /eI/ | Mouth medium-open, spread (mid vowel) |
| 12 | `ih` | /I/, /i:/ | Mouth narrow-open, spread (close vowel) |
| 13 | `oh` | /O:/, /oI/ | Lips rounded, medium-open (back rounded) |
| 14 | `ou` | /u:/, /U/, /w/ | Lips tightly rounded (close rounded) |

### Microsoft Azure Speech 22 Visemes

| ID | Phonemes | Description |
|----|----------|-------------|
| 0 | (silence) | Neutral |
| 1 | /ae/, /ax/, /ah/ | Open jaw, wide mouth |
| 2 | /aa/ | Wide open mouth |
| 3 | /ao/ | Rounded, open |
| 4 | /ey/, /eh/, /uh/ | Mid-open |
| 5 | /er/ | Slightly rounded |
| 6 | /y/, /iy/, /ih/ | Narrow spread |
| 7 | /w/, /uw/ | Tight round |
| 8 | /ow/ | Medium round |
| 9 | /aw/ | Wide to round transition |
| 10 | /oy/ | Round to spread transition |
| 11 | /ay/ | Open to spread transition |
| 12 | /h/ | Neutral (breathy) |
| 13 | /r/ | Slight pucker |
| 14 | /l/ | Tongue tip up |
| 15 | /s/, /z/ | Teeth close |
| 16 | /sh/, /zh/ | Forward lip pucker |
| 17 | /th/, /dh/ | Tongue between teeth |
| 18 | /f/, /v/ | Lower lip under upper teeth |
| 19 | /d/, /t/, /n/ | Tongue at ridge |
| 20 | /k/, /g/, /ng/ | Back tongue |
| 21 | /p/, /b/, /m/ | Lips together |

### VRChat Viseme Standard
Uses the Oculus 15-viseme set. The FX animator layer converts audio analysis (integer 0-14) into blendshape or bone animation each frame.

---

## 11. Coarticulation & JALI

### Coarticulation Basics
In natural speech, mouth shapes blend into neighboring phonemes rather than hitting each target discretely. Two types:
- **Anticipatory**: Mouth begins forming the next sound before the current one finishes
- **Carryover**: Residual shape from the previous sound bleeds into the current one

### Dominance Model
Each viseme has a "dominance function" that defines how strongly it pulls the mouth toward its target shape. Visemes with high dominance (bilabials like /p/, /b/, /m/) override neighbors. Low-dominance visemes (like vowels) are more susceptible to blending.

### JALI (Jaw And Lip Integration)
Developed at University of Toronto. Patent-pending system used in major games.

**Core Concept**: Speech is decomposed into two independent anatomical channels:
1. **Jaw**: Primarily controls mouth opening (vertical)
2. **Lips**: Primarily controls mouth shaping (horizontal/rounding)

**Articulation Continuum:**
| Style | Jaw Contribution | Lip Contribution | Example |
|-------|-----------------|------------------|---------|
| Hypo-articulated (drone) | High | Low | Mumbling, bored speech |
| Normal conversation | Medium | Medium | Standard dialogue |
| Hyper-articulated | Low | High | Shouting, whispering carefully |

**Implementation Parameters:**
- `hyper_factor` (0-1): Blend between jaw-dominant and lip-dominant articulation
- `energy` (0-1): Overall expression intensity
- `emotion_offset`: Per-emotion bias for resting face shape

### Smoothing Parameters for Real-Time
| Parameter | Recommended Value | Notes |
|-----------|------------------|-------|
| Viseme transition time | 60-100ms | Too fast = jitter, too slow = mushy |
| Lookahead window | 2-3 phonemes | For anticipatory coarticulation |
| Smoothing kernel | Cubic bezier | Better than linear interpolation |
| Silence hold threshold | 150ms | Below this, mouth stays in last shape |

---

## 12. Weight Painting Best Practices

### Workflow (AAA Standard)

1. **Start with automatic weights** (heat diffusion) for baseline
2. **Test immediately** with Mixamo retargeted animations or standard test poses
3. **Fix hot spots first**: shoulders, hips, spine twist areas
4. **Polish iteratively**: Fix during actual animation review, not in isolation
5. **Final pass**: Verify in game engine with actual gameplay animations

### Problem Areas and Solutions

**Shoulders (Hardest Area):**
- Use twist bones: `upperArm_twist_L` between shoulder and elbow
- Minimum 2 twist bones in the upper arm
- Clavicle MUST lift when arm goes above 90 degrees
- Paint clavicle influence extending into the upper chest/back area
- Common mistake: raising arm too high without lifting clavicle

**Hips/Thighs:**
- Gluteal area needs gradual falloff from pelvis to thigh
- Inner thigh requires careful painting to avoid "diaper" effect
- Use twist bone between hip and knee
- Weight the lower belly/groin to the pelvis bone, NOT the thigh

**Elbows/Knees:**
- Keep weights clean on single axis (hinge joints)
- Paint a slightly harder falloff on the outer edge (bony side)
- Paint a slightly softer falloff on the inner edge (fleshy side)
- Add corrective shapes for full flex positions

**Wrists:**
- 3 twist joints recommended: `forearm_twist_1`, `_2`, `_3`
- Evenly spaced between elbow and wrist joint
- Prevents the classic "candy wrapper" twist artifact

**Spine:**
- Paint overlapping gradients between spine segments
- Each spine bone should influence ~2 vertebrae above and below
- Chest area: ensure breathing animations don't deform the neck

### Mesh Construction Rules for Clean Deformation
- Place edge loops at every joint (elbow, knee, shoulder, hip, wrist, ankle)
- Minimum 3 edge loops per joint for clean bending
- High-deformation areas need evenly spaced topology
- Triangles/n-gons at joints = guaranteed bad deformation

### Tools and Plugins

| Tool | Platform | Purpose |
|------|----------|---------|
| ngSkinTools (now free) | Maya | Layer-based weight painting |
| EasyWeight | Blender | QoL improvements for weight painting |
| Weight Layers addon | Blender | Procedural weight maps with layer system |
| Voxel Heat Diffuse Skinning | Blender | Better automatic weights for complex meshes |

---

## 13. Heat Diffusion vs Envelope Weighting

### Heat Diffusion (Blender: "Automatic Weights")
- Algorithm: Bone heat based on distance from each vertex to each bone
- Treats bones as heat sources; weights computed from heat distribution
- **Best for**: Organic characters, humanoid rigs, complex multi-bone setups
- **Limitations**: Can fail on non-manifold meshes ("Bone Heat Weighting Failed" error)
- **Fix failures**: Remove doubles, fill holes, ensure manifold mesh, recalculate normals

### Envelope Weighting (Blender: "Envelope Weights")
- Based on bone envelope radius (visible as wireframe capsule around each bone)
- Influence = distance from vertex to bone envelope boundary
- **Best for**: Simple rigs, mechanical objects, multi-layer clothing (Lolita skirts)
- **Limitations**: Crude results on complex organic shapes; time-consuming to tune envelopes

### Recommendation
Always start with **heat diffusion** for characters. Reserve envelope weighting for:
- Clothing/accessories that need simple influence
- Mechanical parts with clear bone ownership
- Cases where heat diffusion fails and mesh repair isn't possible

---

## 14. 4-Influence Limit Enforcement

### Why 4 Bones Per Vertex?
GPU skinning stores bone weights as `vec4` (4 floats). Most engines pass bone indices and weights as 4-component vectors per vertex. Exceeding 4 requires extra vertex attributes and shader passes.

### Engine Limits
| Engine/Platform | Default Max Influences | Configurable |
|----------------|----------------------|-------------|
| Unity (default) | 4 | Yes: 1, 2, or 4 in Quality Settings |
| Unity (URP/HDRP) | 4 | Up to 255 (Compute Deformation) |
| Unreal Engine | 4 (8 optional) | `MAX_TOTAL_INFLUENCES` in project settings |
| Mobile (OpenGL ES) | 4 | Hard limit on some GPUs |
| iOS (Metal) | 4 (default) | Configurable |
| WebGL | 4 | Hard limit |
| PS5/Xbox Series | 4-8 | Per-title configuration |

### Enforcement in Blender
1. **Weight Paint mode** > Weights menu > **Limit Total** (set to 4)
2. Or via Python:
```python
import bpy
# Select mesh object
obj = bpy.context.active_object
# Limit vertex groups per vertex
bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4)
```
3. After limiting, **Normalize All** to ensure weights sum to 1.0:
```python
bpy.ops.object.vertex_group_normalize_all(group_select_mode='BONE_DEFORM', lock_active=False)
```

### Best Practice
- Always run Limit Total BEFORE export
- Then Normalize All
- Verify: no vertex should have weights summing to > 1.001 or < 0.999
- Check for zero-weight vertices (not influenced by any bone)

---

## 15. Dual Quaternion Skinning

### What It Solves
Linear Blend Skinning (LBS) causes **volume loss** at bent joints (candy-wrapper effect on twisted limbs, collapsed shoulders). Dual Quaternion Skinning (DQS) preserves volume by interpolating rigid transforms in dual-quaternion space.

### Blender Setup
1. Select the mesh
2. Properties > Modifiers > Armature modifier
3. Check **"Preserve Volume"** (this enables DQS)

### Trade-offs
| | Linear Blend (LBS) | Dual Quaternion (DQS) |
|---|---|---|
| Volume at bends | Collapses | Preserved |
| Twist behavior | Candy wrapper | Clean |
| Elbows/Knees | Can bulge unnaturally with DQS | May over-inflate |
| Performance | Slightly faster | Slightly slower |
| Blending | Smooth gradients | Can produce artifacts at weight boundaries |

### Hybrid LBS/DQS Approach
Use a per-vertex weight map to blend between LBS and DQS:
- Shoulders: 80% DQS / 20% LBS
- Forearm twist: 100% DQS
- Elbows: 50% DQS / 50% LBS (prevents bulging)
- Knees: 40% DQS / 60% LBS
- Spine: 70% DQS / 30% LBS

> **Unity Note**: Unity does not natively support DQS in the standard skinning pipeline. You need a custom compute shader or the Burst-based DQS package. Unreal supports it via project settings.

---

## 16. Corrective Shapes / Pose-Space Deformation

### What They Are
Shape keys (blendshapes) driven by bone rotation to fix deformation artifacts that skinning alone cannot handle. They activate automatically when a joint reaches a specific pose.

### Standard Corrective Shape Set (Humanoid)

**Shoulder Correctives (6-8):**
| Shape Name | Trigger | Purpose |
|-----------|---------|---------|
| `shoulder_L_fwd_90` | Upper arm forward 90 deg | Fixes deltoid collapse |
| `shoulder_L_back_45` | Upper arm back 45 deg | Fixes rear deltoid/lat intersection |
| `shoulder_L_up_90` | Upper arm raised 90 deg (abduction) | Fixes armpit collapse |
| `shoulder_L_up_135` | Upper arm raised 135+ deg | Fixes extreme raise |
| `shoulder_L_down_45` | Upper arm down past rest | Fixes side compression |
| `shoulder_L_twist_90` | Upper arm twist 90 deg | Fixes bicep/tricep twist |
| *(Mirror all for _R)* | | |

**Elbow Correctives (2):**
| Shape Name | Trigger | Purpose |
|-----------|---------|---------|
| `elbow_L_bend_90` | Forearm bend 90 deg | Sharpens elbow crease, pushes flesh outward |
| `elbow_L_bend_140` | Forearm bend 140 deg | Prevents mesh intersection at full flex |

**Wrist Correctives (4):**
| Shape Name | Trigger | Purpose |
|-----------|---------|---------|
| `wrist_L_bend_fwd` | Hand bent forward 60 deg | Fixes tendon volume loss |
| `wrist_L_bend_back` | Hand bent backward 60 deg | Fixes top-of-wrist compression |
| `wrist_L_twist_90` | Forearm twist near wrist | Fixes spiral twist artifacts |
| `wrist_L_ulnar` | Hand bent sideways (ulnar dev.) | Fixes side compression |

**Hip/Thigh Correctives (4-6):**
| Shape Name | Trigger | Purpose |
|-----------|---------|---------|
| `hip_L_fwd_90` | Thigh forward 90 deg | Fixes groin/hip crease |
| `hip_L_back_30` | Thigh backward 30 deg | Fixes gluteal stretch |
| `hip_L_out_45` | Thigh outward (abduction) | Fixes inner thigh |
| `hip_L_in_30` | Thigh inward (adduction) | Fixes outer hip compression |

**Knee Correctives (2):**
| Shape Name | Trigger | Purpose |
|-----------|---------|---------|
| `knee_L_bend_90` | Shin bent 90 deg | Sharpens kneecap, adds calf bulge |
| `knee_L_bend_140` | Shin bent 140 deg | Prevents calf-thigh intersection |

**Spine Correctives (2-4):**
| Shape Name | Trigger | Purpose |
|-----------|---------|---------|
| `spine_twist_L_45` | Spine twist 45 deg | Preserves torso volume |
| `spine_bend_fwd_45` | Spine bend forward 45 deg | Fixes belly compression |

### Total: 20-30 corrective shapes for a full humanoid (games); 50-100+ for film.

### Driver Setup in Blender
```python
# Example: Drive shoulder_L_fwd_90 from upper_arm_L X rotation
# 1. Add shape key "shoulder_L_fwd_90" on the mesh
# 2. Right-click the Value slider > Add Driver
# 3. Configure:
#    - Type: Scripted Expression
#    - Expression: max(0, var / 1.5708)    # 1.5708 = pi/2 = 90 degrees
#    - Variable "var":
#      - Type: Single Property or Transform Channel
#      - Bone: upper_arm_L
#      - Transform Channel: X Rotation (Local Space)
```

For multi-axis correctives (like shoulders), use **Rotational Difference** driver type:
- Add a reference "rest" bone that doesn't rotate
- Driver measures the angle between the animated bone and the rest bone
- This captures total deviation regardless of which axis was rotated

---

## 17. RBF Drivers

### What They Are
Radial Basis Function drivers interpolate between multiple sculpted corrective shapes based on multi-dimensional input (e.g., shoulder rotation across X, Y, and Z simultaneously). They solve the combinatorial explosion problem of single-axis drivers.

### Available Blender Addons

| Addon | Author | License | Features |
|-------|--------|---------|----------|
| **RBF Nodes** | Ingo Clemens (Brave Rabbit) | Commercial | Node-based, visual, many-to-many mapping |
| **RBF Drivers** | James Snowden | Commercial ($20-40) | Property-based, simpler UI, good documentation |

### Workflow (RBF Drivers addon)
1. Pose the shoulder in its rest position
2. Create a shape key (sculpt the corrective)
3. Pose the shoulder in a new position (e.g., arm raised + twisted)
4. Sculpt another shape key for that pose
5. Repeat for 4-8 key poses
6. Select all shape keys + the bone inputs
7. Create the RBF driver - it automatically interpolates between all poses

### Advantage Over Single-Axis Drivers
- **Single-axis**: Need separate shapes for fwd, back, up, down, twist = 5+ shapes that don't combine well
- **RBF**: Define 4-8 key poses and the solver smoothly blends between ALL of them based on actual bone orientation. One RBF driver replaces 5-10 single-axis drivers.

---

## 18. Skinning Quality Metrics

### How Studios Measure Weight Paint Quality

**Quantitative Metrics:**
| Metric | Description | Acceptable Range |
|--------|-------------|-----------------|
| Vertex displacement error | Average Euclidean distance between deformed and ground-truth positions | < 1mm at rest pose scale |
| L1 norm | Sum of absolute weight errors per vertex | < 0.05 |
| Skinning precision | % of vertices assigned to correct bones | > 95% |
| Recall | % of bone influence regions correctly captured | > 90% |
| Motion loss | Deformation fidelity under LBS across test poses | < 2mm average |
| L1 variance | Consistency of errors across vertices | Low (uniform quality) |
| Max influence count | Highest # of bones influencing any single vertex | <= 4 (games) |
| Zero-weight vertex count | Vertices not influenced by any bone | 0 (must be zero) |
| Weight sum deviation | How far vertex weight totals deviate from 1.0 | < 0.001 |

**Qualitative Checks:**
- No mesh interpenetration at any test pose
- No "candy wrapper" twist artifacts
- No volume loss > 10% at any joint
- Smooth weight gradient transitions (no hard steps)
- Symmetrical weights (L/R difference < 0.01)

### Automated Validation Script (Blender Python)
```python
import bpy
import numpy as np

def validate_skinning(obj, max_influences=4):
    """Validate skinning quality on a mesh object."""
    mesh = obj.data
    issues = []

    for v in mesh.vertices:
        groups = [(g.group, g.weight) for g in v.groups if g.weight > 0.001]

        # Check influence count
        if len(groups) > max_influences:
            issues.append(f"Vertex {v.index}: {len(groups)} influences (max {max_influences})")

        # Check weight sum
        weight_sum = sum(w for _, w in groups)
        if abs(weight_sum - 1.0) > 0.001:
            issues.append(f"Vertex {v.index}: weight sum = {weight_sum:.4f}")

        # Check zero weights
        if len(groups) == 0:
            issues.append(f"Vertex {v.index}: NO WEIGHTS (unweighted)")

    return issues
```

---

## 19. Deformation Test Poses

### Standard 12-Pose Validation Set

| # | Pose Name | What It Tests |
|---|-----------|---------------|
| 1 | **T-Pose** (bind) | Baseline reference; should show no deformation |
| 2 | **A-Pose** | Arms at 45 deg; tests shoulder in most common game pose |
| 3 | **Arms Forward 90** | Both arms straight forward; tests front deltoid + chest |
| 4 | **Arms Up 180** | Arms straight up; tests full shoulder range + armpit |
| 5 | **Arms Behind Back** | Hands clasped behind; tests rear deltoid + scapula |
| 6 | **Deep Squat** | Knees fully bent, hips flexed; tests hip/knee/ankle |
| 7 | **Lunge** | One leg forward, one back; tests hip flexor/extensor asymmetry |
| 8 | **Full Arm Twist** | Forearms rotated 180 deg; tests twist joint chain |
| 9 | **Spine Forward Bend** | Bowing forward 90 deg; tests belly/back deformation |
| 10 | **Spine Twist** | Torso rotated 90 deg; tests oblique/spine weights |
| 11 | **Fetal Curl** | Curled up; extreme test of all joints at maximum flex |
| 12 | **Combat Pose** | Action stance (wide legs, arms up); tests game-typical pose |

### Facial Test Poses (8)

| # | Expression | What It Tests |
|---|-----------|---------------|
| 1 | Neutral | Baseline |
| 2 | Full smile | AU6+AU12; tests cheek, nasolabial, lip corners |
| 3 | Full frown | AU1+AU4+AU15; tests brow, lip corners |
| 4 | Surprise | AU1+AU2+AU5+AU26; tests brow raise + jaw open |
| 5 | Anger | AU4+AU5+AU7+AU23; tests brow furrow + lip tighten |
| 6 | Jaw full open | AU27; tests jaw range + neck/chin |
| 7 | Lip pucker | AU18; tests lip rounding + cheek compression |
| 8 | Asymmetric smile | AU12L only; tests unilateral deformation |

---

## 20. Weight Transfer Between Rigs

### Blender Data Transfer Modifier Method

**Setup:**
1. Place the NEW mesh in the same location as the OLD (weighted) mesh
2. Select NEW mesh > Add Modifier > **Data Transfer**
3. Source: Select OLD mesh
4. Enable **Vertex Data** > **Vertex Groups**
5. Vertex Mapping: **Nearest Face Interpolated** (best for different topology)
6. Apply modifier

**Settings Detail:**
| Parameter | Recommended Value |
|-----------|------------------|
| Vertex Mapping | Nearest Face Interpolated |
| Source Layers Selection | All Layers (creates matching vertex groups) |
| Generate Data Layers | Enabled (so missing groups get created) |
| Mix Mode | Replace |
| Mix Factor | 1.0 |

**Important Caveats:**
- Source mesh must have ALL vertex groups that target needs
- If "Create Data" is disabled, target must already have matching vertex groups
- Works best when meshes are similar proportions; large shape differences = bad transfer
- Always follow up with manual cleanup on problem areas (shoulders, hips)

### Alternative: Transfer Weights Operator
1. Select target mesh
2. Shift-select source mesh
3. **Object > Link/Transfer Data > Transfer Mesh Data > Vertex Groups**
4. This is the operator-based (non-modifier) approach

---

## 21. FBX Export for Unity Humanoid

### Recommended Blender FBX Export Settings

```
Export FBX (.fbx)

Main Tab:
  Path Mode:           Copy (embed textures)
  Batch Mode:          Off

Include:
  [x] Selected Objects  (or all, depending on workflow)
  Object Types:         [x] Armature  [x] Mesh
  [ ] Custom Properties (usually not needed)

Transform:
  Scale:               1.0
  Apply Scalings:      "FBX Units Scale"
  Forward:             -Z Forward
  Up:                  Y Up
  [ ] Apply Unit       (leave unchecked)
  [x] Use Space Transform
  [ ] Apply Transform  (leave UNCHECKED to avoid armature scale x100 bug)

Geometry:
  Smoothing:           Face
  [x] Apply Modifiers  (bakes armature modifier result)
  [ ] Loose Edges
  [ ] Tangent Space

Armature:
  [ ] Add Leaf Bones   (UNCHECK - Unity doesn't need them; they create
                         extra bones that confuse Avatar mapping)
  Primary Bone Axis:   Y Axis
  Secondary Bone Axis: X Axis
  Armature FBX Node Type: Null

Animation (if exporting animations):
  [x] Bake Animation
  Key All Bones:       [x] (ensures clean animation curves)
  [x] NLA Strips       (if using NLA for multiple clips)
  [ ] All Actions      (check this INSTEAD of NLA if each Action = one clip)
  Force Start/End Keying: [x]
  Simplify:            0.0 (no keyframe reduction)
```

### Critical Notes

**Scale Bug Prevention:**
- "Apply Scalings" = `FBX Units Scale` with "Apply Transform" UNCHECKED is the most reliable combo
- In Unity: set Scale Factor to `1` in the FBX import inspector (not 0.01)
- Blender's default unit scale = 1.0 meter = 1 Unity unit

**Leaf Bones:**
- **UNCHECK** "Add Leaf Bones" for Unity Humanoid
- Leaf bones create extra end-effector bones (e.g., "LeftHand_end") that confuse Unity's Avatar auto-mapping
- If your rig already has tip bones, leaf bones will duplicate them

**Animation Clips via NLA:**
1. Create Actions in Blender (Idle, Walk, Run, Attack)
2. Push each Action down to an NLA strip
3. Name each strip clearly (Unity uses the strip name)
4. Last NLA strip = T-pose or A-pose (becomes Unity's default import pose)
5. Export with "NLA Strips" checked

### Bone Naming for Unity Auto-Mapping

Unity's Humanoid Avatar system auto-maps bones by name. Use these naming conventions for highest auto-detection success:

| Body Part | Recommended Name | Alternatives That Work |
|-----------|-----------------|----------------------|
| Root | `Hips` | `pelvis`, `hip` |
| Spine | `Spine` | `spine_01` |
| Chest | `Spine1` or `Chest` | `spine_02`, `upper_spine` |
| Upper Chest | `Spine2` or `UpperChest` | `spine_03` |
| Neck | `Neck` | `neck_01` |
| Head | `Head` | `head` |
| Left Shoulder | `LeftShoulder` | `shoulder_L`, `clavicle_L` |
| Left Upper Arm | `LeftUpperArm` | `upperArm_L`, `arm_L` |
| Left Lower Arm | `LeftLowerArm` | `forearm_L`, `lowerArm_L` |
| Left Hand | `LeftHand` | `hand_L` |
| Right Shoulder | `RightShoulder` | `shoulder_R`, `clavicle_R` |
| Right Upper Arm | `RightUpperArm` | `upperArm_R`, `arm_R` |
| Right Lower Arm | `RightLowerArm` | `forearm_R`, `lowerArm_R` |
| Right Hand | `RightHand` | `hand_R` |
| Left Upper Leg | `LeftUpperLeg` | `thigh_L`, `upperLeg_L` |
| Left Lower Leg | `LeftLowerLeg` | `shin_L`, `calf_L`, `lowerLeg_L` |
| Left Foot | `LeftFoot` | `foot_L` |
| Left Toes | `LeftToes` | `toe_L`, `ball_L` |
| Right Upper Leg | `RightUpperLeg` | `thigh_R`, `upperLeg_R` |
| Right Lower Leg | `RightLowerLeg` | `shin_R`, `calf_R` |
| Right Foot | `RightFoot` | `foot_R` |
| Right Toes | `RightToes` | `toe_R`, `ball_R` |

**Finger Naming Pattern** (optional bones):
```
{Side}{Finger}{Segment}
Example: LeftThumbProximal, LeftIndexIntermediate, RightPinkyDistal

Segments: Proximal, Intermediate, Distal
Fingers: Thumb, Index, Middle, Ring, Pinky (or Little)
```

**Naming Rules:**
- Left/Right prefix is case-sensitive in Unity (`Left` not `left`)
- Use consistent L/R convention: either `_L`/`_R` suffix OR `Left`/`Right` prefix
- Avoid dots in bone names (Blender uses dots like `arm.L`; rename to `arm_L` before export)

---

## 22. Unity HumanBodyBones Reference

### Complete Enum (55 bones, 0-54)

**Required (15 minimum):**
```
Hips = 0
LeftUpperLeg = 1
RightUpperLeg = 2
LeftLowerLeg = 3
RightLowerLeg = 4
LeftFoot = 5
RightFoot = 6
Spine = 7
Chest = 8
Neck = 9         (optional but recommended)
Head = 10
LeftShoulder = 11
RightShoulder = 12
LeftUpperArm = 13
RightUpperArm = 14
LeftLowerArm = 15
RightLowerArm = 16
LeftHand = 17
RightHand = 18
```

**Optional Body:**
```
LeftToes = 19
RightToes = 20
LeftEye = 21
RightEye = 22
Jaw = 23
UpperChest = 54
```

**Left Hand Fingers (15):**
```
LeftThumbProximal = 24
LeftThumbIntermediate = 25
LeftThumbDistal = 26
LeftIndexProximal = 27
LeftIndexIntermediate = 28
LeftIndexDistal = 29
LeftMiddleProximal = 30
LeftMiddleIntermediate = 31
LeftMiddleDistal = 32
LeftRingProximal = 33
LeftRingIntermediate = 34
LeftRingDistal = 35
LeftLittleProximal = 36
LeftLittleIntermediate = 37
LeftLittleDistal = 38
```

**Right Hand Fingers (15):**
```
RightThumbProximal = 39
RightThumbIntermediate = 40
RightThumbDistal = 41
RightIndexProximal = 42
RightIndexIntermediate = 43
RightIndexDistal = 44
RightMiddleProximal = 45
RightMiddleIntermediate = 46
RightMiddleDistal = 47
RightRingProximal = 48
RightRingIntermediate = 49
RightRingDistal = 50
RightLittleProximal = 51
RightLittleIntermediate = 52
RightLittleDistal = 53
```

### Required Hierarchy Pattern
```
Hips (ROOT - must be root of hierarchy)
  +-- Spine
  |     +-- Chest
  |     |     +-- [UpperChest]     (optional)
  |     |     |     +-- Neck
  |     |     |     |     +-- Head
  |     |     |     |           +-- [LeftEye]
  |     |     |     |           +-- [RightEye]
  |     |     |     |           +-- [Jaw]
  |     |     |     +-- LeftShoulder
  |     |     |     |     +-- LeftUpperArm
  |     |     |     |           +-- LeftLowerArm
  |     |     |     |                 +-- LeftHand
  |     |     |     |                       +-- [Fingers...]
  |     |     |     +-- RightShoulder
  |     |     |           +-- RightUpperArm
  |     |     |                 +-- RightLowerArm
  |     |     |                       +-- RightHand
  |     |     |                             +-- [Fingers...]
  +-- LeftUpperLeg
  |     +-- LeftLowerLeg
  |           +-- LeftFoot
  |                 +-- [LeftToes]
  +-- RightUpperLeg
        +-- RightLowerLeg
              +-- RightFoot
                    +-- [RightToes]
```

> **Twist bones, helper bones, and facial bones** are ignored by the Humanoid avatar mapper. They remain in the skeleton but are animated as Generic bones. This is fine -- they still drive corrective shapes and deformation.

---

## Sources

- [Apple ARKit BlendShapeLocation Documentation](https://developer.apple.com/documentation/arkit/arfaceanchor/blendshapelocation)
- [ARKit 52 Blendshapes Ultimate Guide](https://pooyadeperson.com/the-ultimate-guide-to-creating-arkits-52-facial-blendshapes/)
- [ARKit Face Blendshapes Reference](https://arkit-face-blendshapes.com/)
- [ARKit to FACS Cheat Sheet](https://melindaozel.com/arkit-to-facs-cheat-sheet/)
- [FACS Cheat Sheet - Melinda Ozel](https://melindaozel.com/facs-cheat-sheet/)
- [FACS - CMU](https://www.cs.cmu.edu/~face/facs.htm)
- [Facial Action Coding System - Wikipedia](https://en.wikipedia.org/wiki/Facial_Action_Coding_System)
- [FACS Action Unit Reference - Py-Feat](https://py-feat.org/pages/au_reference.html)
- [Rig Logic Whitepaper (MetaHuman)](https://cdn2.unrealengine.com/rig-logic-whitepaper-v2-5c9f23f7e210.pdf)
- [MetaHuman Face Rig Tech Explained - CGPress](https://cgpress.org/archives/metahuman-face-rig-tech-explained.html)
- [Demystifying Rig Logic for MetaHumans](https://kalyansthupili.wordpress.com/2025/04/14/demystifying-rig-logic-for-metahumans/)
- [Facial Rigging: Bones vs Shape Keys - Whizzy Studios](https://www.whizzystudios.com/post/facial-rigging-in-blender-bones-vs-shape-keys-which-should-you-use)
- [Facial Animation Blendshapes or Bones - Polycount](https://polycount.com/discussion/45238/facial-animation-blendshapes-or-bones)
- [Joints or Blendshapes - Method:J](https://www.methodj.com/joints-or-blendshapes/)
- [Bone Count in Character Rig - Polycount](https://polycount.com/discussion/130237/number-of-bones-in-character-rig)
- [Animating Speech & Mastering Facial Rigging - 80.lv](https://80.lv/articles/animating-speech-mastering-facial-rigging-guidelines-for-game-developers)
- [Weight Painting Best Practices - Whizzy Studios](https://www.whizzystudios.com/post/best-practices-for-weight-painting-in-character-rigging)
- [Painting Weights - 3DFiggins](https://www.3dfiggins.com/writeups/paintingWeights/)
- [Corrective Joint Rigging - 3DFiggins](https://www.3dfiggins.com/writeups/corrective/)
- [Rigging Tips for Game Dev - Sol Brennan](https://sol-g-brennan.medium.com/rigging-tips-methods-for-extra-character-deformation-in-game-dev-e4c0e89e7b00)
- [Choosing Weighting Method in Blender](https://www.toolify.ai/ai-news/choosing-the-best-weighting-method-in-blender-3d-167703)
- [Blender Armature Deform Parenting Manual](https://docs.blender.org/manual/en/latest/animation/armatures/skinning/parenting.html)
- [Bone Influence Limit - Blender Projects](https://developer.blender.org/T31919)
- [Bone Influence Limits - Unity Discussions](https://discussions.unity.com/t/what-do-most-consoles-and-game-engines-limit-bone-skin-weights-in-production-builds/917062)
- [Dual Quaternion Skinning - Rodolphe Vaillant](https://rodolphe-vaillant.fr/entry/29/dual-quaternions-skinning-tutorial-and-c-codes)
- [Skinning with Dual Quaternions - Academic Paper](https://users.cs.utah.edu/~ladislav/kavan07skinning/kavan07skinning.pdf)
- [Pose Shape Keys - Blender Studio](https://studio.blender.org/tools/addons/pose_shape_keys)
- [Corrective Shape Keys - MakeHuman](https://static.makehumancommunity.org/oldsite/documentation/corrective_shape_keys.html)
- [RBF Drivers for Blender](https://rbfdrivers.readthedocs.io/)
- [RBF Nodes for Blender - Brave Rabbit](https://braverabbit.gumroad.com/l/rbfNodesBlender)
- [Oculus Viseme Reference](https://developers.meta.com/horizon/documentation/unreal/audio-ovrlipsync-viseme-reference/)
- [Microsoft Azure Speech Viseme](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-speech-synthesis-viseme)
- [Viseme Cheat Sheet](https://melindaozel.com/viseme-cheat-sheet/)
- [VRChat Visemes Wiki](https://wiki.vrchat.com/wiki/Visemes)
- [JALI Lip Sync Paper](https://dgp.toronto.edu/~elf/JALISIG16.pdf)
- [Dynamic Wrinkles - Character Creator](https://www.reallusion.com/character-creator/dynamic-wrinkle.html)
- [Dynamic Wrinkle Maps in UE4](https://leahmcewen.artstation.com/blog/0Yl7/dynamic-wrinkle-maps-in-ue4)
- [MetaHuman Wrinkle Maps - Joe Raasch](https://www.joeraasch.com/projects/metahuman-wrinkle-maps)
- [FACS Rigging & Texture Blending](https://adamspring.co.uk/2020/05/25/facs-rigging-texture-blending-digital-humans/)
- [SALSA LipSync for Unity](https://crazyminnowstudio.com/unity-3d/lip-sync-salsa/)
- [Advanced Facial Rigging - Blender Studio](https://studio.blender.org/training/facial-rigging/)
- [AutoRigPro Documentation](https://www.lucky3d.fr/auto-rig-pro/doc/auto_rig.html)
- [Eye Rig in Blender Tutorial](https://www.tripo3d.ai/blog/collect/tutorial--how-to-create-an-eye-rig-in-blender-0r6yjnxh9qg)
- [Eye Control System with Control Rig UE5](https://80.lv/articles/learn-how-to-rig-eyes-with-control-rig-in-unreal-engine-5-6)
- [Data Transfer Modifier - Blender Manual](https://docs.blender.org/manual/en/latest/modeling/modifiers/modify/data_transfer.html)
- [EasyWeight Blender Addon](https://extensions.blender.org/add-ons/easyweight/)
- [Blender FBX Export Manual](https://docs.blender.org/manual/en/2.81/addons/import_export/io_scene_fbx.html)
- [Blender to Unity Export Guide - Immersive Limit](https://www.immersivelimit.com/tutorials/blender-to-unity-export-correct-scale-rotation)
- [Blender to Unity Settings - RustyCruise Labs](https://rustycruiselabs.com/devlogs/generic/2024-10-19-blender-to-unity-settings/)
- [Unity Manual: Creating Models for Animation](https://docs.unity3d.com/Manual/UsingHumanoidChars.html)
- [Unity HumanBodyBones API](https://docs.unity3d.com/ScriptReference/HumanBodyBones.html)
- [Unity Mecanim Humanoids Blog](https://unity.com/blog/engine-platform/mecanim-humanoids)
- [HumanRig: Automatic Rigging - CVPR 2025](https://arxiv.org/html/2412.02317v1)
- [Forearm Twist Solution - 3DFiggins](https://www.3dfiggins.com/writeups/forearmTwist/)
- [Naughty Dog Wrist Rig (Ellie, TLOU)](https://www.joeraasch.com/projects/metahumanizing-twinblast)
- [ngSkinTools](https://www.ngskintools.com/)
- [T-Pose vs A-Pose - Polycount](https://polycount.com/discussion/192810/t-pose-vs-a-pose)
