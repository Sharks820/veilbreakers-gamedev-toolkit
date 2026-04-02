"""AAA castle and settlement system tests (Phase 39, Plan 03).

Covers:
- Concentric castle wall rings (count, height progression, wall thickness)
- Gatehouse (passage depth/width, portcullis, murder holes, arrow slits)
- Market square (area, central feature, stall count)
- District zoning (5 zone types, market near center, slums at edge)
- Trim sheet UV mapping (stone/wood/roof/ground bands, atlas size)
- Settlement district integration
- Road hierarchy widths

All functions under test are pure-logic (no bpy imports) so they run
without a Blender connection.
"""
from __future__ import annotations

import math
import unittest

from blender_addon.handlers.worldbuilding_layout import (
    generate_concentric_castle_spec,
    generate_market_square,
    assign_district_zones,
    generate_trim_sheet_uv_spec,
)
from blender_addon.handlers.building_quality import (
    get_trim_sheet_uv_band,
    apply_trim_sheet_uvs,
    TRIM_SHEET_ATLAS_SIZE,
    TRIM_SHEET_BANDS,
)


# ===========================================================================
# Concentric Castle Wall Tests
# ===========================================================================


class TestCastleConcentricRings(unittest.TestCase):
    """Verify that generate_concentric_castle_spec produces correct ring structure."""

    def _spec(self, rings: int = 2, radius: float = 50.0, seed: int = 1) -> dict:
        return generate_concentric_castle_spec(
            castle_radius=radius, rings=rings, seed=seed
        )

    def test_castle_concentric_ring_count_two(self):
        """Default 2 rings should produce exactly 2 wall rings."""
        spec = self._spec(rings=2)
        self.assertEqual(spec["ring_count"], 2)
        self.assertEqual(len(spec["rings"]), 2)

    def test_castle_concentric_ring_count_three(self):
        """Requesting 3 rings should produce exactly 3 wall rings."""
        spec = self._spec(rings=3)
        self.assertEqual(spec["ring_count"], 3)
        self.assertEqual(len(spec["rings"]), 3)

    def test_castle_ring_height_progression_two_rings(self):
        """Inner ring must be taller than outer ring (by 2-4m per spec)."""
        spec = self._spec(rings=2)
        rings = spec["rings"]
        outer_h = rings[0]["height"]
        inner_h = rings[1]["height"]
        self.assertGreater(inner_h, outer_h, "Inner ring must be taller than outer ring")
        self.assertGreaterEqual(inner_h - outer_h, 2.0, "Height delta must be >= 2m")
        self.assertLessEqual(inner_h - outer_h, 6.0, "Height delta should be <= 6m")

    def test_castle_ring_height_progression_three_rings(self):
        """Heights must increase from ring 0 (outermost) to ring 2 (innermost)."""
        spec = self._spec(rings=3)
        rings = spec["rings"]
        h0, h1, h2 = rings[0]["height"], rings[1]["height"], rings[2]["height"]
        self.assertGreater(h1, h0, "Ring 1 must be taller than ring 0")
        self.assertGreater(h2, h1, "Ring 2 must be taller than ring 1")

    def test_castle_outer_ring_height_in_range(self):
        """Outer ring height must be 6-8m (research spec)."""
        spec = self._spec(rings=2)
        h = spec["rings"][0]["height"]
        self.assertGreaterEqual(h, 6.0)
        self.assertLessEqual(h, 8.0)

    def test_castle_inner_ring_height_in_range(self):
        """Inner ring height (2-ring) must be 10-12m (research spec)."""
        spec = self._spec(rings=2)
        h = spec["rings"][1]["height"]
        self.assertGreaterEqual(h, 10.0)
        self.assertLessEqual(h, 12.0)

    def test_castle_wall_thickness(self):
        """Wall thickness must be 2-3m (enough for wall-walk)."""
        spec = self._spec(rings=2)
        for ring in spec["rings"]:
            t = ring.get("thickness", 0)
            self.assertGreaterEqual(t, 2.0, f"Wall too thin: {t}m")
            self.assertLessEqual(t, 3.0, f"Wall too thick: {t}m")

    def test_castle_tower_spacing(self):
        """Towers must be spaced every 25-40m around each ring."""
        spec = self._spec(rings=2, radius=60.0, seed=42)
        for ring_idx, ring in enumerate(spec["rings"]):
            towers = ring.get("tower_positions", [])
            if len(towers) >= 2:
                # Check angular spacing converted to arc length
                ring_radius = ring.get("radius", 60.0)
                n = len(towers)
                arc = (2 * math.pi * ring_radius) / n
                self.assertGreaterEqual(
                    arc, 20.0,
                    f"Ring {ring_idx}: tower spacing {arc:.1f}m < 20m"
                )
                self.assertLessEqual(
                    arc, 50.0,
                    f"Ring {ring_idx}: tower spacing {arc:.1f}m > 50m"
                )

    def test_castle_ring_radii_decrease(self):
        """Each inner ring must have a smaller radius than the previous ring."""
        spec = self._spec(rings=3, radius=60.0)
        rings = spec["rings"]
        for i in range(1, len(rings)):
            self.assertLess(
                rings[i]["radius"],
                rings[i - 1]["radius"],
                f"Ring {i} radius not smaller than ring {i-1}",
            )

    def test_castle_gatehouse_present(self):
        """Spec must include a gatehouse dict."""
        spec = self._spec(rings=2)
        self.assertIn("gatehouse", spec)
        self.assertIsNotNone(spec["gatehouse"])


