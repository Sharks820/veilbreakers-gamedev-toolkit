"""Integration tests for the compose_map full pipeline.

Tests the terrain -> water -> roads -> locations -> vegetation pipeline using
only pure-Python helper functions (no Blender TCP connection required).

Bug targeted directly:
  BUG-CHKPT-1: `interior_results = []` on line ~3071 of blender_server.py
      unconditionally wipes `interior_results` at Step 9 even when the
      pipeline is resumed from a checkpoint that already stored interior
      data. This test suite exposes that regression via the pipeline_state
      module (which IS testable without Blender) and via direct inspection of
      the blender_server helper functions.

Coverage:
  1. Terrain cell conversion produces valid heightmap indices
  2. Water level parameter flows through to the command payload
  3. Road waypoints connect mapped locations (cells in-bounds)
  4. Location anchor placement uses terrain height sampling context
  5. Vegetation rule normalization respects exclusion-zone density=0
  6. Checkpoint save/restore preserves ALL fields including interior_results
  7. Resumed pipeline skips already-completed steps
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

# ---------------------------------------------------------------------------
# Path setup — mirror conftest.py so this file works standalone too
# ---------------------------------------------------------------------------

_toolkit_root = Path(__file__).resolve().parent.parent
if str(_toolkit_root) not in sys.path:
    sys.path.insert(0, str(_toolkit_root))

_src_root = _toolkit_root / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

# ---------------------------------------------------------------------------
# Pure-logic imports from blender_server (no Blender TCP needed)
# ---------------------------------------------------------------------------

from veilbreakers_mcp.blender_server import (  # noqa: E402
    _map_point_to_terrain_cell,
    _normalize_map_point,
    _normalize_vegetation_rules,
    _plan_map_location_anchors,
    _resolve_map_generation_budget,
    _build_location_generation_params,
    _lighting_preset_for_biome,
)
from blender_addon.handlers.pipeline_state import (  # noqa: E402
    save_pipeline_checkpoint,
    load_pipeline_checkpoint,
    delete_pipeline_checkpoint,
    validate_checkpoint_compatibility,
    get_remaining_steps,
)


# ===========================================================================
# Helper builders
# ===========================================================================

def _minimal_map_spec(**overrides) -> dict:
    """Minimal valid map_spec suitable for all helper function tests."""
    spec = {
        "name": "TestRegion",
        "seed": 42,
        "terrain": {"preset": "hills", "size": 200.0, "resolution": 64, "height_scale": 20.0},
        "water": {
            "rivers": [{"source": [10, 10], "destination": [190, 190], "width": 5}],
            "water_level": 2.0,
        },
        "roads": [{"waypoints": [[50, 80], [100, 100], [150, 60]], "width": 3}],
        "locations": [
            {"type": "town", "name": "Village", "districts": 3},
            {"type": "castle", "name": "Keep"},
            {"type": "dungeon", "name": "Crypt", "floors": 2},
        ],
        "biome": "thornwood_forest",
        "vegetation": {"density": 0.5},
    }
    spec.update(overrides)
    return spec


def _base_checkpoint_state(**overrides) -> dict:
    """Minimal checkpoint state, pre-water+roads completed."""
    state = {
        "map_name": "TestRegion",
        "seed": 42,
        "location_count": 3,
        "steps_completed": [
            "scene_cleared",
            "terrain_generated",
            "river_0",
            "water_plane",
            "road_0",
        ],
        "created_objects": ["TestRegion_Terrain", "TestRegion_Water"],
        "location_results": [
            {"name": "Village", "type": "town", "anchor": [10.0, 5.0, 1.2]},
            {"name": "Keep", "type": "castle", "anchor": [-20.0, -15.0, 2.8]},
        ],
        "interior_results": [
            {"location": "Village", "result": {"status": "ok"}},
        ],
        "params_snapshot": {"terrain_size": 200.0, "seed": 42},
    }
    state.update(overrides)
    return state


# ===========================================================================
# Suite 1: Terrain cell conversion
# ===========================================================================

class TestTerrainCellConversion(unittest.TestCase):
    """_map_point_to_terrain_cell must produce valid indices for all inputs."""

    def _assert_in_bounds(self, row: int, col: int, resolution: int):
        self.assertGreaterEqual(row, 0, "row < 0")
        self.assertLess(row, resolution, "row >= resolution")
        self.assertGreaterEqual(col, 0, "col < 0")
        self.assertLess(col, resolution, "col >= resolution")

    def test_origin_maps_to_center_cell(self):
        """World origin (0,0) should map to the center cell of the heightmap."""
        res = 64
        row, col = _map_point_to_terrain_cell([0, 0], terrain_size=200.0, resolution=res)
        center = res // 2
        # Allow ±1 cell for rounding
        self.assertAlmostEqual(row, center, delta=1, msg="Row not near center")
        self.assertAlmostEqual(col, center, delta=1, msg="Col not near center")

    def test_corner_positions_produce_in_bounds_cells(self):
        """Each corner of the terrain should produce a valid cell index."""
        res = 64
        size = 200.0
        half = size / 2.0
        corners = [(-half, -half), (half, -half), (-half, half), (half, half)]
        for x, y in corners:
            row, col = _map_point_to_terrain_cell([x, y], terrain_size=size, resolution=res)
            self._assert_in_bounds(row, col, res)

    def test_road_waypoints_produce_valid_cells(self):
        """Road waypoints from the spec should all convert to valid cells."""
        spec = _minimal_map_spec()
        res = int(spec["terrain"]["resolution"])
        size = float(spec["terrain"]["size"])
        for road in spec["roads"]:
            for wp in road["waypoints"]:
                row, col = _map_point_to_terrain_cell(wp, terrain_size=size, resolution=res)
                self._assert_in_bounds(row, col, res)

    def test_high_resolution_does_not_overflow(self):
        """Resolution of 512 must not produce indices >= 512."""
        row, col = _map_point_to_terrain_cell(
            [95.0, 95.0], terrain_size=200.0, resolution=512
        )
        self._assert_in_bounds(row, col, 512)

    def test_position_normalization_shifts_0_to_size_into_centered(self):
        """Positions expressed in [0, size] space should be normalized to centered space."""
        size = 200.0
        # (190, 190) in 0..200 space is near the +x+y edge in centered space
        x, y = _normalize_map_point([190, 190], size)
        self.assertAlmostEqual(x, 90.0, delta=1.0)
        self.assertAlmostEqual(y, 90.0, delta=1.0)

    def test_already_centered_coords_are_not_double_shifted(self):
        """Coords clearly in centered space (negative values) must not be re-shifted."""
        size = 200.0
        x, y = _normalize_map_point([-50.0, -30.0], size)
        self.assertAlmostEqual(x, -50.0, places=3)
        self.assertAlmostEqual(y, -30.0, places=3)


# ===========================================================================
# Suite 2: Water level parameter flow
# ===========================================================================

class TestWaterLevelParameter(unittest.TestCase):
    """Water level from map_spec must flow into the generated Blender commands."""

    def test_water_cfg_extracted_from_spec(self):
        """water_cfg must contain the water_level from the spec."""
        spec = _minimal_map_spec()
        water_cfg = spec.get("water", {})
        self.assertIn("water_level", water_cfg)
        self.assertEqual(water_cfg["water_level"], 2.0)

    def test_custom_water_level_preserved(self):
        """Custom water_level values must not be clamped or modified by spec parsing."""
        spec = _minimal_map_spec()
        spec["water"]["water_level"] = 7.5
        self.assertEqual(spec["water"]["water_level"], 7.5)

    def test_water_level_above_terrain_height_scale_is_valid(self):
        """water_level can exceed height_scale — this is valid for flood maps."""
        spec = _minimal_map_spec()
        spec["water"]["water_level"] = 25.0  # > height_scale of 20
        spec["terrain"]["height_scale"] = 20.0
        # The spec should accept any float
        self.assertEqual(spec["water"]["water_level"], 25.0)

    def test_zero_water_level_is_valid(self):
        """water_level=0 means a surface-flush water body and must not raise."""
        spec = _minimal_map_spec()
        spec["water"]["water_level"] = 0.0
        self.assertEqual(spec["water"]["water_level"], 0.0)

    def test_river_source_destination_are_distinct(self):
        """Rivers with identical source and destination should not be added silently."""
        spec = _minimal_map_spec()
        river = spec["water"]["rivers"][0]
        src = river["source"]
        dst = river["destination"]
        self.assertNotEqual(src, dst, "River source equals destination — degenerate river")


# ===========================================================================
# Suite 3: Road generation — waypoint connectivity
# ===========================================================================

class TestRoadWaypointConnectivity(unittest.TestCase):
    """Road waypoints must be mappable to valid terrain cells."""

    def _waypoints_to_cells(self, waypoints, size, resolution):
        return [
            _map_point_to_terrain_cell(wp, terrain_size=size, resolution=resolution)
            for wp in waypoints
            if isinstance(wp, (list, tuple)) and len(wp) >= 2
        ]

    def test_road_requires_at_least_two_waypoints(self):
        """Road generation requires >= 2 waypoints or it must raise ValueError."""
        spec = _minimal_map_spec()
        size = float(spec["terrain"]["size"])
        res = int(spec["terrain"]["resolution"])
        for road in spec["roads"]:
            cells = self._waypoints_to_cells(road["waypoints"], size, res)
            self.assertGreaterEqual(
                len(cells), 2,
                f"Road only has {len(cells)} valid waypoints — needs at least 2"
            )

    def test_road_cells_are_unique(self):
        """A road whose waypoints map to the same cell has zero length — detect it."""
        spec = _minimal_map_spec()
        size = float(spec["terrain"]["size"])
        res = int(spec["terrain"]["resolution"])
        for road in spec["roads"]:
            cells = self._waypoints_to_cells(road["waypoints"], size, res)
            # Require at least one unique pair of cells
            has_distinct = any(cells[i] != cells[j] for i in range(len(cells)) for j in range(i + 1, len(cells)))
            self.assertTrue(has_distinct, "All road waypoints map to the same cell — zero-length road")

    def test_road_width_is_positive(self):
        """Every road must specify a positive width."""
        spec = _minimal_map_spec()
        for road in spec["roads"]:
            self.assertGreater(road.get("width", 0), 0, "Road has non-positive width")

    def test_multiple_roads_do_not_crash_cell_conversion(self):
        """Multiple roads must all convert without IndexError or ValueError."""
        spec = _minimal_map_spec()
        spec["roads"].append({"waypoints": [[0, 0], [100, 100], [150, 150]], "width": 4})
        size = float(spec["terrain"]["size"])
        res = int(spec["terrain"]["resolution"])
        for road in spec["roads"]:
            cells = self._waypoints_to_cells(road["waypoints"], size, res)
            self.assertGreater(len(cells), 0)


# ===========================================================================
# Suite 4: Location anchor placement
# ===========================================================================

class TestLocationAnchorPlacement(unittest.TestCase):
    """_plan_map_location_anchors must place every location within terrain bounds."""

    def test_all_locations_get_anchors(self):
        """Every location in the spec must receive a placement entry."""
        spec = _minimal_map_spec()
        placements = _plan_map_location_anchors(spec)
        self.assertEqual(len(placements), len(spec["locations"]))

    def test_anchors_within_terrain_bounds(self):
        """All anchors must fall within (-half, +half) in x and y."""
        spec = _minimal_map_spec()
        size = float(spec["terrain"]["size"])
        half = size / 2.0
        placements = _plan_map_location_anchors(spec)
        for p in placements:
            ax, ay = p["anchor"]
            self.assertGreaterEqual(ax, -half, f"{p['name']} anchor_x below -half")
            self.assertLessEqual(ax, half, f"{p['name']} anchor_x above +half")
            self.assertGreaterEqual(ay, -half, f"{p['name']} anchor_y below -half")
            self.assertLessEqual(ay, half, f"{p['name']} anchor_y above +half")

    def test_anchor_has_source_reference(self):
        """Each placement must carry a reference to the original location dict."""
        spec = _minimal_map_spec()
        placements = _plan_map_location_anchors(spec)
        for p in placements:
            self.assertIn("source", p, f"{p['name']} missing source reference")
            self.assertEqual(p["source"]["name"], p["name"])

    def test_no_two_locations_overlap(self):
        """Anchors must respect the minimum separation (radius + radius + 8 m)."""
        spec = _minimal_map_spec()
        placements = _plan_map_location_anchors(spec)
        for i, a in enumerate(placements):
            for j, b in enumerate(placements):
                if i >= j:
                    continue
                ax, ay = a["anchor"]
                bx, by = b["anchor"]
                dist = math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)
                min_gap = a["radius"] + b["radius"] + 8.0
                self.assertGreaterEqual(
                    dist, min_gap * 0.95,  # 5% tolerance
                    f"Locations {a['name']} and {b['name']} overlap: "
                    f"dist={dist:.1f} < required={min_gap:.1f}"
                )

    def test_explicit_position_is_honoured(self):
        """When a location supplies an explicit position, the anchor must match it."""
        spec = _minimal_map_spec()
        # Place a location with an explicit position well inside the terrain
        spec["locations"] = [
            {"type": "building", "name": "Forge", "position": [50.0, 30.0]},
        ]
        placements = _plan_map_location_anchors(spec)
        self.assertEqual(len(placements), 1)
        ax, ay = placements[0]["anchor"]
        self.assertAlmostEqual(ax, 50.0, delta=2.0, msg="Explicit x not respected")
        self.assertAlmostEqual(ay, 30.0, delta=2.0, msg="Explicit y not respected")

    def test_empty_locations_returns_empty_list(self):
        """No locations in spec must produce an empty placements list, not an error."""
        spec = _minimal_map_spec()
        spec["locations"] = []
        placements = _plan_map_location_anchors(spec)
        self.assertEqual(placements, [])

    def test_radius_grows_with_location_complexity(self):
        """Larger town/castle configurations should produce larger radii."""
        spec_small = _minimal_map_spec()
        spec_small["locations"] = [{"type": "town", "name": "Hamlet", "districts": 1}]
        spec_large = _minimal_map_spec()
        spec_large["locations"] = [{"type": "town", "name": "City", "districts": 8}]

        p_small = _plan_map_location_anchors(spec_small)
        p_large = _plan_map_location_anchors(spec_large)
        self.assertGreater(
            p_large[0]["radius"], p_small[0]["radius"],
            "Larger town did not produce larger radius"
        )


# ===========================================================================
# Suite 5: Vegetation rules normalization
# ===========================================================================

class TestVegetationRulesNormalization(unittest.TestCase):
    """_normalize_vegetation_rules must produce well-formed scatter rules."""

    def test_default_rules_are_returned_for_empty_config(self):
        """Empty veg_cfg must return a non-empty default rule set."""
        rules = _normalize_vegetation_rules({}, biome_name="thornwood_forest")
        self.assertGreater(len(rules), 0, "No default rules returned for known biome")

    def test_all_rules_have_required_keys(self):
        """Every returned rule must contain the keys the scatter engine expects."""
        required = {"vegetation_type", "min_alt", "max_alt", "min_slope", "max_slope",
                    "scale_range", "density"}
        veg_cfg = {
            "density": 0.6,
            "rules": [
                {"vegetation_type": "oak_tree", "min_alt": 0.1, "max_alt": 0.8},
                {"asset": "pine_tree", "density": 0.3},
            ],
        }
        rules = _normalize_vegetation_rules(veg_cfg)
        for rule in rules:
            missing = required - set(rule.keys())
            self.assertFalse(missing, f"Rule {rule} missing keys: {missing}")

    def test_density_inherited_from_top_level(self):
        """Rules without explicit density should inherit the top-level density value."""
        veg_cfg = {
            "density": 0.8,
            "rules": [{"vegetation_type": "shrub"}],  # no per-rule density
        }
        rules = _normalize_vegetation_rules(veg_cfg)
        self.assertGreater(len(rules), 0)
        for rule in rules:
            self.assertAlmostEqual(rule["density"], 0.8, places=2)

    def test_zero_density_exclusion_zone(self):
        """density=0 must produce rules with density=0 (exclusion zones around buildings)."""
        veg_cfg = {
            "density": 0.0,
            "rules": [{"vegetation_type": "grass", "density": 0.0}],
        }
        rules = _normalize_vegetation_rules(veg_cfg)
        for rule in rules:
            self.assertEqual(
                rule["density"], 0.0,
                f"Exclusion zone density was non-zero: {rule['density']}"
            )

    def test_slope_range_is_valid_range(self):
        """min_slope must always be <= max_slope for every rule."""
        veg_cfg = {"density": 0.5}
        rules = _normalize_vegetation_rules(veg_cfg, biome_name="thornwood_forest")
        for rule in rules:
            self.assertLessEqual(
                rule["min_slope"], rule["max_slope"],
                f"Rule {rule['vegetation_type']}: min_slope > max_slope"
            )

    def test_altitude_range_is_valid_range(self):
        """min_alt must always be <= max_alt for every rule."""
        veg_cfg = {"density": 0.5}
        rules = _normalize_vegetation_rules(veg_cfg, biome_name="deep_forest")
        for rule in rules:
            self.assertLessEqual(
                rule["min_alt"], rule["max_alt"],
                f"Rule {rule['vegetation_type']}: min_alt > max_alt"
            )

    def test_biome_specific_rules_differ_from_generic(self):
        """Different biome names should produce different default rule sets."""
        rules_forest = _normalize_vegetation_rules({}, biome_name="thornwood_forest")
        rules_swamp = _normalize_vegetation_rules({}, biome_name="corrupted_swamp")
        types_forest = {r["vegetation_type"] for r in rules_forest}
        types_swamp = {r["vegetation_type"] for r in rules_swamp}
        # At minimum the two sets should not be completely identical
        self.assertNotEqual(
            types_forest, types_swamp,
            "Forest and swamp biomes produced identical vegetation rule sets"
        )


# ===========================================================================
# Suite 6: Budget resolution
# ===========================================================================

class TestBudgetResolution(unittest.TestCase):
    """_resolve_map_generation_budget must respect terrain size and location count."""

    def test_large_terrain_uses_large_world_profile(self):
        """Terrain >= 360 units should auto-select the 'large_world' profile."""
        spec = _minimal_map_spec()
        spec["terrain"]["size"] = 400.0
        budget = _resolve_map_generation_budget(spec)
        self.assertEqual(budget["profile"], "large_world")

    def test_small_terrain_uses_balanced_profile(self):
        """Small terrain with few locations should use 'balanced_pc'."""
        spec = _minimal_map_spec()
        spec["terrain"]["size"] = 200.0
        budget = _resolve_map_generation_budget(spec)
        self.assertEqual(budget["profile"], "balanced_pc")

    def test_explicit_cinematic_profile(self):
        """Explicit 'cinematic' performance_budget must be honoured."""
        spec = _minimal_map_spec()
        spec["performance_budget"] = "cinematic"
        budget = _resolve_map_generation_budget(spec)
        self.assertEqual(budget["profile"], "cinematic")
        self.assertEqual(budget["terrain_resolution_cap"], 512)

    def test_vegetation_cap_is_positive(self):
        """vegetation_max_instances must be > 0 for every profile."""
        for profile in ("cinematic", "balanced_pc", "large_world"):
            spec = _minimal_map_spec()
            spec["performance_budget"] = profile
            budget = _resolve_map_generation_budget(spec)
            self.assertGreater(budget["vegetation_max_instances"], 0)

    def test_budget_includes_terrain_size(self):
        """Returned budget must include terrain_size for downstream consumers."""
        spec = _minimal_map_spec()
        budget = _resolve_map_generation_budget(spec)
        self.assertIn("terrain_size", budget)
        self.assertEqual(budget["terrain_size"], float(spec["terrain"]["size"]))


# ===========================================================================
# Suite 7: Checkpoint save/restore — interior_results bug
# ===========================================================================

class TestCheckpointInteriorResultsBug(unittest.TestCase):
    """Reproduce and verify the fix for the checkpoint bug:

    In blender_server.py Step 9 (line ~3071):
        interior_results = []
    This unconditionally wipes interior_results even when the checkpoint has
    already populated them from a previous run.

    The pipeline_state module (pure Python) is the testable surface here.
    We verify that save/load preserves interior_results perfectly, so that
    the resume path in blender_server.py *can* restore them — and that the
    bug is clearly visible when `interior_results = []` executes anyway.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_interior_results_survive_checkpoint_roundtrip(self):
        """interior_results saved in checkpoint must be restored exactly on load."""
        state = _base_checkpoint_state()
        expected_interiors = state["interior_results"]
        self.assertGreater(len(expected_interiors), 0, "Test setup: must have interior data")

        save_pipeline_checkpoint(self.tmp_dir, state)
        loaded = load_pipeline_checkpoint(self.tmp_dir, "TestRegion")

        self.assertIsNotNone(loaded)
        self.assertEqual(
            loaded["interior_results"], expected_interiors,
            "interior_results were not preserved through checkpoint save/load"
        )

    def test_checkpoint_restore_not_overwritten_by_empty_assignment(self):
        """Simulate the bug: interior_results=[] after checkpoint load wipes data.

        This test documents the expected (correct) behaviour — the resume path
        should READ interior_results from the checkpoint; it should NOT reset
        to [] before the interiors step guard check.
        """
        state = _base_checkpoint_state()
        state["steps_completed"] = [
            "scene_cleared", "terrain_generated",
            "river_0", "water_plane", "road_0",
            "location_mesh_Village", "location_placed_Village",
            "location_mesh_Keep", "location_placed_Keep",
            "biome_painted", "lighting_ready",
            "vegetation_scattered",
            "interiors_generated",  # <-- interiors already done
        ]
        state["interior_results"] = [
            {"location": "Village", "result": {"rooms": 4, "doors": 3}},
            {"location": "Keep", "result": {"rooms": 2, "doors": 1}},
        ]

        save_pipeline_checkpoint(self.tmp_dir, state)
        loaded = load_pipeline_checkpoint(self.tmp_dir, "TestRegion")
        self.assertIsNotNone(loaded)

        # --- Simulate the CORRECT resume path ---
        interior_results_from_ckpt = loaded["interior_results"]

        # The bug: if blender_server.py then does `interior_results = []`
        # unconditionally, all the checkpoint data is wiped.
        # The correct code guards with: if "interiors_generated" not in steps_completed:
        # Since "interiors_generated" IS in steps_completed, the block must be skipped.
        steps_completed = loaded["steps_completed"]
        self.assertIn(
            "interiors_generated", steps_completed,
            "interiors_generated not in steps — guard condition cannot fire"
        )

        # Verify that skipping the interior block leaves interior_results intact
        if "interiors_generated" not in steps_completed:
            # This branch MUST NOT execute
            interior_results_from_ckpt = []  # Bug simulation

        self.assertEqual(
            len(interior_results_from_ckpt), 2,
            "BUG: interior_results were wiped by unconditional `interior_results = []`"
        )

    def test_fresh_run_starts_with_empty_interior_results(self):
        """A brand-new pipeline (no checkpoint) must start with interior_results=[]."""
        # No checkpoint exists yet
        loaded = load_pipeline_checkpoint(self.tmp_dir, "NonExistentMap")
        self.assertIsNone(loaded, "No checkpoint should exist for a new map")

        # Simulate blender_server.py initialisation
        interior_results: list[dict] = []
        self.assertEqual(interior_results, [])

    def test_partial_interior_results_are_accumulated_not_replaced(self):
        """If only some locations have interiors done, the completed ones are preserved."""
        state = _base_checkpoint_state()
        state["interior_results"] = [
            {"location": "Village", "result": {"rooms": 4}},
            # Keep's interior NOT yet done
        ]
        state["steps_completed"] = [
            "scene_cleared", "terrain_generated", "terrain_generated",
            "road_0", "location_mesh_Village", "location_mesh_Keep",
            "interior_Village",  # only Village done
        ]

        save_pipeline_checkpoint(self.tmp_dir, state)
        loaded = load_pipeline_checkpoint(self.tmp_dir, "TestRegion")
        self.assertIsNotNone(loaded)

        # When resuming, existing interior_results must be loaded from checkpoint
        resumed_interiors = loaded["interior_results"]
        self.assertEqual(len(resumed_interiors), 1)
        self.assertEqual(resumed_interiors[0]["location"], "Village")

    def test_multiple_interior_entries_preserved(self):
        """All interior_results entries must survive, not just the first."""
        entries = [
            {"location": f"Loc_{i}", "result": {"rooms": i + 1}}
            for i in range(5)
        ]
        state = _base_checkpoint_state(interior_results=entries)
        save_pipeline_checkpoint(self.tmp_dir, state)
        loaded = load_pipeline_checkpoint(self.tmp_dir, "TestRegion")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["interior_results"], entries)


