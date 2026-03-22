"""Tests for world_map, light_integration, and atmospheric_volumes handlers.

All modules are pure logic (no bpy/bmesh). Tests verify data structure,
determinism, edge cases, biome coverage, and performance budgets.
"""

import math

import pytest


# ===================================================================
# World Map Generator Tests (Task #45)
# ===================================================================


class TestWorldMapGeneration:
    """Test world map generation with Voronoi regions and POI distribution."""

    def test_default_generation_returns_worldmap(self):
        from blender_addon.handlers.world_map import generate_world_map

        wm = generate_world_map()
        assert wm is not None
        assert len(wm.regions) == 6
        assert wm.map_size == 2000.0
        assert wm.seed == 42

    def test_custom_region_count(self):
        from blender_addon.handlers.world_map import generate_world_map

        wm = generate_world_map(num_regions=10, seed=99)
        assert len(wm.regions) == 10

    def test_minimum_two_regions(self):
        from blender_addon.handlers.world_map import generate_world_map

        wm = generate_world_map(num_regions=1)
        assert len(wm.regions) >= 2

    def test_regions_have_valid_structure(self):
        from blender_addon.handlers.world_map import generate_world_map, BIOME_TYPES

        wm = generate_world_map(num_regions=4, seed=7)
        for region in wm.regions:
            assert region.name
            assert region.biome in BIOME_TYPES
            assert len(region.center) == 2
            assert len(region.bounds) == 4
            assert region.bounds[0] < region.bounds[2]  # min_x < max_x
            assert region.bounds[1] < region.bounds[3]  # min_y < max_y
            assert region.area > 0

    def test_regions_centers_within_map_bounds(self):
        from blender_addon.handlers.world_map import generate_world_map

        wm = generate_world_map(map_size=1000.0, seed=55)
        for region in wm.regions:
            assert 0 <= region.center[0] <= 1000.0
            assert 0 <= region.center[1] <= 1000.0

    def test_connections_between_adjacent_regions(self):
        from blender_addon.handlers.world_map import generate_world_map

        wm = generate_world_map(num_regions=6, seed=42)
        assert len(wm.connections) > 0
        region_names = {r.name for r in wm.regions}
        for conn in wm.connections:
            assert conn.from_region in region_names
            assert conn.to_region in region_names
            assert conn.distance > 0
            assert len(conn.waypoints) >= 2
            assert conn.road_type in ("main", "path")

    def test_poi_minimum_count(self):
        from blender_addon.handlers.world_map import generate_world_map

        wm = generate_world_map(min_pois=300, seed=42)
        assert len(wm.poi_positions) >= 300

    def test_poi_positions_within_map_bounds(self):
        from blender_addon.handlers.world_map import generate_world_map

        wm = generate_world_map(map_size=500.0, min_pois=50, seed=11)
        for poi in wm.poi_positions:
            assert 0 <= poi.position[0] <= 500.0
            assert 0 <= poi.position[1] <= 500.0

    def test_poi_types_are_valid(self):
        from blender_addon.handlers.world_map import generate_world_map, POI_TYPES

        wm = generate_world_map(min_pois=100, seed=42)
        for poi in wm.poi_positions:
            assert poi.poi_type in POI_TYPES
            assert len(poi.props) > 0
            assert poi.region  # non-empty region name

    def test_deterministic_with_same_seed(self):
        from blender_addon.handlers.world_map import generate_world_map

        wm1 = generate_world_map(seed=123)
        wm2 = generate_world_map(seed=123)
        assert len(wm1.regions) == len(wm2.regions)
        assert len(wm1.connections) == len(wm2.connections)
        assert len(wm1.poi_positions) == len(wm2.poi_positions)
        for r1, r2 in zip(wm1.regions, wm2.regions):
            assert r1.name == r2.name
            assert r1.biome == r2.biome

    def test_different_seeds_produce_different_maps(self):
        from blender_addon.handlers.world_map import generate_world_map

        wm1 = generate_world_map(seed=1)
        wm2 = generate_world_map(seed=2)
        # At least biomes or region positions should differ
        biomes1 = {r.biome for r in wm1.regions}
        biomes2 = {r.biome for r in wm2.regions}
        centers1 = [r.center for r in wm1.regions]
        centers2 = [r.center for r in wm2.regions]
        assert biomes1 != biomes2 or centers1 != centers2

    def test_large_map_with_many_regions(self):
        from blender_addon.handlers.world_map import generate_world_map

        wm = generate_world_map(num_regions=15, map_size=5000.0, min_pois=500, seed=77)
        assert len(wm.regions) == 15
        assert len(wm.poi_positions) >= 500

    def test_small_map(self):
        from blender_addon.handlers.world_map import generate_world_map

        wm = generate_world_map(num_regions=3, map_size=100.0, min_pois=10, seed=33)
        assert len(wm.regions) == 3
        assert len(wm.poi_positions) >= 10