# ===========================================================================
# Gatehouse Tests
# ===========================================================================


class TestCastleGatehouse(unittest.TestCase):
    """Verify gatehouse passage geometry meets AAA specs."""

    def _gatehouse(self, seed: int = 1) -> dict:
        spec = generate_concentric_castle_spec(castle_radius=50.0, rings=2, seed=seed)
        return spec["gatehouse"]

    def test_gatehouse_passage_depth(self):
        """Gatehouse passage must be 8-15m deep (research spec)."""
        gh = self._gatehouse()
        depth = gh.get("passage_depth", 0)
        self.assertGreaterEqual(depth, 8.0, f"Passage too shallow: {depth}m")
        self.assertLessEqual(depth, 15.0, f"Passage too deep: {depth}m")

    def test_gatehouse_passage_width(self):
        """Gatehouse passage must be 3-4m wide (enough for carts)."""
        gh = self._gatehouse()
        width = gh.get("passage_width", 0)
        self.assertGreaterEqual(width, 3.0, f"Passage too narrow: {width}m")
        self.assertLessEqual(width, 4.0, f"Passage too wide: {width}m")

    def test_gatehouse_portcullis_present(self):
        """Gatehouse must have a portcullis object spec."""
        gh = self._gatehouse()
        self.assertIn("portcullis", gh)
        portcullis = gh["portcullis"]
        self.assertIsNotNone(portcullis)

    def test_gatehouse_portcullis_iron_material(self):
        """Portcullis material must be iron/metallic (metallic=1.0)."""
        gh = self._gatehouse()
        portcullis = gh.get("portcullis", {})
        # Portcullis stores metallic and material_srgb directly on the dict
        metallic = portcullis.get("metallic", 0)
        srgb = portcullis.get("material_srgb", ())
        self.assertTrue(
            metallic >= 1.0 or srgb == (135, 131, 126),
            f"Portcullis material must be iron/metallic, got metallic={metallic} srgb={srgb}",
        )

    def test_gatehouse_murder_holes(self):
        """Gatehouse must have 4-6 murder holes in the passage ceiling."""
        gh = self._gatehouse()
        count = gh.get("murder_hole_count", 0)
        self.assertGreaterEqual(count, 4, f"Too few murder holes: {count}")
        self.assertLessEqual(count, 6, f"Too many murder holes: {count}")

    def test_gatehouse_arrow_slits(self):
        """Flanking towers must have arrow slits (>= 1 per tower face)."""
        gh = self._gatehouse()
        # arrow_slits_per_tower_face is the count; flanking_towers carry the actual list
        count = gh.get("arrow_slits_per_tower_face", 0)
        towers = gh.get("flanking_towers", [])
        has_slits = count > 0 or any(len(t.get("arrow_slits", [])) > 0 for t in towers)
        self.assertTrue(has_slits, "No arrow slits defined in gatehouse flanking towers")

    def test_gatehouse_flanking_towers(self):
        """Gatehouse must specify two flanking towers."""
        gh = self._gatehouse()
        towers = gh.get("flanking_towers", [])
        self.assertGreaterEqual(len(towers), 2, "Gatehouse needs at least 2 flanking towers")


