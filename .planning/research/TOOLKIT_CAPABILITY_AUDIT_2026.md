# VeilBreakers Toolkit Capability Audit

**Date:** 2026-04-01
**Purpose:** Full inventory of what we can do vs what we're actually using

---

## UNUSED CAPABILITIES (High-Impact, Already Built)

### Visual Quality (NEVER CALLED)
| Module | What It Does | Why It Matters |
|--------|-------------|----------------|
| visual_validation.py | Scores screenshots: brightness, contrast, edges, entropy, color | AAA quality gate — auto-reject bad-looking output |
| screenshot_diff.py | Pixel-level regression detection between screenshots | Catch visual regressions when modifying generators |
| handle_run_quality_checks | Mesh quality: verts, UVs, materials, texture presence | Already wired but not enforced in pipeline |

### Generators (EXIST but disconnected)
| Generator | Location | What It Does | Status |
|-----------|----------|-------------|--------|
| generate_battlements() | building_quality.py:2465-2758 | Full battlement system: machicolations, murder holes, arrow slits, 3 merlon styles | NEVER called by castle |
| vegetation_leaf_cards | blender_quality | SpeedTree-style leaf card generation | EXISTS, unused on trees |
| trim_sheet | blender_quality | Shared texture atlas generation | EXISTS, unused on buildings |
| smart_material | blender_quality | Automated PBR material creation | Available |
| macro_variation | blender_quality | Large-scale detail variation | Available |
| env_generate_canyon | environment handlers | Canyon generation | EXISTS |
| env_generate_cliff_face | environment handlers | Cliff face mesh generation | EXISTS |
| env_generate_waterfall | environment handlers | Waterfall geometry | EXISTS |
| env_generate_coastline | environment handlers | Coastline generation | EXISTS |
| env_generate_swamp_terrain | environment handlers | Swamp-specific terrain | EXISTS |

### Mesh Operations (Available, Underused)
| Operation | What It Does | Use Case |
|-----------|-------------|----------|
| sculpt_brush (32 types) | Grab, smooth, crease, draw, inflate, etc. | Detail rocks, terrain micro-features |
| dyntopo | Dynamic topology sculpting | Organic rock shapes, terrain detail |
| voxel_remesh | Voxel-based remeshing | Clean up boolean results |
| bake_curvature | Curvature map baking | Drive roughness variation |
| bake_ao | Ambient occlusion baking | Drive cavity dirt |
| bake_normals | Normal map from high-poly | Detail transfer |
| generate_wear | Procedural wear/weathering maps | Age buildings, props |
| enhance_geometry | AAA geometry enhancement pipeline | Level up any mesh |

### Texture/Material (Available, Underused)
| Operation | What It Does |
|-----------|-------------|
| texture inpaint | AI texture inpainting (Stable Diffusion) |
| texture upscale | 4x RealESRGAN upscaling |
| make_tileable | Tiling correction + seam blending |
| delight | Remove lighting from textures |
| weathering_mix | Blend weathering onto existing textures |
| create_biome_terrain | Biome-specific terrain materials |

---

## WIRED AND WORKING

### Terrain
- Perlin noise terrain with multi-octave FBM (lacunarity/persistence)
- Hydraulic + Thermal + Both erosion modes
- Bilinear height interpolation (PR #17)
- 150K+ erosion droplets (PR #17)
- River carving with visible road mesh (PR #17)
- Terrain flattening under buildings (PR #17)
- Multi-biome world generation with transition zones

### Vegetation
- 6 L-system tree species (oak/pine/birch/willow/dead/ancient)
- Wind vertex color baking (R/G/B/A channels)
- Impostor generation
- GPU instancing support
- Biome-aware scatter with 7 presets
- Building exclusion zones (PR #17)
- Slope-aligned placement (PR #17)

### Buildings & Settlements
- 10 settlement types with layout patterns (organic/grid/circular/concentric)
- 20+ building presets with multi-floor interiors
- Road network generation + lot subdivision
- Interior quality tiers: luxury/standard/poor/abandoned/ransacked (PR #17)
- Auto UV unwrap + mesh repair on buildings (PR #17)
- Foundation profiles for sloped sites (PR #17)

### Combat
- 8 encounter templates (ambush, arena, gauntlet, siege, puzzle, etc.)
- Boss arena with cover geometry, hazard zones, fog gates
- Sightline verification, spacing checks, reachability analysis

### Quality
- A-F topology grading with disconnected component + degenerate face detection (PR #17)
- Game-ready check with re-validation loop (PR #17)
- Watertight mesh verification (PR #17)

---

## WHAT WE NEED TO BUILD (from research)

### Immediate (Wire existing code)
1. Wire generate_battlements() into castle pipeline
2. Wire vegetation_leaf_cards into tree generation
3. Wire trim_sheet into building material pipeline
4. Wire visual_validation into post-generation checks
5. Wire bake_curvature → roughness map pipeline
6. Wire generate_wear into building/prop aging

### Short-term (New implementations using existing tools)
7. Multi-angle AAA verification protocol (8+ angles, auto-score, auto-reject)
8. Multi-pass vegetation scatter (trees → grass → debris)
9. Biome-specific grass variants (6 types with LOD)
10. Non-blocky rock generation (sculpt_brush + dyntopo)
11. Combat clearing generation within dense forests
12. Market square + gathering space generation
13. Concentric castle walls (2-3 rings)

### Medium-term (New algorithms)
14. Hatchling's fast erosion (100-300ms for 1024x1024)
15. Ruinify post-processor (blockout → detailed ruins)
16. Canyon/valley river systems with water mesh
17. Mountain silhouette generation (ridge lines, saddle points)
18. Cliff face strata (layered rock with overhangs)
19. Shore blending (depth-based alpha + foam)

### Long-term (AI-powered)
20. Terrain Diffusion heightmap generation
21. TerraFusion height + texture simultaneous generation
22. LLM-driven layout generation (text → structured world data)
23. Growth-graph vegetation (Natsura-style)
24. Hierarchical Chunked WFC for infinite worlds
