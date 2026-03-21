"""Unit tests for Unity prefab C# template generators.

Tests that each generator function produces valid C# source containing
the expected Unity API calls, Undo registration, result JSON output,
MenuItem attributes, and correct selector resolution.
"""

import json
import pytest
from pathlib import Path

from veilbreakers_mcp.shared.unity_templates.prefab_templates import (
    generate_prefab_create_script,
    generate_prefab_variant_script,
    generate_prefab_modify_script,
    generate_prefab_delete_script,
    generate_scaffold_prefab_script,
    generate_add_component_script,
    generate_remove_component_script,
    generate_configure_component_script,
    generate_reflect_component_script,
    generate_hierarchy_script,
    generate_batch_configure_script,
    generate_variant_matrix_script,
    generate_joint_setup_script,
    generate_navmesh_setup_script,
    generate_bone_socket_script,
    generate_validate_project_script,
    generate_job_script,
    _resolve_selector_snippet,
    _load_auto_wire_profile,
)
from veilbreakers_mcp.shared.unity_templates._cs_sanitize import (
    sanitize_cs_string,
    sanitize_cs_identifier,
)


# ---------------------------------------------------------------------------
# Sanitization helpers
# ---------------------------------------------------------------------------


class TestSanitizeCsString:
    """Tests for sanitize_cs_string()."""

    def test_escapes_backslash(self):
        assert "\\\\" in sanitize_cs_string("path\\file")

    def test_escapes_double_quotes(self):
        assert '\\"' in sanitize_cs_string('say "hello"')

    def test_escapes_newlines(self):
        assert "\\n" in sanitize_cs_string("line1\nline2")

    def test_escapes_carriage_return(self):
        assert "\\r" in sanitize_cs_string("line1\rline2")

    def test_plain_string_unchanged(self):
        assert sanitize_cs_string("hello") == "hello"


class TestSanitizeCsIdentifier:
    """Tests for sanitize_cs_identifier()."""

    def test_strips_special_characters(self):
        assert sanitize_cs_identifier("My-Object!@#") == "MyObject"

    def test_preserves_underscores(self):
        assert sanitize_cs_identifier("my_object") == "my_object"

    def test_preserves_alphanumeric(self):
        assert sanitize_cs_identifier("Object123") == "Object123"


# ---------------------------------------------------------------------------
# Auto-wire profiles
# ---------------------------------------------------------------------------


class TestAutoWireProfiles:
    """Tests for auto-wire profile JSON loading."""

    def test_monster_profile_loads(self):
        profile = _load_auto_wire_profile("monster")
        assert profile["prefab_type"] == "monster"
        assert "components" in profile

    def test_monster_profile_has_capsule_collider(self):
        profile = _load_auto_wire_profile("monster")
        types = [c["type"] for c in profile["components"]]
        assert "CapsuleCollider" in types

    def test_monster_profile_has_navmesh_agent(self):
        profile = _load_auto_wire_profile("monster")
        types = [c["type"] for c in profile["components"]]
        assert "UnityEngine.AI.NavMeshAgent" in types

    def test_monster_profile_has_animator(self):
        profile = _load_auto_wire_profile("monster")
        types = [c["type"] for c in profile["components"]]
        assert "Animator" in types

    def test_monster_profile_has_combatant(self):
        profile = _load_auto_wire_profile("monster")
        types = [c["type"] for c in profile["components"]]
        assert "VeilBreakers.Combat.Combatant" in types

    def test_hero_profile_loads(self):
        profile = _load_auto_wire_profile("hero")
        assert profile["prefab_type"] == "hero"

    def test_hero_profile_has_character_controller(self):
        profile = _load_auto_wire_profile("hero")
        types = [c["type"] for c in profile["components"]]
        assert "CharacterController" in types

    def test_prop_profile_loads(self):
        profile = _load_auto_wire_profile("prop")
        assert profile["prefab_type"] == "prop"

    def test_prop_profile_has_box_collider(self):
        profile = _load_auto_wire_profile("prop")
        types = [c["type"] for c in profile["components"]]
        assert "BoxCollider" in types

    def test_ui_profile_loads(self):
        profile = _load_auto_wire_profile("ui")
        assert profile["prefab_type"] == "ui"

    def test_ui_profile_has_canvas_renderer(self):
        profile = _load_auto_wire_profile("ui")
        types = [c["type"] for c in profile["components"]]
        assert "CanvasRenderer" in types

    def test_all_profiles_are_valid_json(self):
        profiles_dir = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "veilbreakers_mcp"
            / "shared"
            / "auto_wire_profiles"
        )
        for name in ["monster", "hero", "prop", "ui"]:
            path = profiles_dir / f"{name}.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            assert "prefab_type" in data
            assert "components" in data


