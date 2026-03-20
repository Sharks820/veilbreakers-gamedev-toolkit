# Phase 12: Core Game Systems - Research

**Researched:** 2026-03-20
**Domain:** Unity C# template generation for core game systems (save/load, health/damage, character controller, input, settings, VeilBreakers combat)
**Confidence:** HIGH

## Summary

Phase 12 adds a new `unity_game` compound MCP tool to the toolkit, containing template generators for every foundational game system an action RPG needs. Unlike most prior phases, this phase must generate C# code that is **compatible with existing VeilBreakers game code** -- the toolkit produces boilerplate/wiring code that complements (not replaces) SaveManager, Combatant, DamageCalculator, BrandSystem, SynergySystem, CorruptionSystem, and InputManager.

The scope is large (14 requirements) but follows an established pattern: Python template generators produce C# source strings, which are written to the Unity project and compiled via the existing two-step workflow. The existing game's architecture (SingletonMonoBehaviour, EventBus static events, VeilBreakers namespaces, UI Toolkit for UI) constrains all template design decisions. The VeilBreakers combat systems (VB-01 through VB-07) are the most complex part -- each generates a runtime MonoBehaviour or static utility class that integrates with the existing Combatant component, DamageCalculator pipeline, and EventBus events.

**Primary recommendation:** Create a new `game_templates.py` template module with 14+ generator functions, wire them into a `unity_game` compound tool in `unity_server.py`, and validate with pytest syntax tests following the established pattern from gameplay_templates.py.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Save/Load (GAME-01):** JSON serialization with AES-CBC encryption option, 3 manual + auto-save slots, version-chained migration framework -- must match existing SaveManager pattern
- **Health/Damage (GAME-05):** Component-based HP MonoBehaviour, integrates with existing Combatant (not replaces), damage pipeline: BasePower x (ATK/DEF) x BrandMult x SynergyMult x Variance x CritMult
- **Character Controller (GAME-06):** Third-person primary (first-person as option), Cinemachine FreeLook for camera, CharacterController component (not Rigidbody)
- **Input System (GAME-07):** Unity Input System, match existing InputManager wrapper with GameAction enum, generate .inputactions file, runtime rebinding with PlayerPrefs persistence
- **Settings Menu (GAME-08):** UI Toolkit (no UGUI), categories: Graphics/Audio/Controls/Accessibility, persistence via PlayerPrefs JSON
- **VB Combat Systems (VB-01 through VB-07):** Player combat controller with light/heavy/dodge/block/combo/i-frames/stamina, brand-specific ability system, synergy engine matching SynergySystem, corruption gameplay matching CorruptionSystem, XP/leveling, currency system, 10 brand damage types matching BrandSystem
- **HTTP/REST (MEDIA-02):** UnityWebRequest wrapper with type-safe GET/POST/PUT/DELETE, JSON serialization, error handling, retry logic
- **Interactable Objects (RPG-03):** State machine for doors/chests/levers/switches, proximity-based trigger with "Press E" prompt (UI prompt deferred to Phase 15)

### Claude's Discretion
- Exact combo chain implementation (number of hits, timing windows)
- I-frame duration and dodge distance
- Stamina regeneration rate and consumption values
- Currency display formatting
- HTTP retry count and timeout defaults
- Interactable state machine transition rules

