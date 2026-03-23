"""Advanced terrain features for VeilBreakers dark fantasy environments.

Provides spline-based terrain deformation, non-destructive terrain layers,
brush-based erosion painting, D8 flow map computation, enhanced thermal
erosion, terrain stamp/feature placement, and object-to-terrain snapping.

Pure-logic functions (no bpy dependency) are separated for testability.
Handler functions that mutate Blender scenes import bpy only at call time.

Gap coverage: #44 (spline deform), #45 (terrain layers), #46 (erosion paint),
#75 (flow map), #48 (thermal erosion), #28/GAP-10 (terrain stamp),
#30/GAP-12 (snap to terrain).
"""

from __future__ import annotations

import json
import math
import random as _random
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]


# ---------------------------------------------------------------------------
# Cubic Bezier spline utilities (pure logic)
# ---------------------------------------------------------------------------

def _cubic_bezier_point(
    p0: Vec3, p1: Vec3, p2: Vec3, p3: Vec3, t: float,
) -> Vec3:
    """Evaluate a cubic Bezier curve at parameter t in [0, 1].

    Args:
        p0, p1, p2, p3: Control points (start, ctrl1, ctrl2, end).
        t: Parameter along curve, 0.0 = p0, 1.0 = p3.

    Returns:
        Interpolated (x, y, z) position on the curve.
    """
    u = 1.0 - t
    uu = u * u
    uuu = uu * u
    tt = t * t
    ttt = tt * t

    x = uuu * p0[0] + 3.0 * uu * t * p1[0] + 3.0 * u * tt * p2[0] + ttt * p3[0]
    y = uuu * p0[1] + 3.0 * uu * t * p1[1] + 3.0 * u * tt * p2[1] + ttt * p3[1]
    z = uuu * p0[2] + 3.0 * uu * t * p1[2] + 3.0 * u * tt * p2[2] + ttt * p3[2]
    return (x, y, z)


def _auto_control_points(
    points: list[Vec3],
    tension: float = 0.5,
) -> list[tuple[Vec3, Vec3, Vec3, Vec3]]:
    """Generate cubic Bezier segments from a list of waypoints.

    Uses Catmull-Rom-style tangent estimation to compute control points
    that produce a smooth curve through the waypoints.

    Args:
        points: Ordered waypoints (at least 2).
        tension: Controls tightness of the curve (0=loose, 1=tight).

    Returns:
        List of (p0, ctrl1, ctrl2, p1) tuples for each Bezier segment.
    """
    if len(points) < 2:
        return []

    segments: list[tuple[Vec3, Vec3, Vec3, Vec3]] = []
    n = len(points)

    for i in range(n - 1):
        p0 = points[i]
        p3 = points[i + 1]

        # Compute tangent at p0
        if i > 0:
            tan0 = tuple(
                (1.0 - tension) * (points[i + 1][k] - points[i - 1][k]) / 2.0
                for k in range(3)
            )
        else:
            tan0 = tuple(
                (1.0 - tension) * (points[i + 1][k] - points[i][k])
                for k in range(3)
            )

        # Compute tangent at p3
        if i + 2 < n:
            tan1 = tuple(
                (1.0 - tension) * (points[i + 2][k] - points[i][k]) / 2.0
                for k in range(3)
            )
        else:
            tan1 = tuple(
                (1.0 - tension) * (points[i + 1][k] - points[i][k])
                for k in range(3)
            )

        ctrl1 = tuple(p0[k] + tan0[k] / 3.0 for k in range(3))
        ctrl2 = tuple(p3[k] - tan1[k] / 3.0 for k in range(3))

        segments.append((p0, ctrl1, ctrl2, p3))  # type: ignore[arg-type]

    return segments


def evaluate_spline(
    spline_points: list[Vec3],
    samples_per_segment: int = 32,
    tension: float = 0.5,
) -> list[Vec3]:
    """Evaluate a smooth spline through the given control points.

    Args:
        spline_points: Ordered waypoints (at least 2).
        samples_per_segment: Number of evaluation points per Bezier segment.
        tension: Curve tightness (0=loose, 1=tight).

    Returns:
        List of (x, y, z) positions along the spline.
    """
    if len(spline_points) < 2:
        return list(spline_points)

    segments = _auto_control_points(spline_points, tension)
    result: list[Vec3] = []

    for seg_idx, (p0, p1, p2, p3) in enumerate(segments):
        n_samples = samples_per_segment if seg_idx < len(segments) - 1 else samples_per_segment + 1
        for i in range(n_samples):
            t = i / samples_per_segment
            pt = _cubic_bezier_point(p0, p1, p2, p3, t)
            result.append(pt)

    return result


