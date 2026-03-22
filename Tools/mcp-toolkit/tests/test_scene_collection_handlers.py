"""Unit tests for scene management, render config, collection, and mesh data handlers.

Tests the pure-logic validation functions for:
- Scene/World: _validate_setup_world_params, _validate_add_light_params,
  _validate_add_camera_params, _validate_configure_render_params
- Collections: _validate_create_collection_params, _validate_move_to_collection_params,
  _validate_set_visibility_params
- Mesh data: _validate_vertex_color_params, _validate_custom_normals_params,
  _validate_edge_data_params

All tests are pure-logic (no Blender/bpy required).
"""

import pytest


# ---------------------------------------------------------------------------
# _validate_setup_world_params tests
# ---------------------------------------------------------------------------


class TestValidateSetupWorldParams:
    """Test world setup parameter validation."""

    def test_defaults_pass(self):
        """Default parameters pass validation."""
        from blender_addon.handlers.scene import _validate_setup_world_params

        result = _validate_setup_world_params({})
        assert result["environment_type"] == "COLOR"
        assert result["color"] == [0.05, 0.05, 0.05]
        assert result["strength"] == 1.0
        assert result["use_nodes"] is True

    def test_valid_hdri_type(self):
        """HDRI environment type is valid."""
        from blender_addon.handlers.scene import _validate_setup_world_params

        result = _validate_setup_world_params({"environment_type": "HDRI"})
        assert result["environment_type"] == "HDRI"

    def test_valid_gradient_type(self):
        """GRADIENT environment type is valid."""
        from blender_addon.handlers.scene import _validate_setup_world_params

        result = _validate_setup_world_params({"environment_type": "GRADIENT"})
        assert result["environment_type"] == "GRADIENT"

    def test_invalid_environment_type_raises(self):
        """Invalid environment_type raises ValueError."""
        from blender_addon.handlers.scene import _validate_setup_world_params

        with pytest.raises(ValueError, match="environment_type"):
            _validate_setup_world_params({"environment_type": "SKYBOX"})

    def test_invalid_color_length_raises(self):
        """Color with wrong number of elements raises ValueError."""
        from blender_addon.handlers.scene import _validate_setup_world_params

        with pytest.raises(ValueError, match="color"):
            _validate_setup_world_params({"color": [1.0, 0.5]})

    def test_invalid_color_value_raises(self):
        """Color value > 1 raises ValueError."""
        from blender_addon.handlers.scene import _validate_setup_world_params

        with pytest.raises(ValueError, match="color"):
            _validate_setup_world_params({"color": [1.5, 0.5, 0.5]})

    def test_negative_strength_raises(self):
        """Negative strength raises ValueError."""
        from blender_addon.handlers.scene import _validate_setup_world_params

        with pytest.raises(ValueError, match="strength"):
            _validate_setup_world_params({"strength": -1.0})

    def test_non_bool_use_nodes_raises(self):
        """Non-boolean use_nodes raises ValueError."""
        from blender_addon.handlers.scene import _validate_setup_world_params

        with pytest.raises(ValueError, match="use_nodes"):
            _validate_setup_world_params({"use_nodes": "yes"})

    def test_all_valid_environment_types(self):
        """All valid environment types pass validation."""
        from blender_addon.handlers.scene import _validate_setup_world_params

        for env_type in ("HDRI", "COLOR", "GRADIENT"):
            result = _validate_setup_world_params({"environment_type": env_type})
            assert result["environment_type"] == env_type


# ---------------------------------------------------------------------------
# _validate_add_light_params tests
# ---------------------------------------------------------------------------


