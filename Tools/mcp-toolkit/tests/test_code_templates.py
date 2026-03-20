"""Unit tests for C# code generation engine (CODE-01, CODE-02, CODE-03).

Tests cover:
- TestGenerateClass: All 8 class types, fields, methods, properties, sanitization
- TestModifyScript: Using insertion, field/method/property/attribute addition, indentation
- TestEditorTools: EditorWindow, PropertyDrawer, InspectorDrawer, SceneOverlay generators
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.code_templates import (
    _build_cs_class,
    _safe_identifier,
    _CS_RESERVED,
    generate_class,
    modify_script,
    generate_editor_window,
    generate_property_drawer,
    generate_inspector_drawer,
    generate_scene_overlay,
    generate_test_class,
    generate_service_locator,
    generate_object_pool,
    generate_singleton,
    generate_state_machine,
    generate_so_event_channel,
)

from veilbreakers_mcp.shared.unity_templates.editor_templates import (
    generate_test_runner_script,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def check_brace_balance(text: str) -> bool:
    """Verify that braces are balanced throughout the string."""
    depth = 0
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if depth < 0:
            return False
    return depth == 0


# ===================================================================
# TestGenerateClass (CODE-01)
# ===================================================================


class TestGenerateClass:
    """Test generate_class for all 8 class types and various configurations."""

    def test_monobehaviour_class(self):
        result = generate_class(
            "PlayerHealth", "MonoBehaviour", namespace="VeilBreakers.Gameplay"
        )
        assert "using UnityEngine;" in result
        assert "namespace VeilBreakers.Gameplay" in result
        assert "class PlayerHealth : MonoBehaviour" in result
        assert check_brace_balance(result)

    def test_scriptable_object(self):
        result = generate_class("ItemDatabase", "ScriptableObject")
        assert "CreateAssetMenu" in result
        assert "ScriptableObject" in result
        assert "class ItemDatabase : ScriptableObject" in result
        assert "using UnityEngine;" in result

    def test_plain_class(self):
        result = generate_class("DamageCalculator", "class")
        assert "class DamageCalculator" in result
        assert "MonoBehaviour" not in result

    def test_static_class(self):
        result = generate_class("MathUtils", "static class")
        assert "static class MathUtils" in result

    def test_abstract_class(self):
        result = generate_class("BaseEnemy", "abstract class")
        assert "abstract class BaseEnemy" in result

    def test_interface(self):
        result = generate_class("IDamageable", "interface")
        assert "interface IDamageable" in result

    def test_enum(self):
        result = generate_class(
            "DamageType", "enum", enum_values=["Physical", "Fire", "Ice", "Lightning"]
        )
        assert "enum DamageType" in result
        assert "Physical" in result
        assert "Fire" in result
        assert "Ice" in result
        assert "Lightning" in result

    def test_struct(self):
        result = generate_class("DamageInfo", "struct")
        assert "struct DamageInfo" in result

    def test_with_fields(self):
        result = generate_class(
            "Player",
            "MonoBehaviour",
            fields=[
                {
                    "access": "private",
                    "type": "float",
                    "name": "health",
                    "default": "100f",
                    "attributes": ["SerializeField"],
                }
            ],
        )
        assert "[SerializeField]" in result
        assert "private float _health = 100f;" in result

    def test_with_methods(self):
        result = generate_class(
            "Player",
            "MonoBehaviour",
            methods=[
                {
                    "access": "public",
                    "return_type": "void",
                    "name": "TakeDamage",
                    "params": "float amount",
                    "body": "_health -= amount;",
                }
            ],
        )
        assert "public void TakeDamage(float amount)" in result
        assert "_health -= amount;" in result

    def test_with_properties(self):
        result = generate_class(
            "Player",
            "MonoBehaviour",
            properties=[
                {
                    "access": "public",
                    "type": "float",
                    "name": "Health",
                    "getter": "return _health;",
                    "setter": "_health = value;",
                }
            ],
        )
        assert "public float Health" in result
        assert "return _health;" in result
        assert "_health = value;" in result

    def test_reserved_word_identifier(self):
        result = generate_class("class")
        assert "@class" in result

    def test_sanitization(self):
        result = generate_class("My Class!@#")
        assert "MyClass" in result
        assert "!" not in result.split("class")[0]  # no special chars in class name

    def test_all_types_have_balanced_braces(self):
        types_and_args = [
            ("Test1", "MonoBehaviour", {}),
            ("Test2", "ScriptableObject", {}),
            ("Test3", "class", {}),
            ("Test4", "static class", {}),
            ("Test5", "abstract class", {}),
            ("Test6", "interface", {}),
            ("Test7", "enum", {"enum_values": ["A", "B", "C"]}),
            ("Test8", "struct", {}),
        ]
        for name, ctype, kwargs in types_and_args:
            result = generate_class(name, ctype, **kwargs)
            assert check_brace_balance(result), (
                f"Unbalanced braces for {ctype}: "
                f"{{ = {result.count('{')}, }} = {result.count('}')}"
            )

    def test_with_namespace_and_interfaces(self):
        result = generate_class(
            "EnemyController",
            "MonoBehaviour",
            namespace="VeilBreakers.AI",
            interfaces=["IDamageable", "IPoolable"],
        )
        assert "namespace VeilBreakers.AI" in result
        assert "IDamageable" in result
        assert "IPoolable" in result
        assert ": MonoBehaviour, IDamageable, IPoolable" in result

    def test_with_summary(self):
        result = generate_class(
            "HealthSystem", "MonoBehaviour", summary="Manages entity health."
        )
        assert "/// <summary>" in result
        assert "Manages entity health." in result

    def test_interface_methods_have_no_body(self):
        result = generate_class(
            "IDamageable",
            "interface",
            methods=[
                {"access": "public", "return_type": "void", "name": "TakeDamage", "params": "float amount"},
                {"access": "public", "return_type": "float", "name": "GetHealth"},
            ],
        )
        assert "void TakeDamage(float amount);" in result
        assert "float GetHealth();" in result
        # Interface methods should NOT have curly braces for body
        # (they have the class braces but not method braces)

    def test_empty_identifier_raises(self):
        with pytest.raises(ValueError, match="empty after sanitization"):
            generate_class("!@#$%")

    def test_build_cs_class_directly(self):
        result = _build_cs_class(
            class_name="DirectTest",
            class_type="class",
            usings=["System"],
        )
        assert "using System;" in result
        assert "class DirectTest" in result


# ===================================================================
# TestModifyScript (CODE-02)
# ===================================================================


_BASIC_CLASS = """using UnityEngine;

