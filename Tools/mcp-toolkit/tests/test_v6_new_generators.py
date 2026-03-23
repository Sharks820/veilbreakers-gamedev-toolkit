"""Unit tests for v6 new generators added this session.

Tests cover:
- combat_feel_templates: hitstop, input buffer, combat camera, damage feedback,
  dodge roll, attack chain
- gameplay_templates: tactical AI coordinator, boss phase controller,
  player combat controller, motion warping, attack telegraph
- shader_templates: anisotropic hair, terrain blend, ice crystal
- vfx_mastery_templates: VFX pool, VFX LOD
- world_templates: WFC dungeon, interior streaming
- content_templates: legendary affix system, equipment variant matrix
- audio_middleware_templates: adaptive music system
"""

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def check_brace_balance(text: str) -> bool:
    """Check that curly braces are balanced in generated C# / shader code."""
    count = 0
    for ch in text:
        if ch == "{":
            count += 1
        elif ch == "}":
            count -= 1
        if count < 0:
            return False
    return count == 0


def assert_no_editor_import(script: str, label: str = "") -> None:
    """Assert that a runtime script does NOT contain 'using UnityEditor'."""
    assert "using UnityEditor" not in script, (
        f"Runtime script{' (' + label + ')' if label else ''} "
        "must not contain 'using UnityEditor'"
    )


# ===========================================================================
# combat_feel_templates
# ===========================================================================

from veilbreakers_mcp.shared.unity_templates.combat_feel_templates import (
    generate_hitstop_system_script,
    generate_input_buffer_script,
    generate_combat_camera_script,
    generate_damage_feedback_script,
    generate_dodge_roll_script,
    generate_attack_chain_script,
)


class TestHitstopSystem:
    """Tests for generate_hitstop_system_script."""

    def test_returns_string(self):
        result = generate_hitstop_system_script()
        assert isinstance(result, str)

    def test_contains_time_timescale(self):
        result = generate_hitstop_system_script()
        assert "Time.timeScale" in result

    def test_contains_class_name(self):
        result = generate_hitstop_system_script()
        assert "VB_HitStopSystem" in result

    def test_brace_balance(self):
        result = generate_hitstop_system_script()
        assert check_brace_balance(result)

    def test_no_editor_import(self):
        result = generate_hitstop_system_script()
        assert_no_editor_import(result, "HitStopSystem")


class TestInputBuffer:
    """Tests for generate_input_buffer_script."""

    def test_returns_string(self):
        result = generate_input_buffer_script()
        assert isinstance(result, str)

    def test_contains_buffer_input(self):
        result = generate_input_buffer_script()
        assert "BufferInput" in result

    def test_contains_consume_buffered_input(self):
        result = generate_input_buffer_script()
        assert "ConsumeBufferedInput" in result

    def test_brace_balance(self):
        result = generate_input_buffer_script()
        assert check_brace_balance(result)

    def test_no_editor_import(self):
        result = generate_input_buffer_script()
        assert_no_editor_import(result, "InputBuffer")


class TestCombatCamera:
    """Tests for generate_combat_camera_script."""

    def test_returns_string(self):
        result = generate_combat_camera_script()
        assert isinstance(result, str)

    def test_contains_class_name(self):
        result = generate_combat_camera_script()
        assert "VB_CombatCamera" in result

    def test_brace_balance(self):
        result = generate_combat_camera_script()
        assert check_brace_balance(result)

    def test_no_editor_import(self):
        result = generate_combat_camera_script()
        assert_no_editor_import(result, "CombatCamera")


class TestDamageFeedback:
    """Tests for generate_damage_feedback_script."""

    def test_returns_string(self):
        result = generate_damage_feedback_script()
        assert isinstance(result, str)

    def test_contains_damage_severity(self):
        result = generate_damage_feedback_script()
        assert "DamageSeverity" in result

    def test_brace_balance(self):
        result = generate_damage_feedback_script()
        assert check_brace_balance(result)

    def test_no_editor_import(self):
        result = generate_damage_feedback_script()
        assert_no_editor_import(result, "DamageFeedback")


