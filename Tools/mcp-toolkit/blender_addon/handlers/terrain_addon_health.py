"""Bundle R — addon version + handler registration integrity checks.

Headless-safe: real Blender would read ``bl_info`` via ``importlib.reload``
and check the live module. In headless mode we grep the source file for
``bl_info`` so the contract still holds on CI.

See Addendum 1.A.5.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

TERRAIN_ADDON_MIN_VERSION: Tuple[int, int, int] = (1, 0, 0)


class AddonVersionMismatch(RuntimeError):
    """Raised when the addon version is below the required floor."""


class AddonNotLoaded(RuntimeError):
    """Raised when the terrain addon is not importable."""


class StaleAddon(RuntimeError):
    """Raised when the on-disk addon differs from the in-memory one."""


def _addon_init_path() -> Path:
    # __init__.py of the blender_addon sibling of this module's parent
    return Path(__file__).resolve().parent.parent / "__init__.py"


def _read_bl_info_version() -> Optional[Tuple[int, ...]]:
    """Parse the ``version`` tuple out of the addon ``bl_info`` dict.

    Returns None if the file or tuple is missing. Pure-AST, so no Blender
    is required.
    """
    p = _addon_init_path()
    if not p.exists():
        return None
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
    except Exception:
        logger.debug("Failed to parse addon __init__.py for bl_info", exc_info=True)
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "bl_info":
                    if isinstance(node.value, ast.Dict):
                        for k, v in zip(node.value.keys, node.value.values):
                            if isinstance(k, ast.Constant) and k.value == "version":
                                if isinstance(v, ast.Tuple):
                                    parts: list[int] = []
                                    for elt in v.elts:
                                        if isinstance(elt, ast.Constant) and isinstance(
                                            elt.value, int
                                        ):
                                            parts.append(elt.value)
                                    return tuple(parts) if parts else None
    # Fallback: regex scan
    m = re.search(r'"version"\s*:\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', p.read_text(encoding="utf-8"))
    if m:
        return tuple(int(x) for x in m.groups())
    return None


def assert_addon_loaded() -> None:
    """Verify that the addon package is present on disk."""
    if not _addon_init_path().exists():
        raise AddonNotLoaded(
            f"blender_addon/__init__.py not found at {_addon_init_path()}"
        )


def assert_addon_version_matches(
    min_version: Tuple[int, ...] = TERRAIN_ADDON_MIN_VERSION,
    *,
    allow_missing: bool = False,
) -> None:
    """Raise ``AddonVersionMismatch`` if the on-disk addon is below min_version.

    Missing ``bl_info`` is a hard-fail by default per Addendum 1.A.5: an addon
    tree with no declared version is treated as version mismatch. Tests that
    intentionally run against a stripped tree may pass ``allow_missing=True``.
    """
    version = _read_bl_info_version()
    if version is None:
        if allow_missing:
            return
        raise AddonVersionMismatch(
            f"terrain addon at {_addon_init_path()} has no bl_info['version']; "
            f"required >= {min_version}. Missing bl_info is a hard-fail — "
            "pass allow_missing=True explicitly if this is intentional."
        )
    if tuple(version) < tuple(min_version):
        raise AddonVersionMismatch(
            f"terrain addon version {version} < required {min_version}. "
            "Upgrade the addon before running terrain passes."
        )


def assert_handlers_registered(required: Sequence[str]) -> None:
    """Check the COMMAND_HANDLERS dict exposes every name in ``required``."""
    from . import COMMAND_HANDLERS  # type: ignore

    missing = [name for name in required if name not in COMMAND_HANDLERS]
    if missing:
        raise AddonNotLoaded(
            f"COMMAND_HANDLERS missing required entries: {missing}"
        )


def detect_stale_addon() -> bool:
    """Return True if the disk version of __init__.py differs from the
    imported module's version.

    Headless stub — compares parsed ``bl_info['version']`` against the
    in-memory module's ``bl_info`` dict if importable.
    """
    on_disk = _read_bl_info_version()
    try:
        from .. import __init__ as _live  # type: ignore
    except Exception:
        logger.debug("Cannot import live addon for staleness check", exc_info=True)
        return False
    live_version = None
    live_bl = getattr(_live, "bl_info", None)
    if isinstance(live_bl, dict):
        live_version = live_bl.get("version")
    if on_disk is None or live_version is None:
        return False
    return tuple(on_disk) != tuple(live_version)


def force_addon_reload() -> None:
    """Re-import the addon package. No-op in headless mode (no bpy)."""
    import importlib

    try:
        from .. import __init__ as _live  # type: ignore

        importlib.reload(_live)
    except Exception:
        # Reload is best-effort; headless environments may not have bpy.
        logger.debug("Addon reload failed (expected in headless mode)", exc_info=True)


__all__ = [
    "TERRAIN_ADDON_MIN_VERSION",
    "AddonVersionMismatch",
    "AddonNotLoaded",
    "StaleAddon",
    "assert_addon_loaded",
    "assert_addon_version_matches",
    "assert_handlers_registered",
    "detect_stale_addon",
    "force_addon_reload",
]
