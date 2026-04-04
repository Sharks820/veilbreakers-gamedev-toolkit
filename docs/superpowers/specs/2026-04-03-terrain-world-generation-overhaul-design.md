# v9.0 Terrain & World Generation Overhaul — Design Spec

**Date:** 2026-04-03
**Author:** Claude Opus (synthesized from 16 parallel agent audits + spec review pass)
**Scope:** Full overhaul of terrain, materials, water, vegetation, castle/settlement, scatter, roads, interiors, Veil system, and Blender→Unity pipeline
**Goal:** Generate a complete, playable dark fantasy game map — not a 200m test piece

---

## 1. Problem Statement

The current Hearthvale generation has fundamental quality failures across every system:

### Scene Audit Results (2,168 objects)
- **Terrain**: 16K verts, 4 flat-color materials (near-white), NO vertex colors, NO texture nodes
- **Castle**: Split into 2 groups 85m apart, 40/44 objects have NO materials, all 44 below terrain (5-12m underground), gate is 0.06m flat plane with no opening, ramparts are 1.43m tall (waist height)
- **Vegetation**: 1,985 objects using 6 mesh templates. 30 trees in water, 79 grass at Z=0, 47 floating, 47 buried, 76 outside terrain bounds. Zero undergrowth variety (no logs, mushrooms, ferns, flowers, vines, moss)
- **Props**: 128 indoor items (barrels, crates, lanterns) scattered in wilderness with no category filtering
- **Water**: 4-vertex flat quad, hard-carved channel banks
- **Roads**: Exist in code but never deform terrain. Bridge detection exists but no bridge geometry generated
- **Interiors**: Code exists but not wired to castle generation. No enterable buildings

### Root Causes
1. **Z=0 hardcoding**: 30+ locations in worldbuilding.py and worldbuilding_layout.py place objects at Z=0 instead of calling `_sample_scene_height()` which EXISTS but is never used
2. **Dead wiring**: HeightBlend node group built but never connected. Road network exists but never called. Interior binding exists but never invoked. Coastline materials defined but never applied
3. **Basic geometry**: Castle uses `type: "box"` for all pieces. Single tree template copied 512x
4. **No filtering**: Scatter engine has no indoor/outdoor categories, no water exclusion, no settlement exclusion
5. **Deprecated API**: `group.inputs.new()` crashes Blender 4.0+ (removed API)

---

## 2. Design Overview

### Approach: System-Level Rewrites with Full Overhauls Where Needed

Keep the pure-logic/handler architecture. Upgrade the OUTPUT quality of 12 systems. Use Tripo AI for vegetation meshes instead of hand-coded geometry.

### Systems (14 phases):

| Phase | System | Type |
|-------|--------|------|
| 1 | Terrain Mesh Quality | FULL OVERHAUL |
| 2 | Terrain Materials & Texturing | FULL OVERHAUL |
| 3 | Water System | FULL OVERHAUL |
| 4 | Scatter Engine | SIGNIFICANT UPGRADE |
| 5 | Vegetation (Tripo meshes) | FULL OVERHAUL |
| 6 | Castle/Settlement Architecture | FULL OVERHAUL |
| 7 | Enterable Interiors | WIRING + UPGRADE |
| 8 | Roads & Paths | WIRING + UPGRADE |
| 9 | Veil Corruption System | NEW SYSTEM |
| 10 | World Traversal Infrastructure | NEW SYSTEM |
| 11 | Zone Classification & Encounters | NEW SYSTEM |
| 12 | Per-Biome Atmosphere | NEW SYSTEM |
| 13 | Blender→Unity Pipeline | FIX + BRIDGE |
| 14 | Integration & Polish | VERIFICATION |

---

## 3. System Designs

### Phase 1: Terrain Mesh Quality

**Current**: fBm noise only, hard-carved river channels, no erosion
**Target**: Multi-octave noise with hydraulic erosion, natural features, combat-friendly clearings

