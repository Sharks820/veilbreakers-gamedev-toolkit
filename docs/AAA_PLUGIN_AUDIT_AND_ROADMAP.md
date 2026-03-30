# VeilBreakers Toolkit — AAA Plugin Audit & Roadmap

**Date:** 2026-03-27
**Target:** Skyrim/Fable-level dark fantasy RPG quality
**PC Specs:** RTX 4060 Ti 8GB VRAM, 32GB RAM
**Constraint:** All tools must be FREE and run on consumer hardware

---

## CRITICAL ARCHITECTURE DECISION

### Asset Generation Strategy (Two-Track)

| Track | Tool | Scope | Why |
|-------|------|-------|-----|
| **API-based AI** | Tripo3D (existing), fal.ai (existing) | Props, weapons, creatures, decorative objects, small-medium assets | Generates solid meshes — no interiors, perfect for items you pick up or fight |
| **Procedural Generation** | Blender addons + custom handlers | ALL architecture, terrain, interiors, dungeons, rooms, walkable spaces | Must create actual hollow geometry with doors, windows, rooms, corridors |

**Tripo CANNOT be used for:** Buildings, dungeons, terrain, rooms, or anything the player walks through. It generates sealed solid meshes.

---

## CURRENT STATE: Toolkit Audit Summary

### What's Working Well (7-9/10)
- Combat timing data (FromSoft-quality frame data)
- Texture operations (numpy PBR pipeline)
- Shader generation (valid URP HLSL)
- Cinemachine 3.x integration
- PrimeTween integration
- MCP compound-tool architecture
- xatlas UV unwrapping
- FBX export axis configuration

### What's Critically Broken (1-4/10)
- **Characters:** 320 vertices vs 50,000 AAA standard, primitive assembly (cylinders + boxes)
- **Buildings:** Sealed boxes, no openings, no detail, no interiors
- **Vegetation:** Cone trees, box rocks, no L-system branching
- **Texture baking:** Procedural materials don't export (blank white on FBX)
- **SSS/skin:** Weight 0.15 (rubber look) vs 1.0 (skin look)
- **Metal colors:** Too dark, not physically based
- **Micro-normals:** Single bump node instead of 3-layer macro/meso/micro

### Known Bug Count
- 18 geometry bugs (7 CRITICAL: floating vertices, inverted normals, disconnected parts)
- 4 compilation blockers (EventBus signature, Path type, DamageCalculator arity)
- 8 security bypasses (type() not blocked, no TCP auth, API key in URL)
- 3 crash edge cases (face index bounds, sphere rings < 2, base_color length)

---

## GAP ANALYSIS: Current vs Skyrim/Fable

### 1. TERRAIN (Current: 5/10 → Target: 8/10)

**What Skyrim does:** Multi-layer heightmap with height-based texture blending, hydraulic erosion, LOD terrain chunks, grass billboard scatter at distance.

**What we have:** Noise-based heightmap (pure Python, slow), basic erosion, no height-based blending, no terrain chunking.

**Top 3 tools to close the gap:**

| Tool | What It Does | VRAM | Free? | MCP Integration |
|------|-------------|------|-------|-----------------|
| **A.N.T. Landscape** (built-in) | Noise-based terrain with erosion via weight paint | 0 | ✅ | Easy — `bpy.ops.mesh.landscape_add()` |
| **Terrain Mixer** (Blender extension) | Node-based blending of up to 9 height inputs | 0 | ✅ | Medium — node graph composition |
| **ErosionR** (GitHub) | Simulated hydraulic erosion on meshes | <1GB | ✅ | Easy — operator calls |

**Quick wins:**
1. NumPy-vectorize heightmap generation (50-200x speedup, ~4 hours)
2. Add height-based texture blending to materials (~4 hours)
3. Integrate A.N.T. Landscape operators for terrain variety (~2 hours)

---

### 2. ARCHITECTURE & BUILDINGS (Current: 2/10 → Target: 7/10)

