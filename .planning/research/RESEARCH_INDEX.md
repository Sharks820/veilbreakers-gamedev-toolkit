# Research Index — v9.0 Terrain & World Generation Overhaul

**IMPORTANT FOR ALL GSD AGENTS**: Before planning or executing ANY phase, read this index and load the relevant research docs. These contain exact measurements, algorithms, and best practices that MUST be followed.

---

## How to Use This Index

1. Find your phase/topic below
2. Read ALL listed research docs before writing code
3. Follow the specific rules in each doc (smootherstep, PBR values, geological patterns, etc.)
4. After implementation, verify against the research criteria

---

## Global Rules (Apply to ALL phases)

| Rule | Source Doc | Key Detail |
|------|-----------|------------|
| Smootherstep for ALL transitions | `TERRAIN_MESHING_TECHNIQUES.md` | `6t^5 - 15t^4 + 10t^3` — no linear interpolation at ANY terrain boundary |
| PBR accuracy | `AAA_TEXTURE_TOPOLOGY_QUALITY.md` | Stone roughness 0.7-0.95, metallic=0.0 for non-metals, base_color energy 0.02-0.95 |
| Z placement | Design spec Section 5 | Use `_sample_scene_height()` — NEVER hardcode Z=0 |
| Water exclusion | `TERRAIN_FEATURE_VISUAL_DETAILS.md` | No vegetation/props within 2m of water unless waterplant/reed |
| Object embedding | `TERRAIN_FINAL_POLISH.md` | Sink rocks 10-30%, props 2-5% into terrain surface |
| Density noise | `TERRAIN_FINAL_POLISH.md` | Perlin modulator 0.3x-1.5x on ALL scatter to break uniform spacing |

---

## Phase → Research Doc Mapping

### Phase 1: Terrain Mesh Quality
| Doc | What to read for |
|-----|-----------------|
| `AAA_PROCEDURAL_TERRAIN_RESEARCH.md` | Erosion algorithms, heightmap resolution standards |
| `TERRAIN_MESHING_TECHNIQUES.md` | Smootherstep transitions, hybrid cliff meshes, biome blending (jittered sparse convolution) |
| `TERRAIN_FEATURE_VISUAL_DETAILS.md` | Exact measurements: bank angles (5-15° inner, 60-90° outer), meander wavelength (11x width), clearing sizes |
| `TERRAIN_TRANSITION_BEST_PRACTICES.md` | Micro-undulation, bridge approaches, ford crossings |
| `SPLINE_TERRAIN_DEFORMATION.md` | Algorithm for spline→terrain vertex deformation, KDTree indexing, cross-section profiles |
| `TERRAIN_FINAL_POLISH.md` | Terrain skirt geometry, detail normals |

### Phase 2: Terrain Materials & Texturing
| Doc | What to read for |
|-----|-----------------|
| `AAA_TERRAIN_TEXTURING_RESEARCH.md` | Multi-layer shaders, bake pipeline, Blender 4.0 API fixes |
| `AAA_TEXTURE_TOPOLOGY_QUALITY.md` | Height-based blending, macro variation, tri-planar mapping, curvature wear, PBR rules |
| `BIOME_VISUAL_REFERENCE_GUIDE.md` | 13 biome visual rules: colors, textures, vegetation patterns, dark fantasy twist |
| `WEB_RESEARCH_TERRAIN_PIPELINE.md` | Pexels API → color extraction → biome auto-generation |
| `WATER_ROCK_INTERACTION_DESIGN.md` | Wet rock PBR formulas (Lagarde): darken albedo, reduce roughness |

### Phase 3: Water System
| Doc | What to read for |
|-----|-----------------|
| `TERRAIN_FEATURE_VISUAL_DETAILS.md` | River bank profiles, stream sinuosity, lake shoreline fractal dimension |
| `WATER_ROCK_INTERACTION_DESIGN.md` | Rapids, waterfall pools, wet/dry transitions, rock placement in water |
| `TERRAIN_MESHING_TECHNIQUES.md` | River channel spline carving, natural bank profiles |
| `SPLINE_TERRAIN_DEFORMATION.md` | River cross-section profiles (symmetric channel, asymmetric meander) |

### Phase 4: Scatter Engine
| Doc | What to read for |
|-----|-----------------|
| `TERRAIN_FINAL_POLISH.md` | Density noise modulation, object embedding depth |
| `BOULDER_ROCK_FORMATION_DESIGN.md` | Geological scatter patterns (Pareto distribution, burial depth, moss placement) |
| `TERRAIN_TRANSITION_BEST_PRACTICES.md` | Audio surface type tagging for footstep sounds |
| `TERRAIN_AUDIO_SYSTEM.md` | Surface type metadata for audio zones |

### Phase 5: Vegetation
| Doc | What to read for |
|-----|-----------------|
| `BIOME_VISUAL_REFERENCE_GUIDE.md` | Per-biome vegetation species, density, dark fantasy varieties |
| `AAA_TEXTURE_TOPOLOGY_QUALITY.md` | Tree bark materials, leaf SSS, topology rules for deformables |
| `RIGGABLE_PHYSICS_MESH_QUALITY.md` | Flag/cloth topology (quad grid), wind physics, cloth-to-bone bake |

### Phase 6: Castle/Settlement Architecture
| Doc | What to read for |
|-----|-----------------|
| `AAA_PROCEDURAL_CITY_TERRAIN_BEST_PRACTICES.md` | Modular kit systems, FromSoftware foundations, Skyrim approach, silhouette rules |
| `AAA_TEXTURE_TOPOLOGY_QUALITY.md` | 1-segment bevels for specular, multi-zone facade materials |
| `CLIFF_CAVE_CANYON_DESIGN.md` | Castle-cliff integration, defensive positioning on terrain |
| `MOUNTAIN_PASS_CANYON_DESIGN.md` | Castle approach terrain, defensive terrain shaping |

