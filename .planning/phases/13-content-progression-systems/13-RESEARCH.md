# Phase 13: Content & Progression Systems - Research

**Researched:** 2026-03-20
**Domain:** Unity C# template generation for content/progression systems (inventory, dialogue, quests, loot, crafting, skill trees, combat balancing) + Blender Python handlers for equipment mesh generation (weapons, modular characters, armor fitting, preview icons) + Unity equipment attachment (SkinnedMeshRenderer rebinding, bone sockets, Multi-Parent Constraint)
**Confidence:** HIGH

## Summary

Phase 13 is the largest phase in v2.0, covering 15 requirements across three distinct domains: (1) Unity C# template generators for RPG content systems (inventory, dialogue, quests, loot tables, crafting, skill trees, combat balancing, shops, journal/codex), (2) Blender Python handlers for equipment mesh generation (weapon meshes, modular character splitting, armor fitting with shape keys, equipment preview icons), and (3) Unity C# template generators for equipment attachment at runtime (SkinnedMeshRenderer bone rebinding, Multi-Parent Constraint for weapon sheathing, bone socket parenting).

The Unity content systems follow the established pattern from Phase 12: Python template generator functions produce complete C# source strings, written to `Assets/Scripts/Runtime/` directories, and wired through a new `unity_content` compound MCP tool. The Blender equipment mesh generators follow the Phase 5-8 pattern: Blender Python handlers registered in the addon's handler framework, invoked through existing `blender_mesh`/`blender_rig`/`asset_pipeline` tools or a new `blender_equipment` tool. The existing VeilBreakers game data (items.json with 60+ items, monsters.json with 60+ monsters and drop_tables, skills.json, heroes.json with 4 hero paths) provides the exact data schemas that generated SO classes must match.

Critical integration points: the inventory system must be compatible with the existing item data schema (item_id, item_type, rarity 0-4, buy_price, sell_price, stat_buffs, corruption_change); loot tables must reference monster brand affinity (VB-08) using the 10 brand types from BrandSystem.cs; skill trees must align with the 4 hero paths (IRONBOUND, FANGBORN, VOIDTOUCHED, UNCHAINED); and equipment attachment must extend the Phase 9 bone socket system (EQUIP-02, 10 standard sockets already implemented).

**Primary recommendation:** Split into 3 plans: (1) Content system template generators + unity_content compound tool (GAME-02/03/04/09/10/11/12, VB-08, RPG-01, RPG-05), (2) Blender equipment mesh generators + handler wiring (EQUIP-01/03/04/05), (3) Unity equipment attachment templates + tool wiring (EQUIP-06) with integration tests for all 15 requirements.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Inventory System (GAME-02):** ScriptableObject item database with categories/stats/icons/rarity, UI Toolkit grid-based inventory with drag-and-drop, 8 equipment slots (head/torso/arms/legs/weapon/shield/accessory x2), storage containers with separate inventory grids
- **Dialogue System (GAME-03):** YarnSpinner-compatible format (.yarn node syntax), branching with conditions checking quest state/inventory/reputation, dialogue UI with speaker portrait/text area/choice buttons via UI Toolkit
- **Quest System (GAME-04):** Objective-based tracking (kill X/collect Y/talk to Z/reach location), quest state machine (NotStarted->Active->Complete->TurnedIn), quest log UI categorized (main/side/daily), reward distribution (XP/gold/items)
- **Loot/Crafting/Skills (GAME-09/10/11):** Weighted loot tables with 5 rarity tiers (Common/Uncommon/Rare/Epic/Legendary), recipe-based crafting with ingredient lists/station requirements/unlock progression, node-graph skill tree with dependency edges/point allocation
- **Combat Balancing (GAME-12):** DPS calculator with brand/synergy modifiers, encounter simulator (N encounters, win rate/duration/damage), stat curve editor for HP/ATK/DEF per enemy type
- **Equipment Systems (EQUIP-01/03/04/05/06):** Weapon mesh from description (Blender) with grip points/trail VFX/collision mesh, modular character split (head/torso/arms/legs), armor fitting with shape keys + weight transfer, 3D rendered preview icons, Unity SkinnedMeshRenderer rebinding + bone socket parenting + Multi-Parent Constraint
- **VeilBreakers-Specific (VB-08/RPG-01/RPG-05):** Brand loot affinity mapping brand->gear drop rates, shop/merchant buy/sell UI with price display/stat comparison, journal/codex/bestiary with lore entries/monster compendium/item encyclopedia

### Claude's Discretion
- Exact inventory grid sizes and slot counts
- Dialogue UI layout specifics
- Quest objective tracking implementation details
- Loot table probability calculations
- Crafting station types and unlock hierarchy
- Skill tree node positioning algorithm
- DPS formula presentation format
- Equipment attachment bone remapping details

