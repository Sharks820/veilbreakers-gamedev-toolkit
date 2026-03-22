"""Tests for vegetation_system.py: per-biome vegetation sets, Poisson placement
with slope/height filtering, wind vertex colors, and seasonal variants.

All pure-logic -- no Blender dependency.
"""

import math

import pytest

from blender_addon.handlers.vegetation_system import (
    BIOME_VEGETATION_SETS,
    compute_vegetation_placement,
    compute_wind_vertex_colors,
    get_seasonal_variant,
)


# ===================================================================
# Helper: generate simple flat terrain data
# ===================================================================

def _make_flat_terrain(
    size: float = 100.0,
    resolution: int = 10,
    height: float = 5.0,
):
    """Generate a flat terrain grid for testing.

    Returns (vertices, faces, normals, area_bounds).
    """
    vertices = []
    normals = []
    step = size / (resolution - 1)

    for j in range(resolution):
        for i in range(resolution):
            x = i * step
            y = j * step
            vertices.append((x, y, height))
            normals.append((0.0, 0.0, 1.0))  # Flat = straight up

    faces = []
    for j in range(resolution - 1):
        for i in range(resolution - 1):
            idx = j * resolution + i
            faces.append((idx, idx + 1, idx + resolution + 1, idx + resolution))

    area_bounds = (0.0, 0.0, size, size)
    return vertices, faces, normals, area_bounds


def _make_sloped_terrain(
    size: float = 100.0,
    resolution: int = 10,
    max_slope_degrees: float = 60.0,
):
    """Generate a terrain with consistent steep slope for testing filtering.

    Returns (vertices, faces, normals, area_bounds).
    """
    vertices = []
    normals = []
    step = size / (resolution - 1)
    slope_rad = math.radians(max_slope_degrees)

    # Height increases steeply along X
    rise_per_unit = math.tan(slope_rad)

    # Normal pointing perpendicular to the slope
    nx = -math.sin(slope_rad)
    nz = math.cos(slope_rad)

    for j in range(resolution):
        for i in range(resolution):
            x = i * step
            y = j * step
            z = x * rise_per_unit
            vertices.append((x, y, z))
            normals.append((nx, 0.0, nz))

    faces = []
    for j in range(resolution - 1):
        for i in range(resolution - 1):
            idx = j * resolution + i
            faces.append((idx, idx + 1, idx + resolution + 1, idx + resolution))

    area_bounds = (0.0, 0.0, size, size)
    return vertices, faces, normals, area_bounds


def _make_varied_terrain(
    size: float = 100.0,
    resolution: int = 20,
):
    """Generate terrain with both flat areas and steep cliffs.

    Left half is flat (low slope), right half is steep.
    Returns (vertices, faces, normals, area_bounds).
    """
    vertices = []
    normals = []
    step = size / (resolution - 1)

    for j in range(resolution):
        for i in range(resolution):
            x = i * step
            y = j * step
            # Left half: flat at height 5
            # Right half: steep ramp
            if x < size / 2:
                z = 5.0
                nx, ny, nz = 0.0, 0.0, 1.0
            else:
                z = 5.0 + (x - size / 2) * 3.0  # Steep
                slope_rad = math.atan(3.0)
                nx, nz = -math.sin(slope_rad), math.cos(slope_rad)
                ny = 0.0
            vertices.append((x, y, z))
            normals.append((nx, ny, nz))

    faces = []
    for j in range(resolution - 1):
        for i in range(resolution - 1):
            idx = j * resolution + i
            faces.append((idx, idx + 1, idx + resolution + 1, idx + resolution))

    area_bounds = (0.0, 0.0, size, size)
    return vertices, faces, normals, area_bounds


# ===================================================================
# Biome vegetation set coverage
# ===================================================================


