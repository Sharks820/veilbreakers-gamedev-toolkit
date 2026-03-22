"""Tests for environmental procedural mesh generators (categories 6-10).

Validates fences/barriers, traps, vehicles, structural elements,
and dark fantasy specific generators return valid mesh data:
- Non-empty vertex and face lists
- All face indices reference valid vertices
- Required metadata keys present
- Different styles/parameters produce different geometry
"""

from __future__ import annotations

import pytest

from blender_addon.handlers.procedural_meshes import (
    # Fences & Barriers
    generate_fence_mesh,
    generate_barricade_mesh,
    generate_railing_mesh,
    # Traps
    generate_spike_trap_mesh,
    generate_bear_trap_mesh,
    generate_pressure_plate_mesh,
    generate_dart_launcher_mesh,
    generate_swinging_blade_mesh,
    generate_falling_cage_mesh,
    # Vehicles & Transport
    generate_cart_mesh,
    generate_boat_mesh,
    generate_wagon_wheel_mesh,
    # Structural Elements
    generate_column_row_mesh,
    generate_buttress_mesh,
    generate_rampart_mesh,
    generate_drawbridge_mesh,
    generate_well_mesh,
    generate_ladder_mesh,
    generate_scaffolding_mesh,
    # Dark Fantasy Specific
    generate_sacrificial_circle_mesh,
    generate_corruption_crystal_mesh,
    generate_veil_tear_mesh,
    generate_soul_cage_mesh,
    generate_blood_fountain_mesh,
    generate_bone_throne_mesh,
    generate_dark_obelisk_mesh,
    generate_spider_web_mesh,
    generate_coffin_mesh,
    generate_gibbet_mesh,
    # Registry
    GENERATORS,
)


# ---------------------------------------------------------------------------
# Helper validation (same contract as test_procedural_meshes.py)
# ---------------------------------------------------------------------------


def validate_mesh_spec(result: dict, name: str, min_verts: int = 4, min_faces: int = 1):
    """Validate a mesh spec dict has all required fields and valid data."""
    assert "vertices" in result, f"{name}: missing 'vertices'"
    assert "faces" in result, f"{name}: missing 'faces'"
    assert "uvs" in result, f"{name}: missing 'uvs'"
    assert "metadata" in result, f"{name}: missing 'metadata'"

    verts = result["vertices"]
    faces = result["faces"]
    meta = result["metadata"]

    assert len(verts) >= min_verts, (
        f"{name}: expected >= {min_verts} vertices, got {len(verts)}"
    )
    assert len(faces) >= min_faces, (
        f"{name}: expected >= {min_faces} faces, got {len(faces)}"
    )

    # All vertices are 3-tuples of numbers
    for i, v in enumerate(verts):
        assert len(v) == 3, f"{name}: vertex {i} has {len(v)} components, expected 3"
        for comp in v:
            assert isinstance(comp, (int, float)), (
                f"{name}: vertex {i} component {comp} is not a number"
            )

    # All face indices reference valid vertices
    n_verts = len(verts)
    for fi, face in enumerate(faces):
        assert len(face) >= 3, f"{name}: face {fi} has {len(face)} verts, need >= 3"
        for idx in face:
            assert 0 <= idx < n_verts, (
                f"{name}: face {fi} index {idx} out of range [0, {n_verts})"
            )

    # Metadata required keys
    assert "name" in meta, f"{name}: metadata missing 'name'"
    assert "poly_count" in meta, f"{name}: metadata missing 'poly_count'"
    assert "vertex_count" in meta, f"{name}: metadata missing 'vertex_count'"
    assert "dimensions" in meta, f"{name}: metadata missing 'dimensions'"

    assert meta["poly_count"] == len(faces), (
        f"{name}: poly_count {meta['poly_count']} != actual {len(faces)}"
    )
    assert meta["vertex_count"] == len(verts), (
        f"{name}: vertex_count {meta['vertex_count']} != actual {len(verts)}"
    )

    dims = meta["dimensions"]
    assert "width" in dims and "height" in dims and "depth" in dims
    for dim_name, val in dims.items():
        assert val >= 0, f"{name}: dimension '{dim_name}' is negative: {val}"

    return True


# ---------------------------------------------------------------------------
# FENCES & BARRIERS tests
# ---------------------------------------------------------------------------


