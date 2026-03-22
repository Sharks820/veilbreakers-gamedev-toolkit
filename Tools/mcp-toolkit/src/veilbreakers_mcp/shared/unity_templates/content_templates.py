"""Content and progression system C# template generators for Unity.

Each function returns a complete C# source string (or tuple of strings for
multi-file generators) for runtime MonoBehaviours, ScriptableObjects, and
UI Toolkit assets.  These are placed in the Unity project's
Assets/Scripts/Runtime/ directory -- they are NOT editor scripts and must
NEVER reference the UnityEditor namespace.

The three balancing-tool generators (DPS calculator, encounter simulator,
stat curve editor) are the ONLY exceptions: they target
Assets/Editor/Balancing/ and DO use ``using UnityEditor;``.

CRITICAL DESIGN PRINCIPLE: Generated MonoBehaviours call into existing
static utility classes.  They do NOT reimplement brand effectiveness
matrices, synergy calculations, corruption formulas, or damage pipelines.
  - BrandSystem.GetEffectiveness()
  - SynergySystem.GetSynergyTier() / GetDamageBonus()
  - CorruptionSystem.GetStatMultiplier() / GetCorruptionState()
  - DamageCalculator.Calculate()
  - EventBus (various events)

Exports:
    generate_inventory_system_script     -- GAME-02: Inventory + equipment + grid UI
    generate_dialogue_system_script      -- GAME-03: Dialogue + YarnSpinner nodes + UI
    generate_quest_system_script         -- GAME-04: Quest state machine + log UI
    generate_loot_table_script           -- VB-08 / RPG-01: Weighted loot + brand affinity
    generate_crafting_system_script      -- GAME-09: Recipe SO + crafting station
    generate_skill_tree_script           -- GAME-10: Skill nodes + hero path tree
    generate_dps_calculator_script       -- GAME-12: EditorWindow DPS tool (EDITOR)
    generate_encounter_simulator_script  -- GAME-12: EditorWindow Monte Carlo (EDITOR)
    generate_stat_curve_editor_script    -- GAME-12: EditorWindow curve editor (EDITOR)
    generate_shop_system_script          -- GAME-11: Merchant + shop UI
    generate_journal_system_script       -- RPG-05: Codex with Lore/Bestiary/Items
"""

from __future__ import annotations

import re
from typing import Optional

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier


# ---------------------------------------------------------------------------
# C# reserved words
# ---------------------------------------------------------------------------

_CS_RESERVED = frozenset({
    "abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char",
    "checked", "class", "const", "continue", "decimal", "default", "delegate",
    "do", "double", "else", "enum", "event", "explicit", "extern", "false",
    "finally", "fixed", "float", "for", "foreach", "goto", "if", "implicit",
    "in", "int", "interface", "internal", "is", "lock", "long", "namespace",
    "new", "null", "object", "operator", "out", "override", "params", "private",
    "protected", "public", "readonly", "ref", "return", "sbyte", "sealed",
    "short", "sizeof", "stackalloc", "static", "string", "struct", "switch",
    "this", "throw", "true", "try", "typeof", "uint", "ulong", "unchecked",
    "unsafe", "ushort", "using", "virtual", "void", "volatile", "while",
})


def _safe_namespace(ns: str) -> str:
    """Sanitize a C# namespace to prevent code injection."""
    sanitized = re.sub(r"[^a-zA-Z0-9_.]", "", ns)
    sanitized = re.sub(r"\.{2,}", ".", sanitized).strip(".")
    if not sanitized:
        return "Generated"
    segments = sanitized.split(".")
    fixed: list[str] = []
    for seg in segments:
        if not seg:
            continue
        if seg[0].isdigit():
            seg = f"_{seg}"
        if seg in _CS_RESERVED:
            seg = f"@{seg}"
        fixed.append(seg)
    return ".".join(fixed) or "Generated"


# ---------------------------------------------------------------------------
# GAME-02: Inventory system (SO + grid + equipment + UI)
# ---------------------------------------------------------------------------


