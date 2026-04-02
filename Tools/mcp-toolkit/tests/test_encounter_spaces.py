"""Tests for encounter_spaces handler."""

import math

import pytest

from blender_addon.handlers.encounter_spaces import (
    ENCOUNTER_TEMPLATES,
    compute_encounter_layout,
    validate_encounter_layout,
    get_available_templates,
    get_templates_by_difficulty,
)


# ---------------------------------------------------------------------------
# Template definitions
# ---------------------------------------------------------------------------


class TestTemplateDefinitions:
    def test_eight_templates(self):
        assert len(ENCOUNTER_TEMPLATES) == 8

    def test_all_templates_have_required_fields(self):
        required = {"shape", "player_entry", "trigger_volume", "difficulty"}
        for name, tmpl in ENCOUNTER_TEMPLATES.items():
            missing = required - set(tmpl.keys())
            assert not missing, f"Template '{name}' missing: {missing}"

    def test_all_templates_have_enemy_bounds(self):
        for name, tmpl in ENCOUNTER_TEMPLATES.items():
            assert "min_enemies" in tmpl, f"'{name}' missing min_enemies"
            assert "max_enemies" in tmpl, f"'{name}' missing max_enemies"
            assert tmpl["min_enemies"] <= tmpl["max_enemies"]


# ---------------------------------------------------------------------------
# Layout computation
# ---------------------------------------------------------------------------


class TestComputeEncounterLayout:
    def test_all_templates_produce_layout(self):
        for name in ENCOUNTER_TEMPLATES:
            layout = compute_encounter_layout(name)
            assert layout["template"] == name
            assert "shape" in layout
            assert "entry" in layout

    def test_invalid_template_raises(self):
        with pytest.raises(ValueError, match="Unknown encounter template"):
            compute_encounter_layout("nonexistent")

    def test_ambush_corridor_structure(self):
        layout = compute_encounter_layout("ambush_corridor")
        assert layout["shape"] == "narrow_corridor"
        assert len(layout["cover"]) > 0
        assert len(layout["enemies"]) > 0
        assert layout["entry"] == (0, 0, 0)
        assert layout["exit"] == (0, 15, 0)

    def test_arena_circle_structure(self):
        layout = compute_encounter_layout("arena_circle")
        assert layout["shape"] == "circular"
        assert len(layout["cover"]) > 0
        assert "bounds" in layout
        assert layout["bounds"]["radius"] == 12.0

    def test_boss_chamber_has_phase_triggers(self):
        layout = compute_encounter_layout("boss_chamber")
        phase_triggers = [t for t in layout["triggers"] if t["type"] == "phase_trigger"]
        assert len(phase_triggers) == 3

    def test_gauntlet_has_hazards(self):
        layout = compute_encounter_layout("gauntlet_run")
        assert len(layout["hazards"]) > 0
        for h in layout["hazards"]:
            assert "type" in h
            assert "center" in h

    def test_stealth_zone_has_patrol_routes(self):
        layout = compute_encounter_layout("stealth_zone")
        assert len(layout["patrol_routes"]) > 0

    def test_puzzle_room_has_mechanisms(self):
        layout = compute_encounter_layout("puzzle_room")
        assert len(layout["mechanisms"]) > 0
        assert len(layout["traps"]) > 0

    def test_defensive_holdout_has_defend_point(self):
        layout = compute_encounter_layout("defensive_holdout")
        assert "defend_point" in layout

    def test_siege_has_barricades(self):
        layout = compute_encounter_layout("siege_approach")
        barricades = [p for p in layout["props"] if p["type"] == "barricade"]
        assert len(barricades) > 0

    def test_enemy_count_override(self):
        layout = compute_encounter_layout("ambush_corridor", enemy_count=2)
        assert len(layout["enemies"]) <= 6  # max_enemies cap

    def test_deterministic(self):
        l1 = compute_encounter_layout("arena_circle", seed=42)
        l2 = compute_encounter_layout("arena_circle", seed=42)
        assert l1["cover"] == l2["cover"]
        assert l1["enemies"] == l2["enemies"]


# ---------------------------------------------------------------------------
# Encounter area bounds
# ---------------------------------------------------------------------------


class TestEncounterBounds:
    def test_circular_bounds(self):
        layout = compute_encounter_layout("arena_circle")
        assert "radius" in layout["bounds"]

    def test_corridor_bounds(self):
        layout = compute_encounter_layout("ambush_corridor")
        b = layout["bounds"]
        assert b["min"][1] == 0  # starts at y=0
        assert b["max"][1] == 15  # length=15

    def test_all_cover_within_bounds(self):
        for name in ENCOUNTER_TEMPLATES:
            layout = compute_encounter_layout(name)
            bounds = layout.get("bounds", {})
            radius = bounds.get("radius")
            b_min = bounds.get("min")
            b_max = bounds.get("max")
            for pos in layout.get("cover", []):
                if radius is not None:
                    dist = math.sqrt(pos[0] ** 2 + pos[1] ** 2)
                    assert dist <= radius * 1.2, \
                        f"Cover {pos} outside radius {radius} in {name}"


# ---------------------------------------------------------------------------
# Spawn points
# ---------------------------------------------------------------------------


class TestSpawnPoints:
    def test_spawn_points_within_area(self):
        layout = compute_encounter_layout("ambush_corridor")
        bounds = layout["bounds"]
        for enemy in layout["enemies"]:
            assert bounds["min"][1] - 1 <= enemy[1] <= bounds["max"][1] + 1

    def test_cover_not_overlapping_spawns(self):
        layout = compute_encounter_layout("ambush_corridor")
        for cover in layout["cover"]:
            for enemy in layout["enemies"]:
                dist = math.sqrt(
                    (cover[0] - enemy[0]) ** 2 +
                    (cover[1] - enemy[1]) ** 2
                )
                # Cover and spawn shouldn't be at exact same spot
                assert dist > 0.1, "Cover and spawn overlap"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidateLayout:
    def test_valid_layout(self):
        layout = compute_encounter_layout("ambush_corridor")
        result = validate_encounter_layout(layout)
        assert isinstance(result["valid"], bool)
        assert isinstance(result["issues"], list)
        assert "metrics" in result

    def test_metrics_computed(self):
        layout = compute_encounter_layout("ambush_corridor")
        result = validate_encounter_layout(layout)
        metrics = result["metrics"]
        assert "cover_count" in metrics
        assert "enemy_count" in metrics
        assert metrics["cover_count"] == len(layout["cover"])

    def test_all_templates_validate(self):
        for name in ENCOUNTER_TEMPLATES:
            layout = compute_encounter_layout(name)
            result = validate_encounter_layout(layout)
            # Should return a result dict (may or may not be valid)
            assert "valid" in result
            assert "issues" in result


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


class TestUtilityFunctions:
    def test_get_available_templates(self):
        templates = get_available_templates()
        assert len(templates) == 8
        assert templates == sorted(templates)

    def test_get_templates_by_difficulty(self):
        hard = get_templates_by_difficulty("hard")
        assert len(hard) > 0
        for name in hard:
            assert ENCOUNTER_TEMPLATES[name]["difficulty"] == "hard"

    def test_boss_difficulty(self):
        boss = get_templates_by_difficulty("boss")
        assert "boss_chamber" in boss
