# V6 Comprehensive Scan Results — 5 Scanners

**Date:** 2026-03-22
**Scanners:** 3 Opus Agents + Codex CLI + Gemini CLI + Python Reviewer

## Scanner Results Summary

| Scanner | Findings |
|---------|----------|
| Opus: Editability | 23 gaps (3 CRITICAL, 7 HIGH) |
| Opus: Performance | 22 optimizations (5 HIGH impact) |
| Opus: Visual Quality | 30 gaps (11 game-breaking, 16 noticeable) |
| Codex CLI | No functional regressions in diff |
| Gemini CLI | 7 geometry bugs, 3 crash edge cases, 5 visual issues, 3 performance |
| Python Reviewer | 0 CRITICAL, 0 HIGH, 2 MEDIUM (false positives) |

---

## CRITICAL: Gemini-Found Geometry Bugs (FIX IMMEDIATELY)

1. **facial_topology.py** — Nasolabial fold vertices are floating (no connecting faces)
2. **facial_topology.py** — Hand finger joints have skipped face generation (`pass`)
3. **facial_topology.py** — Foot toes are disconnected from main body
4. **monster_bodies/npc_characters** — Body parts concatenated without welding vertices
5. **mesh_smoothing.py** — Normal estimation inverted for concave crevices
6. **mesh_smoothing.py** — Z-axis noise reuses n1 instead of n3 (correlated artifacts)
7. **monster_bodies.py** — Upper arm radius is inverted (shoulder thinner than elbow)

## CRITICAL: Editability Gaps (Opus)

1. **GAP-01** — No position-based vertex/face selection (can't select "top row of faces")
2. **GAP-02** — No move/rotate/scale of selected geometry (only extrude/inset/boolean)
3. **GAP-09** — No terrain sculpting at specific coordinates (can't raise/lower terrain)

## CRITICAL: Visual Quality (Opus)

1. Characters are assembled primitives (cylinders+spheres+boxes visible)
2. Face mesh is a deformed flat grid, not sculpted from skull sphere
3. No muscle/anatomy definition on bodies
4. SSS weight too low (0.15 vs should be 1.0 with Subsurface Scale)
5. No micro-normal layering (single Bump node vs 3-layer system)
6. No procedural-to-image bake pipeline integration
7. Vegetation is primitive geometry (cone trees, cube rocks)
8. Box hands/feet (proper generators exist but NOT WIRED to NPC body!)
9. No clothing/equipment mesh generation
10. No eyeballs/eyelids/teeth geometry
11. No height-based terrain texture blending

## HIGH: Performance Optimizations (Opus)

1. Heightmap generation pure-Python O(w*h*octaves) — needs numpy vectorization
2. Vegetation scatter creates individual objects, not GPU instances
3. No terrain chunking for open-world streaming
4. Bake operations sequential across objects/channels
5. OpenSimplex fallback uses MD5 per pixel (catastrophically slow)

## Quick Win: Wire Existing Hand/Foot Generators

Gap #20 from visual quality scan: `generate_hand_mesh()` and `generate_foot_mesh()` ALREADY EXIST in `facial_topology.py` but `npc_characters.py` still uses `_subdivided_box` for hands/feet. This is a pure wiring fix.

---

Full detailed reports available in agent task outputs. Priority: fix Gemini geometry bugs first, then wire hand/foot, then add editing precision (GAP-01/02/09).