class TestFencesBarriers:
    """Test fence and barrier mesh generators."""

    @pytest.mark.parametrize("style", [
        "wooden_picket", "iron_wrought", "stone_low_wall", "bone_fence",
    ])
    def test_fence_styles(self, style):
        result = generate_fence_mesh(style=style)
        validate_mesh_spec(result, f"Fence_{style}", min_verts=20, min_faces=6)

    def test_fence_different_styles_different_geometry(self):
        r1 = generate_fence_mesh(style="wooden_picket")
        r2 = generate_fence_mesh(style="iron_wrought")
        assert r1["vertices"] != r2["vertices"]

    def test_fence_post_count(self):
        r3 = generate_fence_mesh(posts=3)
        r8 = generate_fence_mesh(posts=8)
        assert r8["metadata"]["vertex_count"] > r3["metadata"]["vertex_count"]

    def test_fence_length(self):
        r_short = generate_fence_mesh(length=2.0)
        r_long = generate_fence_mesh(length=8.0)
        d_short = r_short["metadata"]["dimensions"]
        d_long = r_long["metadata"]["dimensions"]
        assert d_long["width"] > d_short["width"]

    @pytest.mark.parametrize("style", ["wooden_hasty", "wagon_overturned", "sandbag"])
    def test_barricade_styles(self, style):
        result = generate_barricade_mesh(style=style)
        validate_mesh_spec(result, f"Barricade_{style}", min_verts=16, min_faces=4)

    def test_barricade_different_styles(self):
        r1 = generate_barricade_mesh(style="wooden_hasty")
        r2 = generate_barricade_mesh(style="sandbag")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", ["iron_ornate", "wooden_simple", "stone_balustrade"])
    def test_railing_styles(self, style):
        result = generate_railing_mesh(style=style)
        validate_mesh_spec(result, f"Railing_{style}", min_verts=20, min_faces=6)

    def test_railing_length(self):
        r_short = generate_railing_mesh(length=1.5)
        r_long = generate_railing_mesh(length=6.0)
        d_short = r_short["metadata"]["dimensions"]
        d_long = r_long["metadata"]["dimensions"]
        assert d_long["width"] > d_short["width"]


# ---------------------------------------------------------------------------
# TRAPS tests
# ---------------------------------------------------------------------------


class TestTraps:
    """Test trap mesh generators."""

    def test_spike_trap_default(self):
        result = generate_spike_trap_mesh()
        validate_mesh_spec(result, "SpikeTrap", min_verts=30, min_faces=10)

    def test_spike_trap_spike_count(self):
        r4 = generate_spike_trap_mesh(spike_count=4)
        r16 = generate_spike_trap_mesh(spike_count=16)
        assert r16["metadata"]["vertex_count"] > r4["metadata"]["vertex_count"]

    def test_spike_trap_size(self):
        r_small = generate_spike_trap_mesh(size=0.5)
        r_large = generate_spike_trap_mesh(size=2.0)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["width"] > d_small["width"]

    def test_bear_trap(self):
        result = generate_bear_trap_mesh()
        validate_mesh_spec(result, "BearTrap", min_verts=30, min_faces=10)

    def test_bear_trap_size(self):
        r_small = generate_bear_trap_mesh(size=0.2)
        r_large = generate_bear_trap_mesh(size=0.8)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["width"] > d_small["width"]

    def test_pressure_plate(self):
        result = generate_pressure_plate_mesh()
        validate_mesh_spec(result, "PressurePlate", min_verts=20, min_faces=6)

    def test_pressure_plate_size(self):
        r_small = generate_pressure_plate_mesh(size=0.3)
        r_large = generate_pressure_plate_mesh(size=1.2)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["width"] > d_small["width"]

    @pytest.mark.parametrize("style", ["stone", "metal"])
    def test_dart_launcher_styles(self, style):
        result = generate_dart_launcher_mesh(style=style)
        validate_mesh_spec(result, f"DartLauncher_{style}", min_verts=20, min_faces=6)

    def test_swinging_blade(self):
        result = generate_swinging_blade_mesh()
        validate_mesh_spec(result, "SwingingBlade", min_verts=30, min_faces=10)

    def test_swinging_blade_length(self):
        r_short = generate_swinging_blade_mesh(blade_length=0.6)
        r_long = generate_swinging_blade_mesh(blade_length=2.0)
        d_short = r_short["metadata"]["dimensions"]
        d_long = r_long["metadata"]["dimensions"]
        assert d_long["height"] > d_short["height"]

    def test_falling_cage(self):
        result = generate_falling_cage_mesh()
        validate_mesh_spec(result, "FallingCage", min_verts=40, min_faces=15)

    def test_falling_cage_size(self):
        r_small = generate_falling_cage_mesh(size=0.8)
        r_large = generate_falling_cage_mesh(size=2.5)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["width"] > d_small["width"]