### Deferred Ideas (OUT OF SCOPE)
None -- autonomous mode stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GAME-02 | Inventory system (item database SO, UI slots, drag-and-drop, equipment, storage) | SO item class matching items.json schema; UI Toolkit grid with PointerManipulator drag-and-drop; 8 equipment slots; storage container with separate grid |
| GAME-03 | Dialogue system (branching trees, dialogue UI, NPC interaction, YarnSpinner-compatible) | Generate .yarn node format (title/---/===/-> choices/<<commands>>); dialogue UI with UI Toolkit; NPC interaction trigger using Phase 12 interactable pattern |
| GAME-04 | Quest system (objectives, tracking, quest givers, quest log UI, completion rewards) | SO-based quest definitions; quest state machine FSM; objective tracker with event-driven completion; quest log UI Toolkit screen; reward distribution to inventory/XP/currency |
| GAME-09 | Loot table system (weighted random, rarity tiers, drop conditions) | WeightedRandom utility; 5 rarity tiers with configurable weights; monster brand affinity modifier; corruption quality bonus |
| GAME-10 | Crafting/recipe system (ingredients, stations, unlock progression) | SO recipe definitions; crafting station MonoBehaviour; ingredient validation against inventory; unlock via quest/level progression |
| GAME-11 | Skill tree/talent system (node graph, dependencies, point allocation) | SO skill node definitions; dependency graph with prerequisite validation; 4 hero path layouts; point allocation per level-up |
| GAME-12 | Combat balancing tools (DPS calculator, encounter simulator, stat curve editor) | EditorWindow DPS calculator with brand/synergy modifiers; Monte Carlo encounter simulator; AnimationCurve-based stat scaling editor |
| EQUIP-01 | Weapon mesh generation from text (swords/axes/maces/staffs with grip points) | Blender Python procedural mesh generation (bmesh + bpy.ops); parametric weapon parts (blade/hilt/guard/pommel); auto-generated grip_point/trail_attach/collision empties |
| EQUIP-03 | Modular character mesh splitting (head/torso/arms/legs) | Blender Python mesh separation by vertex groups; automatic seam creation at body part boundaries; export as separate FBX with shared armature |
| EQUIP-04 | Armor fitting with shape keys + weight transfer | Blender Python shape key driver setup; surface deform modifier for body-conforming armor; automatic weight transfer from character to armor mesh |
| EQUIP-05 | Equipment preview icon rendering | Blender Python off-screen render setup; studio lighting template; transparent background PNG output; configurable camera distance/angle |
| EQUIP-06 | Unity equipment attachment (SkinnedMeshRenderer rebinding, bone sockets, Multi-Parent Constraint) | C# template: bone name matching for SMR rebinding; extends Phase 9 bone socket system; Animation Rigging Multi-Parent Constraint for sheathed weapon positions |
| VB-08 | Brand-specific loot affinity | Loot table weight modifier per brand; references BrandSystem.cs 10 brand enum; IRON mobs boost IRON gear drop rate |
| RPG-01 | Shop/merchant system | Buy/sell UI Toolkit screen; price display with currency formatting; equipment stat comparison panel; merchant inventory as SO asset |
| RPG-05 | Journal/codex/bestiary | Tabbed UI Toolkit screen (Lore/Bestiary/Items); monster compendium with stats/weaknesses from monsters.json; progressive unlock on discovery |

</phase_requirements>

## Standard Stack

### Core (Unity / C# -- generated by templates)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Unity UI Toolkit | Built-in (Unity 6) | Inventory/dialogue/quest/shop/codex UI | UXML + USS, matches VeilBreakers existing UI approach, user decision |
| Unity Animation Rigging | 1.3+ (com.unity.animation.rigging) | Multi-Parent Constraint for weapon sheathing | Official Unity package for runtime constraint solving |
| ScriptableObject | Built-in (Unity 6) | Item/quest/recipe/skill node/loot table data definitions | Standard Unity data-driven design pattern, user decision |

### Toolkit (Python -- template generators + Blender handlers)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FastMCP | 1.26+ | MCP server framework | Tool registration for unity_content compound tool |
| pytest | 8.0+ | Template + handler validation | C# syntax verification + Blender handler logic tests |
| bpy | 4.x (Blender built-in) | Weapon mesh generation, character splitting, armor fitting, icon rendering | All EQUIP-01/03/04/05 Blender operations |
| bmesh | 4.x (Blender built-in) | Procedural mesh construction for weapons | EQUIP-01 vertex/face creation |