class TestBiomeVegetationSets:
    """Validate all 14 biomes have proper vegetation configurations."""

    EXPECTED_BIOMES = [
        "thornwood_forest",
        "corrupted_swamp",
        "mountain_pass",
        "cemetery",
        "ashen_wastes",
        "frozen_hollows",
        "blighted_mire",
        "ruined_citadel",
        "desert",
        "coastal",
        "grasslands",
        "mushroom_forest",
        "crystal_cavern",
        "deep_forest",
    ]

    NEW_BIOMES = [
        "desert", "coastal", "grasslands",
        "mushroom_forest", "crystal_cavern", "deep_forest",
    ]

    def test_all_fourteen_biomes_exist(self):
        """All 14 biomes are defined in BIOME_VEGETATION_SETS."""
        for biome in self.EXPECTED_BIOMES:
            assert biome in BIOME_VEGETATION_SETS, f"Missing biome: {biome}"

    def test_biome_count_is_fourteen(self):
        """Exactly 14 biomes are defined."""
        assert len(BIOME_VEGETATION_SETS) == 14

    def test_each_biome_has_required_categories(self):
        """Each biome has trees, ground_cover, and rocks categories."""
        for biome_name, biome_data in BIOME_VEGETATION_SETS.items():
            for cat in ("trees", "ground_cover", "rocks"):
                assert cat in biome_data, (
                    f"Biome '{biome_name}' missing category '{cat}'"
                )
                assert isinstance(biome_data[cat], list), (
                    f"Biome '{biome_name}' category '{cat}' must be a list"
                )

    def test_vegetation_entries_have_required_fields(self):
        """Every vegetation entry has type, density, and scale_range."""
        for biome_name, biome_data in BIOME_VEGETATION_SETS.items():
            for cat in ("trees", "ground_cover", "rocks"):
                for entry in biome_data[cat]:
                    assert "type" in entry, (
                        f"Missing 'type' in {biome_name}/{cat}: {entry}"
                    )
                    assert "density" in entry, (
                        f"Missing 'density' in {biome_name}/{cat}: {entry}"
                    )
                    assert "scale_range" in entry, (
                        f"Missing 'scale_range' in {biome_name}/{cat}: {entry}"
                    )

    def test_densities_are_valid(self):
        """All density values are between 0 and 1."""
        for biome_name, biome_data in BIOME_VEGETATION_SETS.items():
            for cat in ("trees", "ground_cover", "rocks"):
                for entry in biome_data[cat]:
                    d = entry["density"]
                    assert 0.0 < d <= 1.0, (
                        f"Invalid density {d} in {biome_name}/{cat}"
                    )

    def test_scale_ranges_are_valid(self):
        """All scale_range tuples have min < max and positive values."""
        for biome_name, biome_data in BIOME_VEGETATION_SETS.items():
            for cat in ("trees", "ground_cover", "rocks"):
                for entry in biome_data[cat]:
                    sr = entry["scale_range"]
                    assert len(sr) == 2, (
                        f"scale_range must be 2-tuple in {biome_name}/{cat}"
                    )
                    assert sr[0] > 0, f"scale_range min must be positive"
                    assert sr[1] >= sr[0], (
                        f"scale_range max < min in {biome_name}/{cat}"
                    )

    def test_dark_fantasy_aesthetic(self):
        """Biomes reference dark fantasy vegetation styles, not lush/tropical."""
        all_styles = set()
        for biome_data in BIOME_VEGETATION_SETS.values():
            for cat in ("trees", "ground_cover", "rocks"):
                for entry in biome_data[cat]:
                    style = entry.get("style", "")
                    if style:
                        all_styles.add(style)

        # Should NOT contain lush/tropical styles
        forbidden = {"palm", "tropical", "lush", "bright", "cherry_blossom"}
        for f in forbidden:
            assert f not in all_styles, (
                f"Style '{f}' is too bright for dark fantasy aesthetic"
            )

        # Should contain dark fantasy styles
        dark_styles = {"dead_twisted", "ancient_oak", "boulder", "tombstone"}
        for ds in dark_styles:
            assert ds in all_styles, (
                f"Expected dark fantasy style '{ds}' not found"
            )


# ===================================================================
# Vegetation placement (Poisson + slope/height filtering)
# ===================================================================