# ---------------------------------------------------------------------------
# VEHICLES & TRANSPORT tests
# ---------------------------------------------------------------------------


class TestVehicles:
    """Test vehicle mesh generators."""

    @pytest.mark.parametrize("style", ["merchant_covered", "farm_open", "prison_cage"])
    def test_cart_styles(self, style):
        result = generate_cart_mesh(style=style)
        validate_mesh_spec(result, f"Cart_{style}", min_verts=30, min_faces=10)

    def test_cart_different_styles(self):
        r1 = generate_cart_mesh(style="merchant_covered")
        r2 = generate_cart_mesh(style="prison_cage")
        assert r1["vertices"] != r2["vertices"]

    def test_cart_wheel_count(self):
        r2 = generate_cart_mesh(wheels=2)
        r4 = generate_cart_mesh(wheels=4)
        assert r4["metadata"]["vertex_count"] > r2["metadata"]["vertex_count"]

    def test_cart_size_scaling(self):
        r_small = generate_cart_mesh(size=0.5)
        r_large = generate_cart_mesh(size=2.0)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["width"] > d_small["width"]

    @pytest.mark.parametrize("style", ["rowboat", "viking_longship", "gondola"])
    def test_boat_styles(self, style):
        result = generate_boat_mesh(style=style)
        validate_mesh_spec(result, f"Boat_{style}", min_verts=20, min_faces=8)

    def test_boat_different_styles(self):
        r1 = generate_boat_mesh(style="rowboat")
        r2 = generate_boat_mesh(style="viking_longship")
        assert r1["vertices"] != r2["vertices"]

    def test_boat_size_scaling(self):
        r_small = generate_boat_mesh(size=0.5)
        r_large = generate_boat_mesh(size=2.0)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["width"] > d_small["width"]

    def test_wagon_wheel(self):
        result = generate_wagon_wheel_mesh()
        validate_mesh_spec(result, "WagonWheel", min_verts=30, min_faces=10)

    def test_wagon_wheel_spokes(self):
        r6 = generate_wagon_wheel_mesh(spokes=6)
        r12 = generate_wagon_wheel_mesh(spokes=12)
        assert r12["metadata"]["vertex_count"] > r6["metadata"]["vertex_count"]

    def test_wagon_wheel_radius(self):
        r_small = generate_wagon_wheel_mesh(radius=0.2)
        r_large = generate_wagon_wheel_mesh(radius=0.8)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["width"] > d_small["width"]


# ---------------------------------------------------------------------------
# STRUCTURAL ELEMENTS tests
# ---------------------------------------------------------------------------


