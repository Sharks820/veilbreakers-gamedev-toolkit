"""Unit tests for settlement grammar pure-logic module.

Tests district ring assignment, building type selection, prop manifest
generation, OBB lot subdivision, and road network organic generation --
all without Blender.
"""

from __future__ import annotations

import sys
import os

import pytest

# ---------------------------------------------------------------------------
# Path setup -- mirrors test_building_grammar.py pattern
# ---------------------------------------------------------------------------

# Ensure blender_addon package is importable
_TOOLKIT_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _TOOLKIT_ROOT not in sys.path:
    sys.path.insert(0, _TOOLKIT_ROOT)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_grammar():
    from blender_addon.handlers._settlement_grammar import (
        RING_THRESHOLDS,
        DISTRICT_FILL_RATES,
        DISTRICT_BUILDING_TYPES,
        CORRUPTION_TIERS,
        ROAD_PROP_TYPES,
        ring_for_position,
        weighted_building_type,
        generate_road_network_organic,
        perturb_road_points,
        subdivide_block_to_lots,
        assign_buildings_to_lots,
        generate_prop_manifest,
        prop_tier_for_pressure,
    )
    return {
        "RING_THRESHOLDS": RING_THRESHOLDS,
        "DISTRICT_FILL_RATES": DISTRICT_FILL_RATES,
        "DISTRICT_BUILDING_TYPES": DISTRICT_BUILDING_TYPES,
        "CORRUPTION_TIERS": CORRUPTION_TIERS,
        "ROAD_PROP_TYPES": ROAD_PROP_TYPES,
        "ring_for_position": ring_for_position,
        "weighted_building_type": weighted_building_type,
        "generate_road_network_organic": generate_road_network_organic,
        "perturb_road_points": perturb_road_points,
        "subdivide_block_to_lots": subdivide_block_to_lots,
        "assign_buildings_to_lots": assign_buildings_to_lots,
        "generate_prop_manifest": generate_prop_manifest,
        "prop_tier_for_pressure": prop_tier_for_pressure,
    }


# ---------------------------------------------------------------------------
# Constants integrity tests (no stubs -- should always pass)
# ---------------------------------------------------------------------------

class TestConstants:
    """Test that constants have correct structure and values."""

    def test_district_fill_rates_in_range(self):
        """All fill rates must be in [0, 1]."""
        g = _import_grammar()
        for district, rate in g["DISTRICT_FILL_RATES"].items():
            assert 0.0 <= rate <= 1.0, f"Fill rate out of range for district '{district}': {rate}"

    def test_corruption_tiers_cover_full_range(self):
        """Corruption tiers must cover from 0.0 to >= 1.0 without gaps."""
        g = _import_grammar()
        tiers = g["CORRUPTION_TIERS"]
        prev_threshold = 0.0
        for threshold, band, spacing_min, spacing_max in tiers:
            # No gap between previous and current threshold
            assert threshold > prev_threshold, (
                f"Gap in corruption tiers: prev={prev_threshold}, current={threshold}"
            )
            prev_threshold = threshold
        # Final tier must cover at least 1.0
        assert prev_threshold >= 1.0, (
            f"Corruption tiers do not cover 1.0 (max threshold={prev_threshold})"
        )

    def test_ring_thresholds_ordered_and_cover_full_range(self):
        """RING_THRESHOLDS must be monotonically increasing and cover >= 1.0."""
        g = _import_grammar()
        thresholds = g["RING_THRESHOLDS"]
        prev = 0.0
        for name, t in thresholds:
            assert t > prev, f"Ring thresholds not monotonically increasing at '{name}'"
            prev = t
        assert prev >= 1.0, f"Ring thresholds do not cover 1.0 (max={prev})"

    def test_all_districts_have_building_types(self):
        """Every district named in RING_THRESHOLDS must have a DISTRICT_BUILDING_TYPES entry."""
        g = _import_grammar()
        ring_districts = {name for name, _ in g["RING_THRESHOLDS"]}
        for district in ring_districts:
            assert district in g["DISTRICT_BUILDING_TYPES"], (
                f"District '{district}' missing from DISTRICT_BUILDING_TYPES"
            )

    def test_all_districts_have_road_prop_types(self):
        """Every district named in RING_THRESHOLDS must have a ROAD_PROP_TYPES entry."""
        g = _import_grammar()
        ring_districts = {name for name, _ in g["RING_THRESHOLDS"]}
        for district in ring_districts:
            assert district in g["ROAD_PROP_TYPES"], (
                f"District '{district}' missing from ROAD_PROP_TYPES"
            )