**Changes:**
- Wire existing `_terrain_erosion.py` (has `apply_hydraulic_erosion` + `apply_thermal_erosion`) into terrain generation pipeline. Tune iteration count (existing default: 1000, may need increase for 512x512)
- Target heightmap resolution: 512x512 at 1m/texel for 500m map (power-of-two standard)
- Replace V-cut river channels with S-curve bank profiles (asymmetric inner/outer banks)
- Add river meandering via sinusoidal perpendicular displacement on A* paths
- Generate procedural clearings (flattened circles with vegetation ring) for combat zones
- Generate plateau areas for settlement placement (Bethesda terrain flatten technique)
- Add ridge/valley features via ridged multifractal noise
- Height range: maintain 0-25m but with more dramatic variation (cliffs, hills, valleys)
- **Smootherstep transitions** (6t^5 - 15t^4 + 10t^3) must replace ALL linear blending — zero second derivative at endpoints eliminates visible "kinks" where flat meets slope, hill meets cliff, terrain meets water
- **Hybrid cliff system**: heightmaps cannot represent cliffs >70° without geometry stretching. Use heightmap for surrounding terrain + separate overlay meshes for cliff faces, overhangs, and caves. Cliff overlays get layered stone strata (0.3-2m thick horizontal bands, alternating hard/protruding and soft/recessed)
- **Spline-based terrain deformation**: connect `terrain_advanced.py` Bezier splines with `road_network.py` paths for river channel carving AND road terrain deformation. This is the missing link — both systems exist but aren't connected
- **Biome boundary blending**: use jittered sparse convolution (max(0, R^2 - d^2)^2) instead of linear or Voronoi boundaries. Eliminates visible grid artifacts at biome transitions. Cost: ~200-800ns per coordinate
- **Geological boulder scatter**: Pareto-distributed distance from source, size inversely correlating with distance, 15-45% burial depth, alignment with source direction. NOT random sphere scatter (the single biggest "looks procedural" giveaway)
- **Scree/talus generation** at cliff bases: angle of repose 32-38°, cone-shaped deposits, inverse size grading (large rocks at base, small at top)
- **River bank asymmetry**: cut banks (outer bend, 60-90° steep, eroding) vs point bars (inner bend, 5-15° gentle, depositing). Meander wavelength = 11x channel width

**Key constraints**:
- Terrain mesh must remain navmesh-friendly for Unity. No T-junctions, reasonable density
- Smootherstep MUST be used for ALL feature-to-terrain transitions (hills, cliffs, water edges, roads, clearings)
- Cliff overlay meshes must be separate objects parented to terrain chunk for proper LOD/streaming

### Phase 2: Terrain Materials & Texturing

**Current**: 4 bare Principled BSDF (near-white), no vertex colors, no texture nodes. HeightBlend node group exists but is dead code.
**Target**: Multi-layer procedural shaders with vertex color splatmap, biome-aware blending

**Changes:**
- Fix deprecated `group.inputs.new()` → `group.interface.new_socket()` in `_create_height_blend_group()`
- Wire HeightBlend node group into terrain material builder
- Build `build_layered_terrain_material()` with 4-layer splatmap blending:
  - R channel = grass/ground cover
  - G channel = rock/cliff face
  - B channel = dirt/path
  - A channel = special (mud near water, snow at peaks, corruption near Veil)
- Add vertex color painting to terrain mesh based on height + slope + moisture
- Implement 6 dark fantasy terrain recipes:
  1. Forest floor (dark leaf litter, exposed roots, moss patches) — base_color ~(0.07, 0.06, 0.04)
  2. Rocky highland (gray stone, lichen, sparse grass) — base_color ~(0.13, 0.12, 0.10)
  3. Swamp/marshland (black mud, toxic pools) — base_color ~(0.04, 0.03, 0.03)
  4. Castle stone (weathered, mossy, cracked) — base_color ~(0.15, 0.13, 0.11)
  5. Dirt paths (packed earth, cart tracks) — base_color ~(0.12, 0.10, 0.07)
  6. River banks (wet mud→damp earth→grass gradient) — blended
- Add Noise Texture / Voronoi nodes for micro-detail variation (pebbles, grass blades, dirt particles visible up close)
- Water proximity gradient: dry→damp→wet→mud within 5m of shoreline (5-layer material transition)
- **Tri-planar mapping** for cliff face overlay meshes — eliminates UV stretching on vertical surfaces
- **Height-based texture blending**: rocks poke through grass based on displacement height map, not flat boundary
- **Macro variation layer**: large-scale (50-100m) Noise Texture color/value shifts to break visible tiling patterns
- **Curvature-driven wear**: procedural edge wear at corners and ridges using curvature map output
- **AO-driven dirt accumulation**: crevice darkening using baked or procedural ambient occlusion
- **PBR accuracy enforcement**: stone roughness 0.7-0.95, wood 0.5-0.8, water 0.0-0.1, metallic=0.0 for ALL non-metals. Base color energy conservation: no value below 0.02 or above 0.95

