# Terminal 2: Procedural Animation & Gaits

## Git Setup (DO THIS FIRST)
```bash
cd C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit
git pull origin master
git checkout -b audit/animation
```
Commit to `audit/animation` branch. Do NOT commit to master.

---

## Scope
All procedural animation generation — gait engines, combat animations, creature locomotion, timing profiles, and IK solvers.

## YOUR Files (ONLY touch these)
```
blender_addon/handlers/animation.py          # Main animation handler (generate, idle, custom)
blender_addon/handlers/animation_gaits.py    # Gait engines (biped, quadruped, hexapod, etc.)
blender_addon/handlers/animation_export.py   # FBX batch export, Mixamo retarget
blender_addon/handlers/_combat_timing.py     # Combat timing data (Frame-accurate hit/cancel windows)
tests/test_animation_handlers.py
tests/test_animation_gaits.py
tests/test_animation_export.py
```
New files must go in `blender_addon/handlers/` with `animation_` prefix, or in `tests/` with `test_animation_` prefix.

## DO NOT TOUCH (owned by other terminals)
```
blender_addon/handlers/__init__.py          # SHARED — see Registration Protocol below
blender_addon/handlers/rigging.py           # Terminal 1
blender_addon/handlers/rigging_advanced.py  # Terminal 1
blender_addon/handlers/rigging_templates.py # Terminal 1
blender_addon/handlers/rigging_weights.py   # Terminal 1
blender_addon/handlers/environment.py       # Terminal 4
blender_addon/handlers/environment_scatter.py # Terminal 4
blender_addon/handlers/worldbuilding.py     # Terminal 4
blender_addon/handlers/worldbuilding_layout.py # Terminal 4
blender_addon/handlers/_terrain_*.py        # Terminal 4
blender_addon/handlers/_scatter_engine.py   # Terminal 4
blender_addon/handlers/_building_grammar.py # Terminal 4
blender_addon/handlers/_dungeon_gen.py      # Terminal 4
blender_addon/handlers/export.py            # Phase 1 (done)
src/veilbreakers_mcp/blender_server.py      # Terminal 4
src/veilbreakers_mcp/unity_tools/*          # Terminal 3 & 4
src/veilbreakers_mcp/shared/unity_templates/* # Terminal 3 & 4
```

## Handler Registration Protocol
When you create new handler functions:
1. Create the function in your `animation_*.py` file
2. Do NOT edit `handlers/__init__.py` or `blender_server.py`
3. Create `docs/T2_REGISTRATIONS.md` listing every new handler:
   ```
   # T2 Handler Registrations
   ## New entries for COMMAND_HANDLERS in handlers/__init__.py
   from .animation_generate import handle_generate_spell_cast
   "generate_spell_cast": handle_generate_spell_cast,

   ## New action Literals for blender_server.py blender_animation tool
   "generate_spell_cast" | "generate_hover" | ...
   ```

---

## Interface Contract (READ THIS)

### You CONSUME from Terminal 1 (Rigging)
T1 is adding twist bones and changing rig templates. You must reference bones by the ACTUAL CURRENT naming convention:
```
# CURRENT (these exist NOW — safe to always use):
spine, spine.001, spine.002, spine.003, spine.004, spine.005  (.005 = head)
upper_arm.L/R, forearm.L/R, hand.L/R
thigh.L/R, shin.L/R, foot.L/R
tail, tail.001, tail.002  (quadruped/dragon)
wing_upper.L/R, wing_fore.L/R, wing_tip.L/R  (dragon/bird)
```
NOTE: There is NO separate `shoulder.L/R`, `head`, `neck`, or `toe.L/R` bone yet. `spine.005` IS the head. T1 will add `clavicle.L/R` and finger/toe bones as upgrades.

**New twist bones from T1** (check existence before keying):
`upper_arm_twist.L/R`, `forearm_twist.L/R`, `thigh_twist.L/R`, `shin_twist.L/R`

**New bones T1 may add** (always check `armature.data.bones.get("name")` before keying):
`clavicle.L/R`, finger bones (`thumb_01-03`, etc.), `toe.L/R`

Your generators MUST work with or without these new bones (graceful fallback).

### You EXPOSE to Terminal 3 (Unity VFX)
T3 generates Unity C# AnimatorControllers that consume the animations you create. Your animations must:
- Use consistent animation clip naming: `{creature}_{gait}_{speed}` (e.g., `humanoid_walk_normal`)
- Export root motion data in a standard format (root bone = first bone in hierarchy)
- Combat animations must tag keyframes with the timing data from `_combat_timing.py`

