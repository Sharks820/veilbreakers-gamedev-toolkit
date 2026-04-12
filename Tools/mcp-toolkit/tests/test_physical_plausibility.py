"""Physical plausibility tests for terrain systems.

Tests that rivers flow downhill, drainage networks are acyclic,
erosion produces V-shaped valleys, lakes form in depressions, and
water networks obey physical constraints.
Pure numpy -- no Blender required.
"""

from __future__ import annotations

import math

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def slope_heightmap():
    """64x64 heightmap with a strong gradient (high NW, low SE)."""
    rows, cols = 64, 64
    r = np.linspace(1.0, 0.0, rows).reshape(-1, 1)
    c = np.linspace(1.0, 0.0, cols).reshape(1, -1)
    return (r + c) / 2.0


@pytest.fixture
def mountain_heightmap():
    from blender_addon.handlers._terrain_noise import generate_heightmap
    return generate_heightmap(64, 64, scale=50.0, seed=42, terrain_type="mountains")


@pytest.fixture
def flow_result(mountain_heightmap):
    from blender_addon.handlers.terrain_advanced import compute_flow_map
    raw = compute_flow_map(mountain_heightmap)
    # compute_flow_map returns Python lists; convert to numpy for testing
    return {
        "flow_direction": np.asarray(raw["flow_direction"], dtype=np.int32),
        "flow_accumulation": np.asarray(raw["flow_accumulation"], dtype=np.float64),
        "drainage_basins": np.asarray(raw["drainage_basins"], dtype=np.int32),
        "num_basins": raw["num_basins"],
        "max_accumulation": raw["max_accumulation"],
        "resolution": raw["resolution"],
    }


@pytest.fixture
def eroded_masks(mountain_heightmap):
    from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion_masks
    return apply_hydraulic_erosion_masks(
        mountain_heightmap, iterations=500, seed=42
    )


# ===========================================================================
# River flows downhill
# ===========================================================================


class TestRiverFlowsDownhill:
    """Water must always flow from higher to lower elevation."""

    def test_flow_direction_points_downhill(self, mountain_heightmap, flow_result):
        """Every cell with a valid flow direction must point to a lower neighbor."""
        from blender_addon.handlers.terrain_advanced import _D8_OFFSETS
        hmap = np.asarray(mountain_heightmap, dtype=np.float64)
        flow_dir = flow_result["flow_direction"]
        rows, cols = hmap.shape
        violations = 0
        total_checked = 0

        for r in range(rows):
            for c in range(cols):
                d = int(flow_dir[r, c])
                if d < 0:
                    continue
                dr, dc = _D8_OFFSETS[d]
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    total_checked += 1
                    if hmap[nr, nc] > hmap[r, c] + 1e-12:
                        violations += 1

        assert total_checked > 0, "No flow directions computed"
        assert violations == 0, (
            f"{violations}/{total_checked} cells flow uphill"
        )

    def test_flow_on_gradient_follows_slope(self, slope_heightmap):
        """On a simple gradient, flow should follow the downhill direction."""
        from blender_addon.handlers.terrain_advanced import compute_flow_map
        raw = compute_flow_map(slope_heightmap)
        flow_dir = np.asarray(raw["flow_direction"], dtype=np.int32)
        rows, cols = flow_dir.shape

        # The gradient goes from high (NW) to low (SE), so flow should
        # generally point south (4) or east (2) or southeast (3).
        downhill_dirs = {2, 3, 4}  # E, SE, S
        downhill_count = 0
        total = 0
        for r in range(1, rows - 1):
            for c in range(1, cols - 1):
                d = int(flow_dir[r, c])
                if d >= 0:
                    total += 1
                    if d in downhill_dirs:
                        downhill_count += 1

        frac = downhill_count / max(total, 1)
        assert frac > 0.8, f"Only {frac:.1%} of flow follows gradient (expected >80%)"

    def test_traced_river_monotonically_descends(self, mountain_heightmap, flow_result):
        """A traced river path should have monotonically non-increasing elevation."""
        from blender_addon.handlers._water_network import trace_river_from_flow
        flow_dir = flow_result["flow_direction"]  # already numpy from fixture
        flow_acc = flow_result["flow_accumulation"]
        hmap = np.asarray(mountain_heightmap, dtype=np.float64)

        # Start from the cell with highest flow accumulation
        max_idx = np.unravel_index(flow_acc.argmax(), flow_acc.shape)
        # trace_river_from_flow expects numpy arrays (our fixture already converts)
        path = trace_river_from_flow(
            flow_dir, flow_acc, int(max_idx[0]), int(max_idx[1]), min_accumulation=10.0
        )
        if len(path) < 2:
            pytest.skip("No river path long enough to test")

        elevations = [hmap[r, c] for r, c in path]
        for i in range(1, len(elevations)):
            assert elevations[i] <= elevations[i - 1] + 1e-9, (
                f"River flows uphill at step {i}: {elevations[i-1]:.6f} -> {elevations[i]:.6f}"
            )

    def test_river_width_increases_downstream(self):
        """River width should increase with flow accumulation."""
        from blender_addon.handlers._water_network import compute_river_width
        widths = [compute_river_width(acc) for acc in [10, 100, 1000, 10000]]
        for i in range(1, len(widths)):
            assert widths[i] >= widths[i - 1], (
                f"Width decreased: acc={[10,100,1000,10000][i]} -> w={widths[i]:.2f}"
            )


