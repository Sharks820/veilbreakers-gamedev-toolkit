"""Bundle B legacy bug audit — static inspection of terrain_advanced.py.

Addendum 2.B.1 flagged 4 suspect ``np.clip(...)`` sites in
``terrain_advanced.py`` (lines ~793, ~896, ~1483, ~1530). The concern is
that these clamp world-unit heights into ``[0, 1]``, which silently
destroys terrain elevation data (Rule 10: world heights are meters, never
unit-space).

This module is a DOCUMENTATION + VERIFICATION deliverable. It does NOT
modify the runtime behavior of ``terrain_advanced.py`` — instead, it
provides a static auditor so the 4 target lines are surfaced in the test
suite. Removing the clips is a runtime-breaking change deferred to a
later bundle.

No bpy imports. Pure stdlib.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


TARGET_LINES: tuple = (793, 896, 1483, 1530)
_NP_CLIP_RE = re.compile(r"np\.clip\s*\(")


def _default_terrain_advanced_path() -> Path:
    """Return the path to ``terrain_advanced.py`` in the repo."""
    return Path(__file__).with_name("terrain_advanced.py")


def audit_np_clip_in_file(path: Path) -> List[Dict]:
    """Return a list of ``{file, line, snippet}`` dicts for every np.clip site.

    Non-fatal if the file does not exist — returns an empty list.
    """
    path = Path(path)
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    results: List[Dict] = []
    for i, line in enumerate(text, start=1):
        if _NP_CLIP_RE.search(line):
            results.append(
                {
                    "file": str(path),
                    "line": i,
                    "snippet": line.strip(),
                }
            )
    return results


def audit_terrain_advanced_world_units() -> Dict:
    """Audit the 4 target lines in terrain_advanced.py.

    Returns a dict with keys:
      ``path``        — absolute path to terrain_advanced.py (str)
      ``all_clips``   — every ``np.clip`` site in the file
      ``targets``     — a dict keyed by target line number (as str) with
                        ``found`` (bool), ``snippet`` (str), and ``nearby``
                        (bool, true if a clip was found within +/-3 lines)
      ``target_lines`` — the canonical list of target lines we audited
      ``summary``     — ``{"clip_count": N, "targets_with_clip_nearby": M}``
    """
    path = _default_terrain_advanced_path()
    all_clips = audit_np_clip_in_file(path)

    # Build line -> snippet lookup
    by_line = {entry["line"]: entry["snippet"] for entry in all_clips}

    targets: Dict[str, Dict] = {}
    near_count = 0
    for tgt in TARGET_LINES:
        found = tgt in by_line
        nearby = any(abs(ln - tgt) <= 3 for ln in by_line)
        if nearby:
            near_count += 1
        targets[str(tgt)] = {
            "line": tgt,
            "found": found,
            "snippet": by_line.get(tgt, ""),
            "nearby": nearby,
        }

    return {
        "path": str(path),
        "all_clips": all_clips,
        "targets": targets,
        "target_lines": list(TARGET_LINES),
        "summary": {
            "clip_count": len(all_clips),
            "targets_with_clip_nearby": near_count,
        },
    }


__all__ = [
    "TARGET_LINES",
    "audit_np_clip_in_file",
    "audit_terrain_advanced_world_units",
]