# ---------------------------------------------------------------------------
# Selector helper
# ---------------------------------------------------------------------------


class TestResolveSelectorSnippet:
    """Tests for _resolve_selector_snippet()."""

    def test_name_selector(self):
        snippet = _resolve_selector_snippet({"by": "name", "value": "Player"})
        assert 'GameObject.Find("Player")' in snippet

    def test_path_selector(self):
        snippet = _resolve_selector_snippet({"by": "path", "value": "Env/Props/Rock"})
        assert "Env/Props/Rock" in snippet
        # Should use hierarchy path lookup
        assert "GameObject.Find" in snippet or "Transform.Find" in snippet

    def test_guid_selector(self):
        snippet = _resolve_selector_snippet({"by": "guid", "value": "abc123def456"})
        assert "GlobalObjectId" in snippet or "AssetDatabase" in snippet

    def test_regex_selector(self):
        snippet = _resolve_selector_snippet({"by": "regex", "value": "Enemy_\\d+"})
        assert "Regex.IsMatch" in snippet
        assert "SceneManager" in snippet or "FindObjectsOfType" in snippet

    def test_string_shorthand(self):
        snippet = _resolve_selector_snippet("MyObject")
        expected = _resolve_selector_snippet({"by": "name", "value": "MyObject"})
        assert snippet == expected

    def test_null_check_present(self):
        snippet = _resolve_selector_snippet({"by": "name", "value": "Test"})
        assert "null" in snippet.lower() or "== null" in snippet

    def test_assigns_target_variable(self):
        snippet = _resolve_selector_snippet({"by": "name", "value": "Test"})
        assert "target" in snippet


# ---------------------------------------------------------------------------
# Prefab create script
# ---------------------------------------------------------------------------


class TestGeneratePrefabCreateScript:
    """Tests for generate_prefab_create_script()."""

    def test_contains_prefab_utility(self):
        result = generate_prefab_create_script("TestMonster", "monster", "Assets/Prefabs/Monsters")
        assert "PrefabUtility.SaveAsPrefabAsset" in result

    def test_contains_undo_registration(self):
        result = generate_prefab_create_script("TestMonster", "monster", "Assets/Prefabs/Monsters")
        assert "Undo.RegisterCreatedObjectUndo" in result or "Undo.RecordObject" in result

    def test_contains_menu_item(self):
        result = generate_prefab_create_script("TestMonster", "monster", "Assets/Prefabs/Monsters")
        assert '[MenuItem("VeilBreakers/Prefab/Create Prefab")]' in result

    def test_contains_result_json(self):
        result = generate_prefab_create_script("TestMonster", "monster", "Assets/Prefabs/Monsters")
        assert "vb_result.json" in result

    def test_contains_using_editor(self):
        result = generate_prefab_create_script("TestMonster", "monster", "Assets/Prefabs/Monsters")
        assert "using UnityEditor;" in result

    def test_contains_changed_assets(self):
        result = generate_prefab_create_script("TestMonster", "monster", "Assets/Prefabs/Monsters")
        assert "changed_assets" in result

    def test_monster_type_includes_profile_components(self):
        result = generate_prefab_create_script("TestMonster", "monster", "Assets/Prefabs/Monsters")
        assert "CapsuleCollider" in result
        assert "NavMeshAgent" in result
        assert "Animator" in result
        assert "Combatant" in result

    def test_hero_type_includes_profile_components(self):
        result = generate_prefab_create_script("TestHero", "hero", "Assets/Prefabs/Heroes")
        assert "CharacterController" in result


