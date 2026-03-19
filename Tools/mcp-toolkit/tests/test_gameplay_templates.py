"""Unit tests for Unity gameplay C# template generators.

Tests that each generator function produces valid C# source containing
the expected keywords, Unity API calls, and parameter substitutions.
All gameplay templates generate runtime MonoBehaviour or ScriptableObject
scripts -- they must NEVER contain 'using UnityEditor;'.
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.gameplay_templates import (
    generate_mob_controller_script,
    generate_aggro_system_script,
    generate_patrol_route_script,
    generate_spawn_system_script,
    generate_behavior_tree_script,
    generate_combat_ability_script,
    generate_projectile_script,
    _validate_mob_params,
    _validate_spawn_params,
    _validate_ability_params,
    _validate_projectile_params,
)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


class TestValidateMobParams:
    """Tests for _validate_mob_params()."""

    def test_valid_params_return_none(self):
        result = _validate_mob_params(
            detection_range=15.0,
            attack_range=3.0,
            leash_distance=30.0,
            patrol_speed=2.0,
            chase_speed=5.0,
            flee_health_pct=0.2,
        )
        assert result is None

    def test_detection_range_less_than_attack_range(self):
        result = _validate_mob_params(
            detection_range=2.0,
            attack_range=5.0,
            leash_distance=30.0,
            patrol_speed=2.0,
            chase_speed=5.0,
            flee_health_pct=0.2,
        )
        assert result is not None
        assert isinstance(result, str)

    def test_detection_range_equal_to_attack_range(self):
        result = _validate_mob_params(
            detection_range=5.0,
            attack_range=5.0,
            leash_distance=30.0,
            patrol_speed=2.0,
            chase_speed=5.0,
            flee_health_pct=0.2,
        )
        assert result is not None

    def test_negative_speed(self):
        result = _validate_mob_params(
            detection_range=15.0,
            attack_range=3.0,
            leash_distance=30.0,
            patrol_speed=-1.0,
            chase_speed=5.0,
            flee_health_pct=0.2,
        )
        assert result is not None

    def test_zero_speed(self):
        result = _validate_mob_params(
            detection_range=15.0,
            attack_range=3.0,
            leash_distance=30.0,
            patrol_speed=0.0,
            chase_speed=5.0,
            flee_health_pct=0.2,
        )
        assert result is not None

    def test_negative_detection_range(self):
        result = _validate_mob_params(
            detection_range=-5.0,
            attack_range=3.0,
            leash_distance=30.0,
            patrol_speed=2.0,
            chase_speed=5.0,
            flee_health_pct=0.2,
        )
        assert result is not None

    def test_zero_leash_distance(self):
        result = _validate_mob_params(
            detection_range=15.0,
            attack_range=3.0,
            leash_distance=0.0,
            patrol_speed=2.0,
            chase_speed=5.0,
            flee_health_pct=0.2,
        )
        assert result is not None

    def test_flee_health_pct_above_one(self):
        result = _validate_mob_params(
            detection_range=15.0,
            attack_range=3.0,
            leash_distance=30.0,
            patrol_speed=2.0,
            chase_speed=5.0,
            flee_health_pct=1.5,
        )
        assert result is not None

    def test_flee_health_pct_negative(self):
        result = _validate_mob_params(
            detection_range=15.0,
            attack_range=3.0,
            leash_distance=30.0,
            patrol_speed=2.0,
            chase_speed=5.0,
            flee_health_pct=-0.1,
        )
        assert result is not None

    def test_flee_health_pct_zero_is_valid(self):
        result = _validate_mob_params(
            detection_range=15.0,
            attack_range=3.0,
            leash_distance=30.0,
            patrol_speed=2.0,
            chase_speed=5.0,
            flee_health_pct=0.0,
        )
        assert result is None

    def test_flee_health_pct_one_is_valid(self):
        result = _validate_mob_params(
            detection_range=15.0,
            attack_range=3.0,
            leash_distance=30.0,
            patrol_speed=2.0,
            chase_speed=5.0,
            flee_health_pct=1.0,
        )
        assert result is None


class TestValidateSpawnParams:
    """Tests for _validate_spawn_params()."""

    def test_valid_params_return_none(self):
        result = _validate_spawn_params(
            max_count=10, respawn_timer=5.0, spawn_radius=15.0
        )
        assert result is None

    def test_zero_max_count(self):
        result = _validate_spawn_params(
            max_count=0, respawn_timer=5.0, spawn_radius=15.0
        )
        assert result is not None

    def test_negative_max_count(self):
        result = _validate_spawn_params(
            max_count=-1, respawn_timer=5.0, spawn_radius=15.0
        )
        assert result is not None

    def test_negative_respawn_timer(self):
        result = _validate_spawn_params(
            max_count=10, respawn_timer=-1.0, spawn_radius=15.0
        )
        assert result is not None

    def test_zero_respawn_timer_is_valid(self):
        result = _validate_spawn_params(
            max_count=10, respawn_timer=0.0, spawn_radius=15.0
        )
        assert result is None

    def test_zero_spawn_radius(self):
        result = _validate_spawn_params(
            max_count=10, respawn_timer=5.0, spawn_radius=0.0
        )
        assert result is not None

    def test_negative_spawn_radius(self):
        result = _validate_spawn_params(
            max_count=10, respawn_timer=5.0, spawn_radius=-5.0
        )
        assert result is not None


class TestValidateAbilityParams:
    """Tests for _validate_ability_params()."""

    def test_valid_params_return_none(self):
        result = _validate_ability_params(cooldown=1.5, damage=25.0)
        assert result is None

    def test_negative_cooldown(self):
        result = _validate_ability_params(cooldown=-1.0, damage=25.0)
        assert result is not None

    def test_zero_cooldown_is_valid(self):
        result = _validate_ability_params(cooldown=0.0, damage=25.0)
        assert result is None

    def test_negative_damage(self):
        result = _validate_ability_params(cooldown=1.5, damage=-10.0)
        assert result is not None

    def test_zero_damage_is_valid(self):
        result = _validate_ability_params(cooldown=1.5, damage=0.0)
        assert result is None


class TestValidateProjectileParams:
    """Tests for _validate_projectile_params()."""

    def test_valid_straight(self):
        result = _validate_projectile_params(velocity=20.0, trajectory="straight")
        assert result is None

    def test_valid_arc(self):
        result = _validate_projectile_params(velocity=15.0, trajectory="arc")
        assert result is None

    def test_valid_homing(self):
        result = _validate_projectile_params(velocity=10.0, trajectory="homing")
        assert result is None

    def test_zero_velocity(self):
        result = _validate_projectile_params(velocity=0.0, trajectory="straight")
        assert result is not None

    def test_negative_velocity(self):
        result = _validate_projectile_params(velocity=-5.0, trajectory="straight")
        assert result is not None

    def test_invalid_trajectory(self):
        result = _validate_projectile_params(velocity=20.0, trajectory="zigzag")
        assert result is not None


# ---------------------------------------------------------------------------
# Mob controller script (MOB-01)
# ---------------------------------------------------------------------------


class TestMobController:
    """Tests for generate_mob_controller_script()."""

    def test_contains_using_unity_engine(self):
        result = generate_mob_controller_script("Goblin")
        assert "using UnityEngine;" in result

    def test_no_using_unity_editor(self):
        result = generate_mob_controller_script("Goblin")
        assert "using UnityEditor;" not in result

    def test_contains_using_unity_ai(self):
        result = generate_mob_controller_script("Goblin")
        assert "using UnityEngine.AI;" in result

    def test_contains_navmesh_agent(self):
        result = generate_mob_controller_script("Goblin")
        assert "NavMeshAgent" in result

    def test_contains_mob_state_enum(self):
        result = generate_mob_controller_script("Goblin")
        assert "enum MobState" in result
        assert "Patrol" in result
        assert "Aggro" in result
        assert "Chase" in result
        assert "Attack" in result
        assert "Flee" in result
        assert "ReturnToPatrol" in result

    def test_contains_switch_current_state(self):
        result = generate_mob_controller_script("Goblin")
        assert "switch" in result
        assert "currentState" in result

    def test_contains_detection_range(self):
        result = generate_mob_controller_script("Goblin", detection_range=20.0)
        assert "20" in result
        assert "detectionRange" in result

    def test_contains_attack_range(self):
        result = generate_mob_controller_script("Goblin", attack_range=3.5)
        assert "3.5" in result
        assert "attackRange" in result

    def test_contains_leash_distance(self):
        result = generate_mob_controller_script("Goblin", leash_distance=40.0)
        assert "40" in result
        assert "leashDistance" in result

    def test_contains_patrol_speed(self):
        result = generate_mob_controller_script("Goblin", patrol_speed=2.5)
        assert "2.5" in result
        assert "patrolSpeed" in result

    def test_contains_chase_speed(self):
        result = generate_mob_controller_script("Goblin", chase_speed=6.0)
        assert "6" in result
        assert "chaseSpeed" in result

    def test_contains_flee_health_pct(self):
        result = generate_mob_controller_script("Goblin", flee_health_pct=0.15)
        assert "0.15" in result
        assert "fleeHealthPercent" in result

    def test_contains_set_destination(self):
        result = generate_mob_controller_script("Goblin")
        assert "SetDestination" in result

    def test_sanitizes_name(self):
        result = generate_mob_controller_script("Goblin Archer-01")
        assert "GoblinArcher01" in result

    def test_contains_monobehaviour(self):
        result = generate_mob_controller_script("Goblin")
        assert "MonoBehaviour" in result

    def test_contains_spawn_position(self):
        result = generate_mob_controller_script("Goblin")
        assert "spawnPosition" in result


# ---------------------------------------------------------------------------
# Aggro system script (MOB-02)
# ---------------------------------------------------------------------------


class TestAggroSystem:
    """Tests for generate_aggro_system_script()."""

    def test_contains_using_unity_engine(self):
        result = generate_aggro_system_script("Goblin")
        assert "using UnityEngine;" in result

    def test_no_using_unity_editor(self):
        result = generate_aggro_system_script("Goblin")
        assert "using UnityEditor;" not in result

    def test_contains_overlap_sphere_non_alloc(self):
        result = generate_aggro_system_script("Goblin")
        assert "OverlapSphereNonAlloc" in result

    def test_contains_collider_buffer(self):
        result = generate_aggro_system_script("Goblin")
        assert "Collider[]" in result

    def test_contains_threat_table(self):
        result = generate_aggro_system_script("Goblin")
        assert "threatTable" in result or "ThreatTable" in result

    def test_contains_decay(self):
        result = generate_aggro_system_script("Goblin")
        assert "decay" in result.lower()

    def test_contains_leash_distance(self):
        result = generate_aggro_system_script("Goblin", leash_distance=35.0)
        assert "35" in result
        assert "leashDistance" in result

    def test_contains_detection_range(self):
        result = generate_aggro_system_script("Goblin", detection_range=18.0)
        assert "18" in result
        assert "detectionRange" in result

    def test_contains_decay_rate(self):
        result = generate_aggro_system_script("Goblin", decay_rate=2.0)
        assert "2" in result
        assert "decayRate" in result

    def test_contains_max_threats(self):
        result = generate_aggro_system_script("Goblin", max_threats=16)
        assert "16" in result

    def test_contains_return_to_patrol(self):
        result = generate_aggro_system_script("Goblin")
        assert "ReturnToPatrol" in result or "returnToPatrol" in result.lower()

    def test_contains_monobehaviour(self):
        result = generate_aggro_system_script("Goblin")
        assert "MonoBehaviour" in result

    def test_sanitizes_name(self):
        result = generate_aggro_system_script("Dark Knight-02")
        assert "DarkKnight02" in result

    def test_contains_timer_not_every_frame(self):
        """Decay should run on a timer (e.g. every 0.2s), not every frame."""
        result = generate_aggro_system_script("Goblin")
        assert "0.2" in result or "timer" in result.lower()


# ---------------------------------------------------------------------------
# Patrol route script (MOB-03)
# ---------------------------------------------------------------------------


class TestPatrolRoute:
    """Tests for generate_patrol_route_script()."""

    def test_contains_using_unity_engine(self):
        result = generate_patrol_route_script("Goblin")
        assert "using UnityEngine;" in result

    def test_no_using_unity_editor(self):
        result = generate_patrol_route_script("Goblin")
        assert "using UnityEditor;" not in result

    def test_contains_using_unity_ai(self):
        result = generate_patrol_route_script("Goblin")
        assert "using UnityEngine.AI;" in result

    def test_contains_transform_array_waypoints(self):
        result = generate_patrol_route_script("Goblin")
        assert "Transform[]" in result
        assert "waypoints" in result

    def test_contains_dwell_times(self):
        result = generate_patrol_route_script("Goblin")
        assert "dwellTime" in result or "dwell" in result.lower()

    def test_contains_set_destination(self):
        result = generate_patrol_route_script("Goblin")
        assert "SetDestination" in result

    def test_contains_random_deviation(self):
        result = generate_patrol_route_script("Goblin", random_deviation=2.0)
        assert "2" in result
        assert "Random" in result

    def test_contains_navmesh_agent(self):
        result = generate_patrol_route_script("Goblin")
        assert "NavMeshAgent" in result

    def test_contains_waypoint_index(self):
        result = generate_patrol_route_script("Goblin")
        assert "currentWaypointIndex" in result or "waypointIndex" in result.lower()

    def test_contains_monobehaviour(self):
        result = generate_patrol_route_script("Goblin")
        assert "MonoBehaviour" in result

    def test_sanitizes_name(self):
        result = generate_patrol_route_script("Forest Scout-03")
        assert "ForestScout03" in result

    def test_dwell_time_param(self):
        result = generate_patrol_route_script("Goblin", dwell_time=3.5)
        assert "3.5" in result


# ---------------------------------------------------------------------------
# Spawn system script (MOB-04)
# ---------------------------------------------------------------------------


class TestSpawnSystem:
    """Tests for generate_spawn_system_script()."""

    def test_contains_using_unity_engine(self):
        result = generate_spawn_system_script("DungeonEntry")
        assert "using UnityEngine;" in result

    def test_no_using_unity_editor(self):
        result = generate_spawn_system_script("DungeonEntry")
        assert "using UnityEditor;" not in result

    def test_contains_spawn_wave_class(self):
        result = generate_spawn_system_script("DungeonEntry")
        assert "SpawnWave" in result
        assert "[System.Serializable]" in result

    def test_contains_max_alive(self):
        result = generate_spawn_system_script("DungeonEntry", max_count=20)
        assert "20" in result
        assert "maxAlive" in result

    def test_contains_respawn_timer(self):
        result = generate_spawn_system_script("DungeonEntry", respawn_timer=10.0)
        assert "10" in result
        assert "respawnTimer" in result

    def test_contains_spawn_radius(self):
        result = generate_spawn_system_script("DungeonEntry", spawn_radius=8.0)
        assert "8" in result
        assert "spawnRadius" in result

    def test_contains_wave_cooldown(self):
        result = generate_spawn_system_script("DungeonEntry", wave_cooldown=15.0)
        assert "15" in result
        assert "waveCooldown" in result

    def test_contains_coroutine(self):
        result = generate_spawn_system_script("DungeonEntry")
        assert "IEnumerator" in result or "Coroutine" in result or "StartCoroutine" in result

    def test_contains_random_inside_unit_sphere(self):
        result = generate_spawn_system_script("DungeonEntry")
        assert "Random.insideUnitSphere" in result

    def test_contains_monobehaviour(self):
        result = generate_spawn_system_script("DungeonEntry")
        assert "MonoBehaviour" in result

    def test_sanitizes_name(self):
        result = generate_spawn_system_script("Dungeon Entry-01")
        assert "DungeonEntry01" in result

    def test_contains_wave_count(self):
        result = generate_spawn_system_script("DungeonEntry", wave_count=5)
        assert "5" in result


# ---------------------------------------------------------------------------
# Behavior tree script (MOB-05)
# ---------------------------------------------------------------------------


class TestBehaviorTree:
    """Tests for generate_behavior_tree_script()."""

    def test_contains_using_unity_engine(self):
        result = generate_behavior_tree_script("EnemyAI")
        assert "using UnityEngine;" in result

    def test_no_using_unity_editor(self):
        result = generate_behavior_tree_script("EnemyAI")
        assert "using UnityEditor;" not in result

    def test_contains_bt_node_base(self):
        result = generate_behavior_tree_script("EnemyAI")
        assert "BT_Node" in result
        assert "ScriptableObject" in result

    def test_contains_abstract(self):
        result = generate_behavior_tree_script("EnemyAI")
        assert "abstract" in result

    def test_contains_node_state(self):
        result = generate_behavior_tree_script("EnemyAI")
        assert "NodeState" in result

    def test_contains_sequence_node(self):
        result = generate_behavior_tree_script("EnemyAI")
        assert "Sequence" in result

    def test_contains_selector_node(self):
        result = generate_behavior_tree_script("EnemyAI")
        assert "Selector" in result

    def test_contains_leaf_node(self):
        result = generate_behavior_tree_script("EnemyAI")
        assert "Leaf" in result or "ActionNode" in result

    def test_contains_behavior_tree_runner(self):
        result = generate_behavior_tree_script("EnemyAI")
        assert "BehaviorTreeRunner" in result

    def test_runner_is_monobehaviour(self):
        result = generate_behavior_tree_script("EnemyAI")
        assert "MonoBehaviour" in result

    def test_contains_evaluate(self):
        result = generate_behavior_tree_script("EnemyAI")
        assert "Evaluate" in result

    def test_sanitizes_name(self):
        result = generate_behavior_tree_script("Enemy AI-01")
        assert "EnemyAI01" in result

    def test_custom_node_types(self):
        result = generate_behavior_tree_script(
            "EnemyAI", node_types=["CheckHealth", "FindTarget", "MoveToTarget"]
        )
        assert "CheckHealth" in result
        assert "FindTarget" in result
        assert "MoveToTarget" in result

    def test_no_typedef_keyword(self):
        """C# does not have typedef -- ensure the template never emits it."""
        result = generate_behavior_tree_script("EnemyAI")
        assert "typedef" not in result

    def test_no_misplaced_using_alias(self):
        """A using alias outside of the top-level scope is invalid C#."""
        result = generate_behavior_tree_script("EnemyAI")
        # A 'using X = Y;' line after the first class definition is illegal
        lines = result.split("\n")
        seen_class = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("public class ") or stripped.startswith("public abstract class "):
                seen_class = True
            if seen_class and stripped.startswith("using ") and "=" in stripped:
                pytest.fail(f"Found misplaced using alias after class definition: {stripped}")