def generate_inventory_system_script(
    grid_width: int = 8,
    grid_height: int = 5,
    equipment_slots: Optional[list[str]] = None,
    namespace: str = "VeilBreakers.Content",
) -> tuple[str, str, str, str]:
    """Generate C# for a complete inventory system.

    Returns:
        (item_so_cs, inventory_cs, uxml, uss) tuple.
    """
    if equipment_slots is None:
        equipment_slots = [
            "Head", "Torso", "Arms", "Legs",
            "Weapon", "Shield", "Accessory1", "Accessory2",
        ]
    ns = _safe_namespace(namespace)

    # ----- Item ScriptableObject -----
    item_lines: list[str] = []
    item_lines.append("using System;")
    item_lines.append("using System.Collections.Generic;")
    item_lines.append("using UnityEngine;")
    item_lines.append("")
    item_lines.append("namespace " + ns)
    item_lines.append("{")

    # ItemType enum
    item_lines.append("    /// <summary>Item type matching items.json schema.</summary>")
    item_lines.append("    public enum ItemType")
    item_lines.append("    {")
    item_lines.append("        Consumable = 0,")
    item_lines.append("        Weapon = 1,")
    item_lines.append("        Armor = 2,")
    item_lines.append("        Accessory = 3,")
    item_lines.append("        Material = 4,")
    item_lines.append("        KeyItem = 5")
    item_lines.append("    }")
    item_lines.append("")

    # ItemRarity enum
    item_lines.append("    /// <summary>Item rarity matching items.json schema.</summary>")
    item_lines.append("    public enum ItemRarity")
    item_lines.append("    {")
    item_lines.append("        Common = 0,")
    item_lines.append("        Uncommon = 1,")
    item_lines.append("        Rare = 2,")
    item_lines.append("        Epic = 3,")
    item_lines.append("        Legendary = 4")
    item_lines.append("    }")
    item_lines.append("")

    # EquipmentSlot enum
    item_lines.append("    /// <summary>Equipment slot types.</summary>")
    item_lines.append("    public enum EquipmentSlot")
    item_lines.append("    {")
    for i, slot in enumerate(equipment_slots):
        safe_slot = sanitize_cs_identifier(slot)
        comma = "," if i < len(equipment_slots) - 1 else ""
        item_lines.append("        " + safe_slot + comma)
    item_lines.append("    }")
    item_lines.append("")

    # StatBuff struct
    item_lines.append("    /// <summary>Stat buff definition matching items.json stat_buffs.</summary>")
    item_lines.append("    [Serializable]")
    item_lines.append("    public struct StatBuff")
    item_lines.append("    {")
    item_lines.append("        public string stat;")
    item_lines.append("        public float amount;")
    item_lines.append("        public float duration;")
    item_lines.append("    }")
    item_lines.append("")

    # VB_ItemData ScriptableObject
    item_lines.append("    /// <summary>")
    item_lines.append("    /// ScriptableObject representing a game item.")
    item_lines.append("    /// Schema matches items.json: item_id, display_name, description, icon_path,")
    item_lines.append("    /// item_type, rarity, buy_price, sell_price, is_stackable, max_stack,")
    item_lines.append("    /// stat_buffs, corruption_change, path_change, item_category.")
    item_lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    item_lines.append("    /// </summary>")
    item_lines.append('    [CreateAssetMenu(fileName = "NewItem", menuName = "VeilBreakers/Item Data")]')
    item_lines.append("    public class VB_ItemData : ScriptableObject")
    item_lines.append("    {")
    item_lines.append('        [Header("Identity")]')
    item_lines.append("        public string itemId;")
    item_lines.append("        public string displayName;")
    item_lines.append("        [TextArea] public string description;")
    item_lines.append("        public Sprite icon;")
    item_lines.append("        public string iconPath;")
    item_lines.append("")
    item_lines.append('        [Header("Classification")]')
    item_lines.append("        public ItemType itemType;")
    item_lines.append("        public ItemRarity rarity;")
    item_lines.append("        public string itemCategory;")
    item_lines.append("        public EquipmentSlot equipSlot;")
    item_lines.append("")
    item_lines.append('        [Header("Economy")]')
    item_lines.append("        public int buyPrice;")
    item_lines.append("        public int sellPrice;")
    item_lines.append("        public bool isStackable;")
    item_lines.append("        public int maxStack = 99;")
    item_lines.append("")
    item_lines.append('        [Header("Stats")]')
    item_lines.append("        public StatBuff[] statBuffs;")
    item_lines.append("        public float corruptionChange;")
    item_lines.append("        public float pathChange;")
    item_lines.append("    }")
    item_lines.append("}")
    item_so_cs = "\n".join(item_lines)

    # ----- Inventory MonoBehaviour -----
    inv_lines: list[str] = []
    inv_lines.append("using System;")
    inv_lines.append("using System.Collections.Generic;")
    inv_lines.append("using UnityEngine;")
    inv_lines.append("using VeilBreakers.Core;")
    inv_lines.append("")
    inv_lines.append("namespace " + ns)
    inv_lines.append("{")

    # InventorySlot
    inv_lines.append("    /// <summary>A single slot in the inventory grid.</summary>")
    inv_lines.append("    [Serializable]")
    inv_lines.append("    public class InventorySlot")
    inv_lines.append("    {")
    inv_lines.append("        public VB_ItemData item;")
    inv_lines.append("        public int quantity;")
    inv_lines.append("")
    inv_lines.append("        public bool IsEmpty => item == null;")
    inv_lines.append("    }")
    inv_lines.append("")

    # StorageContainer
    inv_lines.append("    /// <summary>External storage container (chests, stashes).</summary>")
    inv_lines.append("    [Serializable]")
    inv_lines.append("    public class StorageContainer")
    inv_lines.append("    {")
    inv_lines.append("        public string containerId;")
    inv_lines.append("        public int width = 6;")
    inv_lines.append("        public int height = 4;")
    inv_lines.append("        public InventorySlot[] slots;")
    inv_lines.append("")
    inv_lines.append("        public StorageContainer(string id, int w, int h)")
    inv_lines.append("        {")
    inv_lines.append("            containerId = id;")
    inv_lines.append("            width = w;")
    inv_lines.append("            height = h;")
    inv_lines.append("            slots = new InventorySlot[w * h];")
    inv_lines.append("            for (int i = 0; i < slots.Length; i++)")
    inv_lines.append("                slots[i] = new InventorySlot();")
    inv_lines.append("        }")
    inv_lines.append("    }")
    inv_lines.append("")

    # VB_InventorySystem
    inv_lines.append("    /// <summary>")
    inv_lines.append("    /// Grid-based inventory system with equipment slots and storage.")
    inv_lines.append("    /// Uses EventBus for cross-system notifications.")
    inv_lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    inv_lines.append("    /// </summary>")
    inv_lines.append("    public class VB_InventorySystem : MonoBehaviour")
    inv_lines.append("    {")
    inv_lines.append("        public static VB_InventorySystem Instance { get; private set; }")
    inv_lines.append("")
    inv_lines.append('        [Header("Grid Settings")]')
    inv_lines.append("        public int gridWidth = " + str(grid_width) + ";")
    inv_lines.append("        public int gridHeight = " + str(grid_height) + ";")
    inv_lines.append("")
    inv_lines.append("        private InventorySlot[] _gridSlots;")
    inv_lines.append("        private Dictionary<EquipmentSlot, InventorySlot> _equipmentSlots;")
    inv_lines.append("        private StorageContainer _activeStorage;")
    inv_lines.append("")
    inv_lines.append("        /// <summary>Fired when any inventory change occurs.</summary>")
    inv_lines.append("        public event Action OnInventoryChanged;")
    inv_lines.append("        /// <summary>Fired when equipment changes.</summary>")
    inv_lines.append("        public event Action<EquipmentSlot, VB_ItemData> OnEquipmentChanged;")
    inv_lines.append("")

    # Awake
    inv_lines.append("        private void Awake()")
    inv_lines.append("        {")
    inv_lines.append("            if (Instance != null && Instance != this) { Destroy(gameObject); return; }")
    inv_lines.append("            Instance = this;")
    inv_lines.append("            DontDestroyOnLoad(gameObject);")
    inv_lines.append("            _gridSlots = new InventorySlot[gridWidth * gridHeight];")
    inv_lines.append("            for (int i = 0; i < _gridSlots.Length; i++)")
    inv_lines.append("                _gridSlots[i] = new InventorySlot();")
    inv_lines.append("            _equipmentSlots = new Dictionary<EquipmentSlot, InventorySlot>();")
    inv_lines.append("            foreach (EquipmentSlot slot in Enum.GetValues(typeof(EquipmentSlot)))")
    inv_lines.append("                _equipmentSlots[slot] = new InventorySlot();")
    inv_lines.append("        }")
    inv_lines.append("")

    # AddItem
    inv_lines.append("        /// <summary>Add an item to the first available grid slot.</summary>")
    inv_lines.append("        public bool AddItem(VB_ItemData item, int quantity = 1)")
    inv_lines.append("        {")
    inv_lines.append("            if (item == null || quantity <= 0) return false;")
    inv_lines.append("            // Try stacking first")
    inv_lines.append("            if (item.isStackable)")
    inv_lines.append("            {")
    inv_lines.append("                for (int i = 0; i < _gridSlots.Length; i++)")
    inv_lines.append("                {")
    inv_lines.append("                    if (_gridSlots[i].item == item && _gridSlots[i].quantity < item.maxStack)")
    inv_lines.append("                    {")
    inv_lines.append("                        int space = item.maxStack - _gridSlots[i].quantity;")
    inv_lines.append("                        int toAdd = Mathf.Min(quantity, space);")
    inv_lines.append("                        _gridSlots[i].quantity += toAdd;")
    inv_lines.append("                        quantity -= toAdd;")
    inv_lines.append("                        if (quantity <= 0) { NotifyChanged(); return true; }")
    inv_lines.append("                    }")
    inv_lines.append("                }")
    inv_lines.append("            }")
    inv_lines.append("            // Place in empty slot(s), respecting maxStack")
    inv_lines.append("            for (int i = 0; i < _gridSlots.Length; i++)")
    inv_lines.append("            {")
    inv_lines.append("                if (_gridSlots[i].IsEmpty)")
    inv_lines.append("                {")
    inv_lines.append("                    int cap = item.isStackable ? Mathf.Min(quantity, item.maxStack) : 1;")
    inv_lines.append("                    _gridSlots[i].item = item;")
    inv_lines.append("                    _gridSlots[i].quantity = cap;")
    inv_lines.append("                    quantity -= cap;")
    inv_lines.append("                    if (quantity <= 0) { NotifyChanged(); return true; }")
    inv_lines.append("                }")
    inv_lines.append("            }")
    inv_lines.append("            Debug.LogWarning(\"[VB_InventorySystem] Inventory full.\");")
    inv_lines.append("            return false;")
    inv_lines.append("        }")
    inv_lines.append("")

    # RemoveItem
    inv_lines.append("        /// <summary>Remove quantity of an item from inventory.</summary>")
    inv_lines.append("        public bool RemoveItem(VB_ItemData item, int quantity = 1)")
    inv_lines.append("        {")
    inv_lines.append("            if (item == null || quantity <= 0) return false;")
    inv_lines.append("            int remaining = quantity;")
    inv_lines.append("            for (int i = 0; i < _gridSlots.Length && remaining > 0; i++)")
    inv_lines.append("            {")
    inv_lines.append("                if (_gridSlots[i].item == item)")
    inv_lines.append("                {")
    inv_lines.append("                    int remove = Mathf.Min(remaining, _gridSlots[i].quantity);")
    inv_lines.append("                    _gridSlots[i].quantity -= remove;")
    inv_lines.append("                    remaining -= remove;")
    inv_lines.append("                    if (_gridSlots[i].quantity <= 0)")
    inv_lines.append("                    {")
    inv_lines.append("                        _gridSlots[i].item = null;")
    inv_lines.append("                        _gridSlots[i].quantity = 0;")
    inv_lines.append("                    }")
    inv_lines.append("                }")
    inv_lines.append("            }")
    inv_lines.append("            if (remaining <= 0) { NotifyChanged(); return true; }")
    inv_lines.append("            return false;")
    inv_lines.append("        }")
    inv_lines.append("")

    # Equip
    inv_lines.append("        /// <summary>Equip an item to its designated slot.</summary>")
    inv_lines.append("        public bool Equip(VB_ItemData item)")
    inv_lines.append("        {")
    inv_lines.append("            if (item == null) return false;")
    inv_lines.append("            EquipmentSlot slot = item.equipSlot;")
    inv_lines.append("            if (_equipmentSlots.ContainsKey(slot))")
    inv_lines.append("            {")
    inv_lines.append("                // Remove new item from inventory first")
    inv_lines.append("                if (!RemoveItem(item, 1)) return false;")
    inv_lines.append("")
    inv_lines.append("                VB_ItemData previous = _equipmentSlots[slot].item;")
    inv_lines.append("                if (previous != null)")
    inv_lines.append("                {")
    inv_lines.append("                    if (!AddItem(previous))")
    inv_lines.append("                    {")
    inv_lines.append("                        // Inventory full -- re-equip old item and return new item to inventory")
    inv_lines.append("                        _equipmentSlots[slot].item = previous;")
    inv_lines.append("                        _equipmentSlots[slot].quantity = 1;")
    inv_lines.append("                        AddItem(item);")
    inv_lines.append("                        return false;")
    inv_lines.append("                    }")
    inv_lines.append("                }")
    inv_lines.append("                _equipmentSlots[slot].item = item;")
    inv_lines.append("                _equipmentSlots[slot].quantity = 1;")
    inv_lines.append("                OnEquipmentChanged?.Invoke(slot, item);")
    inv_lines.append("                return true;")
    inv_lines.append("            }")
    inv_lines.append("            return false;")
    inv_lines.append("        }")
    inv_lines.append("")

    # Unequip
    inv_lines.append("        /// <summary>Unequip an item and return it to inventory.</summary>")
    inv_lines.append("        public bool Unequip(EquipmentSlot slot)")
    inv_lines.append("        {")
    inv_lines.append("            if (!_equipmentSlots.ContainsKey(slot)) return false;")
    inv_lines.append("            VB_ItemData item = _equipmentSlots[slot].item;")
    inv_lines.append("            if (item == null) return false;")
    inv_lines.append("            if (!AddItem(item)) return false;")
    inv_lines.append("            _equipmentSlots[slot].item = null;")
    inv_lines.append("            _equipmentSlots[slot].quantity = 0;")
    inv_lines.append("            OnEquipmentChanged?.Invoke(slot, null);")
    inv_lines.append("            return true;")
    inv_lines.append("        }")
    inv_lines.append("")

    # GetSlot / GetEquipped / HasItem / GetItemCount
    inv_lines.append("        /// <summary>Get a grid slot by index.</summary>")
    inv_lines.append("        public InventorySlot GetSlot(int index)")
    inv_lines.append("        {")
    inv_lines.append("            if (index < 0 || index >= _gridSlots.Length) return null;")
    inv_lines.append("            return _gridSlots[index];")
    inv_lines.append("        }")
    inv_lines.append("")
    inv_lines.append("        /// <summary>Get the equipped item in a given slot.</summary>")
    inv_lines.append("        public VB_ItemData GetEquipped(EquipmentSlot slot)")
    inv_lines.append("        {")
    inv_lines.append("            return _equipmentSlots.ContainsKey(slot) ? _equipmentSlots[slot].item : null;")
    inv_lines.append("        }")
    inv_lines.append("")
    inv_lines.append("        /// <summary>Check if the inventory contains at least N of an item.</summary>")
    inv_lines.append("        public bool HasItem(VB_ItemData item, int quantity = 1)")
    inv_lines.append("        {")
    inv_lines.append("            return GetItemCount(item) >= quantity;")
    inv_lines.append("        }")
    inv_lines.append("")
    inv_lines.append("        /// <summary>Count total quantity of an item across all grid slots.</summary>")
    inv_lines.append("        public int GetItemCount(VB_ItemData item)")
    inv_lines.append("        {")
    inv_lines.append("            int count = 0;")
    inv_lines.append("            for (int i = 0; i < _gridSlots.Length; i++)")
    inv_lines.append("                if (_gridSlots[i].item == item) count += _gridSlots[i].quantity;")
    inv_lines.append("            return count;")
    inv_lines.append("        }")
    inv_lines.append("")

    # OpenStorage / CloseStorage
    inv_lines.append("        /// <summary>Open an external storage container.</summary>")
    inv_lines.append("        public void OpenStorage(StorageContainer container)")
    inv_lines.append("        {")
    inv_lines.append("            _activeStorage = container;")
    inv_lines.append('            OnStorageOpened?.Invoke(container);')
    inv_lines.append("        }")
    inv_lines.append("")
    inv_lines.append("        /// <summary>Close the active storage container.</summary>")
    inv_lines.append("        public void CloseStorage()")
    inv_lines.append("        {")
    inv_lines.append("            _activeStorage = null;")
    inv_lines.append('            OnStorageClosed?.Invoke();')
    inv_lines.append("        }")
    inv_lines.append("")

    # MoveItem (drag-and-drop support)
    inv_lines.append("        /// <summary>Move an item from one grid slot to another (drag-and-drop).</summary>")
    inv_lines.append("        public void MoveItem(int fromIndex, int toIndex)")
    inv_lines.append("        {")
    inv_lines.append("            if (fromIndex < 0 || fromIndex >= _gridSlots.Length) return;")
    inv_lines.append("            if (toIndex < 0 || toIndex >= _gridSlots.Length) return;")
    inv_lines.append("            var temp = _gridSlots[toIndex];")
    inv_lines.append("            _gridSlots[toIndex] = _gridSlots[fromIndex];")
    inv_lines.append("            _gridSlots[fromIndex] = temp;")
    inv_lines.append("            NotifyChanged();")
    inv_lines.append("        }")
    inv_lines.append("")

    # NotifyChanged
    inv_lines.append("        private void NotifyChanged()")
    inv_lines.append("        {")
    inv_lines.append("            OnInventoryChanged?.Invoke();")
    inv_lines.append("        }")
    inv_lines.append("    }")
    inv_lines.append("}")
    inventory_cs = "\n".join(inv_lines)

    # ----- UXML -----
    uxml_lines: list[str] = []
    uxml_lines.append('<ui:UXML xmlns:ui="UnityEngine.UIElements"')
    uxml_lines.append('         xmlns:uie="UnityEditor.UIElements">')
    uxml_lines.append('    <ui:VisualElement name="inventory-root" class="inventory-root">')
    uxml_lines.append('        <ui:VisualElement name="equipment-panel" class="equipment-panel">')
    uxml_lines.append('            <ui:Label text="Equipment" class="panel-title" />')
    for slot in equipment_slots:
        safe = sanitize_cs_identifier(slot)
        uxml_lines.append('            <ui:VisualElement name="equip-slot-' + safe.lower() + '" class="equip-slot">')
        uxml_lines.append('                <ui:Label text="' + sanitize_cs_string(slot) + '" class="slot-label" />')
        uxml_lines.append('                <ui:VisualElement name="equip-icon-' + safe.lower() + '" class="item-icon" />')
        uxml_lines.append("            </ui:VisualElement>")
    uxml_lines.append("        </ui:VisualElement>")
    uxml_lines.append('        <ui:VisualElement name="grid-panel" class="grid-panel">')
    uxml_lines.append('            <ui:Label text="Inventory" class="panel-title" />')
    uxml_lines.append('            <ui:VisualElement name="grid-container" class="grid-container">')
    for row in range(grid_height):
        for col in range(grid_width):
            idx = row * grid_width + col
            uxml_lines.append('                <ui:VisualElement name="slot-' + str(idx) + '" class="grid-slot drag-target" />')
    uxml_lines.append("            </ui:VisualElement>")
    uxml_lines.append("        </ui:VisualElement>")
    uxml_lines.append('        <ui:VisualElement name="item-tooltip" class="item-tooltip">')
    uxml_lines.append('            <ui:Label name="tooltip-name" class="tooltip-name" />')
    uxml_lines.append('            <ui:Label name="tooltip-rarity" class="tooltip-rarity" />')
    uxml_lines.append('            <ui:Label name="tooltip-desc" class="tooltip-desc" />')
    uxml_lines.append('            <ui:Label name="tooltip-stats" class="tooltip-stats" />')
    uxml_lines.append("        </ui:VisualElement>")
    uxml_lines.append("    </ui:VisualElement>")
    uxml_lines.append("</ui:UXML>")
    uxml = "\n".join(uxml_lines)

    # ----- USS -----
    uss_lines: list[str] = []
    uss_lines.append("/* VeilBreakers Inventory - Dark Fantasy Theme */")
    uss_lines.append(".inventory-root {")
    uss_lines.append("    flex-direction: row;")
    uss_lines.append("    background-color: rgba(15, 10, 10, 0.95);")
    uss_lines.append("    padding: 12px;")
    uss_lines.append("    border-color: rgb(80, 50, 30);")
    uss_lines.append("    border-width: 2px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".equipment-panel {")
    uss_lines.append("    width: 200px;")
    uss_lines.append("    margin-right: 12px;")
    uss_lines.append("    background-color: rgba(25, 18, 14, 0.9);")
    uss_lines.append("    border-color: rgb(60, 40, 25);")
    uss_lines.append("    border-width: 1px;")
    uss_lines.append("    padding: 8px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".panel-title {")
    uss_lines.append("    font-size: 16px;")
    uss_lines.append("    color: rgb(200, 170, 120);")
    uss_lines.append("    -unity-font-style: bold;")
    uss_lines.append("    margin-bottom: 8px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".equip-slot {")
    uss_lines.append("    flex-direction: row;")
    uss_lines.append("    height: 48px;")
    uss_lines.append("    margin-bottom: 4px;")
    uss_lines.append("    background-color: rgba(40, 30, 20, 0.8);")
    uss_lines.append("    border-color: rgb(70, 50, 30);")
    uss_lines.append("    border-width: 1px;")
    uss_lines.append("    padding: 4px;")
    uss_lines.append("    align-items: center;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".slot-label {")
    uss_lines.append("    color: rgb(160, 140, 100);")
    uss_lines.append("    font-size: 11px;")
    uss_lines.append("    width: 80px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".item-icon {")
    uss_lines.append("    width: 40px;")
    uss_lines.append("    height: 40px;")
    uss_lines.append("    background-color: rgba(50, 35, 25, 0.6);")
    uss_lines.append("    border-color: rgb(90, 60, 35);")
    uss_lines.append("    border-width: 1px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".grid-panel {")
    uss_lines.append("    flex-grow: 1;")
    uss_lines.append("    background-color: rgba(25, 18, 14, 0.9);")
    uss_lines.append("    border-color: rgb(60, 40, 25);")
    uss_lines.append("    border-width: 1px;")
    uss_lines.append("    padding: 8px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".grid-container {")
    uss_lines.append("    flex-direction: row;")
    uss_lines.append("    flex-wrap: wrap;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".grid-slot {")
    uss_lines.append("    width: 48px;")
    uss_lines.append("    height: 48px;")
    uss_lines.append("    margin: 2px;")
    uss_lines.append("    background-color: rgba(40, 30, 20, 0.7);")
    uss_lines.append("    border-color: rgb(70, 50, 30);")
    uss_lines.append("    border-width: 1px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".grid-slot:hover {")
    uss_lines.append("    border-color: rgb(200, 170, 120);")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".drag-target {")
    uss_lines.append("    /* Supports drag-and-drop via PointerManipulator */")
    uss_lines.append("    cursor: initial;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".item-tooltip {")
    uss_lines.append("    position: absolute;")
    uss_lines.append("    background-color: rgba(10, 8, 6, 0.95);")
    uss_lines.append("    border-color: rgb(120, 90, 50);")
    uss_lines.append("    border-width: 1px;")
    uss_lines.append("    padding: 8px;")
    uss_lines.append("    display: none;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".tooltip-name { font-size: 14px; color: rgb(220, 190, 130); -unity-font-style: bold; }")
    uss_lines.append(".tooltip-rarity { font-size: 11px; color: rgb(160, 130, 90); }")
    uss_lines.append(".tooltip-desc { font-size: 12px; color: rgb(180, 160, 120); margin-top: 4px; }")
    uss_lines.append(".tooltip-stats { font-size: 11px; color: rgb(140, 200, 140); margin-top: 4px; }")
    uss = "\n".join(uss_lines)

    return (item_so_cs, inventory_cs, uxml, uss)


# ---------------------------------------------------------------------------
# GAME-03: Dialogue system (YarnSpinner-compatible nodes + UI)
# ---------------------------------------------------------------------------


def generate_dialogue_system_script(
    namespace: str = "VeilBreakers.Content",
) -> tuple[str, str, str, str]:
    """Generate C# for a dialogue system with YarnSpinner-compatible nodes.

    Returns:
        (dialogue_data_cs, dialogue_system_cs, uxml, uss) tuple.
    """
    ns = _safe_namespace(namespace)

    # ----- Dialogue Data SO -----
    data_lines: list[str] = []
    data_lines.append("using System;")
    data_lines.append("using System.Collections.Generic;")
    data_lines.append("using UnityEngine;")
    data_lines.append("")
    data_lines.append("namespace " + ns)
    data_lines.append("{")

    # DialogueChoice
    data_lines.append("    /// <summary>A single dialogue choice.</summary>")
    data_lines.append("    [Serializable]")
    data_lines.append("    public class DialogueChoice")
    data_lines.append("    {")
    data_lines.append("        public string text;")
    data_lines.append("        public string condition;")
    data_lines.append("        public string nextNodeId;")
    data_lines.append("        public string command;")
    data_lines.append("    }")
    data_lines.append("")

    # DialogueLine
    data_lines.append("    /// <summary>A single line of dialogue.</summary>")
    data_lines.append("    [Serializable]")
    data_lines.append("    public class DialogueLine")
    data_lines.append("    {")
    data_lines.append("        public string speaker;")
    data_lines.append("        public string text;")
    data_lines.append("        public float delay;")
    data_lines.append("        public string emotion;")
    data_lines.append("    }")
    data_lines.append("")

    # VB_DialogueNode SO
    data_lines.append("    /// <summary>")
    data_lines.append("    /// ScriptableObject for a dialogue conversation node.")
    data_lines.append("    /// Supports YarnSpinner-compatible export (title:/---/===/-> choices/&lt;&lt;commands&gt;&gt;).")
    data_lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    data_lines.append("    /// </summary>")
    data_lines.append('    [CreateAssetMenu(fileName = "NewDialogue", menuName = "VeilBreakers/Dialogue Node")]')
    data_lines.append("    public class VB_DialogueNode : ScriptableObject")
    data_lines.append("    {")
    data_lines.append("        public string nodeId;")
    data_lines.append("        public string speaker;")
    data_lines.append("        public Sprite speakerPortrait;")
    data_lines.append("        public List<DialogueLine> lines = new List<DialogueLine>();")
    data_lines.append("        public List<DialogueChoice> choices = new List<DialogueChoice>();")
    data_lines.append("        public string nextNodeId;")
    data_lines.append("")

    # YarnSpinner export
    data_lines.append("        /// <summary>Export this node to YarnSpinner-compatible format.</summary>")
    data_lines.append("        public string ToYarnSpinnerNode()")
    data_lines.append("        {")
    data_lines.append("            var sb = new System.Text.StringBuilder();")
    data_lines.append('            sb.AppendLine("title: " + nodeId);')
    data_lines.append('            sb.AppendLine("---");')
    data_lines.append("            foreach (var line in lines)")
    data_lines.append("            {")
    data_lines.append('                sb.AppendLine(line.speaker + ": " + line.text);')
    data_lines.append("            }")
    data_lines.append("            foreach (var choice in choices)")
    data_lines.append("            {")
    data_lines.append('                sb.AppendLine("-> " + choice.text);')
    data_lines.append("                if (!string.IsNullOrEmpty(choice.command))")
    data_lines.append('                    sb.AppendLine("    <<" + choice.command + ">>");')
    data_lines.append("                if (!string.IsNullOrEmpty(choice.nextNodeId))")
    data_lines.append('                    sb.AppendLine("    <<jump " + choice.nextNodeId + ">>");')
    data_lines.append("            }")
    data_lines.append('            sb.AppendLine("===");')
    data_lines.append("            return sb.ToString();")
    data_lines.append("        }")
    data_lines.append("    }")
    data_lines.append("}")
    dialogue_data_cs = "\n".join(data_lines)

    # ----- Dialogue System MonoBehaviour -----
    sys_lines: list[str] = []
    sys_lines.append("using System;")
    sys_lines.append("using System.Collections.Generic;")
    sys_lines.append("using UnityEngine;")
    sys_lines.append("using VeilBreakers.Core;")
    sys_lines.append("")
    sys_lines.append("namespace " + ns)
    sys_lines.append("{")

    # NPC Interaction trigger
    sys_lines.append("    /// <summary>NPC interaction trigger for initiating dialogue.</summary>")
    sys_lines.append("    public class VB_NPCDialogueTrigger : MonoBehaviour")
    sys_lines.append("    {")
    sys_lines.append("        public VB_DialogueNode startNode;")
    sys_lines.append("        public float interactionRange = 2.5f;")
    sys_lines.append("")
    sys_lines.append("        /// <summary>Called when the player interacts with this NPC.</summary>")
    sys_lines.append("        public void Interact()")
    sys_lines.append("        {")
    sys_lines.append("            if (startNode != null)")
    sys_lines.append("                VB_DialogueSystem.Instance.StartDialogue(startNode);")
    sys_lines.append("        }")
    sys_lines.append("    }")
    sys_lines.append("")

    # VB_DialogueSystem
    sys_lines.append("    /// <summary>")
    sys_lines.append("    /// Dialogue system with conversation flow, condition checking,")
    sys_lines.append("    /// and EventBus integration.")
    sys_lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    sys_lines.append("    /// </summary>")
    sys_lines.append("    public class VB_DialogueSystem : MonoBehaviour")
    sys_lines.append("    {")
    sys_lines.append("        public static VB_DialogueSystem Instance { get; private set; }")
    sys_lines.append("")
    sys_lines.append("        private VB_DialogueNode _currentNode;")
    sys_lines.append("        private int _currentLineIndex;")
    sys_lines.append("        private bool _isActive;")
    sys_lines.append("")
    sys_lines.append("        public event Action<VB_DialogueNode> OnDialogueStarted;")
    sys_lines.append("        public event Action OnDialogueEnded;")
    sys_lines.append("        public event Action<DialogueLine> OnLineAdvanced;")
    sys_lines.append("        public event Action<List<DialogueChoice>> OnChoicesPresented;")
    sys_lines.append("")

    # Awake
    sys_lines.append("        private void Awake()")
    sys_lines.append("        {")
    sys_lines.append("            if (Instance != null && Instance != this) { Destroy(gameObject); return; }")
    sys_lines.append("            Instance = this;")
    sys_lines.append("        }")
    sys_lines.append("")

    # StartDialogue
    sys_lines.append("        /// <summary>Begin a dialogue conversation.</summary>")
    sys_lines.append("        public void StartDialogue(VB_DialogueNode node)")
    sys_lines.append("        {")
    sys_lines.append("            if (node == null || _isActive) return;")
    sys_lines.append("            _currentNode = node;")
    sys_lines.append("            _currentLineIndex = 0;")
    sys_lines.append("            _isActive = true;")
    sys_lines.append("            OnDialogueStarted?.Invoke(node);")
    sys_lines.append("            if (_currentNode.lines.Count > 0)")
    sys_lines.append("                OnLineAdvanced?.Invoke(_currentNode.lines[0]);")
    sys_lines.append("        }")
    sys_lines.append("")

    # AdvanceLine
    sys_lines.append("        /// <summary>Advance to the next dialogue line.</summary>")
    sys_lines.append("        public void AdvanceLine()")
    sys_lines.append("        {")
    sys_lines.append("            if (!_isActive || _currentNode == null) return;")
    sys_lines.append("            _currentLineIndex++;")
    sys_lines.append("            if (_currentLineIndex < _currentNode.lines.Count)")
    sys_lines.append("            {")
    sys_lines.append("                OnLineAdvanced?.Invoke(_currentNode.lines[_currentLineIndex]);")
    sys_lines.append("            }")
    sys_lines.append("            else if (_currentNode.choices.Count > 0)")
    sys_lines.append("            {")
    sys_lines.append("                var available = FilterChoicesByCondition(_currentNode.choices);")
    sys_lines.append("                OnChoicesPresented?.Invoke(available);")
    sys_lines.append("            }")
    sys_lines.append("            else if (!string.IsNullOrEmpty(_currentNode.nextNodeId))")
    sys_lines.append("            {")
    sys_lines.append("                // Auto-advance to next node (requires lookup)")
    sys_lines.append("                EndDialogue();")
    sys_lines.append("            }")
    sys_lines.append("            else")
    sys_lines.append("            {")
    sys_lines.append("                EndDialogue();")
    sys_lines.append("            }")
    sys_lines.append("        }")
    sys_lines.append("")

    # SelectChoice
    sys_lines.append("        /// <summary>Select a dialogue choice by index.</summary>")
    sys_lines.append("        public void SelectChoice(int choiceIndex)")
    sys_lines.append("        {")
    sys_lines.append("            if (!_isActive || _currentNode == null) return;")
    sys_lines.append("            if (choiceIndex < 0 || choiceIndex >= _currentNode.choices.Count) return;")
    sys_lines.append("            var choice = _currentNode.choices[choiceIndex];")
    sys_lines.append('            OnDialogueChoiceMade?.Invoke(choice.text, _currentNode.nodeId);')
    sys_lines.append("")
    sys_lines.append("            // Navigate to the choice's next node instead of ending dialogue")
    sys_lines.append("            if (!string.IsNullOrEmpty(choice.nextNodeId))")
    sys_lines.append("            {")
    sys_lines.append('                OnDialogueNavigate?.Invoke(choice.nextNodeId);')
    sys_lines.append("            }")
    sys_lines.append("            else")
    sys_lines.append("            {")
    sys_lines.append("                EndDialogue();")
    sys_lines.append("            }")
    sys_lines.append("        }")
    sys_lines.append("")

    # EndDialogue
    sys_lines.append("        /// <summary>End the current dialogue.</summary>")
    sys_lines.append("        public void EndDialogue()")
    sys_lines.append("        {")
    sys_lines.append("            _isActive = false;")
    sys_lines.append("            _currentNode = null;")
    sys_lines.append("            _currentLineIndex = 0;")
    sys_lines.append("            OnDialogueEnded?.Invoke();")
    sys_lines.append("        }")
    sys_lines.append("")

    # FilterChoicesByCondition
    sys_lines.append("        /// <summary>Filter choices based on conditions (quest state, inventory, reputation).</summary>")
    sys_lines.append("        private List<DialogueChoice> FilterChoicesByCondition(List<DialogueChoice> choices)")
    sys_lines.append("        {")
    sys_lines.append("            var result = new List<DialogueChoice>();")
    sys_lines.append("            foreach (var c in choices)")
    sys_lines.append("            {")
    sys_lines.append("                if (string.IsNullOrEmpty(c.condition) || EvaluateCondition(c.condition))")
    sys_lines.append("                    result.Add(c);")
    sys_lines.append("            }")
    sys_lines.append("            return result;")
    sys_lines.append("        }")
    sys_lines.append("")
    sys_lines.append("        /// <summary>Evaluate a condition string (quest_complete:X, has_item:X, reputation:X:N).</summary>")
    sys_lines.append("        private bool EvaluateCondition(string condition)")
    sys_lines.append("        {")
    sys_lines.append("            // Extensible condition system -- plug in quest/inventory/reputation checks")
    sys_lines.append('            Debug.Log("[VB_DialogueSystem] Evaluating condition: " + condition);')
    sys_lines.append("            return true; // Default: all conditions pass")
    sys_lines.append("        }")

    sys_lines.append("    }")
    sys_lines.append("}")
    dialogue_system_cs = "\n".join(sys_lines)

    # ----- UXML -----
    uxml_lines: list[str] = []
    uxml_lines.append('<ui:UXML xmlns:ui="UnityEngine.UIElements">')
    uxml_lines.append('    <ui:VisualElement name="dialogue-root" class="dialogue-root">')
    uxml_lines.append('        <ui:VisualElement name="speaker-panel" class="speaker-panel">')
    uxml_lines.append('            <ui:VisualElement name="speaker-portrait" class="speaker-portrait" />')
    uxml_lines.append('            <ui:Label name="speaker-name" class="speaker-name" text="Speaker" />')
    uxml_lines.append("        </ui:VisualElement>")
    uxml_lines.append('        <ui:VisualElement name="text-area" class="text-area">')
    uxml_lines.append('            <ui:Label name="dialogue-text" class="dialogue-text" text="..." />')
    uxml_lines.append("        </ui:VisualElement>")
    uxml_lines.append('        <ui:VisualElement name="choice-container" class="choice-container">')
    uxml_lines.append('            <ui:Button name="choice-0" class="choice-button" text="Choice 1" />')
    uxml_lines.append('            <ui:Button name="choice-1" class="choice-button" text="Choice 2" />')
    uxml_lines.append('            <ui:Button name="choice-2" class="choice-button" text="Choice 3" />')
    uxml_lines.append('            <ui:Button name="choice-3" class="choice-button" text="Choice 4" />')
    uxml_lines.append("        </ui:VisualElement>")
    uxml_lines.append('        <ui:Button name="continue-button" class="continue-button" text="Continue" />')
    uxml_lines.append("    </ui:VisualElement>")
    uxml_lines.append("</ui:UXML>")
    dialogue_uxml = "\n".join(uxml_lines)

    # ----- USS -----
    uss_lines: list[str] = []
    uss_lines.append("/* VeilBreakers Dialogue - Dark Fantasy Theme */")
    uss_lines.append(".dialogue-root {")
    uss_lines.append("    position: absolute;")
    uss_lines.append("    bottom: 0;")
    uss_lines.append("    left: 0;")
    uss_lines.append("    right: 0;")
    uss_lines.append("    height: 220px;")
    uss_lines.append("    background-color: rgba(12, 8, 6, 0.92);")
    uss_lines.append("    border-top-width: 2px;")
    uss_lines.append("    border-color: rgb(100, 70, 40);")
    uss_lines.append("    padding: 16px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".speaker-panel {")
    uss_lines.append("    flex-direction: row;")
    uss_lines.append("    align-items: center;")
    uss_lines.append("    margin-bottom: 8px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".speaker-portrait {")
    uss_lines.append("    width: 64px;")
    uss_lines.append("    height: 64px;")
    uss_lines.append("    border-color: rgb(120, 90, 50);")
    uss_lines.append("    border-width: 2px;")
    uss_lines.append("    margin-right: 12px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".speaker-name {")
    uss_lines.append("    font-size: 18px;")
    uss_lines.append("    color: rgb(220, 190, 130);")
    uss_lines.append("    -unity-font-style: bold;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".text-area {")
    uss_lines.append("    flex-grow: 1;")
    uss_lines.append("    margin-bottom: 8px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".dialogue-text {")
    uss_lines.append("    font-size: 14px;")
    uss_lines.append("    color: rgb(200, 185, 155);")
    uss_lines.append("    white-space: normal;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".choice-container {")
    uss_lines.append("    flex-direction: column;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".choice-button {")
    uss_lines.append("    height: 32px;")
    uss_lines.append("    margin-bottom: 4px;")
    uss_lines.append("    background-color: rgba(40, 28, 18, 0.85);")
    uss_lines.append("    color: rgb(200, 180, 140);")
    uss_lines.append("    border-color: rgb(80, 55, 30);")
    uss_lines.append("    border-width: 1px;")
    uss_lines.append("    font-size: 13px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".choice-button:hover {")
    uss_lines.append("    background-color: rgba(70, 50, 30, 0.9);")
    uss_lines.append("    border-color: rgb(200, 170, 120);")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".continue-button {")
    uss_lines.append("    align-self: flex-end;")
    uss_lines.append("    width: 120px;")
    uss_lines.append("    height: 30px;")
    uss_lines.append("    background-color: rgba(50, 35, 20, 0.9);")
    uss_lines.append("    color: rgb(200, 180, 140);")
    uss_lines.append("    border-color: rgb(100, 70, 40);")
    uss_lines.append("    border-width: 1px;")
    uss_lines.append("}")
    dialogue_uss = "\n".join(uss_lines)

    return (dialogue_data_cs, dialogue_system_cs, dialogue_uxml, dialogue_uss)


# ---------------------------------------------------------------------------
# GAME-04: Quest system (state machine + objective tracker + log UI)
# ---------------------------------------------------------------------------


def generate_quest_system_script(
    namespace: str = "VeilBreakers.Content",
) -> tuple[str, str, str, str]:
    """Generate C# for a quest system with state machine and objective tracker.

    Returns:
        (quest_data_cs, quest_system_cs, uxml, uss) tuple.
    """
    ns = _safe_namespace(namespace)

    # ----- Quest Data SO -----
    qd_lines: list[str] = []
    qd_lines.append("using System;")
    qd_lines.append("using System.Collections.Generic;")
    qd_lines.append("using UnityEngine;")
    qd_lines.append("")
    qd_lines.append("namespace " + ns)
    qd_lines.append("{")

    # QuestState enum
    qd_lines.append("    /// <summary>Quest state machine states.</summary>")
    qd_lines.append("    public enum QuestState")
    qd_lines.append("    {")
    qd_lines.append("        NotStarted,")
    qd_lines.append("        Active,")
    qd_lines.append("        Complete,")
    qd_lines.append("        TurnedIn")
    qd_lines.append("    }")
    qd_lines.append("")

    # QuestType enum
    qd_lines.append("    /// <summary>Quest classification.</summary>")
    qd_lines.append("    public enum QuestType")
    qd_lines.append("    {")
    qd_lines.append("        Main,")
    qd_lines.append("        Side,")
    qd_lines.append("        Daily")
    qd_lines.append("    }")
    qd_lines.append("")

    # ObjectiveType enum
    qd_lines.append("    /// <summary>Supported objective types.</summary>")
    qd_lines.append("    public enum ObjectiveType")
    qd_lines.append("    {")
    qd_lines.append("        Kill,")
    qd_lines.append("        Collect,")
    qd_lines.append("        TalkTo,")
    qd_lines.append("        ReachLocation")
    qd_lines.append("    }")
    qd_lines.append("")

    # QuestObjective
    qd_lines.append("    /// <summary>A single quest objective.</summary>")
    qd_lines.append("    [Serializable]")
    qd_lines.append("    public class QuestObjective")
    qd_lines.append("    {")
    qd_lines.append("        public string description;")
    qd_lines.append("        public ObjectiveType objectiveType;")
    qd_lines.append("        public string targetId;")
    qd_lines.append("        public int requiredCount = 1;")
    qd_lines.append("        [HideInInspector] public int currentCount;")
    qd_lines.append("        public bool IsComplete => currentCount >= requiredCount;")
    qd_lines.append("    }")
    qd_lines.append("")

    # QuestReward
    qd_lines.append("    /// <summary>Quest reward definition.</summary>")
    qd_lines.append("    [Serializable]")
    qd_lines.append("    public class QuestReward")
    qd_lines.append("    {")
    qd_lines.append("        public int experiencePoints;")
    qd_lines.append("        public int gold;")
    qd_lines.append("        public VB_ItemData[] rewardItems;")
    qd_lines.append("    }")
    qd_lines.append("")

    # VB_QuestData SO
    qd_lines.append("    /// <summary>")
    qd_lines.append("    /// ScriptableObject defining a quest with objectives, rewards, and NPC giver.")
    qd_lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    qd_lines.append("    /// </summary>")
    qd_lines.append('    [CreateAssetMenu(fileName = "NewQuest", menuName = "VeilBreakers/Quest Data")]')
    qd_lines.append("    public class VB_QuestData : ScriptableObject")
    qd_lines.append("    {")
    qd_lines.append("        public string questId;")
    qd_lines.append("        public string questName;")
    qd_lines.append("        [TextArea] public string description;")
    qd_lines.append("        public QuestType questType;")
    qd_lines.append("        public int requiredLevel;")
    qd_lines.append("        public VB_QuestData[] prerequisites;")
    qd_lines.append("        public string questGiverNpcId;")
    qd_lines.append("        public List<QuestObjective> objectives = new List<QuestObjective>();")
    qd_lines.append("        public QuestReward reward;")
    qd_lines.append("    }")
    qd_lines.append("}")
    quest_data_cs = "\n".join(qd_lines)

    # ----- Quest System MonoBehaviour -----
    qs_lines: list[str] = []
    qs_lines.append("using System;")
    qs_lines.append("using System.Collections.Generic;")
    qs_lines.append("using System.Linq;")
    qs_lines.append("using UnityEngine;")
    qs_lines.append("using VeilBreakers.Core;")
    qs_lines.append("")
    qs_lines.append("namespace " + ns)
    qs_lines.append("{")

    # QuestInstance (runtime tracking)
    qs_lines.append("    /// <summary>Runtime instance tracking a quest's progress.</summary>")
    qs_lines.append("    [Serializable]")
    qs_lines.append("    public class QuestInstance")
    qs_lines.append("    {")
    qs_lines.append("        public VB_QuestData data;")
    qs_lines.append("        public QuestState state = QuestState.NotStarted;")
    qs_lines.append("        public List<QuestObjective> trackedObjectives;")
    qs_lines.append("")
    qs_lines.append("        public QuestInstance(VB_QuestData questData)")
    qs_lines.append("        {")
    qs_lines.append("            data = questData;")
    qs_lines.append("            trackedObjectives = new List<QuestObjective>();")
    qs_lines.append("            foreach (var obj in questData.objectives)")
    qs_lines.append("            {")
    qs_lines.append("                trackedObjectives.Add(new QuestObjective")
    qs_lines.append("                {")
    qs_lines.append("                    description = obj.description,")
    qs_lines.append("                    objectiveType = obj.objectiveType,")
    qs_lines.append("                    targetId = obj.targetId,")
    qs_lines.append("                    requiredCount = obj.requiredCount,")
    qs_lines.append("                    currentCount = 0")
    qs_lines.append("                });")
    qs_lines.append("            }")
    qs_lines.append("        }")
    qs_lines.append("")
    qs_lines.append("        public bool AllObjectivesComplete => trackedObjectives.All(o => o.IsComplete);")
    qs_lines.append("    }")
    qs_lines.append("")

    # VB_QuestSystem
    qs_lines.append("    /// <summary>")
    qs_lines.append("    /// Quest management system with state machine, objective tracking,")
    qs_lines.append("    /// and reward distribution via EventBus.")
    qs_lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    qs_lines.append("    /// </summary>")
    qs_lines.append("    public class VB_QuestSystem : MonoBehaviour")
    qs_lines.append("    {")
    qs_lines.append("        public static VB_QuestSystem Instance { get; private set; }")
    qs_lines.append("")
    qs_lines.append("        private Dictionary<string, QuestInstance> _quests = new Dictionary<string, QuestInstance>();")
    qs_lines.append("")
    qs_lines.append("        public event Action<QuestInstance> OnQuestStarted;")
    qs_lines.append("        public event Action<QuestInstance> OnQuestCompleted;")
    qs_lines.append("        public event Action<QuestInstance> OnQuestTurnedIn;")
    qs_lines.append("        public event Action<QuestObjective> OnObjectiveUpdated;")
    qs_lines.append("")

    # Awake
    qs_lines.append("        private void Awake()")
    qs_lines.append("        {")
    qs_lines.append("            if (Instance != null && Instance != this) { Destroy(gameObject); return; }")
    qs_lines.append("            Instance = this;")
    qs_lines.append("        }")
    qs_lines.append("")

    # AcceptQuest
    qs_lines.append("        /// <summary>Accept and start a quest.</summary>")
    qs_lines.append("        public bool AcceptQuest(VB_QuestData questData)")
    qs_lines.append("        {")
    qs_lines.append("            if (questData == null) return false;")
    qs_lines.append("            if (_quests.ContainsKey(questData.questId)) return false;")
    qs_lines.append("            var instance = new QuestInstance(questData);")
    qs_lines.append("            instance.state = QuestState.Active;")
    qs_lines.append("            _quests[questData.questId] = instance;")
    qs_lines.append("            OnQuestStarted?.Invoke(instance);")
    qs_lines.append("            return true;")
    qs_lines.append("        }")
    qs_lines.append("")

    # UpdateObjective
    qs_lines.append("        /// <summary>Update a quest objective (event-driven).</summary>")
    qs_lines.append("        public void UpdateObjective(string questId, ObjectiveType type, string targetId, int amount = 1)")
    qs_lines.append("        {")
    qs_lines.append("            if (!_quests.ContainsKey(questId)) return;")
    qs_lines.append("            var quest = _quests[questId];")
    qs_lines.append("            if (quest.state != QuestState.Active) return;")
    qs_lines.append("            foreach (var obj in quest.trackedObjectives)")
    qs_lines.append("            {")
    qs_lines.append("                if (obj.objectiveType == type && obj.targetId == targetId && !obj.IsComplete)")
    qs_lines.append("                {")
    qs_lines.append("                    obj.currentCount = Mathf.Min(obj.currentCount + amount, obj.requiredCount);")
    qs_lines.append("                    OnObjectiveUpdated?.Invoke(obj);")
    qs_lines.append("                }")
    qs_lines.append("            }")
    qs_lines.append("            if (quest.AllObjectivesComplete)")
    qs_lines.append("            {")
    qs_lines.append("                quest.state = QuestState.Complete;")
    qs_lines.append("                OnQuestCompleted?.Invoke(quest);")
    qs_lines.append("            }")
    qs_lines.append("        }")
    qs_lines.append("")

    # TurnInQuest
    qs_lines.append("        /// <summary>Turn in a completed quest and distribute rewards.</summary>")
    qs_lines.append("        public bool TurnInQuest(string questId)")
    qs_lines.append("        {")
    qs_lines.append("            if (!_quests.ContainsKey(questId)) return false;")
    qs_lines.append("            var quest = _quests[questId];")
    qs_lines.append("            if (quest.state != QuestState.Complete) return false;")
    qs_lines.append("            quest.state = QuestState.TurnedIn;")
    qs_lines.append("            DistributeRewards(quest.data.reward);")
    qs_lines.append("            OnQuestTurnedIn?.Invoke(quest);")
    qs_lines.append("            return true;")
    qs_lines.append("        }")
    qs_lines.append("")

    # DistributeRewards
    qs_lines.append("        /// <summary>Distribute quest rewards via events.</summary>")
    qs_lines.append("        private void DistributeRewards(QuestReward reward)")
    qs_lines.append("        {")
    qs_lines.append("            if (reward == null) return;")
    qs_lines.append("            if (reward.experiencePoints > 0)")
    qs_lines.append('                OnXPGained?.Invoke(reward.experiencePoints);')
    qs_lines.append("            if (reward.gold > 0)")
    qs_lines.append('                OnCurrencyGained?.Invoke("Gold", reward.gold);')
    qs_lines.append("            if (reward.rewardItems != null)")
    qs_lines.append("            {")
    qs_lines.append("                foreach (var item in reward.rewardItems)")
    qs_lines.append("                {")
    qs_lines.append("                    if (item != null)")
    qs_lines.append('                        OnItemReward?.Invoke(item);')
    qs_lines.append("                }")
    qs_lines.append("            }")
    qs_lines.append("        }")
    qs_lines.append("")

    # GetQuest / GetQuestsByState / GetQuestsByType
    qs_lines.append("        /// <summary>Get quest state by ID.</summary>")
    qs_lines.append("        public QuestState GetQuestState(string questId)")
    qs_lines.append("        {")
    qs_lines.append("            return _quests.ContainsKey(questId) ? _quests[questId].state : QuestState.NotStarted;")
    qs_lines.append("        }")
    qs_lines.append("")
    qs_lines.append("        /// <summary>Get all quests in a given state.</summary>")
    qs_lines.append("        public List<QuestInstance> GetQuestsByState(QuestState state)")
    qs_lines.append("        {")
    qs_lines.append("            return _quests.Values.Where(q => q.state == state).ToList();")
    qs_lines.append("        }")
    qs_lines.append("")
    qs_lines.append("        /// <summary>Get all quests of a given type.</summary>")
    qs_lines.append("        public List<QuestInstance> GetQuestsByType(QuestType type)")
    qs_lines.append("        {")
    qs_lines.append("            return _quests.Values.Where(q => q.data.questType == type).ToList();")
    qs_lines.append("        }")
    qs_lines.append("    }")
    qs_lines.append("}")
    quest_system_cs = "\n".join(qs_lines)

    # ----- UXML -----
    uxml_lines: list[str] = []
    uxml_lines.append('<ui:UXML xmlns:ui="UnityEngine.UIElements">')
    uxml_lines.append('    <ui:VisualElement name="quest-log-root" class="quest-log-root">')
    uxml_lines.append('        <ui:Label text="Quest Log" class="quest-log-title" />')
    uxml_lines.append('        <ui:VisualElement name="tab-bar" class="tab-bar">')
    uxml_lines.append('            <ui:Button name="tab-main" class="tab-button active" text="Main" />')
    uxml_lines.append('            <ui:Button name="tab-side" class="tab-button" text="Side" />')
    uxml_lines.append('            <ui:Button name="tab-daily" class="tab-button" text="Daily" />')
    uxml_lines.append("        </ui:VisualElement>")
    uxml_lines.append('        <ui:VisualElement name="quest-content" class="quest-content">')
    uxml_lines.append('            <ui:ScrollView name="quest-list" class="quest-list" />')
    uxml_lines.append('            <ui:VisualElement name="quest-detail" class="quest-detail">')
    uxml_lines.append('                <ui:Label name="quest-title" class="quest-title" />')
    uxml_lines.append('                <ui:Label name="quest-description" class="quest-description" />')
    uxml_lines.append('                <ui:VisualElement name="objectives-list" class="objectives-list" />')
    uxml_lines.append('                <ui:VisualElement name="rewards-panel" class="rewards-panel" />')
    uxml_lines.append('                <ui:Button name="track-button" class="track-button" text="Track" />')
    uxml_lines.append("            </ui:VisualElement>")
    uxml_lines.append("        </ui:VisualElement>")
    uxml_lines.append("    </ui:VisualElement>")
    uxml_lines.append("</ui:UXML>")
    quest_uxml = "\n".join(uxml_lines)

    # ----- USS -----
    uss_lines: list[str] = []
    uss_lines.append("/* VeilBreakers Quest Log - Dark Fantasy Theme */")
    uss_lines.append(".quest-log-root {")
    uss_lines.append("    background-color: rgba(15, 10, 10, 0.95);")
    uss_lines.append("    padding: 16px;")
    uss_lines.append("    border-color: rgb(80, 50, 30);")
    uss_lines.append("    border-width: 2px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".quest-log-title {")
    uss_lines.append("    font-size: 20px;")
    uss_lines.append("    color: rgb(220, 190, 130);")
    uss_lines.append("    -unity-font-style: bold;")
    uss_lines.append("    margin-bottom: 12px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".tab-bar { flex-direction: row; margin-bottom: 8px; }")
    uss_lines.append(".tab-button {")
    uss_lines.append("    flex-grow: 1;")
    uss_lines.append("    height: 30px;")
    uss_lines.append("    background-color: rgba(30, 22, 16, 0.8);")
    uss_lines.append("    color: rgb(160, 140, 100);")
    uss_lines.append("    border-color: rgb(60, 40, 25);")
    uss_lines.append("    border-width: 1px;")
    uss_lines.append("}")
    uss_lines.append(".tab-button.active { background-color: rgba(60, 42, 28, 0.9); color: rgb(220, 190, 130); }")
    uss_lines.append("")
    uss_lines.append(".quest-content { flex-direction: row; flex-grow: 1; }")
    uss_lines.append(".quest-list { width: 250px; margin-right: 12px; }")
    uss_lines.append(".quest-detail { flex-grow: 1; background-color: rgba(25, 18, 14, 0.9); padding: 12px; }")
    uss_lines.append(".quest-title { font-size: 16px; color: rgb(220, 190, 130); -unity-font-style: bold; }")
    uss_lines.append(".quest-description { font-size: 12px; color: rgb(180, 160, 120); margin-top: 8px; }")
    uss_lines.append(".objectives-list { margin-top: 12px; }")
    uss_lines.append(".rewards-panel { margin-top: 12px; padding: 8px; background-color: rgba(40, 30, 20, 0.7); }")
    uss_lines.append(".track-button { width: 100px; height: 28px; margin-top: 8px; }")
    quest_uss = "\n".join(uss_lines)

    return (quest_data_cs, quest_system_cs, quest_uxml, quest_uss)


# ---------------------------------------------------------------------------
# VB-08 / RPG-01: Loot table (weighted random + brand affinity + corruption)
# ---------------------------------------------------------------------------


def generate_loot_table_script(
    namespace: str = "VeilBreakers.Content",
) -> str:
    """Generate C# for a weighted loot table with brand affinity.

    Returns:
        Complete C# source string for loot table SO + roller.
    """
    ns = _safe_namespace(namespace)
    lines: list[str] = []
    lines.append("using System;")
    lines.append("using System.Collections.Generic;")
    lines.append("using UnityEngine;")
    lines.append("using VeilBreakers.Combat;")
    lines.append("using VeilBreakers.Core;")
    lines.append("using VeilBreakers.Data;")
    lines.append("")
    lines.append("namespace " + ns)
    lines.append("{")

    # Brand enum reference
    lines.append("    /// <summary>Loot entry in a loot table.</summary>")
    lines.append("    [Serializable]")
    lines.append("    public class LootEntry")
    lines.append("    {")
    lines.append("        public VB_ItemData item;")
    lines.append("        public float weight = 1f;")
    lines.append("        public ItemRarity minRarity;")
    lines.append("        public int minQuantity = 1;")
    lines.append("        public int maxQuantity = 1;")
    lines.append("        public Brand brandAffinity;")
    lines.append("    }")
    lines.append("")

    # LootResult
    lines.append("    /// <summary>Result of a loot roll.</summary>")
    lines.append("    public struct LootResult")
    lines.append("    {")
    lines.append("        public VB_ItemData item;")
    lines.append("        public int quantity;")
    lines.append("    }")
    lines.append("")

    # VB_LootTable SO
    lines.append("    /// <summary>")
    lines.append("    /// Weighted loot table with brand affinity and corruption bonuses.")
    lines.append("    /// VB-08: Brand affinity delegates to BrandSystem.GetEffectiveness().")
    lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    lines.append("    /// </summary>")
    lines.append('    [CreateAssetMenu(fileName = "NewLootTable", menuName = "VeilBreakers/Loot Table")]')
    lines.append("    public class VB_LootTable : ScriptableObject")
    lines.append("    {")
    lines.append("        public List<LootEntry> entries = new List<LootEntry>();")
    lines.append("        public int rollCount = 1;")
    lines.append("        public float nothingWeight = 0f;")
    lines.append("")

    # Roll method
    lines.append("        /// <summary>")
    lines.append("        /// Roll the loot table with brand affinity and corruption bonuses.")
    lines.append("        /// </summary>")
    lines.append("        /// <param name=\"monsterBrand\">Brand of the defeated monster.</param>")
    lines.append("        /// <param name=\"corruptionLevel\">Player corruption level (0-1).</param>")
    lines.append("        public List<LootResult> Roll(Brand monsterBrand, float corruptionLevel)")
    lines.append("        {")
    lines.append("            var results = new List<LootResult>();")
    lines.append("            for (int roll = 0; roll < rollCount; roll++)")
    lines.append("            {")
    lines.append("                float totalWeight = nothingWeight;")
    lines.append("                var adjustedWeights = new float[entries.Count];")
    lines.append("")
    lines.append("                for (int i = 0; i < entries.Count; i++)")
    lines.append("                {")
    lines.append("                    float w = entries[i].weight;")
    lines.append("")
    lines.append("                    // VB-08: Brand affinity -- delegate to BrandSystem")
    lines.append("                    float brandEffectiveness = BrandSystem.GetEffectiveness(monsterBrand, entries[i].brandAffinity);")
    lines.append("                    if (brandEffectiveness > 1f)")
    lines.append("                        w *= 1.5f; // Boost matching brand gear weight")
    lines.append("")
    lines.append("                    // Corruption bonus: high corruption increases rare drop rates")
    lines.append("                    if (corruptionLevel > 0.5f)")
    lines.append("                        w *= (1f + corruptionLevel * 0.3f);")
    lines.append("")
    lines.append("                    adjustedWeights[i] = w;")
    lines.append("                    totalWeight += w;")
    lines.append("                }")
    lines.append("")
    lines.append("                // Cumulative distribution selection")
    lines.append("                float rand = UnityEngine.Random.Range(0f, totalWeight);")
    lines.append("                float cumulative = 0f;")
    lines.append("")
    lines.append("                // nothingWeight occupies the first band of the distribution")
    lines.append("                cumulative += nothingWeight;")
    lines.append("                if (rand <= cumulative) continue; // rolled 'nothing'")
    lines.append("")
    lines.append("                for (int i = 0; i < entries.Count; i++)")
    lines.append("                {")
    lines.append("                    cumulative += adjustedWeights[i];")
    lines.append("                    if (rand <= cumulative)")
    lines.append("                    {")
    lines.append("                        int qty = UnityEngine.Random.Range(entries[i].minQuantity, entries[i].maxQuantity + 1);")
    lines.append("                        results.Add(new LootResult { item = entries[i].item, quantity = qty });")
    lines.append("                        break;")
    lines.append("                    }")
    lines.append("                }")
    lines.append("            }")
    lines.append("            return results;")
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GAME-09: Crafting system (recipe SO + crafting station)
# ---------------------------------------------------------------------------


def generate_crafting_system_script(
    namespace: str = "VeilBreakers.Content",
) -> tuple[str, str]:
    """Generate C# for a crafting system with recipe definitions.

    Returns:
        (recipe_cs, crafting_cs) tuple.
    """
    ns = _safe_namespace(namespace)

    # ----- Recipe SO -----
    recipe_lines: list[str] = []
    recipe_lines.append("using System;")
    recipe_lines.append("using System.Collections.Generic;")
    recipe_lines.append("using UnityEngine;")
    recipe_lines.append("")
    recipe_lines.append("namespace " + ns)
    recipe_lines.append("{")

    # CraftingStationType
    recipe_lines.append("    /// <summary>Types of crafting stations.</summary>")
    recipe_lines.append("    public enum CraftingStationType")
    recipe_lines.append("    {")
    recipe_lines.append("        Anvil,")
    recipe_lines.append("        Alchemy,")
    recipe_lines.append("        Enchanting,")
    recipe_lines.append("        Cooking,")
    recipe_lines.append("        General")
    recipe_lines.append("    }")
    recipe_lines.append("")

    # CraftingIngredient
    recipe_lines.append("    /// <summary>An ingredient requirement for a recipe.</summary>")
    recipe_lines.append("    [Serializable]")
    recipe_lines.append("    public class CraftingIngredient")
    recipe_lines.append("    {")
    recipe_lines.append("        public VB_ItemData item;")
    recipe_lines.append("        public int count = 1;")
    recipe_lines.append("    }")
    recipe_lines.append("")

    # RecipeUnlockCondition
    recipe_lines.append("    /// <summary>Condition required to unlock a recipe.</summary>")
    recipe_lines.append("    [Serializable]")
    recipe_lines.append("    public class RecipeUnlockCondition")
    recipe_lines.append("    {")
    recipe_lines.append("        public string questId;")
    recipe_lines.append("        public int requiredLevel;")
    recipe_lines.append("    }")
    recipe_lines.append("")

    # VB_Recipe SO
    recipe_lines.append("    /// <summary>")
    recipe_lines.append("    /// ScriptableObject defining a crafting recipe.")
    recipe_lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    recipe_lines.append("    /// </summary>")
    recipe_lines.append('    [CreateAssetMenu(fileName = "NewRecipe", menuName = "VeilBreakers/Recipe")]')
    recipe_lines.append("    public class VB_Recipe : ScriptableObject")
    recipe_lines.append("    {")
    recipe_lines.append("        public string recipeId;")
    recipe_lines.append("        public string recipeName;")
    recipe_lines.append("        public List<CraftingIngredient> ingredients = new List<CraftingIngredient>();")
    recipe_lines.append("        public VB_ItemData resultItem;")
    recipe_lines.append("        public int resultQuantity = 1;")
    recipe_lines.append("        public CraftingStationType requiredStation;")
    recipe_lines.append("        public RecipeUnlockCondition unlockCondition;")
    recipe_lines.append("        public float craftDuration = 1f;")
    recipe_lines.append("    }")
    recipe_lines.append("}")
    recipe_cs = "\n".join(recipe_lines)

    # ----- Crafting System MonoBehaviour -----
    craft_lines: list[str] = []
    craft_lines.append("using System;")
    craft_lines.append("using System.Collections.Generic;")
    craft_lines.append("using UnityEngine;")
    craft_lines.append("using VeilBreakers.Core;")
    craft_lines.append("")
    craft_lines.append("namespace " + ns)
    craft_lines.append("{")

    # VB_CraftingSystem
    craft_lines.append("    /// <summary>")
    craft_lines.append("    /// Crafting system with station interaction, ingredient validation,")
    craft_lines.append("    /// and unlock progression.")
    craft_lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    craft_lines.append("    /// </summary>")
    craft_lines.append("    public class VB_CraftingSystem : MonoBehaviour")
    craft_lines.append("    {")
    craft_lines.append("        public static VB_CraftingSystem Instance { get; private set; }")
    craft_lines.append("")
    craft_lines.append("        [SerializeField] private List<VB_Recipe> _allRecipes = new List<VB_Recipe>();")
    craft_lines.append("        private HashSet<string> _unlockedRecipes = new HashSet<string>();")
    craft_lines.append("        private CraftingStationType _activeStation;")
    craft_lines.append("        private bool _isAtStation;")
    craft_lines.append("")
    craft_lines.append("        public event Action<VB_Recipe> OnItemCrafted;")
    craft_lines.append("")

    # Awake
    craft_lines.append("        private void Awake()")
    craft_lines.append("        {")
    craft_lines.append("            if (Instance != null && Instance != this) { Destroy(gameObject); return; }")
    craft_lines.append("            Instance = this;")
    craft_lines.append("        }")
    craft_lines.append("")

    # OpenStation
    craft_lines.append("        /// <summary>Open a crafting station.</summary>")
    craft_lines.append("        public void OpenStation(CraftingStationType stationType)")
    craft_lines.append("        {")
    craft_lines.append("            _activeStation = stationType;")
    craft_lines.append("            _isAtStation = true;")
    craft_lines.append('            OnCraftingStationOpened?.Invoke(stationType);')
    craft_lines.append("        }")
    craft_lines.append("")

    # CloseStation
    craft_lines.append("        /// <summary>Close the active crafting station.</summary>")
    craft_lines.append("        public void CloseStation()")
    craft_lines.append("        {")
    craft_lines.append("            _isAtStation = false;")
    craft_lines.append('            OnCraftingStationClosed?.Invoke();')
    craft_lines.append("        }")
    craft_lines.append("")

    # UnlockRecipe
    craft_lines.append("        /// <summary>Unlock a recipe.</summary>")
    craft_lines.append("        public void UnlockRecipe(string recipeId)")
    craft_lines.append("        {")
    craft_lines.append("            _unlockedRecipes.Add(recipeId);")
    craft_lines.append('            OnRecipeUnlocked?.Invoke(recipeId);')
    craft_lines.append("        }")
    craft_lines.append("")

    # CanCraft
    craft_lines.append("        /// <summary>Check if a recipe can be crafted at the current station.</summary>")
    craft_lines.append("        public bool CanCraft(VB_Recipe recipe)")
    craft_lines.append("        {")
    craft_lines.append("            if (recipe == null) return false;")
    craft_lines.append("            if (!_isAtStation) return false;")
    craft_lines.append("            if (recipe.requiredStation != _activeStation) return false;")
    craft_lines.append("            if (recipe.unlockCondition != null && !string.IsNullOrEmpty(recipe.unlockCondition.questId))")
    craft_lines.append("            {")
    craft_lines.append("                if (!_unlockedRecipes.Contains(recipe.recipeId)) return false;")
    craft_lines.append("            }")
    craft_lines.append("            // Validate ingredients against inventory")
    craft_lines.append("            var inventory = VB_InventorySystem.Instance;")
    craft_lines.append("            if (inventory == null) return false;")
    craft_lines.append("            foreach (var ingredient in recipe.ingredients)")
    craft_lines.append("            {")
    craft_lines.append("                if (!inventory.HasItem(ingredient.item, ingredient.count))")
    craft_lines.append("                    return false;")
    craft_lines.append("            }")
    craft_lines.append("            return true;")
    craft_lines.append("        }")
    craft_lines.append("")

    # Craft
    craft_lines.append("        /// <summary>Craft a recipe, consuming ingredients and producing the result.</summary>")
    craft_lines.append("        public bool Craft(VB_Recipe recipe)")
    craft_lines.append("        {")
    craft_lines.append("            if (!CanCraft(recipe)) return false;")
    craft_lines.append("            var inventory = VB_InventorySystem.Instance;")
    craft_lines.append("            // Consume ingredients")
    craft_lines.append("            foreach (var ingredient in recipe.ingredients)")
    craft_lines.append("                inventory.RemoveItem(ingredient.item, ingredient.count);")
    craft_lines.append("            // Add result")
    craft_lines.append("            inventory.AddItem(recipe.resultItem, recipe.resultQuantity);")
    craft_lines.append("            OnItemCrafted?.Invoke(recipe);")
    craft_lines.append("            return true;")
    craft_lines.append("        }")
    craft_lines.append("")

    # GetAvailableRecipes
    craft_lines.append("        /// <summary>Get all recipes available at the current station.</summary>")
    craft_lines.append("        public List<VB_Recipe> GetAvailableRecipes()")
    craft_lines.append("        {")
    craft_lines.append("            var result = new List<VB_Recipe>();")
    craft_lines.append("            foreach (var recipe in _allRecipes)")
    craft_lines.append("            {")
    craft_lines.append("                if (recipe.requiredStation == _activeStation)")
    craft_lines.append("                    result.Add(recipe);")
    craft_lines.append("            }")
    craft_lines.append("            return result;")
    craft_lines.append("        }")
    craft_lines.append("    }")
    craft_lines.append("}")
    crafting_cs = "\n".join(craft_lines)

    return (recipe_cs, crafting_cs)


# ---------------------------------------------------------------------------
# GAME-10: Skill tree (node SO + hero path tree)
# ---------------------------------------------------------------------------


def generate_skill_tree_script(
    hero_paths: Optional[list[str]] = None,
    namespace: str = "VeilBreakers.Content",
) -> tuple[str, str]:
    """Generate C# for a skill tree system with hero path layouts.

    Returns:
        (skill_node_cs, skill_tree_cs) tuple.
    """
    if hero_paths is None:
        hero_paths = ["IRONBOUND", "FANGBORN", "VOIDTOUCHED", "UNCHAINED"]
    ns = _safe_namespace(namespace)

    # ----- Skill Node SO -----
    node_lines: list[str] = []
    node_lines.append("using System;")
    node_lines.append("using System.Collections.Generic;")
    node_lines.append("using UnityEngine;")
    node_lines.append("using VeilBreakers.Combat;")
    node_lines.append("")
    node_lines.append("namespace " + ns)
    node_lines.append("{")

    # SkillStatBonus
    node_lines.append("    /// <summary>A stat bonus granted by a skill node.</summary>")
    node_lines.append("    [Serializable]")
    node_lines.append("    public class SkillStatBonus")
    node_lines.append("    {")
    node_lines.append("        public string statName;")
    node_lines.append("        public float amount;")
    node_lines.append("        public bool isPercentage;")
    node_lines.append("    }")
    node_lines.append("")

    # VB_SkillNode SO
    node_lines.append("    /// <summary>")
    node_lines.append("    /// ScriptableObject defining a single skill tree node.")
    node_lines.append("    /// Has prerequisites, brand requirement, stat bonuses, and unlock cost.")
    node_lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    node_lines.append("    /// </summary>")
    node_lines.append('    [CreateAssetMenu(fileName = "NewSkillNode", menuName = "VeilBreakers/Skill Node")]')
    node_lines.append("    public class VB_SkillNode : ScriptableObject")
    node_lines.append("    {")
    node_lines.append("        public string nodeId;")
    node_lines.append("        public string displayName;")
    node_lines.append("        [TextArea] public string description;")
    node_lines.append("        public Sprite icon;")
    node_lines.append("")
    node_lines.append('        [Header("Requirements")]')
    node_lines.append("        public List<VB_SkillNode> prerequisites = new List<VB_SkillNode>();")
    node_lines.append("        public Brand requiredBrand;")
    node_lines.append("        public int unlockCost = 1;")
    node_lines.append("        public int requiredLevel;")
    node_lines.append("")
    node_lines.append('        [Header("Effects")]')
    node_lines.append("        public List<SkillStatBonus> statBonuses = new List<SkillStatBonus>();")
    node_lines.append("        public string abilityUnlock;")
    node_lines.append("")
    node_lines.append('        [Header("Tree Position")]')
    node_lines.append("        public string heroPath;")
    node_lines.append("        public int tier;")
    node_lines.append("        public int column;")
    node_lines.append("    }")
    node_lines.append("}")
    skill_node_cs = "\n".join(node_lines)

    # ----- Skill Tree MonoBehaviour -----
    tree_lines: list[str] = []
    tree_lines.append("using System;")
    tree_lines.append("using System.Collections.Generic;")
    tree_lines.append("using System.Linq;")
    tree_lines.append("using UnityEngine;")
    tree_lines.append("using VeilBreakers.Core;")
    tree_lines.append("")
    tree_lines.append("namespace " + ns)
    tree_lines.append("{")

    # Path enum
    tree_lines.append("    /// <summary>VeilBreakers hero paths.</summary>")
    tree_lines.append("    public enum Path")
    tree_lines.append("    {")
    for i, path in enumerate(hero_paths):
        safe_path = sanitize_cs_identifier(path)
        comma = "," if i < len(hero_paths) - 1 else ""
        tree_lines.append("        " + safe_path + comma)
    tree_lines.append("    }")
    tree_lines.append("")

    # VB_SkillTree
    tree_lines.append("    /// <summary>")
    tree_lines.append("    /// Skill tree system with hero path layouts, point allocation,")
    tree_lines.append("    /// and prerequisite validation.")
    tree_lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    tree_lines.append("    /// </summary>")
    tree_lines.append("    public class VB_SkillTree : MonoBehaviour")
    tree_lines.append("    {")
    tree_lines.append("        public static VB_SkillTree Instance { get; private set; }")
    tree_lines.append("")
    tree_lines.append("        [SerializeField] private List<VB_SkillNode> _allNodes = new List<VB_SkillNode>();")
    tree_lines.append("        private HashSet<string> _unlockedNodes = new HashSet<string>();")
    tree_lines.append("        private int _availablePoints;")
    tree_lines.append("        private int _totalPointsEarned;")
    tree_lines.append("")
    tree_lines.append("        public int AvailablePoints => _availablePoints;")
    tree_lines.append("        public int TotalPointsEarned => _totalPointsEarned;")
    tree_lines.append("")
    tree_lines.append("        public event Action<VB_SkillNode> OnSkillUnlocked;")
    tree_lines.append("        public event Action OnTreeReset;")
    tree_lines.append("")

    # Awake
    tree_lines.append("        private void Awake()")
    tree_lines.append("        {")
    tree_lines.append("            if (Instance != null && Instance != this) { Destroy(gameObject); return; }")
    tree_lines.append("            Instance = this;")
    tree_lines.append("        }")
    tree_lines.append("")

    # AddPoints
    tree_lines.append("        /// <summary>Add skill points (e.g., on level up).</summary>")
    tree_lines.append("        public void AddPoints(int points)")
    tree_lines.append("        {")
    tree_lines.append("            _availablePoints += points;")
    tree_lines.append("            _totalPointsEarned += points;")
    tree_lines.append("        }")
    tree_lines.append("")

    # CanAllocate
    tree_lines.append("        /// <summary>Check if a skill node can be allocated.</summary>")
    tree_lines.append("        public bool CanAllocate(VB_SkillNode node)")
    tree_lines.append("        {")
    tree_lines.append("            if (node == null) return false;")
    tree_lines.append("            if (_unlockedNodes.Contains(node.nodeId)) return false;")
    tree_lines.append("            if (_availablePoints < node.unlockCost) return false;")
    tree_lines.append("            // Check prerequisites")
    tree_lines.append("            foreach (var prereq in node.prerequisites)")
    tree_lines.append("            {")
    tree_lines.append("                if (prereq != null && !_unlockedNodes.Contains(prereq.nodeId))")
    tree_lines.append("                    return false;")
    tree_lines.append("            }")
    tree_lines.append("            return true;")
    tree_lines.append("        }")
    tree_lines.append("")

    # AllocatePoint
    tree_lines.append("        /// <summary>Allocate a point to unlock a skill node.</summary>")
    tree_lines.append("        public bool AllocatePoint(VB_SkillNode node)")
    tree_lines.append("        {")
    tree_lines.append("            if (!CanAllocate(node)) return false;")
    tree_lines.append("            _availablePoints -= node.unlockCost;")
    tree_lines.append("            _unlockedNodes.Add(node.nodeId);")
    tree_lines.append("            OnSkillUnlocked?.Invoke(node);")
    tree_lines.append("            return true;")
    tree_lines.append("        }")
    tree_lines.append("")

    # ResetPoints
    tree_lines.append("        /// <summary>Reset all allocated points.</summary>")
    tree_lines.append("        public void ResetPoints()")
    tree_lines.append("        {")
    tree_lines.append("            _availablePoints = _totalPointsEarned;")
    tree_lines.append("            _unlockedNodes.Clear();")
    tree_lines.append("            OnTreeReset?.Invoke();")
    tree_lines.append("        }")
    tree_lines.append("")

    # IsUnlocked
    tree_lines.append("        /// <summary>Check if a node has been unlocked.</summary>")
    tree_lines.append("        public bool IsUnlocked(string nodeId)")
    tree_lines.append("        {")
    tree_lines.append("            return _unlockedNodes.Contains(nodeId);")
    tree_lines.append("        }")
    tree_lines.append("")

    # GetNodesByPath
    tree_lines.append("        /// <summary>Get all nodes belonging to a hero path.</summary>")
    tree_lines.append("        public List<VB_SkillNode> GetNodesByPath(string heroPath)")
    tree_lines.append("        {")
    tree_lines.append("            return _allNodes.Where(n => n.heroPath == heroPath).ToList();")
    tree_lines.append("        }")
    tree_lines.append("")

    # GetTotalStatBonuses
    tree_lines.append("        /// <summary>Get aggregate stat bonuses from all unlocked nodes.</summary>")
    tree_lines.append("        public Dictionary<string, float> GetTotalStatBonuses()")
    tree_lines.append("        {")
    tree_lines.append("            var bonuses = new Dictionary<string, float>();")
    tree_lines.append("            foreach (var node in _allNodes)")
    tree_lines.append("            {")
    tree_lines.append("                if (!_unlockedNodes.Contains(node.nodeId)) continue;")
    tree_lines.append("                foreach (var bonus in node.statBonuses)")
    tree_lines.append("                {")
    tree_lines.append("                    if (!bonuses.ContainsKey(bonus.statName))")
    tree_lines.append("                        bonuses[bonus.statName] = 0f;")
    tree_lines.append("                    bonuses[bonus.statName] += bonus.amount;")
    tree_lines.append("                }")
    tree_lines.append("            }")
    tree_lines.append("            return bonuses;")
    tree_lines.append("        }")
    tree_lines.append("    }")
    tree_lines.append("}")
    skill_tree_cs = "\n".join(tree_lines)

    return (skill_node_cs, skill_tree_cs)


# ---------------------------------------------------------------------------
# GAME-12: DPS Calculator (EDITOR ONLY)
# ---------------------------------------------------------------------------


def generate_dps_calculator_script(
    brands: Optional[list[str]] = None,
    namespace: str = "VeilBreakers.Editor.Balancing",
) -> str:
    """Generate C# EditorWindow for DPS calculation.

    EDITOR ONLY -- uses ``using UnityEditor;``.

    Returns:
        Complete C# source string.
    """
    if brands is None:
        brands = [
            "IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
            "LEECH", "GRACE", "MEND", "RUIN", "VOID",
        ]
    ns = _safe_namespace(namespace)

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using VeilBreakers.Combat;")
    lines.append("")
    lines.append("namespace " + ns)
    lines.append("{")

    lines.append("    /// <summary>")
    lines.append("    /// Editor tool for calculating DPS with brand/synergy modifiers.")
    lines.append("    /// Formula: DPS = (baseDmg * atkSpeed) * (1 + critChance * (critMult - 1)) * brandMult * synergyMult")
    lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    lines.append("    /// </summary>")
    lines.append('    public class VB_DPSCalculator : EditorWindow')
    lines.append("    {")

    # Fields
    lines.append("        private float _baseATK = 50f;")
    lines.append("        private float _weaponDamage = 30f;")
    lines.append("        private float _attackSpeed = 1.2f;")
    lines.append("        private float _critChance = 0.15f;")
    lines.append("        private float _critMultiplier = 2.0f;")
    lines.append("        private int _attackerBrandIndex = 0;")
    lines.append("        private int _targetBrandIndex = 0;")
    lines.append("        private float _calculatedDPS;")
    lines.append("        private float _brandMultiplier = 1f;")
    lines.append("        private float _synergyMultiplier = 1f;")
    lines.append("")

    # Brand names array
    lines.append("        private static readonly string[] BrandNames = new string[]")
    lines.append("        {")
    for i, brand in enumerate(brands):
        safe = sanitize_cs_string(brand)
        comma = "," if i < len(brands) - 1 else ""
        lines.append('            "' + safe + '"' + comma)
    lines.append("        };")
    lines.append("")

    # MenuItem
    lines.append('        [MenuItem("VeilBreakers/Balancing/DPS Calculator")]')
    lines.append("        public static void ShowWindow()")
    lines.append("        {")
    lines.append('            GetWindow<VB_DPSCalculator>("DPS Calculator");')
    lines.append("        }")
    lines.append("")

    # OnGUI
    lines.append("        private void OnGUI()")
    lines.append("        {")
    lines.append('            GUILayout.Label("DPS Calculator", EditorStyles.boldLabel);')
    lines.append("            EditorGUILayout.Space();")
    lines.append("")
    lines.append('            GUILayout.Label("Base Stats", EditorStyles.miniBoldLabel);')
    lines.append('            _baseATK = EditorGUILayout.FloatField("Base ATK", _baseATK);')
    lines.append('            _weaponDamage = EditorGUILayout.FloatField("Weapon Damage", _weaponDamage);')
    lines.append('            _attackSpeed = EditorGUILayout.FloatField("Attack Speed", _attackSpeed);')
    lines.append('            _critChance = EditorGUILayout.Slider("Crit Chance", _critChance, 0f, 1f);')
    lines.append('            _critMultiplier = EditorGUILayout.FloatField("Crit Multiplier", _critMultiplier);')
    lines.append("")
    lines.append("            EditorGUILayout.Space();")
    lines.append('            GUILayout.Label("Brand/Synergy", EditorStyles.miniBoldLabel);')
    lines.append('            _attackerBrandIndex = EditorGUILayout.Popup("Attacker Brand", _attackerBrandIndex, BrandNames);')
    lines.append('            _targetBrandIndex = EditorGUILayout.Popup("Target Brand", _targetBrandIndex, BrandNames);')
    lines.append("")
    lines.append("            EditorGUILayout.Space();")
    lines.append('            if (GUILayout.Button("Calculate DPS"))')
    lines.append("            {")
    lines.append("                CalculateDPS();")
    lines.append("            }")
    lines.append("")
    lines.append("            EditorGUILayout.Space();")
    lines.append('            GUILayout.Label("Results", EditorStyles.miniBoldLabel);')
    lines.append('            EditorGUILayout.LabelField("Brand Multiplier", _brandMultiplier.ToString("F3"));')
    lines.append('            EditorGUILayout.LabelField("Synergy Multiplier", _synergyMultiplier.ToString("F3"));')
    lines.append("            EditorGUILayout.Space();")
    lines.append('            var style = new GUIStyle(EditorStyles.boldLabel) { fontSize = 18 };')
    lines.append('            GUILayout.Label("DPS: " + _calculatedDPS.ToString("F1"), style);')
    lines.append("        }")
    lines.append("")

    # CalculateDPS
    lines.append("        private void CalculateDPS()")
    lines.append("        {")
    lines.append("            float baseDmg = _baseATK + _weaponDamage;")
    lines.append("            float critFactor = 1f + _critChance * (_critMultiplier - 1f);")
    lines.append("            _brandMultiplier = BrandSystem.GetEffectiveness((Brand)_attackerBrandIndex, (Brand)_targetBrandIndex);")
    lines.append("            var synergyTier = SynergySystem.GetSynergyTier((Brand)_attackerBrandIndex, (Brand)_targetBrandIndex);")
    lines.append("            _synergyMultiplier = SynergySystem.GetDamageBonus(synergyTier);")
    lines.append("            _calculatedDPS = (baseDmg * _attackSpeed) * critFactor * _brandMultiplier * _synergyMultiplier;")
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GAME-12: Encounter Simulator (EDITOR ONLY)
# ---------------------------------------------------------------------------


def generate_encounter_simulator_script(
    namespace: str = "VeilBreakers.Editor.Balancing",
) -> str:
    """Generate C# EditorWindow for Monte Carlo encounter simulation.

    EDITOR ONLY -- uses ``using UnityEditor;``.

    Returns:
        Complete C# source string.
    """
    ns = _safe_namespace(namespace)

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using System.Collections.Generic;")
    lines.append("")
    lines.append("namespace " + ns)
    lines.append("{")

    lines.append("    /// <summary>")
    lines.append("    /// Editor tool for running Monte Carlo encounter simulations.")
    lines.append("    /// Outputs: win rate, average duration, average damage taken, DPS distribution.")
    lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    lines.append("    /// </summary>")
    lines.append('    public class VB_EncounterSimulator : EditorWindow')
    lines.append("    {")

    # Fields
    lines.append("        // Player stats")
    lines.append("        private float _playerHP = 500f;")
    lines.append("        private float _playerATK = 80f;")
    lines.append("        private float _playerDEF = 40f;")
    lines.append("        private float _playerSpeed = 1.0f;")
    lines.append("")
    lines.append("        // Enemy stats")
    lines.append("        private float _enemyHP = 300f;")
    lines.append("        private float _enemyATK = 50f;")
    lines.append("        private float _enemyDEF = 20f;")
    lines.append("        private float _enemySpeed = 0.8f;")
    lines.append("")
    lines.append("        // Simulation settings")
    lines.append("        private int _encounterCount = 1000;")
    lines.append("")
    lines.append("        // Results")
    lines.append("        private float _winRate;")
    lines.append("        private float _avgDuration;")
    lines.append("        private float _avgDamageTaken;")
    lines.append("        private float _avgDPS;")
    lines.append("        private bool _hasResults;")
    lines.append("")

    # MenuItem
    lines.append('        [MenuItem("VeilBreakers/Balancing/Encounter Simulator")]')
    lines.append("        public static void ShowWindow()")
    lines.append("        {")
    lines.append('            GetWindow<VB_EncounterSimulator>("Encounter Simulator");')
    lines.append("        }")
    lines.append("")

    # OnGUI
    lines.append("        private void OnGUI()")
    lines.append("        {")
    lines.append('            GUILayout.Label("Encounter Simulator", EditorStyles.boldLabel);')
    lines.append("            EditorGUILayout.Space();")
    lines.append("")
    lines.append('            GUILayout.Label("Player Stats", EditorStyles.miniBoldLabel);')
    lines.append('            _playerHP = EditorGUILayout.FloatField("HP", _playerHP);')
    lines.append('            _playerATK = EditorGUILayout.FloatField("ATK", _playerATK);')
    lines.append('            _playerDEF = EditorGUILayout.FloatField("DEF", _playerDEF);')
    lines.append('            _playerSpeed = EditorGUILayout.FloatField("Speed", _playerSpeed);')
    lines.append("")
    lines.append("            EditorGUILayout.Space();")
    lines.append('            GUILayout.Label("Enemy Stats", EditorStyles.miniBoldLabel);')
    lines.append('            _enemyHP = EditorGUILayout.FloatField("HP", _enemyHP);')
    lines.append('            _enemyATK = EditorGUILayout.FloatField("ATK", _enemyATK);')
    lines.append('            _enemyDEF = EditorGUILayout.FloatField("DEF", _enemyDEF);')
    lines.append('            _enemySpeed = EditorGUILayout.FloatField("Speed", _enemySpeed);')
    lines.append("")
    lines.append("            EditorGUILayout.Space();")
    lines.append('            GUILayout.Label("Simulation", EditorStyles.miniBoldLabel);')
    lines.append('            _encounterCount = EditorGUILayout.IntField("Encounter Count", _encounterCount);')
    lines.append("")
    lines.append("            EditorGUILayout.Space();")
    lines.append('            if (GUILayout.Button("Run Simulation"))')
    lines.append("            {")
    lines.append("                RunSimulation();")
    lines.append("            }")
    lines.append("")
    lines.append("            if (_hasResults)")
    lines.append("            {")
    lines.append("                EditorGUILayout.Space();")
    lines.append('                GUILayout.Label("Results", EditorStyles.miniBoldLabel);')
    lines.append('                EditorGUILayout.LabelField("Win Rate", (_winRate * 100f).ToString("F1") + "%");')
    lines.append('                EditorGUILayout.LabelField("Avg Duration (turns)", _avgDuration.ToString("F1"));')
    lines.append('                EditorGUILayout.LabelField("Avg Damage Taken", _avgDamageTaken.ToString("F1"));')
    lines.append('                EditorGUILayout.LabelField("Avg DPS", _avgDPS.ToString("F1"));')
    lines.append("            }")
    lines.append("        }")
    lines.append("")

    # RunSimulation
    lines.append("        private void RunSimulation()")
    lines.append("        {")
    lines.append("            int wins = 0;")
    lines.append("            float totalDuration = 0f;")
    lines.append("            float totalDamageTaken = 0f;")
    lines.append("            float totalDamageDealt = 0f;")
    lines.append("")
    lines.append("            for (int i = 0; i < _encounterCount; i++)")
    lines.append("            {")
    lines.append("                float pHP = _playerHP;")
    lines.append("                float eHP = _enemyHP;")
    lines.append("                float turns = 0;")
    lines.append("                float damageTaken = 0f;")
    lines.append("                float damageDealt = 0f;")
    lines.append("")
    lines.append("                while (pHP > 0 && eHP > 0 && turns < 100)")
    lines.append("                {")
    lines.append("                    turns++;")
    lines.append("                    // Player attacks")
    lines.append("                    float pDmg = Mathf.Max(1f, (_playerATK - _enemyDEF) * _playerSpeed);")
    lines.append("                    pDmg *= UnityEngine.Random.Range(0.85f, 1.15f);")
    lines.append("                    eHP -= pDmg;")
    lines.append("                    damageDealt += pDmg;")
    lines.append("")
    lines.append("                    if (eHP <= 0) break;")
    lines.append("")
    lines.append("                    // Enemy attacks")
    lines.append("                    float eDmg = Mathf.Max(1f, (_enemyATK - _playerDEF) * _enemySpeed);")
    lines.append("                    eDmg *= UnityEngine.Random.Range(0.85f, 1.15f);")
    lines.append("                    pHP -= eDmg;")
    lines.append("                    damageTaken += eDmg;")
    lines.append("                }")
    lines.append("")
    lines.append("                if (pHP > 0) wins++;")
    lines.append("                totalDuration += turns;")
    lines.append("                totalDamageTaken += damageTaken;")
    lines.append("                totalDamageDealt += damageDealt;")
    lines.append("            }")
    lines.append("")
    lines.append("            _winRate = (float)wins / _encounterCount;")
    lines.append("            _avgDuration = totalDuration / _encounterCount;")
    lines.append("            _avgDamageTaken = totalDamageTaken / _encounterCount;")
    lines.append("            _avgDPS = totalDamageDealt / Mathf.Max(1f, totalDuration);")
    lines.append("            _hasResults = true;")
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GAME-12: Stat Curve Editor (EDITOR ONLY)
# ---------------------------------------------------------------------------


def generate_stat_curve_editor_script(
    namespace: str = "VeilBreakers.Editor.Balancing",
) -> str:
    """Generate C# EditorWindow for stat curve editing.

    EDITOR ONLY -- uses ``using UnityEditor;``.

    Returns:
        Complete C# source string.
    """
    ns = _safe_namespace(namespace)

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using System.IO;")
    lines.append("")
    lines.append("namespace " + ns)
    lines.append("{")

    lines.append("    /// <summary>")
    lines.append("    /// Editor tool for editing HP/ATK/DEF scaling curves per level.")
    lines.append("    /// Provides AnimationCurve fields, visual preview, and JSON export.")
    lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    lines.append("    /// </summary>")
    lines.append('    public class VB_StatCurveEditor : EditorWindow')
    lines.append("    {")

    # Fields
    lines.append("        private AnimationCurve _hpCurve = AnimationCurve.Linear(1, 100, 100, 5000);")
    lines.append("        private AnimationCurve _atkCurve = AnimationCurve.Linear(1, 10, 100, 500);")
    lines.append("        private AnimationCurve _defCurve = AnimationCurve.Linear(1, 5, 100, 250);")
    lines.append("")
    lines.append("        private string[] _enemyTypes = new string[]")
    lines.append('            { "Normal", "Elite", "Boss", "MiniBoss" };')
    lines.append("        private int _enemyTypeIndex;")
    lines.append("        private int _minLevel = 1;")
    lines.append("        private int _maxLevel = 100;")
    lines.append("        private Vector2 _scrollPosition;")
    lines.append("")

    # MenuItem
    lines.append('        [MenuItem("VeilBreakers/Balancing/Stat Curve Editor")]')
    lines.append("        public static void ShowWindow()")
    lines.append("        {")
    lines.append('            GetWindow<VB_StatCurveEditor>("Stat Curve Editor");')
    lines.append("        }")
    lines.append("")

    # OnGUI
    lines.append("        private void OnGUI()")
    lines.append("        {")
    lines.append('            GUILayout.Label("Stat Curve Editor", EditorStyles.boldLabel);')
    lines.append("            EditorGUILayout.Space();")
    lines.append("")
    lines.append('            _enemyTypeIndex = EditorGUILayout.Popup("Enemy Type", _enemyTypeIndex, _enemyTypes);')
    lines.append("")
    lines.append("            EditorGUILayout.Space();")
    lines.append('            GUILayout.Label("Level Range", EditorStyles.miniBoldLabel);')
    lines.append('            _minLevel = EditorGUILayout.IntField("Min Level", _minLevel);')
    lines.append('            _maxLevel = EditorGUILayout.IntField("Max Level", _maxLevel);')
    lines.append("            EditorGUILayout.MinMaxSlider(ref _scrollPosition.x, ref _scrollPosition.y, 1, 100);")
    lines.append("")
    lines.append("            EditorGUILayout.Space();")
    lines.append('            GUILayout.Label("Stat Curves", EditorStyles.miniBoldLabel);')
    lines.append('            _hpCurve = EditorGUILayout.CurveField("HP Curve", _hpCurve);')
    lines.append('            _atkCurve = EditorGUILayout.CurveField("ATK Curve", _atkCurve);')
    lines.append('            _defCurve = EditorGUILayout.CurveField("DEF Curve", _defCurve);')
    lines.append("")
    lines.append("            EditorGUILayout.Space();")
    lines.append('            GUILayout.Label("Preview (Level " + _minLevel + " - " + _maxLevel + ")", EditorStyles.miniBoldLabel);')
    lines.append("            for (int level = _minLevel; level <= Mathf.Min(_maxLevel, _minLevel + 10); level++)")
    lines.append("            {")
    lines.append("                float t = (float)level;")
    lines.append('                EditorGUILayout.LabelField(')
    lines.append('                    "Level " + level,')
    lines.append('                    "HP:" + _hpCurve.Evaluate(t).ToString("F0") +')
    lines.append('                    " ATK:" + _atkCurve.Evaluate(t).ToString("F0") +')
    lines.append('                    " DEF:" + _defCurve.Evaluate(t).ToString("F0"));')
    lines.append("            }")
    lines.append("")
    lines.append("            EditorGUILayout.Space();")
    lines.append('            if (GUILayout.Button("Export to JSON"))')
    lines.append("            {")
    lines.append("                ExportToJSON();")
    lines.append("            }")
    lines.append("        }")
    lines.append("")

    # ExportToJSON
    lines.append("        private void ExportToJSON()")
    lines.append("        {")
    lines.append('            var path = EditorUtility.SaveFilePanel("Export Stat Curves", Application.dataPath, "stat_curves", "json");')
    lines.append("            if (string.IsNullOrEmpty(path)) return;")
    lines.append("")
    lines.append('            var sb = new System.Text.StringBuilder();')
    lines.append('            sb.AppendLine("{");')
    lines.append('            sb.AppendLine("  \\"enemyType\\": \\"" + _enemyTypes[_enemyTypeIndex] + "\\",");')
    lines.append('            sb.AppendLine("  \\"levels\\": [");')
    lines.append("            for (int level = _minLevel; level <= _maxLevel; level++)")
    lines.append("            {")
    lines.append("                float t = (float)level;")
    lines.append('                string comma = level < _maxLevel ? "," : "";')
    lines.append('                sb.AppendLine("    { \\"level\\": " + level +')
    lines.append('                    ", \\"hp\\": " + _hpCurve.Evaluate(t).ToString("F1") +')
    lines.append('                    ", \\"atk\\": " + _atkCurve.Evaluate(t).ToString("F1") +')
    lines.append('                    ", \\"def\\": " + _defCurve.Evaluate(t).ToString("F1") +')
    lines.append('                    " }" + comma);')
    lines.append("            }")
    lines.append('            sb.AppendLine("  ]");')
    lines.append('            sb.AppendLine("}");')
    lines.append("")
    lines.append("            File.WriteAllText(path, sb.ToString());")
    lines.append('            Debug.Log("[VB_StatCurveEditor] Exported to: " + path);')
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GAME-11: Shop / Merchant system (SO + buy/sell + stat comparison + UI)
# ---------------------------------------------------------------------------


def generate_shop_system_script(
    namespace: str = "VeilBreakers.Content",
) -> tuple[str, str, str, str]:
    """Generate C# for a shop/merchant system.

    Returns:
        (merchant_data_cs, shop_system_cs, uxml, uss) tuple.
    """
    ns = _safe_namespace(namespace)

    # ----- Merchant Data SO -----
    md_lines: list[str] = []
    md_lines.append("using System;")
    md_lines.append("using System.Collections.Generic;")
    md_lines.append("using UnityEngine;")
    md_lines.append("")
    md_lines.append("namespace " + ns)
    md_lines.append("{")

    # MerchantItem
    md_lines.append("    /// <summary>An item in a merchant's inventory with optional price override.</summary>")
    md_lines.append("    [Serializable]")
    md_lines.append("    public class MerchantItem")
    md_lines.append("    {")
    md_lines.append("        public VB_ItemData item;")
    md_lines.append("        public int stock = -1; // -1 = infinite")
    md_lines.append("        public int priceOverride = -1; // -1 = use item default")
    md_lines.append("    }")
    md_lines.append("")

    # VB_MerchantInventory SO
    md_lines.append("    /// <summary>")
    md_lines.append("    /// ScriptableObject defining a merchant's inventory and settings.")
    md_lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    md_lines.append("    /// </summary>")
    md_lines.append('    [CreateAssetMenu(fileName = "NewMerchant", menuName = "VeilBreakers/Merchant Inventory")]')
    md_lines.append("    public class VB_MerchantInventory : ScriptableObject")
    md_lines.append("    {")
    md_lines.append("        public string merchantId;")
    md_lines.append("        public string merchantName;")
    md_lines.append("        public List<MerchantItem> items = new List<MerchantItem>();")
    md_lines.append("        public float sellPriceMultiplier = 0.5f;")
    md_lines.append("        public float restockTimer = 300f;")
    md_lines.append("        public bool canBuyFromPlayer = true;")
    md_lines.append("    }")
    md_lines.append("}")
    merchant_data_cs = "\n".join(md_lines)

    # ----- Shop System MonoBehaviour -----
    ss_lines: list[str] = []
    ss_lines.append("using System;")
    ss_lines.append("using System.Collections.Generic;")
    ss_lines.append("using UnityEngine;")
    ss_lines.append("using VeilBreakers.Core;")
    ss_lines.append("")
    ss_lines.append("namespace " + ns)
    ss_lines.append("{")

    # StatComparison
    ss_lines.append("    /// <summary>Stat comparison result between two items.</summary>")
    ss_lines.append("    public struct StatComparison")
    ss_lines.append("    {")
    ss_lines.append("        public string statName;")
    ss_lines.append("        public float currentValue;")
    ss_lines.append("        public float newValue;")
    ss_lines.append("        public float difference;")
    ss_lines.append("    }")
    ss_lines.append("")

    # VB_ShopSystem
    ss_lines.append("    /// <summary>")
    ss_lines.append("    /// Shop system with buy/sell, currency transactions, and stat comparison.")
    ss_lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    ss_lines.append("    /// </summary>")
    ss_lines.append("    public class VB_ShopSystem : MonoBehaviour")
    ss_lines.append("    {")
    ss_lines.append("        public static VB_ShopSystem Instance { get; private set; }")
    ss_lines.append("")
    ss_lines.append("        private VB_MerchantInventory _activeMerchant;")
    ss_lines.append("        private int _playerGold;")
    ss_lines.append("")
    ss_lines.append("        public event Action<VB_ItemData> OnItemPurchased;")
    ss_lines.append("        public event Action<VB_ItemData> OnItemSold;")
    ss_lines.append("        public VB_MerchantInventory ActiveMerchant => _activeMerchant;")
    ss_lines.append("")

    # Awake
    ss_lines.append("        private void Awake()")
    ss_lines.append("        {")
    ss_lines.append("            if (Instance != null && Instance != this) { Destroy(gameObject); return; }")
    ss_lines.append("            Instance = this;")
    ss_lines.append("        }")
    ss_lines.append("")

    # OpenShop
    ss_lines.append("        /// <summary>Open a merchant's shop.</summary>")
    ss_lines.append("        public void OpenShop(VB_MerchantInventory merchant, int playerGold)")
    ss_lines.append("        {")
    ss_lines.append("            _activeMerchant = merchant;")
    ss_lines.append("            _playerGold = playerGold;")
    ss_lines.append('            OnShopOpened?.Invoke(merchant.merchantId);')
    ss_lines.append("        }")
    ss_lines.append("")

    # CloseShop
    ss_lines.append("        /// <summary>Close the active shop.</summary>")
    ss_lines.append("        public void CloseShop()")
    ss_lines.append("        {")
    ss_lines.append("            _activeMerchant = null;")
    ss_lines.append('            OnShopClosed?.Invoke();')
    ss_lines.append("        }")
    ss_lines.append("")

    # GetBuyPrice
    ss_lines.append("        /// <summary>Get the buy price of a merchant item.</summary>")
    ss_lines.append("        public int GetBuyPrice(MerchantItem merchantItem)")
    ss_lines.append("        {")
    ss_lines.append("            if (merchantItem.priceOverride >= 0) return merchantItem.priceOverride;")
    ss_lines.append("            return merchantItem.item != null ? merchantItem.item.buyPrice : 0;")
    ss_lines.append("        }")
    ss_lines.append("")

    # GetSellPrice
    ss_lines.append("        /// <summary>Get the sell price for a player item.</summary>")
    ss_lines.append("        public int GetSellPrice(VB_ItemData item)")
    ss_lines.append("        {")
    ss_lines.append("            if (_activeMerchant == null || item == null) return 0;")
    ss_lines.append("            return Mathf.RoundToInt(item.sellPrice * _activeMerchant.sellPriceMultiplier);")
    ss_lines.append("        }")
    ss_lines.append("")

    # FormatCurrency
    ss_lines.append("        /// <summary>Format a currency amount for display.</summary>")
    ss_lines.append("        public static string FormatCurrency(int amount)")
    ss_lines.append("        {")
    ss_lines.append('            if (amount >= 1000) return (amount / 1000f).ToString("F1") + "k";')
    ss_lines.append("            return amount.ToString();")
    ss_lines.append("        }")
    ss_lines.append("")

    # Buy
    ss_lines.append("        /// <summary>Buy an item from the merchant.</summary>")
    ss_lines.append("        public bool Buy(MerchantItem merchantItem)")
    ss_lines.append("        {")
    ss_lines.append("            if (_activeMerchant == null || merchantItem == null) return false;")
    ss_lines.append("            int price = GetBuyPrice(merchantItem);")
    ss_lines.append("            if (_playerGold < price) return false;")
    ss_lines.append("            if (merchantItem.stock == 0) return false;")
    ss_lines.append("            var inventory = VB_InventorySystem.Instance;")
    ss_lines.append("            if (inventory == null || !inventory.AddItem(merchantItem.item)) return false;")
    ss_lines.append("            _playerGold -= price;")
    ss_lines.append("            if (merchantItem.stock > 0) merchantItem.stock--;")
    ss_lines.append("            OnItemPurchased?.Invoke(merchantItem.item);")
    ss_lines.append("            return true;")
    ss_lines.append("        }")
    ss_lines.append("")

    # Sell
    ss_lines.append("        /// <summary>Sell an item to the merchant.</summary>")
    ss_lines.append("        public bool Sell(VB_ItemData item)")
    ss_lines.append("        {")
    ss_lines.append("            if (_activeMerchant == null || item == null) return false;")
    ss_lines.append("            if (!_activeMerchant.canBuyFromPlayer) return false;")
    ss_lines.append("            var inventory = VB_InventorySystem.Instance;")
    ss_lines.append("            if (inventory == null || !inventory.RemoveItem(item)) return false;")
    ss_lines.append("            int sellPrice = GetSellPrice(item);")
    ss_lines.append("            _playerGold += sellPrice;")
    ss_lines.append("            OnItemSold?.Invoke(item);")
    ss_lines.append("            return true;")
    ss_lines.append("        }")
    ss_lines.append("")

    # CompareStats
    ss_lines.append("        /// <summary>Compare stats between equipped item and shop item.</summary>")
    ss_lines.append("        public List<StatComparison> CompareStats(VB_ItemData equipped, VB_ItemData shopItem)")
    ss_lines.append("        {")
    ss_lines.append("            var comparisons = new List<StatComparison>();")
    ss_lines.append("            if (shopItem == null) return comparisons;")
    ss_lines.append("            var equippedStats = new Dictionary<string, float>();")
    ss_lines.append("            if (equipped != null && equipped.statBuffs != null)")
    ss_lines.append("            {")
    ss_lines.append("                foreach (var buff in equipped.statBuffs)")
    ss_lines.append("                    equippedStats[buff.stat] = buff.amount;")
    ss_lines.append("            }")
    ss_lines.append("            if (shopItem.statBuffs != null)")
    ss_lines.append("            {")
    ss_lines.append("                foreach (var buff in shopItem.statBuffs)")
    ss_lines.append("                {")
    ss_lines.append("                    float current = equippedStats.ContainsKey(buff.stat) ? equippedStats[buff.stat] : 0f;")
    ss_lines.append("                    comparisons.Add(new StatComparison")
    ss_lines.append("                    {")
    ss_lines.append("                        statName = buff.stat,")
    ss_lines.append("                        currentValue = current,")
    ss_lines.append("                        newValue = buff.amount,")
    ss_lines.append("                        difference = buff.amount - current")
    ss_lines.append("                    });")
    ss_lines.append("                }")
    ss_lines.append("            }")
    ss_lines.append("            return comparisons;")
    ss_lines.append("        }")
    ss_lines.append("    }")
    ss_lines.append("}")
    shop_system_cs = "\n".join(ss_lines)

    # ----- UXML -----
    uxml_lines: list[str] = []
    uxml_lines.append('<ui:UXML xmlns:ui="UnityEngine.UIElements">')
    uxml_lines.append('    <ui:VisualElement name="shop-root" class="shop-root">')
    uxml_lines.append('        <ui:Label name="merchant-name" class="merchant-name" text="Merchant" />')
    uxml_lines.append('        <ui:Label name="player-gold" class="player-gold" text="Gold: 0" />')
    uxml_lines.append('        <ui:VisualElement name="shop-content" class="shop-content">')
    uxml_lines.append('            <ui:VisualElement name="merchant-items" class="merchant-items">')
    uxml_lines.append('                <ui:Label text="Buy" class="section-title" />')
    uxml_lines.append('                <ui:ScrollView name="buy-list" class="item-list" />')
    uxml_lines.append("            </ui:VisualElement>")
    uxml_lines.append('            <ui:VisualElement name="stat-comparison" class="stat-comparison">')
    uxml_lines.append('                <ui:Label text="Comparison" class="section-title" />')
    uxml_lines.append('                <ui:VisualElement name="comparison-panel" class="comparison-panel" />')
    uxml_lines.append("            </ui:VisualElement>")
    uxml_lines.append('            <ui:VisualElement name="player-items" class="player-items">')
    uxml_lines.append('                <ui:Label text="Sell" class="section-title" />')
    uxml_lines.append('                <ui:ScrollView name="sell-list" class="item-list" />')
    uxml_lines.append("            </ui:VisualElement>")
    uxml_lines.append("        </ui:VisualElement>")
    uxml_lines.append('        <ui:VisualElement name="action-bar" class="action-bar">')
    uxml_lines.append('            <ui:Button name="buy-button" class="action-button" text="Buy" />')
    uxml_lines.append('            <ui:Button name="sell-button" class="action-button" text="Sell" />')
    uxml_lines.append('            <ui:Button name="close-button" class="action-button" text="Close" />')
    uxml_lines.append("        </ui:VisualElement>")
    uxml_lines.append("    </ui:VisualElement>")
    uxml_lines.append("</ui:UXML>")
    shop_uxml = "\n".join(uxml_lines)

    # ----- USS -----
    uss_lines: list[str] = []
    uss_lines.append("/* VeilBreakers Shop - Dark Fantasy Theme */")
    uss_lines.append(".shop-root {")
    uss_lines.append("    background-color: rgba(15, 10, 10, 0.95);")
    uss_lines.append("    padding: 16px;")
    uss_lines.append("    border-color: rgb(80, 50, 30);")
    uss_lines.append("    border-width: 2px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".merchant-name {")
    uss_lines.append("    font-size: 20px;")
    uss_lines.append("    color: rgb(220, 190, 130);")
    uss_lines.append("    -unity-font-style: bold;")
    uss_lines.append("    margin-bottom: 4px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".player-gold {")
    uss_lines.append("    font-size: 14px;")
    uss_lines.append("    color: rgb(255, 215, 0);")
    uss_lines.append("    margin-bottom: 12px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".shop-content { flex-direction: row; flex-grow: 1; }")
    uss_lines.append(".merchant-items { flex-grow: 1; margin-right: 8px; }")
    uss_lines.append(".stat-comparison { width: 200px; margin-right: 8px; background-color: rgba(25, 18, 14, 0.9); padding: 8px; }")
    uss_lines.append(".player-items { flex-grow: 1; }")
    uss_lines.append(".section-title { font-size: 14px; color: rgb(200, 170, 120); -unity-font-style: bold; margin-bottom: 8px; }")
    uss_lines.append(".item-list { flex-grow: 1; background-color: rgba(25, 18, 14, 0.8); }")
    uss_lines.append(".comparison-panel { flex-grow: 1; }")
    uss_lines.append("")
    uss_lines.append(".action-bar { flex-direction: row; margin-top: 12px; justify-content: flex-end; }")
    uss_lines.append(".action-button {")
    uss_lines.append("    width: 100px;")
    uss_lines.append("    height: 32px;")
    uss_lines.append("    margin-left: 8px;")
    uss_lines.append("    background-color: rgba(50, 35, 20, 0.9);")
    uss_lines.append("    color: rgb(200, 180, 140);")
    uss_lines.append("    border-color: rgb(100, 70, 40);")
    uss_lines.append("    border-width: 1px;")
    uss_lines.append("}")
    uss_lines.append(".action-button:hover { background-color: rgba(70, 50, 30, 0.9); border-color: rgb(200, 170, 120); }")
    shop_uss = "\n".join(uss_lines)

    return (merchant_data_cs, shop_system_cs, shop_uxml, shop_uss)


# ---------------------------------------------------------------------------
# RPG-05: Journal / Codex system (Lore/Bestiary/Items + tabbed UI)
# ---------------------------------------------------------------------------


def generate_journal_system_script(
    namespace: str = "VeilBreakers.Content",
) -> tuple[str, str, str, str]:
    """Generate C# for a journal/codex system with progressive unlock.

    Returns:
        (journal_data_cs, journal_system_cs, uxml, uss) tuple.
    """
    ns = _safe_namespace(namespace)

    # ----- Journal Data SO -----
    jd_lines: list[str] = []
    jd_lines.append("using System;")
    jd_lines.append("using System.Collections.Generic;")
    jd_lines.append("using UnityEngine;")
    jd_lines.append("")
    jd_lines.append("namespace " + ns)
    jd_lines.append("{")

    # JournalEntryType enum
    jd_lines.append("    /// <summary>Types of journal entries.</summary>")
    jd_lines.append("    public enum JournalEntryType")
    jd_lines.append("    {")
    jd_lines.append("        Lore,")
    jd_lines.append("        Bestiary,")
    jd_lines.append("        Items")
    jd_lines.append("    }")
    jd_lines.append("")

    # MonsterWeakness
    jd_lines.append("    /// <summary>Bestiary weakness entry.</summary>")
    jd_lines.append("    [Serializable]")
    jd_lines.append("    public class MonsterWeakness")
    jd_lines.append("    {")
    jd_lines.append("        public string element;")
    jd_lines.append("        public float multiplier = 1.5f;")
    jd_lines.append("    }")
    jd_lines.append("")

    # BestiaryStats
    jd_lines.append("    /// <summary>Monster stat block for bestiary entries.</summary>")
    jd_lines.append("    [Serializable]")
    jd_lines.append("    public class BestiaryStats")
    jd_lines.append("    {")
    jd_lines.append("        public int hp;")
    jd_lines.append("        public int atk;")
    jd_lines.append("        public int def;")
    jd_lines.append("        public List<MonsterWeakness> weaknesses = new List<MonsterWeakness>();")
    jd_lines.append("    }")
    jd_lines.append("")

    # VB_JournalEntry SO
    jd_lines.append("    /// <summary>")
    jd_lines.append("    /// ScriptableObject for a journal/codex entry.")
    jd_lines.append("    /// Supports Lore, Bestiary, and Items tabs with progressive unlock.")
    jd_lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    jd_lines.append("    /// </summary>")
    jd_lines.append('    [CreateAssetMenu(fileName = "NewJournalEntry", menuName = "VeilBreakers/Journal Entry")]')
    jd_lines.append("    public class VB_JournalEntry : ScriptableObject")
    jd_lines.append("    {")
    jd_lines.append("        public string entryId;")
    jd_lines.append("        public string title;")
    jd_lines.append("        [TextArea(3, 10)] public string content;")
    jd_lines.append("        public JournalEntryType entryType;")
    jd_lines.append("        public Sprite icon;")
    jd_lines.append("")
    jd_lines.append('        [Header("Discovery")]')
    jd_lines.append("        public string discoveryCondition;")
    jd_lines.append("        public bool isHidden = true;")
    jd_lines.append("")
    jd_lines.append('        [Header("Bestiary (optional)")]')
    jd_lines.append("        public BestiaryStats bestiaryStats;")
    jd_lines.append("    }")
    jd_lines.append("}")
    journal_data_cs = "\n".join(jd_lines)

    # ----- Journal System MonoBehaviour -----
    js_lines: list[str] = []
    js_lines.append("using System;")
    js_lines.append("using System.Collections.Generic;")
    js_lines.append("using System.Linq;")
    js_lines.append("using UnityEngine;")
    js_lines.append("using VeilBreakers.Core;")
    js_lines.append("")
    js_lines.append("namespace " + ns)
    js_lines.append("{")

    # VB_JournalSystem
    js_lines.append("    /// <summary>")
    js_lines.append("    /// Journal/codex system with progressive unlock and category filtering.")
    js_lines.append("    /// Integrates with EventBus for discovery events.")
    js_lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    js_lines.append("    /// </summary>")
    js_lines.append("    public class VB_JournalSystem : MonoBehaviour")
    js_lines.append("    {")
    js_lines.append("        public static VB_JournalSystem Instance { get; private set; }")
    js_lines.append("")
    js_lines.append("        [SerializeField] private List<VB_JournalEntry> _allEntries = new List<VB_JournalEntry>();")
    js_lines.append("        private HashSet<string> _discoveredEntries = new HashSet<string>();")
    js_lines.append("")
    js_lines.append("        public event Action<VB_JournalEntry> OnEntryDiscovered;")
    js_lines.append("")

    # Awake
    js_lines.append("        private void Awake()")
    js_lines.append("        {")
    js_lines.append("            if (Instance != null && Instance != this) { Destroy(gameObject); return; }")
    js_lines.append("            Instance = this;")
    js_lines.append("        }")
    js_lines.append("")

    # DiscoverEntry
    js_lines.append("        /// <summary>Discover a journal entry (progressive unlock).</summary>")
    js_lines.append("        public bool DiscoverEntry(string entryId)")
    js_lines.append("        {")
    js_lines.append("            if (_discoveredEntries.Contains(entryId)) return false;")
    js_lines.append("            var entry = _allEntries.Find(e => e.entryId == entryId);")
    js_lines.append("            if (entry == null) return false;")
    js_lines.append("            _discoveredEntries.Add(entryId);")
    js_lines.append("            OnEntryDiscovered?.Invoke(entry);")
    js_lines.append("            return true;")
    js_lines.append("        }")
    js_lines.append("")

    # GetEntries
    js_lines.append("        /// <summary>Get all discovered entries of a type.</summary>")
    js_lines.append("        public List<VB_JournalEntry> GetEntries(JournalEntryType type)")
    js_lines.append("        {")
    js_lines.append("            return _allEntries")
    js_lines.append("                .Where(e => e.entryType == type && _discoveredEntries.Contains(e.entryId))")
    js_lines.append("                .ToList();")
    js_lines.append("        }")
    js_lines.append("")

    # GetAllDiscovered
    js_lines.append("        /// <summary>Get all discovered entries regardless of type.</summary>")
    js_lines.append("        public List<VB_JournalEntry> GetAllDiscovered()")
    js_lines.append("        {")
    js_lines.append("            return _allEntries.Where(e => _discoveredEntries.Contains(e.entryId)).ToList();")
    js_lines.append("        }")
    js_lines.append("")

    # IsDiscovered
    js_lines.append("        /// <summary>Check if an entry has been discovered.</summary>")
    js_lines.append("        public bool IsDiscovered(string entryId)")
    js_lines.append("        {")
    js_lines.append("            return _discoveredEntries.Contains(entryId);")
    js_lines.append("        }")
    js_lines.append("")

    # GetDiscoveryProgress
    js_lines.append("        /// <summary>Get discovery progress for a category (discovered/total).</summary>")
    js_lines.append("        public (int discovered, int total) GetDiscoveryProgress(JournalEntryType type)")
    js_lines.append("        {")
    js_lines.append("            var ofType = _allEntries.Where(e => e.entryType == type).ToList();")
    js_lines.append("            int discovered = ofType.Count(e => _discoveredEntries.Contains(e.entryId));")
    js_lines.append("            return (discovered, ofType.Count);")
    js_lines.append("        }")
    js_lines.append("    }")
    js_lines.append("}")
    journal_system_cs = "\n".join(js_lines)

    # ----- UXML -----
    uxml_lines: list[str] = []
    uxml_lines.append('<ui:UXML xmlns:ui="UnityEngine.UIElements">')
    uxml_lines.append('    <ui:VisualElement name="journal-root" class="journal-root">')
    uxml_lines.append('        <ui:Label text="Journal" class="journal-title" />')
    uxml_lines.append('        <ui:VisualElement name="tab-bar" class="tab-bar">')
    uxml_lines.append('            <ui:Button name="tab-lore" class="tab-button active" text="Lore" />')
    uxml_lines.append('            <ui:Button name="tab-bestiary" class="tab-button" text="Bestiary" />')
    uxml_lines.append('            <ui:Button name="tab-items" class="tab-button" text="Items" />')
    uxml_lines.append("        </ui:VisualElement>")
    uxml_lines.append('        <ui:VisualElement name="journal-content" class="journal-content">')
    uxml_lines.append('            <ui:ScrollView name="entry-list" class="entry-list" />')
    uxml_lines.append('            <ui:VisualElement name="entry-detail" class="entry-detail">')
    uxml_lines.append('                <ui:VisualElement name="entry-icon" class="entry-icon" />')
    uxml_lines.append('                <ui:Label name="entry-title" class="entry-title" />')
    uxml_lines.append('                <ui:Label name="entry-content" class="entry-content" />')
    uxml_lines.append('                <ui:VisualElement name="bestiary-stats" class="bestiary-stats" />')
    uxml_lines.append("            </ui:VisualElement>")
    uxml_lines.append("        </ui:VisualElement>")
    uxml_lines.append("    </ui:VisualElement>")
    uxml_lines.append("</ui:UXML>")
    journal_uxml = "\n".join(uxml_lines)

    # ----- USS -----
    uss_lines: list[str] = []
    uss_lines.append("/* VeilBreakers Journal - Dark Fantasy Theme */")
    uss_lines.append(".journal-root {")
    uss_lines.append("    background-color: rgba(15, 10, 10, 0.95);")
    uss_lines.append("    padding: 16px;")
    uss_lines.append("    border-color: rgb(80, 50, 30);")
    uss_lines.append("    border-width: 2px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".journal-title {")
    uss_lines.append("    font-size: 20px;")
    uss_lines.append("    color: rgb(220, 190, 130);")
    uss_lines.append("    -unity-font-style: bold;")
    uss_lines.append("    margin-bottom: 12px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".tab-bar { flex-direction: row; margin-bottom: 8px; }")
    uss_lines.append(".tab-button {")
    uss_lines.append("    flex-grow: 1;")
    uss_lines.append("    height: 30px;")
    uss_lines.append("    background-color: rgba(30, 22, 16, 0.8);")
    uss_lines.append("    color: rgb(160, 140, 100);")
    uss_lines.append("    border-color: rgb(60, 40, 25);")
    uss_lines.append("    border-width: 1px;")
    uss_lines.append("}")
    uss_lines.append(".tab-button.active { background-color: rgba(60, 42, 28, 0.9); color: rgb(220, 190, 130); }")
    uss_lines.append("")
    uss_lines.append(".journal-content { flex-direction: row; flex-grow: 1; }")
    uss_lines.append(".entry-list { width: 250px; margin-right: 12px; background-color: rgba(25, 18, 14, 0.8); }")
    uss_lines.append(".entry-detail { flex-grow: 1; background-color: rgba(25, 18, 14, 0.9); padding: 12px; }")
    uss_lines.append(".entry-icon { width: 64px; height: 64px; margin-bottom: 8px; }")
    uss_lines.append(".entry-title { font-size: 16px; color: rgb(220, 190, 130); -unity-font-style: bold; }")
    uss_lines.append(".entry-content { font-size: 12px; color: rgb(180, 160, 120); margin-top: 8px; white-space: normal; }")
    uss_lines.append(".bestiary-stats { margin-top: 12px; padding: 8px; background-color: rgba(40, 30, 20, 0.7); }")
    journal_uss = "\n".join(uss_lines)

    return (journal_data_cs, journal_system_cs, journal_uxml, journal_uss)
