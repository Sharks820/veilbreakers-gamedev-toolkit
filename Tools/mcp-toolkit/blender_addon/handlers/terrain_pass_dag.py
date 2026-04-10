"""Pass dependency DAG + parallel wave scheduler (Bundle M).

Builds a dependency graph over registered PassDefinitions using
``requires_channels`` / ``produces_channels`` and emits either a
topological linear order or a layered ("wave") schedule where passes
inside each wave can run concurrently.

Pure Python + numpy. Threading is stdlib.
"""

from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Sequence, Set

from .terrain_pipeline import TerrainPassController
from .terrain_semantics import PassDefinition, PassResult


class PassDAGError(RuntimeError):
    """Raised when the dependency graph is cyclic or unresolvable."""


def _merge_pass_outputs(
    target_controller: TerrainPassController,
    source_result: PassResult,
) -> PassResult:
    """Merge a worker pass result back into the shared controller state."""
    definition = target_controller.get_pass(source_result.pass_name)
    target_stack = target_controller.state.mask_stack
    source_stack = source_result.metrics.pop("_worker_mask_stack", None)

    if source_stack is None:
        raise PassDAGError(
            f"Worker for pass '{source_result.pass_name}' returned no mask stack snapshot"
        )

    for channel in definition.produces_channels:
        if not hasattr(source_stack, channel):
            raise PassDAGError(
                f"Pass '{source_result.pass_name}' declared unknown channel '{channel}'"
            )
        setattr(target_stack, channel, copy.deepcopy(getattr(source_stack, channel)))
        if getattr(source_stack, channel) is not None:
            target_stack.populated_by_pass[channel] = source_result.pass_name
        target_stack.dirty_channels.discard(channel)

    target_stack.height_min_m = source_stack.height_min_m
    target_stack.height_max_m = source_stack.height_max_m
    target_stack.content_hash = None

    source_result.content_hash_after = target_stack.compute_hash()
    target_controller.state.record_pass(source_result)

    return source_result


class PassDAG:
    """Dependency graph over a set of PassDefinitions."""

    def __init__(self, passes: Sequence[PassDefinition]) -> None:
        self._passes: Dict[str, PassDefinition] = {p.name: p for p in passes}
        self._producers: Dict[str, str] = {}
        for p in passes:
            for ch in p.produces_channels:
                # Last producer wins — stable enough for the DAG
                self._producers[ch] = p.name

    @classmethod
    def from_registry(cls, pass_names: Optional[Sequence[str]] = None) -> "PassDAG":
        registry = TerrainPassController.PASS_REGISTRY
        if pass_names is None:
            defs = list(registry.values())
        else:
            missing = [n for n in pass_names if n not in registry]
            if missing:
                raise PassDAGError(
                    f"Unknown passes requested for DAG construction: {missing}"
                )
            defs = [registry[n] for n in pass_names]
        return cls(defs)

    @property
    def names(self) -> List[str]:
        return list(self._passes.keys())

    def dependencies(self, pass_name: str) -> Set[str]:
        """Return the set of pass names that produce channels ``pass_name`` consumes."""
        pdef = self._passes[pass_name]
        deps: Set[str] = set()
        for ch in pdef.requires_channels:
            producer = self._producers.get(ch)
            if producer and producer != pass_name and producer in self._passes:
                deps.add(producer)
        return deps

    def topological_order(self) -> List[str]:
        """Return a flat topological ordering of the passes. Raises on cycle."""
        order: List[str] = []
        visited: Set[str] = set()
        temp: Set[str] = set()

        def visit(n: str) -> None:
            if n in visited:
                return
            if n in temp:
                raise PassDAGError(f"Cycle detected at pass {n}")
            temp.add(n)
            for dep in self.dependencies(n):
                visit(dep)
            temp.discard(n)
            visited.add(n)
            order.append(n)

        for name in sorted(self._passes.keys()):
            visit(name)
        return order

    def parallel_waves(self) -> List[List[str]]:
        """Group passes into waves where each wave can run in parallel.

        Wave N contains passes whose dependencies are all in waves < N.
        """
        wave_index: Dict[str, int] = {}
        # Use topological order so dependencies resolve first
        for name in self.topological_order():
            deps = self.dependencies(name)
            if not deps:
                wave_index[name] = 0
            else:
                wave_index[name] = 1 + max(wave_index[d] for d in deps if d in wave_index)

        waves: Dict[int, List[str]] = {}
        for name, idx in wave_index.items():
            waves.setdefault(idx, []).append(name)
        return [sorted(waves[k]) for k in sorted(waves.keys())]

    def execute_parallel(
        self,
        controller: TerrainPassController,
        *,
        max_workers: int = 4,
        checkpoint: bool = False,
    ) -> List[PassResult]:
        """Execute all passes grouped by wave.

        Each pass in a wave executes against a deep-copied pipeline state,
        then its declared output channels are merged back into the shared
        controller state in deterministic name order. This preserves actual
        concurrency without allowing worker threads to race on a shared
        ``TerrainMaskStack``.
        """
        results: List[PassResult] = []

        for wave in self.parallel_waves():
            if len(wave) == 1:
                res = controller.run_pass(wave[0], checkpoint=checkpoint)
                results.append(res)
                continue

            wave_results: Dict[str, PassResult] = {}

            def _runner(pname: str) -> PassResult:
                worker_state = copy.deepcopy(controller.state)
                worker_controller = TerrainPassController(
                    worker_state,
                    checkpoint_dir=controller.checkpoint_dir,
                )
                result = worker_controller.run_pass(pname, checkpoint=False)
                result.metrics["_worker_mask_stack"] = worker_controller.state.mask_stack
                return result

            with ThreadPoolExecutor(
                max_workers=max(1, min(int(max_workers), len(wave)))
            ) as executor:
                future_to_name = {
                    executor.submit(_runner, pname): pname
                    for pname in wave
                }
                for future in as_completed(future_to_name):
                    pname = future_to_name[future]
                    wave_results[pname] = future.result()

            for pname in sorted(wave):
                merged = _merge_pass_outputs(controller, wave_results[pname])
                if checkpoint and merged.status == "ok":
                    ckpt = controller._save_checkpoint(pname, merged)
                    merged.checkpoint_path = str(ckpt.mask_stack_path)
                    controller.state.checkpoints.append(ckpt)
                results.append(merged)

        return results


__all__ = [
    "PassDAG",
    "PassDAGError",
]
