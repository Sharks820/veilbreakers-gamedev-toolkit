"""Unit tests for worldbuilding handler pure-logic outputs.

Tests _building_ops_to_mesh_spec conversion and handler return shapes
without Blender.
"""

import math
import pytest


# ---------------------------------------------------------------------------
# _building_ops_to_mesh_spec tests
# ---------------------------------------------------------------------------


class TestBuildingOpsToMeshSpec:
    """Test pure-logic conversion of BuildingSpec operations to mesh primitives."""

    def test_returns_list(self):
        """_building_ops_to_mesh_spec returns a list of mesh primitive specs."""
        from blender_addon.handlers._building_grammar import evaluate_building_grammar
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        result = _building_ops_to_mesh_spec(spec)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_box_operation_produces_8_verts_6_faces(self):
        """A 'box' type operation produces 8 vertices and 6 faces."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        spec = BuildingSpec(
            footprint=(10, 8),
            floors=1,
            style="medieval",
            operations=[
                {
                    "type": "box",
                    "position": [0, 0, 0],
                    "size": [10, 8, 0.3],
                    "material": "stone",
                    "role": "foundation",
                }
            ],
        )
        result = _building_ops_to_mesh_spec(spec)
        assert len(result) == 1
        assert result[0]["vertex_count"] == 8
        assert result[0]["face_count"] == 6

    def test_cylinder_operation_produces_correct_vertex_count(self):
        """A 'cylinder' operation produces correct vertex count for given segments."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        segments = 16
        spec = BuildingSpec(
            footprint=(6, 6),
            floors=1,
            style="fortress",
            operations=[
                {
                    "type": "cylinder",
                    "position": [0, 0, 0],
                    "radius": 3.0,
                    "height": 10.0,
                    "segments": segments,
                    "material": "stone",
                    "role": "tower",
                }
            ],
        )
        result = _building_ops_to_mesh_spec(spec)
        assert len(result) == 1
        # Cylinder: segments verts on top ring + segments verts on bottom ring
        expected_verts = segments * 2
        assert result[0]["vertex_count"] == expected_verts

    def test_opening_operation_flagged_for_subtract(self):
        """An 'opening' operation is flagged as a boolean subtract or face construction."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        spec = BuildingSpec(
            footprint=(10, 8),
            floors=1,
            style="medieval",
            operations=[
                {
                    "type": "opening",
                    "wall_index": 0,
                    "position": [2.0, 1.0],
                    "size": [1.2, 2.2],
                    "role": "door",
                }
            ],
        )
        result = _building_ops_to_mesh_spec(spec)
        assert len(result) == 1
        assert result[0]["type"] == "opening"
        assert "subtract" in result[0] or "face_construction" in result[0]

    def test_opening_cutout_clamps_to_wall_bounds(self):
        """Oversized openings are clamped to the parent wall volume."""
        from blender_addon.handlers.worldbuilding import _opening_to_cutout_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        spec = BuildingSpec(
            footprint=(10, 8),
            floors=1,
            style="medieval",
            operations=[
                {
                    "type": "box",
                    "position": [0.0, 0.0, 0.0],
                    "size": [10.0, 0.4, 3.0],
                    "material": "stone",
                    "role": "wall",
                },
                {
                    "type": "opening",
                    "wall_index": 0,
                    "position": [2.0, 0.5],
                    "size": [20.0, 5.0],
                    "role": "door",
                },
            ],
        )
        wall_ops = {
            (0, 0): {
                "type": "box",
                "position": [0.0, 0.0, 0.0],
                "size": [10.0, 0.4, 3.0],
            }
        }
        opening = _opening_to_cutout_spec(spec.operations[1], wall_ops, spec)
        assert opening is not None
        xs = [v[0] for v in opening["vertices"]]
        ys = [v[1] for v in opening["vertices"]]
        zs = [v[2] for v in opening["vertices"]]
        assert max(xs) - min(xs) <= 9.9
        assert max(ys) - min(ys) <= 0.4
        assert max(zs) - min(zs) <= 2.9


# ---------------------------------------------------------------------------
# Handler return shape tests (pure-logic verification of output dicts)
# ---------------------------------------------------------------------------


class TestHandlerReturnShapes:
    """Test that handler helper functions produce correctly-shaped output dicts."""

    def test_building_result_keys(self):
        """_build_building_result returns dict with expected keys."""
        from blender_addon.handlers.worldbuilding import _build_building_result
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        result = _build_building_result("TestBuilding", spec)
        expected_keys = {"name", "style", "floors", "footprint", "vertex_count", "face_count", "material_count"}
        assert expected_keys.issubset(set(result.keys()))

    def test_building_result_tracks_geometry_quality(self):
        """_build_building_result returns geometry completeness metadata."""
        from blender_addon.handlers.worldbuilding import _build_building_result
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        result = _build_building_result("TestBuilding", spec)
        assert result["geometry_quality"] in {"complete", "partial"}
        assert "opening_marker_count" in result
        assert "geometry_issues" in result

    def test_castle_result_keys(self):
        """_build_castle_result returns dict with expected keys."""
        from blender_addon.handlers.worldbuilding import _build_castle_result
        from blender_addon.handlers._building_grammar import generate_castle_spec

        spec = generate_castle_spec(seed=0)
        result = _build_castle_result("TestCastle", spec)
        expected_keys = {"name", "component_count", "opening_count", "geometry_quality"}
        assert expected_keys.issubset(set(result.keys()))

    def test_castle_component_count(self):
        """Castle component_count includes keep + walls + towers + gate."""
        from blender_addon.handlers.worldbuilding import _build_castle_result
        from blender_addon.handlers._building_grammar import generate_castle_spec

        spec = generate_castle_spec(seed=0)
        result = _build_castle_result("TestCastle", spec)
        assert result["component_count"] > 0
        assert result["geometry_quality"] == "complete"

    def test_ruins_result_keys(self):
        """_build_ruins_result returns dict with expected keys."""
        from blender_addon.handlers.worldbuilding import _build_ruins_result
        from blender_addon.handlers._building_grammar import (
            evaluate_building_grammar,
            apply_ruins_damage,
        )

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        damaged = apply_ruins_damage(spec, damage_level=0.5, seed=0)
        result = _build_ruins_result("TestRuins", damaged, "medieval", 0.5)
        expected_keys = {"name", "original_style", "damage_level", "debris_count"}
        assert expected_keys.issubset(set(result.keys()))

    def test_ruins_debris_count(self):
        """Ruins debris_count is positive for moderate damage."""
        from blender_addon.handlers.worldbuilding import _build_ruins_result
        from blender_addon.handlers._building_grammar import (
            evaluate_building_grammar,
            apply_ruins_damage,
        )

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        damaged = apply_ruins_damage(spec, damage_level=0.5, seed=0)
        result = _build_ruins_result("TestRuins", damaged, "medieval", 0.5)
        assert result["debris_count"] > 0

    def test_live_building_quality_summary(self):
        """Live build quality summary should flag missing essentials."""
        from blender_addon.handlers.worldbuilding import _summarize_live_building_quality

        complete = _summarize_live_building_quality(
            expected_openings=3,
            door_count=1,
            window_count=2,
            wall_segment_count=8,
            foundation_piece_count=2,
            roof_created=True,
            component_count=12,
        )
        assert complete["geometry_quality"] == "complete"
        assert complete["geometry_issues"] == []

        partial = _summarize_live_building_quality(
            expected_openings=2,
            door_count=1,
            window_count=0,
            wall_segment_count=0,
            foundation_piece_count=0,
            roof_created=False,
            component_count=0,
        )
        assert partial["geometry_quality"] == "partial"
        assert len(partial["geometry_issues"]) >= 3

    def test_interior_result_keys(self):
        """_build_interior_result returns dict with expected keys."""
        from blender_addon.handlers.worldbuilding import _build_interior_result
        from blender_addon.handlers._building_grammar import generate_interior_layout

        layout = generate_interior_layout(room_type="tavern", width=8, depth=6, seed=0)
        result = _build_interior_result("TestInterior", "tavern", layout)
        expected_keys = {"name", "room_type", "furniture_count", "items"}
        assert expected_keys.issubset(set(result.keys()))

    def test_interior_items_list(self):
        """Interior items is a list of placed item names."""
        from blender_addon.handlers.worldbuilding import _build_interior_result
        from blender_addon.handlers._building_grammar import generate_interior_layout

        layout = generate_interior_layout(room_type="tavern", width=8, depth=6, seed=0)
        result = _build_interior_result("TestInterior", "tavern", layout)
        assert isinstance(result["items"], list)
        assert len(result["items"]) > 0
        assert all(isinstance(name, str) for name in result["items"])

    def test_modular_kit_result_keys(self):
        """_build_modular_kit_result returns dict with expected keys."""
        from blender_addon.handlers.worldbuilding import _build_modular_kit_result
        from blender_addon.handlers._building_grammar import generate_modular_pieces

        pieces = generate_modular_pieces(cell_size=2.0, pieces=["wall_straight", "floor"])
        result = _build_modular_kit_result(pieces, 2.0)
        expected_keys = {"piece_count", "pieces", "cell_size"}
        assert expected_keys.issubset(set(result.keys()))

    def test_modular_kit_piece_names(self):
        """Modular kit pieces list contains piece names."""
        from blender_addon.handlers.worldbuilding import _build_modular_kit_result
        from blender_addon.handlers._building_grammar import generate_modular_pieces

        pieces = generate_modular_pieces(cell_size=2.0, pieces=["wall_straight", "floor"])
        result = _build_modular_kit_result(pieces, 2.0)
        assert "wall_straight" in result["pieces"]
        assert "floor" in result["pieces"]

    def test_modular_kit_cell_size(self):
        """Modular kit result includes the requested cell_size."""
        from blender_addon.handlers.worldbuilding import _build_modular_kit_result
        from blender_addon.handlers._building_grammar import generate_modular_pieces

        pieces = generate_modular_pieces(cell_size=3.0, pieces=["wall_straight"])
        result = _build_modular_kit_result(pieces, 3.0)
        assert result["cell_size"] == 3.0


# ---------------------------------------------------------------------------
# Mesh spec geometry correctness
# ---------------------------------------------------------------------------


class TestMeshSpecGeometry:
    """Test geometry correctness of converted mesh specs."""

    def test_box_verts_match_position_and_size(self):
        """Box vertices span from position to position+size."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        pos = [1.0, 2.0, 3.0]
        size = [4.0, 5.0, 6.0]
        spec = BuildingSpec(
            footprint=(4, 5),
            floors=1,
            style="medieval",
            operations=[
                {
                    "type": "box",
                    "position": pos,
                    "size": size,
                    "material": "stone",
                    "role": "foundation",
                }
            ],
        )
        result = _building_ops_to_mesh_spec(spec)
        verts = result[0]["vertices"]
        # All x-coordinates should be between pos[0] and pos[0]+size[0]
        xs = [v[0] for v in verts]
        assert min(xs) == pytest.approx(pos[0], abs=1e-6)
        assert max(xs) == pytest.approx(pos[0] + size[0], abs=1e-6)

    def test_cylinder_verts_form_circles(self):
        """Cylinder vertices form two circles at correct height."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        radius = 3.0
        height = 10.0
        segments = 8
        spec = BuildingSpec(
            footprint=(6, 6),
            floors=1,
            style="fortress",
            operations=[
                {
                    "type": "cylinder",
                    "position": [0, 0, 0],
                    "radius": radius,
                    "height": height,
                    "segments": segments,
                    "material": "stone",
                    "role": "tower",
                }
            ],
        )
        result = _building_ops_to_mesh_spec(spec)
        verts = result[0]["vertices"]
        # Check all vertex distances from center match radius (within tolerance)
        for v in verts:
            dist = math.sqrt(v[0] ** 2 + v[1] ** 2)
            assert dist == pytest.approx(radius, abs=1e-6)

    def test_full_building_mesh_spec_has_multiple_primitives(self):
        """A full building spec produces multiple mesh primitives."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        result = _building_ops_to_mesh_spec(spec)
        assert len(result) > 1


