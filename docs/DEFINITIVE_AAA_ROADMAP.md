# DEFINITIVE AAA ROADMAP — VeilBreakers Toolkit v7.0

**Date:** 2026-03-27
**Scope:** Architecture, Textures, 3D Modeling, Map Design, Terrain, Intelligent Placement, City Generation, AI Agent Editability
**PC:** RTX 4060 Ti 8GB VRAM, 32GB RAM
**Constraint:** ALL tools FREE, all systems AI-editable through MCP

---

## THE TWO-TRACK STRATEGY

| Track | Tool | Scope |
|-------|------|-------|
| **Procedural (Blender)** | 30+ free addons + custom handlers | Terrain, architecture, roads, cities, interiors, dungeons — anything walkable |
| **AI Generation (Tripo API)** | Batch API calls | ALL small/medium details: furniture, signs, barrels, crates, lanterns, statues, market stalls, well pumps, gravestones, food, tools, clutter |

**Rule:** If the player walks THROUGH it → Procedural. If the player walks PAST it → Tripo.

---

## PART 1: FULL CITY GENERATION PIPELINE

### The Vision: One MCP Command → Full Dark Fantasy City

```
compose_city(
    city_type="walled_medieval",
    district_count=5,
    building_count=80,
    road_style="organic",
    has_river=True,
    has_walls=True,
    has_castle=True,
    style="dark_fantasy",
    populate_interiors=True,
    tripo_detail_budget=200  # Tripo API calls for props
)
```

### Pipeline Steps (All Automatable via MCP)

**Step 1: City Layout (Voronoi + L-System Roads)**
- Generate city boundary (wall perimeter)
- Create district zones via Voronoi tessellation (market, residential, noble, slum, temple)
- Generate primary road network (L-system based, organic or grid)
- Secondary roads via subdivision
- Place key landmarks (castle, cathedral, market square, gate towers)

**Tools:** Custom Python (josauder/procedural_city_generation is open source, MIT license), watabou Medieval Fantasy City Generator (open source, exportable SVG→Blender)

**Step 2: Road Geometry**
- Extrude road paths into actual geometry (cobblestone, dirt, flagstone)
- Add curbs, gutters, drainage
- Generate bridges over rivers
- Apply road surface materials (procedural cobblestone via Voronoi texture)

**Tools:** BagaPie (free, road arrays), Building Tools (road surfaces), custom handlers

**Step 3: Building Generation (PER DISTRICT)**
- Each district has style rules (noble = stone + ornate, slum = wood + ramshackle)
- Generate building shells with Archimesh (rooms, doors, windows, stairs)
- Add roofs with Building Tools (hip, gable, flat, mansard per style)
- Apply facade detail (shutters, flower boxes, signs, awnings)
- Generate walkable interiors for key buildings

**Tools:** Archimesh (GPL, built-in), Building Tools (MIT, free), BagaPie v11 (free — doors, windows, bolts, railings, stairs)

**Step 4: City Walls & Gates**
- Perimeter wall with walkway
- Gate towers at road entry points
- Crenellations, arrow slits, murder holes
- Guard towers at corners

**Tools:** Building Tools + custom modular kit

**Step 5: Detail Population via Tripo API (Batch)**
- Market stalls, barrels, crates, sacks → Tripo batch generation
- Hanging signs, lanterns, braziers → Tripo
- Well pumps, fountains, statues → Tripo
- Market goods (fruit, bread, weapons on display) → Tripo
- Cemetery props, gravestones → Tripo
- Tavern interior props (mugs, plates, kegs) → Tripo

**Budget:** ~200 Tripo API calls per city (batched, cacheable for reuse)

**Step 6: Vegetation & Nature**
- Trees along roads (Sapling Tree Gen with dark fantasy presets)
- Ivy/moss on walls (BagaPie ivy generator)
- Garden plots (OpenScatter for flower/herb scatter)
- River vegetation (reeds, lily pads)