class TestValidateAddLightParams:
    """Test light parameter validation."""

    def test_defaults_pass(self):
        """Default parameters pass validation."""
        from blender_addon.handlers.scene import _validate_add_light_params

        result = _validate_add_light_params({})
        assert result["light_type"] == "POINT"
        assert result["position"] == [0.0, 0.0, 3.0]
        assert result["color"] == [1.0, 1.0, 1.0]
        assert result["energy"] == 1000.0

    def test_all_light_types_valid(self):
        """All valid light types pass validation."""
        from blender_addon.handlers.scene import _validate_add_light_params

        for lt in ("POINT", "SUN", "SPOT", "AREA"):
            result = _validate_add_light_params({"light_type": lt})
            assert result["light_type"] == lt

    def test_invalid_light_type_raises(self):
        """Invalid light_type raises ValueError."""
        from blender_addon.handlers.scene import _validate_add_light_params

        with pytest.raises(ValueError, match="light_type"):
            _validate_add_light_params({"light_type": "DIRECTIONAL"})

    def test_invalid_position_raises(self):
        """Position with wrong length raises ValueError."""
        from blender_addon.handlers.scene import _validate_add_light_params

        with pytest.raises(ValueError, match="position"):
            _validate_add_light_params({"position": [1.0, 2.0]})

    def test_invalid_rotation_raises(self):
        """Rotation with wrong length raises ValueError."""
        from blender_addon.handlers.scene import _validate_add_light_params

        with pytest.raises(ValueError, match="rotation"):
            _validate_add_light_params({"rotation": [1.0]})

    def test_negative_energy_raises(self):
        """Negative energy raises ValueError."""
        from blender_addon.handlers.scene import _validate_add_light_params

        with pytest.raises(ValueError, match="energy"):
            _validate_add_light_params({"energy": -100.0})

    def test_negative_radius_raises(self):
        """Negative radius raises ValueError."""
        from blender_addon.handlers.scene import _validate_add_light_params

        with pytest.raises(ValueError, match="radius"):
            _validate_add_light_params({"radius": -0.5})

    def test_color_out_of_range_raises(self):
        """Color value > 1 raises ValueError."""
        from blender_addon.handlers.scene import _validate_add_light_params

        with pytest.raises(ValueError, match="color"):
            _validate_add_light_params({"color": [1.5, 0.5, 0.5]})

    def test_zero_energy_passes(self):
        """Zero energy is valid (light is off)."""
        from blender_addon.handlers.scene import _validate_add_light_params

        result = _validate_add_light_params({"energy": 0.0})
        assert result["energy"] == 0.0


# ---------------------------------------------------------------------------
# _validate_add_camera_params tests
# ---------------------------------------------------------------------------


class TestValidateAddCameraParams:
    """Test camera parameter validation."""

    def test_defaults_pass(self):
        """Default parameters pass validation."""
        from blender_addon.handlers.scene import _validate_add_camera_params

        result = _validate_add_camera_params({})
        assert result["focal_length"] == 50.0
        assert result["sensor_size"] == 36.0
        assert result["near_clip"] == 0.1
        assert result["far_clip"] == 1000.0
        assert result["dof_focus_distance"] is None

    def test_invalid_position_raises(self):
        """Position with wrong length raises ValueError."""
        from blender_addon.handlers.scene import _validate_add_camera_params

        with pytest.raises(ValueError, match="position"):
            _validate_add_camera_params({"position": [1.0]})

    def test_zero_focal_length_raises(self):
        """Zero focal_length raises ValueError."""
        from blender_addon.handlers.scene import _validate_add_camera_params

        with pytest.raises(ValueError, match="focal_length"):
            _validate_add_camera_params({"focal_length": 0.0})

    def test_negative_sensor_size_raises(self):
        """Negative sensor_size raises ValueError."""
        from blender_addon.handlers.scene import _validate_add_camera_params

        with pytest.raises(ValueError, match="sensor_size"):
            _validate_add_camera_params({"sensor_size": -1.0})

    def test_far_clip_less_than_near_clip_raises(self):
        """far_clip <= near_clip raises ValueError."""
        from blender_addon.handlers.scene import _validate_add_camera_params

        with pytest.raises(ValueError, match="far_clip"):
            _validate_add_camera_params({"near_clip": 10.0, "far_clip": 5.0})

    def test_valid_dof_focus_distance(self):
        """Valid dof_focus_distance passes."""
        from blender_addon.handlers.scene import _validate_add_camera_params

        result = _validate_add_camera_params({"dof_focus_distance": 5.0})
        assert result["dof_focus_distance"] == 5.0

    def test_negative_dof_focus_distance_raises(self):
        """Negative dof_focus_distance raises ValueError."""
        from blender_addon.handlers.scene import _validate_add_camera_params

        with pytest.raises(ValueError, match="dof_focus_distance"):
            _validate_add_camera_params({"dof_focus_distance": -1.0})

    def test_near_clip_positive(self):
        """Zero near_clip raises ValueError."""
        from blender_addon.handlers.scene import _validate_add_camera_params

        with pytest.raises(ValueError, match="near_clip"):
            _validate_add_camera_params({"near_clip": 0.0})


