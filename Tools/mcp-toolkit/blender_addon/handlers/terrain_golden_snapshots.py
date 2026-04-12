"""Bundle N — golden snapshot library.

Canonical reference tiles for deep regression testing. Each golden
snapshot captures the mask stack's content hash plus per-channel hashes
and the pipeline version. A freshly-generated tile is compared against a
stored golden; any mismatch raises a hard ``ValidationIssue``.

Pure numpy + stdlib — no bpy. See plan §19.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

import numpy as np

from .terrain_pipeline import TerrainPassController
from .terrain_semantics import (
    TerrainIntentState,
    TerrainMaskStack,
    TerrainPipelineState,
    ValidationIssue,
)


PIPELINE_VERSION = "bundle_n_1.0"


@dataclass
class GoldenSnapshot:
    """A canonical reference tile hash record."""

    snapshot_id: str
    content_hash: str
    channel_hashes: Dict[str, str] = field(default_factory=dict)
    timestamp: float = 0.0
    pipeline_version: str = PIPELINE_VERSION
    seed: int = 0
    tile_coords: Tuple[int, int] = (0, 0)
    tile_size: int = 0
    cell_size: float = 1.0
    populated_by_pass: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["tile_coords"] = list(self.tile_coords)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoldenSnapshot":
        coords = data.get("tile_coords", [0, 0])
        return cls(
            snapshot_id=str(data["snapshot_id"]),
            content_hash=str(data["content_hash"]),
            channel_hashes=dict(data.get("channel_hashes", {})),
            timestamp=float(data.get("timestamp", 0.0)),
            pipeline_version=str(data.get("pipeline_version", PIPELINE_VERSION)),
            seed=int(data.get("seed", 0)),
            tile_coords=(int(coords[0]), int(coords[1])),
            tile_size=int(data.get("tile_size", 0)),
            cell_size=float(data.get("cell_size", 1.0)),
            populated_by_pass=dict(data.get("populated_by_pass", {})),
        )


def _channel_hashes(stack: TerrainMaskStack) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for name in stack._ARRAY_CHANNELS:
        val = getattr(stack, name, None)
        if val is None:
            continue
        arr = np.ascontiguousarray(val)
        h = hashlib.sha256()
        h.update(name.encode("utf-8"))
        h.update(str(arr.dtype).encode("utf-8"))
        h.update(repr(arr.shape).encode("utf-8"))
        h.update(arr.tobytes())
        out[name] = h.hexdigest()
    return out


def save_golden_snapshot(
    stack: TerrainMaskStack,
    output_dir: Path,
    snapshot_id: str,
    *,
    seed: int = 0,
) -> GoldenSnapshot:
    """Hash the stack, persist a .json record, and return the GoldenSnapshot."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    snap = GoldenSnapshot(
        snapshot_id=snapshot_id,
        content_hash=stack.compute_hash(),
        channel_hashes=_channel_hashes(stack),
        timestamp=time.time(),
        pipeline_version=PIPELINE_VERSION,
        seed=int(seed),
        tile_coords=(int(stack.tile_x), int(stack.tile_y)),
        tile_size=int(stack.tile_size),
        cell_size=float(stack.cell_size),
        populated_by_pass=dict(stack.populated_by_pass),
    )
    path = output_dir / f"{snapshot_id}.golden.json"
    path.write_text(json.dumps(snap.to_dict(), sort_keys=True, indent=2))
    return snap


def load_golden_snapshot(path: Path) -> GoldenSnapshot:
    """Load a previously-saved golden snapshot."""
    raw = json.loads(Path(path).read_text())
    return GoldenSnapshot.from_dict(raw)


