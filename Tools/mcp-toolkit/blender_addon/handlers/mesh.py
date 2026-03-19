"""Mesh topology analysis, auto-repair, and game-readiness check handlers.

Provides:
- handle_analyze_topology: Full topology analysis with A-F grading (MESH-01)
- handle_auto_repair: Chained repair pipeline via bmesh.ops (MESH-02)
- handle_check_game_ready: Composite game-readiness validation (MESH-08)

All analysis uses bmesh for direct geometry access without operator context issues.
"""

from __future__ import annotations

import math
import re

import bmesh
import bpy


# ---------------------------------------------------------------------------
# Pure-logic helpers (testable without Blender)
# ---------------------------------------------------------------------------

# Default Blender object names that indicate the asset hasn't been renamed.
_DEFAULT_NAME_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^Cube(\.\d+)?$"),
    re.compile(r"^Sphere(\.\d+)?$"),
    re.compile(r"^Cylinder(\.\d+)?$"),
    re.compile(r"^Plane(\.\d+)?$"),
    re.compile(r"^Cone(\.\d+)?$"),
    re.compile(r"^Torus(\.\d+)?$"),
    re.compile(r"^Circle(\.\d+)?$"),
    re.compile(r"^Icosphere(\.\d+)?$"),
    re.compile(r"^Monkey(\.\d+)?$"),
    re.compile(r"^Grid(\.\d+)?$"),
]

# Transform tolerance for "applied" check.
_LOC_TOLERANCE = 0.001
_ROT_TOLERANCE = 0.001
_SCALE_TOLERANCE = 0.01


def _compute_grade(metrics: dict) -> str:
    """Compute A-F topology grade from analysis metrics.

    Grading thresholds from 02-RESEARCH.md (worst-first evaluation):
      F: nm>20 or ngon%>25 or pole%>50 or loose>50
      E: nm>5  or ngon%>10 or pole%>30 or loose>10
      D: nm>0  or ngon%>5  or pole%>20 or loose>0 or tri%>40
      C: ngon%>2 or pole%>10 or tri%>20
      B: ngon%>0 or pole%>5  or tri%>10
      A: everything else
    """
    total_faces = max(metrics["face_count"], 1)
    total_verts = max(metrics["vertex_count"], 1)
    ngon_pct = metrics["ngon_percentage"]
    nm = metrics["non_manifold_edges"]
    pole_pct = metrics["pole_count"] / total_verts * 100
    loose = metrics["loose_vertices"] + metrics["loose_edges"]
    tri_pct = metrics["tri_count"] / total_faces * 100

    # Grade from worst to best -- first failing threshold sets grade.
    if nm > 20 or ngon_pct > 25 or pole_pct > 50 or loose > 50:
        return "F"
    if nm > 5 or ngon_pct > 10 or pole_pct > 30 or loose > 10:
        return "E"
    if nm > 0 or ngon_pct > 5 or pole_pct > 20 or loose > 0 or tri_pct > 40:
        return "D"
    if ngon_pct > 2 or pole_pct > 10 or tri_pct > 20:
        return "C"
    if ngon_pct > 0 or pole_pct > 5 or tri_pct > 10:
        return "B"
    return "A"


def _list_issues(m: dict) -> list[str]:
    """Generate human-readable issue list from topology metrics."""
    issues: list[str] = []
    if m["non_manifold_edges"] > 0:
        issues.append(
            f"{m['non_manifold_edges']} non-manifold edges "
            "(will cause rendering artifacts)"
        )
    if m["ngon_count"] > 0:
        issues.append(
            f"{m['ngon_count']} n-gons ({m['ngon_percentage']}% of faces)"
        )
    if m["loose_vertices"] > 0:
        issues.append(f"{m['loose_vertices']} loose vertices")
    if m["loose_edges"] > 0:
        issues.append(f"{m['loose_edges']} loose edges (wire geometry)")
    if m["pole_count"] > m["vertex_count"] * 0.1:
        issues.append(
            f"{m['pole_count']} poles "
            f"({m['e_poles']} E-poles, {m['n_poles']} N-poles)"
        )
    return issues


def _is_default_name(name: str) -> bool:
    """Return True if *name* matches a default Blender object name."""
    return any(pat.match(name) for pat in _DEFAULT_NAME_PATTERNS)