**Key constraint**: Materials must survive Blender→Unity pipeline. Use single BSDF with mixed inputs (not multi-BSDF) for simpler baking. Reserve vertex color A (alpha) channel for Veil corruption intensity — Phase 9 will use this to tint materials at bake time (darken base color, increase roughness, add purple hue proportional to alpha value).

### Phase 3: Water System

**Current**: 4-vertex flat quad at Z=3.0, no shoreline, hard channel edges
**Target**: Shaped river mesh with natural banks, lakes, proper material

**Changes:**
- Replace flat quad with spline-based river mesh following terrain contours
- Variable river width (narrow in canyons, wide in valleys)
- Natural shoreline geometry with noise-displaced edges
- Smooth bank slopes: 15-30° grade (not vertical carved walls)
- Shoreline material transition: water→wet_rock→mud→grass (vertex color driven)
- Add lake/pond generation with irregular shapes and gradual depth shelves
- Add stream tributaries feeding main river
- Water material: transparency, dark blue-green tint, subtle wave normal mapping, flow direction vertex colors for Unity shader
- Reed/waterplant placement zones along shorelines

### Phase 4: Scatter Engine Fixes

**Current**: Dumps all props everywhere. 128 indoor items in wilderness. No water exclusion.
**Target**: Category-aware, zone-aware, terrain-conforming placement

**Changes:**
- Add prop category enum: `WILDERNESS` (rocks, logs, mushrooms), `SETTLEMENT` (barrels, crates, lanterns, benches), `INDOOR` (bookshelves, tables, chairs)
- Only scatter appropriate categories per zone type
- Add water exclusion zones: no vegetation within 2m of water surface (except reeds/waterplants)
- Add settlement exclusion zones: no random vegetation inside castle/town walls
- Add terrain slope filtering: no objects on faces steeper than 45°
- Fix Z=0 hardcoding: replace ALL hardcoded Z values with `_sample_scene_height()` calls (30+ locations in worldbuilding.py, worldbuilding_layout.py)
- Add density variation: Perlin noise-driven pockets of dense/sparse rather than uniform
- Verify objects sit on terrain surface: raycast down from placement point
- Hide template objects at origin (9 templates currently visible)
- Clamp placement to terrain bounds (76 objects currently outside)

### Phase 5: Vegetation (Tripo AI Meshes)

**Current**: 1 tree template (946 verts lollipop) × 512. 1 grass template × 788. No variety.
**Target**: Tripo-generated low-poly meshes, 4+ tree species, undergrowth layers

**Changes:**
- Generate via Tripo AI (low poly, <2K tris per tree, <500 per bush):
  - 4 tree species: dark oak (broad canopy), pine (conical), birch (thin/white bark), dead/twisted (dark fantasy)
  - 2-3 variants per species (different branch patterns)
  - 3 bush types: flowering shrub, thorny bramble, low ground cover
  - Fallen log (2 variants: mossy, fresh)
  - Mushroom cluster (2 variants: small cluster, single large)
  - Fern (2 variants: spread, curled)
  - Boulder cluster (3-5 rocks grouped naturally)
- Validate all Tripo meshes: topology check, tri count budget, UV unwrap
- **Fallback strategy**: if Tripo mesh fails validation after 3 retries, use procedurally generated fallback (improved version of existing template — better than no tree)
- Import as reusable templates, replace single `_template_tree`
- Scale variation with limits: trees 0.8x-1.4x (current range is fine, keep it)
- Biome-aware species distribution: oaks in forests, pines in highlands, dead trees near Veil
- Undergrowth layers per biome from BIOME_VEGETATION_SETS (already defined in code, just needs templates)
- Fix template reference validation: check template exists before placement (currently silent fail)

### Phase 6: Castle/Settlement Architecture

**Current**: Box geometry, 784 verts, split in two groups, 40/44 no materials, all underground, no gate opening
**Target**: Proper medieval castle with modular pieces, terrain-aware, enterable