**Step 7: Lighting**
- Street lanterns (Tripo mesh + point light markers)
- Window glow (emission material on window panes)
- Torch sconces on buildings
- Interior lighting markers (candles, fireplaces, chandeliers)

**Step 8: Export to Unity**
- Bake all procedural materials → image textures (Principled Baker)
- Generate LOD chains
- Export FBX per district (for streaming)
- Unity: setup terrain, lighting, NavMesh, occlusion, post-processing

---

## PART 2: TERRAIN — EVERY FUNCTION NEEDED

### Current Terrain Capabilities (What We Have)

| Function | Status | Quality |
|----------|--------|---------|
| Heightmap generation (noise) | ✅ Have | 3/10 — Pure Python, slow |
| Hydraulic erosion | ✅ Have | 4/10 — Basic, needs multi-pass |
| Biome painting | ✅ Have | 5/10 — Works but no height-based |
| River carving | ✅ Have | 5/10 — Works |
| Road generation | ✅ Have | 4/10 — Basic |
| Sculpt at coordinates | ✅ Have | 7/10 — Good brush math |
| Vegetation scatter | ✅ Have | 4/10 — Cone trees, no rules |

### What's Missing (With Fix)

| Function | Tool/Fix | Free? | Effort |
|----------|----------|-------|--------|
| **NumPy-vectorized heightmap** | Rewrite _terrain_noise.py with numpy | ✅ | 4h |
| **Height-based texture blending** | Shader node: compare heights per-pixel | ✅ | 4h |
| **Thermal erosion** | Add thermal pass to _terrain_erosion.py | ✅ | 4h |
| **Multi-pass erosion chaining** | Large→medium→fine passes | ✅ | 3h |
| **Terrain chunking** | Split into NxN tiles for LOD/streaming | ✅ | 6h |
| **Flow map computation** | D8/MFD algorithm for rivers/moss | ✅ | 6h |
| **A.N.T. Landscape integration** | Wire `bpy.ops.mesh.landscape_add()` | ✅ Built-in | 2h |
| **ErosionR integration** | Wire operator for realistic erosion | ✅ GPLv2 | 3h |
| **Terrain Mixer integration** | Node-based height blending | ✅ Free | 4h |
| **Easy Terrain Gen v2.1** | Customizable hydraulic erosion sim | ✅ Free | 4h |
| **Spline-based terrain deform** | Roads/rivers deform terrain surface | ✅ | 8h |
| **Terrain stamps** | Place predefined features (cliff, crater, mesa) | ✅ | 6h |
| **Sediment/drainage simulation** | Realistic sediment deposit | ✅ | 6h |
| **GPU instancing export** | Vegetation as instanced mesh data | ✅ | 8h |

**Total terrain work: ~68 hours**

---

## PART 3: ARCHITECTURE — COMPLETE SYSTEM

### Building Generation Pipeline

```
generate_building(
    building_type="tavern",      # tavern/house/shop/temple/castle/tower/warehouse/mill
    style="dark_fantasy_gothic",  # dark_fantasy_gothic/medieval_timber/stone_masonry/corrupted
    floors=2,
    has_basement=True,
    generate_interior=True,
    room_types=["tavern_hall", "kitchen", "storage", "bedroom", "bedroom"],
    facade_detail="high",         # low/medium/high
    roof_type="gable",
    wall_material="stone_with_timber",
    tripo_detail_count=15         # Tripo calls for interior props
)
```

### Free Tools for Architecture (ALL Verified Free)

