"""Bundle N supplements — terrain-semantic readability checks (Addendum 1.B.8).

Image-stat-only verification is deprecated. Every visible hero feature
must have a semantic readability check that actually inspects the
TerrainMaskStack instead of just histograms.
"""

from __future__ import annotations

from typing import Any, List, Optional, Sequence, Tuple


from .terrain_semantics import TerrainMaskStack, ValidationIssue


# ---------------------------------------------------------------------------
# Cliff silhouette readability
# ---------------------------------------------------------------------------


def check_cliff_silhouette_readability(
    stack: TerrainMaskStack,
    view_distance_m: float = 100.0,
) -> List[ValidationIssue]:
    """Cliffs at ``view_distance_m`` must have discernible lip/face boundary.

    Requires both ``cliff_candidate`` and ``slope`` channels to be present.
    Readability is proxied by requiring at least 0.5% of the tile to be
    cliff-candidate AND for those cells to have slope > 0.7 rad.
    """
    issues: List[ValidationIssue] = []

    if stack.cliff_candidate is None:
        return issues  # no cliffs in this tile — vacuously readable
    if stack.slope is None:
        issues.append(
            ValidationIssue(
                code="CLIFF_READABILITY_NO_SLOPE",
                severity="hard",
                message="cliff_candidate present but slope channel missing",
                remediation="Run pass_structural_masks before readability audit",
            )
        )
        return issues

    cliff_mask = stack.cliff_candidate > 0.5
    total = cliff_mask.size
    cliff_cells = int(cliff_mask.sum())

    if cliff_cells == 0:
        return issues

    if cliff_cells / total < 0.005:
        issues.append(
            ValidationIssue(
                code="CLIFF_READABILITY_UNDERFOOTED",
                severity="hard",
                message=(
                    f"cliff footprint {cliff_cells}/{total} "
                    f"< 0.5% — unreadable at {view_distance_m:.0f}m"
                ),
                remediation="Expand cliff candidate zones or raise slope threshold",
            )
        )

    sharp = (stack.slope[cliff_mask] > 0.7).mean() if cliff_cells else 0.0
    if sharp < 0.25:
        issues.append(
            ValidationIssue(
                code="CLIFF_READABILITY_SOFT_LIP",
                severity="hard",
                message=(
                    f"only {sharp:.1%} of cliff cells exceed 0.7 rad slope — "
                    "lip boundary will not read"
                ),
                remediation="Sharpen cliff lip via cliff carver pass",
            )
        )

    return issues


# ---------------------------------------------------------------------------
# Waterfall chain completeness
# ---------------------------------------------------------------------------


def check_waterfall_chain_completeness(
    stack: TerrainMaskStack,
    chains: Sequence[Any],
) -> List[ValidationIssue]:
    """Every waterfall chain must carry source + lip + pool + outflow.

    ``chains`` items may be dicts or objects with those four attributes.
    Missing attributes are emitted as hard issues.
    """
    issues: List[ValidationIssue] = []
    required = ("source", "lip", "pool", "outflow")

    for idx, chain in enumerate(chains or ()):
        for attr in required:
            if isinstance(chain, dict):
                present = attr in chain and chain[attr] is not None
            else:
                present = getattr(chain, attr, None) is not None
            if not present:
                issues.append(
                    ValidationIssue(
                        code="WATERFALL_CHAIN_INCOMPLETE",
                        severity="hard",
                        affected_feature=f"waterfall_chain[{idx}]",
                        message=f"waterfall chain {idx} missing {attr!r}",
                        remediation=(
                            "Populate source/lip/pool/outflow before "
                            "readability audit"
                        ),
                    )
                )

    return issues


# ---------------------------------------------------------------------------
# Cave framing presence
# ---------------------------------------------------------------------------