def distance_point_to_polyline(
    px: float, py: float,
    polyline: list[Vec3],
) -> tuple[float, Vec3, float]:
    """Compute minimum 2D (XY) distance from point to polyline.

    Args:
        px, py: Query point in world XY.
        polyline: List of (x, y, z) points forming the polyline.

    Returns:
        (distance, closest_point, t_along_spline) where t_along_spline
        is normalized [0, 1] along the total polyline length.
    """
    if not polyline:
        return float("inf"), (px, py, 0.0), 0.0

    if len(polyline) == 1:
        sp = polyline[0]
        dx = px - sp[0]
        dy = py - sp[1]
        return math.sqrt(dx * dx + dy * dy), sp, 0.0

    best_dist = float("inf")
    best_point: Vec3 = polyline[0]
    best_t = 0.0

    # Compute cumulative segment lengths for t_along_spline
    seg_lengths: list[float] = []
    total_length = 0.0
    for i in range(len(polyline) - 1):
        a = polyline[i]
        b = polyline[i + 1]
        sl = math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)
        seg_lengths.append(sl)
        total_length += sl

    if total_length < 1e-12:
        return 0.0, polyline[0], 0.0

    cumulative = 0.0
    for i in range(len(polyline) - 1):
        ax, ay, az = polyline[i]
        bx, by, bz = polyline[i + 1]

        # Project point onto segment [a, b]
        abx = bx - ax
        aby = by - ay
        ab_len_sq = abx * abx + aby * aby

        if ab_len_sq < 1e-12:
            # Degenerate segment
            dx = px - ax
            dy = py - ay
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < best_dist:
                best_dist = dist
                best_point = (ax, ay, az)
                best_t = cumulative / total_length
            cumulative += seg_lengths[i]
            continue

        t_seg = ((px - ax) * abx + (py - ay) * aby) / ab_len_sq
        t_seg = max(0.0, min(1.0, t_seg))

        cx = ax + t_seg * abx
        cy = ay + t_seg * aby
        cz = az + t_seg * (bz - az)

        dx = px - cx
        dy = py - cy
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < best_dist:
            best_dist = dist
            best_point = (cx, cy, cz)
            best_t = (cumulative + t_seg * seg_lengths[i]) / total_length

        cumulative += seg_lengths[i]

    return best_dist, best_point, best_t


# ---------------------------------------------------------------------------
# Falloff functions
# ---------------------------------------------------------------------------

_FALLOFF_FUNCS = {
    "smooth": lambda d: 0.5 * (1.0 + math.cos(math.pi * d)) if d < 1.0 else 0.0,
    "sharp": lambda d: max(0.0, (1.0 - d) ** 2) if d < 1.0 else 0.0,
    "linear": lambda d: max(0.0, 1.0 - d) if d < 1.0 else 0.0,
    "constant": lambda d: 1.0 if d < 1.0 else 0.0,
}


def compute_falloff(distance_normalized: float, falloff_type: str = "smooth") -> float:
    """Compute falloff weight from normalized distance [0, 1].

    Args:
        distance_normalized: Distance from center divided by radius.
        falloff_type: One of 'smooth', 'sharp', 'linear', 'constant'.

    Returns:
        Weight in [0, 1].
    """
    fn = _FALLOFF_FUNCS.get(falloff_type)
    if fn is None:
        raise ValueError(
            f"Unknown falloff type: {falloff_type!r}. "
            f"Valid: {sorted(_FALLOFF_FUNCS)}"
        )
    return fn(max(0.0, min(distance_normalized, 1.5)))


# ---------------------------------------------------------------------------
# 1. Spline-based terrain deformation (pure logic)
# ---------------------------------------------------------------------------

def compute_spline_deformation(
    vert_positions: list[Vec3],
    spline_points: list[Vec3],
    width: float = 5.0,
    depth: float = 1.0,
    falloff: float = 0.5,
    mode: str = "carve",
    samples_per_segment: int = 32,
) -> dict[int, float]:
    """Compute terrain vertex Z-displacements along a spline path.

    Pure-logic function -- no Blender dependency.

    Args:
        vert_positions: List of (x, y, z) vertex positions.
        spline_points: Control points for the spline (at least 2).
        width: Half-width of the deformation corridor.
        depth: Maximum deformation depth/height.
        falloff: Edge softness (0=sharp cutoff, 1=gradual).
        mode: 'carve' | 'raise' | 'flatten' | 'smooth'.
        samples_per_segment: Spline evaluation resolution.

    Returns:
        Dict mapping vertex index to new Z value.

    Raises:
        ValueError: If mode is invalid or spline_points has fewer than 2 points.
    """
    valid_modes = ("carve", "raise", "flatten", "smooth")
    if mode not in valid_modes:
        raise ValueError(f"Unknown mode: {mode!r}. Valid: {valid_modes}")

    if len(spline_points) < 2:
        raise ValueError("spline_points must contain at least 2 points")

    if width <= 0:
        return {}

    # Evaluate spline to get dense sample polyline
    polyline = evaluate_spline(spline_points, samples_per_segment)

    # Compute spline center heights for flatten mode
    spline_heights: list[float] = []
    if mode == "flatten":
        spline_heights = [pt[2] for pt in polyline]

    result: dict[int, float] = {}
    # Clamp falloff to [0, 1]
    falloff = max(0.0, min(1.0, falloff))
    # When falloff=0, the blend zone is zero (sharp). When falloff=1,
    # the blend zone extends from the center to the edge.
    # We split width into core zone (no falloff) + blend zone.
    blend_fraction = falloff
    core_width = width * (1.0 - blend_fraction)

    # For smooth mode, collect neighbors for averaging
    neighbor_heights: list[float] = []

    for idx, (vx, vy, vz) in enumerate(vert_positions):
        dist, closest, t_spline = distance_point_to_polyline(vx, vy, polyline)

        if dist > width:
            continue

        # Compute weight based on distance from spline center
        if dist <= core_width:
            weight = 1.0
        else:
            # In the blend zone
            blend_dist = (dist - core_width) / max(width - core_width, 1e-6)
            weight = compute_falloff(blend_dist, "smooth")

        if weight <= 0:
            continue

        if mode == "carve":
            new_z = vz - depth * weight
        elif mode == "raise":
            new_z = vz + depth * weight
        elif mode == "flatten":
            # Interpolate towards the spline height at closest point
            if spline_heights:
                spline_idx = int(t_spline * (len(spline_heights) - 1))
                spline_idx = max(0, min(spline_idx, len(spline_heights) - 1))
                target_z = spline_heights[spline_idx]
            else:
                target_z = closest[2]
            new_z = vz + (target_z - vz) * weight
        elif mode == "smooth":
            # Simple smoothing: pull toward average of nearby vertices
            # For pure-logic, just flatten slightly toward spline height
            new_z = vz + (closest[2] - vz) * weight * 0.3
        else:
            continue

        result[idx] = new_z

    return result


