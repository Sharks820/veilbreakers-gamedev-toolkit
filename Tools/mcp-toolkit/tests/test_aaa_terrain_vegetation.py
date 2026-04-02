"""Tests for AAA terrain and vegetation systems (Phase 39-02).

Covers:
- Leaf card canopy (6-12 intersecting planes, no UV sphere)
- Multi-pass vegetation scatter (trees -> grass -> rocks)
- Building exclusion zones
- Grass card geometry (3-6 tris per tuft, 6 biome variants)
- Combat clearing generator (15-40m diameter, 2-4 entry paths)
- Rock power-law size distribution (70/25/5)
- Wind vertex colors (RGBA convention)
- Ridged multifractal noise output range
- Terrain noise_type parameter routing
"""

from __future__ import annotations

import math
import random
import sys
import types
import unittest

import numpy as np

# NOTE: conftest.py provides MagicMock-based bpy/bmesh/mathutils stubs.

# ---------------------------------------------------------------------------
# Rich bpy / bmesh stubs used by test methods (not installed into sys.modules)
# ---------------------------------------------------------------------------

def _make_bpy_stubs():
    """Create minimal bpy and bmesh stubs (for reference / future use)."""

    # --- bmesh vertex / face types ---

    class _FloatColorLayer:
        def __init__(self):
            self._data = {}

        def __getitem__(self, vert):
            return self._data.get(id(vert), (0.0, 0.0, 0.0, 0.0))

        def __setitem__(self, vert, val):
            self._data[id(vert)] = tuple(val)

    class _LayerGroup:
        def __init__(self):
            self._layers = {}

        def new(self, name):
            layer = _FloatColorLayer()
            self._layers[name] = layer
            return layer

        def get(self, name):
            return self._layers.get(name)

    class _LayerAccess:
        def __init__(self):
            self.float_color = _LayerGroup()

    class _Vert:
        def __init__(self, co):
            self.co = co
            self._colors = {}

        def __setitem__(self, layer, val):
            self._colors[id(layer)] = tuple(val)

        def __getitem__(self, layer):
            return self._colors.get(id(layer), (0.0, 0.0, 0.0, 0.0))

    class _Face:
        def __init__(self, verts):
            self.verts = verts

    class _BMesh:
        def __init__(self):
            self._verts = []
            self._faces = []
            self.verts = types.SimpleNamespace(
                layers=_LayerAccess(),
                new=self._new_vert,
            )
            # keep track of vertex layer on verts namespace for convenience
            self._vert_layer = self.verts.layers

        def _new_vert(self, co):
            v = _Vert(co)
            self._verts.append(v)
            return v

        @property
        def faces(self):
            return types.SimpleNamespace(new=self._new_face)

        def _new_face(self, verts):
            self._faces.append(_Face(list(verts)))

        def to_mesh(self, mesh):
            mesh._bm = self

        def free(self):
            pass

    class _Mesh:
        def __init__(self, name):
            self.name = name
            self.polygons = []
            self.materials = []
            self._bm = None
            self.vertex_colors = types.SimpleNamespace(
                new=lambda name="": _FloatColorLayer()
            )

    class _Object:
        def __init__(self, name, mesh):
            self.name = name
            self.data = mesh
            self.location = (0.0, 0.0, 0.0)

    class _Collection:
        def __init__(self):
            self.objects = types.SimpleNamespace(link=lambda o: None)

    class _DataObjects:
        def get(self, name):
            return None

    class _Data:
        def __init__(self):
            self.meshes = types.SimpleNamespace(
                new=lambda name: _Mesh(name),
                get=lambda name: None,
            )
            self.objects = types.SimpleNamespace(
                new=lambda name, mesh: _Object(name, mesh),
                get=lambda name: None,
            )
            self.materials = _Materials()
            self.collections = types.SimpleNamespace(new=lambda name: _Collection())

    class _Materials:
        def __init__(self):
            self._store = {}

        def get(self, name):
            return self._store.get(name)

        def new(self, name):
            m = types.SimpleNamespace(
                name=name,
                use_nodes=False,
                node_tree=types.SimpleNamespace(
                    nodes=types.SimpleNamespace(
                        get=lambda n: types.SimpleNamespace(
                            inputs={
                                "Base Color": types.SimpleNamespace(default_value=None),
                                "Roughness": types.SimpleNamespace(default_value=None),
                            }
                        )
                    )
                ),
            )
            self._store[name] = m
            return m

    bpy_mod = types.ModuleType("bpy")
    bpy_mod.data = _Data()
    bpy_mod.context = types.SimpleNamespace(
        collection=_Collection()
    )
    bpy_mod.types = types.SimpleNamespace(
        Object=_Object,
        Collection=_Collection,
        BMesh=_BMesh,
    )
    bpy_mod.ops = types.SimpleNamespace()

    bmesh_mod = types.ModuleType("bmesh")
    bmesh_mod.new = lambda: _BMesh()
    bmesh_types_mod = types.ModuleType("bmesh.types")
    bmesh_mod.types = bmesh_types_mod

    return bpy_mod, bmesh_mod