class TestWorldMapSerialization:
    """Test world map serialization to dict."""

    def test_to_dict_has_all_keys(self):
        from blender_addon.handlers.world_map import generate_world_map, world_map_to_dict

        wm = generate_world_map(num_regions=3, min_pois=10, seed=42)
        d = world_map_to_dict(wm)
        assert "seed" in d
        assert "map_size" in d
        assert "num_regions" in d
        assert "num_connections" in d
        assert "num_pois" in d
        assert "regions" in d
        assert "connections" in d
        assert "poi_positions" in d
        assert d["num_regions"] == len(d["regions"])
        assert d["num_pois"] == len(d["poi_positions"])

    def test_region_dict_structure(self):
        from blender_addon.handlers.world_map import generate_world_map, world_map_to_dict

        wm = generate_world_map(num_regions=3, min_pois=10, seed=42)
        d = world_map_to_dict(wm)
        for r in d["regions"]:
            assert "name" in r
            assert "center" in r
            assert "biome" in r
            assert "bounds" in r
            assert "area" in r


class TestBiomeTypes:
    """Test biome type definitions."""

    def test_all_biomes_have_required_keys(self):
        from blender_addon.handlers.world_map import BIOME_TYPES

        required = {"color", "vegetation_density", "danger_level", "terrain_roughness", "ambient"}
        for biome_name, biome_def in BIOME_TYPES.items():
            for key in required:
                assert key in biome_def, f"Biome '{biome_name}' missing '{key}'"

    def test_biome_count(self):
        from blender_addon.handlers.world_map import BIOME_TYPES

        assert len(BIOME_TYPES) == 10

    def test_danger_levels_in_range(self):
        from blender_addon.handlers.world_map import BIOME_TYPES

        for name, biome in BIOME_TYPES.items():
            assert 0 <= biome["danger_level"] <= 10, f"{name} danger out of range"

    def test_vegetation_density_in_range(self):
        from blender_addon.handlers.world_map import BIOME_TYPES

        for name, biome in BIOME_TYPES.items():
            assert 0 <= biome["vegetation_density"] <= 1.0, f"{name} veg density out of range"


class TestPOITypes:
    """Test POI type definitions."""

    def test_all_pois_have_required_keys(self):
        from blender_addon.handlers.world_map import POI_TYPES

        required = {"frequency", "min_spacing", "danger_bias", "props"}
        for poi_name, poi_def in POI_TYPES.items():
            for key in required:
                assert key in poi_def, f"POI '{poi_name}' missing '{key}'"

    def test_poi_count(self):
        from blender_addon.handlers.world_map import POI_TYPES

        assert len(POI_TYPES) == 12

    def test_all_pois_have_props(self):
        from blender_addon.handlers.world_map import POI_TYPES

        for name, poi in POI_TYPES.items():
            assert len(poi["props"]) >= 3, f"POI '{name}' has fewer than 3 props"


# ===================================================================
# Landmark System Tests (Task #46)
# ===================================================================


class TestLandmarkTypes:
    """Test landmark type definitions."""

    def test_all_landmarks_have_required_keys(self):
        from blender_addon.handlers.world_map import LANDMARK_TYPES

        required = {"min_height", "visibility_range", "props"}
        for lm_name, lm_def in LANDMARK_TYPES.items():
            for key in required:
                assert key in lm_def, f"Landmark '{lm_name}' missing '{key}'"

    def test_landmark_count(self):
        from blender_addon.handlers.world_map import LANDMARK_TYPES

        assert len(LANDMARK_TYPES) == 5

    def test_glowing_crystal_has_emission(self):
        from blender_addon.handlers.world_map import LANDMARK_TYPES

        assert LANDMARK_TYPES["glowing_crystal"].get("emission") is True

    def test_visibility_ranges_positive(self):
        from blender_addon.handlers.world_map import LANDMARK_TYPES

        for name, lm in LANDMARK_TYPES.items():
            assert lm["visibility_range"] > 0, f"{name} has non-positive visibility range"

    def test_min_heights_positive(self):
        from blender_addon.handlers.world_map import LANDMARK_TYPES

        for name, lm in LANDMARK_TYPES.items():
            assert lm["min_height"] > 0, f"{name} has non-positive min_height"


