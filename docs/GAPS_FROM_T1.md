# Gaps Found by Terminal 1 (Rigging)

## Naming Mismatch: Clavicle/Shoulder Bones

**Files:** `animation_export.py` (Terminal 2)

Terminal 2's `MIXAMO_TO_RIGIFY` mapping uses `DEF-shoulder.L/R` for clavicle bones.
Terminal 1's humanoid template (per audit contract) uses `clavicle.L/R`.

**Action needed:** Terminal 2 should either:
- Add a `DEF-clavicle.L/R` entry alongside `DEF-shoulder.L/R`, OR
- T1 and T2 agree on a single name before merge

## Naming Mismatch: Finger Bone Conventions

**Files:** `animation_export.py` (Terminal 2)

| Terminal 2 (MIXAMO mapping) | Terminal 1 (Template) |
|---|---|
| `thumb.01.L` | `thumb_01.L` |
| `f_index.01.L` | `index_01.L` |
| `f_middle.01.L` | `middle_01.L` |
| `f_ring.01.L` | `ring_01.L` |
| `f_pinky.01.L` | `pinky_01.L` |

Terminal 1 follows the audit Interface Contract naming. Terminal 2's MIXAMO mapping
uses Rigify-style dot notation and `f_` prefix for non-thumb fingers.

**Action needed:** Reconcile naming before merge. Options:
1. T1 adopts T2's naming (requires audit contract amendment)
2. T2 updates MIXAMO mapping to match T1's naming
3. Add aliasing in the retarget handler to support both

## Pre-existing Test Failure: MIXAMO Bone Count

**File:** `tests/test_functional_blender_tools_2.py:872`

Test `test_mixamo_to_rigify_has_22_entries` asserts `len(MIXAMO_TO_RIGIFY) == 22`,
but the mapping now has 52 entries (shoulders + fingers + toes were added by T2).
The test needs updating to `== 52`.

## New Twist Bones: Animation Integration

**Files:** `animation.py`, `animation_gaits.py` (Terminal 2)

Terminal 1 adds twist bones to humanoid/quadruped/dragon/bird/multi_armed templates:
- `upper_arm_twist.L/R`
- `forearm_twist.L/R`
- `thigh_twist.L/R`
- `shin_twist.L/R`

Terminal 2's animation generators should check for twist bone existence and
optionally key them (at 50% of parent rotation) for smoother deformation.

## New Facial Bones: Expression Animation

**Files:** `animation.py` (Terminal 2)

Terminal 1 expands facial rig from 19 to 22 bones (added eye.L/R, eye_target)
and adds:
- 17 FACS Action Units
- 15 Viseme shapes
- Eye tracking bone data

Terminal 2 may want to integrate these into expression animation clips
or lipsync systems.

## Shader Path Conflict: combat_vfx_templates.py

**Branches:** `audit/rigging` vs `audit/unity-vfx`

The `combat_vfx_templates.py` file (from pre-existing T3 commit on this branch)
uses `Shader.Find("Particles/Standard Unlit")` in 9 locations.
The `audit/unity-vfx` branch corrects these to URP paths:
`Shader.Find("Universal Render Pipeline/Particles/Unlit")`.

**Action needed:** When merging both branches, accept the unity-vfx version
for all 9 shader path conflicts. The URP paths are correct for the project.
