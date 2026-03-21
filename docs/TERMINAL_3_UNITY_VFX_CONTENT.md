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
blender_addon/                              # Terminal 1 & 2
src/veilbreakers_mcp/blender_server.py      # Terminal 4
src/veilbreakers_mcp/shared/security.py     # Shared (frozen)
src/veilbreakers_mcp/shared/unity_templates/shader_templates.py  # Terminal 4
src/veilbreakers_mcp/shared/unity_templates/world_templates.py   # Terminal 4
src/veilbreakers_mcp/shared/unity_templates/content_templates.py # Phase 1 (done)
src/veilbreakers_mcp/unity_tools/scene.py   # Phase 1 (done)
src/veilbreakers_mcp/shared/_combat_timing.py  # Terminal 2
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
- Use typed events: `EventBus<EventType>.Raise(new EventType { ... })` (NOT string-based Publish)
- Use `Path` enum (NOT `HeroPath`) in `VeilBreakers.Data` namespace
- Use 4-arg DamageCalculator: `DamageCalculator.Calculate(attacker, target, brand, ability)`

### Brand Color Palette (use these EXACT values)
```python
BRAND_COLORS = {
    "IRON":    (0.72, 0.45, 0.20, 1.0),  # Rust-bronze #B87333
    "SAVAGE":  (0.80, 0.20, 0.10, 1.0),  # Blood red
    "SURGE":   (0.20, 0.60, 1.00, 1.0),  # Electric blue
    "VENOM":   (0.30, 0.80, 0.20, 1.0),  # Toxic green
    "DREAD":   (0.13, 0.55, 0.13, 0.9),  # Fear green (dark) #228B22
    "LEECH":   (0.60, 0.80, 0.20, 1.0),  # Sickly yellow-green #9ACD32
    "GRACE":   (1.00, 0.84, 0.00, 1.0),  # Golden
    "MEND":    (0.20, 0.90, 0.50, 1.0),  # Healing green
    "RUIN":    (0.60, 0.10, 0.60, 1.0),  # Dark magenta
    "VOID":    (0.30, 0.00, 0.50, 1.0),  # Deep purple
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
**In `vfx_templates.py` and `vfx_mastery_templates.py`:**
- Find all brand color definitions and replace with the correct values from the Interface Contract above
- IRON: gray → rust-bronze (0.72, 0.45, 0.20)
- LEECH: red → sickly yellow-green (0.60, 0.80, 0.20)
- DREAD: dark purple → fear-green (0.13, 0.55, 0.13)
- Ensure VOID and DREAD have DIFFERENT colors (VOID=deep purple, DREAD=fear green)

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
- Current: only "talking heads" (static camera, dialogue). Keep this working.
- Add `generate_action_cinematic_script()`:
  - Camera dolly tracks (move along spline)
  - Camera crane shots (vertical arc)
  - Impact zoom (quick zoom on hit frame, pull back)
  - Multi-shot sequences with hard cuts and crossfades
  - VFX reaction (camera shake on explosion, slow-mo on critical hit)
- Use `CinemachineSequencerCamera` for shot list management
- Use `CinemachineCameraOffset` for impact shake

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

## Quality Bar
- All generated C# compiles against Unity 2022.3+ with URP
- Evolution system covers all 10 brands with visually distinct effects
- Brand colors match the Interface Contract palette exactly
- No `EventBus.Publish("string")` — use typed `EventBus<T>.Raise()`
- No `HeroPath` — use `Path`
- No local `_sanitize` — import from `_cs_sanitize`
- No DOTween — use PrimeTween
- No Cinemachine 2.x — use 3.x API
- Dissolve shader named `VB_EvolutionDissolve` (not `VB_Dissolve`)
- All new code has tests
- All tests pass after every commit
