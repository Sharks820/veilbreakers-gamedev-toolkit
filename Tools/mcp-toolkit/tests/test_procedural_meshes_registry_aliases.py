"""Regression tests for procedural mesh registry category aliases."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_HANDLERS_DIR = Path(__file__).resolve().parent.parent / "blender_addon" / "handlers"
_spec = importlib.util.spec_from_file_location(
    "procedural_meshes",
    str(_HANDLERS_DIR / "procedural_meshes.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

GENERATORS = _mod.GENERATORS


def test_legacy_category_aliases_resolve() -> None:
    """Legacy category names should still resolve to the canonical registry."""
    aliases = {
        "door": "door_window",
        "forest_animals": "forest_animal",
        "mountain_animals": "mountain_animal",
        "domestic_animals": "domestic_animal",
        "swamp_animals": "swamp_animal",
    }
    for alias, canonical in aliases.items():
        assert alias in GENERATORS
        assert canonical in GENERATORS
        assert set(GENERATORS[alias].keys()) == set(GENERATORS[canonical].keys())
        name, func = next(iter(GENERATORS[alias].items()))
        result = func()
        assert result["metadata"]["category"] == alias, (
            f"{alias}/{name} did not preserve alias category metadata"
        )


def test_legacy_aliases_do_not_pollute_canonical_registry_keys() -> None:
    """Alias support must not change the canonical registry surface."""
    alias_names = {
        "door",
        "forest_animals",
        "mountain_animals",
        "domestic_animals",
        "swamp_animals",
    }
    assert alias_names.isdisjoint(set(GENERATORS.keys()))
