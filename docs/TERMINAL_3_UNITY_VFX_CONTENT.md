# Terminal 3: VeilBreakers Unity Content & VFX

## Git Setup (DO THIS FIRST)
```bash
cd C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit
git pull origin master
git checkout -b audit/unity-vfx
```
Commit to `audit/unity-vfx` branch. Do NOT commit to master.

---

## Scope
All Unity C# template generation for VFX, evolution system, capture system, corruption variants, combat VFX, cinematic camera, and animation layering.

## YOUR Files (ONLY touch these)
```
src/veilbreakers_mcp/shared/unity_templates/vfx_templates.py
src/veilbreakers_mcp/shared/unity_templates/vfx_mastery_templates.py
src/veilbreakers_mcp/shared/unity_templates/animation_templates.py
src/veilbreakers_mcp/shared/unity_templates/cinematic_templates.py
src/veilbreakers_mcp/shared/unity_templates/camera_templates.py
src/veilbreakers_mcp/unity_tools/vfx.py
src/veilbreakers_mcp/unity_tools/camera.py
```
New files must go in `src/veilbreakers_mcp/shared/unity_templates/` or `tests/` (prefixed `test_vfx_`, `test_camera_`, `test_cinematic_`, or `test_evolution_`).

## DO NOT TOUCH (owned by other terminals)
```
blender_addon/                              # Terminal 1 & 2 (all Blender handlers)
src/veilbreakers_mcp/blender_server.py      # Terminal 4
src/veilbreakers_mcp/shared/security.py     # Shared (frozen)
src/veilbreakers_mcp/shared/unity_templates/shader_templates.py  # Terminal 4
src/veilbreakers_mcp/shared/unity_templates/world_templates.py   # Terminal 4
src/veilbreakers_mcp/shared/unity_templates/game_templates.py    # Terminal 4
src/veilbreakers_mcp/shared/unity_templates/gameplay_templates.py # Terminal 4
src/veilbreakers_mcp/shared/unity_templates/content_templates.py # Terminal 4
src/veilbreakers_mcp/shared/unity_templates/scene_templates.py   # Terminal 4
src/veilbreakers_mcp/shared/unity_templates/prefab_templates.py  # Terminal 4
src/veilbreakers_mcp/shared/unity_templates/ui_templates.py      # Terminal 4
src/veilbreakers_mcp/unity_tools/scene.py   # Phase 1 (done)
blender_addon/handlers/_combat_timing.py    # Terminal 2
```

## CRITICAL: Dissolve Shader Ownership
The audit calls for a dissolve shader with `_DissolveProgress`. The generic dissolve shader in `shader_templates.py` belongs to Terminal 4.

**YOUR approach:** Generate the evolution dissolve shader as INLINE ShaderLab/HLSL within your `vfx_templates.py` or a new `evolution_templates.py` file. Name it `VB_EvolutionDissolve` to avoid collision with T4's generic `VB_Dissolve` shader. This is a VFX-specific shader, not a general-purpose one.

---

## Interface Contract (READ THIS)

### You CONSUME from Terminal 2 (Animation)
T2 generates Blender-side animations. Your Unity AnimatorController templates should reference animation clips by the naming convention T2 uses:
```
{creature}_{gait}_{speed}     → e.g., humanoid_walk_normal
{creature}_{attack}_{type}    → e.g., humanoid_attack_slash
{creature}_{command}_{type}   → e.g., humanoid_combat_idle
```
Your templates should use placeholder clip names that match this pattern. The actual clips get assigned in Unity after FBX import.

### You CONSUME from Terminal 2 (_combat_timing.py)
Combat timing data format (T2 preserves this, you can rely on it):
```python
{
    "anticipation_frames": int,
    "active_frames": int,
    "recovery_frames": int,
    "cancel_window_start": int,
    "cancel_window_end": int,
    "vfx_frame": int,           # existing — single VFX trigger
    "vfx_frames": list[int],    # NEW from T2 — multi-hit VFX triggers (may not exist yet)
}
```
Your combo VFX system should check for `vfx_frames` first, fall back to `[vfx_frame]` if absent.

