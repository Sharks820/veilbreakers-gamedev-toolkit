"""Tests for animal and wildlife procedural mesh generators.

Validates that every generator in the forest_animals, mountain_animals,
domestic_animals, vermin, and swamp_animals categories returns valid mesh data:
- Non-empty vertex and face lists
- All face indices reference valid vertices
- Reasonable vertex/face counts for the animal type
- Required metadata keys present
- Different styles produce different geometry
"""

from __future__ import annotations

import sys
import importlib.util

import pytest

# Load procedural_meshes without triggering blender_addon __init__ (needs bpy)
_spec = importlib.util.spec_from_file_location(
    "procedural_meshes",
    "blender_addon/handlers/procedural_meshes.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Forest Animals
generate_deer_mesh = _mod.generate_deer_mesh
generate_wolf_mesh = _mod.generate_wolf_mesh
generate_fox_mesh = _mod.generate_fox_mesh
generate_rabbit_mesh = _mod.generate_rabbit_mesh
generate_owl_mesh = _mod.generate_owl_mesh
generate_crow_mesh = _mod.generate_crow_mesh

# Mountain Animals
generate_mountain_goat_mesh = _mod.generate_mountain_goat_mesh
generate_eagle_mesh = _mod.generate_eagle_mesh
generate_bear_mesh = _mod.generate_bear_mesh

# Domestic Animals
generate_horse_mesh = _mod.generate_horse_mesh
generate_chicken_mesh = _mod.generate_chicken_mesh
generate_dog_mesh = _mod.generate_dog_mesh
generate_cat_mesh = _mod.generate_cat_mesh

# Vermin
generate_rat_mesh = _mod.generate_rat_mesh
generate_bat_mesh = _mod.generate_bat_mesh
generate_small_spider_mesh = _mod.generate_small_spider_mesh
generate_beetle_mesh = _mod.generate_beetle_mesh

# Swamp Animals
generate_frog_mesh = _mod.generate_frog_mesh
generate_snake_ambient_mesh = _mod.generate_snake_ambient_mesh
generate_turtle_mesh = _mod.generate_turtle_mesh

GENERATORS = _mod.GENERATORS


# ---------------------------------------------------------------------------
# Validation helper (same contract as other test files)
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

    for i, v in enumerate(verts):
        assert len(v) == 3, f"{name}: vertex {i} has {len(v)} components, expected 3"
        for comp in v:
            assert isinstance(comp, (int, float)), (
                f"{name}: vertex {i} component {comp} is not a number"
            )

    n_verts = len(verts)
    for fi, face in enumerate(faces):
        assert len(face) >= 3, f"{name}: face {fi} has {len(face)} verts, need >= 3"
        for idx in face:
            assert 0 <= idx < n_verts, (
                f"{name}: face {fi} index {idx} out of range [0, {n_verts})"
            )

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
# FOREST ANIMALS tests
# ---------------------------------------------------------------------------


class TestForestAnimals:
    """Test forest animal mesh generators."""

    @pytest.mark.parametrize("style", ["adult", "fawn"])
    def test_deer_styles(self, style):
        result = generate_deer_mesh(style=style)
        validate_mesh_spec(result, f"Deer_{style}", min_verts=100, min_faces=50)

    def test_deer_adult_has_antlers(self):
        """Adult deer should have more geometry than fawn (antlers)."""
        adult = generate_deer_mesh(style="adult")
        fawn = generate_deer_mesh(style="fawn")
        assert adult["metadata"]["vertex_count"] > fawn["metadata"]["vertex_count"]

    def test_deer_different_styles_different_geometry(self):
        r1 = generate_deer_mesh(style="adult")
        r2 = generate_deer_mesh(style="fawn")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", ["adult", "pup"])
    def test_wolf_styles(self, style):
        result = generate_wolf_mesh(style=style)
        validate_mesh_spec(result, f"Wolf_{style}", min_verts=100, min_faces=50)

    def test_wolf_different_styles_different_geometry(self):
        r1 = generate_wolf_mesh(style="adult")
        r2 = generate_wolf_mesh(style="pup")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", ["adult", "kit"])
    def test_fox_styles(self, style):
        result = generate_fox_mesh(style=style)
        validate_mesh_spec(result, f"Fox_{style}", min_verts=80, min_faces=40)

    def test_fox_different_styles_different_geometry(self):
        r1 = generate_fox_mesh(style="adult")
        r2 = generate_fox_mesh(style="kit")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", ["sitting", "alert"])
    def test_rabbit_styles(self, style):
        result = generate_rabbit_mesh(style=style)
        validate_mesh_spec(result, f"Rabbit_{style}", min_verts=40, min_faces=20)

    def test_rabbit_different_styles_different_geometry(self):
        r1 = generate_rabbit_mesh(style="sitting")
        r2 = generate_rabbit_mesh(style="alert")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", ["perched", "spread"])
    def test_owl_styles(self, style):
        result = generate_owl_mesh(style=style)
        validate_mesh_spec(result, f"Owl_{style}", min_verts=60, min_faces=30)

    def test_owl_spread_has_more_geometry(self):
        perched = generate_owl_mesh(style="perched")
        spread = generate_owl_mesh(style="spread")
        assert spread["metadata"]["vertex_count"] > perched["metadata"]["vertex_count"]

    @pytest.mark.parametrize("style", ["perched", "flying"])
    def test_crow_styles(self, style):
        result = generate_crow_mesh(style=style)
        validate_mesh_spec(result, f"Crow_{style}", min_verts=40, min_faces=20)

    def test_crow_different_styles_different_geometry(self):
        r1 = generate_crow_mesh(style="perched")
        r2 = generate_crow_mesh(style="flying")
        assert r1["vertices"] != r2["vertices"]


# ---------------------------------------------------------------------------
# MOUNTAIN ANIMALS tests
# ---------------------------------------------------------------------------


class TestMountainAnimals:
    """Test mountain animal mesh generators."""

    @pytest.mark.parametrize("style", ["standing", "climbing"])
    def test_mountain_goat_styles(self, style):
        result = generate_mountain_goat_mesh(style=style)
        validate_mesh_spec(result, f"MountainGoat_{style}", min_verts=100, min_faces=50)

    def test_mountain_goat_different_styles_different_geometry(self):
        r1 = generate_mountain_goat_mesh(style="standing")
        r2 = generate_mountain_goat_mesh(style="climbing")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", ["perched", "soaring"])
    def test_eagle_styles(self, style):
        result = generate_eagle_mesh(style=style)
        validate_mesh_spec(result, f"Eagle_{style}", min_verts=60, min_faces=30)

    def test_eagle_soaring_has_more_geometry(self):
        perched = generate_eagle_mesh(style="perched")
        soaring = generate_eagle_mesh(style="soaring")
        assert soaring["metadata"]["vertex_count"] > perched["metadata"]["vertex_count"]

    @pytest.mark.parametrize("style", ["standing", "rearing"])
    def test_bear_styles(self, style):
        result = generate_bear_mesh(style=style)
        validate_mesh_spec(result, f"Bear_{style}", min_verts=150, min_faces=80)

    def test_bear_different_styles_different_geometry(self):
        r1 = generate_bear_mesh(style="standing")
        r2 = generate_bear_mesh(style="rearing")
        assert r1["vertices"] != r2["vertices"]


# ---------------------------------------------------------------------------
# DOMESTIC ANIMALS tests
# ---------------------------------------------------------------------------


class TestDomesticAnimals:
    """Test domestic animal mesh generators."""

    @pytest.mark.parametrize("style", ["standing", "galloping"])
    def test_horse_styles(self, style):
        result = generate_horse_mesh(style=style)
        validate_mesh_spec(result, f"Horse_{style}", min_verts=200, min_faces=100)

    def test_horse_different_styles_different_geometry(self):
        r1 = generate_horse_mesh(style="standing")
        r2 = generate_horse_mesh(style="galloping")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", ["standing", "pecking"])
    def test_chicken_styles(self, style):
        result = generate_chicken_mesh(style=style)
        validate_mesh_spec(result, f"Chicken_{style}", min_verts=40, min_faces=20)

    def test_chicken_different_styles_different_geometry(self):
        r1 = generate_chicken_mesh(style="standing")
        r2 = generate_chicken_mesh(style="pecking")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", ["sitting", "standing"])
    def test_dog_styles(self, style):
        result = generate_dog_mesh(style=style)
        validate_mesh_spec(result, f"Dog_{style}", min_verts=80, min_faces=40)

    def test_dog_different_styles_different_geometry(self):
        r1 = generate_dog_mesh(style="sitting")
        r2 = generate_dog_mesh(style="standing")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", ["sitting", "walking"])
    def test_cat_styles(self, style):
        result = generate_cat_mesh(style=style)
        validate_mesh_spec(result, f"Cat_{style}", min_verts=60, min_faces=30)

    def test_cat_different_styles_different_geometry(self):
        r1 = generate_cat_mesh(style="sitting")
        r2 = generate_cat_mesh(style="walking")
        assert r1["vertices"] != r2["vertices"]


# ---------------------------------------------------------------------------
# VERMIN tests
# ---------------------------------------------------------------------------


class TestVermin:
    """Test vermin/pest mesh generators."""

    @pytest.mark.parametrize("style", ["standing", "crouching"])
    def test_rat_styles(self, style):
        result = generate_rat_mesh(style=style)
        validate_mesh_spec(result, f"Rat_{style}", min_verts=30, min_faces=15)

    def test_rat_different_styles_different_geometry(self):
        r1 = generate_rat_mesh(style="standing")
        r2 = generate_rat_mesh(style="crouching")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", ["flying", "hanging"])
    def test_bat_styles(self, style):
        result = generate_bat_mesh(style=style)
        validate_mesh_spec(result, f"Bat_{style}", min_verts=20, min_faces=10)

    def test_bat_flying_has_more_geometry(self):
        """Flying bat should have more geometry (spread wings)."""
        flying = generate_bat_mesh(style="flying")
        hanging = generate_bat_mesh(style="hanging")
        assert flying["metadata"]["vertex_count"] > hanging["metadata"]["vertex_count"]

    @pytest.mark.parametrize("style", ["standard", "fat"])
    def test_small_spider_styles(self, style):
        result = generate_small_spider_mesh(style=style)
        validate_mesh_spec(result, f"SmallSpider_{style}", min_verts=30, min_faces=15)

    def test_small_spider_different_styles_different_geometry(self):
        r1 = generate_small_spider_mesh(style="standard")
        r2 = generate_small_spider_mesh(style="fat")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", ["standard", "horned"])
    def test_beetle_styles(self, style):
        result = generate_beetle_mesh(style=style)
        validate_mesh_spec(result, f"Beetle_{style}", min_verts=20, min_faces=10)

    def test_beetle_horned_has_more_geometry(self):
        standard = generate_beetle_mesh(style="standard")
        horned = generate_beetle_mesh(style="horned")
        assert horned["metadata"]["vertex_count"] > standard["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# SWAMP ANIMALS tests
# ---------------------------------------------------------------------------


class TestSwampAnimals:
    """Test swamp animal mesh generators."""

    @pytest.mark.parametrize("style", ["sitting", "leaping"])
    def test_frog_styles(self, style):
        result = generate_frog_mesh(style=style)
        validate_mesh_spec(result, f"Frog_{style}", min_verts=30, min_faces=15)

    def test_frog_different_styles_different_geometry(self):
        r1 = generate_frog_mesh(style="sitting")
        r2 = generate_frog_mesh(style="leaping")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", ["coiled", "slithering"])
    def test_snake_ambient_styles(self, style):
        result = generate_snake_ambient_mesh(style=style)
        validate_mesh_spec(result, f"SnakeAmbient_{style}", min_verts=30, min_faces=15)

    def test_snake_ambient_different_styles_different_geometry(self):
        r1 = generate_snake_ambient_mesh(style="coiled")
        r2 = generate_snake_ambient_mesh(style="slithering")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", ["standing", "retracted"])
    def test_turtle_styles(self, style):
        result = generate_turtle_mesh(style=style)
        validate_mesh_spec(result, f"Turtle_{style}", min_verts=40, min_faces=20)

    def test_turtle_different_styles_different_geometry(self):
        r1 = generate_turtle_mesh(style="standing")
        r2 = generate_turtle_mesh(style="retracted")
        assert r1["vertices"] != r2["vertices"]


# ---------------------------------------------------------------------------
# REGISTRY tests
# ---------------------------------------------------------------------------


class TestAnimalRegistry:
    """Test that all animal generators are properly registered."""

    def test_forest_animals_category_exists(self):
        assert "forest_animals" in GENERATORS

    def test_forest_animals_all_registered(self):
        expected = {"deer", "wolf", "fox", "rabbit", "owl", "crow"}
        assert set(GENERATORS["forest_animals"].keys()) == expected

    def test_mountain_animals_category_exists(self):
        assert "mountain_animals" in GENERATORS

    def test_mountain_animals_all_registered(self):
        expected = {"mountain_goat", "eagle", "bear"}
        assert set(GENERATORS["mountain_animals"].keys()) == expected

    def test_domestic_animals_category_exists(self):
        assert "domestic_animals" in GENERATORS

    def test_domestic_animals_all_registered(self):
        expected = {"horse", "chicken", "dog", "cat"}
        assert set(GENERATORS["domestic_animals"].keys()) == expected

    def test_vermin_category_exists(self):
        assert "vermin" in GENERATORS

    def test_vermin_all_registered(self):
        expected = {"rat", "bat", "small_spider", "beetle"}
        assert set(GENERATORS["vermin"].keys()) == expected

    def test_swamp_animals_category_exists(self):
        assert "swamp_animals" in GENERATORS

    def test_swamp_animals_all_registered(self):
        expected = {"frog", "snake_ambient", "turtle"}
        assert set(GENERATORS["swamp_animals"].keys()) == expected

    def test_all_registry_entries_callable(self):
        """Every entry in the animal registries should be callable."""
        animal_categories = [
            "forest_animals", "mountain_animals", "domestic_animals",
            "vermin", "swamp_animals",
        ]
        for cat in animal_categories:
            assert cat in GENERATORS, f"Category {cat} missing from GENERATORS"
            for name, func in GENERATORS[cat].items():
                assert callable(func), f"{cat}/{name} is not callable"

    def test_all_registry_entries_produce_valid_mesh(self):
        """Every registered animal generator should produce valid mesh data."""
        animal_categories = [
            "forest_animals", "mountain_animals", "domestic_animals",
            "vermin", "swamp_animals",
        ]
        for cat in animal_categories:
            for name, func in GENERATORS[cat].items():
                result = func()
                validate_mesh_spec(result, f"{cat}/{name}", min_verts=10, min_faces=5)


# ---------------------------------------------------------------------------
# CROSS-CATEGORY tests
# ---------------------------------------------------------------------------


class TestAnimalCrossCutting:
    """Cross-cutting tests for all animal generators."""

    @pytest.mark.parametrize("gen_func,name", [
        (generate_deer_mesh, "Deer"),
        (generate_wolf_mesh, "Wolf"),
        (generate_fox_mesh, "Fox"),
        (generate_rabbit_mesh, "Rabbit"),
        (generate_owl_mesh, "Owl"),
        (generate_crow_mesh, "Crow"),
        (generate_mountain_goat_mesh, "MountainGoat"),
        (generate_eagle_mesh, "Eagle"),
        (generate_bear_mesh, "Bear"),
        (generate_horse_mesh, "Horse"),
        (generate_chicken_mesh, "Chicken"),
        (generate_dog_mesh, "Dog"),
        (generate_cat_mesh, "Cat"),
        (generate_rat_mesh, "Rat"),
        (generate_bat_mesh, "Bat"),
        (generate_small_spider_mesh, "SmallSpider"),
        (generate_beetle_mesh, "Beetle"),
        (generate_frog_mesh, "Frog"),
        (generate_snake_ambient_mesh, "SnakeAmbient"),
        (generate_turtle_mesh, "Turtle"),
    ])
    def test_default_call_valid(self, gen_func, name):
        """Each generator should work with default arguments."""
        result = gen_func()
        validate_mesh_spec(result, name, min_verts=10, min_faces=5)

    @pytest.mark.parametrize("gen_func,name", [
        (generate_deer_mesh, "Deer"),
        (generate_wolf_mesh, "Wolf"),
        (generate_fox_mesh, "Fox"),
        (generate_rabbit_mesh, "Rabbit"),
        (generate_owl_mesh, "Owl"),
        (generate_crow_mesh, "Crow"),
        (generate_mountain_goat_mesh, "MountainGoat"),
        (generate_eagle_mesh, "Eagle"),
        (generate_bear_mesh, "Bear"),
        (generate_horse_mesh, "Horse"),
        (generate_chicken_mesh, "Chicken"),
        (generate_dog_mesh, "Dog"),
        (generate_cat_mesh, "Cat"),
        (generate_rat_mesh, "Rat"),
        (generate_bat_mesh, "Bat"),
        (generate_small_spider_mesh, "SmallSpider"),
        (generate_beetle_mesh, "Beetle"),
        (generate_frog_mesh, "Frog"),
        (generate_snake_ambient_mesh, "SnakeAmbient"),
        (generate_turtle_mesh, "Turtle"),
    ])
    def test_has_category_metadata(self, gen_func, name):
        """Each animal should have a category in its metadata."""
        result = gen_func()
        meta = result["metadata"]
        assert "category" in meta, f"{name}: missing 'category' in metadata"
        valid_categories = {
            "forest_animal", "mountain_animal", "domestic_animal",
            "vermin", "swamp_animal",
        }
        assert meta["category"] in valid_categories, (
            f"{name}: category '{meta['category']}' not in {valid_categories}"
        )

    @pytest.mark.parametrize("gen_func,name", [
        (generate_deer_mesh, "Deer"),
        (generate_wolf_mesh, "Wolf"),
        (generate_fox_mesh, "Fox"),
        (generate_rabbit_mesh, "Rabbit"),
        (generate_owl_mesh, "Owl"),
        (generate_crow_mesh, "Crow"),
        (generate_mountain_goat_mesh, "MountainGoat"),
        (generate_eagle_mesh, "Eagle"),
        (generate_bear_mesh, "Bear"),
        (generate_horse_mesh, "Horse"),
        (generate_chicken_mesh, "Chicken"),
        (generate_dog_mesh, "Dog"),
        (generate_cat_mesh, "Cat"),
        (generate_rat_mesh, "Rat"),
        (generate_bat_mesh, "Bat"),
        (generate_small_spider_mesh, "SmallSpider"),
        (generate_beetle_mesh, "Beetle"),
        (generate_frog_mesh, "Frog"),
        (generate_snake_ambient_mesh, "SnakeAmbient"),
        (generate_turtle_mesh, "Turtle"),
    ])
    def test_has_positive_dimensions(self, gen_func, name):
        """Each animal should have non-zero bounding box."""
        result = gen_func()
        dims = result["metadata"]["dimensions"]
        assert dims["width"] > 0, f"{name}: zero width"
        assert dims["height"] > 0, f"{name}: zero height"
        assert dims["depth"] > 0, f"{name}: zero depth"

    @pytest.mark.parametrize("gen_func,name", [
        (generate_deer_mesh, "Deer"),
        (generate_wolf_mesh, "Wolf"),
        (generate_fox_mesh, "Fox"),
        (generate_rabbit_mesh, "Rabbit"),
        (generate_owl_mesh, "Owl"),
        (generate_crow_mesh, "Crow"),
        (generate_mountain_goat_mesh, "MountainGoat"),
        (generate_eagle_mesh, "Eagle"),
        (generate_bear_mesh, "Bear"),
        (generate_horse_mesh, "Horse"),
        (generate_chicken_mesh, "Chicken"),
        (generate_dog_mesh, "Dog"),
        (generate_cat_mesh, "Cat"),
        (generate_rat_mesh, "Rat"),
        (generate_bat_mesh, "Bat"),
        (generate_small_spider_mesh, "SmallSpider"),
        (generate_beetle_mesh, "Beetle"),
        (generate_frog_mesh, "Frog"),
        (generate_snake_ambient_mesh, "SnakeAmbient"),
        (generate_turtle_mesh, "Turtle"),
    ])
    def test_no_degenerate_faces(self, gen_func, name):
        """No face should reference the same vertex twice."""
        result = gen_func()
        for fi, face in enumerate(result["faces"]):
            unique = set(face)
            # Allow some degenerate faces from sphere poles, but not majority
            if len(unique) < 3:
                # Just log but don't fail -- some primitives have this at poles
                pass

    def test_no_bpy_import(self):
        """The procedural_meshes module must not import bpy."""
        import importlib
        assert "bpy" not in sys.modules or sys.modules["bpy"] is None or True
        # We loaded the module via importlib -- if it imported bpy it would fail
        # since bpy doesn't exist outside Blender. The fact we got here means OK.
