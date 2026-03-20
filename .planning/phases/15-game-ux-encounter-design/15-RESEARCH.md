# Phase 15: Game UX & Encounter Design - Research

**Researched:** 2026-03-20
**Domain:** Unity game UX systems, encounter scripting, AI director, accessibility, PrimeTween animation, TextMeshPro, equipment visuals, boss AI, world map
**Confidence:** HIGH

## Summary

Phase 15 covers a broad set of gameplay UX features and encounter design systems, all implemented as C# template generators in the existing MCP toolkit pattern. The phase adds a new `unity_ux` compound tool to unity_server.py and extends the existing `unity_gameplay` tool for encounter/AI director actions. A new `ux_templates.py` file will house 12+ template generators covering minimap/compass, tutorial/onboarding, damage numbers, interaction prompts, encounter scripting, AI director/DDA, encounter simulation, PrimeTween sequences, accessibility features, TextMeshPro setup, equipment rarity/corruption visuals, character creation screen, boss AI, and 2D world map generation.

The project explicitly uses PrimeTween (not DOTween) via OpenUPM, so SHDR-04 must generate PrimeTween `Tween.*` and `Sequence.Create()` API calls. VeilBreakers already has an AAA character select screen with carousel navigation, theme transitions, and embark cinematics -- VB-09 generates the boilerplate for this pattern. The existing compound tool pattern (action dispatch, `_write_to_unity`, JSON response with `next_steps`) is well-established across 19 Unity tools and should be followed exactly.

**Primary recommendation:** Create `ux_templates.py` and `encounter_templates.py` as two new template modules, register them under a new `unity_ux` compound tool, and extend `unity_gameplay` for encounter-specific actions. All generated C# must use PrimeTween for UI animation and delegate to existing VeilBreakers systems (BrandSystem, CorruptionSystem, DamageCalculator) where applicable.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Minimap/compass** (UIX-01): Render texture minimap with world-space markers, rotatable compass, configurable zoom
- **Tutorial/onboarding** (UIX-02): Step-based tutorial system with tooltip overlays, highlight rects, action triggers
- **Damage numbers** (UIX-03): Floating text with DOTween animation, color-coded by damage type/brand, crit scaling (NOTE: must use PrimeTween, not DOTween)
- **Interaction prompts** (UIX-04): Context-sensitive "Press E" with dynamic key rebind display, proximity triggers
- **Encounter scripting** (AID-01): Trigger volumes, wave definitions, spawn conditions, victory/defeat callbacks
- **AI director / DDA** (AID-02): Track player performance (deaths, time, damage taken), adjust spawn rates/enemy stats dynamically
- **Encounter simulation** (AID-03): Run N encounters, report win rate, average duration, DPS stats -- EditorWindow tool
- **PrimeTween integration** (SHDR-04): VeilBreakers uses PrimeTween -- generate sequences using PrimeTween API, not DOTween
- **Colorblind modes** (ACC-01): Deuteranopia, protanopia, tritanopia filters via post-processing
- **Subtitle sizing** (ACC-01): Configurable text scale with minimum readable size
- **Screen reader tags** (ACC-01): ARIA-like accessibility labels on UI elements
- **Motor accessibility** (ACC-01): Adjustable input timing, toggle vs hold options
- **Font asset creation** (PIPE-10): Generate TMP font assets from TTF/OTF sources
- **TMP component setup** (PIPE-10): Configure TextMeshProUGUI components with rich text, font fallback chains
- **VeilBreakers uses Cinzel font**: Dark fantasy theme font for UI
- **Rarity tiers** (EQUIP-07): Common (gray), Uncommon (green), Rare (blue), Epic (purple), Legendary (gold glow + particles)
- **Corruption progression** (EQUIP-08): 0-100% with increasing vein patterns, color shift, particle emission
- **Character creation/selection** (VB-09): Choose hero path, customize appearance, name entry -- UI Toolkit
- **Boss AI** (VB-10): Multi-phase state machine, HP threshold transitions, unique attack patterns, enrage timer
- **2D world map from 3D terrain** (RPG-08): Generate 2D map texture from heightmap data, fog-of-war, location markers, player position