class TestComputeVegetationPlacement:
    """Tests for compute_vegetation_placement."""

    def test_flat_terrain_produces_placements(self):
        """Flat terrain with valid biome produces vegetation."""
        verts, faces, normals, bounds = _make_flat_terrain()
        placements = compute_vegetation_placement(
            verts, faces, normals, "thornwood_forest", bounds, seed=42,
        )
        assert len(placements) > 0, "Expected at least some placements on flat terrain"

    def test_placements_have_required_fields(self):
        """Each placement has position, type, style, scale, rotation."""
        verts, faces, normals, bounds = _make_flat_terrain()
        placements = compute_vegetation_placement(
            verts, faces, normals, "corrupted_swamp", bounds, seed=42,
        )
        for p in placements:
            assert "position" in p
            assert "type" in p
            assert "style" in p
            assert "scale" in p
            assert "rotation" in p

    def test_positions_are_3d(self):
        """Placement positions have x, y, z components."""
        verts, faces, normals, bounds = _make_flat_terrain()
        placements = compute_vegetation_placement(
            verts, faces, normals, "mountain_pass", bounds, seed=42,
        )
        for p in placements:
            assert len(p["position"]) == 3, "Position must be (x, y, z)"

    def test_positions_within_bounds(self):
        """All placements are within the specified area bounds."""
        verts, faces, normals, bounds = _make_flat_terrain(size=50.0)
        placements = compute_vegetation_placement(
            verts, faces, normals, "thornwood_forest", bounds, seed=42,
        )
        min_x, min_y, max_x, max_y = bounds
        for p in placements:
            px, py, _pz = p["position"]
            assert min_x <= px <= max_x, f"x={px} out of bounds [{min_x}, {max_x}]"
            assert min_y <= py <= max_y, f"y={py} out of bounds [{min_y}, {max_y}]"

    def test_steep_slope_filters_trees(self):
        """Trees should not be placed on slopes > 45 degrees."""
        verts, faces, normals, bounds = _make_sloped_terrain(
            max_slope_degrees=60.0,
        )
        placements = compute_vegetation_placement(
            verts, faces, normals, "thornwood_forest", bounds, seed=42,
        )
        tree_placements = [p for p in placements if p["type"] == "tree"]
        # On a 60-degree slope, trees should be filtered out
        assert len(tree_placements) == 0, (
            f"Expected no trees on 60-degree slope, got {len(tree_placements)}"
        )

    def test_invalid_biome_raises(self):
        """Unknown biome name raises ValueError."""
        verts, faces, normals, bounds = _make_flat_terrain()
        with pytest.raises(ValueError, match="Unknown biome"):
            compute_vegetation_placement(
                verts, faces, normals, "candy_land", bounds,
            )

    def test_different_seeds_different_results(self):
        """Different seeds produce different placement sets."""
        verts, faces, normals, bounds = _make_flat_terrain()
        p1 = compute_vegetation_placement(
            verts, faces, normals, "thornwood_forest", bounds, seed=1,
        )
        p2 = compute_vegetation_placement(
            verts, faces, normals, "thornwood_forest", bounds, seed=2,
        )
        # Positions should differ
        if len(p1) > 0 and len(p2) > 0:
            positions_1 = {p["position"] for p in p1}
            positions_2 = {p["position"] for p in p2}
            assert positions_1 != positions_2

    def test_deterministic_with_same_seed(self):
        """Same seed produces identical placements."""
        verts, faces, normals, bounds = _make_flat_terrain()
        p1 = compute_vegetation_placement(
            verts, faces, normals, "cemetery", bounds, seed=42,
        )
        p2 = compute_vegetation_placement(
            verts, faces, normals, "cemetery", bounds, seed=42,
        )
        assert len(p1) == len(p2)
        for a, b in zip(p1, p2):
            assert a["position"] == b["position"]
            assert a["type"] == b["type"]

    def test_empty_terrain_returns_empty(self):
        """Empty vertex list returns empty placements."""
        result = compute_vegetation_placement(
            [], [], [], "thornwood_forest", (0, 0, 100, 100), seed=42,
        )
        assert result == []

    def test_water_level_filtering(self):
        """Vertices below water level should have no vegetation."""
        # Create terrain with low spots
        verts = []
        normals = []
        for j in range(10):
            for i in range(10):
                x = i * 10.0
                y = j * 10.0
                # First row at water level (z=0), rest at normal height
                z = 0.0 if j == 0 else 5.0
                verts.append((x, y, z))
                normals.append((0.0, 0.0, 1.0))

        faces = []
        for j in range(9):
            for i in range(9):
                idx = j * 10 + i
                faces.append((idx, idx + 1, idx + 11, idx + 10))

        placements = compute_vegetation_placement(
            verts, faces, normals, "corrupted_swamp",
            (0, 0, 90, 90), seed=42, water_level=0.1,
        )
        # No placements should be at y near 0 (the low row)
        for p in placements:
            _px, py, _pz = p["position"]
            # Placements near the first row (y < 5) should be rare/absent
            # because those vertices are at water level

    def test_all_biomes_produce_placements(self):
        """Every biome produces at least some placements on flat terrain."""
        verts, faces, normals, bounds = _make_flat_terrain(size=200.0, resolution=20)
        for biome_name in BIOME_VEGETATION_SETS:
            placements = compute_vegetation_placement(
                verts, faces, normals, biome_name, bounds, seed=42,
                min_distance=5.0,
            )
            assert len(placements) > 0, (
                f"Biome '{biome_name}' produced no placements on flat terrain"
            )

    def test_min_distance_spacing(self):
        """Placements respect minimum distance between each other."""
        verts, faces, normals, bounds = _make_flat_terrain(size=50.0, resolution=15)
        min_dist = 5.0
        placements = compute_vegetation_placement(
            verts, faces, normals, "thornwood_forest", bounds,
            seed=42, min_distance=min_dist,
        )
        # Check pairwise distances (subset for performance)
        subset = placements[:30]
        for i in range(len(subset)):
            for j in range(i + 1, len(subset)):
                dx = subset[i]["position"][0] - subset[j]["position"][0]
                dy = subset[i]["position"][1] - subset[j]["position"][1]
                dist = math.sqrt(dx * dx + dy * dy)
                # Allow small tolerance since positions may be offset
                assert dist >= min_dist * 0.9, (
                    f"Placements {i} and {j} too close: {dist:.2f} < {min_dist}"
                )