### Phase 7: Enterable Interiors
| Doc | What to read for |
|-----|-----------------|
| `RIGGABLE_PHYSICS_MESH_QUALITY.md` | Door topology (200-500 tris), hinge rigging, curtains, window coverings |
| `AAA_PROCEDURAL_CITY_TERRAIN_BEST_PRACTICES.md` | Interior lighting, room layout standards |

### Phase 8: Roads & Paths
| Doc | What to read for |
|-----|-----------------|
| `SPLINE_TERRAIN_DEFORMATION.md` | Road cross-section profiles (crown, ditch, embankment), terrain deformation algorithm |
| `TERRAIN_TRANSITION_BEST_PRACTICES.md` | Bridge approach terrain, ford crossings |
| `MOUNTAIN_PASS_CANYON_DESIGN.md` | Switchback trail generation (quadratic cost function in A*) |

### Phase 9: Veil Corruption
| Doc | What to read for |
|-----|-----------------|
| `BIOME_VISUAL_REFERENCE_GUIDE.md` | Corruption visual effects per biome |
| `TERRAIN_TRANSITION_BEST_PRACTICES.md` | Corruption terrain warping (geometry vs shader) |

### Phase 10: World Traversal
| Doc | What to read for |
|-----|-----------------|
| `CLIFF_CAVE_CANYON_DESIGN.md` | Cave entrance geometry, cliff-terrain integration |
| `MOUNTAIN_PASS_CANYON_DESIGN.md` | Mountain pass generation, canyon traversal |
| `TERRAIN_TRANSITION_BEST_PRACTICES.md` | Bridge approach terrain, tunnel geometry |

### Phase 11: Zones & Encounters
| Doc | What to read for |
|-----|-----------------|
| `TERRAIN_FEATURE_VISUAL_DETAILS.md` | Clearing dimensions (10-30m), edge undergrowth density |
| `TERRAIN_FINAL_POLISH.md` | Player navigation aids, landmark visibility |

### Phase 12: Per-Biome Atmosphere
| Doc | What to read for |
|-----|-----------------|
| `BIOME_VISUAL_REFERENCE_GUIDE.md` | Per-biome fog, lighting, particle rules |
| `TERRAIN_AUDIO_SYSTEM.md` | Per-biome ambient audio, weather audio |

### Phase 13: Pipeline (Blender→Unity)
| Doc | What to read for |
|-----|-----------------|
| `AAA_TERRAIN_TEXTURING_RESEARCH.md` | Bake pipeline, Unity URP material mapping |
| `RIGGABLE_PHYSICS_MESH_QUALITY.md` | FBX can't export vertex animation — cloth-to-bone bake required |
| `TERRAIN_AUDIO_SYSTEM.md` | Audio metadata export format |

### Cliff/Rock/Mountain Features (cross-phase)
| Doc | What to read for |
|-----|-----------------|
| `CLIFF_CAVE_CANYON_DESIGN.md` | Cliff strata, cave mouths, canyon walls |
| `BOULDER_ROCK_FORMATION_DESIGN.md` | Boulder generation (convex hull, not icosphere), formation types, wet/dry materials |
| `MOUNTAIN_PASS_CANYON_DESIGN.md` | Ridge-cut algorithm, altitude materials, cliff-ledge-slope rhythm |
| `WATER_ROCK_INTERACTION_DESIGN.md` | Rocks in water, rapids, waterfall enhancement |

---

## Research Docs Master List

1. `AAA_PROCEDURAL_CITY_TERRAIN_BEST_PRACTICES.md` — GDC techniques, modular kits, settlement growth
2. `AAA_PROCEDURAL_TERRAIN_RESEARCH.md` — Erosion, rivers, foundations, LOD
3. `AAA_TERRAIN_TEXTURING_RESEARCH.md` — Shaders, bake pipeline, Blender 4.0 fixes
4. `AAA_TEXTURE_TOPOLOGY_QUALITY.md` — Height blending, macro variation, PBR rules, bevels
5. `BIOME_VISUAL_REFERENCE_GUIDE.md` — 13 biomes with complete visual rules
6. `BOULDER_ROCK_FORMATION_DESIGN.md` — Procedural rocks, formations, wet/dry materials
7. `CANONICAL_PIPELINE_DESIGN.md` — 21-step pipeline architecture
8. `CLIFF_CAVE_CANYON_DESIGN.md` — Strata layering, cave mouths, canyon walls
9. `MOUNTAIN_PASS_CANYON_DESIGN.md` — Ridge-cut, switchbacks, altitude materials
10. `RIGGABLE_PHYSICS_MESH_QUALITY.md` — Doors, chains, cloth, flags, export rules
11. `SPLINE_TERRAIN_DEFORMATION.md` — Algorithm, KDTree, cross-section profiles
12. `TERRAIN_AUDIO_SYSTEM.md` — Footsteps, wind, rain, audio zones (IN PROGRESS)
13. `TERRAIN_FEATURE_VISUAL_DETAILS.md` — Exact measurements for 8 terrain features
14. `TERRAIN_FINAL_POLISH.md` — Density noise, skirts, embedding, detail normals
15. `TERRAIN_MESHING_TECHNIQUES.md` — Smootherstep, hybrid cliffs, spline integration
16. `TERRAIN_TRANSITION_BEST_PRACTICES.md` — 14 transition gaps, micro-undulation, audio tags
17. `WATER_ROCK_INTERACTION_DESIGN.md` — Wet PBR, hydrology placement, spray zones
18. `WEB_RESEARCH_TERRAIN_PIPELINE.md` — Pexels API → auto biome generation
