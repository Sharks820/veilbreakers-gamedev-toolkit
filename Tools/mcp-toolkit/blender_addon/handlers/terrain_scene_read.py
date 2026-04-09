"""Bundle R — capture_scene_read handler.

Produces ``TerrainSceneRead`` snapshots per §5.3 of the implementation
plan. Headless mode accepts supplied kwargs; real Blender would walk the
current scene via ``bpy.data``.

See Addendum 1.A.7.
"""

from __future__ import annotations

import time
from typing import Iterable, Optional, Sequence, Tuple

from .terrain_semantics import (
    BBox,
    HeroFeatureRef,
    TerrainSceneRead,
    WaterfallChainRef,
)


def capture_scene_read(
    *,
    reviewer: str,
    focal_point_hint: Optional[Tuple[float, float, float]] = None,
    major_landforms: Sequence[str] = (),
    hero_features_present: Sequence[HeroFeatureRef] = (),
    hero_features_missing: Sequence[str] = (),
    waterfall_chains: Sequence[WaterfallChainRef] = (),
    cave_candidates: Sequence[Tuple[float, float, float]] = (),
    protected_zones_in_region: Sequence[str] = (),
    edit_scope: Optional[BBox] = None,
    success_criteria: Sequence[str] = ("scene_understood",),
) -> TerrainSceneRead:
    """Build a valid ``TerrainSceneRead`` snapshot.

    Rule 1 of the protocol requires one of these to exist before any
    mutation. In headless tests the caller supplies the content; real
    Blender would populate ``major_landforms`` by scanning ``bpy.data``,
    etc.
    """
    focal = (
        tuple(float(x) for x in focal_point_hint)
        if focal_point_hint is not None
        else (0.0, 0.0, 0.0)
    )
    scope = edit_scope if edit_scope is not None else BBox(
        min_x=focal[0] - 25.0,
        min_y=focal[1] - 25.0,
        max_x=focal[0] + 25.0,
        max_y=focal[1] + 25.0,
    )
    return TerrainSceneRead(
        timestamp=time.time(),
        major_landforms=tuple(major_landforms),
        focal_point=focal,
        hero_features_present=tuple(hero_features_present),
        hero_features_missing=tuple(hero_features_missing),
        waterfall_chains=tuple(waterfall_chains),
        cave_candidates=tuple(tuple(c) for c in cave_candidates),
        protected_zones_in_region=tuple(protected_zones_in_region),
        edit_scope=scope,
        success_criteria=tuple(success_criteria),
        reviewer=str(reviewer),
    )


def handle_capture_scene_read(params: dict) -> dict:
    """MCP-style handler that wraps ``capture_scene_read`` for the bridge."""
    sr = capture_scene_read(
        reviewer=str(params.get("reviewer", "unknown")),
        focal_point_hint=params.get("focal_point"),
        major_landforms=tuple(params.get("major_landforms", ()) or ()),
        hero_features_missing=tuple(params.get("hero_features_missing", ()) or ()),
        success_criteria=tuple(params.get("success_criteria", ("scene_understood",))),
    )
    return {
        "ok": True,
        "timestamp": sr.timestamp,
        "reviewer": sr.reviewer,
        "focal_point": list(sr.focal_point),
        "major_landforms": list(sr.major_landforms),
        "edit_scope": list(sr.edit_scope.to_tuple()),
    }


__all__ = ["capture_scene_read", "handle_capture_scene_read"]