class TestDodgeRoll:
    """Tests for generate_dodge_roll_script."""

    def test_returns_string(self):
        result = generate_dodge_roll_script()
        assert isinstance(result, str)

    def test_contains_dodge_state(self):
        result = generate_dodge_roll_script()
        assert "DodgeState" in result

    def test_contains_invincible(self):
        result = generate_dodge_roll_script()
        assert "Invincible" in result

    def test_brace_balance(self):
        result = generate_dodge_roll_script()
        assert check_brace_balance(result)

    def test_no_editor_import(self):
        result = generate_dodge_roll_script()
        assert_no_editor_import(result, "DodgeRoll")


class TestAttackChain:
    """Tests for generate_attack_chain_script."""

    def test_returns_string(self):
        result = generate_attack_chain_script()
        assert isinstance(result, str)

    def test_contains_combo_state(self):
        result = generate_attack_chain_script()
        assert "ComboState" in result

    def test_contains_attack_data(self):
        result = generate_attack_chain_script()
        assert "VB_AttackData" in result

    def test_brace_balance(self):
        result = generate_attack_chain_script()
        assert check_brace_balance(result)

    def test_no_editor_import(self):
        result = generate_attack_chain_script()
        assert_no_editor_import(result, "AttackChain")


# ===========================================================================
# gameplay_templates (new generators)
# ===========================================================================

from veilbreakers_mcp.shared.unity_templates.gameplay_templates import (
    generate_tactical_ai_coordinator_script,
    generate_boss_phase_controller_script,
    generate_player_combat_controller_script,
    generate_motion_warping_script,
    generate_attack_telegraph_script,
)


class TestTacticalAICoordinator:
    """Tests for generate_tactical_ai_coordinator_script."""

    def test_returns_string(self):
        result = generate_tactical_ai_coordinator_script("TestCoordinator")
        assert isinstance(result, str)

    def test_contains_attack_token(self):
        result = generate_tactical_ai_coordinator_script("TestCoordinator")
        assert "AttackToken" in result

    def test_contains_mob_role(self):
        result = generate_tactical_ai_coordinator_script("TestCoordinator")
        assert "MobRole" in result

    def test_brace_balance(self):
        result = generate_tactical_ai_coordinator_script("TestCoordinator")
        assert check_brace_balance(result)

    def test_no_editor_import(self):
        result = generate_tactical_ai_coordinator_script("TestCoordinator")
        assert_no_editor_import(result, "TacticalAICoordinator")


class TestBossPhaseController:
    """Tests for generate_boss_phase_controller_script."""

    def test_returns_string(self):
        result = generate_boss_phase_controller_script("TestBoss")
        assert isinstance(result, str)

    def test_contains_on_phase_change(self):
        result = generate_boss_phase_controller_script("TestBoss")
        assert "OnPhaseChange" in result

    def test_contains_vulnerability(self):
        result = generate_boss_phase_controller_script("TestBoss")
        assert "Vulnerability" in result

    def test_brace_balance(self):
        result = generate_boss_phase_controller_script("TestBoss")
        assert check_brace_balance(result)

    def test_no_editor_import(self):
        result = generate_boss_phase_controller_script("TestBoss")
        assert_no_editor_import(result, "BossPhaseController")


class TestPlayerCombatController:
    """Tests for generate_player_combat_controller_script."""

    def test_returns_string(self):
        result = generate_player_combat_controller_script()
        assert isinstance(result, str)

    def test_contains_stamina(self):
        result = generate_player_combat_controller_script()
        assert "Stamina" in result

    def test_contains_poise(self):
        result = generate_player_combat_controller_script()
        assert "Poise" in result

    def test_contains_parry(self):
        result = generate_player_combat_controller_script()
        assert "Parry" in result

    def test_brace_balance(self):
        result = generate_player_combat_controller_script()
        assert check_brace_balance(result)

    def test_no_editor_import(self):
        result = generate_player_combat_controller_script()
        assert_no_editor_import(result, "PlayerCombatController")


class TestMotionWarping:
    """Tests for generate_motion_warping_script."""

    def test_returns_string(self):
        result = generate_motion_warping_script("TestWarp")
        assert isinstance(result, str)

    def test_contains_motion_warping(self):
        result = generate_motion_warping_script("TestWarp")
        assert "MotionWarping" in result

    def test_contains_max_warp_distance(self):
        result = generate_motion_warping_script("TestWarp")
        assert "maxWarpDistance" in result

    def test_brace_balance(self):
        result = generate_motion_warping_script("TestWarp")
        assert check_brace_balance(result)

    def test_no_editor_import(self):
        result = generate_motion_warping_script("TestWarp")
        assert_no_editor_import(result, "MotionWarping")