| # | Tool | License | What It Does | MCP-Automatable |
|---|------|---------|-------------|-----------------|
| 1 | **Archimesh** | GPL (built-in) | Rooms, doors, windows, walls, stairs, columns, shelves, cabinets | ✅ Full Python API |
| 2 | **Building Tools** | MIT | Floors, walls, roofs, doors, windows — modular buildings | ✅ Full Python API |
| 3 | **BagaPie v11** | Free | Doors, windows, bolts, railings, stairs, ivy, scatter, arrays | ✅ Operator calls |
| 4 | **Buildify** | Free | Geometry Nodes procedural buildings with modular parts | ⚠️ Node graph |
| 5 | **Archimesh custom meshes** | GPL | Table, lamp, stool, bench, shelf, curtain | ✅ Direct operators |
| 6 | **Infinigen Indoors** | Apache 2.0 | Photorealistic procedural interiors (Princeton research) | ⚠️ Heavy setup |
| 7 | **Level Buddy** | Free | CSG-style level building, one-click FBX export | ✅ Operator calls |
| 8 | **Bystedt's Cloth Builder** | Free | Cloaks, curtains, banners, cloth draping on objects | ✅ Sim + export |

### Architecture Detail Levels

| Detail | Source | Example |
|--------|--------|---------|
| **Structural** | Archimesh + Building Tools | Walls, floors, ceilings, roofs, stairs |
| **Openings** | Building Tools + BagaPie v11 | Doors, windows, archways, shutters |
| **Ornamental** | Custom handlers + BagaPie | Columns, railings, cornices, gutters |
| **Surface** | Procedural materials | Stone, timber, plaster, tile textures |
| **Props (interior)** | Tripo API (batch) | Furniture, tableware, tools, books, food |
| **Props (exterior)** | Tripo API (batch) | Signs, lanterns, barrels, crates, flower pots |
| **Cloth** | Bystedt's Cloth Builder | Banners, curtains, awnings, cloaks on mannequins |
| **Nature** | BagaPie ivy + Sapling Tree Gen | Ivy, vines, moss, window box plants |

---

## PART 4: INTELLIGENT PLACEMENT SYSTEM

### Rule-Based Scatter (Terrain-Aware)

Current system uses basic Poisson disk. Need rule-based placement:

```
scatter_intelligent(
    terrain="world_terrain",
    rules=[
        {"asset": "oak_tree", "slope_max": 30, "height_min": 10, "height_max": 200, "near_water": False, "density": 0.3},
        {"asset": "willow_tree", "slope_max": 15, "near_water": True, "water_distance_max": 20, "density": 0.2},
        {"asset": "rock_large", "slope_min": 25, "height_min": 50, "density": 0.1},
        {"asset": "mushroom_cluster", "slope_max": 20, "shade": True, "moisture": "high", "density": 0.5},
        {"asset": "grass_patch", "slope_max": 40, "height_max": 300, "density": 0.8},
        {"asset": "dead_tree", "corruption": True, "corruption_min": 50, "density": 0.2}
    ],
    seed=42
)
```

### Tools for Intelligent Placement

| Tool | Rule Types | Free? | MCP Integration |
|------|-----------|-------|-----------------|
| **OpenScatter** (GPLv3) | Slope, elevation, moisture, texture mask, wind | ✅ | High — operator wrappers |
| **BagaPie** (Free) | Surface scatter, physics-based, array | ✅ | High — operator calls |
| **Gscatter** (Free) | Layer-based masking (height, texture, slope) | ✅ | Medium |
| **Blender Scatter on Surface** (built-in) | Poisson disk, density | ✅ | Very High |
| **Custom corruption rules** | Brand-based (VOID = dead vegetation, VENOM = mutated) | ✅ | Fully custom |

### Placement Categories

| Category | Source | Rule Examples |
|----------|--------|---------------|
| **Trees** | Sapling Tree Gen + OpenScatter | Height bands, slope limits, near-water preference |
| **Undergrowth** | Graswald plants + OpenScatter | Shade preference, moisture dependency |
| **Rocks** | Procedural + Tripo | Slope minimum, height bands, cluster distribution |
| **Buildings** | Archimesh + Building Tools | Road proximity, terrain flatness, district zoning |
| **NPCs** | Tripo (appearance) + MCP placement | Near buildings, patrol routes, gathering points |
| **Props** | Tripo batch | Near buildings (signs), near roads (carts), near water (docks) |
| **Corruption** | Custom brand rules | Corruption % → dead trees, glowing fungi, warped stone, mist |

