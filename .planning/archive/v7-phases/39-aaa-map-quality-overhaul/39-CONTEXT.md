# Phase 39: AAA Map Quality Overhaul — Context

## Phase Goal
Wire all disconnected generators, fix broken geometry, implement multi-angle visual verification, upgrade terrain/vegetation/water/castle/settlement systems to AAA quality. The generated map must pass alpha-test quality bar for a dark fantasy action RPG with functional combat zones, explorable interiors, and mob spawning.

## Current State (Visual Audit 2026-04-01)

### Broken Items
- Exploded buildings NE of castle (roofs floating at wild angles, white cylinder chimney bug)
- Navy-blue ground at street level (cobblestone material not rendering)
- No water surface mesh (dark disc placeholder)
- PR #17 duplicate `elif` syntax error (FIXED in commit 0b9bee6)
- Biome colors were near-black linear values (FIXED — now PBR-correct)

### Visual Quality Gaps
- Trees = UV sphere blobs (103 identical cauliflower copies)
- Terrain = 2-3 flat color zones with jagged transitions
- Walls = featureless gray slabs, single material everywhere
- No grass or ground cover anywhere
- Buildings = same tan roof, same gray walls, no variety
- Roads barely visible from above
- No market square or gathering spaces
- Castle = single wall ring, no battlements despite code existing

## Existing Capabilities (UNUSED — must wire)

| Generator | File | What It Does | Status |
|-----------|------|-------------|--------|
| generate_battlements() | building_quality.py:2465-2758 | Machicolations, murder holes, arrow slits, 3 merlon styles | NEVER called by castle |
| vegetation_leaf_cards | blender_quality | SpeedTree-style leaf card generation | EXISTS, unused |
| trim_sheet | blender_quality | 2048x2048 shared texture atlas | EXISTS, unused |
| smart_material | blender_quality | Automated PBR from material tables | EXISTS, unused |
| macro_variation | blender_quality | Large-scale detail variation | EXISTS, unused |
| visual_validation.py | shared/ | Scores brightness/contrast/edges/entropy/color | EXISTS, NEVER CALLED |
| screenshot_diff.py | shared/ | Pixel-level regression detection | EXISTS, NEVER CALLED |
| bake_curvature | mesh_enhance.py | Curvature map → roughness variation | Available |
| bake_ao | mesh_enhance.py | AO → cavity dirt maps | Available |
| generate_wear | texture.py | Procedural weathering maps | Available |
| env_generate_canyon | environment handlers | Canyon generation | EXISTS |
| env_generate_cliff_face | environment handlers | Cliff face mesh | EXISTS |
| env_generate_waterfall | environment handlers | Waterfall geometry | EXISTS |
| env_generate_coastline | environment handlers | Coastline generation | EXISTS |
| generate_boss_arena | worldbuilding | Boss encounter arena | EXISTS, WIRED |
| encounter_spaces | worldbuilding | 8 encounter templates | EXISTS, WIRED |
| sculpt_brush (32 types) | mesh.py | Grab/smooth/crease/draw etc. | Available for rock detail |

## Research Documents (extensive, already completed)

1. `.planning/research/PROCEDURAL_3D_AAA_SPECS.md` — 1011 lines: terrain, architecture, vegetation, PBR materials, towns, castles, water, performance budgets
2. `.planning/research/CUTTING_EDGE_PROCEDURAL_2025.md` — Terrain diffusion, Hatchling's fast erosion, Infinigen, Natsura growth graphs, WFC variants, LLM-driven layout
3. `.planning/research/TOOLKIT_CAPABILITY_AUDIT_2026.md` — Full inventory of 16 MCP tools, 162 actions, 114 handler files, wired vs unwired status
4. `.planning/research/AAA_GAMEPLAY_AREA_DESIGN_SPECS.md` — Boss arenas (8 shapes, 5 sizes), mob zones (5 patrol types, 8 density tiers), settlement mapping, dungeon entrances, POI spacing
5. `.planning/research/TERRAIN_SCULPTING_AAA_TECHNIQUES.md` — Ridged multifractal noise, rock strata, canyon generation, river meanders, micro-detail, auto-splatting

## Key Specs From Research

