"""Unit tests for environment handler pure-logic functions.

Tests _validate_terrain_params, _export_heightmap_raw, and validates
handler return dict structure via pure-logic extraction.
"""

import struct
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# _validate_terrain_params tests
# ---------------------------------------------------------------------------


class TestValidateTerrainParams:
    """Test terrain parameter validation (pure logic, no Blender)."""

    def test_valid_defaults(self):
        """Default parameters pass validation."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({})
        assert result["name"] == "Terrain"
        assert result["resolution"] == 257
        assert result["terrain_type"] == "mountains"
        assert result["erosion"] == "none"

    def test_raises_resolution_too_large(self):
        """Resolution > 4096 raises ValueError."""
        from blender_addon.handlers.environment import _validate_terrain_params

        with pytest.raises(ValueError, match="Resolution"):
            _validate_terrain_params({"resolution": 4097})

    def test_raises_resolution_too_small(self):
        """Resolution < 3 raises ValueError."""
        from blender_addon.handlers.environment import _validate_terrain_params

        with pytest.raises(ValueError, match="Resolution"):
            _validate_terrain_params({"resolution": 2})

    def test_raises_unknown_terrain_type(self):
        """Unknown terrain_type raises ValueError."""
        from blender_addon.handlers.environment import _validate_terrain_params

        with pytest.raises(ValueError, match="terrain_type"):
            _validate_terrain_params({"terrain_type": "bogus_terrain"})

    def test_raises_unknown_erosion_mode(self):
        """Unknown erosion mode raises ValueError."""
        from blender_addon.handlers.environment import _validate_terrain_params

        with pytest.raises(ValueError, match="erosion"):
            _validate_terrain_params({"erosion": "wind"})

    def test_max_resolution_4096_passes(self):
        """Resolution 4096 (maximum) passes validation."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({"resolution": 4096})
        assert result["resolution"] == 4096

    def test_default_erosion_iterations_5000(self):
        """Default erosion_iterations is 5000."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({})
        assert result["erosion_iterations"] == 5000

    def test_all_terrain_types_valid(self):
        """All supported terrain types pass validation."""
        from blender_addon.handlers.environment import _validate_terrain_params

        for ttype in [
            "mountains",
            "hills",
            "plains",
            "volcanic",
            "canyon",
            "cliffs",
            "flat",
            "coastal",
            "swamp",
            "chaotic",
        ]:
            result = _validate_terrain_params({"terrain_type": ttype})
            assert result["terrain_type"] == ttype

    def test_all_erosion_modes_valid(self):
        """All erosion modes pass validation."""
        from blender_addon.handlers.environment import _validate_terrain_params

        for mode in ["none", "hydraulic", "thermal", "both"]:
            result = _validate_terrain_params({"erosion": mode})
            assert result["erosion"] == mode

    def test_custom_name_preserved(self):
        """Custom name parameter is preserved."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({"name": "MyTerrain"})
        assert result["name"] == "MyTerrain"

    def test_custom_scale_preserved(self):
        """Custom scale parameter is preserved."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({"scale": 200.0})
        assert result["scale"] == 200.0

    def test_custom_noise_scale_preserved(self):
        """Custom noise_scale parameter is preserved."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({"noise_scale": 48.0})
        assert result["noise_scale"] == 48.0

    def test_custom_height_scale_preserved(self):
        """Custom height_scale parameter is preserved."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({"height_scale": 50.0})
        assert result["height_scale"] == 50.0

    def test_custom_seed_preserved(self):
        """Custom seed parameter is preserved."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({"seed": 42})
        assert result["seed"] == 42

    def test_returns_dict(self):
        """Validated result is a dict."""
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({})
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# _run_height_solver_in_world_space tests
# ---------------------------------------------------------------------------


class TestWorldHeightSolverAdapter:
    """World-unit path solver wrapper must preserve signed terrain ranges."""

    def test_round_trips_negative_elevation_heightmap(self):
        from blender_addon.handlers.environment import _run_height_solver_in_world_space

        hmap = np.array(
            [
                [-40.0, -30.0],
                [-10.0, 20.0],
            ],
            dtype=np.float64,
        )

        def _identity_solver(heightmap, **kwargs):
            return [(0, 0), (1, 1)], heightmap.copy()

        path, restored, transform = _run_height_solver_in_world_space(
            hmap,
            _identity_solver,
        )

        assert path == [(0, 0), (1, 1)]
        np.testing.assert_allclose(restored, hmap, atol=1e-9)
        assert transform.world_min == -40.0
        assert transform.world_max == 20.0

    def test_denormalizes_solver_output_back_to_world_units(self):
        from blender_addon.handlers.environment import _run_height_solver_in_world_space

        hmap = np.array(
            [
                [-40.0, -20.0],
                [0.0, 20.0],
            ],
            dtype=np.float64,
        )

        def _lower_solver(heightmap, **kwargs):
            lowered = np.clip(heightmap - 0.25, 0.0, 1.0)
            return [(0, 0), (1, 1)], lowered

        _path, restored, _transform = _run_height_solver_in_world_space(
            hmap,
            _lower_solver,
        )

        assert float(restored.min()) == pytest.approx(-40.0, abs=1e-9)
        assert float(restored.max()) == pytest.approx(5.0, abs=1e-9)
        assert np.all(restored <= 20.0)


class TestAltitudeRuleNormalization:
    """Biome-rule altitude normalization must preserve negative ranges."""

    def test_negative_range_maps_to_unit_interval(self):
        from blender_addon.handlers.environment import _normalize_altitude_for_rule_range

        assert _normalize_altitude_for_rule_range(-40.0, range_min=-40.0, range_max=20.0) == 0.0
        assert _normalize_altitude_for_rule_range(20.0, range_min=-40.0, range_max=20.0) == 1.0
        assert _normalize_altitude_for_rule_range(-10.0, range_min=-40.0, range_max=20.0) == pytest.approx(0.5)

    def test_clamps_values_outside_explicit_range(self):
        from blender_addon.handlers.environment import _normalize_altitude_for_rule_range

        assert _normalize_altitude_for_rule_range(-50.0, range_min=-40.0, range_max=20.0) == 0.0
        assert _normalize_altitude_for_rule_range(30.0, range_min=-40.0, range_max=20.0) == 1.0