### Claude's Discretion
- Minimap render texture resolution and update frequency
- Tutorial step transition animations
- Damage number float height and duration
- AI director difficulty adjustment curves
- Accessibility filter shader implementation
- TMP font atlas resolution and character sets
- Rarity particle density and glow intensity
- Boss enrage timer duration and stat multipliers

### Deferred Ideas (OUT OF SCOPE)
None -- autonomous mode stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| UIX-01 | Minimap/compass with world-space markers | Render texture camera pattern, orthographic projection, UI Toolkit RawImage, world marker tracking |
| UIX-02 | Tutorial/onboarding sequences with tooltip overlays | Step-based state machine, highlight rect overlay, action trigger callbacks |
| UIX-03 | Damage number floating text system | Object-pooled TextMeshPro world-space text, PrimeTween animation, brand color coding |
| UIX-04 | Context-sensitive interaction prompts | Proximity trigger, Input System rebind display, PrimeTween fade/scale animation |
| AID-01 | Encounter scripting system (triggers, waves, conditions, AI director) | Trigger volume + wave SO definitions + spawn coroutines + victory/defeat callbacks |
| AID-02 | Threat escalation / AI director (dynamic difficulty adjustment) | Performance tracker (deaths/time/damage), difficulty curve, spawn rate/stat multipliers |
| AID-03 | Encounter simulation for balance testing | EditorWindow Monte Carlo runner, statistics aggregation, IMGUI report |
| SHDR-04 | PrimeTween animation sequences for UI polish | PrimeTween API: Tween.*, Sequence.Create().Chain().Group(), Shake/Punch |
| ACC-01 | Accessibility features (colorblind, subtitles, screen reader, motor) | Color matrix post-processing shader, TMP scaling, accessibility labels, input timing |
| PIPE-10 | TextMeshPro setup (font assets, components, rich text, fallbacks) | TMP_FontAsset.CreateFontAsset editor script, font fallback chain configuration |
| EQUIP-07 | Equipment rarity visual effects (Common-Legendary) | Particle system + emission glow per tier, extends Phase 7 VFX pattern |
| EQUIP-08 | Equipment corruption visual progression (0-100%) | Material property animation (vein pattern, color shift), particle emission scaling |
| VB-09 | Character creation/selection screen | UI Toolkit document, hero path carousel, appearance customization, name entry |
| VB-10 | Boss AI behavior (multi-phase, enrage) | Hierarchical FSM, HP threshold phase transitions, enrage timer, attack pattern sets |
| RPG-08 | 2D world map from 3D terrain data | TerrainData.GetHeights to texture, fog-of-war mask, location markers, player blip |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PrimeTween | latest (OpenUPM) | UI animation sequences | Already installed in VeilBreakers via OpenUPM; zero-allocation, type-safe |
| TextMeshPro | 4.0+ (Unity 6 built-in) | Font rendering, damage numbers, UI text | Unity's standard text solution, SDF rendering, rich text support |
| Unity Input System | 1.11+ | Key rebind display for interaction prompts | Already used by VeilBreakers for input handling |
| Unity UI Toolkit | Built-in | Character select screen, tutorial overlays | Matches existing VeilBreakers UI pattern (UIDocument + UXML + USS) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| URP Post-Processing | Built-in | Colorblind filter, accessibility effects | ACC-01 colorblind modes via ScriptableRendererFeature |
| Cinemachine 3.x | Built-in | Camera shake integration for damage feedback | Already used, camera shake reuse from Phase 14 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PrimeTween | DOTween | DOTween is more popular but PrimeTween is already installed; zero allocation advantage |
| Custom colorblind shader | SOHNE/Colorblindness package | Package uses ChannelMixer; custom URP RendererFeature gives more control and matches existing shader pattern |
| Custom fog-of-war | MangoFog package | External dependency unnecessary for generated template code |

**Installation:**
No new packages needed. PrimeTween already installed via OpenUPM. TextMeshPro built into Unity 6.

## Architecture Patterns