# ---------------------------------------------------------------------------
# Combat ability script (MOB-06)
# ---------------------------------------------------------------------------


class TestCombatAbility:
    """Tests for generate_combat_ability_script()."""

    def test_contains_using_unity_engine(self):
        result = generate_combat_ability_script("Fireball")
        assert "using UnityEngine;" in result

    def test_no_using_unity_editor(self):
        result = generate_combat_ability_script("Fireball")
        assert "using UnityEditor;" not in result

    def test_contains_create_asset_menu(self):
        result = generate_combat_ability_script("Fireball")
        assert "CreateAssetMenu" in result

    def test_contains_scriptable_object(self):
        result = generate_combat_ability_script("Fireball")
        assert "ScriptableObject" in result

    def test_contains_ability_executor(self):
        result = generate_combat_ability_script("Fireball")
        assert "AbilityExecutor" in result

    def test_contains_cooldown_queue(self):
        result = generate_combat_ability_script("Fireball")
        assert "Queue" in result
        assert "cooldown" in result.lower()

    def test_contains_damage(self):
        result = generate_combat_ability_script("Fireball", damage=50.0)
        assert "50" in result
        assert "damage" in result.lower()

    def test_contains_cooldown(self):
        result = generate_combat_ability_script("Fireball", cooldown=2.5)
        assert "2.5" in result

    def test_contains_vfx_prefab(self):
        result = generate_combat_ability_script("Fireball", vfx_prefab="FireVFX")
        assert "FireVFX" in result
        assert "vfxPrefab" in result or "vfx" in result.lower()

    def test_contains_sound_name(self):
        result = generate_combat_ability_script("Fireball", sound_name="fire_cast")
        assert "fire_cast" in result

    def test_contains_hitbox_size(self):
        result = generate_combat_ability_script("Fireball", hitbox_size=1.5)
        assert "1.5" in result
        assert "hitbox" in result.lower()

    def test_contains_animation_trigger(self):
        result = generate_combat_ability_script("Fireball")
        assert "animTrigger" in result or "animationTrigger" in result

    def test_contains_monobehaviour_executor(self):
        result = generate_combat_ability_script("Fireball")
        assert "MonoBehaviour" in result

    def test_sanitizes_name(self):
        result = generate_combat_ability_script("Fire Ball-02")
        assert "FireBall02" in result