### C# Code Generation Rules
- Import sanitization: `from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier`
- Use Cinemachine 3.x API: `CinemachineCamera`, `CinemachineFollow`, `CinemachineRotationComposer` (NOT legacy CM2)
- Use PrimeTween (NOT DOTween): `Tween.Alpha()`, `Tween.Scale()`, `Tween.Position()`
- Use C# events: `OnEventName?.Invoke(args)` (NOT `EventBus.Publish("string")` or `EventBus<T>.Raise()`)
- The game's EventBus uses static methods for core events: `EventBus.DamageDealt(source, target, amount, isCrit)` — but for new generated systems, use C# event delegates (`public event Action<T> OnEventName`)
- Use `Path` enum (NOT `HeroPath`) in `VeilBreakers.Data` namespace
- Use game's DamageCalculator signature: `DamageCalculator.Calculate(Combatant attacker, Combatant defender, int basePower, DamageType damageType)`
- Cinemachine is NOT in the game project yet — generated scripts that use Cinemachine should include a note that `com.unity.cinemachine` package must be installed

### Brand Color Palette (from VeilBreakers3DCurrent/BrandSystem.cs — use EXACT values)
```python
# Primary colors (what VFX particles, auras, and effects use)
BRAND_COLORS = {
    "IRON":    (0.55, 0.59, 0.65, 1.0),  # Steel gray
    "SAVAGE":  (0.71, 0.18, 0.18, 1.0),  # Blood red
    "SURGE":   (0.24, 0.55, 0.86, 1.0),  # Electric blue
    "VENOM":   (0.31, 0.71, 0.24, 1.0),  # Toxic green
    "DREAD":   (0.47, 0.24, 0.63, 1.0),  # Deep purple
    "LEECH":   (0.55, 0.16, 0.31, 1.0),  # Dark crimson
    "GRACE":   (0.86, 0.86, 0.94, 1.0),  # Holy silver
    "MEND":    (0.78, 0.67, 0.31, 1.0),  # Healing gold
    "RUIN":    (0.86, 0.47, 0.16, 1.0),  # Flame orange
    "VOID":    (0.16, 0.08, 0.24, 1.0),  # Void dark
}

# Glow variants (for emission, bloom, energy effects)
BRAND_GLOW = {
    "IRON":    (0.71, 0.75, 0.80, 1.0),
    "SAVAGE":  (0.86, 0.27, 0.27, 1.0),
    "SURGE":   (0.39, 0.71, 1.00, 1.0),
    "VENOM":   (0.47, 0.86, 0.39, 1.0),
    "DREAD":   (0.63, 0.39, 0.78, 1.0),
    "LEECH":   (0.71, 0.24, 0.43, 1.0),
    "GRACE":   (1.00, 1.00, 1.00, 1.0),
    "MEND":    (0.94, 0.82, 0.47, 1.0),
    "RUIN":    (1.00, 0.63, 0.31, 1.0),
    "VOID":    (0.39, 0.24, 0.55, 1.0),
}

# Dark variants (for shadows, corruption, dark effects)
BRAND_DARK = {
    "IRON":    (0.31, 0.35, 0.39, 1.0),
    "SAVAGE":  (0.47, 0.10, 0.10, 1.0),
    "SURGE":   (0.12, 0.31, 0.55, 1.0),
    "VENOM":   (0.16, 0.39, 0.12, 1.0),
    "DREAD":   (0.27, 0.12, 0.39, 1.0),
    "LEECH":   (0.35, 0.08, 0.20, 1.0),
    "GRACE":   (0.63, 0.63, 0.71, 1.0),
    "MEND":    (0.55, 0.43, 0.16, 1.0),
    "RUIN":    (0.63, 0.27, 0.08, 1.0),
    "VOID":    (0.06, 0.02, 0.10, 1.0),
}
```

---

## Tasks

### P3-C1: Evolution Animation System (48h)
**The biggest task. Evolution = core VeilBreakers mechanic.**

**Generate these C# components:**

1. **`VB_EvolutionDissolve.shader`** (inline in vfx_templates.py):
   - Property: `_DissolveProgress` (0.0 = old form, 1.0 = new form)
   - Property: `_BrandColor` (Color)
   - Edge glow along dissolve boundary using brand color
   - Noise-based dissolve pattern (not linear wipe)

2. **`EvolutionController.cs`** MonoBehaviour:
   - State machine: Idle → WindUp → Dissolve → Reform → Reveal → Complete
   - `StartEvolution(Brand brand)` public method
   - Each state has configurable duration
   - AnimationEvent hooks at each transition for SFX
   - `OnEvolutionComplete` UnityEvent for game logic