# ---------------------------------------------------------------------------
# Scaffold prefab script
# ---------------------------------------------------------------------------


class TestGenerateScaffoldPrefabScript:
    """Tests for generate_scaffold_prefab_script()."""

    def test_contains_create_primitive(self):
        result = generate_scaffold_prefab_script("TestScaffold", "monster")
        assert "CreatePrimitive(PrimitiveType.Capsule)" in result

    def test_contains_menu_item(self):
        result = generate_scaffold_prefab_script("TestScaffold", "monster")
        assert '[MenuItem("VeilBreakers/Prefab/Create Scaffold")]' in result

    def test_contains_result_json(self):
        result = generate_scaffold_prefab_script("TestScaffold", "monster")
        assert "vb_result.json" in result


# ---------------------------------------------------------------------------
# Prefab variant script
# ---------------------------------------------------------------------------


class TestGeneratePrefabVariantScript:
    """Tests for generate_prefab_variant_script()."""

    def test_contains_instantiate_prefab(self):
        result = generate_prefab_variant_script("TestVariant", "Assets/Prefabs/Base.prefab", {"_corruption": "0.5f"})
        assert "PrefabUtility.InstantiatePrefab" in result

    def test_contains_serialized_object(self):
        result = generate_prefab_variant_script("TestVariant", "Assets/Prefabs/Base.prefab", {"_corruption": "0.5f"})
        assert "SerializedObject" in result

    def test_contains_find_property(self):
        result = generate_prefab_variant_script("TestVariant", "Assets/Prefabs/Base.prefab", {"_corruption": "0.5f"})
        assert "FindProperty" in result

    def test_contains_changed_assets(self):
        result = generate_prefab_variant_script("TestVariant", "Assets/Prefabs/Base.prefab", {"_corruption": "0.5f"})
        assert "changed_assets" in result

    def test_contains_menu_item(self):
        result = generate_prefab_variant_script("TestVariant", "Assets/Prefabs/Base.prefab")
        assert '[MenuItem("VeilBreakers/Prefab/Create Variant")]' in result


# ---------------------------------------------------------------------------
# Prefab modify script
# ---------------------------------------------------------------------------


class TestGeneratePrefabModifyScript:
    """Tests for generate_prefab_modify_script()."""

    def test_contains_load_asset(self):
        result = generate_prefab_modify_script(
            "Assets/Prefabs/X.prefab",
            [{"property": "_hp", "value": "100", "type": "int"}],
        )
        assert "AssetDatabase.LoadAssetAtPath" in result

    def test_contains_serialized_object(self):
        result = generate_prefab_modify_script(
            "Assets/Prefabs/X.prefab",
            [{"property": "_hp", "value": "100", "type": "int"}],
        )
        assert "SerializedObject" in result

    def test_contains_apply_modified(self):
        result = generate_prefab_modify_script(
            "Assets/Prefabs/X.prefab",
            [{"property": "_hp", "value": "100", "type": "int"}],
        )
        assert "ApplyModifiedProperties" in result

    def test_contains_menu_item(self):
        result = generate_prefab_modify_script(
            "Assets/Prefabs/X.prefab",
            [{"property": "_hp", "value": "100", "type": "int"}],
        )
        assert '[MenuItem("VeilBreakers/Prefab/Modify Prefab")]' in result


# ---------------------------------------------------------------------------
# Prefab delete script
# ---------------------------------------------------------------------------


class TestGeneratePrefabDeleteScript:
    """Tests for generate_prefab_delete_script()."""

    def test_contains_delete_asset(self):
        result = generate_prefab_delete_script("Assets/Prefabs/X.prefab")
        assert "AssetDatabase.DeleteAsset" in result

    def test_contains_menu_item(self):
        result = generate_prefab_delete_script("Assets/Prefabs/X.prefab")
        assert '[MenuItem("VeilBreakers/Prefab/Delete Prefab")]' in result

    def test_contains_result_json(self):
        result = generate_prefab_delete_script("Assets/Prefabs/X.prefab")
        assert "vb_result.json" in result