---

## PART 5: TRIPO BATCH DETAIL STRATEGY

### What Tripo Generates (Small/Medium Assets ONLY)

**Market/Town Props (~40 assets, reusable):**
- Barrel, crate, sack, bucket, wheelbarrow, cart, market stall
- Hanging sign (tavern, blacksmith, apothecary, herbalist)
- Lantern, brazier, torch holder, candlestick
- Well pump, fountain, water trough
- Bench, chair, table (outdoor), fence post
- Flower pot, planter, window box

**Interior Props (~60 assets per room type):**
- Tavern: mug, plate, keg, bar tap, dartboard, broom, mop
- Bedroom: pillow, blanket, chamber pot, mirror, wardrobe
- Kitchen: pot, pan, ladle, cutting board, bread loaf, hanging herbs
- Library: book, scroll, ink well, quill, bookshelf (small)
- Forge: anvil, hammer, tongs, bellows, horseshoe, ingot
- Temple: candelabra, incense burner, offering bowl, prayer mat

**Nature Props (~30 assets):**
- Rock (5 sizes), boulder, pebbles
- Fallen log, tree stump, mushroom cluster
- Gravestone (4 styles), broken wagon, skull

**Corruption-Themed Props (~20 per brand):**
- VOID: floating dark crystals, shadow tendrils, void-cracked stones
- VENOM: mutated mushrooms, toxic puddles, corroded metal
- DREAD: bone piles, fear totems, spectral wisps
- RUIN: cracked pillars, rubble piles, shattered weapons

### Batch Generation Pipeline

```python
# Generate all town props in one batch
tripo_batch_generate(
    prompts=[
        "medieval wooden barrel, dark fantasy, game asset",
        "hanging tavern sign, wrought iron bracket, game asset",
        "stone well with wooden bucket, medieval, game asset",
        # ... 40 more
    ],
    style="dark_fantasy",
    output_dir="Assets/Art/Props/Town/",
    cleanup=True,      # Auto-repair + UV + PBR
    generate_lods=True, # LOD0/LOD1/LOD2
    target_faces=2000   # Game-ready poly budget
)
```

---

## PART 6: AI AGENT EDITABILITY — THE CRITICAL GAP

### Current State: Generate-Only Pipeline

The toolkit can CREATE everything but CANNOT EDIT what it creates. This means AI agents must delete and regenerate instead of adjusting. This is the single biggest workflow gap.

### Edit Handlers Needed (Priority Order)

| # | Handler | What It Enables | Effort |
|---|---------|----------------|--------|
| 1 | **`handle_edit_building`** | Add/remove floors, doors, windows, change roof, wall materials | 16h |
| 2 | **`handle_edit_material`** | Change ANY material property (textures, SSS, IOR, emission, maps) | 8h |
| 3 | **`handle_edit_scatter`** | Adjust density locally, remove instances, change rules in-place | 8h |
| 4 | **`handle_edit_world_layout`** | Reposition buildings/locations, change road connections | 12h |
| 5 | **`handle_edit_interior`** | Rearrange rooms, move furniture, change door positions | 12h |
| 6 | **`handle_edit_animation`** | Modify F-curves, keyframe timing, easing, frame ranges | 8h |
| 7 | **`handle_edit_terrain_region`** | Paint biomes, adjust erosion, blend heights in specific areas | 6h |
| 8 | **`handle_edit_modifiers`** | Add/remove/reorder/tweak modifier parameters | 6h |
| 9 | **`handle_edit_physics`** | Modify cloth stiffness, rigid body friction, particle emission | 4h |
| 10 | **`handle_edit_shape_keys`** | Adjust morph target values, blend shapes, drivers | 4h |

**Total editability work: ~84 hours**

### What AI Agents CAN Already Edit