**Changes:**
- Fix castle placement: all pieces co-located at keep position, not split at origin
- Fix Z placement: sample terrain height at castle footprint, place at terrain level
- Primary: Variable-height foundations (FromSoftware technique) — foundation walls step with terrain slope, visible masonry on downslope side
- Fallback: Flatten terrain under footprint (Bethesda technique) with 4m softened edge for flat-terrain buildings
- Foundation rock meshes at castle-terrain seams to hide transitions
- Replace box walls with proper curtain walls: 3m thick, 8m tall, walkway on top
- Replace box towers with octagonal towers: tapered shaft, crenellated crown, arrow slits
- Gatehouse with actual archway opening (boolean cut in wall mesh), portcullis slot
- Keep with varied roofline: pitched roof, chimney, dormer windows
- Battlements on all walls (generate_battlements exists, wire it up)
- Courtyard layout: well, training dummy area, stable area, cart
- Apply multi-zone facade materials to ALL pieces: base stone, wall stone, upper trim, roof tiles, window frames (3-5 material zones per facade, not single material)
- Silhouette variation pass for ALL settlement buildings: chimneys, dormers, rooftop clutter, jetty overhangs (min 4 profile breaks per building side — not just the keep)
- Weathered stone materials: base_color ~0.15-0.20, roughness 0.85+, metallic 0.0, with directional moss/rain weathering
- City infrastructure around castle: ring district system (code exists in settlement_grammar)
- Wire in settlement_generator.py which has 16 settlement types already defined
- Calibrate settlement sizes: village=15, town=40, city=100+ buildings

### Phase 7: Enterable Interiors

**Current**: building_interior_binding.py exists with 13 building types and room layouts, but never called
**Target**: Castle rooms, tavern, shops accessible through doors

**Changes:**
- Wire building_interior_binding into settlement generation pipeline
- Generate interior shells for key buildings: castle keep (throne room, armory, dungeon), tavern (main hall, kitchen, bedrooms), blacksmith (forge, storage), temple (nave, crypt)
- Interior furniture placement from ROOM_FURNISHINGS (14 room types defined)
- Fix door generation: connect doors to actual building wall openings (currently disconnected)
- Fix room spatial validation: verify rooms fit within building bounds
- Add internal room-to-room doorway generation (currently only exterior doors)
- Staircase placement between floors (5 styles exist in building_quality.py)
- Interior lighting from LIGHT_PROP_MAP
- Generate door_metadata for Unity streaming triggers

### Phase 8: Roads & Paths

**Current**: road_network.py generates mesh specs but roads never deform terrain. Bridge detection exists but no bridge geometry.
**Target**: Terrain-integrated roads connecting settlements

**Changes:**
- Wire road_network into compose_map pipeline
- Add terrain deformation: roads cut into terrain surface (crown-and-ditch profile)
- Blend width 2-4m on each side for natural terrain transition
- Road material auto-applied: cobblestone near settlements, packed dirt in wilderness
- Update terrain splatmap under roads (B channel = dirt/path)
- Generate bridge geometry at river crossings (currently only metadata flag in `road_network.py:307` — this is the canonical location for bridge mesh generation)
- Add switchback collision detection (currently can self-intersect)
- Generate intersection geometry (currently metadata only)
- Path hierarchy: main roads (4-8m wide), trails (2-3m), alleys (1-2m)

### Phase 9: Veil Corruption System (NEW)

**Current**: Corruption tiers defined in settlement_grammar but no terrain/material/atmosphere implementation. `_veil_pressure_at()` in map_composer has undefined integration.
**Target**: Visible corruption gradient affecting everything as players approach the Veil

**Changes:**
- Define Veil boundary position (edge of map or configurable spline)
- Corruption gradient: 0% (safe zones near settlements) → 100% (at the Veil boundary)
- Terrain material corruption: progressive darkening, roughness increase, purple/black tint
- Vegetation corruption: healthy trees → blighted → dead/twisted → corrupted (glowing cracks)
- Water corruption: clean blue → murky green → toxic purple near Veil
- Ground corruption: grass → dead grass → cracked earth → void stone
- Corruption props: twisted roots, glowing void crystals, dead animals, corruption tendrils
- Atmospheric corruption: clear → hazy → thick purple fog → void particles
- Consolidate two `_veil_pressure_at()` implementations (map_composer.py and world_map.py have different signatures/weights) into single canonical function in map_composer.py. Wire to return actual pressure values based on distance from Veil boundary

### Phase 10: World Traversal Infrastructure (NEW)