### PBR Material Values (physicallybased.info)
- Granite dark: sRGB(90,85,75) R:0.6-0.85
- Granite light: sRGB(180,170,155) R:0.7-0.9
- Oak: sRGB(190,160,115) R:0.6-0.85
- Thatch: sRGB(175,155,95) R:0.85-1.0
- Iron: sRGB(135,131,126) R:0.5-0.8 metallic=1.0
- Non-metal albedo: NEVER below sRGB 30, NEVER above sRGB 240

### Performance Budget
| Element | Tri Budget | Draw Calls |
|---------|-----------|------------|
| Terrain | 200K | 4-8 |
| Buildings (x30) | 300K | 30-50 |
| Walls/Castle | 150K | 10-20 |
| Trees (x100) | 400K | 5-10 (instanced) |
| Grass | 300K | 2-4 (instanced) |
| Rocks/Props (x200) | 200K | 10-20 (instanced) |
| Water | 20K | 1-2 |
| **TOTAL** | **~1.6M** | **~130** |

### Boss Arena Dimensions
- Small (duel): 20-30m diameter, 315-710m² floor
- Medium (standard): 40-60m diameter, 1260-2830m²
- Large (dragon): 80-120m diameter, 5000-11310m²
- Cover: 3-6 pillars/obstacles, 8-15m spacing
- Entrance: 3-4m wide chokepoint, fog gate locks behind player

### Vegetation Specs
- Tree LOD chain: LOD0 3K-10K tris, LOD1 1K-4K, LOD2 cards 100-600, LOD3 billboard 2-8
- Grass: 3-6 tris/tuft, 8-16 tufts/m² medium quality, LOD at 20/50/80m
- Wind vertex colors: R=flutter, G=phase, B=amplitude, A=trunk_sway
- 6 biome grass types: prairie(0.5-1.2m), forest(0.1-0.3m), swamp(0.8-2.0m), mountain(0.05-0.15m), corrupted(blackened), dead(brown)

### Settlement Layout
- Road hierarchy: main 5-6m, secondary 3-4m, alley 1.5-2m
- District zoning: market(center), residential(near castle), common(mid), military(near walls), religious(near center), slums(edge)
- Market square: 400-2500m², at major road intersection
- Building density: urban core 80-90%, suburbs 40-60%

### Castle Specs
- Concentric: Ring 1 height 6-8m, Ring 2 10-12m, Ring 3 12-16m
- Tower spacing: 25-40m, diameter 4-8m
- Gatehouse: 3-4m wide passage, 8-15m deep, portcullis + murder holes
- Merlons: 0.5m wide x 1.0m tall, 0.4m gaps

### Water Specs
- Spline-based river mesh, 8-16 cross-section subdivisions
- Shore blending: depth-based alpha, foam where depth<0.2m
- Flow vertex colors: R=speed, G=flow_dir_X, B=flow_dir_Z, A=foam

## Test Requirements (User Explicit)
- 50+ procedural generation tests (terrain, vegetation, buildings, encounters)
- 20+ visual quality tests (material validation, geometry checks, floating detection)
- 10+ functional gameplay tests (NPC pathing, mob spawning, interior exploration)
- Visual verification from EVERY angle before any AAA quality claim

## Files to Modify
- `blender_addon/handlers/_terrain_noise.py` — biome rules (DONE), add ridged multifractal
- `blender_addon/handlers/environment.py` — terrain, road, water surface mesh
- `blender_addon/handlers/environment_scatter.py` — multi-pass scatter, grass cards, combat clearings
- `blender_addon/handlers/worldbuilding.py` — castle battlements, concentric walls, market square, boss arena wiring
- `blender_addon/handlers/worldbuilding_layout.py` — district zoning, lot subdivision
- `blender_addon/handlers/building_quality.py` — wire generate_battlements()
- `blender_addon/handlers/vegetation_lsystem.py` — leaf card integration
- `blender_addon/handlers/mesh_enhance.py` — curvature→roughness pipeline
- `src/veilbreakers_mcp/blender_server.py` — AAA verification action, compose_map upgrades
- `src/veilbreakers_mcp/shared/visual_validation.py` — wire into pipeline
- `tests/` — 80+ new tests
