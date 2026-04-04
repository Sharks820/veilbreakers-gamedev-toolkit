"""Shared utility functions for animation handlers.

Provides common interpolation helpers used across all animation modules.
Pure-logic module (NO bpy imports).
"""

from __future__ import annotations


def smoothstep(t: float) -> float:
    """Hermite smoothstep: 3t^2 - 2t^3. Clamps t to [0,1].

    Provides ease-in-ease-out interpolation for natural animation blending.
    smoothstep(0) = 0, smoothstep(0.5) = 0.5, smoothstep(1) = 1.
    """
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)