### Deferred Ideas (OUT OF SCOPE)
None -- autonomous mode stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GAME-01 | Save/load system (JSON/binary, save slots, migration) | Complement existing SaveManager; generate SaveFileHandler-compatible serialization templates with AES-CBC + GZip pattern |
| GAME-05 | Health/damage system (HP component, damage numbers, death, respawn) | Generate HealthComponent MonoBehaviour that works alongside Combatant; reuse DamageCalculator pipeline |
| GAME-06 | Character controller (1st/3rd person, camera follow) | CharacterController.Move() with Cinemachine 3.x FreeLook (CinemachineCamera + OrbitalFollow + RotationComposer) |
| GAME-07 | Input System (InputActionAsset, action maps, rebinding) | Generate .inputactions JSON asset + C# wrapper matching GameAction enum; SaveBindingOverridesAsJson/LoadBindingOverridesFromJson for persistence |
| GAME-08 | Settings menu (graphics, audio, keybindings, accessibility) | UI Toolkit UXML + USS with dark_fantasy theme; SliderInt/DropdownField/Toggle elements; PlayerPrefs JSON persistence |
| MEDIA-02 | HTTP/REST API utilities | UnityWebRequest wrapper with Awaitable async (Unity 6); generic typed GET/POST/PUT/DELETE; retry with exponential backoff |
| VB-01 | Player combat controller | Light/heavy attack FSM, combo chains (3-hit light, 2-hit heavy), dodge with i-frames (0.2s), block with stamina drain, hit reactions |
| VB-02 | Ability system | Brand-specific ability slots matching AbilitySlot enum, cooldown timers, mana/stamina resource, ability activation per combat brand |
| VB-03 | Synergy engine | FULL/PARTIAL/NEUTRAL/ANTI tier evaluation reusing existing SynergySystem static methods; generate UI feedback wiring via EventBus |
| VB-04 | Corruption gameplay | Stat modifiers at 25/50/75/100% thresholds reusing existing CorruptionSystem; ability mutations; threshold triggers via EventBus |
| VB-05 | XP/Leveling system | XP gain from kills/quests, level-up triggers via EventBus.HeroLevelUp, stat scaling per hero Path |
| VB-06 | Currency system | Gold/souls/marks with multiple currency types, earning/spending/display, EventBus.CurrencyChanged integration |
| VB-07 | Damage types | 10 brand-specific damage types with resistance calculations reusing BrandSystem.GetEffectiveness() |
| RPG-03 | Interactable object framework | State machine for doors/chests/levers/switches, proximity trigger, animation/sound hooks |

</phase_requirements>

## Standard Stack

### Core (Unity / C# -- generated by templates)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Unity CharacterController | Built-in (Unity 6) | Player movement | Consistent RPG movement without physics jitter, user decision |
| Unity Input System | 1.11+ (com.unity.inputsystem) | Input handling | Modern input with rebinding, already used by VeilBreakers InputManager |
| Cinemachine | 3.1+ (com.unity.cinemachine) | Camera follow | CinemachineCamera + OrbitalFollow for third-person, user decision |
| UI Toolkit | Built-in (Unity 6) | Settings menu UI | UXML + USS, matches VeilBreakers' existing UI approach |
| UnityWebRequest | Built-in (UnityEngine.Networking) | HTTP/REST calls | Unity's standard networking API, no external dependencies |

### Toolkit (Python -- template generators)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FastMCP | 1.26+ | MCP server framework | All tool registration |
| pytest | 8.0+ | Template validation | C# syntax verification tests |

### No New Dependencies
This phase adds zero new Python or Unity package dependencies. All functionality uses Unity built-ins and existing VeilBreakers patterns.

## Architecture Patterns

### Recommended Project Structure (Template Generators)
```
Tools/mcp-toolkit/src/veilbreakers_mcp/
  shared/unity_templates/
    game_templates.py           # NEW: All 14+ game system generators
  unity_server.py               # ADD: unity_game compound tool (~15 actions)
Tools/mcp-toolkit/tests/
  test_game_templates.py        # NEW: Syntax + content validation tests
```

### Generated C# Output Structure
```
Assets/
  Scripts/Runtime/GameSystems/  # Runtime MonoBehaviours (NOT editor scripts)
    SaveSystem/                 # VB_SaveSystem.cs, VB_SaveMigration.cs
    Health/                     # VB_HealthComponent.cs, VB_DamageNumbers.cs
    Character/                  # VB_CharacterController.cs, VB_CameraSetup.cs
    Input/                      # VeilBreakersInput.inputactions (JSON), VB_InputConfig.cs
    Settings/                   # VB_SettingsMenu.cs + .uxml + .uss
    Combat/                     # VB_PlayerCombat.cs, VB_AbilitySystem.cs
    Progression/                # VB_XPSystem.cs, VB_CurrencySystem.cs
    Interaction/                # VB_Interactable.cs
    Network/                    # VB_HttpClient.cs
```