def handle_spline_deform(params: dict) -> dict:
    """Deform terrain along a spline path for roads/rivers (GAP-44).

    Params:
        object_name: str -- Name of the terrain mesh object.
        spline_points: list of [x, y, z] -- Control points for the spline.
        width: float -- Deformation corridor width (default 5.0).
        depth: float -- How far to carve/raise (default 1.0).
        falloff: float -- Edge softness, 0=sharp, 1=gradual (default 0.5).
        mode: str -- 'carve' | 'raise' | 'flatten' | 'smooth' (default 'carve').

    Returns:
        Dict with operation details and affected vertex count.
    """
    try:
        import bmesh
        import bpy
    except ImportError as exc:
        raise RuntimeError("handle_spline_deform requires Blender") from exc

    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("'object_name' is required")

    obj = bpy.data.objects.get(object_name)
    if obj is None or obj.type != "MESH":
        raise ValueError(f"Terrain mesh not found: {object_name}")

    spline_points_raw = params.get("spline_points", [])
    if len(spline_points_raw) < 2:
        raise ValueError("At least 2 spline_points are required")

    spline_points = [tuple(p[:3]) for p in spline_points_raw]
    width = float(params.get("width", 5.0))
    depth = float(params.get("depth", 1.0))
    falloff = float(params.get("falloff", 0.5))
    mode = params.get("mode", "carve")

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()

        positions = [(v.co.x, v.co.y, v.co.z) for v in bm.verts]
        new_heights = compute_spline_deformation(
            positions, spline_points, width, depth, falloff, mode,
        )

        for idx, new_z in new_heights.items():
            bm.verts[idx].co.z = new_z

        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()

    return {
        "object_name": object_name,
        "mode": mode,
        "affected_vertices": len(new_heights),
        "spline_point_count": len(spline_points),
        "width": width,
        "depth": depth,
        "falloff": falloff,
    }


# ---------------------------------------------------------------------------
# 2. Terrain Layer System (pure logic)
# ---------------------------------------------------------------------------