**Current**: No bridges, mountain passes, cave entrances, or traversal features
**Target**: Complete traversal network for a playable game map

**Changes:**
- Bridge generation at road-river crossings: stone arch bridge, wooden plank bridge
- Mountain pass corridors between biomes: carved path through steep terrain
- Cave/dungeon entrance placement: 3-5 per map region
  - Cave mouths in cliff faces with torch sconces and corruption glow
  - Ruin entrances in forests (broken stone archway)
  - Sewer grates under castle (connects to dungeon)
- Waypoint markers: cairns, ruined statues, signposts at road intersections
- Wire existing generators into `compose_world_map`: `generate_cliff_face` from `terrain_features.py`, cave entrance from `coastline.py`, bridge detection from `road_network.py`

### Phase 11: Zone Classification & Encounters (NEW)

**Current**: encounter_spaces.py has templates but not wired to settlements. No world-level zone map.
**Target**: Difficulty-scaled zones with proper encounter placement

**Changes:**
- Zone classification system:
  - Safe zones: inside settlement walls, 30m radius around gates
  - Contested zones: wilderness between settlements
  - Danger zones: near Veil boundary, high-corruption areas
- Difficulty scaling: tied to distance from nearest settlement + Veil proximity
- Boss arena generation: existing templates + terrain flattening + cover placement
- Mob patrol waypoints: along roads and settlement perimeters
- Bandit camp generator: palisade ring, campfire, tents, crude gate, stolen crates
- Watchtower/outpost generator: standalone tower at vantage points
- ~~NPC spawn markers~~ — DEFERRED to future milestone per user direction
- Wire encounter_spaces defensive_holdout into settlement generation

### Phase 12: Per-Biome Atmosphere (NEW)

**Current**: No per-biome fog, lighting, particles, or color grading
**Target**: Distinct atmosphere per biome zone

**Changes:**
- Per-biome fog: density, color, falloff distance
  - Forest: moderate green-grey fog, 50m falloff
  - Swamp: thick yellow-green fog, 20m falloff
  - Mountains: light blue haze, 100m falloff
  - Corruption: thick purple-black fog, 15m falloff
- Per-biome particles: dust in desert, fireflies in swamp, ash near volcanics, corruption motes near Veil
- Per-biome ambient light: forest green, dungeon purple, mountain blue, corruption red
- God ray integration with sun angle
- Fix atmospheric_volumes.py: 11 of 21 biomes missing atmosphere rules
- Add time-of-day variation (currently static volumes)

### Phase 13: Blender→Unity Pipeline

**Current**: Dual export exists (heightmap RAW + FBX) but gaps in vegetation bridge, prefab dedup, splatmap transfer
**Target**: Complete pipeline that preserves all visual quality

**Changes:**
- Clarify dual-export strategy: RAW heightmap for terrain base, FBX for buildings/props/vegetation
- Vegetation instance serialization: export Blender scatter positions to JSON → Unity C# script calls `TerrainData.SetTreeInstances()` and paints DetailPrototype density
- Splatmap transfer: bake vertex colors to splatmap image → import as Unity Terrain alphamap
- Per-chunk heightmap RAW export (currently only master heightmap)
- Prefab deduplication: hash building meshes by kit type, export one FBX per unique type
- Texture bake pipeline: diffuse, normal, roughness, metallic+smoothness packed per material
- Atlas strategy: 2K per terrain chunk, 1K per building type (shared across instances), 512 for vegetation billboards
- Interior mesh export: per-building interior FBX, door trigger metadata JSON, interior-to-building parent reference mapping for Unity streaming
- Define performance budget: 50K tris per terrain chunk LOD0, max 200 draw calls per loaded chunk, 3x3 streaming window at LOD0, total scene budget ~2M tris loaded at any time

### Phase 14: Integration & Polish

**Changes:**
- Full scene regeneration test with all systems active
- 10-angle AAA contact sheet verification
- Floating geometry detection pass
- Default material detection pass (flag anything still near-white)
- Cross-system integration tests (roads cross water = bridge, vegetation avoids water, castle sits on terrain)
- Performance profiling: total scene poly count, draw call estimate, texture memory
- Regression baselines for future generations

---

## 4. Dependencies