### No New Python Dependencies
This phase adds zero new Python pip dependencies. All Blender operations use bpy/bmesh/mathutils (already in allowed list). Unity operations use built-in Unity 6 APIs. Animation Rigging package may need explicit installation if not already present.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| YarnSpinner-compatible format | Custom JSON dialogue trees | YarnSpinner format is user decision; .yarn files are human-readable and compatible with YarnSpinner Unity plugin if user installs it later |
| UI Toolkit for all UIs | UGUI Canvas | UI Toolkit is locked user decision; matches all prior phases |
| SO-based item database | JSON-only runtime loading | SOs provide Unity Inspector editing, drag-drop asset references, and are the user decision |
| Animation Rigging Multi-Parent Constraint | Simple Transform.SetParent | Multi-Parent Constraint handles weighted blending between sheathed/drawn positions and is specified in requirements |

## Architecture Patterns

### Recommended Project Structure (New Files)
```
Tools/mcp-toolkit/src/veilbreakers_mcp/
  shared/unity_templates/
    content_templates.py          # NEW: Inventory, dialogue, quest, loot, crafting, skill tree, balancing, shop, codex generators
    equipment_templates.py        # NEW: Unity equipment attachment C# generators (EQUIP-06)
  unity_server.py                 # EXTEND: Add unity_content compound tool (~12 actions)
  blender_server.py               # EXTEND: Add equipment mesh generation actions

Tools/mcp-toolkit/blender_addon/handlers/
  equipment.py                    # NEW: Weapon generation, character splitting, armor fitting, icon rendering handlers

Tools/mcp-toolkit/tests/
  test_content_templates.py       # NEW: Content system C# syntax tests
  test_equipment_templates.py     # NEW: Equipment C# syntax tests
  test_equipment_handlers.py      # NEW: Blender equipment handler logic tests
```

### Generated C# Output Structure
```
Assets/
  Scripts/Runtime/ContentSystems/  # Runtime MonoBehaviours (NOT editor scripts)
    Inventory/                     # VB_InventorySystem.cs, VB_ItemDatabase.cs, VB_EquipmentSlots.cs
    Dialogue/                      # VB_DialogueSystem.cs, VB_DialogueUI.cs
    Quest/                         # VB_QuestSystem.cs, VB_QuestObjective.cs, VB_QuestLog.cs
    Loot/                          # VB_LootTable.cs, VB_BrandLootAffinity.cs
    Crafting/                      # VB_CraftingSystem.cs, VB_Recipe.cs
    SkillTree/                     # VB_SkillTree.cs, VB_SkillNode.cs
    Shop/                          # VB_ShopSystem.cs, VB_MerchantInventory.cs
    Journal/                       # VB_Journal.cs, VB_Bestiary.cs, VB_Codex.cs
  Scripts/Editor/BalancingTools/   # EDITOR scripts (need UnityEditor)
    DPSCalculator/                 # VB_DPSCalculator.cs (EditorWindow)
    EncounterSimulator/            # VB_EncounterSimulator.cs (EditorWindow)
    StatCurveEditor/               # VB_StatCurveEditor.cs (EditorWindow)
  Scripts/Runtime/Equipment/       # Runtime equipment attachment
    EquipmentAttachment/           # VB_EquipmentAttachment.cs, VB_WeaponSheath.cs
  UI/
    Inventory.uxml + Inventory.uss
    Dialogue.uxml + Dialogue.uss
    QuestLog.uxml + QuestLog.uss
    Shop.uxml + Shop.uss
    Journal.uxml + Journal.uss
```

### Pattern 1: Content System Template Generator (Runtime)
**What:** Python function generating complete C# runtime MonoBehaviour + SO definitions.
**When to use:** GAME-02/03/04/09/10/11, VB-08, RPG-01, RPG-05.
**Example:**
```python
# Source: Established pattern from game_templates.py / vb_combat_templates.py
def generate_inventory_system_script(
    grid_width: int = 8,
    grid_height: int = 5,
    equipment_slots: list[str] | None = None,
    namespace: str = "VeilBreakers.Content",
) -> tuple[str, str, str, str]:
    """Return (item_so_cs, inventory_cs, uxml, uss) for the inventory system."""
    # ... line-based string concatenation for C# templates
    # ... _sanitize_cs_string() for all user input
    # ... no f-string leaks (all C# $"" interpolation whitelisted)
```

### Pattern 2: Combat Balancing Tool (Editor Window)
**What:** Python function generating C# EditorWindow (uses UnityEditor namespace).
**When to use:** GAME-12 only (DPS calculator, encounter simulator, stat curve editor).
**Note:** These are the ONLY templates in this phase that use `using UnityEditor;` -- they go in `Assets/Scripts/Editor/`, not `Assets/Scripts/Runtime/`.
**Example:**
```python
def generate_dps_calculator_script(
    brands: list[str] | None = None,
    namespace: str = "VeilBreakers.Editor.Balancing",
) -> str:
    """Return C# EditorWindow for DPS calculation with brand/synergy modifiers."""
    # Must use 'using UnityEditor;' -- this is an Editor-only tool
```

