"""Bundle D supplement — preset locking + autosave + retention.

Extends ``terrain_checkpoints`` (Bundle D) without mutating it. Adds:
  * preset lock registry + ``PresetLocked`` exception
  * content-hashed checkpoint filename generator
  * periodic ``save_every_n_operations`` monkey-patch helper
  * retention policy enforcer keyed off ``TerrainQualityProfile``

Per Addendum 1.B.4. No bpy imports.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Callable, List, Optional, Set

from .terrain_quality_profiles import TerrainQualityProfile


# ---------------------------------------------------------------------------
# Preset locks
# ---------------------------------------------------------------------------


class PresetLocked(RuntimeError):
    """Raised when attempting to mutate a locked preset."""


_PRESET_LOCKS: Set[str] = set()


def lock_preset(name: str) -> None:
    """Prevent mutations to preset ``name`` until explicitly unlocked."""
    _PRESET_LOCKS.add(name)


def unlock_preset(name: str) -> None:
    """Remove the lock on preset ``name`` (no-op if not locked)."""
    _PRESET_LOCKS.discard(name)


def is_preset_locked(name: str) -> bool:
    return name in _PRESET_LOCKS


def assert_preset_unlocked(name: str) -> None:
    """Raise ``PresetLocked`` if the preset is locked."""
    if is_preset_locked(name):
        raise PresetLocked(f"preset {name!r} is locked")


# ---------------------------------------------------------------------------
# Autosave monkey-patch
# ---------------------------------------------------------------------------


def save_every_n_operations(
    controller: Any,
    n: int,
) -> Callable[[], None]:
    """Wrap ``controller.run_pass`` so every Nth call triggers a checkpoint.

    Returns an "unpatch" callable that restores the original behavior.
    The controller must expose ``run_pass`` and ``_save_checkpoint``; the
    wrapper calls the checkpoint save after every Nth successful pass.
    """
    if n <= 0:
        raise ValueError(f"n must be >= 1, got {n}")

    original = getattr(controller, "run_pass", None)
    if not callable(original):
        raise AttributeError(
            "controller has no callable run_pass; cannot auto-save"
        )

    counter = {"i": 0}

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        counter["i"] += 1
        if counter["i"] % n == 0:
            save_fn = getattr(controller, "_save_checkpoint", None)
            if callable(save_fn):
                pass_name = getattr(result, "pass_name", "autosave")
                try:
                    save_fn(pass_name)
                except Exception:
                    # Autosave must never bring down the pipeline.
                    pass
        return result

    controller.run_pass = wrapped  # type: ignore[assignment]

    def unpatch() -> None:
        controller.run_pass = original  # type: ignore[assignment]

    return unpatch


# ---------------------------------------------------------------------------
# Checkpoint filename generator
# ---------------------------------------------------------------------------


_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9_\-]+")


def _sanitize(name: str) -> str:
    return _SAFE_NAME_RE.sub("_", name).strip("_") or "pass"


def generate_checkpoint_filename(
    pass_num: int,
    pass_name: str,
    content_hash: str,
) -> str:
    """Return ``terrain_{pass_num:02d}_{pass_name}_{content_hash[:8]}.blend``.

    ``content_hash`` may be a longer hash; only the first 8 hex characters
    are embedded. ``pass_name`` is sanitized to ``[a-zA-Z0-9_-]``.
    """
    if pass_num < 0:
        raise ValueError(f"pass_num must be >= 0, got {pass_num}")
    safe = _sanitize(pass_name)
    short = (content_hash or "").strip()[:8] or "00000000"
    return f"terrain_{pass_num:02d}_{safe}_{short}.blend"


# ---------------------------------------------------------------------------
# Retention policy
# ---------------------------------------------------------------------------


def enforce_retention_policy(
    checkpoint_dir: Path,
    profile: TerrainQualityProfile,
) -> List[Path]:
    """Delete oldest checkpoints beyond ``profile.checkpoint_retention``.

    Only ``terrain_*.blend`` files in the given directory are considered.
    Oldest = smallest mtime. Returns the list of paths deleted. Non-fatal
    if the directory does not exist (returns empty list).
    """
    checkpoint_dir = Path(checkpoint_dir)
    if not checkpoint_dir.exists():
        return []

    keep = max(int(profile.checkpoint_retention), 0)
    files = [
        p for p in checkpoint_dir.iterdir()
        if p.is_file() and p.name.startswith("terrain_") and p.suffix == ".blend"
    ]
    if len(files) <= keep:
        return []

    files.sort(key=lambda p: p.stat().st_mtime)
    to_delete = files[: len(files) - keep]
    deleted: List[Path] = []
    for p in to_delete:
        try:
            p.unlink()
            deleted.append(p)
        except OSError:
            continue
    return deleted


__all__ = [
    "PresetLocked",
    "lock_preset",
    "unlock_preset",
    "is_preset_locked",
    "assert_preset_unlocked",
    "save_every_n_operations",
    "generate_checkpoint_filename",
    "enforce_retention_policy",
]
