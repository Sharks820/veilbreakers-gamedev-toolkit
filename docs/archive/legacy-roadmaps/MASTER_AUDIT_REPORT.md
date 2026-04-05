# VeilBreakers GameDev Toolkit — Master Audit Report

---

## Meta

| Field | Value |
|-------|-------|
| **Date** | 2026-03-22 |
| **Reviewers** | 36 AI agents (22 Claude Opus 4.6, 6 OpenAI GPT-5.4, 2 Gemini 2.5 Pro, 5 Gemini 3.1 Pro Preview, 1 Gemini Flash) |
| **Scope** | 102 Python source files, 67K+ lines, 37 MCP tools, 330+ actions |
| **Test Suite** | 5,768 test functions across 86 test files |
| **Repo Path** | `veilbreakers-gamedev-toolkit/Tools/mcp-toolkit/` |
| **Package Version** | `0.1.0` (pyproject.toml — stale, should reflect v3.0 milestone) |

---

## Executive Summary

**Overall Toolkit Score: 6.5/10**

The VeilBreakers GameDev Toolkit is an ambitious and architecturally sound system with genuine strengths — FromSoft-quality combat timing data (9/10), production-grade texture operations via numpy (9/10), and correct Cinemachine 3.x / PrimeTween API usage throughout. The MCP protocol layer is clean and the template-driven C# generation pattern is well-designed.

However, the audit uncovered critical gaps that block AAA-quality output:

- **120+ bugs** across C# generation, Blender pipeline, and security layers
- **8 confirmed security bypasses** in the AST validator and TCP bridges
- **92-136 hours of animation work** needed for the monster RPG use case
- **34 EventBus.Publish() calls** referencing a method that does not exist in the VeilBreakers project
- **Fatal kwarg mismatches** in 2 code paths that will crash at runtime
- **Zero twist bones** across all 10 rig templates — every limb will candy-wrapper

The toolkit's foundations are excellent. The path from 6.5/10 to 8.5/10 is clear, well-scoped, and achievable in 8-12 weeks.

---

## Section 1: CRITICAL FIXES (Do Immediately)

### P0 — Compilation Blockers

These bugs cause runtime crashes or generate C# code that will not compile against the VeilBreakers project.

| ID | Location | Description | Impact |
|----|----------|-------------|--------|
| **F1** | `unity_tools/scene.py:495-502` | `generate_additive_layer_script()` called with kwargs `layer_name`, `base_layer_index`, `additive_clips`, `default_weight`, `avatar_mask_path` — but function signature accepts `base_layer_name`, `additive_layers`, `base_states`. **Complete kwarg mismatch.** | Fatal TypeError at runtime |
| **C1** | `content_templates.py` (26 calls), `vb_combat_templates.py` (8 calls) | 34 `EventBus.Publish("string")` calls — VB project uses typed `EventBus<T>` methods, not a string-based Publish. | Generated C# won't compile |
| **C2** | `content_templates.py`, `vb_combat_templates.py`, `ux_templates.py`, `unity_tools/ux.py` | 16 `HeroPath` references — VB project uses `Path` enum in `VeilBreakers.Data` namespace. | Generated C# won't compile |
| **C3** | `vb_combat_templates.py:666,708` | `DamageCalculator.Calculate(attacker, target)` with 2 args — VB's `DamageCalculator` requires 4 args (attacker, target, brand, ability). | Generated C# won't compile |

### P0 — Security

| ID | Location | Description | Severity |
|----|----------|-------------|----------|
| **S1** | `security.py` (both copies) | `type()` is NOT in `BLOCKED_FUNCTIONS`. An attacker can use `type("X", (object,), {"__init__": lambda self: ...})` to construct arbitrary classes with operator overrides, achieving full sandbox escape. | Critical |
| **S2** | `security.py` (both copies) | `bpy.utils.register_class` is NOT in `BLOCKED_BPY_ATTRS`. An attacker can register a persistent Blender operator that survives beyond the sandboxed execution, creating a backdoor. | Critical |
| **S3** | `security.py:188` | No AST depth/recursion guard. A 500-character nested expression like `(((((((...))))))` causes `RecursionError` in `ast.parse()`, crashing the validator and potentially the server. | High |
| **S4** | `blender_addon/socket_server.py:52-53` | TCP server on port 9876 binds to localhost with zero authentication. Any local process can send commands. Same issue on Unity bridge (port 9877). | High |
| **S5** | `gemini_client.py:126` | Gemini API key passed as URL query parameter: `?key={self.api_key}`. Key appears in server logs, browser history, proxy caches. Must use `x-goog-api-key` header instead. | Medium |
| **S6** | `wcag_checker.py:249`, `ui_templates.py:16` | `xml.etree.ElementTree` used without `defusedxml`. Vulnerable to XML entity expansion (billion laughs) and external entity injection. | Medium |
| **S7** | `security.py:49` | `__call__` is in `_ALLOWED_DUNDERS`. Combined with allowed `__init__` and `__new__`, enables call-chaining exploits. | Low-Medium |
| **S8** | `security.py` | No compute-bound DoS protection. `map()`, `filter()`, `range()`, `zip()` are all allowed. `[x for x in range(10**9)]` will hang the Blender process. | Low-Medium |

### P0 — 30-Second FBX Fix

The animation export pipeline (`blender_addon/handlers/animation_export.py:1158-1171`) is missing two critical kwargs:

```python
# ADD these to the kwargs dict at line 1171:
"use_tspace": True,                    # Fixes broken normal maps in Unity
"use_armature_deform_only": True,      # Prevents exporting MCH/ORG/control bones
```

Without `use_tspace`, every exported FBX will have broken tangent-space normal maps in Unity. Without `use_armature_deform_only`, Rigify helper bones pollute the Unity Humanoid mapper.

---

## Section 2: SECURITY AUDIT

### Overall Security Score: 6/10

| Area | Score | Details |
|------|-------|---------|
| **AST Validator Design** | 8/10 | Multi-layered allowlist approach is architecturally sound: import allowlist, function blocklist, dunder allowlist, bpy attr blocklist, bare name blocklist. Decorator checking included. |
| **AST Validator Bypass Vectors** | 4/10 | 5 confirmed bypasses: `type()` not blocked (class factory escape), `register_class` not blocked (persistent backdoor), no recursion guard (DoS), `__call__` allowed (chain exploits), no compute limits (infinite loops). |
| **TCP Bridge Authentication** | 2/10 | Zero authentication on both ports (9876 Blender, 9877 Unity). Any local process can connect and execute arbitrary commands. Needs at minimum a shared secret handshake. |
| **SQL Injection Prevention** | 9/10 | `asset_catalog.py` uses parameterized queries throughout. Textbook correct. |
| **Path Traversal** | 7/10 | Unity side: `_write_to_unity()` in `_common.py` validates paths. Blender side: export handlers accept user-controlled `output_dir` without validation — `../../` traversal possible. |
| **API Key Handling** | 6/10 | Environment variables used correctly for Tripo, fal.ai, ElevenLabs. **Gemini key leaked in URL query string** (`gemini_client.py:126`). Should use HTTP header `x-goog-api-key`. |
| **XML Parsing** | 3/10 | `xml.etree.ElementTree` used in `ui_templates.py` and `wcag_checker.py` without `defusedxml`. Vulnerable to billion-laughs and XXE attacks on crafted UXML input. |
| **Code Length Limits** | 8/10 | `MAX_CODE_LENGTH = 50_000` is enforced before AST parsing. Reasonable limit. |
| **Import Control** | 9/10 | Dual-layer: explicit blocklist + allowlist-only for roots. Relative imports blocked. Star imports blocked. |

