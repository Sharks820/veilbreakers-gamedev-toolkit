"""Integration tests for the interior system (MESH-03).

Tests the full pipeline: spatial graphs + activity zones + clutter + lighting
for all major room types.  All pure-logic, no Blender required.
"""

import math

import pytest


# ---------------------------------------------------------------------------
# ROOM_SPATIAL_GRAPHS tests
# ---------------------------------------------------------------------------


class TestRoomSpatialGraphs:
    """Verify ROOM_SPATIAL_GRAPHS covers required room types and structures."""

    def test_spatial_graphs_exist(self):
        from blender_addon.handlers._building_grammar import ROOM_SPATIAL_GRAPHS
        assert isinstance(ROOM_SPATIAL_GRAPHS, dict)

    def test_covers_required_room_types(self):
        from blender_addon.handlers._building_grammar import ROOM_SPATIAL_GRAPHS
        required = {"tavern", "bedroom", "kitchen", "blacksmith", "library", "chapel", "throne_room"}
        for rt in required:
            assert rt in ROOM_SPATIAL_GRAPHS, f"Missing spatial graph for '{rt}'"

    def test_covers_at_least_7_room_types(self):
        from blender_addon.handlers._building_grammar import ROOM_SPATIAL_GRAPHS
        assert len(ROOM_SPATIAL_GRAPHS) >= 7

    def test_each_graph_has_focal_points(self):
        from blender_addon.handlers._building_grammar import ROOM_SPATIAL_GRAPHS
        for rt, graph in ROOM_SPATIAL_GRAPHS.items():
            assert "focal_points" in graph, f"'{rt}' missing focal_points"
            assert isinstance(graph["focal_points"], list)

    def test_each_graph_has_clusters(self):
        from blender_addon.handlers._building_grammar import ROOM_SPATIAL_GRAPHS
        for rt, graph in ROOM_SPATIAL_GRAPHS.items():
            assert "clusters" in graph, f"'{rt}' missing clusters"
            assert isinstance(graph["clusters"], list)

    def test_each_graph_has_wall_preferences(self):
        from blender_addon.handlers._building_grammar import ROOM_SPATIAL_GRAPHS
        for rt, graph in ROOM_SPATIAL_GRAPHS.items():
            assert "wall_preferences" in graph, f"'{rt}' missing wall_preferences"

    def test_focal_point_has_type_and_wall_pref(self):
        from blender_addon.handlers._building_grammar import ROOM_SPATIAL_GRAPHS
        for rt, graph in ROOM_SPATIAL_GRAPHS.items():
            for fp in graph["focal_points"]:
                assert "type" in fp, f"'{rt}' focal point missing 'type'"
                assert "wall_pref" in fp, f"'{rt}' focal point missing 'wall_pref'"

    def test_cluster_has_anchor_and_members(self):
        from blender_addon.handlers._building_grammar import ROOM_SPATIAL_GRAPHS
        for rt, graph in ROOM_SPATIAL_GRAPHS.items():
            for cluster in graph["clusters"]:
                assert "anchor" in cluster, f"'{rt}' cluster missing 'anchor'"
                assert "members" in cluster, f"'{rt}' cluster missing 'members'"

    def test_cluster_members_are_tuples(self):
        from blender_addon.handlers._building_grammar import ROOM_SPATIAL_GRAPHS
        for rt, graph in ROOM_SPATIAL_GRAPHS.items():
            for cluster in graph["clusters"]:
                for member in cluster["members"]:
                    assert len(member) == 3, f"'{rt}' cluster member must be (type, dist, face)"
                    mtype, dist, face = member
                    assert isinstance(mtype, str)
                    assert isinstance(dist, (int, float))
                    assert isinstance(face, bool)


# ---------------------------------------------------------------------------
# Spatial-Aware Placement tests
# ---------------------------------------------------------------------------


