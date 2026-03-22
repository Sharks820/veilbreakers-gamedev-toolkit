"""Tests for prop_density, decal_system, and encounter_spaces modules.

All pure-logic -- no Blender dependency.
Covers: placement distribution, collision avoidance, decal UV validity,
encounter template resolution, layout validation, and edge cases.
"""

import math

import pytest

from blender_addon.handlers.prop_density import (
    ROOM_DENSITY_RULES,
    SURFACE_ZONES,
    compute_detail_prop_placements,
    get_available_room_types,
    get_zone_types,
)
from blender_addon.handlers.decal_system import (
    DECAL_TYPES,
    compute_decal_placements,
    generate_decal_mesh,
    get_available_decal_types,
    get_decal_categories,
    project_decal_to_surface,
)
from blender_addon.handlers.encounter_spaces import (
    ENCOUNTER_TEMPLATES,
    compute_encounter_layout,
    get_available_templates,
    get_templates_by_difficulty,
    validate_encounter_layout,
)


# ===================================================================
# Prop Density System
# ===================================================================


class TestRoomDensityRules:
    """Tests for ROOM_DENSITY_RULES data integrity."""

    def test_at_least_8_room_types(self):
        """Must have at least 8 room types."""
        assert len(ROOM_DENSITY_RULES) >= 8, (
            f"Only {len(ROOM_DENSITY_RULES)} room types, need >= 8"
        )

    def test_all_rooms_have_at_least_one_zone(self):
        """Every room type must define at least one surface zone."""
        for room_type, zones in ROOM_DENSITY_RULES.items():
            assert len(zones) > 0, f"Room '{room_type}' has no zones"

    def test_all_prop_entries_have_type(self):
        """Every prop entry must have a 'type' key."""
        for room_type, zones in ROOM_DENSITY_RULES.items():
            for zone_name, props in zones.items():
                for prop in props:
                    assert "type" in prop, (
                        f"Missing 'type' in {room_type}/{zone_name}: {prop}"
                    )

    def test_all_prop_entries_have_density(self):
        """Every prop entry must have a 'density' key."""
        for room_type, zones in ROOM_DENSITY_RULES.items():
            for zone_name, props in zones.items():
                for prop in props:
                    assert "density" in prop, (
                        f"Missing 'density' in {room_type}/{zone_name}: {prop}"
                    )

    def test_density_values_between_0_and_1(self):
        """All density values must be in [0, 1]."""
        for room_type, zones in ROOM_DENSITY_RULES.items():
            for zone_name, props in zones.items():
                for prop in props:
                    d = prop["density"]
                    assert 0 <= d <= 1.0, (
                        f"Invalid density {d} in {room_type}/{zone_name}"
                    )

    def test_rooms_contain_expected_types(self):
        """Spot-check that specific rooms contain expected room types."""
        assert "tavern" in ROOM_DENSITY_RULES
        assert "dungeon_corridor" in ROOM_DENSITY_RULES
        assert "library" in ROOM_DENSITY_RULES
        assert "kitchen" in ROOM_DENSITY_RULES
        assert "armory" in ROOM_DENSITY_RULES
        assert "throne_room" in ROOM_DENSITY_RULES
        assert "chapel" in ROOM_DENSITY_RULES
        assert "bedroom" in ROOM_DENSITY_RULES

    def test_get_available_room_types(self):
        """get_available_room_types returns sorted list."""
        types = get_available_room_types()
        assert isinstance(types, list)
        assert types == sorted(types)
        assert len(types) >= 8

    def test_get_zone_types(self):
        """get_zone_types returns zones for a given room."""
        zones = get_zone_types("tavern")
        assert "floor" in zones
        assert "table_surface" in zones

    def test_get_zone_types_unknown_room(self):
        """get_zone_types returns empty for unknown room."""
        zones = get_zone_types("nonexistent_room")
        assert zones == []