# ---------------------------------------------------------------------------
# Opening-aware wall planning
# ---------------------------------------------------------------------------


class TestOpeningAwareWallPlanning:
    """Test deterministic wall opening planning for runtime buildings."""

    def test_resolve_building_openings_uses_side_wall_presets(self):
        """Preset openings on left/right/back walls must survive resolution."""
        from blender_addon.handlers.worldbuilding import _resolve_building_openings

        openings = _resolve_building_openings(
            width=8.0,
            depth=10.0,
            floors=2,
            wall_height=4.0,
            wall_thickness=0.4,
            style="gothic",
            requested_openings=[
                {"type": "door", "wall": "front", "floor": 0, "style": "pointed_arch"},
                {"type": "window", "wall": "left", "floor": 0, "style": "pointed_arch"},
                {"type": "window", "wall": "right", "floor": 0, "style": "pointed_arch"},
                {"type": "window", "wall": "back", "floor": 1, "style": "rose_window"},
            ],
        )

        walls = {(opening["wall"], opening["floor"]) for opening in openings}
        assert ("front", 0) in walls
        assert ("left", 0) in walls
        assert ("right", 0) in walls
        assert ("back", 1) in walls

    def test_default_resolved_openings_cover_side_walls(self):
        """Default building openings should not be limited to front/back walls."""
        from blender_addon.handlers.worldbuilding import _resolve_building_openings

        openings = _resolve_building_openings(
            width=10.0,
            depth=8.0,
            floors=1,
            wall_height=4.0,
            wall_thickness=0.4,
            style="medieval",
            requested_openings=[],
        )

        wall_names = {opening["wall"] for opening in openings}
        assert {"front", "back", "left", "right"}.issubset(wall_names)
        assert any(opening["kind"] == "door" and opening["wall"] == "front" for opening in openings)

    def test_resolved_openings_stay_player_usable(self):
        """Procedural doors and windows should not collapse below usable scale."""
        from blender_addon.handlers.worldbuilding import _resolve_building_openings

        openings = _resolve_building_openings(
            width=6.0,
            depth=6.0,
            floors=1,
            wall_height=3.2,
            wall_thickness=0.4,
            style="medieval",
            requested_openings=[],
        )

        for opening in openings:
            if opening["kind"] == "door":
                assert opening["width"] >= 1.2
                assert opening["height"] >= 2.2

    def test_compute_wall_segments_leave_true_open_holes(self):
        """Solid wall segments must not overlap the requested opening rectangles."""
        from blender_addon.handlers.worldbuilding import _compute_wall_segments

        openings = [
            {"kind": "door", "center": 5.0, "width": 1.4, "bottom": 0.0, "height": 2.4},
            {"kind": "window", "center": 2.1, "width": 0.9, "bottom": 1.2, "height": 1.3},
        ]
        segments, clamped = _compute_wall_segments(10.0, 4.0, openings)

        assert len(segments) > 1
        assert len(clamped) == 2

        for segment in segments:
            for opening in clamped:
                overlaps_x = segment["u0"] < opening["u1"] and segment["u1"] > opening["u0"]
                overlaps_z = segment["v0"] < opening["v1"] and segment["v1"] > opening["v0"]
                assert not (overlaps_x and overlaps_z), (
                    f"segment {segment} overlaps opening {opening}"
                )

    def test_structure_origin_from_center_preserves_anchor_for_unrotated_shell(self):
        """Settlement placement should convert center anchors into shell origins."""
        from blender_addon.handlers.worldbuilding import _structure_origin_from_center

        origin = _structure_origin_from_center((10.0, 12.0), (8.0, 6.0), 0.0)
        assert origin == pytest.approx((6.0, 9.0), abs=1e-6)

    def test_structure_origin_from_center_handles_rotation(self):
        """Rotated shells still need their local center aligned to the target anchor."""
        from blender_addon.handlers.worldbuilding import _structure_origin_from_center

        origin_x, origin_y = _structure_origin_from_center((0.0, 0.0), (8.0, 4.0), math.pi / 2.0)
        center_local = (4.0, 2.0)
        world_center = (
            origin_x + center_local[0] * math.cos(math.pi / 2.0) - center_local[1] * math.sin(math.pi / 2.0),
            origin_y + center_local[0] * math.sin(math.pi / 2.0) + center_local[1] * math.cos(math.pi / 2.0),
        )
        assert world_center == pytest.approx((0.0, 0.0), abs=1e-6)


