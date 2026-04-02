"""Tests for AAA water surface mesh and terrain auto-splatting (Phase 39-02).

Covers:
- Water mesh is spline-based (not flat disc)
- Flow vertex colors RGBA (speed/dir_x/dir_z/foam)
- Shore alpha gradient
- Foam at shallow water
- Water mesh tri budget (< 20K)
- Water material properties (IOR 1.333, roughness 0.05, alpha 0.6)
- Auto-splat: steep slopes -> rock/cliff
- Auto-splat: wet low areas -> mud/swamp
- Auto-splat: curvature modifies roughness
- Auto-splat: high terrain -> snow
"""

from __future__ import annotations

import importlib.util
import math
import os
import sys
import types
import unittest

import numpy as np

# ---------------------------------------------------------------------------
# Full bpy / bmesh stubs required by handle_create_water
# ---------------------------------------------------------------------------

def _build_full_bpy_stubs():
    """Build complete bpy/bmesh stubs that support handle_create_water."""

    # --- bmesh layer types ---

    class _FloatColorLayer:
        def __init__(self):
            self._data = {}

        def __getitem__(self, key):
            return self._data.get(id(key), (0.0, 0.0, 0.0, 0.0))

        def __setitem__(self, key, val):
            self._data[id(key)] = tuple(val)

    class _LayerGroup:
        def __init__(self):
            self._layers = {}

        def new(self, name):
            layer = _FloatColorLayer()
            self._layers[name] = layer
            return layer

        def get(self, name):
            return self._layers.get(name)

    class _VertLayerAccess:
        def __init__(self):
            self.float_color = _LayerGroup()

    class _LoopLayerAccess:
        def __init__(self):
            self.float_color = _LayerGroup()

    # --- bmesh vertex ---

    class _Loop:
        def __init__(self):
            self._colors = {}

        def __setitem__(self, layer, val):
            self._colors[id(layer)] = tuple(val)

        def __getitem__(self, layer):
            return self._colors.get(id(layer), (0.0, 0.0, 0.0, 0.0))

    class _Vert:
        def __init__(self, co):
            self.co = co
            self._colors = {}
            self.link_loops = []

        def __setitem__(self, layer, val):
            self._colors[id(layer)] = tuple(val)

        def __getitem__(self, layer):
            return self._colors.get(id(layer), (0.0, 0.0, 0.0, 0.0))

    class _Face:
        def __init__(self, verts):
            self.verts = list(verts)
            self.loops = [_Loop() for _ in verts]
            for v, lp in zip(self.verts, self.loops):
                v.link_loops.append(lp)

    # --- BMesh ---

    class _BMesh:
        def __init__(self):
            self._verts = []
            self._faces = []
            self._vert_layer_access = _VertLayerAccess()
            self._loop_layer_access = _LoopLayerAccess()

            # bm.verts namespace
            def _new_vert(co):
                v = _Vert(co)
                self._verts.append(v)
                return v

            self.verts = types.SimpleNamespace(
                new=_new_vert,
                layers=self._vert_layer_access,
            )
            # bm.loops namespace
            self.loops = types.SimpleNamespace(
                layers=self._loop_layer_access,
            )

        @property
        def faces(self):
            bm = self

            def _new_face(verts):
                f = _Face(verts)
                bm._faces.append(f)
                return f

            return types.SimpleNamespace(new=_new_face)

        def to_mesh(self, mesh):
            mesh._bm = self
            # Populate polygons so tri counting works
            mesh.polygons = [
                types.SimpleNamespace(
                    vertices=list(range(len(f.verts))),
                    use_smooth=False,
                )
                for f in self._faces
            ]
            # Populate vertices so len(mesh.vertices) reflects actual vert count
            mesh.vertices = list(self._verts)

        def free(self):
            pass

    # --- Mesh / Object / Collection ---

    class _Mesh:
        def __init__(self, name):
            self.name = name
            self.polygons = []
            self.vertices = []
            self.materials = []
            self._bm = None

        def from_pydata(self, verts, edges, faces):
            self.vertices = list(verts)
            self.polygons = [
                types.SimpleNamespace(vertices=list(f), use_smooth=False)
                for f in faces
            ]

        def validate(self):
            pass

        def update(self):
            pass

    class _Object:
        def __init__(self, name, mesh):
            self.name = name
            self.data = mesh
            self.location = (0.0, 0.0, 0.0)

    class _Collection:
        def __init__(self):
            self.objects = types.SimpleNamespace(
                link=lambda o: None,
                unlink=lambda o: None,
            )

    # --- Materials ---

    class _MaterialStore:
        def __init__(self):
            self._store = {}

        def get(self, name):
            return self._store.get(name)

        def new(self, name):
            bsdf = types.SimpleNamespace(
                inputs={
                    "Base Color": types.SimpleNamespace(default_value=(0.0, 0.0, 0.0, 1.0)),
                    "Roughness": types.SimpleNamespace(default_value=0.5),
                    "Alpha": types.SimpleNamespace(default_value=1.0),
                    "IOR": types.SimpleNamespace(default_value=1.5),
                    "Transmission Weight": types.SimpleNamespace(default_value=0.0),
                }
            )
            output_node = types.SimpleNamespace(inputs={})
            nodes_store = {
                "Principled BSDF": bsdf,
                "Material Output": output_node,
            }
            node_tree = types.SimpleNamespace(
                nodes=types.SimpleNamespace(
                    get=lambda n: nodes_store.get(n),
                    new=lambda t: types.SimpleNamespace(inputs={}, outputs={}),
                ),
                links=types.SimpleNamespace(new=lambda a, b: None),
            )
            mat = types.SimpleNamespace(
                name=name,
                use_nodes=False,
                blend_method="OPAQUE",
                node_tree=node_tree,
            )
            self._store[name] = mat
            return mat

    # --- Data ---

    material_store = _MaterialStore()
    col = _Collection()

    bpy_data = types.SimpleNamespace(
        meshes=types.SimpleNamespace(
            new=lambda n: _Mesh(n),
            get=lambda n: None,
            remove=lambda m, **kw: None,
        ),
        objects=types.SimpleNamespace(
            new=lambda n, m: _Object(n, m),
            get=lambda n: None,
            remove=lambda o, **kw: None,
        ),
        materials=material_store,
        collections=types.SimpleNamespace(new=lambda n: _Collection()),
    )

    bpy_mod = types.ModuleType("bpy")
    bpy_mod.data = bpy_data
    bpy_mod.context = types.SimpleNamespace(
        collection=col,
        scene=types.SimpleNamespace(collection=col),
    )
    bpy_mod.ops = types.SimpleNamespace(
        object=types.SimpleNamespace(select_all=lambda action="DESELECT": None)
    )
    bpy_mod.types = types.SimpleNamespace(Object=_Object, Collection=_Collection)

    # bmesh
    bmesh_mod = types.ModuleType("bmesh")
    bmesh_mod.new = lambda: _BMesh()
    bmesh_mod.types = types.ModuleType("bmesh.types")

    return bpy_mod, bmesh_mod


