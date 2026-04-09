"""Iteration-velocity metrics (Bundle M).

Records how many passes ran, how long they took, how many hit the
cache, and how many parallel waves executed. Used by the iteration
test harness to prove the 5x speedup target.

Pure Python. No bpy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .terrain_semantics import PassResult


@dataclass
class IterationMetrics:
    total_passes_run: int = 0
    total_duration_s: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    parallel_waves_run: int = 0
    pass_names: List[str] = field(default_factory=list)

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


def record_iteration(metrics: IterationMetrics, result: PassResult) -> None:
    metrics.total_passes_run += 1
    metrics.total_duration_s += float(result.duration_seconds or 0.0)
    metrics.pass_names.append(result.pass_name)


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


__all__ = [
    "IterationMetrics",
    "record_iteration",
    "record_cache_hit",
    "record_cache_miss",
    "record_wave",
    "speedup_factor",
]
