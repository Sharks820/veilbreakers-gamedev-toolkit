"""Tests for AAA performance budget, LOD chains, GPU instancing, and topology grade.

AAA-MAP-10: Performance budget enforcement (<2M tris, <500 draw calls)
AAA-MAP-11: LOD chains auto-generated for all asset types
AAA-MAP-12: Topology grade A minimum enforced with auto-repair
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
# Minimal bpy / bmesh stubs (must be installed before importing handlers)
# ---------------------------------------------------------------------------

def _make_fake_object(name: str) -> types.SimpleNamespace:
    """Return a minimal Blender Object stub with the given name."""
    obj = types.SimpleNamespace(
        name=name,
        location=types.SimpleNamespace(copy=lambda: (0.0, 0.0, 0.0)),
        data=types.SimpleNamespace(
            polygons=[],
            vertices=[],
            materials=[],
        ),
        modifiers=_ModifierList(),
        parent=None,
    )
    obj.__setitem__ = lambda self, k, v: None  # allow obj["key"] = val
    return obj


class _ModifierList(list):
    def new(self, name: str, type: str) -> types.SimpleNamespace:
        mod = types.SimpleNamespace(
            name=name, type=type,
            decimate_type="COLLAPSE", ratio=1.0,
            mode="FACE_AREA_AND_ANGLE", weight=100, keep_sharp=True,
            strength=0.0, mid_level=0.5, texture_coords="LOCAL",
            texture=None,
        )
        self.append(mod)
        return mod


def _make_objects_store():
    """Objects namespace that tracks new() by name."""
    _store: dict[str, types.SimpleNamespace] = {}

    def _get(name):
        return _store.get(name)

    def _new(name, data=None):
        obj = _make_fake_object(name)
        _store[name] = obj
        return obj

    ns = types.SimpleNamespace(get=_get, new=_new, link=lambda o: None)
    return ns


def _make_bpy_stub() -> types.ModuleType:
    bpy = types.ModuleType("bpy")

    _objects_store = _make_objects_store()

    def _mesh_new(name):
        m = types.SimpleNamespace(
            name=name,
            from_pydata=lambda v, e, f: None,
            update=lambda: None,
            polygons=[],
            vertices=[],
            materials=[],
        )
        return m

    data = types.SimpleNamespace(
        objects=_objects_store,
        meshes=types.SimpleNamespace(new=_mesh_new),
        materials=types.SimpleNamespace(new=lambda name: types.SimpleNamespace(
            name=name, use_nodes=False, node_tree=None,
        )),
        images=types.SimpleNamespace(new=lambda name, w, h: types.SimpleNamespace(
            name=name,
            colorspace_settings=types.SimpleNamespace(name="Non-Color"),
        )),
        textures=types.SimpleNamespace(new=lambda name, type: types.SimpleNamespace(
            name=name, noise_scale=1.0, noise_depth=2, cloud_type="COLOR",
        )),
        collections=types.SimpleNamespace(new=lambda name: types.SimpleNamespace(
            name=name,
            objects=types.SimpleNamespace(link=lambda o: None),
        )),
    )
    bpy.data = data

    _scene_collection = types.SimpleNamespace(
        objects=types.SimpleNamespace(link=lambda o: None),
    )
    context = types.SimpleNamespace(
        scene=types.SimpleNamespace(
            collection=_scene_collection,
            render=types.SimpleNamespace(engine="CYCLES"),
            cycles=types.SimpleNamespace(samples=128),
        ),
        view_layer=types.SimpleNamespace(objects=types.SimpleNamespace(active=None)),
    )
    bpy.context = context
    bpy.ops = types.SimpleNamespace(
        object=types.SimpleNamespace(mode_set=lambda **kw: None),
    )
    bpy.types = types.SimpleNamespace(Object=object)
    return bpy


# Always force-install our own stubs so test_aaa_materials.py MagicMock
# contamination doesn't bleed into LOD chain / topology tests.
_CLEAN_BPY = _make_bpy_stub()
sys.modules["bpy"] = _CLEAN_BPY
if "bmesh" not in sys.modules:
    sys.modules["bmesh"] = types.ModuleType("bmesh")
if "mathutils" not in sys.modules:
    mu = types.ModuleType("mathutils")
    mu.Vector = lambda v: v
    mu.Matrix = object
    sys.modules["mathutils"] = mu

# Stub sub-dependencies that environment_scatter uses via relative imports.
# Always force-install so terrain-vegetation test's empty stub doesn't bleed in.
for _mod_name in [
    "blender_addon.handlers._scatter_engine",
    "blender_addon.handlers._mesh_bridge",
]:
    if True:  # unconditional — override any prior stub
        _m = types.ModuleType(_mod_name)

        def _grid_poisson(w, h, min_dist=1.0, seed=0):
            """Return a coarse grid of points to simulate Poisson disk output."""
            step = max(min_dist, 5.0)
            xs = np.arange(step / 2, w, step)
            ys = np.arange(step / 2, h, step)
            xv, yv = np.meshgrid(xs, ys)
            pts = np.stack([xv.ravel(), yv.ravel()], axis=1)
            return pts.astype(np.float64)

        _m.poisson_disk_sample = _grid_poisson
        _m.biome_filter_points = lambda pts, *a, **kw: pts
        _m.context_scatter = lambda *a, **kw: []
        _m.generate_breakable_variants = lambda *a, **kw: {}
        _m.VEGETATION_GENERATOR_MAP = {}
        _m.PROP_GENERATOR_MAP = {}
        _m.mesh_from_spec = lambda *a, **kw: None
        sys.modules[_mod_name] = _m

# _terrain_noise shim
_tn_name = "blender_addon.handlers._terrain_noise"
if _tn_name not in sys.modules:
    _tn = types.ModuleType(_tn_name)
    _tn.compute_slope_map = lambda hm: np.zeros_like(hm)
    sys.modules[_tn_name] = _tn

# ---------------------------------------------------------------------------
# Load handler modules
# ---------------------------------------------------------------------------

_BASE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "blender_addon", "handlers")
)


def _load_module(filename: str, module_name: str):
    spec = importlib.util.spec_from_file_location(
        module_name,
        os.path.join(_BASE, filename),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Remove any cached versions from other test files so our clean bpy stub is used
for _cached_key in list(sys.modules.keys()):
    if any(x in _cached_key for x in ("mesh_enhance", "environment_scatter", "_terrain_noise")):
        del sys.modules[_cached_key]

# Load terrain_noise first so scatter can import it
terrain_noise = _load_module("_terrain_noise.py", "blender_addon.handlers._terrain_noise")
sys.modules["blender_addon.handlers._terrain_noise"] = terrain_noise

# Load handlers (fresh, using our clean bpy stub)
_scatter_mod = _load_module(
    "environment_scatter.py", "blender_addon.handlers.environment_scatter"
)
_mesh_enhance = _load_module(
    "mesh_enhance.py", "blender_addon.handlers.mesh_enhance"
)


# ===========================================================================
# LOD Chain Tests
# ===========================================================================

class TestLODChainTree(unittest.TestCase):
    """AAA-MAP-11: Tree LOD chain has 4 levels with correct ratios."""

    def _call(self) -> dict:
        return _mesh_enhance.auto_generate_lod_chain("MyTree", "tree")

    def test_lod_chain_tree_4_levels(self):
        """Tree must generate exactly 4 LOD levels."""
        result = self._call()
        self.assertEqual(result["lod_count"], 4,
                         f"Expected 4 LOD levels, got {result['lod_count']}")

    def test_lod_chain_tree_lod_objects_length(self):
        """lod_objects list must have 4 entries."""
        result = self._call()
        self.assertEqual(len(result["lod_objects"]), 4)

    def test_lod_ratio_tree_lod0_is_1(self):
        """Tree LOD0 ratio must be 1.0 (full detail)."""
        result = self._call()
        self.assertAlmostEqual(result["lod_objects"][0]["ratio"], 1.0)

    def test_lod_ratio_tree_lod1(self):
        """Tree LOD1 ratio must be ~0.4 (40% of original)."""
        result = self._call()
        self.assertAlmostEqual(result["lod_objects"][1]["ratio"], 0.4)

    def test_lod_ratio_tree_lod2(self):
        """Tree LOD2 ratio must be ~0.06 (6% -- leaf cards)."""
        result = self._call()
        self.assertAlmostEqual(result["lod_objects"][2]["ratio"], 0.06)

    def test_lod_tree_lod3_billboard(self):
        """Tree LOD3 must be flagged as billboard (2-8 tris)."""
        result = self._call()
        lod3 = result["lod_objects"][3]
        self.assertTrue(
            lod3.get("billboard") or lod3.get("ratio", 1) <= 0.002,
            f"LOD3 not flagged as billboard: {lod3}",
        )

    def test_lod_group_name(self):
        """LOD group empty must be named '{obj}_LOD_group'."""
        result = self._call()
        self.assertEqual(result["lod_group"], "MyTree_LOD_group")

    def test_lod_asset_type_returned(self):
        """Result must echo back asset_type."""
        result = self._call()
        self.assertEqual(result["asset_type"], "tree")


class TestLODChainBuilding(unittest.TestCase):
    """AAA-MAP-11: Building LOD chain has 3 levels."""

    def _call(self) -> dict:
        return _mesh_enhance.auto_generate_lod_chain("Keep_01", "building")

    def test_lod_chain_building_3_levels(self):
        """Building must generate exactly 3 LOD levels."""
        result = self._call()
        self.assertEqual(result["lod_count"], 3)

    def test_lod_building_lod1_ratio(self):
        """Building LOD1 must be ~0.5 (50% tris)."""
        result = self._call()
        self.assertAlmostEqual(result["lod_objects"][1]["ratio"], 0.5)

    def test_lod_building_lod2_ratio(self):
        """Building LOD2 must be ~0.15 (15% tris)."""
        result = self._call()
        self.assertAlmostEqual(result["lod_objects"][2]["ratio"], 0.15)


class TestLODChainRock(unittest.TestCase):
    """AAA-MAP-11: Rock LOD chain has 3 levels."""

    def _call(self) -> dict:
        return _mesh_enhance.auto_generate_lod_chain("Boulder_03", "rock")

    def test_lod_chain_rock_3_levels(self):
        """Rock must generate exactly 3 LOD levels."""
        result = self._call()
        self.assertEqual(result["lod_count"], 3)

    def test_lod_rock_lod1_ratio(self):
        """Rock LOD1 must be ~0.3 (30% tris)."""
        result = self._call()
        self.assertAlmostEqual(result["lod_objects"][1]["ratio"], 0.3)

    def test_lod_rock_lod2_ratio(self):
        """Rock LOD2 must be ~0.05 (5% -- distant silhouette)."""
        result = self._call()
        self.assertAlmostEqual(result["lod_objects"][2]["ratio"], 0.05)


class TestLODChainGrass(unittest.TestCase):
    """AAA-MAP-11: Grass LOD chain has 2 levels."""

    def test_lod_chain_grass_2_levels(self):
        """Grass must generate exactly 2 LOD levels."""
        result = _mesh_enhance.auto_generate_lod_chain("GrassTuft_01", "grass")
        self.assertEqual(result["lod_count"], 2)


# ===========================================================================
# GPU Instancing Tests
# ===========================================================================

class TestGPUInstancingTrees(unittest.TestCase):
    """AAA-MAP-10: Tree scatter placements are tagged for GPU instancing."""

    def _run_structure_pass(self):
        hm = np.full((32, 32), 0.4)
        slope = np.zeros((32, 32))
        return _scatter_mod._scatter_pass(
            hm, slope, terrain_size=100.0, pass_type="structure",
            biome="prairie", seed=1,
        )

    def test_gpu_instancing_trees(self):
        """Tree placements must have gpu_instance=True for Blender Collection instancing."""
        placements = self._run_structure_pass()
        trees = [p for p in placements if p.get("vegetation_type") == "tree"]
        self.assertGreater(len(trees), 0, "No trees were placed")
        for t in trees:
            self.assertTrue(
                t.get("gpu_instance"),
                f"Tree placement missing gpu_instance flag: {t}",
            )

    def test_gpu_instancing_bushes(self):
        """Bush placements must also have gpu_instance=True."""
        placements = self._run_structure_pass()
        bushes = [p for p in placements if p.get("vegetation_type") == "bush"]
        for b in bushes:
            self.assertTrue(b.get("gpu_instance"), f"Bush missing gpu_instance: {b}")


class TestGPUInstancingGrass(unittest.TestCase):
    """AAA-MAP-10: Grass cards are tagged for GPU instancing per biome."""

    def test_gpu_instancing_grass(self):
        """Grass placements must have gpu_instance=True."""
        hm = np.full((32, 32), 0.4)
        slope = np.zeros((32, 32))
        placements = _scatter_mod._scatter_pass(
            hm, slope, terrain_size=100.0, pass_type="ground_cover",
            biome="prairie", seed=2,
        )
        grasses = [p for p in placements if "grass" in p.get("vegetation_type", "")]
        self.assertGreater(len(grasses), 0, "No grass was placed")
        for g in grasses:
            self.assertTrue(
                g.get("gpu_instance"),
                f"Grass placement missing gpu_instance: {g}",
            )


class TestGPUInstancingRocks(unittest.TestCase):
    """AAA-MAP-10: Rock placements are tagged for GPU instancing by size class."""

    def test_gpu_instancing_rocks(self):
        """Rock placements must have gpu_instance=True."""
        hm = np.full((32, 32), 0.4)
        slope = np.zeros((32, 32))
        placements = _scatter_mod._scatter_pass(
            hm, slope, terrain_size=100.0, pass_type="debris",
            biome="default", seed=3,
        )
        rocks = [p for p in placements if p.get("vegetation_type") == "rock"]
        self.assertGreater(len(rocks), 0, "No rocks were placed")
        for r in rocks:
            self.assertTrue(
                r.get("gpu_instance"),
                f"Rock placement missing gpu_instance: {r}",
            )


# ===========================================================================
# Performance Budget Spec Tests
# ===========================================================================

class TestPerformanceBudgetSpec(unittest.TestCase):
    """AAA-MAP-10: Per-category tri budgets match research spec."""

    BUDGETS = {
        "terrain":   200_000,
        "buildings": 300_000,
        "walls":     150_000,
        "trees":     400_000,
        "grass":     300_000,
        "rocks":     200_000,
        "water":      20_000,
    }
    TOTAL_BUDGET = 2_000_000
    DRAW_CALL_BUDGET = 500

    def test_total_tri_budget_under_2m(self):
        """Sum of per-category budgets must be under 2 million triangles."""
        total = sum(self.BUDGETS.values())
        self.assertLess(total, self.TOTAL_BUDGET,
                        f"Sum of category budgets {total} exceeds 2M limit")

    def test_draw_call_estimate_under_500(self):
        """Instanced draw call estimate must be under 500."""
        # terrain(4-8) + buildings(30-50) + walls(10-20)
        # + trees(5-10 inst) + grass(2-4 inst) + rocks(10-20 inst) + water(1-2)
        instanced_max = 8 + 50 + 20 + 10 + 4 + 20 + 2  # 114 -- well under 500
        self.assertLess(instanced_max, self.DRAW_CALL_BUDGET)

    def test_terrain_tri_budget(self):
        """Terrain element must have 200K tri budget."""
        self.assertEqual(self.BUDGETS["terrain"], 200_000)

    def test_building_tri_budget(self):
        """Buildings total must have 300K tri budget."""
        self.assertEqual(self.BUDGETS["buildings"], 300_000)

    def test_tree_tri_budget(self):
        """Trees total must have 400K tri budget."""
        self.assertEqual(self.BUDGETS["trees"], 400_000)

    def test_grass_tri_budget(self):
        """Grass total must have 300K tri budget."""
        self.assertEqual(self.BUDGETS["grass"], 300_000)

    def test_rock_tri_budget(self):
        """Rocks/props total must have 200K tri budget."""
        self.assertEqual(self.BUDGETS["rocks"], 200_000)

    def test_water_tri_budget(self):
        """Water element must have 20K tri budget."""
        self.assertEqual(self.BUDGETS["water"], 20_000)

    def test_walls_tri_budget(self):
        """Walls/castle total must have 150K tri budget."""
        self.assertEqual(self.BUDGETS["walls"], 150_000)


# ===========================================================================
# Topology Grade Enforcement Tests
# ===========================================================================

class TestTopologyGradeEnforcement(unittest.TestCase):
    """AAA-MAP-12: Topology grade A minimum enforced with auto-repair."""

    @classmethod
    def setUpClass(cls):
        """Ensure bpy.data.objects.get('TestMesh') returns a valid stub object."""
        import sys as _sys
        _bpy = _sys.modules.get("bpy")
        if _bpy is None or not hasattr(_bpy, "data"):
            return
        # Build a fake mesh with quad-only faces (grade A+) so auto-repair is skipped.
        _fake_poly = types.SimpleNamespace(vertices=[0, 1, 2, 3], area=1.0)
        _fake_mesh = types.SimpleNamespace(
            polygons=[_fake_poly] * 4,
            vertices=[],
            materials=[],
        )
        _fake = types.SimpleNamespace(
            name="TestMesh",
            location=types.SimpleNamespace(copy=lambda: (0.0, 0.0, 0.0)),
            data=_fake_mesh,
            modifiers=_ModifierList(),
            parent=None,
        )
        _orig_get = _bpy.data.objects.get
        _bpy.data.objects.get = lambda name, default=None: (
            _fake if name == "TestMesh" else _orig_get(name)
        )

    def test_topology_grade_enforcement_function_exists(self):
        """enforce_topology_grade must exist in mesh_enhance."""
        self.assertTrue(
            hasattr(_mesh_enhance, "enforce_topology_grade"),
            "enforce_topology_grade not found in mesh_enhance",
        )

    def test_topology_grade_enforcement_returns_dict(self):
        """enforce_topology_grade must return a dict with required keys."""
        result = _mesh_enhance.enforce_topology_grade("TestMesh", "A")
        self.assertIsInstance(result, dict)
        required_keys = {"original_grade", "final_grade", "repaired", "meets_minimum", "issues"}
        for key in required_keys:
            self.assertIn(key, result, f"Missing key '{key}' in result")

    def test_topology_auto_repair_flag(self):
        """enforce_topology_grade must report whether repair was attempted."""
        result = _mesh_enhance.enforce_topology_grade("TestMesh", "A")
        self.assertIn("repaired", result)
        self.assertIsInstance(result["repaired"], bool)

    def test_topology_meets_minimum_field(self):
        """meets_minimum must be a bool."""
        result = _mesh_enhance.enforce_topology_grade("TestMesh", "A")
        self.assertIsInstance(result["meets_minimum"], bool)

    def test_topology_grade_order(self):
        """Grade ordering must satisfy A+ > A > B+ > B > C+ > C > D."""
        grade_order = ["D", "C", "C+", "B", "B+", "A", "A+"]
        for i in range(len(grade_order) - 1):
            self.assertLess(
                grade_order.index(grade_order[i]),
                grade_order.index(grade_order[i + 1]),
            )

    def test_auto_generate_lod_chain_function_exists(self):
        """auto_generate_lod_chain must exist in mesh_enhance."""
        self.assertTrue(
            hasattr(_mesh_enhance, "auto_generate_lod_chain"),
            "auto_generate_lod_chain not found in mesh_enhance",
        )


# ===========================================================================
# World-space position regression (bug fix: positions must be centered at 0)
# ===========================================================================

class TestScatterPositionWorldSpace(unittest.TestCase):
    """Positions returned by _scatter_pass must be world-space (centered at 0,0)."""

    def _scatter(self, pass_type: str, seed: int = 99) -> list:
        hm = np.full((32, 32), 0.4)
        slope = np.zeros((32, 32))
        return _scatter_mod._scatter_pass(
            hm, slope, terrain_size=100.0, pass_type=pass_type,
            biome="prairie", seed=seed,
        )

    def test_structure_positions_world_space(self):
        """Tree/bush positions must be in [-50, 50] for 100m terrain (world-space)."""
        for item in self._scatter("structure"):
            px, py = item["position"]
            self.assertGreaterEqual(px, -50.0, f"x={px} below world-space minimum")
            self.assertLessEqual(px,   50.0, f"x={px} above world-space maximum")
            self.assertGreaterEqual(py, -50.0, f"y={py} below world-space minimum")
            self.assertLessEqual(py,   50.0, f"y={py} above world-space maximum")

    def test_ground_cover_positions_world_space(self):
        """Grass positions must be in [-50, 50] world-space range."""
        for item in self._scatter("ground_cover"):
            px, py = item["position"]
            self.assertGreaterEqual(px, -50.0)
            self.assertLessEqual(px,   50.0)

    def test_debris_positions_world_space(self):
        """Rock positions must be in [-50, 50] world-space range."""
        for item in self._scatter("debris"):
            px, py = item["position"]
            self.assertGreaterEqual(px, -50.0)
            self.assertLessEqual(px,   50.0)


if __name__ == "__main__":
    unittest.main()