class TestNoiseSamplingScale:
    """Terrain footprint and noise sampling scale should be decoupled."""

    def test_derives_smaller_scale_from_terrain_size(self):
        from blender_addon.handlers.environment import _resolve_noise_sampling_scale

        derived = _resolve_noise_sampling_scale(terrain_size=180.0, terrain_type="mountains")
        assert derived < 180.0
        assert derived >= 24.0

    def test_explicit_noise_scale_wins(self):
        from blender_addon.handlers.environment import _resolve_noise_sampling_scale

        assert _resolve_noise_sampling_scale(
            terrain_size=180.0,
            terrain_type="mountains",
            explicit_noise_scale=60.0,
        ) == pytest.approx(60.0)

    def test_invalid_explicit_noise_scale_raises(self):
        from blender_addon.handlers.environment import _resolve_noise_sampling_scale

        with pytest.raises(ValueError, match="noise_scale"):
            _resolve_noise_sampling_scale(
                terrain_size=180.0,
                terrain_type="mountains",
                explicit_noise_scale=0.0,
            )


class TestHeightmapReliefEnhancement:
    """Terrain relief enhancement should expand weak heightmaps without shifting sea level."""

    def test_mountain_relief_is_boosted_when_span_is_too_small(self):
        from blender_addon.handlers.environment import _enhance_heightmap_relief

        hmap = np.array(
            [
                [-0.18, -0.12, -0.05],
                [0.00, 0.06, 0.10],
                [0.14, 0.18, 0.22],
            ],
            dtype=np.float64,
        )
        boosted = _enhance_heightmap_relief(hmap, terrain_type="mountains")
        original_span = float(np.percentile(hmap, 95.0) - np.percentile(hmap, 5.0))
        boosted_span = float(np.percentile(boosted, 95.0) - np.percentile(boosted, 5.0))

        assert boosted_span > original_span
        assert float(boosted.min()) < float(hmap.min())
        assert float(boosted.max()) > float(hmap.max())

    def test_signed_heightmap_keeps_zero_centered_for_coastal_relief(self):
        from blender_addon.handlers.environment import _enhance_heightmap_relief

        hmap = np.array(
            [
                [-0.12, -0.08, -0.04],
                [0.00, 0.03, 0.06],
                [0.10, 0.13, 0.16],
            ],
            dtype=np.float64,
        )
        boosted = _enhance_heightmap_relief(hmap, terrain_type="coastal")

        assert float(boosted[1, 0]) == pytest.approx(0.0, abs=1e-9)
        assert float(boosted.max()) > float(hmap.max())
        assert float(boosted.min()) < float(hmap.min())


class TestRoadTerrainProfiling:
    """Road deformation helpers should create a usable crown-and-ditch profile."""

    def test_apply_road_profile_raises_center_and_softens_shoulders(self):
        from blender_addon.handlers.environment import _apply_road_profile_to_heightmap

        heightmap = np.zeros((9, 9), dtype=np.float64)
        path = [(4, 1), (4, 7)]

        profiled = _apply_road_profile_to_heightmap(
            heightmap,
            path,
            width_cells=3.0,
            grade_strength=1.0,
            crown_height_m=0.1,
            shoulder_width_cells=2.0,
            ditch_depth_m=0.2,
        )

        assert profiled[4, 4] > 0.0
        assert profiled[1, 4] < 0.0
        assert profiled[0, 0] == pytest.approx(0.0)

    def test_sample_path_indices_preserves_forced_boundaries(self):
        from blender_addon.handlers.environment import _sample_path_indices

        path = [(0, c) for c in range(12)]
        indices = _sample_path_indices(path, min_spacing_cells=3.0, forced_indices={4, 8})
        assert indices[0] == 0
        assert indices[-1] == len(path) - 1
        assert 4 in indices
        assert 8 in indices

    def test_collect_bridge_spans_extends_to_banks(self):
        from blender_addon.handlers.environment import _collect_bridge_spans

        path = [(4, c) for c in range(8)]
        base = np.full((9, 9), 2.0, dtype=np.float64)
        base[4, 2:6] = -1.0
        spans = _collect_bridge_spans(
            path,
            base_heightmap=base,
            graded_heightmap=np.full_like(base, 0.5),
            water_level=0.0,
            width_m=2.0,
            rows=9,
            cols=9,
            terrain_width=18.0,
            terrain_height=18.0,
            terrain_origin_x=0.0,
            terrain_origin_y=0.0,
        )

        assert len(spans) == 1
        assert spans[0]["start_index"] < 2
        assert spans[0]["end_index"] > 5
        assert spans[0]["style"] == "rope"
        assert spans[0]["start_pos"][2] > 0.0


# ---------------------------------------------------------------------------
# _export_heightmap_raw tests
# ---------------------------------------------------------------------------


class TestExportHeightmapRaw:
    """Test 16-bit RAW heightmap export (pure logic, no file I/O)."""

    def test_returns_bytes(self):
        """Export returns bytes object."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.array([[0.0, 0.5], [0.5, 1.0]])
        raw = _export_heightmap_raw(hmap, flip_vertical=False)
        assert isinstance(raw, bytes)

    def test_correct_byte_length(self):
        """Output length is width * height * 2 bytes (16-bit)."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.array([[0.0, 0.5], [0.5, 1.0]])
        raw = _export_heightmap_raw(hmap, flip_vertical=False)
        assert len(raw) == 2 * 2 * 2  # 2x2 grid, 2 bytes per pixel

    def test_known_2x2_values(self):
        """Known 2x2 heightmap produces correct uint16 values."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.array([[0.0, 1.0], [0.5, 0.5]])
        raw = _export_heightmap_raw(hmap, flip_vertical=False)
        # Unpack as 4 uint16 little-endian values
        values = struct.unpack("<4H", raw)
        # [0.0 -> 0, 1.0 -> 65535, 0.5 -> ~32767, 0.5 -> ~32767]
        assert values[0] == 0
        assert values[1] == 65535
        # 0.5 * 65535 = 32767.5, cast to uint16 = 32767 or 32768
        assert 32766 <= values[2] <= 32768
        assert 32766 <= values[3] <= 32768

    def test_flip_vertical_reverses_rows(self):
        """flip_vertical=True reverses row order."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.array([[0.0, 0.0], [1.0, 1.0]])
        raw_no_flip = _export_heightmap_raw(hmap, flip_vertical=False)
        raw_flipped = _export_heightmap_raw(hmap, flip_vertical=True)
        # No flip: row 0 = [0, 0], row 1 = [65535, 65535]
        # Flipped: row 0 = [65535, 65535], row 1 = [0, 0]
        vals_no_flip = struct.unpack("<4H", raw_no_flip)
        vals_flipped = struct.unpack("<4H", raw_flipped)
        # First row of no_flip should be last row of flipped
        assert vals_no_flip[0] == vals_flipped[2]
        assert vals_no_flip[1] == vals_flipped[3]
        assert vals_no_flip[2] == vals_flipped[0]
        assert vals_no_flip[3] == vals_flipped[1]

    def test_flat_heightmap_all_same(self):
        """Flat heightmap (all same value) exports as all zeros."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.full((4, 4), 0.5)
        raw = _export_heightmap_raw(hmap, flip_vertical=False)
        values = struct.unpack(f"<{4*4}H", raw)
        # All same value -> normalized to 0 (since max == min)
        assert all(v == 0 for v in values)

    def test_values_in_uint16_range(self):
        """All exported values are in [0, 65535]."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.random.RandomState(42).rand(8, 8)
        raw = _export_heightmap_raw(hmap, flip_vertical=False)
        values = struct.unpack(f"<{8*8}H", raw)
        assert all(0 <= v <= 65535 for v in values)

    def test_little_endian_byte_order(self):
        """Output uses little-endian byte order."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        # Create a heightmap where we know the exact uint16 value
        hmap = np.array([[0.0, 1.0]])
        raw = _export_heightmap_raw(hmap, flip_vertical=False)
        # Value 65535 in little-endian is 0xFF 0xFF
        # Value 0 in little-endian is 0x00 0x00
        assert raw[0:2] == b"\x00\x00"  # 0
        assert raw[2:4] == b"\xff\xff"  # 65535

    def test_larger_heightmap(self):
        """Correctly handles larger heightmaps."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.random.RandomState(42).rand(64, 64)
        raw = _export_heightmap_raw(hmap, flip_vertical=True)
        assert len(raw) == 64 * 64 * 2

    def test_shared_value_range_preserves_world_scale(self):
        """A shared export range should avoid per-tile renormalization."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.array([[10.0, 20.0]], dtype=np.float64)
        raw = _export_heightmap_raw(
            hmap,
            flip_vertical=False,
            value_range=(0.0, 40.0),
        )
        values = struct.unpack("<2H", raw)
        assert 16383 <= values[0] <= 16384
        assert 32767 <= values[1] <= 32768

    def test_shared_value_range_clamps_outside_bounds(self):
        """Shared export range should clamp values outside the provided range."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.array([[-5.0, 50.0]], dtype=np.float64)
        raw = _export_heightmap_raw(
            hmap,
            flip_vertical=False,
            value_range=(0.0, 40.0),
        )
        values = struct.unpack("<2H", raw)
        assert values[0] == 0
        assert values[1] == 65535