# ---------------------------------------------------------------------------
# Ring district assignment tests
# ---------------------------------------------------------------------------

class TestRingDistrictAssignment:
    """Test ring_for_position returns correct district zones."""

    def test_ring_district_assignment_basic_distances(self):
        """Positions at known distances map to expected rings."""
        g = _import_grammar()
        ring_for_position = g["ring_for_position"]
        center = (0.0, 0.0)
        radius = 100.0

        # 10% of radius => market_square (threshold 0.15)
        pos_10pct = (10.0, 0.0)
        assert ring_for_position(pos_10pct, center, radius) == "market_square"

        # 25% of radius => civic_ring (threshold 0.15-0.35)
        pos_25pct = (25.0, 0.0)
        assert ring_for_position(pos_25pct, center, radius) == "civic_ring"

        # 50% of radius => residential (threshold 0.35-0.60)
        pos_50pct = (50.0, 0.0)
        assert ring_for_position(pos_50pct, center, radius) == "residential"

        # 70% of radius => industrial (threshold 0.60-0.80)
        pos_70pct = (70.0, 0.0)
        assert ring_for_position(pos_70pct, center, radius) == "industrial"

        # 90% of radius => outskirts (threshold 0.80-1.01)
        pos_90pct = (90.0, 0.0)
        assert ring_for_position(pos_90pct, center, radius) == "outskirts"

    def test_ring_boundary_edge_cases(self):
        """At exactly 0.15 * radius, position falls into civic_ring (first ring that FAILS threshold < 0.15)."""
        g = _import_grammar()
        ring_for_position = g["ring_for_position"]
        center = (0.0, 0.0)
        radius = 100.0

        # Exactly at the market_square/civic_ring boundary (dist_norm = 0.15)
        # dist_norm < 0.15 is False, so civic_ring is next
        pos_boundary = (15.0, 0.0)
        result = ring_for_position(pos_boundary, center, radius)
        assert result == "civic_ring", (
            f"Expected 'civic_ring' at exact boundary 0.15, got '{result}'"
        )

    def test_ring_center_is_market_square(self):
        """Center position (dist=0) must be market_square."""
        g = _import_grammar()
        ring_for_position = g["ring_for_position"]
        center = (0.0, 0.0)
        radius = 100.0
        assert ring_for_position((0.0, 0.0), center, radius) == "market_square"

    def test_ring_beyond_radius_is_outskirts(self):
        """Positions beyond radius fall into outskirts."""
        g = _import_grammar()
        ring_for_position = g["ring_for_position"]
        center = (0.0, 0.0)
        radius = 100.0
        assert ring_for_position((150.0, 0.0), center, radius) == "outskirts"

    def test_ring_non_origin_center(self):
        """ring_for_position works with non-origin centers."""
        g = _import_grammar()
        ring_for_position = g["ring_for_position"]
        center = (500.0, 300.0)
        radius = 80.0
        # Position at center -> market_square
        assert ring_for_position((500.0, 300.0), center, radius) == "market_square"
        # Position at 40% of radius from center -> residential
        pos = (500.0 + 32.0, 300.0)  # 32/80 = 0.40 -> residential
        assert ring_for_position(pos, center, radius) == "residential"


# ---------------------------------------------------------------------------
# Prop tier tests
# ---------------------------------------------------------------------------

class TestPropTierForPressure:
    """Test prop_tier_for_pressure returns correct band names and spacings."""

    def test_prop_tier_pristine(self):
        """Pressure 0.1 -> pristine, spacing 3-5m."""
        g = _import_grammar()
        band, spacing_min, spacing_max = g["prop_tier_for_pressure"](0.1)
        assert band == "pristine"
        assert spacing_min == pytest.approx(3.0)
        assert spacing_max == pytest.approx(5.0)

    def test_prop_tier_weathered(self):
        """Pressure 0.3 -> weathered, spacing 5-8m."""
        g = _import_grammar()
        band, spacing_min, spacing_max = g["prop_tier_for_pressure"](0.3)
        assert band == "weathered"
        assert spacing_min == pytest.approx(5.0)
        assert spacing_max == pytest.approx(8.0)

    def test_prop_tier_damaged(self):
        """Pressure 0.6 -> damaged, spacing 8-15m."""
        g = _import_grammar()
        band, spacing_min, spacing_max = g["prop_tier_for_pressure"](0.6)
        assert band == "damaged"
        assert spacing_min == pytest.approx(8.0)
        assert spacing_max == pytest.approx(15.0)

    def test_prop_tier_corrupted(self):
        """Pressure 0.9 -> corrupted, spacing 15-50m."""
        g = _import_grammar()
        band, spacing_min, spacing_max = g["prop_tier_for_pressure"](0.9)
        assert band == "corrupted"
        assert spacing_min == pytest.approx(15.0)
        assert spacing_max == pytest.approx(50.0)

    def test_prop_tier_exact_boundary(self):
        """Pressure exactly at 0.2 boundary: 0.2 is NOT < 0.2, so weathered."""
        g = _import_grammar()
        band, _, _ = g["prop_tier_for_pressure"](0.2)
        assert band == "weathered"