# ---------------------------------------------------------------------------
# Add component script
# ---------------------------------------------------------------------------


class TestGenerateAddComponentScript:
    """Tests for generate_add_component_script()."""

    def test_name_selector(self):
        result = generate_add_component_script({"by": "name", "value": "TargetObject"}, "Rigidbody")
        # Must use selector snippet, not raw GameObject.Find
        assert "Rigidbody" in result
        assert "Undo.AddComponent" in result or "ObjectFactory.AddComponent" in result or "AddComponent" in result

    def test_path_selector(self):
        result = generate_add_component_script({"by": "path", "value": "Environment/Props/TargetObject"}, "Rigidbody")
        assert "Environment/Props/TargetObject" in result

    def test_guid_selector(self):
        result = generate_add_component_script({"by": "guid", "value": "abc123"}, "Rigidbody")
        assert "GlobalObjectId" in result or "AssetDatabase" in result

    def test_regex_selector(self):
        result = generate_add_component_script({"by": "regex", "value": "Monster_.*"}, "Rigidbody")
        assert "Regex.IsMatch" in result

    def test_contains_menu_item(self):
        result = generate_add_component_script({"by": "name", "value": "TargetObject"}, "Rigidbody")
        assert '[MenuItem("VeilBreakers/Prefab/Add Component")]' in result

    def test_contains_result_json(self):
        result = generate_add_component_script({"by": "name", "value": "TargetObject"}, "Rigidbody")
        assert "vb_result.json" in result

    def test_contains_undo(self):
        result = generate_add_component_script({"by": "name", "value": "TargetObject"}, "Rigidbody")
        assert "Undo." in result


# ---------------------------------------------------------------------------
# Remove component script
# ---------------------------------------------------------------------------


class TestGenerateRemoveComponentScript:
    """Tests for generate_remove_component_script()."""

    def test_contains_destroy(self):
        result = generate_remove_component_script({"by": "name", "value": "TargetObject"}, "Rigidbody")
        assert "Undo.DestroyObjectImmediate" in result

    def test_contains_menu_item(self):
        result = generate_remove_component_script({"by": "name", "value": "TargetObject"}, "Rigidbody")
        assert '[MenuItem("VeilBreakers/Prefab/Remove Component")]' in result

    def test_contains_result_json(self):
        result = generate_remove_component_script({"by": "name", "value": "TargetObject"}, "Rigidbody")
        assert "vb_result.json" in result


# ---------------------------------------------------------------------------
# Configure component script
# ---------------------------------------------------------------------------


class TestGenerateConfigureComponentScript:
    """Tests for generate_configure_component_script()."""

    def test_contains_serialized_object(self):
        result = generate_configure_component_script(
            {"by": "name", "value": "TargetObject"},
            "Rigidbody",
            [{"property": "mass", "value": "5.0", "type": "float"}],
        )
        assert "SerializedObject" in result

    def test_contains_find_property(self):
        result = generate_configure_component_script(
            {"by": "name", "value": "TargetObject"},
            "Rigidbody",
            [{"property": "mass", "value": "5.0", "type": "float"}],
        )
        assert "FindProperty" in result

    def test_contains_float_value(self):
        result = generate_configure_component_script(
            {"by": "name", "value": "TargetObject"},
            "Rigidbody",
            [{"property": "mass", "value": "5.0", "type": "float"}],
        )
        assert "floatValue" in result

    def test_contains_apply_modified(self):
        result = generate_configure_component_script(
            {"by": "name", "value": "TargetObject"},
            "Rigidbody",
            [{"property": "mass", "value": "5.0", "type": "float"}],
        )
        assert "ApplyModifiedProperties" in result

    def test_contains_menu_item(self):
        result = generate_configure_component_script(
            {"by": "name", "value": "TargetObject"},
            "Rigidbody",
            [{"property": "mass", "value": "5.0", "type": "float"}],
        )
        assert '[MenuItem("VeilBreakers/Prefab/Configure Component")]' in result


# ---------------------------------------------------------------------------
# Reflect component script
# ---------------------------------------------------------------------------