class TestExportSplatmapRaw:
    """Test RAW splatmap export (pure logic, no file I/O)."""

    def test_returns_bytes(self):
        from blender_addon.handlers.environment import _export_splatmap_raw

        splat = np.zeros((2, 2, 4), dtype=np.float64)
        splat[:, :, 0] = 1.0
        raw = _export_splatmap_raw(splat, flip_vertical=False)
        assert isinstance(raw, bytes)
        assert len(raw) == 2 * 2 * 4

    def test_normalizes_channels(self):
        from blender_addon.handlers.environment import _export_splatmap_raw

        splat = np.array(
            [
                [[2.0, 1.0, 1.0, 0.0], [0.0, 0.0, 0.0, 0.0]],
                [[0.25, 0.25, 0.25, 0.25], [1.0, 0.0, 0.0, 0.0]],
            ]
        )
        raw = _export_splatmap_raw(splat, flip_vertical=False)
        values = np.frombuffer(raw, dtype=np.uint8)
        assert values.shape == (2 * 2 * 4,)
        assert values.max() <= 255


class TestWorldSplatmapWeights:
    """World splatmap weighting should honor a shared height range."""

    def test_shared_height_range_keeps_weights_stable(self):
        from blender_addon.handlers.terrain_materials import compute_world_splatmap_weights

        tile = np.array(
            [
                [0.0, 0.2],
                [0.4, 0.6],
            ],
            dtype=np.float64,
        )

        local_weights = compute_world_splatmap_weights(
            tile,
            biome_name="thornwood_forest",
        )
        shared_weights = compute_world_splatmap_weights(
            tile,
            biome_name="thornwood_forest",
            height_range=(0.0, 2.0),
        )

        assert not np.allclose(local_weights[0, 1], shared_weights[0, 1])

    def test_larger_cell_size_keeps_same_height_delta_less_cliff_like(self):
        from blender_addon.handlers.terrain_materials import compute_world_splatmap_weights

        hmap = np.tile(np.linspace(0.0, 1.0, 5), (5, 1))
        fine = compute_world_splatmap_weights(
            hmap,
            biome_name="thornwood_forest",
            cell_size=1.0,
        )
        coarse = compute_world_splatmap_weights(
            hmap,
            biome_name="thornwood_forest",
            cell_size=4.0,
        )

        assert coarse[2, 2][0] > fine[2, 2][0]
        assert coarse[2, 2][1] < fine[2, 2][1]


# ---------------------------------------------------------------------------
# Handler return dict structure tests
# ---------------------------------------------------------------------------


class TestHandlerReturnDictKeys:
    """Verify expected keys in handler return dicts (via pure-logic validation)."""

    def test_generate_terrain_expected_keys(self):
        """handle_generate_terrain returns dict with required keys."""
        # We can't call the handler without Blender, but we can verify
        # the validation function returns the right structure
        from blender_addon.handlers.environment import _validate_terrain_params

        result = _validate_terrain_params({
            "name": "TestTerrain",
            "resolution": 65,
            "terrain_type": "hills",
            "erosion": "hydraulic",
        })
        # Validated params should contain all the keys the handler uses
        assert "name" in result
        assert "resolution" in result
        assert "terrain_type" in result
        assert "erosion" in result
        assert "height_scale" in result
        assert "seed" in result

    def test_export_raw_produces_correct_format(self):
        """_export_heightmap_raw produces Unity-compatible 16-bit little-endian."""
        from blender_addon.handlers.environment import _export_heightmap_raw

        hmap = np.random.RandomState(42).rand(33, 33)
        raw = _export_heightmap_raw(hmap, flip_vertical=True)
        # Should be 33 * 33 * 2 bytes
        assert len(raw) == 33 * 33 * 2
        # Should be parseable as uint16 array
        arr = np.frombuffer(raw, dtype=np.uint16)
        assert arr.shape == (33 * 33,)
        assert arr.min() >= 0
        assert arr.max() <= 65535