public class TestClass : MonoBehaviour
{
    private int _health = 100;

    public void Start()
    {
        Debug.Log("Hello");
    }
}
"""

_NAMESPACED_CLASS = """using UnityEngine;

namespace VeilBreakers.Gameplay
{
    public class TestClass : MonoBehaviour
    {
        private int _health = 100;

        public void Start()
        {
            Debug.Log("Hello");
        }
    }
}
"""


class TestModifyScript:
    """Test modify_script for all modification types."""

    def test_add_using(self):
        result, changes = modify_script(_BASIC_CLASS, add_usings=["System.Linq"])
        assert "using System.Linq;" in result
        assert any("System.Linq" in c for c in changes)

    def test_add_using_no_duplicate(self):
        result, changes = modify_script(_BASIC_CLASS, add_usings=["UnityEngine"])
        # Should not add duplicate
        assert result.count("using UnityEngine;") == 1
        assert len(changes) == 0

    def test_add_field(self):
        result, changes = modify_script(
            _BASIC_CLASS,
            add_fields=[{"access": "private", "type": "float", "name": "speed", "default": "5f"}],
        )
        assert "private float" in result
        assert "speed" in result
        assert any("field" in c.lower() for c in changes)

    def test_add_method(self):
        result, changes = modify_script(
            _BASIC_CLASS,
            add_methods=[
                {
                    "access": "public",
                    "return_type": "void",
                    "name": "TakeDamage",
                    "params": "float amount",
                    "body": "_health -= (int)amount;",
                }
            ],
        )
        assert "public void TakeDamage(float amount)" in result
        assert "_health -= (int)amount;" in result
        assert any("method" in c.lower() for c in changes)

    def test_add_property(self):
        result, changes = modify_script(
            _BASIC_CLASS,
            add_properties=[
                {"access": "public", "type": "int", "name": "Health", "getter": "return _health;"},
            ],
        )
        assert "public int Health" in result
        assert "return _health;" in result
        assert any("property" in c.lower() for c in changes)

    def test_add_attribute(self):
        result, changes = modify_script(
            _BASIC_CLASS,
            add_attributes=[{"target_class": "TestClass", "attribute": "Serializable"}],
        )
        assert "[Serializable]" in result
        # The attribute should appear before the class declaration
        attr_pos = result.index("[Serializable]")
        class_pos = result.index("class TestClass")
        assert attr_pos < class_pos
        assert any("Serializable" in c for c in changes)

    def test_preserves_indentation_tabs(self):
        tab_source = "using UnityEngine;\n\npublic class Foo\n{\n\tprivate int _x;\n}\n"
        result, changes = modify_script(
            tab_source,
            add_fields=[{"access": "private", "type": "float", "name": "y"}],
        )
        # Should detect tab indentation and use it
        assert "\t" in result

    def test_returns_changes_list(self):
        result, changes = modify_script(
            _BASIC_CLASS, add_usings=["System.Collections.Generic"]
        )
        assert isinstance(result, str)
        assert isinstance(changes, list)
        assert len(changes) > 0
        assert all(isinstance(c, str) for c in changes)

    def test_balanced_braces_after_modify(self):
        result, _ = modify_script(
            _BASIC_CLASS,
            add_usings=["System.Linq"],
            add_fields=[{"access": "private", "type": "string", "name": "label"}],
            add_methods=[
                {"access": "public", "return_type": "void", "name": "Reset", "body": "_health = 100;"}
            ],
        )
        assert check_brace_balance(result), (
            f"Braces unbalanced: {{ = {result.count('{')}, }} = {result.count('}')}"
        )

    def test_empty_modifications(self):
        result, changes = modify_script(_BASIC_CLASS)
        assert result == _BASIC_CLASS
        assert changes == []

    def test_multiple_usings(self):
        result, changes = modify_script(
            _BASIC_CLASS,
            add_usings=["System.Linq", "System.Collections.Generic"],
        )
        assert "using System.Linq;" in result
        assert "using System.Collections.Generic;" in result
        assert len(changes) == 2

    def test_namespaced_class_modification(self):
        result, changes = modify_script(
            _NAMESPACED_CLASS,
            add_methods=[
                {"access": "public", "return_type": "void", "name": "OnDestroy", "body": "Debug.Log(\"Destroyed\");"}
            ],
        )
        assert "public void OnDestroy()" in result
        assert check_brace_balance(result)


# ===================================================================
# TestEditorTools (CODE-03)
# ===================================================================


class TestEditorTools:
    """Test editor tool generators for EditorWindow, PropertyDrawer, Inspector, Overlay."""

    def test_editor_window_basic(self):
        result = generate_editor_window("DebugWindow", "VeilBreakers/Tools/Debug")
        assert "MenuItem" in result
        assert "EditorWindow" in result
        assert "OnGUI" in result
        assert "GetWindow" in result

    def test_editor_window_namespace(self):
        result = generate_editor_window(
            "DebugWindow", "VeilBreakers/Tools/Debug", namespace="VeilBreakers.Editor"
        )
        assert "namespace VeilBreakers.Editor" in result

    def test_editor_window_ui_toolkit(self):
        result = generate_editor_window(
            "ModernWindow", "VeilBreakers/Tools/Modern", use_ui_toolkit=True
        )
        assert "CreateGUI" in result
        assert "UIElements" in result

    def test_property_drawer(self):
        result = generate_property_drawer("HealthRange")
        assert "CustomPropertyDrawer" in result
        assert "OnGUI" in result
        assert "GetPropertyHeight" in result
        assert "BeginProperty" in result
        assert "EndProperty" in result

    def test_inspector_drawer(self):
        result = generate_inspector_drawer("EnemyController")
        assert "CustomEditor" in result
        assert "OnInspectorGUI" in result
        assert "serializedObject.Update" in result
        assert "serializedObject.ApplyModifiedProperties" in result

    def test_inspector_drawer_with_fields(self):
        result = generate_inspector_drawer(
            "EnemyController", fields_to_draw=["_health", "_speed"]
        )
        assert "FindProperty" in result
        assert "_health" in result
        assert "_speed" in result

    def test_scene_overlay(self):
        result = generate_scene_overlay("GridOverlay", "Grid Tool")
        assert "Overlay" in result
        assert "ITransientOverlay" in result
        assert "CreatePanelContent" in result
        assert "VisualElement" in result
        assert "Grid Tool" in result

    def test_all_editor_tools_have_using_editor(self):
        generators = [
            lambda: generate_editor_window("Win", "VeilBreakers/Win"),
            lambda: generate_property_drawer("MyType"),
            lambda: generate_inspector_drawer("MyComp"),
            lambda: generate_scene_overlay("MyOverlay", "My Overlay"),
        ]
        for gen in generators:
            result = gen()
            assert "using UnityEditor;" in result, (
                f"Missing 'using UnityEditor;' in generator output"
            )

    def test_all_balanced_braces(self):
        generators = [
            lambda: generate_editor_window("Win", "VeilBreakers/Win"),
            lambda: generate_property_drawer("MyType"),
            lambda: generate_inspector_drawer("MyComp"),
            lambda: generate_scene_overlay("MyOverlay", "My Overlay"),
        ]
        for gen in generators:
            result = gen()
            assert check_brace_balance(result), (
                f"Unbalanced braces: {{ = {result.count('{')}, }} = {result.count('}')}"
            )

    def test_editor_window_custom_on_gui(self):
        result = generate_editor_window(
            "CustomWindow",
            "VeilBreakers/Custom",
            on_gui_body='EditorGUILayout.LabelField("Custom Label");',
        )
        assert "Custom Label" in result

    def test_scene_overlay_custom_panel(self):
        result = generate_scene_overlay(
            "CustomOverlay",
            "Custom Tool",
            panel_body='root.Add(new Button() { text = "Click" });',
        )
        assert "Click" in result

    def test_property_drawer_class_naming(self):
        result = generate_property_drawer("HealthRange")
        assert "class HealthRangeDrawer" in result

    def test_inspector_drawer_class_naming(self):
        result = generate_inspector_drawer("EnemyController")
        assert "class EnemyControllerEditor" in result


# ===================================================================
# TestSafeIdentifier
# ===================================================================


class TestSafeIdentifier:
    """Test _safe_identifier utility function."""

    def test_normal_identifier(self):
        assert _safe_identifier("PlayerHealth") == "PlayerHealth"

    def test_reserved_word(self):
        assert _safe_identifier("class") == "@class"

    def test_strips_invalid_chars(self):
        assert _safe_identifier("My Class!") == "MyClass"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            _safe_identifier("!@#")

    def test_reserved_set_is_frozenset(self):
        assert isinstance(_CS_RESERVED, frozenset)
        assert "class" in _CS_RESERVED
        assert "void" in _CS_RESERVED


# ===================================================================
# TestGenerateTests (CODE-04)
# ===================================================================


class TestGenerateTests:
    """Test generate_test_class for NUnit test class generation."""

    def test_editmode_test_class(self):
        result = generate_test_class("PlayerHealthTest", "EditMode")
        assert "[TestFixture]" in result
        assert "[Test]" in result
        assert "using NUnit.Framework;" in result

    def test_playmode_test_class(self):
        result = generate_test_class("CombatIntegrationTest", "PlayMode")
        assert "using UnityEngine.TestTools;" in result

    def test_unity_test_method(self):
        result = generate_test_class(
            "AsyncTest",
            test_methods=[
                {"name": "TestDamageOverTime", "body": "yield return null;", "is_unity_test": True}
            ],
        )
        assert "[UnityTest]" in result
        assert "IEnumerator" in result

    def test_setup_teardown(self):
        result = generate_test_class(
            "LifecycleTest",
            setup_body="_sut = new object();",
            teardown_body="_sut = null;",
        )
        assert "[SetUp]" in result
        assert "[TearDown]" in result

    def test_target_class(self):
        result = generate_test_class("HealthTest", target_class="PlayerHealth")
        assert "private PlayerHealth _sut;" in result

    def test_namespace(self):
        result = generate_test_class(
            "NamespacedTest", namespace="VeilBreakers.Tests"
        )
        assert "namespace VeilBreakers.Tests" in result

    def test_balanced_braces(self):
        result = generate_test_class(
            "BraceTest",
            test_methods=[
                {"name": "Test1", "body": "Assert.AreEqual(1, 1);"},
                {"name": "Test2", "is_unity_test": True},
            ],
            setup_body="Debug.Log(\"setup\");",
            teardown_body="Debug.Log(\"teardown\");",
            namespace="VeilBreakers.Tests",
        )
        assert check_brace_balance(result)


# ===================================================================
# TestRunnerScript (CODE-05)
# ===================================================================


class TestRunnerScript:
    """Test generate_test_runner_script for TestRunnerApi integration."""

    def test_basic_runner(self):
        result = generate_test_runner_script()
        assert "TestRunnerApi" in result
        assert "ICallbacks" in result
        assert "vb_result.json" in result
        assert "MenuItem" in result
        assert "runSynchronously" in result

    def test_editmode_filter(self):
        result = generate_test_runner_script(test_mode="EditMode")
        assert "TestMode.EditMode" in result

    def test_playmode_filter(self):
        result = generate_test_runner_script(test_mode="PlayMode")
        assert "TestMode.PlayMode" in result

    def test_assembly_filter(self):
        result = generate_test_runner_script(
            assembly_filter="VeilBreakers.Tests.EditMode"
        )
        assert "assemblyNames" in result
        assert "VeilBreakers.Tests.EditMode" in result

    def test_result_json_structure(self):
        result = generate_test_runner_script()
        assert "pass_count" in result
        assert "fail_count" in result
        assert "tests" in result

    def test_balanced_braces(self):
        result = generate_test_runner_script()
        assert check_brace_balance(result)

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="test_mode"):
            generate_test_runner_script(test_mode="Invalid")


# ===================================================================
# TestServiceLocator (CODE-06)
# ===================================================================


class TestServiceLocator:
    """Test generate_service_locator for service registry pattern."""

    def test_basic_locator(self):
        result = generate_service_locator()
        assert "ServiceLocator" in result
        assert "Register<T>" in result
        assert "Get<T>" in result
        assert "TryGet" in result
        assert "Unregister" in result
        assert "Clear" in result

    def test_namespace(self):
        result = generate_service_locator()
        assert "VeilBreakers.Patterns" in result

    def test_scene_persistent(self):
        result = generate_service_locator(include_scene_persistent=True)
        assert "ServiceLocatorInitializer" in result
        assert "RuntimeInitializeOnLoadMethod" in result

    def test_without_scene_persistent(self):
        result = generate_service_locator(include_scene_persistent=False)
        assert "ServiceLocatorInitializer" not in result

    def test_balanced_braces(self):
        result = generate_service_locator()
        assert check_brace_balance(result)

    def test_balanced_braces_without_persistent(self):
        result = generate_service_locator(include_scene_persistent=False)
        assert check_brace_balance(result)


# ===================================================================
# TestObjectPool (CODE-07)
# ===================================================================


class TestObjectPool:
    """Test generate_object_pool for generic pooling system."""

    def test_basic_pool(self):
        result = generate_object_pool()
        assert "ObjectPool<T>" in result
        assert "Stack<T>" in result
        assert "Get()" in result
        assert "Release" in result
        assert "CountActive" in result
        assert "CountInactive" in result

    def test_gameobject_pool(self):
        result = generate_object_pool(include_gameobject_pool=True)
        assert "GameObjectPool" in result
        assert "SetActive" in result
        assert "Instantiate" in result

    def test_without_gameobject_pool(self):
        result = generate_object_pool(include_gameobject_pool=False)
        assert "GameObjectPool" not in result

    def test_namespace(self):
        result = generate_object_pool()
        assert "VeilBreakers.Patterns" in result

    def test_balanced_braces(self):
        result = generate_object_pool()
        assert check_brace_balance(result)

    def test_balanced_braces_without_go_pool(self):
        result = generate_object_pool(include_gameobject_pool=False)
        assert check_brace_balance(result)


# ===================================================================
# TestSingleton (CODE-08)
# ===================================================================


class TestSingleton:
    """Test generate_singleton for MonoBehaviour and Plain singletons."""

    def test_monobehaviour_singleton(self):
        result = generate_singleton("GameManager", "MonoBehaviour")
        assert "MonoBehaviour" in result
        assert "Instance" in result
        assert "Awake" in result
        assert "_instance" in result

    def test_persistent(self):
        result = generate_singleton("GameManager", persistent=True)
        assert "DontDestroyOnLoad" in result

    def test_non_persistent(self):
        result = generate_singleton("GameManager", persistent=False)
        assert "DontDestroyOnLoad" not in result

    def test_plain_singleton(self):
        result = generate_singleton("ConfigManager", "Plain")
        assert "Lazy<" in result
        # Check for private constructor
        assert "private ConfigManager()" in result

    def test_compatible_comment(self):
        result = generate_singleton("GameManager")
        assert "SingletonMonoBehaviour" in result

    def test_balanced_braces_mono(self):
        result = generate_singleton("Test1", "MonoBehaviour")
        assert check_brace_balance(result)

    def test_balanced_braces_plain(self):
        result = generate_singleton("Test2", "Plain")
        assert check_brace_balance(result)


# ===================================================================
# TestStateMachine (CODE-09)
# ===================================================================


class TestStateMachine:
    """Test generate_state_machine for IState/StateMachine/BaseState."""

    def test_state_machine(self):
        result = generate_state_machine()
        assert "IState" in result
        assert "StateMachine" in result
        assert "BaseState" in result
        assert "ChangeState" in result
        assert "Enter" in result
        assert "Exit" in result
        assert "Update" in result

    def test_interface_methods(self):
        result = generate_state_machine()
        assert "void Enter();" in result
        assert "void Exit();" in result
        assert "void Update();" in result
        assert "void FixedUpdate();" in result

    def test_state_dictionary(self):
        result = generate_state_machine()
        assert "Dictionary<Type, IState>" in result
        assert "AddState" in result

    def test_namespace(self):
        result = generate_state_machine()
        assert "VeilBreakers.Patterns" in result

    def test_balanced_braces(self):
        result = generate_state_machine()
        assert check_brace_balance(result)


# ===================================================================
# TestSOEvents (CODE-10)
# ===================================================================


class TestSOEvents:
    """Test generate_so_event_channel for ScriptableObject event channels."""

    def test_base_event_channel(self):
        result = generate_so_event_channel()
        assert "GameEvent" in result
        assert "GameEvent<T>" in result
        assert "GameEventListener" in result
        assert "CreateAssetMenu" in result
        assert "Action" in result

    def test_namespace_distinct(self):
        result = generate_so_event_channel()
        assert "VeilBreakers.Events.Channels" in result
        assert "VeilBreakers.Core" not in result

    def test_specific_event(self):
        result = generate_so_event_channel(event_name="PlayerDeath")
        assert "PlayerDeathEvent" in result

    def test_typed_event(self):
        result = generate_so_event_channel(
            event_name="DamageDealt", has_parameter=True, parameter_type="float"
        )
        assert "GameEvent<float>" in result

    def test_listener_component(self):
        result = generate_so_event_channel()
        assert "GameEventListener" in result
        assert "UnityEvent _response" in result
        assert "OnEnable" in result
        assert "OnDisable" in result

    def test_editor_debug_log(self):
        result = generate_so_event_channel()
        assert "#if UNITY_EDITOR" in result

    def test_balanced_braces(self):
        result = generate_so_event_channel()
        assert check_brace_balance(result)

    def test_balanced_braces_specific(self):
        result = generate_so_event_channel(event_name="Test")
        assert check_brace_balance(result)

    def test_balanced_braces_typed(self):
        result = generate_so_event_channel(
            event_name="Test", has_parameter=True, parameter_type="int"
        )
        assert check_brace_balance(result)