class TestAttackTelegraph:
    """Tests for generate_attack_telegraph_script."""

    def test_returns_string(self):
        result = generate_attack_telegraph_script("TestTelegraph")
        assert isinstance(result, str)

    def test_contains_telegraph_type(self):
        result = generate_attack_telegraph_script("TestTelegraph")
        assert "TelegraphType" in result

    def test_contains_ground_circle(self):
        result = generate_attack_telegraph_script("TestTelegraph")
        assert "GroundCircle" in result

    def test_brace_balance(self):
        result = generate_attack_telegraph_script("TestTelegraph")
        assert check_brace_balance(result)

    def test_no_editor_import(self):
        result = generate_attack_telegraph_script("TestTelegraph")
        assert_no_editor_import(result, "AttackTelegraph")


# ===========================================================================
# shader_templates
# ===========================================================================

from veilbreakers_mcp.shared.unity_templates.shader_templates import (
    generate_anisotropic_hair_shader,
    generate_terrain_blend_shader,
    generate_ice_crystal_shader,
)


class TestAnisotropicHairShader:
    """Tests for generate_anisotropic_hair_shader."""

    def test_returns_string(self):
        result = generate_anisotropic_hair_shader()
        assert isinstance(result, str)

    def test_contains_kajiya_kay(self):
        result = generate_anisotropic_hair_shader()
        assert "KajiyaKay" in result

    def test_contains_flow_map(self):
        result = generate_anisotropic_hair_shader()
        assert "FlowMap" in result

    def test_brace_balance(self):
        result = generate_anisotropic_hair_shader()
        assert check_brace_balance(result)


class TestTerrainBlendShader:
    """Tests for generate_terrain_blend_shader."""

    def test_returns_string(self):
        result = generate_terrain_blend_shader()
        assert isinstance(result, str)

    def test_contains_height_blend(self):
        result = generate_terrain_blend_shader()
        assert "HeightBlend" in result

    def test_contains_splat_map(self):
        result = generate_terrain_blend_shader()
        assert "SplatMap" in result

    def test_brace_balance(self):
        result = generate_terrain_blend_shader()
        assert check_brace_balance(result)


class TestIceCrystalShader:
    """Tests for generate_ice_crystal_shader."""

    def test_returns_string(self):
        result = generate_ice_crystal_shader()
        assert isinstance(result, str)

    def test_contains_refraction(self):
        result = generate_ice_crystal_shader()
        assert "Refraction" in result

    def test_contains_sparkle(self):
        result = generate_ice_crystal_shader()
        assert "Sparkle" in result

    def test_brace_balance(self):
        result = generate_ice_crystal_shader()
        assert check_brace_balance(result)


# ===========================================================================
# vfx_mastery_templates
# ===========================================================================

from veilbreakers_mcp.shared.unity_templates.vfx_mastery_templates import (
    generate_vfx_pool_script,
    generate_vfx_lod_script,
)


class TestVFXPool:
    """Tests for generate_vfx_pool_script."""

    def test_returns_dict(self):
        result = generate_vfx_pool_script()
        assert isinstance(result, dict)

    def test_has_script_content(self):
        result = generate_vfx_pool_script()
        assert "script_content" in result

    def test_contains_pool_manager(self):
        result = generate_vfx_pool_script()
        assert "VFXPoolManager" in result["script_content"]

    def test_brace_balance(self):
        result = generate_vfx_pool_script()
        assert check_brace_balance(result["script_content"])

    def test_no_editor_import(self):
        result = generate_vfx_pool_script()
        assert_no_editor_import(result["script_content"], "VFXPool")


class TestVFXLOD:
    """Tests for generate_vfx_lod_script."""

    def test_returns_dict(self):
        result = generate_vfx_lod_script()
        assert isinstance(result, dict)

    def test_has_script_content(self):
        result = generate_vfx_lod_script()
        assert "script_content" in result

    def test_contains_lod_manager(self):
        result = generate_vfx_lod_script()
        assert "VFXLODManager" in result["script_content"]

    def test_brace_balance(self):
        result = generate_vfx_lod_script()
        assert check_brace_balance(result["script_content"])

    def test_no_editor_import(self):
        result = generate_vfx_lod_script()
        assert_no_editor_import(result["script_content"], "VFXLOD")


