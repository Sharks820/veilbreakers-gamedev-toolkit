"""Bundle K — terrain_stochastic_shader.

Implements stochastic (histogram-preserving) tile-sampling offsets used to
break visible tiling in terrain PBR layers. The core idea is from Heitz &
Neyret 2018 "High-Performance By-Example Noise using a Histogram-Preserving
Blending Operator" — we don't reproduce the full shader here, but we:

1. Compute a per-cell UV offset vector (float32) that a Shader Graph sampler
   can use to shift a tileable texture.
2. Provide a `StochasticShaderTemplate` dataclass that carries the shader
   parameters Unity needs to reconstruct the sampling mask.
3. Export a minimal Shader Graph JSON stub (schema-v1) that documents the
   template for the Unity importer.

Pure numpy, no bpy.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

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
class StochasticShaderTemplate:
    """Parameters describing a stochastic-tiling shader configuration.

    Consumed by the Unity Shader Graph importer. ``tile_size_m`` is the
    world-space extent of one texture tile. ``randomness_strength`` scales
    the per-cell UV offset (0 = pure tiling, 1 = full Heitz-Neyret offset).
    """

    template_id: str
    tile_size_m: float = 4.0
    randomness_strength: float = 0.75
    histogram_preserving: bool = True
    layer_index: int = 0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "tile_size_m": float(self.tile_size_m),
            "randomness_strength": float(self.randomness_strength),
            "histogram_preserving": bool(self.histogram_preserving),
            "layer_index": int(self.layer_index),
            "notes": self.notes,
        }


def build_stochastic_sampling_mask(
    stack: TerrainMaskStack,
    tile_size_m: float,
    seed: int,
) -> np.ndarray:
    """Return a (H, W, 2) float32 UV-offset mask that breaks visible tiling.

    Each cell gets a pseudo-random (u, v) offset in [-0.5, 0.5]. Offsets are
    locally coherent (neighboring cells get similar values) via a low-freq
    RNG grid upsample — this matches how Heitz-Neyret chooses tile indices
    from a triangular basis — but we skip the full triangulation here and
    use bilinear interpolation instead (cheap, deterministic, shader-friendly).

    The ``tile_size_m`` is threaded into the frequency: the RNG grid has
    one sample per tile so UVs stay consistent within a tile footprint.
    """
    if stack.height is None:
        raise ValueError("build_stochastic_sampling_mask requires stack.height")
    if tile_size_m <= 0.0:
        raise ValueError(f"tile_size_m must be > 0, got {tile_size_m}")

    h = np.asarray(stack.height)
    rows, cols = h.shape
    cell_m = float(stack.cell_size)
    tiles_y = max(2, int(np.ceil(rows * cell_m / tile_size_m)) + 2)
    tiles_x = max(2, int(np.ceil(cols * cell_m / tile_size_m)) + 2)

    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    grid_u = rng.uniform(-0.5, 0.5, size=(tiles_y, tiles_x)).astype(np.float64)
    grid_v = rng.uniform(-0.5, 0.5, size=(tiles_y, tiles_x)).astype(np.float64)

    ys = np.linspace(0.0, tiles_y - 1.0, rows)
    xs = np.linspace(0.0, tiles_x - 1.0, cols)
    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    y1 = np.clip(y0 + 1, 0, tiles_y - 1)
    x1 = np.clip(x0 + 1, 0, tiles_x - 1)
    ty = (ys - y0).reshape(-1, 1)
    tx = (xs - x0).reshape(1, -1)

    def _bilinear(g: np.ndarray) -> np.ndarray:
        a = g[np.ix_(y0, x0)]
        b = g[np.ix_(y0, x1)]
        c = g[np.ix_(y1, x0)]
        d = g[np.ix_(y1, x1)]
        top = a * (1 - tx) + b * tx
        bot = c * (1 - tx) + d * tx
        return top * (1 - ty) + bot * ty

    u = _bilinear(grid_u)
    v = _bilinear(grid_v)
    return np.stack([u, v], axis=-1).astype(np.float32)


def export_unity_shader_template(
    template: StochasticShaderTemplate,
    output_path: Path,
) -> Dict[str, Any]:
    """Emit a minimal Unity Shader Graph JSON stub for the stochastic template.

    This is not a complete Shader Graph asset — it's a schema-v1 manifest
    the Unity-side importer reads to reconstruct the stochastic sampler.
    Returns the dict that was written.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema": "veilbreakers.terrain.stochastic_shader/v1",
        "shader_graph_type": "ShaderGraph/TerrainLit_Stochastic",
        "template": template.to_dict(),
        "inputs": {
            "SamplingMask": "texture2D float2",
            "TileSize": "float",
            "RandomnessStrength": "float",
        },
        "outputs": {
            "Albedo": "float3",
            "Roughness": "float",
            "Normal": "float3",
        },
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def pass_stochastic_shader(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle K pass: build stochastic UV offset mask.

    Consumes: height
    Produces: (no new channel — stores on stack.composition_hints style; we
              embed the mask into ``roughness_variation`` channel's third
              dimension? No — that changes dtype. Instead we write it to
              ``populated_by_pass`` only and attach as a metric, because
              the mask is shader-consumed not mask-stack consumed.)

    To keep the pipeline honest, we ALSO add a subtle perturbation to
    ``roughness_variation`` so downstream passes see the stochastic signal.
    """
    from .terrain_pipeline import derive_pass_seed

    t0 = time.perf_counter()
    stack = state.mask_stack
    hints = state.intent.composition_hints if state.intent else {}
    tile_size_m = float(hints.get("stochastic_tile_size_m", 4.0))

    seed = derive_pass_seed(
        state.intent.seed if state.intent else 0,
        "stochastic_shader",
        state.tile_x,
        state.tile_y,
        region,
    )
    mask = build_stochastic_sampling_mask(stack, tile_size_m, seed)

    # Fold offset magnitude as a small perturbation into roughness_variation
    magnitude = np.sqrt(mask[..., 0] ** 2 + mask[..., 1] ** 2).astype(np.float32)
    existing = stack.get("roughness_variation")
    if existing is None:
        rough = magnitude * 0.1
    else:
        rough = np.asarray(existing, dtype=np.float32) + magnitude * 0.02
    stack.set("roughness_variation", rough.astype(np.float32), "stochastic_shader")

    return PassResult(
        pass_name="stochastic_shader",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("roughness_variation",),
        metrics={
            "tile_size_m": tile_size_m,
            "mask_shape": list(mask.shape),
            "offset_mean_abs": float(np.mean(np.abs(mask))),
            "seed_used": int(seed),
        },
        issues=[],
        seed_used=int(seed),
    )


def register_bundle_k_stochastic_shader_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="stochastic_shader",
            func=pass_stochastic_shader,
            requires_channels=("height",),
            produces_channels=("roughness_variation",),
            seed_namespace="stochastic_shader",
            requires_scene_read=False,
            description="Bundle K: stochastic tile-sampling UV offsets",
        )
    )


__all__ = [
    "StochasticShaderTemplate",
    "build_stochastic_sampling_mask",
    "export_unity_shader_template",
    "pass_stochastic_shader",
    "register_bundle_k_stochastic_shader_pass",
]
