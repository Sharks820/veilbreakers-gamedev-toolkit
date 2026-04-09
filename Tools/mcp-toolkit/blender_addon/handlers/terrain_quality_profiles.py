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
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Optional


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
    erosion_strategy: str = "hydraulic"
    checkpoint_retention: int = 4
    erosion_margin_cells: int = 8
    splatmap_bit_depth: int = 8
    heightmap_bit_depth: int = 16
    shadow_clipmap_bit_depth: int = 8
    extends: Optional[str] = None


# ---------------------------------------------------------------------------
# Built-in profiles
# ---------------------------------------------------------------------------


PREVIEW_PROFILE = TerrainQualityProfile(
    name="preview",
    erosion_iterations=2,
    erosion_strategy="hydraulic_fast",
    checkpoint_retention=2,
    erosion_margin_cells=4,
    splatmap_bit_depth=8,
    heightmap_bit_depth=16,
    shadow_clipmap_bit_depth=8,
    extends=None,
)

PRODUCTION_PROFILE = TerrainQualityProfile(
    name="production",
    erosion_iterations=8,
    erosion_strategy="hydraulic",
    checkpoint_retention=4,
    erosion_margin_cells=8,
    splatmap_bit_depth=8,
    heightmap_bit_depth=16,
    shadow_clipmap_bit_depth=8,
    extends="preview",
)

HERO_SHOT_PROFILE = TerrainQualityProfile(
    name="hero_shot",
    erosion_iterations=24,
    erosion_strategy="hydraulic_thermal",
    checkpoint_retention=8,
    erosion_margin_cells=16,
    splatmap_bit_depth=16,
    heightmap_bit_depth=32,
    shadow_clipmap_bit_depth=16,
    extends="production",
)

AAA_OPEN_WORLD_PROFILE = TerrainQualityProfile(
    name="aaa_open_world",
    erosion_iterations=48,
    erosion_strategy="hydraulic_thermal_wind",
    checkpoint_retention=12,
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
    return TerrainQualityProfile(
        name=child.name,
        erosion_iterations=max(
            child.erosion_iterations, parent.erosion_iterations
        ),
        erosion_strategy=child.erosion_strategy or parent.erosion_strategy,
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
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for name in list_quality_profiles():
        profile = _BUILTIN_PROFILES[name]
        out = root / f"{name}.json"
        out.write_text(json.dumps(asdict(profile), indent=2))
        written.append(out)
    return written


__all__ = [
    "TerrainQualityProfile",
    "PREVIEW_PROFILE",
    "PRODUCTION_PROFILE",
    "HERO_SHOT_PROFILE",
    "AAA_OPEN_WORLD_PROFILE",
    "load_quality_profile",
    "list_quality_profiles",
    "write_profile_jsons",
]