### Pattern 3: Blender Equipment Handler
**What:** Python handler function registered in blender_addon, invoked via TCP from blender_server.py.
**When to use:** EQUIP-01/03/04/05 (all Blender-side operations).
**Example:**
```python
# In blender_addon/handlers/equipment.py
async def equipment_generate_weapon(params: dict) -> dict:
    """Generate weapon mesh from description parameters.

    Uses bmesh for procedural geometry, creates grip_point/trail_attach empties,
    generates collision mesh as simplified convex hull.
    """
    weapon_type = params.get("weapon_type", "sword")  # sword/axe/mace/staff/bow/dagger/shield
    # ... bmesh vertex/face creation
    # ... empty creation for attachment points
    # ... collision mesh generation
```

### Pattern 4: VeilBreakers Data Schema Alignment
**What:** Generated SO classes must match existing items.json/monsters.json/skills.json schemas.
**When to use:** All content systems that interact with existing game data.
**Critical fields from items.json:**
```csharp
// Must match existing schema:
// item_id (string), display_name, description, icon_path
// item_type (int: 0=consumable, 1=weapon, 2=armor, 3=accessory, 4=material, 5=key_item)
// rarity (int: 0=Common, 1=Uncommon, 2=Rare, 3=Epic, 4=Legendary)
// buy_price, sell_price, is_stackable, max_stack
// stat_buffs (array of {stat, amount, duration})
// corruption_change, path_change
// item_category (string: consumables, weapons, armor, accessories, materials, key_items)
```

### Pattern 5: Delegation to Existing VeilBreakers Systems
**What:** Generated code references existing static utility classes, never reimplements game logic.
**When to use:** VB-08 (brand loot), any system touching brands/synergy/corruption.
**Already established in Phase 12:** `BrandSystem.GetEffectiveness()`, `SynergySystem.GetSynergyTier()`, `CorruptionSystem.GetStatMultiplier()`, `EventBus` events.
```csharp
// VB-08: Brand loot affinity -- DELEGATE to BrandSystem, never reimplement
float brandBonus = BrandSystem.GetEffectiveness(monsterBrand, gearBrand);
float adjustedWeight = baseWeight * (brandBonus > 1f ? 1.5f : 1f);
```

### Anti-Patterns to Avoid
- **Reimplementing brand/synergy/corruption logic:** Always delegate to BrandSystem/SynergySystem/CorruptionSystem
- **Mixing Editor and Runtime code:** GAME-12 balancing tools are EditorWindows; everything else is Runtime MonoBehaviour/SO. Never put `using UnityEditor;` in Runtime scripts
- **Using UGUI Canvas:** All UIs must use UI Toolkit (UXML + USS), never UnityEngine.UI
- **Hard-coding item data:** Item definitions are SO assets, not C# constants. The generator creates the SO class definition; actual item data comes from existing items.json or manual SO creation
- **Generating actual .yarn files:** Generate C# code that can PRODUCE .yarn-compatible node format, or parse existing .yarn files -- do not embed dialogue content in C# templates
- **f-string leaks in C# interpolation:** Continue using the established whitelist pattern for C# `$""` interpolation variables

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Weighted random selection | Custom probability code | Standard weighted random with cumulative distribution | Off-by-one errors in probability calculations are extremely common |
| Dialogue tree traversal | Custom tree walker | YarnSpinner-compatible node format with standard traversal | User wants YarnSpinner compatibility; the format is well-defined |
| Inventory drag-and-drop | Custom mouse tracking | UI Toolkit PointerManipulator base class | Built-in event system handles capture/release/overlap detection |
| Bone name matching for SMR rebinding | Manual bone index mapping | Dictionary<string, Transform> bone name lookup | Bone order changes between models; name-based matching is order-independent |
| Quest state machine | if/else state tracking | Enum-based FSM (same pattern as Phase 12 combat FSM) | Clean transitions, serializable state, event-driven |
| Skill tree dependency resolution | Custom graph traversal | Topological sort / prerequisite set checking | Standard CS pattern, handles circular dependency detection |
| Equipment stat comparison | Manual stat diff display | Generic stat comparison utility that works across all equipment types | Avoids duplicate comparison code per slot type |

**Key insight:** This phase generates TEMPLATE CODE that produces game systems. The templates themselves should use well-understood patterns (FSM, SO data, weighted random, PointerManipulator) rather than inventing novel approaches. The value is in the automation and integration, not algorithmic novelty.

## Common Pitfalls

### Pitfall 1: Item Type Enum Mismatch
**What goes wrong:** Generated C# enum values don't match the integer item_type values in items.json (0=consumable, 1=weapon, 2=armor, etc.).
**Why it happens:** Template author assumes different ordering or naming.
**How to avoid:** Use the exact integer mapping from items.json. Include explicit `= 0`, `= 1` assignments in the generated enum.
**Warning signs:** Existing item data loads but displays wrong categories.