class TerrainLayer:
    """Represents a single non-destructive terrain editing layer.

    Attributes:
        name: Layer name.
        heights: 2D numpy array of height offsets.
        blend_mode: How this layer combines with layers below it.
        strength: Multiplier applied to the height values.
    """

    __slots__ = ("name", "heights", "blend_mode", "strength")

    VALID_BLEND_MODES = ("ADD", "SUBTRACT", "MAX", "MIN", "MULTIPLY")

    def __init__(
        self,
        name: str,
        width: int,
        height: int,
        blend_mode: str = "ADD",
        strength: float = 1.0,
    ) -> None:
        if blend_mode not in self.VALID_BLEND_MODES:
            raise ValueError(
                f"Invalid blend_mode: {blend_mode!r}. "
                f"Valid: {self.VALID_BLEND_MODES}"
            )
        self.name = name
        self.heights = np.zeros((height, width), dtype=np.float64)
        self.blend_mode = blend_mode
        self.strength = max(0.0, min(1.0, strength))

    def to_dict(self) -> dict[str, Any]:
        """Serialize layer to a plain dict (for storage on custom props)."""
        return {
            "name": self.name,
            "blend_mode": self.blend_mode,
            "strength": self.strength,
            "shape": list(self.heights.shape),
            "data": self.heights.tolist(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TerrainLayer":
        """Deserialize layer from a plain dict."""
        shape = data["shape"]
        layer = cls(
            name=data["name"],
            width=shape[1],
            height=shape[0],
            blend_mode=data.get("blend_mode", "ADD"),
            strength=data.get("strength", 1.0),
        )
        layer.heights = np.array(data["data"], dtype=np.float64).reshape(shape)
        return layer


def apply_layer_operation(
    layer: TerrainLayer,
    operation: str,
    center: Vec2,
    radius: float,
    strength: float = 1.0,
    grid_width: int = 0,
    grid_height: int = 0,
    terrain_size: Vec2 = (100.0, 100.0),
    seed: int = 42,
) -> int:
    """Apply a brush operation to a terrain layer.

    Args:
        layer: Target terrain layer.
        operation: 'raise' | 'lower' | 'smooth' | 'noise' | 'stamp'.
        center: (x, y) world-space center of the brush.
        radius: Brush radius in world units.
        strength: Operation intensity (0-1).
        grid_width, grid_height: Layer grid dimensions (auto-detected if 0).
        terrain_size: World-space (width, depth) of the terrain.
        seed: Random seed for noise operation.

    Returns:
        Number of cells affected.
    """
    valid_ops = ("raise", "lower", "smooth", "noise", "stamp")
    if operation not in valid_ops:
        raise ValueError(f"Unknown operation: {operation!r}. Valid: {valid_ops}")

    rows, cols = layer.heights.shape
    tw, td = terrain_size

    if tw <= 0 or td <= 0:
        return 0

    # Convert world-space brush to grid-space
    cx_grid = center[0] / tw * cols
    cy_grid = center[1] / td * rows
    r_grid_x = radius / tw * cols
    r_grid_y = radius / td * rows

    affected = 0
    rng = _random.Random(seed)

    min_row = max(0, int(cy_grid - r_grid_y) - 1)
    max_row = min(rows, int(cy_grid + r_grid_y) + 2)
    min_col = max(0, int(cx_grid - r_grid_x) - 1)
    max_col = min(cols, int(cx_grid + r_grid_x) + 2)

    for r in range(min_row, max_row):
        for c in range(min_col, max_col):
            # Compute normalized distance to brush center
            dx = (c - cx_grid) / max(r_grid_x, 1e-6)
            dy = (r - cy_grid) / max(r_grid_y, 1e-6)
            dist = math.sqrt(dx * dx + dy * dy)

            if dist > 1.0:
                continue

            weight = compute_falloff(dist, "smooth") * strength

            if operation == "raise":
                layer.heights[r, c] += weight
            elif operation == "lower":
                layer.heights[r, c] -= weight
            elif operation == "smooth":
                # Average with neighbors
                neighbors = []
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            neighbors.append(layer.heights[nr, nc])
                if neighbors:
                    avg = sum(neighbors) / len(neighbors)
                    layer.heights[r, c] += (avg - layer.heights[r, c]) * weight
            elif operation == "noise":
                noise_val = rng.gauss(0.0, 0.5)
                layer.heights[r, c] += noise_val * weight
            elif operation == "stamp":
                layer.heights[r, c] = weight

            affected += 1

    return affected


def flatten_layers(
    base_heights: np.ndarray,
    layers: list[TerrainLayer],
) -> np.ndarray:
    """Merge all terrain layers into a final heightmap.

    Args:
        base_heights: 2D numpy array of base terrain heights.
        layers: Ordered list of TerrainLayer objects (applied in order).

    Returns:
        2D numpy array of final merged heights, same shape as base_heights.
    """
    result = base_heights.astype(np.float64).copy()

    for layer in layers:
        lh = layer.heights * layer.strength

        # Ensure the layer matches the base dimensions
        if lh.shape != result.shape:
            # Resize layer to match base using nearest-neighbor
            from_rows, from_cols = lh.shape
            to_rows, to_cols = result.shape
            row_indices = np.clip(
                (np.arange(to_rows) * from_rows / to_rows).astype(int),
                0, from_rows - 1,
            )
            col_indices = np.clip(
                (np.arange(to_cols) * from_cols / to_cols).astype(int),
                0, from_cols - 1,
            )
            lh = lh[np.ix_(row_indices, col_indices)]

        if layer.blend_mode == "ADD":
            result = result + lh
        elif layer.blend_mode == "SUBTRACT":
            result = result - lh
        elif layer.blend_mode == "MAX":
            result = np.maximum(result, result + lh)
        elif layer.blend_mode == "MIN":
            result = np.minimum(result, result + lh)
        elif layer.blend_mode == "MULTIPLY":
            # Multiply mode: lh values centered around 0, so 1+lh is multiplier
            result = result * (1.0 + lh)

    return result


def handle_terrain_layers(params: dict) -> dict:
    """Non-destructive layered terrain editing (GAP-45).

    Params:
        object_name: str -- Terrain mesh object name.
        action: str -- 'add_layer' | 'remove_layer' | 'modify_layer' |
                       'flatten_layers' | 'list_layers'.
        layer_name: str -- Name for the layer.
        operation: str -- For modify_layer: 'raise' | 'lower' | 'smooth' |
                         'noise' | 'stamp'.
        blend_mode: str -- 'ADD' | 'SUBTRACT' | 'MAX' | 'MIN' | 'MULTIPLY'.
        strength: float -- Layer/brush strength (0-1).
        center: [x, y] -- Brush center for modify_layer.
        radius: float -- Brush radius for modify_layer.

    Returns:
        Dict with action results.
    """
    try:
        import bmesh
        import bpy
    except ImportError as exc:
        raise RuntimeError("handle_terrain_layers requires Blender") from exc

    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("'object_name' is required")

    obj = bpy.data.objects.get(object_name)
    if obj is None or obj.type != "MESH":
        raise ValueError(f"Terrain mesh not found: {object_name}")

    action = params.get("action", "list_layers")
    valid_actions = ("add_layer", "remove_layer", "modify_layer",
                     "flatten_layers", "list_layers")
    if action not in valid_actions:
        raise ValueError(f"Unknown action: {action!r}. Valid: {valid_actions}")

    # Load existing layers from custom property
    layers_json = obj.get("terrain_layers", "[]")
    if isinstance(layers_json, str):
        layers_data = json.loads(layers_json)
    else:
        layers_data = []

    layers = [TerrainLayer.from_dict(d) for d in layers_data]

    layer_name = params.get("layer_name", "")

    if action == "add_layer":
        if not layer_name:
            raise ValueError("'layer_name' is required for add_layer")
        blend_mode = params.get("blend_mode", "ADD")
        strength = float(params.get("strength", 1.0))
        # Use terrain grid resolution (approximate from vertex count)
        mesh = obj.data
        res = max(2, int(math.sqrt(len(mesh.vertices))))
        new_layer = TerrainLayer(layer_name, res, res, blend_mode, strength)
        layers.append(new_layer)
        obj["terrain_layers"] = json.dumps([l.to_dict() for l in layers])
        return {"action": "add_layer", "layer_name": layer_name,
                "total_layers": len(layers)}

    elif action == "remove_layer":
        if not layer_name:
            raise ValueError("'layer_name' is required for remove_layer")
        layers = [l for l in layers if l.name != layer_name]
        obj["terrain_layers"] = json.dumps([l.to_dict() for l in layers])
        return {"action": "remove_layer", "layer_name": layer_name,
                "total_layers": len(layers)}

    elif action == "modify_layer":
        if not layer_name:
            raise ValueError("'layer_name' is required for modify_layer")
        target = None
        for l in layers:
            if l.name == layer_name:
                target = l
                break
        if target is None:
            raise ValueError(f"Layer not found: {layer_name}")

        operation = params.get("operation", "raise")
        center = params.get("center", [50.0, 50.0])
        radius = float(params.get("radius", 10.0))
        strength = float(params.get("strength", 1.0))
        dims = obj.dimensions
        terrain_size = (dims.x, dims.y)

        affected = apply_layer_operation(
            target, operation, tuple(center[:2]), radius, strength,
            terrain_size=terrain_size,
            seed=params.get("seed", 42),
        )

        obj["terrain_layers"] = json.dumps([l.to_dict() for l in layers])
        return {"action": "modify_layer", "layer_name": layer_name,
                "operation": operation, "affected_cells": affected}

    elif action == "flatten_layers":
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()

            # Build base heightmap from current mesh
            res = max(2, int(math.sqrt(len(bm.verts))))
            base = np.array([v.co.z for v in bm.verts]).reshape(res, -1)

            merged = flatten_layers(base, layers)
            flat = merged.ravel()

            for i, v in enumerate(bm.verts):
                if i < len(flat):
                    v.co.z = float(flat[i])

            bm.to_mesh(obj.data)
            obj.data.update()
        finally:
            bm.free()

        return {"action": "flatten_layers", "layers_merged": len(layers)}

    elif action == "list_layers":
        return {
            "action": "list_layers",
            "layers": [
                {"name": l.name, "blend_mode": l.blend_mode,
                 "strength": l.strength, "shape": list(l.heights.shape)}
                for l in layers
            ],
            "total_layers": len(layers),
        }

    return {"action": action, "status": "no-op"}


# ---------------------------------------------------------------------------
# 3. Erosion Painting (pure logic core)
# ---------------------------------------------------------------------------

def compute_erosion_brush(
    heightmap: np.ndarray,
    brush_center: Vec2,
    brush_radius: float,
    erosion_type: str = "hydraulic",
    iterations: int = 5,
    strength: float = 0.5,
    terrain_size: Vec2 = (100.0, 100.0),
    seed: int = 42,
) -> np.ndarray:
    """Apply erosion within a brush radius on a heightmap.

    Pure-logic function -- no Blender dependency.

    Args:
        heightmap: 2D numpy heightmap.
        brush_center: (x, y) world-space brush center.
        brush_radius: Brush radius in world units.
        erosion_type: 'hydraulic' | 'thermal' | 'wind'.
        iterations: Number of erosion passes within the brush.
        strength: Erosion intensity (0-1).
        terrain_size: World-space (width, depth) of the terrain.
        seed: Random seed.

    Returns:
        Modified heightmap (copy).
    """
    valid_types = ("hydraulic", "thermal", "wind")
    if erosion_type not in valid_types:
        raise ValueError(
            f"Unknown erosion_type: {erosion_type!r}. Valid: {valid_types}"
        )

    result = heightmap.astype(np.float64).copy()
    rows, cols = result.shape
    tw, td = terrain_size

    if tw <= 0 or td <= 0 or brush_radius <= 0:
        return result

    # Convert to grid space
    cx = brush_center[0] / tw * cols
    cy = brush_center[1] / td * rows
    rx = brush_radius / tw * cols
    ry = brush_radius / td * rows

    min_r = max(1, int(cy - ry) - 1)
    max_r = min(rows - 1, int(cy + ry) + 2)
    min_c = max(1, int(cx - rx) - 1)
    max_c = min(cols - 1, int(cx + rx) + 2)

    rng = _random.Random(seed)

    for _it in range(iterations):
        delta = np.zeros_like(result)

        for r in range(min_r, max_r):
            for c in range(min_c, max_c):
                dx = (c - cx) / max(rx, 1e-6)
                dy = (r - cy) / max(ry, 1e-6)
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 1.0:
                    continue

                brush_weight = compute_falloff(dist, "smooth") * strength

                if erosion_type == "hydraulic":
                    # Simplified hydraulic: material moves downhill
                    h = result[r, c]
                    for dr, dc_off in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = r + dr, c + dc_off
                        if 0 <= nr < rows and 0 <= nc < cols:
                            diff = h - result[nr, nc]
                            if diff > 0:
                                transfer = diff * 0.1 * brush_weight
                                delta[r, c] -= transfer
                                delta[nr, nc] += transfer

                elif erosion_type == "thermal":
                    # Thermal: excess slope material slides down
                    h = result[r, c]
                    talus = 0.05 / max(brush_weight, 0.01)
                    for dr, dc_off in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = r + dr, c + dc_off
                        if 0 <= nr < rows and 0 <= nc < cols:
                            diff = h - result[nr, nc]
                            if diff > talus:
                                transfer = (diff - talus) * 0.3 * brush_weight
                                delta[r, c] -= transfer
                                delta[nr, nc] += transfer

                elif erosion_type == "wind":
                    # Wind erosion: noise-based directional erosion
                    noise = rng.gauss(0.0, 0.3)
                    delta[r, c] -= abs(noise) * brush_weight * 0.05
                    # Deposit downwind (positive X direction)
                    deposit_c = min(c + 1, cols - 1)
                    delta[r, deposit_c] += abs(noise) * brush_weight * 0.03

        result += delta

    return np.clip(result, 0.0, 1.0)


def handle_erosion_paint(params: dict) -> dict:
    """Brush-based erosion at specific coordinates (GAP-46).

    Params:
        object_name: str -- Terrain mesh object name.
        brush_center: [x, y] -- World coords on terrain.
        brush_radius: float -- Brush radius.
        erosion_type: str -- 'hydraulic' | 'thermal' | 'wind'.
        iterations: int -- Number of erosion passes (default 5).
        strength: float -- Erosion strength (default 0.5).

    Returns:
        Dict with operation details.
    """
    try:
        import bmesh
        import bpy
    except ImportError as exc:
        raise RuntimeError("handle_erosion_paint requires Blender") from exc

    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("'object_name' is required")

    obj = bpy.data.objects.get(object_name)
    if obj is None or obj.type != "MESH":
        raise ValueError(f"Terrain mesh not found: {object_name}")

    brush_center = tuple(params.get("brush_center", [50.0, 50.0])[:2])
    brush_radius = float(params.get("brush_radius", 10.0))
    erosion_type = params.get("erosion_type", "hydraulic")
    iterations = int(params.get("iterations", 5))
    strength = float(params.get("strength", 0.5))

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()

        res = max(2, int(math.sqrt(len(bm.verts))))
        heightmap = np.array([v.co.z for v in bm.verts]).reshape(res, -1)

        dims = obj.dimensions
        terrain_size = (dims.x, dims.y)

        eroded = compute_erosion_brush(
            heightmap, brush_center, brush_radius, erosion_type,
            iterations, strength, terrain_size,
        )

        flat = eroded.ravel()
        for i, v in enumerate(bm.verts):
            if i < len(flat):
                v.co.z = float(flat[i])

        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()

    return {
        "object_name": object_name,
        "erosion_type": erosion_type,
        "brush_center": list(brush_center),
        "brush_radius": brush_radius,
        "iterations": iterations,
        "strength": strength,
    }


# ---------------------------------------------------------------------------
# 4. Flow Map Computation (pure logic, no bpy)
# ---------------------------------------------------------------------------

# D8 direction offsets: 8 neighbors (N, NE, E, SE, S, SW, W, NW)
_D8_OFFSETS = [
    (-1, 0), (-1, 1), (0, 1), (1, 1),
    (1, 0), (1, -1), (0, -1), (-1, -1),
]
_D8_DISTANCES = [
    1.0, math.sqrt(2.0), 1.0, math.sqrt(2.0),
    1.0, math.sqrt(2.0), 1.0, math.sqrt(2.0),
]


def compute_flow_map(
    heightmap: list[list[float]] | np.ndarray,
    resolution: int | None = None,
) -> dict[str, Any]:
    """Compute water flow direction from heightmap using D8 algorithm.

    Pure-logic function -- no bpy needed.

    Args:
        heightmap: 2D array of height values (list of lists or numpy array).
        resolution: Unused, kept for API compatibility.

    Returns:
        Dict with:
          flow_direction: 2D array of direction indices (0-7 for 8 neighbors,
                         -1 for pits/flat).
          flow_accumulation: 2D array of accumulated flow (higher = more
                           upstream area draining through this cell).
          drainage_basins: 2D array of basin IDs (cells draining to same pit
                         share a basin ID).
    """
    hmap = np.asarray(heightmap, dtype=np.float64)
    rows, cols = hmap.shape

    # --- Step 1: Compute flow direction (D8 steepest descent) ---
    flow_dir = np.full((rows, cols), -1, dtype=np.int32)

    for r in range(rows):
        for c in range(cols):
            max_slope = 0.0
            best_dir = -1

            for d_idx, (dr, dc) in enumerate(_D8_OFFSETS):
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    slope = (hmap[r, c] - hmap[nr, nc]) / _D8_DISTANCES[d_idx]
                    if slope > max_slope:
                        max_slope = slope
                        best_dir = d_idx

            flow_dir[r, c] = best_dir

    # --- Step 2: Compute flow accumulation ---
    # Each cell accumulates flow from all cells that drain into it.
    flow_acc = np.ones((rows, cols), dtype=np.float64)

    # Sort cells by height (highest first) for top-down accumulation
    flat_indices = np.argsort(-hmap.ravel())

    for flat_idx in flat_indices:
        r = flat_idx // cols
        c = flat_idx % cols

        d = flow_dir[r, c]
        if d < 0:
            continue

        dr, dc = _D8_OFFSETS[d]
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            flow_acc[nr, nc] += flow_acc[r, c]

    # --- Step 3: Compute drainage basins ---
    # Trace each cell downstream to its terminal pit; assign basin IDs.
    basins = np.full((rows, cols), -1, dtype=np.int32)
    basin_id = 0

    for r in range(rows):
        for c in range(cols):
            if basins[r, c] >= 0:
                continue

            # Trace downstream
            path: list[tuple[int, int]] = []
            cr, cc = r, c
            visited_set: set[tuple[int, int]] = set()

            while True:
                if (cr, cc) in visited_set:
                    break
                visited_set.add((cr, cc))
                path.append((cr, cc))

                if basins[cr, cc] >= 0:
                    # Hit an already-assigned cell
                    assigned_id = basins[cr, cc]
                    for pr, pc in path:
                        basins[pr, pc] = assigned_id
                    break

                d = flow_dir[cr, cc]
                if d < 0:
                    # Terminal pit: assign new basin
                    for pr, pc in path:
                        basins[pr, pc] = basin_id
                    basin_id += 1
                    break

                dr, dc = _D8_OFFSETS[d]
                nr, nc = cr + dr, cc + dc
                if not (0 <= nr < rows and 0 <= nc < cols):
                    # Edge of map: assign new basin
                    for pr, pc in path:
                        basins[pr, pc] = basin_id
                    basin_id += 1
                    break

                cr, cc = nr, nc

    return {
        "flow_direction": flow_dir.tolist(),
        "flow_accumulation": flow_acc.tolist(),
        "drainage_basins": basins.tolist(),
        "num_basins": basin_id,
        "max_accumulation": float(flow_acc.max()),
        "resolution": (rows, cols),
    }


# ---------------------------------------------------------------------------
# 5. Thermal Erosion (enhanced pure-logic)
# ---------------------------------------------------------------------------

def apply_thermal_erosion(
    heightmap: list[list[float]] | np.ndarray,
    iterations: int = 50,
    talus_angle: float = 0.5,
    strength: float = 0.3,
) -> list[list[float]]:
    """Thermal erosion -- material slumps from steep slopes to flat areas.

    Distinct from hydraulic (water-based). Simulates rockfall and scree slopes.
    Pure-logic function.

    Args:
        heightmap: 2D array of height values.
        iterations: Number of erosion passes (default 50).
        talus_angle: Maximum stable height difference (tangent of angle).
                    Lower = more erosion. Default 0.5.
        strength: Fraction of excess material transferred per iteration (0-1).
                 Default 0.3.

    Returns:
        2D list of eroded height values (same dimensions as input).
    """
    hmap = np.asarray(heightmap, dtype=np.float64).copy()
    rows, cols = hmap.shape

    if rows < 2 or cols < 2:
        return hmap.tolist()

    # 4-connected neighbor offsets with distances
    offsets = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0)]

    for _it in range(iterations):
        delta = np.zeros_like(hmap)

        for r in range(1, rows - 1):
            for c in range(1, cols - 1):
                h = hmap[r, c]
                max_diff = 0.0
                total_diff = 0.0
                diffs: list[tuple[int, int, float]] = []

                for dr, dc, dist in offsets:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        h_diff = (h - hmap[nr, nc]) / dist
                        if h_diff > talus_angle:
                            excess = h_diff - talus_angle
                            diffs.append((nr, nc, excess))
                            total_diff += excess
                            if excess > max_diff:
                                max_diff = excess

                if total_diff > 0 and max_diff > 0:
                    transfer = max_diff * strength * 0.5
                    for nr, nc, d in diffs:
                        fraction = d / total_diff
                        amount = transfer * fraction
                        delta[r, c] -= amount
                        delta[nr, nc] += amount

        hmap += delta

    return hmap.tolist()