# ---------------------------------------------------------------------------
# _validate_configure_render_params tests
# ---------------------------------------------------------------------------


class TestValidateConfigureRenderParams:
    """Test render configuration parameter validation."""

    def test_defaults_pass(self):
        """Default parameters pass validation."""
        from blender_addon.handlers.scene import _validate_configure_render_params

        result = _validate_configure_render_params({})
        assert result["engine"] == "EEVEE"
        assert result["samples"] == 128
        assert result["resolution_x"] == 1920
        assert result["resolution_y"] == 1080
        assert result["use_denoising"] is True
        assert result["film_transparent"] is False

    def test_cycles_engine_valid(self):
        """CYCLES engine passes validation."""
        from blender_addon.handlers.scene import _validate_configure_render_params

        result = _validate_configure_render_params({"engine": "CYCLES"})
        assert result["engine"] == "CYCLES"

    def test_invalid_engine_raises(self):
        """Invalid engine raises ValueError."""
        from blender_addon.handlers.scene import _validate_configure_render_params

        with pytest.raises(ValueError, match="engine"):
            _validate_configure_render_params({"engine": "OPENGL"})

    def test_zero_samples_raises(self):
        """Zero samples raises ValueError."""
        from blender_addon.handlers.scene import _validate_configure_render_params

        with pytest.raises(ValueError, match="samples"):
            _validate_configure_render_params({"samples": 0})

    def test_negative_resolution_raises(self):
        """Negative resolution raises ValueError."""
        from blender_addon.handlers.scene import _validate_configure_render_params

        with pytest.raises(ValueError, match="resolution_x"):
            _validate_configure_render_params({"resolution_x": -100})

    def test_non_bool_denoising_raises(self):
        """Non-boolean use_denoising raises ValueError."""
        from blender_addon.handlers.scene import _validate_configure_render_params

        with pytest.raises(ValueError, match="use_denoising"):
            _validate_configure_render_params({"use_denoising": 1})

    def test_non_int_samples_raises(self):
        """Float samples raises ValueError."""
        from blender_addon.handlers.scene import _validate_configure_render_params

        with pytest.raises(ValueError, match="samples"):
            _validate_configure_render_params({"samples": 128.5})

    def test_high_resolution_passes(self):
        """4K resolution passes validation."""
        from blender_addon.handlers.scene import _validate_configure_render_params

        result = _validate_configure_render_params({
            "resolution_x": 3840,
            "resolution_y": 2160,
        })
        assert result["resolution_x"] == 3840
        assert result["resolution_y"] == 2160


# ---------------------------------------------------------------------------
# _validate_create_collection_params tests
# ---------------------------------------------------------------------------


