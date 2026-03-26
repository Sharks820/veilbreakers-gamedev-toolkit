"""Equipment attachment C# template generators for Unity.

Provides:
    generate_equipment_attachment_script -- EQUIP-06: SkinnedMeshRenderer bone
        rebinding + Multi-Parent Constraint weapon sheathing.

These are RUNTIME scripts.  They must NEVER reference ``using UnityEditor;``.

CRITICAL DESIGN PRINCIPLE: Generated MonoBehaviours call into existing
static utility classes.  They do NOT reimplement brand effectiveness
matrices, synergy calculations, corruption formulas, or damage pipelines.
  - C# events for equipment change notifications
  - Phase 9 bone socket system (10 standard sockets)
"""

from __future__ import annotations

import re
from typing import Optional

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier


def _safe_namespace(ns: str) -> str:
    """Sanitize a C# namespace to prevent code injection.

    Valid C# namespaces allow only letters, digits, underscores, and dots.
    Strips everything else.  Segments starting with a digit get a ``_``
    prefix, and segments that are C# reserved words get an ``@`` prefix.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_.]", "", ns)
    sanitized = re.sub(r"\.{2,}", ".", sanitized).strip(".")
    if not sanitized:
        return "Generated"
    # Validate each segment: fix leading-digit and reserved-word segments
    _cs_reserved = frozenset({
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
    segments = sanitized.split(".")
    fixed: list[str] = []
    for seg in segments:
        if not seg:
            continue
        if seg[0].isdigit():
            seg = f"_{seg}"
        if seg in _cs_reserved:
            seg = f"@{seg}"
        fixed.append(seg)
    return ".".join(fixed) or "Generated"


# Standard bone sockets from Phase 9 bone socket system
STANDARD_BONE_SOCKETS = [
    "weapon_hand_R",
    "weapon_hand_L",
    "shield_hand_L",
    "back_weapon",
    "hip_L",
    "hip_R",
    "head",
    "chest",
    "spell_hand_R",
    "spell_hand_L",
]


def generate_equipment_attachment_script(
    namespace: str = "VeilBreakers.Equipment",
) -> tuple[str, str]:
    """Generate C# for equipment attachment with bone rebinding and weapon sheathing.

    Returns:
        (attachment_cs, weapon_sheath_cs) tuple.

    attachment_cs -- VB_EquipmentAttachment MonoBehaviour:
        - SkinnedMeshRenderer bone rebinding using name-based Dictionary<string, Transform>
        - BuildBoneMap(Transform root) recursive helper
        - RebindToArmature(SkinnedMeshRenderer equipmentSMR, Transform armatureRoot)
        - EquipArmor / UnequipArmor for slot management
        - Equipment slot tracking
        - C# event (OnEquipmentChanged) for equipment change notifications
        - References Phase 9 bone socket system (10 standard sockets)

    weapon_sheath_cs -- VB_WeaponSheath MonoBehaviour:
        - Multi-Parent Constraint from Animation Rigging for drawn/sheathed positions
        - SetDrawn() / SetSheathed() with weight animation
        - Configurable drawn and sheathed parent transforms
    """
    ns = _safe_namespace(namespace)

    # ----- VB_EquipmentAttachment -----
    att_lines: list[str] = []
    att_lines.append("using System;")
    att_lines.append("using System.Collections.Generic;")
    att_lines.append("using UnityEngine;")
    att_lines.append("")
    att_lines.append(f"namespace {ns}")
    att_lines.append("{")

    # Equipment slot enum
    att_lines.append("    /// <summary>Equipment slots matching Phase 9 bone socket system.</summary>")
    att_lines.append("    public enum EquipmentSlot")
    att_lines.append("    {")
    att_lines.append("        Head,")
    att_lines.append("        Torso,")
    att_lines.append("        Arms,")
    att_lines.append("        Legs,")
    att_lines.append("        WeaponRight,")
    att_lines.append("        WeaponLeft,")
    att_lines.append("        Shield,")
    att_lines.append("        Accessory1,")
    att_lines.append("        Accessory2")
    att_lines.append("    }")
    att_lines.append("")

    # Equipment change event
    att_lines.append("    /// <summary>Event data for equipment change notifications.</summary>")
    att_lines.append("    [Serializable]")
    att_lines.append("    public struct EquipmentChangeEvent")
    att_lines.append("    {")
    att_lines.append("        public EquipmentSlot Slot;")
    att_lines.append("        public string ItemName;")
    att_lines.append("        public bool Equipped;")
    att_lines.append("    }")
    att_lines.append("")

    # Main class
    att_lines.append("    /// <summary>")
    att_lines.append("    /// Equipment attachment system using SkinnedMeshRenderer bone rebinding.")
    att_lines.append("    /// Uses name-based bone matching for robust cross-armature equipment swapping.")
    att_lines.append("    /// Integrates with Phase 9 bone socket system (10 standard sockets).")
    att_lines.append("    /// </summary>")
    att_lines.append("    public class VB_EquipmentAttachment : MonoBehaviour")
    att_lines.append("    {")

    # Standard bone socket names
    att_lines.append("        /// <summary>Standard bone socket names from Phase 9 system.</summary>")
    att_lines.append("        public static readonly string[] StandardBoneSockets = new string[]")
    att_lines.append("        {")
    for sock in STANDARD_BONE_SOCKETS:
        att_lines.append(f'            "{sock}",')
    att_lines.append("        };")
    att_lines.append("")

    # Fields
    att_lines.append("        [Header(\"Armature Configuration\")]")
    att_lines.append("        [Tooltip(\"Root transform of the character armature.\")]")
    att_lines.append("        [SerializeField] private Transform _armatureRoot;")
    att_lines.append("")
    att_lines.append("        [Tooltip(\"SkinnedMeshRenderer of the base character body.\")]")
    att_lines.append("        [SerializeField] private SkinnedMeshRenderer _baseMeshRenderer;")
    att_lines.append("")
    att_lines.append("        /// <summary>Currently equipped items by slot.</summary>")
    att_lines.append("        private readonly Dictionary<EquipmentSlot, SkinnedMeshRenderer> _equippedItems =")
    att_lines.append("            new Dictionary<EquipmentSlot, SkinnedMeshRenderer>();")
    att_lines.append("")
    att_lines.append("        /// <summary>Cached bone map for the character armature.</summary>")
    att_lines.append("        private Dictionary<string, Transform> _boneMap;")
    att_lines.append("")
    att_lines.append("        /// <summary>Fired when equipment is changed (equipped or unequipped).</summary>")
    att_lines.append("        public event Action<EquipmentChangeEvent> OnEquipmentChanged;")
    att_lines.append("")

    # Awake
    att_lines.append("        private void Awake()")
    att_lines.append("        {")
    att_lines.append("            if (_armatureRoot == null)")
    att_lines.append("            {")
    att_lines.append("                _armatureRoot = transform.Find(\"Armature\");")
    att_lines.append("            }")
    att_lines.append("            if (_armatureRoot != null)")
    att_lines.append("            {")
    att_lines.append("                _boneMap = BuildBoneMap(_armatureRoot);")
    att_lines.append("            }")
    att_lines.append("            else")
    att_lines.append("            {")
    att_lines.append('                Debug.LogWarning("[VB_EquipmentAttachment] No armature root found.");')
    att_lines.append("            }")
    att_lines.append("        }")
    att_lines.append("")

    # BuildBoneMap
    att_lines.append("        /// <summary>")
    att_lines.append("        /// Recursively build a name-to-transform lookup for all bones in the hierarchy.")
    att_lines.append("        /// Uses Dictionary&lt;string, Transform&gt; for O(1) bone matching by name.")
    att_lines.append("        /// </summary>")
    att_lines.append("        public static Dictionary<string, Transform> BuildBoneMap(Transform root)")
    att_lines.append("        {")
    att_lines.append("            var map = new Dictionary<string, Transform>();")
    att_lines.append("            PopulateBoneMapRecursive(root, map);")
    att_lines.append("            return map;")
    att_lines.append("        }")
    att_lines.append("")
    att_lines.append("        private static void PopulateBoneMapRecursive(Transform current, Dictionary<string, Transform> map)")
    att_lines.append("        {")
    att_lines.append("            if (!map.ContainsKey(current.name))")
    att_lines.append("            {")
    att_lines.append("                map[current.name] = current;")
    att_lines.append("            }")
    att_lines.append("            for (int i = 0; i < current.childCount; i++)")
    att_lines.append("            {")
    att_lines.append("                PopulateBoneMapRecursive(current.GetChild(i), map);")
    att_lines.append("            }")
    att_lines.append("        }")
    att_lines.append("")

    # RebindToArmature
    att_lines.append("        /// <summary>")
    att_lines.append("        /// Rebind a SkinnedMeshRenderer to this character's armature using name-based matching.")
    att_lines.append("        /// Remaps bones[] array by matching bone names in the character's bone map.")
    att_lines.append("        /// </summary>")
    att_lines.append("        public void RebindToArmature(SkinnedMeshRenderer equipmentSMR, Transform armatureRoot)")
    att_lines.append("        {")
    att_lines.append("            if (equipmentSMR == null)")
    att_lines.append("            {")
    att_lines.append('                Debug.LogError("[VB_EquipmentAttachment] equipmentSMR is null.");')
    att_lines.append("                return;")
    att_lines.append("            }")
    att_lines.append("")
    att_lines.append("            Dictionary<string, Transform> targetMap = _boneMap;")
    att_lines.append("            if (armatureRoot != _armatureRoot)")
    att_lines.append("            {")
    att_lines.append("                targetMap = BuildBoneMap(armatureRoot);")
    att_lines.append("            }")
    att_lines.append("")
    att_lines.append("            Transform[] originalBones = equipmentSMR.bones;")
    att_lines.append("            Transform[] newBones = new Transform[originalBones.Length];")
    att_lines.append("")
    att_lines.append("            for (int i = 0; i < originalBones.Length; i++)")
    att_lines.append("            {")
    att_lines.append("                if (originalBones[i] != null && targetMap.TryGetValue(originalBones[i].name, out Transform mapped))")
    att_lines.append("                {")
    att_lines.append("                    newBones[i] = mapped;")
    att_lines.append("                }")
    att_lines.append("                else")
    att_lines.append("                {")
    att_lines.append("                    if (originalBones[i] != null)")
    att_lines.append("                    {")
    att_lines.append('                        Debug.LogWarning($"[VB_EquipmentAttachment] Bone \'{originalBones[i].name}\' not found in target armature.");')
    att_lines.append("                    }")
    att_lines.append("                    newBones[i] = null;")
    att_lines.append("                }")
    att_lines.append("            }")
    att_lines.append("")
    att_lines.append("            equipmentSMR.bones = newBones;")
    att_lines.append("")
    att_lines.append("            // Rebind the root bone as well")
    att_lines.append("            if (equipmentSMR.rootBone != null && targetMap.TryGetValue(equipmentSMR.rootBone.name, out Transform newRoot))")
    att_lines.append("            {")
    att_lines.append("                equipmentSMR.rootBone = newRoot;")
    att_lines.append("            }")
    att_lines.append("        }")
    att_lines.append("")

    # EquipArmor
    att_lines.append("        /// <summary>")
    att_lines.append("        /// Equip armor to a specific slot. Rebinds the SkinnedMeshRenderer to the character armature.")
    att_lines.append("        /// Fires OnEquipmentChanged event.")
    att_lines.append("        /// </summary>")
    att_lines.append("        public void EquipArmor(SkinnedMeshRenderer armorSMR, EquipmentSlot slot = EquipmentSlot.Torso, string itemName = \"\")")
    att_lines.append("        {")
    att_lines.append("            if (armorSMR == null)")
    att_lines.append("            {")
    att_lines.append('                Debug.LogError("[VB_EquipmentAttachment] armorSMR is null.");')
    att_lines.append("                return;")
    att_lines.append("            }")
    att_lines.append("")
    att_lines.append("            if (_armatureRoot == null)")
    att_lines.append("            {")
    att_lines.append('                Debug.LogError("[VB_EquipmentAttachment] _armatureRoot is null. Cannot equip armor without armature.");')
    att_lines.append("                return;")
    att_lines.append("            }")
    att_lines.append("")
    att_lines.append("            // Unequip existing item in this slot")
    att_lines.append("            UnequipArmor(slot);")
    att_lines.append("")
    att_lines.append("            // Rebind to character armature")
    att_lines.append("            RebindToArmature(armorSMR, _armatureRoot);")
    att_lines.append("")
    att_lines.append("            // Track equipped item")
    att_lines.append("            _equippedItems[slot] = armorSMR;")
    att_lines.append("            armorSMR.gameObject.SetActive(true);")
    att_lines.append("")
    att_lines.append("            // Fire equipment changed event")
    att_lines.append("            OnEquipmentChanged?.Invoke(new EquipmentChangeEvent")
    att_lines.append("            {")
    att_lines.append("                Slot = slot,")
    att_lines.append("                ItemName = itemName,")
    att_lines.append("                Equipped = true")
    att_lines.append("            });")
    att_lines.append("        }")
    att_lines.append("")

    # UnequipArmor
    att_lines.append("        /// <summary>")
    att_lines.append("        /// Unequip armor from a specific slot. Deactivates the equipment GameObject.")
    att_lines.append("        /// Fires OnEquipmentChanged event.")
    att_lines.append("        /// </summary>")
    att_lines.append("        public void UnequipArmor(EquipmentSlot slot)")
    att_lines.append("        {")
    att_lines.append("            if (_equippedItems.TryGetValue(slot, out SkinnedMeshRenderer existing))")
    att_lines.append("            {")
    att_lines.append("                if (existing != null)")
    att_lines.append("                {")
    att_lines.append("                    existing.gameObject.SetActive(false);")
    att_lines.append("                }")
    att_lines.append("                _equippedItems.Remove(slot);")
    att_lines.append("")
    att_lines.append("                OnEquipmentChanged?.Invoke(new EquipmentChangeEvent")
    att_lines.append("                {")
    att_lines.append("                    Slot = slot,")
    att_lines.append('                    ItemName = "",')
    att_lines.append("                    Equipped = false")
    att_lines.append("                });")
    att_lines.append("            }")
    att_lines.append("        }")
    att_lines.append("")

    # UnequipArmor by name overload
    att_lines.append("        /// <summary>Unequip armor by slot name string (convenience overload).</summary>")
    att_lines.append("        public void UnequipArmor(string slotName)")
    att_lines.append("        {")
    att_lines.append("            if (Enum.TryParse<EquipmentSlot>(slotName, true, out EquipmentSlot slot))")
    att_lines.append("            {")
    att_lines.append("                UnequipArmor(slot);")
    att_lines.append("            }")
    att_lines.append("            else")
    att_lines.append("            {")
    att_lines.append('                Debug.LogWarning($"[VB_EquipmentAttachment] Unknown slot name: {slotName}");')
    att_lines.append("            }")
    att_lines.append("        }")
    att_lines.append("")

    # GetEquipped
    att_lines.append("        /// <summary>Get the SkinnedMeshRenderer equipped in a given slot, or null.</summary>")
    att_lines.append("        public SkinnedMeshRenderer GetEquipped(EquipmentSlot slot)")
    att_lines.append("        {")
    att_lines.append("            _equippedItems.TryGetValue(slot, out SkinnedMeshRenderer smr);")
    att_lines.append("            return smr;")
    att_lines.append("        }")
    att_lines.append("")

    # IsSlotOccupied
    att_lines.append("        /// <summary>Check whether a slot currently has equipment.</summary>")
    att_lines.append("        public bool IsSlotOccupied(EquipmentSlot slot)")
    att_lines.append("        {")
    att_lines.append("            return _equippedItems.ContainsKey(slot);")
    att_lines.append("        }")
    att_lines.append("")

    # UnequipAll
    att_lines.append("        /// <summary>Unequip all equipment from all slots.</summary>")
    att_lines.append("        public void UnequipAll()")
    att_lines.append("        {")
    att_lines.append("            var slots = new List<EquipmentSlot>(_equippedItems.Keys);")
    att_lines.append("            foreach (EquipmentSlot slot in slots)")
    att_lines.append("            {")
    att_lines.append("                UnequipArmor(slot);")
    att_lines.append("            }")
    att_lines.append("        }")

    # Close class and namespace
    att_lines.append("    }")
    att_lines.append("}")

    attachment_cs = "\n".join(att_lines) + "\n"

    # ----- VB_WeaponSheath -----
    ws_lines: list[str] = []
    ws_lines.append("using System;")
    ws_lines.append("using System.Collections;")
    ws_lines.append("using UnityEngine;")
    ws_lines.append("using UnityEngine.Animations.Rigging;")
    ws_lines.append("")
    ws_lines.append(f"namespace {ns}")
    ws_lines.append("{")

    ws_lines.append("    /// <summary>")
    ws_lines.append("    /// Weapon sheathing system using Animation Rigging Multi-Parent Constraint.")
    ws_lines.append("    /// Blends between drawn and sheathed positions via constraint source weights.")
    ws_lines.append("    /// Requires the com.unity.animation.rigging package.")
    ws_lines.append("    /// </summary>")
    ws_lines.append("    [RequireComponent(typeof(MultiParentConstraint))]")
    ws_lines.append("    public class VB_WeaponSheath : MonoBehaviour")
    ws_lines.append("    {")

    # Fields
    ws_lines.append("        [Header(\"Sheath Configuration\")]")
    ws_lines.append("        [Tooltip(\"Transform of the bone socket for the drawn (in-hand) position.\")]")
    ws_lines.append("        [SerializeField] private Transform _drawnParent;")
    ws_lines.append("")
    ws_lines.append("        [Tooltip(\"Transform of the bone socket for the sheathed (holstered) position.\")]")
    ws_lines.append("        [SerializeField] private Transform _sheathedParent;")
    ws_lines.append("")
    ws_lines.append("        [Tooltip(\"Duration of the draw/sheathe weight transition.\")]")
    ws_lines.append("        [SerializeField] private float _transitionDuration = 0.25f;")
    ws_lines.append("")
    ws_lines.append("        private MultiParentConstraint _constraint;")
    ws_lines.append("        private bool _isDrawn = true;")
    ws_lines.append("        private Coroutine _transitionCoroutine;")
    ws_lines.append("")

    # Awake
    ws_lines.append("        private void Awake()")
    ws_lines.append("        {")
    ws_lines.append("            _constraint = GetComponent<MultiParentConstraint>();")
    ws_lines.append("        }")
    ws_lines.append("")

    # Start -- set up sources
    ws_lines.append("        private void Start()")
    ws_lines.append("        {")
    ws_lines.append("            if (_constraint == null) return;")
    ws_lines.append("")
    ws_lines.append("            // Ensure sources are configured: index 0 = drawn, index 1 = sheathed")
    ws_lines.append("            var data = _constraint.data;")
    ws_lines.append("            var sourceObjects = data.sourceObjects;")
    ws_lines.append("            if (sourceObjects.Count < 2)")
    ws_lines.append("            {")
    ws_lines.append("                // Auto-configure sources if not already set")
    ws_lines.append("                sourceObjects.Clear();")
    ws_lines.append("                if (_drawnParent != null)")
    ws_lines.append("                {")
    ws_lines.append("                    sourceObjects.Add(new WeightedTransform(_drawnParent, 1f));")
    ws_lines.append("                }")
    ws_lines.append("                if (_sheathedParent != null)")
    ws_lines.append("                {")
    ws_lines.append("                    sourceObjects.Add(new WeightedTransform(_sheathedParent, 0f));")
    ws_lines.append("                }")
    ws_lines.append("                data.sourceObjects = sourceObjects;")
    ws_lines.append("                _constraint.data = data;")
    ws_lines.append("            }")
    ws_lines.append("        }")
    ws_lines.append("")

    # SetDrawn
    ws_lines.append("        /// <summary>")
    ws_lines.append("        /// Transition weapon to the drawn (in-hand) position.")
    ws_lines.append("        /// Sets source weight[0] (drawn) to 1 and source weight[1] (sheathed) to 0.")
    ws_lines.append("        /// </summary>")
    ws_lines.append("        public void SetDrawn()")
    ws_lines.append("        {")
    ws_lines.append("            if (_isDrawn) return;")
    ws_lines.append("            _isDrawn = true;")
    ws_lines.append("            TransitionWeights(1f, 0f);")
    ws_lines.append("        }")
    ws_lines.append("")

    # SetSheathed
    ws_lines.append("        /// <summary>")
    ws_lines.append("        /// Transition weapon to the sheathed (holstered) position.")
    ws_lines.append("        /// Sets source weight[0] (drawn) to 0 and source weight[1] (sheathed) to 1.")
    ws_lines.append("        /// </summary>")
    ws_lines.append("        public void SetSheathed()")
    ws_lines.append("        {")
    ws_lines.append("            if (!_isDrawn) return;")
    ws_lines.append("            _isDrawn = false;")
    ws_lines.append("            TransitionWeights(0f, 1f);")
    ws_lines.append("        }")
    ws_lines.append("")

    # IsDrawn property
    ws_lines.append("        /// <summary>Whether the weapon is currently drawn (true) or sheathed (false).</summary>")
    ws_lines.append("        public bool IsDrawn => _isDrawn;")
    ws_lines.append("")

    # Toggle
    ws_lines.append("        /// <summary>Toggle between drawn and sheathed states.</summary>")
    ws_lines.append("        public void Toggle()")
    ws_lines.append("        {")
    ws_lines.append("            if (_isDrawn) SetSheathed();")
    ws_lines.append("            else SetDrawn();")
    ws_lines.append("        }")
    ws_lines.append("")

    # TransitionWeights
    ws_lines.append("        private void TransitionWeights(float drawnWeight, float sheathedWeight)")
    ws_lines.append("        {")
    ws_lines.append("            if (_transitionCoroutine != null)")
    ws_lines.append("            {")
    ws_lines.append("                StopCoroutine(_transitionCoroutine);")
    ws_lines.append("            }")
    ws_lines.append("            _transitionCoroutine = StartCoroutine(AnimateWeights(drawnWeight, sheathedWeight));")
    ws_lines.append("        }")
    ws_lines.append("")

    # AnimateWeights coroutine
    ws_lines.append("        private IEnumerator AnimateWeights(float targetDrawn, float targetSheathed)")
    ws_lines.append("        {")
    ws_lines.append("            var data = _constraint.data;")
    ws_lines.append("            var sources = data.sourceObjects;")
    ws_lines.append("            if (sources.Count < 2) yield break;")
    ws_lines.append("")
    ws_lines.append("            float startDrawn = sources[0].weight;")
    ws_lines.append("            float startSheathed = sources[1].weight;")
    ws_lines.append("            float elapsed = 0f;")
    ws_lines.append("")
    ws_lines.append("            while (elapsed < _transitionDuration)")
    ws_lines.append("            {")
    ws_lines.append("                elapsed += Time.deltaTime;")
    ws_lines.append("                float t = Mathf.Clamp01(elapsed / _transitionDuration);")
    ws_lines.append("")
    ws_lines.append("                var drawn = sources[0];")
    ws_lines.append("                drawn.weight = Mathf.Lerp(startDrawn, targetDrawn, t);")
    ws_lines.append("                sources[0] = drawn;")
    ws_lines.append("")
    ws_lines.append("                var sheathed = sources[1];")
    ws_lines.append("                sheathed.weight = Mathf.Lerp(startSheathed, targetSheathed, t);")
    ws_lines.append("                sources[1] = sheathed;")
    ws_lines.append("")
    ws_lines.append("                data.sourceObjects = sources;")
    ws_lines.append("                _constraint.data = data;")
    ws_lines.append("                yield return null;")
    ws_lines.append("            }")
    ws_lines.append("")
    ws_lines.append("            // Snap to final values")
    ws_lines.append("            var finalDrawn = sources[0];")
    ws_lines.append("            finalDrawn.weight = targetDrawn;")
    ws_lines.append("            sources[0] = finalDrawn;")
    ws_lines.append("")
    ws_lines.append("            var finalSheathed = sources[1];")
    ws_lines.append("            finalSheathed.weight = targetSheathed;")
    ws_lines.append("            sources[1] = finalSheathed;")
    ws_lines.append("")
    ws_lines.append("            data.sourceObjects = sources;")
    ws_lines.append("            _constraint.data = data;")
    ws_lines.append("            _transitionCoroutine = null;")
    ws_lines.append("        }")

    # Close class and namespace
    ws_lines.append("    }")
    ws_lines.append("}")

    weapon_sheath_cs = "\n".join(ws_lines) + "\n"

    return (attachment_cs, weapon_sheath_cs)