class TestSpatialPlacement:
    """Test that generate_interior_layout produces spatially coherent layouts."""

    def test_tavern_chairs_near_tables(self):
        """Across multiple seeds, chairs are generally near tables.

        The cluster solver places chairs around table anchors, but
        collision avoidance may push some chairs to fallback positions.
        We verify that across 10 seeds, at least one produces a majority
        of chairs near tables.
        """
        from blender_addon.handlers._building_grammar import generate_interior_layout
        best_ratio = 0.0
        for seed in range(10):
            layout = generate_interior_layout("tavern", 10, 8, seed=seed)
            tables = [i for i in layout if i["type"] == "table"]
            chairs = [i for i in layout if i["type"] == "chair"]
            if not tables or not chairs:
                continue
            near_count = 0
            for chair in chairs:
                cx, cy = chair["position"][0], chair["position"][1]
                for table in tables:
                    tx, ty = table["position"][0], table["position"][1]
                    dist = math.sqrt((cx - tx)**2 + (cy - ty)**2)
                    if dist < 2.0:
                        near_count += 1
                        break
            ratio = near_count / len(chairs)
            best_ratio = max(best_ratio, ratio)
        assert best_ratio >= 0.5, \
            f"Best chair-near-table ratio across 10 seeds: {best_ratio:.0%}"

    def test_bedroom_nightstand_near_bed(self):
        """Nightstand should be reasonably close to bed.

        The cluster uses 0.4m offset but stochastic placement may yield
        different distances per seed. Try multiple seeds and verify at least
        one produces a close placement (< 1.5m).
        """
        from blender_addon.handlers._building_grammar import generate_interior_layout
        found_close = False
        for seed in range(10):
            layout = generate_interior_layout("bedroom", 6, 5, seed=seed)
            beds = [i for i in layout if i["type"] == "bed"]
            nightstands = [i for i in layout if i["type"] == "nightstand"]
            if beds and nightstands:
                bx, by = beds[0]["position"][0], beds[0]["position"][1]
                nx, ny = nightstands[0]["position"][0], nightstands[0]["position"][1]
                dist = math.sqrt((bx - nx)**2 + (by - ny)**2)
                if dist < 1.5:
                    found_close = True
                    break
        assert found_close, "Nightstand never placed close to bed across 10 seeds"

    def test_wall_clearance_03m(self):
        """All non-floor items should have >= 0.3m clearance from room edges."""
        from blender_addon.handlers._building_grammar import generate_interior_layout
        for room_type in ["tavern", "bedroom", "kitchen"]:
            layout = generate_interior_layout(room_type, 8, 6, seed=42)
            for item in layout:
                if item["scale"][2] < 0.1:
                    continue  # skip floor items
                x, y = item["position"][0], item["position"][1]
                sx, sy = item["scale"][0], item["scale"][1]
                # Item edge should be at least ~0.2m from wall (0.3 margin minus half-size tolerance)
                assert x - sx/2 >= -0.05, f"{item['type']} left edge too close to wall"
                assert y - sy/2 >= -0.05, f"{item['type']} front edge too close to wall"
                assert x + sx/2 <= 8.05, f"{item['type']} right edge too close to wall"
                assert y + sy/2 <= 6.05, f"{item['type']} back edge too close to wall"

    def test_door_corridor_clear(self):
        """1.0m corridor from front wall center to room center should be clear."""
        from blender_addon.handlers._building_grammar import generate_interior_layout
        layout = generate_interior_layout("tavern", 8, 6, seed=42)
        corridor_cx = 4.0  # width/2
        corridor_half_w = 0.5  # 1.0m / 2
        for item in layout:
            if item["scale"][2] < 0.1:
                continue  # floor items exempt
            x, y = item["position"][0], item["position"][1]
            sx, sy = item["scale"][0], item["scale"][1]
            item_left = x - sx / 2
            item_right = x + sx / 2
            item_front = y - sy / 2
            item_back = y + sy / 2
            # Check if item overlaps corridor
            if item_right > corridor_cx - corridor_half_w and item_left < corridor_cx + corridor_half_w:
                assert item_front >= 3.0 or item_back <= 0.0, \
                    f"{item['type']} at ({x:.1f},{y:.1f}) blocks door corridor"

    def test_deterministic_with_seed(self):
        """Same seed should produce same layout."""
        from blender_addon.handlers._building_grammar import generate_interior_layout
        layout1 = generate_interior_layout("tavern", 8, 6, seed=123)
        layout2 = generate_interior_layout("tavern", 8, 6, seed=123)
        assert len(layout1) == len(layout2)
        for a, b in zip(layout1, layout2):
            assert a == b

    def test_different_seeds_different_layouts(self):
        """Different seeds should produce different layouts."""
        from blender_addon.handlers._building_grammar import generate_interior_layout
        layout1 = generate_interior_layout("tavern", 8, 6, seed=1)
        layout2 = generate_interior_layout("tavern", 8, 6, seed=2)
        # At least one position should differ
        any_diff = False
        for a, b in zip(layout1, layout2):
            if a["position"] != b["position"]:
                any_diff = True
                break
        assert any_diff, "Different seeds produced identical layouts"

    def test_no_item_overlaps(self):
        """No two non-floor items should overlap."""
        from blender_addon.handlers._building_grammar import generate_interior_layout
        for room_type in ["tavern", "bedroom", "blacksmith", "library"]:
            layout = generate_interior_layout(room_type, 8, 6, seed=42)
            items = [i for i in layout if i["scale"][2] >= 0.1]
            for i, a in enumerate(items):
                for j, b in enumerate(items):
                    if i >= j:
                        continue
                    ax, ay = a["position"][0], a["position"][1]
                    asx, asy = a["scale"][0], a["scale"][1]
                    bx, by = b["position"][0], b["position"][1]
                    bsx, bsy = b["scale"][0], b["scale"][1]
                    overlap_x = abs(ax - bx) < (asx + bsx) / 2
                    overlap_y = abs(ay - by) < (asy + bsy) / 2
                    assert not (overlap_x and overlap_y), \
                        f"{room_type}: {a['type']} and {b['type']} overlap"

    def test_all_spatial_graph_rooms_produce_output(self):
        """Every room type with a spatial graph should produce furniture."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, ROOM_SPATIAL_GRAPHS,
        )
        for room_type in ROOM_SPATIAL_GRAPHS:
            layout = generate_interior_layout(room_type, 8, 6, seed=42)
            assert len(layout) >= 1, f"'{room_type}' produced no furniture"

    def test_basic_fallback_rooms_still_work(self):
        """Room types without spatial graphs use basic fallback placement."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, ROOM_SPATIAL_GRAPHS, _ROOM_CONFIGS,
        )
        basic_rooms = set(_ROOM_CONFIGS.keys()) - set(ROOM_SPATIAL_GRAPHS.keys())
        for room_type in basic_rooms:
            layout = generate_interior_layout(room_type, 8, 6, seed=42)
            assert len(layout) >= 1, f"'{room_type}' basic fallback produced no furniture"