**What Skyrim does:** Modular kit pieces (walls, corners, pillars, arches, stairs) snapped on a grid. Every building has door openings, window frames, interior rooms. Gothic/Nordic architectural vocabulary with stone detail, crenellations, exposed beams.

**What we have:** Sealed boxes with no openings. No architectural detail. Single color per building.

**THIS IS THE #1 GAP. Must be 100% procedural — NOT Tripo.**

**Top 3 tools to close the gap:**

| Tool | What It Does | VRAM | Free? | MCP Integration |
|------|-------------|------|-------|-----------------|
| **Archimesh** (built-in extension) | Rooms, doors, windows, walls, stairs, furniture — walkable interiors | 0 | ✅ | High — `bpy.ops.mesh.archimesh_*` operators |
| **Building Tools** (GitHub: ranjian0) | Modular building creation: floors, walls, roof, openings | 0 | ✅ | High — Python operators |
| **Snap!** (GitHub: varkenvarken) | Define snap points for modular kit assembly | 0 | ✅ | Medium — snap point system |

**Additional critical tools:**
- **Buildify** (Geometry Nodes) — procedural Gothic building generation
- **HiFi Architecture Builder** (Blender extension) — walls, pillars, stairs, domes
- **Sverchok** (open source) — Houdini-like node-based procedural modeling

**Architecture strategy for the toolkit:**
1. **Modular kit system:** Generate wall, corner, pillar, arch, door frame, window frame, floor, ceiling, stair, roof pieces
2. **Room composer:** Snap kits together into rooms with proper openings
3. **Building assembler:** Stack rooms into buildings with exterior shells
4. **Style presets:** Gothic, medieval, dark fantasy, corrupted variants
5. **Interior decorator:** Place furniture, props, lighting markers per room type

---

### 3. WALKABLE INTERIORS (Current: 3/10 → Target: 8/10)

**What Skyrim does:** Every interior is a separate cell with rooms connected by doors. Rooms have proper occlusion, lighting, and are densely decorated with props that tell a story.

**What we have:** `compose_interior` exists but generates abstract room shells without proper geometry.

**Top 3 tools to close the gap:**

| Tool | What It Does | VRAM | Free? | MCP Integration |
|------|-------------|------|-------|-----------------|
| **WFC 3D Generator** (GitHub: Primarter) | Wave Function Collapse for tile-based room generation | 0 | ✅ | Very High — perfect for dungeon/room layouts |
| **Dungeon Maker** (itch.io: retroshaper) | Geometry Nodes dungeon generation | 0 | ✅ | Medium — node graph |
| **Archimesh** (built-in) | Individual room shells with door/window openings | 0 | ✅ | High |

**Interior strategy:**
1. Generate room layout (BSP or WFC)
2. Create room shells using Archimesh operators (walls with openings)
3. Place door frames, windows at connection points
4. Furnish rooms by type (tavern_hall → tables, chairs, bar; bedroom → bed, wardrobe, rug)
5. Add lighting markers (torch sconces, chandeliers, fireplaces)
6. Export with occlusion zone markers for Unity

---

### 4. VEGETATION (Current: 2/10 → Target: 7/10)

**What Skyrim does:** L-system trees with bark textures and leaf cards, grass billboards with wind animation, Poisson-distributed scatter with slope/height rules.

**What we have:** Cone trees, box rocks, basic Poisson scatter.

**Top 3 tools to close the gap:**

| Tool | What It Does | VRAM | Free? | MCP Integration |
|------|-------------|------|-------|-----------------|
| **Sapling Tree Gen** (built-in extension) | Parametric L-system trees, 100+ species configurations | 0 | ✅ | Easy — `bpy.ops.curve.tree_add()` |
| **Modular Tree** (GitHub: GoodPie fork) | Node-based tree generation with bark/leaf presets | 0 | ✅ | Medium — node groups |
| **OpenScatter** (GitHub: GitMay3D) | Slope/elevation/moisture-aware object scattering | <1GB | ✅ | Easy — operator calls |

**Additional:**
- **Graswald** — 145+ free plant species (FBX/Alembic ready)
- **Gscatter** — free layer-based scatter with masking
- **GBH Tool** (GitHub) — procedural hair/grass strands