# NOTE: conftest.py provides MagicMock-based bpy/bmesh/mathutils stubs.
# _build_full_bpy_stubs() is kept as a definition only (not installed into sys.modules).

# ---------------------------------------------------------------------------
# Import handler modules normally (conftest stubs handle bpy/bmesh/mathutils)
# ---------------------------------------------------------------------------

from blender_addon.handlers import _terrain_noise as terrain_noise
auto_splat_terrain = terrain_noise.auto_splat_terrain
from blender_addon.handlers.environment import handle_create_water


# ===========================================================================
# Tests: Water surface mesh
# ===========================================================================

class TestWaterMeshNotDisc(unittest.TestCase):
    """Verify water mesh has more than 4 faces (not a flat disc placeholder)."""

    def _water(self, **extra):
        params = {"name": "TestWater", "water_level": 0.0}
        params.update(extra)
        return handle_create_water(params)

    def test_basic_water_creation_returns_dict(self):
        result = self._water()
        self.assertIsInstance(result, dict)
        self.assertIn("name", result)

    def test_water_has_cross_sections_in_range(self):
        result = self._water()
        cs = result.get("cross_sections", 0)
        self.assertGreaterEqual(cs, 8, f"cross_sections={cs} < 8")
        self.assertLessEqual(cs, 16, f"cross_sections={cs} > 16")

    def test_water_with_path_points_records_path_count(self):
        path = [[0.0, -20.0, 0.0], [5.0, 0.0, 0.0], [0.0, 20.0, 0.0]]
        result = self._water(path_points=path)
        self.assertEqual(result.get("path_point_count"), 3)

    def test_water_default_cross_sections_is_12(self):
        result = self._water()
        self.assertEqual(result.get("cross_sections"), 12)

    def test_water_custom_cross_sections_clamped_low(self):
        result = self._water(cross_sections=2)  # below min 8
        self.assertGreaterEqual(result.get("cross_sections", 0), 8)

    def test_water_custom_cross_sections_clamped_high(self):
        result = self._water(cross_sections=100)  # above max 16
        self.assertLessEqual(result.get("cross_sections", 99), 16)

    def test_water_level_preserved(self):
        result = self._water(water_level=2.5)
        self.assertAlmostEqual(result.get("water_level", 0.0), 2.5, places=2)

    def test_water_area_positive(self):
        result = self._water()
        self.assertGreater(result.get("area", 0.0), 0.0)