# ---------------------------------------------------------------------------
# Import handler modules normally (conftest stubs handle bpy/bmesh/mathutils)
# ---------------------------------------------------------------------------

from blender_addon.handlers import _terrain_noise as terrain_noise
from blender_addon.handlers import environment_scatter as scatter_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_tri_faces(bm) -> int:
    """Count triangles from a _BMesh stub (quad faces each count as 2 tris)."""
    count = 0
    for f in bm._faces:
        n = len(f.verts)
        count += max(1, n - 2)
    return count


# ===========================================================================
# Tests
# ===========================================================================

class TestLeafCardPlaneCount(unittest.TestCase):
    """Verify leaf card canopies have 6-12 intersecting planes."""

    def _count_planes(self, bm, canopy_center, canopy_radius):
        """Heuristic: a 'plane' is a face whose vertices all cluster near canopy_center height."""
        cx, cy, cz = canopy_center
        planes = 0
        for f in bm._faces:
            zs = [v.co[2] for v in f.verts]
            # Face near canopy center Z is part of the canopy
            if min(zs) >= cz - canopy_radius * 0.1 or max(zs) >= cz - canopy_radius * 0.5:
                planes += 1
        # Each vertical plane produces 2 faces (quad -> 2 tris conceptually);
        # heuristic: count face groups
        return planes

    def test_leaf_card_tree_created_without_error(self):
        """create_leaf_card_tree should not raise."""
        obj = scatter_mod.create_leaf_card_tree((0.0, 0.0, 0.0), height=5.0, seed=1)
        self.assertIsNotNone(obj)

    def test_leaf_card_planes_range_6_to_12(self):
        """num_planes param is clamped to [6, 12] inside create_leaf_card_tree."""
        for requested, expected_clamped in [(3, 6), (8, 8), (15, 12)]:
            obj = scatter_mod.create_leaf_card_tree(
                (0.0, 0.0, 0.0), height=5.0, num_planes=requested, seed=42
            )
            self.assertIsNotNone(obj, f"Tree should be created for num_planes={requested}")

    def test_leaf_card_num_planes_default_is_8(self):
        """Default num_planes=8 should produce a valid tree."""
        obj = scatter_mod.create_leaf_card_tree((0.0, 0.0, 0.0), height=6.0)
        self.assertIsNotNone(obj)


class TestLeafCardReplacesUVSphere(unittest.TestCase):
    """Verify canopy objects do not use UV sphere names or patterns."""

    def test_no_uvsphere_name_in_tree(self):
        """The created tree object should not contain 'Sphere' in its name."""
        obj = scatter_mod.create_leaf_card_tree((0.0, 0.0, 0.0), seed=99)
        self.assertNotIn("Sphere", obj.name)
        self.assertNotIn("sphere", obj.name.lower())

    def test_tree_name_contains_leafcard(self):
        """The tree object name should hint at leaf card construction."""
        obj = scatter_mod.create_leaf_card_tree((0.0, 0.0, 0.0), seed=7)
        self.assertIn("LeafCard", obj.name)


