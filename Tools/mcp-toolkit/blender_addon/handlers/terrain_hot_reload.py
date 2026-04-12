"""Hot-reload watcher for terrain rule modules (Bundle M).

Re-imports biome-rule / material-rule modules when their source files
change on disk, so tuning iteration doesn't require a Blender restart.

Pure Python. No bpy.
"""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Dict, List, Optional


# Modules we will attempt to reload. Missing modules are silently skipped.
_BIOME_RULE_MODULES = (
    "blender_addon.handlers.terrain_ecotone_graph",
    "blender_addon.handlers.terrain_materials_v2",
    "blender_addon.handlers.terrain_banded",
)

_MATERIAL_RULE_MODULES = (
    "blender_addon.handlers.terrain_materials",
    "blender_addon.handlers.terrain_materials_v2",
)


def _module_path(mod: ModuleType) -> Optional[Path]:
    f = getattr(mod, "__file__", None)
    return Path(f) if f else None


def _safe_reload(name: str) -> bool:
    mod = sys.modules.get(name)
    if mod is None:
        try:
            importlib.import_module(name)
            return True
        except Exception:
            return False
    try:
        importlib.reload(mod)
        return True
    except Exception:
        return False


def reload_biome_rules() -> List[str]:
    """Reload biome-rule modules. Returns list of successfully reloaded names."""
    ok: List[str] = []
    for name in _BIOME_RULE_MODULES:
        if _safe_reload(name):
            ok.append(name)
    return ok


def reload_material_rules() -> List[str]:
    ok: List[str] = []
    for name in _MATERIAL_RULE_MODULES:
        if _safe_reload(name):
            ok.append(name)
    return ok


@dataclass
class HotReloadWatcher:
    """Watches rule-module source files and reloads them when mtime changes."""

    watched_modules: List[str] = field(default_factory=list)
    _mtimes: Dict[str, float] = field(default_factory=dict)

    def add(self, module_name: str) -> None:
        if module_name not in self.watched_modules:
            self.watched_modules.append(module_name)
            mod = sys.modules.get(module_name)
            if mod is not None:
                p = _module_path(mod)
                if p and p.exists():
                    self._mtimes[module_name] = p.stat().st_mtime

    def watch_biome_rules(self) -> None:
        for m in _BIOME_RULE_MODULES:
            self.add(m)

    def watch_material_rules(self) -> None:
        for m in _MATERIAL_RULE_MODULES:
            self.add(m)

    def check_and_reload(self) -> List[str]:
        """Check mtimes and reload any module whose source file changed.

        Returns list of reloaded module names.
        """
        reloaded: List[str] = []
        for name in list(self.watched_modules):
            mod = sys.modules.get(name)
            if mod is None:
                if _safe_reload(name):
                    reloaded.append(name)
                    new_mod = sys.modules.get(name)
                    if new_mod:
                        p = _module_path(new_mod)
                        if p and p.exists():
                            self._mtimes[name] = p.stat().st_mtime
                continue
            p = _module_path(mod)
            if p is None or not p.exists():
                continue
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            prev = self._mtimes.get(name)
            if prev is None:
                self._mtimes[name] = mtime
                continue
            if mtime > prev:
                if _safe_reload(name):
                    reloaded.append(name)
                    self._mtimes[name] = mtime
        return reloaded

    def force_reload_all(self) -> List[str]:
        out: List[str] = []
        for name in list(self.watched_modules):
            if _safe_reload(name):
                out.append(name)
        return out


__all__ = [
    "HotReloadWatcher",
    "reload_biome_rules",
    "reload_material_rules",
]
