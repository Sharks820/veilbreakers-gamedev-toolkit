"""Unit tests for Unity equipment attachment C# template generators.

Tests that each generator function produces valid C# source containing
the expected keywords, Unity API calls, and parameter substitutions.
Equipment attachment templates generate runtime MonoBehaviour scripts --
they must NEVER contain 'using UnityEditor;'.
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.equipment_templates import (
    generate_equipment_attachment_script,
    STANDARD_BONE_SOCKETS,
)


# ---------------------------------------------------------------------------
# Equipment attachment template (EQUIP-06)
# ---------------------------------------------------------------------------


class TestEquipmentAttachment:
    """Tests for generate_equipment_attachment_script() -- attachment output."""

    def test_returns_tuple(self):
        result = generate_equipment_attachment_script()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_attachment_contains_class(self):
        att, _ = generate_equipment_attachment_script()
        assert "class VB_EquipmentAttachment" in att

    def test_attachment_extends_monobehaviour(self):
        att, _ = generate_equipment_attachment_script()
        assert "MonoBehaviour" in att

    def test_no_editor_namespace_in_attachment(self):
        att, _ = generate_equipment_attachment_script()
        assert "using UnityEditor" not in att

    def test_skinned_mesh_renderer_bone_rebinding(self):
        att, _ = generate_equipment_attachment_script()
        assert "SkinnedMeshRenderer" in att

    def test_name_based_bone_lookup(self):
        att, _ = generate_equipment_attachment_script()
        assert "Dictionary<string, Transform>" in att

    def test_build_bone_map_present(self):
        att, _ = generate_equipment_attachment_script()
        assert "BuildBoneMap" in att

    def test_build_bone_map_recursive(self):
        att, _ = generate_equipment_attachment_script()
        assert "PopulateBoneMapRecursive" in att

    def test_rebind_to_armature_present(self):
        att, _ = generate_equipment_attachment_script()
        assert "RebindToArmature" in att

    def test_rebind_remaps_bones_array(self):
        att, _ = generate_equipment_attachment_script()
        assert "equipmentSMR.bones" in att

    def test_equip_armor_present(self):
        att, _ = generate_equipment_attachment_script()
        assert "EquipArmor" in att

    def test_unequip_armor_present(self):
        att, _ = generate_equipment_attachment_script()
        assert "UnequipArmor" in att

    def test_unequip_by_slot_name(self):
        att, _ = generate_equipment_attachment_script()
        assert "UnequipArmor(string slotName)" in att

    def test_equipment_slot_tracking(self):
        att, _ = generate_equipment_attachment_script()
        assert "_equippedItems" in att
        assert "Dictionary<EquipmentSlot, SkinnedMeshRenderer>" in att

    def test_equipment_slot_enum(self):
        att, _ = generate_equipment_attachment_script()
        assert "enum EquipmentSlot" in att

    def test_eventbus_integration(self):
        att, _ = generate_equipment_attachment_script()
        assert "EventBus.Raise" in att
        assert "EquipmentChangeEvent" in att

    def test_standard_bone_sockets_referenced(self):
        att, _ = generate_equipment_attachment_script()
        assert "StandardBoneSockets" in att
        for socket in STANDARD_BONE_SOCKETS:
            assert socket in att, f"Missing bone socket: {socket}"

    def test_ten_standard_sockets(self):
        assert len(STANDARD_BONE_SOCKETS) == 10

    def test_root_bone_rebinding(self):
        att, _ = generate_equipment_attachment_script()
        assert "rootBone" in att

    def test_default_namespace(self):
        att, _ = generate_equipment_attachment_script()
        assert "namespace VeilBreakers.Content" in att

    def test_is_slot_occupied(self):
        att, _ = generate_equipment_attachment_script()
        assert "IsSlotOccupied" in att

    def test_unequip_all(self):
        att, _ = generate_equipment_attachment_script()
        assert "UnequipAll" in att


# ---------------------------------------------------------------------------
# Weapon sheath template (EQUIP-06)
# ---------------------------------------------------------------------------


class TestWeaponSheath:
    """Tests for generate_equipment_attachment_script() -- weapon sheath output."""

    def test_sheath_contains_class(self):
        _, ws = generate_equipment_attachment_script()
        assert "class VB_WeaponSheath" in ws

    def test_sheath_extends_monobehaviour(self):
        _, ws = generate_equipment_attachment_script()
        assert "MonoBehaviour" in ws

    def test_no_editor_namespace_in_sheath(self):
        _, ws = generate_equipment_attachment_script()
        assert "using UnityEditor" not in ws

    def test_multi_parent_constraint(self):
        _, ws = generate_equipment_attachment_script()
        assert "MultiParentConstraint" in ws

    def test_animation_rigging_using(self):
        _, ws = generate_equipment_attachment_script()
        assert "using UnityEngine.Animations.Rigging;" in ws

    def test_set_drawn_present(self):
        _, ws = generate_equipment_attachment_script()
        assert "SetDrawn()" in ws

    def test_set_sheathed_present(self):
        _, ws = generate_equipment_attachment_script()
        assert "SetSheathed()" in ws

    def test_source_weight_manipulation(self):
        _, ws = generate_equipment_attachment_script()
        # Verifies drawn/sheathed weight blending
        assert "weight" in ws.lower()
        assert "sourceObjects" in ws

    def test_drawn_parent_field(self):
        _, ws = generate_equipment_attachment_script()
        assert "_drawnParent" in ws

    def test_sheathed_parent_field(self):
        _, ws = generate_equipment_attachment_script()
        assert "_sheathedParent" in ws

    def test_transition_duration(self):
        _, ws = generate_equipment_attachment_script()
        assert "_transitionDuration" in ws

    def test_toggle_method(self):
        _, ws = generate_equipment_attachment_script()
        assert "Toggle()" in ws

    def test_is_drawn_property(self):
        _, ws = generate_equipment_attachment_script()
        assert "IsDrawn" in ws

    def test_weighted_transform(self):
        _, ws = generate_equipment_attachment_script()
        assert "WeightedTransform" in ws

    def test_coroutine_animation(self):
        _, ws = generate_equipment_attachment_script()
        assert "IEnumerator" in ws
        assert "AnimateWeights" in ws


# ---------------------------------------------------------------------------
# Namespace override
# ---------------------------------------------------------------------------


class TestNamespaceOverride:
    """Tests for custom namespace in equipment templates."""

    def test_custom_namespace_changes_attachment(self):
        att, _ = generate_equipment_attachment_script(namespace="Custom.Equipment")
        assert "namespace Custom.Equipment" in att
        assert "namespace VeilBreakers.Content" not in att

    def test_custom_namespace_changes_sheath(self):
        _, ws = generate_equipment_attachment_script(namespace="Custom.Equipment")
        assert "namespace Custom.Equipment" in ws
        assert "namespace VeilBreakers.Content" not in ws

    def test_default_namespace_in_attachment(self):
        att, _ = generate_equipment_attachment_script()
        assert "namespace VeilBreakers.Content" in att

    def test_default_namespace_in_sheath(self):
        _, ws = generate_equipment_attachment_script()
        assert "namespace VeilBreakers.Content" in ws

    def test_sanitized_namespace(self):
        att, _ = generate_equipment_attachment_script(namespace="Bad;Name<>")
        assert "namespace BadName" in att
        assert ";" not in att.split("namespace")[1].split("{")[0]