class TestLandmarkPlacement:
    """Test landmark distribution across world map."""

    def test_place_landmarks_default(self):
        from blender_addon.handlers.world_map import generate_world_map, place_landmarks

        wm = generate_world_map(num_regions=4, seed=42)
        landmarks = place_landmarks(wm)
        assert len(landmarks) > 0
        # At most 1 per region by default
        assert len(landmarks) <= len(wm.regions)

    def test_place_landmarks_multiple_per_region(self):
        from blender_addon.handlers.world_map import generate_world_map, place_landmarks

        wm = generate_world_map(num_regions=4, seed=42)
        landmarks = place_landmarks(wm, landmarks_per_region=3)
        # May have fewer due to spacing constraints
        assert len(landmarks) > 0

    def test_landmark_structure(self):
        from blender_addon.handlers.world_map import generate_world_map, place_landmarks, LANDMARK_TYPES

        wm = generate_world_map(num_regions=4, seed=42)
        landmarks = place_landmarks(wm)
        for lm in landmarks:
            assert lm.landmark_type in LANDMARK_TYPES
            assert len(lm.position) == 2
            assert lm.height > 0
            assert lm.visibility_range > 0
            assert lm.region  # non-empty
            assert len(lm.props) > 0

    def test_landmark_height_above_minimum(self):
        from blender_addon.handlers.world_map import generate_world_map, place_landmarks, LANDMARK_TYPES

        wm = generate_world_map(num_regions=6, seed=42)
        landmarks = place_landmarks(wm, seed=99)
        for lm in landmarks:
            min_h = LANDMARK_TYPES[lm.landmark_type]["min_height"]
            assert lm.height >= min_h

    def test_landmark_deterministic(self):
        from blender_addon.handlers.world_map import generate_world_map, place_landmarks

        wm = generate_world_map(num_regions=4, seed=42)
        lm1 = place_landmarks(wm, seed=10)
        lm2 = place_landmarks(wm, seed=10)
        assert len(lm1) == len(lm2)
        for a, b in zip(lm1, lm2):
            assert a.position == b.position
            assert a.landmark_type == b.landmark_type


class TestStorytellingPatterns:
    """Test environmental storytelling patterns."""

    def test_all_patterns_exist(self):
        from blender_addon.handlers.world_map import STORYTELLING_PATTERNS

        assert len(STORYTELLING_PATTERNS) == 4
        expected = {"battlefield_aftermath", "abandoned_camp", "blood_trail", "corruption_spread"}
        assert set(STORYTELLING_PATTERNS.keys()) == expected

    def test_all_patterns_have_props(self):
        from blender_addon.handlers.world_map import STORYTELLING_PATTERNS

        for name, props in STORYTELLING_PATTERNS.items():
            assert len(props) == 4, f"Pattern '{name}' should have exactly 4 props"

    def test_generate_scene_valid_pattern(self):
        from blender_addon.handlers.world_map import generate_storytelling_scene

        scene = generate_storytelling_scene(
            "battlefield_aftermath", center=(100, 200), radius=15.0, seed=42
        )
        assert scene.pattern == "battlefield_aftermath"
        assert scene.center == (100, 200)
        assert scene.radius == 15.0
        assert len(scene.prop_placements) == 4

    def test_generate_scene_invalid_pattern_raises(self):
        from blender_addon.handlers.world_map import generate_storytelling_scene

        with pytest.raises(ValueError, match="Unknown storytelling pattern"):
            generate_storytelling_scene("nonexistent_pattern", center=(0, 0))

    def test_scene_props_have_position_and_rotation(self):
        from blender_addon.handlers.world_map import generate_storytelling_scene

        scene = generate_storytelling_scene(
            "abandoned_camp", center=(50, 50), radius=10.0, seed=7
        )
        for prop in scene.prop_placements:
            assert "type" in prop
            assert "position" in prop
            assert "rotation" in prop
            assert "scale" in prop
            assert len(prop["position"]) == 2

    def test_blood_trail_linear_distribution(self):
        from blender_addon.handlers.world_map import generate_storytelling_scene

        scene = generate_storytelling_scene(
            "blood_trail", center=(0, 0), radius=20.0, seed=42
        )
        # Blood trail props should be distributed linearly
        assert len(scene.prop_placements) == 4
        # First prop should be closer to center than last
        first = scene.prop_placements[0]["position"]
        last = scene.prop_placements[-1]["position"]
        d_first = math.sqrt(first[0] ** 2 + first[1] ** 2)
        d_last = math.sqrt(last[0] ** 2 + last[1] ** 2)
        assert d_first < d_last

    def test_scene_deterministic(self):
        from blender_addon.handlers.world_map import generate_storytelling_scene

        s1 = generate_storytelling_scene("corruption_spread", (10, 20), seed=55)
        s2 = generate_storytelling_scene("corruption_spread", (10, 20), seed=55)
        assert len(s1.prop_placements) == len(s2.prop_placements)
        for p1, p2 in zip(s1.prop_placements, s2.prop_placements):
            assert p1["type"] == p2["type"]
            assert p1["position"] == p2["position"]


# ===================================================================
# Light Source Integration Tests (Task #50)
# ===================================================================


class TestLightPropMap:
    """Test light prop definitions."""

    def test_all_light_props_have_required_keys(self):
        from blender_addon.handlers.light_integration import LIGHT_PROP_MAP

        required = {"type", "color", "energy", "radius", "flicker", "offset_z", "shadow"}
        for prop_name, prop_def in LIGHT_PROP_MAP.items():
            for key in required:
                assert key in prop_def, f"Light prop '{prop_name}' missing '{key}'"

    def test_light_prop_count(self):
        from blender_addon.handlers.light_integration import LIGHT_PROP_MAP

        assert len(LIGHT_PROP_MAP) == 8

    def test_light_types_valid(self):
        from blender_addon.handlers.light_integration import LIGHT_PROP_MAP

        valid_types = {"point", "area", "spot"}
        for name, prop in LIGHT_PROP_MAP.items():
            assert prop["type"] in valid_types, f"{name} has invalid light type"

    def test_colors_are_tuples_of_three(self):
        from blender_addon.handlers.light_integration import LIGHT_PROP_MAP

        for name, prop in LIGHT_PROP_MAP.items():
            assert len(prop["color"]) == 3, f"{name} color is not RGB tuple"
            for c in prop["color"]:
                assert 0 <= c <= 1.0

    def test_energy_positive(self):
        from blender_addon.handlers.light_integration import LIGHT_PROP_MAP

        for name, prop in LIGHT_PROP_MAP.items():
            assert prop["energy"] > 0, f"{name} has non-positive energy"


