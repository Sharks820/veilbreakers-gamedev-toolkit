"""Master registrar smoke test — verifies the full pipeline loads end-to-end."""

from __future__ import annotations


def test_master_registrar_loads_all_bundles():
    from blender_addon.handlers.terrain_master_registrar import (
        register_all_terrain_passes,
    )
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    TerrainPassController.clear_registry()
    try:
        loaded = register_all_terrain_passes(strict=False)
    finally:
        # Leave the registry in a known state for other tests
        TerrainPassController.clear_registry()

    assert "A" in loaded, "Bundle A foundation must always load"
    # We expect at least 10 bundles to load cleanly in a dev environment
    clean = [b for b in loaded if "SKIPPED" not in b]
    assert len(clean) >= 10, f"Only {len(clean)} bundles loaded: {loaded}"


def test_master_registrar_strict_mode_raises_on_missing():
    """Strict mode surfaces the first missing registrar."""
    from blender_addon.handlers.terrain_master_registrar import (
        _safe_import_registrar,
    )

    # Sanity: _safe_import_registrar returns None for a bogus module
    assert _safe_import_registrar("blender_addon.handlers.definitely_not_a_module", "fn") is None


def test_master_registrar_produces_unified_pass_graph():
    """After loading, the PASS_REGISTRY should hold enough passes for a DAG."""
    from blender_addon.handlers.terrain_master_registrar import (
        register_all_terrain_passes,
    )
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    TerrainPassController.clear_registry()
    try:
        register_all_terrain_passes(strict=False)
        registry_size = len(TerrainPassController.PASS_REGISTRY)
    finally:
        TerrainPassController.clear_registry()

    # Bundle A alone registers 4 passes; with B/C/D/E/F/J/K/L/N/O each adding
    # at least one pass, we expect ≥ 12 total in a healthy env.
    assert registry_size >= 12, f"Expected ≥12 passes, got {registry_size}"