class TestValidateCreateCollectionParams:
    """Test collection creation parameter validation."""

    def test_valid_name_passes(self):
        """Valid name passes validation."""
        from blender_addon.handlers.scene import _validate_create_collection_params

        result = _validate_create_collection_params({"name": "Weapons"})
        assert result["name"] == "Weapons"
        assert result["parent_collection"] is None
        assert result["color_tag"] == "NONE"

    def test_missing_name_raises(self):
        """Missing name raises ValueError."""
        from blender_addon.handlers.scene import _validate_create_collection_params

        with pytest.raises(ValueError, match="name"):
            _validate_create_collection_params({})

    def test_empty_name_raises(self):
        """Empty string name raises ValueError."""
        from blender_addon.handlers.scene import _validate_create_collection_params

        with pytest.raises(ValueError, match="name"):
            _validate_create_collection_params({"name": ""})

    def test_invalid_color_tag_raises(self):
        """Invalid color_tag raises ValueError."""
        from blender_addon.handlers.scene import _validate_create_collection_params

        with pytest.raises(ValueError, match="color_tag"):
            _validate_create_collection_params({"name": "Test", "color_tag": "RED"})

    def test_valid_color_tags(self):
        """All valid color tags pass validation."""
        from blender_addon.handlers.scene import _validate_create_collection_params

        for tag in ("NONE", "COLOR_01", "COLOR_02", "COLOR_03", "COLOR_04",
                     "COLOR_05", "COLOR_06", "COLOR_07", "COLOR_08"):
            result = _validate_create_collection_params({
                "name": "Test",
                "color_tag": tag,
            })
            assert result["color_tag"] == tag

    def test_parent_collection_string(self):
        """Parent collection as string passes."""
        from blender_addon.handlers.scene import _validate_create_collection_params

        result = _validate_create_collection_params({
            "name": "Child",
            "parent_collection": "Parent",
        })
        assert result["parent_collection"] == "Parent"

    def test_parent_collection_non_string_raises(self):
        """Non-string parent_collection raises ValueError."""
        from blender_addon.handlers.scene import _validate_create_collection_params

        with pytest.raises(ValueError, match="parent_collection"):
            _validate_create_collection_params({
                "name": "Test",
                "parent_collection": 123,
            })


# ---------------------------------------------------------------------------
# _validate_move_to_collection_params tests
# ---------------------------------------------------------------------------


class TestValidateMoveToCollectionParams:
    """Test move-to-collection parameter validation."""

    def test_valid_params_pass(self):
        """Valid params pass validation."""
        from blender_addon.handlers.scene import _validate_move_to_collection_params

        result = _validate_move_to_collection_params({
            "object_name": "Cube",
            "collection_name": "Weapons",
        })
        assert result["object_name"] == "Cube"
        assert result["collection_name"] == "Weapons"

    def test_missing_object_name_raises(self):
        """Missing object_name raises ValueError."""
        from blender_addon.handlers.scene import _validate_move_to_collection_params

        with pytest.raises(ValueError, match="object_name"):
            _validate_move_to_collection_params({"collection_name": "Weapons"})

    def test_missing_collection_name_raises(self):
        """Missing collection_name raises ValueError."""
        from blender_addon.handlers.scene import _validate_move_to_collection_params

        with pytest.raises(ValueError, match="collection_name"):
            _validate_move_to_collection_params({"object_name": "Cube"})

    def test_empty_object_name_raises(self):
        """Empty object_name raises ValueError."""
        from blender_addon.handlers.scene import _validate_move_to_collection_params

        with pytest.raises(ValueError, match="object_name"):
            _validate_move_to_collection_params({
                "object_name": "",
                "collection_name": "Weapons",
            })


# ---------------------------------------------------------------------------
# _validate_set_visibility_params tests
# ---------------------------------------------------------------------------