### _combat_timing.py Interface
T3's combo VFX system reads timing data. You MUST preserve the existing data structure:
```python
{
    "anticipation_frames": int,
    "active_frames": int,
    "recovery_frames": int,
    "cancel_window_start": int,
    "cancel_window_end": int,
    "vfx_frame": int,
}
```
You may ADD new fields (e.g., `vfx_frames: list[int]` for multi-hit) but do NOT remove or rename existing fields.

---

## Tasks

### P2-A2: Replace Single-Sine Gait Engine (12h)
**What:** Current engine = single sine wave per joint. Looks robotic.

**How:**
- Multi-harmonic system: `θ(t) = A₁sin(ωt + φ₁) + A₂sin(2ωt + φ₂) + A₃sin(3ωt + φ₃)`
- Each joint gets independent: amplitude array `[A₁,A₂,A₃]`, phase offsets `[φ₁,φ₂,φ₃]`
- Replace linear keyframe interpolation with cubic Bezier easing
- Hip joint: add lateral sway component (sine at half frequency of step cycle)
- Torso: add counter-rotation (opposite phase to hip rotation)
- Head: add stabilization (dampened inverse of spine motion)
- Keep existing function signatures — this is a drop-in replacement of the internal engine

### P2-A4: Add Spell-Cast Animation Type (12h)
**What:** Zero magic animations. Critical for VOID, SURGE, MEND brands.

**How:**
- 3 cast types, each as a handler function:
  - `generate_channel`: arms raise gradually, energy gathering gesture, body tension increases, looping hold phase
  - `generate_release`: sharp thrust/push, recoil recovery, energy dispersal
  - `generate_sustain`: stable stance, rhythmic pulse on arms/hands, looping
- Hand variants: `cast_hand` param: `"left"` | `"right"` | `"both"`
- Each type should have anticipation -> active -> recovery phases matching `_combat_timing.py` format
- Add timing entries to `_combat_timing.py`:
  ```python
  "channel": {"anticipation_frames": 12, "active_frames": -1, "recovery_frames": 8, ...}  # -1 = looping
  "release": {"anticipation_frames": 8, "active_frames": 4, "recovery_frames": 12, ...}
  "sustain": {"anticipation_frames": 6, "active_frames": -1, "recovery_frames": 10, ...}
  ```

### P2-A8: Add Curve Tangent Types (4h)
**What:** All keyframes use linear tangents. Motion looks mechanical.

**How:**
- After inserting keyframes, set tangent type on the F-curves:
  ```python
  for fcurve in action.fcurves:
      for kf in fcurve.keyframe_points:
          kf.interpolation = 'BEZIER'
          kf.handle_left_type = 'AUTO_CLAMPED'
          kf.handle_right_type = 'AUTO_CLAMPED'
  ```
- Add `tangent_type` parameter to all generate functions: `"AUTO_CLAMPED"` (default), `"BEZIER"`, `"LINEAR"`
- Apply to ALL existing generators (walk, run, attack, idle, fly, custom)
- Keep LINEAR as an option for mechanical/robot animations

### P2-A9: Fix Biped Walk (8h)
**What:** Current walk = marching robot. Need biomechanically correct gait.

**How (per-joint breakdown):**
- **Pelvis:** vertical bounce (2x step frequency, small amplitude), lateral sway (1x, toward stance leg), forward tilt
- **Hip:** flexion/extension cycle with asymmetric timing (stance phase longer than swing)
- **Knee:** flex during swing phase, extend during stance, slight flex at heel strike
- **Ankle:** dorsiflexion during swing, plantarflexion at toe-off, controlled landing at heel strike
- **Spine:** counter-rotation to pelvis (shoulders twist opposite to hips)
- **Arms:** counter-swing (opposite to ipsilateral leg), elbow slight flex during forward swing
- **Head:** stabilization — minimal movement, gaze forward
- Use gait cycle phases: heel strike (0%) → foot flat (15%) → midstance (30%) → heel off (50%) → toe off (62%) → midswing (75%) → heel strike (100%)

### P2-A10: Fix Quadruped Gaits (8h)
**What:** "Walk" is a trot, "run" is a bound. Need proper gaits.

**How:**
- **Walk** (4-beat): LH → LF → RH → RF, each leg independent, 3 legs on ground minimum, phase offsets: LH=0, LF=0.25, RH=0.5, RF=0.75
- **Trot** (2-beat): diagonal pairs (LF+RH, RF+LH), phase offset 0.5 between pairs (keep existing, just label correctly)
- **Canter** (3-beat): one hind → diagonal pair → one fore, asymmetric with lead leg
- **Gallop** (4-beat): RH → LH → RF → LF, suspension phase (all feet off ground), distinct lead leg, spine flexion/extension cycle
- `gait` param accepts: `"walk"` | `"trot"` | `"canter"` | `"gallop"` (was: `"walk"` | `"run"`)
- Keep backward compat: `"run"` maps to `"gallop"`