---

### 5. CHARACTERS & CREATURES (Current: 2/10 → Target: 6/10)

**What Skyrim does:** Sculpted base meshes, clean topology, SSS skin, normal maps with micro-detail, blend shapes for expressions.

**What we have:** 320-vertex primitive assemblies (cylinders + boxes), no SSS, no micro-normals.

**Strategy (two approaches):**

| Approach | For | How |
|----------|-----|-----|
| **Tripo API** | Unique creatures, monsters, bosses | Generate from concept art → cleanup → rig |
| **Skin Modifier** | Generic NPCs, humanoid bodies | Blender Skin modifier (skeleton vertices → continuous mesh) |

**Top 3 tools:**

| Tool | What It Does | VRAM | Free? | MCP Integration |
|------|-------------|------|-------|-----------------|
| **Bbrush** (Blender extension) | ZBrush-like sculpting with silhouette display | 0 | ✅ | Medium |
| **RetopoFlow** (GitHub: CGCookie) | Sketch-based retopology for clean game-ready topology | 0 | ✅ | Low (manual) |
| **CloudRig** (Blender extension) | Helper bones + constraints for game-ready rigs | 0 | ✅ | Medium |

**Immediate fixes (no new tools needed):**
1. SSS weight: 0.15 → 1.0 with Subsurface Scale control (~30 min)
2. Metal base colors: use physically-based values from research (~30 min)
3. Wire hand/foot generators that already exist but aren't connected (~2 hours)
4. Add 3-layer micro-normal (macro/meso/micro bump chain) (~4 hours)

---

### 6. MATERIALS & TEXTURES (Current: 4/10 → Target: 8/10)

**Critical problem:** Procedural Blender materials are destroyed on FBX export. All baked textures come out blank white.

**Top 3 tools:**

| Tool | What It Does | VRAM | Free? | MCP Integration |
|------|-------------|------|-------|-----------------|
| **Principled Baker** (GitHub: danielenger) | One-click bake all PBR maps from procedural materials | 0 | ✅ | High — `bpy.ops` |
| **BakeLab** (GitHub: specoolar) | Auto unwrap → bake → save/pack in 1 click | 0 | ✅ | High |
| **Dream Textures** (GitHub: carson-katri) | Stable Diffusion in Blender (tight on 8GB but works) | 6-8GB | ✅ | Medium |

**Pipeline fix:**
1. Create procedural material in Blender
2. Auto-bake to image textures (albedo, normal, metallic, roughness, AO)
3. Swap node tree to use baked images instead of procedural nodes
4. Export FBX with working textures

---

### 7. SCATTER & PROP PLACEMENT (Current: 4/10 → Target: 8/10)

**What Skyrim does:** Rule-based placement — trees near water, rocks on slopes, mushrooms in shade, clutter in interiors based on room type.

**Top 3 tools:**

| Tool | What It Does | VRAM | Free? | MCP Integration |
|------|-------------|------|-------|-----------------|
| **OpenScatter** (GitHub) | Slope/elevation/moisture masking, wind animation | <1GB | ✅ | Easy |
| **BagaPie** (Blender extension) | Select assets + surface → press J | 0 | ✅ | Easy |
| **Blender Scatter on Surface** (built-in) | Native Poisson disk distribution on mesh surfaces | 0 | ✅ | Very Easy |

---

### 8. LIGHTING & ATMOSPHERE (Current: 3/10 → Target: 7/10)

**What Skyrim does:** Volumetric god rays, fog volumes, time-of-day cycle, ambient occlusion, interior torchlight with flickering.

**Our toolkit already has `setup_lighting` and `setup_post_processing` in Unity.** The gap is mostly on the Blender preview side and missing Unity volumetrics.

**Quick wins (no new tools):**
1. EEVEE volumetric world settings for Blender preview
2. Nishita sky model for realistic atmosphere (~400 lines)
3. Unity `create_deep_environmental_vfx` already exists — verify it works
4. Add torch/candle flickering light templates