```
Phase 1 (Terrain Mesh) ──→ Phase 2 (Materials) ──→ Phase 3 (Water)
Phase 1 ───────────────→ Phase 4 (Scatter)     ──→ Phase 5 (Vegetation)
Phase 1 ───────────────→ Phase 6 (Castle)      ──→ Phase 7 (Interiors)
Phase 1 + Phase 3 ─────→ Phase 8 (Roads)       ──→ Phase 10 (Traversal)
Phase 2 ───────────────→ Phase 5 (Vegetation materials)
Phase 2 ───────────────→ Phase 9 (Veil)
Phase 3 ───────────────→ Phase 4 (Water exclusion zones)
Phase 4-6 ─────────────→ Phase 11 (Zones)
Phase 9 (Veil) ────────→ Phase 12 (Atmosphere)
Phase 1-12 ────────────→ Phase 13 (Pipeline)
Phase 13 ──────────────→ Phase 14 (Integration)
```

---

## 5. Bug Fix Inventory (from 16-agent audit)

### Critical Bugs to Fix During Relevant Phases

| Bug | Phase | Location |
|-----|-------|----------|
| `group.inputs.new()` deprecated API | 2 | terrain_materials.py:1560 |
| Z=0 hardcoding (30+ locations) | 4, 6 | worldbuilding.py, worldbuilding_layout.py |
| Castle split at two locations | 6 | worldbuilding.py:5509 |
| 40/44 castle objects no materials | 6 | worldbuilding.py castle generation |
| Gate is 0.06m flat plane | 6 | _building_grammar.py |
| Ramparts 1.43m tall | 6 | _building_grammar.py |
| 30 trees in water | 4 | scatter engine |
| 79 grass at Z=0 | 4 | scatter engine |
| 128 indoor items in wilderness | 4 | scatter engine |
| 9 templates visible at origin | 4 | template management |
| 76 objects outside bounds | 4 | scatter engine bounds check |
| Door generation disconnected | 7 | building_interior_binding.py:239 |
| Road terrain deformation absent | 8 | road_network.py:679 |
| Bridge geometry not generated | 8 | road_network.py:307 |
| Coastline materials not applied | 3 | coastline.py:426 |
| Veil pressure undefined | 9 | map_composer.py:276 |
| HeightBlend node never wired | 2 | terrain_materials.py |
| 11/21 biomes missing atmosphere | 12 | atmospheric_volumes.py |

---

## 6. Tripo AI Asset Strategy

### Vegetation Meshes to Generate
All meshes must be: low-poly (<2K tris), PBR-ready, single object, white background, dark fantasy medieval style

| Asset | Tripo Prompt | Max Tris | Variants |
|-------|-------------|----------|----------|
| Dark Oak | "gnarled dark oak tree, thick twisted trunk, broad canopy, dark fantasy forest" | 2000 | 3 |
| Pine | "tall dark pine tree, conical shape, sparse branches, dark fantasy mountain" | 1500 | 2 |
| Birch | "thin white birch tree, peeling bark, sparse leaves, dark fantasy" | 1500 | 2 |
| Dead Tree | "dead twisted tree, no leaves, gnarled branches, dark corruption, fantasy" | 1000 | 2 |
| Flowering Shrub | "low dark shrub with small pale flowers, dark fantasy undergrowth" | 500 | 2 |
| Thorny Bramble | "thorny bramble bush, dark twisted branches, dark fantasy" | 500 | 2 |
| Fallen Log | "fallen mossy log, dark forest floor, mushrooms growing, dark fantasy" | 800 | 2 |
| Mushroom Cluster | "cluster of fantasy mushrooms, pale caps, dark forest floor" | 400 | 2 |
| Fern | "dark fern plant, curled fronds, forest undergrowth, dark fantasy" | 300 | 2 |
| Boulder Cluster | "group of 3 moss-covered boulders, dark fantasy landscape" | 600 | 2 |
| Reed Cluster | "tall reeds and cattails, waterside, dark fantasy marsh" | 300 | 1 |

**Total: 22 unique vegetation meshes** replacing current 6 templates.

---

## 7. Success Criteria

1. Generate a 500x500m+ map with multiple biomes (forest, highland, swamp, corruption)
2. Castle is architecturally coherent: walls, towers, gatehouse with opening, keep, courtyard
3. At least 3 settlements (castle, village, bandit camp) connected by roads
4. Terrain has visible texture variation: grass, rock, dirt, mud, corruption
5. No objects below terrain, in water (except waterplants), or floating >0.5m
6. No indoor props in wilderness
7. Veil corruption visible as gradient across the map
8. Bridges at river crossings, paths through mountains
9. At least 1 enterable building with furnished interior
10. All materials PBR-correct (no metallic stone, no mirror-roughness on wood)
11. Full Blender→Unity pipeline exports without losing visual quality
12. Scene renders in Blender viewport at >15 FPS with all objects visible