### Pattern 1: Template Generator Function
**What:** Each generator is a Python function returning a complete C# source string.
**When to use:** Every requirement gets one or more generator functions.
**Example:**
```python
# Source: Established pattern from gameplay_templates.py
def generate_save_system_script(
    slot_count: int = 3,
    use_encryption: bool = True,
    use_compression: bool = True,
) -> str:
    """Generate C# save/load system compatible with VeilBreakers SaveManager."""
    safe_slot_count = max(1, min(10, slot_count))
    lines = []
    lines.append("using System;")
    lines.append("using System.IO;")
    lines.append("using UnityEngine;")
    # ... build C# source via line concatenation
    return "\n".join(lines)
```

### Pattern 2: Complement, Don't Replace
**What:** Generated code uses existing VeilBreakers systems rather than reimplementing them.
**When to use:** All VB-specific generators (VB-01 through VB-07).
**Example:**
```csharp
// Generated combat controller USES existing DamageCalculator
using VeilBreakers.Combat;
using VeilBreakers.Systems;
using VeilBreakers.Core;

public class VB_PlayerCombat : MonoBehaviour
{
    private Combatant _combatant; // Uses existing component

    public void PerformAttack(Combatant target, int basePower)
    {
        var result = DamageCalculator.Calculate(
            _combatant, target, basePower,
            DamageType.PHYSICAL, _currentSynergyTier);
        target.TakeDamage(result.finalDamage, result.isCritical);
        EventBus.DamageDealt(_combatant.CombatantId, target.CombatantId,
            result.finalDamage, result.isCritical);
    }
}
```

### Pattern 3: Line-Based String Concatenation
**What:** Build C# source as a list of strings, joined with newline at the end.
**When to use:** All template generators (established Phase 11 decision).
**Why:** Avoids f-string/brace escaping nightmares with deeply nested C# code containing `{}` everywhere.
```python
lines = []
lines.append("public class Foo")
lines.append("{")
lines.append(f"    public int Value = {value};")
lines.append("}")
return "\n".join(lines)
```

### Pattern 4: Runtime Scripts (NOT Editor Scripts)
**What:** Game system templates generate runtime MonoBehaviours placed in `Assets/Scripts/Runtime/`, not `Assets/Editor/`.
**When to use:** All GAME/VB/RPG requirements. These scripts run in builds, not just the editor.
**Critical difference from most prior phases:** Prior phases generated editor scripts (Assets/Editor/Generated/) that run menu items. Game system scripts are runtime code that exists permanently in the project.

### Pattern 5: VeilBreakers Namespace Convention
**What:** Generated code uses VeilBreakers namespaces matching existing code.
**When to use:** All generated C# that integrates with existing game code.
```csharp
namespace VeilBreakers.GameSystems  // or VeilBreakers.Combat, etc.
{
    // Generated code
}
```