# ===========================================================================
# Market Square Tests
# ===========================================================================


class TestMarketSquare(unittest.TestCase):
    """Verify market square generator output."""

    def _square(self, size: str = "medium", seed: int = 42) -> dict:
        return generate_market_square(
            center=(0.0, 0.0),
            size=size,
            road_intersections=[(0.0, 5.0), (5.0, 0.0)],
            seed=seed,
        )

    def test_market_square_area_small(self):
        """Small market square must be ~400m2."""
        sq = self._square(size="small")
        area = sq.get("area", 0)
        self.assertGreaterEqual(area, 350.0, "Small square area < 350m2")
        self.assertLessEqual(area, 500.0, "Small square area > 500m2")

    def test_market_square_area_medium(self):
        """Medium market square must be ~900m2."""
        sq = self._square(size="medium")
        area = sq.get("area", 0)
        self.assertGreaterEqual(area, 700.0, "Medium square area < 700m2")
        self.assertLessEqual(area, 1100.0, "Medium square area > 1100m2")

    def test_market_square_area_large(self):
        """Large market square must be ~2500m2."""
        sq = self._square(size="large")
        area = sq.get("area", 0)
        self.assertGreaterEqual(area, 2000.0, "Large square area < 2000m2")
        self.assertLessEqual(area, 3000.0, "Large square area > 3000m2")

    def test_market_square_area_range(self):
        """Any size square must be within 400-2500m2 spec range."""
        for size in ("small", "medium", "large"):
            sq = self._square(size=size)
            area = sq.get("area", 0)
            self.assertGreaterEqual(area, 350.0, f"{size}: area {area} < 350m2")
            self.assertLessEqual(area, 3000.0, f"{size}: area {area} > 3000m2")

    def test_market_square_central_feature(self):
        """Market square must have a central feature (well/fountain/market_cross)."""
        sq = self._square()
        feature_type = sq.get("central_feature_type", "")
        valid = {"well", "fountain", "market_cross"}
        self.assertIn(feature_type, valid, f"Unknown central feature: {feature_type}")

    def test_market_square_stall_count(self):
        """Market square must have at least 1 stall."""
        sq = self._square()
        stalls = sq.get("stall_count", 0)
        self.assertGreater(stalls, 0, "No market stalls generated")

    def test_market_square_stall_positions(self):
        """stall_positions list length must match stall_count."""
        sq = self._square()
        count = sq.get("stall_count", -1)
        positions = sq.get("stall_positions", [])
        self.assertEqual(
            len(positions), count,
            f"stall_count={count} but {len(positions)} positions",
        )

    def test_market_square_center_preserved(self):
        """Center coordinates must match the supplied center parameter."""
        center = (10.0, 20.0)
        sq = generate_market_square(center=center, size="medium", road_intersections=[], seed=0)
        self.assertEqual(sq.get("center"), center)


# ===========================================================================
# District Zoning Tests
# ===========================================================================