class TestGenerateReflectComponentScript:
    """Tests for generate_reflect_component_script()."""

    def test_contains_serialized_object(self):
        result = generate_reflect_component_script({"by": "name", "value": "TargetObject"}, "Rigidbody")
        assert "SerializedObject" in result

    def test_contains_get_iterator(self):
        result = generate_reflect_component_script({"by": "name", "value": "TargetObject"}, "Rigidbody")
        assert "GetIterator" in result

    def test_contains_next_visible(self):
        result = generate_reflect_component_script({"by": "name", "value": "TargetObject"}, "Rigidbody")
        assert "NextVisible" in result

    def test_contains_property_type(self):
        result = generate_reflect_component_script({"by": "name", "value": "TargetObject"}, "Rigidbody")
        assert "propertyType" in result

    def test_contains_menu_item(self):
        result = generate_reflect_component_script({"by": "name", "value": "TargetObject"}, "Rigidbody")
        assert '[MenuItem("VeilBreakers/Prefab/Reflect Component")]' in result


# ---------------------------------------------------------------------------
# Hierarchy script
# ---------------------------------------------------------------------------


class TestGenerateHierarchyScript:
    """Tests for generate_hierarchy_script()."""

    def test_create_empty(self):
        result = generate_hierarchy_script(operation="create_empty", name="EmptyObj")
        assert "new GameObject" in result
        assert "Undo.RegisterCreatedObjectUndo" in result

    def test_reparent(self):
        result = generate_hierarchy_script(
            operation="reparent",
            selector={"by": "name", "value": "Child"},
            parent_name="NewParent",
        )
        assert "SetParent" in result

    def test_set_layer(self):
        result = generate_hierarchy_script(
            operation="set_layer",
            selector={"by": "name", "value": "Obj"},
            layer="Enemy",
        )
        assert "gameObject.layer" in result or ".layer" in result

    def test_set_tag(self):
        result = generate_hierarchy_script(
            operation="set_tag",
            selector={"by": "name", "value": "Obj"},
            tag="Monster",
        )
        assert "gameObject.tag" in result or ".tag" in result

    def test_enable(self):
        result = generate_hierarchy_script(
            operation="enable",
            selector={"by": "name", "value": "Obj"},
        )
        assert "SetActive" in result

    def test_rename(self):
        result = generate_hierarchy_script(
            operation="rename",
            selector={"by": "name", "value": "OldName"},
            new_name="NewName",
        )
        assert ".name =" in result or ".name=" in result

    def test_contains_menu_item(self):
        result = generate_hierarchy_script(operation="create_empty", name="EmptyObj")
        assert '[MenuItem("VeilBreakers/Prefab/Hierarchy")]' in result

    def test_contains_result_json(self):
        result = generate_hierarchy_script(operation="create_empty", name="EmptyObj")
        assert "vb_result.json" in result


# ---------------------------------------------------------------------------
# Batch configure script
# ---------------------------------------------------------------------------


class TestGenerateBatchConfigureScript:
    """Tests for generate_batch_configure_script()."""

    def test_tag_selector_uses_find_with_tag(self):
        result = generate_batch_configure_script(
            {"by": "tag", "value": "Monster"},
            "Rigidbody",
            [{"property": "mass", "value": "5.0", "type": "float"}],
        )
        assert "FindGameObjectsWithTag" in result

    def test_contains_menu_item(self):
        result = generate_batch_configure_script(
            {"by": "tag", "value": "Monster"},
            "Rigidbody",
            [{"property": "mass", "value": "5.0", "type": "float"}],
        )
        assert '[MenuItem("VeilBreakers/Prefab/Batch Configure")]' in result

    def test_contains_result_json(self):
        result = generate_batch_configure_script(
            {"by": "tag", "value": "Monster"},
            "Rigidbody",
            [{"property": "mass", "value": "5.0", "type": "float"}],
        )
        assert "vb_result.json" in result


# ---------------------------------------------------------------------------
# Variant matrix script
# ---------------------------------------------------------------------------


