"""Tests for phase 58-03 fixes: dungeon Z-up, settlement height_fn, mesh_bridge logging."""
from __future__ import annotations

import math
import unittest

from blender_addon.handlers._dungeon_gen import (
    generate_bsp_dungeon,
    generate_dungeon_prop_placements,
)
from blender_addon.handlers._settlement_grammar import (
    _z_at,
    generate_prop_manifest,
    generate_road_network_organic,
)


class TestDungeonPropWorldSpace(unittest.TestCase):
    """Verify dungeon props use Blender world-space (Z-up) coordinates."""

    def setUp(self):
        self.layout = generate_bsp_dungeon(width=32, height=32, seed=42)

    def test_default_cell_size_positions_scaled(self):
        """With default cell_size=2.0, all XY coords are even integers."""
        props = generate_dungeon_prop_placements(self.layout, seed=1)
        self.assertGreater(len(props), 0, "Should generate at least one prop")
        for p in props:
            x, y, z = p["position"]
            # Positions should be multiples of cell_size (2.0)
            self.assertAlmostEqual(x % 2.0, 0.0, places=6,
                                   msg=f"X={x} not multiple of cell_size=2.0")
            self.assertAlmostEqual(y % 2.0, 0.0, places=6,
                                   msg=f"Y={y} not multiple of cell_size=2.0")

    def test_custom_cell_size(self):
        """cell_size=3.0 scales grid coords by 3."""
        props = generate_dungeon_prop_placements(self.layout, seed=1, cell_size=3.0)
        for p in props:
            x, y, _z = p["position"]
            self.assertAlmostEqual(x % 3.0, 0.0, places=6)
            self.assertAlmostEqual(y % 3.0, 0.0, places=6)

    def test_floor_z_offset(self):
        """floor_z raises all prop Z coordinates."""
        props_z0 = generate_dungeon_prop_placements(self.layout, seed=1, floor_z=0.0)
        props_z5 = generate_dungeon_prop_placements(self.layout, seed=1, floor_z=5.0)
        self.assertEqual(len(props_z0), len(props_z5))
        for p0, p5 in zip(props_z0, props_z5):
            z_diff = p5["position"][2] - p0["position"][2]
            self.assertAlmostEqual(z_diff, 5.0, places=4,
                                   msg="floor_z=5 should shift Z by +5")

    def test_torch_sconce_wall_mount_height(self):
        """Torch sconces have Z offset for wall mounting (1.8m above floor)."""
        props = generate_dungeon_prop_placements(self.layout, seed=1, floor_z=0.0)
        torches = [p for p in props if p["type"] == "torch_sconce"]
        self.assertGreater(len(torches), 0, "Should have torch_sconce props")
        for t in torches:
            self.assertAlmostEqual(t["position"][2], 1.8, places=4,
                                   msg="Torch sconce should be at 1.8m above floor")

    def test_backward_compat_no_args(self):
        """Calling without cell_size/floor_z still works (defaults)."""
        props = generate_dungeon_prop_placements(self.layout, seed=1)
        self.assertGreater(len(props), 0)

    def test_position_is_float_tuple(self):
        """All positions must be (float, float, float) tuples."""
        props = generate_dungeon_prop_placements(self.layout, seed=1, cell_size=2.5)
        for p in props:
            pos = p["position"]
            self.assertEqual(len(pos), 3)
            for v in pos:
                self.assertIsInstance(v, float)


class TestSettlementHeightFn(unittest.TestCase):
    """Verify settlement grammar respects height_fn for terrain-aware Z."""

    def test_z_at_with_none(self):
        self.assertEqual(_z_at(10.0, 20.0, None), 0.0)

    def test_z_at_with_callback(self):
        fn = lambda x, y: x + y
        self.assertAlmostEqual(_z_at(3.0, 4.0, fn), 7.0)

    def test_road_network_flat_by_default(self):
        """Without height_fn, all waypoint Z values are 0.0."""
        segs = generate_road_network_organic(center=(0, 0), radius=50, seed=1)
        for seg in segs:
            for pt in seg["points"]:
                self.assertAlmostEqual(pt[2], 0.0, places=6,
                                       msg=f"Default Z should be 0.0, got {pt[2]}")

    def test_road_network_uses_height_fn(self):
        """With height_fn, waypoint Z values reflect terrain."""
        fn = lambda x, y: 10.0  # flat plateau at Z=10
        segs = generate_road_network_organic(
            center=(0, 0), radius=50, seed=1, height_fn=fn
        )
        for seg in segs:
            # Start and end points should have Z=10
            self.assertAlmostEqual(seg["start"][2], 10.0, places=4)
            self.assertAlmostEqual(seg["end"][2], 10.0, places=4)

    def test_road_network_variable_height(self):
        """Height varies with position."""
        fn = lambda x, y: x * 0.1  # slope in X direction
        segs = generate_road_network_organic(
            center=(50, 50), radius=30, seed=1, height_fn=fn
        )
        z_values = set()
        for seg in segs:
            z_values.add(round(seg["start"][2], 2))
            z_values.add(round(seg["end"][2], 2))
        # Different X positions should give different Z values
        self.assertGreater(len(z_values), 1,
                           "Variable height_fn should produce varied Z values")

    def test_prop_manifest_flat_by_default(self):
        """Without height_fn, prop Z values are 0.0."""
        segs = generate_road_network_organic(center=(0, 0), radius=50, seed=1)
        props = generate_prop_manifest(segs, veil_pressure=0.3, seed=1)
        for p in props:
            self.assertAlmostEqual(p["position"][2], 0.0, places=6)

    def test_prop_manifest_uses_height_fn(self):
        """With height_fn, prop Z follows terrain."""
        fn = lambda x, y: 5.0
        segs = generate_road_network_organic(
            center=(0, 0), radius=50, seed=1, height_fn=fn
        )
        props = generate_prop_manifest(
            segs, veil_pressure=0.3, seed=1, height_fn=fn
        )
        if props:
            for p in props:
                self.assertAlmostEqual(p["position"][2], 5.0, places=4)


class TestMeshBridgeSilentSwallow(unittest.TestCase):
    """Verify _mesh_bridge logs instead of silently swallowing degenerate faces."""

    def test_degenerate_face_handler_exists(self):
        """The except clause should reference logging, not bare pass."""
        import inspect
        from blender_addon.handlers._mesh_bridge import mesh_from_spec
        source = inspect.getsource(mesh_from_spec)
        self.assertNotIn("pass  # skip duplicate", source,
                         "Silent pass on degenerate faces should be replaced with logging")
        self.assertIn("logging", source,
                      "Degenerate face handler should use logging")


if __name__ == "__main__":
    unittest.main()