class TestFlickerPresets:
    """Test flicker animation presets."""

    def test_all_presets_have_required_keys(self):
        from blender_addon.handlers.light_integration import FLICKER_PRESETS

        required = {"frequency", "amplitude", "pattern"}
        for name, preset in FLICKER_PRESETS.items():
            for key in required:
                assert key in preset, f"Flicker preset '{name}' missing '{key}'"

    def test_preset_count(self):
        from blender_addon.handlers.light_integration import FLICKER_PRESETS

        assert len(FLICKER_PRESETS) == 4


class TestComputeLightPlacements:
    """Test light placement computation."""

    def test_empty_input(self):
        from blender_addon.handlers.light_integration import compute_light_placements

        result = compute_light_placements([])
        assert result == []

    def test_non_light_props_ignored(self):
        from blender_addon.handlers.light_integration import compute_light_placements

        props = [
            {"type": "chest", "position": (10, 20)},
            {"type": "barrel", "position": (30, 40)},
        ]
        result = compute_light_placements(props)
        assert len(result) == 0

    def test_torch_sconce_generates_light(self):
        from blender_addon.handlers.light_integration import compute_light_placements

        props = [{"type": "torch_sconce", "position": (5, 10)}]
        result = compute_light_placements(props)
        assert len(result) == 1
        light = result[0]
        assert light["light_type"] == "point"
        assert light["source_prop"] == "torch_sconce"
        assert light["position"][0] == 5.0
        assert light["position"][1] == 10.0
        assert light["position"][2] == 2.0  # offset_z
        assert light["energy"] == 50
        assert light["flicker"] is not None

    def test_campfire_generates_light(self):
        from blender_addon.handlers.light_integration import compute_light_placements

        props = [{"type": "campfire", "position": (0, 0)}]
        result = compute_light_placements(props)
        assert len(result) == 1
        assert result[0]["energy"] == 100
        assert result[0]["flicker"] is not None

    def test_lantern_no_flicker(self):
        from blender_addon.handlers.light_integration import compute_light_placements

        props = [{"type": "lantern", "position": (0, 0)}]
        result = compute_light_placements(props)
        assert len(result) == 1
        assert result[0]["flicker"] is None

    def test_3d_position_adds_offset(self):
        from blender_addon.handlers.light_integration import compute_light_placements

        props = [{"type": "campfire", "position": (10, 20, 5)}]
        result = compute_light_placements(props)
        assert result[0]["position"][2] == 5.5  # 5 + 0.5 offset

    def test_scale_affects_energy(self):
        from blender_addon.handlers.light_integration import compute_light_placements

        props = [{"type": "campfire", "position": (0, 0), "scale": 2.0}]
        result = compute_light_placements(props)
        assert result[0]["energy"] == 200  # 100 * 2.0

    def test_disabled_light_skipped(self):
        from blender_addon.handlers.light_integration import compute_light_placements

        props = [{"type": "campfire", "position": (0, 0), "on": False}]
        result = compute_light_placements(props)
        assert len(result) == 0

    def test_multiple_props_mixed(self):
        from blender_addon.handlers.light_integration import compute_light_placements

        props = [
            {"type": "torch_sconce", "position": (0, 0)},
            {"type": "chest", "position": (5, 5)},
            {"type": "campfire", "position": (10, 10)},
            {"type": "barrel", "position": (15, 15)},
            {"type": "lantern", "position": (20, 20)},
        ]
        result = compute_light_placements(props)
        assert len(result) == 3  # torch, campfire, lantern

    def test_window_area_light(self):
        from blender_addon.handlers.light_integration import compute_light_placements

        props = [{"type": "window", "position": (5, 10)}]
        result = compute_light_placements(props)
        assert len(result) == 1
        assert result[0]["light_type"] == "area"

    def test_all_light_props_produce_lights(self):
        from blender_addon.handlers.light_integration import compute_light_placements, LIGHT_PROP_MAP

        for prop_type in LIGHT_PROP_MAP:
            props = [{"type": prop_type, "position": (0, 0)}]
            result = compute_light_placements(props)
            assert len(result) == 1, f"Light prop '{prop_type}' didn't produce a light"