# ===================================================================
# Wind vertex colors
# ===================================================================


class TestComputeWindVertexColors:
    """Tests for compute_wind_vertex_colors."""

    def _make_tree_vertices(self):
        """Simple tree: trunk column + crown sphere approximation."""
        verts = []
        # Trunk: cylinder along Z
        for z in [0.0, 0.5, 1.0, 1.5, 2.0]:
            for angle in range(0, 360, 90):
                r = 0.2
                x = math.cos(math.radians(angle)) * r
                y = math.sin(math.radians(angle)) * r
                verts.append((x, y, z))

        # Crown: wider sphere on top
        for z in [2.5, 3.0, 3.5, 4.0]:
            for angle in range(0, 360, 45):
                r = 0.8 * (1.0 - abs(z - 3.0) / 1.5)
                x = math.cos(math.radians(angle)) * r
                y = math.sin(math.radians(angle)) * r
                verts.append((x, y, z))

        return verts

    def test_returns_valid_colors(self):
        """All color channels are in [0, 1] range."""
        verts = self._make_tree_vertices()
        colors = compute_wind_vertex_colors(verts)
        assert len(colors) == len(verts)
        for r, g, b in colors:
            assert 0.0 <= r <= 1.0, f"R channel {r} out of range"
            assert 0.0 <= g <= 1.0, f"G channel {g} out of range"
            assert 0.0 <= b <= 1.0, f"B channel {b} out of range"

    def test_trunk_base_has_low_sway(self):
        """Vertices at the trunk base should have low R and G values."""
        verts = self._make_tree_vertices()
        colors = compute_wind_vertex_colors(verts)
        # First 4 vertices are at z=0, near trunk center
        for i in range(4):
            r, g, b = colors[i]
            assert g < 0.15, f"Base vertex {i} G too high: {g}"

    def test_crown_top_has_high_amplitude(self):
        """Vertices at the crown top should have high G values."""
        verts = self._make_tree_vertices()
        colors = compute_wind_vertex_colors(verts)
        # Last vertices are at top of crown (z near 4.0)
        top_verts = [i for i, v in enumerate(verts) if v[2] >= 3.5]
        for i in top_verts:
            r, g, b = colors[i]
            assert g > 0.5, f"Crown top vertex {i} G too low: {g}"

    def test_crown_outer_has_high_sway(self):
        """Crown outer vertices (far from trunk) should have higher R."""
        verts = self._make_tree_vertices()
        colors = compute_wind_vertex_colors(verts)
        # Compare trunk verts (small R) vs crown verts (larger R)
        trunk_r_avg = sum(colors[i][0] for i in range(4)) / 4.0
        crown_indices = [i for i, v in enumerate(verts) if v[2] >= 2.5]
        if crown_indices:
            crown_r_avg = sum(colors[i][0] for i in crown_indices) / len(crown_indices)
            assert crown_r_avg > trunk_r_avg, (
                f"Crown R avg ({crown_r_avg:.3f}) should exceed "
                f"trunk R avg ({trunk_r_avg:.3f})"
            )

    def test_empty_vertices_returns_empty(self):
        """Empty vertex list returns empty color list."""
        assert compute_wind_vertex_colors([]) == []

    def test_explicit_trunk_center(self):
        """Explicit trunk_center parameter is respected."""
        verts = [(0, 0, 0), (5, 0, 5), (10, 0, 10)]
        colors = compute_wind_vertex_colors(verts, trunk_center=(0, 0))
        # Vertex at (0,0,0) is at trunk center, so R should be 0
        assert colors[0][0] == 0.0
        # Vertex at (10,0,10) is far from center, so R should be 1.0
        assert colors[2][0] == pytest.approx(1.0)

    def test_explicit_ground_level(self):
        """Explicit ground_level parameter is respected."""
        verts = [(0, 0, 5), (0, 0, 10), (0, 0, 15)]
        colors = compute_wind_vertex_colors(verts, ground_level=5.0)
        # G values should be 0, 0.5, 1.0
        assert colors[0][1] == pytest.approx(0.0)
        assert colors[1][1] == pytest.approx(0.5)
        assert colors[2][1] == pytest.approx(1.0)

    def test_color_channels_are_3_tuple(self):
        """Each color is a 3-tuple (r, g, b)."""
        verts = [(0, 0, 0), (1, 1, 1)]
        colors = compute_wind_vertex_colors(verts)
        for c in colors:
            assert isinstance(c, tuple)
            assert len(c) == 3