3. **Per-brand particle configs** (10 brands):
   - VOID: dark purple portal particles, reality-crack line renderer
   - SURGE: lightning bolts (line renderer + particles), electrical arcs
   - IRON: orange-hot metal drip particles, cooling steam
   - SAVAGE: bone fragment particles, growth spurt scale animation
   - VENOM: green bubble particles, toxic mist volume
   - DREAD: shadow wisp particles, fear-pulse shockwave
   - LEECH: yellow-green tendrils (line renderers), energy drain trail
   - GRACE: golden light rays, feather particles, ascending sparkles
   - MEND: green pulse rings, cell-division particles
   - RUIN: geometric shard particles, fragmentation + reconstruction

4. **Evolution camera sequence** (using Cinemachine 3.x):
   - WindUp: dolly zoom to creature
   - Dissolve: slow orbit around creature
   - Reform: pull back to reveal new form
   - Use `CinemachineSequencerCamera` for shot list

### P3-C2: Capture Animation System (16h)
**Generate C# `CaptureController.cs`:**
- States: Idle → Binding → Struggle → Resolution (Success/FailFlee/FailBerserk)
- `StartCapture(Brand captureBrand, float difficulty)` public method
- Struggle phase: `_StruggleAmplitude` decreases over time (1.0 → 0.0)
- QTE integration: `OnQTEWindowOpen` / `OnQTEWindowClose` events with timing
- Success: scale-down tween + flash + particle burst
- Fail (flee): shatter VFX + creature flee animation trigger
- Fail (berserk): shatter VFX + rage buff visual + damage boost
- Brand-specific binding VFX: IRON=chain particles, VENOM=containment sphere, VOID=portal suction

### P3-C4: Corruption Idle Variants (20h)
**Generate `CorruptionAnimationController.cs`:**
- Reads `float corruptionLevel` (0.0 to 1.0)
- Tier thresholds: ASCENDED (<0.1), PURIFIED (0.1-0.25), UNSTABLE (0.25-0.5), CORRUPTED (0.5-0.75), ABYSSAL (>0.75)
- ASCENDED: gentle hover offset (Y position sine wave), radiant particle emission, serene animator speed
- PURIFIED: subtle material shimmer (emission pulse), upright posture blend
- UNSTABLE: random glitch frames (skip animator time randomly), material flicker
- CORRUPTED: dark vein shader overlay (`_VeinIntensity` property), heavier animation speed, aggressive idle blend
- ABYSSAL: extremity jitter (random rotation offsets on hands/head bones), shadow particle burst, scale pulse (0.95-1.05 sine)

### P3-C7: Per-Creature Death/Idle Variations (12h)
**Generate `BrandDeathController.cs` and `BrandIdleModifier.cs`:**

Death per brand (triggered via `OnDeath(Brand brand)`):
- IRON: rust material spread + crumble particle + rigid body fragments
- VENOM: dissolve shader (green) + melt scale (Y shrink) + puddle decal
- SURGE: electrical overload particles + flash + ragdoll with sparks
- SAVAGE: collapse + bone crack audio event + dust cloud
- VOID: implosion scale (shrink to point) + dimensional rift particle
- DREAD: shadow dispersal (alpha fade + shadow particles scatter)
- LEECH: wither (desaturate material + shrink + particle drain)
- GRACE: peaceful fade (alpha + ascending light particles)
- MEND: crystal formation + shatter
- RUIN: fragmentation (mesh pieces fly apart via rigid bodies)

Idle per brand (blended additively):
- IRON: heavy breathing (chest scale pulse), occasional metal creak audio event
- SURGE: twitchy micro-movements, spark particles
- etc. (each brand gets a 3-5 line idle behavior description)

### P4-I8: Fix Brand VFX Colors (2h)
**In BOTH `vfx_templates.py` AND `vfx_mastery_templates.py`:**

The two files have CONFLICTING brand colors — they must be unified to the Interface Contract palette.

**Current values in vfx_templates.py → Correct values (from BrandSystem.cs):**
- IRON: `[1.0,0.6,0.2]` (orange) → `[0.55,0.59,0.65,1.0]` (steel gray)
- SAVAGE: `[0.2,0.9,0.1]` (toxic green) → `[0.71,0.18,0.18,1.0]` (blood red)
- VENOM: `[0.9,0.3,0.1]` (red) → `[0.31,0.71,0.24,1.0]` (toxic green)
- LEECH: `[0.2,0.5,0.15]` (dark green) → `[0.55,0.16,0.31,1.0]` (dark crimson)
- GRACE: `[1.0,0.95,0.7]` (pale) → `[0.86,0.86,0.94,1.0]` (holy silver)
- MEND: `[0.3,0.9,0.6]` (cyan) → `[0.78,0.67,0.31,1.0]` (healing gold)
- RUIN: `[0.4,0.3,0.2]` (brown) → `[0.86,0.47,0.16,1.0]` (flame orange)
- VOID: `[0.3,0.1,0.5]` (IDENTICAL to DREAD!) → `[0.16,0.08,0.24,1.0]` (void dark)
- DREAD: `[0.3,0.1,0.5]` (same as VOID) → `[0.47,0.24,0.63,1.0]` (deep purple)