---

## 8. Terrain Meshing & Quality Rules (Mandatory)

These rules apply across ALL phases and ALL terrain/mesh generation:

### Transition Rules
- **Smootherstep EVERYWHERE**: `6t^5 - 15t^4 + 10t^3` for all feature-to-terrain transitions. No linear interpolation at terrain boundaries.
- **Biome boundaries**: jittered sparse convolution blending over 10-50m ecotone zones. Never sharp Voronoi edges.
- **Water banks**: 5-layer material gradient (submerged pebbles → wet mud → damp earth → dry grass → normal terrain) over 2-5m width.
- **Road edges**: 2-4m blend width, crown-and-ditch profile, terrain splatmap updated under road surface.

### Geometry Rules
- **Cliff faces >70°**: MUST use overlay meshes, not heightmap stretching. Separate objects parented to terrain.
- **Scree at cliff bases**: 32-38° angle of repose, inverse size grading, Pareto-distributed boulder sizes.
- **Boulders**: 15-45% buried, moss on north-facing surfaces, power-law size distribution (exponent ~2.5).
- **River meanders**: wavelength = 11x channel width, asymmetric banks (cut bank 60-90°, point bar 5-15°).
- **Clearings**: irregular shapes, 10-30m diameter, denser undergrowth at edges.

### Material Rules
- **Tri-planar mapping** on all cliff/vertical surfaces. No UV stretching.
- **Height-based blending**: rocks protrude through grass via displacement height, not flat boundary.
- **Macro variation**: 50-100m scale noise to break tiling.
- **PBR enforcement**: stone roughness 0.7-0.95, wood 0.5-0.8, metallic=0.0 for non-metals. No mirror stone (roughness 0.0).
- **Curvature wear** at edges/corners. AO-driven dirt in crevices.

### Riggable/Physics Mesh Rules
- **Doors**: 200-500 tris, edge loops around hinges, clean quad flow. Types: wooden plank, iron-bound, portcullis, trapdoor.
- **Ropes/Chains**: catenary curve for natural hang. Rope: twisted strand or cylinder+normal map, 50-100 tris/segment. Chain: 80-120 tris/link, instanced.
- **Flags/Banners/Cloth**: uniform quad grid 10-20 segments per axis, pin constraints at attachment (top edge for banners, corners for flags). Wind force + turbulence for natural movement. 200-400 tris per flag.
- **Curtains/Window coverings**: gravity-draped cloth sim, baked to keyframes for export. 100-300 tris.
- **Hanging objects**: chandelier chains with pendulum sway, hanging signs with wind rotation, cage suspension.
- **Deformable topology**: edge loops MUST follow deformation paths. Minimum 3 edge loops across bending areas. Quads only in deformation zones — no triangles. Weight painting for smooth deformation.
- **Export**: all rigged/physics objects export as FBX with armature. Cloth sim baked to keyframes. Spring bones for runtime physics in Unity.

### Spline Integration (Critical Missing Link)
- `terrain_advanced.py` Bezier splines + `road_network.py` path output → terrain deformation function
- Rivers AND roads use this same spline→deform pipeline
- Spline defines: center line, width profile, depth profile, bank slope profile
- Terrain vertices within spline influence radius get displaced to match profile

---

## 9. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Tripo API latency for 22 meshes | Batch generate all meshes upfront, cache as templates |
| Performance with more vegetation variety | LOD pipeline already handles 4-level trees + billboards |
| Terrain erosion breaks existing features | Run erosion BEFORE settlement/vegetation placement |
| Castle overhaul breaks existing tests | All castle tests use generate_castle_spec — update spec, tests follow |
| Pipeline complexity | Phase 13 is dedicated to pipeline; test export after each phase |

---

## 9. Out of Scope

- Runtime terrain deformation (this is generation-time only)
- Dynamic weather effects (Unity-side only)
- Procedural quest generation (separate system)
- Character/NPC mesh generation (existing system, not part of terrain overhaul)
- Audio/music integration (separate system)