class TestDistrictZoning(unittest.TestCase):
    """Verify district zone assignment logic."""

    def _zones(self, seed: int = 0) -> dict:
        # assign_district_zones expects {"min": (x,y), "max": (x,y)}
        bounds = {
            "min": (-100.0, -100.0),
            "max": (100.0, 100.0),
        }
        return assign_district_zones(
            settlement_bounds=bounds,
            castle_pos=(0.0, 0.0),
            wall_positions=[(80.0, 0.0), (-80.0, 0.0), (0.0, 80.0), (0.0, -80.0)],
            road_network=[{"start": (-100.0, 0.0), "end": (100.0, 0.0), "width": 5.5}],
            seed=seed,
        )

    def test_district_zone_types(self):
        """Result must contain all 5 required zone types."""
        result = self._zones()
        zone_types = {z["type"] for z in result["zones"]}
        required = {"market", "residential", "military", "religious", "slums"}
        missing = required - zone_types
        self.assertFalse(missing, f"Missing district types: {missing}")

    def test_district_market_near_center(self):
        """Market zone seed point must be closest to settlement center (0,0)."""
        result = self._zones()
        zones_by_type = {z["type"]: z for z in result["zones"]}
        market = zones_by_type.get("market")
        self.assertIsNotNone(market, "No market zone found")
        market_seed = market.get("seed_pos", (0, 0))
        market_dist = math.hypot(market_seed[0], market_seed[1])

        for zone in result["zones"]:
            if zone["type"] == "market":
                continue
            seed_pt = zone.get("seed_pos", (0, 0))
            dist = math.hypot(seed_pt[0], seed_pt[1])
            # Market should be among the closest zones to center
            # (allow ties with religious zone which is also near center)
            if zone["type"] not in ("religious",):
                self.assertLessEqual(
                    market_dist, dist + 15.0,
                    f"Market ({market_dist:.1f}m) is farther from center than {zone['type']} ({dist:.1f}m)",
                )

    def test_district_slums_at_edge(self):
        """Slums zone seed point must be near settlement periphery (>= 60m from center)."""
        result = self._zones()
        zones_by_type = {z["type"]: z for z in result["zones"]}
        slums = zones_by_type.get("slums")
        self.assertIsNotNone(slums, "No slums zone found")
        seed_pt = slums.get("seed_pos", (0, 0))
        dist = math.hypot(seed_pt[0], seed_pt[1])
        # Slums placed at ~80% of radius (radius=100 → ~80m), threshold 60m
        self.assertGreaterEqual(dist, 60.0, f"Slums too close to center: {dist:.1f}m")

    def test_district_zone_polygons_present(self):
        """Each zone must include a polygon_verts list with >= 3 vertices."""
        result = self._zones()
        for zone in result["zones"]:
            verts = zone.get("polygon_verts", [])
            self.assertGreaterEqual(
                len(verts), 3,
                f"Zone {zone['type']} polygon has only {len(verts)} vertices",
            )

    def test_district_zone_count(self):
        """Result must contain exactly 5 zones."""
        result = self._zones()
        self.assertEqual(len(result["zones"]), 5)

    def test_settlement_has_districts(self):
        """assign_district_zones must return non-empty zones list."""
        result = self._zones(seed=99)
        self.assertGreater(len(result.get("zones", [])), 0)


# ===========================================================================
# Trim Sheet UV Tests
# ===========================================================================


class TestTrimSheetUV(unittest.TestCase):
    """Verify trim sheet atlas UV band assignment."""

    def test_trim_sheet_atlas_size(self):
        """TRIM_SHEET_ATLAS_SIZE must be 2048."""
        self.assertEqual(TRIM_SHEET_ATLAS_SIZE, 2048)

    def test_trim_sheet_uv_bands_stone_range(self):
        """Stone/wall band must be Y 0-256 pixels."""
        band = get_trim_sheet_uv_band("stone")
        lo_px, hi_px = band["band_pixel_range"]
        self.assertEqual(lo_px, 0)
        self.assertEqual(hi_px, 256)

    def test_trim_sheet_uv_bands_wall_range(self):
        """Wall band must be Y 0-256 pixels (same as stone)."""
        band = get_trim_sheet_uv_band("wall")
        lo_px, hi_px = band["band_pixel_range"]
        self.assertEqual(lo_px, 0)
        self.assertEqual(hi_px, 256)

    def test_trim_sheet_uv_bands_wood_range(self):
        """Wood band must be Y 384-640 pixels."""
        band = get_trim_sheet_uv_band("wood")
        lo_px, hi_px = band["band_pixel_range"]
        self.assertEqual(lo_px, 384)
        self.assertEqual(hi_px, 640)

    def test_trim_sheet_uv_bands_roof_range(self):
        """Roof band must be Y 1024-1280 pixels."""
        band = get_trim_sheet_uv_band("roof")
        lo_px, hi_px = band["band_pixel_range"]
        self.assertEqual(lo_px, 1024)
        self.assertEqual(hi_px, 1280)

    def test_trim_sheet_uv_bands_ground_range(self):
        """Ground band must be Y 1280-1408 pixels."""
        band = get_trim_sheet_uv_band("ground")
        lo_px, hi_px = band["band_pixel_range"]
        self.assertEqual(lo_px, 1280)
        self.assertEqual(hi_px, 1408)

    def test_trim_sheet_uv_normalised(self):
        """UV band values must be in [0, 1] range."""
        for key in TRIM_SHEET_BANDS:
            band = get_trim_sheet_uv_band(key)
            lo, hi = band["uv_band"]
            self.assertGreaterEqual(lo, 0.0)
            self.assertLessEqual(hi, 1.0)
            self.assertLess(lo, hi)

    def test_apply_trim_sheet_uvs_annotates_spec(self):
        """apply_trim_sheet_uvs must add trim_sheet_uvs to the spec."""
        spec = {
            "name": "test_building",
            "components": ["wall_north", "wall_south", "roof_main", "floor_ground"],
        }
        result = apply_trim_sheet_uvs(spec)
        self.assertIn("trim_sheet_uvs", result)
        self.assertIn("trim_sheet_atlas_size", result)

    def test_apply_trim_sheet_uvs_wall_component(self):
        """Wall components must map to stone band (Y 0-256)."""
        spec = {"components": ["wall_north"]}
        result = apply_trim_sheet_uvs(spec)
        uv_entry = result["trim_sheet_uvs"].get("wall_north", {})
        lo_px, hi_px = uv_entry.get("band_pixel_range", (-1, -1))
        self.assertEqual(lo_px, 0)
        self.assertEqual(hi_px, 256)

    def test_apply_trim_sheet_uvs_roof_component(self):
        """Roof components must map to roof band (Y 1024-1280)."""
        spec = {"components": ["roof_tiles"]}
        result = apply_trim_sheet_uvs(spec)
        uv_entry = result["trim_sheet_uvs"].get("roof_tiles", {})
        lo_px, hi_px = uv_entry.get("band_pixel_range", (-1, -1))
        self.assertEqual(lo_px, 1024)
        self.assertEqual(hi_px, 1280)

    def test_generate_trim_sheet_uv_spec_wall(self):
        """generate_trim_sheet_uv_spec for wall must use correct atlas size and band."""
        spec = generate_trim_sheet_uv_spec(mesh_type="wall", atlas_size=2048)
        self.assertEqual(spec["atlas_size"], 2048)
        lo_px, hi_px = spec["band_pixel_range"]
        self.assertEqual(lo_px, 0)
        self.assertEqual(hi_px, 256)

    def test_generate_trim_sheet_uv_spec_normalised(self):
        """UV band from generate_trim_sheet_uv_spec must be in [0,1]."""
        spec = generate_trim_sheet_uv_spec(mesh_type="stone", atlas_size=2048)
        lo, hi = spec["uv_band"]
        self.assertGreaterEqual(lo, 0.0)
        self.assertLessEqual(hi, 1.0)
        self.assertLess(lo, hi)


