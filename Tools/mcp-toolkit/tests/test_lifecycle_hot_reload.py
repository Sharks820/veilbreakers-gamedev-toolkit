"""Tests for addon lifecycle and hot-reload safety (F090-F097).

Verifies:
- socket_server.stop() drains pending commands
- register_default_passes is idempotent (overwrite not accumulate)
- _safe_import_registrar logs on failure instead of silent swallow
- TerrainPassController.clear_registry actually empties PASS_REGISTRY
"""

from __future__ import annotations

import logging
import queue
import threading
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# F090: socket_server.stop() drains pending commands
# ---------------------------------------------------------------------------


class TestSocketServerDrainOnStop:
    """Verify that stop() resolves all pending command events."""

    def _make_server(self):
        """Create a BlenderMCPServer without starting the socket."""
        with patch("blender_addon.socket_server.bpy"):
            from blender_addon.socket_server import BlenderMCPServer

            srv = BlenderMCPServer.__new__(BlenderMCPServer)
            srv.port = 9876
            srv.command_queue = queue.Queue()
            srv.server_thread = None
            srv.running = True
            srv._server_socket = None
            return srv

    def test_stop_drains_queued_commands(self):
        """Pending commands get error responses on shutdown."""
        srv = self._make_server()
        events = []
        containers = []
        for _ in range(3):
            evt = threading.Event()
            ctr: dict = {}
            srv.command_queue.put(({"type": "test"}, evt, ctr))
            events.append(evt)
            containers.append(ctr)

        # Patch bpy.app.timers to avoid Blender dependency
        with patch("blender_addon.socket_server.bpy") as mock_bpy:
            mock_bpy.app.timers.is_registered.return_value = False
            srv.stop()

        # All events should be set
        for evt in events:
            assert evt.is_set(), "Event was not signalled during drain"

        # All containers should have shutdown error
        for ctr in containers:
            assert ctr["response"]["status"] == "error"
            assert "shutting down" in ctr["response"]["message"].lower()

    def test_stop_empty_queue_is_fine(self):
        """Stop with no pending commands should not raise."""
        srv = self._make_server()
        with patch("blender_addon.socket_server.bpy") as mock_bpy:
            mock_bpy.app.timers.is_registered.return_value = False
            srv.stop()
        assert not srv.running


# ---------------------------------------------------------------------------
# F091-F092: register_default_passes idempotency
# ---------------------------------------------------------------------------


class TestRegisterDefaultPassesIdempotent:
    """Calling register_default_passes twice must not duplicate entries."""

    def test_double_registration_same_count(self):
        from blender_addon.handlers.terrain_pipeline import (
            TerrainPassController,
            register_default_passes,
        )

        TerrainPassController.clear_registry()
        register_default_passes()
        count_first = len(TerrainPassController.PASS_REGISTRY)

        register_default_passes()
        count_second = len(TerrainPassController.PASS_REGISTRY)

        assert count_first == count_second, (
            f"Double registration changed registry size: {count_first} -> {count_second}"
        )
        # Cleanup
        TerrainPassController.clear_registry()

    def test_clear_registry_empties(self):
        from blender_addon.handlers.terrain_pipeline import (
            TerrainPassController,
            register_default_passes,
        )

        TerrainPassController.clear_registry()
        register_default_passes()
        assert len(TerrainPassController.PASS_REGISTRY) > 0

        TerrainPassController.clear_registry()
        assert len(TerrainPassController.PASS_REGISTRY) == 0


# ---------------------------------------------------------------------------
# F093-F094: _safe_import_registrar logging
# ---------------------------------------------------------------------------


class TestSafeImportRegistrar:
    """_safe_import_registrar must log on failure, not silently return None."""

    def test_missing_module_returns_none(self):
        from blender_addon.handlers.terrain_master_registrar import (
            _safe_import_registrar,
        )

        result = _safe_import_registrar("nonexistent.module.path", "func")
        assert result is None

    def test_missing_module_logs_debug(self, caplog):
        from blender_addon.handlers.terrain_master_registrar import (
            _safe_import_registrar,
        )

        with caplog.at_level(logging.DEBUG, logger="blender_addon.handlers.terrain_master_registrar"):
            _safe_import_registrar("nonexistent.module.path", "func")
        assert any("not found" in r.message for r in caplog.records), (
            f"Expected 'not found' log message, got: {[r.message for r in caplog.records]}"
        )

    def test_non_callable_attr_returns_none(self, caplog):
        from blender_addon.handlers.terrain_master_registrar import (
            _safe_import_registrar,
        )

        # os.path is a module attribute that exists but is not callable
        with caplog.at_level(logging.WARNING, logger="blender_addon.handlers.terrain_master_registrar"):
            result = _safe_import_registrar("os", "sep")
        assert result is None

    def test_valid_registrar_returns_callable(self):
        from blender_addon.handlers.terrain_master_registrar import (
            _safe_import_registrar,
        )

        fn = _safe_import_registrar(
            "blender_addon.handlers.terrain_pipeline", "register_default_passes"
        )
        assert fn is not None
        assert callable(fn)


# ---------------------------------------------------------------------------
# F095-F097: register_all_terrain_passes resilience
# ---------------------------------------------------------------------------


class TestRegisterAllTerrainPasses:
    """Master registrar handles missing bundles gracefully."""

    def test_returns_loaded_bundle_list(self):
        from blender_addon.handlers.terrain_master_registrar import (
            register_all_terrain_passes,
        )
        from blender_addon.handlers.terrain_pipeline import TerrainPassController

        TerrainPassController.clear_registry()
        loaded = register_all_terrain_passes(strict=False)
        assert "A" in loaded, "Bundle A (foundation) must always load"
        TerrainPassController.clear_registry()

    def test_strict_mode_raises_on_missing(self):
        from blender_addon.handlers.terrain_master_registrar import (
            register_all_terrain_passes,
        )
        from blender_addon.handlers.terrain_pipeline import TerrainPassController

        TerrainPassController.clear_registry()
        # Patch one registrar to simulate missing bundle
        with patch(
            "blender_addon.handlers.terrain_master_registrar._safe_import_registrar",
            side_effect=lambda m, a: None,
        ):
            with pytest.raises(ImportError):
                register_all_terrain_passes(strict=True)
        TerrainPassController.clear_registry()