# ---------------------------------------------------------------------------
# Scene sampling / cleanup helpers
# ---------------------------------------------------------------------------


class TestWorldbuildingFallbackHelpers:
    """Test non-fatal worldbuilding fallbacks keep working and log failures."""

    def test_sample_scene_height_logs_and_falls_back_when_raycast_fails(self, caplog, monkeypatch):
        """_sample_scene_height should log and return 0.0 when ray_cast fails."""
        import sys
        from types import SimpleNamespace

        from blender_addon.handlers import worldbuilding

        monkeypatch.setattr(
            sys.modules["mathutils"],
            "Vector",
            lambda values: tuple(values),
            raising=False,
        )
        monkeypatch.setattr(
            worldbuilding.bpy,
            "context",
            SimpleNamespace(
                evaluated_depsgraph_get=lambda: object(),
                scene=SimpleNamespace(
                    ray_cast=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("ray cast unavailable"))
                ),
            ),
            raising=False,
        )

        with caplog.at_level("DEBUG", logger=worldbuilding.logger.name):
            result = worldbuilding._sample_scene_height(12.5, -4.0, "TestTerrain")

        assert result == 0.0
        assert "Scene height sampling failed" in caplog.text

    def test_clear_material_slots_logs_and_returns_false_on_failure(self, caplog):
        """_clear_material_slots should log non-fatal failures instead of swallowing them."""
        from types import SimpleNamespace

        from blender_addon.handlers.worldbuilding import _clear_material_slots, logger

        class _BrokenMaterials:
            def clear(self):
                raise RuntimeError("clear failed")

        obj = SimpleNamespace(name="Road", data=SimpleNamespace(materials=_BrokenMaterials()))

        with caplog.at_level("DEBUG", logger=logger.name):
            result = _clear_material_slots(obj, context="road cleanup")

        assert result is False
        assert "Failed to clear materials" in caplog.text