---

### 9. LEVEL DESIGN TOOLS (Current: 4/10 → Target: 7/10)

**Top 3 tools:**

| Tool | What It Does | VRAM | Free? | MCP Integration |
|------|-------------|------|-------|-----------------|
| **WFC 3D Generator** (GitHub) | Wave Function Collapse for constrained tile placement | 0 | ✅ | Very High |
| **Snap!** (GitHub) | Modular kit snap-point system | 0 | ✅ | High |
| **Blender Procedural Level Gen** (GitHub: aaronjolson) | BSP, random walk, castle dungeon generation | 0 | ✅ | High |

---

### 10. PERFORMANCE & EXPORT (Current: 6/10 → Target: 8/10)

**Top 3 tools:**

| Tool | What It Does | VRAM | Free? | MCP Integration |
|------|-------------|------|-------|-----------------|
| **LODGen** (Blender extension) | Progressive decimation LOD chains | 0 | ✅ | Easy |
| **UV-Packer** (Packer-IO, free) | 48% UV efficiency vs 28% Blender native | 0 | ✅ | Medium |
| **MeshLint** (GitHub) | Topology validation ("spell-checker for meshes") | 0 | ✅ | Easy |

---

## COMPLETE FREE PLUGIN LIST (All <8GB VRAM, All Automatable)

### MUST INTEGRATE (Biggest Impact)

| # | Plugin | Category | GitHub/URL | Why |
|---|--------|----------|-----------|-----|
| 1 | **Archimesh** | Architecture | Built-in Blender extension | Walkable rooms with doors/windows — replaces sealed boxes |
| 2 | **Building Tools** | Architecture | github.com/ranjian0/building_tools | Modular floors/walls/roofs with openings |
| 3 | **Sapling Tree Gen** | Vegetation | Built-in Blender extension | L-system trees — replaces cone primitives |
| 4 | **OpenScatter** | Scatter | github.com/GitMay3D/OpenScatter | Terrain-aware placement rules |
| 5 | **Principled Baker** | Textures | github.com/danielenger/Principled-Baker | Fix blank texture export problem |
| 6 | **WFC 3D Generator** | Level Design | github.com/Primarter/WaveFunctionCollapse | Constraint-based dungeon/room generation |
| 7 | **A.N.T. Landscape** | Terrain | Built-in Blender extension | Noise terrain with erosion |

### SHOULD INTEGRATE (High Value)

| # | Plugin | Category | GitHub/URL | Why |
|---|--------|----------|-----------|-----|
| 8 | **Terrain Mixer** | Terrain | Blender extension platform | Height-based terrain blending |
| 9 | **ErosionR** | Terrain | github.com/nerk987/ErosionR | Realistic weathering |
| 10 | **Snap!** | Level Design | github.com/varkenvarken/Snap | Modular kit snap points |
| 11 | **CloudRig** | Rigging | Blender extension platform | Game-ready rigs from metarigs |
| 12 | **EasyWeight** | Rigging | Blender extension platform | Weight painting QoL |
| 13 | **BagaPie** | Scatter | Blender extension platform | Quick asset scattering |
| 14 | **LODGen** | Performance | Blender extension platform | LOD chain generation |
| 15 | **MeshLint** | Quality | github.com/rking/meshlint | Topology validation |
| 16 | **Graswald** | Vegetation | gscatter.com | 145+ free plant species |
| 17 | **BakeLab** | Textures | github.com/specoolar/Bakelab-Blender-addon | All-in-one baking |

### NICE TO HAVE (Future)