def check_cave_framing_presence(
    stack: TerrainMaskStack,
    caves: Sequence[Any],
) -> List[ValidationIssue]:
    """Each visible cave requires >=2 framing markers + a damp signal."""
    issues: List[ValidationIssue] = []

    for idx, cave in enumerate(caves or ()):
        if isinstance(cave, dict):
            framing = cave.get("framing_markers") or ()
            damp = cave.get("damp_signal")
        else:
            framing = getattr(cave, "framing_markers", ()) or ()
            damp = getattr(cave, "damp_signal", None)

        if len(framing) < 2:
            issues.append(
                ValidationIssue(
                    code="CAVE_FRAMING_INSUFFICIENT",
                    severity="hard",
                    affected_feature=f"cave[{idx}]",
                    message=(
                        f"cave {idx} has {len(framing)} framing markers; "
                        "require >= 2"
                    ),
                    remediation="Place framing rocks at cave mouth",
                )
            )

        if damp is None or (isinstance(damp, (int, float)) and float(damp) <= 0.0):
            issues.append(
                ValidationIssue(
                    code="CAVE_DAMP_MISSING",
                    severity="hard",
                    affected_feature=f"cave[{idx}]",
                    message=f"cave {idx} missing damp signal",
                    remediation="Paint damp mask at cave entrance",
                )
            )

    return issues


# ---------------------------------------------------------------------------
# Focal composition (rule of thirds)
# ---------------------------------------------------------------------------


def check_focal_composition(
    stack: TerrainMaskStack,
    focal_point: Tuple[float, float],
) -> List[ValidationIssue]:
    """Focal point must land near a rule-of-thirds intersection.

    ``focal_point`` is a normalized (u, v) pair in [0, 1]. The four
    rule-of-thirds intersections are at (1/3, 1/3), (2/3, 1/3),
    (1/3, 2/3), (2/3, 2/3). The minimum distance must be < 0.1.
    """
    issues: List[ValidationIssue] = []

    if focal_point is None:
        return issues
    u, v = float(focal_point[0]), float(focal_point[1])
    if not (0.0 <= u <= 1.0 and 0.0 <= v <= 1.0):
        issues.append(
            ValidationIssue(
                code="FOCAL_OUT_OF_FRAME",
                severity="hard",
                message=f"focal point ({u}, {v}) outside [0,1]^2",
                remediation="Reposition camera or focal anchor",
            )
        )
        return issues

    thirds = [(1 / 3, 1 / 3), (2 / 3, 1 / 3), (1 / 3, 2 / 3), (2 / 3, 2 / 3)]
    d_min = min(((u - tu) ** 2 + (v - tv) ** 2) ** 0.5 for tu, tv in thirds)
    if d_min > 0.10:
        issues.append(
            ValidationIssue(
                code="FOCAL_COMPOSITION_OFF_THIRDS",
                severity="hard",
                message=(
                    f"focal point ({u:.2f},{v:.2f}) is {d_min:.2f} from nearest "
                    "rule-of-thirds intersection (limit 0.10)"
                ),
                remediation="Nudge focal point toward a thirds intersection",
            )
        )
    return issues


# ---------------------------------------------------------------------------
# Aggregate audit entry-point
# ---------------------------------------------------------------------------


def run_semantic_readability_audit(
    stack: TerrainMaskStack,
    *,
    chains: Optional[Sequence[Any]] = None,
    caves: Optional[Sequence[Any]] = None,
    focal: Optional[Tuple[float, float]] = None,
) -> List[ValidationIssue]:
    """Run all four terrain-semantic readability checks.

    Callers receive a flat list of hard issues. An empty list means the
    audit passed; any hard issue is treated as a release blocker by
    ``run_readability_audit``.
    """
    issues: List[ValidationIssue] = []
    issues.extend(check_cliff_silhouette_readability(stack))
    if chains is not None:
        issues.extend(check_waterfall_chain_completeness(stack, chains))
    if caves is not None:
        issues.extend(check_cave_framing_presence(stack, caves))
    if focal is not None:
        issues.extend(check_focal_composition(stack, focal))
    return issues