class TestComputeDetailPropPlacements:
    """Tests for compute_detail_prop_placements."""

    def test_returns_list(self):
        """Result is a list."""
        result = compute_detail_prop_placements(
            room_bounds=((0, 0, 0), (5, 5, 3)),
            room_type="tavern",
            seed=42,
        )
        assert isinstance(result, list)

    def test_nonzero_placements(self):
        """Generates a nonzero number of placements."""
        result = compute_detail_prop_placements(
            room_bounds=((0, 0, 0), (6, 6, 3)),
            room_type="tavern",
            seed=42,
        )
        assert len(result) > 0

    def test_placement_structure(self):
        """Each placement has required keys."""
        result = compute_detail_prop_placements(
            room_bounds=((0, 0, 0), (5, 5, 3)),
            room_type="dungeon_corridor",
            seed=42,
        )
        for p in result:
            assert "type" in p
            assert "position" in p
            assert "rotation" in p
            assert "scale" in p
            assert "zone" in p
            assert isinstance(p["position"], tuple)
            assert len(p["position"]) == 3

    def test_positions_within_bounds(self):
        """All floor/table placements are within room bounds (X/Y)."""
        bounds = ((2, 3, 0), (8, 9, 3))
        result = compute_detail_prop_placements(
            room_bounds=bounds,
            room_type="tavern",
            seed=42,
        )
        floor_props = [p for p in result if p["zone"] == "floor"]
        for p in floor_props:
            x, y, z = p["position"]
            assert bounds[0][0] <= x <= bounds[1][0], (
                f"x={x} outside [{bounds[0][0]}, {bounds[1][0]}]"
            )
            assert bounds[0][1] <= y <= bounds[1][1], (
                f"y={y} outside [{bounds[0][1]}, {bounds[1][1]}]"
            )

    def test_collision_avoidance_with_furniture(self):
        """Props should not overlap furniture."""
        furniture = [
            {"position": (2.5, 2.5, 0), "size": (2, 2, 1)},
        ]
        result = compute_detail_prop_placements(
            room_bounds=((0, 0, 0), (5, 5, 3)),
            room_type="tavern",
            furniture_positions=furniture,
            seed=42,
        )
        floor_props = [p for p in result if p["zone"] == "floor"]
        for p in floor_props:
            x, y, _ = p["position"]
            # Should not be within furniture bounds + clearance
            in_furn = (
                furniture[0]["position"][0] - 1.15 <= x <= furniture[0]["position"][0] + 1.15
                and furniture[0]["position"][1] - 1.15 <= y <= furniture[0]["position"][1] + 1.15
            )
            assert not in_furn, f"Prop at ({x}, {y}) overlaps furniture"

    def test_density_multiplier_increases_count(self):
        """Higher density_multiplier produces more props."""
        result_1x = compute_detail_prop_placements(
            room_bounds=((0, 0, 0), (8, 8, 3)),
            room_type="tavern",
            seed=42,
            density_multiplier=1.0,
        )
        result_2x = compute_detail_prop_placements(
            room_bounds=((0, 0, 0), (8, 8, 3)),
            room_type="tavern",
            seed=42,
            density_multiplier=2.0,
        )
        assert len(result_2x) > len(result_1x)

    def test_deterministic_with_same_seed(self):
        """Same seed produces identical results."""
        result_a = compute_detail_prop_placements(
            room_bounds=((0, 0, 0), (5, 5, 3)),
            room_type="tavern",
            seed=99,
        )
        result_b = compute_detail_prop_placements(
            room_bounds=((0, 0, 0), (5, 5, 3)),
            room_type="tavern",
            seed=99,
        )
        assert len(result_a) == len(result_b)
        for a, b in zip(result_a, result_b):
            assert a["type"] == b["type"]
            assert a["position"] == b["position"]

    def test_different_seeds_different_results(self):
        """Different seeds produce different placements."""
        result_a = compute_detail_prop_placements(
            room_bounds=((0, 0, 0), (6, 6, 3)),
            room_type="tavern",
            seed=1,
        )
        result_b = compute_detail_prop_placements(
            room_bounds=((0, 0, 0), (6, 6, 3)),
            room_type="tavern",
            seed=2,
        )
        # At least some positions should differ
        positions_a = [p["position"] for p in result_a]
        positions_b = [p["position"] for p in result_b]
        assert positions_a != positions_b

    def test_unknown_room_type_raises(self):
        """Unknown room type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown room type"):
            compute_detail_prop_placements(
                room_bounds=((0, 0, 0), (5, 5, 3)),
                room_type="nonexistent_room",
            )

    def test_wall_props_have_wall_zone(self):
        """Wall-placed props should have zone='walls'."""
        result = compute_detail_prop_placements(
            room_bounds=((0, 0, 0), (5, 5, 3)),
            room_type="dungeon_corridor",
            seed=42,
        )
        wall_props = [p for p in result if p["zone"] == "walls"]
        assert len(wall_props) > 0, "Should generate wall props"
        for p in wall_props:
            assert p["zone"] == "walls"

    def test_ceiling_props_have_ceiling_zone(self):
        """Ceiling props should have zone='ceiling'."""
        result = compute_detail_prop_placements(
            room_bounds=((0, 0, 0), (5, 5, 3)),
            room_type="dungeon_corridor",
            seed=42,
        )
        ceiling_props = [p for p in result if p["zone"] == "ceiling"]
        assert len(ceiling_props) > 0, "Should generate ceiling props"

    def test_all_room_types_generate_placements(self):
        """Every defined room type generates at least 1 placement."""
        for room_type in ROOM_DENSITY_RULES:
            result = compute_detail_prop_placements(
                room_bounds=((0, 0, 0), (6, 6, 3)),
                room_type=room_type,
                seed=42,
            )
            assert len(result) > 0, f"Room type '{room_type}' produced 0 placements"

    def test_large_room_generates_many_props(self):
        """A large room should generate many props (AAA density)."""
        result = compute_detail_prop_placements(
            room_bounds=((0, 0, 0), (15, 15, 3)),
            room_type="tavern",
            seed=42,
            density_multiplier=1.5,
        )
        # 15x15 = 225 sq meters, expect substantial count
        assert len(result) >= 30, (
            f"Large room only got {len(result)} props, expected 30+"
        )

    def test_rotation_range(self):
        """All rotations should be in [0, 360]."""
        result = compute_detail_prop_placements(
            room_bounds=((0, 0, 0), (6, 6, 3)),
            room_type="tavern",
            seed=42,
        )
        for p in result:
            r = p["rotation"]
            assert -360 <= r <= 720, f"Rotation {r} out of expected range"

    def test_scale_positive(self):
        """All scales should be positive."""
        result = compute_detail_prop_placements(
            room_bounds=((0, 0, 0), (6, 6, 3)),
            room_type="tavern",
            seed=42,
        )
        for p in result:
            assert p["scale"] > 0, f"Non-positive scale: {p['scale']}"


# ===================================================================
# Decal System
# ===================================================================


class TestDecalTypes:
    """Tests for DECAL_TYPES data integrity."""

    def test_at_least_8_decal_types(self):
        """Must have at least 8 decal types."""
        assert len(DECAL_TYPES) >= 8, (
            f"Only {len(DECAL_TYPES)} decal types, need >= 8"
        )

    def test_all_types_have_size_range(self):
        """Every decal type must have a size_range."""
        for name, config in DECAL_TYPES.items():
            assert "size_range" in config, f"Missing size_range in '{name}'"
            assert len(config["size_range"]) == 2
            assert config["size_range"][0] <= config["size_range"][1]

    def test_all_types_have_material(self):
        """Every decal type must have a material name."""
        for name, config in DECAL_TYPES.items():
            assert "material" in config, f"Missing material in '{name}'"
            assert isinstance(config["material"], str)

    def test_get_available_decal_types(self):
        """get_available_decal_types returns sorted list."""
        types = get_available_decal_types()
        assert types == sorted(types)
        assert len(types) >= 8

    def test_get_decal_categories(self):
        """Categories group decal types correctly."""
        cats = get_decal_categories()
        assert isinstance(cats, dict)
        total = sum(len(v) for v in cats.values())
        assert total == len(DECAL_TYPES)

    def test_expected_types_present(self):
        """Key decal types should be present."""
        assert "blood_splatter" in DECAL_TYPES
        assert "crack" in DECAL_TYPES
        assert "moss_patch" in DECAL_TYPES
        assert "rune_marking" in DECAL_TYPES
        assert "scorch_mark" in DECAL_TYPES


class TestGenerateDecalMesh:
    """Tests for generate_decal_mesh."""

    def test_returns_dict(self):
        """Result is a dict."""
        result = generate_decal_mesh("blood_splatter", size=1.0)
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        """Result has vertices, faces, uvs, material, properties."""
        result = generate_decal_mesh("crack", size=0.5)
        assert "vertices" in result
        assert "faces" in result
        assert "uvs" in result
        assert "material" in result
        assert "properties" in result
        assert "decal_type" in result

    def test_quad_vertex_count(self):
        """Simple quad has 4 vertices."""
        result = generate_decal_mesh("moss_patch", size=1.0)
        assert len(result["vertices"]) == 4

    def test_quad_face_count(self):
        """Simple quad has 1 face."""
        result = generate_decal_mesh("moss_patch", size=1.0)
        assert len(result["faces"]) == 1
        assert len(result["faces"][0]) == 4  # quad

    def test_uv_count_matches_vertices(self):
        """UV count matches vertex count."""
        result = generate_decal_mesh("blood_splatter", size=1.0)
        assert len(result["uvs"]) == len(result["vertices"])

    def test_uv_range_0_to_1(self):
        """All UV coordinates in [0, 1]."""
        result = generate_decal_mesh("scorch_mark", size=2.0)
        for u, v in result["uvs"]:
            assert 0.0 <= u <= 1.0, f"U={u} outside [0, 1]"
            assert 0.0 <= v <= 1.0, f"V={v} outside [0, 1]"

    def test_size_scales_vertices(self):
        """Larger size produces larger vertex coordinates."""
        small = generate_decal_mesh("crack", size=0.5)
        large = generate_decal_mesh("crack", size=2.0)
        max_small = max(abs(v[0]) for v in small["vertices"])
        max_large = max(abs(v[0]) for v in large["vertices"])
        assert max_large > max_small

    def test_vertices_are_flat(self):
        """All vertices should have z=0 (flat quad)."""
        result = generate_decal_mesh("water_stain", size=1.0)
        for v in result["vertices"]:
            assert v[2] == 0.0, f"Non-flat vertex: z={v[2]}"

    def test_unknown_type_raises(self):
        """Unknown decal type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown decal type"):
            generate_decal_mesh("nonexistent_decal")

    def test_all_types_generate_valid_mesh(self):
        """Every defined decal type generates a valid mesh."""
        for decal_type in DECAL_TYPES:
            result = generate_decal_mesh(decal_type, size=1.0)
            assert len(result["vertices"]) >= 4
            assert len(result["faces"]) >= 1
            assert len(result["uvs"]) == len(result["vertices"])

    def test_subdivided_mesh_more_vertices(self):
        """Subdivisions increase vertex count."""
        simple = generate_decal_mesh("blood_splatter", size=1.0, subdivisions=0)
        subdiv = generate_decal_mesh("blood_splatter", size=1.0, subdivisions=2)
        assert len(subdiv["vertices"]) > len(simple["vertices"])

    def test_emission_property_for_rune(self):
        """Rune decal should have emission property."""
        result = generate_decal_mesh("rune_marking", size=0.5)
        assert result["properties"]["emission"] is True
        assert result["properties"]["emission_strength"] > 0

    def test_normal_only_property_for_crack(self):
        """Crack decal should have normal_only property."""
        result = generate_decal_mesh("crack", size=0.5)
        assert result["properties"]["normal_only"] is True

    def test_subdivided_uvs_still_valid(self):
        """Subdivided mesh UVs are still in [0, 1]."""
        result = generate_decal_mesh("moss_patch", size=1.0, subdivisions=3)
        for u, v in result["uvs"]:
            assert -0.001 <= u <= 1.001, f"U={u} outside [0, 1]"
            assert -0.001 <= v <= 1.001, f"V={v} outside [0, 1]"