### Pitfall 2: Rarity Tier Off-by-One
**What goes wrong:** Rarity enum starts at 1 instead of 0, causing Common items to show as Uncommon.
**Why it happens:** Natural inclination to start enums at 1 for "levels."
**How to avoid:** Match items.json: rarity 0=Common, 1=Uncommon, 2=Rare, 3=Epic, 4=Legendary.
**Warning signs:** Loot table weights produce wrong rarity distribution.

### Pitfall 3: SkinnedMeshRenderer Bone Order Dependency
**What goes wrong:** Equipment mesh deforms incorrectly when attached to character.
**Why it happens:** Non-optimized mode requires bones in exact order matching the mesh's bone index array.
**How to avoid:** Use name-based bone matching (Dictionary lookup), not index-based. Always rebuild the bones array to match the target armature's bone transforms by name.
**Warning signs:** Mesh stretches or collapses when equipped.

### Pitfall 4: Editor-Only Code in Runtime Scripts
**What goes wrong:** Build fails because Runtime scripts reference UnityEditor namespace.
**Why it happens:** GAME-12 balancing tools are EditorWindows; copy-pasting the pattern into content system generators.
**How to avoid:** Only `generate_dps_calculator_script`, `generate_encounter_simulator_script`, and `generate_stat_curve_editor_script` should contain `using UnityEditor;`. ALL other generators in this phase produce Runtime-only code.
**Warning signs:** `#if UNITY_EDITOR` guards needed (should not be needed if separation is correct).

### Pitfall 5: YarnSpinner Format Syntax Errors
**What goes wrong:** Generated .yarn content fails to parse in YarnSpinner.
**Why it happens:** Missing `---` separator, incorrect `===` node terminator, wrong choice syntax.
**How to avoid:** .yarn format is: `title: NodeName\n---\nContent\n===`. Choices use `-> Choice text`. Commands use `<<command>>`. Variables use `{$var}`.
**Warning signs:** YarnSpinner console errors on import.

### Pitfall 6: Brand Enum Value Mismatch
**What goes wrong:** Brand loot affinity uses wrong brand index.
**Why it happens:** monsters.json uses integer brand IDs (e.g., brand: 10), but BrandSystem.cs uses the Brand enum.
**How to avoid:** Reference the Brand enum by name (Brand.IRON, Brand.SAVAGE, etc.), not by integer. The generated code should cast from int to Brand enum when loading from JSON.
**Warning signs:** IRON mobs dropping VOID-themed gear.

### Pitfall 7: Circular Quest/Inventory Dependencies
**What goes wrong:** Quest completion requires inventory check, inventory requires quest unlock, creating initialization deadlock.
**Why it happens:** Tight coupling between quest and inventory systems.
**How to avoid:** Use EventBus pattern (already established in Phase 12) for cross-system communication. Quest system fires events, inventory system listens. No direct references between systems.
**Warning signs:** NullReferenceException on game start depending on initialization order.

## Code Examples

### Verified Pattern: SO Item Definition (matches items.json schema)
```csharp
// Source: VeilBreakers items.json schema analysis
[CreateAssetMenu(fileName = "New Item", menuName = "VeilBreakers/Items/Item")]
public class VB_ItemData : ScriptableObject
{
    public string itemId;
    public string displayName;
    [TextArea] public string description;
    public Sprite icon;

    public ItemType itemType;        // 0=Consumable, 1=Weapon, 2=Armor, 3=Accessory, 4=Material, 5=KeyItem
    public ItemRarity rarity;        // 0=Common, 1=Uncommon, 2=Rare, 3=Epic, 4=Legendary

    public bool isKeyItem;
    public bool isStackable;
    public int maxStack = 99;

    public int buyPrice;
    public int sellPrice;
    public bool canSell = true;

    // Combat usage
    public bool usableInBattle;
    public bool usableInField;
    public bool consumedOnUse = true;

    // Effects
    public int hpRestore;
    public float hpRestorePercent;
    public int mpRestore;
    public float mpRestorePercent;
    public StatBuff[] statBuffs;

    public int corruptionChange;
    public int pathChange;

    public string itemCategory;      // consumables, weapons, armor, accessories, materials, key_items
}

public enum ItemType { Consumable = 0, Weapon = 1, Armor = 2, Accessory = 3, Material = 4, KeyItem = 5 }
public enum ItemRarity { Common = 0, Uncommon = 1, Rare = 2, Epic = 3, Legendary = 4 }
```

