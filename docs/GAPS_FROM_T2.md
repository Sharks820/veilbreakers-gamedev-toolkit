# Gaps Found by Terminal 2 (Animation)

## Terminal 1 (Rigging) — test_rigging_templates.py failures

The following 15 tests in `test_rigging_templates.py` fail due to missing bones
in the rigging templates. These are T1's responsibility:

### Missing Clavicle Bones
- `test_has_clavicles`: HUMANOID_BONES missing `clavicle.L` / `clavicle.R`
- `test_clavicle_parents_spine003`: KeyError on `clavicle.L`
- `test_upper_arm_parents_clavicle`: Expects upper_arm parent = clavicle, but currently it's spine.003

### Missing Finger Bones
- `test_has_all_finger_bones`: HUMANOID_BONES missing finger bones (`thumb_01.L` through `pinky_03.R`)
- `test_finger_01_parents_hand`: KeyError on finger bones
- `test_finger_chain_parents`: KeyError on finger bones

### Missing Toe Bones
- `test_has_toe_bones`: HUMANOID_BONES missing `toe.L` / `toe.R`
- `test_toe_parents`: KeyError on `toe.L`

### Missing Twist Bones
- `test_has_arm_twist_bones[humanoid]`: Missing `upper_arm_twist.L/R`, `forearm_twist.L/R`
- `test_has_leg_twist_bones[humanoid]`: Missing `thigh_twist.L/R`, `shin_twist.L/R`
- `test_twist_bone_parents`: KeyError on twist bones

### Missing Dragon Wing Finger Bones
- `test_has_wing_finger_bones`: DRAGON_BONES missing `wing_finger_1.L` through `wing_finger_3.L/R`
- `test_wing_finger_parents`: KeyError on wing finger bones
- `test_wing_finger_lr_symmetry`: KeyError on wing finger bones

### Bone Roll Mismatch
- `test_humanoid_forearm_rolls`: Expects forearm.L roll = 1.5708 (pi/2), but current value is 0.0

## Impact on T2

Animation generators reference bones by the CURRENT naming convention and
gracefully fall back when optional bones (twist, clavicle, finger, toe)
don't exist. All T2 handlers use `armature.data.bones.get("name")` pattern
before keying, so no crashes will occur if these bones are missing.

When T1 adds these bones, T2 animations will automatically use them if present.

## Terminal 3 (Unity VFX/Content) — No gaps found

T2's animation clip naming follows the documented contract:
`{creature}_{gait}_{speed}` format. Combat timing data structure is
backward-compatible (no fields removed/renamed, new fields added).