class TestValidateSetVisibilityParams:
    """Test set-visibility parameter validation."""

    def test_visible_only_passes(self):
        """Setting only visible passes validation."""
        from blender_addon.handlers.scene import _validate_set_visibility_params

        result = _validate_set_visibility_params({
            "name": "Cube",
            "visible": True,
        })
        assert result["name"] == "Cube"
        assert result["visible"] is True
        assert result["render_visible"] is None

    def test_render_visible_only_passes(self):
        """Setting only render_visible passes validation."""
        from blender_addon.handlers.scene import _validate_set_visibility_params

        result = _validate_set_visibility_params({
            "name": "Cube",
            "render_visible": False,
        })
        assert result["render_visible"] is False

    def test_both_visibility_flags(self):
        """Setting both visible and render_visible passes."""
        from blender_addon.handlers.scene import _validate_set_visibility_params

        result = _validate_set_visibility_params({
            "name": "Cube",
            "visible": False,
            "render_visible": True,
        })
        assert result["visible"] is False
        assert result["render_visible"] is True

    def test_missing_name_raises(self):
        """Missing name raises ValueError."""
        from blender_addon.handlers.scene import _validate_set_visibility_params

        with pytest.raises(ValueError, match="name"):
            _validate_set_visibility_params({"visible": True})

    def test_neither_visibility_flag_raises(self):
        """Neither visible nor render_visible raises ValueError."""
        from blender_addon.handlers.scene import _validate_set_visibility_params

        with pytest.raises(ValueError, match="At least one"):
            _validate_set_visibility_params({"name": "Cube"})

    def test_non_bool_visible_raises(self):
        """Non-boolean visible raises ValueError."""
        from blender_addon.handlers.scene import _validate_set_visibility_params

        with pytest.raises(ValueError, match="visible"):
            _validate_set_visibility_params({
                "name": "Cube",
                "visible": 1,
            })

    def test_non_bool_render_visible_raises(self):
        """Non-boolean render_visible raises ValueError."""
        from blender_addon.handlers.scene import _validate_set_visibility_params

        with pytest.raises(ValueError, match="render_visible"):
            _validate_set_visibility_params({
                "name": "Cube",
                "render_visible": "yes",
            })


# ---------------------------------------------------------------------------
# _validate_vertex_color_params tests
# ---------------------------------------------------------------------------


class TestValidateVertexColorParams:
    """Test vertex color parameter validation."""

    def test_defaults_pass(self):
        """Default parameters with name pass validation."""
        from blender_addon.handlers.mesh import _validate_vertex_color_params

        result = _validate_vertex_color_params({"name": "Cube"})
        assert result["name"] == "Cube"
        assert result["operation"] == "CREATE_LAYER"
        assert result["layer_name"] == "Col"
        assert result["color"] == [1.0, 1.0, 1.0, 1.0]
        assert result["vertex_indices"] is None

    def test_all_operations_valid(self):
        """All valid operations pass validation."""
        from blender_addon.handlers.mesh import _validate_vertex_color_params

        for op in ("CREATE_LAYER", "PAINT", "FILL"):
            result = _validate_vertex_color_params({
                "name": "Cube",
                "operation": op,
            })
            assert result["operation"] == op

    def test_invalid_operation_raises(self):
        """Invalid operation raises ValueError."""
        from blender_addon.handlers.mesh import _validate_vertex_color_params

        with pytest.raises(ValueError, match="operation"):
            _validate_vertex_color_params({
                "name": "Cube",
                "operation": "DELETE_LAYER",
            })

    def test_missing_name_raises(self):
        """Missing name raises ValueError."""
        from blender_addon.handlers.mesh import _validate_vertex_color_params

        with pytest.raises(ValueError, match="name"):
            _validate_vertex_color_params({})

    def test_color_must_be_4_elements(self):
        """Color with wrong length raises ValueError."""
        from blender_addon.handlers.mesh import _validate_vertex_color_params

        with pytest.raises(ValueError, match="color"):
            _validate_vertex_color_params({
                "name": "Cube",
                "color": [1.0, 0.0, 0.0],
            })

    def test_color_value_out_of_range_raises(self):
        """Color value > 1 raises ValueError."""
        from blender_addon.handlers.mesh import _validate_vertex_color_params

        with pytest.raises(ValueError, match="color"):
            _validate_vertex_color_params({
                "name": "Cube",
                "color": [1.5, 0.0, 0.0, 1.0],
            })

    def test_vertex_indices_with_negative_raises(self):
        """Negative vertex index raises ValueError."""
        from blender_addon.handlers.mesh import _validate_vertex_color_params

        with pytest.raises(ValueError, match="vertex_indices"):
            _validate_vertex_color_params({
                "name": "Cube",
                "vertex_indices": [0, -1, 2],
            })

    def test_valid_vertex_indices(self):
        """Valid vertex indices pass."""
        from blender_addon.handlers.mesh import _validate_vertex_color_params

        result = _validate_vertex_color_params({
            "name": "Cube",
            "operation": "PAINT",
            "vertex_indices": [0, 1, 5],
        })
        assert result["vertex_indices"] == [0, 1, 5]

    def test_empty_layer_name_raises(self):
        """Empty layer_name raises ValueError."""
        from blender_addon.handlers.mesh import _validate_vertex_color_params

        with pytest.raises(ValueError, match="layer_name"):
            _validate_vertex_color_params({
                "name": "Cube",
                "layer_name": "",
            })