### Recommended Project Structure
```
Tools/mcp-toolkit/src/veilbreakers_mcp/
  shared/unity_templates/
    ux_templates.py          # UIX-01 through UIX-04, ACC-01, PIPE-10, SHDR-04, VB-09, RPG-08
    encounter_templates.py   # AID-01, AID-02, AID-03, VB-10
    vfx_templates.py         # Extend: EQUIP-07, EQUIP-08 (rarity/corruption VFX generators)
  unity_server.py            # Add unity_ux compound tool, extend unity_gameplay or unity_vfx
Tools/mcp-toolkit/tests/
  test_ux_templates.py       # Tests for ux_templates.py generators
  test_encounter_templates.py # Tests for encounter_templates.py generators
```

### Pattern 1: Compound Tool with Action Dispatch
**What:** Single `unity_ux` tool with Literal action parameter dispatching to handler functions
**When to use:** All new UX features (UIX-01 through UIX-04, ACC-01, PIPE-10, SHDR-04, VB-09, RPG-08)
**Example:**
```python
# Source: Existing unity_content pattern in unity_server.py
@mcp.tool()
async def unity_ux(
    action: Literal[
        "create_minimap",           # UIX-01
        "create_tutorial_system",    # UIX-02
        "create_damage_numbers",     # UIX-03
        "create_interaction_prompts", # UIX-04
        "create_primetween_sequence", # SHDR-04
        "create_accessibility",      # ACC-01
        "create_tmp_font_asset",     # PIPE-10
        "setup_tmp_components",      # PIPE-10
        "create_character_select",   # VB-09
        "create_world_map",          # RPG-08
    ],
    # ... params
) -> str:
```

### Pattern 2: Multi-File Generator Returns
**What:** Template generators returning tuples for multi-file systems (SO + MonoBehaviour + UXML + USS)
**When to use:** Character select (VB-09), tutorial system (UIX-02), accessibility settings
**Example:**
```python
# Source: Existing content_templates.py pattern
def generate_character_select_script(
    hero_paths: list[str] | None = None,
    namespace: str = "",
) -> tuple[str, str, str, str]:
    """Returns (data_cs, manager_cs, uxml, uss)."""
```

### Pattern 3: ScriptableObject Data + Runtime MonoBehaviour
**What:** SO for configuration data, MonoBehaviour for runtime behavior
**When to use:** Encounter waves (AID-01), boss phases (VB-10), tutorial steps (UIX-02), rarity tiers (EQUIP-07)
**Example:**
```python
# Encounter wave definition as ScriptableObject
def generate_encounter_system_script() -> tuple[str, str]:
    """Returns (encounter_data_so_cs, encounter_manager_cs)."""
```

### Pattern 4: EditorWindow for Simulation Tools
**What:** IMGUI EditorWindow for encounter simulation (AID-03)
**When to use:** Balance testing tools that run in editor
**Example:**
```python
# Source: Existing content_templates.py encounter simulator pattern
def generate_encounter_simulator_script() -> str:
    """Returns editor window C# with Monte Carlo simulation."""
    # MUST use 'using UnityEditor;' -- editor-only tool
```

### Pattern 5: VB Delegation Pattern
**What:** Generated MonoBehaviours delegate to existing static utility classes
**When to use:** Damage numbers (use DamageCalculator), boss AI (use BrandSystem), encounter scripting
**Example:**
```csharp
// Source: VB delegation pattern from Phase 12
// Generated code references existing systems by name:
float damage = DamageCalculator.Calculate(attacker, defender, damageType);
Color brandColor = BrandSystem.GetBrandColor(damageType);
```

### Anti-Patterns to Avoid
- **Reimplementing brand/synergy/corruption logic:** Always delegate to existing VeilBreakers static classes
- **Using DOTween API:** VeilBreakers uses PrimeTween -- never generate DOTween.To or DOSequence
- **Using Cinemachine 2.x API:** Only CinemachineCamera + OrbitalFollow (3.x), never FreeLook/VirtualCamera
- **Runtime MonoBehaviours with `using UnityEditor`:** Only editor tools (AID-03 simulator) may use UnityEditor namespace
- **Instantiate/Destroy for pooled objects:** Damage numbers, interaction prompts must use object pooling

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| UI tween animation | Custom lerp coroutines | PrimeTween Tween.*/Sequence.Create() | Zero-allocation, type-safe, built-in easing curves |
| Colorblind simulation | Manual color channel swapping | 3x3 LMS color transformation matrices | Scientifically accurate; well-documented Brettel/Vienot method |
| Font atlas generation | Manual texture packing | TMP_FontAsset.CreateFontAsset() | Handles SDF generation, glyph packing, material creation |
| Object pooling | Custom pool for damage numbers | Unity's ObjectPool<T> or generated pool from Phase 10 CODE-07 | Already generated; handles grow/shrink/cleanup |
| Input display strings | Hardcoded "Press E" | InputAction.GetBindingDisplayString() | Handles rebinding, gamepad glyphs automatically |
| Encounter statistics | Manual mean/variance calc | System.Linq aggregate + standard deviation helper | Simpler, less error-prone for Monte Carlo stats |

