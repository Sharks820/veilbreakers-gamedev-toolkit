"""Unit tests for encounter and AI system C# template generators.

Tests that each generator function produces valid C# source containing
the expected keywords, Unity API calls, parameter substitutions, and
correct structure for encounter scripting, AI direction, simulation,
and boss AI behavior.

Runtime generators must NEVER contain 'using UnityEditor;'.
Editor generators (encounter simulator) MUST contain it.
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.encounter_templates import (
    generate_encounter_system_script,
    generate_ai_director_script,
    generate_encounter_simulator_script,
    generate_boss_ai_script,
)


# ---------------------------------------------------------------------------
# AID-01: Encounter Scripting
# ---------------------------------------------------------------------------


class TestEncounterScripting:
    """Tests for generate_encounter_system_script() -- AID-01."""

    def test_encounter_returns_2_tuple(self):
        result = generate_encounter_system_script()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_encounter_wave_so(self):
        so, _ = generate_encounter_system_script()
        assert "ScriptableObject" in so
        assert "CreateAssetMenu" in so

    def test_encounter_wave_so_menu_path(self):
        so, _ = generate_encounter_system_script()
        assert "VeilBreakers/Encounter/Wave Definition" in so

    def test_encounter_spawn_entry(self):
        so, _ = generate_encounter_system_script()
        assert "SpawnEntry" in so
        assert "prefabName" in so
        assert "count" in so

    def test_encounter_spawn_entry_serializable(self):
        so, _ = generate_encounter_system_script()
        assert "[Serializable]" in so

    def test_encounter_spawn_entry_difficulty_multiplier(self):
        so, _ = generate_encounter_system_script()
        assert "difficultyMultiplier" in so

    def test_encounter_victory_conditions(self):
        so, _ = generate_encounter_system_script()
        assert "victoryConditions" in so
        assert "all_dead" in so

    def test_encounter_defeat_condition(self):
        so, _ = generate_encounter_system_script()
        assert "defeatCondition" in so
        assert "player_death" in so

    def test_encounter_time_limit(self):
        so, _ = generate_encounter_system_script()
        assert "timeLimit" in so

    def test_encounter_trigger_volume(self):
        _, mgr = generate_encounter_system_script()
        assert "OnTriggerEnter" in mgr

    def test_encounter_player_tag_check(self):
        _, mgr = generate_encounter_system_script()
        assert "Player" in mgr

    def test_encounter_coroutine_spawning(self):
        _, mgr = generate_encounter_system_script()
        assert "StartCoroutine" in mgr
        assert "RunEncounter" in mgr

    def test_encounter_events(self):
        _, mgr = generate_encounter_system_script()
        assert "OnEncounterStarted" in mgr
        assert "OnWaveComplete" in mgr
        assert "OnEncounterVictory" in mgr
        assert "OnEncounterDefeat" in mgr

    def test_encounter_wave_started_event(self):
        _, mgr = generate_encounter_system_script()
        assert "OnWaveStarted" in mgr

    def test_encounter_fog_gates(self):
        _, mgr = generate_encounter_system_script()
        assert "_fogGates" in mgr

    def test_encounter_difficulty_modifier(self):
        _, mgr = generate_encounter_system_script()
        assert "SetDifficultyModifier" in mgr

    def test_encounter_reset(self):
        _, mgr = generate_encounter_system_script()
        assert "ResetEncounter" in mgr

    def test_encounter_force_end(self):
        _, mgr = generate_encounter_system_script()
        assert "ForceEndEncounter" in mgr

    def test_encounter_spawned_defeated_tracking(self):
        _, mgr = generate_encounter_system_script()
        assert "_spawnedCount" in mgr
        assert "_defeatedCount" in mgr

    def test_encounter_custom_name(self):
        _, mgr = generate_encounter_system_script(name="DragonLair")
        assert "VB_EncounterManager_DragonLair" in mgr

    def test_encounter_namespace(self):
        so, mgr = generate_encounter_system_script(namespace="VeilBreakers.Encounters")
        assert "namespace VeilBreakers.Encounters" in so
        assert "namespace VeilBreakers.Encounters" in mgr

    def test_encounter_no_editor_namespace(self):
        _, mgr = generate_encounter_system_script()
        assert "using UnityEditor;" not in mgr

    def test_encounter_wave_delay(self):
        so, _ = generate_encounter_system_script()
        assert "waveDelay" in so

    def test_encounter_unity_event_import(self):
        _, mgr = generate_encounter_system_script()
        assert "using UnityEngine.Events;" in mgr


# ---------------------------------------------------------------------------
# AID-02: AI Director
# ---------------------------------------------------------------------------


class TestAIDirector:
    """Tests for generate_ai_director_script() -- AID-02."""

    def test_ai_director_difficulty_score(self):
        output = generate_ai_director_script()
        assert "_difficultyScore" in output

    def test_ai_director_animation_curves(self):
        output = generate_ai_director_script()
        assert "AnimationCurve" in output

    def test_ai_director_spawn_rate_curve(self):
        output = generate_ai_director_script()
        assert "_spawnRateCurve" in output

    def test_ai_director_enemy_stat_curve(self):
        output = generate_ai_director_script()
        assert "_enemyStatCurve" in output

    def test_ai_director_spawn_rate(self):
        output = generate_ai_director_script()
        assert "GetSpawnRateMultiplier" in output

    def test_ai_director_stat_multiplier(self):
        output = generate_ai_director_script()
        assert "GetStatMultiplier" in output

    def test_ai_director_evaluate_curve(self):
        output = generate_ai_director_script()
        assert ".Evaluate(" in output

    def test_ai_director_record_result(self):
        output = generate_ai_director_script()
        assert "RecordEncounterResult" in output

    def test_ai_director_death_tracking(self):
        output = generate_ai_director_script()
        assert "_recentDeaths" in output

    def test_ai_director_clear_time(self):
        output = generate_ai_director_script()
        assert "_averageClearTime" in output

    def test_ai_director_damage_ratio(self):
        output = generate_ai_director_script()
        assert "_damageTakenRatio" in output

    def test_ai_director_adjustment_speed(self):
        output = generate_ai_director_script()
        assert "_adjustmentSpeed" in output

    def test_ai_director_sliding_window(self):
        output = generate_ai_director_script()
        assert "_clearTimes" in output
        assert "_windowSize" in output

    def test_ai_director_update_difficulty(self):
        output = generate_ai_director_script()
        assert "UpdateDifficulty" in output

    def test_ai_director_lerp(self):
        output = generate_ai_director_script()
        assert "Mathf.Lerp" in output

    def test_ai_director_difficulty_property(self):
        output = generate_ai_director_script()
        assert "DifficultyScore" in output

    def test_ai_director_custom_name(self):
        output = generate_ai_director_script(name="CombatDirector")
        assert "VB_AIDirector_CombatDirector" in output

    def test_ai_director_namespace(self):
        output = generate_ai_director_script(namespace="VeilBreakers.AI")
        assert "namespace VeilBreakers.AI" in output

    def test_ai_director_no_editor_namespace(self):
        output = generate_ai_director_script()
        assert "using UnityEditor;" not in output

    def test_ai_director_target_difficulty(self):
        output = generate_ai_director_script()
        assert "_targetDifficulty" in output

    def test_ai_director_encounter_integration(self):
        output = generate_ai_director_script()
        assert "SetDifficultyModifier" in output


# ---------------------------------------------------------------------------
# AID-03: Encounter Simulator
# ---------------------------------------------------------------------------


class TestEncounterSimulator:
    """Tests for generate_encounter_simulator_script() -- AID-03."""

    def test_simulator_editor_window(self):
        output = generate_encounter_simulator_script()
        assert "EditorWindow" in output

    def test_simulator_menu_item(self):
        output = generate_encounter_simulator_script()
        assert "MenuItem" in output

    def test_simulator_menu_path(self):
        output = generate_encounter_simulator_script()
        assert "VeilBreakers/Tools/Encounter Simulator" in output

    def test_simulator_simulation_count(self):
        output = generate_encounter_simulator_script()
        assert "_simulationCount" in output

    def test_simulator_win_rate(self):
        output = generate_encounter_simulator_script()
        assert "_winRate" in output

    def test_simulator_uses_editor_namespace(self):
        output = generate_encounter_simulator_script()
        assert "UnityEditor" in output

    def test_simulator_imgui(self):
        output = generate_encounter_simulator_script()
        assert "OnGUI" in output

    def test_simulator_player_dps(self):
        output = generate_encounter_simulator_script()
        assert "_playerDPS" in output

    def test_simulator_player_hp(self):
        output = generate_encounter_simulator_script()
        assert "_playerHP" in output

    def test_simulator_dodge_chance(self):
        output = generate_encounter_simulator_script()
        assert "_playerDodgeChance" in output

    def test_simulator_difficulty_recommendation_too_easy(self):
        output = generate_encounter_simulator_script()
        assert "Too Easy" in output

    def test_simulator_difficulty_recommendation_balanced(self):
        output = generate_encounter_simulator_script()
        assert "Balanced" in output

    def test_simulator_difficulty_recommendation_too_hard(self):
        output = generate_encounter_simulator_script()
        assert "Too Hard" in output

    def test_simulator_wave_config(self):
        output = generate_encounter_simulator_script()
        assert "_waveCount" in output
        assert "_enemiesPerWave" in output

    def test_simulator_monte_carlo_batched(self):
        output = generate_encounter_simulator_script()
        assert "EditorApplication.update" in output
        assert "_batchSize" in output

    def test_simulator_avg_clear_time(self):
        output = generate_encounter_simulator_script()
        assert "_avgClearTime" in output

    def test_simulator_std_dev(self):
        output = generate_encounter_simulator_script()
        assert "_stdDevClearTime" in output

    def test_simulator_export_json(self):
        output = generate_encounter_simulator_script()
        assert "ExportResults" in output
        assert "json" in output.lower()

    def test_simulator_difficulty_score_slider(self):
        output = generate_encounter_simulator_script()
        assert "_difficultyScore" in output

    def test_simulator_unity_editor_guard(self):
        output = generate_encounter_simulator_script()
        assert "#if UNITY_EDITOR" in output
        assert "#endif" in output

    def test_simulator_custom_name(self):
        output = generate_encounter_simulator_script(name="BalanceTester")
        assert "VB_BalanceTester" in output

    def test_simulator_namespace(self):
        output = generate_encounter_simulator_script(namespace="VeilBreakers.Tools")
        assert "namespace VeilBreakers.Tools" in output

    def test_simulator_progress_bar(self):
        output = generate_encounter_simulator_script()
        assert "ProgressBar" in output


# ---------------------------------------------------------------------------
# VB-10: Boss AI
# ---------------------------------------------------------------------------


class TestBossAI:
    """Tests for generate_boss_ai_script() -- VB-10."""

    def test_boss_phase_enum(self):
        output = generate_boss_ai_script()
        assert "BossPhase" in output
        assert "Phase1" in output
        assert "Enrage" in output

    def test_boss_hp_thresholds(self):
        output = generate_boss_ai_script()
        assert "_phase2Threshold" in output
        assert "_phase3Threshold" in output

    def test_boss_enrage_timer(self):
        output = generate_boss_ai_script()
        assert "_enrageTimer" in output

    def test_boss_enrage_value(self):
        output = generate_boss_ai_script()
        assert "180f" in output

    def test_boss_pending_transition(self):
        output = generate_boss_ai_script()
        assert "_pendingTransition" in output

    def test_boss_phase_transition(self):
        output = generate_boss_ai_script()
        assert "CheckPhaseTransition" in output

    def test_boss_execute_phase_transition(self):
        output = generate_boss_ai_script()
        assert "ExecutePhaseTransition" in output

    def test_boss_attack_patterns(self):
        output = generate_boss_ai_script()
        assert "AttackPattern" in output

    def test_boss_attack_pattern_fields(self):
        output = generate_boss_ai_script()
        assert "damage" in output
        assert "range" in output
        assert "cooldown" in output
        assert "animTrigger" in output

    def test_boss_state_machine(self):
        output = generate_boss_ai_script()
        assert "BossState" in output
        assert "Idle" in output
        assert "Attacking" in output
        assert "PhaseTransition" in output
        assert "Stunned" in output
        assert "Dead" in output

    def test_boss_events(self):
        output = generate_boss_ai_script()
        assert "OnPhaseChanged" in output
        assert "OnBossDeath" in output

    def test_boss_enrage_event(self):
        output = generate_boss_ai_script()
        assert "OnEnrage" in output

    def test_boss_enrage_effects(self):
        output = generate_boss_ai_script()
        # Enrage reduces cooldowns and increases damage
        assert "cooldown * 0.5f" in output
        assert "damage *= 1.5f" in output

    def test_boss_phase_speed_multiplier(self):
        output = generate_boss_ai_script()
        assert "_phaseSpeedMultiplier" in output

    def test_boss_phase_damage_multiplier(self):
        output = generate_boss_ai_script()
        assert "_phaseDamageMultiplier" in output

    def test_boss_custom_phase_count(self):
        output = generate_boss_ai_script(phase_count=4)
        assert "Phase4" in output

    def test_boss_custom_phase_count_thresholds(self):
        output = generate_boss_ai_script(phase_count=4)
        assert "_phase4Threshold" in output

    def test_boss_default_3_phases(self):
        output = generate_boss_ai_script()
        assert "Phase1" in output
        assert "Phase2" in output
        assert "Phase3" in output

    def test_boss_damage_calculator(self):
        output = generate_boss_ai_script()
        assert "DamageCalculator" in output

    def test_boss_fog_gates(self):
        output = generate_boss_ai_script()
        assert "_fogGates" in output

    def test_boss_health_bar_ui(self):
        output = generate_boss_ai_script()
        assert "_healthBarUI" in output

    def test_boss_custom_name(self):
        output = generate_boss_ai_script(name="DragonLord")
        assert "VB_BossAI_DragonLord" in output

    def test_boss_namespace(self):
        output = generate_boss_ai_script(namespace="VeilBreakers.Bosses")
        assert "namespace VeilBreakers.Bosses" in output

    def test_boss_no_editor_namespace(self):
        output = generate_boss_ai_script()
        assert "using UnityEditor;" not in output

    def test_boss_stun_mechanic(self):
        output = generate_boss_ai_script()
        assert "Stun" in output

    def test_boss_take_damage(self):
        output = generate_boss_ai_script()
        assert "TakeDamage" in output

    def test_boss_hp_ratio_property(self):
        output = generate_boss_ai_script()
        assert "HPRatio" in output

    def test_boss_phase_attack_sets(self):
        output = generate_boss_ai_script()
        assert "PhaseAttackSet" in output
        assert "_phaseAttackSets" in output

    def test_boss_min_phase_count_clamped(self):
        # phase_count=1 should clamp to 2
        output = generate_boss_ai_script(phase_count=1)
        assert "Phase2" in output

    def test_boss_max_phase_count_clamped(self):
        # phase_count=10 should clamp to 5
        output = generate_boss_ai_script(phase_count=10)
        assert "Phase5" in output
        assert "Phase6" not in output
