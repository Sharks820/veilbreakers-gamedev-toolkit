# Terminal 1: Blender Rigging & Skeletal Systems

## Git Setup (DO THIS FIRST)
```bash
cd C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit
git pull origin master
git checkout -b audit/rigging
```
Commit to `audit/rigging` branch. Do NOT commit to master.

---

## Scope
All rigging, weight painting, facial rig, and skeletal system improvements in the Blender addon handlers.

## YOUR Files (ONLY touch these)
```
blender_addon/handlers/rig_setup.py
blender_addon/handlers/rig_templates.py
blender_addon/handlers/rig_validation.py
blender_addon/handlers/rig_weights.py
blender_addon/handlers/rig_facial.py
blender_addon/handlers/rig_spring.py
blender_addon/handlers/rig_ik.py
blender_addon/handlers/rig_retarget.py
```
New files must go in `blender_addon/handlers/` with `rig_` prefix, or in `tests/` with `test_rig_` prefix.

## DO NOT TOUCH (owned by other terminals)
```
blender_addon/handlers/__init__.py          # SHARED — see Registration Protocol below
blender_addon/handlers/animation_*.py       # Terminal 2
blender_addon/handlers/environment.py       # Terminal 4
blender_addon/handlers/worldbuilding.py     # Terminal 4
blender_addon/handlers/export.py            # Phase 1 (done)
src/veilbreakers_mcp/blender_server.py      # Terminal 4
src/veilbreakers_mcp/unity_tools/*          # Terminal 3 & 4
src/veilbreakers_mcp/shared/unity_templates/* # Terminal 3 & 4
```

## Handler Registration Protocol
When you create new handler functions that need command dispatch:
1. Create the handler function in your `rig_*.py` file
2. Do NOT edit `handlers/__init__.py` or `blender_server.py`
3. Instead, create `docs/T1_REGISTRATIONS.md` listing every new handler:
   ```
   # T1 Handler Registrations
   ## New entries for COMMAND_HANDLERS in handlers/__init__.py
   from .rig_setup import handle_rig_add_twist_bones
   "rig_add_twist_bones": handle_rig_add_twist_bones,

   ## New action Literals for blender_server.py blender_rig tool
   "add_twist_bones" | "limit_weights" | ...
   ```
4. These will be integrated after all terminals merge.

---

## Interface Contract (READ THIS — other terminals depend on you)

### Bone Naming Convention (Terminal 2 depends on this)
Terminal 2's animation generators reference bones by name. You MUST preserve these existing names:
```
spine, spine.001, spine.002, spine.003 (torso chain)
shoulder.L/R, upper_arm.L/R, forearm.L/R, hand.L/R
thigh.L/R, shin.L/R, foot.L/R, toe.L/R
head, neck
```
When adding twist bones, use this naming pattern:
```
upper_arm_twist.L/R    (between shoulder and forearm)
forearm_twist.L/R      (between forearm and hand)
thigh_twist.L/R        (between thigh and shin)
shin_twist.L/R         (between shin and foot)
```

### Rig Template Output Format
Each rig template function must continue to return a dict with:
```python
{
    "armature_name": str,
    "bone_count": int,
    "bone_names": list[str],   # ALL bone names including new twist bones
    "template_type": str,      # humanoid, quadruped, etc.
}
```
Do NOT change this return format — Terminal 2 and export handlers consume it.

### Weight Data Format
Weight painting results must continue to use Blender's native vertex group system. The 4-influence limit should be enforced as a post-processing step that normalizes existing weights, NOT by changing the weighting algorithm itself.

---

## Tasks

### P2-A1: Add Twist Bones to All 10 Rig Templates (16h)
**What:** Add 2 twist bones per limb segment to ALL 10 templates: humanoid, quadruped, bird, insect, arachnid, serpent, aquatic, hexapod, tentacle, amorphous.

**How:**
- Twist bones go BETWEEN joint bones (e.g., `upper_arm_twist.L` between `shoulder.L` and `forearm.L`)
- Each twist bone gets a `COPY_ROTATION` constraint targeting its parent bone
- Constraint influence: 0.5 (splits the rotation between parent and twist bone)
- Lock rotation to the bone's local twist axis only (typically Y for arms, Y for legs)
- For non-humanoid templates, adapt to their limb topology (e.g., hexapod has 6 leg pairs)
- **Verify:** 180-degree forearm rotation should NOT produce candy-wrapper

### P2-A3: Fix Spring Bone System (8h)
**What:** Current spring bones use `DAMPED_TRACK` with no target — non-functional.

**How:**
- Implement mass-spring-damper dynamics: `F = -k*x - c*v + m*g`
- Parameters per spring chain: `mass` (0.1-2.0), `stiffness` (0.1-10.0), `damping` (0.1-5.0), `gravity_factor` (0.0-1.0)
- Use Blender's `frame_change_post` handler to update spring bone positions each frame
- Support chain-based dynamics (each bone in chain affects the next)
- Collision with a simple sphere collider (optional parameter)
- Must work for: hair, capes, tails, tentacles, accessories, chains

