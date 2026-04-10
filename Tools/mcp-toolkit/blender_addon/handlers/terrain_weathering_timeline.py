"""Bundle Q — Procedural weathering event timeline.

Generates a deterministic sequence of weathering events (rain, wind,
freeze, thaw) over a duration. Events mutate the mask stack's wetness
channel when applied. Seeded via ``derive_pass_seed`` if available,
otherwise ``numpy.random.default_rng``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from .terrain_semantics import TerrainMaskStack


WEATHER_KINDS = ("rain", "wind", "freeze", "thaw", "drought")


@dataclass
class WeatheringEvent:
    """A single weathering event on the timeline."""

    time_hours: float
    kind: str
    intensity: float


def generate_weathering_timeline(
    duration_hours: float,
    seed: int,
) -> List[WeatheringEvent]:
    """Produce a deterministic list of weathering events.

    The generator averages one event per ~2 hours of duration, with
    per-event kind and intensity drawn from a seeded RNG.
    """
    if duration_hours <= 0:
        return []

    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    n = max(1, int(round(duration_hours / 2.0)))

    times = np.sort(rng.uniform(0.0, float(duration_hours), size=n))
    kinds = rng.choice(WEATHER_KINDS, size=n)
    intensities = rng.uniform(0.1, 1.0, size=n)

    return [
        WeatheringEvent(
            time_hours=float(t),
            kind=str(k),
            intensity=float(i),
        )
        for t, k, i in zip(times, kinds, intensities)
    ]


def apply_weathering_event(
    stack: TerrainMaskStack,
    event: WeatheringEvent,
) -> None:
    """Mutate the stack's wetness in place.

    rain / thaw   -> add wetness
    drought / wind -> subtract wetness
    freeze        -> no change (ice clamps wetness in place)

    Wetness is clamped to ``[0, 2 * max_observed_wetness]`` to prevent
    runaway accumulation. If wetness isn't populated yet, a zero array
    the same shape as ``height`` is allocated.
    """
    if stack.height is None:
        return

    if stack.wetness is None:
        stack.wetness = np.zeros_like(stack.height, dtype=np.float32)

    max_existing = float(stack.wetness.max()) if stack.wetness.size else 0.0
    ceil = max(1.0, max_existing * 2.0)

    delta = float(event.intensity)
    kind = event.kind
    if kind in ("rain", "thaw"):
        stack.wetness = np.clip(stack.wetness + delta, 0.0, ceil).astype(
            stack.wetness.dtype, copy=False
        )
    elif kind in ("drought", "wind"):
        stack.wetness = np.clip(stack.wetness - delta, 0.0, ceil).astype(
            stack.wetness.dtype, copy=False
        )
    elif kind == "freeze":
        return
    else:
        return