| # | Plugin | Category | GitHub/URL | Why |
|---|--------|----------|-----------|-----|
| 18 | **Sverchok** | Procedural | nortikin.github.io/sverchok | Houdini-like node modeling |
| 19 | **RetopoFlow** | Characters | github.com/CGCookie/retopoflow | Manual retopology |
| 20 | **Bbrush** | Sculpting | Blender extension | ZBrush-like sculpting |
| 21 | **Dream Textures** | AI Textures | github.com/carson-katri/dream-textures | SD in Blender (tight on 8GB) |
| 22 | **Animation Retargeting** | Animation | github.com/Mwni/blender-animation-retargeting | Transfer anims between rigs |
| 23 | **Keemap Retarget** | Animation | github.com/nkeeline/Keemap-Blender-Rig-ReTargeting-Addon | Cross-rig bone mapping |
| 24 | **UV-Packer** | UV | uv-packer.com/blender | Better UV packing |
| 25 | **Buildify** | Architecture | Geometry Nodes library | Gothic procedural buildings |
| 26 | **HiFi Architecture Builder** | Architecture | Blender extension | Walls, pillars, domes |

---

## PRIORITIZED IMPLEMENTATION PLAN

### Phase 1: Fix What's Broken (Week 1) — Biggest Visual Impact

**No new plugins needed — fix existing code:**

| Task | Hours | Impact |
|------|-------|--------|
| Fix SSS weight (0.15 → 1.0 with Subsurface Scale) | 0.5 | Skin looks like skin instead of rubber |
| Fix metal base colors to physically-based values | 0.5 | Metals shine properly |
| Wire hand/foot generators (exist but not connected) | 2 | Characters have proper extremities |
| Fix nasolabial fold floating vertices | 1 | No face holes |
| Fix upper arm radius (inverted shoulder/elbow) | 1 | Arms look right |
| Fix mesh smoothing inverted normals | 2 | No dark patches |
| Fix mesh smoothing Z-noise reuse (n1→n3) | 0.5 | No correlated artifacts |
| Weld body parts at junctions | 2 | No light-leak seams |
| NumPy-vectorize heightmap (50-200x speedup) | 4 | Terrain generates instantly |
| Add 3-layer micro-normal chain | 4 | Surfaces have detail at every zoom level |

**Total: ~18 hours, raises overall quality from 4.4/10 → 5.5/10**

### Phase 2: Architecture Revolution (Weeks 2-3)

**Integrate: Archimesh + Building Tools + Snap!**

| Task | Hours | Impact |
|------|-------|--------|
| Integrate Archimesh operators into `blender_worldbuilding` | 8 | Rooms with door/window openings |
| Create modular kit generator (wall, corner, pillar, arch, door frame, floor, ceiling) | 16 | Bethesda-style kit assembly |
| Implement room composer (snap kits → walkable rooms) | 12 | Actual interiors |
| Add style presets (Gothic, medieval, dark fantasy, corrupted) | 8 | Visual variety |
| Interior decoration by room type | 8 | Furnished, lived-in spaces |
| Door/window frame geometry with opening cuts | 6 | Walk through doors |
| Staircase and multi-floor support | 6 | Vertical navigation |

**Total: ~64 hours, raises architecture from 2/10 → 7/10**

### Phase 3: Texture Pipeline Fix (Week 2, parallel)

**Integrate: Principled Baker + BakeLab**

| Task | Hours | Impact |
|------|-------|--------|
| Integrate Principled Baker operators | 4 | Auto-bake all PBR maps |
| Add bake-then-swap-nodes pipeline | 6 | Procedural → image for export |
| Fix FBX export (add `use_tspace=True`) | 0.5 | Normal maps work in Unity |
| Verify full round-trip: Blender procedural → bake → FBX → Unity | 4 | End-to-end texture pipeline |

**Total: ~15 hours, fixes texture export completely**

### Phase 4: Vegetation & Scatter (Week 3)

**Integrate: Sapling Tree Gen + OpenScatter + Graswald assets**

| Task | Hours | Impact |
|------|-------|--------|
| Integrate Sapling Tree Gen operators | 4 | Real L-system trees |
| Create dark fantasy tree presets (dead oak, twisted pine, corrupted willow) | 4 | Themed vegetation |
| Integrate OpenScatter for terrain-aware distribution | 6 | Trees on slopes, flowers near water |
| Add leaf card generation (billboard sprites from rendered leaves) | 6 | Foliage LOD |
| Wind vertex color baking for shader-based wind | 4 | Trees sway in wind |