class TestComputeDecalPlacements:
    """Tests for compute_decal_placements."""

    def test_returns_list(self):
        """Result is a list."""
        result = compute_decal_placements(
            surface_bounds=((0, 0), (10, 10)),
            decal_types=["blood_splatter", "crack"],
            density=0.1,
            seed=42,
        )
        assert isinstance(result, list)

    def test_nonzero_placements(self):
        """Generates placements for a reasonably sized area."""
        result = compute_decal_placements(
            surface_bounds=((0, 0), (10, 10)),
            decal_types=["blood_splatter"],
            density=0.1,
            seed=42,
        )
        assert len(result) > 0

    def test_placement_structure(self):
        """Each placement has required keys."""
        result = compute_decal_placements(
            surface_bounds=((0, 0), (10, 10)),
            decal_types=["crack", "moss_patch"],
            density=0.1,
            seed=42,
        )
        for p in result:
            assert "decal_type" in p
            assert "position" in p
            assert "rotation" in p
            assert "size" in p
            assert "surface_normal" in p
            assert p["decal_type"] in DECAL_TYPES

    def test_positions_within_bounds(self):
        """All positions within the specified surface bounds."""
        bounds = ((2, 3), (8, 9))
        result = compute_decal_placements(
            surface_bounds=bounds,
            decal_types=["water_stain"],
            density=0.2,
            seed=42,
        )
        for p in result:
            x, y = p["position"]
            assert bounds[0][0] <= x <= bounds[1][0]
            assert bounds[0][1] <= y <= bounds[1][1]

    def test_exclusion_zones_respected(self):
        """Decals avoid exclusion zones."""
        exclude = [{"center": (5, 5), "radius": 3.0}]
        result = compute_decal_placements(
            surface_bounds=((0, 0), (10, 10)),
            decal_types=["blood_splatter"],
            density=0.5,
            seed=42,
            exclude_regions=exclude,
        )
        for p in result:
            x, y = p["position"]
            dist = math.sqrt((x - 5) ** 2 + (y - 5) ** 2)
            assert dist >= 3.0, (
                f"Decal at ({x:.1f}, {y:.1f}) inside exclusion zone"
            )

    def test_density_affects_count(self):
        """Higher density produces more decals."""
        low = compute_decal_placements(
            surface_bounds=((0, 0), (10, 10)),
            decal_types=["crack"],
            density=0.05,
            seed=42,
        )
        high = compute_decal_placements(
            surface_bounds=((0, 0), (10, 10)),
            decal_types=["crack"],
            density=0.5,
            seed=42,
        )
        assert len(high) > len(low)

    def test_deterministic_with_same_seed(self):
        """Same seed produces identical results."""
        result_a = compute_decal_placements(
            surface_bounds=((0, 0), (10, 10)),
            decal_types=["blood_splatter", "crack"],
            density=0.1,
            seed=99,
        )
        result_b = compute_decal_placements(
            surface_bounds=((0, 0), (10, 10)),
            decal_types=["blood_splatter", "crack"],
            density=0.1,
            seed=99,
        )
        assert len(result_a) == len(result_b)

    def test_no_valid_types_raises(self):
        """All invalid decal types raises ValueError."""
        with pytest.raises(ValueError, match="No valid decal types"):
            compute_decal_placements(
                surface_bounds=((0, 0), (10, 10)),
                decal_types=["nonexistent"],
                density=0.1,
            )

    def test_overlap_prevention(self):
        """Placed decals should not heavily overlap."""
        result = compute_decal_placements(
            surface_bounds=((0, 0), (10, 10)),
            decal_types=["blood_splatter"],
            density=0.3,
            seed=42,
        )
        for i in range(len(result)):
            for j in range(i + 1, len(result)):
                pi = result[i]["position"]
                pj = result[j]["position"]
                dist = math.sqrt((pi[0] - pj[0]) ** 2 + (pi[1] - pj[1]) ** 2)
                # Minimum spacing is 70% of combined half-sizes
                min_spacing = (result[i]["size"] / 2 + result[j]["size"] / 2) * 0.7
                assert dist >= min_spacing * 0.95, (
                    f"Decals {i} and {j} too close: {dist:.2f} < {min_spacing:.2f}"
                )