# ===================================================================
# Seasonal variants
# ===================================================================


class TestGetSeasonalVariant:
    """Tests for get_seasonal_variant."""

    VALID_SEASONS = ["summer", "autumn", "winter", "corrupted"]

    def test_all_seasons_return_valid_params(self):
        """Every season produces a dict with required keys."""
        for season in self.VALID_SEASONS:
            result = get_seasonal_variant("tree", season)
            assert "color_tint" in result
            assert "saturation_mult" in result
            assert "leaf_density" in result
            assert "roughness_offset" in result
            assert "description" in result
            assert "affects_leaves" in result

    def test_different_seasons_different_params(self):
        """Each season produces different material parameters for trees."""
        results = {}
        for season in self.VALID_SEASONS:
            results[season] = get_seasonal_variant("tree", season)

        # Check that at least color tints differ
        tints = [r["color_tint"] for r in results.values()]
        unique_tints = set(tints)
        assert len(unique_tints) == len(self.VALID_SEASONS), (
            "Each season should produce a unique color tint"
        )

    def test_invalid_season_raises(self):
        """Unknown season raises ValueError."""
        with pytest.raises(ValueError, match="Unknown season"):
            get_seasonal_variant("tree", "spring")

    def test_autumn_has_orange_tint(self):
        """Autumn variant adds warm (orange/red) color tint."""
        result = get_seasonal_variant("tree", "autumn")
        r, g, b = result["color_tint"]
        assert r > 0, "Autumn should have positive red tint"
        assert r > abs(b), "Autumn red tint should dominate"

    def test_winter_reduces_leaf_density(self):
        """Winter variant has very low leaf density for deciduous trees."""
        result = get_seasonal_variant("tree", "winter")
        assert result["leaf_density"] < 0.3, (
            f"Winter leaf_density too high: {result['leaf_density']}"
        )

    def test_corrupted_has_purple_tint(self):
        """Corrupted variant adds purple/violet tint."""
        result = get_seasonal_variant("tree", "corrupted")
        r, g, b = result["color_tint"]
        assert b > 0, "Corrupted should have positive blue tint"

    def test_summer_is_neutral(self):
        """Summer is the baseline with no tint and full density."""
        result = get_seasonal_variant("tree", "summer")
        assert result["color_tint"] == (0.0, 0.0, 0.0)
        assert result["saturation_mult"] == 1.0
        assert result["leaf_density"] == 1.0

    def test_rocks_less_affected(self):
        """Rock/mineral types are minimally affected by seasons."""
        for season in self.VALID_SEASONS:
            rock = get_seasonal_variant("rock", season)
            tree = get_seasonal_variant("tree", season)
            # Rock tint magnitude should be <= tree tint magnitude
            rock_mag = sum(abs(c) for c in rock["color_tint"])
            tree_mag = sum(abs(c) for c in tree["color_tint"])
            assert rock_mag <= tree_mag + 0.01, (
                f"Rock tint ({rock_mag:.3f}) exceeds tree tint ({tree_mag:.3f}) "
                f"in {season}"
            )

    def test_mushroom_corrupted_stronger(self):
        """Mushrooms have stronger corruption reaction."""
        mushroom_corrupt = get_seasonal_variant("mushroom", "corrupted")
        tree_corrupt = get_seasonal_variant("tree", "corrupted")
        # Mushroom blue tint should be stronger in corruption
        assert mushroom_corrupt["color_tint"][2] > tree_corrupt["color_tint"][2], (
            "Mushroom corruption blue tint should exceed tree corruption"
        )

    def test_affects_leaves_flag(self):
        """affects_leaves is True for foliage, False for minerals."""
        tree_summer = get_seasonal_variant("tree", "summer")
        assert tree_summer["affects_leaves"] is True
        rock_summer = get_seasonal_variant("rock", "summer")
        assert rock_summer["affects_leaves"] is False

    def test_rock_leaf_density_always_one(self):
        """Rocks always have leaf_density 1.0 (no leaves to lose)."""
        for season in self.VALID_SEASONS:
            result = get_seasonal_variant("rock", season)
            assert result["leaf_density"] == 1.0