### Recommended Security Fixes (Priority Order)

1. Add `"type"` to `BLOCKED_FUNCTIONS` in both `security.py` copies
2. Add `"register_class"`, `"unregister_class"` to `BLOCKED_BPY_ATTRS`
3. Add recursion depth guard: `sys.setrecursionlimit()` or try/except `RecursionError` around `ast.parse()`
4. Add shared-secret authentication to TCP bridges (HMAC handshake)
5. Move Gemini API key from URL query to `x-goog-api-key` header
6. Add `defusedxml` dependency and replace `xml.etree.ElementTree` imports
7. Consider removing `__call__` from `_ALLOWED_DUNDERS` or adding call-depth tracking
8. Add compute timeout (Blender's `bpy.app.timers` can enforce wall-clock limits)

---

## Section 3: C# CODE GENERATION

### Template Scores

| Template File | Score | Strengths | Issues |
|--------------|-------|-----------|--------|
| **code_templates.py** | 8/10 | Best sanitization of all templates. Clean class builder pattern with namespace injection, using directives, proper indentation. | Has local `_sanitize` copy (should import from `_cs_sanitize`). |
| **game_templates.py** | 7/10 | Save system is excellent (JSON + AES + migration versioning). Character controller has correct ground check. | Double `controller.Move()` call in character controller template. `_sanitize` local copy. |
| **vb_combat_templates.py** | 6/10 | Real-time combat path is correct and well-structured with proper state machine. | Turn-based mode is a no-op (generates skeleton with `DamageCalculator.Calculate(a, b)` — wrong arity). 8 `EventBus.Publish` calls. 8 `HeroPath` references. |
| **gameplay_templates.py** | 7/10 | Mob FSM is solid (Patrol/Chase/Attack/Flee with proper transitions). Boss AI has multi-phase hierarchical FSM. | Behavior tree leaf nodes are stubs (execute returns `Running` always). Local `_sanitize` copy. |
| **content_templates.py** | 5/10 | Inventory system is complete with grid+equipment+UI. Loot table weighting is correct. | **26 `EventBus.Publish` calls** (most of any file). Quest gating ignored (quests always available). Crafting system consumes materials before checking success. 2 `HeroPath` references. |
| **vfx_templates.py** | 5/10 | Brand VFX identity per brand. Correct URP shader graph references. | `VisualEffect` component added without `VisualEffectAsset` reference (will be invisible in Unity). Cinemachine impulse guard is incomplete. Local `_sanitize` copy. |
| **world_templates.py** | 5/10 | Weather system has correct Beaufort scale mapping. Day-night cycle math is sound. | `[SerializeField]` fields declared but never wired to inspector values in generated scripts. Physics bridge joints have good API but no visual debugging. |
| **qa_templates.py** | 8/10 | Unity bridge server implementation is excellent — proper async TCP with message framing. | Static analyzer rules are too shallow (only checks naming conventions, not logic patterns). |
| **scene_templates.py** | 8/10 | Cinemachine 3.x API usage is correct throughout. NavMesh baking uses correct agent settings. | NavMeshBuildSource has struct-copy bug (modifying copy, not original). Additive layer call site has fatal kwarg mismatch (F1 above). |
| **camera_templates.py** | 9/10 | All Cinemachine 3.x types correct: `CinemachineCamera`, `CinemachineFollow`, `CinemachineRotationComposer`. Priority system correct. | Minor: no dead zone configuration in follow cameras. |
| **build_templates.py** | 8/10 | Correct GameCI workflow YAML. LFS configuration complete. Multi-platform (6 targets) with IL2CPP backend. | No code signing configuration for macOS/iOS builds. |
| **shader_templates.py** | 9/10 | Correct URP HLSL structure. Dissolve, force field, water, foliage, outline, damage flash all generate valid shader code. | Missing `#pragma multi_compile_shadowcaster` and `#pragma multi_compile_fog` in some shaders. |
| **ux_templates.py** | 8/10 | PrimeTween API calls verified correct. Damage numbers use ObjectPool pattern. | 5 `HeroPath` references (should be `Path`). |
| **ui_templates.py** | 8/10 | UXML generation is standards-compliant. USS dark fantasy theme is cohesive. | Uses `xml.etree.ElementTree` without defusedxml. Theme colors drift from production `ThemeManager.cs`. |
| **cinematic_templates.py** | 3/10 | PlayableDirector bindings are correct. | Only generates "talking heads" sequences — no camera movement, no action sequences, no combat cinematics. Imported from `_cs_sanitize` (good). |
| **animation_templates.py** | 7/10 | Animator state machine generation is correct. Blend tree configuration works. | Additive layer function has the F1 kwarg mismatch bug. Imported from `_cs_sanitize` (good). |
| **equipment_templates.py** | 7/10 | Complete bone rebinding with O(1) lookup via dictionary. Socket system is well-designed. | Local `_sanitize` copy. |

### _cs_sanitize Migration Status

The toolkit has a centralized sanitization module at `_cs_sanitize.py`. Migration status:

- **7 files migrated** (import from `_cs_sanitize`): `production_templates.py`, `vfx_mastery_templates.py`, `ui_polish_templates.py`, `cinematic_templates.py`, `character_templates.py`, `audio_middleware_templates.py`, `animation_templates.py`
- **23 files still have local `def _sanitize()` copies**: Every other template file listed above.

**Action:** Complete the migration. Each local copy is a divergence risk.

---

## Section 4: 3D PIPELINE & BLENDER

### Pipeline Scores (AAA Standard)

| Component | Score | Strengths | Gaps |
|-----------|-------|-----------|------|
| **Terrain Generation** | 5/10 | Correct fBm (fractal Brownian motion) with octave stacking. Perlin/Simplex noise via opensimplex. | Capped at 1024x1024 resolution (AAA needs 4096+). Unvectorized Python loops — should use numpy for heightmap generation. No thermal/hydraulic erosion integration into generation pass. |
| **Erosion Simulation** | 6/10 | Good particle-based hydraulic erosion model. Sediment transport and deposition correct. | No flow accumulation maps. No sediment thickness maps for painting. 500 max iterations is too low for realistic results (needs 5000+). No thermal erosion (talus angle). |
| **Scatter / Vegetation** | 7/10 | Correct Bridson's Poisson disk sampling. Density maps supported. Instance-based scattering. | No moisture map support (vegetation type should vary with moisture). No terrain-normal tilt filtering (trees shouldn't grow on cliffs). No biome-edge blending. |
| **Dungeon Generation** | 7/10 | Solid BSP (binary space partition) with BFS connectivity guarantee. Room sizing and corridor generation work. | No T-junction cleanup (corridors can create ugly wall intersections). No room-type specialization (boss room, treasure room, etc.). No height variation. |
| **Town Generation** | 5/10 | Voronoi-based district partitioning. Building placement within districts. | Manhattan distance metric produces diamond-shaped districts (should use Euclidean). No geography awareness (rivers, hills). No road network generation. |
| **Building Grammar** | 6/10 | Rich style vocabulary (medieval, gothic, industrial, etc.). Foundation/wall/roof decomposition. | All geometry is solid boxes — no window openings, no door cutouts, no architectural detail meshes. No LOD-aware geometry reduction. |
| **Mesh Quality Analysis** | 7/10 | Strong A-F grading system. Checks: triangle count, UV overlap, degenerate faces, manifold edges. | LOD generation uses uniform decimation — no silhouette preservation. No per-material boundary preservation. |
| **FBX Export** | 7/10 | Correct Unity-compatible axes (`axis_forward="-Z"`, `axis_up="Y"`). `add_leaf_bones=False`. | Missing `use_tspace=True` (broken normal maps). Missing `use_armature_deform_only=True` (helper bone pollution). |
| **Texture Operations** | 9/10 | Production-quality numpy pipeline. Normal map generation, AO baking, channel packing, PBR workflow. Correct sRGB/linear handling. | No tiling/seamless texture support. Could benefit from GPU acceleration for large textures. |
| **Equipment System** | 7/10 | Complete bone rebinding pipeline with O(1) dictionary lookup. Modular character splitting (head, torso, arms, legs). | No LOD-aware equipment — equipment doesn't simplify with character LOD. No equipment socket preview in Blender. |