# ---------------------------------------------------------------------------
# Weighted building type tests
# ---------------------------------------------------------------------------

class TestWeightedBuildingType:
    """Test weighted_building_type returns valid types."""

    def test_returns_valid_type_for_district(self):
        """Building type must be in the district's type list (or neighbor's at boundary)."""
        g = _import_grammar()
        weighted_building_type = g["weighted_building_type"]
        DISTRICT_BUILDING_TYPES = g["DISTRICT_BUILDING_TYPES"]

        for district in DISTRICT_BUILDING_TYPES:
            neighbor = "civic_ring" if district == "residential" else "residential"
            result = weighted_building_type(district, neighbor, 0.5, seed=42)
            valid_types = DISTRICT_BUILDING_TYPES[district] + DISTRICT_BUILDING_TYPES.get(neighbor, [])
            assert result in valid_types, (
                f"Got invalid building type '{result}' for district '{district}'"
            )

    def test_boundary_blending_uses_neighbor_types(self):
        """At dist_to_boundary < 0.05, neighbor types should appear ~30% of the time."""
        g = _import_grammar()
        weighted_building_type = g["weighted_building_type"]
        DISTRICT_BUILDING_TYPES = g["DISTRICT_BUILDING_TYPES"]

        district = "residential"
        neighbor = "civic_ring"
        neighbor_types = DISTRICT_BUILDING_TYPES[neighbor]

        neighbor_count = 0
        trials = 200
        for i in range(trials):
            result = weighted_building_type(district, neighbor, 0.02, seed=i * 17)
            if result in neighbor_types:
                neighbor_count += 1

        # Expect roughly 30% neighbor types -- allow range 10-60% to be robust
        ratio = neighbor_count / trials
        assert 0.10 <= ratio <= 0.60, (
            f"Boundary blending ratio {ratio:.2f} outside expected range [0.10, 0.60]"
        )


# ---------------------------------------------------------------------------
# OBB lot subdivision tests
# ---------------------------------------------------------------------------

class TestOBBLotSubdivision:
    """Test subdivide_block_to_lots produces correct lot structures."""

    def _make_square(self, size: float) -> list[tuple[float, float]]:
        """Return a square polygon of given side length, centered at origin."""
        h = size / 2.0
        return [(-h, -h), (h, -h), (h, h), (-h, h)]

    def test_obb_lot_subdivision_basic(self):
        """A 20x20m square with residential district (min_area=25m²) should produce >= 2 lots."""
        g = _import_grammar()
        subdivide_block_to_lots = g["subdivide_block_to_lots"]

        square = self._make_square(20.0)  # area = 400m²; min_lot_area=25, 2*25=50 < 400 -> splits
        lots = subdivide_block_to_lots(square, "residential", seed=42)
        assert len(lots) >= 2, f"Expected >= 2 lots, got {len(lots)}"

    def test_obb_lot_subdivision_respects_min_area(self):
        """An 8x8m square (area=64m²) with residential (min=25, need 50 to split) -> >= 1 lots.
        Area 64 >= 50, may split. But with a 5x5 square (25m²) < 2*25=50, stays as 1."""
        g = _import_grammar()
        subdivide_block_to_lots = g["subdivide_block_to_lots"]

        # 5x5 = 25m² < 2*25 = 50 -> base case, returns 1 lot
        small_square = self._make_square(5.0)
        lots = subdivide_block_to_lots(small_square, "residential", seed=42)
        assert len(lots) == 1, f"Expected 1 lot for sub-minimum area polygon, got {len(lots)}"

    def test_each_lot_has_street_frontage_edge(self):
        """Every returned lot must have a street_frontage_edge field."""
        g = _import_grammar()
        subdivide_block_to_lots = g["subdivide_block_to_lots"]

        square = self._make_square(30.0)
        lots = subdivide_block_to_lots(square, "residential", seed=123)
        for i, lot in enumerate(lots):
            assert "street_frontage_edge" in lot, f"Lot {i} missing 'street_frontage_edge'"
            edge = lot["street_frontage_edge"]
            assert len(edge) == 2, f"Lot {i} frontage edge must have 2 vertices"

    def test_each_lot_has_area(self):
        """Each lot must have an 'area' field that is positive."""
        g = _import_grammar()
        subdivide_block_to_lots = g["subdivide_block_to_lots"]

        square = self._make_square(40.0)
        lots = subdivide_block_to_lots(square, "civic_ring", seed=7)
        for i, lot in enumerate(lots):
            assert "area" in lot, f"Lot {i} missing 'area'"
            assert lot["area"] > 0.0, f"Lot {i} has non-positive area: {lot['area']}"

    def test_each_lot_has_district(self):
        """Each lot must have a 'district' field matching the input district."""
        g = _import_grammar()
        subdivide_block_to_lots = g["subdivide_block_to_lots"]

        square = self._make_square(30.0)
        lots = subdivide_block_to_lots(square, "industrial", seed=99)
        for lot in lots:
            assert lot.get("district") == "industrial"


