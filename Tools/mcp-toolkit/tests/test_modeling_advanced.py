"""Unit tests for advanced modeling operations (modeling_advanced.py).

Tests all pure-logic validation, falloff computation, bisect helpers,
checkpoint round-trip, alpha stamp patterns, and modifier/bridge
parameter validation -- no Blender/bpy required.
"""

import math
import tempfile
import time
import types
from pathlib import Path

import pytest

_TMP_TEST_PNG = str(Path(tempfile.gettempdir()) / "test.png")


# ---------------------------------------------------------------------------
# Symmetry parameter validation
# ---------------------------------------------------------------------------


class TestValidateSymmetryParams:
    """Test symmetry edit parameter validation."""

    def test_valid_defaults(self):
        from blender_addon.handlers.modeling_advanced import validate_symmetry_params

        name, axis, enable = validate_symmetry_params({"object_name": "Cube"})
        assert name == "Cube"
        assert axis == "X"
        assert enable is True

    def test_all_axes_valid(self):
        from blender_addon.handlers.modeling_advanced import validate_symmetry_params

        for ax in ("X", "Y", "Z"):
            _, axis, _ = validate_symmetry_params(
                {"object_name": "Cube", "axis": ax}
            )
            assert axis == ax

    def test_lowercase_axis_accepted(self):
        from blender_addon.handlers.modeling_advanced import validate_symmetry_params

        _, axis, _ = validate_symmetry_params(
            {"object_name": "Cube", "axis": "y"}
        )
        assert axis == "Y"

    def test_invalid_axis_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_symmetry_params

        with pytest.raises(ValueError, match="Invalid axis"):
            validate_symmetry_params({"object_name": "Cube", "axis": "W"})

    def test_missing_object_name_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_symmetry_params

        with pytest.raises(ValueError, match="object_name is required"):
            validate_symmetry_params({})

    def test_disable_symmetry(self):
        from blender_addon.handlers.modeling_advanced import validate_symmetry_params

        _, _, enable = validate_symmetry_params(
            {"object_name": "Cube", "enable": False}
        )
        assert enable is False


# ---------------------------------------------------------------------------
# Loop select parameter validation
# ---------------------------------------------------------------------------


class TestValidateLoopSelectParams:
    """Test loop selection parameter validation."""

    def test_valid_loop(self):
        from blender_addon.handlers.modeling_advanced import validate_loop_select_params

        name, idx, mode, extend = validate_loop_select_params(
            {"object_name": "Cube", "edge_index": 5}
        )
        assert name == "Cube"
        assert idx == 5
        assert mode == "LOOP"
        assert extend is False

    def test_ring_mode(self):
        from blender_addon.handlers.modeling_advanced import validate_loop_select_params

        _, _, mode, _ = validate_loop_select_params(
            {"object_name": "Cube", "edge_index": 0, "mode": "RING"}
        )
        assert mode == "RING"

    def test_invalid_mode_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_loop_select_params

        with pytest.raises(ValueError, match="Invalid loop mode"):
            validate_loop_select_params(
                {"object_name": "Cube", "edge_index": 0, "mode": "FACE"}
            )

    def test_missing_edge_index_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_loop_select_params

        with pytest.raises(ValueError, match="edge_index is required"):
            validate_loop_select_params({"object_name": "Cube"})

    def test_negative_edge_index_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_loop_select_params

        with pytest.raises(ValueError, match="non-negative"):
            validate_loop_select_params(
                {"object_name": "Cube", "edge_index": -1}
            )

    def test_extend_flag(self):
        from blender_addon.handlers.modeling_advanced import validate_loop_select_params

        _, _, _, extend = validate_loop_select_params(
            {"object_name": "Cube", "edge_index": 0, "extend": True}
        )
        assert extend is True


# ---------------------------------------------------------------------------
# Selection modify parameter validation
# ---------------------------------------------------------------------------


class TestValidateSelectionModifyParams:
    """Test grow/shrink selection parameter validation."""

    def test_valid_grow(self):
        from blender_addon.handlers.modeling_advanced import validate_selection_modify_params

        name, action, steps = validate_selection_modify_params(
            {"object_name": "Cube"}
        )
        assert name == "Cube"
        assert action == "GROW"
        assert steps == 1

    def test_shrink(self):
        from blender_addon.handlers.modeling_advanced import validate_selection_modify_params

        _, action, _ = validate_selection_modify_params(
            {"object_name": "Cube", "action": "SHRINK"}
        )
        assert action == "SHRINK"

    def test_multiple_steps(self):
        from blender_addon.handlers.modeling_advanced import validate_selection_modify_params

        _, _, steps = validate_selection_modify_params(
            {"object_name": "Cube", "steps": 5}
        )
        assert steps == 5

    def test_invalid_action_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_selection_modify_params

        with pytest.raises(ValueError, match="Invalid selection action"):
            validate_selection_modify_params(
                {"object_name": "Cube", "action": "INVERT"}
            )

    def test_zero_steps_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_selection_modify_params

        with pytest.raises(ValueError, match="steps must be >= 1"):
            validate_selection_modify_params(
                {"object_name": "Cube", "steps": 0}
            )


# ---------------------------------------------------------------------------
# Bridge edge loop parameter validation
# ---------------------------------------------------------------------------


class TestValidateBridgeParams:
    """Test bridge edge loop parameter validation."""

    def test_valid_defaults(self):
        from blender_addon.handlers.modeling_advanced import validate_bridge_params

        name, segments, twist, interp = validate_bridge_params(
            {"object_name": "Cube"}
        )
        assert name == "Cube"
        assert segments == 1
        assert twist == 0
        assert interp == "LINEAR"

    def test_all_interpolations(self):
        from blender_addon.handlers.modeling_advanced import validate_bridge_params

        for interp_type in ("LINEAR", "PATH", "SURFACE"):
            _, _, _, interp = validate_bridge_params(
                {"object_name": "Cube", "interpolation": interp_type}
            )
            assert interp == interp_type

    def test_invalid_interpolation_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_bridge_params

        with pytest.raises(ValueError, match="Invalid interpolation"):
            validate_bridge_params(
                {"object_name": "Cube", "interpolation": "CUBIC"}
            )

    def test_zero_segments_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_bridge_params

        with pytest.raises(ValueError, match="segments must be >= 1"):
            validate_bridge_params(
                {"object_name": "Cube", "segments": 0}
            )

    def test_custom_segments_and_twist(self):
        from blender_addon.handlers.modeling_advanced import validate_bridge_params

        _, segments, twist, _ = validate_bridge_params(
            {"object_name": "Cube", "segments": 4, "twist": 2}
        )
        assert segments == 4
        assert twist == 2