# ---------------------------------------------------------------------------
# _validate_custom_normals_params tests
# ---------------------------------------------------------------------------


class TestValidateCustomNormalsParams:
    """Test custom normals parameter validation."""

    def test_defaults_pass(self):
        """Default parameters with name pass validation."""
        from blender_addon.handlers.mesh import _validate_custom_normals_params

        result = _validate_custom_normals_params({"name": "Cube"})
        assert result["name"] == "Cube"
        assert result["operation"] == "CALCULATE"
        assert result["split_angle"] == 30.0
        assert result["source_object"] is None

    def test_all_operations_valid(self):
        """All valid operations pass validation."""
        from blender_addon.handlers.mesh import _validate_custom_normals_params

        for op in ("CALCULATE", "CLEAR"):
            result = _validate_custom_normals_params({
                "name": "Cube",
                "operation": op,
            })
            assert result["operation"] == op

    def test_transfer_requires_source_object(self):
        """TRANSFER operation without source_object raises ValueError."""
        from blender_addon.handlers.mesh import _validate_custom_normals_params

        with pytest.raises(ValueError, match="source_object"):
            _validate_custom_normals_params({
                "name": "Cube",
                "operation": "TRANSFER",
            })

    def test_transfer_with_source_object_passes(self):
        """TRANSFER operation with source_object passes."""
        from blender_addon.handlers.mesh import _validate_custom_normals_params

        result = _validate_custom_normals_params({
            "name": "Cube",
            "operation": "TRANSFER",
            "source_object": "HighPoly",
        })
        assert result["source_object"] == "HighPoly"

    def test_invalid_operation_raises(self):
        """Invalid operation raises ValueError."""
        from blender_addon.handlers.mesh import _validate_custom_normals_params

        with pytest.raises(ValueError, match="operation"):
            _validate_custom_normals_params({
                "name": "Cube",
                "operation": "FLIP",
            })

    def test_split_angle_out_of_range_raises(self):
        """split_angle > 180 raises ValueError."""
        from blender_addon.handlers.mesh import _validate_custom_normals_params

        with pytest.raises(ValueError, match="split_angle"):
            _validate_custom_normals_params({
                "name": "Cube",
                "split_angle": 200.0,
            })

    def test_negative_split_angle_raises(self):
        """Negative split_angle raises ValueError."""
        from blender_addon.handlers.mesh import _validate_custom_normals_params

        with pytest.raises(ValueError, match="split_angle"):
            _validate_custom_normals_params({
                "name": "Cube",
                "split_angle": -10.0,
            })

    def test_missing_name_raises(self):
        """Missing name raises ValueError."""
        from blender_addon.handlers.mesh import _validate_custom_normals_params

        with pytest.raises(ValueError, match="name"):
            _validate_custom_normals_params({})


# ---------------------------------------------------------------------------
# _validate_edge_data_params tests
# ---------------------------------------------------------------------------