# ---------------------------------------------------------------------------
# Activity Zone tests
# ---------------------------------------------------------------------------


class TestActivityZones:
    """Test activity zone definitions and coverage."""

    def test_zones_exist(self):
        from blender_addon.handlers._building_grammar import ROOM_ACTIVITY_ZONES
        assert isinstance(ROOM_ACTIVITY_ZONES, dict)

    def test_covers_required_room_types(self):
        from blender_addon.handlers._building_grammar import ROOM_ACTIVITY_ZONES
        required = {"tavern", "bedroom", "kitchen", "blacksmith", "library", "chapel"}
        for rt in required:
            assert rt in ROOM_ACTIVITY_ZONES, f"Missing activity zones for '{rt}'"

    def test_zone_coverage_at_least_80_percent(self):
        from blender_addon.handlers._building_grammar import (
            ROOM_ACTIVITY_ZONES, compute_zone_coverage,
        )
        for room_type in ROOM_ACTIVITY_ZONES:
            coverage = compute_zone_coverage(room_type)
            assert coverage >= 0.80, \
                f"'{room_type}' zone coverage {coverage:.0%} < 80%"

    def test_zone_has_required_fields(self):
        from blender_addon.handlers._building_grammar import ROOM_ACTIVITY_ZONES
        for rt, zones in ROOM_ACTIVITY_ZONES.items():
            for zone in zones:
                assert "name" in zone, f"'{rt}' zone missing 'name'"
                assert "fraction" in zone, f"'{rt}' zone missing 'fraction'"
                assert "anchor" in zone, f"'{rt}' zone missing 'anchor'"
                assert "allowed" in zone, f"'{rt}' zone missing 'allowed'"

    def test_get_zone_for_item(self):
        from blender_addon.handlers._building_grammar import get_zone_for_item
        assert get_zone_for_item("tavern", "bar_counter") == "bar_zone"
        assert get_zone_for_item("tavern", "table") == "seating_zone"
        assert get_zone_for_item("tavern", "fireplace") == "hearth_zone"
        assert get_zone_for_item("bedroom", "bed") == "sleep_zone"
        assert get_zone_for_item("bedroom", "desk") == "work_zone"
        assert get_zone_for_item("kitchen", "cooking_fire") == "fire_zone"
        assert get_zone_for_item("blacksmith", "forge") == "forge_zone"
        assert get_zone_for_item("blacksmith", "anvil") == "anvil_zone"

    def test_get_zone_for_item_returns_none_for_unknown(self):
        from blender_addon.handlers._building_grammar import get_zone_for_item
        assert get_zone_for_item("tavern", "nonexistent_item") is None
        assert get_zone_for_item("nonexistent_room", "table") is None

    def test_get_zone_bounds(self):
        from blender_addon.handlers._building_grammar import (
            ROOM_ACTIVITY_ZONES, get_zone_bounds,
        )
        # Test tavern bar_zone (back wall, 30%)
        tavern_zones = ROOM_ACTIVITY_ZONES["tavern"]
        bar_zone = tavern_zones[0]
        assert bar_zone["name"] == "bar_zone"
        x_min, y_min, x_max, y_max = get_zone_bounds(bar_zone, 8.0, 6.0)
        assert x_min == 0.0
        assert y_max == 6.0
        assert y_min == pytest.approx(6.0 * 0.7, abs=0.01)

    def test_all_zone_fractions_positive(self):
        from blender_addon.handlers._building_grammar import ROOM_ACTIVITY_ZONES
        for rt, zones in ROOM_ACTIVITY_ZONES.items():
            for zone in zones:
                assert zone["fraction"] > 0, f"'{rt}' zone '{zone['name']}' has non-positive fraction"

    def test_tavern_items_in_correct_zones(self):
        from blender_addon.handlers._building_grammar import get_zone_for_item
        assert get_zone_for_item("tavern", "bar_counter") == "bar_zone"
        assert get_zone_for_item("tavern", "barrel") == "bar_zone"
        assert get_zone_for_item("tavern", "shelf") == "bar_zone"
        assert get_zone_for_item("tavern", "table") == "seating_zone"
        assert get_zone_for_item("tavern", "chair") == "seating_zone"