# ---------------------------------------------------------------------------
# Modifier parameter validation
# ---------------------------------------------------------------------------


class TestValidateModifierParams:
    """Test modifier stack parameter validation."""

    def test_valid_add(self):
        from blender_addon.handlers.modeling_advanced import validate_modifier_params

        result = validate_modifier_params({
            "object_name": "Cube",
            "action": "add",
            "modifier_type": "SUBSURF",
        })
        assert result["action"] == "add"
        assert result["modifier_type"] == "SUBSURF"

    def test_all_valid_modifier_types(self):
        from blender_addon.handlers.modeling_advanced import (
            validate_modifier_params,
            VALID_MODIFIER_TYPES,
        )

        for mod_type in VALID_MODIFIER_TYPES:
            result = validate_modifier_params({
                "object_name": "Cube",
                "action": "add",
                "modifier_type": mod_type,
            })
            assert result["modifier_type"] == mod_type

    def test_invalid_modifier_type_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_modifier_params

        with pytest.raises(ValueError, match="Invalid modifier_type"):
            validate_modifier_params({
                "object_name": "Cube",
                "action": "add",
                "modifier_type": "INVALID_MOD",
            })

    def test_invalid_action_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_modifier_params

        with pytest.raises(ValueError, match="Invalid modifier action"):
            validate_modifier_params({
                "object_name": "Cube",
                "action": "destroy",
            })

    def test_configure_requires_modifier_name(self):
        from blender_addon.handlers.modeling_advanced import validate_modifier_params

        with pytest.raises(ValueError, match="modifier_name is required"):
            validate_modifier_params({
                "object_name": "Cube",
                "action": "configure",
            })

    def test_apply_requires_modifier_name(self):
        from blender_addon.handlers.modeling_advanced import validate_modifier_params

        with pytest.raises(ValueError, match="modifier_name is required"):
            validate_modifier_params({
                "object_name": "Cube",
                "action": "apply",
            })

    def test_remove_requires_modifier_name(self):
        from blender_addon.handlers.modeling_advanced import validate_modifier_params

        with pytest.raises(ValueError, match="modifier_name is required"):
            validate_modifier_params({
                "object_name": "Cube",
                "action": "remove",
            })

    def test_reorder_requires_index(self):
        from blender_addon.handlers.modeling_advanced import validate_modifier_params

        with pytest.raises(ValueError, match="index is required"):
            validate_modifier_params({
                "object_name": "Cube",
                "action": "reorder",
                "modifier_name": "MyMod",
            })

    def test_list_action(self):
        from blender_addon.handlers.modeling_advanced import validate_modifier_params

        result = validate_modifier_params({
            "object_name": "Cube",
            "action": "list",
        })
        assert result["action"] == "list"

    def test_configure_with_settings(self):
        from blender_addon.handlers.modeling_advanced import validate_modifier_params

        result = validate_modifier_params({
            "object_name": "Cube",
            "action": "configure",
            "modifier_name": "Subsurf",
            "settings": {"levels": 2, "render_levels": 3},
        })
        assert result["settings"] == {"levels": 2, "render_levels": 3}

    def test_add_with_settings(self):
        from blender_addon.handlers.modeling_advanced import validate_modifier_params

        result = validate_modifier_params({
            "object_name": "Cube",
            "action": "add",
            "modifier_type": "MIRROR",
            "settings": {"use_axis": [True, False, False]},
        })
        assert result["settings"] == {"use_axis": [True, False, False]}

    def test_modifier_types_are_valid_blender_types(self):
        """All modifier types in VALID_MODIFIER_TYPES should be real Blender types."""
        from blender_addon.handlers.modeling_advanced import VALID_MODIFIER_TYPES

        # Known Blender modifier types (comprehensive list)
        blender_modifier_types = {
            "SUBSURF", "MIRROR", "ARRAY", "SOLIDIFY", "BEVEL",
            "BOOLEAN", "SHRINKWRAP", "SKIN", "REMESH", "DECIMATE",
            "SMOOTH", "CORRECTIVE_SMOOTH", "LAPLACIANSMOOTH", "WEIGHTED_NORMAL",
            "DISPLACE", "CURVE", "LATTICE", "MESH_DEFORM", "SURFACE_DEFORM",
            "CAST", "WAVE", "WARP", "CLOTH", "PARTICLE_SYSTEM",
            "SIMPLE_DEFORM", "WIREFRAME", "SCREW", "BUILD", "TRIANGULATE",
            "MULTIRES", "EDGE_SPLIT", "DATA_TRANSFER", "NORMAL_EDIT",
        }
        for mod_type in VALID_MODIFIER_TYPES:
            assert mod_type in blender_modifier_types, (
                f"{mod_type} is not a known Blender modifier type"
            )

    def test_all_actions_are_valid(self):
        """All defined actions should be in VALID_MODIFIER_ACTIONS."""
        from blender_addon.handlers.modeling_advanced import VALID_MODIFIER_ACTIONS

        expected = {"add", "configure", "apply", "remove", "list", "reorder"}
        assert VALID_MODIFIER_ACTIONS == expected