class TestMergeNearbyLights:
    """Test light merging for performance."""

    def test_empty_input(self):
        from blender_addon.handlers.light_integration import merge_nearby_lights

        assert merge_nearby_lights([]) == []

    def test_single_light_no_merge(self):
        from blender_addon.handlers.light_integration import merge_nearby_lights

        lights = [{
            "light_type": "point", "position": (0, 0, 1),
            "color": (1, 0.8, 0.5), "energy": 50, "radius": 5.0,
            "shadow": True, "flicker": None, "source_prop": "torch_sconce",
        }]
        result = merge_nearby_lights(lights)
        assert len(result) == 1

    def test_far_apart_lights_not_merged(self):
        from blender_addon.handlers.light_integration import merge_nearby_lights

        lights = [
            {"light_type": "point", "position": (0, 0, 1), "color": (1, 1, 1),
             "energy": 50, "radius": 5, "shadow": True, "flicker": None, "source_prop": "a"},
            {"light_type": "point", "position": (100, 100, 1), "color": (1, 1, 1),
             "energy": 50, "radius": 5, "shadow": True, "flicker": None, "source_prop": "b"},
        ]
        result = merge_nearby_lights(lights, merge_distance=2.0)
        assert len(result) == 2

    def test_close_lights_merged(self):
        from blender_addon.handlers.light_integration import merge_nearby_lights

        lights = [
            {"light_type": "point", "position": (0, 0, 1), "color": (1, 0, 0),
             "energy": 50, "radius": 5, "shadow": True, "flicker": None, "source_prop": "a"},
            {"light_type": "point", "position": (0.5, 0.5, 1), "color": (0, 1, 0),
             "energy": 30, "radius": 3, "shadow": False, "flicker": None, "source_prop": "b"},
        ]
        result = merge_nearby_lights(lights, merge_distance=2.0)
        assert len(result) == 1
        merged = result[0]
        assert merged["energy"] == 80  # 50 + 30
        assert merged["radius"] == 5  # max
        assert merged["shadow"] is True  # either has shadow
        assert merged["merged_count"] == 2

    def test_merged_position_is_energy_weighted(self):
        from blender_addon.handlers.light_integration import merge_nearby_lights

        lights = [
            {"light_type": "point", "position": (0, 0, 0), "color": (1, 1, 1),
             "energy": 100, "radius": 5, "shadow": True, "flicker": None, "source_prop": "a"},
            {"light_type": "point", "position": (1, 0, 0), "color": (1, 1, 1),
             "energy": 0, "radius": 3, "shadow": False, "flicker": None, "source_prop": "b"},
        ]
        result = merge_nearby_lights(lights, merge_distance=2.0)
        assert len(result) == 1
        # Position should be close to (0,0,0) since energy weight is 100 vs 0
        assert result[0]["position"][0] == pytest.approx(0.0, abs=0.01)


class TestLightBudget:
    """Test performance budget estimation."""

    def test_empty_lights(self):
        from blender_addon.handlers.light_integration import compute_light_budget

        result = compute_light_budget([])
        assert result["total_lights"] == 0
        assert result["estimated_cost"] == 0

    def test_simple_lights(self):
        from blender_addon.handlers.light_integration import compute_light_budget

        lights = [
            {"shadow": False, "flicker": None},
            {"shadow": False, "flicker": None},
        ]
        result = compute_light_budget(lights)
        assert result["total_lights"] == 2
        assert result["shadow_lights"] == 0
        assert result["estimated_cost"] == 2.0

    def test_shadow_lights_cost_more(self):
        from blender_addon.handlers.light_integration import compute_light_budget

        lights = [
            {"shadow": True, "flicker": None},
        ]
        result = compute_light_budget(lights, shadow_cost=3.0)
        assert result["estimated_cost"] == 4.0  # 1 base + 3 shadow

    def test_flicker_lights_cost_more(self):
        from blender_addon.handlers.light_integration import compute_light_budget

        lights = [
            {"shadow": False, "flicker": {"frequency": 2}},
        ]
        result = compute_light_budget(lights, flicker_cost=0.5)
        assert result["estimated_cost"] == 1.5  # 1 base + 0.5 flicker

    def test_recommendation_levels(self):
        from blender_addon.handlers.light_integration import compute_light_budget

        # Excellent
        assert compute_light_budget(
            [{"shadow": False, "flicker": None}] * 5
        )["recommendation"] == "excellent"

        # Heavy
        result_heavy = compute_light_budget(
            [{"shadow": True, "flicker": {"f": 1}}] * 30
        )
        assert "heavy" in result_heavy["recommendation"] or "acceptable" in result_heavy["recommendation"] or "excessive" in result_heavy["recommendation"]


# ===================================================================
# Atmospheric Volumes Tests (Task #51)
# ===================================================================