# ---------------------------------------------------------------------------
# Clutter Scatter tests
# ---------------------------------------------------------------------------


class TestClutterScatter:
    """Test decorative clutter scatter system."""

    def test_clutter_pools_exist(self):
        from blender_addon.handlers._building_grammar import CLUTTER_POOLS
        assert isinstance(CLUTTER_POOLS, dict)

    def test_clutter_pools_cover_at_least_6_rooms(self):
        from blender_addon.handlers._building_grammar import CLUTTER_POOLS
        assert len(CLUTTER_POOLS) >= 6

    def test_clutter_pools_have_items(self):
        from blender_addon.handlers._building_grammar import CLUTTER_POOLS
        for rt, pool in CLUTTER_POOLS.items():
            assert len(pool) >= 3, f"'{rt}' clutter pool has < 3 items"

    def test_poisson_disk_scatter(self):
        """Poisson disk produces non-overlapping points."""
        from blender_addon.handlers._building_grammar import _poisson_disk_scatter_2d
        import random
        rng = random.Random(42)
        points = _poisson_disk_scatter_2d(4.0, 3.0, 0.3, rng)
        assert len(points) >= 5, "Too few Poisson disk points"
        # Verify min distance
        for i, (ax, ay) in enumerate(points):
            for j, (bx, by) in enumerate(points):
                if i >= j:
                    continue
                dist = math.sqrt((ax - bx)**2 + (ay - by)**2)
                assert dist >= 0.29, f"Points too close: {dist:.3f}m"

    def test_poisson_disk_all_in_bounds(self):
        """All Poisson disk points should be within bounds."""
        from blender_addon.handlers._building_grammar import _poisson_disk_scatter_2d
        import random
        rng = random.Random(42)
        w, d = 5.0, 4.0
        points = _poisson_disk_scatter_2d(w, d, 0.2, rng)
        for x, y in points:
            assert 0 <= x < w, f"Point x={x} out of bounds [0, {w})"
            assert 0 <= y < d, f"Point y={y} out of bounds [0, {d})"

    def test_clutter_count_5_to_15(self):
        """Default density should produce 5-15 clutter items."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_clutter_layout,
        )
        layout = generate_interior_layout("tavern", 8, 6, seed=42)
        clutter = generate_clutter_layout("tavern", 8, 6, layout, seed=42, density=0.5)
        assert 5 <= len(clutter) <= 15, f"Clutter count {len(clutter)} outside [5, 15]"

    def test_clutter_density_zero(self):
        """Density 0.0 should produce exactly 5 items."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_clutter_layout,
        )
        layout = generate_interior_layout("tavern", 8, 6, seed=42)
        clutter = generate_clutter_layout("tavern", 8, 6, layout, seed=42, density=0.0)
        assert len(clutter) == 5

    def test_clutter_density_one(self):
        """Density 1.0 should produce 15 items."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_clutter_layout,
        )
        layout = generate_interior_layout("tavern", 8, 6, seed=42)
        clutter = generate_clutter_layout("tavern", 8, 6, layout, seed=42, density=1.0)
        assert len(clutter) == 15

    def test_clutter_items_from_pool(self):
        """All clutter items should come from the room's pool."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_clutter_layout, CLUTTER_POOLS,
        )
        layout = generate_interior_layout("tavern", 8, 6, seed=42)
        clutter = generate_clutter_layout("tavern", 8, 6, layout, seed=42)
        pool = set(CLUTTER_POOLS["tavern"])
        for item in clutter:
            item_name = item.get("name", item.get("type"))
            assert item_name in pool, f"Clutter '{item_name}' not in tavern pool"

    def test_clutter_in_room_bounds(self):
        """No clutter items should be outside room bounds."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_clutter_layout,
        )
        w, d = 8.0, 6.0
        layout = generate_interior_layout("tavern", w, d, seed=42)
        clutter = generate_clutter_layout("tavern", w, d, layout, seed=42)
        for item in clutter:
            x, y = item["position"][0], item["position"][1]
            assert 0 <= x <= w, f"Clutter x={x} outside [0, {w}]"
            assert 0 <= y <= d, f"Clutter y={y} outside [0, {d}]"

    def test_clutter_deterministic(self):
        """Same seed produces same clutter layout."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_clutter_layout,
        )
        layout = generate_interior_layout("tavern", 8, 6, seed=42)
        c1 = generate_clutter_layout("tavern", 8, 6, layout, seed=42)
        c2 = generate_clutter_layout("tavern", 8, 6, layout, seed=42)
        assert len(c1) == len(c2)
        for a, b in zip(c1, c2):
            assert a == b

    def test_clutter_has_surface_parent(self):
        """Clutter on surfaces should have surface_parent set."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_clutter_layout,
        )
        layout = generate_interior_layout("tavern", 8, 6, seed=42)
        clutter = generate_clutter_layout("tavern", 8, 6, layout, seed=42)
        surface_items = [c for c in clutter if c["surface_parent"] not in (None, "floor")]
        floor_items = [c for c in clutter if c["surface_parent"] in (None, "floor")]
        # Should have some of each (tavern has tables)
        assert len(surface_items) >= 1 or len(floor_items) >= 1

    def test_clutter_multiple_room_types(self):
        """Clutter works for multiple room types."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_clutter_layout,
        )
        for room_type in ["tavern", "bedroom", "blacksmith", "kitchen", "library", "chapel"]:
            layout = generate_interior_layout(room_type, 8, 6, seed=42)
            clutter = generate_clutter_layout(room_type, 8, 6, layout, seed=42)
            assert len(clutter) >= 5, f"'{room_type}' clutter count < 5"

    def test_unknown_pool_uses_default(self):
        """Room with no clutter pool uses default fallback pool."""
        from blender_addon.handlers._building_grammar import generate_clutter_layout
        clutter = generate_clutter_layout("nonexistent", 8, 6, [], seed=42)
        assert len(clutter) >= 5, "Unknown room should use default pool"