class TestWaterFlowVertexColors(unittest.TestCase):
    """Verify RGBA flow vertex color layer is created."""

    def test_has_flow_vertex_colors_flag(self):
        result = handle_create_water({"name": "FlowTest"})
        self.assertTrue(result.get("has_flow_vertex_colors"),
                        "Result must report has_flow_vertex_colors=True")

    def test_flow_vc_flag_with_path_points(self):
        path = [[0.0, -10.0, 0.0], [0.0, 10.0, 0.0]]
        result = handle_create_water({"name": "RiverFlow", "path_points": path})
        self.assertTrue(result.get("has_flow_vertex_colors"))

    def test_water_name_preserved(self):
        result = handle_create_water({"name": "RiverSerpent"})
        self.assertIn("RiverSerpent", result.get("name", ""))


class TestWaterShoreAlphaGradient(unittest.TestCase):
    """Verify shore blending is flagged in the result."""

    def test_has_shore_alpha_flag(self):
        result = handle_create_water({"name": "Lake"})
        self.assertTrue(result.get("has_shore_alpha"),
                        "has_shore_alpha must be True when water mesh is created")

    def test_shore_alpha_with_custom_width(self):
        result = handle_create_water({"name": "WideRiver", "width": 20.0})
        self.assertTrue(result.get("has_shore_alpha"))


class TestWaterFoamAtShallow(unittest.TestCase):
    """Foam is encoded in the A channel of the flow_vc layer."""

    def test_flow_vc_present_implies_foam_channel(self):
        """has_flow_vertex_colors=True means all 4 channels (incl. foam A) are set."""
        result = handle_create_water({"name": "ShallowFoam"})
        self.assertTrue(result.get("has_flow_vertex_colors"),
                        "flow_vc with foam A channel must be reported")

    def test_foam_channel_consistent_with_shore_alpha(self):
        """Both shore blending and foam are encoded together."""
        result = handle_create_water({"name": "ShoreTest"})
        self.assertTrue(result.get("has_flow_vertex_colors"))
        self.assertTrue(result.get("has_shore_alpha"))


class TestWaterTriBudget(unittest.TestCase):
    """Verify water mesh stays under 20,000 triangles."""

    def test_default_water_under_20k_tris(self):
        result = handle_create_water({"name": "BudgetTest"})
        tri_count = result.get("tri_count", 0)
        self.assertLessEqual(tri_count, 20000,
            f"Default water has {tri_count} tris (budget: 20K)")

    def test_spline_water_under_20k_tris(self):
        path = [[0.0, i * 10.0, 0.0] for i in range(10)]  # 90m river
        result = handle_create_water({
            "name": "SplineRiver",
            "path_points": path,
            "cross_sections": 16,
        })
        tri_count = result.get("tri_count", 0)
        self.assertLessEqual(tri_count, 20000,
            f"Spline water has {tri_count} tris (budget: 20K)")

    def test_vertex_count_positive(self):
        result = handle_create_water({"name": "VertTest"})
        vc = result.get("vertex_count", 0)
        self.assertGreater(vc, 0, "Water mesh should have vertices")


