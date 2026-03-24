# AI Interior/Room 3D Generation Research

**Date**: 2026-03-24
**Goal**: Find AI tools that generate walkable 3D interiors (rooms with walls, floors, ceilings, furniture)

---

## Executive Summary

**UPDATE: Two viable options found. One available now (World Labs Marble), one incoming (Meta WorldGen).**

The field splits into four categories:
1. **Cloud room generators** (World Labs Marble) - generates full 3D rooms, exports GLB mesh (600K tris), available NOW as SaaS
2. **Research mesh generators** (Text2Room, Ctrl-Room, ControlRoom3D, SceneCraft) - output real meshes but need 12-16GB+ VRAM, have quality issues
3. **LLM-driven scene assembly** (Holodeck, ProcTHOR) - arrange existing 3D assets in rooms using AI planning
4. **Neural rendering** (Google Genie 3) - walkable worlds but NOT exportable to mesh
5. **Upcoming** (Meta WorldGen) - game-engine-native meshes WITH navmeshes, up to 50x50m. Not yet released.

**Recommended approach**:
- **Immediate**: World Labs Marble for hero interior rooms → export GLB → import to Blender → cleanup/retexture with dark fantasy PBR
- **Bulk/layout**: compose_interior pipeline (procedural room shells + Tripo furniture)
- **Watch**: Meta WorldGen for potential 2026 release

---

## Tools Analyzed

### 0a. World Labs Marble -- AVAILABLE NOW, BEST OPTION
- **What**: Full 3D environment generation from text/image/panorama. Generates rooms with walls, floors, ceilings, furniture.
- **Output**: GLB mesh (~600K tris with textures) + separate collider mesh (3-4 MB). Also exports Gaussian splats.
- **Game-ready?**: Partially. Real triangulated geometry with textures, but needs retopo/retexture for production. High-quality mesh takes up to 1 hour, 100-200 MB.
- **VRAM**: Cloud-based (no local GPU needed). Unity import tested at 1.3 GB VRAM for 6.1M splat scene on RTX 3070.
- **Open Source**: No. Commercial SaaS (freemium).
- **Quality**: Good for blockouts and stylized environments. "Chisel" editor lets you define wall/room layouts before generation. Supports fantasy, sci-fi, cartoon, realistic styles.
- **Integration**: Exports to Unity (GLB), Unreal, Blender.
- **VeilBreakers workflow**: Generate room in Marble → export GLB → import_model to Blender → repair/retopo → re-UV → dark fantasy PBR retexture → export to Unity
- **Sources**: https://www.worldlabs.ai/blog/marble-world-model, https://docs.worldlabs.ai/marble/export/mesh

### 0b. Meta WorldGen -- NOT YET AVAILABLE, BEST FUTURE OPTION
- **What**: Full walkable 3D environments up to 50x50m from text prompts. Includes interior rooms.
- **Output**: Standard textured meshes (not splats) + navmesh. Directly compatible with Unity/Unreal.
- **Game-ready?**: Yes, by design. The ONLY system designed for game-engine-native output with navigation meshes.
- **Pipeline**: LLM layout planning → scene reconstruction → scene decomposition (extractable objects) → per-object refinement via AssetGen2.
- **Status**: Research paper only (arXiv:2511.16825, Nov 2025). Meta says production version may arrive in 2026.
- **Quality**: Demonstrated medieval villages, indoor rooms. Objects individually decomposable and editable.
- **Limitations**: Max 50x50m. ~5 minutes per scene.
- **Sources**: https://arxiv.org/abs/2511.16825, https://www.meta.com/blog/worldgen-3d-world-generation-reality-labs-generative-ai-research/

### 1. Text2Room (ICCV 2023)
- **What**: Generates textured 3D room meshes from text prompts
- **Output**: PLY meshes (NOT game-ready, needs conversion to FBX/GLB)
- **VRAM**: 12-16GB+ (runs Stable Diffusion + depth estimation + Pytorch3D simultaneously)
- **Quality**: Known issues with holes, seam artifacts, repetitive objects (e.g., multiple cabinets)
- **Export**: PLY only - not supported by Unity/Unreal natively
- **Open Source**: Yes - github.com/lukasHoel/text2room
- **Verdict**: Research quality. Not viable on 8GB VRAM. Mesh quality not game-ready.
- **Source**: https://arxiv.org/abs/2303.11989

### 2. Ctrl-Room (3DV 2025)
- **What**: Improvement over Text2Room with layout constraints
- **Output**: 3D room meshes with designer-style layouts
- **Quality**: Better than Text2Room on CLIP/IS metrics. Separates layout and appearance modeling
- **Status**: Published 2025, limited public implementation
- **Verdict**: Better architecture than Text2Room but same fundamental limitations
- **Source**: https://arxiv.org/abs/2310.03602

### 3. ControlRoom3D (CVPR 2024)
- **What**: Room generation using semantic proxy rooms
- **Output**: Textured 3D room meshes from user-defined 3D semantic proxy
- **Key insight**: User provides rough room layout as bounding boxes, system generates detailed geometry
- **Verdict**: Interesting approach but research-only, no production tooling
- **Source**: https://openaccess.thecvf.com/CVPR2024