class TestHandleModifierReporting:
    """Test modifier handler reports applied and failed settings accurately."""

    class _FakeModifier:
        def __init__(self, name: str):
            self.name = name
            self._good_setting = None

        @property
        def good_setting(self):
            return self._good_setting

        @good_setting.setter
        def good_setting(self, value):
            self._good_setting = value

        @property
        def bad_setting(self):
            return None

        @bad_setting.setter
        def bad_setting(self, value):
            raise TypeError("bad setting rejected")

    class _FakeModifiers:
        def __init__(self):
            self._mods = {}

        def new(self, name, type):
            mod = TestHandleModifierReporting._FakeModifier(name)
            self._mods[name] = mod
            return mod

        def get(self, name):
            return self._mods.get(name)

        def __iter__(self):
            return iter(self._mods.values())

    class _FakeObject:
        def __init__(self, name="Cube"):
            self.name = name
            self.modifiers = TestHandleModifierReporting._FakeModifiers()

    def test_add_reports_only_successful_settings(self, monkeypatch, caplog):
        from blender_addon.handlers import modeling_advanced

        fake_obj = self._FakeObject()
        monkeypatch.setattr(modeling_advanced, "_get_mesh_object", lambda name: fake_obj)

        with caplog.at_level("WARNING", logger=modeling_advanced.logger.name):
            result = modeling_advanced.handle_modifier({
                "object_name": "Cube",
                "action": "add",
                "modifier_type": "SUBSURF",
                "modifier_name": "Subsurf",
                "settings": {
                    "good_setting": 2,
                    "bad_setting": 3,
                    "missing_setting": 4,
                },
            })

        assert result["settings_applied"] == ["good_setting"]
        assert set(result["failed_settings"]) == {"bad_setting", "missing_setting"}
        assert "Failed to set modifier" in caplog.text

    def test_configure_reports_only_successful_settings(self, monkeypatch, caplog):
        from blender_addon.handlers import modeling_advanced

        fake_obj = self._FakeObject()
        fake_obj.modifiers._mods["Subsurf"] = self._FakeModifier("Subsurf")
        monkeypatch.setattr(modeling_advanced, "_get_mesh_object", lambda name: fake_obj)

        with caplog.at_level("WARNING", logger=modeling_advanced.logger.name):
            result = modeling_advanced.handle_modifier({
                "object_name": "Cube",
                "action": "configure",
                "modifier_name": "Subsurf",
                "settings": {
                    "good_setting": 5,
                    "bad_setting": 6,
                    "missing_setting": 7,
                },
            })

        assert result["applied_settings"] == ["good_setting"]
        assert set(result["failed_settings"]) == {"bad_setting", "missing_setting"}
        assert "Failed to configure modifier" in caplog.text


class TestMeshQualityReporting:
    """Test mesh-quality reporting added to advanced modeling handlers."""

    def test_summarize_mesh_quality_flags_repair_recommended(self, monkeypatch):
        from blender_addon.handlers import mesh, modeling_advanced

        monkeypatch.setattr(mesh, "_analyze_mesh", lambda obj: {
            "grade": "D",
            "non_manifold_edges": 3,
            "boundary_edges": 4,
            "ngon_count": 2,
            "loose_vertices": 1,
            "loose_edges": 0,
            "issues": ["3 non-manifold edges", "1 loose vertices"],
        })

        result = modeling_advanced._summarize_mesh_quality(
            types.SimpleNamespace(name="Cube")
        )

        assert result["topology_grade"] == "D"
        assert result["geometry_quality"] == "repair_recommended"
        assert result["repair_recommended"] is True
        assert result["non_manifold_edges"] == 3
        assert result["quality_issues"] == [
            "3 non-manifold edges",
            "1 loose vertices",
        ]

    def test_summarize_mesh_quality_logs_and_falls_back(self, monkeypatch, caplog):
        from blender_addon.handlers import mesh, modeling_advanced

        def _fail(obj):
            raise RuntimeError("analysis unavailable")

        monkeypatch.setattr(mesh, "_analyze_mesh", _fail)

        with caplog.at_level("WARNING", logger=modeling_advanced.logger.name):
            result = modeling_advanced._summarize_mesh_quality(
                types.SimpleNamespace(name="Cube")
            )

        assert result["topology_grade"] is None
        assert result["geometry_quality"] == "unknown"
        assert result["quality_issues"] == []
        assert "Failed to analyze mesh quality" in caplog.text

    class _FakeModifier:
        def __init__(self, name: str):
            self.name = name

    class _FakeModifiers:
        def __init__(self, modifier):
            self._modifier = modifier

        def get(self, name):
            return self._modifier if self._modifier.name == name else None

    class _FakeObject:
        def __init__(self, name="Cube"):
            self.name = name
            self.modifiers = TestMeshQualityReporting._FakeModifiers(
                TestMeshQualityReporting._FakeModifier("Subsurf")
            )
            self.data = types.SimpleNamespace(
                vertices=[object()] * 8,
                polygons=[object()] * 6,
            )
            self.selected = False

        def select_set(self, state: bool):
            self.selected = state

    class _FakeOverride:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeContext:
        def __init__(self):
            self.view_layer = types.SimpleNamespace(
                objects=types.SimpleNamespace(active=None)
            )

        def temp_override(self, **kwargs):
            return TestMeshQualityReporting._FakeOverride()

    class _FakeOpsObject:
        def __init__(self):
            self.applied_modifiers = []

        def modifier_apply(self, modifier):
            self.applied_modifiers.append(modifier)

    def test_handle_modifier_apply_reports_mesh_quality(self, monkeypatch):
        from blender_addon.handlers import modeling_advanced

        fake_obj = self._FakeObject()
        fake_ops_object = self._FakeOpsObject()
        fake_bpy = types.SimpleNamespace(
            context=self._FakeContext(),
            ops=types.SimpleNamespace(object=fake_ops_object),
        )

        monkeypatch.setattr(modeling_advanced, "_get_mesh_object", lambda name: fake_obj)
        monkeypatch.setattr(modeling_advanced, "_get_3d_context", lambda: {"area": "view"})
        monkeypatch.setattr(modeling_advanced, "bpy", fake_bpy)
        monkeypatch.setattr(modeling_advanced, "_summarize_mesh_quality", lambda obj: {
            "topology_grade": "B",
            "geometry_quality": "clean",
            "repair_recommended": False,
            "non_manifold_edges": 0,
            "boundary_edges": 0,
            "ngon_count": 0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "quality_issues": [],
        })

        result = modeling_advanced.handle_modifier({
            "object_name": "Cube",
            "action": "apply",
            "modifier_name": "Subsurf",
        })

        assert fake_obj.selected is True
        assert fake_bpy.context.view_layer.objects.active is fake_obj
        assert fake_ops_object.applied_modifiers == ["Subsurf"]
        assert result["modifier_name"] == "Subsurf"
        assert result["topology_grade"] == "B"
        assert result["geometry_quality"] == "clean"
        assert result["repair_recommended"] is False


# ---------------------------------------------------------------------------
# Circularize parameter validation
# ---------------------------------------------------------------------------