class TestValidateEdgeDataParams:
    """Test edge data parameter validation."""

    def test_defaults_pass(self):
        """Default parameters with name pass validation."""
        from blender_addon.handlers.mesh import _validate_edge_data_params

        result = _validate_edge_data_params({"name": "Cube"})
        assert result["name"] == "Cube"
        assert result["operation"] == "SET_CREASE"
        assert result["edge_indices"] is None
        assert result["value"] == 1.0

    def test_all_operations_valid(self):
        """All valid operations pass validation."""
        from blender_addon.handlers.mesh import _validate_edge_data_params

        for op in ("SET_CREASE", "SET_BEVEL_WEIGHT", "SET_SHARP"):
            result = _validate_edge_data_params({
                "name": "Cube",
                "operation": op,
            })
            assert result["operation"] == op

    def test_invalid_operation_raises(self):
        """Invalid operation raises ValueError."""
        from blender_addon.handlers.mesh import _validate_edge_data_params

        with pytest.raises(ValueError, match="operation"):
            _validate_edge_data_params({
                "name": "Cube",
                "operation": "SET_SEAM",
            })

    def test_missing_name_raises(self):
        """Missing name raises ValueError."""
        from blender_addon.handlers.mesh import _validate_edge_data_params

        with pytest.raises(ValueError, match="name"):
            _validate_edge_data_params({})

    def test_value_out_of_range_raises(self):
        """Value > 1 raises ValueError."""
        from blender_addon.handlers.mesh import _validate_edge_data_params

        with pytest.raises(ValueError, match="value"):
            _validate_edge_data_params({
                "name": "Cube",
                "value": 1.5,
            })

    def test_negative_value_raises(self):
        """Negative value raises ValueError."""
        from blender_addon.handlers.mesh import _validate_edge_data_params

        with pytest.raises(ValueError, match="value"):
            _validate_edge_data_params({
                "name": "Cube",
                "value": -0.1,
            })

    def test_valid_edge_indices(self):
        """Valid edge indices pass."""
        from blender_addon.handlers.mesh import _validate_edge_data_params

        result = _validate_edge_data_params({
            "name": "Cube",
            "edge_indices": [0, 3, 7],
            "value": 0.5,
        })
        assert result["edge_indices"] == [0, 3, 7]
        assert result["value"] == 0.5

    def test_negative_edge_index_raises(self):
        """Negative edge index raises ValueError."""
        from blender_addon.handlers.mesh import _validate_edge_data_params

        with pytest.raises(ValueError, match="edge_indices"):
            _validate_edge_data_params({
                "name": "Cube",
                "edge_indices": [0, -1],
            })

    def test_non_list_edge_indices_raises(self):
        """Non-list edge_indices raises ValueError."""
        from blender_addon.handlers.mesh import _validate_edge_data_params

        with pytest.raises(ValueError, match="edge_indices"):
            _validate_edge_data_params({
                "name": "Cube",
                "edge_indices": "all",
            })

    def test_zero_value_passes(self):
        """Zero value (remove crease/weight) passes."""
        from blender_addon.handlers.mesh import _validate_edge_data_params

        result = _validate_edge_data_params({
            "name": "Cube",
            "value": 0.0,
        })
        assert result["value"] == 0.0


# ---------------------------------------------------------------------------
# Registration tests -- verify all new handlers are in COMMAND_HANDLERS
# ---------------------------------------------------------------------------


class TestCommandHandlerRegistration:
    """Verify all new handlers are registered in COMMAND_HANDLERS."""

    def test_scene_world_handlers_registered(self):
        """Scene/world handlers are registered."""
        from blender_addon.handlers import COMMAND_HANDLERS

        expected = [
            "setup_world",
            "add_light",
            "add_camera",
            "configure_render",
        ]
        for cmd in expected:
            assert cmd in COMMAND_HANDLERS, f"Missing handler registration: {cmd}"

    def test_collection_handlers_registered(self):
        """Collection handlers are registered."""
        from blender_addon.handlers import COMMAND_HANDLERS

        expected = [
            "create_collection",
            "move_to_collection",
            "set_visibility",
        ]
        for cmd in expected:
            assert cmd in COMMAND_HANDLERS, f"Missing handler registration: {cmd}"

    def test_mesh_data_handlers_registered(self):
        """Vertex color, custom normals, edge data handlers are registered."""
        from blender_addon.handlers import COMMAND_HANDLERS

        expected = [
            "mesh_vertex_color",
            "mesh_custom_normals",
            "mesh_edge_data",
        ]
        for cmd in expected:
            assert cmd in COMMAND_HANDLERS, f"Missing handler registration: {cmd}"