# ---------------------------------------------------------------------------
# Building assignment tests
# ---------------------------------------------------------------------------

class TestAssignBuildingsToLots:
    """Test assign_buildings_to_lots respects fill rates and district types."""

    def _make_residential_lots(self, count: int = 20) -> list[dict]:
        """Create simple lots in the residential ring (50% of radius from center)."""
        lots = []
        for i in range(count):
            x = 50.0 + i * 0.5  # All at ~50% radius
            lots.append({
                "polygon": [(x - 5, -5), (x + 5, -5), (x + 5, 5), (x - 5, 5)],
                "street_frontage_edge": ((x - 5, -5), (x + 5, -5)),
                "district": "residential",
                "area": 100.0,
            })
        return lots

    def test_assign_buildings_respects_fill_rate(self):
        """~80% of residential lots should have a building_type (not None)."""
        g = _import_grammar()
        assign_buildings_to_lots = g["assign_buildings_to_lots"]

        # Use 100 trials across different seeds to get stable statistics
        filled = 0
        total = 0
        center = (0.0, 0.0)
        radius = 100.0

        for seed_offset in range(10):
            lots = self._make_residential_lots(count=20)
            assigned = assign_buildings_to_lots(lots, center, radius, veil_pressure=0.1, seed=seed_offset * 17)
            for lot in assigned:
                total += 1
                if lot.get("building_type") is not None:
                    filled += 1

        fill_ratio = filled / total
        # DISTRICT_FILL_RATES["residential"] = 0.80, allow generous tolerance
        assert 0.60 <= fill_ratio <= 0.98, (
            f"Residential fill rate {fill_ratio:.2f} outside expected range [0.60, 0.98]"
        )

    def test_assign_buildings_lot_has_frontage(self):
        """Every assigned lot must have orientation_edge set."""
        g = _import_grammar()
        assign_buildings_to_lots = g["assign_buildings_to_lots"]

        lots = self._make_residential_lots(count=5)
        assigned = assign_buildings_to_lots(lots, (0.0, 0.0), 100.0, veil_pressure=0.2, seed=42)
        for i, lot in enumerate(assigned):
            assert "orientation_edge" in lot, f"Lot {i} missing 'orientation_edge'"

    def test_assign_buildings_returns_district(self):
        """Each assigned lot must have a district field."""
        g = _import_grammar()
        assign_buildings_to_lots = g["assign_buildings_to_lots"]

        lots = self._make_residential_lots(count=3)
        assigned = assign_buildings_to_lots(lots, (0.0, 0.0), 100.0, veil_pressure=0.0, seed=1)
        for lot in assigned:
            assert "district" in lot
            assert isinstance(lot["district"], str)


# ---------------------------------------------------------------------------
# Prop manifest tests
# ---------------------------------------------------------------------------