class TestValidateCircularizeParams:
    """Test circularize parameter validation."""

    def test_valid_defaults(self):
        from blender_addon.handlers.modeling_advanced import validate_circularize_params

        name, flatten = validate_circularize_params({"object_name": "Cube"})
        assert name == "Cube"
        assert flatten is True

    def test_no_flatten(self):
        from blender_addon.handlers.modeling_advanced import validate_circularize_params

        _, flatten = validate_circularize_params(
            {"object_name": "Cube", "flatten": False}
        )
        assert flatten is False

    def test_missing_object_name_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_circularize_params

        with pytest.raises(ValueError, match="object_name is required"):
            validate_circularize_params({})


# ---------------------------------------------------------------------------
# Insert mesh parameter validation
# ---------------------------------------------------------------------------


class TestValidateInsertMeshParams:
    """Test insert mesh parameter validation."""

    def test_valid_params(self):
        from blender_addon.handlers.modeling_advanced import validate_insert_mesh_params

        name, mesh_name, points, align = validate_insert_mesh_params({
            "object_name": "Terrain",
            "insert_mesh_name": "Rock",
            "points": [{"position": [1, 2, 3]}],
        })
        assert name == "Terrain"
        assert mesh_name == "Rock"
        assert len(points) == 1
        assert align is True

    def test_missing_insert_mesh_name_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_insert_mesh_params

        with pytest.raises(ValueError, match="insert_mesh_name is required"):
            validate_insert_mesh_params({
                "object_name": "Terrain",
                "points": [{"position": [0, 0, 0]}],
            })

    def test_empty_points_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_insert_mesh_params

        with pytest.raises(ValueError, match="At least one point"):
            validate_insert_mesh_params({
                "object_name": "Terrain",
                "insert_mesh_name": "Rock",
                "points": [],
            })

    def test_point_missing_position_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_insert_mesh_params

        with pytest.raises(ValueError, match="missing 'position'"):
            validate_insert_mesh_params({
                "object_name": "Terrain",
                "insert_mesh_name": "Rock",
                "points": [{"normal": [0, 0, 1]}],
            })

    def test_multiple_points(self):
        from blender_addon.handlers.modeling_advanced import validate_insert_mesh_params

        _, _, points, _ = validate_insert_mesh_params({
            "object_name": "Terrain",
            "insert_mesh_name": "Rock",
            "points": [
                {"position": [0, 0, 0], "normal": [0, 0, 1], "scale": 2.0},
                {"position": [5, 5, 0], "normal": [0, 1, 0]},
            ],
        })
        assert len(points) == 2
        assert points[0]["scale"] == 2.0


# ---------------------------------------------------------------------------
# Alpha stamp parameter validation
# ---------------------------------------------------------------------------


class TestValidateAlphaStampParams:
    """Test alpha stamp parameter validation."""

    def test_valid_defaults(self):
        from blender_addon.handlers.modeling_advanced import validate_alpha_stamp_params

        result = validate_alpha_stamp_params({"object_name": "Cube"})
        assert result["pattern"] == "scales"
        assert result["radius"] == 1.0
        assert result["depth"] == 0.1

    def test_all_patterns_valid(self):
        from blender_addon.handlers.modeling_advanced import (
            validate_alpha_stamp_params,
            VALID_ALPHA_PATTERNS,
        )

        for pat in VALID_ALPHA_PATTERNS:
            if pat == "custom":
                result = validate_alpha_stamp_params({
                    "object_name": "Cube",
                    "pattern": pat,
                    "custom_image_path": _TMP_TEST_PNG,
                })
            else:
                result = validate_alpha_stamp_params({
                    "object_name": "Cube",
                    "pattern": pat,
                })
            assert result["pattern"] == pat

    def test_invalid_pattern_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_alpha_stamp_params

        with pytest.raises(ValueError, match="Invalid pattern"):
            validate_alpha_stamp_params({
                "object_name": "Cube",
                "pattern": "diamonds",
            })

    def test_custom_requires_image_path(self):
        from blender_addon.handlers.modeling_advanced import validate_alpha_stamp_params

        with pytest.raises(ValueError, match="custom_image_path is required"):
            validate_alpha_stamp_params({
                "object_name": "Cube",
                "pattern": "custom",
            })

    def test_zero_radius_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_alpha_stamp_params

        with pytest.raises(ValueError, match="radius must be positive"):
            validate_alpha_stamp_params({
                "object_name": "Cube",
                "radius": 0,
            })

    def test_negative_radius_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_alpha_stamp_params

        with pytest.raises(ValueError, match="radius must be positive"):
            validate_alpha_stamp_params({
                "object_name": "Cube",
                "radius": -1.0,
            })

    def test_position_validation(self):
        from blender_addon.handlers.modeling_advanced import validate_alpha_stamp_params

        with pytest.raises(ValueError, match="position must be"):
            validate_alpha_stamp_params({
                "object_name": "Cube",
                "position": [1, 2],
            })


# ---------------------------------------------------------------------------
# Proportional edit parameter validation
# ---------------------------------------------------------------------------


class TestValidateProportionalEditParams:
    """Test proportional editing parameter validation."""

    def test_valid_translate(self):
        from blender_addon.handlers.modeling_advanced import validate_proportional_edit_params

        result = validate_proportional_edit_params({
            "object_name": "Cube",
            "vertex_indices": [0, 1, 2],
            "value": [0, 0, 1],
        })
        assert result["transform_type"] == "TRANSLATE"
        assert result["falloff_type"] == "SMOOTH"
        assert result["falloff_radius"] == 2.0

    def test_all_falloff_types_valid(self):
        from blender_addon.handlers.modeling_advanced import (
            validate_proportional_edit_params,
            VALID_FALLOFF_TYPES,
        )

        for falloff in VALID_FALLOFF_TYPES:
            result = validate_proportional_edit_params({
                "object_name": "Cube",
                "vertex_indices": [0],
                "falloff_type": falloff,
            })
            assert result["falloff_type"] == falloff

    def test_invalid_falloff_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_proportional_edit_params

        with pytest.raises(ValueError, match="Invalid falloff_type"):
            validate_proportional_edit_params({
                "object_name": "Cube",
                "vertex_indices": [0],
                "falloff_type": "EXPONENTIAL",
            })

    def test_invalid_transform_type_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_proportional_edit_params

        with pytest.raises(ValueError, match="Invalid transform_type"):
            validate_proportional_edit_params({
                "object_name": "Cube",
                "vertex_indices": [0],
                "transform_type": "SHEAR",
            })

    def test_empty_vertex_indices_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_proportional_edit_params

        with pytest.raises(ValueError, match="must not be empty"):
            validate_proportional_edit_params({
                "object_name": "Cube",
                "vertex_indices": [],
            })

    def test_zero_falloff_radius_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_proportional_edit_params

        with pytest.raises(ValueError, match="falloff_radius must be positive"):
            validate_proportional_edit_params({
                "object_name": "Cube",
                "vertex_indices": [0],
                "falloff_radius": 0,
            })

    def test_all_transform_types(self):
        from blender_addon.handlers.modeling_advanced import validate_proportional_edit_params

        for tt in ("TRANSLATE", "ROTATE", "SCALE"):
            result = validate_proportional_edit_params({
                "object_name": "Cube",
                "vertex_indices": [0],
                "transform_type": tt,
            })
            assert result["transform_type"] == tt