### Anti-Patterns to Avoid
- **Reimplementing existing systems:** Never generate a new DamageCalculator or BrandSystem. Use the existing static classes.
- **Editor namespace in runtime scripts:** Generated game scripts must NEVER `using UnityEditor;` -- they run in builds.
- **F-string templates with C# braces:** Always use line-based concatenation, not `f"class Foo {{ }}"` which is error-prone.
- **Hardcoding VeilBreakers enum values:** Reference the enums by name (Brand.IRON, not magic number 1), so generated code stays correct if enums change.
- **Replacing SingletonMonoBehaviour pattern:** Use it for manager classes, matching existing VeilBreakers convention.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Input rebind persistence | Custom serialization | `SaveBindingOverridesAsJson` / `LoadBindingOverridesFromJson` + PlayerPrefs | Unity Input System built-in, handles composite bindings correctly |
| Brand effectiveness | New lookup table | `BrandSystem.GetEffectiveness()` | Already implemented, tested, and handles hybrid brands |
| Synergy evaluation | New synergy calculator | `SynergySystem.GetSynergyTier()` / `GetDamageBonus()` | Already handles FULL/PARTIAL/NEUTRAL/ANTI with Path-specific strong/weak brands |
| Corruption modifiers | New modifier system | `CorruptionSystem.GetStatMultiplier()` / `GetCorruptionState()` | Already implements inverted corruption (lower = stronger) |
| Damage calculation | New formula | `DamageCalculator.Calculate()` | Full pipeline with brand/synergy/corruption/crit already built |
| Event communication | Custom event system | `EventBus.XxxEvent()` | 50+ static events already wired throughout game |
| Camera follow | Custom camera script | Cinemachine CinemachineCamera + OrbitalFollow | Professional camera system with collision avoidance, blending |
| Settings persistence | Custom file I/O | `PlayerPrefs` with JSON serialization | Simple, cross-platform, matches VeilBreakers existing approach |

**Key insight:** VeilBreakers already has pure-logic implementations of brand/synergy/corruption/damage systems. The toolkit generates the BOILERPLATE MonoBehaviour wiring that connects these systems to Unity GameObjects, Input, and UI -- not the game logic itself.

## Common Pitfalls

### Pitfall 1: Editor References in Runtime Scripts
**What goes wrong:** Generated C# files import `UnityEditor` namespace, causing build failures.
**Why it happens:** Prior phases generated editor scripts (Assets/Editor/); developers reuse patterns without checking.
**How to avoid:** Every runtime template generator must be validated in tests to NOT contain `using UnityEditor`. Add explicit test assertion: `assert "using UnityEditor" not in result`.
**Warning signs:** Tests pass locally but Unity build fails on device.

### Pitfall 2: Cinemachine 2.x vs 3.x API Confusion
**What goes wrong:** Generated code references `CinemachineFreeLook` (Cinemachine 2.x class that no longer exists in 3.x).
**Why it happens:** Training data and older tutorials reference Cinemachine 2.x API.
**How to avoid:** Use Cinemachine 3.x API: `CinemachineCamera` with `CinemachineOrbitalFollow` and `CinemachineRotationComposer` components. The `CinemachineFreeLook` class was replaced.
**Warning signs:** Compile errors referencing missing types.

### Pitfall 3: C# Brace Escaping in Python F-Strings
**What goes wrong:** F-strings with C# code produce `KeyError` or malformed output because `{` and `}` are Python format specifiers.
**Why it happens:** C# is heavily brace-laden; every class/method/if/switch uses braces.
**How to avoid:** Use line-based string concatenation (established Phase 11 decision). Build `lines = []`, append each line, `"\n".join(lines)`.
**Warning signs:** `KeyError` exceptions, `{{` literal braces appearing in generated code.

### Pitfall 4: InputActionAsset JSON Format
**What goes wrong:** Generated .inputactions file has wrong JSON structure, Unity can't parse it.
**Why it happens:** InputActionAsset has a specific JSON schema with maps, actions, bindings arrays, and composite binding parts.
**How to avoid:** Use the exact JSON structure Unity expects: top-level `maps` array, each containing `actions` array and `bindings` array with `id`, `path`, `interactions`, `processors`, `groups`, `action`, `isComposite`, `isPartOfComposite` fields.
**Warning signs:** "Failed to deserialize InputActionAsset" errors in Unity console.

### Pitfall 5: Missing EventBus Integration
**What goes wrong:** Generated systems work in isolation but don't communicate with existing VeilBreakers systems.
**Why it happens:** Generator only considers the system being generated, not its integration points.
**How to avoid:** Every generated system that changes game state must fire appropriate EventBus events (e.g., `EventBus.DamageDealt()`, `EventBus.HeroLevelUp()`, `EventBus.CurrencyChanged()`).
**Warning signs:** Other game systems don't react to generated system's state changes.

