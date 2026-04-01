"""Tests for _settlement_grammar.py — pure-logic settlement generation.

Covers: PROP_PROMPTS, CORRUPTION_DESCS, get_prop_prompt(),
        prop_tier_for_pressure(), ring_for_position(),
        generate_road_network_organic(), generate_concentric_districts(),
        subdivide_block_to_lots(), generate_prop_manifest(),
        _road_segment_mesh_spec_with_curbs().

No bpy/bmesh required — pure logic.
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers._settlement_grammar import (
    CORRUPTION_DESCS,
    CORRUPTION_TIERS,
    DISTRICT_FILL_RATES,
    PROP_PROMPTS,
    RING_THRESHOLDS,
    _block_area,
    _perturb_road_segment,
    _road_segment_mesh_spec_with_curbs,
    generate_concentric_districts,
    generate_prop_manifest,
    generate_road_network_organic,
    get_prop_prompt,
    prop_tier_for_pressure,
    ring_for_position,
    subdivide_block_to_lots,
)


# ===========================================================================
# Task 1: PROP_PROMPTS, CORRUPTION_DESCS, get_prop_prompt
# ===========================================================================


class TestPropPrompts:
    """Tests for Tripo prompt templates."""

    ALL_PROP_TYPES = [
        "lantern_post",
        "market_stall",
        "well",
        "barrel_cluster",
        "cart",
        "bench",
        "trough",
        "notice_board",
    ]
    ALL_CORRUPTION_BANDS = ["pristine", "weathered", "damaged", "corrupted"]

    def test_prop_prompts_all_types_have_entries(self):
        """All 8 required prop types must be in PROP_PROMPTS."""
        for pt in self.ALL_PROP_TYPES:
            assert pt in PROP_PROMPTS, f"Missing prop type: {pt}"

    def test_prop_prompts_count(self):
        """Exactly 8 prop types defined."""
        assert len(PROP_PROMPTS) == 8

    def test_corruption_descs_all_bands(self):
        """All 4 corruption bands must have descriptions."""
        for band in self.ALL_CORRUPTION_BANDS:
            assert band in CORRUPTION_DESCS, f"Missing corruption band: {band}"

    def test_get_prop_prompt_formats_corruption(self):
        """get_prop_prompt for well/corrupted must mention void energy."""
        result = get_prop_prompt("well", "corrupted")
        assert "void energy" in result

    def test_get_prop_prompt_no_curly_braces_remaining(self):
        """After formatting, no {placeholder} curly braces should remain."""
        for pt in self.ALL_PROP_TYPES:
            for band in self.ALL_CORRUPTION_BANDS:
                result = get_prop_prompt(pt, band)
                assert "{" not in result, f"Unformatted placeholder in {pt}/{band}: {result!r}"
                assert "}" not in result, f"Unformatted placeholder in {pt}/{band}: {result!r}"

    def test_get_prop_prompt_contains_dark_fantasy(self):
        """All prompts must contain 'dark fantasy' for D-10 compliance."""
        for pt in self.ALL_PROP_TYPES:
            result = get_prop_prompt(pt, "pristine")
            assert "dark fantasy" in result.lower(), f"Missing 'dark fantasy' in prompt for {pt}"

    def test_get_prop_prompt_contains_pbr_ready(self):
        """All prompts must contain 'PBR-ready' for material consistency."""
        for pt in self.ALL_PROP_TYPES:
            result = get_prop_prompt(pt, "weathered")
            assert "PBR-ready" in result, f"Missing 'PBR-ready' in prompt for {pt}"

    def test_get_prop_prompt_pristine_no_corruption_text(self):
        """Pristine prompt should not mention void energy or corruption."""
        for pt in self.ALL_PROP_TYPES:
            result = get_prop_prompt(pt, "pristine")
            assert "void energy" not in result
            assert "eldritch" not in result

    def test_get_prop_prompt_corrupted_has_void_energy(self):
        """Corrupted band must reference void energy for visual differentiation."""
        for pt in self.ALL_PROP_TYPES:
            result = get_prop_prompt(pt, "corrupted")
            assert "void energy" in result or "eldritch" in result

    def test_get_prop_prompt_invalid_prop_type_raises(self):
        """Unknown prop type raises KeyError."""
        with pytest.raises(KeyError):
            get_prop_prompt("dragon_statue", "pristine")

    def test_get_prop_prompt_invalid_corruption_band_raises(self):
        """Unknown corruption band raises KeyError."""
        with pytest.raises(KeyError):
            get_prop_prompt("well", "destroyed")

    def test_prop_prompts_contain_white_background(self):
        """All prompts specify white background for clean Tripo AI extraction."""
        for pt in self.ALL_PROP_TYPES:
            raw_template = PROP_PROMPTS[pt]
            assert "white background" in raw_template, f"Missing 'white background' in {pt}"

    def test_prop_prompts_specify_single_object(self):
        """Each prompt specifies single-object isolation (no environment)."""
        for pt in self.ALL_PROP_TYPES:
            raw_template = PROP_PROMPTS[pt]
            assert "no environment" in raw_template, f"Missing 'no environment' in {pt}"

    def test_corruption_descs_weathered_mentions_worn(self):
        """Weathered description should mention worn/aged textures."""
        desc = CORRUPTION_DESCS["weathered"]
        assert "worn" in desc or "aged" in desc

    def test_corruption_descs_damaged_mentions_corruption(self):
        """Damaged description should mention corruption."""
        desc = CORRUPTION_DESCS["damaged"]
        assert "corruption" in desc or "corrupt" in desc


# ===========================================================================
# Task 1: Prop cache infrastructure (worldbuilding.py)
# ===========================================================================


class TestPropCacheInfrastructure:
    """Tests for _PROP_CACHE, _get_or_generate_prop, prefetch_town_props,
    and clear_prop_cache in worldbuilding.py.

    No Blender connection required — tests cache logic in isolation.
    """

    def setup_method(self):
        """Ensure clean cache state before each test."""
        from blender_addon.handlers import worldbuilding as wb
        wb.clear_prop_cache()

    def teardown_method(self):
        """Clean up after each test."""
        from blender_addon.handlers import worldbuilding as wb
        wb.clear_prop_cache()

    def test_clear_prop_cache_empties_dict(self):
        """clear_prop_cache() must empty _PROP_CACHE."""
        from blender_addon.handlers import worldbuilding as wb
        wb._PROP_CACHE[("lantern_post", "pristine")] = "/tmp/lantern.glb"
        assert len(wb._PROP_CACHE) == 1
        wb.clear_prop_cache()
        assert len(wb._PROP_CACHE) == 0

    def test_get_or_generate_prop_returns_none_without_connection(self):
        """Without a blender_connection, generation is skipped — returns None."""
        from blender_addon.handlers.worldbuilding import _get_or_generate_prop
        result = _get_or_generate_prop("well", "pristine", "some prompt", blender_connection=None)
        assert result is None

    def test_get_or_generate_prop_uses_cache(self):
        """Second call with same key returns cached value without calling connection."""
        from blender_addon.handlers import worldbuilding as wb
        wb._PROP_CACHE[("bench", "weathered")] = "/tmp/bench_weathered.glb"
        result = wb._get_or_generate_prop("bench", "weathered", "some prompt", blender_connection=None)
        # Cache hit should still return value even without connection
        assert result == "/tmp/bench_weathered.glb"

    def test_prefetch_town_props_returns_summary_dict(self):
        """prefetch_town_props returns dict keyed by (prop_type, corruption_band)."""
        from blender_addon.handlers.worldbuilding import prefetch_town_props
        manifest = [
            {"cache_key": ("well", "pristine"), "prop_type": "well"},
            {"cache_key": ("bench", "pristine"), "prop_type": "bench"},
        ]
        result = prefetch_town_props(manifest, veil_pressure=0.1, blender_connection=None)
        assert isinstance(result, dict)
        assert ("well", "pristine") in result
        assert ("bench", "pristine") in result

    def test_prefetch_town_props_deduplicates_keys(self):
        """prefetch_town_props only generates each (type, band) once."""
        from blender_addon.handlers.worldbuilding import prefetch_town_props
        manifest = [
            {"cache_key": ("well", "pristine")},
            {"cache_key": ("well", "pristine")},  # duplicate
            {"cache_key": ("well", "pristine")},  # duplicate
        ]
        result = prefetch_town_props(manifest, veil_pressure=0.1, blender_connection=None)
        # Only one unique key
        assert len(result) == 1

    def test_prefetch_town_props_uses_existing_cache(self):
        """prefetch_town_props returns cached paths without regenerating."""
        from blender_addon.handlers import worldbuilding as wb
        wb._PROP_CACHE[("cart", "corrupted")] = "/tmp/cart_corrupt.glb"
        manifest = [{"cache_key": ("cart", "corrupted")}]
        result = wb.prefetch_town_props(manifest, veil_pressure=0.85, blender_connection=None)
        assert result[("cart", "corrupted")] == "/tmp/cart_corrupt.glb"

    def test_prefetch_town_props_handles_invalid_cache_key(self):
        """prefetch_town_props handles unknown prop types gracefully."""
        from blender_addon.handlers.worldbuilding import prefetch_town_props
        manifest = [{"cache_key": ("unknown_prop_xyz", "pristine")}]
        # Should not raise — returns None for unknown types
        result = prefetch_town_props(manifest, veil_pressure=0.1, blender_connection=None)
        assert result[("unknown_prop_xyz", "pristine")] is None


# ===========================================================================
# District ring assignment (D-03)
# ===========================================================================


class TestRingDistrictAssignment:
    """Tests for ring_for_position() concentric ring model."""

    CENTER = (0.0, 0.0)
    RADIUS = 100.0

    def test_center_is_market_square(self):
        """Position at center (r=0) must be market_square."""
        assert ring_for_position((0.0, 0.0), self.CENTER, self.RADIUS) == "market_square"

    def test_market_square_boundary(self):
        """Position at 14% radius is market_square."""
        pos = (self.RADIUS * 0.14, 0.0)
        assert ring_for_position(pos, self.CENTER, self.RADIUS) == "market_square"

    def test_civic_ring_boundary(self):
        """Position at 25% radius is civic_ring."""
        pos = (self.RADIUS * 0.25, 0.0)
        assert ring_for_position(pos, self.CENTER, self.RADIUS) == "civic_ring"

    def test_residential_zone(self):
        """Position at 50% radius is residential."""
        pos = (self.RADIUS * 0.50, 0.0)
        assert ring_for_position(pos, self.CENTER, self.RADIUS) == "residential"

    def test_industrial_zone(self):
        """Position at 70% radius is industrial."""
        pos = (self.RADIUS * 0.70, 0.0)
        assert ring_for_position(pos, self.CENTER, self.RADIUS) == "industrial"

    def test_outskirts_zone(self):
        """Position at 90% radius is outskirts."""
        pos = (self.RADIUS * 0.90, 0.0)
        assert ring_for_position(pos, self.CENTER, self.RADIUS) == "outskirts"

    def test_beyond_radius_is_outskirts(self):
        """Position beyond settlement radius is outskirts."""
        pos = (self.RADIUS * 1.5, 0.0)
        assert ring_for_position(pos, self.CENTER, self.RADIUS) == "outskirts"

    def test_ring_thresholds_are_ordered(self):
        """RING_THRESHOLDS must be in ascending threshold order."""
        thresholds = [t for _, t in RING_THRESHOLDS]
        assert thresholds == sorted(thresholds)

    def test_ring_thresholds_cover_full_range(self):
        """Last threshold must be >= 1.0 to cover all positions."""
        last_threshold = RING_THRESHOLDS[-1][1]
        assert last_threshold >= 1.0

    def test_ring_for_3d_position(self):
        """ring_for_position works with 3D tuples (ignores Z)."""
        pos_3d = (self.RADIUS * 0.25, 0.0, 5.0)
        assert ring_for_position(pos_3d, self.CENTER, self.RADIUS) == "civic_ring"

    def test_non_origin_center(self):
        """ring_for_position works with non-origin center."""
        center = (100.0, 200.0)
        # Position at center should be market_square
        assert ring_for_position((100.0, 200.0), center, self.RADIUS) == "market_square"
        # Position 90% radius from center = outskirts
        pos = (100.0 + self.RADIUS * 0.9, 200.0)
        assert ring_for_position(pos, center, self.RADIUS) == "outskirts"


# ===========================================================================
# Corruption tier lookup (D-08)
# ===========================================================================


class TestPropCorruptionTiers:
    """Tests for prop_tier_for_pressure() corruption-scaled density."""

    def test_low_pressure_pristine(self):
        """Pressure 0.1 -> pristine band, tight spacing (3-5m)."""
        band, sp_min, sp_max = prop_tier_for_pressure(0.1)
        assert band == "pristine"
        assert sp_min <= 3.0
        assert sp_max <= 6.0

    def test_medium_pressure_weathered(self):
        """Pressure 0.35 -> weathered band."""
        band, _, _ = prop_tier_for_pressure(0.35)
        assert band == "weathered"

    def test_high_pressure_damaged(self):
        """Pressure 0.65 -> damaged band."""
        band, _, _ = prop_tier_for_pressure(0.65)
        assert band == "damaged"

    def test_extreme_pressure_corrupted(self):
        """Pressure 0.9 -> corrupted band, wide spacing (15-50m)."""
        band, sp_min, sp_max = prop_tier_for_pressure(0.9)
        assert band == "corrupted"
        assert sp_min >= 15.0

    def test_pressure_boundary_zero(self):
        """Pressure 0.0 -> pristine."""
        band, _, _ = prop_tier_for_pressure(0.0)
        assert band == "pristine"

    def test_pressure_boundary_one(self):
        """Pressure 1.0 -> corrupted."""
        band, _, _ = prop_tier_for_pressure(1.0)
        assert band == "corrupted"

    def test_spacing_min_less_than_max(self):
        """spacing_min < spacing_max for all tiers."""
        for pressure in [0.1, 0.35, 0.65, 0.9]:
            band, sp_min, sp_max = prop_tier_for_pressure(pressure)
            assert sp_min < sp_max, f"Invalid spacing for pressure={pressure}: {sp_min} >= {sp_max}"

    def test_higher_pressure_means_wider_spacing(self):
        """Higher Veil pressure produces larger spacing (props are sparser)."""
        _, low_min, _ = prop_tier_for_pressure(0.1)
        _, high_min, _ = prop_tier_for_pressure(0.9)
        assert high_min > low_min

    def test_corruption_tiers_count(self):
        """Exactly 4 corruption tiers defined (D-08 spec)."""
        assert len(CORRUPTION_TIERS) == 4


# ===========================================================================
# Organic road network (D-01)
# ===========================================================================


class TestRoadNetworkOrganic:
    """Tests for generate_road_network_organic() L-system road generation."""

    def test_returns_list_of_segments(self):
        """Output is a list of dicts."""
        segments = generate_road_network_organic((0.0, 0.0), 100.0, seed=42)
        assert isinstance(segments, list)
        assert len(segments) > 0

    def test_segment_keys(self):
        """Each segment has required keys."""
        segments = generate_road_network_organic((0.0, 0.0), 100.0, seed=42)
        required_keys = {"start", "end", "width", "style", "points"}
        for seg in segments:
            assert required_keys.issubset(seg.keys()), f"Missing keys in segment: {seg.keys()}"

    def test_main_roads_are_4m_wide(self):
        """Main road segments must be 4.0m wide (D-02)."""
        segments = generate_road_network_organic((0.0, 0.0), 100.0, seed=42)
        main_roads = [s for s in segments if s["style"] == "main_road"]
        assert len(main_roads) > 0
        for seg in main_roads:
            assert seg["width"] == 4.0, f"Main road width is {seg['width']}, expected 4.0"

    def test_alleys_are_2m_wide(self):
        """Alley segments must be 2.0m wide (D-02)."""
        segments = generate_road_network_organic((0.0, 0.0), 100.0, seed=42)
        alleys = [s for s in segments if s["style"] == "alley"]
        assert len(alleys) > 0
        for seg in alleys:
            assert seg["width"] == 2.0, f"Alley width is {seg['width']}, expected 2.0"

    def test_has_multiple_road_styles(self):
        """Generated network has at least 2 distinct road styles."""
        segments = generate_road_network_organic((0.0, 0.0), 100.0, seed=42)
        styles = {s["style"] for s in segments}
        assert len(styles) >= 2

    def test_produces_more_than_5_segments(self):
        """Town road network has > 5 segments."""
        segments = generate_road_network_organic((0.0, 0.0), 100.0, seed=42)
        assert len(segments) > 5

    def test_deterministic_with_same_seed(self):
        """Same seed produces identical road network."""
        s1 = generate_road_network_organic((0.0, 0.0), 100.0, seed=99)
        s2 = generate_road_network_organic((0.0, 0.0), 100.0, seed=99)
        assert len(s1) == len(s2)
        for a, b in zip(s1, s2):
            assert a["start"] == b["start"]
            assert a["end"] == b["end"]

    def test_different_seeds_produce_different_layouts(self):
        """Different seeds produce different road networks."""
        s1 = generate_road_network_organic((0.0, 0.0), 100.0, seed=1)
        s2 = generate_road_network_organic((0.0, 0.0), 100.0, seed=2)
        starts_1 = [seg["start"] for seg in s1]
        starts_2 = [seg["start"] for seg in s2]
        assert starts_1 != starts_2

    def test_points_are_3_tuples(self):
        """All points in segment must be 3-tuples."""
        segments = generate_road_network_organic((0.0, 0.0), 100.0, seed=42)
        for seg in segments:
            for pt in seg["points"]:
                assert len(pt) == 3, f"Point is not 3D: {pt}"

    def test_road_perturb_inserts_midpoints(self):
        """_perturb_road_segment returns more than 2 points."""
        import random
        rng = random.Random(42)
        start = (0.0, 0.0, 0.0)
        end = (100.0, 0.0, 0.0)
        points = _perturb_road_segment(start, end, rng, amplitude=5.0, steps=3)
        assert len(points) > 2
        assert points[0] == start
        assert points[-1] == end


# ===========================================================================
# Concentric district generation (D-03)
# ===========================================================================


class TestConcentricDistricts:
    """Tests for generate_concentric_districts()."""

    def test_returns_required_keys(self):
        """Output has center, radius, rings, thresholds."""
        result = generate_concentric_districts((0.0, 0.0), 100.0, seed=42)
        assert "center" in result
        assert "radius" in result
        assert "rings" in result
        assert "thresholds" in result

    def test_five_rings(self):
        """Exactly 5 concentric rings defined."""
        result = generate_concentric_districts((0.0, 0.0), 100.0, seed=42)
        assert len(result["rings"]) == 5

    def test_ring_names(self):
        """Ring names match the spec."""
        expected = {"market_square", "civic_ring", "residential", "industrial", "outskirts"}
        result = generate_concentric_districts((0.0, 0.0), 100.0, seed=42)
        actual = {r["name"] for r in result["rings"]}
        assert actual == expected

    def test_rings_have_fill_rate(self):
        """Every ring has a fill_rate field."""
        result = generate_concentric_districts((0.0, 0.0), 100.0, seed=42)
        for ring in result["rings"]:
            assert "fill_rate" in ring
            assert 0.0 <= ring["fill_rate"] <= 1.0

    def test_market_square_fill_rate_is_100(self):
        """Market square fill rate must be 1.0 (100%) per D-06."""
        result = generate_concentric_districts((0.0, 0.0), 100.0, seed=42)
        market = next(r for r in result["rings"] if r["name"] == "market_square")
        assert market["fill_rate"] == 1.0

    def test_residential_fill_rate_is_80(self):
        """Residential fill rate must be 0.8 (80%) per D-06."""
        result = generate_concentric_districts((0.0, 0.0), 100.0, seed=42)
        residential = next(r for r in result["rings"] if r["name"] == "residential")
        assert residential["fill_rate"] == 0.80

    def test_outskirts_fill_rate_is_60(self):
        """Outskirts fill rate must be 0.6 (60%) per D-06."""
        result = generate_concentric_districts((0.0, 0.0), 100.0, seed=42)
        outskirts = next(r for r in result["rings"] if r["name"] == "outskirts")
        assert outskirts["fill_rate"] == 0.60

    def test_rings_are_concentric(self):
        """Each ring's inner_r equals the previous ring's outer_r."""
        result = generate_concentric_districts((0.0, 0.0), 100.0, seed=42)
        rings = result["rings"]
        prev_outer = 0.0
        for ring in rings:
            assert abs(ring["inner_r"] - prev_outer) < 1e-6, (
                f"Ring {ring['name']} inner_r={ring['inner_r']} != prev outer={prev_outer}"
            )
            prev_outer = ring["outer_r"]

    def test_outermost_ring_reaches_settlement_radius(self):
        """Outermost ring outer_r matches the settlement radius."""
        radius = 150.0
        result = generate_concentric_districts((0.0, 0.0), radius, seed=42)
        last_ring = result["rings"][-1]
        assert abs(last_ring["outer_r"] - radius) < 0.1


# ===========================================================================
# OBB lot subdivision (D-05)
# ===========================================================================


class TestOBBLotSubdivision:
    """Tests for subdivide_block_to_lots()."""

    SQUARE_BLOCK = [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)]

    def test_returns_list_of_lots(self):
        """Output is a list of lot dicts."""
        lots = subdivide_block_to_lots(self.SQUARE_BLOCK, "residential", seed=42)
        assert isinstance(lots, list)
        assert len(lots) > 0

    def test_lot_keys(self):
        """Each lot has polygon, district, area, street_frontage_edge."""
        lots = subdivide_block_to_lots(self.SQUARE_BLOCK, "residential", seed=42)
        required_keys = {"polygon", "district", "area", "street_frontage_edge"}
        for lot in lots:
            assert required_keys.issubset(lot.keys())

    def test_small_block_not_subdivided(self):
        """Block smaller than 2x min_lot_area returns as single lot."""
        tiny = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]  # 16m2
        lots = subdivide_block_to_lots(tiny, "residential", seed=42, min_lot_area=25.0)
        assert len(lots) == 1

    def test_large_block_subdivided(self):
        """400m2 block should be subdivided into multiple lots."""
        lots = subdivide_block_to_lots(self.SQUARE_BLOCK, "residential", seed=42)
        assert len(lots) > 1

    def test_lot_district_matches_input(self):
        """Each lot inherits the input district name."""
        lots = subdivide_block_to_lots(self.SQUARE_BLOCK, "market_square", seed=42)
        for lot in lots:
            assert lot["district"] == "market_square"

    def test_lot_area_positive(self):
        """Each lot has positive area."""
        lots = subdivide_block_to_lots(self.SQUARE_BLOCK, "residential", seed=42)
        for lot in lots:
            assert lot["area"] > 0.0

    def test_block_area_formula(self):
        """_block_area returns correct area for a unit square."""
        unit_square = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        assert abs(_block_area(unit_square) - 1.0) < 1e-6

    def test_block_area_rectangle(self):
        """_block_area returns correct area for a rectangle."""
        rect = [(0.0, 0.0), (5.0, 0.0), (5.0, 3.0), (0.0, 3.0)]
        assert abs(_block_area(rect) - 15.0) < 1e-6

    def test_deterministic_subdivision(self):
        """Same seed produces identical subdivision."""
        lots1 = subdivide_block_to_lots(self.SQUARE_BLOCK, "residential", seed=7)
        lots2 = subdivide_block_to_lots(self.SQUARE_BLOCK, "residential", seed=7)
        assert len(lots1) == len(lots2)

    def test_street_frontage_edge_is_valid_index(self):
        """street_frontage_edge is a valid polygon edge index."""
        lots = subdivide_block_to_lots(self.SQUARE_BLOCK, "residential", seed=42)
        for lot in lots:
            n_verts = len(lot["polygon"])
            edge = lot["street_frontage_edge"]
            assert 0 <= edge < n_verts


# ===========================================================================
# Prop manifest generation (D-07, D-08)
# ===========================================================================


class TestPropManifestGeneration:
    """Tests for generate_prop_manifest()."""

    SEGMENTS = [
        {
            "start": (0.0, 0.0, 0.0),
            "end": (50.0, 0.0, 0.0),
            "points": [(0.0, 0.0, 0.0), (25.0, 1.0, 0.0), (50.0, 0.0, 0.0)],
            "width": 4.0,
            "style": "main_road",
        },
        {
            "start": (0.0, 0.0, 0.0),
            "end": (0.0, 50.0, 0.0),
            "points": [(0.0, 0.0, 0.0), (1.0, 25.0, 0.0), (0.0, 50.0, 0.0)],
            "width": 4.0,
            "style": "main_road",
        },
    ]

    def test_returns_list(self):
        """Output is a list."""
        result = generate_prop_manifest(self.SEGMENTS, 0.1, seed=42)
        assert isinstance(result, list)

    def test_prop_spec_keys(self):
        """Each prop spec has required keys."""
        result = generate_prop_manifest(self.SEGMENTS, 0.1, seed=42)
        if result:
            required = {"prop_type", "position", "rotation_z", "corruption_band", "cache_key"}
            for spec in result:
                assert required.issubset(spec.keys()), f"Missing keys: {spec.keys()}"

    def test_manifest_position_format(self):
        """All positions are 3-tuples of floats."""
        result = generate_prop_manifest(self.SEGMENTS, 0.1, seed=42)
        for spec in result:
            pos = spec["position"]
            assert len(pos) == 3, f"Position not 3D: {pos}"
            for coord in pos:
                assert isinstance(coord, float), f"Non-float coordinate: {coord}"

    def test_manifest_cache_keys_are_tuples(self):
        """All cache_key values are (str, str) tuples."""
        result = generate_prop_manifest(self.SEGMENTS, 0.1, seed=42)
        for spec in result:
            ck = spec["cache_key"]
            assert isinstance(ck, tuple), f"cache_key is not a tuple: {ck}"
            assert len(ck) == 2, f"cache_key is not a 2-tuple: {ck}"
            assert isinstance(ck[0], str), f"cache_key[0] is not str: {ck[0]}"
            assert isinstance(ck[1], str), f"cache_key[1] is not str: {ck[1]}"

    def test_low_pressure_has_more_props(self):
        """Low Veil pressure (0.1) produces more props than high pressure (0.9)."""
        low = generate_prop_manifest(self.SEGMENTS, 0.1, seed=42)
        high = generate_prop_manifest(self.SEGMENTS, 0.9, seed=42)
        assert len(low) >= len(high), (
            f"Expected low pressure ({len(low)}) >= high pressure ({len(high)}) props"
        )

    def test_high_pressure_corrupted_band(self):
        """High pressure props have 'corrupted' or 'damaged' corruption band."""
        result = generate_prop_manifest(self.SEGMENTS, 0.9, seed=42)
        for spec in result:
            assert spec["corruption_band"] in ("corrupted", "damaged"), (
                f"Expected corrupted/damaged band for high pressure, got: {spec['corruption_band']}"
            )

    def test_low_pressure_pristine_band(self):
        """Low pressure props have 'pristine' corruption band."""
        result = generate_prop_manifest(self.SEGMENTS, 0.1, seed=42)
        for spec in result:
            assert spec["corruption_band"] == "pristine", (
                f"Expected pristine for low pressure, got: {spec['corruption_band']}"
            )

    def test_trails_produce_no_props(self):
        """Trail segments produce no props (only main roads and alleys)."""
        trail_segments = [
            {
                "start": (0.0, 0.0, 0.0),
                "end": (50.0, 0.0, 0.0),
                "points": [(0.0, 0.0, 0.0), (50.0, 0.0, 0.0)],
                "width": 1.5,
                "style": "trail",
            }
        ]
        result = generate_prop_manifest(trail_segments, 0.1, seed=42)
        assert len(result) == 0

    def test_deterministic_with_same_seed(self):
        """Same seed produces identical prop manifest."""
        m1 = generate_prop_manifest(self.SEGMENTS, 0.1, seed=77)
        m2 = generate_prop_manifest(self.SEGMENTS, 0.1, seed=77)
        assert len(m1) == len(m2)
        for a, b in zip(m1, m2):
            assert a["position"] == b["position"]
            assert a["prop_type"] == b["prop_type"]

    def test_prop_types_are_in_known_set(self):
        """All generated prop types are from PROP_PROMPTS."""
        result = generate_prop_manifest(self.SEGMENTS, 0.1, seed=42)
        known_types = set(PROP_PROMPTS.keys())
        for spec in result:
            assert spec["prop_type"] in known_types, (
                f"Unknown prop type: {spec['prop_type']}"
            )


# ===========================================================================
# Task 4: Road curb mesh spec (D-02)
# ===========================================================================


class TestRoadCurbGeometry:
    """Tests for _road_segment_mesh_spec_with_curbs()."""

    START: tuple = (0.0, 0.0, 0.0)
    END: tuple = (10.0, 0.0, 0.0)
    WIDTH = 4.0
    CURB_HEIGHT = 0.15
    GUTTER_WIDTH = 0.3

    def _get_spec(self, width=None, curb_height=None, gutter_width=None):
        return _road_segment_mesh_spec_with_curbs(
            self.START, self.END,
            width=width or self.WIDTH,
            curb_height=curb_height or self.CURB_HEIGHT,
            gutter_width=gutter_width or self.GUTTER_WIDTH,
        )

    def test_returns_required_keys(self):
        """Spec has vertices, faces, uv_groups, type, total_width, road_width, curb_height."""
        spec = self._get_spec()
        required = {"vertices", "faces", "uv_groups", "type", "total_width", "road_width", "curb_height"}
        assert required.issubset(spec.keys())

    def test_type_is_road_curb_strip(self):
        """type field is 'road_curb_strip'."""
        spec = self._get_spec()
        assert spec["type"] == "road_curb_strip"

    def test_total_width_is_road_plus_gutters(self):
        """total_width = road_width + 2 * gutter_width."""
        spec = self._get_spec(width=4.0, gutter_width=0.3)
        expected = 4.0 + 2 * 0.3
        assert abs(spec["total_width"] - expected) < 1e-6

    def test_has_vertices(self):
        """Generates a non-empty vertex list."""
        spec = self._get_spec()
        assert len(spec["vertices"]) > 0

    def test_has_faces(self):
        """Generates a non-empty face list."""
        spec = self._get_spec()
        assert len(spec["faces"]) > 0

    def test_curb_verts_have_z_offset(self):
        """Curb top vertices (cols 1 and 5) are raised by curb_height."""
        spec = _road_segment_mesh_spec_with_curbs(
            self.START, self.END,
            width=4.0, curb_height=0.15, gutter_width=0.3, resolution=1
        )
        verts = spec["vertices"]
        # With resolution=1: 2 cross-sections, 7 verts each = 14 verts
        # First cross-section cols 1 and 5 should have Z = curb_height
        assert len(verts) >= 7
        first_row = verts[:7]  # first cross-section
        col1_z = first_row[1][2]
        col5_z = first_row[5][2]
        assert abs(col1_z - 0.15) < 1e-6, f"Col 1 Z={col1_z}, expected 0.15"
        assert abs(col5_z - 0.15) < 1e-6, f"Col 5 Z={col5_z}, expected 0.15"

    def test_road_surface_verts_at_zero_z(self):
        """Road surface verts (cols 0, 2, 3, 4, 6) are at road level (Z=0)."""
        spec = _road_segment_mesh_spec_with_curbs(
            self.START, self.END,
            width=4.0, curb_height=0.15, gutter_width=0.3, resolution=1
        )
        verts = spec["vertices"]
        first_row = verts[:7]
        for col in [0, 2, 3, 4, 6]:
            z = first_row[col][2]
            assert abs(z - 0.0) < 1e-6, f"Col {col} Z={z}, expected 0.0"

    def test_uv_groups_has_road_surface_and_curb(self):
        """uv_groups has 'road_surface' and 'curb' keys."""
        spec = self._get_spec()
        assert "road_surface" in spec["uv_groups"]
        assert "curb" in spec["uv_groups"]

    def test_road_surface_faces_exist(self):
        """At least some faces are classified as road_surface."""
        spec = self._get_spec()
        assert len(spec["uv_groups"]["road_surface"]) > 0

    def test_curb_faces_exist(self):
        """At least some faces are classified as curb."""
        spec = self._get_spec()
        assert len(spec["uv_groups"]["curb"]) > 0

    def test_degenerate_segment_returns_empty(self):
        """Zero-length segment returns empty mesh spec."""
        spec = _road_segment_mesh_spec_with_curbs(
            (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), width=4.0
        )
        assert spec["vertices"] == []
        assert spec["faces"] == []

    def test_all_face_indices_in_bounds(self):
        """All vertex indices in faces are within bounds of vertex list."""
        spec = self._get_spec()
        n_verts = len(spec["vertices"])
        for face in spec["faces"]:
            for idx in face:
                assert 0 <= idx < n_verts, f"Face index {idx} out of bounds (n={n_verts})"

    def test_main_road_width_spec(self):
        """Main roads are 4m road surface (D-02)."""
        spec = _road_segment_mesh_spec_with_curbs(self.START, self.END, width=4.0)
        assert spec["road_width"] == 4.0

    def test_alley_width_spec(self):
        """Alleys are 2m road surface (D-02)."""
        spec = _road_segment_mesh_spec_with_curbs(self.START, self.END, width=2.0)
        assert spec["road_width"] == 2.0
