"""Bundle N — determinism CI regression harness.

Re-runs a deterministic pipeline N times against the same seed/intent and
asserts that the resulting ``TerrainMaskStack`` content hashes are
bit-identical. Detects mid-pipeline non-determinism (stray ``hash()``,
``random.random()``, wall-clock seeds) before it ships.

Pure Python + numpy — no bpy. See
docs/terrain_ultra_implementation_plan_2026-04-08.md §19 Bundle N.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .terrain_pipeline import TerrainPassController
from .terrain_semantics import (
    TerrainMaskStack,
    TerrainPipelineState,
    ValidationIssue,
)


@dataclass
class DeterminismRun:
    """Result of one deterministic pipeline replay."""

    run_index: int
    content_hash: str
    per_channel_hashes: Dict[str, str] = field(default_factory=dict)
    duration_seconds: float = 0.0
    pass_hashes: Tuple[str, ...] = ()


def _snapshot_channel_hashes(stack: TerrainMaskStack) -> Dict[str, str]:
    """Return per-channel SHA-256 (truncated) for a stack."""
    import hashlib

    out: Dict[str, str] = {}
    for name in stack._ARRAY_CHANNELS:
        val = getattr(stack, name, None)
        if val is None:
            continue
        import numpy as np

        arr = np.ascontiguousarray(val)
        h = hashlib.sha256()
        h.update(name.encode("utf-8"))
        h.update(str(arr.dtype).encode("utf-8"))
        h.update(repr(arr.shape).encode("utf-8"))
        h.update(arr.tobytes())
        out[name] = h.hexdigest()
    return out


def _clone_state(state: TerrainPipelineState) -> TerrainPipelineState:
    """Deep-copy a pipeline state so a replay starts from a fresh mask stack."""
    return copy.deepcopy(state)


def run_determinism_check(
    controller: TerrainPassController,
    seed: int,
    runs: int = 3,
    *,
    pass_sequence: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Execute the same pipeline ``runs`` times and assert bit-identical outputs.

    The controller's current state is used as the baseline. Each run deep-copies
    the baseline and executes ``pass_sequence`` (or the default pipeline). The
    returned dict has keys:

        ``deterministic`` : bool
        ``runs``          : list[DeterminismRun]
        ``reference_hash``: str
        ``mismatches``    : list[(run_index, hash)]
        ``channel_divergences`` : list[(run_index, channel_name)]
    """
    if runs < 2:
        raise ValueError("run_determinism_check requires runs >= 2")

    baseline_state = _clone_state(controller.state)
    baseline_state.intent = baseline_state.intent  # retain intent

    run_records: List[DeterminismRun] = []
    for i in range(runs):
        # Fresh state + fresh controller (new checkpoint_dir not needed — we
        # pass checkpoint=False to avoid polluting disk).
        replay_state = _clone_state(baseline_state)
        replay_ctrl = TerrainPassController(replay_state, checkpoint_dir=controller.checkpoint_dir)
        t0 = time.perf_counter()
        results = replay_ctrl.run_pipeline(
            pass_sequence=list(pass_sequence) if pass_sequence else None,
            checkpoint=False,
        )
        dt = time.perf_counter() - t0
        content_hash = replay_state.mask_stack.compute_hash()
        channel_hashes = _snapshot_channel_hashes(replay_state.mask_stack)
        pass_hashes = tuple(r.content_hash_after or "" for r in results)
        run_records.append(
            DeterminismRun(
                run_index=i,
                content_hash=content_hash,
                per_channel_hashes=channel_hashes,
                duration_seconds=dt,
                pass_hashes=pass_hashes,
            )
        )

    reference = run_records[0]
    mismatches: List[Tuple[int, str]] = []
    channel_divergences: List[Tuple[int, str]] = []
    for rec in run_records[1:]:
        if rec.content_hash != reference.content_hash:
            mismatches.append((rec.run_index, rec.content_hash))
            for ch, h in rec.per_channel_hashes.items():
                if reference.per_channel_hashes.get(ch) != h:
                    channel_divergences.append((rec.run_index, ch))

    return {
        "deterministic": not mismatches,
        "runs": run_records,
        "reference_hash": reference.content_hash,
        "mismatches": mismatches,
        "channel_divergences": channel_divergences,
        "seed": int(seed),
        "run_count": runs,
    }


def detect_determinism_regressions(
    baseline_hash: str,
    current_hash: str,
) -> List[ValidationIssue]:
    """Compare a freshly-computed content hash against a stored baseline."""
    issues: List[ValidationIssue] = []
    if not baseline_hash or not current_hash:
        issues.append(
            ValidationIssue(
                code="DETERMINISM_HASH_MISSING",
                severity="soft",
                message=(
                    f"one or both hashes missing — baseline={baseline_hash!r}, "
                    f"current={current_hash!r}"
                ),
            )
        )
        return issues
    if baseline_hash != current_hash:
        issues.append(
            ValidationIssue(
                code="DETERMINISM_REGRESSION",
                severity="hard",
                message=(
                    "mask stack hash diverged from baseline: "
                    f"baseline={baseline_hash[:16]}... current={current_hash[:16]}..."
                ),
                remediation=(
                    "Audit recently-touched passes for hash()/random.random()/"
                    "time.time() and replace with derive_pass_seed."
                ),
            )
        )
    return issues


__all__ = [
    "DeterminismRun",
    "run_determinism_check",
    "detect_determinism_regressions",
]
