# VeilBreakers GameDev Toolkit

AI-powered game development MCP toolkit that transforms Claude into a complete game development team.

## What This Is

Three custom **MCP (Model Context Protocol) servers** that give Claude the capabilities of:
- **3D Artists** — modeling, texturing, UV mapping
- **Technical Artists** — rigging, skinning, shader work
- **Animators** — keyframe animation, procedural motion, creature gaits
- **Environment Artists** — terrain, vegetation, buildings, biomes
- **UI/UX Designers** — layout validation, visual testing, responsive design
- **QA Engineers** — automated testing with built-in validation at every step

## Architecture

```
                    +-------------------------------------+
                    |           CLAUDE (Opus 4.6)          |
                    |     Game Development AI Director     |
                    +------+----------+----------+--------+
                           |          |          |
              +------------v--+  +----v--------+  +v-----------------+
              |   BLENDER     |  |   ASSET      |  |   UNITY          |
              |   GAMEDEV     |  |   PIPELINE   |  |   ENHANCED       |
              |   MCP         |  |   MCP        |  |   MCP            |
              |               |  |              |  |                  |
              | - Rigging     |  | - Tripo3D    |  | - Visual Test    |
              | - Animation   |  | - CHORD PBR  |  | - UI Validation  |
              | - Topology    |  | - Gaea       |  | - Anim Setup     |
              | - Texturing   |  | - PyMeshLab  |  | - Scene Build    |
              | - Environment |  | - Real-ESRGAN|  | - AI/Mobs        |
              | - Export      |  | - xatlas UV  |  | - Performance    |
              +-------+-------+  +------+-------+  +--------+---------+
                      |                 |                    |
                      v                 v                    v
                  [Blender]     [External APIs +      [Unity Editor]
                  (bpy API)     Local Python Tools]   (C# Scripting)
```

## MCP Servers

### 1. `blender-gamedev` - 3D Art + Animation Pipeline
**Tech:** Python + FastMCP 3.0 + Blender bpy API

- **Rigging**: 10 creature rig templates (humanoid, quadruped, dragon, insect, serpent, floating, multi-armed, arachnid, winged biped, amorphous), auto weight painting with deformation testing
- **Animation**: Procedural gait generation (biped, quad, hexapod, serpent, flying), contact sheet previews, secondary motion physics
- **Topology**: Mesh analysis with A-F grading, auto-repair, retopology, UV quality metrics
- **Texturing**: PBR material creation, texture baking, AI integration (CHORD/Scenario)
- **Environment**: Geometry Nodes terrain, vegetation scatter, procedural buildings, biome presets
- **Export**: Unity-optimized FBX with auto LOD generation and validation

### 2. `asset-pipeline` - AI Asset Generation + Processing
**Tech:** Python + FastMCP 3.0 + External API Clients

- **3D Generation**: Tripo3D, Meshy, Rodin API integration with auto-cleanup
- **Textures**: Ubisoft CHORD (open-source PBR), Scenario API, Real-ESRGAN upscaling
- **Terrain**: Gaea CLI integration, procedural heightmap generation
- **Mesh Processing**: PyMeshLab (analysis, repair, decimation), xatlas (UV unwrapping), LOD generation

### 3. `unity-enhanced` - Unity Editor Superpowers
**Tech:** C# Unity Editor scripts + Node.js MCP bridge

- **Visual Testing**: Screenshot capture, UI layout validation, responsive testing, Gemini visual review
- **Animation**: Animator controller creation, avatar setup, Animation Rigging configuration
- **Scene Building**: Terrain API, ProBuilder, vegetation scatter, lighting, cameras
- **AI/Mobs**: Mob controller generation, NavMesh automation, behavior trees, spawn systems
- **Performance**: Profiling, LOD generation, lightmap baking, occlusion culling

## The Core Innovation: Validation-First Design

Every tool returns **structured validation data + visual proof**. No more blind execution.

| Operation | Old Way (Blind) | New Way (Validated) |
|-----------|----------------|---------------------|
| Rig a creature | Execute Python, hope it works | Auto-test at 8 poses, return contact sheet |
| Weight paint | Set weights, can't see result | Deformation test with stretch/clip report |
| Animation | Set keyframes, can't see motion | Render contact sheet (every 4th frame, 3 angles) |
| UI change | Edit code, can't see layout | Screenshot + validation rules + Gemini review |
| Mesh cleanup | Run operations blindly | Topology score card (A-F) + before/after |

## Requirements

### Python Packages
```
fastmcp>=3.0
pymeshlab
xatlas
fast-simplification
Pillow
numpy
```

### External Tools
- Blender 3.6+ with Rigify enabled
- Unity 2022.3+ with UI Toolkit
- Real-ESRGAN (binary)
- Gaea Community Edition (optional, for terrain)

### API Keys (Optional)
- Tripo3D API key (for AI 3D generation)
- Scenario API key (for AI texture generation)

## Installation

```bash
# Clone
git clone https://github.com/Sharks820/veilbreakers-gamedev-toolkit.git
cd veilbreakers-gamedev-toolkit

# Install Python dependencies
pip install -r requirements.txt

# Add to Claude Code .mcp.json
# See docs/SETUP.md for configuration
```

## Project Status

**Phase 1: Foundation** - IN PROGRESS
- [ ] FastMCP server skeleton
- [ ] Blender socket bridge addon
- [ ] Mesh analysis tools
- [ ] Contact sheet rendering
- [ ] Deformation testing

See [MASTERPLAN.md](docs/MASTERPLAN.md) for full roadmap.

## Built For

This toolkit is built specifically for **VeilBreakers 3D**, a AAA-quality 3D monster RPG, but the MCP servers are generic enough for any Unity + Blender game development workflow.

## License

MIT