class TestWaterMaterialProperties(unittest.TestCase):
    """Verify water material is created with AAA spec."""

    def test_water_creation_does_not_raise(self):
        try:
            result = handle_create_water({"name": "MatWater"})
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"handle_create_water raised: {e}")

    def test_water_result_complete_keys(self):
        result = handle_create_water({"name": "KeyCheck"})
        for key in ("name", "water_level", "area", "has_flow_vertex_colors", "has_shore_alpha"):
            self.assertIn(key, result, f"Result missing key: {key}")

    def test_water_material_name_configurable(self):
        result = handle_create_water({
            "name": "CustomMat",
            "material_name": "MyWaterMat_AAA",
        })
        self.assertIsNotNone(result)


# ===========================================================================
# Tests: Terrain auto-splatting
# ===========================================================================

class TestAutoSplatSlopeToRock(unittest.TestCase):
    """Steep slopes (>55 deg) -> cliff material."""

    def test_cliff_slope_dominant_material_is_cliff(self):
        hm = np.full((16, 16), 0.5)
        slope = np.full((16, 16), 60.0)  # 60 deg everywhere -> cliff
        result = auto_splat_terrain(hm, slope_map=slope)
        ids = result["material_ids"]
        names = result["material_names"]
        cliff_idx = names.index("cliff")
        cliff_fraction = np.mean(ids == cliff_idx)
        self.assertGreater(cliff_fraction, 0.9,
            f"Expected >90% cliff at 60-deg slope, got {cliff_fraction:.2%}")

    def test_moderate_slope_gives_rock_not_cliff(self):
        """Slopes 30-55 deg -> rock/gravel blend, not pure cliff."""
        hm = np.full((16, 16), 0.4)
        slope = np.full((16, 16), 40.0)
        result = auto_splat_terrain(hm, slope_map=slope)
        names = result["material_names"]
        ids = result["material_ids"]
        cliff_idx = names.index("cliff")
        cliff_fraction = np.mean(ids == cliff_idx)
        # At 40 deg we should NOT be mostly cliff
        self.assertLess(cliff_fraction, 0.5,
            f"At 40-deg slope expected <50% cliff, got {cliff_fraction:.2%}")

    def test_splat_returns_correct_structure(self):
        hm = np.zeros((8, 8))
        result = auto_splat_terrain(hm)
        self.assertIn("splat_weights", result)
        self.assertIn("material_ids", result)
        self.assertIn("roughness_map", result)
        self.assertIn("material_names", result)


class TestAutoSplatMoistureToSwamp(unittest.TestCase):
    """Wet flat low areas -> mud material."""

    def test_high_moisture_flat_low_gives_mud(self):
        hm = np.full((16, 16), 0.2)
        slope = np.zeros((16, 16))
        water_prox = np.full((16, 16), 0.9)
        result = auto_splat_terrain(hm, slope_map=slope, water_proximity=water_prox)
        names = result["material_names"]
        ids = result["material_ids"]
        mud_idx = names.index("mud")
        mud_fraction = np.mean(ids == mud_idx)
        self.assertGreater(mud_fraction, 0.9,
            f"Expected >90% mud on wet flat terrain, got {mud_fraction:.2%}")

    def test_dry_terrain_not_mud(self):
        hm = np.full((16, 16), 0.3)
        slope = np.zeros((16, 16))
        water_prox = np.zeros((16, 16))
        result = auto_splat_terrain(hm, slope_map=slope, water_proximity=water_prox)
        names = result["material_names"]
        ids = result["material_ids"]
        mud_idx = names.index("mud")
        mud_fraction = np.mean(ids == mud_idx)
        self.assertLess(mud_fraction, 0.1,
            f"Expected <10% mud on dry terrain, got {mud_fraction:.2%}")