### Pitfall 6: Stamina/Resource Consumption Without Regeneration
**What goes wrong:** Combat controller consumes stamina for dodge/block/attack but has no regeneration, making character unusable after a few actions.
**Why it happens:** Focus on consumption mechanics, forget recovery.
**How to avoid:** Always pair resource consumption with regeneration: stamina regens passively (e.g., 15/sec when not attacking), mana regens slowly or via items.
**Warning signs:** Player runs out of stamina in first combat encounter.

### Pitfall 7: Save System Compatibility
**What goes wrong:** Generated save system uses different serialization format than existing SaveManager, creating two incompatible save systems.
**Why it happens:** Generator creates standalone save system instead of complementing existing one.
**How to avoid:** Generated code should extend SaveData (add new fields) and use SaveFileHandler patterns (AES-CBC, GZip, atomic writes, backup rotation). The save system generator produces data classes that SaveManager already knows how to serialize.
**Warning signs:** Two save files per slot, or save corruption when mixing old/new saves.

## Code Examples

### Save System Data Extension (Complement Pattern)
```csharp
// Generated code extends existing SaveData pattern
using System;
using System.Collections.Generic;
using VeilBreakers.Data;

namespace VeilBreakers.GameSystems
{
    /// <summary>
    /// Extension data for new game systems, stored within SaveData.
    /// Generated by VeilBreakers MCP toolkit.
    /// </summary>
    [Serializable]
    public class GameSystemsSaveData
    {
        // Currency
        public int gold;
        public int souls;
        public int marks;

        // XP / Leveling
        public int totalXp;
        public int currentLevel;

        // Interactable states (door opened, chest looted, etc.)
        public List<InteractableState> interactableStates = new List<InteractableState>();
    }

    [Serializable]
    public class InteractableState
    {
        public string interactableId;
        public int stateIndex;
    }
}
```

### Character Controller Template Output
```csharp
// Source: Unity CharacterController docs + VeilBreakers patterns
using UnityEngine;
using VeilBreakers.Core;

namespace VeilBreakers.GameSystems
{
    /// <summary>
    /// Third-person character controller using CharacterController component.
    /// Generated by VeilBreakers MCP toolkit.
    /// </summary>
    [RequireComponent(typeof(CharacterController))]
    public class VB_CharacterController : MonoBehaviour
    {
        [Header("Movement")]
        [SerializeField] private float _moveSpeed = 5f;
        [SerializeField] private float _sprintMultiplier = 1.5f;
        [SerializeField] private float _rotationSpeed = 10f;
        [SerializeField] private float _gravity = -20f;
        [SerializeField] private float _jumpHeight = 1.5f;

        private CharacterController _controller;
        private Vector3 _velocity;
        private bool _isGrounded;
        private Transform _cameraTransform;

        private void Start()
        {
            _controller = GetComponent<CharacterController>();
            _cameraTransform = Camera.main.transform;
        }

        private void Update()
        {
            _isGrounded = _controller.isGrounded;
            if (_isGrounded && _velocity.y < 0)
                _velocity.y = -2f;

            // Input via InputManager
            Vector2 input = GetMovementInput();
            Vector3 move = _cameraTransform.right * input.x +
                          _cameraTransform.forward * input.y;
            move.y = 0f;
            move.Normalize();

            _controller.Move(move * _moveSpeed * Time.deltaTime);

            // Gravity
            _velocity.y += _gravity * Time.deltaTime;
            _controller.Move(_velocity * Time.deltaTime);

            // Rotate to face movement direction
            if (move.sqrMagnitude > 0.01f)
            {
                Quaternion targetRotation = Quaternion.LookRotation(move);
                transform.rotation = Quaternion.Slerp(
                    transform.rotation, targetRotation,
                    _rotationSpeed * Time.deltaTime);
            }
        }

        private Vector2 GetMovementInput()
        {
            // Placeholder -- actual implementation reads from InputManager
            return Vector2.zero;
        }
    }
}
```