### 4. Holodeck (CVPR 2024, Allen AI) -- MOST PROMISING
- **What**: GPT-4 driven 3D environment generation using Objaverse assets
- **How it works**: LLM understands "what should be in a tavern?" and selects/arranges assets from Objaverse's 800K+ 3D model collection
- **Platform**: AI2-THOR / Unity 2020.3.25f1
- **Open Source**: Yes - github.com/allenai/Holodeck
- **Requirements**: GPT-4o API key + conda environment + Unity editor
- **Export**: Unity-compatible formats (OBJ, GLB via Objaverse)
- **Verdict**: Best existing tool for AI-driven interior composition. Could potentially be adapted for our pipeline. The key limitation is dependency on AI2-THOR framework
- **Source**: https://yueyang1996.github.io/holodeck/

### 5. ProcTHOR (AI2)
- **What**: Procedural generation of diverse, realistic, interactive 3D environments
- **Platform**: AI2-THOR
- **Quality**: Good for training AI agents, less focused on visual quality
- **Verdict**: Useful concept but AI2-THOR dependency makes it hard to integrate with Blender pipeline
- **Source**: https://procthor.allenai.org/

### 6. Google Genie 3 (2025-2026)
- **What**: Neural real-time walkable 3D world generation from text
- **Output**: Real-time neural rendering ONLY - no mesh export
- **Platform**: Cloud-only, requires TPU clusters
- **Access**: Google AI Ultra subscription ($250/month) - US only
- **Verdict**: Impressive tech but fundamentally incompatible with game development. Cannot export to any 3D format. Worlds exist only as neural renders
- **Source**: https://deepmind.google/discover/blog/genie-3/

### 7. Gaussian Splatting approaches
- **What**: Various tools for 3D scene capture/reconstruction using Gaussian splats
- **Output**: Point clouds / splats (not triangle meshes)
- **Game integration**: Unity/Unreal splat renderers exist but performance-heavy
- **Verdict**: Could capture AI-generated panoramic rooms as splats, but conversion to game-ready mesh is lossy and complex

---

### 8. SceneCraft (NeurIPS 2024)
- **What**: Multi-room apartments from 3D bounding box layouts + text
- **Output**: NeRF (primary) with mesh export via nerfstudio
- **Game-ready?**: No. NeRF requires baking to mesh.
- **Quality**: Highest CLIP Score (24.34) among baselines. Supports multi-bedroom apartments with irregular layouts.
- **Open source**: Yes - github.com/OrangeSodahub/SceneCraft
- **Verdict**: Most ambitious room-scale generation but NeRF output not game-usable

### 9. Pano2Room (SIGGRAPH Asia 2024)
- **What**: 3D room reconstruction from a single panoramic image
- **Output**: Intermediate mesh + final Gaussian splat
- **Interesting pipeline**: Generate AI panorama → Pano2Room → mesh. But mesh quality degrades with distance.
- **Open source**: Yes - github.com/TrickyGo/Pano2Room

### 10. MIDI / Tripo Compositional (CVPR 2025)
- **What**: Multi-object compositional 3D scenes from a single image (Tripo research)
- **Output**: Multiple separate GLB/FBX meshes with spatial relationships
- **Open source**: Yes - github.com/VAST-AI-Research/MIDI-3D
- **Verdict**: Not room shells, but interesting for generating multiple related furniture pieces from a reference image

---

## Practical Workflow for VeilBreakers Interiors

### Option A: World Labs Marble + Cleanup (Hero Rooms)
1. Generate room in Marble from concept art or text prompt
2. Use "Chisel" editor to define wall/room layout
3. Export as GLB mesh (600K tris with textures)
4. Import: `asset_pipeline action=import_model filepath=room.glb`
5. Cleanup: `asset_pipeline action=cleanup object_name=room`
6. Retexture: `blender_texture action=create_pbr` with dark fantasy materials
7. Export to Unity

### Option B: compose_interior Pipeline (Bulk/Layout)
1. **Procedural room shells** - Box rooms with proper dimensions, doors, occlusion markers
2. **Per-room detailed geometry** - generate_interior with room-type-specific features
3. **Storytelling props** - Narrative clutter placed by add_storytelling_props
4. **AI-generated hero furniture** - Tripo for key furniture pieces (prompt queue generated automatically)
5. **Unity integration** - Interior streaming, door system, dungeon lighting, portal audio

### Why This Works Better Than Full AI Generation
- Room shells are structurally correct (no holes, proper doors, proper scale)
- Tripo furniture is high quality with PBR materials
- Procedural placement handles the "what goes where" problem
- Unity handles lighting/atmosphere which sells the visual quality
- No 12-16GB VRAM requirement

### Future Integration Opportunity: Holodeck-Style LLM Planning
Could enhance compose_interior by:
1. Using LLM (Claude/GPT) to determine room contents based on room type and narrative context
2. Querying Objaverse or generating with Tripo based on LLM suggestions
3. LLM-driven placement rules instead of hardcoded per-room-type lists

---

## Sources
- Text2Room: https://github.com/lukasHoel/text2room
- Ctrl-Room: https://arxiv.org/abs/2310.03602
- ControlRoom3D: https://jonasschult.github.io/ControlRoom3D/
- Holodeck: https://github.com/allenai/Holodeck
- ProcTHOR: https://procthor.allenai.org/
- Google Genie 3: https://deepmind.google/discover/blog/genie-3/
- SceneCraft: https://arxiv.org/html/2410.09049v1