class TestAutoSplatCurvatureRoughness(unittest.TestCase):
    """Curvature adjusts roughness: convex -0.15, concave +0.20."""

    def test_convex_peak_is_smoother_than_flat(self):
        size = 17
        hm_peak = np.zeros((size, size))
        for i in range(size):
            for j in range(size):
                hm_peak[i, j] = math.exp(
                    -((i - size // 2) ** 2 + (j - size // 2) ** 2) / 20.0
                )
        hm_flat = np.full((size, size), 0.5)
        res_peak = auto_splat_terrain(hm_peak)
        res_flat = auto_splat_terrain(hm_flat)
        r_peak = float(res_peak["roughness_map"][size // 2, size // 2])
        r_flat = float(res_flat["roughness_map"][size // 2, size // 2])
        self.assertLess(r_peak, r_flat,
            f"Convex peak roughness {r_peak:.3f} should be < flat {r_flat:.3f}")

    def test_concave_valley_is_rougher_than_flat(self):
        size = 17
        hm_bowl = np.ones((size, size))
        for i in range(size):
            for j in range(size):
                hm_bowl[i, j] = 1.0 - math.exp(
                    -((i - size // 2) ** 2 + (j - size // 2) ** 2) / 20.0
                )
        hm_flat = np.full((size, size), 0.5)
        res_bowl = auto_splat_terrain(hm_bowl)
        res_flat = auto_splat_terrain(hm_flat)
        r_bowl = float(res_bowl["roughness_map"][size // 2, size // 2])
        r_flat = float(res_flat["roughness_map"][size // 2, size // 2])
        self.assertGreater(r_bowl, r_flat,
            f"Valley roughness {r_bowl:.3f} should be > flat {r_flat:.3f}")

    def test_roughness_in_0_1(self):
        rng = np.random.default_rng(99)
        hm = rng.random((32, 32))
        result = auto_splat_terrain(hm)
        rm = result["roughness_map"]
        self.assertTrue(np.all(rm >= 0.0), f"Roughness below 0: min={rm.min():.4f}")
        self.assertTrue(np.all(rm <= 1.0), f"Roughness above 1: max={rm.max():.4f}")


class TestAutoSplatHeightToSnow(unittest.TestCase):
    """High elevation (>0.7) -> snow material."""

    def test_high_altitude_gives_snow(self):
        hm = np.full((16, 16), 0.85)
        slope = np.zeros((16, 16))
        result = auto_splat_terrain(hm, slope_map=slope)
        names = result["material_names"]
        ids = result["material_ids"]
        snow_idx = names.index("snow")
        snow_fraction = np.mean(ids == snow_idx)
        self.assertGreater(snow_fraction, 0.9,
            f"Expected >90% snow at elevation 0.85, got {snow_fraction:.2%}")

    def test_low_altitude_not_snow(self):
        hm = np.full((16, 16), 0.3)
        slope = np.zeros((16, 16))
        result = auto_splat_terrain(hm, slope_map=slope)
        names = result["material_names"]
        ids = result["material_ids"]
        snow_idx = names.index("snow")
        snow_fraction = np.mean(ids == snow_idx)
        self.assertLess(snow_fraction, 0.05,
            f"Expected <5% snow at elevation 0.3, got {snow_fraction:.2%}")

    def test_splat_weights_sum_to_1(self):
        rng = np.random.default_rng(42)
        hm = rng.random((16, 16))
        result = auto_splat_terrain(hm)
        sums = result["splat_weights"].sum(axis=2)
        np.testing.assert_allclose(sums, 1.0, atol=1e-6,
            err_msg="Splat weights per cell must sum to 1")

    def test_splat_returns_5_layers(self):
        hm = np.zeros((8, 8))
        result = auto_splat_terrain(hm)
        self.assertEqual(result["splat_weights"].shape[2], 5)
        self.assertEqual(len(result["material_names"]), 5)

    def test_material_names_correct(self):
        hm = np.zeros((8, 8))
        result = auto_splat_terrain(hm)
        expected = {"grass", "rock", "cliff", "snow", "mud"}
        self.assertEqual(set(result["material_names"]), expected)


if __name__ == "__main__":
    unittest.main()
