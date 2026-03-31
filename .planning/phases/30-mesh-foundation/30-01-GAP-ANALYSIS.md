# Phase 30: Mesh Foundation — Gap Analysis (v2)

**Date:** 2026-03-31 (revised from 2026-03-30 v1)
**Plan Reference:** 30-01-PLAN.md, 30-RESEARCH.md
**Revision Reason:** v1 had incorrect generator count (284 vs actual 267), misclassified existing generators as missing, used wrong function name prefix (gen_* vs generate_*)

---

## Executive Summary

**Finding:** `procedural_meshes.py` contains **267** `generate_*` functions across 21 categories. The visual quality problem is NOT that generators use primitive helpers — composition from primitives is a valid construction method. The problem is that the **final output** lacks sufficient vertex density, edge flow, surface detail, and proper material assignment to look AAA.

**Scale:**
- Total generators: 267 functions (verified by `grep -c "def generate_" procedural_meshes.py`)
- Quality rating INTERMEDIATE or better: ~30% (barrel, rock, pillar, some weapons)
- Quality rating BASIC (need visual upgrade): ~60%
- Quality rating PRIMITIVE (need major rework): ~10%

**Note:** Previous gap analysis v1 cited "127+" (from v3.0 era docs) and "284" (overcounting). Both numbers were wrong. The actual count is 267.

---

## Quality Assessment by Category

### Tier 1: INTERMEDIATE+ (Acceptable with Minor Polish)

| Generator | Why It Works | Action |
|---|---|---|
| `generate_barrel_mesh` | `_make_lathe` with sinusoidal bulge, proper stave count | Add edge loops, assign wood material |
| `generate_rock_mesh` (boulder) | `_make_faceted_rock_shell` with noise displacement | Assign stone procedural material |
| `generate_pillar_mesh` (round) | Lathe with entasis, proper base/capital profiles | Assign stone material |
| `generate_greatsword_mesh` | Custom quad strip blade with taper | Add edge bevel, assign metal material |

### Tier 2: BASIC (Need Edge Loops + Material)

| Generator | Issue | Fix |
|---|---|---|
| `generate_table_mesh` | Beveled boxes, no wood plank lines | Add edge loops on tabletop edges, assign rough_timber material |
| `generate_chair_mesh` | Beveled boxes, sphere finials | Add edge loops, assign polished_wood material |
| `generate_chest_mesh` | Decent lid (half-cylinder), but flat iron bands | Add bevel to bands, assign iron_clad + aged_wood materials |
| `generate_door_mesh` | Flat plank lines, cylinder hinges | Add edge loops on plank edges, assign rough_timber material |
| `generate_tree_mesh` | Trunk lathe OK, **canopy is sphere clusters** | **Replace canopy with L-system branching** — highest visual impact fix |
| `generate_bookshelf_mesh` | EXISTS (not missing as v1 claimed), has individual book geometry | Assign wood material, add edge loops |
| `generate_crate_mesh` | EXISTS (not missing as v1 claimed) | Assign aged_wood material, add slat detail |
| `generate_bed_mesh` | Frame + mattress assembly | Assign fabric + wood materials |

### Tier 3: PRIMITIVE (Need Significant Rework)

| Generator | Issue | Required Fix |
|---|---|---|
| Building grammar details | ALL detail ops are 0.5m cubes (gargoyles, buttresses, spires) | Wire `building_quality.py` generators (stone blocks, arches, shingles) into grammar |
| `_ops_to_mesh` (worldbuilding) | Every dungeon/cave/town element is a cube | Replace cube grid with profile extrusion |
| `generate_rock_mesh` (rubble) | Random beveled boxes scattered | Use noise-displaced icosphere fragments |

---

## Misclassifications Fixed from v1

| Item | v1 Claim | Actual Status |
|---|---|---|
| Bookshelf generator | "MISSING" | EXISTS at `generate_bookshelf_mesh` (line ~1320), has individual book geometry |
| Crate generator | "MISSING" | EXISTS at `generate_crate_mesh` (line ~9266) |
| Barrel rack | "MISSING" | Low priority, not critical for Phase 30 |
| Function names | Used `gen_*` prefix | Actual prefix is `generate_*_mesh` |
| Generator count | "284 functions" | 267 `generate_*` functions |

---

## Existing Infrastructure (DO NOT Recreate)

| System | File | Status | Phase 30 Action |
|---|---|---|---|
| LOD presets (7 tiers) | `lod_pipeline.py` | Complete | ADD `furniture` preset only |
| Silhouette preservation | `lod_pipeline.py` | `compute_silhouette_importance()` exists | EXTEND threshold validation |
| Procedural materials (45+) | `procedural_materials.py` | AAA quality node trees | WIRE as default (currently opt-in) |
| Smart materials (22) | `texture_quality.py` | 5-layer architecture | FIX roughness (uses scalar, needs noise nodes) |
| Material tiers (25) | `material_tiers.py` | RPG equipment progression | No change needed |
| Terrain biome palettes (14) | `terrain_materials.py` | Splatmap blending | No change needed |
| Mesh bridge | `_mesh_bridge.py` | Generator mapping tables | EXTEND with material mapping |

---

## Acceptance Criteria (Corrected from v1)

The v1 "no primitives" rule is WRONG. Using `_make_beveled_box()` to construct a table is fine — Houdini's procedural buildings do the same with box primitives.

**Correct acceptance criteria for Phase 30:**
1. **Output quality** — Contact sheet of generated mesh shows AAA-grade silhouette at 4 viewing angles
2. **Vertex density** — Furniture >500 verts, buildings >2000, vegetation >300
3. **Topology** — Zero non-manifold edges, consistent normals, UV coverage >0.8
4. **Material** — Every generated mesh has a procedural material assigned (not flat color)
5. **Determinism** — Same seed produces identical MeshSpec across runs
6. **LOD** — Each asset type has LOD chain with >85% silhouette preservation
7. **Budget** — Scene validator enforces per-room (50K-150K) and per-block (200K-500K) limits

---

## Priority Actions (Revised)

1. **Wire procedural materials as default** — Immediate visual improvement, low effort
2. **Add edge loops + bevel to key generators** — `bmesh.ops.bevel`, `bmesh.ops.subdivide_edges` after assembly
3. **Replace tree canopy sphere clusters** — L-system branching with leaf cards
4. **Enforce seed-based RNG** — Audit all 267 generators
5. **Add furniture LOD preset** — Add to existing LOD_PRESETS dict
6. **Implement scene budget validator** — New feature
7. **Implement boolean cleanup pipeline** — New feature

---

*Revised 2026-03-31 — corrected generator count (267), fixed misclassifications, replaced "no primitives" gate with output quality metrics*