def _evaluate_game_readiness(
    *,
    topology_result: dict,
    object_name: str,
    poly_budget: int,
    has_uv: bool,
    has_material: bool,
    location: tuple[float, float, float],
    rotation: tuple[float, float, float],
    scale: tuple[float, float, float],
) -> dict:
    """Evaluate game-readiness from pre-computed data (testable without Blender).

    Returns structured dict with per-check pass/fail and overall game_ready bool.
    """
    grade = topology_result["grade"]
    tri_count = topology_result["tri_count"]
    quad_count = topology_result["quad_count"]
    ngon_count = topology_result["ngon_count"]

    # Estimated triangle count for the game engine (quads split, ngons fan-triangulated).
    estimated_tris = tri_count + quad_count * 2 + ngon_count * 3

    # --- Sub-checks ---
    topology_pass = grade in ("A", "B", "C")
    budget_pass = estimated_tris <= poly_budget
    uv_pass = has_uv
    material_pass = has_material
    naming_pass = not _is_default_name(object_name)

    loc_ok = all(abs(v) < _LOC_TOLERANCE for v in location)
    rot_ok = all(abs(v) < _ROT_TOLERANCE for v in rotation)
    scale_ok = all(abs(v - 1.0) < _SCALE_TOLERANCE for v in scale)
    transform_pass = loc_ok and rot_ok and scale_ok

    game_ready = all([
        topology_pass, budget_pass, uv_pass,
        material_pass, naming_pass, transform_pass,
    ])

    checks = {
        "topology": {
            "passed": topology_pass,
            "grade": grade,
            "detail": f"Grade {grade}" + ("" if topology_pass else " (need C or better)"),
        },
        "poly_budget": {
            "passed": budget_pass,
            "estimated_tris": estimated_tris,
            "budget": poly_budget,
            "detail": f"{estimated_tris:,} / {poly_budget:,} tris",
        },
        "uv": {
            "passed": uv_pass,
            "detail": "UV layer present" if uv_pass else "No UV layer found",
        },
        "materials": {
            "passed": material_pass,
            "detail": "Material assigned" if material_pass else "No material slots",
        },
        "naming": {
            "passed": naming_pass,
            "detail": object_name if naming_pass else f"'{object_name}' is a default Blender name",
        },
        "transform": {
            "passed": transform_pass,
            "detail": "Transforms applied" if transform_pass else "Unapplied transforms detected",
        },
    }

    failed = [k for k, v in checks.items() if not v["passed"]]
    if game_ready:
        summary = "All checks passed -- asset is game-ready"
    else:
        summary = f"Failed checks: {', '.join(failed)}"

    return {
        "object_name": object_name,
        "game_ready": game_ready,
        "checks": checks,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Blender handlers (require bpy + bmesh at runtime)
# ---------------------------------------------------------------------------


def _analyze_mesh(obj: object) -> dict:
    """Run full topology analysis on a Blender mesh object.

    Returns raw metrics dict (used by handle_analyze_topology and _quick_grade).
    """
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        total_verts = len(bm.verts)
        total_edges = len(bm.edges)
        total_faces = len(bm.faces)

        # Non-manifold edges
        non_manifold_edges = [e for e in bm.edges if not e.is_manifold]

        # Face type counts
        ngons = [f for f in bm.faces if len(f.verts) > 4]
        tris = [f for f in bm.faces if len(f.verts) == 3]
        quads = [f for f in bm.faces if len(f.verts) == 4]

        # Poles (non-4-valence interior vertices)
        e_poles = [v for v in bm.verts if len(v.link_edges) == 3 and not v.is_boundary]
        n_poles = [v for v in bm.verts if len(v.link_edges) >= 5 and not v.is_boundary]

        # Loose geometry
        loose_verts = [v for v in bm.verts if len(v.link_edges) == 0]
        loose_edges = [e for e in bm.edges if len(e.link_faces) == 0]

        # Boundary edges
        boundary_edges = [e for e in bm.edges if e.is_boundary]

        # Edge flow: average face angle at edges with 2 linked faces
        edge_angles: list[float] = []
        for e in bm.edges:
            if len(e.link_faces) == 2:
                angle = e.link_faces[0].normal.angle(e.link_faces[1].normal)
                edge_angles.append(math.degrees(angle))

    finally:
        bm.free()

    metrics = {
        "object_name": obj.name,
        "vertex_count": total_verts,
        "edge_count": total_edges,
        "face_count": total_faces,
        "tri_count": len(tris),
        "quad_count": len(quads),
        "ngon_count": len(ngons),
        "ngon_percentage": round(len(ngons) / max(total_faces, 1) * 100, 1),
        "non_manifold_edges": len(non_manifold_edges),
        "boundary_edges": len(boundary_edges),
        "e_poles": len(e_poles),
        "n_poles": len(n_poles),
        "pole_count": len(e_poles) + len(n_poles),
        "loose_vertices": len(loose_verts),
        "loose_edges": len(loose_edges),
        "avg_edge_angle": round(
            sum(edge_angles) / max(len(edge_angles), 1), 1
        ),
        "max_edge_angle": round(max(edge_angles) if edge_angles else 0, 1),
    }
    metrics["grade"] = _compute_grade(metrics)
    metrics["issues"] = _list_issues(metrics)
    return metrics


def _quick_grade(obj: object) -> str:
    """Return just the topology grade for an object (used after repair)."""
    return _analyze_mesh(obj)["grade"]


def handle_analyze_topology(params: dict) -> dict:
    """Full topology analysis with A-F grading (MESH-01).

    Params:
        object_name: Name of the Blender mesh object to analyze.

    Returns dict with all topology metrics, grade, and issues list.
    """
    name = params.get("object_name")
    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    return _analyze_mesh(obj)


def handle_auto_repair(params: dict) -> dict:
    """Auto-repair pipeline: chained bmesh.ops in optimal order (MESH-02).

    Params:
        object_name: Name of the Blender mesh object to repair.
        merge_distance: Distance threshold for remove_doubles (default 0.0001).
        max_hole_sides: Maximum sides for hole filling (default 8).

    Repair order (matters -- see 02-RESEARCH.md):
      1. Remove loose verts
      2. Remove loose edges
      3. Dissolve degenerate
      4. Remove doubles
      5. Recalculate normals
      6. Fill holes
    """
    name = params.get("object_name")
    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    merge_distance = params.get("merge_distance", 0.0001)
    max_hole_sides = params.get("max_hole_sides", 8)

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        report: dict = {}

        # 1. Remove loose vertices (no edges)
        loose_verts = [v for v in bm.verts if len(v.link_edges) == 0]
        if loose_verts:
            bmesh.ops.delete(bm, geom=loose_verts, context="VERTS")
            report["removed_loose_verts"] = len(loose_verts)
        else:
            report["removed_loose_verts"] = 0

        # 2. Remove loose edges (no faces)
        loose_edges = [e for e in bm.edges if len(e.link_faces) == 0]
        if loose_edges:
            bmesh.ops.delete(bm, geom=loose_edges, context="EDGES")
            report["removed_loose_edges"] = len(loose_edges)
        else:
            report["removed_loose_edges"] = 0

        # 3. Dissolve degenerate (zero-area faces, zero-length edges)
        result = bmesh.ops.dissolve_degenerate(
            bm, dist=0.0001, edges=bm.edges[:]
        )
        report["dissolved_degenerate"] = len(result.get("region", []))

        # 4. Remove doubles (merge by distance)
        result = bmesh.ops.remove_doubles(
            bm, verts=bm.verts[:], dist=merge_distance
        )
        report["merged_vertices"] = len(result.get("targetmap", {}))

        # 5. Recalculate normals (make consistent outward)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        report["normals_recalculated"] = True

        # 6. Fill holes (boundary edges)
        boundary_edges = [e for e in bm.edges if e.is_boundary]
        if boundary_edges:
            result = bmesh.ops.holes_fill(
                bm, edges=boundary_edges, sides=max_hole_sides
            )
            report["holes_filled"] = len(result.get("faces", []))
        else:
            report["holes_filled"] = 0

        # Write back to mesh
        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()

    # Re-analyze to confirm repair effectiveness
    report["post_repair_grade"] = _quick_grade(obj)
    report["object_name"] = name
    return report


def handle_check_game_ready(params: dict) -> dict:
    """Composite game-readiness validation (MESH-08).

    Params:
        object_name: Name of the Blender mesh object to check.
        poly_budget: Maximum triangle count allowed (default 50000).
        platform: Target platform -- "pc", "mobile", or "console" (default "pc").

    Checks: topology grade, poly budget, UV presence, materials, naming, transforms.
    """
    name = params.get("object_name")
    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    poly_budget = params.get("poly_budget", 50000)
    # platform is accepted for future budget presets but not used yet
    # params.get("platform", "pc")

    # Run topology analysis
    topology_result = _analyze_mesh(obj)

    # Check UV layer
    has_uv = bool(obj.data.uv_layers)

    # Check materials
    has_material = len(obj.data.materials) > 0

    # Extract transforms
    location = tuple(obj.location)
    rotation = tuple(obj.rotation_euler)
    scale = tuple(obj.scale)

    return _evaluate_game_readiness(
        topology_result=topology_result,
        object_name=obj.name,
        poly_budget=poly_budget,
        has_uv=has_uv,
        has_material=has_material,
        location=location,
        rotation=rotation,
        scale=scale,
    )