class TestControllerTerrainPath:
    def test_generate_terrain_uses_controller_heightmap_as_source_of_truth(self):
        from blender_addon.handlers import environment as env_mod
        from blender_addon.handlers.terrain_semantics import TerrainMaskStack

        height = np.full((3, 3), 2.0, dtype=np.float64)
        stack = TerrainMaskStack(
            tile_size=2,
            cell_size=1.0,
            world_origin_x=0.0,
            world_origin_y=0.0,
            tile_x=0,
            tile_y=0,
            height=height,
        )
        stack.set("cliff_candidate", np.ones_like(height, dtype=bool), "test")
        controller_state = SimpleNamespace(mask_stack=stack)
        controller_results = [
            SimpleNamespace(pass_name="macro_world", status="ok"),
            SimpleNamespace(pass_name="structural_masks", status="ok"),
            SimpleNamespace(pass_name="cliffs", status="ok"),
            SimpleNamespace(pass_name="validation_minimal", status="ok"),
        ]
        controller_execution = {
            "state": controller_state,
            "results": controller_results,
            "mask_stack": stack,
            "tile_x": 0,
            "tile_y": 0,
        }
        cliff_overlays = [
            {
                "cliff_id": "hero_01",
                "tier": "hero",
                "position": [0.0, 0.0, 2.0],
                "rotation": [0.0, 0.0, 0.0],
                "width": 6.0,
                "height": 8.0,
            }
        ]
        captured: dict[str, object] = {}

        def _fake_create_mesh(**kwargs):
            captured["heightmap"] = np.asarray(kwargs["heightmap"]).copy()
            captured["controller_cliff_placements"] = kwargs.get("controller_cliff_placements")
            return {
                "name": kwargs["name"],
                "vertex_count": int(np.asarray(kwargs["heightmap"]).size),
                "cliff_overlays": len(kwargs.get("controller_cliff_placements") or []),
                "hero_cliff_overlays": 1,
            }

        with patch.object(env_mod, "_execute_terrain_pipeline", return_value=controller_execution), \
             patch.object(env_mod, "_create_terrain_mesh_from_heightmap", side_effect=_fake_create_mesh), \
             patch.object(env_mod, "_cliff_structures_to_overlay_placements", return_value=cliff_overlays), \
             patch.object(env_mod, "generate_heightmap", side_effect=AssertionError("legacy path should not run")), \
             patch("blender_addon.handlers.terrain_cliffs.carve_cliff_system", return_value=["hero_cliff"]):
            result = env_mod.handle_generate_terrain(
                {
                    "name": "ControllerTerrain",
                    "resolution": 3,
                    "terrain_type": "hills",
                    "erosion": "none",
                    "seed": 7,
                    "scale": 32.0,
                    "height_scale": 4.0,
                    "use_controller": True,
                    "cliff_overlays": True,
                }
            )

        np.testing.assert_array_equal(captured["heightmap"], height)
        assert captured["controller_cliff_placements"] == cliff_overlays
        assert result["controller_used"] is True
        assert result["controller_ok"] is True
        assert result["hero_cliff_overlays"] == 1
        assert result["heightmap"] == height.tolist()
        assert result["tile_size"] == 2
        assert result["cell_size"] == pytest.approx(16.0)
        assert result["world_origin_x"] == pytest.approx(-16.0)
        assert result["world_origin_y"] == pytest.approx(-16.0)
        assert result["water_network_present"] is False

    def test_controller_path_threads_cave_candidates_but_defers_cave_pipeline_by_default(self):
        from blender_addon.handlers import environment as env_mod
        from blender_addon.handlers.terrain_semantics import TerrainMaskStack

        height = np.zeros((3, 3), dtype=np.float64)
        stack = TerrainMaskStack(
            tile_size=2,
            cell_size=1.0,
            world_origin_x=0.0,
            world_origin_y=0.0,
            tile_x=0,
            tile_y=0,
            height=height,
        )
        controller_execution = {
            "state": SimpleNamespace(mask_stack=stack),
            "results": [],
            "mask_stack": stack,
            "tile_x": 0,
            "tile_y": 0,
        }
        captured: dict[str, object] = {}

        def _fake_execute(params):
            captured["params"] = dict(params)
            return controller_execution

        def _fake_create_mesh(**kwargs):
            return {
                "name": kwargs["name"],
                "vertex_count": int(np.asarray(kwargs["heightmap"]).size),
                "cliff_overlays": 0,
                "hero_cliff_overlays": 0,
            }

        with patch.object(env_mod, "_execute_terrain_pipeline", side_effect=_fake_execute), \
             patch.object(env_mod, "_create_terrain_mesh_from_heightmap", side_effect=_fake_create_mesh):
            result = env_mod.handle_generate_terrain(
                {
                    "name": "CaveControllerTerrain",
                    "resolution": 3,
                    "terrain_type": "mountains",
                    "erosion": "none",
                    "seed": 11,
                    "scale": 32.0,
                    "height_scale": 6.0,
                    "use_controller": True,
                    "object_location": (4.0, -2.0, 0.0),
                    "scene_read": {
                        "reviewer": "pytest",
                        "cave_candidates": [(6.0, 3.0, 0.0)],
                    },
                }
            )

        params = captured["params"]
        assert params["scene_read"]["cave_candidates"] == [(6.0, 3.0, 0.0)]
        assert params["pipeline"] == ["macro_world", "structural_masks", "cliffs", "validation_minimal"]
        assert params["world_origin_x"] == pytest.approx(-12.0)
        assert params["world_origin_y"] == pytest.approx(-18.0)
        assert result["cave_candidates"] == [[6.0, 3.0, 0.0]]
        assert result["cave_mask_present"] is False
        assert result["cave_pipeline_deferred"] is True

    def test_controller_path_can_opt_in_to_cave_pipeline(self):
        from blender_addon.handlers import environment as env_mod
        from blender_addon.handlers.terrain_semantics import TerrainMaskStack

        height = np.zeros((3, 3), dtype=np.float64)
        stack = TerrainMaskStack(
            tile_size=2,
            cell_size=1.0,
            world_origin_x=0.0,
            world_origin_y=0.0,
            tile_x=0,
            tile_y=0,
            height=height,
        )
        controller_execution = {
            "state": SimpleNamespace(mask_stack=stack),
            "results": [],
            "mask_stack": stack,
            "tile_x": 0,
            "tile_y": 0,
        }
        captured: dict[str, object] = {}

        def _fake_execute(params):
            captured["params"] = dict(params)
            return controller_execution

        def _fake_create_mesh(**kwargs):
            return {
                "name": kwargs["name"],
                "vertex_count": int(np.asarray(kwargs["heightmap"]).size),
                "cliff_overlays": 0,
                "hero_cliff_overlays": 0,
            }

        with patch.object(env_mod, "_execute_terrain_pipeline", side_effect=_fake_execute), \
             patch.object(env_mod, "_create_terrain_mesh_from_heightmap", side_effect=_fake_create_mesh):
            result = env_mod.handle_generate_terrain(
                {
                    "name": "CaveControllerTerrain",
                    "resolution": 3,
                    "terrain_type": "mountains",
                    "erosion": "none",
                    "seed": 11,
                    "scale": 32.0,
                    "height_scale": 6.0,
                    "use_controller": True,
                    "controller_apply_caves": True,
                    "object_location": (4.0, -2.0, 0.0),
                    "scene_read": {
                        "reviewer": "pytest",
                        "cave_candidates": [(6.0, 3.0, 0.0)],
                    },
                }
            )

        params = captured["params"]
        assert params["pipeline"] == ["macro_world", "structural_masks", "caves", "integrate_deltas", "cliffs", "validation_minimal"]
        assert result["cave_pipeline_deferred"] is False