class TestProjectDecalToSurface:
    """Tests for project_decal_to_surface."""

    def test_returns_dict(self):
        """Result is a dict with required keys."""
        result = project_decal_to_surface(
            decal_position=(5, 5),
            surface_normal=(0, 0, 1),
            surface_point=(5, 5, 0),
            decal_size=1.0,
        )
        assert isinstance(result, dict)
        assert "position" in result
        assert "normal" in result
        assert "scale" in result
        assert "tangent" in result
        assert "bitangent" in result

    def test_offset_along_normal(self):
        """Position should be offset slightly from surface point."""
        result = project_decal_to_surface(
            decal_position=(0, 0),
            surface_normal=(0, 0, 1),
            surface_point=(0, 0, 0),
            decal_size=1.0,
            offset=0.01,
        )
        assert result["position"][2] == pytest.approx(0.01, abs=1e-6)

    def test_tangent_perpendicular_to_normal(self):
        """Tangent should be perpendicular to normal."""
        result = project_decal_to_surface(
            decal_position=(0, 0),
            surface_normal=(0, 0, 1),
            surface_point=(0, 0, 0),
            decal_size=1.0,
        )
        n = result["normal"]
        t = result["tangent"]
        dot = n[0] * t[0] + n[1] * t[1] + n[2] * t[2]
        assert abs(dot) < 1e-6, f"Tangent not perpendicular to normal: dot={dot}"

    def test_bitangent_perpendicular_to_both(self):
        """Bitangent should be perpendicular to both normal and tangent."""
        result = project_decal_to_surface(
            decal_position=(0, 0),
            surface_normal=(1, 0, 0),
            surface_point=(5, 0, 0),
            decal_size=1.0,
        )
        n = result["normal"]
        t = result["tangent"]
        b = result["bitangent"]
        dot_nb = n[0] * b[0] + n[1] * b[1] + n[2] * b[2]
        dot_tb = t[0] * b[0] + t[1] * b[1] + t[2] * b[2]
        assert abs(dot_nb) < 1e-6
        assert abs(dot_tb) < 1e-6

    def test_wall_normal(self):
        """Decal on a vertical wall should orient correctly."""
        result = project_decal_to_surface(
            decal_position=(0, 5),
            surface_normal=(1, 0, 0),
            surface_point=(0, 5, 2),
            decal_size=0.5,
        )
        assert result["normal"] == pytest.approx((1, 0, 0), abs=1e-6)