class TestGenerateVariantMatrixScript:
    """Tests for generate_variant_matrix_script()."""

    def test_contains_start_asset_editing(self):
        result = generate_variant_matrix_script(
            "BaseMonster", "Assets/Prefabs/Base.prefab",
            corruption_tiers=[1, 2, 3, 4, 5], brands=["IRON", "VENOM"],
        )
        assert "StartAssetEditing" in result

    def test_contains_stop_asset_editing(self):
        result = generate_variant_matrix_script(
            "BaseMonster", "Assets/Prefabs/Base.prefab",
            corruption_tiers=[1, 2, 3, 4, 5], brands=["IRON", "VENOM"],
        )
        assert "StopAssetEditing" in result

    def test_contains_save_as_prefab(self):
        result = generate_variant_matrix_script(
            "BaseMonster", "Assets/Prefabs/Base.prefab",
            corruption_tiers=[1, 2, 3, 4, 5], brands=["IRON", "VENOM"],
        )
        assert "SaveAsPrefabAsset" in result

    def test_contains_menu_item(self):
        result = generate_variant_matrix_script(
            "BaseMonster", "Assets/Prefabs/Base.prefab",
            corruption_tiers=[1, 2, 3, 4, 5], brands=["IRON", "VENOM"],
        )
        assert '[MenuItem("VeilBreakers/Prefab/Generate Variant Matrix")]' in result


# ---------------------------------------------------------------------------
# Joint setup script
# ---------------------------------------------------------------------------


class TestGenerateJointSetupScript:
    """Tests for generate_joint_setup_script()."""

    def test_hinge_joint(self):
        result = generate_joint_setup_script(
            {"by": "name", "value": "TargetObject"}, "HingeJoint", {"axis": "0,1,0"},
        )
        assert "HingeJoint" in result

    def test_spring_joint(self):
        result = generate_joint_setup_script(
            {"by": "name", "value": "Obj"}, "SpringJoint", {},
        )
        assert "SpringJoint" in result

    def test_configurable_joint(self):
        result = generate_joint_setup_script(
            {"by": "name", "value": "Obj"}, "ConfigurableJoint", {},
        )
        assert "ConfigurableJoint" in result

    def test_character_joint(self):
        result = generate_joint_setup_script(
            {"by": "name", "value": "Obj"}, "CharacterJoint", {},
        )
        assert "CharacterJoint" in result

    def test_fixed_joint(self):
        result = generate_joint_setup_script(
            {"by": "name", "value": "Obj"}, "FixedJoint", {},
        )
        assert "FixedJoint" in result

    def test_contains_add_component(self):
        result = generate_joint_setup_script(
            {"by": "name", "value": "Obj"}, "HingeJoint", {},
        )
        assert "AddComponent" in result

    def test_contains_menu_item(self):
        result = generate_joint_setup_script(
            {"by": "name", "value": "Obj"}, "HingeJoint", {},
        )
        assert '[MenuItem("VeilBreakers/Prefab/Setup Joint")]' in result

    def test_uses_selector(self):
        result = generate_joint_setup_script(
            {"by": "name", "value": "Obj"}, "HingeJoint", {},
        )
        # Should use selector resolution
        assert "GameObject.Find" in result or "target" in result


# ---------------------------------------------------------------------------
# NavMesh setup script
# ---------------------------------------------------------------------------


class TestGenerateNavmeshSetupScript:
    """Tests for generate_navmesh_setup_script()."""

    def test_add_obstacle(self):
        result = generate_navmesh_setup_script(
            operation="add_obstacle",
            selector={"by": "name", "value": "Wall"},
        )
        assert "NavMeshObstacle" in result

    def test_add_link(self):
        result = generate_navmesh_setup_script(
            operation="add_link",
            selector={"by": "name", "value": "Bridge"},
        )
        assert "NavMeshLink" in result

    def test_configure_area(self):
        result = generate_navmesh_setup_script(
            operation="configure_area",
            selector={"by": "name", "value": "Ground"},
        )
        assert "NavMesh.SetAreaCost" in result or "SetAreaCost" in result

    def test_contains_menu_item(self):
        result = generate_navmesh_setup_script(
            operation="add_obstacle",
            selector={"by": "name", "value": "Wall"},
        )
        assert '[MenuItem("VeilBreakers/Prefab/NavMesh Setup")]' in result


