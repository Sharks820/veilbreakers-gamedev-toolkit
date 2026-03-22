# V5 Gap Analysis: Character & Visual Quality (Opus Agent 3/3)

## Summary: 46 gaps, 8 CRITICAL, 20 HIGH

### CRITICAL (8) — Must fix for any shipped content
1. VQ-001: NPC bodies are mannequins (2-4K tris vs 20-50K needed)
2. VQ-002: Zero edge loops at joints for animation deformation
3. VQ-003: No facial topology (eyes/mouth are bumps on sphere)
4. VQ-007: No subdivision surface workflow (faceted geometry)
5. VQ-017: Eyes are placeholder spheres (no cornea/iris/pupil)
6. VQ-021: No facial blend shapes (mesh can't support them)
7. VQ-025: Monster bodies are primitive assemblages (cylinder+sphere+box visible)
8. VQ-041: No mesh smoothing after assembly (hard edges at junctions)

### KEY INSIGHT
> "The Unity rendering side is significantly ahead of the Blender generation side. The shaders exist to render AAA-quality characters, but the Blender geometry generators produce primitive-grade meshes that cannot leverage those shaders."

### Most Impactful Fixes (in order):
1. Replace cylinder/sphere assembly with bmesh quad-cage + subdivision surface
2. Add automatic voxel remesh + smooth pass after monster body generation
3. Set SSS/transmission/anisotropic on existing material presets (~30 min fix)
4. Generate separate eye mesh geometry + material slots per body region
5. Integrate LOD pipeline into body generation flow

### Quick Wins (LOW complexity, immediate quality boost):
- VQ-036: Add Transmission to leaf/membrane materials (1 line per preset)
- VQ-038: Add Anisotropic to hair/metal materials (1 line per preset)
- VQ-039: Add Coat Weight to lacquer/chitin materials (1 line per preset)
- VQ-040: Add Subsurface Weight to skin/snow/mushroom materials (1 line per preset)

### Texture Gaps (8):
- No UDIM multi-tile UV for heroes
- No Substance Painter workflow
- No detail normal maps (pores, weave)
- No SSS thickness maps
- No trim sheet workflow
- No decal projection system
- No texture atlasing pipeline
- Limited bake types (missing curvature, thickness, position, ID)

### Monster Quality Gaps (7):
- Primitive assemblage look
- Brand features glued on (no organic transition)
- No geometric surface detail (scales, chitin, fur are material-only)
- Poor silhouette variety
- No evolution visual progression
- No damage states
- Boss monsters have no visual presence differentiation
