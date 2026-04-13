"""Feature tier hierarchy + budgeting for Bundle H.

Classifies hero features into tiers and enforces per-tier budgets so
AAA scenes don't drown in competing "hero moments".

Pure numpy. No bpy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, List, Optional


from .terrain_semantics import (
    HeroFeatureSpec,
    TerrainIntentState,
    TerrainMaskStack,
)


# ---------------------------------------------------------------------------
# Feature tier enum
# ---------------------------------------------------------------------------


class FeatureTier(Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    AMBIENT = "ambient"

    @classmethod
    def from_str(cls, value: str) -> "FeatureTier":
        v = (value or "").lower().strip()
        for t in cls:
            if t.value == v:
                return t
        return cls.SECONDARY


_TIER_PRIORITY = {
    FeatureTier.PRIMARY: 0,
    FeatureTier.SECONDARY: 1,
    FeatureTier.TERTIARY: 2,
    FeatureTier.AMBIENT: 3,
}


# ---------------------------------------------------------------------------
# Budget dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureBudget:
    tier: FeatureTier
    max_features_per_km2: float
    max_total_tris: int
    max_footprint_m: float


DEFAULT_BUDGETS: dict = {
    FeatureTier.PRIMARY: FeatureBudget(FeatureTier.PRIMARY, 0.5, 2_000_000, 500.0),
    FeatureTier.SECONDARY: FeatureBudget(FeatureTier.SECONDARY, 4.0, 800_000, 250.0),
    FeatureTier.TERTIARY: FeatureBudget(FeatureTier.TERTIARY, 20.0, 200_000, 100.0),
    FeatureTier.AMBIENT: FeatureBudget(FeatureTier.AMBIENT, 200.0, 50_000, 40.0),
}


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_feature_tier(
    feature_spec: HeroFeatureSpec,
    stack: Optional[TerrainMaskStack] = None,
    intent: Optional[TerrainIntentState] = None,
) -> FeatureTier:
    """Classify a feature into a tier.

    Primary = explicit tier or feature_kind in a cinematic list.
    Secondary/Tertiary/Ambient = based on tier field or fallback by kind.
    Dynamic weighting: if a stack has saliency_macro set and the feature sits
    on a very high-saliency cell (>0.8), promote by one tier (capped at PRIMARY).
    """
    declared = FeatureTier.from_str(feature_spec.tier)

    cinematic_kinds = {"canyon", "waterfall", "arch", "megaboss_arena", "sanctum"}
    if feature_spec.feature_kind.lower() in cinematic_kinds:
        declared = FeatureTier.PRIMARY

    # Dynamic promotion by saliency sample
    if stack is not None and stack.saliency_macro is not None:
        fx, fy, _ = feature_spec.world_position
        cell = float(stack.cell_size)
        col = int(round((fx - stack.world_origin_x) / cell))
        row = int(round((fy - stack.world_origin_y) / cell))
        rows, cols = stack.saliency_macro.shape
        if 0 <= row < rows and 0 <= col < cols:
            sal = float(stack.saliency_macro[row, col])
            if sal > 0.8 and declared != FeatureTier.PRIMARY:
                promoted_idx = max(0, _TIER_PRIORITY[declared] - 1)
                for t, idx in _TIER_PRIORITY.items():
                    if idx == promoted_idx:
                        declared = t
                        break

    return declared


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------


def enforce_feature_budget(
    features: Iterable[Any],
    budget: FeatureBudget,
) -> List[Any]:
    """Prune ``features`` down to the limits declared in ``budget``.

    ``features`` may be a list of HeroFeatureSpec or generic dicts. Pruning
    strategy: keep all entries with the highest authored priority until
    ``max_features_per_km2`` is exceeded on a notional 1 km² baseline, and
    cap the total count at ``max_total_tris // 10_000`` as a simple proxy.
    Features exceeding ``max_footprint_m`` are dropped regardless.
    """
    features_list = list(features)
    if not features_list:
        return []

    def _footprint(f: Any) -> float:
        if isinstance(f, HeroFeatureSpec):
            if f.bounds is not None:
                return max(f.bounds.width, f.bounds.height)
            return 0.0
        if isinstance(f, dict):
            return float(f.get("footprint_m", 0.0))
        return 0.0

    # Drop oversized features
    filtered = [f for f in features_list if _footprint(f) <= budget.max_footprint_m]

    # Cap raw count at max_features_per_km2 (treat as hard cap)
    max_count = max(1, int(round(budget.max_features_per_km2)))
    # Also cap by notional tri budget (10k tris per feature)
    tri_cap = max(1, budget.max_total_tris // 10_000)
    hard_cap = min(max_count, tri_cap)

    # Deterministic keep order: by feature_id if available
    def _sort_key(f: Any) -> str:
        if isinstance(f, HeroFeatureSpec):
            return f.feature_id
        if isinstance(f, dict):
            return str(f.get("feature_id", ""))
        return repr(f)

    filtered.sort(key=_sort_key)
    return filtered[:hard_cap]


__all__ = [
    "FeatureTier",
    "FeatureBudget",
    "DEFAULT_BUDGETS",
    "classify_feature_tier",
    "enforce_feature_budget",
]