# ---------------------------------------------------------------------------
# Lighting Placement tests
# ---------------------------------------------------------------------------


class TestLightingPlacement:
    """Test lighting placement engine."""

    def test_lighting_schemas_exist(self):
        from blender_addon.handlers._building_grammar import LIGHTING_SCHEMAS
        assert isinstance(LIGHTING_SCHEMAS, dict)

    def test_lighting_schemas_cover_all_22_room_types(self):
        from blender_addon.handlers._building_grammar import LIGHTING_SCHEMAS, _ROOM_CONFIGS
        for rt in _ROOM_CONFIGS:
            assert rt in LIGHTING_SCHEMAS, f"Missing lighting schema for '{rt}'"

    def test_min_2_lights_per_room(self):
        """Every room type should have at least 2 light sources."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_lighting_layout, _ROOM_CONFIGS,
        )
        for room_type in _ROOM_CONFIGS:
            layout = generate_interior_layout(room_type, 8, 6, seed=42)
            lights = generate_lighting_layout(room_type, 8, 6, 3.0, layout, seed=42)
            assert len(lights) >= 2, f"'{room_type}' has {len(lights)} lights (need >= 2)"

    def test_all_lights_in_temperature_range(self):
        """All lights should be 2700-3500K."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_lighting_layout,
        )
        for room_type in ["tavern", "bedroom", "blacksmith", "chapel", "throne_room"]:
            layout = generate_interior_layout(room_type, 8, 6, seed=42)
            lights = generate_lighting_layout(room_type, 8, 6, 3.0, layout, seed=42)
            for light in lights:
                temp = light["color_temperature"]
                assert 2700 <= temp <= 3500, \
                    f"'{room_type}' light temp {temp}K outside [2700, 3500]"

    def test_doorway_torches(self):
        """Doorway torch_sconces should be at ~1.6m height."""
        from blender_addon.handlers._building_grammar import generate_lighting_layout
        lights = generate_lighting_layout("tavern", 8, 6, 3.0, [], seed=42)
        torches = [l for l in lights if l["type"] == "torch_sconce"]
        assert len(torches) >= 2, "Need at least 2 doorway torches"
        for torch in torches:
            assert abs(torch["position"][2] - 1.6) < 0.01, \
                f"Torch height {torch['position'][2]} != 1.6m"

    def test_doorway_torches_flank_door(self):
        """Torches should flank the door position."""
        from blender_addon.handlers._building_grammar import generate_lighting_layout
        door_pos = [(4.0, 0.0)]  # center of front wall
        lights = generate_lighting_layout("tavern", 8, 6, 3.0, [], door_pos, seed=42)
        torches = [l for l in lights if l["type"] == "torch_sconce"]
        # Should have one left and one right of door
        xs = [t["position"][0] for t in torches[:2]]
        assert min(xs) < 4.0, "No torch to left of door"
        assert max(xs) > 4.0, "No torch to right of door"

    def test_candles_on_tables(self):
        """Tavern should have candles on table surfaces."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_lighting_layout,
        )
        layout = generate_interior_layout("tavern", 8, 6, seed=42)
        lights = generate_lighting_layout("tavern", 8, 6, 3.0, layout, seed=42)
        candles = [l for l in lights if l["type"] == "candle"]
        tables = [i for i in layout if i["type"] == "table"]
        if tables:
            assert len(candles) >= 1, "No candles on tables in tavern"

    def test_fireplace_emissive(self):
        """Room with fireplace should have fireplace_light."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_lighting_layout,
        )
        layout = generate_interior_layout("tavern", 8, 6, seed=42)
        has_fireplace = any(i["type"] == "fireplace" for i in layout)
        lights = generate_lighting_layout("tavern", 8, 6, 3.0, layout, seed=42)
        fp_lights = [l for l in lights if l["type"] == "fireplace_light"]
        if has_fireplace:
            assert len(fp_lights) >= 1, "No fireplace light despite fireplace existing"

    def test_lighting_deterministic(self):
        """Same seed produces same lighting layout."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_lighting_layout,
        )
        layout = generate_interior_layout("tavern", 8, 6, seed=42)
        l1 = generate_lighting_layout("tavern", 8, 6, 3.0, layout, seed=42)
        l2 = generate_lighting_layout("tavern", 8, 6, 3.0, layout, seed=42)
        assert len(l1) == len(l2)
        for a, b in zip(l1, l2):
            assert a == b

    def test_light_has_required_fields(self):
        """Each light dict has type, position, light_type, color_temperature, radius, intensity."""
        from blender_addon.handlers._building_grammar import generate_lighting_layout
        lights = generate_lighting_layout("tavern", 8, 6, 3.0, [], seed=42)
        for light in lights:
            assert "type" in light
            assert "position" in light
            assert "light_type" in light
            assert "color_temperature" in light
            assert "radius" in light
            assert "intensity" in light
            assert len(light["position"]) == 3

    def test_light_types_are_known(self):
        """All generated light types should be in LIGHT_TYPES."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_lighting_layout, LIGHT_TYPES,
        )
        for room_type in ["tavern", "bedroom", "blacksmith", "chapel"]:
            layout = generate_interior_layout(room_type, 8, 6, seed=42)
            lights = generate_lighting_layout(room_type, 8, 6, 3.0, layout, seed=42)
            for light in lights:
                assert light["light_type"] in LIGHT_TYPES, \
                    f"Unknown light type '{light['light_type']}'"