**Total: ~24 hours, raises vegetation from 2/10 → 7/10**

### Phase 5: Level Design & Dungeons (Week 4)

**Integrate: WFC 3D Generator + procedural level gen**

| Task | Hours | Impact |
|------|-------|--------|
| Integrate WFC 3D for tile-based room placement | 8 | Constraint-based dungeon layouts |
| Create modular dungeon tile set (corridor, room, T-junction, corner, stairs) | 12 | Snap-together dungeons |
| Add room connectivity validation (pathfinding) | 4 | Every room is reachable |
| Occlusion zone markers for Unity | 4 | Interior performance |
| Boss arena templates with Phase-based hazard zones | 6 | Epic boss fights |

**Total: ~34 hours, raises level design from 4/10 → 7/10**

### Phase 6: Quality Polish (Week 5)

| Task | Hours | Impact |
|------|-------|--------|
| Integrate LODGen for standardized LOD chains | 4 | Consistent performance |
| Integrate MeshLint for topology validation | 4 | Catch bad meshes early |
| Expose remaining 26 Blender sculpt brushes | 8 | Full sculpt toolkit |
| Add height-based terrain texture blending | 6 | Rock on peaks, grass in valleys |
| UV-Packer integration | 4 | Better UV space usage |
| Atmospheric volumetrics (EEVEE preview) | 4 | God rays and fog |

**Total: ~30 hours**

---

## TIMELINE SUMMARY

| Phase | Weeks | Hours | Quality Gain |
|-------|-------|-------|-------------|
| 1: Fix Broken Code | 1 | 18h | 4.4 → 5.5 |
| 2: Architecture | 2-3 | 64h | Architecture 2 → 7 |
| 3: Texture Pipeline | 2 (parallel) | 15h | Textures 4 → 8 |
| 4: Vegetation & Scatter | 3 | 24h | Vegetation 2 → 7 |
| 5: Level Design | 4 | 34h | Levels 4 → 7 |
| 6: Quality Polish | 5 | 30h | Overall 6.5 → 7.5 |

**Total: ~185 hours over 5 weeks → Overall toolkit quality: 4.4/10 → 7.5/10**

That puts you in Skyrim Special Edition territory for procedural content — not quite Elden Ring, but absolutely competitive with Fable and early-era Bethesda titles.

---

## TOOL SCOPE MATRIX

| Asset Type | Generation Method | Interior? | LOD? |
|-----------|------------------|-----------|------|
| **Terrain** | Procedural (A.N.T. + custom noise + erosion) | N/A | Chunked |
| **Buildings (exterior)** | Modular kit (Building Tools + custom) | Shells only | Yes |
| **Buildings (interior)** | Room composer (Archimesh + WFC) | YES — walkable | Occlusion zones |
| **Dungeons** | WFC + BSP + modular tiles | YES — walkable | Per-room LOD |
| **Trees** | Sapling Tree Gen (L-system) | N/A | Billboard at distance |
| **Grass/Plants** | Graswald assets + OpenScatter | N/A | Billboard |
| **Props (small)** | Tripo API + cleanup | No | Yes |
| **Weapons** | Procedural (existing 41 types) + Tripo for unique | No | Yes |
| **Creatures** | Tripo API + retopo + rig | No | Yes |
| **NPCs (generic)** | Skin Modifier + procedural | No | Yes |
| **Furniture** | Procedural (existing 9 types, expand to 30+) | Part of interior | Yes |
| **Rocks/Clutter** | Procedural + Tripo for hero rocks | No | Yes |

---

## WHAT THIS REPORT DOES NOT COVER

- Animation system gaps (92-136 hours of work — separate initiative)
- Security fixes (8 bypasses — separate initiative)
- Unity C# compilation fixes (4 blockers — separate initiative)
- Character vertex density scaling (320 → 20,000+ — part of Phase 1 extension)

---

*Report generated: 2026-03-27*
*Toolkit version: v3.0 (with v4-v6 uncommitted work)*
*Test suite: 435+ procedural mesh tests pass, 55 collection errors (Python 3.12 requirement)*