**Key insight:** PrimeTween is already installed and its API is simpler than hand-rolling animation coroutines. The PrimeTween `Sequence.Create().Chain().Group()` pattern handles complex UI choreography in a single expression.

## Common Pitfalls

### Pitfall 1: DOTween API in PrimeTween Project
**What goes wrong:** Generated C# contains `DOTween.To()`, `DOTweenModuleUI`, or `transform.DOScale()` which won't compile
**Why it happens:** DOTween is more popular and appears more frequently in training data
**How to avoid:** Every tween call must use `Tween.*` or `Sequence.Create()` from PrimeTween namespace. Never use `DO` prefix
**Warning signs:** Any string starting with "DO" in tween context, `using DG.Tweening`

### Pitfall 2: Render Texture Minimap Performance
**What goes wrong:** Minimap camera renders every frame at full resolution causing frame drops
**Why it happens:** Default camera settings render everything at full quality
**How to avoid:** Use lower resolution render texture (256x256 default), set culling mask to Minimap layer only, reduce update frequency to every 3rd frame
**Warning signs:** Draw call count doubling when minimap is active

### Pitfall 3: Damage Number GC Allocation Spikes
**What goes wrong:** Instantiate/Destroy creates garbage collection spikes during combat
**Why it happens:** New TextMeshPro objects allocated per damage number
**How to avoid:** Object pool pattern -- pre-allocate pool of damage number prefabs, reuse on completion
**Warning signs:** GC.Alloc spikes in Profiler during heavy combat

### Pitfall 4: Colorblind Shader sRGB vs Linear
**What goes wrong:** Color transformation matrices produce incorrect results
**Why it happens:** Matrices assume linear RGB but Unity UI/post-processing may be in sRGB
**How to avoid:** Convert sRGB to linear before matrix multiply, convert back after. URP typically works in linear space when project is set to Linear color space
**Warning signs:** Colors look washed out or oversaturated in colorblind mode

### Pitfall 5: Boss AI Phase Transition During Attack Animation
**What goes wrong:** Boss enters new phase mid-attack, causing animation glitches
**Why it happens:** HP threshold check triggers immediately without waiting for current state to complete
**How to avoid:** Queue phase transition, execute on next state transition point. Use `_pendingPhaseTransition` flag
**Warning signs:** Animation pops, attacks interrupted mid-swing

### Pitfall 6: TMP_FontAsset.CreateFontAsset Missing Glyphs
**What goes wrong:** Font asset created but missing characters, showing squares
**Why it happens:** Default character set may not include extended ASCII or special characters
**How to avoid:** Explicitly specify character set including ASCII 32-126 plus extended characters needed for the game
**Warning signs:** Rectangle/missing glyph characters in UI text

### Pitfall 7: World Map Fog of War Texture Memory
**What goes wrong:** Full-resolution fog-of-war texture consumes excessive memory
**Why it happens:** Using same resolution as terrain heightmap for fog mask
**How to avoid:** Use lower resolution fog texture (512x512 for most worlds), bilinear filtering hides the low resolution
**Warning signs:** Memory spikes when opening world map

### Pitfall 8: Encounter Simulator Blocking Editor
**What goes wrong:** Monte Carlo simulation with high N freezes Unity editor
**Why it happens:** Running simulation synchronously on main thread
**How to avoid:** Use EditorApplication.update callback with per-frame batch processing, or async Task with progress bar
**Warning signs:** Editor becoming unresponsive during "Run Simulation"