| System | Create | Edit | Delete | Inspect |
|--------|--------|------|--------|---------|
| Mesh topology | ✅ | ✅ Full | ✅ | ✅ |
| Terrain sculpt | ✅ | ✅ Full | ✅ | ✅ |
| Object transforms | ✅ | ✅ Full | ✅ | ✅ |
| Basic materials (BSDF) | ✅ | ⚠️ Partial | ✅ | ✅ |
| UV mapping | ✅ | ⚠️ Partial | ✅ | ✅ |
| Rigging weights | ✅ | ⚠️ Partial | ✅ | ✅ |

### What AI Agents CANNOT Edit (Must Fix)

| System | Create | Edit | Delete | Inspect | Fix |
|--------|--------|------|--------|---------|-----|
| Buildings post-gen | ✅ | ❌ | ✅ | ✅ | handle_edit_building |
| Interior layouts | ✅ | ❌ | ✅ | ✅ | handle_edit_interior |
| World graph | ✅ | ❌ | ✅ | ✅ | handle_edit_world_layout |
| Scatter density | ✅ | ❌ | ✅ | ✅ | handle_edit_scatter |
| Animation curves | ✅ | ❌ | ❌ | ⚠️ | handle_edit_animation |
| Material textures | ✅ | ❌ | ❌ | ✅ | handle_edit_material |
| Modifier params | ⚠️ | ❌ | ⚠️ | ⚠️ | handle_edit_modifiers |
| Geometry Nodes | ⚠️ | ❌ | ⚠️ | ⚠️ | handle_edit_geonodes |
| Shader nodes | ✅ | ❌ | ❌ | ⚠️ | handle_edit_material |

---

## PART 7: COMPLETE FREE PLUGIN REGISTRY

### ALL Plugins — Verified Free, License Confirmed

**TIER 1: MUST INTEGRATE (Biggest Impact)**

| # | Plugin | License | Category | URL | Status |
|---|--------|---------|----------|-----|--------|
| 1 | Archimesh | GPL | Architecture | Built-in Blender extension | ✅ Free confirmed |
| 2 | Building Tools | MIT | Architecture | github.com/ranjian0/building_tools | ✅ Free confirmed |
| 3 | BagaPie v11 | Free | Architecture/Scatter | extensions.blender.org | ✅ Free confirmed (assets extra) |
| 4 | Sapling Tree Gen | GPL | Vegetation | Built-in Blender extension | ✅ Free confirmed |
| 5 | OpenScatter | GPLv3 | Scatter | github.com/GitMay3D/OpenScatter | ✅ Free confirmed |
| 6 | Principled Baker | Free | Textures | github.com/danielenger/Principled-Baker | ✅ Free confirmed |
| 7 | A.N.T. Landscape | GPL | Terrain | Built-in Blender extension | ✅ Free confirmed |
| 8 | ErosionR | GPL | Terrain | github.com/nerk987/ErosionR | ✅ Free confirmed |
| 9 | Terrain Mixer | Free | Terrain | extensions.blender.org | ✅ Free confirmed |

**TIER 2: HIGH VALUE**

| # | Plugin | License | Category | URL | Status |
|---|--------|---------|----------|-----|--------|
| 10 | Buildify | Free | Architecture | paveloliva.gumroad.com/l/buildify | ✅ Free confirmed |
| 11 | Level Buddy | Free | Level Design | matt-lucas.itch.io/level-buddy | ✅ Free confirmed |
| 12 | Bystedt's Cloth Builder | Free | Cloth/Armor | 3dbystedt.gumroad.com | ✅ Free confirmed |
| 13 | EZ Tree | Apache 2.0 | Vegetation | Open source Python | ✅ Free confirmed |
| 14 | Modeling Cloth | Free | Physics | richcolburn.gumroad.com | ✅ Free confirmed |
| 15 | Easy Terrain Gen v2.1 | Free | Terrain | BlenderArtists | ✅ Free confirmed |
| 16 | BakeLab | Free | Textures | github.com/specoolar/Bakelab-Blender-addon | ✅ Free confirmed |
| 17 | MeshLint | Free | Quality | github.com/rking/meshlint | ✅ Free confirmed |
| 18 | Rigify | GPL | Rigging | Built-in Blender | ✅ Free confirmed |
| 19 | Game Rig Tools | Free | Rigging | toshicg.gumroad.com | ✅ Free confirmed |