# ---------------------------------------------------------------------------
# 6. Terrain Stamp / Feature Placement (pure logic + handler)
# ---------------------------------------------------------------------------

# Stamp shape generators
_STAMP_SHAPES = {
    "crater": lambda r_norm: max(0.0, 1.0 - abs(r_norm * 2.0 - 1.0)),
    "mesa": lambda r_norm: 1.0 if r_norm < 0.6 else max(0.0, 1.0 - (r_norm - 0.6) / 0.4),
    "hill": lambda r_norm: max(0.0, math.cos(r_norm * math.pi / 2.0)),
    "valley": lambda r_norm: -max(0.0, math.cos(r_norm * math.pi / 2.0)),
    "plateau": lambda r_norm: 1.0 if r_norm < 0.7 else max(0.0, 1.0 - (r_norm - 0.7) / 0.3),
    "ridge": lambda r_norm: max(0.0, 1.0 - abs(r_norm - 0.5) * 2.0),
}


def compute_stamp_heightmap(
    stamp_type: str,
    resolution: int = 64,
    custom_heightmap: list[list[float]] | None = None,
) -> np.ndarray:
    """Generate a 2D stamp heightmap for a given stamp type.

    Pure-logic function.

    Args:
        stamp_type: 'crater' | 'mesa' | 'hill' | 'valley' | 'plateau' |
                   'ridge' | 'custom'.
        resolution: Output heightmap resolution.
        custom_heightmap: Used when stamp_type is 'custom'.

    Returns:
        2D numpy array of shape (resolution, resolution) with values in [0, 1]
        (or [-1, 0] for valley).
    """
    if stamp_type == "custom":
        if custom_heightmap is not None:
            return np.asarray(custom_heightmap, dtype=np.float64)
        return np.zeros((resolution, resolution), dtype=np.float64)

    if stamp_type not in _STAMP_SHAPES:
        raise ValueError(
            f"Unknown stamp_type: {stamp_type!r}. "
            f"Valid: {sorted(list(_STAMP_SHAPES.keys()) + ['custom'])}"
        )

    shape_fn = _STAMP_SHAPES[stamp_type]
    stamp = np.zeros((resolution, resolution), dtype=np.float64)
    center = resolution / 2.0

    for r in range(resolution):
        for c in range(resolution):
            dx = (c - center) / center
            dy = (r - center) / center
            dist = math.sqrt(dx * dx + dy * dy)
            if dist <= 1.0:
                stamp[r, c] = shape_fn(dist)

    return stamp