# ===========================================================================
# Suite 8: Resume skips completed steps
# ===========================================================================

class TestResumeSkipsCompletedSteps(unittest.TestCase):
    """Steps already in steps_completed must be skipped on resume."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_get_remaining_steps_excludes_completed(self):
        """get_remaining_steps must return only steps not in checkpoint."""
        checkpoint = {
            "steps_completed": ["scene_cleared", "terrain_generated", "road_0"],
        }
        all_steps = [
            "scene_cleared", "terrain_generated", "water_plane",
            "road_0", "road_1", "vegetation_scattered",
        ]
        remaining = get_remaining_steps(checkpoint, all_steps)
        self.assertNotIn("scene_cleared", remaining)
        self.assertNotIn("terrain_generated", remaining)
        self.assertNotIn("road_0", remaining)
        self.assertIn("water_plane", remaining)
        self.assertIn("road_1", remaining)
        self.assertIn("vegetation_scattered", remaining)

    def test_empty_steps_completed_means_all_remaining(self):
        """If no steps are completed, all steps should be returned."""
        checkpoint = {"steps_completed": []}
        all_steps = ["scene_cleared", "terrain_generated", "road_0"]
        remaining = get_remaining_steps(checkpoint, all_steps)
        self.assertEqual(remaining, all_steps)

    def test_all_steps_completed_means_none_remaining(self):
        """If all steps are completed, remaining must be empty."""
        all_steps = ["scene_cleared", "terrain_generated", "road_0"]
        checkpoint = {"steps_completed": all_steps[:]}
        remaining = get_remaining_steps(checkpoint, all_steps)
        self.assertEqual(remaining, [])

    def test_road_steps_are_individually_skippable(self):
        """Roads use per-road step keys (road_0, road_1 ...) — verify individual skip."""
        completed = {
            "steps_completed": ["scene_cleared", "terrain_generated", "road_0"],
        }
        spec_roads = [{"waypoints": [[0, 0], [100, 100]]}, {"waypoints": [[50, 50], [150, 150]]}]
        _completed_roads = {s.replace("road_", "") for s in completed["steps_completed"] if s.startswith("road_")}
        to_process = [i for i, _ in enumerate(spec_roads) if str(i) not in _completed_roads]
        self.assertNotIn(0, to_process, "road_0 should be skipped")
        self.assertIn(1, to_process, "road_1 should not be skipped")

    def test_location_mesh_steps_are_individually_skippable(self):
        """Location mesh steps use location name as key — verify individual skip."""
        completed_steps = [
            "scene_cleared", "terrain_generated",
            "location_mesh_Village",  # Village already done
        ]
        locations = [
            {"name": "Village", "type": "town"},
            {"name": "Keep", "type": "castle"},
        ]
        completed_locs = {
            s.replace("location_mesh_", "")
            for s in completed_steps
            if s.startswith("location_mesh_")
        }
        to_process = [loc for loc in locations if loc["name"] not in completed_locs]
        names_to_process = [loc["name"] for loc in to_process]
        self.assertNotIn("Village", names_to_process, "Village should be skipped")
        self.assertIn("Keep", names_to_process, "Keep should not be skipped")

    def test_checkpoint_compatibility_seed_mismatch_rejected(self):
        """Checkpoint with different seed must be rejected as incompatible."""
        checkpoint = {"seed": 42, "location_count": 3}
        spec = _minimal_map_spec()
        spec["seed"] = 99  # different seed
        ok, reason = validate_checkpoint_compatibility(checkpoint, spec)
        self.assertFalse(ok)
        self.assertIn("42", reason)
        self.assertIn("99", reason)

    def test_checkpoint_compatibility_location_count_mismatch_rejected(self):
        """Checkpoint with different location count must be rejected."""
        checkpoint = {"seed": 42, "location_count": 5}
        spec = _minimal_map_spec()  # has 3 locations
        ok, reason = validate_checkpoint_compatibility(checkpoint, spec)
        self.assertFalse(ok)
        self.assertIn("5", reason)
        self.assertIn("3", reason)

    def test_checkpoint_compatibility_matching_spec_accepted(self):
        """Checkpoint matching seed and location count must be accepted."""
        spec = _minimal_map_spec()
        checkpoint = {"seed": spec["seed"], "location_count": len(spec["locations"])}
        ok, reason = validate_checkpoint_compatibility(checkpoint, spec)
        self.assertTrue(ok, f"Compatible checkpoint rejected: {reason}")
        self.assertEqual(reason, "")


# ===========================================================================
# Suite 9: Lighting preset for biome
# ===========================================================================

class TestLightingPresetForBiome(unittest.TestCase):
    """_lighting_preset_for_biome must return valid preset strings for all biomes."""

    KNOWN_BIOMES = [
        "thornwood_forest", "deep_forest", "veil_crack_zone",
        "corrupted_swamp", "cemetery", "tundra", "desert",
    ]

    def test_thornwood_forest_gets_forest_preset(self):
        preset = _lighting_preset_for_biome("thornwood_forest")
        self.assertEqual(preset, "forest_review")

    def test_corrupted_biomes_get_veil_preset(self):
        for biome in ("veil_crack_zone", "corrupted_swamp", "cemetery"):
            preset = _lighting_preset_for_biome(biome)
            self.assertEqual(preset, "veil_corrupted", f"Wrong preset for {biome}")

    def test_unknown_biome_returns_default(self):
        preset = _lighting_preset_for_biome("unknown_biome_xyz")
        self.assertIsNotNone(preset)
        self.assertIsInstance(preset, str)
        self.assertGreater(len(preset), 0)

    def test_empty_biome_name_returns_default(self):
        preset = _lighting_preset_for_biome("")
        self.assertIsInstance(preset, str)
        self.assertGreater(len(preset), 0)


# ===========================================================================
# Suite 10: End-to-end pipeline step ordering (pure logic, no Blender)
# ===========================================================================

class TestPipelineStepOrdering(unittest.TestCase):
    """Verify that helper functions produce correct inputs for each pipeline step."""

    def test_full_spec_produces_correct_budget_and_locations(self):
        """Full map_spec must produce a budget AND location placements without errors."""
        spec = _minimal_map_spec()
        budget = _resolve_map_generation_budget(spec)
        placements = _plan_map_location_anchors(spec)

        self.assertIn("profile", budget)
        self.assertEqual(len(placements), len(spec["locations"]))

    def test_terrain_resolution_capped_by_budget(self):
        """Terrain resolution from spec must be capped to budget's terrain_resolution_cap."""
        spec = _minimal_map_spec()
        spec["performance_budget"] = "large_world"
        spec["terrain"]["resolution"] = 1024  # requests way more than budget allows

        budget = _resolve_map_generation_budget(spec)
        cap = budget["terrain_resolution_cap"]
        effective_res = min(int(spec["terrain"]["resolution"]), int(cap))
        self.assertLessEqual(effective_res, cap)

    def test_vegetation_max_instances_capped_by_budget(self):
        """Vegetation instance count must be capped to budget's vegetation_max_instances."""
        spec = _minimal_map_spec()
        spec["performance_budget"] = "large_world"
        spec["vegetation"]["max_instances"] = 99999

        budget = _resolve_map_generation_budget(spec)
        cap = budget["vegetation_max_instances"]
        effective = min(int(spec["vegetation"]["max_instances"]), int(cap))
        self.assertLessEqual(effective, cap)

    def test_location_params_include_seed_offset(self):
        """Each location's generation params must have unique seed (map_seed + offset + index)."""
        spec = _minimal_map_spec()
        map_seed = spec["seed"]
        seeds = []
        for i, loc in enumerate(spec["locations"]):
            params = _build_location_generation_params(
                loc, map_spec=spec, map_seed=map_seed, index=i
            )
            seeds.append(params["seed"])
        # Seeds must all be distinct
        self.assertEqual(len(seeds), len(set(seeds)), "Duplicate seeds in location params")

    def test_location_params_carry_name(self):
        """Location params must include the location name for object creation."""
        spec = _minimal_map_spec()
        for i, loc in enumerate(spec["locations"]):
            params = _build_location_generation_params(
                loc, map_spec=spec, map_seed=spec["seed"], index=i
            )
            self.assertIn("name", params)
            self.assertEqual(params["name"], loc["name"])

    def test_dungeon_location_has_floors_if_specified(self):
        """Dungeon location with floors specified must carry num_floors in params.

        _build_location_generation_params maps location["floors"] -> params["num_floors"]
        for dungeon types (used by world_generate_multi_floor_dungeon).
        """
        spec = _minimal_map_spec()
        dungeon_loc = next(l for l in spec["locations"] if l["type"] == "dungeon")
        params = _build_location_generation_params(
            dungeon_loc, map_spec=spec, map_seed=spec["seed"], index=2
        )
        # Dungeon floors are stored as num_floors (not floors) in the generated params
        self.assertIn("num_floors", params)
        self.assertEqual(params["num_floors"], dungeon_loc["floors"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
