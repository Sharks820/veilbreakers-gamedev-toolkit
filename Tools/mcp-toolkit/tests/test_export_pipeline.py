"""Integration tests for compose_map export pipeline Steps 11-16 (Phase 46 Plan 03).

Tests handler registration and compose_map step presence.
"""

from __future__ import annotations



# ---------------------------------------------------------------------------
# TestHandlerRegistration -- verify new handlers in EXTRA_HANDLERS
# ---------------------------------------------------------------------------


class TestHandlerRegistration:
    """Verify collision, vegetation, and splatmap handlers are registered."""

    def test_generate_collision_meshes_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert "generate_collision_meshes" in COMMAND_HANDLERS, \
            "generate_collision_meshes handler not registered"

    def test_serialize_vegetation_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert "serialize_vegetation" in COMMAND_HANDLERS, \
            "serialize_vegetation handler not registered"

    def test_export_splatmap_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert "export_splatmap" in COMMAND_HANDLERS, \
            "export_splatmap handler not registered"

    def test_render_angle_is_real_handler(self):
        """render_angle should be the real handler, not viewport screenshot alias."""
        from blender_addon.handlers import COMMAND_HANDLERS
        from blender_addon.handlers.viewport import handle_get_viewport_screenshot

        handler = COMMAND_HANDLERS.get("render_angle")
        assert handler is not None, "render_angle not registered"
        assert handler is not handle_get_viewport_screenshot, \
            "render_angle should NOT be aliased to handle_get_viewport_screenshot"


# ---------------------------------------------------------------------------
# TestComposeMapExportSteps -- verify step names in compose_map code
# ---------------------------------------------------------------------------


class TestComposeMapExportSteps:
    """Verify compose_map contains Steps 11-16 after heightmap_exported."""

    def _get_compose_map_source(self) -> str:
        """Read compose_map section from blender_server.py."""
        import inspect
        import veilbreakers_mcp.blender_server as bs_module
        return inspect.getsource(bs_module)

    def test_game_check_step_present(self):
        source = self._get_compose_map_source()
        assert "game_check_validated" in source

    def test_textures_baked_step_present(self):
        source = self._get_compose_map_source()
        assert "textures_baked" in source

    def test_lods_generated_step_present(self):
        source = self._get_compose_map_source()
        assert "lods_generated" in source

    def test_collisions_generated_step_present(self):
        source = self._get_compose_map_source()
        assert "collisions_generated" in source

    def test_data_exported_step_present(self):
        source = self._get_compose_map_source()
        assert "data_exported" in source

    def test_fbx_exported_step_present(self):
        source = self._get_compose_map_source()
        assert "fbx_exported" in source

    def test_steps_after_heightmap(self):
        """New steps appear AFTER heightmap_exported in the source."""
        source = self._get_compose_map_source()
        hm_pos = source.index("heightmap_exported")
        gc_pos = source.index("game_check_validated")
        assert gc_pos > hm_pos, "game_check_validated should be after heightmap_exported"

    def test_checkpoint_resume_pattern(self):
        """Each new step follows 'not in steps_completed' pattern."""
        source = self._get_compose_map_source()
        for step in ["game_check_validated", "textures_baked", "lods_generated",
                      "collisions_generated", "data_exported", "fbx_exported"]:
            pattern = f'"{step}" not in steps_completed'
            assert pattern in source, f"Step {step} missing checkpoint-resume guard"

    def test_collision_filters_structures(self):
        """Collision generation filters to structure objects only."""
        source = self._get_compose_map_source()
        assert "building" in source
        assert "wall" in source
        assert "gate" in source
        assert "_structure_objects" in source

    def test_fbx_uses_derive_addressable_groups(self):
        """FBX export step uses derive_addressable_groups."""
        source = self._get_compose_map_source()
        assert "derive_addressable_groups" in source

    def test_result_includes_new_fields(self):
        """Result dict includes game_check_failures and fbx_exported_files."""
        source = self._get_compose_map_source()
        assert "game_check_failures" in source
        assert "fbx_exported_files" in source