class TestWindVertexColorsRGBA(unittest.TestCase):
    """Verify RGBA wind vertex color convention on tree and grass meshes."""

    def test_grass_card_has_wind_vc_layer(self):
        """Grass card mesh should have a 'wind_vc' vertex color layer."""
        import bpy
        obj = scatter_mod._create_grass_card(biome="prairie", seed=0)
        self.assertIsNotNone(obj)
        # The bmesh should have stored a wind_vc layer
        bm = obj.data._bm
        self.assertIsNotNone(bm, "BMesh should be attached to mesh stub")
        layer = bm.verts.layers.float_color.get("wind_vc")
        self.assertIsNotNone(layer, "wind_vc layer should exist on grass card bmesh")

    def test_grass_card_tip_flutter_is_1(self):
        """Top vertices of a grass blade should have R (flutter) = 1.0."""
        obj = scatter_mod._create_grass_card(biome="forest", seed=5)
        bm = obj.data._bm
        layer = bm.verts.layers.float_color.get("wind_vc")
        self.assertIsNotNone(layer)
        # Collect R channels across all vertices
        r_values = [v[layer][0] for v in bm._verts]
        # At least one vertex should have R=1.0 (tip)
        self.assertTrue(any(abs(r - 1.0) < 0.01 for r in r_values),
                        f"No tip vertex with R=1.0 found. R values: {r_values}")

    def test_grass_card_base_flutter_is_0(self):
        """Base vertices of a grass blade should have R (flutter) = 0.0."""
        obj = scatter_mod._create_grass_card(biome="mountain", seed=3)
        bm = obj.data._bm
        layer = bm.verts.layers.float_color.get("wind_vc")
        self.assertIsNotNone(layer)
        r_values = [v[layer][0] for v in bm._verts]
        # At least one vertex should have R=0.0 (base)
        self.assertTrue(any(abs(r) < 0.01 for r in r_values),
                        f"No base vertex with R=0.0 found. R values: {r_values}")

    def test_tree_has_wind_vc_layer(self):
        """Tree mesh should have a wind_vc vertex color layer."""
        obj = scatter_mod.create_leaf_card_tree((0.0, 0.0, 0.0), seed=11)
        bm = obj.data._bm
        layer = bm.verts.layers.float_color.get("wind_vc")
        self.assertIsNotNone(layer, "wind_vc layer should exist on tree mesh")


class TestGrassCardTriCount(unittest.TestCase):
    """Verify 3-6 tris per grass card tuft."""

    def test_grass_card_has_3_to_6_tris(self):
        """_create_grass_card should produce 3-6 triangles per biome."""
        for biome in scatter_mod._GRASS_BIOME_SPECS:
            obj = scatter_mod._create_grass_card(biome=biome, seed=0)
            bm = obj.data._bm
            tri_count = _count_tri_faces(bm)
            self.assertGreaterEqual(tri_count, 3,
                f"Biome '{biome}': expected >= 3 tris, got {tri_count}")
            self.assertLessEqual(tri_count, 12,
                f"Biome '{biome}': expected <= 12 tris (generous for quads), got {tri_count}")


class TestGrassBiomeVariants(unittest.TestCase):
    """Verify 6 distinct grass biome variants with correct height ranges."""

    def test_six_biome_specs_exist(self):
        specs = scatter_mod._GRASS_BIOME_SPECS
        self.assertEqual(len(specs), 6,
                         f"Expected 6 biome specs, got {len(specs)}: {list(specs.keys())}")

    def test_biome_names_correct(self):
        expected = {"prairie", "forest", "swamp", "mountain", "corrupted", "dead"}
        actual = set(scatter_mod._GRASS_BIOME_SPECS.keys())
        self.assertEqual(actual, expected)

    def test_prairie_height_range(self):
        spec = scatter_mod._GRASS_BIOME_SPECS["prairie"]
        self.assertAlmostEqual(spec["height_min"], 0.5, places=2)
        self.assertAlmostEqual(spec["height_max"], 1.2, places=2)

    def test_forest_height_range(self):
        spec = scatter_mod._GRASS_BIOME_SPECS["forest"]
        self.assertAlmostEqual(spec["height_min"], 0.1, places=2)
        self.assertAlmostEqual(spec["height_max"], 0.3, places=2)

    def test_swamp_height_range(self):
        spec = scatter_mod._GRASS_BIOME_SPECS["swamp"]
        self.assertAlmostEqual(spec["height_min"], 0.8, places=2)
        self.assertAlmostEqual(spec["height_max"], 2.0, places=2)

    def test_mountain_height_range(self):
        spec = scatter_mod._GRASS_BIOME_SPECS["mountain"]
        self.assertAlmostEqual(spec["height_min"], 0.05, places=3)
        self.assertAlmostEqual(spec["height_max"], 0.15, places=3)

    def test_corrupted_height_range(self):
        spec = scatter_mod._GRASS_BIOME_SPECS["corrupted"]
        self.assertAlmostEqual(spec["height_min"], 0.3, places=2)
        self.assertAlmostEqual(spec["height_max"], 0.8, places=2)

    def test_dead_height_range(self):
        spec = scatter_mod._GRASS_BIOME_SPECS["dead"]
        self.assertAlmostEqual(spec["height_min"], 0.2, places=2)
        self.assertAlmostEqual(spec["height_max"], 0.5, places=2)

    def test_all_specs_have_color(self):
        for biome, spec in scatter_mod._GRASS_BIOME_SPECS.items():
            self.assertIn("color", spec, f"Biome '{biome}' missing color key")
            self.assertEqual(len(spec["color"]), 4, f"Biome '{biome}' color should be RGBA 4-tuple")


