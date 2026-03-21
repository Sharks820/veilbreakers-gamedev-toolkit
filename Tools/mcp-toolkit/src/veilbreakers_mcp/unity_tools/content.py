"""unity_content tool handler."""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, _read_unity_result, _handle_dict_template, STANDARD_NEXT_STEPS,
)

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
from veilbreakers_mcp.shared.unity_templates.equipment_templates import (
    generate_equipment_attachment_script,
)




# ===========================================================================
# Compound tool: unity_content (Content & Progression Systems -- Phase 13)
# ===========================================================================


@mcp.tool()
async def unity_content(
    action: Literal[
        # Content Systems (content_templates.py)
        "create_inventory_system",      # GAME-02
        "create_dialogue_system",       # GAME-03
        "create_quest_system",          # GAME-04
        "create_loot_table",            # GAME-09
        "create_crafting_system",       # GAME-10
        "create_skill_tree",            # GAME-11
        "create_dps_calculator",        # GAME-12
        "create_encounter_simulator",   # GAME-12
        "create_stat_curve_editor",     # GAME-12
        "create_shop_system",           # RPG-01
        "create_journal_system",        # RPG-05
        # Equipment (equipment_templates.py)
        "create_equipment_attachment",  # EQUIP-06
    ],
    name: str = "default",
    # Inventory params (GAME-02)
    grid_width: int = 8,
    grid_height: int = 5,
    equipment_slots: list[str] | None = None,
    # Skill tree params (GAME-11)
    hero_paths: list[str] | None = None,
    # DPS calculator params (GAME-12)
    brands: list[str] | None = None,
    # Namespace (shared)
    namespace: str = ""
) -> str:
    """Content and progression systems -- inventory, dialogue, quests, loot, crafting, skill tree, balancing tools, shop, journal, and equipment attachment."""
    try:
        ns_kwargs: dict = {}
        if namespace:
            ns_kwargs["namespace"] = namespace

        if action == "create_inventory_system":
            return await _handle_content_inventory(
                grid_width, grid_height, equipment_slots, ns_kwargs,
            )
        elif action == "create_dialogue_system":
            return await _handle_content_dialogue(ns_kwargs)
        elif action == "create_quest_system":
            return await _handle_content_quest(ns_kwargs)
        elif action == "create_loot_table":
            return await _handle_content_loot_table(ns_kwargs)
        elif action == "create_crafting_system":
            return await _handle_content_crafting(ns_kwargs)
        elif action == "create_skill_tree":
            return await _handle_content_skill_tree(hero_paths, ns_kwargs)
        elif action == "create_dps_calculator":
            return await _handle_content_dps_calculator(brands, ns_kwargs)
        elif action == "create_encounter_simulator":
            return await _handle_content_encounter_simulator(ns_kwargs)
        elif action == "create_stat_curve_editor":
            return await _handle_content_stat_curve_editor(ns_kwargs)
        elif action == "create_shop_system":
            return await _handle_content_shop(ns_kwargs)
        elif action == "create_journal_system":
            return await _handle_content_journal(ns_kwargs)
        elif action == "create_equipment_attachment":
            return await _handle_content_equipment_attachment(ns_kwargs)
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})

    except Exception as exc:
        logger.exception("unity_content action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# Content action handlers
# ---------------------------------------------------------------------------


async def _handle_content_inventory(
    grid_width: int, grid_height: int,
    equipment_slots: list[str] | None, ns_kwargs: dict,
) -> str:
    """Create inventory system (GAME-02)."""
    item_so, inventory_cs, uxml, uss = generate_inventory_system_script(
        grid_width=grid_width,
        grid_height=grid_height,
        equipment_slots=equipment_slots,
        **ns_kwargs,
    )
    base = "Assets/Scripts/Runtime/ContentSystems/Inventory"
    paths = []
    paths.append(_write_to_unity(item_so, f"{base}/VB_ItemData.cs"))
    paths.append(_write_to_unity(inventory_cs, f"{base}/VB_InventorySystem.cs"))
    paths.append(_write_to_unity(uxml, "Assets/UI/Inventory.uxml"))
    paths.append(_write_to_unity(uss, "Assets/UI/Inventory.uss"))
    return json.dumps({
        "status": "success",
        "action": "create_inventory_system",
        "paths": paths,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_content_dialogue(ns_kwargs: dict) -> str:
    """Create dialogue system (GAME-03)."""
    data_cs, system_cs, uxml, uss = generate_dialogue_system_script(**ns_kwargs)
    base = "Assets/Scripts/Runtime/ContentSystems/Dialogue"
    paths = []
    paths.append(_write_to_unity(data_cs, f"{base}/VB_DialogueData.cs"))
    paths.append(_write_to_unity(system_cs, f"{base}/VB_DialogueSystem.cs"))
    paths.append(_write_to_unity(uxml, "Assets/UI/Dialogue.uxml"))
    paths.append(_write_to_unity(uss, "Assets/UI/Dialogue.uss"))
    return json.dumps({
        "status": "success",
        "action": "create_dialogue_system",
        "paths": paths,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_content_quest(ns_kwargs: dict) -> str:
    """Create quest system (GAME-04)."""
    data_cs, system_cs, uxml, uss = generate_quest_system_script(**ns_kwargs)
    base = "Assets/Scripts/Runtime/ContentSystems/Quests"
    paths = []
    paths.append(_write_to_unity(data_cs, f"{base}/VB_QuestData.cs"))
    paths.append(_write_to_unity(system_cs, f"{base}/VB_QuestSystem.cs"))
    paths.append(_write_to_unity(uxml, "Assets/UI/QuestLog.uxml"))
    paths.append(_write_to_unity(uss, "Assets/UI/QuestLog.uss"))
    return json.dumps({
        "status": "success",
        "action": "create_quest_system",
        "paths": paths,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_content_loot_table(ns_kwargs: dict) -> str:
    """Create loot table system (GAME-09)."""
    script = generate_loot_table_script(**ns_kwargs)
    rel_path = "Assets/Scripts/Runtime/ContentSystems/Loot/VB_LootTable.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_loot_table",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_content_crafting(ns_kwargs: dict) -> str:
    """Create crafting system (GAME-10)."""
    recipe_cs, crafting_cs = generate_crafting_system_script(**ns_kwargs)
    base = "Assets/Scripts/Runtime/ContentSystems/Crafting"
    paths = []
    paths.append(_write_to_unity(recipe_cs, f"{base}/VB_CraftingRecipe.cs"))
    paths.append(_write_to_unity(crafting_cs, f"{base}/VB_CraftingSystem.cs"))
    return json.dumps({
        "status": "success",
        "action": "create_crafting_system",
        "paths": paths,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_content_skill_tree(
    hero_paths: list[str] | None, ns_kwargs: dict,
) -> str:
    """Create skill tree system (GAME-11)."""
    node_cs, tree_cs = generate_skill_tree_script(
        hero_paths=hero_paths,
        **ns_kwargs,
    )
    base = "Assets/Scripts/Runtime/ContentSystems/SkillTree"
    paths = []
    paths.append(_write_to_unity(node_cs, f"{base}/VB_SkillNode.cs"))
    paths.append(_write_to_unity(tree_cs, f"{base}/VB_SkillTree.cs"))
    return json.dumps({
        "status": "success",
        "action": "create_skill_tree",
        "paths": paths,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_content_dps_calculator(
    brands: list[str] | None, ns_kwargs: dict,
) -> str:
    """Create DPS calculator editor tool (GAME-12)."""
    script = generate_dps_calculator_script(brands=brands, **ns_kwargs)
    rel_path = "Assets/Scripts/Editor/BalancingTools/VB_DPSCalculator.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_dps_calculator",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_content_encounter_simulator(ns_kwargs: dict) -> str:
    """Create encounter simulator editor tool (GAME-12)."""
    script = generate_encounter_simulator_script(**ns_kwargs)
    rel_path = "Assets/Scripts/Editor/BalancingTools/VB_EncounterSimulator.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_encounter_simulator",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_content_stat_curve_editor(ns_kwargs: dict) -> str:
    """Create stat curve editor tool (GAME-12)."""
    script = generate_stat_curve_editor_script(**ns_kwargs)
    rel_path = "Assets/Scripts/Editor/BalancingTools/VB_StatCurveEditor.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_stat_curve_editor",
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_content_shop(ns_kwargs: dict) -> str:
    """Create shop/merchant system (RPG-01)."""
    merchant_cs, shop_cs, uxml, uss = generate_shop_system_script(**ns_kwargs)
    base = "Assets/Scripts/Runtime/ContentSystems/Shop"
    paths = []
    paths.append(_write_to_unity(merchant_cs, f"{base}/VB_MerchantData.cs"))
    paths.append(_write_to_unity(shop_cs, f"{base}/VB_ShopSystem.cs"))
    paths.append(_write_to_unity(uxml, "Assets/UI/Shop.uxml"))
    paths.append(_write_to_unity(uss, "Assets/UI/Shop.uss"))
    return json.dumps({
        "status": "success",
        "action": "create_shop_system",
        "paths": paths,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_content_journal(ns_kwargs: dict) -> str:
    """Create journal/codex system (RPG-05)."""
    data_cs, system_cs, uxml, uss = generate_journal_system_script(**ns_kwargs)
    base = "Assets/Scripts/Runtime/ContentSystems/Journal"
    paths = []
    paths.append(_write_to_unity(data_cs, f"{base}/VB_JournalData.cs"))
    paths.append(_write_to_unity(system_cs, f"{base}/VB_JournalSystem.cs"))
    paths.append(_write_to_unity(uxml, "Assets/UI/Journal.uxml"))
    paths.append(_write_to_unity(uss, "Assets/UI/Journal.uss"))
    return json.dumps({
        "status": "success",
        "action": "create_journal_system",
        "paths": paths,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)


async def _handle_content_equipment_attachment(ns_kwargs: dict) -> str:
    """Create equipment attachment system (EQUIP-06)."""
    attachment_cs, weapon_sheath_cs = generate_equipment_attachment_script(**ns_kwargs)
    base = "Assets/Scripts/Runtime/ContentSystems/Equipment"
    paths = []
    paths.append(_write_to_unity(attachment_cs, f"{base}/VB_EquipmentAttachment.cs"))
    paths.append(_write_to_unity(weapon_sheath_cs, f"{base}/VB_WeaponSheath.cs"))
    return json.dumps({
        "status": "success",
        "action": "create_equipment_attachment",
        "paths": paths,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)