### P3-C3: Combat Command Flow (32h)
**What:** Only attack exists. Need full combat animation vocabulary.

**Implement as separate handler functions — one per command type:**

**P0 (must have):**
- `generate_command_receive`: subtle nod/ready stance, 8-12 frames
- `generate_combat_idle`: brand parameter selects stance style (IRON=heavy wide, GRACE=flowing sway, SURGE=twitchy shifts, DREAD=unnaturally still)
- `generate_approach`: walk toward target position, wind-up begins in last 25% of approach
- `generate_return_to_formation`: post-attack walk back, weapon lowered
- `generate_guard`: raise guard pose, arms/shield up, damage reduction visual hint

**P1 (should have):**
- `generate_flee`: turn and run, stumble variant at low HP (add `stumble: bool` param)
- `generate_target_switch`: head turn → body pivot → settle into new facing
- `generate_synergy_activation`: team flash pose, brand-colored energy pulse

**P2 (nice to have):**
- `generate_ultimate_windup`: extended anticipation (2-3x normal), energy gathering
- `generate_victory_pose`: brand-specific celebration
- `generate_defeat_collapse`: brand-specific death (IRON=crumble, VENOM=dissolve, VOID=implode)

### P3-C5: Floating Creature Hover System (10h)
**What:** Flying monsters T-pose in place. No hover system.

**How:**
- `generate_hover_idle`: vertical bob (sine, 0.5-1.0 Hz), slight lateral drift, body tilt
- `generate_hover_move`: banking on turns (roll toward turn direction), altitude transitions
- `generate_wing_flap`: if armature has wing bones, sync flap cycle to vertical bob
- `generate_tentacle_float`: for amorphous/tentacle creatures, sinusoidal tentacle wave
- Parameters: `bob_amplitude`, `bob_frequency`, `bank_angle`, `drift_amount`

### P5-Q2: IK Foot Placement with Ground-Contact Solver (16h)
**What:** IK chains exist but no ground adaptation.

**How:**
- Generate an animation post-processing function (not real-time — bakes corrected keyframes)
- For each frame: raycast downward from each foot bone
- Adjust foot bone position to terrain surface
- Rotate foot to match terrain normal (ankle correction)
- Adjust hip height based on lowest foot position
- Support flat ground, slopes, and discrete steps
- Output: corrected action with ground-contact keyframes baked in

### P5-Q6: Per-Brand Animation Timing Profiles (12h)
**What:** All creatures animate at same speed. Brands need distinct timing feel.

**How:**
- Add to `_combat_timing.py` a `BRAND_TIMING_MODIFIERS` dict:
  ```python
  BRAND_TIMING_MODIFIERS = {
      "IRON":   {"anticipation_scale": 1.5, "active_scale": 1.0, "recovery_scale": 1.3, "easing": "ease_in_out_cubic"},
      "SURGE":  {"anticipation_scale": 0.5, "active_scale": 0.7, "recovery_scale": 0.6, "easing": "ease_out_expo"},
      "SAVAGE": {"anticipation_scale": 0.8, "active_scale": 0.9, "recovery_scale": 0.5, "easing": "ease_in_quad"},
      "VENOM":  {"anticipation_scale": 1.2, "active_scale": 0.4, "recovery_scale": 1.5, "easing": "ease_in_expo"},
      "GRACE":  {"anticipation_scale": 0.9, "active_scale": 1.1, "recovery_scale": 0.9, "easing": "ease_in_out_sine"},
      "DREAD":  {"anticipation_scale": 1.3, "active_scale": 0.8, "recovery_scale": 1.0, "easing": "linear_with_pauses"},
      "VOID":   {"anticipation_scale": 1.0, "active_scale": 1.0, "recovery_scale": 1.0, "easing": "time_warp"},
      "LEECH":  {"anticipation_scale": 1.1, "active_scale": 1.0, "recovery_scale": 1.4, "easing": "ease_in_sticky"},
      "MEND":   {"anticipation_scale": 1.0, "active_scale": 1.2, "recovery_scale": 0.8, "easing": "ease_in_out_sine"},
      "RUIN":   {"anticipation_scale": 0.7, "active_scale": 0.6, "recovery_scale": 0.7, "easing": "chaotic_random"},
  }
  ```
- All combat animation generators apply brand modifier when `brand` param is provided
- `anticipation_scale` multiplies the number of anticipation frames, etc.