class TestWorldTerrainGeneration:
    def test_world_terrain_wraps_tile_generation(self):
        """handle_generate_world_terrain delegates to tiled generation for compatibility."""
        from blender_addon.handlers import environment as env_mod

        with patch.object(env_mod, "handle_generate_terrain_tile", return_value={"name": "X", "tile_x": 0, "tile_y": 0}):
            result = env_mod.handle_generate_world_terrain({"name": "X"})

        assert result["name"] == "X"
        assert result["deprecated_command"] is True
        assert result["compatibility_mode"] == "world_to_tile_wrapper"

    def test_world_terrain_can_wrap_multiple_tiles(self):
        from blender_addon.handlers import environment as env_mod

        with patch.object(env_mod, "handle_generate_terrain_tile", side_effect=lambda params: {
            "name": params["name"],
            "tile_x": params["tile_x"],
            "tile_y": params["tile_y"],
        }):
            result = env_mod.handle_generate_world_terrain({
                "name": "World",
                "tiles_x": 2,
                "tiles_y": 2,
            })

        assert result["tile_count"] == 4
        assert result["deprecated_command"] is True
        assert {(tile["tile_x"], tile["tile_y"]) for tile in result["tiles"]} == {
            (0, 0), (1, 0), (0, 1), (1, 1),
        }


def test_execute_terrain_pipeline_wires_water_network_and_spec():
    from blender_addon.handlers import environment as env_mod

    height = np.linspace(16.0, 0.0, 9 * 9, dtype=np.float64).reshape(9, 9)
    execution = env_mod._execute_terrain_pipeline(
        {
            "tile_size": 8,
            "cell_size": 2.0,
            "seed": 19,
            "terrain_type": "hills",
            "height": height,
            "pipeline": ["macro_world"],
            "min_drainage_area": 123.0,
            "river_threshold": 456.0,
            "lake_min_area": 12.0,
            "braided_channels": True,
            "seasonal_state": "flood",
        }
    )

    state = execution["state"]
    assert state.water_network is not None
    assert state.intent.water_system_spec is not None
    assert state.intent.water_system_spec.min_drainage_area == pytest.approx(123.0)
    assert state.intent.water_system_spec.river_threshold == pytest.approx(456.0)
    assert state.intent.water_system_spec.lake_min_area == pytest.approx(12.0)
    assert state.intent.water_system_spec.braided_channels is True
    assert state.intent.water_system_spec.seasonal_state == "flood"


def test_handle_generate_waterfall_materializes_object_and_threads_direction():
    from blender_addon.handlers import environment as env_mod

    captured: dict[str, object] = {}

    class _DummyMaterials(list):
        def clear(self):
            del self[:]

    dummy_obj = SimpleNamespace(
        name="HeroFalls",
        data=SimpleNamespace(materials=_DummyMaterials()),
    )

    def _fake_generate_waterfall(**kwargs):
        captured["facing_direction"] = kwargs["facing_direction"]
        return {
            "mesh": {
                "vertices": [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
                "faces": [(0, 1, 2)],
            },
            "material_indices": [0],
            "dimensions": {"height": kwargs["height"], "width": kwargs["width"]},
            "vertex_count": 3,
            "face_count": 1,
        }

    def _fake_create_mesh(spec, **kwargs):
        captured["mesh_spec"] = spec
        captured["location"] = kwargs["location"]
        return dummy_obj

    with patch.object(env_mod, "generate_waterfall", side_effect=_fake_generate_waterfall), \
         patch.object(env_mod, "_create_mesh_object_from_spec", side_effect=_fake_create_mesh), \
         patch.object(env_mod, "_ensure_water_material", return_value=object()):
        result = env_mod.handle_generate_waterfall(
            {
                "name": "HeroFalls",
                "height": 12.0,
                "width": 4.0,
                "location": [1.0, 2.0, 3.0],
                "facing_direction": [1.0, 0.0],
                "materialize_object": True,
                "allow_legacy_geometry_fallback": True,
            }
        )

    assert captured["facing_direction"] == (1.0, 0.0)
    assert captured["location"] == (1.0, 2.0, 3.0)
    assert captured["mesh_spec"]["material_ids"] == [0]
    assert result["name"] == "HeroFalls"
    assert result["object_created"] is True
    assert len(dummy_obj.data.materials) == 1


def test_handle_generate_waterfall_can_require_heightmap_context():
    from blender_addon.handlers import environment as env_mod

    with pytest.raises(ValueError, match="requires heightmap/water-network context"):
        env_mod.handle_generate_waterfall(
            {
                "name": "StrictFalls",
                "height": 9.0,
                "width": 3.0,
            }
        )

    legacy = env_mod.handle_generate_waterfall(
        {
            "height": 9.0,
            "width": 3.0,
            "allow_legacy_geometry_fallback": True,
        }
    )
    assert legacy["authoring_path"] == "legacy_geometry_fallback"


def test_handle_generate_waterfall_publishes_functional_contract():
    from blender_addon.handlers import environment as env_mod

    result = env_mod.handle_generate_waterfall(
        {
            "height": 11.0,
            "width": 4.0,
            "location": [3.0, 4.0, 5.0],
            "allow_legacy_geometry_fallback": True,
        }
    )

    assert result["functional_object_chain_id"] == "300_400_500"
    assert len(result["functional_object_names"]) == 7
    assert result["functional_objects"]["sheet_volume"] == "WF_300_400_500_sheet_volume"
    assert result["functional_object_contract_issues"] == []
    assert result["functional_object_positions"]["impact_pool"][0] == pytest.approx(3.0)


def test_handle_generate_waterfall_validates_authored_functional_names():
    from blender_addon.handlers import environment as env_mod

    result = env_mod.handle_generate_waterfall(
        {
            "height": 11.0,
            "width": 4.0,
            "location": [1.0, 2.0, 3.0],
            "allow_legacy_geometry_fallback": True,
            "functional_object_names": ["BadName"],
        }
    )

    issue_codes = {issue["code"] for issue in result["functional_object_contract_issues"]}
    assert "WATERFALL_OBJECT_WRONG_CHAIN" in issue_codes
    assert "WATERFALL_FUNCTIONAL_OBJECT_MISSING" in issue_codes

    def test_multi_biome_world_uses_mesh_backed_scatter_helper(self):
        from blender_addon.handlers import environment as env_mod

        class _ColorDatum:
            def __init__(self):
                self.color = None

        class _ColorAttr:
            def __init__(self, count):
                self.data = [_ColorDatum() for _ in range(count)]

        class _ColorAttributes:
            def __init__(self):
                self._attrs = {}

            def get(self, name):
                return self._attrs.get(name)

            def new(self, name, type, domain):
                attr = _ColorAttr(4)
                self._attrs[name] = attr
                return attr

            def remove(self, attr):
                for key, value in list(self._attrs.items()):
                    if value is attr:
                        del self._attrs[key]

        class _Mesh:
            def __init__(self):
                self.color_attributes = _ColorAttributes()
                self.vertices = [object(), object(), object(), object()]

        class _Obj:
            def __init__(self):
                self.data = _Mesh()

        class _Spec:
            def __init__(self):
                self.biome_names = ["thornwood_forest", "corrupted_swamp"]
                self.biome_ids = np.array([[0, 1], [1, 0]], dtype=np.int32)
                self.corruption_map = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float64)
                self.flatten_zones = [{"center": [0.0, 0.0], "radius": 10.0}]

        fake_obj = _Obj()
        scatter_calls = []
        terrain_calls = []

        def _fake_generate_terrain(params):
            terrain_calls.append(dict(params))
            return {"vertex_count": 4}

        with patch.object(env_mod, "handle_generate_terrain", side_effect=_fake_generate_terrain), \
             patch.object(env_mod, "_compute_vertex_colors_for_biome_map", return_value=[(1.0, 0.0, 0.0, 1.0)] * 4), \
             patch.object(env_mod.bpy.data.objects, "get", return_value=fake_obj), \
             patch("blender_addon.handlers._biome_grammar.generate_world_map_spec", return_value=_Spec()), \
             patch("blender_addon.handlers.terrain_materials.handle_create_biome_terrain", return_value={"status": "ok"}), \
             patch("blender_addon.handlers.vegetation_system.scatter_biome_vegetation", side_effect=lambda params: scatter_calls.append(params) or {"instance_count": 3}):
            result = env_mod.handle_generate_multi_biome_world(
                {
                    "name": "BiomeWorld",
                    "width": 2,
                    "height": 2,
                    "world_size": 128.0,
                    "scatter_vegetation": True,
                    "seed": 7,
                }
            )

        assert result["name"] == "BiomeWorld"
        assert result["vegetation_count"] == 6
        assert terrain_calls[0]["use_controller"] is True
        assert [call["biome_name"] for call in scatter_calls] == ["thornwood_forest", "corrupted_swamp"]