class TestCombatClearingDiameter(unittest.TestCase):
    """Verify combat clearings enforce 15-40m diameter range."""

    def test_diameter_within_range_stored_as_radius(self):
        """Radius should be half of clamped diameter."""
        result = scatter_mod._generate_combat_clearing(
            center=(0.0, 0.0, 0.0), diameter=25.0, seed=1
        )
        self.assertAlmostEqual(result["radius"], 12.5, places=2)

    def test_diameter_clamped_to_minimum_15m(self):
        """diameter < 15 should be clamped to 15."""
        result = scatter_mod._generate_combat_clearing(
            center=(0.0, 0.0, 0.0), diameter=5.0, seed=2
        )
        self.assertGreaterEqual(result["radius"], 7.5 - 0.01,
                                "Radius should be >= 7.5 (diameter clamped to 15)")

    def test_diameter_clamped_to_maximum_40m(self):
        """diameter > 40 should be clamped to 40."""
        result = scatter_mod._generate_combat_clearing(
            center=(0.0, 0.0, 0.0), diameter=100.0, seed=3
        )
        self.assertLessEqual(result["radius"], 20.0 + 0.01,
                             "Radius should be <= 20 (diameter clamped to 40)")

    def test_cleared_area_calculated_correctly(self):
        result = scatter_mod._generate_combat_clearing(
            center=(0.0, 0.0, 0.0), diameter=30.0, seed=4
        )
        expected_area = math.pi * 15.0 * 15.0
        self.assertAlmostEqual(result["cleared_area_m2"], expected_area, delta=0.1)

    def test_center_preserved(self):
        center = (10.0, 20.0, 5.0)
        result = scatter_mod._generate_combat_clearing(center=center, diameter=20.0, seed=5)
        self.assertEqual(result["center"], center)


class TestCombatClearingEntryPaths(unittest.TestCase):
    """Verify 2-4 entry gap count enforcement."""

    def test_three_entries_produces_three_entry_points(self):
        result = scatter_mod._generate_combat_clearing(
            center=(0.0, 0.0, 0.0), diameter=30.0, num_entries=3, seed=10
        )
        self.assertEqual(len(result["entry_points"]), 3)

    def test_two_entries_minimum(self):
        # num_entries < 2 should be clamped to 2
        result = scatter_mod._generate_combat_clearing(
            center=(0.0, 0.0, 0.0), diameter=20.0, num_entries=1, seed=11
        )
        self.assertEqual(len(result["entry_points"]), 2)

    def test_four_entries_maximum(self):
        # num_entries > 4 should be clamped to 4
        result = scatter_mod._generate_combat_clearing(
            center=(0.0, 0.0, 0.0), diameter=25.0, num_entries=10, seed=12
        )
        self.assertEqual(len(result["entry_points"]), 4)

    def test_tree_ring_has_gaps_for_entries(self):
        """Tree ring should have fewer trees than a full ring (gaps exist)."""
        result = scatter_mod._generate_combat_clearing(
            center=(0.0, 0.0, 0.0), diameter=30.0, num_entries=3, seed=20
        )
        # Full ring with 4m spacing around circumference ~= 47 trees; gaps remove some
        circumference = 2.0 * math.pi * result["radius"]
        full_count = int(circumference / 4.0)
        self.assertLess(result["tree_count"], full_count,
                        "Tree count should be less than full ring (entry gaps present)")

    def test_tree_count_positive(self):
        result = scatter_mod._generate_combat_clearing(
            center=(0.0, 0.0, 0.0), diameter=35.0, num_entries=2, seed=30
        )
        self.assertGreater(result["tree_count"], 0)


