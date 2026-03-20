# Phase 13: Content & Progression Systems - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning
**Source:** Auto-generated (autonomous mode)

<domain>
## Phase Boundary

Higher-level game systems driving player engagement: inventory system (item database SO, UI slots, drag-and-drop, equipment, storage), dialogue system (branching trees, dialogue UI, NPC interaction, YarnSpinner-compatible), quest system (objectives, tracking, quest givers, quest log UI, completion rewards), loot table system (weighted random, rarity tiers, drop conditions), crafting/recipe system (ingredients, crafting stations, unlock progression), skill tree/talent system (node graph, dependencies, point allocation), combat balancing tools (DPS calculator, encounter simulator, stat curve editor), weapon mesh generation (swords/axes/maces/staffs with grip points), modular character meshes (head/torso/arms/legs for armor swapping), armor fitting (shape keys + weight transfer), equipment preview icons, Unity equipment attachment (SkinnedMeshRenderer rebinding, bone sockets), brand-specific loot affinity, shop/merchant system, and journal/codex/bestiary.

Requirements: GAME-02, GAME-03, GAME-04, GAME-09, GAME-10, GAME-11, GAME-12, EQUIP-01, EQUIP-03, EQUIP-04, EQUIP-05, EQUIP-06, VB-08, RPG-01, RPG-05.

</domain>

<decisions>
## Implementation Decisions

### Inventory System (GAME-02)
- **ScriptableObject item database**: Items defined as SO assets with categories, stats, icons, rarity
- **UI Toolkit slots**: Grid-based inventory UI with drag-and-drop via UI Toolkit
- **Equipment slots**: Head, torso, arms, legs, weapon, shield, accessory x2
- **Storage containers**: Chests/stash with separate inventory grids

### Dialogue System (GAME-03)
- **YarnSpinner-compatible format**: Generate dialogue trees in Yarn format for compatibility
- **Branching with conditions**: Dialogue choices can check quest state, inventory, reputation
- **Dialogue UI generation**: Speaker portrait, text area, choice buttons via UI Toolkit

### Quest System (GAME-04)
- **Objective-based tracking**: Kill X, collect Y, talk to Z, reach location
- **Quest state machine**: NotStarted → Active → Complete → TurnedIn
- **Quest log UI**: Categorized (main/side/daily) with tracking markers
- **Reward distribution**: XP, gold, items on completion

### Loot/Crafting/Skills (GAME-09, GAME-10, GAME-11)
- **Weighted loot tables**: Rarity tiers (Common/Uncommon/Rare/Epic/Legendary) with weighted random
- **Recipe-based crafting**: Ingredient lists, crafting station requirement, unlock via progression
- **Node-graph skill tree**: Visual node layout with dependency edges, point allocation per level

### Combat Balancing (GAME-12)
- **DPS calculator**: Input stats, output DPS with brand/synergy modifiers
- **Encounter simulator**: Run N encounters, report win rate, average duration, damage taken
- **Stat curve editor**: Level scaling curves for HP, ATK, DEF per enemy type

### Equipment Systems (EQUIP-01, 03, 04, 05, 06)
- **Weapon generation** (EQUIP-01): Mesh from description (Blender), grip points, trail VFX attachment, collision mesh
- **Modular character** (EQUIP-03): Split mesh into swappable parts
- **Armor fitting** (EQUIP-04): Shape keys + vertex weight transfer for fitted armor
- **Preview icons** (EQUIP-05): 3D rendered equipment icons for inventory UI
- **Unity attachment** (EQUIP-06): SkinnedMeshRenderer rebinding, bone socket parenting

### VeilBreakers-Specific (VB-08, RPG-01, RPG-05)
- **Brand loot affinity** (VB-08): IRON brand mobs drop IRON-themed gear
- **Shop/merchant** (RPG-01): Buy/sell UI, price display, equipment stat comparison
- **Journal/codex/bestiary** (RPG-05): Lore entries, monster compendium, item encyclopedia

### Claude's Discretion
- Exact inventory grid sizes and slot counts
- Dialogue UI layout specifics
- Quest objective tracking implementation details
- Loot table probability calculations
- Crafting station types and unlock hierarchy
- Skill tree node positioning algorithm
- DPS formula presentation format
- Equipment attachment bone remapping details

</decisions>

<canonical_refs>
## Canonical References

### VeilBreakers Game Project
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Resources/Data/items.json` — Existing item data
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Resources/Data/monsters.json` — Monster data for loot tables
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Systems/BrandSystem.cs` — Brand affinity source

### Toolkit Implementation
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_server.py` — Add unity_content compound tool
- `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py` — Weapon/armor mesh generation

### Requirements
- `.planning/REQUIREMENTS.md`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 10 `unity_code`: Generate SO classes, custom editors
- Phase 11 `unity_data`: SO asset creation, data authoring windows
- Phase 12 `unity_game`: Game system templates pattern
- Phase 9 `unity_prefab`: Bone socket attachment, auto-wire profiles
- Blender `blender_mesh`: Mesh generation, retopo for weapon meshes
- Blender `blender_rig`: Bone sockets for equipment attachment

### Integration Points
- New `unity_content` compound tool
- Extend `blender_mesh` or `asset_pipeline` for weapon/armor generation
- Equipment attachment extends Phase 9 bone socket system

</code_context>

<specifics>
## Specific Ideas

- VeilBreakers has 60+ monsters with brands — loot affinity should map brand → gear drop rates
- 10 combat brands (IRON, SAVAGE, SURGE, VENOM, DREAD, LEECH, GRACE, MEND, RUIN, VOID)
- 4 hero paths (IRONBOUND, FANGBORN, VOIDTOUCHED, UNCHAINED) affect skill tree layout
- Existing item data in JSON should be importable into SO-based inventory system
- Corruption affects loot quality — higher corruption = better drops but more cursed items

</specifics>

<deferred>
## Deferred Ideas

None — autonomous mode stayed within phase scope

</deferred>

---

*Phase: 13-content-progression-systems*
*Context gathered: 2026-03-20 via autonomous mode*