### Blender Server Architecture

The `blender_server.py` monolith (1,988 lines) serves as the MCP entry point for all Blender tools. It delegates to handler modules in `blender_addon/handlers/` (35 handler files). Architecture is clean — each handler is focused on a single domain (animation, rigging, environment, etc.).

---

## Section 5: ANIMATION PIPELINE (Monster RPG Focus)

This is the **most critical section** for VeilBreakers. The game's core loop involves capturing, evolving, and battling monsters — every one of those verbs requires animation support that is currently missing or skeletal.

### Rigging

| Component | Score | Status |
|-----------|-------|--------|
| **Twist Bones** | 0/10 | Zero twist bones across all 10 rig templates (humanoid, quadruped, bird, insect, arachnid, serpent, aquatic, hexapod, tentacle, amorphous). Every limb will exhibit candy-wrapper deformation on rotation. This is the single highest-impact animation bug. |
| **Corrective Blend Shapes** | 0/10 | Zero driver-based corrective shapes. Shoulder, elbow, and knee deformation will collapse at extreme angles. |
| **Spring / Jiggle Bones** | 2/10 | `rig_setup_spring_bones` handler exists and is registered in the command dispatch. However, the implementation uses `DAMPED_TRACK` constraint with no target set — constraint is non-functional. No actual spring dynamics solver (mass-spring-damper). |
| **Weight Painting** | 5/10 | Heat diffusion automatic weights are correct. But no enforcement of 4-influence-per-vertex limit (Unity's skinning limit). Excess influences cause visual artifacts on mobile and older hardware. |
| **Facial Rigging** | 3/10 | 19 bones with 3 canned expressions (happy, angry, surprised). No FACS (Facial Action Coding System) blendshapes. No viseme support for lip sync. No eye tracking rig. |
| **Rig Validation** | 4/10 | A-F grading system with bone count, hierarchy depth, and naming convention checks. Missing: influence limit check, zero-weight bone detection, symmetry validation, bone roll verification. |
| **Humanoid Template** | 5/10 | Core spine-hip-limb hierarchy is correct. Missing: shoulder bones, finger bones (5 per hand), toe bones, bone rolls for Unity Humanoid auto-mapping. |

### Procedural Animation

| Gait / Type | Score | Status |
|------------|-------|--------|
| **Biped Walk** | 4/10 | Single-harmonic sine wave for all joints. No heel-strike phase. No hip sway. No arm counter-swing. No weight shift. Looks like a marching robot. |
| **Biped Run** | 3/10 | Same sine wave as walk with higher amplitude. No flight phase (both feet off ground). No forward lean. No arm pump. |
| **Quadruped Walk** | 5/10 | Diagonal leg pairing is correct — but this is a **trot**, not a walk. True walk has 3-beat timing with each leg independent. |
| **Quadruped Run** | 4/10 | Uses synchronized front/back pairing — this is a **bound**, not a gallop. Gallop has asymmetric timing with a distinct lead leg. |
| **Hexapod** | 7/10 | Correct alternating tripod gait (legs 1-4-5 then 2-3-6). Proper phase offset. Best procedural gait in the toolkit. |
| **Arachnid** | 6/10 | Correct 4-4 leg grouping with alternating phase. However, legs rotate on the wrong axis (rotating around bone Y instead of local Z for lateral spread). |
| **Serpent** | 8/10 | Biomechanically accurate traveling sine wave. Phase propagation along spine is correct. Amplitude modulation for speed changes. Second-best procedural animation. |
| **Attack (All Types)** | 6/10 | Good 3-phase structure (anticipation, strike, recovery). 8 attack types (slash, stab, smash, bite, claw, tail, slam, projectile). | Linear interpolation between keyframes (should use easing curves). No root motion generation. No hit-stop/freeze-frame support. |
| **Combat Timing Data** | 9/10 | **CROWN JEWEL.** Frame-accurate timing data for anticipation, active, recovery, cancel windows. Comparable to FromSoft (Dark Souls / Elden Ring) quality. This data structure is exceptional and should drive all combat animation. |

### Monster-Specific Gaps (VeilBreakers Requirements)

| Feature | Score | Status | Hours to Fix |
|---------|-------|--------|-------------|
| **Floating Creatures** | 3/10 | No hover system. No bob oscillation. No banking on turns. Flying monsters will T-pose in place. | 8-12h |
| **Multi-Armed Horrors** | 2/10 | Only 2-arm bone chains supported. VB has 4-armed and 6-armed monsters. No independent arm IK. | 12-16h |
| **Amorphous / Blob** | 1/10 | No morph target animation. No scale-based deformation. No pseudopod extension. Blob creatures are completely unsupported. | 16-24h |
| **Spell / Magic Gestures** | 2/10 | Zero magic-casting animations. No gesture vocabulary. No channeling poses. Critical for VOID, SURGE, MEND brands. | 12-16h |
| **Capture Animation** | 0/10 | **Completely missing.** Capture is a core VeilBreakers mechanic. Need: bind/trap trigger, struggle (decreasing amplitude), capture success, capture fail (flee/berserk), QTE sync, brand-specific capture VFX integration. | 12-16h |
| **Evolution Animation** | 0/10 | **Completely missing.** Evolution is a core VeilBreakers mechanic. Need: per-brand evolution VFX (VOID=reality tear, SURGE=lightning cocoon, IRON=metal forge, etc.), dissolve shader with `_DissolveProgress`, evolution controller MonoBehaviour, camera sequence. | 40-60h |
| **Animation Layering** | 0/10 | Flat keyframes only. Cannot walk and cast simultaneously. Cannot idle and look around. No additive layer generation despite the additive_layer template existing (blocked by F1 kwarg bug). | 8-12h |
| **Combat Command Flow** | 3/10 | Attack animation works. Everything around it is missing: combat idle, approach with anticipation, return to formation, guard/defend, flee/retreat, target switch, synergy activation, ultimate wind-up. | 24-36h |
| **Corruption Idle Variants** | 2/10 | Shader-side corruption effects exist (`vfx_templates.py`). Animation-side is absent — no twitching at CORRUPTED tier, no levitation at ASCENDED tier, no dark-vein pulsing at ABYSSAL tier. | 16-24h |

### Anti-Glitch Technique Scores

These are the techniques that prevent visual artifacts in production animation:

| Technique | Score | Notes |
|-----------|-------|-------|
| Twist bones | 0/10 | Zero across all templates |
| Corrective blend shapes | 0/10 | Zero driver-based correctives |
| Bone rolls | 0/10 | No roll values set — defaults cause axis flipping |
| Weight influence limits | N/A | Not enforced (should be max 4) |
| Curve tangent types | 2/10 | All keyframes use linear tangents (should use auto-clamped or Bezier) |
| Transition blending | 1/10 | No crossfade duration between states |
| Root motion export | 7/10 | Root motion extraction exists but not integrated with FBX batch export |
| IK foot placement | 3/10 | IK chain setup exists, no ground-contact solver |
| Bone hierarchy validation | 2/10 | Basic naming check only |
| FBX tangent export | 0/10 | `use_tspace=False` (default) — breaks all normal maps |

---

## Section 6: VFX-ANIMATION SYNC

| Component | Score | Status |
|-----------|-------|--------|
| **Frame-Accurate Timing** | 9/10 | Combat timing data includes frame-level hit windows, cancel windows, and active frames. Exceptional quality. |
| **Brand VFX Identity** | 8/10 | Each of the 10 brands has distinct VFX color palettes and particle behaviors. IRON=metallic sparks, VENOM=green drip, SURGE=blue lightning, etc. |
| **AnimationEvent Generation** | 7/10 | AnimationEvent insertion at hit frames is implemented in animation_templates.py. Events carry damage type and brand info. |
| **Animation-to-VFX Bridge** | 4/10 | Single `vfx_frame` per attack animation. No multi-hit support. No VFX sustain duration. A 3-hit combo plays VFX on first hit only. |
| **Combo / Chain Awareness** | 2/10 | No combo system. Attacks are isolated events. No chain-cancel windows. No VFX escalation across combo hits. |
| **Channel / Sustain VFX** | 2/10 | No channeling VFX (e.g., holding a MEND heal). No sustained aura VFX during buffs. VFX are fire-and-forget only. |
| **Per-Brand Timing Profiles** | 3/10 | Combat timing is universal. IRON attacks should be slow+heavy, SURGE should be fast+snappy, GRACE should flow. Brand identity is in VFX only, not in timing. |

---

## Section 7: UI/UX

| Component | Score | Status |
|-----------|-------|--------|
| **UXML Generation** | 8/10 | Standards-compliant UI Toolkit UXML. Proper VisualElement hierarchy. Template supports all common UI patterns (screens, panels, lists, buttons). |
| **USS Dark Fantasy Theme** | 7/10 | Cohesive dark theme with appropriate typography and spacing. Color palette is atmospheric. | Drifts from the production `ThemeManager.cs` in the VB Unity project — generated USS uses hardcoded hex values instead of CSS custom properties. |
| **WCAG Contrast Checking** | 8/10 | Correct W3C relative luminance formula. Correct 4.5:1 / 3:1 thresholds for AA/AAA. | Silently skips elements with missing background colors instead of flagging them. |
| **PrimeTween Integration** | 9/10 | All PrimeTween API calls verified correct against PrimeTween 1.3.x source. Tween.UIScale, Tween.Alpha, Tween.Position all correct. Easing types correct. |
| **Brand VFX Colors** | 6/10 | Most brands have correct hex values. **IRON is wrong** (uses gray instead of rust-bronze). **LEECH is wrong** (uses red instead of sickly yellow-green). **VOID and DREAD are identical** (both use dark purple — DREAD should be fear-green). |
| **Shader Generation** | 9/10 | Correct URP HLSL structure. `#include "Packages/com.unity.render-pipelines.universal/..."` paths correct. All 6 shader types generate valid code. | Missing `#pragma multi_compile_shadowcaster` and `#pragma multi_compile_fog` in dissolve and force-field shaders. |
| **Cinematic System** | 3/10 | PlayableDirector bindings are correct. Timeline track setup works. | Only generates "talking heads" sequences — static camera, dialogue-only. No camera movement, no action sequences, no combat cinematics, no VFX integration. |

---

## Section 8: TOKEN EFFICIENCY

The toolkit's MCP schema consumes a significant portion of the LLM context window.

### Current State

| Metric | Value |
|--------|-------|
| **Total schema tokens** | ~75,800 |
| **As % of 200K context** | 37.9% |
| **Top consumer** | `unity_world` — 4,611 tokens |
| **Average params per tool** | 51 |
| **Typical params used per call** | 3-5 |
| **Parameter waste ratio** | ~90% (unused optional params still in schema) |

### Top 10 Token Consumers

| Tool | Tokens | % of Total |
|------|--------|-----------|
| `unity_world` | 4,611 | 6.1% |
| `unity_game` | 4,208 | 5.5% |
| `unity_content` | 3,891 | 5.1% |
| `unity_gameplay` | 3,754 | 5.0% |
| `unity_vfx` | 3,622 | 4.8% |
| `unity_scene` | 3,410 | 4.5% |
| `unity_prefab` | 3,198 | 4.2% |
| `unity_ux` | 2,987 | 3.9% |
| `unity_ui` | 2,876 | 3.8% |
| `unity_camera` | 2,654 | 3.5% |

### Reduction Strategies

| Strategy | Savings | Effort |
|----------|---------|--------|
| **Remove docstring duplication** (same text in description + param help) | ~10,500 tokens (14%) | Low — automated refactor |
| **Compact optional params** (merge related params into JSON objects) | ~7,348 tokens (10%) | Medium — schema change |
| **Compress default descriptions** (shorten verbose help text) | ~3,000 tokens (4%) | Low — text editing |
| **Total easy wins** | **~20,848 tokens (28%)** | 1-2 days |
| **Deferred tool splitting** (load tool schemas on-demand) | ~69,700 tokens (92%) | High — requires MCP client support |

---

## Section 9: PRODUCTION READINESS

### Test Infrastructure

| Metric | Value | Assessment |
|--------|-------|-----------|
| Test functions | 5,768 | Strong count |
| Test files | 86 | Good coverage breadth |
| Testing framework | pytest + pytest-asyncio | Correct choice |
| Coverage tooling | **None** | No pytest-cov, no coverage reports, no CI gate |
| Integration tests | Present (functional_blender, functional_unity) | Good — tests actual tool invocations |
| Mocking | Extensive bpy mocking | Correct — tests run without Blender |

### Documentation

| Aspect | Status |
|--------|--------|
| Docstrings | Excellent — every public function has Args/Returns/Raises |
| Type hints | Complete — all function signatures have type annotations |
| Generated API docs | **None** — no Sphinx/mkdocs setup |
| README | Stale — references v1.0 architecture |
| CLAUDE.md | Current — comprehensive tool reference |

### Versioning

`pyproject.toml` still reads `version = "0.1.0"` despite the project being at a v3.0 milestone. This should be updated to reflect actual maturity.

### Observability

| Metric | Value |
|--------|-------|
| Files with `logger` | 25 out of 81 source files |
| Files with zero logging | 56 files |
| Log levels used | `info`, `warning`, `error` |
| Structured logging | No — all plain string formatting |
| Error reporting | Exceptions propagated to MCP layer as JSON error responses |

### Code Duplication

- **23 template files** still have local `def _sanitize()` copies instead of importing from `_cs_sanitize.py`
- **2 security.py copies** (server + addon) must be kept in sync manually — no shared symlink or build step
- **Legacy directories**: `asset-pipeline/`, `blender-gamedev/`, `unity-enhanced/` at repo root are dead stubs from earlier architecture — should be removed or archived

### Architecture Health

| Aspect | Status | Notes |
|--------|--------|-------|
| Unity server monolith | **Refactored** | `unity_server.py` is now 23 lines — delegates to `unity_tools/` subpackage (8,972 lines across 22 modules). Clean split. |
| Blender server | Monolith (1,988 lines) | Still large but manageable. Handler delegation to `blender_addon/handlers/` is clean. |
| Shared module | Well-organized | `shared/` has focused modules: security, config, texture_ops, clients. |
| Dependency management | Modern | `uv` lockfile, `hatchling` build backend, Python 3.12+. |

---

## Section 10: VEILBREAKERS-SPECIFIC REQUIREMENTS

These are features that the VeilBreakers project specifically needs and that are currently absent or insufficient in the toolkit.

### 10.1 Evolution Animation System (40-60 hours)

Evolution is a core VeilBreakers mechanic — monsters evolve when fed specific Brand essences. The toolkit generates zero evolution content.

**Required deliverables:**

1. **10 brand-specific evolution VFX designs:**
   - VOID: Reality tear / dimensional rift surrounding creature
   - SURGE: Lightning cocoon with electrical discharge
   - IRON: Metal forge effect — molten metal flows over body, hardens
   - SAVAGE: Bone/claw/horn growth with cracking SFX
   - VENOM: Toxic chrysalis with bubbling dissolution
   - DREAD: Shadow swarm convergence with fear aura
   - LEECH: Parasitic tendrils pulling energy from environment
   - GRACE: Radiant ascension — light beams, feather particles
   - MEND: Cellular regeneration — green healing pulses
   - RUIN: Entropy cascade — geometric fragmentation and reconstruction

2. **Dissolve shader with `_DissolveProgress` property** (0.0 = old form, 1.0 = new form)
3. **EvolutionController MonoBehaviour** — state machine: Idle -> WindUp -> Dissolve -> Reform -> Reveal
4. **Camera sequence** — zoom to creature, orbit during transformation, pull back for reveal
5. **Sound design hooks** — AnimationEvents at each phase transition

### 10.2 Real-Time Combat Command Flow (24-36 hours)

The combat system generates attack animations but nothing around them. A complete command flow requires:

| Animation | Priority | Notes |
|-----------|----------|-------|
| Command receive | P0 | Subtle acknowledgment pose (nod, ready stance) |
| Combat idle | P0 | Brand-appropriate idle (IRON = heavy stance, GRACE = flowing) |
| Approach with anticipation | P0 | Walk/run to melee range with wind-up beginning |
| Attack execute | Done | Already implemented (8 types) |
| Return to formation | P0 | Post-attack return to party position |
| Guard / defend | P0 | Raise guard pose, damage reduction visual |
| Flee / retreat | P1 | Turn and run, stumble variant for low HP |
| Target switch | P1 | Head turn + body pivot to new target |
| Synergy activation | P1 | Team-wide synergy flash + pose |
| Ultimate wind-up | P2 | Extended anticipation for ultimate abilities |
| Victory pose | P2 | Brand-specific celebration |
| Defeat collapse | P2 | Brand-specific death (IRON = rust crumble, VENOM = dissolve) |

### 10.3 Capture Animation System (12-16 hours)

| Phase | Description |
|-------|-------------|
| **Bind / trap trigger** | Capture device activates — brand-specific binding VFX |
| **Struggle** | Target resists with decreasing amplitude oscillation |
| **QTE sync** | Player input syncs to struggle peaks — timing window animation |
| **Capture success** | Creature compressed into capture device with flash |
| **Capture fail (flee)** | Device shatters, creature runs |
| **Capture fail (berserk)** | Device shatters, creature rages (+damage buff) |
| **Brand-specific capture VFX** | IRON = chains, VENOM = containment field, VOID = dimensional pocket |

### 10.4 Corruption-Tier Animation Variants (16-24 hours)

Each corruption tier should visually affect creature behavior:

| Tier | Range | Animation Effect |
|------|-------|-----------------|
| **ASCENDED** | 0-10% | Subtle float/hover, radiant glow, serene idle |
| **PURIFIED** | 11-25% | Light shimmer on skin, confident posture |
| **UNSTABLE** | 26-50% | Occasional glitch frames (1-2 frame pops), flickering |
| **CORRUPTED** | 51-75% | Aggressive stance shift, dark vein pulsing across mesh, heavier footfalls |
| **ABYSSAL** | 76-100% | Erratic secondary motion (jitter on extremities), shadow particles, unstable scale pulsing |

---

## Section 11: IMPLEMENTATION ROADMAP

### Phase 1: Critical Fixes (1-2 days)

**Goal:** Zero crashes, zero security bypasses, zero compile failures.

| Task | Hours | Owner |
|------|-------|-------|
| Add `"type"` to BLOCKED_FUNCTIONS (both security.py copies) | 0.5h | Security |
| Add `"register_class"`, `"unregister_class"` to BLOCKED_BPY_ATTRS | 0.5h | Security |
| Add try/except RecursionError guard around ast.parse() | 0.5h | Security |
| Fix F1: generate_additive_layer_script kwarg mismatch in scene.py | 1h | Unity Tools |
| Fix C1: Replace 34 EventBus.Publish() with typed VB EventBus methods | 4h | Templates |
| Fix C2: Replace 16 HeroPath references with Path (VeilBreakers.Data) | 1h | Templates |
| Fix C3: DamageCalculator.Calculate() — add brand and ability args | 1h | Templates |
| Add use_tspace=True and use_armature_deform_only=True to FBX export | 0.5h | Blender |
| Move Gemini API key from URL query to x-goog-api-key header | 0.5h | Shared |
| **Phase 1 Total** | **~10h** | |

### Phase 2: Animation Foundation (2-3 weeks)

**Goal:** All rig templates produce deformation-correct output. Procedural animations use proper biomechanics.

| Task | Hours | Owner |
|------|-------|-------|
| Add twist bones to all 10 rig templates (2 per limb segment) | 16h | Rigging |
| Replace single-sine gait engine with multi-harmonic + easing curves | 12h | Animation |
| Fix spring bone system (implement real mass-spring-damper solver) | 8h | Rigging |
| Add spell-cast animation type (channel, release, sustain variants) | 12h | Animation |
| Fix bone rolls for all templates (correct values for Unity Humanoid) | 4h | Rigging |
| Add 4-influence-per-vertex weight limit enforcement | 4h | Rigging |
| Expand facial rig (FACS blendshapes, visemes, eye tracking) | 16h | Rigging |
| Add curve tangent types (auto-clamped Bezier instead of linear) | 4h | Animation |
| Fix biped walk (heel-strike, hip sway, arm counter-swing) | 8h | Animation |
| Fix quadruped gaits (true walk, true gallop with lead leg) | 8h | Animation |
| **Phase 2 Total** | **~92h** | |

### Phase 3: VeilBreakers Content (3-4 weeks)

**Goal:** All core VeilBreakers mechanics have animation support.

| Task | Hours | Owner |
|------|-------|-------|
| Evolution animation system (10 brand variants + controller + camera) | 48h | Animation + VFX |
| Capture animation system (bind, struggle, success, fail, QTE sync) | 16h | Animation |
| Combat command flow (idle, approach, return, guard, flee, etc.) | 32h | Animation |
| Corruption idle variants (5 tiers with visual behavior changes) | 20h | Animation |
| Floating creature hover system (bob, bank, altitude control) | 10h | Animation |
| Multi-armed creature support (4-arm and 6-arm bone chains + IK) | 14h | Rigging |
| Per-creature death/idle variations (brand-specific) | 12h | Animation |
| **Phase 3 Total** | **~152h** | |

### Phase 4: Polish & Infrastructure (2-3 weeks)

**Goal:** Code quality, observability, and developer experience.

| Task | Hours | Owner |
|------|-------|-------|
| Complete _cs_sanitize migration (23 remaining template files) | 8h | Templates |
| Token efficiency: remove docstring duplication (-10,500 tokens) | 4h | Schema |
| Token efficiency: compact optional parameters (-7,348 tokens) | 8h | Schema |
| TCP bridge authentication (HMAC shared-secret handshake) | 12h | Security |
| Add defusedxml dependency, replace xml.etree imports | 2h | Security |
| Add structured logging to 56 files with zero logging | 16h | Observability |
| Add pytest-cov and coverage gates (minimum 80%) | 4h | Testing |
| Fix brand VFX colors (IRON, LEECH, VOID vs DREAD) | 2h | VFX |
| Update pyproject.toml version to 3.0.0 | 0.5h | Meta |
| Remove legacy directories (asset-pipeline/, blender-gamedev/, unity-enhanced/) | 1h | Cleanup |
| Add API documentation generation (mkdocs or Sphinx) | 8h | Docs |
| **Phase 4 Total** | **~66h** | |

### Phase 5: AAA Quality (4-6 weeks)

**Goal:** Toolkit output is indistinguishable from hand-authored AAA content.

| Task | Hours | Owner |
|------|-------|-------|
| Corrective blend shapes (shoulder, elbow, knee, hip) | 24h | Rigging |
| IK foot placement with ground-contact solver | 16h | Animation |
| Multi-hit combo VFX chains (escalating VFX across combo) | 20h | VFX |
| Channel/sustain VFX system (hold-to-charge, beam, aura) | 16h | VFX |
| Cinematic camera for action sequences (not just talking heads) | 20h | Camera |
| Per-brand animation timing profiles (IRON=slow, SURGE=fast) | 12h | Animation |
| Amorphous creature animation (morph targets, scale deformation) | 20h | Animation |
| Animation layer system (walk+cast, idle+look, run+guard) | 16h | Animation |
| Terrain generation at 4096+ resolution with numpy vectorization | 12h | Environment |
| Town generation with Euclidean Voronoi and road networks | 16h | Worldbuilding |
| Building grammar with window/door openings | 12h | Worldbuilding |
| Shadow/fog pragmas for all shader templates | 4h | Shaders |
| **Phase 5 Total** | **~188h** | |

### Summary Timeline

| Phase | Duration | Cumulative Score Impact |
|-------|----------|----------------------|
| Phase 1: Critical Fixes | 1-2 days | 6.5 -> 7.0 |
| Phase 2: Animation Foundation | 2-3 weeks | 7.0 -> 7.5 |
| Phase 3: VeilBreakers Content | 3-4 weeks | 7.5 -> 8.0 |
| Phase 4: Polish & Infrastructure | 2-3 weeks | 8.0 -> 8.5 |
| Phase 5: AAA Quality | 4-6 weeks | 8.5 -> 9.0+ |

---

## Section 12: WHAT WORKS WELL (Don't Break)

These components are the toolkit's crown jewels. Protect them during refactoring.

| Component | Score | Why It's Great |
|-----------|-------|----------------|
| **Combat Timing Data** | 9/10 | Frame-accurate anticipation/active/recovery/cancel windows. FromSoft-quality. Used by: `_combat_timing.py`, `animation_templates.py`. |
| **Texture Operations** | 9/10 | Production-quality numpy pipeline. Normal maps, AO, channel packing, PBR. Correct sRGB/linear. Used by: `texture_ops.py`, `texture_validation.py`. |
| **Cinemachine 3.x Templates** | 9/10 | All CM 3.x types correct: `CinemachineCamera`, `CinemachineFollow`, `CinemachineRotationComposer`, `CinemachineGroupFraming`. No legacy CM2 references. Used by: `camera_templates.py`. |
| **PrimeTween Integration** | 9/10 | All API calls verified against PrimeTween 1.3.x source. Tween types, easing, callbacks all correct. Used by: `ux_templates.py`, `ui_polish_templates.py`. |
| **SQL Injection Prevention** | 9/10 | Parameterized queries throughout `asset_catalog.py`. No string concatenation in SQL. Textbook correct. |
| **URP Shader Generation** | 9/10 | Correct HLSL structure, correct include paths, correct vertex/fragment program structure. All 6 shader types produce valid URP shaders. |
| **Security Validator Design** | 8/10 | Multi-layered allowlist architecture. Import control, function blocklist, dunder allowlist, bpy attr blocklist, decorator checking. Design is sound — just needs the bypass vectors patched. |
| **MCP Protocol Layer** | 8/10 | Clean FastMCP integration. Consistent error handling pattern across all 37 tools. JSON response format is standardized. |
| **C# Sanitization** | 8/10 | `_cs_sanitize.py` provides: identifier validation, namespace injection, using directive management, indentation normalization. Multiple defense layers. |
| **Graceful API Degradation** | 8/10 | All external API clients (Tripo3D, fal.ai, ElevenLabs, Gemini) return structured stub responses when API keys are missing. No crashes, no hanging. |
| **Creature Template Breadth** | 8/10 | 10 rig templates covering humanoid, quadruped, bird, insect, arachnid, serpent, aquatic, hexapod, tentacle, amorphous. Excellent coverage for a monster RPG. |
| **Hexapod Gait** | 7/10 | Correct alternating tripod — the gold standard for 6-legged locomotion. |
| **Serpent Animation** | 8/10 | Biomechanically accurate traveling wave with proper phase propagation. |
| **NavMesh / Scene Setup** | 8/10 | Correct NavMeshSurface API, correct agent settings, proper baking workflow. |
| **Build Pipeline** | 8/10 | GameCI integration, LFS config, 6-platform support, IL2CPP backend. Production-ready CI/CD. |

---

## Appendix A: All 36 Agents

| # | Agent ID | Model | Focus Area | Score Given | Key Finding |
|---|----------|-------|------------|-------------|-------------|
| 1 | Opus-SEC-01 | Claude Opus 4.6 | Security validator deep-dive | 8/10 design, 4/10 bypass resistance | `type()` not in BLOCKED_FUNCTIONS — full sandbox escape |
| 2 | Opus-SEC-02 | Claude Opus 4.6 | TCP bridge security | 2/10 | Zero authentication on both ports |
| 3 | Opus-SEC-03 | Claude Opus 4.6 | API key handling | 6/10 | Gemini key in URL query string |
| 4 | Opus-CS-01 | Claude Opus 4.6 | code_templates.py | 8/10 | Best sanitization, local _sanitize copy |
| 5 | Opus-CS-02 | Claude Opus 4.6 | game_templates.py | 7/10 | Double controller.Move() in character controller |
| 6 | Opus-CS-03 | Claude Opus 4.6 | vb_combat_templates.py | 6/10 | 8 EventBus.Publish, DamageCalculator wrong arity |
| 7 | Opus-CS-04 | Claude Opus 4.6 | content_templates.py | 5/10 | 26 EventBus.Publish — most of any file |
| 8 | Opus-CS-05 | Claude Opus 4.6 | gameplay_templates.py | 7/10 | Behavior tree leaves are stubs |
| 9 | Opus-CS-06 | Claude Opus 4.6 | vfx_templates.py | 5/10 | VisualEffect without VisualEffectAsset |
| 10 | Opus-CS-07 | Claude Opus 4.6 | camera_templates.py | 9/10 | All CM 3.x correct — exemplary |
| 11 | Opus-CS-08 | Claude Opus 4.6 | scene_templates.py | 8/10 | NavMeshBuildSource struct-copy bug |
| 12 | Opus-RIG-01 | Claude Opus 4.6 | Rig templates (all 10) | 3/10 | Zero twist bones, zero corrective shapes |
| 13 | Opus-RIG-02 | Claude Opus 4.6 | Weight painting | 5/10 | No 4-influence limit enforcement |
| 14 | Opus-RIG-03 | Claude Opus 4.6 | Facial rigging | 3/10 | 19 bones, 3 expressions, no FACS/visemes |
| 15 | Opus-ANIM-01 | Claude Opus 4.6 | Biped/quadruped gaits | 4/10 | Single-sine, quadruped walk is actually a trot |
| 16 | Opus-ANIM-02 | Claude Opus 4.6 | Hexapod/arachnid/serpent | 7/10 | Hexapod correct, serpent excellent |
| 17 | Opus-ANIM-03 | Claude Opus 4.6 | Attack animations | 6/10 | Good structure, linear interpolation, no root motion |
| 18 | Opus-ANIM-04 | Claude Opus 4.6 | Combat timing data | 9/10 | FromSoft-quality — crown jewel |
| 19 | Opus-ENV-01 | Claude Opus 4.6 | Terrain + erosion | 5.5/10 | Correct fBm, 1024 cap, unvectorized |
| 20 | Opus-ENV-02 | Claude Opus 4.6 | Dungeons + towns | 6/10 | BSP solid, Manhattan Voronoi bad |
| 21 | Opus-FBX-01 | Claude Opus 4.6 | FBX export pipeline | 7/10 | Missing use_tspace, use_armature_deform_only |
| 22 | Opus-TOK-01 | Claude Opus 4.6 | Token efficiency audit | N/A | 75,800 tokens, 28% easy reduction |
| 23 | GPT-CS-01 | GPT-5.4 | C# template cross-review | 6.5/10 avg | EventBus.Publish pattern does not exist in VB |
| 24 | GPT-CS-02 | GPT-5.4 | shader_templates.py | 9/10 | Missing shadow/fog pragmas |
| 25 | GPT-CS-03 | GPT-5.4 | build_templates.py | 8/10 | Correct GameCI, no code signing |
| 26 | GPT-SEC-01 | GPT-5.4 | Security adversarial testing | 4/10 bypass | __call__ chaining exploit confirmed |
| 27 | GPT-ANIM-01 | GPT-5.4 | Monster animation gaps | 2/10 | Capture + Evolution = 0/10, core mechanics missing |
| 28 | GPT-VFX-01 | GPT-5.4 | VFX-animation sync | 5/10 | Single vfx_frame, no combo support |
| 29 | Gem25-ARCH-01 | Gemini 2.5 Pro | Architecture review | 7/10 | unity_server.py refactor complete, blender_server still monolith |
| 30 | Gem25-TEST-01 | Gemini 2.5 Pro | Test infrastructure | 5/10 | 5,768 tests but no coverage tooling |
| 31 | Gem31-RIG-01 | Gemini 3.1 Pro Preview | Rig biomechanics | 3/10 | Spring bones non-functional (DAMPED_TRACK with no target) |
| 32 | Gem31-ANIM-01 | Gemini 3.1 Pro Preview | Gait biomechanics | 5/10 | Quadruped run is a bound, not a gallop |
| 33 | Gem31-ENV-01 | Gemini 3.1 Pro Preview | Environment pipeline | 6/10 | Scatter correct, no moisture/tilt filtering |
| 34 | Gem31-UI-01 | Gemini 3.1 Pro Preview | UI/UX templates | 7.5/10 | UXML good, USS drifts from ThemeManager |
| 35 | Gem31-WORLD-01 | Gemini 3.1 Pro Preview | Worldbuilding | 5.5/10 | Building grammar = solid boxes, no openings |
| 36 | GemFlash-SCAN-01 | Gemini Flash | Full-codebase pattern scan | N/A | 23 local _sanitize copies identified |

---

## Appendix B: File Reference

### Source Files by Category

| Category | Path | Files | Lines |
|----------|------|-------|-------|
| Unity MCP Entry | `src/veilbreakers_mcp/unity_server.py` | 1 | 23 |
| Unity Tool Handlers | `src/veilbreakers_mcp/unity_tools/` | 22 | 8,972 |
| Blender MCP Entry | `src/veilbreakers_mcp/blender_server.py` | 1 | 1,988 |
| Blender Addon | `blender_addon/` | 38 | ~12,000 |
| Shared Libraries | `src/veilbreakers_mcp/shared/` | 19 | ~8,500 |
| Unity Templates | `src/veilbreakers_mcp/shared/unity_templates/` | 34 | ~35,000 |
| Security | `*/security.py` (2 copies) | 2 | 388 |
| Tests | `tests/` | 86 | ~25,000 |

### Key Files for Each Bug

| Bug ID | File(s) | Line(s) |
|--------|---------|---------|
| F1 | `unity_tools/scene.py` + `unity_templates/animation_templates.py` | 495-502 + 280-285 |
| C1 | `unity_templates/content_templates.py`, `unity_templates/vb_combat_templates.py` | Multiple |
| C2 | `unity_templates/content_templates.py`, `unity_templates/vb_combat_templates.py`, `unity_templates/ux_templates.py`, `unity_tools/ux.py` | Multiple |
| C3 | `unity_templates/vb_combat_templates.py` | 666, 708 |
| S1 | `shared/security.py`, `blender_addon/security.py` | 30-37 |
| S2 | `shared/security.py`, `blender_addon/security.py` | 54-66 |
| S3 | `shared/security.py`, `blender_addon/security.py` | 187-190 |
| S4 | `blender_addon/socket_server.py` | 50-55 |
| S5 | `shared/gemini_client.py` | 126 |
| S6 | `shared/wcag_checker.py`, `unity_templates/ui_templates.py` | 249, 16 |

---

## Appendix C: Scoring Methodology

All scores use a 0-10 scale calibrated against AAA game development standards:

| Score | Meaning |
|-------|---------|
| 9-10 | Production-ready. Ship it. |
| 7-8 | Good foundation, minor fixes needed. |
| 5-6 | Functional but significant gaps for AAA use. |
| 3-4 | Proof of concept. Needs substantial work. |
| 1-2 | Stub or non-functional. |
| 0 | Completely absent. |

Scores represent **consensus** across all agents reviewing that area. Where agents disagreed by more than 2 points, the lower score was used (conservative approach for a fix prompt).

---

## Appendix D: Quick-Reference Fix Commands

### Phase 1 One-Liners

```bash
# S1: Block type() in security validator
# In both security.py files, add "type" to BLOCKED_FUNCTIONS frozenset

# S2: Block register_class in bpy attrs
# In both security.py files, add "register_class", "unregister_class" to BLOCKED_BPY_ATTRS

# FBX fix: Add to animation_export.py kwargs dict (after line 1170)
# "use_tspace": True,
# "use_armature_deform_only": True,

# S5: Gemini client fix (gemini_client.py:126)
# Replace: url = f"...?key={self.api_key}"
# With:    url = "..."  and  headers = {"x-goog-api-key": self.api_key}
```

### Grep Commands to Find All Instances

```bash
# Find all EventBus.Publish calls
grep -rn "EventBus\.Publish" src/

# Find all HeroPath references
grep -rn "HeroPath" src/

# Find all local _sanitize definitions (migration targets)
grep -rn "def _sanitize" src/veilbreakers_mcp/shared/unity_templates/

# Find all files without logging
# (compare against: grep -rl "logger" src/)
```

---

## Appendix E: Findings Added After Initial Report (Gap Check)

The following 15 findings were identified in the 36-agent review but missing from the initial report draft:

### Runtime Bugs (Not in Main Sections)
| # | Finding | File | Agent |
|---|---------|------|-------|
| G1 | `MonsterCollection.uxml` corruption-bar-fill has zero width (overflow bug) | Assets/Resources/UI/Templates/MonsterCollection.uxml:145 | Agent 2 (Background Scan) |
| G2 | `delight.py` module-level `raise ImportError` crashes entire MCP server if numpy missing | blender_server.py imports delight_albedo at module load (line 31) | Agent 9 (Runtime Edge Cases) |
| G3 | `palette_validator.py` same module-level ImportError crash | shared/palette_validator.py:21-27 | Agent 9 |
| G4 | Race condition in lazy `_connection` singleton (no threading lock) | blender_server.py:42-58, unity_server.py (audio client) | Agent 9 |
| G5 | `json.loads()` on malformed Blender response — unhandled JSONDecodeError | blender_client.py:96 | Agent 9 |
| G6 | Character controller has double-Move bug (horizontal movement applied twice per frame) | game_templates.py character controller generator | Agent 7 (VB-Unity Auditor) |
| G7 | ReDoS risk in prefab regex selector — user regex passed to `new Regex()` | prefab_templates.py selector resolution | Agent 7 |

### 3D Pipeline Gaps (Not in Main Sections)
| # | Finding | File | Agent |
|---|---------|------|-------|
| G8 | Dragon template missing wing membrane bones (3-5 "finger" bones for membrane skinning) | rigging_templates.py DRAGON_BONES | Agent 24 (Skeleton Topology) |
| G9 | No MikkTSpace tangent basis option for normal map baking | Blender bake pipeline | Agent 13 (AAA 3D) |
| G10 | UV padding default 2px — AAA requires 4-8px minimum at 1024+ for mipmap safety | blender_server.py:510 `padding: int = 2` | Agent 13 |
| G11 | `screenshot_diff.py` pixel-by-pixel Python loop — 100ms per 1080p image | screenshot_diff.py:62-68, 141-153 | Agent 12 (Perf/DX) |
| G12 | `texture_ops._render_wear_numpy()` nested Python loops for wear map rendering — 1.75s per call | texture_ops.py:617-636 | Agent 12 |

### Animation/Export Gaps (Not in Main Sections)
| # | Finding | File | Agent |
|---|---------|------|-------|
| G13 | Mixamo retarget drops ALL 30 finger bones and hip translation (COPY_ROTATION only, no COPY_LOCATION) | animation_export.py:34-62 (mapping), :772-776 (constraints) | Agent 25 (Export) |
| G14 | Animator Controllers generate states but ZERO transitions between them (disconnected islands) | animation_templates.py (no AddTransition calls) | Agent 25 |
| G15 | No AnimationEvent bridge from Blender combat timing to Unity AnimationClip events | _combat_timing.py produces events, animation_export.py doesn't serialize them | Agent 25 |

### AAA Game References (Research Context)
The evolution and combat command animation designs were informed by research into:
- **FromSoftware** (Elden Ring/Dark Souls): Monster attack telegraphs, delayed attacks, hit reactions with hitstop
- **Capcom** (Monster Hunter World/Rise): Monster weight, secondary motion, turf war choreography, capture/trap sequences
- **Game Freak** (Pokemon Legends: Arceus/Scarlet-Violet): Evolution transformation (glow → silhouette morph → reveal), 1000+ creature idle variations
- **BioWare** (Dragon Age: Inquisition/Veilguard): Real-time party combat, companion command flow, tactical pause + execution, formation systems
- **Level-5** (Ni no Kuni): Real-time monster command flow (send → attack → return), All-Out synchronized commands
- **Bandai Namco** (Digimon Survive/World): Multi-stage Digivolution with sectional body transformation
- **Atlus** (Shin Megami Tensei V): Demon fusion particle ceremony, per-hit hitstop rhythm
- **Square Enix** (Final Fantasy XVI): Eikon transformation with element-specific metamorphosis (fire cocoon, ice crystallization)
- **Pocketpair** (Palworld): Sphere throw → deploy, recall compression, multi-Pal simultaneous combat

---

*This report is the single source of truth for all VeilBreakers GameDev Toolkit development. Updated 2026-03-22 by consensus of 36 AI agents across 4 model families.*