# ---------------------------------------------------------------------------
# Bone socket script
# ---------------------------------------------------------------------------


class TestGenerateBoneSocketScript:
    """Tests for generate_bone_socket_script()."""

    def test_contains_socket_prefix(self):
        result = generate_bone_socket_script(
            "Assets/Prefabs/Hero.prefab",
            sockets=["weapon_hand_R", "shield_hand_L"],
        )
        assert "Socket_" in result

    def test_contains_set_parent(self):
        result = generate_bone_socket_script(
            "Assets/Prefabs/Hero.prefab",
            sockets=["weapon_hand_R", "shield_hand_L"],
        )
        assert "SetParent" in result or "parent" in result

    def test_contains_all_standard_sockets_in_bone_map(self):
        result = generate_bone_socket_script("Assets/Prefabs/Hero.prefab")
        # All 10 standard socket names should appear in the bone mapping dict
        standard_sockets = [
            "weapon_hand_R", "weapon_hand_L", "shield_hand_L",
            "back_weapon", "hip_L", "hip_R", "head", "chest",
            "spell_hand_R", "spell_hand_L",
        ]
        for socket in standard_sockets:
            assert socket in result

    def test_contains_menu_item(self):
        result = generate_bone_socket_script(
            "Assets/Prefabs/Hero.prefab",
            sockets=["weapon_hand_R"],
        )
        assert '[MenuItem("VeilBreakers/Prefab/Setup Bone Sockets")]' in result

    def test_contains_result_json(self):
        result = generate_bone_socket_script(
            "Assets/Prefabs/Hero.prefab",
            sockets=["weapon_hand_R"],
        )
        assert "vb_result.json" in result


# ---------------------------------------------------------------------------
# Validate project script
# ---------------------------------------------------------------------------


class TestGenerateValidateProjectScript:
    """Tests for generate_validate_project_script()."""

    def test_contains_find_assets(self):
        result = generate_validate_project_script()
        assert 'AssetDatabase.FindAssets' in result

    def test_contains_t_prefab(self):
        result = generate_validate_project_script()
        assert "t:Prefab" in result

    def test_contains_get_components(self):
        result = generate_validate_project_script()
        assert "GetComponents" in result or "GetComponent" in result

    def test_contains_menu_item(self):
        result = generate_validate_project_script()
        assert '[MenuItem("VeilBreakers/Prefab/Validate Project Integrity")]' in result

    def test_contains_result_json(self):
        result = generate_validate_project_script()
        assert "vb_result.json" in result


# ---------------------------------------------------------------------------
# Job script (batch operations)
# ---------------------------------------------------------------------------


class TestGenerateJobScript:
    """Tests for generate_job_script()."""

    def test_multi_operation_batching(self):
        result = generate_job_script([
            {
                "action": "add_component",
                "selector": {"by": "name", "value": "Obj1"},
                "component_type": "Rigidbody",
            },
            {
                "action": "configure",
                "selector": {"by": "name", "value": "Obj2"},
                "component_type": "BoxCollider",
                "properties": [{"property": "size", "value": "2,2,2", "type": "vector3"}],
            },
        ])
        assert "AddComponent" in result
        assert "SerializedObject" in result or "BoxCollider" in result

    def test_contains_start_asset_editing(self):
        result = generate_job_script([
            {"action": "add_component", "selector": {"by": "name", "value": "Obj1"}, "component_type": "Rigidbody"},
        ])
        assert "StartAssetEditing" in result

    def test_contains_stop_asset_editing(self):
        result = generate_job_script([
            {"action": "add_component", "selector": {"by": "name", "value": "Obj1"}, "component_type": "Rigidbody"},
        ])
        assert "StopAssetEditing" in result

    def test_contains_undo_grouping(self):
        result = generate_job_script([
            {"action": "add_component", "selector": {"by": "name", "value": "Obj1"}, "component_type": "Rigidbody"},
        ])
        assert "Undo." in result
        assert "IncrementCurrentGroup" in result or "RegisterCompleteObjectUndo" in result

    def test_contains_menu_item(self):
        result = generate_job_script([
            {"action": "add_component", "selector": {"by": "name", "value": "Obj1"}, "component_type": "Rigidbody"},
        ])
        assert '[MenuItem("VeilBreakers/Prefab/Execute Job Script")]' in result

    def test_empty_operations_returns_noop(self):
        result = generate_job_script([])
        assert "vb_result.json" in result
        # Should be a minimal script (warning or no-op)
        assert "warning" in result.lower() or "no" in result.lower() or "empty" in result.lower()

    def test_single_script_for_multiple_ops(self):
        result = generate_job_script([
            {"action": "add_component", "selector": {"by": "name", "value": "Obj1"}, "component_type": "Rigidbody"},
            {"action": "add_component", "selector": {"by": "name", "value": "Obj2"}, "component_type": "BoxCollider"},
        ])
        # Should be ONE script with one MenuItem
        count = result.count('[MenuItem(')
        assert count == 1