**TIER 3: NICE TO HAVE**

| # | Plugin | License | Category | URL | Status |
|---|--------|---------|----------|-----|--------|
| 20 | Sverchok | GPL | Procedural | nortikin.github.io/sverchok | ✅ Free confirmed |
| 21 | Infinigen Indoors | Apache 2.0 | Interiors | github.com/princeton-vl/infinigen | ✅ Free confirmed |
| 22 | Dream Textures | GPL | AI Textures | github.com/carson-katri/dream-textures | ✅ Free (8GB tight) |
| 23 | BlenderGIS | GPL | World Data | github.com/domlysz/BlenderGIS | ✅ Free confirmed |
| 24 | Gscatter | Free | Scatter | gscatter.com | ✅ Free confirmed |
| 25 | UV-Packer | Free | UV | uv-packer.com/blender | ✅ Free confirmed |
| 26 | WFC 3D Generator | Open Source | Level Design | github.com/Primarter/WaveFunctionCollapse | ✅ Free confirmed |
| 27 | Proc City Gen | Open Source | City Layout | github.com/josauder/procedural_city_generation | ✅ MIT license |
| 28 | Animation Retargeting | GPL | Animation | github.com/Mwni/blender-animation-retargeting | ✅ Free confirmed |

**TOTAL: 28 verified free plugins, zero paid requirements**

---

## PART 8: TEXTURE & MATERIAL PIPELINE (COMPLETE)

### The Problem
Procedural Blender materials = beautiful in viewport, blank white on FBX export. This kills the entire Unity pipeline.

### The Fix Pipeline

```
1. Create procedural material (existing handlers — works)
    ↓
2. Auto-bake to images (Principled Baker / BakeLab — NEW)
    → Albedo, Normal, Metallic, Roughness, AO, Emission, Height
    ↓
3. Swap node tree (replace procedural nodes with Image Texture nodes — NEW)
    ↓
4. FBX export with use_tspace=True (existing — needs flag fix)
    ↓
5. Unity auto-import with material remapping (existing — works)
```

### Material Fixes Needed

| Fix | Impact | Effort |
|-----|--------|--------|
| SSS weight 0.15 → 1.0 + Subsurface Scale control | Skin looks real | 30 min |
| Metal base colors → physically-based values | Metals reflect properly | 30 min |
| 3-layer micro-normal (macro/meso/micro bump chain) | Surface detail at all distances | 4h |
| Principled Baker integration | Procedural → image baking | 4h |
| Node tree swap automation | Auto-replace procedural with baked | 6h |
| FBX tspace flag | Normal maps survive export | 15 min |
| Per-material texture resolution control | Hero assets get 2K, props get 512 | 2h |

---

## PART 9: PRIORITIZED IMPLEMENTATION PLAN

### Sprint 1: Foundation Fixes (Days 1-2) — 18 hours
No new plugins. Fix what's broken.

| Task | Hours |
|------|-------|
| SSS weight fix | 0.5 |
| Metal base color fix | 0.5 |
| Wire hand/foot generators | 2 |
| Fix 7 CRITICAL geometry bugs | 7 |
| NumPy-vectorize heightmap | 4 |
| 3-layer micro-normal chain | 4 |

### Sprint 2: Texture Pipeline (Days 3-4) — 15 hours
Integrate Principled Baker + BakeLab, fix export.

| Task | Hours |
|------|-------|
| Principled Baker integration | 4 |
| Node tree swap automation | 6 |
| FBX tspace flag + round-trip verification | 4 |
| Per-material resolution control | 1 |

### Sprint 3: Terrain Revolution (Days 5-8) — 30 hours
Full terrain pipeline.

