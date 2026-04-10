"""Iteration-velocity metrics (Bundle M).

Records how many passes ran, how long they took, how many hit the
cache, and how many parallel waves executed. Also tracks per-pass
duration samples so we can report p50 / p95 percentiles and produce a
human-readable summary. Used by the iteration test harness to prove
(or disprove) the 5x speedup target from the ultra implementation
plan §3.2.

Pure Python + stdlib statistics. No bpy.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .terrain_semantics import PassResult


@dataclass
class IterationMetrics:
    total_passes_run: int = 0
    total_duration_s: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    parallel_waves_run: int = 0
    pass_names: List[str] = field(default_factory=list)
    # Per-pass duration samples in seconds, preserved for percentile
    # reporting. Indexed in the same order as ``pass_names``.
    durations_s: List[float] = field(default_factory=list)

    @property
    def avg_pass_duration_s(self) -> float:
        return (
            self.total_duration_s / self.total_passes_run
            if self.total_passes_run > 0
            else 0.0
        )

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total) if total > 0 else 0.0

    @property
    def p50_duration_s(self) -> float:
        return _percentile(self.durations_s, 50.0)

    @property
    def p95_duration_s(self) -> float:
        return _percentile(self.durations_s, 95.0)

    @property
    def max_duration_s(self) -> float:
        return max(self.durations_s) if self.durations_s else 0.0

    def per_pass_totals(self) -> Dict[str, float]:
        """Return aggregate wall-clock per registered pass name.

        Useful for identifying the dominant cost center when the
        iteration harness reports a slow overall run.
        """
        totals: Dict[str, float] = {}
        for name, dur in zip(self.pass_names, self.durations_s):
            totals[name] = totals.get(name, 0.0) + float(dur)
        return totals

    def summary_report(self) -> Dict[str, Any]:
        """Return a JSON-friendly snapshot of every tracked metric."""
        return {
            "total_passes_run": self.total_passes_run,
            "total_duration_s": round(self.total_duration_s, 6),
            "avg_pass_duration_s": round(self.avg_pass_duration_s, 6),
            "p50_duration_s": round(self.p50_duration_s, 6),
            "p95_duration_s": round(self.p95_duration_s, 6),
            "max_duration_s": round(self.max_duration_s, 6),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": round(self.cache_hit_rate, 4),
            "parallel_waves_run": self.parallel_waves_run,
            "per_pass_totals_s": {
                k: round(v, 6) for k, v in self.per_pass_totals().items()
            },
        }


def _percentile(samples: List[float], pct: float) -> float:
    """Return a simple linear-interpolation percentile (0–100).

    Fall back to ``0.0`` for an empty list so callers can embed the
    result in a summary dict without guarding every call.
    """
    if not samples:
        return 0.0
    ordered = sorted(samples)
    if len(ordered) == 1:
        return float(ordered[0])
    # Clamp pct to the inclusive 0..100 range.
    p = max(0.0, min(100.0, float(pct)))
    k = (len(ordered) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    frac = k - lo
    return float(ordered[lo] * (1.0 - frac) + ordered[hi] * frac)


def record_iteration(metrics: IterationMetrics, result: PassResult) -> None:
    duration = float(result.duration_seconds or 0.0)
    metrics.total_passes_run += 1
    metrics.total_duration_s += duration
    metrics.pass_names.append(result.pass_name)
    metrics.durations_s.append(duration)


def record_cache_hit(metrics: IterationMetrics) -> None:
    metrics.cache_hits += 1


def record_cache_miss(metrics: IterationMetrics) -> None:
    metrics.cache_misses += 1


def record_wave(metrics: IterationMetrics) -> None:
    metrics.parallel_waves_run += 1


def speedup_factor(
    baseline: IterationMetrics,
    current: IterationMetrics,
) -> float:
    """Return baseline_duration / current_duration.

    Returns ``float('inf')`` if current took zero time and baseline
    took positive time (perfect cache). Returns ``0.0`` if baseline
    was zero.
    """
    b = baseline.total_duration_s
    c = current.total_duration_s
    if b <= 0.0:
        return 0.0
    if c <= 0.0:
        return float("inf")
    return b / c


def meets_speedup_target(
    baseline: IterationMetrics,
    current: IterationMetrics,
    *,
    target: float = 5.0,
) -> bool:
    """Return ``True`` if ``current`` is at least ``target`` × faster than
    ``baseline``.

    Defaults to the 5x speedup target from the ultra plan §3.2 item 13.
    """
    factor = speedup_factor(baseline, current)
    return factor >= float(target)


def stdev_duration_s(metrics: IterationMetrics) -> float:
    """Return the population standard deviation of pass durations.

    Useful for flagging runs where one pass is dominating wall-clock —
    we use this in CI to alert on iteration-velocity regressions.
    """
    if len(metrics.durations_s) < 2:
        return 0.0
    try:
        return float(statistics.pstdev(metrics.durations_s))
    except statistics.StatisticsError:
        return 0.0


__all__ = [
    "IterationMetrics",
    "record_iteration",
    "record_cache_hit",
    "record_cache_miss",
    "record_wave",
    "speedup_factor",
    "meets_speedup_target",
    "stdev_duration_s",
]