def apply_stamp_to_heightmap(
    heightmap: np.ndarray,
    stamp: np.ndarray,
    position: Vec2,
    radius: float,
    height: float = 1.0,
    falloff: float = 0.5,
    terrain_size: Vec2 = (100.0, 100.0),
) -> np.ndarray:
    """Apply a stamp heightmap onto a terrain heightmap.

    Pure-logic function.

    Args:
        heightmap: 2D terrain heightmap.
        stamp: 2D stamp heightmap (values typically in [0, 1]).
        position: (x, y) world-space position to place the stamp center.
        radius: World-space radius of the stamp.
        height: Height multiplier for the stamp values.
        falloff: Edge softness (0=sharp, 1=gradual).
        terrain_size: (width, depth) of the terrain in world units.

    Returns:
        Modified heightmap (copy).
    """
    result = heightmap.astype(np.float64).copy()
    rows, cols = result.shape
    stamp_rows, stamp_cols = stamp.shape
    tw, td = terrain_size

    if tw <= 0 or td <= 0 or radius <= 0:
        return result

    # Convert world-space to grid-space
    cx = position[0] / tw * cols
    cy = position[1] / td * rows
    r_cells_x = radius / tw * cols
    r_cells_y = radius / td * rows

    min_r = max(0, int(cy - r_cells_y) - 1)
    max_r = min(rows, int(cy + r_cells_y) + 2)
    min_c = max(0, int(cx - r_cells_x) - 1)
    max_c = min(cols, int(cx + r_cells_x) + 2)

    for r in range(min_r, max_r):
        for c in range(min_c, max_c):
            # Normalized position relative to stamp center [-1, 1]
            nx = (c - cx) / max(r_cells_x, 1e-6)
            ny = (r - cy) / max(r_cells_y, 1e-6)
            dist = math.sqrt(nx * nx + ny * ny)

            if dist > 1.0:
                continue

            # Sample the stamp
            su = (nx + 1.0) * 0.5  # Map [-1,1] to [0,1]
            sv = (ny + 1.0) * 0.5
            si = max(0, min(int(sv * (stamp_rows - 1) + 0.5), stamp_rows - 1))
            sj = max(0, min(int(su * (stamp_cols - 1) + 0.5), stamp_cols - 1))
            stamp_val = stamp[si, sj]

            # Apply falloff at edges
            edge_falloff = compute_falloff(dist, "smooth") if falloff > 0 else 1.0
            blend = edge_falloff * (1.0 - falloff) + edge_falloff * falloff

            result[r, c] += stamp_val * height * blend

    return result


