"""Bundle N — telemetry recording & dashboard aggregation.

Writes a newline-delimited JSON log of per-tile pass metrics and reads
it back to build an aggregated dashboard. Used to track iteration
velocity, budget pressure, and readability scores across runs.

Pure stdlib — no bpy. See plan §19.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .terrain_semantics import TerrainPipelineState


@dataclass
class TelemetryRecord:
    """One tile-pass telemetry sample."""

    timestamp: float
    tile_coords: Tuple[int, int]
    pass_durations: Dict[str, float] = field(default_factory=dict)
    mask_channel_counts: int = 0
    budget_usage: Dict[str, Any] = field(default_factory=dict)
    readability_score: float = 0.0
    pipeline_version: str = "bundle_n_1.0"
    content_hash: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["tile_coords"] = list(self.tile_coords)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelemetryRecord":
        coords = data.get("tile_coords", [0, 0])
        return cls(
            timestamp=float(data.get("timestamp", 0.0)),
            tile_coords=(int(coords[0]), int(coords[1])),
            pass_durations=dict(data.get("pass_durations", {})),
            mask_channel_counts=int(data.get("mask_channel_counts", 0)),
            budget_usage=dict(data.get("budget_usage", {})),
            readability_score=float(data.get("readability_score", 0.0)),
            pipeline_version=str(data.get("pipeline_version", "bundle_n_1.0")),
            content_hash=str(data.get("content_hash", "")),
            extra=dict(data.get("extra", {})),
        )


def _count_populated_channels(state: TerrainPipelineState) -> int:
    stack = state.mask_stack
    total = 0
    for name in stack._ARRAY_CHANNELS:
        if getattr(stack, name, None) is not None:
            total += 1
    return total


def record_telemetry(
    state: TerrainPipelineState,
    record_path: Path,
    *,
    budget_usage: Optional[Dict[str, Any]] = None,
    readability_score: float = 0.0,
    extra: Optional[Dict[str, Any]] = None,
) -> TelemetryRecord:
    """Append a telemetry record to ``record_path`` (newline-delimited JSON)."""
    record_path = Path(record_path)
    record_path.parent.mkdir(parents=True, exist_ok=True)

    pass_durations = {
        r.pass_name: float(r.duration_seconds) for r in state.pass_history
    }
    record = TelemetryRecord(
        timestamp=time.time(),
        tile_coords=(int(state.tile_x), int(state.tile_y)),
        pass_durations=pass_durations,
        mask_channel_counts=_count_populated_channels(state),
        budget_usage=dict(budget_usage or {}),
        readability_score=float(readability_score),
        content_hash=state.mask_stack.compute_hash(),
        extra=dict(extra or {}),
    )
    with record_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record.to_dict(), sort_keys=True))
        fh.write("\n")
    return record


def _load_records(record_path: Path) -> List[TelemetryRecord]:
    path = Path(record_path)
    if not path.exists():
        return []
    out: List[TelemetryRecord] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        out.append(TelemetryRecord.from_dict(data))
    return out


def summarize_telemetry(record_path: Path) -> Dict[str, Any]:
    """Aggregate metrics across every recorded telemetry sample."""
    records = _load_records(record_path)
    if not records:
        return {
            "record_count": 0,
            "tile_count": 0,
            "pass_duration_avg": {},
            "pass_duration_total": {},
            "readability_avg": 0.0,
            "readability_min": 0.0,
            "readability_max": 0.0,
            "mask_channel_avg": 0.0,
        }

    tile_set = {tuple(r.tile_coords) for r in records}
    pass_total: Dict[str, float] = {}
    pass_count: Dict[str, int] = {}
    readability_values: List[float] = []
    channel_values: List[int] = []
    for r in records:
        for name, dt in r.pass_durations.items():
            pass_total[name] = pass_total.get(name, 0.0) + float(dt)
            pass_count[name] = pass_count.get(name, 0) + 1
        readability_values.append(float(r.readability_score))
        channel_values.append(int(r.mask_channel_counts))

    avg_duration = {
        k: (pass_total[k] / pass_count[k]) if pass_count[k] else 0.0
        for k in pass_total
    }

    return {
        "record_count": len(records),
        "tile_count": len(tile_set),
        "pass_duration_avg": avg_duration,
        "pass_duration_total": pass_total,
        "pass_sample_count": pass_count,
        "readability_avg": sum(readability_values) / len(readability_values),
        "readability_min": min(readability_values),
        "readability_max": max(readability_values),
        "mask_channel_avg": sum(channel_values) / len(channel_values),
        "earliest_timestamp": min(r.timestamp for r in records),
        "latest_timestamp": max(r.timestamp for r in records),
    }


__all__ = [
    "TelemetryRecord",
    "record_telemetry",
    "summarize_telemetry",
]