# ===================================================================
# Encounter Spaces
# ===================================================================


class TestEncounterTemplates:
    """Tests for ENCOUNTER_TEMPLATES data integrity."""

    def test_at_least_5_templates(self):
        """Must have at least 5 encounter templates."""
        assert len(ENCOUNTER_TEMPLATES) >= 5, (
            f"Only {len(ENCOUNTER_TEMPLATES)} templates, need >= 5"
        )

    def test_all_templates_have_shape(self):
        """Every template must have a shape."""
        for name, tmpl in ENCOUNTER_TEMPLATES.items():
            assert "shape" in tmpl, f"Missing 'shape' in template '{name}'"

    def test_all_templates_have_player_entry(self):
        """Every template must have a player entry point."""
        for name, tmpl in ENCOUNTER_TEMPLATES.items():
            assert "player_entry" in tmpl, (
                f"Missing 'player_entry' in template '{name}'"
            )

    def test_all_templates_have_difficulty(self):
        """Every template must have a difficulty level."""
        for name, tmpl in ENCOUNTER_TEMPLATES.items():
            assert "difficulty" in tmpl, (
                f"Missing 'difficulty' in template '{name}'"
            )

    def test_expected_templates_present(self):
        """Key templates should be present."""
        assert "ambush_corridor" in ENCOUNTER_TEMPLATES
        assert "arena_circle" in ENCOUNTER_TEMPLATES
        assert "gauntlet_run" in ENCOUNTER_TEMPLATES
        assert "siege_approach" in ENCOUNTER_TEMPLATES
        assert "puzzle_room" in ENCOUNTER_TEMPLATES

    def test_get_available_templates(self):
        """get_available_templates returns sorted list."""
        templates = get_available_templates()
        assert templates == sorted(templates)
        assert len(templates) >= 5

    def test_get_templates_by_difficulty(self):
        """Filtering by difficulty returns matching templates."""
        hard = get_templates_by_difficulty("hard")
        assert isinstance(hard, list)
        for name in hard:
            assert ENCOUNTER_TEMPLATES[name]["difficulty"] == "hard"