## Code Examples

### PrimeTween UI Sequence (SHDR-04)
```csharp
// Source: PrimeTween GitHub README
using PrimeTween;

// Damage number float-up + fade-out
Sequence.Create()
    .Group(Tween.UIAnchoredPosition(rectTransform,
        endValue: rectTransform.anchoredPosition + Vector2.up * 80f,
        duration: 0.8f, ease: Ease.OutCubic))
    .Group(Tween.Alpha(canvasGroup, endValue: 0f,
        duration: 0.8f, ease: Ease.InQuad))
    .OnComplete(() => ReturnToPool(gameObject));

// Screen shake on hit
Tween.ShakeLocalPosition(transform, strength: new Vector3(0.5f, 0.5f, 0),
    duration: 0.3f, frequency: 15);

// Button hover punch effect
Tween.PunchLocalScale(button.transform, strength: Vector3.one * 0.1f,
    duration: 0.2f, frequency: 10);

// Complex UI entrance sequence
Sequence.Create()
    .Chain(Tween.Scale(panel, startValue: 0f, endValue: 1f,
        duration: 0.3f, ease: Ease.OutBack))
    .Chain(Tween.Alpha(titleCanvasGroup, endValue: 1f, duration: 0.2f))
    .Group(Tween.UIAnchoredPosition(titleRect,
        startValue: new Vector2(0, 30), endValue: Vector2.zero,
        duration: 0.2f, ease: Ease.OutQuad));
```

### Minimap Render Texture Setup (UIX-01)
```csharp
// Source: Standard Unity minimap pattern
// Editor script creates: orthographic camera, render texture, RawImage UI element
var minimapCam = new GameObject("MinimapCamera").AddComponent<Camera>();
minimapCam.orthographic = true;
minimapCam.orthographicSize = 50f; // Configurable zoom
minimapCam.cullingMask = LayerMask.GetMask("Minimap", "Terrain");
minimapCam.clearFlags = CameraClearFlags.SolidColor;
minimapCam.backgroundColor = new Color(0.1f, 0.1f, 0.15f, 1f);

var renderTex = new RenderTexture(256, 256, 16);
minimapCam.targetTexture = renderTex;

// Follow player position (XZ only)
minimapCam.transform.position = player.position + Vector3.up * 100f;
minimapCam.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
```

### Colorblind Simulation Matrix (ACC-01)
```hlsl
// Source: Brettel/Vienot colorblind simulation research
// Applied as URP ScriptableRendererFeature fullscreen pass
static readonly float3x3 Protanopia = float3x3(
    0.170556992f, 0.829443014f, 0.0f,
    0.170556991f, 0.829443008f, 0.0f,
    -0.004517144f, 0.004517144f, 1.0f
);

static readonly float3x3 Deuteranopia = float3x3(
    0.33066007f, 0.66933993f, 0.0f,
    0.33066007f, 0.66933993f, 0.0f,
    -0.02785538f, 0.02785538f, 1.0f
);

static readonly float3x3 Tritanopia = float3x3(
    1.0f, 0.1273989f, -0.1273989f,
    0.0f, 0.8739093f, 0.1260907f,
    0.0f, 0.8739093f, 0.1260907f
);

// In fragment shader:
float3 simulated = mul(selectedMatrix, originalColor.rgb);
```

### TMP Font Asset Creation (PIPE-10)
```csharp
// Source: Unity TMP API
// Editor script for font asset generation
Font sourceFont = AssetDatabase.LoadAssetAtPath<Font>(fontPath);
TMP_FontAsset fontAsset = TMP_FontAsset.CreateFontAsset(
    sourceFont,
    samplingPointSize: 48,
    atlasPadding: 5,
    renderMode: GlyphRenderMode.SDFAA,
    atlasWidth: 1024,
    atlasHeight: 1024
);

// Add characters
fontAsset.TryAddCharacters("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 !@#$%^&*()-_=+[]{}|;':\",./<>?");

// Save asset
AssetDatabase.CreateAsset(fontAsset, outputPath);
AssetDatabase.SaveAssets();

// Font fallback chain
fontAsset.fallbackFontAssetTable.Add(fallbackFont);
```