| Task | Hours |
|------|-------|
| A.N.T. Landscape integration | 2 |
| ErosionR integration | 3 |
| Height-based texture blending | 4 |
| Thermal erosion pass | 4 |
| Multi-pass erosion chaining | 3 |
| Flow map computation | 6 |
| Spline-based terrain deform (roads/rivers) | 8 |

### Sprint 4: Architecture System (Days 9-16) — 64 hours
Build the Bethesda-style modular kit.

| Task | Hours |
|------|-------|
| Archimesh integration (rooms, doors, windows, stairs) | 8 |
| Building Tools integration (floors, walls, roofs) | 8 |
| BagaPie v11 integration (doors, windows, railings, ivy) | 6 |
| Modular kit generator (25 piece types × 5 styles) | 16 |
| Room composer (snap kits → walkable rooms) | 12 |
| Style presets (Gothic, medieval, dark fantasy, corrupted) | 8 |
| Interior decoration by room type | 6 |

### Sprint 5: City Generation (Days 17-22) — 48 hours
Full city builder.

| Task | Hours |
|------|-------|
| Voronoi district zoning | 8 |
| L-system road network generation | 12 |
| Road geometry (cobblestone/dirt surfaces) | 6 |
| City wall + gate generation | 8 |
| Building placement per district rules | 8 |
| Tripo batch detail population | 6 |

### Sprint 6: Intelligent Placement (Days 23-26) — 30 hours
Rule-based everything.

| Task | Hours |
|------|-------|
| OpenScatter integration | 6 |
| BagaPie integration | 4 |
| Terrain-aware rule engine (slope, height, moisture, corruption) | 12 |
| Sapling Tree Gen integration + dark fantasy presets | 4 |
| Wind vertex color baking | 4 |

### Sprint 7: AI Editability (Days 27-34) — 84 hours
Make everything editable through MCP.

| Task | Hours |
|------|-------|
| handle_edit_building (add/remove floors, doors, windows, roof) | 16 |
| handle_edit_material (full property editing + texture assignment) | 8 |
| handle_edit_scatter (local density, instance removal, rule tweaking) | 8 |
| handle_edit_world_layout (reposition, reconnect, add locations) | 12 |
| handle_edit_interior (rearrange rooms, move furniture, swap props) | 12 |
| handle_edit_animation (F-curves, keyframes, easing) | 8 |
| handle_edit_terrain_region (local biome paint, erosion, blending) | 6 |
| handle_edit_modifiers (add/remove/reorder/tweak) | 6 |
| handle_edit_physics (cloth stiffness, rigid body params) | 4 |
| handle_edit_shape_keys (morph values, drivers) | 4 |

### Sprint 8: Quality & Testing (Days 35-38) — 30 hours
Bug scan, test, verify.

| Task | Hours |
|------|-------|
| Full pytest suite (target: 15,000+ tests, 0 failures) | 8 |
| Codex + Gemini bug scan (3 rounds minimum) | 12 |
| Visual verification (Blender screenshots of generated cities) | 4 |
| Unity import verification (full round-trip) | 6 |

---

## GRAND TOTAL

| Sprint | Days | Hours | What You Get |
|--------|------|-------|-------------|
| 1: Foundation Fixes | 1-2 | 18h | Working meshes, fast terrain, real skin |
| 2: Texture Pipeline | 3-4 | 15h | Textures that survive export |
| 3: Terrain Revolution | 5-8 | 30h | Skyrim-quality terrain with erosion |
| 4: Architecture System | 9-16 | 64h | Walkable buildings with interiors |
| 5: City Generation | 17-22 | 48h | Full cities with roads and districts |
| 6: Intelligent Placement | 23-26 | 30h | Rule-based scatter like Bethesda |
| 7: AI Editability | 27-34 | 84h | Edit EVERYTHING through MCP |
| 8: Quality & Testing | 35-38 | 30h | Bug-free, verified, ready to ship |
| **TOTAL** | **38 days** | **319h** | **AAA procedural city builder** |

---

## SKYRIM FEATURES CROSS-CHECK (Did We Miss Anything?)