# ===========================================================================
# world_templates
# ===========================================================================

from veilbreakers_mcp.shared.unity_templates.world_templates import (
    generate_wfc_dungeon_script,
    generate_interior_streaming_script,
)


class TestWFCDungeon:
    """Tests for generate_wfc_dungeon_script."""

    def test_returns_dict(self):
        result = generate_wfc_dungeon_script()
        assert isinstance(result, dict)

    def test_has_script_content(self):
        result = generate_wfc_dungeon_script()
        assert "script_content" in result

    def test_contains_wfc(self):
        result = generate_wfc_dungeon_script()
        assert "WFC" in result["script_content"]

    def test_brace_balance(self):
        result = generate_wfc_dungeon_script()
        assert check_brace_balance(result["script_content"])


class TestInteriorStreaming:
    """Tests for generate_interior_streaming_script."""

    def test_returns_tuple_of_two(self):
        result = generate_interior_streaming_script()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_both_elements_are_strings(self):
        result = generate_interior_streaming_script()
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)

    def test_brace_balance_manager(self):
        manager_cs, _ = generate_interior_streaming_script()
        assert check_brace_balance(manager_cs)

    def test_brace_balance_trigger(self):
        _, trigger_cs = generate_interior_streaming_script()
        assert check_brace_balance(trigger_cs)

    def test_no_editor_import_manager(self):
        manager_cs, _ = generate_interior_streaming_script()
        assert_no_editor_import(manager_cs, "InteriorStreaming manager")

    def test_no_editor_import_trigger(self):
        _, trigger_cs = generate_interior_streaming_script()
        assert_no_editor_import(trigger_cs, "InteriorStreaming trigger")


# ===========================================================================
# content_templates
# ===========================================================================

from veilbreakers_mcp.shared.unity_templates.content_templates import (
    generate_legendary_affix_system_script,
    generate_equipment_variant_matrix_script,
)


class TestLegendaryAffixSystem:
    """Tests for generate_legendary_affix_system_script."""

    def test_returns_tuple_of_three(self):
        result = generate_legendary_affix_system_script()
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_all_elements_are_strings(self):
        result = generate_legendary_affix_system_script()
        for i, script in enumerate(result):
            assert isinstance(script, str), f"Element {i} is not a string"

    def test_brace_balance_all(self):
        result = generate_legendary_affix_system_script()
        for i, script in enumerate(result):
            assert check_brace_balance(script), (
                f"Unbalanced braces in legendary affix script element {i}"
            )

    def test_no_editor_import_all(self):
        result = generate_legendary_affix_system_script()
        for i, script in enumerate(result):
            assert_no_editor_import(script, f"LegendaryAffix element {i}")


class TestEquipmentVariantMatrix:
    """Tests for generate_equipment_variant_matrix_script."""

    def test_returns_dict(self):
        result = generate_equipment_variant_matrix_script()
        assert isinstance(result, dict)

    def test_has_script_content(self):
        result = generate_equipment_variant_matrix_script()
        assert "script_content" in result

    def test_brace_balance(self):
        result = generate_equipment_variant_matrix_script()
        assert check_brace_balance(result["script_content"])


# ===========================================================================
# audio_middleware_templates
# ===========================================================================

from veilbreakers_mcp.shared.unity_templates.audio_middleware_templates import (
    generate_adaptive_music_system_script,
)


class TestAdaptiveMusicSystem:
    """Tests for generate_adaptive_music_system_script."""

    def test_returns_tuple_of_two(self):
        result = generate_adaptive_music_system_script()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_both_elements_are_strings(self):
        result = generate_adaptive_music_system_script()
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)

    def test_brace_balance_both(self):
        result = generate_adaptive_music_system_script()
        for i, script in enumerate(result):
            assert check_brace_balance(script), (
                f"Unbalanced braces in adaptive music script element {i}"
            )

    def test_no_editor_import_both(self):
        result = generate_adaptive_music_system_script()
        for i, script in enumerate(result):
            assert_no_editor_import(script, f"AdaptiveMusic element {i}")