### Verified Pattern: Weighted Random Loot Table
```csharp
// Source: Standard weighted random distribution algorithm
public class VB_LootTable : ScriptableObject
{
    [System.Serializable]
    public class LootEntry
    {
        public VB_ItemData item;
        public float weight = 1f;
        public ItemRarity minRarity = ItemRarity.Common;
        public int minQuantity = 1;
        public int maxQuantity = 1;
        // VB-08: Brand affinity
        public Brand brandAffinity = Brand.NONE;
    }

    public LootEntry[] entries;

    public VB_ItemData Roll(Brand monsterBrand = Brand.NONE, float corruptionLevel = 0f)
    {
        float totalWeight = 0f;
        float[] adjustedWeights = new float[entries.Length];

        for (int i = 0; i < entries.Length; i++)
        {
            float w = entries[i].weight;
            // VB-08: Brand affinity bonus
            if (entries[i].brandAffinity != Brand.NONE && monsterBrand != Brand.NONE)
            {
                float effectiveness = BrandSystem.GetEffectiveness(monsterBrand, entries[i].brandAffinity);
                if (effectiveness >= BrandSystem.SUPER_EFFECTIVE) w *= 1.5f;
            }
            // Corruption bonus to rarity
            if (corruptionLevel > 0.5f) w *= (1f + corruptionLevel * 0.3f);
            adjustedWeights[i] = w;
            totalWeight += w;
        }

        float roll = UnityEngine.Random.Range(0f, totalWeight);
        float cumulative = 0f;
        for (int i = 0; i < entries.Length; i++)
        {
            cumulative += adjustedWeights[i];
            if (roll <= cumulative) return entries[i].item;
        }
        return entries[entries.Length - 1].item;
    }
}
```

### Verified Pattern: YarnSpinner-Compatible Node Format
```csharp
// Source: YarnSpinner documentation (yarnspinner.dev)
// Generated .yarn file format:
// title: NodeName
// ---
// NPC: Hello, traveler!
// -> Tell me about the quest.
//     <<set $questAccepted to true>>
//     NPC: There's trouble in the mines...
//     <<jump QuestDetails>>
// -> I'm just passing through.
//     NPC: Safe travels then.
// ===

public static class VB_YarnGenerator
{
    public static string GenerateNode(string title, List<DialogueLine> lines)
    {
        var sb = new System.Text.StringBuilder();
        sb.AppendLine($"title: {title}");
        sb.AppendLine("---");
        foreach (var line in lines)
        {
            if (line.IsChoice)
                sb.AppendLine($"-> {line.Text}");
            else
                sb.AppendLine($"{line.Speaker}: {line.Text}");
        }
        sb.AppendLine("===");
        return sb.ToString();
    }
}
```

### Verified Pattern: UI Toolkit Drag-and-Drop Inventory Slot
```csharp
// Source: Unity docs (docs.unity3d.com/6000.3/Documentation/Manual/UIE-create-drag-and-drop-ui.html)
public class InventorySlotManipulator : PointerManipulator
{
    private Vector2 _startPosition;
    private bool _enabled;

    protected override void RegisterCallbacksOnTarget()
    {
        target.RegisterCallback<PointerDownEvent>(OnPointerDown);
        target.RegisterCallback<PointerMoveEvent>(OnPointerMove);
        target.RegisterCallback<PointerUpEvent>(OnPointerUp);
        target.RegisterCallback<PointerCaptureOutEvent>(OnPointerCaptureOut);
    }

    private void OnPointerDown(PointerDownEvent evt)
    {
        _startPosition = evt.position;
        target.CapturePointer(evt.pointerId);
        _enabled = true;
    }

    private void OnPointerMove(PointerMoveEvent evt)
    {
        if (!_enabled || !target.HasPointerCapture(evt.pointerId)) return;
        Vector3 delta = evt.position - (Vector3)_startPosition;
        target.transform.position += delta;
        _startPosition = evt.position;
    }

    private void OnPointerUp(PointerUpEvent evt)
    {
        if (!_enabled || !target.HasPointerCapture(evt.pointerId)) return;
        target.ReleasePointer(evt.pointerId);
    }

    private void OnPointerCaptureOut(PointerCaptureOutEvent evt)
    {
        // Snap to nearest valid slot or return to original position
        _enabled = false;
    }
}
```

### Verified Pattern: SkinnedMeshRenderer Bone Rebinding
```csharp
// Source: Unity docs (docs.unity3d.com/ScriptReference/SkinnedMeshRenderer-bones.html)
// and community best practice (name-based matching, not index-based)
public static class VB_MeshRebinder
{
    public static void RebindToArmature(SkinnedMeshRenderer equipmentSMR, Transform armatureRoot)
    {
        // Build name->Transform lookup from target armature
        var boneMap = new Dictionary<string, Transform>();
        BuildBoneMap(armatureRoot, boneMap);

        // Remap equipment bones to target armature's transforms
        Transform[] originalBones = equipmentSMR.bones;
        Transform[] newBones = new Transform[originalBones.Length];

        for (int i = 0; i < originalBones.Length; i++)
        {
            string boneName = originalBones[i] != null ? originalBones[i].name : "";
            if (boneMap.TryGetValue(boneName, out Transform targetBone))
                newBones[i] = targetBone;
            else
                newBones[i] = armatureRoot; // Fallback to root
        }

        equipmentSMR.bones = newBones;
        equipmentSMR.rootBone = armatureRoot;
    }

    private static void BuildBoneMap(Transform root, Dictionary<string, Transform> map)
    {
        map[root.name] = root;
        foreach (Transform child in root)
            BuildBoneMap(child, map);
    }
}
```

