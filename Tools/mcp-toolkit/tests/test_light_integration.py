"""Tests for light_integration handler."""

import math

import pytest

from blender_addon.handlers.light_integration import (
    LIGHT_PROP_MAP,
    FLICKER_PRESETS,
    compute_light_placements,
    merge_nearby_lights,
    compute_light_budget,
)


# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------


class TestLightDefinitions:
    def test_eight_light_props(self):
        assert len(LIGHT_PROP_MAP) == 8

    def test_all_props_have_required_fields(self):
        required = {"type", "color", "energy", "radius", "flicker", "offset_z", "shadow"}
        for name, prop in LIGHT_PROP_MAP.items():
            missing = required - set(prop.keys())
            assert not missing, f"Prop '{name}' missing: {missing}"

    def test_color_is_rgb(self):
        for name, prop in LIGHT_PROP_MAP.items():
            assert len(prop["color"]) == 3

    def test_energy_positive(self):
        for name, prop in LIGHT_PROP_MAP.items():
            assert prop["energy"] > 0

    def test_flicker_presets_exist(self):
        assert len(FLICKER_PRESETS) >= 4
        for name, preset in FLICKER_PRESETS.items():
            assert "frequency" in preset
            assert "amplitude" in preset
            assert "pattern" in preset


# ---------------------------------------------------------------------------
# Light placements
# ---------------------------------------------------------------------------


class TestComputeLightPlacements:
    def test_basic_placement(self):
        props = [
            {"type": "torch_sconce", "position": (5, 10, 0)},
            {"type": "campfire", "position": (15, 20, 0)},
        ]
        lights = compute_light_placements(props)
        assert len(lights) == 2

    def test_non_light_props_ignored(self):
        props = [
            {"type": "barrel", "position": (0, 0)},
            {"type": "torch_sconce", "position": (5, 5)},
        ]
        lights = compute_light_placements(props)
        assert len(lights) == 1
        assert lights[0]["source_prop"] == "torch_sconce"

    def test_light_position_includes_offset(self):
        props = [{"type": "torch_sconce", "position": (5, 10, 3)}]
        lights = compute_light_placements(props)
        # offset_z for torch_sconce is 2.0
        assert lights[0]["position"][2] == 5.0  # 3 + 2.0

    def test_2d_position_uses_offset_as_z(self):
        props = [{"type": "lantern", "position": (5, 10)}]
        lights = compute_light_placements(props)
        # offset_z for lantern is 1.5
        assert lights[0]["position"][2] == 1.5

    def test_light_has_all_fields(self):
        props = [{"type": "brazier", "position": (0, 0, 0)}]
        lights = compute_light_placements(props)
        light = lights[0]
        assert "light_type" in light
        assert "position" in light
        assert "color" in light
        assert "energy" in light
        assert "radius" in light
        assert "shadow" in light
        assert "flicker" in light
        assert "source_prop" in light

    def test_flicker_data_for_torch(self):
        props = [{"type": "torch_sconce", "position": (0, 0)}]
        lights = compute_light_placements(props)
        flicker = lights[0]["flicker"]
        assert flicker is not None
        assert "frequency" in flicker
        assert "pattern" in flicker

    def test_no_flicker_for_lantern(self):
        props = [{"type": "lantern", "position": (0, 0)}]
        lights = compute_light_placements(props)
        assert lights[0]["flicker"] is None

    def test_disabled_prop(self):
        props = [{"type": "campfire", "position": (0, 0), "on": False}]
        lights = compute_light_placements(props)
        assert len(lights) == 0

    def test_scale_affects_energy(self):
        props = [{"type": "campfire", "position": (0, 0, 0), "scale": 2.0}]
        lights = compute_light_placements(props)
        assert lights[0]["energy"] == 200.0  # 100 * 2.0

    def test_empty_input(self):
        lights = compute_light_placements([])
        assert lights == []


# ---------------------------------------------------------------------------
# Light merging
# ---------------------------------------------------------------------------