**Current values in vfx_mastery_templates.py → ALSO fix (CONFLICTING with vfx_templates!):**
- IRON: `[1.0,0.5,0.1]` → `[0.55,0.59,0.65,1.0]` (steel gray)
- DREAD: `[1.0,1.0,1.0]` (white!) → `[0.47,0.24,0.63,1.0]` (deep purple)
- LEECH: `[1.0,0.8,0.3]` (golden!) → `[0.55,0.16,0.31,1.0]` (dark crimson)
- VOID: `[0.5,0.02,0.02]` (deep red!) → `[0.16,0.08,0.24,1.0]` (void dark)

**Both files must use the EXACT values from the Interface Contract palette (BrandSystem.cs).**
**Also add BRAND_GLOW and BRAND_DARK variants from the palette for emission and shadow effects.**

### P5-Q3: Multi-Hit Combo VFX Chains (20h)
**Generate `ComboVFXController.cs`:**
- Track combo count (int, resets after timeout)
- VFX escalation: hit 1 = small particle burst, hit 2 = medium + screen shake, hit 3+ = large + chromatic aberration
- Per-brand combo finisher VFX (at combo count 5+): brand-specific particle explosion
- Read timing data from generated combat timing configs
- Support `vfx_frames` (multi-hit) with fallback to single `vfx_frame`
- Chain-cancel: if next attack starts within cancel window, VFX transitions smoothly (no gap)

### P5-Q4: Channel/Sustain VFX System (16h)
**Generate 3 controller MonoBehaviours:**
- `ChannelVFXController.cs`: looping particle effect while ability is held, intensity ramps up over time, OnRelease burst
- `AuraVFXController.cs`: persistent particle halo attached to character, brand-colored, enable/disable with fade
- `BeamVFXController.cs`: line renderer + particles between caster and target, tracks target position, width pulses

### P5-Q5: Cinematic Camera for Action Sequences (20h)
**Extend `cinematic_templates.py`:**
- Current system already has: multi-shot sequences, transitions (cut/crossfade/push/fade), character staging (idle/walk/run/talk/fight/kneel), signal tracks, audio tracks, PlayableDirector binding. This is NOT a from-scratch build.
- **What's MISSING is camera MOVEMENT during shots.** Currently cameras are placed at fixed positions per shot. Add:
  - `generate_action_cinematic_script()` with:
    - Camera dolly tracks (CinemachineSmoothPath + CinemachineTrackedDolly)
    - Camera crane shots (vertical arc via animated CinemachineCameraOffset)
    - Impact zoom (quick zoom on hit frame via FOV animation, pull back)
    - Slow-motion integration (`Time.timeScale` curves on Timeline)
    - VFX reaction (Cinemachine impulse source triggered by Timeline signals)
  - Extend existing shot types beyond the current 5 defaults (Establishing, CloseUp, Reaction, TwoShot, Closing)
  - Add: OrbitalShot, TrackingShot, WhipPan, CrashZoom, PullBack shot types
- Use `CinemachineSequencerCamera` for shot list management (already partially in place)
- Use `CinemachineImpulseSource` for impact shake (NOT CinemachineCameraOffset)

### P5-Q8: Animation Layer System (16h)
**Extend `animation_templates.py`:**
- Generate `AnimationLayerManager.cs`:
  - Manages N additive layers on an Animator
  - Preset layer configs: walk+cast, idle+look, run+guard, any+hit_reaction
  - Smooth weight blending via PrimeTween when layers activate/deactivate
  - Avatar masks per layer (upper body, lower body, full body, arms only)
  - `SetLayerActive(string layerName, float blendDuration)` API

---

## Post-Task Protocol

### After EACH task:
1. Run your relevant tests:
   ```bash
   cd Tools/mcp-toolkit && python -m pytest tests/ -k "vfx or camera or cinematic or animation_template or evolution" --tb=short -q
   ```