### P2-A5: Fix Bone Rolls for All Templates (4h)
**What:** Zero bone roll values currently set — causes axis flipping in Unity Humanoid.

**How:**
- Humanoid spine chain: roll = 0 (forward-facing)
- Arms: upper_arm roll = 0, forearm roll = 90° (for proper twist axis)
- Legs: thigh roll = 0, shin roll = 0
- Hands/feet: aligned to world axes
- Head/neck: roll = 0
- Use `bone.roll = math.radians(X)` for each bone
- **Verify:** Import FBX into Unity, configure as Humanoid — should auto-map without errors

### P2-A6: Add 4-Influence-Per-Vertex Weight Limit (4h)
**What:** Unity supports max 4 bone influences per vertex. Excess causes artifacts.

**How:**
- After auto-weighting (`bpy.ops.object.parent_set(type='ARMATURE_AUTO')`), run a cleanup pass
- For each vertex: get all vertex group weights, sort descending, keep top 4, normalize to sum=1.0
- Implement as `enforce_weight_limit(obj, max_influences=4)`
- Call this automatically after any weight painting operation
- Log how many vertices were affected (for debugging)

### P2-A7: Expand Facial Rig (16h)
**What:** Current: 19 bones, 3 expressions. Need FACS + visemes + eye tracking.

**How:**
- **FACS blendshapes** (shape keys driven by bones): AU1 (inner brow raise), AU2 (outer brow raise), AU4 (brow lower), AU5 (upper lid raise), AU6 (cheek raise), AU7 (lid tightener), AU9 (nose wrinkle), AU10 (upper lip raise), AU12 (lip corner pull/smile), AU15 (lip corner depress), AU17 (chin raise), AU20 (lip stretch), AU23 (lip tightener), AU25 (lips part), AU26 (jaw drop), AU27 (mouth stretch), AU28 (lip suck)
- **Visemes** (shape keys): sil, PP, FF, TH, DD, kk, CH, SS, nn, RR, aa, E, ih, oh, ou
- **Eye tracking**: 4 bones (eye.L, eye.R, eyelid_upper.L/R, eyelid_lower.L/R), look target bone, eyelid follow via driver (lid follows eye rotation at 0.3 influence)
- Shape keys driven by bone transforms via Blender drivers

### P3-C6: Multi-Armed Creature Support (14h)
**What:** VeilBreakers has 4-armed and 6-armed monsters. Only 2-arm chains exist.

**How:**
- Add `arm_count` parameter to humanoid/monster rig templates (2, 4, or 6)
- Shoulder attachment points spaced evenly on torso (for 4-arm: upper and lower pairs; for 6-arm: three pairs)
- Each arm pair gets independent IK chains with unique pole targets
- Weight painting: gradual falloff between adjacent arm influence zones
- Naming: `upper_arm_A.L/R`, `upper_arm_B.L/R`, `upper_arm_C.L/R` (A=top pair, etc.)

### P5-Q1: Corrective Blend Shapes (24h)
**What:** Zero corrective shapes exist. Joints collapse at extreme angles.

**How:**
- For each major joint, create shape keys that activate based on bone rotation:
  - Shoulder flexion (>60°): restore deltoid volume
  - Shoulder abduction (>45°): prevent armpit collapse
  - Elbow flexion (>90°): restore bicep/forearm volume
  - Knee flexion (>90°): restore quad/calf volume
  - Hip flexion (>60°): prevent groin collapse
- Use Blender shape key drivers: `driver.expression = "max(0, var - threshold) * strength"`
- Driver variable: bone's rotation on the flexion axis
- At minimum 2 correctives per joint (flexion + secondary axis)

---

## Post-Task Protocol

### After EACH task:
1. Run ONLY your relevant tests first:
   ```bash
   cd Tools/mcp-toolkit && python -m pytest tests/ -k "rig" --tb=short -q
   ```
2. Then run the full suite to check for regressions:
   ```bash
   cd Tools/mcp-toolkit && python -m pytest tests/ --tb=short -q
   ```
3. If ANY failures, fix and re-scan. Repeat until CLEAN.
4. Pull and rebase before committing:
   ```bash
   git pull origin master --rebase
   git add blender_addon/handlers/rig_*.py tests/test_rig_*.py
   git commit -m "$(cat <<'EOF'
   <type>: <description>

   Co-Authored-By: Claude <noreply@anthropic.com>
   EOF
   )"
   ```

### Commit types: `feat:` (new), `fix:` (bug), `test:` (tests only)

### If you find gaps in OTHER terminals' files:
Write to `docs/GAPS_FROM_T1.md` — do NOT edit their files.

---

## Quality Bar
- Twist bones: 180° forearm rotation = no candy-wrapper
- Spring bones: visible secondary motion when parent moves
- Bone rolls: Unity Humanoid auto-maps without errors
- Weight limit: no vertex exceeds 4 influences
- Facial rig: all 17 FACS AUs and 15 visemes functional
- All new handler functions have tests
- All tests pass after every commit
