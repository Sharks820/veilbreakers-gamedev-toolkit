"""Pass dependency DAG + parallel wave scheduler (Bundle M).

Builds a dependency graph over registered PassDefinitions using
``requires_channels`` / ``produces_channels`` and emits either a
topological linear order or a layered ("wave") schedule where passes
inside each wave can run concurrently.

Pure Python + numpy. Threading is stdlib.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional, Sequence, Set

from .terrain_pipeline import TerrainPassController
from .terrain_semantics import PassDefinition, PassResult


class PassDAGError(RuntimeError):
    """Raised when the dependency graph is cyclic or unresolvable."""


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
            defs = [registry[n] for n in pass_names if n in registry]
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

        NOTE: Within a wave passes may share the same mask stack. For
        deterministic correctness with shared-state numpy ops we serialize
        writes via a lock. Parallelism benefit comes from GIL-releasing
        numpy kernels inside each pass.
        """
        results: List[PassResult] = []
        lock = threading.Lock()

        for wave in self.parallel_waves():
            if len(wave) == 1:
                res = controller.run_pass(wave[0], checkpoint=checkpoint)
                results.append(res)
                continue

            wave_results: Dict[str, PassResult] = {}
            threads: List[threading.Thread] = []

            def _runner(pname: str) -> None:
                with lock:
                    r = controller.run_pass(pname, checkpoint=checkpoint)
                wave_results[pname] = r

            # Simple thread fanout, bounded by max_workers
            active: List[threading.Thread] = []
            for pname in wave:
                t = threading.Thread(target=_runner, args=(pname,), daemon=True)
                t.start()
                active.append(t)
                threads.append(t)
                if len(active) >= max(1, int(max_workers)):
                    for a in active:
                        a.join()
                    active = []
            for a in active:
                a.join()
            for pname in wave:
                if pname in wave_results:
                    results.append(wave_results[pname])

        return results


__all__ = [
    "PassDAG",
    "PassDAGError",
]