### InputActionAsset JSON Structure
```json
{
    "name": "VeilBreakersInput",
    "maps": [
        {
            "name": "Gameplay",
            "id": "unique-guid-here",
            "actions": [
                {
                    "name": "Move",
                    "type": "Value",
                    "id": "unique-guid",
                    "expectedControlType": "Vector2",
                    "processors": "",
                    "interactions": "",
                    "initialStateCheck": true
                },
                {
                    "name": "LightAttack",
                    "type": "Button",
                    "id": "unique-guid",
                    "expectedControlType": "Button",
                    "processors": "",
                    "interactions": ""
                }
            ],
            "bindings": [
                {
                    "name": "WASD",
                    "id": "unique-guid",
                    "path": "",
                    "interactions": "",
                    "processors": "",
                    "groups": "",
                    "action": "Move",
                    "isComposite": true,
                    "isPartOfComposite": false
                },
                {
                    "name": "up",
                    "id": "unique-guid",
                    "path": "<Keyboard>/w",
                    "interactions": "",
                    "processors": "",
                    "groups": "Keyboard",
                    "action": "Move",
                    "isComposite": false,
                    "isPartOfComposite": true
                }
            ]
        },
        {
            "name": "UI",
            "id": "unique-guid",
            "actions": [],
            "bindings": []
        }
    ],
    "controlSchemes": [
        {
            "name": "Keyboard",
            "bindingGroup": "Keyboard",
            "devices": [
                { "devicePath": "<Keyboard>", "isOptional": false },
                { "devicePath": "<Mouse>", "isOptional": false }
            ]
        },
        {
            "name": "Gamepad",
            "bindingGroup": "Gamepad",
            "devices": [
                { "devicePath": "<Gamepad>", "isOptional": false }
            ]
        }
    ]
}
```

