# AI Interior/Room 3D Generation Research

**Date**: 2026-03-24
**Goal**: Find AI tools that generate walkable 3D interiors (rooms with walls, floors, ceilings, furniture)

---

## Executive Summary

**Tools exist, but none are production-ready for game development on consumer hardware.**

The field splits into three categories:
1. **Research mesh generators** (Text2Room, Ctrl-Room, ControlRoom3D) - output real meshes but need 12-16GB+ VRAM, have quality issues, export to PLY not game formats
2. **LLM-driven scene assembly** (Holodeck, ProcTHOR) - arrange existing 3D assets in rooms using AI planning. Most promising for our use case
3. **Neural rendering** (Google Genie 3) - generate walkable worlds but NOT exportable to mesh. Cloud-only, not game-engine compatible

**Best practical approach**: Hybrid pipeline combining procedural room shells + LLM-driven prop selection + Tripo AI-generated furniture. This is what our `compose_interior` action implements.

---

## Tools Analyzed

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

## Practical Workflow for VeilBreakers Interiors

Given the research, the optimal approach is what we've built:

### compose_interior Pipeline
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