# ---------------------------------------------------------------------------
# Cross-cutting checks: all generators
# ---------------------------------------------------------------------------


class TestAllGeneratorsCommon:
    """Tests that all generators share common patterns."""

    def _get_all_results(self):
        """Return list of (name, result) tuples for all generators."""
        results = []
        results.append(("prefab_create", generate_prefab_create_script("T", "prop", "Assets")))
        results.append(("scaffold", generate_scaffold_prefab_script("T", "prop")))
        results.append(("variant", generate_prefab_variant_script("T", "Assets/Base.prefab")))
        results.append(("modify", generate_prefab_modify_script("Assets/X.prefab", [{"property": "x", "value": "1", "type": "int"}])))
        results.append(("delete", generate_prefab_delete_script("Assets/X.prefab")))
        results.append(("add_comp", generate_add_component_script({"by": "name", "value": "O"}, "Rigidbody")))
        results.append(("remove_comp", generate_remove_component_script({"by": "name", "value": "O"}, "Rigidbody")))
        results.append(("configure", generate_configure_component_script({"by": "name", "value": "O"}, "Rigidbody", [{"property": "mass", "value": "1", "type": "float"}])))
        results.append(("reflect", generate_reflect_component_script({"by": "name", "value": "O"}, "Rigidbody")))
        results.append(("hierarchy", generate_hierarchy_script(operation="create_empty", name="E")))
        results.append(("batch_cfg", generate_batch_configure_script({"by": "tag", "value": "M"}, "Rigidbody", [{"property": "mass", "value": "1", "type": "float"}])))
        results.append(("variant_mx", generate_variant_matrix_script("B", "Assets/B.prefab", [1], ["IRON"])))
        results.append(("joint", generate_joint_setup_script({"by": "name", "value": "O"}, "HingeJoint", {})))
        results.append(("navmesh", generate_navmesh_setup_script(operation="add_obstacle", selector={"by": "name", "value": "W"})))
        results.append(("sockets", generate_bone_socket_script("Assets/H.prefab", ["weapon_hand_R"])))
        results.append(("validate", generate_validate_project_script()))
        results.append(("job", generate_job_script([{"action": "add_component", "selector": {"by": "name", "value": "O"}, "component_type": "Rigidbody"}])))
        return results

    def test_all_contain_undo(self):
        # validate is a read-only scan and does not need Undo
        skip_undo = {"validate"}
        for name, result in self._get_all_results():
            if name in skip_undo:
                continue
            assert "Undo." in result or "Undo.RegisterCreatedObjectUndo" in result, f"{name} missing Undo"

    def test_all_contain_result_json(self):
        for name, result in self._get_all_results():
            assert "vb_result.json" in result, f"{name} missing vb_result.json"

    def test_all_contain_changed_assets_or_validation(self):
        for name, result in self._get_all_results():
            assert "changed_assets" in result or "validation_status" in result, (
                f"{name} missing changed_assets/validation_status"
            )

    def test_all_contain_using_editor(self):
        for name, result in self._get_all_results():
            assert "using UnityEditor;" in result, f"{name} missing using UnityEditor"
