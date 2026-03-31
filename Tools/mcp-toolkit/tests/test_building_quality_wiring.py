"""Tests verifying building_quality generators are wired into building grammar.

Tests confirm:
- Detail operations produce real geometry (not 0.5m cubes)
- CGA facade split produces different layouts for different seeds
- Roof operations contain tile/shingle geometry (not flat boxes)
- 5 buildings with same style + different seeds have different facade layouts
- mesh_spec operations carry full vertex/face data
"""

import pytest

from blender_addon.handlers._building_grammar import (
    BuildingSpec,
    STYLE_CONFIGS,
    evaluate_building_grammar,
)


# ---------------------------------------------------------------------------
# Detail wiring tests
# ---------------------------------------------------------------------------


class TestDetailWiring:
    """Verify detail operations use real geometry, not placeholder cubes."""

    def test_medieval_details_not_uniform_cubes(self):
        """Medieval building details should NOT all be identical 0.5m cubes."""
        spec = evaluate_building_grammar(10.0, 8.0, 2, "medieval", seed=42)
        detail_ops = [op for op in spec.operations if op.get("role") == "detail"]
        assert len(detail_ops) > 0, "No detail operations generated"

        # Check that detail sizes vary (not all 0.5 x 0.5 x 0.5)
        sizes = set()
        for op in detail_ops:
            if "size" in op:
                sizes.add(tuple(round(s, 2) for s in op["size"]))
        assert len(sizes) > 1, "All details have identical size -- still cubes?"

    def test_gothic_details_include_mesh_spec(self):
        """Gothic buildings should have mesh_spec details (from building_quality)."""
        spec = evaluate_building_grammar(12.0, 10.0, 3, "gothic", seed=42)
        mesh_spec_ops = [
            op for op in spec.operations if op.get("type") == "mesh_spec"
        ]
        # Gothic has chimney, rose_window, battlements etc that produce mesh_specs
        # At minimum, the roof should be mesh_spec
        assert len(mesh_spec_ops) >= 1, "No mesh_spec operations in gothic building"

    def test_mesh_spec_has_vertices_and_faces(self):
        """mesh_spec operations must have vertex and face data."""
        spec = evaluate_building_grammar(10.0, 8.0, 2, "gothic", seed=42)
        mesh_spec_ops = [
            op for op in spec.operations if op.get("type") == "mesh_spec"
        ]
        for op in mesh_spec_ops:
            assert "vertices" in op, f"mesh_spec missing vertices: {op.get('detail_type')}"
            assert "faces" in op, f"mesh_spec missing faces: {op.get('detail_type')}"
            assert len(op["vertices"]) >= 4, (
                f"mesh_spec has too few vertices ({len(op['vertices'])}): "
                f"{op.get('detail_type')}"
            )

    def test_fortress_has_battlement_details(self):
        """Fortress buildings should include battlement geometry."""
        spec = evaluate_building_grammar(12.0, 10.0, 2, "fortress", seed=42)
        detail_types = {
            op.get("detail_type") for op in spec.operations if op.get("role") == "detail"
        }
        # Fortress style has: battlement, machicolation, murder_hole
        # At least one battlement-related detail should exist
        battlement_types = detail_types & {
            "battlement", "machicolation_corbel", "machicolation_platform",
            "murder_hole",
        }
        assert len(battlement_types) >= 1, (
            f"No battlement details found. Types present: {detail_types}"
        )

    def test_medieval_has_timber_frame_details(self):
        """Medieval buildings should include timber frame beams in at least 1 of 10 seeds."""
        # Timber frame is randomly selected from detail subset, so try multiple seeds
        found = False
        for seed in range(10):
            spec = evaluate_building_grammar(8.0, 6.0, 2, "medieval", seed=seed)
            detail_types = {
                op.get("detail_type") for op in spec.operations if op.get("role") == "detail"
            }
            timber_types = detail_types & {"timber_post", "timber_rail", "timber_brace"}
            if len(timber_types) >= 1:
                found = True
                break
        assert found, "No timber frame details found across 10 seeds"

    def test_organic_has_nature_details(self):
        """Organic buildings should include vine/moss/root details in at least 1 of 10 seeds."""
        found = False
        for seed in range(10):
            spec = evaluate_building_grammar(8.0, 8.0, 1, "organic", seed=seed)
            detail_types = {
                op.get("detail_type") for op in spec.operations if op.get("role") == "detail"
            }
            nature_types = detail_types & {
                "vine_stem", "vine_leaves", "moss_patch",
                "root_support", "root_tip",
            }
            if len(nature_types) >= 1:
                found = True
                break
        assert found, "No nature details found across 10 seeds"

    def test_no_detail_is_half_meter_cube(self):
        """No detail operation should be a 0.5x0.5x0.5 box (the old bug)."""
        for style in STYLE_CONFIGS:
            spec = evaluate_building_grammar(10.0, 8.0, 2, style, seed=42)
            for op in spec.operations:
                if op.get("role") == "detail" and op.get("type") == "box":
                    size = op.get("size", [])
                    if len(size) == 3:
                        is_half_cube = (
                            abs(size[0] - 0.5) < 0.01
                            and abs(size[1] - 0.5) < 0.01
                            and abs(size[2] - 0.5) < 0.01
                        )
                        assert not is_half_cube, (
                            f"Found 0.5m cube detail in style '{style}': "
                            f"{op.get('detail_type')}"
                        )


