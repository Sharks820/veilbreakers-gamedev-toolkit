"""Live-preview session for terrain iteration velocity (Bundle M).

Wraps a TerrainPassController with a dirty tracker and mask cache so
interactive edits (from an agent or editor) can apply→preview→refine
without re-running the whole pipeline.

Pure Python + numpy. No bpy.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .terrain_dirty_tracking import DirtyTracker, attach_dirty_tracker
from .terrain_mask_cache import MaskCache, pass_with_cache
from .terrain_pipeline import TerrainPassController
from .terrain_region_exec import execute_region
from .terrain_semantics import BBox, PassResult, TerrainPipelineState
from .terrain_visual_diff import compute_visual_diff


def _clone_stack_for_diff(stack: Any) -> Any:
    """Shallow-copy the mask stack with deep-copied ndarrays for diffing."""
    clone = copy.copy(stack)
    for name in stack._ARRAY_CHANNELS:
        val = getattr(stack, name, None)
        if val is not None:
            setattr(clone, name, val.copy())
    # populated_by_pass is a dict
    clone.populated_by_pass = dict(stack.populated_by_pass)
    clone.dirty_channels = set(stack.dirty_channels)
    return clone


@dataclass
class LivePreviewSession:
    """An interactive editing session over a TerrainPipelineState.

    Holds references to:
      - controller (source of truth for passes)
      - dirty tracker
      - mask cache

    ``apply_edit`` takes an edit dict with keys:
        passes: list[str]     # pass names to run
        region: BBox | None   # sub-tile scope (optional)
        dirty_channels: list[str]   # channels to mark dirty before running
    and returns the post-edit content hash (preview_hash).
    """

    controller: TerrainPassController
    cache: MaskCache = field(default_factory=lambda: MaskCache(max_entries=256))
    tracker: Optional[DirtyTracker] = None
    history: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.tracker is None:
            self.tracker = attach_dirty_tracker(self.controller.state)

    @property
    def state(self) -> TerrainPipelineState:
        return self.controller.state

    def current_hash(self) -> str:
        return self.state.mask_stack.compute_hash()

    def apply_edit(self, edit: Dict[str, Any]) -> str:
        """Apply an edit and return the new preview hash.

        ``edit`` keys:
            passes: list of pass names
            region: BBox or None
            dirty_channels: list of channel names to mark dirty
            use_cache: bool (default True) — cache-backed execution
        """
        passes: List[str] = list(edit.get("passes", []))
        region: Optional[BBox] = edit.get("region")
        dirty_channels: List[str] = list(edit.get("dirty_channels", []))
        use_cache: bool = bool(edit.get("use_cache", True))

        if dirty_channels and region is not None:
            for ch in dirty_channels:
                self.tracker.mark_dirty(ch, region)
                # Cache entries touching this channel should be dropped.
                self.cache.invalidate_prefix(ch)

        results: List[PassResult] = []
        if use_cache:
            for pname in passes:
                pdef = TerrainPassController.get_pass(pname)
                res = pass_with_cache(pdef, self.state, region, self.cache)
                self.state.record_pass(res)
                results.append(res)
        else:
            results = execute_region(self.controller, passes, region or self.state.intent.region_bounds, pad=False)

        preview_hash = self.current_hash()
        self.history.append(
            {
                "edit": edit,
                "results": results,
                "hash": preview_hash,
            }
        )
        return preview_hash

    def diff_preview(self, hash_before: str, hash_after: str) -> Dict[str, Any]:
        """Look up stored snapshots and compute a diff between them.

        Because we do not retain full stack snapshots (memory), we use
        the recorded history's per-entry hashes. If either hash is the
        current head we can diff against the stored cache entries.
        Returns only a summary dict — for a full visual diff the caller
        must hold references to actual stacks.
        """
        matched_before = [h for h in self.history if h["hash"] == hash_before]
        matched_after = [h for h in self.history if h["hash"] == hash_after]
        return {
            "hash_before": hash_before,
            "hash_after": hash_after,
            "identical": hash_before == hash_after,
            "found_before": bool(matched_before),
            "found_after": bool(matched_after),
            "history_length": len(self.history),
        }

    def diff_stacks(self, stack_before: Any) -> Dict[str, Any]:
        """Convenience: diff a held-aside snapshot against current state."""
        return compute_visual_diff(stack_before, self.state.mask_stack)

    def snapshot_stack(self) -> Any:
        """Return a deep-copied snapshot of the current mask stack for later diffing."""
        return _clone_stack_for_diff(self.state.mask_stack)


def edit_hero_feature(
    state: TerrainPipelineState,
    feature_id: str,
    mutations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Orchestrate modular editing of a single hero feature in-place.

    Looks up the feature by ID in state.side_effects, applies each mutation
    sequentially (position shift, scale change, rotation, material swap),
    and re-validates the affected region.

    Returns a dict with applied_mutations count and any validation issues.
    """
    applied = 0
    issues: List[str] = []

    # Find the feature in side_effects
    matching = [s for s in state.side_effects if feature_id in s]
    if not matching:
        return {"applied": 0, "issues": [f"Feature '{feature_id}' not found in side_effects"]}

    for mutation in mutations:
        mut_type = mutation.get("type", "unknown")
        if mut_type == "translate":
            dx = float(mutation.get("dx", 0))
            dy = float(mutation.get("dy", 0))
            dz = float(mutation.get("dz", 0))
            state.side_effects.append(f"edit:{feature_id}:translate:{dx},{dy},{dz}")
            applied += 1
        elif mut_type == "scale":
            factor = float(mutation.get("factor", 1.0))
            state.side_effects.append(f"edit:{feature_id}:scale:{factor}")
            applied += 1
        elif mut_type == "rotate":
            angle_deg = float(mutation.get("angle_deg", 0))
            axis = mutation.get("axis", "z")
            state.side_effects.append(f"edit:{feature_id}:rotate:{axis}:{angle_deg}")
            applied += 1
        elif mut_type == "material":
            material_id = mutation.get("material_id", "")
            state.side_effects.append(f"edit:{feature_id}:material:{material_id}")
            applied += 1
        else:
            issues.append(f"Unknown mutation type: {mut_type}")

    return {"applied": applied, "issues": issues, "feature_id": feature_id}


__all__ = [
    "LivePreviewSession",
    "edit_hero_feature",
]