### P5-Q7: Amorphous Creature Animation (20h)
**What:** Blob creatures completely unsupported (1/10).

**How:**
- `generate_blob_locomotion`: body compression/expansion cycle for movement (scale X/Z vs Y alternation)
- `generate_pseudopod_reach`: shape key animation — extends a limb-like protrusion toward a target direction
- `generate_blob_idle`: subtle pulsing scale, surface ripple via shape keys
- `generate_blob_attack`: rapid pseudopod extension + retraction
- `generate_blob_split`: scale down + duplicate visual (for split abilities)
- Uses shape keys extensively — create shape keys programmatically, then animate them
- Works with the amorphous rig template from T1

---

## Post-Task Protocol

### After EACH task:
1. Run your relevant tests:
   ```bash
   cd Tools/mcp-toolkit && python -m pytest tests/ -k "animation or combat_timing" --tb=short -q
   ```
2. Full suite regression check:
   ```bash
   cd Tools/mcp-toolkit && python -m pytest tests/ --tb=short -q
   ```
3. If ANY failures, fix and re-scan. Repeat until CLEAN.
4. Pull and rebase before committing:
   ```bash
   git fetch origin master && git rebase origin/master
   git add blender_addon/handlers/animation_*.py src/veilbreakers_mcp/shared/_combat_timing.py tests/test_animation_*.py
   git commit -m "$(cat <<'EOF'
   <type>: <description>

   Co-Authored-By: Claude <noreply@anthropic.com>
   EOF
   )"
   ```

### Commit types: `feat:` (new), `fix:` (bug), `refactor:` (restructure)

### If you find gaps in OTHER terminals' files:
Write to `docs/GAPS_FROM_T2.md` — do NOT edit their files.

---

## APPENDIX E — Additional Audit Findings (Originally Missing)

### G13: Mixamo Retarget Drops Finger Bones and Hip Translation
**File:** `animation_export.py` (lines 34-62 mapping, lines 772-776 constraints)
**What:** Mixamo retarget only creates COPY_ROTATION constraints — drops ALL 30 finger bone rotations and hip TRANSLATION (only copies hip rotation). Characters will have frozen fingers and floating root.
**How:**
- Add finger bone mappings to the Mixamo → VB bone name mapping dict
- Add COPY_LOCATION constraint on the hip/root bone (not just COPY_ROTATION)
- Verify: retargeted animation should move the character through space AND animate fingers

### G15: AnimationEvent Bridge — Blender Timing to Unity Clips
**File:** `animation_export.py` + `_combat_timing.py`
**What:** `_combat_timing.py` produces frame-accurate timing data, but `animation_export.py` doesn't serialize AnimationEvents into the exported FBX or generate a companion .anim.meta file. Unity has no way to receive the timing data.
**How:**
- During batch_export, for each animation clip, generate a JSON sidecar file `{clip_name}.timing.json` containing the combat timing data
- OR: create a Unity editor script (write to T3's scope via GAPS file) that reads timing JSON and inserts AnimationEvents post-import
- Recommend: generate the JSON sidecar (simpler, no cross-terminal dependency)

### UPGRADE: Root Motion Quality
**What:** Audit Section 5 notes root motion extraction exists but isn't integrated with FBX batch export.
**How:** When `batch_export` runs, automatically extract root motion from the root bone and bake it as proper FBX root motion data. The root bone's world-space translation should be zeroed out and transferred to the FBX's root motion curves. This ensures Unity's `Apply Root Motion` checkbox works correctly.

### UPGRADE: Arachnid Rotation Axis Fix
**What:** Audit Section 5 notes arachnid legs rotate on wrong axis (bone Y instead of local Z for lateral spread).
**How:** In the arachnid gait generator, change the rotation axis for leg spread from the bone's Y axis to local Z. This makes legs spread laterally (like a real spider) instead of rotating forward/backward.

---

## Quality Bar
- Biped walk: natural to a non-technical observer, proper heel-toe cycle
- Quadruped gaits: walk/trot/canter/gallop visually distinct
- Brand timing: IRON attacks feel perceptibly slower/heavier than SURGE
- Combat flow: all P0 commands implemented and smooth
- Hover system: creatures visually float, bank into turns
- Amorphous: blob creatures can move, attack, and idle with visible deformation
- Mixamo retarget: fingers animate, hip translates
- Root motion: exported clips work with Unity's Apply Root Motion
- Arachnid: legs spread laterally like a real spider
- No linear tangents on organic motion (except when explicitly requested)
- `_combat_timing.py` backward compatible — no removed/renamed fields
- All new code has tests
- All tests pass after every commit