class TestAtmosphericVolumes:
    """Test atmospheric volume definitions."""

    def test_all_volumes_have_required_keys(self):
        from blender_addon.handlers.atmospheric_volumes import ATMOSPHERIC_VOLUMES

        required = {"shape", "density", "height", "color", "opacity", "animation", "animation_speed", "particle_type"}
        for vol_name, vol_def in ATMOSPHERIC_VOLUMES.items():
            for key in required:
                assert key in vol_def, f"Volume '{vol_name}' missing '{key}'"

    def test_volume_count(self):
        from blender_addon.handlers.atmospheric_volumes import ATMOSPHERIC_VOLUMES

        assert len(ATMOSPHERIC_VOLUMES) == 7

    def test_valid_shapes(self):
        from blender_addon.handlers.atmospheric_volumes import ATMOSPHERIC_VOLUMES

        valid_shapes = {"box", "sphere", "cone"}
        for name, vol in ATMOSPHERIC_VOLUMES.items():
            assert vol["shape"] in valid_shapes, f"{name} has invalid shape"

    def test_colors_are_rgb_tuples(self):
        from blender_addon.handlers.atmospheric_volumes import ATMOSPHERIC_VOLUMES

        for name, vol in ATMOSPHERIC_VOLUMES.items():
            assert len(vol["color"]) == 3, f"{name} color is not RGB"
            for c in vol["color"]:
                assert 0 <= c <= 1.0

    def test_void_shimmer_has_distortion(self):
        from blender_addon.handlers.atmospheric_volumes import ATMOSPHERIC_VOLUMES

        assert ATMOSPHERIC_VOLUMES["void_shimmer"].get("distortion") is True

    def test_fireflies_are_emissive(self):
        from blender_addon.handlers.atmospheric_volumes import ATMOSPHERIC_VOLUMES

        ff = ATMOSPHERIC_VOLUMES["fireflies"]
        assert ff["particle_type"] == "emissive"
        assert ff.get("emission_strength", 0) > 0

    def test_god_rays_direction_down(self):
        from blender_addon.handlers.atmospheric_volumes import ATMOSPHERIC_VOLUMES

        assert ATMOSPHERIC_VOLUMES["god_rays"]["direction"] == "down"

    def test_smoke_plume_direction_up(self):
        from blender_addon.handlers.atmospheric_volumes import ATMOSPHERIC_VOLUMES

        assert ATMOSPHERIC_VOLUMES["smoke_plume"]["direction"] == "up"


class TestBiomeAtmosphereRules:
    """Test biome-to-atmosphere mapping."""

    def test_all_biomes_have_rules(self):
        from blender_addon.handlers.atmospheric_volumes import BIOME_ATMOSPHERE_RULES, ATMOSPHERIC_VOLUMES

        # All biomes from world_map should have atmosphere rules
        assert len(BIOME_ATMOSPHERE_RULES) == 10

    def test_rules_reference_valid_volumes(self):
        from blender_addon.handlers.atmospheric_volumes import BIOME_ATMOSPHERE_RULES, ATMOSPHERIC_VOLUMES

        for biome, rules in BIOME_ATMOSPHERE_RULES.items():
            for rule in rules:
                assert rule["volume"] in ATMOSPHERIC_VOLUMES, \
                    f"Biome '{biome}' references unknown volume '{rule['volume']}'"

    def test_rules_have_required_keys(self):
        from blender_addon.handlers.atmospheric_volumes import BIOME_ATMOSPHERE_RULES

        for biome, rules in BIOME_ATMOSPHERE_RULES.items():
            for rule in rules:
                assert "volume" in rule
                assert "coverage" in rule
                assert "min_count" in rule
                assert 0 <= rule["coverage"] <= 1.0


class TestComputeAtmosphericPlacements:
    """Test atmospheric placement computation."""

    def test_dark_forest_placements(self):
        from blender_addon.handlers.atmospheric_volumes import compute_atmospheric_placements

        result = compute_atmospheric_placements(
            "dark_forest", (0, 0, 100, 100), seed=42
        )
        assert len(result) > 0
        vol_types = {p["volume_type"] for p in result}
        assert "ground_fog" in vol_types

    def test_corrupted_swamp_placements(self):
        from blender_addon.handlers.atmospheric_volumes import compute_atmospheric_placements

        result = compute_atmospheric_placements(
            "corrupted_swamp", (0, 0, 200, 200), seed=42
        )
        vol_types = {p["volume_type"] for p in result}
        assert "ground_fog" in vol_types
        assert "spore_cloud" in vol_types

    def test_unknown_biome_uses_default(self):
        from blender_addon.handlers.atmospheric_volumes import compute_atmospheric_placements

        result = compute_atmospheric_placements(
            "nonexistent_biome", (0, 0, 50, 50), seed=42
        )
        assert len(result) > 0

    def test_placement_structure(self):
        from blender_addon.handlers.atmospheric_volumes import compute_atmospheric_placements

        result = compute_atmospheric_placements(
            "enchanted_glade", (0, 0, 80, 80), seed=42
        )
        for p in result:
            assert "volume_type" in p
            assert "position" in p
            assert len(p["position"]) == 3
            assert "size" in p
            assert len(p["size"]) == 3
            assert "shape" in p
            assert "color" in p
            assert "density" in p
            assert "opacity" in p
            assert "animation" in p

    def test_positions_within_bounds(self):
        from blender_addon.handlers.atmospheric_volumes import compute_atmospheric_placements

        bounds = (10, 20, 50, 60)
        result = compute_atmospheric_placements("dark_forest", bounds, seed=42)
        for p in result:
            assert bounds[0] <= p["position"][0] <= bounds[2]
            assert bounds[1] <= p["position"][1] <= bounds[3]

    def test_density_scale_increases_count(self):
        from blender_addon.handlers.atmospheric_volumes import compute_atmospheric_placements

        base = compute_atmospheric_placements(
            "dark_forest", (0, 0, 100, 100), seed=42, density_scale=1.0
        )
        scaled = compute_atmospheric_placements(
            "dark_forest", (0, 0, 100, 100), seed=42, density_scale=2.0
        )
        assert len(scaled) >= len(base)

    def test_deterministic(self):
        from blender_addon.handlers.atmospheric_volumes import compute_atmospheric_placements

        r1 = compute_atmospheric_placements("volcanic_wastes", (0, 0, 100, 100), seed=42)
        r2 = compute_atmospheric_placements("volcanic_wastes", (0, 0, 100, 100), seed=42)
        assert len(r1) == len(r2)
        for a, b in zip(r1, r2):
            assert a["volume_type"] == b["volume_type"]
            assert a["position"] == b["position"]

    def test_all_biomes_produce_volumes(self):
        from blender_addon.handlers.atmospheric_volumes import (
            compute_atmospheric_placements,
            BIOME_ATMOSPHERE_RULES,
        )

        for biome in BIOME_ATMOSPHERE_RULES:
            result = compute_atmospheric_placements(biome, (0, 0, 100, 100), seed=42)
            assert len(result) > 0, f"Biome '{biome}' produced no volumes"


