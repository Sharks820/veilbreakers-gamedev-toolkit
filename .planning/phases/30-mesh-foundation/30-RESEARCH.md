# Phase 30: Mesh Foundation — Research

**Date:** 2026-03-31
**Status:** Complete
**Sources:** Codebase audit (267 generators), Context7 (Unity/Blender APIs), procedural generation literature

---

## 1. Current Codebase State

### 1.1 Procedural Mesh Generators

**File:** `blender_addon/handlers/procedural_meshes.py` (842KB)
**Generator Count:** 267 `generate_*` functions across 21 categories
**Note:** Previous documents cite "127+" (v3.0 era) and "284" (gap analysis error). The actual current count is **267**.

**Architecture:**
- Pure Python, no bpy dependency. Returns `MeshSpec` dicts (vertices, faces, uvs, metadata)
- 8 primitive helpers: `_make_box`, `_make_beveled_box`, `_make_cylinder`, `_make_cone`, `_make_sphere`, `_make_torus_ring`, `_make_tapered_cylinder`, `_make_lathe`
- Composition pattern: `parts.append() → _merge_meshes() → _make_result()`
- Bridge layer: `_mesh_bridge.py` maps generator names to functions, `mesh_from_spec()` converts MeshSpec to Blender objects

**Quality Assessment by Category:**

| Category | Representative | Quality | Issue |
|---|---|---|---|
| Furniture (tables, chairs, chests) | generate_table_mesh | BASIC | Beveled boxes assembled. No edge loops, no wood plank detail |
| Barrels | generate_barrel_mesh | INTERMEDIATE | Lathe with sinusoidal bulge profile — proper barrel shape |
| Rocks/Boulders | generate_rock_mesh | INTERMEDIATE | `_make_faceted_rock_shell()` with noise displacement — best organic mesh |
| Pillars | generate_pillar_mesh | INTERMEDIATE | Lathe with entasis — competent classical column |
| Trees | generate_tree_mesh | BASIC | Trunk lathe is OK, canopy is sphere clusters (awful) |
| Weapons | generate_greatsword_mesh | BASIC+ | Custom quad strip blades, but very low-poly |
| Doors | generate_door_mesh | BASIC | Beveled boxes + cylinders for hinges |
| Buildings | _building_grammar.py | BASIC | Boxes for walls. Detail operations (gargoyles, buttresses) are ALL 0.5m cubes |
| Bookshelves | generate_bookshelf_mesh | EXISTS | Already has individual book geometry — not missing as gap analysis claimed |
| Crates | generate_crate_mesh | EXISTS | Already exists — not missing as gap analysis claimed |

**Root Cause of Visual Weakness:**
1. Parts are floating intersecting meshes — never boolean-unioned, never sharing vertices at junctions
2. No subdivision surface support — no edge loops, no creases
3. No mesh deformation — branches are vertical cylinders, not path-following tubes
4. `_make_lathe` and `_make_profile_extrude` are UNDERUTILIZED — barrel and pillar prove they work

**Key Insight:** The "no primitives" rule from the gap analysis is WRONG as an acceptance criterion. Primitives are valid construction methods. The problem is that the FINAL OUTPUT lacks sufficient vertex density, edge flow, and surface detail. A beveled box IS a valid building block — but it needs subdivision, edge loops, and surface noise to look AAA.

### 1.2 LOD Pipeline

**File:** `blender_addon/handlers/lod_pipeline.py` (31KB)
**Status:** ALREADY EXISTS with 7 preset tiers

```
LOD_PRESETS = {
    "hero_character": ratios [1.0, 0.5, 0.25, 0.1],
    "standard_mob": ratios [1.0, 0.5, 0.25, 0.08],
    "building": ratios [1.0, 0.5, 0.2, 0.07],
    "prop_small": ratios [1.0, 0.5, 0.15],
    "prop_medium": ratios [1.0, 0.5, 0.2],
    "weapon": ratios [1.0, 0.5, 0.2],
    "vegetation": ratios [1.0, 0.5, 0.15, 0.0] (billboard)
}
```

**Existing Functions:**
- `compute_silhouette_importance()` — pure-logic silhouette weight computation
- `compute_region_importance()` — region-based importance boosting
- `decimate_preserving_silhouette()` — edge-collapse with weighted preservation
- `generate_lod_chain()` — full LOD chain from preset

**Gap:** No furniture-specific preset. Need to ADD `"furniture": [1.0, 0.5, 0.25]` to existing presets.

### 1.3 Material System

**Three layers exist — partially disconnected:**

| Layer | File | Quality | Auto-Applied? |
|---|---|---|---|
| Basic materials | materials.py | MINIMAL (flat color + float roughness) | YES (default) |
| Procedural materials | procedural_materials.py | NEAR-AAA (45+ presets, tri-frequency normals, node trees) | NO (explicit opt-in) |
| Smart materials | texture_quality.py | AAA (22 presets, 5-layer architecture, age-driven weathering) | NO (explicit opt-in) |

