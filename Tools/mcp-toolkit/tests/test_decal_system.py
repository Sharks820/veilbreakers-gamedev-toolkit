"""Tests for decal_system handler."""

import math

import pytest

from blender_addon.handlers.decal_system import (
    DECAL_TYPES,
    generate_decal_mesh,
    compute_decal_placements,
    project_decal_to_surface,
    get_decal_categories,
    get_available_decal_types,
)


# ---------------------------------------------------------------------------
# Decal type definitions
# ---------------------------------------------------------------------------


class TestDecalDefinitions:
    def test_ten_decal_types(self):
        assert len(DECAL_TYPES) == 10

    def test_all_types_have_required_fields(self):
        required = {"size_range", "alpha", "material", "color", "roughness", "category"}
        for name, config in DECAL_TYPES.items():
            missing = required - set(config.keys())
            assert not missing, f"Decal '{name}' missing: {missing}"

    def test_size_range_valid(self):
        for name, config in DECAL_TYPES.items():
            lo, hi = config["size_range"]
            assert lo > 0
            assert hi >= lo, f"Decal '{name}' has inverted size_range"

    def test_color_is_rgba(self):
        for name, config in DECAL_TYPES.items():
            assert len(config["color"]) == 4, f"Decal '{name}' color not RGBA"

    def test_roughness_in_range(self):
        for name, config in DECAL_TYPES.items():
            assert 0.0 <= config["roughness"] <= 1.0


# ---------------------------------------------------------------------------
# Blood decals (generate_decal_mesh)
# ---------------------------------------------------------------------------


class TestGenerateDecalMesh:
    def test_blood_splatter(self):
        mesh = generate_decal_mesh("blood_splatter")
        assert len(mesh["vertices"]) == 4  # single quad
        assert len(mesh["faces"]) == 1
        assert mesh["decal_type"] == "blood_splatter"
        assert mesh["material"] == "blood_decal"

    def test_vertices_are_3d(self):
        mesh = generate_decal_mesh("crack")
        for v in mesh["vertices"]:
            assert len(v) == 3

    def test_uvs_are_2d(self):
        mesh = generate_decal_mesh("moss_patch")
        for uv in mesh["uvs"]:
            assert len(uv) == 2

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Unknown decal type"):
            generate_decal_mesh("nonexistent")

    def test_size_parameter(self):
        small = generate_decal_mesh("blood_splatter", size=0.5)
        large = generate_decal_mesh("blood_splatter", size=2.0)
        # Large should have wider vertex spread
        small_range = max(v[0] for v in small["vertices"]) - min(v[0] for v in small["vertices"])
        large_range = max(v[0] for v in large["vertices"]) - min(v[0] for v in large["vertices"])
        assert large_range > small_range

    def test_subdivisions(self):
        no_sub = generate_decal_mesh("scorch_mark", subdivisions=0)
        sub = generate_decal_mesh("scorch_mark", subdivisions=2)
        assert len(sub["vertices"]) > len(no_sub["vertices"])
        assert len(sub["faces"]) > len(no_sub["faces"])

    def test_properties_present(self):
        mesh = generate_decal_mesh("rune_marking")
        props = mesh["properties"]
        assert props["emission"] is True
        assert "emission_strength" in props

    def test_all_types_generate(self):
        for dt in DECAL_TYPES:
            mesh = generate_decal_mesh(dt)
            assert len(mesh["vertices"]) > 0
            assert len(mesh["faces"]) > 0


# ---------------------------------------------------------------------------
# Scorch marks (UVs)
# ---------------------------------------------------------------------------


class TestScorchMarkUVs:
    def test_scorch_has_proper_uvs(self):
        mesh = generate_decal_mesh("scorch_mark")
        assert len(mesh["uvs"]) == len(mesh["vertices"])
        # UVs should cover [0,1] range
        us = [uv[0] for uv in mesh["uvs"]]
        vs = [uv[1] for uv in mesh["uvs"]]
        assert min(us) == 0.0
        assert max(us) == 1.0
        assert min(vs) == 0.0
        assert max(vs) == 1.0


# ---------------------------------------------------------------------------
# Decal sizes
# ---------------------------------------------------------------------------