class TestVolumeMeshSpec:
    """Test volume mesh specification generation."""

    def test_box_mesh_spec(self):
        from blender_addon.handlers.atmospheric_volumes import compute_volume_mesh_spec

        spec = compute_volume_mesh_spec("ground_fog")
        assert spec["shape"] == "box"
        assert len(spec["vertices"]) == 8
        assert len(spec["faces"]) == 6
        assert spec["volume_type"] == "ground_fog"

    def test_sphere_mesh_spec(self):
        from blender_addon.handlers.atmospheric_volumes import compute_volume_mesh_spec

        spec = compute_volume_mesh_spec("fireflies")
        assert spec["shape"] == "sphere"
        assert len(spec["vertices"]) == 12
        assert len(spec["faces"]) == 20

    def test_cone_mesh_spec(self):
        from blender_addon.handlers.atmospheric_volumes import compute_volume_mesh_spec

        spec = compute_volume_mesh_spec("god_rays")
        assert spec["shape"] == "cone"
        assert len(spec["vertices"]) == 9  # 1 apex + 8 base
        assert len(spec["faces"]) >= 8

    def test_custom_position_and_scale(self):
        from blender_addon.handlers.atmospheric_volumes import compute_volume_mesh_spec

        spec = compute_volume_mesh_spec(
            "ground_fog", position=(10, 20, 5), scale=2.0
        )
        assert spec["transform"]["position"] == (10, 20, 5)
        assert spec["transform"]["scale"] == 2.0

    def test_unknown_volume_raises(self):
        from blender_addon.handlers.atmospheric_volumes import compute_volume_mesh_spec

        with pytest.raises(ValueError, match="Unknown volume type"):
            compute_volume_mesh_spec("nonexistent_volume")

    def test_all_volume_types_produce_specs(self):
        from blender_addon.handlers.atmospheric_volumes import (
            compute_volume_mesh_spec,
            ATMOSPHERIC_VOLUMES,
        )

        for vol_name in ATMOSPHERIC_VOLUMES:
            spec = compute_volume_mesh_spec(vol_name)
            assert len(spec["vertices"]) > 0
            assert len(spec["faces"]) > 0


class TestAtmospherePerformance:
    """Test atmosphere performance estimation."""

    def test_empty_placements(self):
        from blender_addon.handlers.atmospheric_volumes import estimate_atmosphere_performance

        result = estimate_atmosphere_performance([])
        assert result["total_volumes"] == 0
        assert result["estimated_cost"] == 0

    def test_basic_volumes(self):
        from blender_addon.handlers.atmospheric_volumes import estimate_atmosphere_performance

        placements = [
            {"volume_type": "ground_fog"},
            {"volume_type": "ground_fog"},
        ]
        result = estimate_atmosphere_performance(placements)
        assert result["total_volumes"] == 2
        assert result["particle_volumes"] == 0
        assert result["estimated_cost"] == 2.0

    def test_particle_volumes_cost_more(self):
        from blender_addon.handlers.atmospheric_volumes import estimate_atmosphere_performance

        placements = [
            {"volume_type": "dust_motes", "particle_type": "point"},
        ]
        result = estimate_atmosphere_performance(placements, particle_cost=2.0)
        assert result["estimated_cost"] == 3.0  # 1 base + 2 particle

    def test_distortion_volumes_cost_more(self):
        from blender_addon.handlers.atmospheric_volumes import estimate_atmosphere_performance

        placements = [
            {"volume_type": "void_shimmer", "distortion": True},
        ]
        result = estimate_atmosphere_performance(placements, distortion_cost=5.0)
        assert result["estimated_cost"] == 6.0  # 1 base + 5 distortion

    def test_volume_type_counts(self):
        from blender_addon.handlers.atmospheric_volumes import estimate_atmosphere_performance

        placements = [
            {"volume_type": "ground_fog"},
            {"volume_type": "ground_fog"},
            {"volume_type": "dust_motes", "particle_type": "point"},
        ]
        result = estimate_atmosphere_performance(placements)
        counts = result["volume_type_counts"]
        assert counts["ground_fog"] == 2
        assert counts["dust_motes"] == 1

    def test_recommendation_levels(self):
        from blender_addon.handlers.atmospheric_volumes import estimate_atmosphere_performance

        # Excellent
        result = estimate_atmosphere_performance(
            [{"volume_type": "fog"}] * 5
        )
        assert result["recommendation"] == "excellent"