# ---------------------------------------------------------------------------
# Bisect parameter validation
# ---------------------------------------------------------------------------


class TestValidateBisectParams:
    """Test bisect parameter validation."""

    def test_valid_defaults(self):
        from blender_addon.handlers.modeling_advanced import validate_bisect_params

        result = validate_bisect_params({"object_name": "Cube"})
        assert result["plane_point"] == [0, 0, 0]
        # Default normal [0, 0, 1] should be already normalized
        assert abs(result["plane_normal"][2] - 1.0) < 1e-6
        assert result["clear_inner"] is False
        assert result["clear_outer"] is False
        assert result["fill"] is False

    def test_normal_normalization(self):
        from blender_addon.handlers.modeling_advanced import validate_bisect_params

        result = validate_bisect_params({
            "object_name": "Cube",
            "plane_normal": [3, 0, 0],
        })
        # Should be normalized to [1, 0, 0]
        assert abs(result["plane_normal"][0] - 1.0) < 1e-6
        assert abs(result["plane_normal"][1]) < 1e-6
        assert abs(result["plane_normal"][2]) < 1e-6

    def test_diagonal_normal_normalization(self):
        from blender_addon.handlers.modeling_advanced import validate_bisect_params

        result = validate_bisect_params({
            "object_name": "Cube",
            "plane_normal": [1, 1, 1],
        })
        length = math.sqrt(sum(c * c for c in result["plane_normal"]))
        assert abs(length - 1.0) < 1e-6

    def test_zero_normal_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_bisect_params

        with pytest.raises(ValueError, match="must not be a zero vector"):
            validate_bisect_params({
                "object_name": "Cube",
                "plane_normal": [0, 0, 0],
            })

    def test_wrong_length_plane_point_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_bisect_params

        with pytest.raises(ValueError, match="plane_point must be"):
            validate_bisect_params({
                "object_name": "Cube",
                "plane_point": [0, 0],
            })

    def test_wrong_length_plane_normal_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_bisect_params

        with pytest.raises(ValueError, match="plane_normal must be"):
            validate_bisect_params({
                "object_name": "Cube",
                "plane_normal": [0, 0],
            })

    def test_clear_and_fill_flags(self):
        from blender_addon.handlers.modeling_advanced import validate_bisect_params

        result = validate_bisect_params({
            "object_name": "Cube",
            "clear_inner": True,
            "clear_outer": True,
            "fill": True,
        })
        assert result["clear_inner"] is True
        assert result["clear_outer"] is True
        assert result["fill"] is True


# ---------------------------------------------------------------------------
# Checkpoint parameter validation
# ---------------------------------------------------------------------------


class TestValidateCheckpointParams:
    """Test mesh checkpoint parameter validation."""

    def test_valid_save(self):
        from blender_addon.handlers.modeling_advanced import validate_checkpoint_params

        name, action, cp_name = validate_checkpoint_params({
            "object_name": "Cube",
            "action": "save",
            "checkpoint_name": "before_edit",
        })
        assert name == "Cube"
        assert action == "save"
        assert cp_name == "before_edit"

    def test_default_action_is_save(self):
        from blender_addon.handlers.modeling_advanced import validate_checkpoint_params

        _, action, _ = validate_checkpoint_params({"object_name": "Cube"})
        assert action == "save"

    def test_all_actions_valid(self):
        from blender_addon.handlers.modeling_advanced import validate_checkpoint_params

        for act in ("save", "restore", "list", "clear"):
            _, action, _ = validate_checkpoint_params({
                "object_name": "Cube",
                "action": act,
            })
            assert action == act