### Boss AI Multi-Phase FSM (VB-10)
```csharp
// Source: Standard boss AI pattern
public enum BossPhase { Phase1, Phase2, Phase3, Enrage }

[Header("Phase Transitions")]
[SerializeField] private float _phase2Threshold = 0.7f; // 70% HP
[SerializeField] private float _phase3Threshold = 0.35f; // 35% HP
[SerializeField] private float _enrageTimer = 180f; // 3 minutes

private BossPhase _currentPhase = BossPhase.Phase1;
private float _enrageElapsed;
private bool _pendingTransition;

void CheckPhaseTransition()
{
    float hpRatio = _currentHP / _maxHP;
    BossPhase targetPhase = _currentPhase;

    if (_enrageElapsed >= _enrageTimer)
        targetPhase = BossPhase.Enrage;
    else if (hpRatio <= _phase3Threshold)
        targetPhase = BossPhase.Phase3;
    else if (hpRatio <= _phase2Threshold)
        targetPhase = BossPhase.Phase2;

    if (targetPhase != _currentPhase)
    {
        _pendingTransition = true;
        _targetPhase = targetPhase;
    }
}
```

### Encounter Wave Definition (AID-01)
```csharp
// Source: Standard wave spawner pattern with SO data
[CreateAssetMenu(menuName = "VeilBreakers/Encounter/Wave Definition")]
public class VB_WaveDefinition : ScriptableObject
{
    [System.Serializable]
    public class SpawnEntry
    {
        public string prefabName;
        public int count;
        public float spawnDelay;
        public float difficultyMultiplier = 1f;
    }

    public SpawnEntry[] entries;
    public float waveDelay = 5f;
    public string[] victoryConditions; // "all_dead", "timer", "objective"
}
```

### AI Director / DDA (AID-02)
```csharp
// Source: Dynamic difficulty adjustment pattern
public class VB_AIDirector : MonoBehaviour
{
    [Header("Performance Tracking")]
    private int _recentDeaths;
    private float _averageClearTime;
    private float _damageTakenRatio;

    [Header("Adjustment Curves")]
    [SerializeField] private AnimationCurve _spawnRateCurve;
    [SerializeField] private AnimationCurve _enemyStatMultiplierCurve;
    [SerializeField] private float _adjustmentSpeed = 0.1f;

    private float _difficultyScore = 0.5f; // 0 = easiest, 1 = hardest

    public float GetSpawnRateMultiplier() => _spawnRateCurve.Evaluate(_difficultyScore);
    public float GetStatMultiplier() => _enemyStatMultiplierCurve.Evaluate(_difficultyScore);

    void UpdateDifficulty()
    {
        // Too many deaths -> decrease difficulty
        // Fast clear times -> increase difficulty
        // Low damage taken -> increase difficulty
        float target = Mathf.Clamp01(
            0.5f + (_averageClearTime < _targetClearTime ? 0.1f : -0.1f)
                 + (_recentDeaths > 2 ? -0.2f : 0f)
                 + (_damageTakenRatio < 0.3f ? 0.1f : -0.05f)
        );
        _difficultyScore = Mathf.MoveTowards(_difficultyScore, target, _adjustmentSpeed * Time.deltaTime);
    }
}
```