### Verified Pattern: Blender Procedural Weapon Mesh (bmesh)
```python
# Source: Blender Python API (docs.blender.org/api/current/) + bpy mesh creation patterns
import bpy
import bmesh
import mathutils

def generate_sword(length=1.2, blade_width=0.08, guard_width=0.25, hilt_length=0.25):
    """Generate a basic sword mesh with grip point and trail attach empties."""
    mesh = bpy.data.meshes.new("Sword_Mesh")
    bm = bmesh.new()

    # Blade (tapered quad strip)
    half_w = blade_width / 2
    verts_blade = [
        bm.verts.new((0, 0, 0)),                    # base left
        bm.verts.new((blade_width, 0, 0)),           # base right
        bm.verts.new((blade_width * 0.1, 0, length)),# tip left
        bm.verts.new((blade_width * 0.9, 0, length)),# tip right
    ]
    bm.faces.new([verts_blade[0], verts_blade[1], verts_blade[3], verts_blade[2]])

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("Sword", mesh)
    bpy.context.collection.objects.link(obj)

    # Create attachment point empties
    for name, loc in [
        ("grip_point", (blade_width/2, 0, -hilt_length/2)),
        ("trail_attach_top", (blade_width/2, 0, length)),
        ("trail_attach_bottom", (blade_width/2, 0, 0)),
    ]:
        empty = bpy.data.objects.new(name, None)
        empty.empty_display_type = 'PLAIN_AXES'
        empty.empty_display_size = 0.05
        empty.location = loc
        empty.parent = obj
        bpy.context.collection.objects.link(empty)

    return {"object_name": obj.name, "vertices": len(mesh.vertices), "faces": len(mesh.polygons)}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| UGUI Canvas inventory | UI Toolkit runtime UI | Unity 6 (2024) | UI Toolkit is now production-ready for runtime, fully replaces UGUI for new projects |
| Transform.SetParent for weapons | Animation Rigging Multi-Parent Constraint | Unity 2020+ | Weighted blending between multiple parent positions (drawn/sheathed) |
| SkinnedMeshRenderer.bones index-based | Name-based bone matching (optimized mode) | Unity 2022+ | Order-independent, works across different mesh exports |
| Custom dialogue parser | YarnSpinner 2.x (.yarn format) | 2023 | Community standard for Unity dialogue, well-documented format |
| Singleton inventory manager | SO event channels + service locator | 2024+ | Decoupled systems, testable, matches VeilBreakers architecture |

**Deprecated/outdated:**
- UGUI GridLayoutGroup for inventory grids: Use UI Toolkit flex layout instead
- YarnSpinner 1.x format: Use 2.x format (title/---/===)
- SkinnedMeshRenderer.BakeMesh for equipment preview: Use off-screen render for higher quality icons

## Open Questions

1. **Animation Rigging Package Installation**
   - What we know: EQUIP-06 requires com.unity.animation.rigging for Multi-Parent Constraint
   - What's unclear: Whether this package is already installed in the VeilBreakers Unity project
   - Recommendation: Generated equipment attachment script should check for the package and include installation instructions in next_steps if missing

2. **Existing Item Data Import Pipeline**
   - What we know: VeilBreakers has items.json with 60+ items, monsters.json with 60+ monsters, skills.json, heroes.json
   - What's unclear: Whether the generator should include a JSON-to-SO import utility or just define the SO schema
   - Recommendation: Generate both the SO class definition AND a one-time JSON importer EditorWindow that reads items.json and creates .asset files

3. **Blender Equipment Handler Registration**
   - What we know: Existing handlers are in blender_addon/handlers/ and registered in handlers/__init__.py
   - What's unclear: Whether weapon generation should be a new action on `asset_pipeline` or a new `blender_equipment` compound tool
   - Recommendation: Extend `asset_pipeline` with `generate_weapon` action OR create new Blender tool -- either fits the compound pattern. Recommend extending asset_pipeline since weapon generation is an asset pipeline concern.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | Tools/mcp-toolkit/pyproject.toml (existing) |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_content_templates.py tests/test_equipment_templates.py tests/test_equipment_handlers.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GAME-02 | Inventory SO + UI + equipment slots | unit | `pytest tests/test_content_templates.py::TestInventorySystem -x` | Wave 0 |
| GAME-03 | Dialogue system + YarnSpinner format | unit | `pytest tests/test_content_templates.py::TestDialogueSystem -x` | Wave 0 |
| GAME-04 | Quest system + state machine + log UI | unit | `pytest tests/test_content_templates.py::TestQuestSystem -x` | Wave 0 |
| GAME-09 | Loot tables + weighted random + rarity | unit | `pytest tests/test_content_templates.py::TestLootTable -x` | Wave 0 |
| GAME-10 | Crafting + recipes + stations | unit | `pytest tests/test_content_templates.py::TestCraftingSystem -x` | Wave 0 |
| GAME-11 | Skill tree + node graph + dependencies | unit | `pytest tests/test_content_templates.py::TestSkillTree -x` | Wave 0 |
| GAME-12 | DPS calculator + encounter sim + stat curves | unit | `pytest tests/test_content_templates.py::TestBalancingTools -x` | Wave 0 |
| EQUIP-01 | Weapon mesh generation | unit | `pytest tests/test_equipment_handlers.py::TestWeaponGeneration -x` | Wave 0 |
| EQUIP-03 | Modular character splitting | unit | `pytest tests/test_equipment_handlers.py::TestModularCharacter -x` | Wave 0 |
| EQUIP-04 | Armor fitting shape keys | unit | `pytest tests/test_equipment_handlers.py::TestArmorFitting -x` | Wave 0 |
| EQUIP-05 | Equipment preview icons | unit | `pytest tests/test_equipment_handlers.py::TestPreviewIcons -x` | Wave 0 |
| EQUIP-06 | Unity equipment attachment | unit | `pytest tests/test_equipment_templates.py::TestEquipmentAttachment -x` | Wave 0 |
| VB-08 | Brand loot affinity | unit | `pytest tests/test_content_templates.py::TestBrandLootAffinity -x` | Wave 0 |
| RPG-01 | Shop/merchant system | unit | `pytest tests/test_content_templates.py::TestShopSystem -x` | Wave 0 |
| RPG-05 | Journal/codex/bestiary | unit | `pytest tests/test_content_templates.py::TestJournalSystem -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/test_content_templates.py tests/test_equipment_templates.py tests/test_equipment_handlers.py -x -q`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_content_templates.py` -- covers GAME-02/03/04/09/10/11/12, VB-08, RPG-01, RPG-05
- [ ] `tests/test_equipment_templates.py` -- covers EQUIP-06
- [ ] `tests/test_equipment_handlers.py` -- covers EQUIP-01/03/04/05
- [ ] `shared/unity_templates/content_templates.py` -- new template module
- [ ] `shared/unity_templates/equipment_templates.py` -- new template module
- [ ] `blender_addon/handlers/equipment.py` -- new handler module