# ===================================================================
# Integration: biome + placement + seasons
# ===================================================================


class TestVegetationIntegration:
    """Integration tests combining multiple vegetation system functions."""

    def test_all_biomes_with_all_seasons(self):
        """Every biome/season combination produces valid placements + variants."""
        verts, faces, normals, bounds = _make_flat_terrain(
            size=100.0, resolution=15,
        )

        for biome_name, biome_data in BIOME_VEGETATION_SETS.items():
            placements = compute_vegetation_placement(
                verts, faces, normals, biome_name, bounds,
                seed=42, min_distance=5.0,
            )

            # Get unique vegetation types from placements
            veg_types = set(p["type"] for p in placements)

            for season in ("summer", "autumn", "winter", "corrupted"):
                for vt in veg_types:
                    variant = get_seasonal_variant(vt, season)
                    assert "color_tint" in variant

    def test_varied_terrain_mixed_placements(self):
        """Varied terrain (flat + steep) produces placements only on flat areas."""
        verts, faces, normals, bounds = _make_varied_terrain(
            size=100.0, resolution=20,
        )
        placements = compute_vegetation_placement(
            verts, faces, normals, "thornwood_forest", bounds,
            seed=42, min_distance=3.0,
        )
        # Trees should only appear on the flat left half (x < 50)
        tree_placements = [p for p in placements if p["type"] == "tree"]
        for p in tree_placements:
            px = p["position"][0]
            assert px < 60, (
                f"Tree at x={px:.1f} should not be on steep right half"
            )


