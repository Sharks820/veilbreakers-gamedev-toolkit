# Phase 12: Core Game Systems - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning
**Source:** Auto-generated (autonomous mode, recommended defaults)

<domain>
## Phase Boundary

Foundational game systems every Unity RPG needs: save/load persistence (JSON/binary serialization, save slots, data migration), health/damage system (HP component, damage numbers, death handling, respawn), character controller (first/third-person movement, camera follow), Input System configuration (action maps, control schemes, rebinding), settings menu (graphics quality, audio volume, keybindings, accessibility), HTTP/REST API utilities, VeilBreakers core combat systems (player combat controller, ability system, synergy engine, corruption gameplay, XP/leveling, currency, damage types), and interactable object framework.

Requirements: GAME-01, GAME-05, GAME-06, GAME-07, GAME-08, MEDIA-02, VB-01, VB-02, VB-03, VB-04, VB-05, VB-06, VB-07, RPG-03.

</domain>

<decisions>
## Implementation Decisions

### Save/Load System (GAME-01)
- **JSON serialization with encryption option**: Match VeilBreakers' existing SaveManager pattern (AES-CBC + GZip). Generate complementary save system that handles new game data types
- **3 manual + auto-save slots**: Match existing VeilBreakers save slot structure
- **Data migration framework**: Version-chained migrations matching existing MigrationRunner pattern

### Health/Damage System (GAME-05)
- **Component-based HP**: MonoBehaviour with current/max HP, damage/heal methods, death event, damage numbers
- **Integrate with VeilBreakers Combatant**: Generated health system should work alongside existing Combatant component, not replace it
- **Damage pipeline**: BasePower × (ATK/DEF) × BrandMult × SynergyMult × Variance × CritMult — matching existing DamageCalculator

### Character Controller (GAME-06)
- **Third-person primary**: Dark fantasy action RPG is third-person. First-person as option
- **Camera follow via Cinemachine**: Use Cinemachine FreeLook for third-person (Phase 14 will expand this)
- **Movement uses CharacterController**: Not Rigidbody-based, for consistent RPG movement

### Input System (GAME-07)
- **Unity Input System**: Match existing InputManager wrapper with GameAction enum
- **Generate InputActionAsset**: Create .inputactions file with action maps (Gameplay, UI, Menu)
- **Rebinding support**: Runtime rebinding with PlayerPrefs persistence

### Settings Menu (GAME-08)
- **UI Toolkit**: Match VeilBreakers' UI Toolkit approach (no legacy UGUI)
- **Categories**: Graphics (quality presets, resolution, fullscreen), Audio (master/sfx/music/voice volumes), Controls (keybinding display + rebind), Accessibility (subtitle size, colorblind mode)
- **Persistence via PlayerPrefs JSON**: Match existing VeilBreakers settings approach

### VeilBreakers Combat Systems (VB-01 through VB-07)
- **Player combat controller** (VB-01): Light/heavy attack, dodge, block, combo chains, hit reactions, i-frames, stamina
- **Ability system** (VB-02): Brand-specific ability slots, cooldowns, mana/stamina resource
- **Synergy engine** (VB-03): FULL/PARTIAL/NEUTRAL/ANTI tier evaluation — match existing SynergySystem
- **Corruption gameplay** (VB-04): Stat modifiers, ability mutations, threshold triggers at 25/50/75/100% — match existing CorruptionSystem
- **XP/Leveling** (VB-05): XP from kills/quests, level-up triggers, stat scaling per hero path
- **Currency system** (VB-06): Gold/souls/marks earning, spending, display
- **Damage types** (VB-07): 10 brand-specific damage types with resistance calculations — match existing BrandSystem

### HTTP/REST Utilities (MEDIA-02)
- **UnityWebRequest wrapper**: Type-safe GET/POST/PUT/DELETE with JSON serialization, error handling, retry logic

### Interactable Objects (RPG-03)
- **State machine for interactables**: Doors, chests, levers, switches with animations and sound
- **Interaction trigger**: Proximity-based with "Press E" prompt (Phase 15 will add the UI prompt)

### Claude's Discretion
- Exact combo chain implementation (number of hits, timing windows)
- I-frame duration and dodge distance
- Stamina regeneration rate and consumption values
- Currency display formatting
- HTTP retry count and timeout defaults
- Interactable state machine transition rules

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### VeilBreakers Game Project (complement, don't replace)
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Managers/SaveManager.cs` — Existing save system (complement)
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Combat/Combatant.cs` — Existing combat component
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Combat/DamageCalculator.cs` — Existing damage pipeline
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Systems/BrandSystem.cs` — 10-brand effectiveness matrix
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Systems/SynergySystem.cs` — Synergy tier evaluation
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Systems/CorruptionSystem.cs` — Corruption stat modifiers
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Core/InputManager.cs` — Existing Input System wrapper
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Core/EventBus.cs` — Event system for game-wide communication

### Toolkit Implementation
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_server.py` — Add unity_game compound tool
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/` — Template generators

### Requirements
- `.planning/REQUIREMENTS.md` — GAME-01, GAME-05, GAME-06, GAME-07, GAME-08, MEDIA-02, VB-01 through VB-07, RPG-03

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 10 `unity_code` tool: Generate MonoBehaviours, SO definitions, architecture patterns
- Phase 9 `unity_prefab`: Create prefabs with auto-wired components
- Phase 11 `unity_data`: ScriptableObject definitions and data authoring tools
- Existing game has SaveManager, Combatant, DamageCalculator, BrandSystem, SynergySystem, CorruptionSystem — toolkit generators should produce COMPATIBLE code

### Established Patterns
- VeilBreakers uses SingletonMonoBehaviour<T> for managers
- EventBus with 50+ static events for cross-system communication
- GameDatabase for JSON data loading
- UI Toolkit (UXML + USS) for all UI

### Integration Points
- New `unity_game` compound tool for core systems
- Generated code should use VeilBreakers namespaces
- Combat systems should integrate with existing EventBus events

</code_context>

<specifics>
## Specific Ideas

- Save system must be compatible with existing SaveManager's AES-CBC encryption and slot structure
- Health/damage should complement Combatant, not create a separate system
- All VB systems (combat, ability, synergy, corruption, XP, currency, damage types) already have pure-logic implementations in the game — the toolkit generates the BOILERPLATE code that wires these systems together
- Input System should generate .inputactions asset files, not just C# code
- Settings menu should use the dark fantasy theme (VeilBreakers.uss)

</specifics>

<deferred>
## Deferred Ideas

None — autonomous mode stayed within phase scope

</deferred>

---

*Phase: 12-core-game-systems*
*Context gathered: 2026-03-20 via autonomous mode*