class TestRuntimeModelingAdvancedHandlers:
    """Runtime-style advanced modeling tests using fake Blender objects."""

    class _FakeMeshData:
        def __init__(self, vertex_count: int = 8, polygon_count: int = 6):
            self.vertices = [object()] * vertex_count
            self.polygons = [object()] * polygon_count

        def copy(self):
            return TestRuntimeModelingAdvancedHandlers._FakeMeshData(
                len(self.vertices),
                len(self.polygons),
            )

        def update(self):
            return None

    class _FakeObject:
        def __init__(self, name: str, data=None):
            self.name = name
            self.data = data or TestRuntimeModelingAdvancedHandlers._FakeMeshData()
            self.selected = False
            self.location = None
            self.scale = None

        def select_set(self, state: bool):
            self.selected = state

        def copy(self):
            return TestRuntimeModelingAdvancedHandlers._FakeObject(
                self.name,
                data=self.data,
            )

    class _FakeCollectionObjects:
        def __init__(self):
            self.linked = []

        def link(self, obj):
            self.linked.append(obj)

    class _FakeOverride:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeContext:
        def __init__(self):
            self.view_layer = types.SimpleNamespace(
                objects=types.SimpleNamespace(active=None)
            )
            self.collection = types.SimpleNamespace(
                objects=TestRuntimeModelingAdvancedHandlers._FakeCollectionObjects()
            )

        def temp_override(self, **kwargs):
            return TestRuntimeModelingAdvancedHandlers._FakeOverride()

    class _FakeObjectOps:
        def __init__(self):
            self.mode_calls = []

        def mode_set(self, mode):
            self.mode_calls.append(mode)

    class _FakeMeshOps:
        def __init__(self):
            self.circle_calls = []

        def looptools_circle(self, **kwargs):
            self.circle_calls.append(kwargs)

    class _FakeVector:
        def __init__(self, coords):
            self.coords = tuple(coords)
            self.length = math.sqrt(sum(float(c) * float(c) for c in self.coords))

    def test_handle_circularize_uses_looptools_and_reports_quality(self, monkeypatch):
        from blender_addon.handlers import modeling_advanced

        fake_obj = self._FakeObject("CircleMesh")
        fake_context = self._FakeContext()
        object_ops = self._FakeObjectOps()
        mesh_ops = self._FakeMeshOps()
        fake_bpy = types.SimpleNamespace(
            context=fake_context,
            ops=types.SimpleNamespace(object=object_ops, mesh=mesh_ops),
        )

        monkeypatch.setattr(modeling_advanced, "_get_mesh_object", lambda name: fake_obj)
        monkeypatch.setattr(modeling_advanced, "_get_3d_context", lambda: {"area": "VIEW_3D"})
        monkeypatch.setattr(modeling_advanced, "bpy", fake_bpy)
        monkeypatch.setattr(modeling_advanced, "_attach_mesh_quality", lambda payload, obj: {
            **payload,
            "topology_grade": "B",
            "geometry_quality": "clean",
        })

        result = modeling_advanced.handle_circularize({
            "object_name": "CircleMesh",
            "flatten": False,
        })

        assert fake_obj.selected is True
        assert fake_context.view_layer.objects.active is fake_obj
        assert object_ops.mode_calls == ["EDIT", "OBJECT"]
        assert mesh_ops.circle_calls == [{
            "fit": "best",
            "flatten": False,
            "influence": 100,
        }]
        assert result["method"] == "looptools"
        assert result["geometry_quality"] == "clean"

    def test_handle_insert_mesh_creates_instances_and_links_them(self, monkeypatch):
        from blender_addon.handlers import modeling_advanced

        fake_context = self._FakeContext()
        target_obj = self._FakeObject("Terrain")
        source_obj = self._FakeObject("RockSource")
        source_obj.data = self._FakeMeshData(vertex_count=12, polygon_count=8)
        fake_bpy = types.SimpleNamespace(
            data=types.SimpleNamespace(objects={"RockSource": source_obj}),
            context=fake_context,
        )

        monkeypatch.setattr(modeling_advanced, "_get_mesh_object", lambda name: target_obj)
        monkeypatch.setattr(modeling_advanced, "bpy", fake_bpy)
        monkeypatch.setattr(modeling_advanced.mathutils, "Vector", self._FakeVector)

        result = modeling_advanced.handle_insert_mesh({
            "object_name": "Terrain",
            "insert_mesh_name": "RockSource",
            "points": [
                {"position": [1, 2, 3], "scale": 2.0},
                {"position": [4, 5, 6], "scale": 0.5},
            ],
            "align_to_normal": False,
        })

        linked = fake_context.collection.objects.linked
        assert len(linked) == 2
        assert linked[0].name == "RockSource_insert_000"
        assert linked[1].name == "RockSource_insert_001"
        assert linked[0].location.coords == (1, 2, 3)
        assert linked[0].scale == (2.0, 2.0, 2.0)
        assert linked[1].scale == (0.5, 0.5, 0.5)
        assert result["instances_created"] == 2
        assert result["instance_names"] == [
            "RockSource_insert_000",
            "RockSource_insert_001",
        ]

    def test_invalid_action_raises(self):
        from blender_addon.handlers.modeling_advanced import validate_checkpoint_params

        with pytest.raises(ValueError, match="Invalid checkpoint action"):
            validate_checkpoint_params({
                "object_name": "Cube",
                "action": "delete",
            })

    def test_auto_generated_checkpoint_name(self):
        from blender_addon.handlers.modeling_advanced import validate_checkpoint_params

        _, _, cp_name = validate_checkpoint_params({"object_name": "Cube"})
        assert cp_name.startswith("checkpoint_")


# ---------------------------------------------------------------------------
# Falloff weight computation
# ---------------------------------------------------------------------------


class TestComputeFalloffWeight:
    """Test proportional editing falloff weight computation."""

    def test_at_center_weight_is_1(self):
        from blender_addon.handlers.modeling_advanced import compute_falloff_weight

        # All falloff types should give 1.0 at distance=0
        # (except RANDOM which gives a value based on seed)
        for ft in ("SMOOTH", "SPHERE", "ROOT", "SHARP", "LINEAR", "CONSTANT"):
            w = compute_falloff_weight(0.0, 2.0, ft)
            assert abs(w - 1.0) < 1e-6, f"Failed for {ft}: {w}"

    def test_at_radius_weight_is_0(self):
        from blender_addon.handlers.modeling_advanced import compute_falloff_weight

        for ft in ("SMOOTH", "SPHERE", "ROOT", "SHARP", "LINEAR"):
            w = compute_falloff_weight(2.0, 2.0, ft)
            assert w == 0.0, f"Failed for {ft}: {w}"

    def test_beyond_radius_weight_is_0(self):
        from blender_addon.handlers.modeling_advanced import compute_falloff_weight

        for ft in ("SMOOTH", "SPHERE", "ROOT", "SHARP", "LINEAR", "CONSTANT", "RANDOM"):
            w = compute_falloff_weight(5.0, 2.0, ft)
            assert w == 0.0, f"Failed for {ft}: {w}"

    def test_constant_falloff(self):
        from blender_addon.handlers.modeling_advanced import compute_falloff_weight

        # Constant falloff should be 1.0 everywhere inside radius
        assert compute_falloff_weight(0.5, 2.0, "CONSTANT") == 1.0
        assert compute_falloff_weight(1.5, 2.0, "CONSTANT") == 1.0

    def test_linear_falloff_midpoint(self):
        from blender_addon.handlers.modeling_advanced import compute_falloff_weight

        w = compute_falloff_weight(1.0, 2.0, "LINEAR")
        assert abs(w - 0.5) < 1e-6

    def test_smooth_falloff_midpoint(self):
        from blender_addon.handlers.modeling_advanced import compute_falloff_weight

        # At midpoint, smooth falloff = 0.5 * (1 + cos(pi * 0.5)) = 0.5
        w = compute_falloff_weight(1.0, 2.0, "SMOOTH")
        assert abs(w - 0.5) < 1e-6

    def test_sharp_falloff_decreases_faster_than_linear(self):
        from blender_addon.handlers.modeling_advanced import compute_falloff_weight

        # At midpoint, sharp = (1-0.5)^2 = 0.25, linear = 0.5
        sharp = compute_falloff_weight(1.0, 2.0, "SHARP")
        linear = compute_falloff_weight(1.0, 2.0, "LINEAR")
        assert sharp < linear

    def test_root_falloff_decreases_slower_than_linear(self):
        from blender_addon.handlers.modeling_advanced import compute_falloff_weight

        root = compute_falloff_weight(1.0, 2.0, "ROOT")
        linear = compute_falloff_weight(1.0, 2.0, "LINEAR")
        assert root > linear

    def test_sphere_falloff_value(self):
        from blender_addon.handlers.modeling_advanced import compute_falloff_weight

        # At t=0.5: sqrt(1 - 0.25) = sqrt(0.75) ~= 0.866
        w = compute_falloff_weight(1.0, 2.0, "SPHERE")
        expected = math.sqrt(0.75)
        assert abs(w - expected) < 1e-6

    def test_zero_radius_returns_0(self):
        from blender_addon.handlers.modeling_advanced import compute_falloff_weight

        w = compute_falloff_weight(0.0, 0.0, "LINEAR")
        assert w == 0.0

    def test_random_falloff_within_range(self):
        from blender_addon.handlers.modeling_advanced import compute_falloff_weight

        w = compute_falloff_weight(0.5, 2.0, "RANDOM")
        assert 0.0 <= w <= 1.0