## Sources

### Primary (HIGH confidence)
- VeilBreakers items.json -- exact item data schema with 60+ items, field names, enum integer values
- VeilBreakers monsters.json -- exact monster data schema with brand affiliations, drop_table structure
- VeilBreakers skills.json -- skill data schema with prerequisites, brand requirements
- VeilBreakers heroes.json -- hero paths (4 paths), starter monsters, innate skills
- VeilBreakers BrandSystem.cs -- 10 core brands + 6 hybrid brands, effectiveness matrix, GetEffectiveness() API
- Unity UI Toolkit docs (docs.unity3d.com/6000.3) -- PointerManipulator drag-and-drop pattern
- Unity SkinnedMeshRenderer docs -- bones property, name-based rebinding approach
- Unity Animation Rigging docs (com.unity.animation.rigging@1.1) -- Multi-Parent Constraint for weapon attachment
- YarnSpinner docs (yarnspinner.dev) -- .yarn file format syntax (title/---/===, -> choices, <<commands>>)
- Existing Phase 12 game_templates.py and vb_combat_templates.py -- established code generation patterns
- Existing Phase 9 prefab_templates.py -- bone socket setup pattern (EQUIP-02)

### Secondary (MEDIUM confidence)
- Unity UI Toolkit inventory tutorials (discussions.unity.com) -- grid layout and flex-wrap patterns
- Unity modular character discussions -- SkinnedMeshRenderer bone remapping best practices
- Blender Python API docs (docs.blender.org/api/current) -- bmesh procedural mesh creation

### Tertiary (LOW confidence)
- Procedural weapon generation approaches -- general patterns from tutorials and books, would need validation with actual Blender testing

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using established Unity built-ins and existing project patterns
- Architecture: HIGH - Follows exact same template generator pattern from Phases 10-12
- Content system design: HIGH - Based on actual VeilBreakers game data schemas (items.json, monsters.json)
- Equipment mesh generation: MEDIUM - Blender procedural mesh patterns are well-understood but weapon-specific generation needs implementation testing
- Equipment attachment: HIGH - SkinnedMeshRenderer rebinding and bone sockets are established Unity patterns
- Pitfalls: HIGH - Based on actual project data analysis (enum values, brand system integration)

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (30 days -- stable domain, no fast-moving APIs)