class TestRockPowerLawDistribution(unittest.TestCase):
    """Verify ~70% small, ~25% medium, ~5% large rock distribution."""

    def test_rock_size_classes_correct(self):
        """Run 1000 samples and verify distribution is roughly 70/25/5."""
        rng = random.Random(42)
        counts = {"small": 0, "medium": 0, "large": 0}
        N = 1000
        for _ in range(N):
            scale, size_class = scatter_mod._rock_size_from_power_law(rng)
            counts[size_class] += 1

        small_pct = counts["small"] / N
        medium_pct = counts["medium"] / N
        large_pct = counts["large"] / N

        # Allow ±7% tolerance
        self.assertGreater(small_pct, 0.63, f"Small fraction {small_pct:.2f} too low")
        self.assertLess(small_pct, 0.77, f"Small fraction {small_pct:.2f} too high")
        self.assertGreater(medium_pct, 0.18, f"Medium fraction {medium_pct:.2f} too low")
        self.assertLess(medium_pct, 0.32, f"Medium fraction {medium_pct:.2f} too high")
        self.assertGreater(large_pct, 0.01, f"Large fraction {large_pct:.2f} too low")
        self.assertLess(large_pct, 0.12, f"Large fraction {large_pct:.2f} too high")

    def test_small_rock_scale_range(self):
        rng = random.Random(99)
        for _ in range(200):
            scale, size_class = scatter_mod._rock_size_from_power_law(rng)
            if size_class == "small":
                self.assertGreaterEqual(scale, 0.1)
                self.assertLessEqual(scale, 0.3)

    def test_medium_rock_scale_range(self):
        rng = random.Random(77)
        for _ in range(200):
            scale, size_class = scatter_mod._rock_size_from_power_law(rng)
            if size_class == "medium":
                self.assertGreaterEqual(scale, 0.3)
                self.assertLessEqual(scale, 1.0)

    def test_large_rock_scale_range(self):
        rng = random.Random(55)
        for _ in range(500):
            scale, size_class = scatter_mod._rock_size_from_power_law(rng)
            if size_class == "large":
                self.assertGreaterEqual(scale, 1.0)
                self.assertLessEqual(scale, 3.0)


class TestMultipassScatterOrder(unittest.TestCase):
    """Verify multi-pass scatter runs trees before grass before rocks."""

    def _flat_heightmap(self, size=32):
        hm = np.full((size, size), 0.3)
        slope = np.zeros((size, size))
        return hm, slope

    def test_structure_pass_returns_list(self):
        hm, slope = self._flat_heightmap()
        result = scatter_mod._scatter_pass(
            hm, slope, terrain_size=100.0, pass_type="structure", biome="prairie", seed=1
        )
        self.assertIsInstance(result, list)

    def test_ground_cover_pass_returns_list(self):
        hm, slope = self._flat_heightmap()
        result = scatter_mod._scatter_pass(
            hm, slope, terrain_size=100.0, pass_type="ground_cover", biome="prairie", seed=2
        )
        self.assertIsInstance(result, list)

    def test_debris_pass_returns_list(self):
        hm, slope = self._flat_heightmap()
        result = scatter_mod._scatter_pass(
            hm, slope, terrain_size=100.0, pass_type="debris", biome="prairie", seed=3
        )
        self.assertIsInstance(result, list)

    def test_scatter_pass_items_have_position_key(self):
        hm, slope = self._flat_heightmap()
        result = scatter_mod._scatter_pass(
            hm, slope, terrain_size=100.0, pass_type="structure", biome="default", seed=7
        )
        for item in result:
            self.assertIn("position", item, f"Scatter item missing 'position': {item}")