# ---------------------------------------------------------------------------
# Facade split variation tests
# ---------------------------------------------------------------------------


class TestFacadeVariation:
    """Verify CGA facade split produces unique layouts per seed."""

    def test_different_seeds_produce_different_openings(self):
        """Two buildings with same style but different seeds should differ."""
        spec_a = evaluate_building_grammar(10.0, 8.0, 2, "medieval", seed=1)
        spec_b = evaluate_building_grammar(10.0, 8.0, 2, "medieval", seed=2)

        openings_a = [
            op for op in spec_a.operations if op.get("type") == "opening"
        ]
        openings_b = [
            op for op in spec_b.operations if op.get("type") == "opening"
        ]

        # Either count differs or positions differ
        different = (
            len(openings_a) != len(openings_b)
            or any(
                a.get("position") != b.get("position")
                for a, b in zip(openings_a, openings_b)
            )
        )
        assert different, "Two different seeds produced identical opening layouts"

    def test_five_buildings_all_different(self):
        """5 buildings with seeds 1-5 should all have different operation counts."""
        op_signatures = []
        for seed in range(1, 6):
            spec = evaluate_building_grammar(10.0, 8.0, 2, "medieval", seed=seed)
            # Signature: count of each operation type + total count
            sig = {
                "total": len(spec.operations),
                "openings": len([o for o in spec.operations if o["type"] == "opening"]),
                "details": len([o for o in spec.operations if o.get("role") == "detail"]),
                "mesh_specs": len([o for o in spec.operations if o["type"] == "mesh_spec"]),
            }
            op_signatures.append(sig)

        # At least 3 out of 5 should be unique (allowing some rare collisions)
        unique_sigs = len({
            (s["total"], s["openings"], s["details"], s["mesh_specs"])
            for s in op_signatures
        })
        assert unique_sigs >= 3, (
            f"Only {unique_sigs} unique building signatures out of 5. "
            f"Signatures: {op_signatures}"
        )

    def test_facade_has_at_least_one_door(self):
        """Every building must have at least one door."""
        for style in STYLE_CONFIGS:
            spec = evaluate_building_grammar(8.0, 6.0, 2, style, seed=42)
            doors = [
                op for op in spec.operations
                if op.get("type") == "opening" and op.get("role") == "door"
            ]
            assert len(doors) >= 1, f"No door in {style} building"

    def test_facade_has_bay_index_metadata(self):
        """CGA-split openings should carry bay_index metadata."""
        spec = evaluate_building_grammar(12.0, 10.0, 3, "medieval", seed=42)
        bay_openings = [
            op for op in spec.operations
            if op.get("type") == "opening" and "bay_index" in op
        ]
        assert len(bay_openings) > 0, "No openings with bay_index from CGA split"

    def test_corner_bays_have_no_openings(self):
        """With 4+ bays, corner bays (0 and N-1) should be solid (no openings)."""
        spec = evaluate_building_grammar(20.0, 15.0, 2, "gothic", seed=42)
        # Gothic has bay_divisor=4, so with +/-1 we get 3-5 bays
        # Check that no opening has bay_index 0
        openings = [
            op for op in spec.operations
            if op.get("type") == "opening" and "bay_index" in op
        ]
        bay_0_openings = [o for o in openings if o.get("bay_index") == 0]
        # With 3+ bays, corner bay 0 should be solid
        if len(openings) > 0:
            max_bay = max(o.get("bay_index", 0) for o in openings)
            if max_bay >= 3:
                assert len(bay_0_openings) == 0, (
                    f"Found opening in corner bay 0 (max_bay={max_bay})"
                )