# ---------------------------------------------------------------------------
# Projectile script (MOB-07)
# ---------------------------------------------------------------------------


class TestProjectileSystem:
    """Tests for generate_projectile_script()."""

    def test_contains_using_unity_engine(self):
        result = generate_projectile_script("Arrow")
        assert "using UnityEngine;" in result

    def test_no_using_unity_editor(self):
        result = generate_projectile_script("Arrow")
        assert "using UnityEditor;" not in result

    def test_contains_trajectory_enum(self):
        result = generate_projectile_script("Arrow")
        assert "TrajectoryType" in result
        assert "Straight" in result
        assert "Arc" in result
        assert "Homing" in result

    def test_contains_velocity(self):
        result = generate_projectile_script("Arrow", velocity=25.0)
        assert "25" in result
        assert "velocity" in result.lower()

    def test_contains_trail_renderer(self):
        result = generate_projectile_script("Arrow")
        assert "TrailRenderer" in result

    def test_contains_on_trigger_enter(self):
        result = generate_projectile_script("Arrow")
        assert "OnTriggerEnter" in result

    def test_contains_impact_vfx(self):
        result = generate_projectile_script("Arrow", impact_vfx="ArrowImpact")
        assert "ArrowImpact" in result

    def test_contains_rigidbody_for_arc(self):
        result = generate_projectile_script("Arrow")
        assert "Rigidbody" in result

    def test_contains_transform_translate_for_straight(self):
        result = generate_projectile_script("Arrow")
        assert "Translate" in result or "transform" in result

    def test_contains_lifetime(self):
        result = generate_projectile_script("Arrow", lifetime=5.0)
        assert "5" in result
        assert "lifetime" in result.lower()

    def test_contains_monobehaviour(self):
        result = generate_projectile_script("Arrow")
        assert "MonoBehaviour" in result

    def test_sanitizes_name(self):
        result = generate_projectile_script("Fire Arrow-01")
        assert "FireArrow01" in result

    def test_contains_destroy_after_lifetime(self):
        result = generate_projectile_script("Arrow")
        assert "Destroy" in result

    def test_trail_width_param(self):
        result = generate_projectile_script("Arrow", trail_width=0.3)
        assert "0.3" in result