# ---------------------------------------------------------------------------
# Proportional weights computation
# ---------------------------------------------------------------------------


class TestComputeProportionalWeights:
    """Test bulk proportional weight computation."""

    def test_center_vertex_weight_1(self):
        from blender_addon.handlers.modeling_advanced import compute_proportional_weights

        positions = [(0, 0, 0), (1, 0, 0), (2, 0, 0)]
        weights = compute_proportional_weights(positions, [0], 5.0, "LINEAR")
        assert weights[0] == 1.0

    def test_far_vertex_not_in_weights(self):
        from blender_addon.handlers.modeling_advanced import compute_proportional_weights

        positions = [(0, 0, 0), (100, 0, 0)]
        weights = compute_proportional_weights(positions, [0], 2.0, "LINEAR")
        assert 1 not in weights

    def test_multiple_centers(self):
        from blender_addon.handlers.modeling_advanced import compute_proportional_weights

        positions = [(0, 0, 0), (5, 0, 0), (2, 0, 0)]
        weights = compute_proportional_weights(positions, [0, 1], 3.0, "LINEAR")
        assert weights[0] == 1.0
        assert weights[1] == 1.0
        # Vertex 2 is 2.0 from center 0, and 3.0 from center 1
        # Min distance is 2.0, weight = 1 - 2/3 = 0.333...
        assert 2 in weights
        assert abs(weights[2] - (1.0 - 2.0 / 3.0)) < 1e-6

    def test_empty_positions(self):
        from blender_addon.handlers.modeling_advanced import compute_proportional_weights

        weights = compute_proportional_weights([], [], 2.0, "LINEAR")
        assert weights == {}


# ---------------------------------------------------------------------------
# Bisect side computation
# ---------------------------------------------------------------------------


class TestComputeBisectSide:
    """Test bisect plane side determination."""

    def test_vertex_above_plane(self):
        from blender_addon.handlers.modeling_advanced import compute_bisect_side

        result = compute_bisect_side(
            (0, 0, 1), [0, 0, 0], [0, 0, 1],
        )
        assert result == "outer"

    def test_vertex_below_plane(self):
        from blender_addon.handlers.modeling_advanced import compute_bisect_side

        result = compute_bisect_side(
            (0, 0, -1), [0, 0, 0], [0, 0, 1],
        )
        assert result == "inner"

    def test_vertex_on_plane(self):
        from blender_addon.handlers.modeling_advanced import compute_bisect_side

        result = compute_bisect_side(
            (5, 5, 0), [0, 0, 0], [0, 0, 1],
        )
        assert result == "on_plane"

    def test_offset_plane(self):
        from blender_addon.handlers.modeling_advanced import compute_bisect_side

        # Plane at z=5, vertex at z=3 -> inner
        result = compute_bisect_side(
            (0, 0, 3), [0, 0, 5], [0, 0, 1],
        )
        assert result == "inner"

    def test_angled_plane(self):
        from blender_addon.handlers.modeling_advanced import compute_bisect_side

        # Plane with normal (1,1,0), point at origin
        # Vertex at (1,1,0) should be outer
        result = compute_bisect_side(
            (1, 1, 0), [0, 0, 0], [1, 1, 0],
        )
        assert result == "outer"


# ---------------------------------------------------------------------------
# Normalize vector helper
# ---------------------------------------------------------------------------