# ===========================================================================
# Drainage network acyclicity
# ===========================================================================


class TestDrainageAcyclic:
    """Drainage networks must be directed acyclic graphs."""

    def test_flow_graph_has_no_cycles(self, mountain_heightmap, flow_result):
        """Following flow directions from any cell must terminate (no loops)."""
        from blender_addon.handlers.terrain_advanced import _D8_OFFSETS
        flow_dir = flow_result["flow_direction"]
        rows, cols = flow_dir.shape
        max_steps = rows * cols  # upper bound on path length

        # Test a sample of cells
        rng = np.random.RandomState(42)
        sample_cells = [(rng.randint(0, rows), rng.randint(0, cols)) for _ in range(200)]

        for start_r, start_c in sample_cells:
            visited = set()
            r, c = start_r, start_c
            steps = 0
            while steps < max_steps:
                if (r, c) in visited:
                    pytest.fail(f"Cycle detected starting from ({start_r}, {start_c})")
                visited.add((r, c))
                d = int(flow_dir[r, c])
                if d < 0:
                    break
                dr, dc = _D8_OFFSETS[d]
                nr, nc = r + dr, c + dc
                if not (0 <= nr < rows and 0 <= nc < cols):
                    break
                r, c = nr, nc
                steps += 1

    def test_every_cell_reaches_pit_or_edge(self, mountain_heightmap, flow_result):
        """Every cell must drain to a pit (flat) or the map boundary."""
        from blender_addon.handlers.terrain_advanced import _D8_OFFSETS
        flow_dir = flow_result["flow_direction"]
        rows, cols = flow_dir.shape

        rng = np.random.RandomState(99)
        sample_cells = [(rng.randint(0, rows), rng.randint(0, cols)) for _ in range(200)]

        for start_r, start_c in sample_cells:
            r, c = start_r, start_c
            visited = set()
            terminated = False
            while True:
                if (r, c) in visited:
                    break  # cycle (caught by other test)
                visited.add((r, c))
                d = int(flow_dir[r, c])
                if d < 0:
                    terminated = True  # pit
                    break
                dr, dc = _D8_OFFSETS[d]
                nr, nc = r + dr, c + dc
                if not (0 <= nr < rows and 0 <= nc < cols):
                    terminated = True  # boundary
                    break
                r, c = nr, nc
            assert terminated, f"Cell ({start_r},{start_c}) never terminates"

    def test_drainage_basins_cover_all_cells(self, flow_result):
        """Every cell must belong to exactly one drainage basin."""
        basins = flow_result["drainage_basins"]
        assert (basins >= 0).all(), "Some cells have no basin assignment"

    def test_drainage_basins_contiguous(self, flow_result):
        """Each drainage basin should form a contiguous region."""
        basins = flow_result["drainage_basins"]
        unique_basins = np.unique(basins)
        rows, cols = basins.shape

        for bid in unique_basins[:10]:  # Check first 10 basins
            mask = basins == bid
            if mask.sum() < 2:
                continue
            # Simple flood-fill from first cell to check contiguity
            cells = list(zip(*np.where(mask)))
            start = cells[0]
            visited = set()
            queue = [start]
            while queue:
                r, c = queue.pop()
                if (r, c) in visited:
                    continue
                if not mask[r, c]:
                    continue
                visited.add((r, c))
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1),
                                (-1, -1), (-1, 1), (1, -1), (1, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        queue.append((nr, nc))
            assert len(visited) == mask.sum(), (
                f"Basin {bid}: {len(visited)} reachable but {mask.sum()} total cells"
            )


# ===========================================================================
# Erosion produces V-shaped valleys
# ===========================================================================


class TestErosionVShapedValleys:
    """Hydraulic erosion should carve valleys with V-shaped cross-sections."""

    def test_erosion_carves_channels(self, mountain_heightmap, eroded_masks):
        """Eroded terrain should have lower values along high-drainage paths."""
        delta = mountain_heightmap - eroded_masks.height
        # Most erosion should happen where drainage is high
        drainage = eroded_masks.drainage
        high_drain = drainage > np.percentile(drainage, 90)
        low_drain = drainage < np.percentile(drainage, 10)

        if high_drain.sum() == 0 or low_drain.sum() == 0:
            pytest.skip("Not enough drainage variation")

        avg_erosion_high = delta[high_drain].mean()
        avg_erosion_low = delta[low_drain].mean()
        assert avg_erosion_high > avg_erosion_low, (
            f"Erosion not concentrated in channels: high-drain={avg_erosion_high:.6f}, "
            f"low-drain={avg_erosion_low:.6f}"
        )

    def test_erosion_amount_positive(self, eroded_masks):
        """Erosion amount mask should be non-negative everywhere."""
        assert (eroded_masks.erosion_amount >= -1e-12).all()

    def test_deposition_amount_positive(self, eroded_masks):
        """Deposition amount mask should be non-negative everywhere."""
        assert (eroded_masks.deposition_amount >= -1e-12).all()

    def test_wetness_correlates_with_drainage(self, eroded_masks):
        """Wetness should correlate positively with drainage."""
        wet = eroded_masks.wetness.ravel()
        drain = eroded_masks.drainage.ravel()
        # Only check if there's variation
        if wet.std() < 1e-12 or drain.std() < 1e-12:
            pytest.skip("No variation in wetness or drainage")
        correlation = np.corrcoef(wet, drain)[0, 1]
        assert correlation > 0.0, f"Wetness-drainage correlation={correlation:.3f} should be positive"

    def test_valley_cross_section_v_shape(self, mountain_heightmap, eroded_masks):
        """Cross-section through an eroded channel should be V-shaped (concave)."""
        drainage = eroded_masks.drainage
        height = eroded_masks.height
        rows, cols = height.shape

        # Find the row with highest max drainage (likely a valley)
        row_max_drain = drainage.max(axis=1)
        best_row = int(row_max_drain.argmax())
        if best_row < 2 or best_row >= rows - 2:
            best_row = rows // 2

        # Find the column of max drainage in that row
        best_col = int(drainage[best_row].argmax())

        # Extract a cross-section centered on the channel
        half_width = min(10, best_col, cols - best_col - 1)
        if half_width < 3:
            pytest.skip("Channel too close to edge for cross-section")

        cross = height[best_row, best_col - half_width:best_col + half_width + 1]
        center_h = cross[half_width]
        left_h = cross[0]
        right_h = cross[-1]

        # V-shape: center should be lower than or equal to edges
        assert center_h <= max(left_h, right_h) + 1e-6, (
            f"Channel center ({center_h:.4f}) not lower than edges "
            f"({left_h:.4f}, {right_h:.4f})"
        )

    def test_thermal_erosion_smooths_steep(self):
        """Thermal erosion should reduce maximum slope (talus redistribution)."""
        from blender_addon.handlers._terrain_erosion import apply_thermal_erosion
        from blender_addon.handlers._terrain_noise import generate_heightmap, compute_slope_map

        hmap = generate_heightmap(64, 64, scale=30.0, seed=42, terrain_type="cliffs")
        slope_before = compute_slope_map(hmap)
        eroded = apply_thermal_erosion(hmap, iterations=200)
        slope_after = compute_slope_map(eroded)

        # Max slope should decrease or stay same
        assert slope_after.max() <= slope_before.max() + 0.1, (
            f"Thermal erosion increased max slope: {slope_before.max():.2f} -> {slope_after.max():.2f}"
        )


# ===========================================================================
# Lake detection
# ===========================================================================


class TestLakePhysics:
    """Lakes must form in local minima with sufficient drainage."""

    def test_lakes_at_local_minima(self, mountain_heightmap, flow_result):
        """Detected lakes should be at local minima of the heightmap."""
        from blender_addon.handlers._water_network import detect_lakes
        hmap = np.asarray(mountain_heightmap, dtype=np.float64)
        lakes = detect_lakes(hmap, flow_result["flow_accumulation"], min_area=5)

        for lake in lakes:
            cr, cc = lake["center_row"], lake["center_col"]
            center_h = hmap[cr, cc]
            rows, cols = hmap.shape
            # Check that center is lower than at least half its neighbors
            lower_count = 0
            neighbor_count = 0
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = cr + dr, cc + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        neighbor_count += 1
                        if hmap[nr, nc] >= center_h - 1e-9:
                            lower_count += 1
            assert lower_count > neighbor_count / 2, (
                f"Lake center ({cr},{cc}) not at local minimum"
            )

    def test_lake_surface_z_above_bottom(self, mountain_heightmap, flow_result):
        """Lake surface elevation must be >= the pit bottom."""
        from blender_addon.handlers._water_network import detect_lakes
        hmap = np.asarray(mountain_heightmap, dtype=np.float64)
        lakes = detect_lakes(hmap, flow_result["flow_accumulation"], min_area=5)

        for lake in lakes:
            cr, cc = lake["center_row"], lake["center_col"]
            bottom = hmap[cr, cc]
            assert lake["surface_z"] >= bottom - 1e-9

    def test_lake_cells_below_surface(self, mountain_heightmap, flow_result):
        """All cells in a lake should have elevation <= surface_z."""
        from blender_addon.handlers._water_network import detect_lakes
        hmap = np.asarray(mountain_heightmap, dtype=np.float64)
        lakes = detect_lakes(hmap, flow_result["flow_accumulation"], min_area=5)

        for lake in lakes:
            for r, c in lake["cells"]:
                assert hmap[r, c] <= lake["surface_z"] + 1e-9, (
                    f"Lake cell ({r},{c}) elevation {hmap[r,c]:.4f} > surface {lake['surface_z']:.4f}"
                )


# ===========================================================================
# Water network constraints
# ===========================================================================


class TestWaterNetworkPhysics:
    """Water network graph must obey physical constraints."""

    def test_river_width_positive(self):
        """River width must always be positive."""
        from blender_addon.handlers._water_network import compute_river_width
        for acc in [0, 1, 10, 100, 1000, 100000]:
            w = compute_river_width(acc)
            assert w > 0, f"Zero/negative width for accumulation={acc}"

    def test_river_width_bounded(self):
        """River width must respect min/max bounds."""
        from blender_addon.handlers._water_network import compute_river_width
        w_tiny = compute_river_width(0, min_width=2.0, max_width=50.0)
        w_huge = compute_river_width(1e9, min_width=2.0, max_width=50.0)
        assert w_tiny >= 2.0
        assert w_huge <= 50.0

    def test_flow_accumulation_positive(self, flow_result):
        """Flow accumulation must be >= 1 everywhere (each cell counts itself)."""
        assert (flow_result["flow_accumulation"] >= 1.0).all()

    def test_flow_accumulation_total_matches(self, flow_result):
        """Total flow accumulation at pits should account for all cells."""
        flow_dir = flow_result["flow_direction"]
        flow_acc = flow_result["flow_accumulation"]
        rows, cols = flow_dir.shape

        # Pit cells are those with flow_dir == -1
        pits = flow_dir == -1
        # Also boundary terminals
        total_cells = rows * cols
        # Sum of accumulation at terminal cells should >= total_cells
        # (each cell contributes 1 to some downstream path)
        terminal_acc = flow_acc[pits].sum()
        assert terminal_acc >= total_cells * 0.5, (
            f"Terminal accumulation {terminal_acc:.0f} < 50% of {total_cells} cells"
        )

    def test_erosion_masks_shapes_consistent(self, eroded_masks, mountain_heightmap):
        """All erosion mask arrays must have the same shape as the heightmap."""
        shape = mountain_heightmap.shape
        assert eroded_masks.height.shape == shape
        assert eroded_masks.erosion_amount.shape == shape
        assert eroded_masks.deposition_amount.shape == shape
        assert eroded_masks.wetness.shape == shape
        assert eroded_masks.drainage.shape == shape
        assert eroded_masks.bank_instability.shape == shape

    def test_erosion_conserves_material_approximately(self, mountain_heightmap, eroded_masks):
        """Total erosion and deposition should roughly balance (mass conservation)."""
        total_erosion = eroded_masks.erosion_amount.sum()
        total_deposition = eroded_masks.deposition_amount.sum()
        # Allow significant deviation since some sediment leaves the map
        if total_erosion < 1e-6:
            pytest.skip("Negligible erosion")
        ratio = total_deposition / total_erosion
        assert 0.01 < ratio < 100.0, (
            f"Erosion/deposition ratio {ratio:.3f} extremely unbalanced"
        )