**Critical Disconnect:** The default material path (`handle_material_create` in materials.py) creates flat single-color Principled BSDF with scalar roughness. The AAA-quality procedural materials and smart materials exist but are NEVER automatically applied to generated meshes.

**Fix Required:** Wire procedural material auto-assignment into the mesh generation pipeline. When a generator produces a table, it should automatically get the "rough_timber" or "polished_wood" procedural material, not a flat brown color.

**Roughness Issue (from Codex):** Even SMART_MATERIAL_PRESETS in wrinkle_maps.py use scalar roughness values (lines 434, 437). The procedural_materials.py system DOES use noise-driven roughness chains, but the smart material system does not. Both systems need roughness texture nodes.

### 1.4 Terrain System

**Files:** `_terrain_noise.py`, `_terrain_erosion.py`, `terrain_advanced.py`, `terrain_features.py`, `terrain_materials.py`, `terrain_sculpt.py`

**What Works:**
- Heightmap: fBm with opensimplex, 8 octaves, numpy-vectorized — solid
- Hydraulic erosion: Proper droplet-based with bilinear gradient, brush-based erosion/deposition — legitimate implementation
- Thermal erosion: Talus-angle based, 8-connected neighbors
- Terrain sculpt: Brush-based vertex ops (raise, lower, smooth, flatten, stamp)
- Terrain materials: 14 biome palettes, splatmap blending, corruption tint

**What's Weak:**
- Erosion default is 1,000 droplets — needs 50,000+ for visible channels
- terrain_features.py uses sin-based hash noise (NOT real Perlin) — visible repetition
- No cliff mesh generation beyond heightmap
- No domain warping for organic terrain features
- No multi-resolution terrain or virtual texturing

### 1.5 Building/Architecture System

**Files:** `_building_grammar.py`, `modular_building_kit.py`, `building_quality.py`

**Building Grammar (`evaluate_building_grammar`):**
- Produces BuildingSpec with geometry operations
- Foundation, walls (4 boxes per floor), floor slabs, roof (box)
- Window/door openings as metadata ONLY — not actual geometry cuts
- **CRITICAL BUG:** All detail operations (gargoyles, buttresses, chimneys, rose windows, spires) are rendered as identical `{"type": "box", "size": [0.5, 0.5, 0.5]}` — a gargoyle is literally a 50cm cube

**Building Quality (`building_quality.py`) — DISCONNECTED but GOOD:**
- Stone block grids (running bond pattern)
- Arch curves (gothic, roman, horseshoe, Tudor, ogee)
- Voussoir blocks for arches
- Shingle rows for roofs
- Molding profile extrusion
- **These are NOT wired into the building grammar.** They exist as standalone generators.

**Modular Kit (`modular_building_kit.py`):**
- 175 piece variants across 5 styles
- `_cut_opening()` — proper window/door cutouts with sill, header, jambs
- Per-vertex jitter for organic imperfection
- This is MORE advanced than the building grammar but is a separate system

### 1.6 City/Town Generation

**Files:** `_dungeon_gen.py` (TownLayout), `worldbuilding_layout.py`

**Town Layout:** Voronoi-based district zoning, Bresenham road connectors, rectangular lot subdivision, landmark placement at district centers.

**Critical Disconnect:** Town generator creates building PLOT MARKERS (boxes) but does NOT generate actual buildings on plots. The building grammar exists separately but is never called from town generation.

**Road Rendering:** Every road cell is a flat colored box. No road mesh with curbs, no cobblestone texture, no intersection geometry.

### 1.7 Interior/Furnishing System

**Files:** `building_interior_binding.py`, `_building_grammar.py` (generate_interior_layout)

- BUILDING_ROOM_MAP maps building types → room configurations
- STYLE_MATERIAL_MAP maps styles → material palettes
- Furniture placement exists but lacks spatial awareness (no "chairs face tables" constraint)
- No clutter/prop scattering within rooms
- No lighting placement logic

### 1.8 Tripo Pipeline

**Two clients:** tripo_client.py (API credits), tripo_studio_client.py (subscription credits)
**Post-processing:** cleanup_ai_model (8 steps), full_asset_pipeline (11 steps)
**29 building type prompts** pre-authored with style modifiers

**Critical Bug:** `cleanup_ai_model()` creates NEW BLANK PBR image textures and assigns them — effectively overwriting Tripo's embedded PBR textures instead of extracting them. The Tripo model's textures stay in the GLB and are never unpacked into standalone albedo/normal/roughness/metallic/AO files.

---

## 2. Technique Research

