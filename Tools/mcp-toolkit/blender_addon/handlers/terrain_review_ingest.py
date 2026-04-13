"""Bundle N — review ingest / intent-feedback loop.

Parses review JSON (from a human reviewer OR from an AI reviewer run such
as ``vb-review``) and folds the findings into the terrain
``TerrainIntentState`` as new composition hints, protected-zone bumps,
or hero feature tweaks.

Pure stdlib — no bpy, no numpy required. See plan §19.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .terrain_semantics import TerrainIntentState


ALLOWED_SEVERITIES: Tuple[str, ...] = ("hard", "soft", "info")
ALLOWED_SOURCES: Tuple[str, ...] = ("human", "ai")


@dataclass
class ReviewFinding:
    """One item from an external review report."""

    source: str  # "human" | "ai"
    severity: str  # "hard" | "soft" | "info"
    location: Optional[Tuple[float, float, float]] = None
    message: str = ""
    suggested_fix: str = ""
    tags: Tuple[str, ...] = ()
    affected_feature: Optional[str] = None

    def __post_init__(self) -> None:
        if self.source not in ALLOWED_SOURCES:
            raise ValueError(
                f"ReviewFinding.source must be one of {ALLOWED_SOURCES}, got {self.source!r}"
            )
        if self.severity not in ALLOWED_SEVERITIES:
            raise ValueError(
                f"ReviewFinding.severity must be one of {ALLOWED_SEVERITIES}, got {self.severity!r}"
            )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.location is not None:
            d["location"] = list(self.location)
        d["tags"] = list(self.tags)
        return d


def _coerce_location(raw: Any) -> Optional[Tuple[float, float, float]]:
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)) and len(raw) >= 3:
        return (float(raw[0]), float(raw[1]), float(raw[2]))
    return None


def ingest_review_json(path: Path) -> List[ReviewFinding]:
    """Parse a review report JSON file into a list of ReviewFinding."""
    data = json.loads(Path(path).read_text())
    findings_raw: List[Dict[str, Any]]
    if isinstance(data, dict) and "findings" in data:
        findings_raw = list(data["findings"])
    elif isinstance(data, list):
        findings_raw = list(data)
    else:
        raise ValueError(
            f"Unsupported review JSON shape — expected 'findings' key or list, "
            f"got {type(data).__name__}"
        )
    out: List[ReviewFinding] = []
    for item in findings_raw:
        if not isinstance(item, dict):
            continue
        try:
            finding = ReviewFinding(
                source=str(item.get("source", "ai")),
                severity=str(item.get("severity", "soft")),
                location=_coerce_location(item.get("location")),
                message=str(item.get("message", "")),
                suggested_fix=str(item.get("suggested_fix", "")),
                tags=tuple(str(t) for t in item.get("tags", [])),
                affected_feature=(
                    str(item["affected_feature"])
                    if item.get("affected_feature") is not None
                    else None
                ),
            )
        except ValueError:
            # Skip malformed entries silently — review JSON is
            # externally authored and may drift.
            continue
        out.append(finding)
    return out


def apply_review_findings(
    intent: TerrainIntentState,
    findings: List[ReviewFinding],
) -> TerrainIntentState:
    """Fold review findings back into the authoring intent.

    Hard findings set ``composition_hints['review_blockers']``, soft findings
    append to ``composition_hints['review_suggestions']``. This function
    never mutates ``intent`` in place — it returns a new frozen dataclass.
    """
    from dataclasses import replace as _replace

    hints = dict(intent.composition_hints)
    blockers: List[Dict[str, Any]] = list(hints.get("review_blockers", []))
    suggestions: List[Dict[str, Any]] = list(hints.get("review_suggestions", []))
    info: List[Dict[str, Any]] = list(hints.get("review_info", []))

    for f in findings:
        payload = f.to_dict()
        if f.severity == "hard":
            blockers.append(payload)
        elif f.severity == "soft":
            suggestions.append(payload)
        else:
            info.append(payload)

    hints["review_blockers"] = blockers
    hints["review_suggestions"] = suggestions
    hints["review_info"] = info
    hints["review_total_ingested"] = int(
        hints.get("review_total_ingested", 0)
    ) + len(findings)

    return _replace(intent, composition_hints=hints)


__all__ = [
    "ALLOWED_SEVERITIES",
    "ALLOWED_SOURCES",
    "ReviewFinding",
    "ingest_review_json",
    "apply_review_findings",
]