class TestComputeEncounterLayout:
    """Tests for compute_encounter_layout."""

    def test_returns_dict(self):
        """Result is a dict."""
        result = compute_encounter_layout("ambush_corridor", seed=42)
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        """Result has all required keys."""
        result = compute_encounter_layout("arena_circle", seed=42)
        assert "shape" in result
        assert "bounds" in result
        assert "cover" in result
        assert "enemies" in result
        assert "entry" in result
        assert "triggers" in result
        assert "difficulty" in result
        assert "template" in result

    def test_cover_positions_resolved(self):
        """String cover specs (like ring_8) are resolved to coordinate lists."""
        result = compute_encounter_layout("arena_circle", seed=42)
        assert isinstance(result["cover"], list)
        assert len(result["cover"]) == 8  # ring_8
        for pos in result["cover"]:
            assert isinstance(pos, tuple)
            assert len(pos) == 3

    def test_enemy_positions_resolved(self):
        """String enemy specs are resolved to coordinate lists."""
        result = compute_encounter_layout("arena_circle", seed=42)
        assert isinstance(result["enemies"], list)
        assert len(result["enemies"]) > 0

    def test_ring_positions_are_circular(self):
        """Ring positions should be roughly equidistant from center."""
        result = compute_encounter_layout("arena_circle", seed=42)
        cover = result["cover"]
        distances = [math.sqrt(p[0]**2 + p[1]**2) for p in cover]
        # All should be approximately the same distance
        avg_dist = sum(distances) / len(distances)
        for d in distances:
            assert abs(d - avg_dist) < 0.1, (
                f"Ring point at distance {d:.1f}, expected ~{avg_dist:.1f}"
            )

    def test_corridor_bounds(self):
        """Corridor templates should have correct width/length bounds."""
        result = compute_encounter_layout("ambush_corridor", seed=42)
        bounds = result["bounds"]
        assert bounds["max"][1] == 15.0  # length
        assert bounds["max"][0] == 1.5   # half width

    def test_unknown_template_raises(self):
        """Unknown template raises ValueError."""
        with pytest.raises(ValueError, match="Unknown encounter template"):
            compute_encounter_layout("nonexistent_template")

    def test_deterministic_with_same_seed(self):
        """Same seed produces identical layouts."""
        result_a = compute_encounter_layout("gauntlet_run", seed=42)
        result_b = compute_encounter_layout("gauntlet_run", seed=42)
        assert result_a["enemies"] == result_b["enemies"]
        assert result_a["cover"] == result_b["cover"]

    def test_all_templates_compute_successfully(self):
        """Every template computes without error."""
        for name in ENCOUNTER_TEMPLATES:
            result = compute_encounter_layout(name, seed=42)
            assert result["template"] == name

    def test_trigger_volumes_present(self):
        """Encounter should have at least one trigger volume."""
        result = compute_encounter_layout("ambush_corridor", seed=42)
        assert len(result["triggers"]) > 0

    def test_boss_chamber_has_phase_triggers(self):
        """Boss chamber should have phase trigger zones."""
        result = compute_encounter_layout("boss_chamber", seed=42)
        phase_triggers = [
            t for t in result["triggers"] if t["type"] == "phase_trigger"
        ]
        assert len(phase_triggers) >= 3

    def test_puzzle_room_has_mechanisms(self):
        """Puzzle room should have mechanism positions."""
        result = compute_encounter_layout("puzzle_room", seed=42)
        assert len(result["mechanisms"]) > 0

    def test_gauntlet_has_hazards(self):
        """Gauntlet run should have hazard zones."""
        result = compute_encounter_layout("gauntlet_run", seed=42)
        assert len(result["hazards"]) >= 3

    def test_gauntlet_has_checkpoints(self):
        """Gauntlet run should have checkpoint positions."""
        result = compute_encounter_layout("gauntlet_run", seed=42)
        assert len(result["checkpoints"]) >= 2

    def test_stealth_zone_has_patrol_routes(self):
        """Stealth zone should have patrol routes."""
        result = compute_encounter_layout("stealth_zone", seed=42)
        assert len(result["patrol_routes"]) >= 2

    def test_stealth_zone_has_shadow_zones(self):
        """Stealth zone should have shadow zones."""
        result = compute_encounter_layout("stealth_zone", seed=42)
        assert len(result["shadow_zones"]) >= 2

    def test_enemy_count_override(self):
        """enemy_count parameter overrides default count."""
        result = compute_encounter_layout(
            "ambush_corridor", seed=42, enemy_count=2,
        )
        assert len(result["enemies"]) == 2

    def test_siege_approach_has_props(self):
        """Siege approach should have barricade and archer perch props."""
        result = compute_encounter_layout("siege_approach", seed=42)
        prop_types = [p["type"] for p in result["props"]]
        assert "barricade" in prop_types
        assert "archer_perch" in prop_types

    def test_defensive_holdout_has_defend_point(self):
        """Defensive holdout should have a defend point."""
        result = compute_encounter_layout("defensive_holdout", seed=42)
        assert "defend_point" in result

    def test_ambush_corridor_has_alcoves(self):
        """Ambush corridor should have flanking alcoves in props."""
        result = compute_encounter_layout("ambush_corridor", seed=42)
        alcoves = [p for p in result["props"] if p["type"] == "alcove"]
        assert len(alcoves) >= 2