# ---------------------------------------------------------------------------
# VB Building Preset tests
# ---------------------------------------------------------------------------


class TestVBBuildingPresets:
    """Test VeilBreakers building preset data and lookup helpers."""

    def test_presets_dict_has_five_entries(self):
        """VB_BUILDING_PRESETS should include the AAA preset set."""
        from blender_addon.handlers.worldbuilding import VB_BUILDING_PRESETS

        assert len(VB_BUILDING_PRESETS) >= 10

    def test_preset_names(self):
        """All core and extended VB building preset names are present."""
        from blender_addon.handlers.worldbuilding import VB_BUILDING_PRESETS

        expected = {
            "shrine_minor", "shrine_major", "ruined_fortress_tower",
            "abandoned_house", "forge", "inn", "warehouse", "barracks",
            "gatehouse", "rowhouse",
        }
        assert expected.issubset(set(VB_BUILDING_PRESETS.keys()))

    def test_each_preset_has_required_keys(self):
        """Every VB building preset must have style, floors, width, depth."""
        from blender_addon.handlers.worldbuilding import VB_BUILDING_PRESETS

        required = {"style", "floors", "width", "depth"}
        for name, preset in VB_BUILDING_PRESETS.items():
            missing = required - set(preset.keys())
            assert not missing, f"Preset '{name}' missing keys: {missing}"

    def test_each_preset_has_valid_style(self):
        """Every VB building preset style must exist in STYLE_CONFIGS."""
        from blender_addon.handlers.worldbuilding import VB_BUILDING_PRESETS
        from blender_addon.handlers._building_grammar import STYLE_CONFIGS

        for name, preset in VB_BUILDING_PRESETS.items():
            assert preset["style"] in STYLE_CONFIGS, (
                f"Preset '{name}' has invalid style '{preset['style']}'"
            )

    def test_each_preset_has_props_list(self):
        """Every VB building preset must have a non-empty props list."""
        from blender_addon.handlers.worldbuilding import VB_BUILDING_PRESETS

        for name, preset in VB_BUILDING_PRESETS.items():
            assert isinstance(preset.get("props"), list), f"Preset '{name}' missing props"
            assert len(preset["props"]) > 0, f"Preset '{name}' has empty props"

    def test_each_preset_has_openings_list(self):
        """Every VB building preset must have a non-empty openings list."""
        from blender_addon.handlers.worldbuilding import VB_BUILDING_PRESETS

        for name, preset in VB_BUILDING_PRESETS.items():
            assert isinstance(preset.get("openings"), list), f"Preset '{name}' missing openings"
            assert len(preset["openings"]) > 0, f"Preset '{name}' has empty openings"

    def test_shrine_minor_is_gothic_one_floor(self):
        """shrine_minor preset is gothic, 1 floor, 4x4."""
        from blender_addon.handlers.worldbuilding import VB_BUILDING_PRESETS

        p = VB_BUILDING_PRESETS["shrine_minor"]
        assert p["style"] == "gothic"
        assert p["floors"] == 1
        assert p["width"] == 4.0
        assert p["depth"] == 4.0

    def test_shrine_major_is_gothic_two_floors(self):
        """shrine_major preset is gothic, 2 floors, 8x10."""
        from blender_addon.handlers.worldbuilding import VB_BUILDING_PRESETS

        p = VB_BUILDING_PRESETS["shrine_major"]
        assert p["style"] == "gothic"
        assert p["floors"] == 2
        assert p["width"] == 8.0
        assert p["depth"] == 10.0

    def test_ruined_fortress_tower_no_roof(self):
        """ruined_fortress_tower preset has no roof (ruined)."""
        from blender_addon.handlers.worldbuilding import VB_BUILDING_PRESETS

        p = VB_BUILDING_PRESETS["ruined_fortress_tower"]
        assert p["has_roof"] is False
        assert p["floors"] == 3

    def test_forge_uses_fortress_style(self):
        """Forge preset uses fortress style (closest to industrial)."""
        from blender_addon.handlers.worldbuilding import VB_BUILDING_PRESETS

        p = VB_BUILDING_PRESETS["forge"]
        assert p["style"] == "fortress"
        assert "anvil" in p["props"]

    def test_get_vb_building_preset_returns_dict(self):
        """get_vb_building_preset returns dict for valid name."""
        from blender_addon.handlers.worldbuilding import get_vb_building_preset

        result = get_vb_building_preset("shrine_minor")
        assert isinstance(result, dict)
        assert result["style"] == "gothic"

    def test_get_vb_building_preset_returns_none_for_unknown(self):
        """get_vb_building_preset returns None for unknown name."""
        from blender_addon.handlers.worldbuilding import get_vb_building_preset

        assert get_vb_building_preset("nonexistent_building") is None

    def test_preset_produces_valid_building_spec(self):
        """A VB building preset produces a valid BuildingSpec when evaluated."""
        from blender_addon.handlers.worldbuilding import VB_BUILDING_PRESETS
        from blender_addon.handlers._building_grammar import evaluate_building_grammar, BuildingSpec

        for name, preset in VB_BUILDING_PRESETS.items():
            spec = evaluate_building_grammar(
                width=preset["width"],
                depth=preset["depth"],
                floors=preset["floors"],
                style=preset["style"],
                seed=42,
            )
            assert isinstance(spec, BuildingSpec), f"Preset '{name}' failed spec generation"
            assert len(spec.operations) > 0, f"Preset '{name}' produced empty operations"

    def test_preset_mesh_spec_has_geometry(self):
        """A VB building preset produces mesh specs with geometry."""
        from blender_addon.handlers.worldbuilding import VB_BUILDING_PRESETS, _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        for name, preset in VB_BUILDING_PRESETS.items():
            spec = evaluate_building_grammar(
                width=preset["width"],
                depth=preset["depth"],
                floors=preset["floors"],
                style=preset["style"],
                seed=42,
            )
            mesh_specs = _building_ops_to_mesh_spec(spec)
            assert len(mesh_specs) > 0, f"Preset '{name}' produced empty mesh specs"

    def test_opening_styles_in_presets(self):
        """Each opening in a preset has required keys: type, wall, floor, style."""
        from blender_addon.handlers.worldbuilding import VB_BUILDING_PRESETS

        required_keys = {"type", "wall", "floor", "style"}
        for name, preset in VB_BUILDING_PRESETS.items():
            for i, opening in enumerate(preset["openings"]):
                missing = required_keys - set(opening.keys())
                assert not missing, (
                    f"Preset '{name}' opening {i} missing keys: {missing}"
                )