2. Full suite regression check:
   ```bash
   cd Tools/mcp-toolkit && python -m pytest tests/ --tb=short -q
   ```
3. If ANY failures, fix and re-scan. Repeat until CLEAN.
4. Pull and rebase:
   ```bash
   git fetch origin master && git rebase origin/master
   git add src/veilbreakers_mcp/shared/unity_templates/*.py src/veilbreakers_mcp/unity_tools/vfx.py src/veilbreakers_mcp/unity_tools/camera.py tests/test_vfx_*.py tests/test_camera_*.py tests/test_cinematic_*.py
   git commit -m "$(cat <<'EOF'
   <type>: <description>

   Co-Authored-By: Claude <noreply@anthropic.com>
   EOF
   )"
   ```

### Commit types: `feat:` (new), `fix:` (bug)

### If you find gaps in OTHER terminals' files:
Write to `docs/GAPS_FROM_T3.md` — do NOT edit their files.

---

## APPENDIX E — Additional Audit Findings (Originally Missing)

### G14: Animator Controllers Generate States but ZERO Transitions
**File:** `animation_templates.py`
**What:** Generated AnimatorControllers create states but never call `AddTransition()` between them. States are disconnected islands — no state machine flow.
**How:** After creating states, generate transitions:
- Idle → Walk (when `speed > 0.1`)
- Walk → Run (when `speed > 0.5`)
- Any → Attack (when `attackTrigger`)
- Attack → Idle (on exit time)
- Use `AnimatorStateTransition` with proper `hasExitTime`, `duration`, `offset` settings
- Add `AnimatorControllerParameter` entries for each transition condition

### FIX: VisualEffect Without VisualEffectAsset
**File:** `vfx_templates.py`
**What:** `VisualEffect` component is added to GameObjects without assigning a `VisualEffectAsset` reference — the VFX will be invisible in Unity.
**How:** When generating VFX scripts, either:
- Generate a companion VFX Graph asset creation script that produces the `.vfx` asset
- OR: use ParticleSystem instead of VisualEffect for procedurally-configured effects (ParticleSystem can be fully configured via C# without an asset file)
- For brand VFX that need VFX Graph, generate the asset creation in an editor script

### FIX: Camera Dead Zone Configuration
**File:** `camera_templates.py`
**What:** Follow cameras generated without dead zone configuration — camera tracks target with zero tolerance, causing jittery following.
**How:** Add dead zone params to camera generation:
```csharp
var composer = vcam.GetComponent<CinemachineRotationComposer>();
composer.Composition.DeadZone.Width = 0.1f;
composer.Composition.DeadZone.Height = 0.08f;
composer.Composition.SoftZone.Width = 0.8f;
composer.Composition.SoftZone.Height = 0.8f;
```

### FIX: Cinemachine Impulse Guard Incomplete
**File:** `vfx_templates.py`
**What:** Cinemachine impulse (camera shake) guard is incomplete — impulse source created but no impulse listener on the camera.
**How:** Ensure generated camera setups include `CinemachineImpulseListener` component when combat VFX are configured.

### UPGRADE: VFX-Animation Multi-Hit Bridge
**What:** Audit Section 6 notes single `vfx_frame` per attack. Your combo system (P5-Q3) handles the Unity side, but also ensure:
- AnimationEvent generation in `animation_templates.py` supports MULTIPLE events per clip (one per hit in a multi-hit combo)
- Each event carries: hit index, damage type, brand, VFX intensity level

---

## Quality Bar
- All generated C# compiles against Unity 2022.3+ with URP
- Evolution system covers all 10 brands with visually distinct effects
- Brand colors match the Interface Contract palette exactly
- Animator Controllers have TRANSITIONS between states (not disconnected)
- VisualEffect components have valid asset references (or use ParticleSystem)
- Follow cameras have dead zones for smooth tracking
- Cinemachine impulse has both source and listener
- Multi-hit animations generate multiple AnimationEvents
- No `EventBus.Publish("string")` or `EventBus<T>.Raise()` — use C# events `OnEvent?.Invoke(args)`
- No `HeroPath` — use `Path`
- No local `_sanitize` — import from `_cs_sanitize`
- No DOTween — use PrimeTween
- No Cinemachine 2.x — use 3.x API
- Dissolve shader named `VB_EvolutionDissolve` (not `VB_Dissolve`)
- All new code has tests
- All tests pass after every commit
