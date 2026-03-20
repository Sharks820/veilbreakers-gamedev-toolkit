"""Unit tests for VeilBreakers combat system C# template generators.

Tests that each generator function produces valid C# source containing
the expected keywords, Unity API calls, parameter substitutions, and
correct delegation to existing VeilBreakers systems (SynergySystem,
CorruptionSystem, BrandSystem, DamageCalculator, EventBus).

All VB combat templates generate runtime MonoBehaviour or static utility
scripts -- they must NEVER contain 'using UnityEditor;'.
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.vb_combat_templates import (
    generate_player_combat_script,
    generate_ability_system_script,
    generate_synergy_engine_script,
    generate_corruption_gameplay_script,
    generate_xp_leveling_script,
    generate_currency_system_script,
    generate_damage_type_script,
)


# ---------------------------------------------------------------------------
# VB-01: Player combat controller
# ---------------------------------------------------------------------------


class TestPlayerCombatTemplate:
    """Tests for generate_player_combat_script()."""

    def test_contains_class_declaration(self):
        result = generate_player_combat_script()
        assert "class VB_PlayerCombat" in result

    def test_no_editor_namespace(self):
        result = generate_player_combat_script()
        assert "using UnityEditor" not in result

    def test_contains_fsm_states(self):
        result = generate_player_combat_script()
        assert "CombatState" in result
        assert "Idle" in result
        assert "LightAttack" in result
        assert "Dodge" in result

    def test_contains_combo_chain(self):
        result = generate_player_combat_script()
        lower = result.lower()
        assert "combo" in lower

    def test_contains_iframes(self):
        result = generate_player_combat_script()
        lower = result.lower()
        assert "iframe" in lower or "invincib" in lower or "iframeduration" in lower

    def test_contains_stamina(self):
        result = generate_player_combat_script()
        lower = result.lower()
        assert "stamina" in lower

    def test_contains_damage_calculator(self):
        result = generate_player_combat_script()
        assert "DamageCalculator" in result

    def test_contains_event_bus(self):
        result = generate_player_combat_script()
        assert "EventBus" in result

    def test_custom_combo_count(self):
        result = generate_player_combat_script(light_combo_count=5)
        assert "lightComboCount = 5" in result

    def test_contains_heavy_attack(self):
        result = generate_player_combat_script()
        assert "HeavyAttack" in result

    def test_contains_block_state(self):
        result = generate_player_combat_script()
        assert "Block" in result
        assert "blockDamageReduction" in result or "blockStaminaDrain" in result

    def test_contains_hit_reaction(self):
        result = generate_player_combat_script()
        assert "HitReaction" in result

    def test_contains_dead_state(self):
        result = generate_player_combat_script()
        assert "Dead" in result

    def test_contains_monobehaviour(self):
        result = generate_player_combat_script()
        assert "MonoBehaviour" in result

    def test_contains_animator(self):
        result = generate_player_combat_script()
        assert "Animator" in result

    def test_contains_virtual_input_methods(self):
        result = generate_player_combat_script()
        assert "virtual" in result
        assert "GetLightAttackInput" in result or "GetAttackInput" in result

    def test_custom_dodge_distance(self):
        result = generate_player_combat_script(dodge_distance=6.0)
        assert "6" in result

    def test_custom_stamina_max(self):
        result = generate_player_combat_script(stamina_max=150.0)
        assert "150" in result

    def test_contains_combatant_reference(self):
        result = generate_player_combat_script()
        assert "Combatant" in result
        assert "GetComponent<Combatant>" in result


# ---------------------------------------------------------------------------
# VB-02: Ability system
# ---------------------------------------------------------------------------


class TestAbilitySystemTemplate:
    """Tests for generate_ability_system_script()."""

    def test_contains_class_declaration(self):
        result = generate_ability_system_script()
        assert "class VB_AbilitySystem" in result

    def test_no_editor_namespace(self):
        result = generate_ability_system_script()
        assert "using UnityEditor" not in result

    def test_contains_ability_slots(self):
        result = generate_ability_system_script()
        assert "AbilitySlot" in result

    def test_contains_cooldown(self):
        result = generate_ability_system_script()
        lower = result.lower()
        assert "cooldown" in lower

    def test_contains_mana(self):
        result = generate_ability_system_script()
        lower = result.lower()
        assert "mana" in lower

    def test_contains_brand(self):
        result = generate_ability_system_script()
        assert "Brand" in result

    def test_contains_event_bus(self):
        result = generate_ability_system_script()
        assert "EventBus" in result

    def test_custom_max_slots(self):
        result = generate_ability_system_script(max_ability_slots=6)
        assert "6" in result

    def test_custom_mana_max(self):
        result = generate_ability_system_script(mana_max=200.0)
        assert "200" in result

    def test_contains_monobehaviour(self):
        result = generate_ability_system_script()
        assert "MonoBehaviour" in result

    def test_contains_try_activate(self):
        result = generate_ability_system_script()
        assert "TryActivateAbility" in result or "TryActivate" in result


# ---------------------------------------------------------------------------
# VB-03: Synergy engine
# ---------------------------------------------------------------------------


class TestSynergyEngineTemplate:
    """Tests for generate_synergy_engine_script()."""

    def test_contains_class_declaration(self):
        result = generate_synergy_engine_script()
        assert "class VB_SynergyEngine" in result

    def test_no_editor_namespace(self):
        result = generate_synergy_engine_script()
        assert "using UnityEditor" not in result

    def test_delegates_to_synergy_system(self):
        result = generate_synergy_engine_script()
        assert "SynergySystem.GetSynergyTier" in result

    def test_delegates_damage_bonus(self):
        result = generate_synergy_engine_script()
        assert "SynergySystem.GetDamageBonus" in result

    def test_does_not_reimplement(self):
        """Must NOT contain hardcoded tier multipliers alongside tier names.

        The multiplier values should come from SynergySystem, not be
        hardcoded in the generated code.
        """
        result = generate_synergy_engine_script()
        # Should NOT have lines like: if (tier == FULL) return 1.5f;
        # because the actual value comes from SynergySystem.GetDamageBonus()
        lines = result.split("\n")
        for line in lines:
            # Check for hardcoded return of specific synergy multiplier
            if "1.5f" in line and "FULL" in line and "return" in line:
                pytest.fail(
                    f"Found hardcoded synergy multiplier: {line.strip()}"
                )

    def test_contains_synergy_tier(self):
        result = generate_synergy_engine_script()
        assert "SynergyTier" in result

    def test_contains_event_bus(self):
        result = generate_synergy_engine_script()
        assert "EventBus" in result

    def test_contains_combo_meter(self):
        result = generate_synergy_engine_script()
        lower = result.lower()
        assert "combo" in lower

    def test_contains_visual_feedback_colors(self):
        result = generate_synergy_engine_script()
        # Should have color references for tier feedback
        assert "Color" in result

    def test_contains_monobehaviour(self):
        result = generate_synergy_engine_script()
        assert "MonoBehaviour" in result


# ---------------------------------------------------------------------------
# VB-04: Corruption gameplay
# ---------------------------------------------------------------------------


class TestCorruptionGameplayTemplate:
    """Tests for generate_corruption_gameplay_script()."""

    def test_contains_class_declaration(self):
        result = generate_corruption_gameplay_script()
        assert "class VB_CorruptionGameplay" in result

    def test_no_editor_namespace(self):
        result = generate_corruption_gameplay_script()
        assert "using UnityEditor" not in result

    def test_delegates_to_corruption_system(self):
        result = generate_corruption_gameplay_script()
        assert "CorruptionSystem.GetStatMultiplier" in result

    def test_delegates_corruption_state(self):
        result = generate_corruption_gameplay_script()
        assert "CorruptionSystem.GetCorruptionState" in result

    def test_contains_threshold_triggers(self):
        result = generate_corruption_gameplay_script()
        assert "25" in result or "threshold" in result.lower()

    def test_contains_corruption_state_enum(self):
        result = generate_corruption_gameplay_script()
        assert "CorruptionState" in result

    def test_contains_event_bus(self):
        result = generate_corruption_gameplay_script()
        assert "EventBus" in result

    def test_contains_visual_feedback(self):
        result = generate_corruption_gameplay_script()
        assert "_CorruptionLevel" in result

    def test_contains_npc_reaction(self):
        result = generate_corruption_gameplay_script()
        lower = result.lower()
        assert "npc" in lower

    def test_contains_ability_mutation(self):
        result = generate_corruption_gameplay_script()
        lower = result.lower()
        assert "mutated" in lower or "mutation" in lower or "abilit" in lower

    def test_custom_thresholds(self):
        result = generate_corruption_gameplay_script(thresholds=[10, 30, 60, 90])
        assert "10f" in result
        assert "30f" in result
        assert "60f" in result
        assert "90f" in result

    def test_contains_monobehaviour(self):
        result = generate_corruption_gameplay_script()
        assert "MonoBehaviour" in result


# ---------------------------------------------------------------------------
# VB-05: XP / leveling system
# ---------------------------------------------------------------------------


class TestXPLevelingTemplate:
    """Tests for generate_xp_leveling_script()."""

    def test_contains_class_declaration(self):
        result = generate_xp_leveling_script()
        assert "class VB_XPSystem" in result

    def test_no_editor_namespace(self):
        result = generate_xp_leveling_script()
        assert "using UnityEditor" not in result

    def test_contains_level_up(self):
        result = generate_xp_leveling_script()
        assert "LevelUp" in result

    def test_contains_xp_tracking(self):
        result = generate_xp_leveling_script()
        assert "XP" in result or "xp" in result or "experience" in result

    def test_contains_event_bus_levelup(self):
        result = generate_xp_leveling_script()
        assert "EventBus" in result
        assert "LevelUp" in result

    def test_custom_max_level(self):
        result = generate_xp_leveling_script(max_level=100)
        assert "100" in result

    def test_contains_hero_path(self):
        result = generate_xp_leveling_script()
        assert "Path" in result

    def test_contains_exponential_curve(self):
        result = generate_xp_leveling_script()
        assert "Pow" in result or "pow" in result or "scaling" in result.lower()

    def test_contains_stat_allocation(self):
        result = generate_xp_leveling_script()
        lower = result.lower()
        assert "stat" in lower
        assert "attack" in lower or "atk" in lower

    def test_contains_add_xp(self):
        result = generate_xp_leveling_script()
        assert "AddXP" in result

    def test_contains_monobehaviour(self):
        result = generate_xp_leveling_script()
        assert "MonoBehaviour" in result

    def test_custom_base_xp(self):
        result = generate_xp_leveling_script(base_xp_per_level=200)
        assert "200" in result


# ---------------------------------------------------------------------------
# VB-06: Currency system
# ---------------------------------------------------------------------------


class TestCurrencySystemTemplate:
    """Tests for generate_currency_system_script()."""

    def test_contains_class_declaration(self):
        result = generate_currency_system_script()
        assert "class VB_CurrencySystem" in result

    def test_no_editor_namespace(self):
        result = generate_currency_system_script()
        assert "using UnityEditor" not in result

    def test_contains_gold(self):
        result = generate_currency_system_script()
        assert "Gold" in result

    def test_contains_souls(self):
        result = generate_currency_system_script()
        assert "Souls" in result

    def test_contains_earn_spend(self):
        result = generate_currency_system_script()
        assert "Earn" in result or "earn" in result
        assert "Spend" in result or "spend" in result

    def test_contains_event_bus(self):
        result = generate_currency_system_script()
        assert "EventBus" in result

    def test_custom_currency_types(self):
        result = generate_currency_system_script(
            currency_types=["Gems", "Tokens", "Essence"]
        )
        assert "Gems" in result
        assert "Tokens" in result
        assert "Essence" in result

    def test_contains_singleton(self):
        result = generate_currency_system_script()
        assert "Instance" in result

    def test_contains_has_enough(self):
        result = generate_currency_system_script()
        assert "HasEnough" in result

    def test_contains_get_balance(self):
        result = generate_currency_system_script()
        assert "GetBalance" in result

    def test_contains_save_data(self):
        result = generate_currency_system_script()
        assert "CurrencyData" in result or "SaveData" in result or "save" in result.lower()

    def test_contains_format_helper(self):
        result = generate_currency_system_script()
        assert "Format" in result or "format" in result

    def test_contains_monobehaviour(self):
        result = generate_currency_system_script()
        assert "MonoBehaviour" in result


# ---------------------------------------------------------------------------
# VB-07: Damage type system
# ---------------------------------------------------------------------------


class TestDamageTypeTemplate:
    """Tests for generate_damage_type_script()."""

    def test_contains_class_declaration(self):
        result = generate_damage_type_script()
        assert "class VB_DamageTypeSystem" in result

    def test_no_editor_namespace(self):
        result = generate_damage_type_script()
        assert "using UnityEditor" not in result

    def test_delegates_to_brand_system(self):
        result = generate_damage_type_script()
        assert "BrandSystem.GetEffectiveness" in result

    def test_contains_damage_types(self):
        result = generate_damage_type_script()
        assert "Physical" in result
        assert "Magical" in result

    def test_contains_brand_damage_types(self):
        result = generate_damage_type_script()
        assert "Iron" in result

    def test_contains_apply_resistance(self):
        result = generate_damage_type_script()
        assert "ApplyResistance" in result

    def test_contains_true_damage(self):
        result = generate_damage_type_script()
        lower = result.lower()
        assert "true" in lower
        assert "bypass" in lower or "ignores" in lower

    def test_contains_brand_to_damage_type(self):
        result = generate_damage_type_script()
        assert "DamageTypeToBrand" in result or "BrandToDamageType" in result

    def test_contains_effectiveness_tooltip(self):
        result = generate_damage_type_script()
        assert "Tooltip" in result or "tooltip" in result or "Effectiveness" in result

    def test_does_not_contain_effectiveness_matrix(self):
        """Must NOT contain a hardcoded effectiveness matrix.

        Should delegate to BrandSystem.GetEffectiveness() instead.
        """
        result = generate_damage_type_script()
        # Should not have hardcoded 2.0f or 0.5f effectiveness values
        # in assignment/return contexts (but BrandSystem.SUPER_EFFECTIVE refs are OK)
        lines = result.split("\n")
        for line in lines:
            stripped = line.strip()
            if ("2.0f" in stripped and "return" in stripped
                    and "BrandSystem" not in stripped):
                pytest.fail(
                    f"Found hardcoded effectiveness value: {stripped}"
                )