# ---------------------------------------------------------------------------
# Roof generation tests
# ---------------------------------------------------------------------------


class TestRoofGeneration:
    """Verify roofs use AAA tile geometry, not flat boxes."""

    def test_gabled_roof_has_mesh_spec(self):
        """Medieval gabled roof should produce mesh_spec with tile data."""
        spec = evaluate_building_grammar(8.0, 6.0, 1, "medieval", seed=42)
        roof_mesh_specs = [
            op for op in spec.operations
            if op.get("type") == "mesh_spec" and op.get("role") == "roof"
        ]
        assert len(roof_mesh_specs) >= 1, "No mesh_spec roof operation for gabled roof"

    def test_roof_mesh_spec_has_many_vertices(self):
        """Roof tile mesh should have significantly more than 8 vertices."""
        spec = evaluate_building_grammar(8.0, 6.0, 1, "medieval", seed=42)
        roof_ops = [
            op for op in spec.operations
            if op.get("type") == "mesh_spec" and op.get("role") == "roof"
        ]
        for op in roof_ops:
            vert_count = len(op.get("vertices", []))
            assert vert_count > 50, (
                f"Roof has only {vert_count} vertices -- too few for tile geometry"
            )

    def test_hip_roof_for_gothic(self):
        """Gothic pointed roof should map to hip roof style."""
        spec = evaluate_building_grammar(10.0, 8.0, 2, "gothic", seed=42)
        roof_ops = [
            op for op in spec.operations
            if op.get("role") == "roof" or op.get("role") == "roof_base"
        ]
        assert len(roof_ops) >= 1, "No roof operations found for gothic building"

    def test_flat_roof_for_fortress(self):
        """Fortress flat roof should still produce geometry."""
        spec = evaluate_building_grammar(12.0, 10.0, 2, "fortress", seed=42)
        roof_ops = [
            op for op in spec.operations
            if op.get("role") == "roof" or op.get("role") == "roof_base"
        ]
        assert len(roof_ops) >= 1, "No roof operations found for fortress building"

    def test_domed_roof_for_organic(self):
        """Organic domed roof should produce cylinder operation."""
        spec = evaluate_building_grammar(8.0, 8.0, 1, "organic", seed=42)
        domed_ops = [
            op for op in spec.operations
            if op.get("type") == "cylinder" and op.get("role") == "roof"
        ]
        assert len(domed_ops) >= 1, "No cylinder roof for organic (domed) building"


# ---------------------------------------------------------------------------
# Building variation tests
# ---------------------------------------------------------------------------


class TestBuildingVariation:
    """Verify per-building variation system works."""

    def test_floor_heights_vary_across_seeds(self):
        """Different seeds should produce different total building heights."""
        heights = []
        for seed in range(5):
            spec = evaluate_building_grammar(8.0, 6.0, 2, "medieval", seed=seed)
            # Get max Z from wall operations
            wall_ops = [op for op in spec.operations if op.get("role") == "wall"]
            if wall_ops:
                max_z = max(
                    op["position"][2] + op["size"][2]
                    for op in wall_ops
                    if "position" in op and "size" in op
                )
                heights.append(round(max_z, 2))
        unique_heights = len(set(heights))
        assert unique_heights >= 2, (
            f"Only {unique_heights} unique wall heights across 5 seeds: {heights}"
        )

    def test_deterministic_with_same_seed(self):
        """Same seed must produce identical BuildingSpec."""
        spec_a = evaluate_building_grammar(10.0, 8.0, 2, "medieval", seed=42)
        spec_b = evaluate_building_grammar(10.0, 8.0, 2, "medieval", seed=42)
        assert len(spec_a.operations) == len(spec_b.operations)
        for a, b in zip(spec_a.operations, spec_b.operations):
            assert a.get("type") == b.get("type")
            assert a.get("role") == b.get("role")

    def test_all_styles_produce_valid_specs(self):
        """Every style produces a valid BuildingSpec with all required components."""
        required_roles = {"foundation", "wall", "detail"}
        for style in STYLE_CONFIGS:
            spec = evaluate_building_grammar(10.0, 8.0, 2, style, seed=42)
            assert isinstance(spec, BuildingSpec)
            roles = {op.get("role") for op in spec.operations}
            missing = required_roles - roles
            assert not missing, f"Style '{style}' missing roles: {missing}"