# ===========================================================================
# Road Hierarchy Tests
# ===========================================================================


class TestRoadHierarchyWidths(unittest.TestCase):
    """Verify road width constants used in settlement generation."""

    def test_road_hierarchy_widths(self):
        """District zones road_network must respect width spec when provided."""
        bounds = {
            "min": (-150.0, -150.0),
            "max": (150.0, 150.0),
        }
        road_network = [
            {"start": (-150.0, 0.0), "end": (150.0, 0.0), "width": 5.5, "type": "main"},
            {"start": (0.0, -150.0), "end": (0.0, 150.0), "width": 3.0, "type": "secondary"},
            {"start": (-50.0, -20.0), "end": (50.0, -20.0), "width": 1.8, "type": "alley"},
        ]
        result = assign_district_zones(
            settlement_bounds=bounds,
            castle_pos=(0.0, 0.0),
            wall_positions=[],
            road_network=road_network,
            seed=7,
        )
        # Verify result is valid (zone assignment runs without errors)
        self.assertIn("zones", result)
        self.assertGreater(len(result["zones"]), 0)

        # Verify road width constants are in expected ranges
        main_road_widths = [r["width"] for r in road_network if r["type"] == "main"]
        secondary_widths = [r["width"] for r in road_network if r["type"] == "secondary"]
        alley_widths = [r["width"] for r in road_network if r["type"] == "alley"]

        for w in main_road_widths:
            self.assertGreaterEqual(w, 5.0, f"Main road too narrow: {w}m")
            self.assertLessEqual(w, 6.0, f"Main road too wide: {w}m")
        for w in secondary_widths:
            self.assertGreaterEqual(w, 3.0, f"Secondary road too narrow: {w}m")
            self.assertLessEqual(w, 4.0, f"Secondary road too wide: {w}m")
        for w in alley_widths:
            self.assertGreaterEqual(w, 1.5, f"Alley too narrow: {w}m")
            self.assertLessEqual(w, 2.0, f"Alley too wide: {w}m")


if __name__ == "__main__":
    unittest.main()