class TestExportHeightRangeResolution:
    def test_tiled_world_uses_shared_height_range(self):
        from blender_addon.handlers.environment import _resolve_export_height_range

        hmap = np.array([[10.0, 20.0], [30.0, 40.0]], dtype=np.float64)
        result = _resolve_export_height_range(
            {
                "tiled_world": True,
                "height_range": (0.0, 80.0),
            },
            hmap,
        )

        assert result == (0.0, 80.0)

    def test_legacy_export_defaults_to_local_range(self):
        from blender_addon.handlers.environment import _resolve_export_height_range

        hmap = np.array([[10.0, 20.0], [30.0, 40.0]], dtype=np.float64)
        result = _resolve_export_height_range({}, hmap)

        assert result is None


class TestRoadMaskPainting:
    def test_new_splatmap_stays_zero_outside_road(self):
        from blender_addon.handlers.environment import _paint_road_mask_on_terrain

        class _Vertex:
            def __init__(self, x, y, z=0.0):
                self.co = SimpleNamespace(x=x, y=y, z=z)

        class _Loop:
            def __init__(self, vertex_index):
                self.vertex_index = vertex_index

        class _ColorDatum:
            def __init__(self):
                self.color = (0.0, 0.0, 0.0, 0.0)

        class _ColorAttr:
            def __init__(self, count):
                self.data = [_ColorDatum() for _ in range(count)]

        class _ColorAttributes:
            def __init__(self):
                self._attrs = {}

            def get(self, name):
                return self._attrs.get(name)

            def new(self, name, type, domain):
                attr = _ColorAttr(4)
                self._attrs[name] = attr
                return attr

        class _Mesh:
            def __init__(self):
                self.vertices = [
                    _Vertex(0.0, 0.0),
                    _Vertex(2.0, 0.0),
                    _Vertex(100.0, 100.0),
                    _Vertex(102.0, 100.0),
                ]
                self.loops = [_Loop(0), _Loop(1), _Loop(2), _Loop(3)]
                self.color_attributes = _ColorAttributes()

        terrain_obj = SimpleNamespace(data=_Mesh(), matrix_world=None)

        _paint_road_mask_on_terrain(
            terrain_obj,
            [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
            road_half_width=1.0,
            shoulder_width=0.5,
            surface_key="dirt_path",
        )

        attr = terrain_obj.data.color_attributes.get("VB_TerrainSplatmap")
        assert attr is not None
        near_colors = [np.asarray(attr.data[i].color[:4], dtype=np.float32) for i in (0, 1)]
        far_colors = [np.asarray(attr.data[i].color[:4], dtype=np.float32) for i in (2, 3)]

        assert all(float(color.sum()) > 1e-6 for color in near_colors)
        assert all(float(color.sum()) <= 1e-6 for color in far_colors)


# ---------------------------------------------------------------------------
# Tiled terrain parameter resolution
# ---------------------------------------------------------------------------


class TestResolveTerrainTileParams:
    def test_defaults_compute_world_origin_and_center(self):
        from blender_addon.handlers.environment import _resolve_terrain_tile_params

        result = _resolve_terrain_tile_params({"tile_x": 1, "tile_y": 2})

        assert result["tile_size"] == 256
        assert result["resolution"] == 257
        assert result["world_origin_x"] == 256.0
        assert result["world_origin_y"] == 512.0
        assert result["terrain_size"] == 256.0
        assert result["object_location"] == (384.0, 640.0, 0.0)

    def test_explicit_resolution_derives_tile_size(self):
        from blender_addon.handlers.environment import _resolve_terrain_tile_params

        result = _resolve_terrain_tile_params({
            "tile_x": 3,
            "tile_y": 4,
            "resolution": 65,
            "cell_size": 2.0,
        })

        assert result["tile_size"] == 64
        assert result["resolution"] == 65
        assert result["terrain_size"] == 128.0
        assert result["world_origin_x"] == 384.0
        assert result["world_origin_y"] == 512.0
        assert result["object_location"] == (448.0, 576.0, 0.0)

    def test_resolution_tile_size_mismatch_raises(self):
        from blender_addon.handlers.environment import _resolve_terrain_tile_params

        with pytest.raises(ValueError, match="resolution must equal tile_size"):
            _resolve_terrain_tile_params({"tile_size": 64, "resolution": 63})


class TestTerrainWorldCoordinateHelpers:
    def test_grid_to_world_xy_respects_center_offset(self):
        from blender_addon.handlers.environment import _terrain_grid_to_world_xy

        start = _terrain_grid_to_world_xy(
            0,
            0,
            rows=3,
            cols=3,
            terrain_size=100.0,
            terrain_origin_x=150.0,
            terrain_origin_y=200.0,
        )
        center = _terrain_grid_to_world_xy(
            1,
            1,
            rows=3,
            cols=3,
            terrain_size=100.0,
            terrain_origin_x=150.0,
            terrain_origin_y=200.0,
        )
        end = _terrain_grid_to_world_xy(
            2,
            2,
            rows=3,
            cols=3,
            terrain_size=100.0,
            terrain_origin_x=150.0,
            terrain_origin_y=200.0,
        )

        assert start == (100.0, 150.0)
        assert center == (150.0, 200.0)
        assert end == (200.0, 250.0)

    def test_grid_to_world_xy_uses_rectangular_axes(self):
        from blender_addon.handlers.environment import _terrain_grid_to_world_xy

        start = _terrain_grid_to_world_xy(
            0,
            0,
            rows=3,
            cols=5,
            terrain_width=200.0,
            terrain_height=80.0,
            terrain_origin_x=10.0,
            terrain_origin_y=20.0,
        )
        center = _terrain_grid_to_world_xy(
            1,
            2,
            rows=3,
            cols=5,
            terrain_width=200.0,
            terrain_height=80.0,
            terrain_origin_x=10.0,
            terrain_origin_y=20.0,
        )
        end = _terrain_grid_to_world_xy(
            2,
            4,
            rows=3,
            cols=5,
            terrain_width=200.0,
            terrain_height=80.0,
            terrain_origin_x=10.0,
            terrain_origin_y=20.0,
        )

        assert start == (-90.0, -20.0)
        assert center == (10.0, 20.0)
        assert end == (110.0, 60.0)

    def test_resolve_water_path_points_defaults_to_offset_terrain_center(self):
        from blender_addon.handlers.environment import _resolve_water_path_points

        path = _resolve_water_path_points(
            path_points_raw=None,
            terrain_origin_x=320.0,
            terrain_origin_y=640.0,
            fallback_depth=100.0,
            water_level=3.0,
        )

        assert path == [
            (320.0, 590.0, 3.0),
            (320.0, 690.0, 3.0),
        ]

    def test_resolve_water_path_points_preserves_explicit_points(self):
        from blender_addon.handlers.environment import _resolve_water_path_points

        path = _resolve_water_path_points(
            path_points_raw=[[1, 2, 3], [4, 5, 6]],
            terrain_origin_x=320.0,
            terrain_origin_y=640.0,
            fallback_depth=100.0,
            water_level=3.0,
        )

        assert path == [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]


class TestRiverPathSmoothing:
    """River path smoothing should reduce stair-stepping and stay downhill."""

    def test_smooth_river_path_points_resamples_and_preserves_descent(self):
        from blender_addon.handlers.environment import _smooth_river_path_points

        path = [
            (0.0, 0.0, 12.0),
            (1.0, 0.0, 11.7),
            (1.0, 1.0, 11.4),
            (2.0, 1.0, 11.1),
            (2.0, 2.0, 10.8),
            (3.0, 2.0, 10.5),
            (3.0, 3.0, 10.2),
        ]

        smoothed = _smooth_river_path_points(path, enforce_monotonic_z=True)

        assert smoothed[0] == path[0]
        assert len(smoothed) <= len(path)
        assert all(
            later[2] <= earlier[2] + 1e-9
            for earlier, later in zip(smoothed, smoothed[1:])
        )
        assert any(
            abs(x - round(x)) > 1e-6 or abs(y - round(y)) > 1e-6
            for x, y, _ in smoothed[1:-1]
        ), "Expected smoothed river control points to move off the stair-step grid"


class TestRiverTerminalWidthTaper:
    def test_terminal_width_scale_narrows_endpoints_but_not_midstream(self):
        from blender_addon.handlers.environment import _resolve_river_terminal_width_scale

        scales = [
            _resolve_river_terminal_width_scale(i, 9, taper_rings=3)
            for i in range(9)
        ]

        assert scales[0] < scales[1] < scales[2] < 1.0
        assert scales[3] == pytest.approx(1.0)
        assert scales[4] == pytest.approx(1.0)
        assert scales[-1] == pytest.approx(scales[0])

    def test_terminal_width_scale_disables_cleanly(self):
        from blender_addon.handlers.environment import _resolve_river_terminal_width_scale

        assert _resolve_river_terminal_width_scale(0, 6, taper_rings=0) == pytest.approx(1.0)
        assert _resolve_river_terminal_width_scale(0, 2, taper_rings=3) == pytest.approx(1.0)


class TestRiverBankContactSolver:
    def test_solver_can_find_close_bank_contact_inside_default_half_width(self):
        from blender_addon.handlers.environment import _resolve_river_bank_contact

        def _sampler(x: float, y: float) -> float:
            return -1.5 if abs(x) < 0.6 else 1.25

        dist, terrain_z = _resolve_river_bank_contact(
            terrain_height_sampler=_sampler,
            center_x=0.0,
            center_y=0.0,
            surface_z=0.0,
            normal_x=1.0,
            normal_y=0.0,
            default_half_width=4.0,
            side_sign=1.0,
        )

        assert dist < 1.0
        assert terrain_z > 0.0


# ---------------------------------------------------------------------------
# _nearest_pot_plus_1 tests
# ---------------------------------------------------------------------------


class TestNearestPotPlus1:
    """Test power-of-two + 1 calculation for Unity compatibility."""

    def test_129_stays_129(self):
        """129 is already a POT+1 (128+1)."""
        from blender_addon.handlers.environment import _nearest_pot_plus_1

        assert _nearest_pot_plus_1(129) == 129

    def test_100_becomes_129(self):
        """100 rounds up to 129 (128+1)."""
        from blender_addon.handlers.environment import _nearest_pot_plus_1

        assert _nearest_pot_plus_1(100) == 129

    def test_257_stays_257(self):
        """257 is already a POT+1 (256+1)."""
        from blender_addon.handlers.environment import _nearest_pot_plus_1

        assert _nearest_pot_plus_1(257) == 257

    def test_513_stays_513(self):
        """513 is already a POT+1 (512+1)."""
        from blender_addon.handlers.environment import _nearest_pot_plus_1

        assert _nearest_pot_plus_1(513) == 513

    def test_3_becomes_3(self):
        """3 is already a POT+1 (2+1)."""
        from blender_addon.handlers.environment import _nearest_pot_plus_1

        assert _nearest_pot_plus_1(3) == 3

    def test_65_becomes_65(self):
        """65 is already a POT+1 (64+1)."""
        from blender_addon.handlers.environment import _nearest_pot_plus_1

        assert _nearest_pot_plus_1(65) == 65

    def test_50_becomes_65(self):
        """50 rounds up to 65 (64+1)."""
        from blender_addon.handlers.environment import _nearest_pot_plus_1

        assert _nearest_pot_plus_1(50) == 65


# ---------------------------------------------------------------------------
# VB biome preset tests
# ---------------------------------------------------------------------------


class TestVBBiomePresets:
    """Test VeilBreakers biome preset lookup and structure."""

    VB_BIOME_NAMES = [
        "thornwood_forest",
        "corrupted_swamp",
        "mountain_pass",
        "ruined_fortress",
        "abandoned_village",
        "veil_crack_zone",
        "underground_dungeon",
        "sacred_shrine",
        "battlefield",
        "cemetery",
    ]

    def test_has_ten_biome_presets(self):
        """VB_BIOME_PRESETS contains exactly 10 biomes."""
        from blender_addon.handlers.environment import VB_BIOME_PRESETS

        assert len(VB_BIOME_PRESETS) == 10

    def test_all_biome_names_present(self):
        """All expected VeilBreakers biome names are present."""
        from blender_addon.handlers.environment import VB_BIOME_PRESETS

        for name in self.VB_BIOME_NAMES:
            assert name in VB_BIOME_PRESETS, f"Missing biome: {name}"

    def test_all_biomes_have_required_keys(self):
        """Every biome preset has terrain_type, resolution, height_scale, erosion, scatter_rules."""
        from blender_addon.handlers.environment import VB_BIOME_PRESETS

        required_keys = {"terrain_type", "resolution", "height_scale", "erosion", "scatter_rules"}
        for name, preset in VB_BIOME_PRESETS.items():
            for key in required_keys:
                assert key in preset, f"Biome '{name}' missing key '{key}'"

    def test_all_biome_terrain_types_are_valid(self):
        """Every biome's terrain_type maps to a valid TERRAIN_PRESETS entry."""
        from blender_addon.handlers.environment import VB_BIOME_PRESETS
        from blender_addon.handlers._terrain_noise import TERRAIN_PRESETS

        for name, preset in VB_BIOME_PRESETS.items():
            assert preset["terrain_type"] in TERRAIN_PRESETS, (
                f"Biome '{name}' terrain_type '{preset['terrain_type']}' "
                f"not in TERRAIN_PRESETS"
            )

    def test_scatter_rules_have_required_keys(self):
        """Every scatter rule has asset, density, min_distance, scale_range."""
        from blender_addon.handlers.environment import VB_BIOME_PRESETS

        rule_keys = {"asset", "density", "min_distance", "scale_range"}
        for name, preset in VB_BIOME_PRESETS.items():
            for i, rule in enumerate(preset["scatter_rules"]):
                for key in rule_keys:
                    assert key in rule, (
                        f"Biome '{name}' scatter_rule[{i}] missing key '{key}'"
                    )

    def test_scatter_rules_scale_range_is_two_element_list(self):
        """scale_range is a list of exactly 2 floats [min, max]."""
        from blender_addon.handlers.environment import VB_BIOME_PRESETS

        for name, preset in VB_BIOME_PRESETS.items():
            for i, rule in enumerate(preset["scatter_rules"]):
                sr = rule["scale_range"]
                assert len(sr) == 2, (
                    f"Biome '{name}' rule[{i}] scale_range has {len(sr)} elements"
                )
                assert sr[0] <= sr[1], (
                    f"Biome '{name}' rule[{i}] scale_range min > max"
                )

    def test_get_vb_biome_preset_returns_copy(self):
        """get_vb_biome_preset returns an independent copy."""
        from blender_addon.handlers.environment import get_vb_biome_preset, VB_BIOME_PRESETS

        preset = get_vb_biome_preset("thornwood_forest")
        assert preset is not None
        # Mutate the copy and verify original is unchanged
        preset["resolution"] = 9999
        assert VB_BIOME_PRESETS["thornwood_forest"]["resolution"] != 9999

    def test_thornwood_forest_uses_progression_tree_assets(self):
        from blender_addon.handlers.environment import VB_BIOME_PRESETS

        assets = {rule["asset"] for rule in VB_BIOME_PRESETS["thornwood_forest"]["scatter_rules"]}
        assert "tree_healthy" in assets
        assert "tree_boundary" in assets
        assert "tree_blighted" in assets

    def test_get_vb_biome_preset_returns_none_for_unknown(self):
        """get_vb_biome_preset returns None for unknown biome name."""
        from blender_addon.handlers.environment import get_vb_biome_preset

        assert get_vb_biome_preset("nonexistent_biome") is None
        assert get_vb_biome_preset("") is None

    def test_get_vb_biome_preset_all_biomes(self):
        """get_vb_biome_preset returns a dict for every known biome."""
        from blender_addon.handlers.environment import get_vb_biome_preset

        for name in self.VB_BIOME_NAMES:
            preset = get_vb_biome_preset(name)
            assert isinstance(preset, dict), f"get_vb_biome_preset('{name}') returned {type(preset)}"

    def test_biome_preset_resolves_in_validate(self):
        """A biome name resolves to valid terrain params via _validate_terrain_params.

        The handler builds effective params from the preset before validation,
        so here we simulate that resolution.
        """
        from blender_addon.handlers.environment import (
            get_vb_biome_preset,
            _validate_terrain_params,
        )

        for name in self.VB_BIOME_NAMES:
            preset = get_vb_biome_preset(name)
            # Build the effective params dict as the handler would
            effective = {
                "terrain_type": preset["terrain_type"],
                "resolution": preset["resolution"],
                "height_scale": preset["height_scale"],
            }
            if preset.get("erosion"):
                effective["erosion"] = "hydraulic"
                effective["erosion_iterations"] = preset.get("erosion_iterations", 5000)
            else:
                effective["erosion"] = "none"
            result = _validate_terrain_params(effective)
            assert result["terrain_type"] == preset["terrain_type"]
            assert result["resolution"] == preset["resolution"]
            assert result["height_scale"] == preset["height_scale"]

    def test_biome_explicit_override(self):
        """Explicit params override biome preset defaults.

        Simulates the handler's param merge logic.
        """
        from blender_addon.handlers.environment import (
            get_vb_biome_preset,
            _validate_terrain_params,
        )

        preset = get_vb_biome_preset("cemetery")
        assert preset is not None
        # Override resolution and height_scale
        effective = {
            "terrain_type": preset["terrain_type"],
            "resolution": 1024,
            "height_scale": 50.0,
            "erosion": "none",
        }
        result = _validate_terrain_params(effective)
        assert result["resolution"] == 1024
        assert result["height_scale"] == 50.0