class TestGeneratePropManifest:
    """Test generate_prop_manifest returns correct structure and respects corruption tiers."""

    def _make_simple_segments(self, style: str = "main_road") -> list[dict]:
        """Return a simple two-point road segment."""
        return [
            {
                "points": [(0.0, 0.0), (20.0, 0.0)],
                "width": 4.0 if style == "main_road" else 2.0,
                "style": style,
                "seed": 42,
            }
        ]

    def test_prop_manifest_corruption_tiers_spacing(self):
        """Pristine pressure (0.1) produces more props than corrupted (0.9) for same segment."""
        g = _import_grammar()
        generate_prop_manifest = g["generate_prop_manifest"]

        segments = self._make_simple_segments()
        center = (0.0, 0.0)
        radius = 200.0

        props_pristine = generate_prop_manifest(segments, center, radius, veil_pressure=0.1, seed=42)
        props_corrupted = generate_prop_manifest(segments, center, radius, veil_pressure=0.9, seed=42)

        assert len(props_pristine) >= len(props_corrupted), (
            f"Pristine ({len(props_pristine)}) should have >= props than corrupted ({len(props_corrupted)})"
        )

    def test_prop_manifest_returns_cache_keys(self):
        """All prop items must have cache_key as a (str, str) tuple."""
        g = _import_grammar()
        generate_prop_manifest = g["generate_prop_manifest"]

        segments = self._make_simple_segments()
        props = generate_prop_manifest(segments, (0.0, 0.0), 200.0, veil_pressure=0.1, seed=42)

        for i, prop in enumerate(props):
            assert "cache_key" in prop, f"Prop {i} missing 'cache_key'"
            key = prop["cache_key"]
            assert isinstance(key, tuple) and len(key) == 2, (
                f"Prop {i} cache_key must be a 2-tuple, got {key!r}"
            )
            assert isinstance(key[0], str), f"Prop {i} cache_key[0] must be str"
            assert isinstance(key[1], str), f"Prop {i} cache_key[1] must be str"

    def test_prop_manifest_has_required_fields(self):
        """Each prop must have prop_type, position, rotation_z, corruption_band, cache_key."""
        g = _import_grammar()
        generate_prop_manifest = g["generate_prop_manifest"]

        segments = self._make_simple_segments()
        props = generate_prop_manifest(segments, (0.0, 0.0), 200.0, veil_pressure=0.3, seed=7)

        required = {"prop_type", "position", "rotation_z", "corruption_band", "cache_key"}
        for i, prop in enumerate(props):
            missing = required - set(prop.keys())
            assert not missing, f"Prop {i} missing fields: {missing}"

    def test_prop_manifest_empty_segments(self):
        """Empty road segment list produces empty prop manifest."""
        g = _import_grammar()
        generate_prop_manifest = g["generate_prop_manifest"]
        props = generate_prop_manifest([], (0.0, 0.0), 100.0, veil_pressure=0.1, seed=42)
        assert props == []


# ---------------------------------------------------------------------------
# Road network organic tests
# ---------------------------------------------------------------------------

