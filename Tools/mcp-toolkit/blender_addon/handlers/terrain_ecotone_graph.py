"""Bundle J — terrain_ecotone_graph.

Builds an adjacency graph of biomes present on a tile and defines the
smooth transition zones between them (ecotones). Outputs are stored on
``stack.populated_by_pass['ecotone_graph']`` via metrics; the graph is
also returned to the caller.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
    ValidationIssue,
)


@dataclass
class EcotoneEdge:
    """Describes a transition between two adjacent biomes."""

    from_biome: int
    to_biome: int
    transition_width_m: float
    mixing_curve: str = "smoothstep"  # "linear" | "smoothstep" | "sigmoid"
    shared_cells: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "from_biome": int(self.from_biome),
            "to_biome": int(self.to_biome),
            "transition_width_m": float(self.transition_width_m),
            "mixing_curve": self.mixing_curve,
            "shared_cells": int(self.shared_cells),
        }


def _find_adjacencies(biome: np.ndarray) -> Dict[Tuple[int, int], int]:
    """Return a dict of (a, b) -> number of shared 4-neighbor borders.

    Always stores with ``a < b`` to deduplicate.
    """
    pairs: Dict[Tuple[int, int], int] = {}
    # Horizontal neighbors
    left = biome[:, :-1]
    right = biome[:, 1:]
    diff_h = left != right
    for a, b in zip(left[diff_h].tolist(), right[diff_h].tolist()):
        key = (int(min(a, b)), int(max(a, b)))
        pairs[key] = pairs.get(key, 0) + 1
    # Vertical neighbors
    up = biome[:-1, :]
    down = biome[1:, :]
    diff_v = up != down
    for a, b in zip(up[diff_v].tolist(), down[diff_v].tolist()):
        key = (int(min(a, b)), int(max(a, b)))
        pairs[key] = pairs.get(key, 0) + 1
    return pairs


def build_ecotone_graph(stack: TerrainMaskStack) -> Dict[str, Any]:
    """Return a dict describing the biome adjacency graph.

    If ``stack.biome_id`` is None, returns an empty graph.

    Shape::
        {
            "nodes": [biome_id, ...],
            "edges": [EcotoneEdge.as_dict(), ...],
            "cell_size_m": float,
            "tile_size": int,
        }
    """
    if stack.biome_id is None:
        return {
            "nodes": [],
            "edges": [],
            "cell_size_m": float(stack.cell_size),
            "tile_size": int(stack.tile_size),
        }

    biome = np.asarray(stack.biome_id, dtype=np.int64)
    nodes = sorted({int(v) for v in np.unique(biome).tolist()})
    adjacencies = _find_adjacencies(biome)

    edges: List[EcotoneEdge] = []
    for (a, b), shared in sorted(adjacencies.items()):
        # Transition width scales with shared border length (cells * cell_size)
        width = float(max(2, min(32, int(round(shared ** 0.5)))) * stack.cell_size)
        edges.append(
            EcotoneEdge(
                from_biome=a,
                to_biome=b,
                transition_width_m=width,
                mixing_curve="smoothstep",
                shared_cells=int(shared),
            )
        )

    return {
        "nodes": nodes,
        "edges": [e.as_dict() for e in edges],
        "cell_size_m": float(stack.cell_size),
        "tile_size": int(stack.tile_size),
    }


def validate_ecotone_smoothness(graph: Dict[str, Any]) -> List[ValidationIssue]:
    """Flag any ecotone edge whose transition_width is unreasonably narrow.

    Narrow edges (< 2 cells) signal hard biome boundaries, which look
    painterly rather than natural. Soft issue (warning).
    """
    issues: List[ValidationIssue] = []
    cell_size = float(graph.get("cell_size_m", 1.0) or 1.0)
    for edge in graph.get("edges", []):
        width = float(edge.get("transition_width_m", 0.0))
        if width < 2.0 * cell_size:
            issues.append(
                ValidationIssue(
                    code="ECOTONE_HARD_BOUNDARY",
                    severity="soft",
                    message=(
                        f"biomes {edge['from_biome']}->{edge['to_biome']} "
                        f"have narrow ecotone {width:.2f}m (< 2 cells)"
                    ),
                )
            )
    return issues


def pass_ecotones(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle J pass: build ecotone graph.

    Consumes: height, biome_id (optional)
    Produces: (metadata only; no new mask channel)
    """
    t0 = time.perf_counter()
    stack = state.mask_stack

    # Populate traversability as the Unity-ready channel this pass guarantees,
    # so protocol Rule 7 holds even when biome_id is absent. Only compute if
    # not already populated.
    if stack.traversability is None:
        from .terrain_navmesh_export import compute_traversability

        stack.set("traversability", compute_traversability(stack), "ecotones")

    graph = build_ecotone_graph(stack)
    issues = validate_ecotone_smoothness(graph)

    return PassResult(
        pass_name="ecotones",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("traversability",),
        metrics={
            "node_count": len(graph["nodes"]),
            "edge_count": len(graph["edges"]),
            "graph": graph,
        },
        issues=issues,
    )


def register_bundle_j_ecotones_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="ecotones",
            func=pass_ecotones,
            requires_channels=("height",),
            produces_channels=("traversability",),
            seed_namespace="ecotones",
            requires_scene_read=False,
            description="Bundle J: biome adjacency / ecotone graph",
        )
    )


__all__ = [
    "EcotoneEdge",
    "build_ecotone_graph",
    "validate_ecotone_smoothness",
    "pass_ecotones",
    "register_bundle_j_ecotones_pass",
]
