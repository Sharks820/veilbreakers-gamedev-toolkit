"""Bundle D supplement — terrain quality profiles.

Defines 4 preset quality profiles for the terrain pipeline (preview,
production, hero_shot, aaa_open_world) with inheritance. Profiles are
also written as JSON to ``Tools/mcp-toolkit/presets/terrain/quality_profiles/``
so external tools can inspect them.

Per Addendum 1.B.4 of docs/terrain_ultra_implementation_plan_2026-04-08.md.
No bpy imports — pure stdlib + dataclasses.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Dict, List, Optional

from .terrain_semantics import ErosionStrategy


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PresetLocked(Exception):
    """Raised when trying to modify a locked quality profile."""

    pass


# ---------------------------------------------------------------------------
# Profile dataclass
# ---------------------------------------------------------------------------


@dataclass
class TerrainQualityProfile:
    """Quality tier for the terrain pipeline.

    ``extends`` names a parent profile. Inherited fields are merged at
    load time by ``load_quality_profile``. A child profile that specifies
    ``erosion_iterations`` overrides the parent; otherwise the parent
    value is used as a floor.
    """

    name: str
    erosion_iterations: int = 8
    erosion_strategy: ErosionStrategy = ErosionStrategy.TILED_PADDED
    checkpoint_retention: int = 20
    erosion_margin_cells: int = 8
    splatmap_bit_depth: int = 8
    heightmap_bit_depth: int = 16
    shadow_clipmap_bit_depth: int = 8
    extends: Optional[str] = None
    lock_preset: bool = False
    save_every_n_operations: int = 0
    checkpoint_naming: str = "terrain_{nn}_{pass}_{hash}"


# ---------------------------------------------------------------------------
# Built-in profiles
#
# Numeric values per Addendum 1.B.4:
#   checkpoint_retention: 5 / 20 / 40 / 80
#   erosion_strategy:    TILED_PADDED for preview+production;
#                        EXACT for hero_shot+aaa_open_world (bit-exact seams).
# ---------------------------------------------------------------------------


PREVIEW_PROFILE = TerrainQualityProfile(
    name="preview",
    erosion_iterations=2,
    erosion_strategy=ErosionStrategy.TILED_PADDED,
    checkpoint_retention=5,
    erosion_margin_cells=4,
    splatmap_bit_depth=8,
    heightmap_bit_depth=16,
    shadow_clipmap_bit_depth=8,
    extends=None,
)

PRODUCTION_PROFILE = TerrainQualityProfile(
    name="production",
    erosion_iterations=8,
    erosion_strategy=ErosionStrategy.TILED_PADDED,
    checkpoint_retention=20,
    erosion_margin_cells=8,
    splatmap_bit_depth=8,
    heightmap_bit_depth=16,
    shadow_clipmap_bit_depth=8,
    extends="preview",
)

HERO_SHOT_PROFILE = TerrainQualityProfile(
    name="hero_shot",
    erosion_iterations=24,
    erosion_strategy=ErosionStrategy.EXACT,
    checkpoint_retention=40,
    erosion_margin_cells=16,
    splatmap_bit_depth=16,
    heightmap_bit_depth=32,
    shadow_clipmap_bit_depth=16,
    extends="production",
)

AAA_OPEN_WORLD_PROFILE = TerrainQualityProfile(
    name="aaa_open_world",
    erosion_iterations=48,
    erosion_strategy=ErosionStrategy.EXACT,
    checkpoint_retention=80,
    erosion_margin_cells=32,
    splatmap_bit_depth=16,
    heightmap_bit_depth=32,
    shadow_clipmap_bit_depth=16,
    extends="hero_shot",
)


_BUILTIN_PROFILES: Dict[str, TerrainQualityProfile] = {
    "preview": PREVIEW_PROFILE,
    "production": PRODUCTION_PROFILE,
    "hero_shot": HERO_SHOT_PROFILE,
    "aaa_open_world": AAA_OPEN_WORLD_PROFILE,
}


# ---------------------------------------------------------------------------
# Loader with inheritance merge
# ---------------------------------------------------------------------------


def _merge_with_parent(
    child: TerrainQualityProfile,
    parent: TerrainQualityProfile,
) -> TerrainQualityProfile:
    """Merge ``child`` over ``parent``: numeric fields take the max of both.

    Profile inheritance contract (Addendum 1.B.4): a child profile can
    strengthen quality but never weaken it, so numeric quality knobs use
    the max between parent and child. Strategy strings take the child's
    value. ``checkpoint_retention``, ``erosion_iterations``, bit depths
    are all "higher = better" and use max().
    """
    # For the erosion strategy, child always wins (EXACT can downgrade to
    # TILED_PADDED only when explicitly overridden).
    return TerrainQualityProfile(
        name=child.name,
        erosion_iterations=max(
            child.erosion_iterations, parent.erosion_iterations
        ),
        erosion_strategy=child.erosion_strategy,
        checkpoint_retention=max(
            child.checkpoint_retention, parent.checkpoint_retention
        ),
        erosion_margin_cells=max(
            child.erosion_margin_cells, parent.erosion_margin_cells
        ),
        splatmap_bit_depth=max(
            child.splatmap_bit_depth, parent.splatmap_bit_depth
        ),
        heightmap_bit_depth=max(
            child.heightmap_bit_depth, parent.heightmap_bit_depth
        ),
        shadow_clipmap_bit_depth=max(
            child.shadow_clipmap_bit_depth, parent.shadow_clipmap_bit_depth
        ),
        extends=child.extends,
        lock_preset=child.lock_preset or parent.lock_preset,
        save_every_n_operations=max(
            child.save_every_n_operations, parent.save_every_n_operations
        ),
        checkpoint_naming=child.checkpoint_naming,
    )


def load_quality_profile(name: str) -> TerrainQualityProfile:
    """Return the resolved (parent-merged) profile for ``name``."""
    if name not in _BUILTIN_PROFILES:
        raise KeyError(f"Unknown quality profile: {name!r}")
    profile = _BUILTIN_PROFILES[name]
    if profile.extends:
        parent = load_quality_profile(profile.extends)
        return _merge_with_parent(profile, parent)
    return replace(profile)


def list_quality_profiles() -> List[str]:
    """Return all built-in profile names in quality-ascending order."""
    return ["preview", "production", "hero_shot", "aaa_open_world"]


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------


def write_profile_jsons(root: Path) -> List[Path]:
    """Write every built-in profile as ``{name}.json`` under ``root``.

    Returns the list of paths written. Idempotent — safe to call at
    import time in tests that need the JSON files on disk.

    Rejects path-traversal and forbids writing outside either the
    repo's ``Tools/mcp-toolkit/`` tree or a caller-supplied
    ``tempfile.gettempdir()`` ancestor, so poisoned callers cannot
    clobber unrelated filesystem state.
    """
    import os
    import tempfile

    root = Path(root).resolve()
    if ".." in str(root):
        raise ValueError(f"write_profile_jsons: path traversal rejected: {root}")
    tmp_root = Path(tempfile.gettempdir()).resolve()
    this_file = Path(__file__).resolve()
    # walk up to find Tools/mcp-toolkit ancestor
    repo_root: Optional[Path] = None
    for ancestor in this_file.parents:
        if ancestor.name == "mcp-toolkit":
            repo_root = ancestor
            break
    allowed_roots: List[Path] = [tmp_root]
    if repo_root is not None:
        allowed_roots.append(repo_root.resolve())
    if not any(
        str(root).startswith(str(allowed) + os.sep) or str(root) == str(allowed)
        for allowed in allowed_roots
    ):
        raise ValueError(
            f"write_profile_jsons: refusing to write outside sandbox. "
            f"root={root} allowed={allowed_roots}"
        )
    root.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for name in list_quality_profiles():
        profile = _BUILTIN_PROFILES[name]
        payload = asdict(profile)
        # ErosionStrategy is an Enum — serialize as its .value string
        if isinstance(payload.get("erosion_strategy"), ErosionStrategy):
            payload["erosion_strategy"] = payload["erosion_strategy"].value
        elif hasattr(profile.erosion_strategy, "value"):
            payload["erosion_strategy"] = profile.erosion_strategy.value
        out = root / f"{name}.json"
        out.write_text(json.dumps(payload, indent=2))
        written.append(out)
    return written


# ---------------------------------------------------------------------------
# Lock / unlock helpers
# ---------------------------------------------------------------------------


def lock_preset(profile: TerrainQualityProfile) -> TerrainQualityProfile:
    """Return a copy of the profile with lock_preset=True."""
    from dataclasses import replace

    return replace(profile, lock_preset=True)


def unlock_preset(profile: TerrainQualityProfile) -> TerrainQualityProfile:
    """Return a copy with lock_preset=False."""
    from dataclasses import replace

    return replace(profile, lock_preset=False)


__all__ = [
    "PresetLocked",
    "TerrainQualityProfile",
    "PREVIEW_PROFILE",
    "PRODUCTION_PROFILE",
    "HERO_SHOT_PROFILE",
    "AAA_OPEN_WORLD_PROFILE",
    "load_quality_profile",
    "list_quality_profiles",
    "write_profile_jsons",
    "lock_preset",
    "unlock_preset",
]
