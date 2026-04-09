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
    viewport_vantage: Optional[object] = None,
    addon_version: Optional[Tuple[int, int, int]] = None,
    terrain_content_hash: Optional[str] = None,
    lockable_anchors: Sequence[str] = (),
) -> TerrainSceneRead:
    """Build a valid ``TerrainSceneRead`` snapshot.

    Rule 1 of the protocol requires one of these to exist before any
    mutation. In headless tests the caller supplies the content; real
    Blender would populate ``major_landforms`` by scanning ``bpy.data``,
    etc.

    The optional ``viewport_vantage``, ``addon_version``,
    ``terrain_content_hash``, and ``lockable_anchors`` parameters carry
    the Addendum 1.A.7 extended metadata. They are stashed onto the
    returned ``TerrainSceneRead`` via monkey-patch attributes so the
    frozen dataclass surface stays stable while new consumers can
    read them without another contract break.
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
    sr = TerrainSceneRead(
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
    # Stash the Addendum 1.A.7 extended metadata in a sidecar registry
    # so the frozen dataclass stays untouched.
    _EXTENDED_METADATA[id(sr)] = {
        "viewport_vantage": viewport_vantage,
        "addon_version": tuple(addon_version) if addon_version is not None else None,
        "terrain_content_hash": terrain_content_hash,
        "lockable_anchors": tuple(lockable_anchors),
    }
    return sr


# Module-level registry of extended metadata keyed by id(scene_read). Frozen
# dataclasses can't carry arbitrary attributes, so we keep this sidecar.
_EXTENDED_METADATA: "dict[int, dict]" = {}


def get_extended_metadata(sr: TerrainSceneRead) -> Optional[dict]:
    """Return the Addendum 1.A.7 extended metadata for ``sr``, if any."""
    return _EXTENDED_METADATA.get(id(sr))


def _coerce_bbox(raw) -> Optional[BBox]:
    if raw is None:
        return None
    if isinstance(raw, BBox):
        return raw
    if isinstance(raw, dict):
        return BBox(
            min_x=float(raw.get("min_x", 0.0)),
            min_y=float(raw.get("min_y", 0.0)),
            max_x=float(raw.get("max_x", 0.0)),
            max_y=float(raw.get("max_y", 0.0)),
        )
    if isinstance(raw, (list, tuple)) and len(raw) == 4:
        mn_x, mn_y, mx_x, mx_y = raw
        return BBox(float(mn_x), float(mn_y), float(mx_x), float(mx_y))
    return None


def handle_capture_scene_read(params: dict) -> dict:
    """MCP-style handler that wraps ``capture_scene_read`` for the bridge.

    Passes through the full parameter surface from Addendum 1.A.7 so
    bridge callers can produce a full-fidelity ``TerrainSceneRead`` with
    hero feature refs, waterfall chains, cave candidates, protected
    zones, and an explicit edit scope.
    """
    sr = capture_scene_read(
        reviewer=str(params.get("reviewer", "unknown")),
        focal_point_hint=params.get("focal_point"),
        major_landforms=tuple(params.get("major_landforms", ()) or ()),
        hero_features_present=tuple(params.get("hero_features_present", ()) or ()),
        hero_features_missing=tuple(params.get("hero_features_missing", ()) or ()),
        waterfall_chains=tuple(params.get("waterfall_chains", ()) or ()),
        cave_candidates=tuple(
            tuple(c) for c in (params.get("cave_candidates", ()) or ())
        ),
        protected_zones_in_region=tuple(
            params.get("protected_zones_in_region", ()) or ()
        ),
        edit_scope=_coerce_bbox(params.get("edit_scope")),
        success_criteria=tuple(params.get("success_criteria", ("scene_understood",))),
        viewport_vantage=params.get("viewport_vantage"),
        addon_version=(
            tuple(params.get("addon_version"))
            if params.get("addon_version") is not None
            else None
        ),
        terrain_content_hash=params.get("terrain_content_hash"),
        lockable_anchors=tuple(params.get("lockable_anchors", ()) or ()),
    )
    extended = get_extended_metadata(sr) or {}
    return {
        "ok": True,
        "timestamp": sr.timestamp,
        "reviewer": sr.reviewer,
        "focal_point": list(sr.focal_point),
        "major_landforms": list(sr.major_landforms),
        "hero_features_present_count": len(sr.hero_features_present),
        "hero_features_missing": list(sr.hero_features_missing),
        "waterfall_chains_count": len(sr.waterfall_chains),
        "cave_candidates_count": len(sr.cave_candidates),
        "protected_zones_in_region": list(sr.protected_zones_in_region),
        "edit_scope": list(sr.edit_scope.to_tuple()),
        "success_criteria": list(sr.success_criteria),
        "addon_version": (
            list(extended["addon_version"])
            if extended.get("addon_version") is not None
            else None
        ),
        "terrain_content_hash": extended.get("terrain_content_hash"),
        "lockable_anchors": list(extended.get("lockable_anchors", ())),
        "has_viewport_vantage": extended.get("viewport_vantage") is not None,
    }


__all__ = [
    "capture_scene_read",
    "handle_capture_scene_read",
    "get_extended_metadata",
]