### 2.1 CGA Split Grammar (for Building Facades)
- Industry standard via Esri CityEngine
- Start with footprint polygon → extrude(height) → comp(f) faces → split(y) floors → split(x) bays → fill rules per bay
- Each rule produces geometry + child scopes
- Implement as recursive face subdivision on bmesh: `bmesh.utils.face_split()`, `bmesh.ops.subdivide_edges()`, `bmesh.ops.extrude_face_region()`

### 2.2 Straight Skeleton Roofs
- bpypolyskel exists for Blender — 99.99% success rate on OpenStreetMap footprints
- Shrinks polygon edges inward at equal speed, lifts by offset distance = roof surface
- Handles hip, gable (zero-speed edges on gable ends), mansard (two-stage)
- Python implementation available: github.com/Botffy/polyskel

### 2.3 Wave Function Collapse (WFC)
- Constraint propagation: tile grid → collapse lowest entropy → propagate adjacency rules
- For modular building/interior assembly — each tile has 6-face adjacency constraints
- Python implementations: github.com/Coac/wave-function-collapse (1D/2D/3D)
- Unity's TileBase neighbor-mask pattern provides infrastructure

### 2.4 L-System Trees
- String rewriting: `F -> F[+F]F[-F]F` with stack-based branching
- 3D extension with pitch/roll/yaw rotations
- Stochastic rules for natural variation
- Parametric rules for branch length/angle decay
- Implement as turtle interpreter calling bmesh cylinder creation per segment

### 2.5 Hydraulic Erosion (50K+ Droplets)
- Particle-based: spawn droplet → compute gradient → move downhill → erode/deposit → evaporate
- Brush-based erosion affects a soft radius (not point sampling)
- Key params: inertia, sediment capacity, deposition rate, evaporation rate
- Existing implementation in _terrain_erosion.py is correct — just needs more iterations

### 2.6 Domain Warping
- Replace f(p) with f(g(p)) where g distorts coordinates via another noise function
- Creates organic, flowing, tectonic-looking terrain
- Can chain: f(p + fbm(p + fbm(p))) for increasingly warped results
- Trivial to implement, dramatic visual improvement

### 2.7 Poisson Disk Sampling (Bridson's Algorithm)
- O(n) performance: active list + spatial grid (cell size r/sqrt(2))
- Density-modulated: vary minimum distance r by biome/slope/moisture
- Eliminates uniform-random "shotgun blast" scatter appearance

### 2.8 Constraint-Based Furniture Placement
- Simulated annealing against interior design guidelines
- Constraints: clearance from walls, alignment, focal point orientation, conversation distance, path accessibility, visual balance
- Activity zones per room type (kitchen work triangle, bedroom clusters)
- "Make It Home" (Yu et al., SIGGRAPH 2011) is reference implementation

### 2.9 Road Network Generation
- L-system approach (Parish/Mueller 2001): population density guides road growth
- Tensor field approach (Chen 2008): grid/radial patterns from field design, streamline tracing
- Watabou's approach: Voronoi-based block extraction, road along cell edges

### 2.10 bmesh Operations for AAA Geometry
From Context7 Blender API docs:
- `bmesh.ops.extrude_face_region(bm, geom=faces)` — face extrusion for walls/floors
- `bmesh.ops.subdivide_edges(bm, edges, cuts=N, use_grid_fill=True)` — add edge loops
- `bmesh.ops.bevel(bm, geom=edges, offset=0.1, segments=2)` — edge/vert bevel for detail
- `bmesh.ops.bisect_plane(bm, geom, plane_co, plane_no)` — slice mesh for floor separation
- `bmesh.ops.solidify(bm, geom, thickness)` — wall thickness
- `bmesh.utils.face_split(face, vert_a, vert_b)` — split face for grammar rules

---

## 3. Priority Actions for Phase 30

Based on research, the highest-impact improvements in order:

1. **Wire procedural materials as default** — Low effort, high impact. Every generated mesh gets appropriate procedural material instead of flat color.
2. **Add edge loops + bevel to primitive assembly** — After `_merge_meshes()`, run subdivision on key edges to catch light properly. Medium effort, high visual impact.
3. **Enforce seed-based RNG** — Audit all 267 generators, fix global state users. Medium effort, essential for reproducibility.
4. **Add furniture LOD preset** — Trivial, add to existing LOD_PRESETS dict.
5. **Implement scene budget validator** — New feature, needed for performance enforcement.
6. **Implement boolean cleanup pipeline** — New feature, needed for clean export.
7. **Fix smart material roughness** — Replace scalar roughness in SMART_MATERIAL_PRESETS with noise-driven roughness chains.

---

*Research compiled from: codebase audit (2026-03-31), Context7 Unity/Blender API docs, procedural generation literature (CGA, WFC, L-systems, erosion algorithms)*
