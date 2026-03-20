# Phase 15: Game UX & Encounter Design - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning
**Source:** Auto-generated (autonomous mode)

<domain>
## Phase Boundary

Polished gameplay UX elements and scripted encounter systems: minimap/compass with world markers, tutorial/onboarding sequences with tooltip overlays, floating damage numbers, context-sensitive interaction prompts, encounter scripting (triggers, waves, conditions, AI director), threat escalation / dynamic difficulty adjustment, encounter simulation for balance testing, DOTween/LeanTween animation sequences for UI polish, accessibility features (colorblind modes, subtitle sizing, screen reader tags, motor accessibility), TextMeshPro setup (font assets, TMP components, rich text, font fallbacks), equipment rarity visual effects (Common→Legendary glow + particles), equipment corruption visual progression (0-100%), character creation/selection screen, boss AI behavior (multi-phase, enrage), and 2D world map from 3D terrain data.

Requirements: UIX-01, UIX-02, UIX-03, UIX-04, AID-01, AID-02, AID-03, SHDR-04, ACC-01, PIPE-10, EQUIP-07, EQUIP-08, VB-09, VB-10, RPG-08.

</domain>

<decisions>
## Implementation Decisions

### Game UX (UIX-01 through UIX-04)
- **Minimap/compass** (UIX-01): Render texture minimap that EXACTLY emulates the actual game maps — every movement, every area must be 1:1 accurate with the 3D world. Uses orthographic camera render texture from actual scene geometry (not a static image). World-space markers for POIs, rotatable compass, configurable zoom. Player position must match exactly between minimap and 3D world at all times. No approximations or AI-generated map art — the minimap IS the game world viewed from above
- **Tutorial/onboarding** (UIX-02): Step-based tutorial system with tooltip overlays, highlight rects, action triggers
- **Damage numbers** (UIX-03): Floating text with PrimeTween animation, color-coded by damage type/brand, crit scaling
- **Interaction prompts** (UIX-04): Context-sensitive "Press E" with dynamic key rebind display, proximity triggers

### Encounter Design (AID-01 through AID-03)
- **Encounter scripting** (AID-01): Trigger volumes, wave definitions, spawn conditions, victory/defeat callbacks
- **AI director / DDA** (AID-02): Track player performance (deaths, time, damage taken), adjust spawn rates/enemy stats dynamically
- **Encounter simulation** (AID-03): Run N encounters, report win rate, average duration, DPS stats — EditorWindow tool

### UI Polish (SHDR-04)
- **DOTween sequences**: Generate tween animation sequences for UI elements (fade, scale, move, rotate, punch, shake)
- **PrimeTween integration**: VeilBreakers already uses PrimeTween — generate sequences using PrimeTween API, not DOTween

### Accessibility (ACC-01)
- **Colorblind modes**: Deuteranopia, protanopia, tritanopia filters via post-processing
- **Subtitle sizing**: Configurable text scale with minimum readable size
- **Screen reader tags**: ARIA-like accessibility labels on UI elements
- **Motor accessibility**: Adjustable input timing, toggle vs hold options

### TextMeshPro (PIPE-10)
- **Font asset creation**: Generate TMP font assets from TTF/OTF sources
- **TMP component setup**: Configure TextMeshProUGUI components with rich text, font fallback chains
- **VeilBreakers uses Cinzel font**: Dark fantasy theme font for UI

### Equipment Visuals (EQUIP-07, EQUIP-08)
- **Rarity tiers** (EQUIP-07): Common (gray), Uncommon (green), Rare (blue), Epic (purple), Legendary (gold glow + particles)
- **Corruption progression** (EQUIP-08): 0-100% with increasing vein patterns, color shift, particle emission

### VeilBreakers Screens (VB-09, VB-10)
- **Character creation/selection** (VB-09): Choose hero path, customize appearance, name entry — UI Toolkit
- **Boss AI** (VB-10): Multi-phase state machine, HP threshold transitions, unique attack patterns, enrage timer

### World Map (RPG-08)
- **2D world map from 3D terrain**: Generate 2D map texture from heightmap data, fog-of-war, location markers, player position

### Claude's Discretion
- Minimap render texture resolution and update frequency (must be high enough for 1:1 accuracy)
- Tutorial step transition animations
- Damage number float height and duration
- AI director difficulty adjustment curves
- Accessibility filter shader implementation
- TMP font atlas resolution and character sets
- Rarity particle density and glow intensity
- Boss enrage timer duration and stat multipliers

</decisions>

<canonical_refs>
## Canonical References

### VeilBreakers Game Project
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/UI/CharacterSelect/` — Existing character select (VB-09 extends this pattern)
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Combat/BattleManager.cs` — Combat orchestration for encounter integration

### Toolkit Implementation
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_server.py` — Add unity_ux compound tool
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/` — Template generators

### Requirements
- `.planning/REQUIREMENTS.md`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 12 `unity_game`: Game system template pattern (extend for encounter systems)
- Phase 14 `unity_camera`: Camera shake already implemented (reuse for damage feedback)
- Phase 10 `unity_code`: Custom editor window generation (for encounter simulator)
- Phase 7 `unity_vfx`: Particle VFX (extend for rarity/corruption effects)
- VeilBreakers uses PrimeTween (not DOTween) — SHDR-04 must use PrimeTween API

### Integration Points
- New `unity_ux` compound tool for UX elements
- Extend `unity_gameplay` for encounter scripting/AI director
- Equipment visuals extend Phase 7 VFX tools
- Boss AI extends Phase 8 mob AI patterns

</code_context>

<specifics>
## Specific Ideas

- VeilBreakers already has AAA character select screen — VB-09 toolkit generates the BOILERPLATE, user customizes visually
- PrimeTween is already installed via OpenUPM — DOTween sequences should use PrimeTween's Tween.* API
- 10 combat brands each need distinct rarity glow colors matching their brand identity
- Boss AI should support VeilBreakers' multi-phase corruption bosses (corruption increases per phase)

</specifics>

<deferred>
## Deferred Ideas

None — autonomous mode stayed within phase scope

</deferred>

---

*Phase: 15-game-ux-encounter-design*
*Context gathered: 2026-03-20 via autonomous mode*
