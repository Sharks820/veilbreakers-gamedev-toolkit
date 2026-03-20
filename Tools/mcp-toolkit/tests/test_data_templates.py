"""Unit tests for data architecture template generators (DATA-01 through DATA-04).

Tests cover:
- TestScriptableObjectAssets (DATA-02): SO definitions and .asset creation scripts
- TestJsonConfig (DATA-01): JSON validation and typed loading generators
- TestLocalization (DATA-03): Localization setup and string table entry scripts
- TestDataAuthoring (DATA-04): IMGUI EditorWindow for batch SO authoring
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.data_templates import (
    generate_so_definition,
    generate_asset_creation_script,
    generate_json_validator_script,
    generate_json_loader_script,
    generate_localization_setup_script,
    generate_localization_entries_script,
    generate_data_authoring_window,
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
# TestScriptableObjectAssets (DATA-02)
# ===================================================================


class TestScriptableObjectAssets:
    """Test ScriptableObject definition and asset creation script generators."""

    def test_so_definition_basic(self):
        result = generate_so_definition("ItemConfig")
        assert "class ItemConfig : ScriptableObject" in result
        assert "CreateAssetMenu" in result
        assert "using UnityEngine;" in result
        assert check_brace_balance(result)

    def test_so_definition_with_fields(self):
        result = generate_so_definition(
            "ItemConfig",
            fields=[
                {"name": "itemName", "type": "string"},
                {"name": "rarity", "type": "int", "default": "0"},
                {"name": "icon", "type": "Sprite", "header": "Visual"},
            ],
        )
        assert "itemName" in result
        assert "rarity" in result
        assert "icon" in result
        assert '[Header("Visual")]' in result
        assert check_brace_balance(result)

    def test_so_definition_with_namespace(self):
        result = generate_so_definition(
            "WeaponConfig", namespace="VeilBreakers.Items"
        )
        assert "namespace VeilBreakers.Items" in result
        assert "class WeaponConfig : ScriptableObject" in result
        assert check_brace_balance(result)

    def test_so_definition_custom_menu(self):
        result = generate_so_definition(
            "WeaponConfig", menu_name="Items/WeaponConfig"
        )
        assert 'menuName = "VeilBreakers/Items/WeaponConfig"' in result

    def test_so_definition_with_tooltip(self):
        result = generate_so_definition(
            "ItemConfig",
            fields=[
                {
                    "name": "damage",
                    "type": "float",
                    "tooltip": "Base damage dealt",
                },
            ],
        )
        assert "[Tooltip(" in result
        assert "Base damage dealt" in result

    def test_so_definition_with_summary(self):
        result = generate_so_definition(
            "ItemConfig", summary="Defines an item in the game world."
        )
        assert "/// <summary>" in result
        assert "Defines an item in the game world." in result

    def test_so_definition_default_values(self):
        result = generate_so_definition(
            "ItemConfig",
            fields=[
                {"name": "maxStack", "type": "int", "default": "99"},
                {"name": "displayName", "type": "string", "default": "Unknown"},
            ],
        )
        assert "= 99" in result
        assert '= "Unknown"' in result

    def test_asset_creation_script(self):
        result = generate_asset_creation_script(
            "MonsterConfig",
            assets=[{"monsterId": "goblin", "baseHp": 50}],
            category="Monsters",
        )
        assert "ScriptableObject.CreateInstance" in result
        assert "AssetDatabase.CreateAsset" in result
        assert "Assets/Data/Monsters" in result
        assert "vb_result.json" in result
        assert check_brace_balance(result)

    def test_asset_creation_undo(self):
        result = generate_asset_creation_script(
            "ItemConfig",
            assets=[{"itemName": "Sword"}],
        )
        assert "Undo.RegisterCreatedObjectUndo" in result

    def test_asset_creation_multiple(self):
        result = generate_asset_creation_script(
            "MonsterConfig",
            assets=[
                {"monsterId": "goblin", "baseHp": 50},
                {"monsterId": "skeleton", "baseHp": 80},
                {"monsterId": "dragon", "baseHp": 500},
            ],
            category="Monsters",
        )
        # Should reference all three assets
        assert "goblin" in result
        assert "skeleton" in result
        assert "dragon" in result
        assert check_brace_balance(result)

    def test_asset_creation_save_refresh(self):
        result = generate_asset_creation_script("ItemConfig")
        assert "AssetDatabase.SaveAssets()" in result
        assert "AssetDatabase.Refresh()" in result

    def test_sanitization_in_so(self):
        result = generate_so_definition("Item Config!@#")
        # Special chars should be stripped from identifier
        assert "ItemConfig" in result
        assert "!@#" not in result
        assert check_brace_balance(result)


# ===================================================================
# TestJsonConfig (DATA-01)
# ===================================================================


class TestJsonConfig:
    """Test JSON config validation and loader generators."""

    def test_json_validator_basic(self):
        result = generate_json_validator_script(
            "MonsterData", "Resources/Data/monsters.json"
        )
        assert "MenuItem" in result
        assert "vb_result.json" in result
        assert "File.ReadAllText" in result
        assert check_brace_balance(result)

    def test_json_validator_with_schema(self):
        result = generate_json_validator_script(
            "MonsterData",
            "Resources/Data/monsters.json",
            schema={
                "monster_id": {"type": "string", "required": True},
                "base_hp": {"type": "int", "min": 1},
            },
        )
        # Should validate required string field
        assert "IsNullOrEmpty" in result
        assert "monster_id" in result
        # Should validate min value
        assert "base_hp" in result
        assert check_brace_balance(result)

    def test_json_validator_wrapper_class(self):
        result = generate_json_validator_script(
            "MonsterData",
            "Resources/Data/monsters.json",
            schema={"monster_id": {"type": "string", "required": True}},
            wrapper_class="MonsterDataWrapper",
        )
        assert "MonsterDataWrapper" in result
        assert check_brace_balance(result)

    def test_json_validator_range_max(self):
        result = generate_json_validator_script(
            "BalanceConfig",
            "Resources/Data/balance.json",
            schema={
                "difficulty": {"type": "int", "min": 1, "max": 10},
            },
            wrapper_class="BalanceWrapper",
        )
        assert ">= 1" in result or "< 1" in result
        assert "exceeds 10" in result or "> 10" in result
        assert check_brace_balance(result)

    def test_json_loader_basic(self):
        result = generate_json_loader_script(
            "MonsterData",
            fields=[
                {"name": "monster_id", "type": "string"},
                {"name": "base_hp", "type": "int"},
            ],
        )
        assert "[System.Serializable]" in result
        assert "monster_id" in result
        assert "base_hp" in result
        assert check_brace_balance(result)

    def test_json_loader_array_wrapper(self):
        result = generate_json_loader_script(
            "MonsterData",
            fields=[{"name": "id", "type": "string"}],
            is_array=True,
        )
        assert "MonsterDataWrapper" in result
        assert "List<MonsterData>" in result
        assert check_brace_balance(result)

    def test_json_loader_resources_load(self):
        result = generate_json_loader_script(
            "MonsterData",
            fields=[{"name": "id", "type": "string"}],
            json_path="Data/monsters",
        )
        assert "Resources.Load<TextAsset>" in result

    def test_json_loader_single_object(self):
        result = generate_json_loader_script(
            "GameSettings",
            fields=[{"name": "difficulty", "type": "int"}],
            is_array=False,
        )
        # Should not create wrapper
        assert "GameSettingsWrapper" not in result
        assert "JsonUtility.FromJson<GameSettings>" in result
        assert check_brace_balance(result)

    def test_json_loader_namespace(self):
        result = generate_json_loader_script(
            "ItemData",
            namespace="VeilBreakers.Data",
            fields=[{"name": "name", "type": "string"}],
        )
        assert "namespace VeilBreakers.Data" in result

    def test_all_json_scripts_balanced_braces(self):
        validator = generate_json_validator_script(
            "TestData", "Resources/Data/test.json"
        )
        loader = generate_json_loader_script(
            "TestData",
            fields=[{"name": "id", "type": "string"}],
        )
        assert check_brace_balance(validator)
        assert check_brace_balance(loader)


# ===================================================================
# TestLocalization (DATA-03)
# ===================================================================


class TestLocalization:
    """Test localization setup and entry generators."""

    def test_localization_setup_basic(self):
        result = generate_localization_setup_script()
        assert "Locale.CreateLocale" in result
        assert "CreateStringTableCollection" in result
        assert "VeilBreakers_UI" in result
        assert check_brace_balance(result)

    def test_localization_setup_multiple_locales(self):
        result = generate_localization_setup_script(locales=["es", "fr"])
        assert "es" in result
        assert "fr" in result
        assert "en" in result  # default locale always present

    def test_localization_setup_custom_table(self):
        result = generate_localization_setup_script(
            table_name="VeilBreakers_Combat"
        )
        assert "VeilBreakers_Combat" in result

    def test_localization_setup_output_dir(self):
        result = generate_localization_setup_script(
            output_dir="Assets/Game/Localization"
        )
        assert "Assets/Game/Localization" in result

    def test_localization_setup_creates_folders(self):
        result = generate_localization_setup_script()
        assert "AssetDatabase.CreateFolder" in result
        assert "Locales" in result
        assert "StringTables" in result

    def test_localization_entries(self):
        result = generate_localization_entries_script(
            entries={
                "UI.MainMenu.StartGame": "Start Game",
                "Combat.Brand.Iron": "Iron",
            }
        )
        assert "UI.MainMenu.StartGame" in result
        assert "Start Game" in result
        assert "Combat.Brand.Iron" in result
        assert "Iron" in result
        assert "AddEntry" in result
        assert check_brace_balance(result)

    def test_localization_entries_locale(self):
        result = generate_localization_entries_script(
            locale="es",
            entries={"UI.MainMenu.StartGame": "Iniciar Juego"},
        )
        assert "es" in result

    def test_localization_entries_tracking(self):
        result = generate_localization_entries_script(
            entries={"key1": "val1"}
        )
        # Should track added/skipped/failed counts
        assert "added" in result
        assert "skipped" in result
        assert "failed" in result

    def test_localization_setup_preprocessor_guard(self):
        result = generate_localization_setup_script()
        assert "#if UNITY_EDITOR" in result
        assert "#endif" in result

    def test_all_localization_scripts_balanced_braces(self):
        setup = generate_localization_setup_script()
        entries = generate_localization_entries_script(
            entries={"key": "value"}
        )
        assert check_brace_balance(setup)
        assert check_brace_balance(entries)


# ===================================================================
# TestDataAuthoring (DATA-04)
# ===================================================================


class TestDataAuthoring:
    """Test data authoring EditorWindow generator."""

    def test_authoring_window_basic(self):
        result = generate_data_authoring_window("ItemEditor", "ItemConfig")
        assert "EditorWindow" in result
        assert "MenuItem" in result
        assert "OnGUI" in result
        assert "FindAssets" in result
        assert check_brace_balance(result)

    def test_authoring_window_fields(self):
        result = generate_data_authoring_window(
            "ItemEditor",
            "ItemConfig",
            fields=[
                {"name": "itemName", "type": "string", "label": "Name"},
            ],
        )
        assert "TextField" in result or "PropertyField" in result
        assert "Name" in result

    def test_authoring_window_category(self):
        result = generate_data_authoring_window(
            "ItemEditor",
            "ItemConfig",
            category="Items",
        )
        assert "Items" in result

    def test_authoring_window_create_button(self):
        result = generate_data_authoring_window("ItemEditor", "ItemConfig")
        assert "ScriptableObject.CreateInstance" in result or "CreateNewAsset" in result

    def test_authoring_window_save_dirty(self):
        result = generate_data_authoring_window("ItemEditor", "ItemConfig")
        assert "EditorUtility.SetDirty" in result
        assert "AssetDatabase.SaveAssets" in result

    def test_authoring_window_delete(self):
        result = generate_data_authoring_window("ItemEditor", "ItemConfig")
        assert "Delete" in result
        assert "AssetDatabase.DeleteAsset" in result

    def test_authoring_window_scroll_view(self):
        result = generate_data_authoring_window("ItemEditor", "ItemConfig")
        assert "BeginScrollView" in result
        assert "EndScrollView" in result

    def test_authoring_window_namespace(self):
        result = generate_data_authoring_window(
            "ItemEditor",
            "ItemConfig",
            namespace="VeilBreakers.Data",
        )
        assert "using VeilBreakers.Data;" in result

    def test_authoring_window_custom_menu(self):
        result = generate_data_authoring_window(
            "ItemEditor",
            "ItemConfig",
            menu_path="Item Database",
        )
        assert "Item Database" in result

    def test_authoring_window_multiple_field_types(self):
        result = generate_data_authoring_window(
            "StatsEditor",
            "StatsConfig",
            fields=[
                {"name": "statName", "type": "string", "label": "Name"},
                {"name": "value", "type": "int", "label": "Value"},
                {"name": "multiplier", "type": "float", "label": "Multiplier"},
                {"name": "isActive", "type": "bool", "label": "Active"},
            ],
        )
        assert "TextField" in result
        assert "IntField" in result
        assert "FloatField" in result
        assert "Toggle" in result

    def test_all_authoring_scripts_balanced_braces(self):
        basic = generate_data_authoring_window("TestEditor", "TestConfig")
        with_fields = generate_data_authoring_window(
            "TestEditor",
            "TestConfig",
            fields=[{"name": "val", "type": "int", "label": "Val"}],
        )
        assert check_brace_balance(basic)
        assert check_brace_balance(with_fields)