class TestMergeNearbyLights:
    def test_empty_input(self):
        assert merge_nearby_lights([]) == []

    def test_no_merge_distant(self):
        lights = [
            {"position": (0, 0, 0), "color": (1, 1, 1), "energy": 50,
             "radius": 5, "shadow": True, "flicker": None},
            {"position": (100, 100, 0), "color": (1, 1, 1), "energy": 50,
             "radius": 5, "shadow": False, "flicker": None},
        ]
        merged = merge_nearby_lights(lights, merge_distance=2.0)
        assert len(merged) == 2

    def test_merge_close_lights(self):
        lights = [
            {"position": (0, 0, 0), "color": (1, 0, 0), "energy": 50,
             "radius": 5, "shadow": True, "flicker": None},
            {"position": (0.5, 0, 0), "color": (0, 1, 0), "energy": 50,
             "radius": 3, "shadow": False, "flicker": None},
        ]
        merged = merge_nearby_lights(lights, merge_distance=2.0)
        assert len(merged) == 1

    def test_merged_energy_sums(self):
        lights = [
            {"position": (0, 0, 0), "color": (1, 1, 1), "energy": 30,
             "radius": 5, "shadow": False, "flicker": None},
            {"position": (0.1, 0, 0), "color": (1, 1, 1), "energy": 70,
             "radius": 3, "shadow": False, "flicker": None},
        ]
        merged = merge_nearby_lights(lights, merge_distance=2.0)
        assert merged[0]["energy"] == 100.0

    def test_merged_radius_takes_max(self):
        lights = [
            {"position": (0, 0, 0), "color": (1, 1, 1), "energy": 50,
             "radius": 8, "shadow": False, "flicker": None},
            {"position": (0.1, 0, 0), "color": (1, 1, 1), "energy": 50,
             "radius": 3, "shadow": False, "flicker": None},
        ]
        merged = merge_nearby_lights(lights, merge_distance=2.0)
        assert merged[0]["radius"] == 8

    def test_merged_shadow_is_union(self):
        lights = [
            {"position": (0, 0, 0), "color": (1, 1, 1), "energy": 50,
             "radius": 5, "shadow": True, "flicker": None},
            {"position": (0.1, 0, 0), "color": (1, 1, 1), "energy": 50,
             "radius": 5, "shadow": False, "flicker": None},
        ]
        merged = merge_nearby_lights(lights, merge_distance=2.0)
        assert merged[0]["shadow"] is True

    def test_reduces_count(self):
        # 3 lights all within merge distance
        lights = [
            {"position": (0, 0, 0), "color": (1, 1, 1), "energy": 30,
             "radius": 5, "shadow": False, "flicker": None},
            {"position": (0.5, 0, 0), "color": (1, 1, 1), "energy": 30,
             "radius": 5, "shadow": False, "flicker": None},
            {"position": (0.2, 0.3, 0), "color": (1, 1, 1), "energy": 30,
             "radius": 5, "shadow": False, "flicker": None},
        ]
        merged = merge_nearby_lights(lights, merge_distance=2.0)
        assert len(merged) < len(lights)


# ---------------------------------------------------------------------------
# Light budget
# ---------------------------------------------------------------------------


class TestComputeLightBudget:
    def test_empty(self):
        result = compute_light_budget([])
        assert result["total_lights"] == 0
        assert result["estimated_cost"] == 0

    def test_basic_budget(self):
        lights = [
            {"shadow": True, "flicker": {"pattern": "noise"}},
            {"shadow": False, "flicker": None},
        ]
        result = compute_light_budget(lights)
        assert result["total_lights"] == 2
        assert result["shadow_lights"] == 1
        assert result["flicker_lights"] == 1

    def test_shadow_cost(self):
        no_shadow = [{"shadow": False, "flicker": None}]
        with_shadow = [{"shadow": True, "flicker": None}]
        r1 = compute_light_budget(no_shadow, shadow_cost=3.0)
        r2 = compute_light_budget(with_shadow, shadow_cost=3.0)
        assert r2["estimated_cost"] > r1["estimated_cost"]

    def test_recommendation_levels(self):
        # Few lights = excellent
        few = [{"shadow": False, "flicker": None}]
        r = compute_light_budget(few)
        assert r["recommendation"] in ("excellent", "good")

        # Many shadow lights = heavy
        many = [{"shadow": True, "flicker": {"p": 1}} for _ in range(80)]
        r2 = compute_light_budget(many)
        assert "reduce" in r2["recommendation"] or "excessive" in r2["recommendation"] or "heavy" in r2["recommendation"]

    def test_cost_calculation(self):
        lights = [
            {"shadow": True, "flicker": {"p": 1}},
        ]
        result = compute_light_budget(lights, shadow_cost=3.0, flicker_cost=0.5)
        # base=1 + shadow=3.0 + flicker=0.5 = 4.5
        assert result["estimated_cost"] == 4.5