# ===================================================================
# Handler Registration Tests
# ===================================================================


class TestHandlerRegistration:
    """Verify all new handlers are registered in COMMAND_HANDLERS."""

    def test_world_map_handler_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "world_generate_world_map" in COMMAND_HANDLERS

    def test_light_placement_handler_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "env_compute_light_placements" in COMMAND_HANDLERS

    def test_light_merge_handler_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "env_merge_lights" in COMMAND_HANDLERS

    def test_light_budget_handler_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "env_light_budget" in COMMAND_HANDLERS

    def test_atmospheric_handler_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "env_compute_atmospheric_placements" in COMMAND_HANDLERS

    def test_volume_mesh_spec_handler_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "env_volume_mesh_spec" in COMMAND_HANDLERS

    def test_atmosphere_performance_handler_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        assert "env_atmosphere_performance" in COMMAND_HANDLERS


class TestHandlerExecution:
    """Test that registered handlers execute correctly via COMMAND_HANDLERS."""

    def test_world_map_handler_returns_dict(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        result = COMMAND_HANDLERS["world_generate_world_map"]({
            "num_regions": 3, "map_size": 500, "seed": 42, "min_pois": 10
        })
        assert isinstance(result, dict)
        assert result["num_regions"] == 3
        assert result["num_pois"] >= 10

    def test_light_placement_handler_returns_list(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        result = COMMAND_HANDLERS["env_compute_light_placements"]({
            "prop_positions": [{"type": "campfire", "position": (0, 0)}]
        })
        assert isinstance(result, list)
        assert len(result) == 1

    def test_atmospheric_handler_returns_list(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        result = COMMAND_HANDLERS["env_compute_atmospheric_placements"]({
            "biome_name": "dark_forest",
            "area_bounds": [0, 0, 100, 100],
            "seed": 42,
        })
        assert isinstance(result, list)
        assert len(result) > 0

    def test_volume_mesh_handler_returns_dict(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        result = COMMAND_HANDLERS["env_volume_mesh_spec"]({
            "volume_type": "ground_fog",
        })
        assert isinstance(result, dict)
        assert "vertices" in result

    def test_atmosphere_performance_handler(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        result = COMMAND_HANDLERS["env_atmosphere_performance"]({
            "placements": [{"volume_type": "fog"}, {"volume_type": "fog"}],
        })
        assert isinstance(result, dict)
        assert result["total_volumes"] == 2


# ===================================================================
# Import Tests
# ===================================================================


class TestImports:
    """Verify all modules import cleanly via __init__.py."""

    def test_world_map_imports(self):
        from blender_addon.handlers import (
            generate_world_map,
            place_landmarks,
            generate_storytelling_scene,
            world_map_to_dict,
            BIOME_TYPES,
            POI_TYPES,
            LANDMARK_TYPES,
            STORYTELLING_PATTERNS,
        )
        assert callable(generate_world_map)
        assert callable(place_landmarks)
        assert callable(generate_storytelling_scene)
        assert callable(world_map_to_dict)
        assert isinstance(BIOME_TYPES, dict)
        assert isinstance(POI_TYPES, dict)
        assert isinstance(LANDMARK_TYPES, dict)
        assert isinstance(STORYTELLING_PATTERNS, dict)

    def test_light_integration_imports(self):
        from blender_addon.handlers import (
            compute_light_placements,
            merge_nearby_lights,
            compute_light_budget,
            LIGHT_PROP_MAP,
            FLICKER_PRESETS,
        )
        assert callable(compute_light_placements)
        assert callable(merge_nearby_lights)
        assert callable(compute_light_budget)
        assert isinstance(LIGHT_PROP_MAP, dict)
        assert isinstance(FLICKER_PRESETS, dict)

    def test_atmospheric_volumes_imports(self):
        from blender_addon.handlers import (
            compute_atmospheric_placements,
            compute_volume_mesh_spec,
            estimate_atmosphere_performance,
            ATMOSPHERIC_VOLUMES,
            BIOME_ATMOSPHERE_RULES,
        )
        assert callable(compute_atmospheric_placements)
        assert callable(compute_volume_mesh_spec)
        assert callable(estimate_atmosphere_performance)
        assert isinstance(ATMOSPHERIC_VOLUMES, dict)
        assert isinstance(BIOME_ATMOSPHERE_RULES, dict)