| Skyrim Feature | Our Coverage | Status |
|---------------|-------------|--------|
| Heightmap terrain with LOD | ✅ NumPy terrain + chunking | Planned |
| Hydraulic/thermal erosion | ✅ Multi-pass + ErosionR | Planned |
| Height-based texture blending | ✅ Per-pixel height compare | Planned |
| Grass billboard instancing | ✅ OpenScatter + GPU instancing | Planned |
| L-system trees with leaf cards | ✅ Sapling Tree Gen | Planned |
| Modular building kits | ✅ 25 pieces × 5 styles | Planned |
| Walkable interiors | ✅ Archimesh rooms | Planned |
| Interior cell streaming | ✅ unity_world create_interior_streaming | Already exists |
| NavMesh baking | ✅ unity_scene bake_navmesh | Already exists |
| Dynamic weather | ✅ unity_world create_weather | Already exists |
| Day/night cycle | ✅ unity_world create_day_night | Already exists |
| Water system | ✅ blender_environment create_water + Unity water shader | Already exists |
| LOD system | ✅ setup_lod_groups + generate_lods | Already exists |
| Occlusion culling | ✅ setup_occlusion | Already exists |
| Post-processing (bloom, AO, fog) | ✅ setup_post_processing | Already exists |
| Volumetric fog/god rays | ✅ create_deep_environmental_vfx | Already exists |
| Radiant AI (NPC schedules) | ❌ Not in scope (runtime AI) | Game code, not toolkit |
| Radiant Story (dynamic quests) | ❌ Not in scope (runtime) | Game code, not toolkit |
| Havok physics (ragdoll) | ✅ setup_ragdoll + Unity physics | Already exists |
| Combat system | ✅ Full 10-brand system | Already exists in VeilBreakers3D |

**Verdict: Every Skyrim feature that's within toolkit scope is either already built or planned. The only missing features (Radiant AI/Story) are runtime game logic, not asset pipeline tools.**

---

## SCOPE VERIFICATION: NOTHING REMAINING

### Architecture ✅
- Modular kits: 25 pieces × 5 styles
- Room generation: Archimesh + WFC
- Building assembly: Building Tools + BagaPie
- Interior decoration: Tripo batch + procedural furniture
- Style presets: Gothic, medieval, dark fantasy, corrupted

### Textures ✅
- Procedural creation: 45+ materials
- Baking pipeline: Principled Baker + BakeLab
- Export: FBX with tspace
- AI generation: Dream Textures (optional, 8GB tight)

### 3D Modeling ✅
- Characters: Tripo + Skin Modifier + sculpt
- Props: Tripo batch
- Buildings: Procedural (NOT Tripo)
- Terrain: Procedural
- Vegetation: Sapling Tree Gen + L-system

### Map Design ✅
- City layout: Voronoi districts + L-system roads
- World graph: MST-connected locations
- Dungeon layout: WFC + BSP
- Terrain: Multi-pass erosion + height blending

### Intelligent Placement ✅
- Slope/height/moisture rules: OpenScatter
- Biome-driven: Custom corruption rules
- Interior decoration: Room-type templates
- City zoning: District-based building rules

### Terrain ✅
- Generation: NumPy-vectorized noise + A.N.T. Landscape
- Erosion: Hydraulic + Thermal + Multi-pass + ErosionR
- Blending: Height-based per-pixel
- Features: Flow maps, spline deform, stamps
- Sculpting: Coordinate-based brush math
- Export: Chunked for streaming

### AI Editability ✅
- 10 edit handlers covering every major system
- Full CRUD on all generated assets
- No more delete-and-regenerate workflow

### All Plugins Free ✅
- 28 plugins verified, zero paid requirements
- All <8GB VRAM
- All automatable via Python/MCP

---

*DEFINITIVE ROADMAP v7.0 — 2026-03-27*
*28 free plugins, 319 hours, 8 sprints, full city generation pipeline*
*Target: Skyrim/Fable-competitive dark fantasy RPG toolkit*