### Interactable State Machine Pattern
```csharp
// Source: RPG-03 requirement + VeilBreakers patterns
using UnityEngine;
using UnityEngine.Events;

namespace VeilBreakers.GameSystems
{
    public class VB_Interactable : MonoBehaviour
    {
        public enum InteractableType { Door, Chest, Lever, Switch }
        public enum InteractState { Idle, Interacting, Open, Closed, Locked }

        [SerializeField] private InteractableType _type;
        [SerializeField] private InteractState _currentState = InteractState.Idle;
        [SerializeField] private float _interactionRadius = 2f;
        [SerializeField] private string _interactableId;
        [SerializeField] private bool _requiresKey;
        [SerializeField] private string _requiredKeyId;

        [Header("Events")]
        public UnityEvent OnInteract;
        public UnityEvent OnStateChanged;

        private bool _playerInRange;

        public InteractState CurrentState => _currentState;
        public bool CanInteract => _playerInRange && _currentState != InteractState.Locked;

        public void Interact()
        {
            if (!CanInteract) return;

            _currentState = _type switch
            {
                InteractableType.Door => _currentState == InteractState.Open
                    ? InteractState.Closed : InteractState.Open,
                InteractableType.Chest => InteractState.Open,
                InteractableType.Lever => _currentState == InteractState.Idle
                    ? InteractState.Open : InteractState.Idle,
                InteractableType.Switch => _currentState == InteractState.Idle
                    ? InteractState.Open : InteractState.Idle,
                _ => _currentState
            };

            OnInteract?.Invoke();
            OnStateChanged?.Invoke();
        }
    }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| CinemachineFreeLook (separate class) | CinemachineCamera + OrbitalFollow + RotationComposer | Cinemachine 3.0 (2023) | FreeLook is now a composition of behaviors on CinemachineCamera, not a separate MonoBehaviour |
| Input System rebind via custom serialization | SaveBindingOverridesAsJson / LoadBindingOverridesFromJson | Input System 1.4+ | Built-in JSON serialization for rebinds, use with PlayerPrefs |
| UGUI for settings menus | UI Toolkit (UXML + USS) | Unity 2021+ | VeilBreakers already uses UI Toolkit; all new UI must use it |
| Coroutine-based UnityWebRequest | Awaitable async (Unity 6) or custom awaiter | Unity 6 (2024) | Unity 6 supports Awaitable natively; can use `await request.SendWebRequest()` patterns |
| MonoBehaviour.Update() input polling | InputAction.performed callbacks | Input System 1.0+ | Event-driven input is more efficient than polling every frame |

**Deprecated/outdated:**
- `CinemachineFreeLook` class: Replaced by `CinemachineCamera` with `CinemachineOrbitalFollow` in Cinemachine 3.x
- `UnityEngine.Input` (old input): Replaced by Input System package; VeilBreakers already uses new Input System
- UGUI (`UnityEngine.UI`): VeilBreakers uses UI Toolkit exclusively for new UI

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | `Tools/mcp-toolkit/pyproject.toml` (testpaths = ["tests"]) |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_game_templates.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GAME-01 | Save system template generates valid C# with slots, encryption, migration | unit | `pytest tests/test_game_templates.py::TestSaveSystemTemplate -x` | Wave 0 |
| GAME-05 | Health/damage template generates HP component compatible with Combatant | unit | `pytest tests/test_game_templates.py::TestHealthDamageTemplate -x` | Wave 0 |
| GAME-06 | Character controller template generates CharacterController-based movement | unit | `pytest tests/test_game_templates.py::TestCharacterControllerTemplate -x` | Wave 0 |
| GAME-07 | Input config template generates valid .inputactions JSON + C# wrapper | unit | `pytest tests/test_game_templates.py::TestInputSystemTemplate -x` | Wave 0 |
| GAME-08 | Settings menu template generates UXML + USS + C# controller | unit | `pytest tests/test_game_templates.py::TestSettingsMenuTemplate -x` | Wave 0 |
| MEDIA-02 | HTTP client template generates UnityWebRequest wrapper with retry | unit | `pytest tests/test_game_templates.py::TestHttpClientTemplate -x` | Wave 0 |
| VB-01 | Combat controller template generates light/heavy/dodge/block/combo FSM | unit | `pytest tests/test_game_templates.py::TestPlayerCombatTemplate -x` | Wave 0 |
| VB-02 | Ability system template generates brand-specific ability slots | unit | `pytest tests/test_game_templates.py::TestAbilitySystemTemplate -x` | Wave 0 |
| VB-03 | Synergy engine template generates tier evaluation using SynergySystem | unit | `pytest tests/test_game_templates.py::TestSynergyEngineTemplate -x` | Wave 0 |
| VB-04 | Corruption gameplay template generates threshold triggers using CorruptionSystem | unit | `pytest tests/test_game_templates.py::TestCorruptionGameplayTemplate -x` | Wave 0 |
| VB-05 | XP/leveling template generates level-up with EventBus integration | unit | `pytest tests/test_game_templates.py::TestXPLevelingTemplate -x` | Wave 0 |
| VB-06 | Currency system template generates multi-currency with EventBus | unit | `pytest tests/test_game_templates.py::TestCurrencySystemTemplate -x` | Wave 0 |
| VB-07 | Damage type template generates brand-specific resistance calculations | unit | `pytest tests/test_game_templates.py::TestDamageTypeTemplate -x` | Wave 0 |
| RPG-03 | Interactable template generates state machine with proximity trigger | unit | `pytest tests/test_game_templates.py::TestInteractableTemplate -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/test_game_templates.py -x -q`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest -x -q`
- **Phase gate:** Full suite green (3,737+ existing tests + new tests) before verification

### Wave 0 Gaps
- [ ] `tests/test_game_templates.py` -- covers all GAME/VB/RPG/MEDIA template generators
- [ ] Framework install: None needed -- pytest already configured and working (3,737 tests collected)