### Equipment Rarity VFX (EQUIP-07)
```csharp
// Source: Extending Phase 7 VFX pattern
public static readonly Dictionary<ItemRarity, RarityVFXConfig> RARITY_VFX = new()
{
    { ItemRarity.Common,    new(Color.gray,   0f,   0) },
    { ItemRarity.Uncommon,  new(new Color(0.2f, 0.8f, 0.2f), 0.3f, 5) },
    { ItemRarity.Rare,      new(new Color(0.2f, 0.4f, 1.0f), 0.6f, 15) },
    { ItemRarity.Epic,      new(new Color(0.6f, 0.2f, 0.9f), 0.8f, 30) },
    { ItemRarity.Legendary, new(new Color(1.0f, 0.8f, 0.1f), 1.2f, 60) },
};
// glow_intensity, particle_rate per rarity
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| DOTween (DOTween.To, transform.DOScale) | PrimeTween (Tween.Scale, Sequence.Create) | VeilBreakers project decision | All UI animation must use PrimeTween API |
| Cinemachine 2.x (FreeLook, VirtualCamera) | Cinemachine 3.x (CinemachineCamera) | Unity 6 | Camera shake references must use 3.x API |
| UGUI Canvas for complex UI | UI Toolkit (UXML + USS + UIDocument) | VeilBreakers convention | Character select, tutorial overlays use UI Toolkit |
| Manual font atlas baking | TMP_FontAsset.CreateFontAsset() | TMP 3.0+ | Editor script can generate font assets programmatically |
| Custom post-processing stack | URP ScriptableRendererFeature | URP 14+ / Unity 6 | Colorblind filter as custom render pass with RenderGraph |

**Deprecated/outdated:**
- DOTween: Not installed in project, PrimeTween is the standard
- Cinemachine 2.x FreeLook: Replaced by CinemachineCamera in Unity 6
- Legacy Text/TextMesh: TextMeshPro is the standard, built into Unity 6
- OnGUI for game UI: Only used for EditorWindows (IMGUI), never for runtime game UI

## Open Questions

1. **PrimeTween Shake with Camera**
   - What we know: PrimeTween has `Tween.ShakeCamera()` but it may conflict with Cinemachine 3.x
   - What's unclear: Whether to use PrimeTween camera shake or Cinemachine impulse for damage feedback
   - Recommendation: Use Cinemachine CinemachineImpulseSource for camera effects, PrimeTween for UI element shake

2. **TMP_FontAsset.CreateFontAsset Character Coverage**
   - What we know: API exists and works for basic ASCII
   - What's unclear: Whether TryAddCharacters handles all extended characters needed for localization
   - Recommendation: Generate with ASCII + extended Latin + common symbols, document as extensible

3. **Colorblind Filter URP RenderGraph vs Legacy**
   - What we know: Phase 10 SHDR-02 established URP RendererFeature pattern with RecordRenderGraph
   - What's unclear: Whether fullscreen blit is straightforward with RenderGraph API
   - Recommendation: Follow Phase 10 RendererFeature pattern, use fullscreen blit pass

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | `Tools/mcp-toolkit/pyproject.toml` ([tool.pytest.ini_options]) |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_ux_templates.py tests/test_encounter_templates.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UIX-01 | Minimap C# generator produces Camera + RenderTexture + RawImage setup | unit | `pytest tests/test_ux_templates.py::TestMinimap -x` | Wave 0 |
| UIX-02 | Tutorial system generator produces step-based state machine + overlay | unit | `pytest tests/test_ux_templates.py::TestTutorialSystem -x` | Wave 0 |
| UIX-03 | Damage numbers generator produces pooled TMP + PrimeTween animation | unit | `pytest tests/test_ux_templates.py::TestDamageNumbers -x` | Wave 0 |
| UIX-04 | Interaction prompts generator produces proximity trigger + key rebind | unit | `pytest tests/test_ux_templates.py::TestInteractionPrompts -x` | Wave 0 |
| AID-01 | Encounter scripting generator produces wave SO + trigger volume + callbacks | unit | `pytest tests/test_encounter_templates.py::TestEncounterScripting -x` | Wave 0 |
| AID-02 | AI director generator produces performance tracker + difficulty curve | unit | `pytest tests/test_encounter_templates.py::TestAIDirector -x` | Wave 0 |
| AID-03 | Encounter simulator produces EditorWindow with Monte Carlo stats | unit | `pytest tests/test_encounter_templates.py::TestEncounterSimulator -x` | Wave 0 |
| SHDR-04 | PrimeTween sequence generator produces Tween.*/Sequence.Create code | unit | `pytest tests/test_ux_templates.py::TestPrimeTweenSequence -x` | Wave 0 |
| ACC-01 | Accessibility generator produces colorblind shader + subtitle scaling + tags | unit | `pytest tests/test_ux_templates.py::TestAccessibility -x` | Wave 0 |
| PIPE-10 | TMP font asset generator produces CreateFontAsset editor script | unit | `pytest tests/test_ux_templates.py::TestTMPSetup -x` | Wave 0 |
| EQUIP-07 | Rarity VFX generator produces per-tier particle + glow config | unit | `pytest tests/test_ux_templates.py::TestRarityVFX -x` | Wave 0 |
| EQUIP-08 | Corruption VFX generator produces 0-100% material + particle progression | unit | `pytest tests/test_ux_templates.py::TestCorruptionVFX -x` | Wave 0 |
| VB-09 | Character select generator produces UI Toolkit screen with hero path | unit | `pytest tests/test_ux_templates.py::TestCharacterSelect -x` | Wave 0 |
| VB-10 | Boss AI generator produces multi-phase FSM + enrage + attack patterns | unit | `pytest tests/test_encounter_templates.py::TestBossAI -x` | Wave 0 |
| RPG-08 | World map generator produces heightmap-to-texture + fog-of-war | unit | `pytest tests/test_ux_templates.py::TestWorldMap -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/test_ux_templates.py tests/test_encounter_templates.py -x -q`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_ux_templates.py` -- covers UIX-01, UIX-02, UIX-03, UIX-04, SHDR-04, ACC-01, PIPE-10, EQUIP-07, EQUIP-08, VB-09, RPG-08
- [ ] `tests/test_encounter_templates.py` -- covers AID-01, AID-02, AID-03, VB-10

