"""Bundle E supplements — asset metadata taxonomy (Addendum 1.B.5).

Pure python / numpy. No bpy. Headless unit-testable.

Implements the full asset metadata tag taxonomy from master plan §15 plus
the ``AssetContextRuleExt`` extension fields (``scale_variance_by_role``,
``camera_priority_weight``) used by ``place_assets_by_zone`` scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .terrain_semantics import ValidationIssue


# ---------------------------------------------------------------------------
# Tag taxonomy (master plan §15, frozen constants)
# ---------------------------------------------------------------------------

LOCATION_TAGS: Tuple[str, ...] = (
    "cliff",
    "riverbank",
    "waterfall_base",
    "cave_entrance",
    "plateau",
    "forest_floor",
    "beach",
    "wetland",
    "alpine",
    "cultivated",
)

ROLE_TAGS: Tuple[str, ...] = ("hero", "support", "filler")

SIZE_TAGS: Tuple[str, ...] = ("large", "medium", "small")

CONTEXT_TAGS: Tuple[str, ...] = (
    "silhouette_critical",
    "foreground_only",
    "mid_distance",
    "background_fill",
)


# ---------------------------------------------------------------------------
# AssetMetadata dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AssetMetadata:
    """Full per-asset metadata tag container (Addendum 1.B.5).

    All four tag categories must be populated or the asset is rejected
    by ``validate_asset_metadata``.
    """

    location_tags: Tuple[str, ...]
    role_tag: str
    size_tag: str
    context_tags: Tuple[str, ...]


def validate_asset_metadata(meta: AssetMetadata) -> List[ValidationIssue]:
    """Validate an AssetMetadata against the taxonomy.

    Emits hard issues for:
    - ASSET_META_NO_LOCATION: no location tag
    - ASSET_META_INVALID_ROLE: role not in ROLE_TAGS
    - ASSET_META_INVALID_SIZE: size not in SIZE_TAGS
    - ASSET_META_NO_CONTEXT: no context tag
    - ASSET_META_INVALID_LOCATION: unknown location tag
    - ASSET_META_INVALID_CONTEXT: unknown context tag
    """
    issues: List[ValidationIssue] = []

    if not meta.location_tags:
        issues.append(
            ValidationIssue(
                code="ASSET_META_NO_LOCATION",
                severity="hard",
                message="Asset metadata missing required location tag",
                remediation="Add at least one tag from LOCATION_TAGS",
            )
        )
    else:
        for tag in meta.location_tags:
            if tag not in LOCATION_TAGS:
                issues.append(
                    ValidationIssue(
                        code="ASSET_META_INVALID_LOCATION",
                        severity="hard",
                        message=f"Unknown location tag {tag!r}",
                        remediation=f"Use one of {LOCATION_TAGS}",
                    )
                )

    if meta.role_tag not in ROLE_TAGS:
        issues.append(
            ValidationIssue(
                code="ASSET_META_INVALID_ROLE",
                severity="hard",
                message=f"Role tag {meta.role_tag!r} not in {ROLE_TAGS}",
                remediation=f"Use one of {ROLE_TAGS}",
            )
        )

    if meta.size_tag not in SIZE_TAGS:
        issues.append(
            ValidationIssue(
                code="ASSET_META_INVALID_SIZE",
                severity="hard",
                message=f"Size tag {meta.size_tag!r} not in {SIZE_TAGS}",
                remediation=f"Use one of {SIZE_TAGS}",
            )
        )

    if not meta.context_tags:
        issues.append(
            ValidationIssue(
                code="ASSET_META_NO_CONTEXT",
                severity="hard",
                message="Asset metadata missing required context tag",
                remediation="Add at least one tag from CONTEXT_TAGS",
            )
        )
    else:
        for tag in meta.context_tags:
            if tag not in CONTEXT_TAGS:
                issues.append(
                    ValidationIssue(
                        code="ASSET_META_INVALID_CONTEXT",
                        severity="hard",
                        message=f"Unknown context tag {tag!r}",
                        remediation=f"Use one of {CONTEXT_TAGS}",
                    )
                )

    return issues


def classify_size_from_bounds(bbox_meters: float) -> str:
    """Map a bounding-box diagonal (meters) to a size tag.

    large  > 3 m
    medium 0.5 .. 3 m
    small  < 0.5 m
    """
    if bbox_meters > 3.0:
        return "large"
    if bbox_meters >= 0.5:
        return "medium"
    return "small"


# ---------------------------------------------------------------------------
# AssetContextRuleExt — Addendum 1.B.5 scatter-rule extensions
# ---------------------------------------------------------------------------


@dataclass
class AssetContextRuleExt:
    """Extension fields added to AssetContextRule.

    hero assets get lower scale variance (more iconic), filler gets higher
    (breakup). ``camera_priority_weight`` biases placement scoring toward
    the current ViewportVantage frustum.
    """

    asset_id: str
    scale_variance_by_role: float = 0.2
    camera_priority_weight: float = 0.0

    def effective_variance(self, role_tag: str) -> float:
        """Return role-adjusted scale variance.

        hero   -> 0.5x baseline (iconic)
        support-> 1.0x baseline
        filler -> 1.5x baseline (breakup)
        """
        base = float(self.scale_variance_by_role)
        if role_tag == "hero":
            return base * 0.5
        if role_tag == "filler":
            return base * 1.5
        return base