## Open Questions

1. **Unity 6 Awaitable for UnityWebRequest**
   - What we know: Unity 6 supports `Awaitable` for async operations natively. UnityWebRequest traditionally uses coroutines or custom awaiters.
   - What's unclear: Whether generated code should use `Awaitable` (Unity 6 only) or the traditional coroutine pattern (broader compatibility).
   - Recommendation: Generate Awaitable-based async code since VeilBreakers targets Unity 6. Include a `_useCoroutines` option for fallback.

2. **InputActionAsset as JSON vs C# generation**
   - What we know: .inputactions files are JSON that Unity deserializes. VeilBreakers already has a VeilBreakersInputActions generated C# class.
   - What's unclear: Whether the toolkit should generate the JSON .inputactions file or a C# script that creates InputActionAssets programmatically.
   - Recommendation: Generate the JSON .inputactions file directly (simpler, Unity-standard approach). The auto-generated C# wrapper class is created by Unity's code generation from the .inputactions file.

3. **Runtime vs Editor script split for settings menu**
   - What we know: Settings menu needs runtime UXML/USS/C# (runs in builds) but also needs an editor script to create the initial assets.
   - What's unclear: Whether to generate a single runtime script that loads UXML at runtime, or an editor script that creates the UXML asset.
   - Recommendation: Generate the UXML string content and write it as a .uxml asset file; generate USS as a .uss file; generate a runtime C# MonoBehaviour that loads and binds them. No editor script needed -- toolkit writes files directly.

## Sources

### Primary (HIGH confidence)
- Existing VeilBreakers source code: SaveManager.cs, Combatant.cs, DamageCalculator.cs, BrandSystem.cs, SynergySystem.cs, CorruptionSystem.cs, InputManager.cs, EventBus.cs, Enums.cs, SaveData.cs -- directly read and analyzed
- Existing toolkit source code: unity_server.py (5,821 lines, 15 compound tools), gameplay_templates.py, conftest.py -- directly read and analyzed
- Unity Input System docs: [ActionBindings.md](https://github.com/Unity-Technologies/InputSystem/blob/develop/Packages/com.unity.inputsystem/Documentation~/ActionBindings.md) -- rebinding API
- Unity Input System tutorials: [Video Tutorial Series](https://unity.com/resources/input-system-video-tutorial-series)

### Secondary (MEDIUM confidence)
- Cinemachine 3.1 docs: [ThirdPersonCameras](https://docs.unity3d.com/Packages/com.unity.cinemachine@3.1/manual/ThirdPersonCameras.html), [FreeLookCameras](https://docs.unity3d.com/Packages/com.unity.cinemachine@3.1/manual/FreeLookCameras.html) -- CinemachineCamera + OrbitalFollow pattern
- Unity CharacterController docs: [CharacterController.Move](https://docs.unity3d.com/ScriptReference/CharacterController.Move.html) -- movement API reference
- Unity UI Toolkit docs: [UI Toolkit manual](https://docs.unity3d.com/Manual/UIElements.html) -- UXML/USS authoring

### Tertiary (LOW confidence)
- Unity 6 Awaitable for UnityWebRequest: Multiple community sources mention it but official documentation confirmation pending

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using Unity built-ins and existing VeilBreakers patterns, all verified by reading source code
- Architecture: HIGH - Follows established compound tool pattern from 11 prior phases, directly observed in codebase
- Pitfalls: HIGH - Identified from direct source code analysis (Cinemachine 3.x vs 2.x, brace escaping, editor vs runtime)
- VeilBreakers integration: HIGH - All existing game systems (SaveManager, Combatant, DamageCalculator, BrandSystem, SynergySystem, CorruptionSystem, InputManager, EventBus) directly read and understood
- InputActionAsset JSON format: MEDIUM - Based on GitHub docs + community examples, not fully verified with Unity 6 schema

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (30 days -- stable Unity APIs, locked project decisions)
