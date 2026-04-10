"""Geometry quality tests for all 10 riggable prop generators (Phase 44, Plan 01).

Covers vertex count ranges, face count minimums, detail geometry presence,
chain tri optimization, and flag cloth-sim vertex density.

All generators are pure-logic (no bpy) so they run without Blender.
"""
from __future__ import annotations

import unittest

from blender_addon.handlers.riggable_objects import (
    generate_chest,
    generate_door,
    generate_chain,
    generate_flag,
    generate_chandelier,
    generate_drawbridge,
    generate_rope_bridge,
    generate_hanging_sign,
    generate_windmill,
    generate_cage,
)


# =========================================================================
# Chest
# =========================================================================

class TestChest(unittest.TestCase):
    """Chest generator must produce 500-800 verts with iron banding detail."""

    def setUp(self):
        self.result = generate_chest(style="wooden")

    def test_returns_valid_mesh(self):
        self.assertIn("vertices", self.result)
        self.assertIn("faces", self.result)
        self.assertGreater(len(self.result["vertices"]), 0)
        self.assertGreater(len(self.result["faces"]), 0)

    def test_vertex_count_in_range(self):
        v = len(self.result["vertices"])
        self.assertGreaterEqual(v, 500, f"Chest verts {v} below 500 target")
        self.assertLessEqual(v, 800, f"Chest verts {v} above 800 ceiling")

    def test_has_detail_geometry(self):
        """Face count must be well above a single box (6 faces) indicating detail."""
        f = len(self.result["faces"])
        self.assertGreater(f, 50, f"Chest faces {f} too few -- missing detail geometry")

    def test_iron_bound_has_straps(self):
        """Iron-bound chest variant must have significantly more geometry."""
        iron = generate_chest(style="iron_bound")
        wooden = self.result
        # Iron bound should have MORE verts due to strap geometry
        self.assertGreater(
            len(iron["vertices"]),
            len(wooden["vertices"]),
            "Iron-bound chest should have more verts than wooden (strap geometry)",
        )


# =========================================================================
# Door
# =========================================================================

class TestDoor(unittest.TestCase):
    """Door generator must produce 300-600 verts with handle/hinge detail."""

    def setUp(self):
        self.result = generate_door(style="wooden_plank")

    def test_returns_valid_mesh(self):
        self.assertIn("vertices", self.result)
        self.assertIn("faces", self.result)
        self.assertGreater(len(self.result["vertices"]), 0)

    def test_vertex_count_in_range(self):
        v = len(self.result["vertices"])
        self.assertGreaterEqual(v, 300, f"Door verts {v} below 300 target")
        self.assertLessEqual(v, 600, f"Door verts {v} above 600 ceiling")

    def test_has_handle_and_hinges(self):
        """Face count should be significantly above a flat slab."""
        f = len(self.result["faces"])
        self.assertGreater(f, 80, f"Door faces {f} too few -- missing handle/hinge detail")


# =========================================================================
# Chain
# =========================================================================

class TestChain(unittest.TestCase):
    """Chain generator must produce <=80 tris per link (was 288)."""

    def setUp(self):
        self.link_count = 8
        self.result = generate_chain(link_count=self.link_count, style="iron")

    def test_returns_valid_mesh(self):
        self.assertIn("vertices", self.result)
        self.assertIn("faces", self.result)
        self.assertGreater(len(self.result["vertices"]), 0)

    def test_tris_per_link_optimized(self):
        total_tris = sum(len(face) - 2 for face in self.result["faces"])
        tris_per_link = total_tris / self.link_count
        self.assertLessEqual(
            tris_per_link, 80,
            f"Chain tris/link {tris_per_link:.0f} exceeds 80 target (was 288)",
        )

    def test_total_verts_reasonable(self):
        """Total verts should be less than current 576 for 8 links."""
        v = len(self.result["vertices"])
        self.assertLess(v, 576, f"Chain verts {v} not reduced from baseline 576")


# =========================================================================
# Flag
# =========================================================================

class TestFlag(unittest.TestCase):
    """Flag generator must produce 800+ verts for cloth simulation."""

    def setUp(self):
        self.result = generate_flag(style="banner")

    def test_returns_valid_mesh(self):
        self.assertIn("vertices", self.result)
        self.assertIn("faces", self.result)
        self.assertGreater(len(self.result["vertices"]), 0)

    def test_cloth_sim_density(self):
        v = len(self.result["vertices"])
        self.assertGreaterEqual(v, 800, f"Flag verts {v} below 800 cloth-sim target")

    def test_quad_grid_topology(self):
        """Most faces should be quads (4-sided) for cloth sim."""
        quads = sum(1 for f in self.result["faces"] if len(f) == 4)
        total = len(self.result["faces"])
        ratio = quads / total if total > 0 else 0
        self.assertGreater(ratio, 0.5, f"Quad ratio {ratio:.2f} too low for cloth sim")


# =========================================================================
# Hanging Sign
# =========================================================================