class TestDecalSizes:
    def test_sizes_are_reasonable(self):
        for name, config in DECAL_TYPES.items():
            lo, hi = config["size_range"]
            assert lo >= 0.1, f"Decal '{name}' min size too small"
            assert hi <= 10.0, f"Decal '{name}' max size too large"


# ---------------------------------------------------------------------------
# Decal placements
# ---------------------------------------------------------------------------


class TestComputeDecalPlacements:
    def test_basic_placement(self):
        placements = compute_decal_placements(
            surface_bounds=((0, 0), (10, 10)),
            decal_types=["blood_splatter"],
            density=0.5,
            seed=42,
        )
        assert len(placements) > 0

    def test_placement_structure(self):
        placements = compute_decal_placements(
            surface_bounds=((0, 0), (10, 10)),
            decal_types=["crack", "moss_patch"],
            density=0.2,
        )
        for p in placements:
            assert "decal_type" in p
            assert "position" in p
            assert len(p["position"]) == 2
            assert "rotation" in p
            assert 0 <= p["rotation"] <= 360
            assert "size" in p
            assert p["size"] > 0

    def test_invalid_types_raises(self):
        with pytest.raises(ValueError, match="No valid decal types"):
            compute_decal_placements(
                surface_bounds=((0, 0), (10, 10)),
                decal_types=["nonexistent"],
            )

    def test_exclusion_zones(self):
        placements = compute_decal_placements(
            surface_bounds=((0, 0), (10, 10)),
            decal_types=["blood_splatter"],
            density=2.0,
            seed=42,
            exclude_regions=[{"center": (5, 5), "radius": 4.0}],
        )
        for p in placements:
            x, y = p["position"]
            dist = math.sqrt((x - 5) ** 2 + (y - 5) ** 2)
            assert dist >= 4.0, "Decal placed inside exclusion zone"

    def test_deterministic(self):
        p1 = compute_decal_placements(
            ((0, 0), (10, 10)), ["scorch_mark"], density=0.5, seed=42
        )
        p2 = compute_decal_placements(
            ((0, 0), (10, 10)), ["scorch_mark"], density=0.5, seed=42
        )
        assert p1 == p2

    def test_higher_density_more_decals(self):
        low = compute_decal_placements(
            ((0, 0), (20, 20)), ["dirt_accumulation"], density=0.01, seed=42
        )
        high = compute_decal_placements(
            ((0, 0), (20, 20)), ["dirt_accumulation"], density=1.0, seed=42
        )
        assert len(high) >= len(low)


# ---------------------------------------------------------------------------
# Surface projection
# ---------------------------------------------------------------------------


class TestProjectDecalToSurface:
    def test_basic_projection(self):
        result = project_decal_to_surface(
            decal_position=(5, 5),
            surface_normal=(0, 0, 1),
            surface_point=(5, 5, 0),
            decal_size=1.0,
        )
        assert "position" in result
        assert "normal" in result
        assert "scale" in result
        assert "tangent" in result
        assert "bitangent" in result

    def test_offset_along_normal(self):
        result = project_decal_to_surface(
            decal_position=(0, 0),
            surface_normal=(0, 0, 1),
            surface_point=(0, 0, 0),
            decal_size=1.0,
            offset=0.01,
        )
        assert result["position"][2] > 0  # Offset above surface

    def test_tangent_perpendicular_to_normal(self):
        result = project_decal_to_surface(
            decal_position=(0, 0),
            surface_normal=(0, 0, 1),
            surface_point=(0, 0, 0),
            decal_size=1.0,
        )
        n = result["normal"]
        t = result["tangent"]
        dot = n[0] * t[0] + n[1] * t[1] + n[2] * t[2]
        assert abs(dot) < 1e-6, "Tangent not perpendicular to normal"

    def test_zero_normal_fallback(self):
        result = project_decal_to_surface(
            decal_position=(0, 0),
            surface_normal=(0, 0, 0),
            surface_point=(0, 0, 0),
            decal_size=1.0,
        )
        # Should fall back to (0, 0, 1)
        assert result["normal"] == (0, 0, 1)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


class TestUtilities:
    def test_get_decal_categories(self):
        cats = get_decal_categories()
        assert "violence" in cats
        assert "environmental" in cats
        assert "blood_splatter" in cats["violence"]

    def test_get_available_types(self):
        types = get_available_decal_types()
        assert len(types) == 10
        assert types == sorted(types)
