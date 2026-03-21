"""Unit tests for content and progression system C# template generators.

Tests that each generator function produces valid C# source containing
the expected keywords, Unity API calls, parameter substitutions, and
correct delegation to existing VeilBreakers systems.

Runtime generators must NEVER contain 'using UnityEditor;'.
Editor generators (DPS calc, encounter sim, stat curve) MUST contain it.
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.content_templates import (
    generate_inventory_system_script,
    generate_dialogue_system_script,
    generate_quest_system_script,
    generate_loot_table_script,
    generate_crafting_system_script,
    generate_skill_tree_script,
    generate_dps_calculator_script,
    generate_encounter_simulator_script,
    generate_stat_curve_editor_script,
    generate_shop_system_script,
    generate_journal_system_script,
)


# ---------------------------------------------------------------------------
# GAME-02: Inventory system
# ---------------------------------------------------------------------------


class TestInventorySystem:
    """Tests for generate_inventory_system_script()."""

    def test_returns_four_tuple(self):
        result = generate_inventory_system_script()
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_item_so_contains_class(self):
        item_so, _, _, _ = generate_inventory_system_script()
        assert "class VB_ItemData" in item_so

    def test_item_so_has_create_asset_menu(self):
        item_so, _, _, _ = generate_inventory_system_script()
        assert "CreateAssetMenu" in item_so

    def test_item_so_is_scriptable_object(self):
        item_so, _, _, _ = generate_inventory_system_script()
        assert "ScriptableObject" in item_so

    def test_item_type_enum_values(self):
        item_so, _, _, _ = generate_inventory_system_script()
        assert "Consumable = 0" in item_so
        assert "Weapon = 1" in item_so
        assert "Armor = 2" in item_so
        assert "Accessory = 3" in item_so
        assert "Material = 4" in item_so
        assert "KeyItem = 5" in item_so

    def test_item_rarity_enum_values(self):
        item_so, _, _, _ = generate_inventory_system_script()
        assert "Common = 0" in item_so
        assert "Uncommon = 1" in item_so
        assert "Rare = 2" in item_so
        assert "Epic = 3" in item_so
        assert "Legendary = 4" in item_so

    def test_item_so_has_stat_buffs(self):
        item_so, _, _, _ = generate_inventory_system_script()
        assert "StatBuff" in item_so
        assert "statBuffs" in item_so

    def test_item_so_has_corruption_change(self):
        item_so, _, _, _ = generate_inventory_system_script()
        assert "corruptionChange" in item_so

    def test_item_so_has_path_change(self):
        item_so, _, _, _ = generate_inventory_system_script()
        assert "pathChange" in item_so

    def test_item_so_has_buy_sell_price(self):
        item_so, _, _, _ = generate_inventory_system_script()
        assert "buyPrice" in item_so
        assert "sellPrice" in item_so

    def test_item_so_has_stackable(self):
        item_so, _, _, _ = generate_inventory_system_script()
        assert "isStackable" in item_so
        assert "maxStack" in item_so

    def test_inventory_contains_class(self):
        _, inv, _, _ = generate_inventory_system_script()
        assert "class VB_InventorySystem" in inv

    def test_inventory_is_monobehaviour(self):
        _, inv, _, _ = generate_inventory_system_script()
        assert "MonoBehaviour" in inv

    def test_inventory_has_add_remove(self):
        _, inv, _, _ = generate_inventory_system_script()
        assert "AddItem" in inv
        assert "RemoveItem" in inv

    def test_inventory_has_equip_unequip(self):
        _, inv, _, _ = generate_inventory_system_script()
        assert "Equip" in inv
        assert "Unequip" in inv

    def test_inventory_has_equipment_slots(self):
        item_so, inv, _, _ = generate_inventory_system_script()
        assert "EquipmentSlot" in item_so
        assert "Head" in item_so
        assert "Weapon" in item_so
        assert "EquipmentSlot" in inv

    def test_inventory_has_event_bus(self):
        _, inv, _, _ = generate_inventory_system_script()
        assert "EventBus" in inv

    def test_inventory_has_storage(self):
        _, inv, _, _ = generate_inventory_system_script()
        assert "StorageContainer" in inv
        assert "OpenStorage" in inv

    def test_inventory_has_drag_support(self):
        _, inv, uxml, uss = generate_inventory_system_script()
        assert "MoveItem" in inv
        has_drag = "drag" in uss.lower() or "PointerManipulator" in uss
        assert has_drag

    def test_custom_grid_dimensions(self):
        _, inv, _, _ = generate_inventory_system_script(grid_width=10, grid_height=6)
        assert "gridWidth = 10" in inv
        assert "gridHeight = 6" in inv

    def test_custom_equipment_slots(self):
        item_so, _, _, _ = generate_inventory_system_script(
            equipment_slots=["MainHand", "OffHand", "Helm"]
        )
        assert "MainHand" in item_so
        assert "OffHand" in item_so
        assert "Helm" in item_so

    def test_no_editor_namespace_item_so(self):
        item_so, _, _, _ = generate_inventory_system_script()
        assert "using UnityEditor" not in item_so

    def test_no_editor_namespace_inventory(self):
        _, inv, _, _ = generate_inventory_system_script()
        assert "using UnityEditor" not in inv

    def test_uxml_not_empty(self):
        _, _, uxml, _ = generate_inventory_system_script()
        assert len(uxml) > 100

    def test_uss_not_empty(self):
        _, _, _, uss = generate_inventory_system_script()
        assert len(uss) > 100

    def test_uxml_has_grid_slots(self):
        _, _, uxml, _ = generate_inventory_system_script()
        assert "grid-slot" in uxml

    def test_uxml_has_equipment_panel(self):
        _, _, uxml, _ = generate_inventory_system_script()
        assert "equipment-panel" in uxml

    def test_item_so_has_namespace(self):
        item_so, _, _, _ = generate_inventory_system_script(namespace="Test.NS")
        assert "namespace Test.NS" in item_so


# ---------------------------------------------------------------------------
# GAME-03: Dialogue system
# ---------------------------------------------------------------------------


class TestDialogueSystem:
    """Tests for generate_dialogue_system_script()."""

    def test_returns_four_tuple(self):
        result = generate_dialogue_system_script()
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_dialogue_data_contains_class(self):
        data, _, _, _ = generate_dialogue_system_script()
        assert "class VB_DialogueNode" in data

    def test_dialogue_data_has_create_asset_menu(self):
        data, _, _, _ = generate_dialogue_system_script()
        assert "CreateAssetMenu" in data

    def test_dialogue_data_has_speaker(self):
        data, _, _, _ = generate_dialogue_system_script()
        assert "speaker" in data

    def test_dialogue_data_has_choices(self):
        data, _, _, _ = generate_dialogue_system_script()
        assert "DialogueChoice" in data
        assert "choices" in data

    def test_yarn_spinner_title_format(self):
        data, _, _, _ = generate_dialogue_system_script()
        assert 'title: ' in data

    def test_yarn_spinner_separator(self):
        data, _, _, _ = generate_dialogue_system_script()
        assert '---' in data

    def test_yarn_spinner_end_marker(self):
        data, _, _, _ = generate_dialogue_system_script()
        assert '===' in data

    def test_yarn_spinner_choice_arrow(self):
        data, _, _, _ = generate_dialogue_system_script()
        assert '-> ' in data

    def test_yarn_spinner_command_syntax(self):
        data, _, _, _ = generate_dialogue_system_script()
        assert '<<' in data
        assert '>>' in data

    def test_dialogue_system_contains_class(self):
        _, sys, _, _ = generate_dialogue_system_script()
        assert "class VB_DialogueSystem" in sys

    def test_dialogue_system_has_start(self):
        _, sys, _, _ = generate_dialogue_system_script()
        assert "StartDialogue" in sys

    def test_dialogue_system_has_advance(self):
        _, sys, _, _ = generate_dialogue_system_script()
        assert "AdvanceLine" in sys

    def test_dialogue_system_has_select_choice(self):
        _, sys, _, _ = generate_dialogue_system_script()
        assert "SelectChoice" in sys

    def test_dialogue_system_has_end(self):
        _, sys, _, _ = generate_dialogue_system_script()
        assert "EndDialogue" in sys

    def test_dialogue_system_has_condition_checking(self):
        _, sys, _, _ = generate_dialogue_system_script()
        assert "EvaluateCondition" in sys

    def test_dialogue_system_has_event_bus(self):
        _, sys, _, _ = generate_dialogue_system_script()
        assert "EventBus" in sys

    def test_uxml_has_speaker_portrait(self):
        _, _, uxml, _ = generate_dialogue_system_script()
        assert "speaker-portrait" in uxml

    def test_uxml_has_choice_buttons(self):
        _, _, uxml, _ = generate_dialogue_system_script()
        assert "choice-button" in uxml

    def test_no_editor_namespace_data(self):
        data, _, _, _ = generate_dialogue_system_script()
        assert "using UnityEditor" not in data

    def test_no_editor_namespace_system(self):
        _, sys, _, _ = generate_dialogue_system_script()
        assert "using UnityEditor" not in sys

    def test_npc_trigger_class(self):
        _, sys, _, _ = generate_dialogue_system_script()
        assert "VB_NPCDialogueTrigger" in sys


# ---------------------------------------------------------------------------
# GAME-04: Quest system
# ---------------------------------------------------------------------------


class TestQuestSystem:
    """Tests for generate_quest_system_script()."""

    def test_returns_four_tuple(self):
        result = generate_quest_system_script()
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_quest_data_contains_class(self):
        data, _, _, _ = generate_quest_system_script()
        assert "class VB_QuestData" in data

    def test_quest_state_enum(self):
        data, _, _, _ = generate_quest_system_script()
        assert "NotStarted" in data
        assert "Active" in data
        assert "Complete" in data
        assert "TurnedIn" in data

    def test_objective_types(self):
        data, _, _, _ = generate_quest_system_script()
        assert "Kill" in data
        assert "Collect" in data
        assert "TalkTo" in data
        assert "ReachLocation" in data

    def test_quest_data_has_rewards(self):
        data, _, _, _ = generate_quest_system_script()
        assert "QuestReward" in data
        assert "experiencePoints" in data
        assert "gold" in data
        assert "rewardItems" in data

    def test_quest_data_has_objectives(self):
        data, _, _, _ = generate_quest_system_script()
        assert "QuestObjective" in data
        assert "objectives" in data

    def test_quest_data_has_giver_npc(self):
        data, _, _, _ = generate_quest_system_script()
        assert "questGiverNpcId" in data

    def test_quest_data_has_create_asset_menu(self):
        data, _, _, _ = generate_quest_system_script()
        assert "CreateAssetMenu" in data

    def test_quest_system_contains_class(self):
        _, sys, _, _ = generate_quest_system_script()
        assert "class VB_QuestSystem" in sys

    def test_quest_system_has_accept(self):
        _, sys, _, _ = generate_quest_system_script()
        assert "AcceptQuest" in sys

    def test_quest_system_has_update_objective(self):
        _, sys, _, _ = generate_quest_system_script()
        assert "UpdateObjective" in sys

    def test_quest_system_has_turn_in(self):
        _, sys, _, _ = generate_quest_system_script()
        assert "TurnInQuest" in sys

    def test_quest_system_has_reward_distribution(self):
        _, sys, _, _ = generate_quest_system_script()
        assert "DistributeRewards" in sys

    def test_quest_system_has_event_bus(self):
        _, sys, _, _ = generate_quest_system_script()
        assert "EventBus" in sys

    def test_quest_system_reward_via_event_bus(self):
        _, sys, _, _ = generate_quest_system_script()
        assert "OnXPGained" in sys
        assert "OnCurrencyGained" in sys

    def test_quest_log_tabs(self):
        _, _, uxml, _ = generate_quest_system_script()
        assert "Main" in uxml
        assert "Side" in uxml
        assert "Daily" in uxml

    def test_no_editor_namespace_data(self):
        data, _, _, _ = generate_quest_system_script()
        assert "using UnityEditor" not in data

    def test_no_editor_namespace_system(self):
        _, sys, _, _ = generate_quest_system_script()
        assert "using UnityEditor" not in sys

    def test_quest_system_has_get_by_state(self):
        _, sys, _, _ = generate_quest_system_script()
        assert "GetQuestsByState" in sys

    def test_quest_system_has_get_by_type(self):
        _, sys, _, _ = generate_quest_system_script()
        assert "GetQuestsByType" in sys


# ---------------------------------------------------------------------------
# VB-08 / RPG-01: Loot table
# ---------------------------------------------------------------------------


class TestLootTable:
    """Tests for generate_loot_table_script()."""

    def test_returns_string(self):
        result = generate_loot_table_script()
        assert isinstance(result, str)

    def test_contains_class(self):
        result = generate_loot_table_script()
        assert "class VB_LootTable" in result

    def test_has_create_asset_menu(self):
        result = generate_loot_table_script()
        assert "CreateAssetMenu" in result

    def test_has_loot_entry(self):
        result = generate_loot_table_script()
        assert "LootEntry" in result
        assert "weight" in result

    def test_has_roll_method(self):
        result = generate_loot_table_script()
        assert "Roll(" in result

    def test_roll_takes_brand_and_corruption(self):
        result = generate_loot_table_script()
        assert "Brand monsterBrand" in result
        assert "float corruptionLevel" in result

    def test_has_weighted_random(self):
        result = generate_loot_table_script()
        assert "totalWeight" in result
        assert "cumulative" in result

    def test_brand_system_delegation(self):
        result = generate_loot_table_script()
        assert "BrandSystem.GetEffectiveness" in result

    def test_brand_affinity_weight_boost(self):
        result = generate_loot_table_script()
        assert "1.5f" in result

    def test_corruption_modifier(self):
        result = generate_loot_table_script()
        assert "corruptionLevel > 0.5f" in result
        assert "0.3f" in result

    def test_has_min_rarity(self):
        result = generate_loot_table_script()
        assert "minRarity" in result

    def test_has_quantity_range(self):
        result = generate_loot_table_script()
        assert "minQuantity" in result
        assert "maxQuantity" in result

    def test_has_brand_affinity_field(self):
        result = generate_loot_table_script()
        assert "brandAffinity" in result

    def test_no_editor_namespace(self):
        result = generate_loot_table_script()
        assert "using UnityEditor" not in result


# ---------------------------------------------------------------------------
# GAME-09: Crafting system
# ---------------------------------------------------------------------------


class TestCraftingSystem:
    """Tests for generate_crafting_system_script()."""

    def test_returns_two_tuple(self):
        result = generate_crafting_system_script()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_recipe_contains_class(self):
        recipe, _ = generate_crafting_system_script()
        assert "class VB_Recipe" in recipe

    def test_recipe_has_create_asset_menu(self):
        recipe, _ = generate_crafting_system_script()
        assert "CreateAssetMenu" in recipe

    def test_recipe_has_ingredients(self):
        recipe, _ = generate_crafting_system_script()
        assert "CraftingIngredient" in recipe
        assert "ingredients" in recipe

    def test_recipe_has_result_item(self):
        recipe, _ = generate_crafting_system_script()
        assert "resultItem" in recipe

    def test_recipe_has_station_type(self):
        recipe, _ = generate_crafting_system_script()
        assert "CraftingStationType" in recipe
        assert "requiredStation" in recipe

    def test_recipe_has_unlock_condition(self):
        recipe, _ = generate_crafting_system_script()
        assert "RecipeUnlockCondition" in recipe
        assert "questId" in recipe
        assert "requiredLevel" in recipe

    def test_crafting_system_contains_class(self):
        _, craft = generate_crafting_system_script()
        assert "class VB_CraftingSystem" in craft

    def test_crafting_has_can_craft(self):
        _, craft = generate_crafting_system_script()
        assert "CanCraft" in craft

    def test_crafting_has_craft(self):
        _, craft = generate_crafting_system_script()
        assert "Craft(" in craft

    def test_crafting_validates_ingredients(self):
        _, craft = generate_crafting_system_script()
        assert "HasItem" in craft

    def test_crafting_has_station_interaction(self):
        _, craft = generate_crafting_system_script()
        assert "OpenStation" in craft
        assert "CloseStation" in craft

    def test_crafting_has_event_bus(self):
        _, craft = generate_crafting_system_script()
        assert "EventBus" in craft

    def test_no_editor_namespace_recipe(self):
        recipe, _ = generate_crafting_system_script()
        assert "using UnityEditor" not in recipe

    def test_no_editor_namespace_craft(self):
        _, craft = generate_crafting_system_script()
        assert "using UnityEditor" not in craft


# ---------------------------------------------------------------------------
# GAME-10: Skill tree
# ---------------------------------------------------------------------------


class TestSkillTree:
    """Tests for generate_skill_tree_script()."""

    def test_returns_two_tuple(self):
        result = generate_skill_tree_script()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_skill_node_contains_class(self):
        node, _ = generate_skill_tree_script()
        assert "class VB_SkillNode" in node

    def test_skill_node_has_create_asset_menu(self):
        node, _ = generate_skill_tree_script()
        assert "CreateAssetMenu" in node

    def test_skill_node_has_prerequisites(self):
        node, _ = generate_skill_tree_script()
        assert "prerequisites" in node

    def test_skill_node_has_brand_requirement(self):
        node, _ = generate_skill_tree_script()
        assert "requiredBrand" in node
        assert "Brand" in node

    def test_skill_node_has_stat_bonuses(self):
        node, _ = generate_skill_tree_script()
        assert "SkillStatBonus" in node
        assert "statBonuses" in node

    def test_skill_node_has_unlock_cost(self):
        node, _ = generate_skill_tree_script()
        assert "unlockCost" in node

    def test_skill_tree_contains_class(self):
        _, tree = generate_skill_tree_script()
        assert "class VB_SkillTree" in tree

    def test_skill_tree_has_hero_paths(self):
        _, tree = generate_skill_tree_script()
        assert "IRONBOUND" in tree
        assert "FANGBORN" in tree
        assert "VOIDTOUCHED" in tree
        assert "UNCHAINED" in tree

    def test_skill_tree_has_allocate_point(self):
        _, tree = generate_skill_tree_script()
        assert "AllocatePoint" in tree

    def test_skill_tree_has_reset_points(self):
        _, tree = generate_skill_tree_script()
        assert "ResetPoints" in tree

    def test_skill_tree_has_prerequisite_validation(self):
        _, tree = generate_skill_tree_script()
        assert "CanAllocate" in tree
        assert "prerequisites" in tree

    def test_skill_tree_has_available_points(self):
        _, tree = generate_skill_tree_script()
        assert "_availablePoints" in tree
        assert "AvailablePoints" in tree

    def test_skill_tree_has_event_bus(self):
        _, tree = generate_skill_tree_script()
        assert "EventBus" in tree

    def test_custom_hero_paths(self):
        _, tree = generate_skill_tree_script(hero_paths=["PathA", "PathB"])
        assert "PathA" in tree
        assert "PathB" in tree

    def test_no_editor_namespace_node(self):
        node, _ = generate_skill_tree_script()
        assert "using UnityEditor" not in node

    def test_no_editor_namespace_tree(self):
        _, tree = generate_skill_tree_script()
        assert "using UnityEditor" not in tree

    def test_skill_tree_has_hero_path_enum(self):
        _, tree = generate_skill_tree_script()
        assert "enum Path" in tree

    def test_skill_tree_get_nodes_by_path(self):
        _, tree = generate_skill_tree_script()
        assert "GetNodesByPath" in tree


# ---------------------------------------------------------------------------
# GAME-12: DPS Calculator (EDITOR)
# ---------------------------------------------------------------------------


class TestDPSCalculator:
    """Tests for generate_dps_calculator_script()."""

    def test_returns_string(self):
        result = generate_dps_calculator_script()
        assert isinstance(result, str)

    def test_contains_editor_window(self):
        result = generate_dps_calculator_script()
        assert "EditorWindow" in result

    def test_contains_class(self):
        result = generate_dps_calculator_script()
        assert "class VB_DPSCalculator" in result

    def test_has_using_unity_editor(self):
        result = generate_dps_calculator_script()
        assert "using UnityEditor;" in result

    def test_has_brand_dropdowns(self):
        result = generate_dps_calculator_script()
        assert "BrandNames" in result
        assert "Popup" in result

    def test_has_all_ten_brands(self):
        result = generate_dps_calculator_script()
        assert "IRON" in result
        assert "SAVAGE" in result
        assert "SURGE" in result
        assert "VENOM" in result
        assert "DREAD" in result
        assert "LEECH" in result
        assert "GRACE" in result
        assert "MEND" in result
        assert "RUIN" in result
        assert "VOID" in result

    def test_has_dps_formula(self):
        result = generate_dps_calculator_script()
        assert "critChance" in result
        assert "critMult" in result or "critMultiplier" in result or "_critMultiplier" in result
        assert "brandMultiplier" in result or "_brandMultiplier" in result

    def test_has_ongui(self):
        result = generate_dps_calculator_script()
        assert "OnGUI" in result

    def test_has_menu_item(self):
        result = generate_dps_calculator_script()
        assert "MenuItem" in result

    def test_has_brand_system_reference(self):
        result = generate_dps_calculator_script()
        assert "BrandSystem" in result

    def test_has_synergy_system_reference(self):
        result = generate_dps_calculator_script()
        assert "SynergySystem" in result

    def test_custom_brands(self):
        result = generate_dps_calculator_script(brands=["FIRE", "ICE"])
        assert "FIRE" in result
        assert "ICE" in result


# ---------------------------------------------------------------------------
# GAME-12: Encounter Simulator (EDITOR)
# ---------------------------------------------------------------------------


class TestEncounterSimulator:
    """Tests for generate_encounter_simulator_script()."""

    def test_returns_string(self):
        result = generate_encounter_simulator_script()
        assert isinstance(result, str)

    def test_contains_editor_window(self):
        result = generate_encounter_simulator_script()
        assert "EditorWindow" in result

    def test_contains_class(self):
        result = generate_encounter_simulator_script()
        assert "class VB_EncounterSimulator" in result

    def test_has_using_unity_editor(self):
        result = generate_encounter_simulator_script()
        assert "using UnityEditor;" in result

    def test_has_monte_carlo(self):
        result = generate_encounter_simulator_script()
        assert "_encounterCount" in result

    def test_has_player_stats(self):
        result = generate_encounter_simulator_script()
        assert "_playerHP" in result
        assert "_playerATK" in result
        assert "_playerDEF" in result

    def test_has_enemy_stats(self):
        result = generate_encounter_simulator_script()
        assert "_enemyHP" in result
        assert "_enemyATK" in result
        assert "_enemyDEF" in result

    def test_has_run_simulation(self):
        result = generate_encounter_simulator_script()
        assert "RunSimulation" in result

    def test_has_run_button(self):
        result = generate_encounter_simulator_script()
        assert "Run Simulation" in result

    def test_has_results_output(self):
        result = generate_encounter_simulator_script()
        assert "_winRate" in result
        assert "_avgDuration" in result
        assert "_avgDamageTaken" in result
        assert "_avgDPS" in result

    def test_has_ongui(self):
        result = generate_encounter_simulator_script()
        assert "OnGUI" in result

    def test_has_menu_item(self):
        result = generate_encounter_simulator_script()
        assert "MenuItem" in result


# ---------------------------------------------------------------------------
# GAME-12: Stat Curve Editor (EDITOR)
# ---------------------------------------------------------------------------


class TestStatCurveEditor:
    """Tests for generate_stat_curve_editor_script()."""

    def test_returns_string(self):
        result = generate_stat_curve_editor_script()
        assert isinstance(result, str)

    def test_contains_editor_window(self):
        result = generate_stat_curve_editor_script()
        assert "EditorWindow" in result

    def test_contains_class(self):
        result = generate_stat_curve_editor_script()
        assert "class VB_StatCurveEditor" in result

    def test_has_using_unity_editor(self):
        result = generate_stat_curve_editor_script()
        assert "using UnityEditor;" in result

    def test_has_animation_curves(self):
        result = generate_stat_curve_editor_script()
        assert "AnimationCurve" in result

    def test_has_hp_atk_def_curves(self):
        result = generate_stat_curve_editor_script()
        assert "_hpCurve" in result
        assert "_atkCurve" in result
        assert "_defCurve" in result

    def test_has_curve_field(self):
        result = generate_stat_curve_editor_script()
        assert "CurveField" in result

    def test_has_enemy_type_dropdown(self):
        result = generate_stat_curve_editor_script()
        assert "_enemyTypes" in result
        assert "Popup" in result or "dropdown" in result.lower()

    def test_has_level_range(self):
        result = generate_stat_curve_editor_script()
        assert "_minLevel" in result
        assert "_maxLevel" in result

    def test_has_json_export(self):
        result = generate_stat_curve_editor_script()
        assert "ExportToJSON" in result
        assert "Export to JSON" in result

    def test_has_ongui(self):
        result = generate_stat_curve_editor_script()
        assert "OnGUI" in result

    def test_has_menu_item(self):
        result = generate_stat_curve_editor_script()
        assert "MenuItem" in result

    def test_has_preview(self):
        result = generate_stat_curve_editor_script()
        assert "Preview" in result or "Evaluate" in result


# ---------------------------------------------------------------------------
# GAME-11: Shop system
# ---------------------------------------------------------------------------


class TestShopSystem:
    """Tests for generate_shop_system_script()."""

    def test_returns_four_tuple(self):
        result = generate_shop_system_script()
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_merchant_data_contains_class(self):
        md, _, _, _ = generate_shop_system_script()
        assert "class VB_MerchantInventory" in md

    def test_merchant_data_has_create_asset_menu(self):
        md, _, _, _ = generate_shop_system_script()
        assert "CreateAssetMenu" in md

    def test_merchant_data_has_items(self):
        md, _, _, _ = generate_shop_system_script()
        assert "MerchantItem" in md
        assert "items" in md

    def test_merchant_data_has_price_override(self):
        md, _, _, _ = generate_shop_system_script()
        assert "priceOverride" in md

    def test_merchant_data_has_restock_timer(self):
        md, _, _, _ = generate_shop_system_script()
        assert "restockTimer" in md

    def test_shop_system_contains_class(self):
        _, ss, _, _ = generate_shop_system_script()
        assert "class VB_ShopSystem" in ss

    def test_shop_system_has_buy(self):
        _, ss, _, _ = generate_shop_system_script()
        assert "Buy(" in ss

    def test_shop_system_has_sell(self):
        _, ss, _, _ = generate_shop_system_script()
        assert "Sell(" in ss

    def test_shop_system_has_price_display(self):
        _, ss, _, _ = generate_shop_system_script()
        assert "GetBuyPrice" in ss
        assert "GetSellPrice" in ss

    def test_shop_system_has_currency_formatting(self):
        _, ss, _, _ = generate_shop_system_script()
        assert "FormatCurrency" in ss

    def test_shop_system_has_stat_comparison(self):
        _, ss, _, _ = generate_shop_system_script()
        assert "CompareStats" in ss
        assert "StatComparison" in ss

    def test_shop_system_has_event_bus(self):
        _, ss, _, _ = generate_shop_system_script()
        assert "EventBus" in ss

    def test_uxml_has_buy_sell(self):
        _, _, uxml, _ = generate_shop_system_script()
        assert "buy" in uxml.lower()
        assert "sell" in uxml.lower()

    def test_uxml_has_stat_comparison_panel(self):
        _, _, uxml, _ = generate_shop_system_script()
        assert "stat-comparison" in uxml or "comparison" in uxml

    def test_no_editor_namespace_merchant(self):
        md, _, _, _ = generate_shop_system_script()
        assert "using UnityEditor" not in md

    def test_no_editor_namespace_shop(self):
        _, ss, _, _ = generate_shop_system_script()
        assert "using UnityEditor" not in ss

    def test_shop_uxml_not_empty(self):
        _, _, uxml, _ = generate_shop_system_script()
        assert len(uxml) > 100

    def test_shop_uss_not_empty(self):
        _, _, _, uss = generate_shop_system_script()
        assert len(uss) > 100


# ---------------------------------------------------------------------------
# RPG-05: Journal system
# ---------------------------------------------------------------------------


class TestJournalSystem:
    """Tests for generate_journal_system_script()."""

    def test_returns_four_tuple(self):
        result = generate_journal_system_script()
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_journal_data_contains_class(self):
        data, _, _, _ = generate_journal_system_script()
        assert "class VB_JournalEntry" in data

    def test_journal_data_has_create_asset_menu(self):
        data, _, _, _ = generate_journal_system_script()
        assert "CreateAssetMenu" in data

    def test_journal_entry_types(self):
        data, _, _, _ = generate_journal_system_script()
        assert "Lore" in data
        assert "Bestiary" in data
        assert "Items" in data

    def test_journal_data_has_discovery_condition(self):
        data, _, _, _ = generate_journal_system_script()
        assert "discoveryCondition" in data

    def test_journal_data_has_bestiary_stats(self):
        data, _, _, _ = generate_journal_system_script()
        assert "BestiaryStats" in data
        assert "weaknesses" in data

    def test_journal_data_has_hidden_flag(self):
        data, _, _, _ = generate_journal_system_script()
        assert "isHidden" in data

    def test_journal_system_contains_class(self):
        _, sys, _, _ = generate_journal_system_script()
        assert "class VB_JournalSystem" in sys

    def test_journal_system_has_discover_entry(self):
        _, sys, _, _ = generate_journal_system_script()
        assert "DiscoverEntry" in sys

    def test_journal_system_has_get_entries(self):
        _, sys, _, _ = generate_journal_system_script()
        assert "GetEntries" in sys

    def test_journal_system_has_progressive_unlock(self):
        _, sys, _, _ = generate_journal_system_script()
        assert "_discoveredEntries" in sys

    def test_journal_system_has_event_bus(self):
        _, sys, _, _ = generate_journal_system_script()
        assert "EventBus" in sys

    def test_journal_system_has_discovery_event(self):
        _, sys, _, _ = generate_journal_system_script()
        assert "OnJournalEntryDiscovered" in sys or "OnEntryDiscovered" in sys

    def test_uxml_has_tabs(self):
        _, _, uxml, _ = generate_journal_system_script()
        assert "Lore" in uxml
        assert "Bestiary" in uxml
        assert "Items" in uxml

    def test_uxml_has_entry_detail(self):
        _, _, uxml, _ = generate_journal_system_script()
        assert "entry-detail" in uxml

    def test_no_editor_namespace_data(self):
        data, _, _, _ = generate_journal_system_script()
        assert "using UnityEditor" not in data

    def test_no_editor_namespace_system(self):
        _, sys, _, _ = generate_journal_system_script()
        assert "using UnityEditor" not in sys

    def test_journal_has_is_discovered(self):
        _, sys, _, _ = generate_journal_system_script()
        assert "IsDiscovered" in sys

    def test_journal_has_progress_tracker(self):
        _, sys, _, _ = generate_journal_system_script()
        assert "GetDiscoveryProgress" in sys


# ---------------------------------------------------------------------------
# VB-08: Brand loot affinity (cross-cutting)
# ---------------------------------------------------------------------------


class TestBrandLootAffinity:
    """Verify VB-08 brand affinity is properly delegated in loot table."""

    def test_brand_system_get_effectiveness_present(self):
        result = generate_loot_table_script()
        assert "BrandSystem.GetEffectiveness" in result

    def test_brand_enum_referenced(self):
        result = generate_loot_table_script()
        assert "Brand " in result  # Brand type reference

    def test_weight_adjustment_for_brand_match(self):
        result = generate_loot_table_script()
        # Brand match boosts weight by 1.5x
        assert "1.5f" in result

    def test_no_reimplementation_of_effectiveness(self):
        result = generate_loot_table_script()
        # Should NOT contain effectiveness matrix reimplementation
        assert "effectivenessMatrix" not in result.lower()
        assert "float[,]" not in result

    def test_corruption_affects_drop_rates(self):
        result = generate_loot_table_script()
        assert "corruptionLevel" in result
        assert "0.3f" in result

    def test_brand_affinity_field_on_entry(self):
        result = generate_loot_table_script()
        assert "brandAffinity" in result

    def test_uses_cumulative_distribution(self):
        result = generate_loot_table_script()
        assert "cumulative" in result

    def test_monster_brand_parameter(self):
        result = generate_loot_table_script()
        assert "monsterBrand" in result