class TestHangingSign(unittest.TestCase):
    """Hanging sign must produce 300-500 verts with bracket detail."""

    def setUp(self):
        self.result = generate_hanging_sign()

    def test_returns_valid_mesh(self):
        self.assertIn("vertices", self.result)
        self.assertIn("faces", self.result)
        self.assertGreater(len(self.result["vertices"]), 0)

    def test_vertex_count_in_range(self):
        v = len(self.result["vertices"])
        self.assertGreaterEqual(v, 300, f"Sign verts {v} below 300 target")
        self.assertLessEqual(v, 500, f"Sign verts {v} above 500 ceiling")


# =========================================================================
# Cage
# =========================================================================

class TestCage(unittest.TestCase):
    """Cage must produce 800-1500 verts."""

    def setUp(self):
        self.result = generate_cage(style="hanging_cage")

    def test_returns_valid_mesh(self):
        self.assertIn("vertices", self.result)
        self.assertIn("faces", self.result)
        self.assertGreater(len(self.result["vertices"]), 0)

    def test_vertex_count_in_range(self):
        v = len(self.result["vertices"])
        self.assertGreaterEqual(v, 800, f"Cage verts {v} below 800")
        self.assertLessEqual(v, 1500, f"Cage verts {v} above 1500 ceiling")


# =========================================================================
# Chandelier
# =========================================================================

class TestChandelier(unittest.TestCase):
    """Chandelier must produce 2000-3500 verts."""

    def setUp(self):
        self.result = generate_chandelier()

    def test_returns_valid_mesh(self):
        self.assertIn("vertices", self.result)
        self.assertIn("faces", self.result)
        self.assertGreater(len(self.result["vertices"]), 0)

    def test_vertex_count_in_range(self):
        v = len(self.result["vertices"])
        self.assertGreaterEqual(v, 2000, f"Chandelier verts {v} below 2000")
        self.assertLessEqual(v, 3500, f"Chandelier verts {v} above 3500")


# =========================================================================
# Drawbridge
# =========================================================================

class TestDrawbridge(unittest.TestCase):
    """Drawbridge must produce 500-1000 verts with hinge detail."""

    def setUp(self):
        self.result = generate_drawbridge()

    def test_returns_valid_mesh(self):
        self.assertIn("vertices", self.result)
        self.assertIn("faces", self.result)
        self.assertGreater(len(self.result["vertices"]), 0)

    def test_vertex_count_in_range(self):
        v = len(self.result["vertices"])
        self.assertGreaterEqual(v, 500, f"Drawbridge verts {v} below 500 target")
        self.assertLessEqual(v, 1000, f"Drawbridge verts {v} above 1000 ceiling")


# =========================================================================
# Rope Bridge
# =========================================================================

class TestRopeBridge(unittest.TestCase):
    """Rope bridge must produce 1500-2500 verts."""

    def setUp(self):
        self.result = generate_rope_bridge()

    def test_returns_valid_mesh(self):
        self.assertIn("vertices", self.result)
        self.assertIn("faces", self.result)
        self.assertGreater(len(self.result["vertices"]), 0)

    def test_vertex_count_in_range(self):
        v = len(self.result["vertices"])
        self.assertGreaterEqual(v, 1500, f"Rope bridge verts {v} below 1500")
        self.assertLessEqual(v, 2500, f"Rope bridge verts {v} above 2500")


# =========================================================================
# Windmill
# =========================================================================

class TestWindmill(unittest.TestCase):
    """Windmill must produce 1500-3000 verts with blade detail."""

    def setUp(self):
        self.result = generate_windmill()

    def test_returns_valid_mesh(self):
        self.assertIn("vertices", self.result)
        self.assertIn("faces", self.result)
        self.assertGreater(len(self.result["vertices"]), 0)

    def test_vertex_count_in_range(self):
        v = len(self.result["vertices"])
        self.assertGreaterEqual(v, 1500, f"Windmill verts {v} below 1500 target")
        self.assertLessEqual(v, 3000, f"Windmill verts {v} above 3000 ceiling")


# =========================================================================
# All Props Valid Mesh
# =========================================================================

class TestAllPropsReturnValidMesh(unittest.TestCase):
    """Every generator returns dict with 'vertices' and 'faces' keys, len > 0."""

    GENERATORS = [
        ("chest", generate_chest, {}),
        ("door", generate_door, {}),
        ("chain", generate_chain, {}),
        ("flag", generate_flag, {}),
        ("chandelier", generate_chandelier, {}),
        ("drawbridge", generate_drawbridge, {}),
        ("rope_bridge", generate_rope_bridge, {}),
        ("hanging_sign", generate_hanging_sign, {}),
        ("windmill", generate_windmill, {}),
        ("cage", generate_cage, {}),
    ]

    def test_all_return_vertices_and_faces(self):
        for name, gen, kwargs in self.GENERATORS:
            with self.subTest(generator=name):
                result = gen(**kwargs)
                self.assertIn("vertices", result, f"{name} missing 'vertices'")
                self.assertIn("faces", result, f"{name} missing 'faces'")
                self.assertGreater(len(result["vertices"]), 0, f"{name} has 0 vertices")
                self.assertGreater(len(result["faces"]), 0, f"{name} has 0 faces")


if __name__ == "__main__":
    unittest.main()
