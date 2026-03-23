# Gaps Found by Terminal 1 (Rigging)

## ~~Naming Mismatch: Clavicle/Shoulder Bones~~ RESOLVED

T1 renamed `clavicle.L/R` to `shoulder.L/R` to match T2's `MIXAMO_TO_RIGIFY` mapping.
No merge conflict expected.

## ~~Naming Mismatch: Finger Bone Conventions~~ RESOLVED

T1 adopted T2's Rigify-style naming convention:
- `thumb_01` -> `thumb.01` (dot separator)
- `index_01` -> `f_index.01` (f_ prefix + dot separator)
- `middle_01` -> `f_middle.01`, `ring_01` -> `f_ring.01`, `pinky_01` -> `f_pinky.01`

No merge conflict expected.

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