# ---------------------------------------------------------------------------
# VB Dungeon Preset tests
# ---------------------------------------------------------------------------


class TestVBDungeonPresets:
    """Test VeilBreakers dungeon preset data and lookup helpers."""

    def test_presets_dict_has_four_entries(self):
        """VB_DUNGEON_PRESETS must have exactly 4 presets."""
        from blender_addon.handlers.worldbuilding import VB_DUNGEON_PRESETS

        assert len(VB_DUNGEON_PRESETS) == 4

    def test_preset_names(self):
        """All expected VB dungeon preset names are present."""
        from blender_addon.handlers.worldbuilding import VB_DUNGEON_PRESETS

        expected = {
            "abandoned_prison", "corrupted_cave", "storm_peak", "veil_tear_dungeon",
        }
        assert set(VB_DUNGEON_PRESETS.keys()) == expected

    def test_each_preset_has_required_keys(self):
        """Every VB dungeon preset must have width, height, min_room_size, max_depth, cell_size, wall_height."""
        from blender_addon.handlers.worldbuilding import VB_DUNGEON_PRESETS

        required = {"width", "height", "min_room_size", "max_depth", "cell_size", "wall_height"}
        for name, preset in VB_DUNGEON_PRESETS.items():
            missing = required - set(preset.keys())
            assert not missing, f"Preset '{name}' missing keys: {missing}"

    def test_each_preset_has_monster_table(self):
        """Every VB dungeon preset must have a non-empty monster_table list."""
        from blender_addon.handlers.worldbuilding import VB_DUNGEON_PRESETS

        for name, preset in VB_DUNGEON_PRESETS.items():
            assert isinstance(preset.get("monster_table"), list), f"Preset '{name}' missing monster_table"
            assert len(preset["monster_table"]) > 0, f"Preset '{name}' has empty monster_table"

    def test_each_preset_has_props_list(self):
        """Every VB dungeon preset must have a non-empty props list."""
        from blender_addon.handlers.worldbuilding import VB_DUNGEON_PRESETS

        for name, preset in VB_DUNGEON_PRESETS.items():
            assert isinstance(preset.get("props"), list), f"Preset '{name}' missing props"
            assert len(preset["props"]) > 0, f"Preset '{name}' has empty props"

    def test_each_preset_has_room_types(self):
        """Every VB dungeon preset must have a room_types dict."""
        from blender_addon.handlers.worldbuilding import VB_DUNGEON_PRESETS

        for name, preset in VB_DUNGEON_PRESETS.items():
            assert isinstance(preset.get("room_types"), dict), f"Preset '{name}' missing room_types"
            assert "entrance" in preset["room_types"], f"Preset '{name}' room_types lacks entrance"
            assert "boss" in preset["room_types"], f"Preset '{name}' room_types lacks boss"

    def test_abandoned_prison_values(self):
        """abandoned_prison preset has expected dimensions."""
        from blender_addon.handlers.worldbuilding import VB_DUNGEON_PRESETS

        p = VB_DUNGEON_PRESETS["abandoned_prison"]
        assert p["width"] == 40
        assert p["height"] == 40
        assert p["wall_height"] == 3.0
        assert "chainbound" in p["monster_table"]

    def test_veil_tear_dungeon_largest(self):
        """veil_tear_dungeon is the largest with deepest BSP."""
        from blender_addon.handlers.worldbuilding import VB_DUNGEON_PRESETS

        p = VB_DUNGEON_PRESETS["veil_tear_dungeon"]
        assert p["width"] == 45
        assert p["max_depth"] == 7
        assert p["wall_height"] == 6.0
        assert "void_crystal" in p["props"]

    def test_corrupted_cave_larger_cells(self):
        """corrupted_cave has larger cell_size for organic feel."""
        from blender_addon.handlers.worldbuilding import VB_DUNGEON_PRESETS

        p = VB_DUNGEON_PRESETS["corrupted_cave"]
        assert p["cell_size"] == 2.5

    def test_get_vb_dungeon_preset_returns_dict(self):
        """get_vb_dungeon_preset returns dict for valid name."""
        from blender_addon.handlers.worldbuilding import get_vb_dungeon_preset

        result = get_vb_dungeon_preset("storm_peak")
        assert isinstance(result, dict)
        assert result["width"] == 35

    def test_get_vb_dungeon_preset_returns_none_for_unknown(self):
        """get_vb_dungeon_preset returns None for unknown name."""
        from blender_addon.handlers.worldbuilding import get_vb_dungeon_preset

        assert get_vb_dungeon_preset("nonexistent_dungeon") is None

    def test_preset_generates_valid_dungeon(self):
        """A VB dungeon preset can produce a valid multi-floor dungeon."""
        from blender_addon.handlers.worldbuilding import VB_DUNGEON_PRESETS
        from blender_addon.handlers._dungeon_gen import generate_multi_floor_dungeon

        for name, preset in VB_DUNGEON_PRESETS.items():
            dungeon = generate_multi_floor_dungeon(
                width=preset["width"],
                height=preset["height"],
                num_floors=2,
                min_room_size=preset["min_room_size"],
                max_depth=preset["max_depth"],
                cell_size=preset["cell_size"],
                wall_height=preset["wall_height"],
                seed=42,
            )
            assert dungeon.num_floors == 2, f"Preset '{name}' failed dungeon generation"
            assert dungeon.total_rooms > 0, f"Preset '{name}' produced dungeon with no rooms"