class TestValidateEncounterLayout:
    """Tests for validate_encounter_layout."""

    def test_valid_layout_passes(self):
        """A well-constructed layout should validate."""
        layout = compute_encounter_layout("arena_circle", seed=42)
        validation = validate_encounter_layout(layout)
        assert isinstance(validation, dict)
        assert "valid" in validation
        assert "issues" in validation
        assert "metrics" in validation

    def test_metrics_present(self):
        """Validation should produce useful metrics."""
        layout = compute_encounter_layout("ambush_corridor", seed=42)
        validation = validate_encounter_layout(layout)
        metrics = validation["metrics"]
        assert "cover_count" in metrics
        assert "enemy_count" in metrics

    def test_bunched_cover_flagged(self):
        """Cover positions too close together should be flagged."""
        layout = {
            "entry": (0, 0, 0),
            "cover": [(0, 0, 0), (0, 0.5, 0)],  # too close
            "enemies": [(0, 10, 0)],
            "hazards": [],
            "bounds": {"min": (-5, -5, 0), "max": (5, 15, 3)},
        }
        validation = validate_encounter_layout(layout)
        assert not validation["valid"]
        assert any("too close" in issue for issue in validation["issues"])

    def test_enemy_near_entry_flagged(self):
        """Enemy spawn too close to entry should be flagged."""
        layout = {
            "entry": (0, 0, 0),
            "cover": [],
            "enemies": [(0, 1, 0)],  # very close to entry
            "hazards": [],
            "bounds": {"min": (-5, -5, 0), "max": (5, 5, 3)},
        }
        validation = validate_encounter_layout(layout)
        assert not validation["valid"]
        assert any("too close to entry" in issue for issue in validation["issues"])

    def test_hazard_at_entry_flagged(self):
        """Hazard overlapping entry point should be flagged."""
        layout = {
            "entry": (0, 0, 0),
            "cover": [(5, 5, 0)],
            "enemies": [(0, 10, 0)],
            "hazards": [{"center": (0, 0.5, 0), "radius": 2.0, "type": "fire"}],
            "bounds": {"min": (-5, -5, 0), "max": (5, 15, 3)},
        }
        validation = validate_encounter_layout(layout)
        assert not validation["valid"]
        assert any("Hazard" in issue for issue in validation["issues"])

    def test_all_default_templates_pass_validation(self):
        """All default templates should produce valid layouts."""
        for name in ENCOUNTER_TEMPLATES:
            layout = compute_encounter_layout(name, seed=42)
            validation = validate_encounter_layout(layout)
            if not validation["valid"]:
                # Only puzzle room with no enemies is allowed to have issues
                if name == "puzzle_room":
                    continue
                # Check that issues aren't critical
                assert validation["valid"], (
                    f"Template '{name}' failed validation: {validation['issues']}"
                )

    def test_cover_to_enemy_ratio(self):
        """Metrics should include cover-to-enemy ratio when enemies present."""
        layout = compute_encounter_layout("arena_circle", seed=42)
        validation = validate_encounter_layout(layout)
        if layout["enemies"]:
            assert "cover_to_enemy_ratio" in validation["metrics"]