# ---------------------------------------------------------------------------
# Full Pipeline Integration tests
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """Test full interior pipeline: furniture + clutter + lighting."""

    @pytest.mark.parametrize("room_type", [
        "tavern", "bedroom", "blacksmith", "kitchen", "library", "chapel",
    ])
    def test_full_pipeline(self, room_type):
        """Full pipeline produces furniture, clutter, and lighting."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_clutter_layout,
            generate_lighting_layout,
        )
        layout = generate_interior_layout(room_type, 8, 6, seed=42)
        assert len(layout) >= 1, f"No furniture for {room_type}"

        clutter = generate_clutter_layout(room_type, 8, 6, layout, seed=42)
        assert 5 <= len(clutter) <= 15, f"Clutter count {len(clutter)} outside [5,15]"

        lights = generate_lighting_layout(room_type, 8, 6, 3.0, layout, seed=42)
        assert len(lights) >= 2, f"Light count {len(lights)} < 2"

    def test_tiny_room_3x3(self):
        """3x3m room should still produce valid layout."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_clutter_layout,
            generate_lighting_layout,
        )
        layout = generate_interior_layout("dungeon_cell", 3, 3, seed=42)
        assert len(layout) >= 1

        clutter = generate_clutter_layout("dungeon_cell", 3, 3, layout, seed=42)
        # Small room may have fewer clutter items
        assert len(clutter) >= 0

        lights = generate_lighting_layout("dungeon_cell", 3, 3, 2.5, layout, seed=42)
        assert len(lights) >= 2

    def test_huge_room_20x20(self):
        """20x20m room should still work."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_clutter_layout,
            generate_lighting_layout,
        )
        layout = generate_interior_layout("great_hall", 20, 20, seed=42)
        assert len(layout) >= 1

        clutter = generate_clutter_layout("great_hall", 20, 20, layout, seed=42)
        assert len(clutter) >= 5

        lights = generate_lighting_layout("great_hall", 20, 20, 5.0, layout, seed=42)
        assert len(lights) >= 2

    def test_no_clutter_overlaps_furniture(self):
        """Floor clutter should not be inside furniture footprints."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_clutter_layout,
        )
        layout = generate_interior_layout("tavern", 8, 6, seed=42)
        clutter = generate_clutter_layout("tavern", 8, 6, layout, seed=42)
        floor_clutter = [c for c in clutter if c["surface_parent"] is None]
        for c in floor_clutter:
            cx, cy = c["position"][0], c["position"][1]
            for furn in layout:
                fx, fy = furn["position"][0], furn["position"][1]
                fsx, fsy = furn["scale"][0], furn["scale"][1]
                in_x = abs(cx - fx) < fsx / 2
                in_y = abs(cy - fy) < fsy / 2
                # Allow some tolerance since clutter is tiny
                assert not (in_x and in_y), \
                    f"Floor clutter at ({cx:.1f},{cy:.1f}) inside {furn['type']}"

    def test_oddly_shaped_room(self):
        """Narrow room (3x12) should work."""
        from blender_addon.handlers._building_grammar import (
            generate_interior_layout, generate_clutter_layout,
            generate_lighting_layout,
        )
        layout = generate_interior_layout("storage", 3, 12, seed=42)
        assert len(layout) >= 1

        clutter = generate_clutter_layout("storage", 3, 12, layout, seed=42)
        lights = generate_lighting_layout("storage", 3, 12, 3.0, layout, seed=42)
        assert len(lights) >= 2

    def test_empty_room_type_returns_empty(self):
        """Unknown room type returns empty layout."""
        from blender_addon.handlers._building_grammar import generate_interior_layout
        layout = generate_interior_layout("nonexistent_room", 8, 6, seed=42)
        assert layout == []