def handle_terrain_stamp(params: dict) -> dict:
    """Stamp features onto existing terrain (GAP-28/GAP-10).

    Params:
        object_name: str -- Terrain mesh object name.
        stamp_type: str -- 'crater' | 'mesa' | 'hill' | 'valley' | 'plateau' |
                          'ridge' | 'custom'.
        position: [x, y] -- World coords for stamp center.
        radius: float -- Stamp radius.
        height: float -- Stamp height multiplier.
        falloff: float -- Edge softness (0-1).
        custom_heightmap: list[list[float]] -- For 'custom' stamp type.

    Returns:
        Dict with operation details.
    """
    try:
        import bmesh
        import bpy
    except ImportError as exc:
        raise RuntimeError("handle_terrain_stamp requires Blender") from exc

    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("'object_name' is required")

    obj = bpy.data.objects.get(object_name)
    if obj is None or obj.type != "MESH":
        raise ValueError(f"Terrain mesh not found: {object_name}")

    stamp_type = params.get("stamp_type", "hill")
    position = tuple(params.get("position", [50.0, 50.0])[:2])
    radius = float(params.get("radius", 10.0))
    height = float(params.get("height", 1.0))
    falloff = float(params.get("falloff", 0.5))
    custom_heightmap = params.get("custom_heightmap")

    stamp = compute_stamp_heightmap(stamp_type, 64, custom_heightmap)

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()

        res = max(2, int(math.sqrt(len(bm.verts))))
        heightmap = np.array([v.co.z for v in bm.verts]).reshape(res, -1)

        dims = obj.dimensions
        terrain_size = (dims.x, dims.y)

        stamped = apply_stamp_to_heightmap(
            heightmap, stamp, position, radius, height, falloff, terrain_size,
        )

        flat = stamped.ravel()
        for i, v in enumerate(bm.verts):
            if i < len(flat):
                v.co.z = float(flat[i])

        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()

    return {
        "object_name": object_name,
        "stamp_type": stamp_type,
        "position": list(position),
        "radius": radius,
        "height": height,
        "falloff": falloff,
    }