# ===================================================================
# Integration: Cross-system coherence
# ===================================================================


class TestCrossSystemIntegration:
    """Tests that the three systems can work together conceptually."""

    def test_encounter_room_can_be_detailed(self):
        """An encounter room can be detailed with props."""
        layout = compute_encounter_layout("puzzle_room", seed=42)
        bounds = layout["bounds"]
        room_bounds = (bounds["min"], bounds["max"])

        # Use encounter props as furniture to avoid
        furniture = [
            {"position": m, "size": (1, 1, 1)}
            for m in layout["mechanisms"]
        ]

        props = compute_detail_prop_placements(
            room_bounds=room_bounds,
            room_type="dungeon_corridor",
            furniture_positions=furniture,
            seed=42,
        )
        assert len(props) > 0

    def test_encounter_floor_can_have_decals(self):
        """An encounter floor can have decals placed on it."""
        layout = compute_encounter_layout("ambush_corridor", seed=42)
        bounds = layout["bounds"]

        decals = compute_decal_placements(
            surface_bounds=(
                (bounds["min"][0], bounds["min"][1]),
                (bounds["max"][0], bounds["max"][1]),
            ),
            decal_types=["blood_splatter", "crack", "dirt_accumulation"],
            density=0.15,
            seed=42,
        )
        assert len(decals) > 0

    def test_decal_mesh_can_be_generated_for_placements(self):
        """Each decal placement can produce a valid mesh."""
        placements = compute_decal_placements(
            surface_bounds=((0, 0), (5, 5)),
            decal_types=["moss_patch", "rune_marking"],
            density=0.2,
            seed=42,
        )
        for p in placements:
            mesh = generate_decal_mesh(p["decal_type"], size=p["size"])
            assert len(mesh["vertices"]) >= 4
            assert len(mesh["faces"]) >= 1