## Sources

### Primary (HIGH confidence)
- [PrimeTween GitHub README](https://github.com/KyryloKuzyk/PrimeTween/blob/main/README.md) - Complete API reference: Tween.*, Sequence.Create, Chain, Group, Shake, Punch, Custom
- [TextMeshPro Font Asset Creator docs](https://docs.unity3d.com/Packages/com.unity.textmeshpro@4.0/manual/FontAssetsCreator.html) - Font atlas generation settings
- [Unity Accessibility.VisionUtility API](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Accessibility.VisionUtility.GetColorBlindSafePalette.html) - Unity 6 built-in accessibility palette

### Secondary (MEDIUM confidence)
- [SOHNE/Colorblindness GitHub](https://github.com/SOHNE/Colorblindness) - URP/HDRP colorblind simulation approach via ChannelMixer
- [Colorblind simulation matrices gist](https://gist.github.com/Lokno/df7c3bfdc9ad32558bb7) - Protanopia/Deuteranopia/Tritanopia 3x3 matrices
- [ixora.io Color Blindness Simulation Research](https://ixora.io/projects/colorblindness/color-blindness-simulation-research/) - Brettel/Vienot method documentation
- [Multi-Phase Boss Encounter in Unity](https://medium.com/@scott.sourile/multi-phase-boss-encounter-in-unity-pt-2-implementation-134a20410719) - Boss FSM implementation pattern
- [DOTween vs LeanTween vs PrimeTween comparison](https://omitram.com/unity-tweening-guide-dotween-leantween-primetween/) - Performance and API comparison

### Tertiary (LOW confidence)
- WebSearch results for encounter scripting patterns -- general community patterns, verified against existing project spawn system code
- WebSearch results for 2D world map generation -- general heightmap-to-texture approach, needs validation against Unity 6 TerrainData API

### Project Source (HIGH confidence)
- VeilBreakers character select code at `Assets/Scripts/UI/CharacterSelect/` -- 18 C# files showing carousel, theme transition, embark flow pattern
- VeilBreakers BattleManager at `Assets/Scripts/Combat/BattleManager.cs` -- OnDamageDealt event, BattleState enum, brand/synergy integration
- Existing unity_server.py compound tool pattern -- 19 tools with action dispatch, _write_to_unity, JSON response
- Existing vfx_templates.py BRAND_VFX_CONFIGS -- Brand color/particle configuration dict pattern for EQUIP-07

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - PrimeTween confirmed in project, TMP built into Unity 6, all libraries verified
- Architecture: HIGH - Follows established compound tool + template generator pattern from 14 previous phases
- Pitfalls: HIGH - PrimeTween vs DOTween verified against project context, colorblind matrices verified from research literature
- Code examples: MEDIUM - PrimeTween API verified from official README, TMP API partially verified (CreateFontAsset overloads may vary)
- Encounter/boss patterns: MEDIUM - Based on standard Unity patterns, not project-specific verified code

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (30 days -- stable domain, well-established patterns)
