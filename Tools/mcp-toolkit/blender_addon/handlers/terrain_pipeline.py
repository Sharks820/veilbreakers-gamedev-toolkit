"""TerrainPassController — the atomic pass orchestrator.

Bundle A — Foundation. Every terrain mutation routes through here.
See docs/terrain_ultra_implementation_plan_2026-04-08.md §5.10, §5.11, §5.12, §6.

Responsibilities
----------------
- Register passes via ``TerrainPassController.register_pass(PassDefinition)``
- Run a single pass or an ordered pipeline
- Enforce scene-read before mutation (passes that require it)
- Enforce protected-zone policy per pass
- Derive deterministic per-pass seeds
- Emit checkpoints after successful passes
- Rollback to any prior checkpoint

NO Blender imports. Pure Python + numpy so the controller can be unit-tested.
Blender geometry snapshots are handled by ``handle_run_terrain_pass`` on the
Blender side of the TCP bridge.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from .terrain_semantics import (
    BBox,
    PassContractError,
    PassDefinition,
    PassResult,
    ProtectedZoneViolation,
    SceneReadRequired,
    TerrainCheckpoint,
    TerrainIntentState,
    TerrainMaskStack,
    TerrainPipelineState,
    UnknownPassError,
    ValidationIssue,
)


def _make_gate_issue(code: str, severity: str, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, severity=severity, message=message)


# ---------------------------------------------------------------------------
# Determinism seed derivation (§5.12)
# ---------------------------------------------------------------------------


def derive_pass_seed(
    intent_seed: int,
    seed_namespace: str,
    tile_x: int,
    tile_y: int,
    region: Optional[BBox],
) -> int:
    """Derive a deterministic 32-bit seed from intent + pass + tile + region.

    Uses SHA-256 over a JSON-encoded tuple. Python's built-in ``hash()`` is
    PYTHONHASHSEED-randomized, so we cannot use it. The resulting integer
    is masked to 32 bits for numpy RNG compatibility.
    """
    payload = json.dumps(
        [
            int(intent_seed),
            str(seed_namespace),
            int(tile_x),
            int(tile_y),
            list(region.to_tuple()) if region is not None else None,
        ],
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:4], "big") & 0xFFFFFFFF


# ---------------------------------------------------------------------------
# TerrainPassController (§5.10)
# ---------------------------------------------------------------------------


class TerrainPassController:
    """Central pass orchestrator. All terrain mutations route through here."""

    # Class-level pass registry — populated via ``register_pass``
    PASS_REGISTRY: Dict[str, PassDefinition] = {}

    def __init__(
        self,
        state: TerrainPipelineState,
        *,
        checkpoint_dir: Optional[Path] = None,
    ) -> None:
        self.state = state
        self.checkpoint_dir: Path = Path(
            checkpoint_dir
            if checkpoint_dir is not None
            else Path(".planning") / "terrain_checkpoints"
        )

    # -- registration --------------------------------------------------------

    @classmethod
    def register_pass(cls, definition: PassDefinition) -> None:
        """Register a pass definition by name. Duplicate names overwrite."""
        cls.PASS_REGISTRY[definition.name] = definition

    @classmethod
    def get_pass(cls, pass_name: str) -> PassDefinition:
        if pass_name not in cls.PASS_REGISTRY:
            raise UnknownPassError(f"Pass not registered: {pass_name}")
        return cls.PASS_REGISTRY[pass_name]

    @classmethod
    def clear_registry(cls) -> None:
        """Test helper — clears the pass registry."""
        cls.PASS_REGISTRY.clear()

    # -- enforcement hooks ---------------------------------------------------

    def require_scene_read(self, operation: str) -> None:
        """Raise SceneReadRequired if current intent lacks a TerrainSceneRead."""
        if self.state.intent.scene_read is None:
            raise SceneReadRequired(
                f"Pass '{operation}' requires a TerrainSceneRead on the intent. "
                "Attach one via intent.with_scene_read() before running mutating passes."
            )

    def enforce_protected_zones(
        self,
        pass_name: str,
        target_bounds: BBox,
    ) -> None:
        """Raise ProtectedZoneViolation only if a forbidding zone fully
        covers ``target_bounds`` — i.e. the pass would have no mutable
        cells to work on.

        Partial intersection is allowed: the pass is expected to consult
        per-cell protected masks (see ``pass_erosion``) and skip mutation
        on forbidden cells.
        """
        for zone in self.state.intent.protected_zones:
            if not zone.bounds.intersects(target_bounds):
                continue
            if zone.permits(pass_name):
                continue
            fully_covers = (
                zone.bounds.min_x <= target_bounds.min_x
                and zone.bounds.min_y <= target_bounds.min_y
                and zone.bounds.max_x >= target_bounds.max_x
                and zone.bounds.max_y >= target_bounds.max_y
            )
            if fully_covers:
                raise ProtectedZoneViolation(
                    f"Pass '{pass_name}' forbidden in protected zone "
                    f"'{zone.zone_id}' (kind={zone.kind}) which fully "
                    f"covers target_bounds — no mutable cells available."
                )

    # -- execution -----------------------------------------------------------

    def run_pass(
        self,
        pass_name: str,
        region: Optional[BBox] = None,
        *,
        force: bool = False,
        checkpoint: bool = True,
    ) -> PassResult:
        """Run a single registered pass against the current state.

        Enforces:
            - Scene-read presence (if the pass requires it)
            - Protected-zone permissions over ``region`` (or full region_bounds)
            - Channel prerequisites declared by the pass
            - Post-run verification that ``produces_channels`` are actually set

        Records the pass result on ``state.pass_history``, optionally emits
        a checkpoint, and returns the ``PassResult``.
        """
        definition = self.get_pass(pass_name)

        if definition.requires_scene_read:
            self.require_scene_read(pass_name)

        target_bounds = region if region is not None else self.state.intent.region_bounds
        if definition.respects_protected_zones:
            self.enforce_protected_zones(pass_name, target_bounds)

        missing_inputs = [
            ch
            for ch in definition.requires_channels
            if self.state.mask_stack.get(ch) is None
        ]
        if missing_inputs:
            raise PassContractError(
                f"Pass '{pass_name}' requires channels {missing_inputs} "
                "but they are not populated on the mask stack."
            )

        content_hash_before = self.state.mask_stack.compute_hash()
        seed_used = derive_pass_seed(
            self.state.intent.seed,
            definition.seed_namespace or pass_name,
            self.state.tile_x,
            self.state.tile_y,
            region,
        )

        t0 = time.perf_counter()
        try:
            result = definition.func(self.state, region)
        except Exception as exc:  # pragma: no cover — surface all errors
            result = PassResult(
                pass_name=pass_name,
                status="failed",
                duration_seconds=time.perf_counter() - t0,
                metrics={"error": repr(exc)},
                seed_used=seed_used,
                content_hash_before=content_hash_before,
            )
            self.state.record_pass(result)
            raise

        if not isinstance(result, PassResult):
            raise PassContractError(
                f"Pass '{pass_name}' did not return a PassResult "
                f"(got {type(result).__name__})"
            )

        # Defaults / enforced fields
        result.pass_name = pass_name
        result.seed_used = seed_used
        result.content_hash_before = content_hash_before
        if result.duration_seconds <= 0.0:
            result.duration_seconds = time.perf_counter() - t0

        # Verify produced-channel contract
        missing_outputs = [
            ch
            for ch in definition.produces_channels
            if self.state.mask_stack.get(ch) is None
        ]
        if missing_outputs and result.status == "ok":
            raise PassContractError(
                f"Pass '{pass_name}' declared produces_channels={definition.produces_channels} "
                f"but did not populate {missing_outputs}"
            )

        # Run quality gate if defined (§agent protocol rule 4)
        if definition.quality_gate is not None and result.status == "ok":
            gate = definition.quality_gate
            try:
                gate_issues = gate.check(result, self.state.mask_stack)
            except Exception as exc:  # pragma: no cover — gate bugs must fail loudly
                gate_issues = [
                    # Construct ValidationIssue lazily to avoid a hard import loop
                    _make_gate_issue(
                        code=f"GATE_{gate.name.upper()}_CRASHED",
                        severity="hard",
                        message=f"quality gate {gate.name} raised: {exc!r}",
                    )
                ]
            if gate_issues:
                hard = [i for i in gate_issues if getattr(i, "severity", "") == "hard"]
                if hard and gate.blocking:
                    result.status = "failed"
                    result.issues.extend(gate_issues)
                else:
                    result.status = "warning" if result.status == "ok" else result.status
                    result.warnings.extend(gate_issues)

        # Run visual validator (optional)
        if definition.visual_validator is not None and result.status in ("ok", "warning"):
            try:
                signature = definition.visual_validator(self.state.mask_stack)
                result.metrics.setdefault("visual_signature_bytes", len(signature or b""))
            except Exception as exc:  # pragma: no cover
                result.metrics["visual_signature_error"] = repr(exc)

        result.content_hash_after = self.state.mask_stack.compute_hash()
        self.state.record_pass(result)

        if checkpoint and result.status == "ok":
            ckpt = self._save_checkpoint(pass_name, result)
            result.checkpoint_path = str(ckpt.mask_stack_path)
            self.state.checkpoints.append(ckpt)

        return result

    def run_pipeline(
        self,
        intent: Optional[TerrainIntentState] = None,
        pass_sequence: Optional[List[str]] = None,
        *,
        region: Optional[BBox] = None,
        checkpoint: bool = True,
    ) -> List[PassResult]:
        """Run a sequence of passes in order. Stops on the first failure."""
        if intent is not None:
            # Replace intent — caller is re-homing state
            self.state.intent = intent

        if pass_sequence is None:
            pass_sequence = [
                "macro_world",
                "structural_masks",
                "erosion",
                "validation_minimal",
            ]

        results: List[PassResult] = []
        for pass_name in pass_sequence:
            res = self.run_pass(pass_name, region=region, checkpoint=checkpoint)
            results.append(res)
            if res.status == "failed":
                break
        return results

    # -- checkpoints ---------------------------------------------------------

    def _save_checkpoint(self, pass_name: str, result: PassResult) -> TerrainCheckpoint:
        """Persist the current mask stack to ``checkpoint_dir``.

        Geometry snapshots (Blender .blend files) are the responsibility
        of the handler-side bridge — this controller is Blender-free so
        it only snapshots the mask stack.
        """
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_id = f"{pass_name}_{uuid.uuid4().hex[:8]}"
        mask_path = self.checkpoint_dir / f"{checkpoint_id}.npz"
        self.state.mask_stack.to_npz(mask_path)

        parent_id = (
            self.state.checkpoints[-1].checkpoint_id
            if self.state.checkpoints
            else None
        )
        ckpt = TerrainCheckpoint(
            checkpoint_id=checkpoint_id,
            pass_name=pass_name,
            timestamp=time.time(),
            intent_hash=self.state.intent.intent_hash(),
            mask_stack_path=mask_path,
            geometry_snapshot_path=None,
            content_hash=result.content_hash_after or self.state.mask_stack.compute_hash(),
            parent_checkpoint_id=parent_id,
            metrics=dict(result.metrics),
        )
        return ckpt

    def rollback_to(self, checkpoint_id: str) -> None:
        """Rewind mask stack state to a prior checkpoint by id."""
        for ckpt in reversed(self.state.checkpoints):
            if ckpt.checkpoint_id == checkpoint_id:
                restored = TerrainMaskStack.from_npz(ckpt.mask_stack_path)
                self.state.mask_stack = restored
                # Truncate history past the restored point
                idx = self.state.checkpoints.index(ckpt)
                self.state.checkpoints = self.state.checkpoints[: idx + 1]
                return
        raise KeyError(f"Unknown checkpoint id: {checkpoint_id}")

    def rollback_last_checkpoint(self) -> None:
        if not self.state.checkpoints:
            raise RuntimeError("No checkpoints available to roll back to.")
        self.rollback_to(self.state.checkpoints[-1].checkpoint_id)


# ---------------------------------------------------------------------------
# Default pass registration
# ---------------------------------------------------------------------------


def register_default_passes() -> None:
    """Register the four Bundle A default passes on the controller.

    Importing this module does NOT auto-register — call this function
    (or import ``_terrain_world`` which calls it) to activate them.
    This lets unit tests start from an empty registry.
    """
    # Lazy import to avoid circular dependency at module load time.
    from . import _terrain_world as _tw

    TerrainPassController.register_pass(
        PassDefinition(
            name="macro_world",
            func=_tw.pass_macro_world,
            requires_channels=(),
            produces_channels=("height",),
            seed_namespace="macro_world",
            may_modify_geometry=False,
            requires_scene_read=False,
        )
    )
    TerrainPassController.register_pass(
        PassDefinition(
            name="structural_masks",
            func=_tw.pass_structural_masks,
            requires_channels=("height",),
            produces_channels=(
                "slope",
                "curvature",
                "concavity",
                "convexity",
                "ridge",
                "basin",
                "saliency_macro",
            ),
            seed_namespace="structural_masks",
            requires_scene_read=False,
        )
    )
    TerrainPassController.register_pass(
        PassDefinition(
            name="erosion",
            func=_tw.pass_erosion,
            requires_channels=("height",),
            produces_channels=(
                "erosion_amount",
                "deposition_amount",
                "wetness",
                "drainage",
                "bank_instability",
                "talus",
            ),
            seed_namespace="erosion",
            requires_scene_read=True,
        )
    )
    TerrainPassController.register_pass(
        PassDefinition(
            name="validation_minimal",
            func=_tw.pass_validation_minimal,
            requires_channels=("height", "slope"),
            produces_channels=(),
            seed_namespace="validation_minimal",
            may_modify_geometry=False,
            respects_protected_zones=False,
            requires_scene_read=False,
        )
    )


__all__ = [
    "TerrainPassController",
    "derive_pass_seed",
    "register_default_passes",
]