class TestGenerateRoadNetworkOrganic:
    """Test generate_road_network_organic produces valid segment structures."""

    def test_road_network_returns_segments(self):
        """With 5 settlement points, should return at least 4 segments (MST edges)."""
        g = _import_grammar()
        generate_road_network_organic = g["generate_road_network_organic"]

        settlement_points = [
            (0.0, 0.0), (30.0, 10.0), (-20.0, 40.0), (10.0, -30.0), (50.0, 50.0)
        ]
        segments = generate_road_network_organic(
            center=(0.0, 0.0), radius=100.0, seed=42, settlement_points=settlement_points
        )
        # MST of 5 points = 4 edges minimum
        assert len(segments) >= 4, f"Expected >= 4 segments, got {len(segments)}"

    def test_road_network_segment_styles(self):
        """All segments must have style as 'main_road' or 'alley'."""
        g = _import_grammar()
        generate_road_network_organic = g["generate_road_network_organic"]

        settlement_points = [(0.0, 0.0), (30.0, 0.0), (60.0, 0.0), (-30.0, 0.0), (0.0, 30.0)]
        segments = generate_road_network_organic(
            center=(0.0, 0.0), radius=100.0, seed=7, settlement_points=settlement_points
        )
        valid_styles = {"main_road", "alley"}
        for i, seg in enumerate(segments):
            assert "style" in seg, f"Segment {i} missing 'style'"
            assert seg["style"] in valid_styles, (
                f"Segment {i} has invalid style '{seg['style']}'"
            )

    def test_road_network_segment_widths(self):
        """main_road segments must be 4.0m wide, alleys 2.0m wide."""
        g = _import_grammar()
        generate_road_network_organic = g["generate_road_network_organic"]

        settlement_points = [(0.0, 0.0), (30.0, 0.0), (60.0, 0.0), (-30.0, 0.0), (0.0, 30.0)]
        segments = generate_road_network_organic(
            center=(0.0, 0.0), radius=100.0, seed=99, settlement_points=settlement_points
        )
        for i, seg in enumerate(segments):
            if seg["style"] == "main_road":
                assert seg["width"] == pytest.approx(4.0), (
                    f"main_road segment {i} has wrong width {seg['width']}"
                )
            elif seg["style"] == "alley":
                assert seg["width"] == pytest.approx(2.0), (
                    f"alley segment {i} has wrong width {seg['width']}"
                )

    def test_road_network_too_few_points(self):
        """With fewer than 2 settlement points, returns empty list."""
        g = _import_grammar()
        generate_road_network_organic = g["generate_road_network_organic"]

        assert generate_road_network_organic((0.0, 0.0), 100.0, 42, []) == []
        assert generate_road_network_organic((0.0, 0.0), 100.0, 42, [(0.0, 0.0)]) == []

    def test_road_network_points_are_tuples(self):
        """Each segment must have 'points' as a list of 2-tuples."""
        g = _import_grammar()
        generate_road_network_organic = g["generate_road_network_organic"]

        pts = [(0.0, 0.0), (20.0, 10.0), (40.0, -5.0)]
        segments = generate_road_network_organic(
            center=(0.0, 0.0), radius=100.0, seed=1, settlement_points=pts
        )
        for i, seg in enumerate(segments):
            assert "points" in seg, f"Segment {i} missing 'points'"
            assert len(seg["points"]) >= 2, f"Segment {i} has < 2 points"
            for j, pt in enumerate(seg["points"]):
                assert len(pt) == 2, (
                    f"Segment {i} point {j} is not a 2-tuple: {pt!r}"
                )


# ---------------------------------------------------------------------------
# Curb geometry tests (road_network.py)
# ---------------------------------------------------------------------------

class TestRoadCurbGeometry:
    """Test _road_segment_mesh_spec_with_curbs in road_network.py."""

    def _import_curb_fn(self):
        from blender_addon.handlers.road_network import _road_segment_mesh_spec_with_curbs
        return _road_segment_mesh_spec_with_curbs

    def test_road_curb_geometry_vertex_count(self):
        """A 4m road with 2-point segment (1 step) -> 2 rows * 6 cols = 12 vertices minimum."""
        fn = self._import_curb_fn()
        start = (0.0, 0.0, 0.0)
        end = (10.0, 0.0, 0.0)
        spec = fn(start, end, width=4.0)
        verts = spec["vertices"]
        assert len(verts) >= 12, (
            f"Expected >= 12 vertices for 2-point segment, got {len(verts)}"
        )

    def test_road_curb_geometry_z_offset(self):
        """Curb-top vertices (col 1 and col 4) must have Z = curb_height."""
        fn = self._import_curb_fn()
        curb_h = 0.15
        start = (0.0, 0.0, 0.0)
        end = (10.0, 0.0, 0.0)
        spec = fn(start, end, width=4.0, curb_height=curb_h)
        verts = spec["vertices"]

        # Find vertices with Z approximately equal to curb_height
        curb_verts = [v for v in verts if abs(v[2] - curb_h) < 1e-4]
        road_verts = [v for v in verts if abs(v[2]) < 1e-4]

        assert len(curb_verts) > 0, "No curb vertices found at Z = curb_height"
        assert len(road_verts) > 0, "No road surface vertices found at Z = 0"

    def test_road_curb_geometry_has_uv_layers(self):
        """Spec must include uv_layers with 'road_surface' and 'curb' keys."""
        fn = self._import_curb_fn()
        start = (0.0, 0.0, 0.0)
        end = (5.0, 0.0, 0.0)
        spec = fn(start, end, width=4.0)
        assert "uv_layers" in spec, "Missing 'uv_layers' in mesh spec"
        assert "road_surface" in spec["uv_layers"], "Missing 'road_surface' UV layer"
        assert "curb" in spec["uv_layers"], "Missing 'curb' UV layer"

    def test_road_curb_geometry_has_faces(self):
        """Spec must have at least one face."""
        fn = self._import_curb_fn()
        start = (0.0, 0.0, 0.0)
        end = (10.0, 0.0, 0.0)
        spec = fn(start, end, width=4.0)
        assert len(spec.get("faces", [])) > 0, "No faces in curb mesh spec"
