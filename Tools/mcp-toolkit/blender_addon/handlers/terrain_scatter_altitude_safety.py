"""Scatter altitude safety audit — persistent bug canary.

Addendum 3.A + Addendum 3.B.6 + Addendum 3.B.7.

Every refactor touching scatter/biome/river/road code has historically
regressed to ``heights / heights.max()`` or ``altitude / height_scale``
clamped to ``[0, 1]``. Negative-elevation lowlands collapse to zero,
corrupting biome/slope/material downstream.

This module gives agents a single-call audit that greps arbitrary source
text for the known bad patterns. Use alongside ``WorldHeightTransform``
from ``terrain_semantics`` — that adapter is the safe replacement.
"""

from __future__ import annotations

import re
from typing import List, Tuple


WORLD_HEIGHT_TRANSFORM_WARNING = (
    "SCATTER ALTITUDE SAFETY: This code path once used "
    "`heights / heights.max()` or `altitude / height_scale` clamped to "
    "[0, 1], which silently collapses negative-elevation lowlands (basins, "
    "wetlands, underwater valleys) to zero. Use "
    "`terrain_semantics.WorldHeightTransform` instead — it preserves sign "
    "and round-trips signed elevations. See Addendum 3.A / 3.B.6 / 3.B.7."
)


# Ordered most-specific-first so the audit reports the precise idiom.
_BAD_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("heights_div_heights_max", re.compile(r"heights\s*/\s*heights\.max\s*\(")),
    ("heightmap_div_heightmap_max", re.compile(r"heightmap\s*/\s*heightmap\.max\s*\(")),
    ("altitude_div_height_scale", re.compile(r"altitude\s*/\s*height_scale\b")),
    ("center_z_div_height_scale", re.compile(r"center\.z\s*/\s*height_scale\b")),
    ("np_clip_0_1_on_altitude", re.compile(r"np\.clip\s*\(\s*altitude[^,]*,\s*0\.?0?\s*,\s*1\.?0?\s*\)")),
)


def audit_scatter_altitude_conversion(module_source: str) -> List[str]:
    """Return a list of offending lines found in ``module_source``.

    Each returned entry is ``"<pattern_id>:L<lineno>: <line>"``. An empty
    list means the source is clean.
    """
    if not module_source:
        return []

    offenders: List[str] = []
    for lineno, line in enumerate(module_source.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for pattern_id, regex in _BAD_PATTERNS:
            if regex.search(line):
                offenders.append(f"{pattern_id}:L{lineno}: {stripped}")
                break
    return offenders


__all__ = [
    "WORLD_HEIGHT_TRANSFORM_WARNING",
    "audit_scatter_altitude_conversion",
]