class TestNormalizeVector:
    """Test vector normalization helper."""

    def test_unit_vector_unchanged(self):
        from blender_addon.handlers.modeling_advanced import normalize_vector

        result = normalize_vector([1, 0, 0])
        assert abs(result[0] - 1.0) < 1e-6
        assert abs(result[1]) < 1e-6
        assert abs(result[2]) < 1e-6

    def test_scaled_vector_normalized(self):
        from blender_addon.handlers.modeling_advanced import normalize_vector

        result = normalize_vector([3, 0, 0])
        assert abs(result[0] - 1.0) < 1e-6

    def test_diagonal_vector(self):
        from blender_addon.handlers.modeling_advanced import normalize_vector

        result = normalize_vector([1, 1, 1])
        length = math.sqrt(sum(c * c for c in result))
        assert abs(length - 1.0) < 1e-6

    def test_zero_vector_returns_zero(self):
        from blender_addon.handlers.modeling_advanced import normalize_vector

        result = normalize_vector([0, 0, 0])
        assert result == [0.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# Alpha stamp pattern generation
# ---------------------------------------------------------------------------


class TestGeneratePatternImage:
    """Test procedural alpha stamp pattern generation."""

    def test_scales_pattern(self):
        from blender_addon.handlers.modeling_advanced import _generate_pattern_image

        grid = _generate_pattern_image("scales", 32)
        assert len(grid) == 32
        assert len(grid[0]) == 32
        # Values should be in [0, 1]
        for row in grid:
            for val in row:
                assert 0.0 <= val <= 1.0

    def test_scars_pattern(self):
        from blender_addon.handlers.modeling_advanced import _generate_pattern_image

        grid = _generate_pattern_image("scars", 32)
        assert len(grid) == 32
        for row in grid:
            for val in row:
                assert 0.0 <= val <= 1.0

    def test_rivets_pattern(self):
        from blender_addon.handlers.modeling_advanced import _generate_pattern_image

        grid = _generate_pattern_image("rivets", 32)
        assert len(grid) == 32

    def test_cracks_pattern(self):
        from blender_addon.handlers.modeling_advanced import _generate_pattern_image

        grid = _generate_pattern_image("cracks", 32)
        assert len(grid) == 32

    def test_bark_pattern(self):
        from blender_addon.handlers.modeling_advanced import _generate_pattern_image

        grid = _generate_pattern_image("bark", 32)
        assert len(grid) == 32

    def test_unknown_pattern_returns_flat(self):
        from blender_addon.handlers.modeling_advanced import _generate_pattern_image

        grid = _generate_pattern_image("unknown", 16)
        assert len(grid) == 16
        for row in grid:
            for val in row:
                assert val == 0.0

    def test_all_valid_patterns_generate(self):
        from blender_addon.handlers.modeling_advanced import (
            _generate_pattern_image,
            VALID_ALPHA_PATTERNS,
        )

        for pattern in VALID_ALPHA_PATTERNS:
            if pattern == "custom":
                continue  # Custom requires external image
            grid = _generate_pattern_image(pattern, 16)
            assert len(grid) == 16
            assert len(grid[0]) == 16


# ---------------------------------------------------------------------------
# Checkpoint save/restore round-trip (pure-logic)
# ---------------------------------------------------------------------------


class TestCheckpointRoundTrip:
    """Test checkpoint serialization and storage round-trip."""

    def test_serialize_mesh_data(self):
        from blender_addon.handlers.modeling_advanced import _serialize_mesh_data_pure

        verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        edges = [(0, 1), (1, 2), (2, 0)]
        faces = [(0, 1, 2)]

        cp = _serialize_mesh_data_pure(verts, edges, faces, "test_cp")
        assert cp["name"] == "test_cp"
        assert cp["vertex_count"] == 3
        assert cp["edge_count"] == 3
        assert cp["face_count"] == 1
        assert cp["vertices"] == verts
        assert cp["edges"] == edges
        assert cp["faces"] == faces
        assert "timestamp" in cp

    def test_checkpoint_storage_operations(self):
        from blender_addon.handlers.modeling_advanced import (
            get_checkpoint_storage,
            clear_all_checkpoints,
            _serialize_mesh_data_pure,
        )

        clear_all_checkpoints()
        storage = get_checkpoint_storage()
        assert len(storage) == 0

        # Add a checkpoint
        cp = _serialize_mesh_data_pure(
            [(0, 0, 0), (1, 0, 0)], [(0, 1)], [], "cp1",
        )
        storage.setdefault("TestObj", []).append(cp)
        assert len(storage["TestObj"]) == 1

        # Add another
        cp2 = _serialize_mesh_data_pure(
            [(0, 0, 0)], [], [], "cp2",
        )
        storage["TestObj"].append(cp2)
        assert len(storage["TestObj"]) == 2

        # Clear
        clear_all_checkpoints()
        assert len(storage) == 0

    def test_checkpoint_data_integrity(self):
        from blender_addon.handlers.modeling_advanced import _serialize_mesh_data_pure

        # A quad mesh
        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
        faces = [(0, 1, 2, 3)]

        cp = _serialize_mesh_data_pure(verts, edges, faces, "quad_check")

        # Verify the data can be used to reconstruct
        assert len(cp["vertices"]) == 4
        assert len(cp["edges"]) == 4
        assert len(cp["faces"]) == 1
        assert len(cp["faces"][0]) == 4  # Quad has 4 verts

    def test_empty_mesh_checkpoint(self):
        from blender_addon.handlers.modeling_advanced import _serialize_mesh_data_pure

        cp = _serialize_mesh_data_pure([], [], [], "empty")
        assert cp["vertex_count"] == 0
        assert cp["edge_count"] == 0
        assert cp["face_count"] == 0


# ---------------------------------------------------------------------------
# Cross-cutting validation: constants consistency
# ---------------------------------------------------------------------------


class TestConstantsConsistency:
    """Test that all constant sets are consistent and complete."""

    def test_falloff_types_match_compute(self):
        """All VALID_FALLOFF_TYPES should be handled in compute_falloff_weight."""
        from blender_addon.handlers.modeling_advanced import (
            compute_falloff_weight,
            VALID_FALLOFF_TYPES,
        )

        for ft in VALID_FALLOFF_TYPES:
            # Should not raise
            w = compute_falloff_weight(0.5, 2.0, ft)
            assert isinstance(w, float)

    def test_alpha_patterns_match_generator(self):
        """All non-custom patterns should be handled by the generator."""
        from blender_addon.handlers.modeling_advanced import (
            _generate_pattern_image,
            VALID_ALPHA_PATTERNS,
        )

        for pat in VALID_ALPHA_PATTERNS:
            if pat == "custom":
                continue
            grid = _generate_pattern_image(pat, 8)
            assert len(grid) == 8

    def test_checkpoint_actions_complete(self):
        from blender_addon.handlers.modeling_advanced import VALID_CHECKPOINT_ACTIONS

        assert VALID_CHECKPOINT_ACTIONS == {"save", "restore", "list", "clear"}

    def test_symmetry_axes_complete(self):
        from blender_addon.handlers.modeling_advanced import VALID_SYMMETRY_AXES

        assert VALID_SYMMETRY_AXES == {"X", "Y", "Z"}

    def test_loop_modes_complete(self):
        from blender_addon.handlers.modeling_advanced import VALID_LOOP_MODES

        assert VALID_LOOP_MODES == {"LOOP", "RING"}

    def test_bridge_interpolations_complete(self):
        from blender_addon.handlers.modeling_advanced import VALID_BRIDGE_INTERPOLATIONS

        assert VALID_BRIDGE_INTERPOLATIONS == {"LINEAR", "PATH", "SURFACE"}

    def test_proportional_transforms_complete(self):
        from blender_addon.handlers.modeling_advanced import VALID_PROPORTIONAL_TRANSFORMS

        assert VALID_PROPORTIONAL_TRANSFORMS == {"TRANSLATE", "ROTATE", "SCALE"}