class TestStructural:
    """Test structural element mesh generators."""

    @pytest.mark.parametrize("style", ["doric", "corinthian", "gothic"])
    def test_column_row_styles(self, style):
        result = generate_column_row_mesh(style=style)
        validate_mesh_spec(result, f"ColumnRow_{style}", min_verts=40, min_faces=15)

    def test_column_row_count(self):
        r2 = generate_column_row_mesh(count=2)
        r6 = generate_column_row_mesh(count=6)
        assert r6["metadata"]["vertex_count"] > r2["metadata"]["vertex_count"]

    def test_column_row_different_styles(self):
        r1 = generate_column_row_mesh(style="doric")
        r2 = generate_column_row_mesh(style="gothic")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", ["flying", "standard"])
    def test_buttress_styles(self, style):
        result = generate_buttress_mesh(style=style)
        validate_mesh_spec(result, f"Buttress_{style}", min_verts=20, min_faces=6)

    def test_buttress_height(self):
        r_short = generate_buttress_mesh(height=2.0)
        r_tall = generate_buttress_mesh(height=6.0)
        d_short = r_short["metadata"]["dimensions"]
        d_tall = r_tall["metadata"]["dimensions"]
        assert d_tall["height"] > d_short["height"]

    def test_rampart(self):
        result = generate_rampart_mesh()
        validate_mesh_spec(result, "Rampart", min_verts=40, min_faces=10)

    def test_rampart_length(self):
        r_short = generate_rampart_mesh(length=3.0)
        r_long = generate_rampart_mesh(length=10.0)
        d_short = r_short["metadata"]["dimensions"]
        d_long = r_long["metadata"]["dimensions"]
        assert d_long["width"] > d_short["width"]

    def test_drawbridge(self):
        result = generate_drawbridge_mesh()
        validate_mesh_spec(result, "Drawbridge", min_verts=40, min_faces=15)

    def test_drawbridge_dimensions(self):
        r_small = generate_drawbridge_mesh(width=2.0, length=2.0)
        r_large = generate_drawbridge_mesh(width=4.0, length=6.0)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["width"] > d_small["width"]

    def test_well_with_roof(self):
        result = generate_well_mesh(roof=True)
        validate_mesh_spec(result, "Well_roof", min_verts=30, min_faces=10)

    def test_well_without_roof(self):
        result = generate_well_mesh(roof=False)
        validate_mesh_spec(result, "Well_no_roof", min_verts=20, min_faces=6)

    def test_well_roof_adds_geometry(self):
        r_no = generate_well_mesh(roof=False)
        r_yes = generate_well_mesh(roof=True)
        assert r_yes["metadata"]["vertex_count"] > r_no["metadata"]["vertex_count"]

    def test_ladder(self):
        result = generate_ladder_mesh()
        validate_mesh_spec(result, "Ladder", min_verts=20, min_faces=8)

    def test_ladder_rungs(self):
        r4 = generate_ladder_mesh(rungs=4)
        r12 = generate_ladder_mesh(rungs=12)
        assert r12["metadata"]["vertex_count"] > r4["metadata"]["vertex_count"]

    def test_ladder_height(self):
        r_short = generate_ladder_mesh(height=1.5)
        r_tall = generate_ladder_mesh(height=5.0)
        d_short = r_short["metadata"]["dimensions"]
        d_tall = r_tall["metadata"]["dimensions"]
        assert d_tall["height"] > d_short["height"]

    def test_scaffolding(self):
        result = generate_scaffolding_mesh()
        validate_mesh_spec(result, "Scaffolding", min_verts=40, min_faces=15)

    def test_scaffolding_levels(self):
        r2 = generate_scaffolding_mesh(levels=2)
        r5 = generate_scaffolding_mesh(levels=5)
        assert r5["metadata"]["vertex_count"] > r2["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# DARK FANTASY SPECIFIC tests
# ---------------------------------------------------------------------------


class TestDarkFantasy:
    """Test dark fantasy specific mesh generators."""

    def test_sacrificial_circle(self):
        result = generate_sacrificial_circle_mesh()
        validate_mesh_spec(result, "SacrificialCircle", min_verts=40, min_faces=15)

    def test_sacrificial_circle_rune_count(self):
        r4 = generate_sacrificial_circle_mesh(rune_count=4)
        r10 = generate_sacrificial_circle_mesh(rune_count=10)
        assert r10["metadata"]["vertex_count"] > r4["metadata"]["vertex_count"]

    def test_corruption_crystal(self):
        result = generate_corruption_crystal_mesh()
        validate_mesh_spec(result, "CorruptionCrystal", min_verts=30, min_faces=10)

    def test_corruption_crystal_facets(self):
        r4 = generate_corruption_crystal_mesh(facets=4)
        r10 = generate_corruption_crystal_mesh(facets=10)
        assert r10["metadata"]["vertex_count"] > r4["metadata"]["vertex_count"]

    def test_corruption_crystal_height(self):
        r_small = generate_corruption_crystal_mesh(height=0.5)
        r_large = generate_corruption_crystal_mesh(height=3.0)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["height"] > d_small["height"]

    def test_veil_tear(self):
        result = generate_veil_tear_mesh()
        validate_mesh_spec(result, "VeilTear", min_verts=30, min_faces=10)

    def test_veil_tear_dimensions(self):
        r_small = generate_veil_tear_mesh(width=1.0, height=1.5)
        r_large = generate_veil_tear_mesh(width=3.0, height=5.0)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["height"] > d_small["height"]

    def test_soul_cage(self):
        result = generate_soul_cage_mesh()
        validate_mesh_spec(result, "SoulCage", min_verts=30, min_faces=10)

    def test_soul_cage_bars(self):
        r4 = generate_soul_cage_mesh(bars=4)
        r12 = generate_soul_cage_mesh(bars=12)
        assert r12["metadata"]["vertex_count"] > r4["metadata"]["vertex_count"]

    def test_blood_fountain(self):
        result = generate_blood_fountain_mesh()
        validate_mesh_spec(result, "BloodFountain", min_verts=40, min_faces=15)

    def test_blood_fountain_tiers(self):
        r1 = generate_blood_fountain_mesh(tiers=1)
        r3 = generate_blood_fountain_mesh(tiers=3)
        assert r3["metadata"]["vertex_count"] > r1["metadata"]["vertex_count"]

    def test_bone_throne(self):
        result = generate_bone_throne_mesh()
        validate_mesh_spec(result, "BoneThrone", min_verts=50, min_faces=20)

    def test_dark_obelisk(self):
        result = generate_dark_obelisk_mesh()
        validate_mesh_spec(result, "DarkObelisk", min_verts=20, min_faces=8)

    def test_dark_obelisk_runes(self):
        r2 = generate_dark_obelisk_mesh(runes=2)
        r8 = generate_dark_obelisk_mesh(runes=8)
        assert r8["metadata"]["vertex_count"] > r2["metadata"]["vertex_count"]

    def test_dark_obelisk_height(self):
        r_short = generate_dark_obelisk_mesh(height=1.5)
        r_tall = generate_dark_obelisk_mesh(height=5.0)
        d_short = r_short["metadata"]["dimensions"]
        d_tall = r_tall["metadata"]["dimensions"]
        assert d_tall["height"] > d_short["height"]

    def test_spider_web(self):
        result = generate_spider_web_mesh()
        validate_mesh_spec(result, "SpiderWeb", min_verts=20, min_faces=8)

    def test_spider_web_complexity(self):
        r_simple = generate_spider_web_mesh(rings=3, radials=4)
        r_complex = generate_spider_web_mesh(rings=8, radials=12)
        assert r_complex["metadata"]["vertex_count"] > r_simple["metadata"]["vertex_count"]

    @pytest.mark.parametrize("style", ["wooden_simple", "stone_ornate", "iron_bound"])
    def test_coffin_styles(self, style):
        result = generate_coffin_mesh(style=style)
        validate_mesh_spec(result, f"Coffin_{style}", min_verts=12, min_faces=6)

    def test_coffin_different_styles(self):
        r1 = generate_coffin_mesh(style="wooden_simple")
        r2 = generate_coffin_mesh(style="stone_ornate")
        assert r1["vertices"] != r2["vertices"] or \
               r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]

    def test_gibbet(self):
        result = generate_gibbet_mesh()
        validate_mesh_spec(result, "Gibbet", min_verts=40, min_faces=15)

    def test_gibbet_height(self):
        r_short = generate_gibbet_mesh(height=2.0)
        r_tall = generate_gibbet_mesh(height=5.0)
        d_short = r_short["metadata"]["dimensions"]
        d_tall = r_tall["metadata"]["dimensions"]
        assert d_tall["height"] > d_short["height"]


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestRegistry:
    """Test that all new generators are properly registered."""

    def test_fence_barrier_category_exists(self):
        assert "fence_barrier" in GENERATORS

    def test_trap_category_exists(self):
        assert "trap" in GENERATORS

    def test_vehicle_category_exists(self):
        assert "vehicle" in GENERATORS

    def test_structural_category_exists(self):
        assert "structural" in GENERATORS

    def test_dark_fantasy_category_exists(self):
        assert "dark_fantasy" in GENERATORS

    def test_fence_barrier_generators(self):
        expected = {"fence", "barricade", "railing"}
        assert set(GENERATORS["fence_barrier"].keys()) == expected

    def test_trap_generators(self):
        expected = {
            "spike_trap", "bear_trap", "pressure_plate",
            "dart_launcher", "swinging_blade", "falling_cage",
        }
        assert set(GENERATORS["trap"].keys()) == expected

    def test_vehicle_generators(self):
        expected = {"cart", "boat", "wagon_wheel"}
        assert set(GENERATORS["vehicle"].keys()) == expected

    def test_structural_generators(self):
        expected = {
            "column_row", "buttress", "rampart", "drawbridge",
            "well", "ladder", "scaffolding",
        }
        assert set(GENERATORS["structural"].keys()) == expected

    def test_dark_fantasy_generators(self):
        expected = {
            "sacrificial_circle", "corruption_crystal", "veil_tear",
            "soul_cage", "blood_fountain", "bone_throne",
            "dark_obelisk", "spider_web", "coffin", "gibbet",
        }
        assert expected.issubset(set(GENERATORS["dark_fantasy"].keys()))

    def test_all_registered_generators_callable(self):
        """Verify every registered generator can be called with defaults."""
        for category, generators in GENERATORS.items():
            if category in ("fence_barrier", "trap", "vehicle", "structural", "dark_fantasy"):
                for name, func in generators.items():
                    result = func()
                    assert "vertices" in result, f"{category}/{name}: missing vertices"
                    assert "faces" in result, f"{category}/{name}: missing faces"
                    assert len(result["vertices"]) > 0, f"{category}/{name}: no vertices"
                    assert len(result["faces"]) > 0, f"{category}/{name}: no faces"

    def test_total_category_count(self):
        """Ensure we have at least 21 categories (expanded with food, potions, etc)."""
        assert len(GENERATORS) >= 21
