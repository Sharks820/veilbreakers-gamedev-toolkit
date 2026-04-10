"""Bundle R — runtime protocol enforcement.

Turns the 7 rules from TERRAIN_EDITING_PROTOCOL.md into callable Python gates
that any terrain mutation handler can route through. Any gate failure raises
``ProtocolViolation`` — the handler is expected to let this propagate.

See docs/terrain_ultra_implementation_plan_2026-04-08.md Addendum 1.A.2 for
the authoritative spec of each rule.
"""

from __future__ import annotations

import functools
import time
from typing import Any, Callable, Optional

from .terrain_semantics import (
    BBox,
    TerrainAnchor,
    TerrainIntentState,
    TerrainPipelineState,
)

TERRAIN_ADDON_MIN_VERSION = (1, 0, 0)

# Default thresholds per Addendum 1.A.2
DEFAULT_SCENE_READ_MAX_AGE_S = 300.0
DEFAULT_BULK_EDIT_CELL_FRACTION = 0.02  # > 2% of tile cells = bulk
DEFAULT_BULK_EDIT_OBJECT_COUNT = 20
VALID_PLACEMENT_CLASSES = frozenset(
    {"surface", "interior", "above_surface", "below_surface"}
)


class ProtocolViolation(RuntimeError):
    """Raised when a terrain mutation bypasses one of the 7 enforced rules."""