def compare_against_golden(
    stack: TerrainMaskStack,
    golden: GoldenSnapshot,
    tolerance: float = 0.0,
) -> List[ValidationIssue]:
    """Compare a fresh stack against a stored golden.

    ``tolerance`` is reserved for future float-aware comparisons; currently
    any content-hash mismatch is a hard failure.
    """
    issues: List[ValidationIssue] = []
    current_hash = stack.compute_hash()
    if current_hash != golden.content_hash:
        issues.append(
            ValidationIssue(
                code="GOLDEN_HASH_MISMATCH",
                severity="hard",
                message=(
                    f"golden '{golden.snapshot_id}' content hash diverged: "
                    f"expected {golden.content_hash[:16]}..., "
                    f"got {current_hash[:16]}..."
                ),
                remediation=(
                    "Regenerate the golden if the change is intentional, "
                    "otherwise audit the offending pass."
                ),
            )
        )
    current_channels = _channel_hashes(stack)
    divergences: List[str] = []
    for ch, h in golden.channel_hashes.items():
        if current_channels.get(ch) != h:
            divergences.append(ch)
    new_channels = sorted(set(current_channels) - set(golden.channel_hashes))
    if new_channels:
        issues.append(
            ValidationIssue(
                code="GOLDEN_NEW_CHANNEL",
                severity="soft",
                message=(
                    f"new channels present since golden capture: {new_channels}"
                ),
            )
        )
    if divergences:
        issues.append(
            ValidationIssue(
                code="GOLDEN_CHANNEL_DIVERGENCE",
                severity="hard",
                message=(
                    f"channels diverged from golden '{golden.snapshot_id}': "
                    f"{divergences[:6]}"
                ),
            )
        )
    if golden.pipeline_version != PIPELINE_VERSION:
        issues.append(
            ValidationIssue(
                code="GOLDEN_PIPELINE_VERSION_DRIFT",
                severity="soft",
                message=(
                    f"golden pipeline_version={golden.pipeline_version!r} "
                    f"does not match current {PIPELINE_VERSION!r}"
                ),
            )
        )
    _ = tolerance
    return issues


def seed_golden_library(
    controller: TerrainPassController,
    output_dir: Path,
    count: int = 120,
    *,
    base_intent: Optional[TerrainIntentState] = None,
    build_state_fn: Optional[Any] = None,
) -> List[GoldenSnapshot]:
    """Generate ``count`` canonical golden snapshots.

    Strategy: for i in [0, count), deep-copy the controller's baseline state,
    override the seed to ``baseline_seed + i`` (modulo tile coords also
    offset), run the default pipeline, and save the result.

    ``build_state_fn`` is an optional callable ``(seed, tile_x, tile_y) ->
    TerrainPipelineState`` allowing tests to inject lightweight state
    construction without requiring a fully-populated controller. If not
    provided, the controller's current state is cloned via deepcopy.
    """
    import copy

    from dataclasses import replace as _replace

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshots: List[GoldenSnapshot] = []

    for i in range(count):
        if build_state_fn is not None:
            state = build_state_fn(
                seed=(base_intent.seed if base_intent else 0) + i,
                tile_x=i % 8,
                tile_y=i // 8,
            )
        else:
            state = copy.deepcopy(controller.state)
            new_seed = int(state.intent.seed) + i
            state.intent = _replace(state.intent, seed=new_seed)

        replay_ctrl = TerrainPassController(
            state, checkpoint_dir=controller.checkpoint_dir
        )
        try:
            replay_ctrl.run_pipeline(checkpoint=False)
        except Exception:
            # Skip tiles that fail to generate — seed library is best-effort.
            logger.debug("Seed %d failed during golden snapshot generation", new_seed, exc_info=True)
            continue
        snap_id = f"golden_{i:04d}_seed{state.intent.seed}"
        snap = save_golden_snapshot(
            state.mask_stack,
            output_dir,
            snap_id,
            seed=int(state.intent.seed),
        )
        snapshots.append(snap)

    manifest_path = output_dir / "golden_library_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "pipeline_version": PIPELINE_VERSION,
                "count": len(snapshots),
                "snapshot_ids": [s.snapshot_id for s in snapshots],
                "timestamp": time.time(),
            },
            sort_keys=True,
            indent=2,
        )
    )
    return snapshots


__all__ = [
    "PIPELINE_VERSION",
    "GoldenSnapshot",
    "save_golden_snapshot",
    "load_golden_snapshot",
    "compare_against_golden",
    "seed_golden_library",
]