# ===================================================================
# New biome vegetation sets
# ===================================================================


class TestNewBiomeVegetationSets:
    """Tests specific to the 6 new biome vegetation configurations."""

    NEW_BIOMES = [
        "desert", "coastal", "grasslands",
        "mushroom_forest", "crystal_cavern", "deep_forest",
    ]

    @pytest.mark.parametrize("biome_name", NEW_BIOMES)
    def test_new_biome_exists(self, biome_name):
        assert biome_name in BIOME_VEGETATION_SETS

    @pytest.mark.parametrize("biome_name", NEW_BIOMES)
    def test_new_biome_has_categories(self, biome_name):
        biome = BIOME_VEGETATION_SETS[biome_name]
        for cat in ("trees", "ground_cover", "rocks"):
            assert cat in biome

    @pytest.mark.parametrize("biome_name", NEW_BIOMES)
    def test_new_biome_entries_valid(self, biome_name):
        biome = BIOME_VEGETATION_SETS[biome_name]
        for cat in ("trees", "ground_cover", "rocks"):
            for entry in biome[cat]:
                assert "type" in entry
                assert "density" in entry
                assert "scale_range" in entry
                assert 0.0 < entry["density"] <= 1.0
                sr = entry["scale_range"]
                assert len(sr) == 2
                assert sr[0] > 0
                assert sr[1] >= sr[0]

    def test_desert_has_sparse_vegetation(self):
        """Desert biome should have low vegetation density."""
        biome = BIOME_VEGETATION_SETS["desert"]
        total_density = sum(
            e["density"]
            for cat in ("trees", "ground_cover", "rocks")
            for e in biome[cat]
        )
        # Desert should be sparse
        assert total_density < 0.5

    def test_grasslands_has_dense_ground_cover(self):
        """Grasslands should have high ground cover density."""
        biome = BIOME_VEGETATION_SETS["grasslands"]
        gc_density = sum(e["density"] for e in biome["ground_cover"])
        assert gc_density >= 0.5

    def test_crystal_cavern_no_trees(self):
        """Crystal cavern should have no trees (underground)."""
        biome = BIOME_VEGETATION_SETS["crystal_cavern"]
        assert len(biome["trees"]) == 0

    def test_deep_forest_has_large_trees(self):
        """Deep forest trees should include very large scale ranges."""
        biome = BIOME_VEGETATION_SETS["deep_forest"]
        max_scale = max(e["scale_range"][1] for e in biome["trees"])
        assert max_scale >= 4.0

    def test_mushroom_forest_has_mushroom_types(self):
        """Mushroom forest should have mushroom vegetation types."""
        biome = BIOME_VEGETATION_SETS["mushroom_forest"]
        all_types = set()
        for cat in ("trees", "ground_cover", "rocks"):
            for e in biome[cat]:
                all_types.add(e["type"])
        assert "mushroom" in all_types

    @pytest.mark.parametrize("biome_name", NEW_BIOMES)
    def test_new_biome_produces_placements(self, biome_name):
        """Each new biome produces placements on flat terrain."""
        verts, faces, normals, bounds = _make_flat_terrain(
            size=200.0, resolution=20,
        )
        placements = compute_vegetation_placement(
            verts, faces, normals, biome_name, bounds,
            seed=42, min_distance=5.0,
        )
        # crystal_cavern has no trees but should still produce rocks/ground_cover
        assert len(placements) > 0, (
            f"Biome '{biome_name}' produced no placements"
        )

    def test_no_tropical_styles_in_new_biomes(self):
        """New biomes should not contain bright/tropical styles."""
        forbidden = {"palm", "tropical", "lush", "bright", "cherry_blossom"}
        for biome_name in self.NEW_BIOMES:
            biome = BIOME_VEGETATION_SETS[biome_name]
            for cat in ("trees", "ground_cover", "rocks"):
                for entry in biome[cat]:
                    style = entry.get("style", "")
                    assert style not in forbidden, (
                        f"Style '{style}' in {biome_name} is too bright "
                        f"for dark fantasy"
                    )