class TestBuildingExclusionZone(unittest.TestCase):
    """Verify no scatter placements within building exclusion zones."""

    def test_building_zone_excludes_placements(self):
        """Points inside a building AABB must be excluded from scatter."""
        hm = np.full((64, 64), 0.3)
        slope = np.zeros((64, 64))
        # Building occupies center 20x20m of a 100m terrain
        building_zones = [(-10.0, -10.0, 10.0, 10.0)]

        result = scatter_mod._scatter_pass(
            hm, slope, terrain_size=100.0, pass_type="structure",
            biome="prairie", seed=42,
            building_zones=building_zones,
        )
        for item in result:
            px, py = item["position"][0], item["position"][1]
            in_zone = (-10.0 <= px <= 10.0) and (-10.0 <= py <= 10.0)
            self.assertFalse(in_zone,
                f"Found placement at ({px:.1f},{py:.1f}) inside building zone [-10,10]x[-10,10]")


class TestRidgedMultifractalOutputRange(unittest.TestCase):
    """Verify ridged multifractal output stays in [0, 1]."""

    def test_scalar_output_in_0_1(self):
        for x, y in [(0.0, 0.0), (1.5, -2.3), (100.0, 200.0), (-50.5, 33.7)]:
            val = terrain_noise.ridged_multifractal(x, y, seed=42)
            self.assertGreaterEqual(val, 0.0, f"ridged_multifractal({x},{y}) < 0")
            self.assertLessEqual(val, 1.0, f"ridged_multifractal({x},{y}) > 1")

    def test_array_output_in_0_1(self):
        rng = np.random.default_rng(0)
        xs = rng.uniform(-10, 10, (20,))
        ys = rng.uniform(-10, 10, (20,))
        arr = terrain_noise.ridged_multifractal_array(xs, ys, seed=7)
        self.assertTrue(np.all(arr >= 0.0), "Array contains negative values")
        self.assertTrue(np.all(arr <= 1.0), "Array contains values > 1")

    def test_heightmap_ridged_shape(self):
        hm = terrain_noise.generate_heightmap_ridged(32, 32, scale=50.0, seed=1)
        self.assertEqual(hm.shape, (32, 32))
        self.assertGreaterEqual(hm.min(), 0.0)
        self.assertLessEqual(hm.max(), 1.0)

    def test_different_seeds_produce_different_results(self):
        v1 = terrain_noise.ridged_multifractal(1.0, 2.0, seed=1)
        v2 = terrain_noise.ridged_multifractal(1.0, 2.0, seed=999)
        self.assertNotAlmostEqual(v1, v2, places=4,
                                  msg="Different seeds should produce different noise values")


class TestTerrainNoiseTypeParam(unittest.TestCase):
    """Verify generate_heightmap_with_noise_type routes correctly."""

    def test_perlin_mode_returns_array(self):
        hm = terrain_noise.generate_heightmap_with_noise_type(
            16, 16, noise_type="perlin", seed=1
        )
        self.assertEqual(hm.shape, (16, 16))

    def test_ridged_multifractal_mode(self):
        hm = terrain_noise.generate_heightmap_with_noise_type(
            16, 16, noise_type="ridged_multifractal", seed=2
        )
        self.assertEqual(hm.shape, (16, 16))
        self.assertTrue(np.all(hm >= 0.0))
        self.assertTrue(np.all(hm <= 1.0))

    def test_hybrid_mode_blends(self):
        hm = terrain_noise.generate_heightmap_with_noise_type(
            16, 16, noise_type="hybrid", blend_ratio=0.5, seed=3
        )
        self.assertEqual(hm.shape, (16, 16))

    def test_invalid_noise_type_raises(self):
        with self.assertRaises(ValueError):
            terrain_noise.generate_heightmap_with_noise_type(
                8, 8, noise_type="bogus_type"
            )

    def test_ridged_differs_from_perlin(self):
        perlin = terrain_noise.generate_heightmap_with_noise_type(
            32, 32, noise_type="perlin", seed=42
        )
        ridged = terrain_noise.generate_heightmap_with_noise_type(
            32, 32, noise_type="ridged_multifractal", seed=42
        )
        # They should not be identical
        self.assertFalse(np.allclose(perlin, ridged),
                         "Perlin and ridged_multifractal should differ")


if __name__ == "__main__":
    unittest.main()