# ---------------------------------------------------------------------------
# 7. Object-to-Terrain Snapping (handler only)
# ---------------------------------------------------------------------------

def handle_snap_to_terrain(params: dict) -> dict:
    """Snap objects to terrain surface via raycast (GAP-30/GAP-12).

    Params:
        object_names: list[str] -- Objects to snap.
        terrain_name: str -- Terrain object name.
        align_to_normal: bool -- Rotate to match terrain slope (default True).
        offset: float -- Vertical offset above terrain (default 0.0).

    Returns:
        Dict with snapping results per object.
    """
    try:
        import bpy
        from mathutils import Vector
    except ImportError as exc:
        raise RuntimeError("handle_snap_to_terrain requires Blender") from exc

    object_names = params.get("object_names", [])
    terrain_name = params.get("terrain_name")
    align_to_normal = params.get("align_to_normal", True)
    offset = float(params.get("offset", 0.0))

    if not terrain_name:
        raise ValueError("'terrain_name' is required")
    if not object_names:
        raise ValueError("'object_names' must be a non-empty list")

    terrain = bpy.data.objects.get(terrain_name)
    if terrain is None:
        raise ValueError(f"Terrain object not found: {terrain_name}")

    # Ensure terrain mesh is up to date for raycasting
    depsgraph = bpy.context.evaluated_depsgraph_get()

    results: list[dict[str, Any]] = []

    for obj_name in object_names:
        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            results.append({"name": obj_name, "snapped": False,
                            "error": "Object not found"})
            continue

        # Cast ray from above the object straight down
        origin = Vector((obj.location.x, obj.location.y,
                         terrain.location.z + terrain.dimensions.z + 100.0))
        direction = Vector((0.0, 0.0, -1.0))

        success, location, normal, _face_idx = terrain.ray_cast(
            terrain.matrix_world.inverted() @ origin,
            terrain.matrix_world.inverted().to_3x3() @ direction,
        )

        if success:
            # Transform hit back to world space
            world_hit = terrain.matrix_world @ location
            world_normal = (terrain.matrix_world.to_3x3() @ normal).normalized()

            obj.location.x = world_hit.x
            obj.location.y = world_hit.y
            obj.location.z = world_hit.z + offset

            if align_to_normal:
                # Align object Z-axis to terrain normal
                up = Vector((0, 0, 1))
                rot_axis = up.cross(world_normal)
                if rot_axis.length > 1e-6:
                    rot_angle = up.angle(world_normal)
                    rot_axis.normalize()
                    from mathutils import Matrix
                    rot_mat = Matrix.Rotation(rot_angle, 4, rot_axis)
                    obj.rotation_euler = rot_mat.to_euler()

            results.append({
                "name": obj_name,
                "snapped": True,
                "position": [world_hit.x, world_hit.y, world_hit.z + offset],
                "normal": [world_normal.x, world_normal.y, world_normal.z],
            })
        else:
            results.append({"name": obj_name, "snapped": False,
                            "error": "Raycast missed terrain"})

    return {
        "terrain_name": terrain_name,
        "snapped_count": sum(1 for r in results if r.get("snapped")),
        "total_objects": len(object_names),
        "results": results,
    }