class ProtocolGate:
    """The 7 terrain-editing rules, as callable static gates.

    Each rule takes whatever context it needs (state and/or params dict)
    and either returns ``None`` on success or raises ``ProtocolViolation``.
    """

    @staticmethod
    def rule_1_observe_before_calculate(
        state: TerrainPipelineState,
        *,
        max_age_s: float = DEFAULT_SCENE_READ_MAX_AGE_S,
        now: Optional[float] = None,
    ) -> None:
        """Assert a TerrainSceneRead was captured recently enough."""
        sr = state.intent.scene_read
        if sr is None:
            raise ProtocolViolation(
                "rule_1: no TerrainSceneRead attached to intent — "
                "capture one via terrain_scene_read.capture_scene_read() first."
            )
        current = time.time() if now is None else now
        age = current - float(sr.timestamp)
        if age < 0:
            # Clock skew / synthetic tests — treat as fresh
            age = 0.0
        if age > max_age_s:
            raise ProtocolViolation(
                f"rule_1: scene_read is {age:.0f}s old (max {max_age_s:.0f}s). "
                "Re-capture before running further mutations."
            )

    @staticmethod
    def rule_2_sync_to_user_viewport(
        state: TerrainPipelineState,
        *,
        out_of_view_ok: bool = False,
    ) -> None:
        """Require that a ViewportVantage is attached to the pipeline state
        (or that the caller explicitly opts out via ``out_of_view_ok=True``)."""
        if out_of_view_ok:
            return
        vantage = getattr(state, "viewport_vantage", None)
        if vantage is None:
            raise ProtocolViolation(
                "rule_2: no ViewportVantage attached to state. Call "
                "terrain_viewport_sync.read_user_vantage() and attach it "
                "as state.viewport_vantage, or pass out_of_view_ok=True."
            )

    @staticmethod
    def rule_3_lock_reference_empties(
        state: TerrainPipelineState,
        *,
        tolerance: float = 0.01,
    ) -> None:
        """Assert every locked anchor still matches its recorded position."""
        # Import here to avoid circular dependency at module load.
        from .terrain_reference_locks import assert_all_anchors_intact

        reports = assert_all_anchors_intact(state.intent, tolerance=tolerance)
        drifted = [r for r in reports if r.drifted]
        if drifted:
            names = ", ".join(r.anchor_name for r in drifted)
            raise ProtocolViolation(
                f"rule_3: anchor drift detected for: {names}. "
                "Re-lock anchors or revert the drifting mutation."
            )

    @staticmethod
    def rule_4_real_geometry_not_vertex_tricks(params: dict) -> None:
        """Forbid vertex-color-only fakes for hero features."""
        feature_kind = str(params.get("feature_kind", "")).lower()
        hero_kinds = {"cliff", "cave", "waterfall"}
        if feature_kind in hero_kinds and bool(params.get("vertex_color_fake", False)):
            raise ProtocolViolation(
                f"rule_4: hero feature '{feature_kind}' cannot be a vertex-color fake. "
                "Cliffs, caves, and waterfalls must land as real mesh additions."
            )

    @staticmethod
    def rule_5_smallest_diff_per_iteration(
        state: TerrainPipelineState,
        *,
        cells_affected: int = 0,
        objects_affected: int = 0,
        bulk_edit: bool = False,
        cell_fraction_threshold: float = DEFAULT_BULK_EDIT_CELL_FRACTION,
        object_count_threshold: int = DEFAULT_BULK_EDIT_OBJECT_COUNT,
    ) -> None:
        """Reject pass-sized mutations without an explicit ``bulk_edit=True``."""
        if bulk_edit:
            return
        tile_cells = max(1, state.mask_stack.height.size)
        cell_frac = cells_affected / tile_cells
        if cell_frac > cell_fraction_threshold:
            raise ProtocolViolation(
                f"rule_5: mutation affects {cell_frac*100:.1f}% of tile "
                f"(threshold {cell_fraction_threshold*100:.0f}%). "
                "Use a region-scoped pass or set bulk_edit=True."
            )
        if objects_affected > object_count_threshold:
            raise ProtocolViolation(
                f"rule_5: mutation affects {objects_affected} objects "
                f"(threshold {object_count_threshold}). "
                "Split into smaller edits or set bulk_edit=True."
            )

    @staticmethod
    def rule_6_surface_vs_interior_classification(params: dict) -> None:
        """Every placed object must carry a valid ``placement_class`` tag."""
        placements = params.get("placements") or []
        if not isinstance(placements, list):
            return
        bad: list[str] = []
        for idx, placement in enumerate(placements):
            if not isinstance(placement, dict):
                continue
            pc = placement.get("placement_class")
            if pc not in VALID_PLACEMENT_CLASSES:
                bad.append(f"[{idx}] {placement.get('id', 'anon')!r}: {pc!r}")
        if bad:
            raise ProtocolViolation(
                "rule_6: invalid placement_class on: "
                + ", ".join(bad)
                + f". Must be one of {sorted(VALID_PLACEMENT_CLASSES)}."
            )

    @staticmethod
    def rule_7_plugin_usage(params: Optional[dict] = None) -> None:
        """Require the vb-blender addon to be loaded at the expected version."""
        from .terrain_addon_health import assert_addon_version_matches

        assert_addon_version_matches(TERRAIN_ADDON_MIN_VERSION)


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def enforce_protocol(
    *,
    require_rule_1: bool = True,
    require_rule_2: bool = True,
    require_rule_3: bool = True,
    require_rule_4: bool = True,
    require_rule_5: bool = True,
    require_rule_6: bool = True,
    require_rule_7: bool = True,
) -> Callable:
    """Wrap a terrain mutation handler so that all 7 gates must pass.

    The wrapped function must accept ``state: TerrainPipelineState`` as its
    first positional arg and ``params: dict`` as its second. Individual rule
    requirements can be toggled off via the kwargs (useful for unit-test
    fixtures that cannot stand up a full scene read).
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(
            state: TerrainPipelineState,
            params: Optional[dict] = None,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            params = dict(params or {})
            if require_rule_1:
                ProtocolGate.rule_1_observe_before_calculate(state)
            if require_rule_2:
                ProtocolGate.rule_2_sync_to_user_viewport(
                    state,
                    out_of_view_ok=bool(params.get("out_of_view_ok", False)),
                )
            if require_rule_3:
                ProtocolGate.rule_3_lock_reference_empties(state)
            if require_rule_4:
                ProtocolGate.rule_4_real_geometry_not_vertex_tricks(params)
            if require_rule_5:
                ProtocolGate.rule_5_smallest_diff_per_iteration(
                    state,
                    cells_affected=int(params.get("cells_affected", 0)),
                    objects_affected=int(params.get("objects_affected", 0)),
                    bulk_edit=bool(params.get("bulk_edit", False)),
                )
            if require_rule_6:
                ProtocolGate.rule_6_surface_vs_interior_classification(params)
            if require_rule_7:
                ProtocolGate.rule_7_plugin_usage(params)
            return fn(state, params, *args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    "ProtocolViolation",
    "ProtocolGate",
    "enforce_protocol",
    "TERRAIN_ADDON_MIN_VERSION",
    "VALID_PLACEMENT_CLASSES",
]
