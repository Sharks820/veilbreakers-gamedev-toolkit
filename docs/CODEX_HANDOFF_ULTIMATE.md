# CODEX HANDOFF — ULTIMATE IMPLEMENTATION GUIDE

**Date:** 2026-03-27
**Author:** Claude AI (Senior Game Developer)
**Recipient:** Codex AI (Implementation Agent)
**Goal:** Integrate 41 free Blender addons into VeilBreakers MCP Toolkit to achieve 9/10+ AAA visual quality
**PC:** RTX 4060 Ti 8GB VRAM, 32GB RAM — NO tools requiring >8GB VRAM

---

## TABLE OF CONTENTS

1. [Architecture Overview](#1-architecture-overview)
2. [Codebase Map](#2-codebase-map)
3. [Handler Registration Pattern](#3-handler-registration-pattern)
4. [MCP Server Dispatch Pattern](#4-mcp-server-dispatch-pattern)
5. [The 41 Tools — Complete Implementation Specs](#5-the-41-tools)
6. [Phase 1: Prove the Pipeline](#6-phase-1-prove-the-pipeline)
7. [Phase 2: Architecture + Textures](#7-phase-2-architecture--textures)
8. [Phase 3: Terrain + Vegetation + Water](#8-phase-3-terrain--vegetation--water)
9. [Phase 4: Interiors + Dungeons + Cities](#9-phase-4-interiors--dungeons--cities)
10. [Phase 5: Optimization + Quality Gate](#10-phase-5-optimization--quality-gate)
11. [Phase 6: Edit Handlers (AI Editability)](#11-phase-6-edit-handlers)
12. [Testing Requirements](#12-testing-requirements)
13. [Player-Scale Constants](#13-player-scale-constants)
14. [Texture Pipeline Specification](#14-texture-pipeline-specification)
15. [Critical Bugs to Fix](#15-critical-bugs-to-fix)
16. [Quality Verification Matrix](#16-quality-verification-matrix)
17. [Anti-Regression Protocol](#17-anti-regression-protocol)
18. [Git Workflow](#18-git-workflow)

---

## 1. ARCHITECTURE OVERVIEW

```
┌────────────────────────────────────────────────────────────┐
│ Claude / Codex AI Agent                                    │
│                                                            │
│ Calls MCP tools: blender_worldbuilding(action="generate_   │
│   real_building", floors=2, style="gothic")                │
└───────────────────────┬────────────────────────────────────┘
                        │ MCP Protocol (stdio)
┌───────────────────────▼────────────────────────────────────┐
│ MCP Server (blender_server.py)                             │
│                                                            │
│ @mcp.tool() blender_worldbuilding(action, ...)             │
│   → builds params dict                                     │
│   → await blender.send_command("world_generate_building",  │
│                                 params)                    │
│   → returns JSON + viewport screenshot                     │
└───────────────────────┬────────────────────────────────────┘
                        │ TCP Socket (localhost:9876)
┌───────────────────────▼────────────────────────────────────┐
│ Blender Addon (blender_addon/)                             │
│                                                            │
│ handlers/__init__.py → COMMAND_HANDLERS dict (283 entries) │
│ COMMAND_HANDLERS["world_generate_building"] →               │
│   handle_generate_building(params)                         │
│                                                            │
│ Handler calls Building Tools Python API:                   │
│   bpy.ops.building_tools.build_floor(...)                  │
│   bpy.ops.building_tools.add_door(...)                     │
│                                                            │
│ Returns result dict with mesh stats                        │
└────────────────────────────────────────────────────────────┘
```

### For Unity tools:
```
AI Agent → MCP Server (unity_server.py)
         → Generates C# editor script
         → _write_to_unity(script, "Assets/Editor/Generated/Code/MyTool.cs")
         → Returns { next_steps: ["unity_editor action=recompile", "Run menu item"] }
```

---

## 2. CODEBASE MAP

```
Tools/mcp-toolkit/
├── src/veilbreakers_mcp/
│   ├── blender_server.py          # 15 Blender compound tools (MCP entry points)
│   ├── unity_server.py            # Main Unity MCP entry, imports unity_tools
│   ├── unity_tools/               # 22 Unity tool modules
│   │   ├── __init__.py            # Imports all modules (side-effect registration)
│   │   ├── _common.py             # _write_to_unity(), STANDARD_NEXT_STEPS
│   │   ├── editor.py              # unity_editor tool
│   │   ├── vfx.py, audio.py, ui.py, scene.py, gameplay.py, ...
│   │   └── build.py
│   └── shared/
│       ├── blender_client.py      # BlenderConnection TCP client
│       ├── config.py              # Settings (host, port, paths)
│       ├── security.py            # Code AST validation
│       ├── texture_ops.py         # HSV, seam blending, masking
│       ├── esrgan_runner.py       # Real-ESRGAN upscaling
│       ├── tripo_client.py        # Tripo API 3D generation
│       ├── fal_client.py          # fal.ai concept art / inpaint
│       ├── pipeline_runner.py     # Multi-step pipeline orchestration
│       └── asset_catalog.py       # Asset metadata catalog
│
├── blender_addon/
│   ├── __init__.py                # Addon entry, registers panel + TCP server
│   ├── handlers/
│   │   ├── __init__.py            # COMMAND_HANDLERS dict (283 registered commands)
│   │   ├── worldbuilding.py       # 6077 lines — buildings, castles, dungeons, towns
│   │   ├── environment.py         # Terrain, rivers, roads, water, scatter
│   │   ├── texture.py             # PBR creation, baking, validation
│   │   ├── mesh.py                # 3574 lines — topology, repair, sculpt, boolean
│   │   ├── vegetation_lsystem.py  # L-system tree generation (pure logic)
│   │   ├── vegetation_system.py   # Biome-specific vegetation placement
│   │   ├── _dungeon_gen.py        # 1266 lines — BSP dungeon grid (pure logic, NO mesh)
│   │   ├── _scatter_engine.py     # 603 lines — Poisson disk scatter
│   │   ├── _terrain_erosion.py    # 300 lines — hydraulic + thermal erosion
│   │   ├── _terrain_noise.py      # Heightmap generation, biome assignment
│   │   ├── _building_grammar.py   # 2716 lines — building spec grammar
│   │   ├── modular_building_kit.py# Grid-based modular kit pieces
│   │   ├── settlement_generator.py# 2386 lines — settlement composition
│   │   ├── procedural_meshes.py   # 22197 lines — THE LARGEST FILE
│   │   ├── procedural_materials.py# Procedural material node trees
│   │   └── ... (110 total handler files)
│   └── ...
│
├── tests/                         # pytest suite (13,952+ tests pass on user's machine)
│   ├── conftest.py                # Shared fixtures
│   ├── test_worldbuilding.py      # Worldbuilding handler tests
│   └── ... (100+ test files)
│
└── .planning/                     # Phase plans, state tracking
```

---

## 3. HANDLER REGISTRATION PATTERN

### Step 1: Write handler function in appropriate module

```python
# blender_addon/handlers/building_tools_integration.py
"""Integration handler for Building Tools addon (ranjian0/building_tools).

Wraps Building Tools Python operators for MCP automation.
Creates buildings with REAL boolean-cut door/window openings.
"""
from __future__ import annotations
import logging
from typing import Any
import bpy

logger = logging.getLogger(__name__)

# Player-scale constants (MANDATORY — never change these)
DOOR_HEIGHT_MIN = 2.2    # meters
DOOR_WIDTH_MIN = 1.0
CORRIDOR_WIDTH_MIN = 1.5
CORRIDOR_HEIGHT_MIN = 2.5
ROOM_MIN_SIZE = 3.0
CEILING_HEIGHT_STD = 2.8
CEILING_HEIGHT_GRAND = 4.0
FLOOR_THICKNESS = 0.3
STAIR_STEP_HEIGHT = 0.2
WINDOW_SILL_HEIGHT = 0.9


def handle_generate_real_building(params: dict[str, Any]) -> dict[str, Any]:
    """Generate a building with REAL openings using Building Tools addon.

    Params:
        style: str — "gothic" | "medieval" | "fortress" | "cottage" | "ramshackle"
        floors: int — number of floors (default 1)
        width: float — building width in meters (default 8.0)
        depth: float — building depth in meters (default 6.0)
        wall_height: float — per-floor wall height (default 3.0)
        openings: list[dict] — door/window specs per wall
        roof_type: str — "gable" | "hip" | "flat" | "mansard"
        name: str — object name prefix
        seed: int — reproducibility seed

    Returns:
        dict with building_name, mesh_stats, opening_count, walkable (bool)
    """
    # Implementation wraps bpy.ops.building_tools.* operators
    ...
    return {"status": "success", "building_name": name, "walkable": True}
```

### Step 2: Import in `handlers/__init__.py`

```python
from .building_tools_integration import (
    handle_generate_real_building,
    handle_edit_building,
)
```

### Step 3: Register in COMMAND_HANDLERS dict

```python
COMMAND_HANDLERS: dict[str, Callable[[dict[str, Any]], Any]] = {
    # ... existing handlers ...

    # Building Tools integration (AAA architecture)
    "world_generate_real_building": handle_generate_real_building,
    "world_edit_building": handle_edit_building,
}
```

### Step 4: Add MCP tool action in `blender_server.py`

In the `blender_worldbuilding` tool function, add new action to the `Literal[...]` type and add elif dispatch:

```python
@mcp.tool()
async def blender_worldbuilding(
    action: Literal[
        # ... existing actions ...
        "generate_real_building",   # NEW
        "edit_building",            # NEW
    ],
    # ... existing params ...
    openings: list[dict] | None = None,  # NEW param
    roof_type: str | None = None,        # NEW param
):
    # ... existing dispatch ...

    elif action == "generate_real_building":
        params: dict = {}
        if name is not None: params["name"] = name
        if width is not None: params["width"] = width
        if depth is not None: params["depth"] = depth
        if style is not None: params["style"] = style
        if openings is not None: params["openings"] = openings
        if roof_type is not None: params["roof_type"] = roof_type
        if seed is not None: params["seed"] = seed
        result = await blender.send_command("world_generate_real_building", params)
        return await _with_screenshot(blender, result, capture_viewport)
```

---

## 4. MCP SERVER DISPATCH PATTERN

### Blender tools (blender_server.py)

```python
@mcp.tool()
async def tool_name(
    action: Literal["action1", "action2"],
    param1: str | None = None,
    param2: float | None = None,
    capture_viewport: bool = True,
):
    """Tool docstring."""
    blender = get_blender_connection()

    if action == "action1":
        params: dict = {}
        if param1 is not None: params["param1"] = param1
        if param2 is not None: params["param2"] = param2
        result = await blender.send_command("handler_name", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "action2":
        # ...

    return "Unknown action"
```

**Key rules:**
- `get_blender_connection()` is a lazy singleton (TCP to localhost:9876)
- `await blender.send_command(handler_name, params_dict)` dispatches to Blender
- `await _with_screenshot(blender, result, capture_viewport)` returns JSON + PNG
- Only include non-None params in the dict
- Handler name convention: `domain_action` (e.g., `world_generate_building`)

### Unity tools (unity_tools/*.py)

```python
@mcp.tool()
async def unity_tool_name(
    action: Literal["action1"],
    param1: str | None = None,
):
    """Tool docstring."""
    if action == "action1":
        script = generate_some_csharp(param1)
        rel_path = "Assets/Editor/Generated/Code/MyScript.cs"
        abs_path = _write_to_unity(script, rel_path)
        return json.dumps({
            "status": "success",
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
        })
    return "Unknown action"
```

---

## 5. THE 41 TOOLS — COMPLETE IMPLEMENTATION SPECS

### A. ARCHITECTURE & BUILDINGS

#### A1: Building Tools (ranjian0/building_tools) — GPL-3.0
**GitHub:** https://github.com/ranjian0/building_tools
**What it does:** Creates buildings with REAL boolean-cut door/window openings
**Python API operators:**
```python
bpy.ops.building_tools.add_floorplan()  # Floor shape
bpy.ops.building_tools.add_floors()     # Multi-story extrusion
bpy.ops.building_tools.add_window()     # Boolean-cut window
bpy.ops.building_tools.add_door()       # Boolean-cut door
bpy.ops.building_tools.add_roof()       # Parametric roof
bpy.ops.building_tools.add_stairs()     # Interior stairs
bpy.ops.building_tools.add_balcony()    # Balcony geometry
```
**Handler file:** `blender_addon/handlers/building_tools_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"world_generate_real_building"` → `handle_generate_real_building`
- `"world_edit_building_openings"` → `handle_edit_building_openings`
- `"world_edit_building_roof"` → `handle_edit_building_roof`
- `"world_edit_building_floors"` → `handle_edit_building_floors`
**MCP tool:** `blender_worldbuilding` actions: `generate_real_building`, `edit_building_openings`, `edit_building_roof`, `edit_building_floors`
**Test file:** `tests/test_building_tools_integration.py`
**Tests needed:**
- Building with 1-5 floors generates valid mesh
- Door opening passes walkability check (width ≥ 1.0m, height ≥ 2.2m)
- Window opening has actual hole in wall geometry
- Roof generates correct type (gable/hip/flat/mansard)
- All dark fantasy style presets produce valid output
- Boolean operations don't create non-manifold geometry
- Stairs connect floors properly
- Player-scale constants are enforced

#### A2: Archimesh (Built-in Blender Extension)
**What it does:** Room shells, doors, windows, stairs, columns, shelves, furniture
**Python API:**
```python
bpy.ops.mesh.archimesh_room()       # Room with walls + openings
bpy.ops.mesh.archimesh_door()       # Door geometry
bpy.ops.mesh.archimesh_window()     # Window geometry
bpy.ops.mesh.archimesh_column()     # Column geometry
bpy.ops.mesh.archimesh_stair()      # Stair geometry
bpy.ops.mesh.archimesh_shelves()    # Shelf/bookcase
```
**Handler file:** `blender_addon/handlers/archimesh_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"arch_generate_room"` → `handle_archimesh_room`
- `"arch_generate_furniture"` → `handle_archimesh_furniture`
**MCP tool:** `blender_worldbuilding` actions: `generate_archimesh_room`, `generate_archimesh_furniture`
**Prerequisite:** Enable Archimesh in Blender preferences: `bpy.ops.preferences.addon_enable(module="archimesh")`

#### A3: BagaPie v11 (Blender Extensions Platform)
**What it does:** Doors, windows, bolts, railings, stairs, ivy, scatter arrays
**Install:** Blender Extensions Platform (free)
**Handler file:** `blender_addon/handlers/bagapie_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"bagapie_scatter_array"` → `handle_bagapie_scatter`
- `"bagapie_ivy"` → `handle_bagapie_ivy`
- `"bagapie_railing"` → `handle_bagapie_railing`
**MCP tool:** `blender_environment` actions: `scatter_bagapie`, `generate_ivy`, `generate_railing`

#### A4: Snap! (varkenvarken/Snap)
**GitHub:** https://github.com/varkenvarken/Snap
**What it does:** Modular kit snap-point system (Bethesda-style wall→door→floor snapping)
**Handler file:** `blender_addon/handlers/snap_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"snap_add_point"` → `handle_snap_add_point`
- `"snap_connect"` → `handle_snap_connect`
- `"snap_auto_assemble"` → `handle_snap_auto_assemble`
**MCP tool:** `blender_worldbuilding` actions: `snap_add_point`, `snap_connect`, `snap_auto_assemble`

---

### B. WALKABLE INTERIORS & DUNGEONS

#### B1: Proc Level Gen (aaronjolson/Blender-Python-Procedural-Level-Generation)
**GitHub:** https://github.com/aaronjolson/Blender-Python-Procedural-Level-Generation
**What it does:** Creates ACTUAL walkable dungeon/castle mesh (not just grid data)
**CRITICAL:** This replaces the broken `_dungeon_gen.py` grid-only output
**Integration strategy:**
1. KEEP existing `_dungeon_gen.py` BSP algorithm for layout planning
2. NEW: Use Proc Level Gen to materialize the grid into actual 3D mesh
3. Grid cell → wall/floor/ceiling geometry with real openings
**Handler file:** `blender_addon/handlers/proc_level_gen_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"world_generate_walkable_dungeon"` → `handle_walkable_dungeon`
- `"world_generate_walkable_interior"` → `handle_walkable_interior`
**MCP tool:** `blender_worldbuilding` actions: `generate_walkable_dungeon`, `generate_walkable_interior`
**Tests needed:**
- Every room ≥ 3m × 3m
- Every door ≥ 1.0m wide × 2.2m tall
- Every corridor ≥ 1.5m wide × 2.5m tall
- Floor-ceiling height ≥ 2.8m (standard) or ≥ 4.0m (grand)
- No overlapping geometry
- All rooms connected (flood fill test)

#### B2: MakeTile (richeyrose/make-tile)
**GitHub:** https://github.com/richeyrose/make-tile
**What it does:** Modular dungeon tiles with OpenLOCK snap connections
**Handler file:** `blender_addon/handlers/maketile_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"maketile_generate_tile"` → `handle_maketile_tile`
- `"maketile_connect_tiles"` → `handle_maketile_connect`
**MCP tool:** `blender_worldbuilding` actions: `generate_dungeon_tile`, `connect_tiles`

#### B3: Cell Fracture (Built-in Blender Extension)
**What it does:** Breakable objects (barrels, crates, walls) — intact → fractured pairs
**Python API:** `bpy.ops.object.cell_fracture_crack_it()`
**Handler file:** `blender_addon/handlers/cell_fracture_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"physics_cell_fracture"` → `handle_cell_fracture`
**MCP tool:** `blender_mesh` action: `cell_fracture`
**Prerequisite:** `bpy.ops.preferences.addon_enable(module="object_fracture_cell")`

---

### C. TERRAIN

#### C1: Terrain HeightMap Generator (sp4cerat/Terrain-HeightMap-Generator)
**GitHub:** https://github.com/sp4cerat/Terrain-HeightMap-Generator
**What it does:** DLA erosion at 1024×1024+, GPU-accelerated
**CRITICAL FIX:** Current terrain is 256×256. This needs to be 1024×1024 minimum.
**Integration strategy:**
1. Generate heightmap externally using the tool's C++/GPU binary
2. Import heightmap as 16-bit PNG into existing `environment.py` terrain handler
3. Apply our existing erosion passes on top
**Handler file:** `blender_addon/handlers/terrain_heightmap_gen_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"env_generate_dla_heightmap"` → `handle_dla_heightmap`
**MCP tool:** `blender_environment` action: `generate_dla_terrain`
**Config changes to `_terrain_noise.py`:**
- Default resolution: 256 → 1024
- Erosion particles: 50K → 500K
- Thermal erosion transfer: 50% → 15%
- Thermal passes: 10 → 50

#### C2: A.N.T. Landscape (Built-in Blender Extension)
**Already partially wired.** Verify it's enabled and callable.
**Prerequisite:** `bpy.ops.preferences.addon_enable(module="ant_landscape")`

#### C3: Terrain Mixer (Blender Extensions Platform)
**Handler file:** `blender_addon/handlers/terrain_mixer_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"env_terrain_mixer_paint"` → `handle_terrain_mixer_paint`
- `"env_terrain_mixer_blend"` → `handle_terrain_mixer_blend`
**MCP tool:** `blender_environment` actions: `terrain_mixer_paint`, `terrain_mixer_blend`

---

### D. VEGETATION

#### D1: tree-gen (friggog/tree-gen) — GPL
**GitHub:** https://github.com/friggog/tree-gen
**What it does:** Weber & Penn L-system trees with real branches, bark, leaves, game LOD
**CRITICAL:** Replaces cone primitives currently used for trees
**Dark fantasy presets to create:**
```python
TREE_PRESETS = {
    "dead_oak": {"branches": 5, "leaves": False, "bark": "dark", "twist": 0.8},
    "corrupted_willow": {"branches": 8, "leaves": True, "droop": 0.9, "tendrils": True},
    "ancient_pine": {"branches": 4, "leaves": True, "height": 15, "sparse": True},
    "mushroom_tree": {"cap": True, "trunk_only": True, "corruption": True},
    "bog_mangrove": {"roots": True, "branches": 6, "moss": True},
    "blighted_birch": {"leaves": False, "bark": "white_peeling", "dead_branches": 0.6},
}
```
**Handler file:** `blender_addon/handlers/treegen_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"veg_generate_tree"` → `handle_treegen_tree`
- `"veg_generate_tree_lod"` → `handle_treegen_lod`
**MCP tool:** `blender_environment` actions: `generate_lsystem_tree`, `generate_tree_lod`
**Each tree must have:**
- 3 LOD levels (high: 5K tris, medium: 1K tris, low: billboard)
- Bark PBR material (albedo, normal, roughness)
- Leaf cards (alpha-tested quads)
- Wind vertex colors (for Unity foliage shader)

#### D2: Spacetree (varkenvarken/spacetree) — GPL
**GitHub:** https://github.com/varkenvarken/spacetree
**Handler file:** `blender_addon/handlers/spacetree_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"veg_generate_spacetree"` → `handle_spacetree`
**MCP tool:** `blender_environment` action: `generate_space_colonization_tree`

#### D3: Sapling Tree Gen (Built-in Blender)
**Already partially wired** in `vegetation_lsystem.py`. Verify integration complete.
**Prerequisite:** `bpy.ops.preferences.addon_enable(module="add_curve_sapling")`

---

### E. SCATTER & PLACEMENT

#### E1: OpenScatter (GitMay3D/OpenScatter) — GPLv3
**GitHub:** https://github.com/GitMay3D/OpenScatter
**What it does:** Advanced rule-based scatter with slope, height, moisture masking, collision avoidance, wind animation, viewport LOD
**CRITICAL:** Replaces dumb Poisson disk in `_scatter_engine.py`
**Integration strategy:**
1. KEEP existing `_scatter_engine.py` as fallback
2. NEW: Wire OpenScatter Python API as primary scatter method
3. Add environmental storytelling rules (corruption zones, ruin debris, etc.)
**Handler file:** `blender_addon/handlers/openscatter_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"env_openscatter"` → `handle_openscatter`
- `"env_openscatter_rule"` → `handle_openscatter_add_rule`
**MCP tool:** `blender_environment` actions: `scatter_openscatter`, `add_scatter_rule`

#### E2: Gscatter (gscatter.com)
**Handler file:** `blender_addon/handlers/gscatter_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"env_gscatter"` → `handle_gscatter`
**MCP tool:** `blender_environment` action: `scatter_gscatter`

---

### F. TEXTURES — THE FULL PIPELINE

#### F1: Principled Baker (danielenger/Principled-Baker) — FREE
**GitHub:** https://github.com/danielenger/Principled-Baker
**What it does:** Bakes ALL Principled BSDF channels to image textures in ONE operation
**CRITICAL FIX:** Currently procedural materials → blank white on FBX export. This fixes it.
**Python API:**
```python
# Must be called from Blender context
bpy.ops.object.principled_baker_bake(
    resolution=2048,        # hero: 2048, standard: 1024, prop: 512
    suffix_text_mod="NONE",
    selected_to_active=False,
    use_autodetect=True,    # auto-detect which channels to bake
)
```
**Handler file:** `blender_addon/handlers/principled_baker_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"tex_bake_principled"` → `handle_principled_bake`
- `"tex_bake_and_swap"` → `handle_bake_and_swap_nodes`
**MCP tool:** `blender_texture` actions: `bake_principled`, `bake_and_swap`
**The bake-and-swap pipeline (AUTOMATED):**
```
1. Select object
2. Principled Baker bakes: albedo, normal, metallic, roughness, AO, emission, height
3. Create Image Texture nodes for each baked image
4. Disconnect procedural nodes
5. Connect Image Texture nodes to Principled BSDF inputs
6. Pack images into .blend
7. FBX export with use_tspace=True → textures travel with mesh
8. Unity auto-imports correctly
```

#### F2: Material Maker (materialmaker.org) — MIT
**What it does:** Standalone procedural material editor, exports PBR map sets
**Integration:** CLI-based export → import PBR maps into Blender
**Handler file:** `blender_addon/handlers/material_maker_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"tex_material_maker_generate"` → `handle_material_maker_generate`
- `"tex_material_maker_import"` → `handle_material_maker_import`
**MCP tool:** `blender_texture` actions: `material_maker_generate`, `material_maker_import`

#### F3: Paint System (Blender Extensions Platform, Feb 2025)
**Handler file:** `blender_addon/handlers/paint_system_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"tex_paint_layer"` → `handle_paint_system_layer`
**MCP tool:** `blender_texture` action: `paint_layer`

#### F4: Dream Textures (carson-katri/dream-textures) — GPL
**GitHub:** https://github.com/carson-katri/dream-textures
**What it does:** Stable Diffusion texture generation inside Blender
**VRAM:** ~6GB in fp16 mode — fits RTX 4060 Ti 8GB
**Handler file:** `blender_addon/handlers/dream_textures_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"tex_dream_generate"` → `handle_dream_texture_generate`
- `"tex_dream_project"` → `handle_dream_texture_project`
**MCP tool:** `blender_texture` actions: `dream_generate`, `dream_project`

#### F5: DeepBump (HugoTini/DeepBump) — MIT
**GitHub:** https://github.com/HugoTini/DeepBump
**What it does:** AI normal map generation from single photo/albedo
**Handler file:** `blender_addon/handlers/deepbump_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"tex_deepbump_normal"` → `handle_deepbump_normal`
**MCP tool:** `blender_texture` action: `generate_normal_map`

#### F6: Anti-Seam (Blender Extensions Platform)
**Handler file:** `blender_addon/handlers/antiseam_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"tex_fix_seams"` → `handle_antiseam`
**MCP tool:** `blender_texture` action: `fix_seams`

#### F7: Atlas Repacker (Blender Extensions Platform)
**Handler file:** `blender_addon/handlers/atlas_repacker_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"tex_repack_atlas"` → `handle_atlas_repack`
**MCP tool:** `blender_texture` action: `repack_atlas`

#### F8: Poly Haven / AmbientCG (CC0 texture libraries)
**No addon needed.** Download PBR map sets and import.
**Handler file:** `blender_addon/handlers/polyhaven_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"tex_import_polyhaven"` → `handle_polyhaven_import`
**MCP tool:** `blender_texture` action: `import_polyhaven`
**Implementation:** HTTP GET to polyhaven.com/api/assets → download → import as Image Texture

#### F9: Real-ESRGAN (xinntao/Real-ESRGAN) — BSD-3
**ALREADY INTEGRATED** in `shared/esrgan_runner.py`. Verify it works.
**Existing MCP tool:** `blender_texture` action: `upscale`

---

### G. WATER SYSTEMS

#### G1: Blender Ocean Modifier (Built-in)
**Already partially integrated** in environment handlers. Verify full automation.
**Key:** `bpy.ops.object.modifier_add(type='OCEAN')`

#### G2: Mantaflow (Built-in Blender)
**Handler file:** `blender_addon/handlers/mantaflow_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"env_fluid_simulation"` → `handle_mantaflow_fluid`
**MCP tool:** `blender_environment` action: `create_fluid_simulation`

#### G3: Custom flow-path rivers
**Already exists** in `environment.py` → `handle_carve_river`. Verify D8 flow path works.

---

### H. COLLISION & PHYSICS

#### H1: Collision Tools (Blender Extensions Platform)
**Handler file:** `blender_addon/handlers/collision_tools_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"physics_collision_hull"` → `handle_collision_hull`
- `"physics_collision_merge"` → `handle_collision_merge`
**MCP tool:** `blender_mesh` actions: `generate_collision_hull`, `merge_collision`

#### H2: Cell Fracture — See B3 above

---

### I. CLOTH & FABRIC

#### I1: Bystedt's Cloth Builder (Gumroad, free)
**Handler file:** `blender_addon/handlers/cloth_builder_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"cloth_generate"` → `handle_cloth_builder`
**MCP tool:** `blender_rig` action: `generate_cloth`

#### I2: Blender Cloth Modifier (Built-in)
**Key:** `bpy.ops.object.modifier_add(type='CLOTH')`
**Already partially integrated** in physics handlers.

---

### J. RIGGING & ANIMATION

#### J1: Keemap Retarget (nkeeline/Keemap-Blender-Rig-ReTargeting-Addon)
**GitHub:** https://github.com/nkeeline/Keemap-Blender-Rig-ReTargeting-Addon
**Handler file:** `blender_addon/handlers/keemap_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"anim_retarget_keemap"` → `handle_keemap_retarget`
- `"anim_save_bone_mapping"` → `handle_keemap_save_mapping`
**MCP tool:** `blender_animation` actions: `retarget_keemap`, `save_bone_mapping`

#### J2: Rigodotify (catprisbrey/Rigodotify)
**GitHub:** https://github.com/catprisbrey/Rigodotify
**Handler file:** `blender_addon/handlers/rigodotify_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"rig_convert_unity"` → `handle_rigodotify_convert`
**MCP tool:** `blender_rig` action: `convert_to_unity_rig`

#### J3: Rigify (Built-in Blender)
**Already integrated** in `rigging.py` and `rigging_templates.py`. Verify.

---

### K. QUALITY & OPTIMIZATION

#### K1: MeshLint (rking/meshlint) — MIT
**GitHub:** https://github.com/rking/meshlint
**Handler file:** `blender_addon/handlers/meshlint_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"quality_meshlint"` → `handle_meshlint_check`
**MCP tool:** `blender_mesh` action: `meshlint_validate`
**MUST be run before every FBX export as quality gate.**

#### K2: Game Asset Optimizer (Blender Extensions Platform)
**Handler file:** `blender_addon/handlers/game_asset_optimizer_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"quality_optimize_game_asset"` → `handle_game_asset_optimize`
**MCP tool:** `blender_mesh` action: `optimize_game_asset`

#### K3: ACT: Game Asset Toolset (Blender Extensions Platform)
**Handler file:** `blender_addon/handlers/act_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"export_act"` → `handle_act_export`
**MCP tool:** `blender_export` action: `export_act`

#### K4: Polycount (Vinc3r/Polycount)
**GitHub:** https://github.com/Vinc3r/Polycount
**Handler file:** `blender_addon/handlers/polycount_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"quality_polycount"` → `handle_polycount_check`
**MCP tool:** `blender_mesh` action: `polycount_check`

#### K5: LODify (Blender Extensions Platform)
**Handler file:** `blender_addon/handlers/lodify_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"quality_lodify"` → `handle_lodify`
**MCP tool:** `blender_mesh` action: `lodify_analyze`

---

### L. WORLD & CITY GENERATION

#### L1: Proc City Gen (josauder/procedural_city_generation) — MIT
**GitHub:** https://github.com/josauder/procedural_city_generation
**Handler file:** `blender_addon/handlers/proc_city_gen_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"world_generate_city_layout"` → `handle_city_layout`
- `"world_generate_city_roads"` → `handle_city_roads`
**MCP tool:** `blender_worldbuilding` actions: `generate_city_layout`, `generate_city_roads`

#### L2: Anvil Level Design (alexjhetherington/anvil-level-design)
**GitHub:** https://github.com/alexjhetherington/anvil-level-design
**Handler file:** `blender_addon/handlers/anvil_integration.py` (NEW)
**COMMAND_HANDLERS entries:**
- `"world_anvil_bsp"` → `handle_anvil_bsp_edit`
**MCP tool:** `blender_worldbuilding` action: `anvil_bsp_edit`

---

## 6. PHASE 1: PROVE THE PIPELINE (Days 1-3)

**Goal:** ONE building + ONE texture that survives export + ONE real tree = pipeline proven.

### Task 1.1: Install Building Tools
```bash
cd /path/to/blender/addons/
git clone https://github.com/ranjian0/building_tools.git
```
Then enable in Blender:
```python
bpy.ops.preferences.addon_enable(module="building_tools")
```

### Task 1.2: Create `building_tools_integration.py`
- Create handler file at `blender_addon/handlers/building_tools_integration.py`
- Implement `handle_generate_real_building(params)`:
  1. Call `bpy.ops.building_tools.add_floorplan()` with dimensions
  2. Call `bpy.ops.building_tools.add_floors()` with floor count
  3. For each opening: call `bpy.ops.building_tools.add_door/add_window()`
  4. Call `bpy.ops.building_tools.add_roof()` with type
  5. Validate all dimensions against player-scale constants
  6. Return mesh stats
- Import and register in `handlers/__init__.py`

### Task 1.3: Create `principled_baker_integration.py`
- Create handler file at `blender_addon/handlers/principled_baker_integration.py`
- Implement `handle_principled_bake(params)`:
  1. Select target object
  2. Create bake images at requested resolution
  3. Call `bpy.ops.object.principled_baker_bake()`
  4. Swap procedural nodes → Image Texture nodes
  5. Pack images into .blend
  6. Return baked channel list
- Implement `handle_bake_and_swap_nodes(params)`:
  1. Run bake
  2. Disconnect all procedural nodes
  3. Connect Image Texture → Principled BSDF for each channel
  4. Verify FBX export produces non-blank textures

### Task 1.4: Create `treegen_integration.py`
- Create handler file at `blender_addon/handlers/treegen_integration.py`
- Implement `handle_treegen_tree(params)`:
  1. Call tree-gen's Python API with species/preset params
  2. Generate 3 LOD levels
  3. Compute wind vertex colors
  4. Create bark + leaf materials
  5. Return tree mesh stats

### Task 1.5: Wire into blender_server.py
- Add new actions to `blender_worldbuilding` Literal type
- Add new actions to `blender_texture` Literal type
- Add new actions to `blender_environment` Literal type
- Add elif dispatch for each action

### Task 1.6: Write Tests
- `tests/test_building_tools_integration.py` — at least 15 tests
- `tests/test_principled_baker_integration.py` — at least 10 tests
- `tests/test_treegen_integration.py` — at least 10 tests

### Task 1.7: VISUAL VERIFICATION
- Generate a 2-floor gothic building with 2 doors and 4 windows
- Apply stone material → bake with Principled Baker → export FBX
- Import FBX → verify textures are NOT blank
- Generate a dead oak tree-gen tree → verify it has branches (NOT a cone)
- Screenshot all three in same Blender scene → verify 8/10+ visual quality

---

## 7. PHASE 2: ARCHITECTURE + TEXTURES (Days 4-10)

### Tasks:
- A2: Wire Archimesh (enable addon + handler)
- A3: Wire BagaPie (install + handler)
- A4: Wire Snap! (install + handler)
- F2: Wire Material Maker (install + handler)
- F3: Wire Paint System (install + handler)
- F4: Wire Dream Textures (install + handler — verify 8GB VRAM works)
- F5: Wire DeepBump (install + handler)
- F6: Wire Anti-Seam (install + handler)
- F7: Wire Atlas Repacker (install + handler)
- F8: Wire Poly Haven import (HTTP API + handler)
- H1: Wire Collision Tools (install + handler)

### Deliverable:
- Full building with multiple rooms, each with baked PBR textures
- Material variety (stone walls, wood floors, metal fixtures)
- Collision meshes on all solid surfaces
- Screenshot comparison: before (blank textures) vs after (full PBR)

---

## 8. PHASE 3: TERRAIN + VEGETATION + WATER (Days 11-16)

### Tasks:
- C1: Wire Terrain HeightMap Gen (install binary + handler)
- C2: Verify A.N.T. Landscape enabled
- C3: Wire Terrain Mixer (install + handler)
- D1: Complete tree-gen dark fantasy presets (6 species)
- D2: Wire Spacetree (install + handler)
- D3: Verify Sapling Tree Gen enabled
- E1: Wire OpenScatter (install + handler + storytelling rules)
- E2: Wire Gscatter (install + handler)
- G1: Verify Ocean Modifier integration
- G2: Wire Mantaflow (handler)
- G3: Verify flow-path rivers work

### Terrain config changes (in `_terrain_noise.py`):
```python
# BEFORE (broken):
DEFAULT_RESOLUTION = 256
DEFAULT_EROSION_PARTICLES = 50000
THERMAL_TRANSFER_RATE = 0.5
THERMAL_PASSES = 10

# AFTER (AAA):
DEFAULT_RESOLUTION = 1024
DEFAULT_EROSION_PARTICLES = 500000
THERMAL_TRANSFER_RATE = 0.15
THERMAL_PASSES = 50
```

### OpenScatter storytelling rules to implement:
```python
SCATTER_RULES = {
    "FOREST_ZONE": [
        {"asset": "tree", "slope_max": 30, "height_range": [50, 300], "density": 0.7},
        {"asset": "undergrowth", "slope_max": 20, "in_shade": True, "density": 0.5},
        {"asset": "mushroom", "moisture": "HIGH", "near": "dead_tree", "density": 0.3},
        {"asset": "fallen_log", "chance": 0.05, "near": "large_tree"},
    ],
    "CORRUPTION_ZONE": [
        {"asset": "dead_tree", "replace_pct": 0.8},
        {"asset": "shadow_crystal", "near": "void_source", "density": 0.2},
        {"asset": "corrupted_soil", "ground_swap": True},
        {"asset": "mist_particles", "height_max": 2.0, "density": 0.8},
    ],
    "RUINS_ZONE": [
        {"asset": "rubble", "near": "wall", "density": 0.4},
        {"asset": "broken_weapon", "density": 0.1},
        {"asset": "overgrown_vine", "on": "wall", "slope_min": 60, "density": 0.6},
    ],
}
```

### Deliverable:
- 1024×1024 terrain with DLA erosion, rivers, height-based textures
- Real L-system trees (6 dark fantasy species)
- Intelligent scatter following storytelling rules
- Water bodies with proper shore transitions

---

## 9. PHASE 4: INTERIORS + DUNGEONS + CITIES (Days 17-24)

### Tasks:
- B1: Wire Proc Level Gen (install + handler)
- B2: Wire MakeTile (install + handler)
- B3: Wire Cell Fracture (enable + handler)
- I1: Wire Bystedt's Cloth Builder (install + handler)
- L1: Wire Proc City Gen (install + handler)
- L2: Wire Anvil Level Design (install + handler)

### Dungeon grid-to-mesh converter (CRITICAL NEW CODE):
```python
# In proc_level_gen_integration.py
def grid_to_walkable_mesh(grid: np.ndarray, rooms: list[Room], cell_size: float = 3.0):
    """Convert _dungeon_gen BSP grid → actual 3D mesh geometry.

    Cell types from _dungeon_gen.py:
        0 = wall (skip)
        1 = floor (generate floor + ceiling + walls where adjacent to 0)
        2 = corridor (narrow floor + walls + ceiling)
        3 = door (door frame with opening)

    Returns MeshSpec with vertices, faces, materials.
    """
    # For each non-wall cell:
    #   1. Create floor plane at y=0
    #   2. Create ceiling plane at y=CEILING_HEIGHT_STD
    #   3. For each adjacent wall cell: create wall face
    #   4. For door cells: create wall with DOOR_HEIGHT_MIN × DOOR_WIDTH_MIN opening
    #   5. Merge all geometry
    #   6. Validate player-scale constants
```

### City composition pipeline:
```
compose_city_layout(districts, style)
  → generate_road_network(L_system or organic)
  → per district:
      → generate_building_plots(voronoi)
      → per plot:
          → generate_real_building(Building Tools)
          → bake_textures(Principled Baker)
      → scatter_props(OpenScatter, storytelling rules)
      → scatter_vegetation(tree-gen + OpenScatter)
  → generate_city_walls(modular kit + Snap!)
  → bake_all_materials()
  → export_per_district_fbx()
```

### Deliverable:
- Walkable 10-room dungeon (every room ≥ 3m × 3m, every door passable)
- 3 breakable objects (barrel, crate, wall section)
- Banner/cloak cloth simulation
- Small city with 20+ buildings, roads, walls, gate

---

## 10. PHASE 5: OPTIMIZATION + QUALITY GATE (Days 25-30)

### Tasks:
- K1: Wire MeshLint (install + handler)
- K2: Wire Game Asset Optimizer (install + handler)
- K3: Wire ACT export (install + handler)
- K4: Wire Polycount (install + handler)
- K5: Wire LODify (install + handler)
- J1: Wire Keemap Retarget (install + handler)
- J2: Wire Rigodotify (install + handler)

### Pre-export quality gate (MANDATORY on every export):
```python
def pre_export_quality_gate(objects: list) -> dict:
    """Run before EVERY FBX/GLTF export.

    1. MeshLint: tris, ngons, non-manifold, stray verts → FAIL if any critical
    2. Polycount: per-object budget check → WARN if over budget
    3. LODify: verify LOD chain exists for large meshes → WARN if missing
    4. Collision Tools: verify collision mesh exists → WARN if missing
    5. Principled Baker: verify textures baked (not procedural) → FAIL if blank
    """
```

---

## 11. PHASE 6: EDIT HANDLERS (AI Editability)

**CRITICAL GAP:** The toolkit can CREATE assets but CANNOT EDIT them post-generation.
10 edit handlers must be built:

### Edit Handler 1: Building Editor
```python
def handle_edit_building(params):
    """Edit existing building: add/remove openings, change roof, add floor."""
    # Params: building_name, operation (add_door, remove_window, change_roof, add_floor)
```

### Edit Handler 2: Material Editor
```python
def handle_edit_material(params):
    """Edit material properties: color, roughness, metallic, swap texture."""
    # Params: object_name, material_slot, property_name, new_value
```

### Edit Handler 3: Scatter Editor
```python
def handle_edit_scatter(params):
    """Edit scatter: remove instances in area, change density, add exclusion zone."""
    # Params: scatter_name, operation (remove_area, change_density, add_exclusion)
```

### Edit Handler 4: World Layout Editor
```python
def handle_edit_world_layout(params):
    """Edit world: move building, rotate, swap style, delete structure."""
    # Params: object_name, operation (move, rotate, swap_style, delete)
```

### Edit Handler 5: Interior Editor
```python
def handle_edit_interior(params):
    """Edit interior: add/remove furniture, change room purpose, add props."""
    # Params: room_name, operation (add_furniture, remove_furniture, change_purpose)
```

### Edit Handler 6: Animation Editor
```python
def handle_edit_animation(params):
    """Edit animation: adjust timing, change pose, blend actions."""
    # Params: armature_name, action_name, operation (adjust_timing, change_pose)
```

### Edit Handler 7: Terrain Editor
```python
def handle_edit_terrain(params):
    """Edit terrain: raise/lower area, smooth, add feature, change biome."""
    # Params: terrain_name, operation, position, radius, strength
```

### Edit Handler 8: Modifier Editor
```python
def handle_edit_modifiers(params):
    """Edit modifiers: add, remove, reorder, change properties."""
    # Params: object_name, modifier_name, operation, properties
```

### Edit Handler 9: Physics Editor
```python
def handle_edit_physics(params):
    """Edit physics: collision mesh, rigid body, cloth settings."""
    # Params: object_name, physics_type, operation, properties
```

### Edit Handler 10: Shape Key Editor
```python
def handle_edit_shape_keys(params):
    """Edit shape keys: add, remove, set value, create driver."""
    # Params: object_name, shape_key_name, operation, value
```

**Handler file:** `blender_addon/handlers/edit_handlers.py` (NEW)
**Register ALL in COMMAND_HANDLERS** and wire into appropriate MCP tools.

---

## 12. TESTING REQUIREMENTS

### Test file naming: `tests/test_{handler_name}.py`
### Test pattern:
```python
import pytest
from blender_addon.handlers.building_tools_integration import (
    handle_generate_real_building,
)

class TestBuildingToolsIntegration:
    """Tests for Building Tools addon integration."""

    def test_basic_building_generates_mesh(self):
        """Building with default params produces valid mesh."""
        result = handle_generate_real_building({"floors": 1, "width": 8.0})
        assert result["status"] == "success"
        assert result["walkable"] is True

    def test_door_meets_player_scale(self):
        """Door openings meet minimum player-scale requirements."""
        result = handle_generate_real_building({
            "floors": 1,
            "openings": [{"type": "door", "wall": "front"}],
        })
        # Door must be ≥ 1.0m wide × 2.2m tall
        assert result["doors"][0]["width"] >= 1.0
        assert result["doors"][0]["height"] >= 2.2
```

### Minimum test counts per integration:
| Integration | Min Tests |
|-------------|-----------|
| Building Tools | 15 |
| Principled Baker | 10 |
| tree-gen | 10 |
| OpenScatter | 10 |
| Proc Level Gen | 15 |
| MakeTile | 8 |
| Terrain HeightMap | 10 |
| Collision Tools | 8 |
| Cell Fracture | 5 |
| MeshLint | 8 |
| Keemap Retarget | 8 |
| Each remaining tool | 5 minimum |
| **TOTAL MINIMUM** | **200+ new tests** |

### Running tests:
```bash
cd Tools/mcp-toolkit
python -m pytest tests/ --override-ini="cache_dir=/tmp/pytest_cache" -v
```

---

## 13. PLAYER-SCALE CONSTANTS

**ENFORCE IN EVERY HANDLER THAT GENERATES WALKABLE GEOMETRY:**

```python
# blender_addon/handlers/_player_scale.py (NEW — shared constants)

PLAYER_HEIGHT = 1.8           # meters
DOOR_HEIGHT_MIN = 2.2         # player + clearance
DOOR_WIDTH_MIN = 1.0          # player + weapon
CORRIDOR_WIDTH_MIN = 1.5      # combat space
CORRIDOR_HEIGHT_MIN = 2.5     # overhead clearance
ROOM_MIN_SIZE = 3.0           # smallest playable room (3m × 3m)
STAIR_WIDTH_MIN = 1.0         # navigation
STAIR_STEP_HEIGHT = 0.2       # Unity NavMesh traversable (0.15-0.25m)
WINDOW_SILL_HEIGHT = 0.9      # player doesn't clip through
CEILING_HEIGHT_STD = 2.8      # standard rooms
CEILING_HEIGHT_GRAND = 4.0    # grand halls, cathedrals
FLOOR_THICKNESS = 0.3         # no z-fighting
WALL_THICKNESS = 0.3          # structural minimum
```

Every walkable geometry handler MUST:
1. Import these constants
2. Clamp all dimensions to minimums
3. Return validation result in response

---

## 14. TEXTURE PIPELINE SPECIFICATION

### The Complete Automated Pipeline:

```
INPUT: Object with procedural Blender material
  │
  ├─[1] CREATE MATERIAL
  │   Option A: Blender procedural nodes (existing handlers)
  │   Option B: Material Maker → export PBR maps → import
  │   Option C: Dream Textures → AI-generated (prompt-based)
  │   Option D: Poly Haven / AmbientCG → download CC0 PBR set
  │   Option E: Paint System → hand-painted layers
  │
  ├─[2] ENHANCE
  │   DeepBump: generate normal map from albedo photo
  │
  ├─[3] BAKE (Principled Baker)
  │   Channels: albedo, normal, metallic, roughness, AO, emission, height
  │   Resolution: hero 2048, standard 1024, props 512
  │   Auto-swap: procedural nodes → Image Texture nodes
  │
  ├─[4] UPSCALE (Real-ESRGAN)
  │   512 → 2048 or 1024 → 4096
  │   Model: realesrgan-x4plus (general) or realesrgan-x4plus-anime (stylized)
  │
  ├─[5] FIX SEAMS (Anti-Seam)
  │   Fix visible UV seam lines
  │
  ├─[6] ATLAS PACK (Atlas Repacker)
  │   Combine multiple materials into texture atlas
  │   Update UV coordinates
  │
  ├─[7] EXPORT
  │   FBX with use_tspace=True
  │   Pack images into FBX
  │
  └─[8] UNITY IMPORT
      Auto-configured material mapping
      Normal map marked as Normal Map type
      Metallic map → Standard shader Metallic slot
```

### MCP command sequence for full pipeline:
```
blender_texture(action="bake_principled", object_name="Building", resolution=2048)
blender_texture(action="upscale", image_path="/tmp/albedo.png", scale=4)
blender_texture(action="fix_seams", object_name="Building")
blender_texture(action="repack_atlas", objects=["Building", "Tree"])
blender_export(export_format="fbx", filepath="/output/scene.fbx", apply_modifiers=true)
```

---

## 15. CRITICAL BUGS TO FIX

### Bug 1: Buildings are sealed boxes (0/10 walkability)
**File:** `blender_addon/handlers/worldbuilding.py`
**Problem:** Boolean subtraction code is commented out. Door/window frames are decorative geometry on solid walls.
**Fix:** Replace with Building Tools integration (handle_generate_real_building)
**Priority:** P0 — blocks everything

### Bug 2: Interiors produce zero geometry
**File:** `blender_addon/handlers/worldbuilding.py` → `generate_interior`
**Problem:** Returns JSON metadata only, no mesh materializer exists
**Fix:** Chain Proc Level Gen → Archimesh → furniture placement
**Priority:** P0

### Bug 3: Dungeons are 2D grid data only
**File:** `blender_addon/handlers/_dungeon_gen.py`
**Problem:** Outputs numpy grid (0/1/2/3), no 3D mesh generated
**Fix:** Grid-to-mesh converter using MakeTile tiles or direct bmesh generation
**Priority:** P0

### Bug 4: Textures export blank white
**File:** `blender_addon/handlers/texture.py` + `export.py`
**Problem:** Procedural materials destroyed on FBX export
**Fix:** Principled Baker bake-and-swap pipeline before every export
**Priority:** P0

### Bug 5: Terrain too low-res
**File:** `blender_addon/handlers/_terrain_noise.py`
**Problem:** Default 256×256 resolution, 50K erosion particles
**Fix:** Increase to 1024×1024, 500K particles
**Priority:** P1

### Bug 6: Trees are cones
**File:** `blender_addon/handlers/vegetation_lsystem.py`
**Problem:** Current L-system produces very basic shapes
**Fix:** tree-gen integration with real Weber & Penn algorithm
**Priority:** P1

### Bug 7: Scatter is dumb (hard cutoffs, no storytelling)
**File:** `blender_addon/handlers/_scatter_engine.py`
**Problem:** Poisson disk with fixed 15m affinity radius
**Fix:** OpenScatter integration with environmental storytelling rules
**Priority:** P1

---

## 16. QUALITY VERIFICATION MATRIX

After ALL phases complete, every row MUST be checked:

| Check | How to Verify | Pass Criteria |
|-------|--------------|---------------|
| Building walkability | Generate building → check door booleans | Player (1.8m tall) fits through every door |
| Interior walkability | Generate interior → flood-fill test | All rooms connected, all ≥ 3m × 3m |
| Dungeon walkability | Generate dungeon → connectivity test | All rooms reachable, all doors passable |
| Texture export | Generate + bake + export FBX → import | No blank/white textures on ANY surface |
| Tree quality | Generate tree → screenshot | Real branches, bark, leaves — NOT a cone |
| Scatter intelligence | Scatter on terrain → screenshot | Trees on slopes < 30°, mushrooms near dead trees |
| Terrain resolution | Generate terrain → measure detail | 1024×1024+, no grid artifacts at 10m distance |
| Water surfaces | Generate water → screenshot | Proper shore transitions, no z-fighting |
| Collision meshes | Export → check collision | Every solid surface has convex hull collision |
| Breakable objects | Fracture barrel → check pieces | Clean fracture, 5-20 pieces, no tiny fragments |
| Cloth simulation | Generate cloak → check drape | Realistic drape, no clipping through body |
| LOD chains | Generate LODs → check | 3 levels minimum, smooth transitions |
| MeshLint clean | Run on all exports | 0 critical issues (non-manifold, stray verts) |
| Player-scale pass | Measure all openings | All doors/corridors meet minimums |
| Animation retarget | Retarget Mixamo → custom rig | No bone mismatches, clean playback |
| City composition | Generate full city → screenshot | Roads connect, buildings don't overlap, walls enclose |
| FBX → Unity import | Import all exports | No errors, materials auto-assign, animations play |
| Performance budget | Profile scene | < 500K tris per district, < 100 draw calls |

---

## 17. ANTI-REGRESSION PROTOCOL

1. **ALWAYS read a file before editing it.** No exceptions.
2. **Test after every 3-5 changes.** Run `pytest` for relevant tests.
3. **Never loop on the same failing approach more than twice.** Try a fundamentally different approach.
4. **Never guess at API signatures.** Look up Building Tools, tree-gen, OpenScatter, etc. operators in their source code.
5. **If you break something while fixing something else, revert the regression immediately.**
6. **Run MeshLint before every export.**
7. **Run player-scale validation on every walkable geometry.**
8. **Screenshot every visual change** — use `blender_viewport(action="contact_sheet")`.

---

## 18. GIT WORKFLOW

```bash
# Before starting work:
git checkout master
git pull

# Create feature branch:
git checkout -b feature/addon-integration-phase-N

# After each phase:
git add -A
git commit -m "Phase N: [description]"

# Merge back:
git checkout master
git merge feature/addon-integration-phase-N
git branch -f develop master
```

**Branch naming:**
- `feature/building-tools-integration`
- `feature/texture-pipeline`
- `feature/terrain-upgrade`
- `feature/vegetation-treegen`
- `feature/dungeon-mesh-gen`
- `feature/city-composition`
- `feature/edit-handlers`
- `feature/quality-gate`

---

## SUMMARY — WHAT CODEX MUST DELIVER

| # | Deliverable | New Files | New Handlers | New Tests |
|---|-------------|-----------|-------------|-----------|
| 1 | Building Tools integration | 1 handler | 4 commands | 15 |
| 2 | Principled Baker integration | 1 handler | 2 commands | 10 |
| 3 | tree-gen integration | 1 handler | 2 commands | 10 |
| 4 | OpenScatter integration | 1 handler | 2 commands | 10 |
| 5 | Proc Level Gen integration | 1 handler | 2 commands | 15 |
| 6 | MakeTile integration | 1 handler | 2 commands | 8 |
| 7 | Cell Fracture integration | 1 handler | 1 command | 5 |
| 8 | Terrain HeightMap Gen | 1 handler | 1 command | 10 |
| 9 | Terrain config upgrade | 0 (modify existing) | 0 | 5 |
| 10 | Archimesh integration | 1 handler | 2 commands | 8 |
| 11 | BagaPie integration | 1 handler | 3 commands | 5 |
| 12 | Snap! integration | 1 handler | 3 commands | 5 |
| 13 | Spacetree integration | 1 handler | 1 command | 5 |
| 14 | Terrain Mixer integration | 1 handler | 2 commands | 5 |
| 15 | Gscatter integration | 1 handler | 1 command | 5 |
| 16 | Material Maker integration | 1 handler | 2 commands | 5 |
| 17 | Paint System integration | 1 handler | 1 command | 5 |
| 18 | Dream Textures integration | 1 handler | 2 commands | 5 |
| 19 | DeepBump integration | 1 handler | 1 command | 5 |
| 20 | Anti-Seam integration | 1 handler | 1 command | 5 |
| 21 | Atlas Repacker integration | 1 handler | 1 command | 5 |
| 22 | Poly Haven import | 1 handler | 1 command | 5 |
| 23 | Collision Tools integration | 1 handler | 2 commands | 8 |
| 24 | Cloth Builder integration | 1 handler | 1 command | 5 |
| 25 | Keemap Retarget integration | 1 handler | 2 commands | 8 |
| 26 | Rigodotify integration | 1 handler | 1 command | 5 |
| 27 | MeshLint integration | 1 handler | 1 command | 8 |
| 28 | Game Asset Optimizer | 1 handler | 1 command | 5 |
| 29 | ACT export integration | 1 handler | 1 command | 5 |
| 30 | Polycount integration | 1 handler | 1 command | 5 |
| 31 | LODify integration | 1 handler | 1 command | 5 |
| 32 | Proc City Gen integration | 1 handler | 2 commands | 8 |
| 33 | Anvil Level Design integration | 1 handler | 1 command | 5 |
| 34 | Mantaflow integration | 1 handler | 1 command | 5 |
| 35 | Edit handlers (10 total) | 1 handler file | 10 commands | 30 |
| 36 | Player-scale constants module | 1 shared module | 0 | 10 |
| 37 | Pre-export quality gate | 1 pipeline module | 1 command | 10 |
| 38 | Dungeon grid-to-mesh converter | 1 converter module | 1 command | 15 |
| 39 | blender_server.py action wiring | 0 (modify existing) | 0 | 0 |
| 40 | handlers/__init__.py registration | 0 (modify existing) | 0 | 0 |
| **TOTALS** | **~36 new files** | **~58 new commands** | **~300+ new tests** |

---

## ADDON INSTALL SCRIPT

```bash
#!/bin/bash
# install_all_addons.sh — Run in Blender's addons directory

# GitHub clones
git clone https://github.com/ranjian0/building_tools.git
git clone https://github.com/friggog/tree-gen.git
git clone https://github.com/GitMay3D/OpenScatter.git
git clone https://github.com/danielenger/Principled-Baker.git
git clone https://github.com/aaronjolson/Blender-Python-Procedural-Level-Generation.git
git clone https://github.com/sp4cerat/Terrain-HeightMap-Generator.git
git clone https://github.com/varkenvarken/Snap.git
git clone https://github.com/richeyrose/make-tile.git
git clone https://github.com/rking/meshlint.git
git clone https://github.com/varkenvarken/spacetree.git
git clone https://github.com/josauder/procedural_city_generation.git
git clone https://github.com/alexjhetherington/anvil-level-design.git
git clone https://github.com/nkeeline/Keemap-Blender-Rig-ReTargeting-Addon.git
git clone https://github.com/catprisbrey/Rigodotify.git
git clone https://github.com/HugoTini/DeepBump.git
git clone https://github.com/Vinc3r/Polycount.git
git clone https://github.com/carson-katri/dream-textures.git

# Real-ESRGAN setup (already integrated via shared/esrgan_runner.py):
#   pip install realesrgan --break-system-packages
#   OR download NCNN-Vulkan binary from https://github.com/xinntao/Real-ESRGAN/releases
#   Place realesrgan-ncnn-vulkan binary in PATH or configure in shared/config.py

# Bystedt's Cloth Builder (free Gumroad download):
#   Download from: https://3dbystedt.gumroad.com/l/cloth-builder
#   Install: Blender > Edit > Preferences > Add-ons > Install > select .zip

# Material Maker: download from materialmaker.org (standalone app, MIT license)
# Poly Haven: API access at polyhaven.com/api (CC0 textures, no API key needed)
# AmbientCG: API access at ambientcg.com/api (CC0 textures, no API key needed)

# Built-in addons to enable (run in Blender Python console):
# bpy.ops.preferences.addon_enable(module="archimesh")
# bpy.ops.preferences.addon_enable(module="ant_landscape")
# bpy.ops.preferences.addon_enable(module="add_curve_sapling")
# bpy.ops.preferences.addon_enable(module="object_fracture_cell")
# bpy.ops.preferences.addon_enable(module="rigify")

# Blender Extensions Platform addons (install via Blender UI):
# BagaPie, Terrain Mixer, Paint System, Anti-Seam, Atlas Repacker
# Collision Tools, Game Asset Optimizer, ACT, LODify, Gscatter

echo "All GitHub addons cloned. Enable built-in addons in Blender preferences."
```

---

## 19. AAA QUALITY STANDARDS — THE DIFFERENCE BETWEEN "WORKS" AND "SKYRIM"

Without these standards, you get functional cities (6-7/10). With them, you get AAA-competitive (8.5-9/10).

---

### 19A. DARK FANTASY MATERIAL PALETTE (MANDATORY)

Every city needs 30-40 distinct materials. Codex must create or source ALL of these before generating any city. Source: Poly Haven CC0 + Material Maker procedural + custom procedural nodes.

**Wall Materials (8):**
| Material ID | Description | Source | Tiling |
|-------------|-------------|--------|--------|
| `wall_rough_stone` | Rough-cut dark stone blocks | Poly Haven "castle_brick" | 2m×2m |
| `wall_smooth_stone` | Polished stone (noble district) | Poly Haven "stone_wall" | 2m×2m |
| `wall_dark_brick` | Dark fired brick with mortar | Material Maker procedural | 1m×1m |
| `wall_crumbling_stone` | Damaged stone, missing chunks (slum/ruins) | Poly Haven + damage overlay | 2m×2m |
| `wall_mossy_stone` | Stone with green moss growth | Base stone + moss blend | 2m×2m |
| `wall_timber_frame` | Half-timber (wood frame + plaster fill) | Material Maker | 4m×3m |
| `wall_wood_planks` | Horizontal wood planking (cottages) | Poly Haven "wood_planks" | 2m×2m |
| `wall_corrupted` | Stone with void corruption veins (brand zones) | Custom procedural | 2m×2m |

**Wood Materials (5):**
| Material ID | Description |
|-------------|-------------|
| `wood_aged_oak` | Dark aged oak planks with grain |
| `wood_dark_timber` | Structural beams, nearly black |
| `wood_rotting` | Decayed wood, soft edges (slum buildings) |
| `wood_charred` | Fire-damaged wood (ruins, forge area) |
| `wood_polished` | Polished dark wood (noble interiors) |

**Metal Materials (4):**
| Material ID | Description |
|-------------|-------------|
| `metal_iron_trim` | Black iron door hinges, window frames |
| `metal_rusted_iron` | Corroded iron (old gates, chains) |
| `metal_tarnished_bronze` | Greenish bronze (statues, bells) |
| `metal_blackened_steel` | Forge-darkened steel (weapons, armor) |

**Roof Materials (4):**
| Material ID | Description |
|-------------|-------------|
| `roof_dark_thatch` | Bundled dark straw (cottages, slum) |
| `roof_broken_slate` | Cracked grey slate tiles (standard) |
| `roof_moss_tile` | Clay tiles with moss (old buildings) |
| `roof_copper_green` | Oxidized copper sheets (noble, temple) |

**Floor/Ground Materials (8):**
| Material ID | Description |
|-------------|-------------|
| `floor_cobblestone` | Irregular dark cobblestones (main roads) |
| `floor_flagstone` | Cut stone slabs (plazas, noble areas) |
| `floor_dirt_packed` | Hard-packed earth (slum alleys) |
| `floor_wood_plank` | Indoor wood flooring |
| `floor_marble_cracked` | Cracked white marble (temple, ruins) |
| `ground_soil` | Dark forest soil |
| `ground_gravel` | Loose gravel paths |
| `ground_mud` | Wet mud (near water, rain areas) |

**Special/VeilBreakers Materials (4):**
| Material ID | Description |
|-------------|-------------|
| `vb_corruption_veins` | Glowing purple-black veins (VOID brand) |
| `vb_void_crystal` | Translucent dark crystal surface |
| `vb_bone_surface` | Bleached bone texture (DREAD brand) |
| `vb_venom_slime` | Toxic green-black organic surface |

**TOTAL: 33 materials. ALL must be created as PBR sets (albedo, normal, metallic, roughness, AO) at 1024×1024 minimum before any city generation begins.**

**Implementation:** Create a `MaterialLibrary` handler that:
1. Downloads/generates all 33 materials on first run
2. Caches them in `Assets/Art/Materials/Library/`
3. Maps material IDs to Blender material names
4. Auto-assigns based on building style, district, and surface type

---

### 19B. POLYGON BUDGET TABLE (ENFORCED BY HANDLERS)

Every handler MUST enforce these budgets. MeshLint + Polycount validate before export.

| Asset Type | Tri Budget (High LOD) | Medium LOD | Low LOD | Texture Res |
|------------|----------------------|------------|---------|-------------|
| Building exterior (standard) | 2,000-4,000 | 800-1,500 | 200-400 | 1024×1024 |
| Building exterior (hero) | 8,000-15,000 | 3,000-5,000 | 800-1,500 | 2048×2048 |
| Interior room (per room) | 3,000-8,000 | N/A | N/A | 1024×1024 |
| Tree (canopy + trunk) | 4,000-6,000 | 1,000-2,000 | Billboard | 1024×1024 |
| Rock (large boulder) | 800-2,000 | 300-600 | 100-200 | 512×512 |
| Prop (small: mug, plate) | 100-300 | N/A | N/A | 256×256 |
| Prop (medium: barrel, chair) | 300-800 | N/A | N/A | 512×512 |
| Prop (large: cart, stall) | 800-2,000 | 400-800 | N/A | 1024×1024 |
| Terrain chunk (64×64m) | 16,384 | 4,096 | 1,024 | Splatmap |
| City wall segment (8m) | 1,500-3,000 | 500-1,000 | 200 | 1024×1024 |
| **Full city district target** | **300,000-500,000** | **100,000-150,000** | **30,000-50,000** | — |

**Performance target:** 30fps on RTX 4060 Ti at 1080p with one full district loaded + adjacent districts at medium LOD.

---

### 19C. UV / TEXEL DENSITY STANDARDS

| Asset Category | Target Texel Density | UV Channel 1 | UV Channel 2 |
|----------------|---------------------|--------------|--------------|
| Hero assets (buildings, landmarks) | 512 pixels/meter | Manual unwrap | Lightmap (auto, non-overlapping) |
| Standard assets | 256 pixels/meter | Smart project or manual | Lightmap (auto) |
| Distant/background | 128 pixels/meter | Smart project | Lightmap (auto) |
| Terrain | Splatmap (4 layers) | Auto | Lightmap |
| Props | 256-512 pixels/meter | Auto unwrap | None (use light probes) |

**Rules:**
- NO visible UV stretching (max 15% distortion)
- Tiling materials on surfaces > 4m² (walls, floors, roofs)
- Break up tiling with: vertex color variation, decal overlays, detail normal maps
- Atlas packing utilization target: 85%+
- Lightmap padding: 4px minimum at 1024 resolution
- All UVs validated by `blender_uv(action="analyze")` before export

---

### 19D. INTERIOR PROP DENSITY BY ROOM TYPE

This is what separates "empty box" from "lived-in space." Codex MUST hit these counts.

| Room Type | Min Props | Max Props | Required Props | Detail Props (random fill) |
|-----------|-----------|-----------|----------------|---------------------------|
| **Tavern Hall** | 40 | 80 | 4-8 tables, 8-16 chairs, 1 bar counter, 1 fireplace, 2-4 kegs | mugs, plates, food, candles, bottles, broom, hanging meats, bread |
| **Bedroom** | 15 | 25 | 1 bed, 1 wardrobe, 1 chest, 1 nightstand | candle, book, chamber pot, mirror, rug, pillow |
| **Kitchen** | 20 | 35 | 1 cooking pot, 1 table, shelves, fireplace/oven | pots, pans, ladle, cutting board, hanging herbs, bread, vegetables |
| **Library** | 30 | 50 | 4-8 bookshelves, 1-2 desks, 2-4 chairs | books (stacked, open, shelved), scrolls, ink wells, candelabra, globe |
| **Forge** | 15 | 25 | 1 anvil, 1 forge, 1 quenching trough, weapon rack | hammers, tongs, ingots, horseshoes, bellows, coal pile |
| **Temple/Chapel** | 20 | 40 | altar, 4-8 pews, 2-4 candelabra, 1 lectern | prayer mats, offering bowls, incense, holy symbols, candles |
| **Shop** | 25 | 40 | 1 counter, display shelves, 1 chest (register) | wares by type (weapons, potions, food, clothing), signage |
| **Throne Room** | 15 | 30 | 1 throne, 2-4 banners, 2 guard positions | carpet runner, candlestands, weapon displays, map table |
| **Prison Cell** | 5 | 10 | 1 cot, 1 bucket, chains/shackles | straw, rat (dead), plate with old food, scratched tally marks |
| **Corridor** | 3 | 8 per 10m | torch sconces (every 5m) | wall tapestry, weapon rack, suit of armor, cobwebs |

**Prop placement rules (for Codex):**
1. Gravity: all props rest on surfaces (tables, floors, shelves) — NO floating objects
2. Clustering: props near furniture they belong to (plates ON tables, books ON shelves)
3. Randomization: ±10% position jitter, ±15° rotation jitter for natural look
4. Scale variation: ±10% per prop instance
5. Collision: no prop-prop intersection (minimum 5cm gap)
6. Storytelling: 1-3 "story props" per room (overturned chair = struggle, open book = interrupted reading, blood stain = danger)

---

### 19E. LIGHTING PLACEMENT RULES

**Exterior Lighting:**
| Light Source | Placement Rule | Color Temp | Intensity | Radius |
|-------------|---------------|------------|-----------|--------|
| Torch sconce | Every 10-15m on walls, flanking every door, at intersections | 2200K (warm amber) | 1.5 | 6m |
| Street lantern | Every 15-20m along main roads | 2500K (warm yellow) | 2.0 | 8m |
| Window glow | Every window on occupied buildings | 2000K (firelight) | 0.5 (emission) | N/A |
| Forge glow | Blacksmith building, emanates from forge | 1800K (orange-red) | 3.0 | 10m |
| Brazier | Gate entrances, guard posts, plazas | 2200K | 2.5 | 5m |
| Corruption glow | VOID brand zones | 8000K (cold purple) | 1.0 | 4m |

**Interior Lighting:**
| Light Source | Placement Rule | Color Temp | Intensity | Radius |
|-------------|---------------|------------|-----------|--------|
| Fireplace | 1 per common room, against wall | 1800K | 3.0 | 8m |
| Candle cluster | Every table, nightstand, desk | 2200K | 0.5 | 2m |
| Chandelier | Grand rooms (tavern hall, throne room), centered | 2200K | 2.0 | 6m |
| Wall sconce | Every 5m in corridors, flanking doorways | 2200K | 1.0 | 4m |
| Skylight | Libraries, temples (if roof allows) | 6500K (daylight) | 1.5 | 10m |

**Ambient:**
- 1 reflection probe per room interior
- 1 light probe group per 20m² exterior
- Volumetric fog in alleys (density 0.02, color grey-blue)
- Volumetric fog in corruption zones (density 0.05, color dark purple)

**Implementation:** Every building handler and interior handler MUST output a `lighting_markers` list in its result dict. Each marker: `{type, position, color_temp, intensity, radius}`. Unity import script converts markers to actual lights.

---

### 19F. BUILDING VARIETY SYSTEM (Anti-Repetition)

A city with 50 identical buildings = instant "procedural" look. This system prevents that.

**Variation Axes (multiply together for unique combinations):**

| Axis | Options | Count |
|------|---------|-------|
| Width | narrow (4m), standard (6m), wide (8m) | 3 |
| Floors | 1, 2, 3 | 3 |
| Roof type | gable, hip, flat, mansard | 4 |
| Facade style | plain, ornate, damaged, overgrown | 4 |
| Material set | stone, wood, timber-frame, mixed | 4 |
| Window style | small square, tall narrow, arched, shuttered | 4 |
| Door style | simple, arched, double, reinforced | 4 |

**Total unique combinations: 3 × 3 × 4 × 4 × 4 × 4 × 4 = 9,216 possible buildings**

**Per-District Style Rules:**

```python
DISTRICT_STYLES = {
    "noble": {
        "width_bias": "wide",          # prefer wider buildings
        "floor_range": [2, 3],          # taller
        "roof_types": ["hip", "mansard"],
        "facade": ["ornate"],
        "materials": ["smooth_stone", "marble_cracked"],
        "windows": ["arched", "tall_narrow"],
        "doors": ["double", "arched"],
        "has_garden": True,
        "weathering": 0.1,              # minimal damage
    },
    "market": {
        "width_bias": "standard",
        "floor_range": [1, 2],
        "roof_types": ["gable", "flat"],
        "facade": ["plain", "ornate"],
        "materials": ["timber_frame", "mixed"],
        "windows": ["shuttered", "small_square"],
        "doors": ["simple", "reinforced"],
        "has_awning": True,             # shop awnings
        "weathering": 0.3,
    },
    "slum": {
        "width_bias": "narrow",         # cramped
        "floor_range": [1, 2],
        "roof_types": ["gable", "flat"],
        "facade": ["damaged", "plain"],
        "materials": ["wood", "rotting_wood"],
        "windows": ["small_square", "boarded"],
        "doors": ["simple"],
        "lean_angle": [-3, 3],          # buildings lean!
        "weathering": 0.7,              # heavy damage
    },
    "temple": {
        "width_bias": "wide",
        "floor_range": [1, 2],
        "roof_types": ["gable"],        # cathedral-style
        "facade": ["ornate"],
        "materials": ["smooth_stone"],
        "windows": ["arched"],          # stained glass
        "doors": ["double", "arched"],
        "has_tower": True,              # bell tower / steeple
        "weathering": 0.2,
    },
    "corruption_zone": {
        "width_bias": "any",
        "floor_range": [1, 2],
        "roof_types": ["damaged_gable", "collapsed"],
        "facade": ["damaged", "corrupted"],
        "materials": ["crumbling_stone", "corrupted"],
        "windows": ["broken", "boarded"],
        "doors": ["broken_off"],
        "corruption_level": [0.5, 1.0],
        "weathering": 0.9,
        "void_crystals": True,
    },
}
```

**Hero buildings (2-3 per city, manually configured):**
- Tavern (named, unique sign, 2 floors, full interior)
- Temple/Cathedral (largest building, unique spire/tower)
- Lord's Manor or Castle Keep (dominant sightline from city gate)
- Blacksmith (visible forge glow, unique chimney)

---

### 19G. WEATHERING PIPELINE (Mandatory Post-Processing)

Every building gets a weathering pass BEFORE texture baking. This is what makes buildings look real vs. CG.

```
Building mesh generated (Building Tools)
    ↓
[1] MOSS GROWTH — vertex paint green at base (height < 1m),
    north-facing walls (dot product with (0,0,-1) > 0.5),
    near water sources (distance < 20m)
    ↓
[2] DIRT STREAKS — procedural dirt texture below windows,
    rain drip lines from roof edges,
    intensity = building_age × 0.1
    ↓
[3] DAMAGE PATCHES — random 5-15% of wall surface gets
    "crumbling" displacement, missing stone blocks,
    intensity scales with district.weathering value
    ↓
[4] AGE DARKENING — multiply albedo by 0.7-0.9 based on
    building_age, heavier at ground level
    ↓
[5] IVY/VINE GROWTH — BagaPie ivy on 10-30% of buildings
    (weighted by district.weathering), prefer north walls
    and near-ground surfaces
    ↓
Principled Baker bakes ALL channels with weathering applied
```

**Implementation:** Add `weathering_pass(object, intensity, style)` function called by every building handler between mesh generation and texture baking.

---

### 19H. COMPOSE_CITY PIPELINE — EXACT DATA FLOW

This is the complete pipeline Codex must implement. Each step's output feeds the next step's input.

```python
def compose_city(params: dict) -> dict:
    """
    Full city generation pipeline.

    Params:
        city_type: "walled_medieval" | "open_village" | "fortress" | "port_town"
        district_count: int (2-6)
        buildings_per_district: int (10-30)
        style: "dark_fantasy" (locked)
        has_walls: bool
        has_river: bool
        has_castle: bool
        corruption_district: str | None (brand name if any district is corrupted)
        populate_interiors: list[str] (which building types get interiors)
        seed: int

    Pipeline:
    """

    # STEP 1: Generate terrain base
    terrain = generate_terrain(
        resolution=1024,
        height_scale=20.0,
        erosion_iterations=500000,
        seed=seed,
    )
    # Output: heightmap ndarray, slope_map, flow_map

    # STEP 2: Determine city footprint on terrain
    city_center = find_flat_area(terrain, min_radius=200)  # meters
    city_boundary = generate_boundary(city_center, radius=150, type=city_type)
    # Output: boundary polygon (list of 2D points)

    # STEP 3: Generate district zones
    districts = voronoi_districts(
        boundary=city_boundary,
        count=district_count,
        types=["noble", "market", "residential", "slum", "temple"],
    )
    # Output: list of {polygon, type, style_rules}

    # STEP 4: Generate road network
    roads = generate_road_network(
        districts=districts,
        style="organic",  # or "grid" for fortress
        main_roads=3,
        secondary_subdivision=2,
    )
    # Output: list of road polylines + widths

    # STEP 5: Flatten terrain under roads + buildings
    terrain = flatten_for_roads(terrain, roads, blend_radius=5.0)
    terrain = flatten_for_districts(terrain, districts, blend_radius=10.0)
    # Output: modified heightmap

    # STEP 6: Generate road geometry
    road_meshes = []
    for road in roads:
        mesh = create_road_mesh(road, material="floor_cobblestone",
                                curbs=True, drainage=True)
        road_meshes.append(mesh)

    # STEP 7: Generate buildings per district
    all_buildings = []
    for district in districts:
        plots = generate_building_plots(
            district=district,
            roads=roads,
            min_spacing=2.0,
            setback=1.5,
        )
        # Output: list of {position, rotation, width, depth}

        style = DISTRICT_STYLES[district.type]
        for plot in plots:
            building = generate_real_building(
                position=plot.position,
                rotation=plot.rotation,
                width=random_from(style.width_bias),
                floors=random.randint(*style.floor_range),
                roof_type=random.choice(style.roof_types),
                facade=random.choice(style.facade),
                material=random.choice(style.materials),
                openings=generate_openings(style),
                weathering=style.weathering,
                seed=seed + plot.index,
            )
            all_buildings.append(building)

    # STEP 8: Generate hero buildings (unique, manually spec'd)
    hero_buildings = generate_hero_buildings(
        city_type=city_type,
        districts=districts,
        tavern=True, temple=True, manor=True,
    )
    all_buildings.extend(hero_buildings)

    # STEP 9: City walls (if applicable)
    if has_walls:
        walls = generate_city_walls(
            boundary=city_boundary,
            gate_positions=road_exits,
            tower_spacing=40.0,
            wall_height=6.0,
            walkway=True,
            crenellations=True,
        )

    # STEP 10: Populate interiors
    for building in all_buildings:
        if building.type in populate_interiors:
            interior = generate_walkable_interior(
                building=building,
                room_types=BUILDING_ROOM_MAP[building.type],
                prop_density=PROP_DENSITY[building.room_type],
            )
            # Interior includes lighting_markers

    # STEP 11: Apply weathering to all buildings
    for building in all_buildings:
        weathering_pass(building, intensity=building.weathering)

    # STEP 12: Vegetation scatter
    scatter_vegetation(
        terrain=terrain,
        exclude_zones=[city_boundary],  # no trees inside city
        rules=SCATTER_RULES["FOREST_ZONE"],
        tree_species=["dead_oak", "ancient_pine"],
    )
    # Inside city: garden trees, ivy, window boxes
    scatter_city_vegetation(
        buildings=all_buildings,
        districts=districts,
        ivy_chance=0.2,
        garden_chance={"noble": 0.8, "market": 0.1, "slum": 0.0},
    )

    # STEP 13: Scatter detail props (Tripo batch)
    scatter_city_props(
        roads=roads,
        districts=districts,
        prop_budget=200,  # max Tripo calls
        props_per_road_segment=3,  # barrels, crates, carts
        props_per_building=2,      # signs, flower pots, lanterns
    )

    # STEP 14: Place lighting markers
    lighting = generate_city_lighting(
        buildings=all_buildings,
        roads=roads,
        rules=LIGHTING_RULES,
    )

    # STEP 15: River (if applicable)
    if has_river:
        river = carve_river(terrain, flow_map, width=8.0)
        bridges = generate_bridges(river, roads)

    # STEP 16: Material library — assign all materials
    assign_materials(
        buildings=all_buildings,
        roads=road_meshes,
        terrain=terrain,
        material_library=DARK_FANTASY_PALETTE,
    )

    # STEP 17: Bake ALL textures (Principled Baker)
    for obj in all_objects:
        bake_principled(obj, resolution=get_resolution(obj))
        # Swap procedural → image texture nodes

    # STEP 18: Generate LODs
    for obj in all_objects:
        generate_lods(obj, levels=[1.0, 0.4, 0.1])

    # STEP 19: Quality gate
    for obj in all_objects:
        meshlint_validate(obj)        # topology check
        polycount_check(obj)          # budget check
        collision_hull(obj)           # physics collision
        player_scale_validate(obj)    # walkability check

    # STEP 20: Export per-district FBX
    for district in districts:
        export_fbx(
            objects=district.all_objects,
            filepath=f"Export/{city_name}/{district.name}.fbx",
            use_tspace=True,
            apply_modifiers=True,
        )

    return {
        "city_name": city_name,
        "districts": len(districts),
        "buildings": len(all_buildings),
        "total_tris": sum(b.tri_count for b in all_buildings),
        "lighting_markers": len(lighting),
        "export_paths": [...],
    }
```

---

### 19I. MODULAR KIT GRID STANDARD

All modular pieces MUST snap to this grid:

```
Base unit: 2m × 2m × 3m (W × D × H)

Wall segments:  2m, 4m, 6m, 8m lengths × 3m height
                Thickness: 0.3m
Floor tiles:    2m × 2m, 4m × 4m
Stairs:         2m width, 3m rise (one floor), 0.2m step height
Columns:        0.3m × 0.3m × 3m
Doorframe:      1.2m × 2.4m (fits inside 2m wall segment)
Window frame:   0.8m × 1.2m (centered in wall segment)
Archway:        2m × 2.8m

Snap grid: 0.5m increments (all vertices align to 0.5m grid)
Origin point: bottom-center of each piece
Pivot: world-space aligned (no rotation on export)
```

---

---

### 19J. TERMINAL AGENT INTEGRATION — COWORK_BRIDGE MATERIAL MAPPING

The terminal agent's `Tools/cowork_bridge/` scripts define 8 runtime material slots used in `build_aaa_town.py`. These MUST map 1:1 to the Section 19A palette:

```
Terminal Agent Material  →  Handoff Palette ID           →  BSDF Values
─────────────────────────────────────────────────────────────────────────
VB_Stone                 →  wall_rough_stone              →  (0.22, 0.19, 0.16, 1), R=0.88, M=0.0
VB_DarkStone             →  wall_dark_brick               →  (0.14, 0.12, 0.10, 1), R=0.92, M=0.0
VB_Timber                →  wood_weathered_oak            →  (0.22, 0.13, 0.06, 1), R=0.70, M=0.0
VB_Slate                 →  roof_broken_slate             →  (0.16, 0.16, 0.20, 1), R=0.78, M=0.0
VB_Glass                 →  (NEW: window_leaded_glass)    →  (0.12, 0.18, 0.25, 1), R=0.15, M=0.0
VB_Iron                  →  metal_wrought_iron            →  (0.12, 0.12, 0.14, 1), R=0.50, M=0.82
VB_Plaster               →  wall_stained_plaster          →  (0.42, 0.38, 0.32, 1), R=0.92, M=0.0
VB_Floor                 →  floor_wood_plank              →  (0.20, 0.15, 0.10, 1), R=0.80, M=0.0
```

**Implementation rule:** The `MaterialLibrary` handler (Section 19A) MUST accept BOTH naming conventions. When the terminal agent's `build_aaa_town.py` assigns `VB_Stone`, the material system should resolve it to `wall_rough_stone` and use the full PBR set. Add an alias map:

```python
MATERIAL_ALIASES = {
    "VB_Stone": "wall_rough_stone",
    "VB_DarkStone": "wall_dark_brick",
    "VB_Timber": "wood_weathered_oak",
    "VB_Slate": "roof_broken_slate",
    "VB_Glass": "window_leaded_glass",  # NEW material added
    "VB_Iron": "metal_wrought_iron",
    "VB_Plaster": "wall_stained_plaster",
    "VB_Floor": "floor_wood_plank",
}
```

**Updated material count:** 34 (33 original + `window_leaded_glass`). All 34 need PBR sets.

The terminal agent's `generate_starter_city_map.py` MAP_SPEC format is already compatible with `asset_pipeline(action="compose_map")`. No format conflicts.

---

### 19K. WILDERNESS LOCATION TYPES — COMPLETE SPECS

The compose_map pipeline supports `locations` list entries. Beyond cities/towns/dungeons, Codex MUST implement these wilderness location types:

#### 19K-1. BANDIT CAMP
```python
{
    "type": "bandit_camp",
    "name": str,                     # e.g. "RoadwatchCamp"
    "camp_size": "small" | "medium" | "large",  # 3-5 | 6-10 | 11-15 tents
    "layout": "ring" | "linear" | "hilltop",
    "fortification": "none" | "palisade" | "barricade",
    "corruption_level": float,       # 0.0-1.0, affects texture tint
}
```

**Required geometry:**
- **Tents:** Cloth-draped pole structures, 2.5m × 3m × 2.2m height. NOT cubes with tent texture — actual angled poles with fabric mesh draped over. 3 variants (small sleeping tent, large command tent, lean-to).
- **Palisade:** Sharpened log fence, height 2.5m, log diameter 0.15m, spacing 0.02m, gate opening 2m wide. Constructed from cylindrical mesh with randomized heights (±0.3m) and lean angles (±5°).
- **Barricade:** Overturned carts, stacked crates, log barriers. Composed from prop kit meshes placed along perimeter.
- **Campfire:** Central fire pit with stone ring (12 stones), firewood stack, cooking spit. Particle emitter marker for Unity VFX.
- **Watch tower:** 4-post wooden tower, 5m height, platform at 4m, ladder access. Budget: 800 tris.
- **Props per tent:** bedroll, weapon rack, loot sack, lantern, bones/skulls (if corrupted)
- **Scatter:** patrol paths marked with waypoint empties (NPC_Patrol_01, NPC_Patrol_02...), loot containers marked with LOOT_Container empties

**Poly budget:** Small 15K, Medium 30K, Large 50K total.

#### 19K-2. WILDERNESS RUINS
```python
{
    "type": "ruins",
    "name": str,
    "ruin_age": "recent" | "ancient" | "primordial",
    "original_type": "tower" | "chapel" | "gatehouse" | "shrine" | "homestead" | "bridge",
    "damage_level": float,           # 0.3-0.9 (percentage destroyed)
    "overgrown": bool,               # ivy, roots, moss overgrowth
    "has_basement": bool,            # accessible underground chamber
}
```

**Required geometry:**
- Start with the INTACT building geometry (from the building generator)
- Apply destruction: random face deletion (damage_level %), edge loop displacement for cracks, fallen debris as separate meshes
- **Collapse rules:** Roofs fall first (damage > 0.3), upper floors next (> 0.5), walls crumble inward (> 0.7), foundations remain until (> 0.9)
- **Debris:** Scattered stone/wood chunks auto-generated from deleted faces. Each deleted face spawns 2-4 debris pieces at random offsets within 3m radius
- **Overgrowth (if enabled):** Ivy mesh climbing surviving walls (separate UV, tiling ivy texture), moss vertex paint on top surfaces, root meshes penetrating floor
- **Basement (if enabled):** Stone-walled chamber below ground, accessed via broken floor section or revealed staircase. Room dimensions: 4m × 4m × 2.5m minimum

**Poly budget:** Same as intact building × 1.3 (debris adds geometry)

#### 19K-3. CAVES
```python
{
    "type": "cave",
    "name": str,
    "cave_depth": "shallow" | "medium" | "deep",  # 1-2 | 3-5 | 6-10 chambers
    "cave_style": "natural" | "mining" | "beast_lair" | "corrupted",
    "entrance_type": "cliff_face" | "hillside" | "sinkhole" | "hidden",
    "has_water": bool,               # underground pool/stream
}
```

**Required geometry:**
- **Entrance:** Irregular opening in terrain, minimum 2.2m height × 1.5m width (player-scale). Transition mesh blends cave mouth into terrain.
- **Chambers:** Convex hull-based room generation with noise-displaced vertices for organic walls. NO box rooms — all surfaces must have displacement noise (0.3-0.8m amplitude).
- **Tunnels:** Connecting corridors between chambers, minimum 1.5m × 2.2m cross-section, gentle curves (bezier path extrusion).
- **Stalactites/stalagmites:** Cone-based meshes with noise, placed on ceiling/floor. Density: 2-5 per chamber.
- **Mining variant:** Add support beam meshes (timber cross-braces every 3m), rail tracks, ore vein textures on walls.
- **Beast lair variant:** Add bone pile props, nest geometry (matted branches), claw-mark normal map overlay.
- **Corrupted variant:** Void crystal props, corruption vein texture, glowing particle markers.

**Poly budget:** Shallow 20K, Medium 50K, Deep 100K

#### 19K-4. BOSS ARENAS (OUTDOOR)
```python
{
    "type": "boss_arena",
    "name": str,
    "arena_type": "corrupted_clearing" | "ruined_colosseum" | "volcanic_crater" | "frozen_lake" | "void_rift",
    "radius": float,                 # 15-40m
    "cover_points": int,             # 3-8 destructible cover objects
    "phase_triggers": int,           # 1-3 environmental phase changes
    "hazard_zones": list,            # areas of damage (lava, void, spikes)
}
```

**Required geometry:**
- Circular/elliptical arena floor with raised rim (1-2m height) to contain combat
- Cover objects: destructible pillars (3 LODs: intact, damaged, rubble), rock formations, ruined walls
- Phase trigger markers: empties named `PHASE_TRIGGER_01` through `PHASE_TRIGGER_N` at positions where environmental changes activate
- Hazard zones: marked with empties + ground decal UV regions (lava crack, void pool, spike field)
- Arena must be navigable — flat fighting surface with no invisible collision traps

**Poly budget:** 40K-80K depending on type

---

### 19L. WATER BODIES — COMPLETE SPECS

Every water type MUST be generated as actual geometry with proper material setup, not just a flat plane.

#### 19L-1. PONDS
```python
{
    "water_type": "pond",
    "radius": float,        # 3-15m
    "depth": float,          # 0.3-2.0m
    "has_shore_blend": True, # terrain blends into water edge
}
```

**Geometry:**
- Displaced disc mesh, subdivided 32×32, slight concavity (center lower)
- Shore: terrain vertices within 2m of pond edge slope down to water level
- Shoreline detail ring: mud/sand material transition, reeds/cattails as card meshes around 40% of perimeter
- Water material: transparent with scroll UV for ripple, depth fade (shallow = lighter), Fresnel reflection
- Underwater rocks/pebbles visible through shallow sections

#### 19L-2. LAKES
```python
{
    "water_type": "lake",
    "dimensions": [float, float],  # width × depth in meters (30-200m)
    "shore_type": "sandy" | "rocky" | "swampy" | "cliff",
    "has_island": bool,
    "has_dock": bool,
}
```

**Geometry:**
- Large water plane mesh, wave vertex displacement via vertex shader marker
- Shore: 5m transition zone with material blend (terrain → mud → sand → water)
- Rocky shore: boulder meshes placed along 30-60% of shoreline
- Dock (if enabled): timber pier structure, 2m wide × 8-15m long, mooring posts, rope coils
- Island (if enabled): small terrain piece (10-30m diameter) positioned within lake bounds

#### 19L-3. RIVERS
Already handled by `blender_environment(action="carve_river")`, but Codex must ensure:
- Width variation along length (narrow at source, wider at mouth)
- Bank erosion: terrain vertices near river displaced downward, exposed soil/rock material
- Bridge support: where roads cross rivers, auto-generate bridge geometry (stone arch, wooden plank)
- Ford points: shallow crossings marked with `FORD_POINT` empties for AI pathfinding

#### 19L-4. OCEAN / COASTAL
```python
{
    "water_type": "ocean",
    "shore_length": float,    # coastline length in meters
    "cliff_height": float,    # 0 for beach, 5-30m for cliffs
    "has_beach": bool,
    "has_harbor": bool,
}
```

**Geometry:**
- Ocean plane extends to terrain edge boundary, large enough to fill camera frustum
- **Beach:** Gradual terrain slope to water level, sand material zone (10-20m width), dune meshes, driftwood props, shell/seaweed scatter
- **Cliffs:** Sheer terrain edge with exposed rock face, wave crash VFX marker at base, sea cave openings (optional)
- **Harbor:** Wooden quay structures along shoreline, 3-5 mooring posts, crane/hoist mesh, warehouse buildings facing waterfront
- Wave material: scrolling normal map with 2 UV layers at different speeds for realistic wave interference pattern

**Water material properties (ALL water types):**
```
Base Color: (0.04, 0.08, 0.12, 0.7)   # Deep dark blue-green, semi-transparent
Roughness: 0.05                         # Near-mirror for calm, 0.15 for choppy
Metallic: 0.0
IOR: 1.33                              # Water refraction
Normal map: tiling caustic pattern, 2048×2048
Scroll speed: UV1 = (0.02, 0.01), UV2 = (-0.01, 0.015)
Shore blend: alpha fade over 2m using vertex color or depth texture
Foam: white emission along shore contact line (particle or mesh strip)
```

---

### 19M. CASTLE AND FORTRESS GENERATION — DETAILED SPECS

Beyond `blender_worldbuilding(action="generate_castle")`, Codex must ensure these standards:

```python
{
    "type": "castle",
    "name": str,
    "castle_style": "motte_bailey" | "concentric" | "hilltop" | "waterfront" | "ruined",
    "outer_size": float,         # 30-80m outer wall perimeter radius
    "keep_size": float,          # 10-25m keep footprint
    "tower_count": int,          # 4-8 corner/wall towers
    "has_moat": bool,
    "has_drawbridge": bool,
    "has_interior_keep": bool,   # walkable keep interior
    "garrison_size": int,        # NPC capacity for patrol routes
}
```

**Required structural elements:**
1. **Curtain wall:** 3m thick, 8-12m height, with walkable battlements (1m parapet, 0.5m crenellation gaps at 2m intervals). Actual walkable surface with collision.
2. **Towers:** Cylindrical or square, 12-16m height, 4-6m diameter, with internal spiral staircase geometry (1m wide, 0.2m step height). Arrow slit openings every 90° per floor.
3. **Gatehouse:** Double-door entrance, 3m × 4m opening, portcullis slot, murder holes in ceiling, flanking towers.
4. **Keep:** Central structure, 2-3 floors. If `has_interior_keep`: great hall (floor 1), lord's chamber (floor 2), tower top (floor 3 or roof access). ALL rooms player-scale per Section 19 standards.
5. **Bailey:** Open courtyard between curtain wall and keep. Contains: well, stable building, armory building, barracks building.
6. **Moat (if enabled):** Water-filled trench, 4m wide × 2m deep, surrounds outer wall. Uses pond water material.
7. **Drawbridge (if enabled):** Riggable mesh with hinge point at gatehouse. Vertex groups: `bridge_plank`, `chain_left`, `chain_right` for Unity animation.

**NPC patrol infrastructure:**
- Battlement patrol: waypoints every 10m along wall tops
- Gate guard: 2 positions flanking gatehouse entrance
- Courtyard patrol: circuit through bailey buildings
- Tower posts: 1 position per tower top
- All waypoints as empties: `NPC_Patrol_Castle_XX`

**Poly budget:** Small castle 80K, Large castle 150K, Ruined castle 120K

---

### 19N. NPC USABILITY — NAVMESH, PATROL, INTERACTION

**EVERY walkable space (building, interior, settlement, dungeon, cave) MUST include NPC infrastructure:**

#### NavMesh Compatibility
- All walkable surfaces: flat within 5° tolerance (Unity NavMesh agent requirement)
- Step height maximum: 0.4m (NavMeshAgent.stepHeight default)
- Slope maximum: 45° for walkable, 30° preferred
- Minimum corridor width: 1.5m (NavMeshAgent.radius = 0.5m, need clearance for 2 agents passing)
- Door openings: minimum 1.0m wide (single), 2.0m (double) — agent must fit with 0.2m clearance each side
- NO invisible collision gaps: every walkable surface must be contiguous mesh

#### Patrol Waypoints (Blender → Unity)
```
Empty naming convention:
  NPC_Patrol_{LocationName}_{RouteID:02d}_{WaypointID:02d}
  Example: NPC_Patrol_StarterCity_03_07

Properties (stored as custom Blender properties on each empty):
  npc_wait_time: float     # seconds to pause at this point (0 = walk through)
  npc_animation: str       # "idle" | "inspect" | "sit" | "guard" | "sweep" | "pray"
  npc_facing: [x, y, z]   # direction to face when stopped (optional)
```

Minimum patrol density by location type:
| Location | Min Routes | Min Waypoints/Route | Required Animations |
|----------|-----------|---------------------|---------------------|
| Town market | 3 | 6 | idle, inspect, sit |
| Town residential | 2 | 4 | idle, sweep |
| Castle battlements | 2 | 8 | guard, idle |
| Castle courtyard | 2 | 5 | guard, idle, inspect |
| Tavern interior | 1 | 4 | sit, idle |
| Temple interior | 1 | 3 | pray, idle |
| Dungeon (guard) | 2 | 4 | guard, idle, inspect |

#### Interaction Zones
```
Empty naming convention:
  INTERACT_{Type}_{Name}
  Example: INTERACT_Merchant_BlacksmithAnvil

Types:
  Merchant    — shop/trade trigger (1.5m radius)
  Dialogue    — NPC conversation trigger (2.0m radius)
  Rest        — save/heal point (bed, campfire) (1.5m radius)
  Craft       — forge, alchemy table (1.5m radius)
  Loot        — container (chest, barrel, corpse) (1.0m radius)
  Door        — scene transition (1.0m × 2.2m box trigger)
  Examine     — lore object, readable (1.0m radius)
  Sit         — player sit point (chair, bench) — position + facing direction

Properties on empties:
  interact_radius: float
  interact_prompt: str     # "Talk to Merchant" / "Open Chest" / "Read Inscription"
  interact_required_key: str  # optional: key item name needed
```

#### Spawn Points
```
Empty naming convention:
  SPAWN_{Type}_{ID:03d}
  Types: Player, NPC, Monster, Boss

Properties:
  spawn_level_range: [int, int]
  spawn_faction: str
  spawn_density: str       # "lone" | "pair" | "group" | "swarm"
```

---

### 19O. INTELLIGENT ROAD AND STREET DESIGN

Roads are NOT just texture strips on terrain. They are geometry-aware, terrain-conforming infrastructure.

#### Road Hierarchy
| Road Type | Width | Material | Curbs | Drainage | Sidewalk | Speed |
|-----------|-------|----------|-------|----------|----------|-------|
| **Highway** (between cities) | 5-6m | `floor_cobblestone` | Stone curbs 0.15m | Ditches both sides 0.5m deep | None | Travel |
| **Main road** (through city) | 4-5m | `floor_cobblestone` | Stone curbs 0.1m | Center crown (2cm rise) | 1.5m flagstone both sides | Patrol |
| **Side street** | 2.5-3.5m | `floor_cobblestone` | None | Slope to center | Optional 1m one side | Walk |
| **Alley** | 1.5-2.5m | `floor_dirt_packed` | None | None | None | Sneak |
| **Path** (wilderness) | 1-2m | `ground_gravel` or `ground_soil` | None | None | None | Explore |
| **Bridge** | Same as road it carries | Stone/wood deck | Parapet 1m both sides | None | Part of deck | Cross |

#### Terrain Conformance Rules
1. **Flatten under roads:** Terrain vertices within road width + 1m blend zone are height-matched to road spline
2. **Road follows terrain slope** up to 15°. Above 15°, switch to stairs/switchbacks
3. **Switchbacks on steep terrain:** Road zigzags with hairpin turns (min radius 4m), retaining walls on cut-side
4. **Bridges over water:** Detect river/ravine crossings along road spline. Auto-generate bridge geometry:
   - **Stone bridge:** Arch construction, 1-3 arches depending on span, parapet walls, keystone detail
   - **Wood bridge:** Post-and-beam, plank deck, rope railings for paths
5. **Intersections:** Where 2+ roads meet, generate expanded node:
   - T-junction: road end terminates flush with crossing road, corner radius 1m
   - Crossroads: 4-way intersection with optional fountain/statue plaza (radius 3m)
   - Roundabout/plaza: circular expanded area (radius 5-10m) with central feature

#### Street Intelligence (Settlement Roads)
- **Face buildings:** Roads run BETWEEN building plots, never THROUGH buildings
- **Access:** Every building front door faces a road within 3m
- **Variety:** Road width varies ±0.5m along length for organic feel
- **Drainage:** Main roads have 2cm center crown (cross-section is shallow arc, not flat)
- **Wear patterns:** Vertex color darkening at intersections and building entrances
- **Turning space:** Minimum 3m turning radius at dead ends (cart turnaround)
- **Steps/ramps:** Where road elevation changes > 0.5m over 3m, auto-generate steps (0.2m rise, 0.3m tread)

#### Road Mesh Generation (Codex Implementation)
```python
def generate_road_mesh(spline_points, width, material, curbs=True, drainage=True):
    """
    1. Sample spline at 1m intervals → centerline points
    2. At each point, compute perpendicular direction
    3. Extrude cross-section profile:
       - If drainage: center 2cm higher than edges (arc profile)
       - If curbs: add 0.1-0.15m raised edges
       - If sidewalk: extend flat surface beyond curbs
    4. Connect cross-sections into quad strip mesh
    5. Project onto terrain (raycast each vertex down to terrain surface + 0.05m offset)
    6. Generate UVs: U = across road (0-1), V = along road (tiling at 1:1 texel density)
    7. Apply material from palette
    8. Blend terrain at edges: terrain vertices within 1m of road edge lerp to road height
    """
```

---

### 19P. BLOOD AND GORE TEXTURE/VFX SYSTEM

**VeilBreakers is a dark fantasy RPG — blood and visceral combat feedback are ESSENTIAL for the tone.**

#### Blood Material Palette (ADD to Section 19A)
| Material ID | Description | BSDF Values |
|-------------|-------------|-------------|
| `vb_blood_fresh` | Bright arterial blood (hit VFX, splatter) | Color: (0.45, 0.02, 0.02, 1), R=0.25, M=0.0, SSS: (0.8, 0.1, 0.05) |
| `vb_blood_dried` | Darkened oxidized blood (stains, old scenes) | Color: (0.18, 0.04, 0.02, 1), R=0.75, M=0.0 |
| `vb_blood_pool` | Standing blood puddle (glossy, reflective) | Color: (0.35, 0.01, 0.01, 0.9), R=0.1, M=0.0, IOR=1.4 |
| `vb_blood_trail` | Drag marks / blood smears | Color: (0.25, 0.03, 0.02, 0.7), R=0.5, M=0.0 |
| `vb_gore_flesh` | Exposed tissue / wound surface | Color: (0.55, 0.12, 0.1, 1), R=0.4, M=0.0, SSS: (0.9, 0.15, 0.05) |
| `vb_gore_bone` | Exposed bone (differs from `vb_bone_surface` — this is fresh) | Color: (0.75, 0.7, 0.6, 1), R=0.6, M=0.0 |
| `vb_viscera` | Internal organs / dark gore (boss kills, corruption) | Color: (0.3, 0.05, 0.08, 1), R=0.3, M=0.0, SSS: (0.6, 0.1, 0.1) |

**Updated material count:** 41 (34 + 7 blood/gore). All 41 need PBR sets.

#### Blood Decal System (Unity)
New action for `unity_vfx`: `create_blood_decal_system`

```python
{
    "action": "create_blood_decal_system",
    "decal_types": [
        "splatter_small",    # 0.3-0.5m, single hit
        "splatter_large",    # 0.8-1.5m, critical hit / finisher
        "pool",              # 0.5-1.0m, stationary bleed
        "trail",             # 0.3m wide × 2-5m long, drag/crawl
        "spray_directional", # cone-shaped from hit direction
        "handprint",         # wall/floor handprint (0.2m, high detail)
        "footprint_bloody",  # bloody footstep trail (fades over 10 steps)
    ],
    "max_active_decals": 64,         # pool limit for performance
    "decal_lifetime": 120.0,         # seconds before fade-out
    "fade_duration": 5.0,            # fade-out animation time
    "layer": "BloodDecals",          # dedicated decal layer
    "receives_shadow": True,
    "uses_dithering": True,          # smooth alpha fade
}
```

**Decal projection rules:**
- Blood decals use URP Decal Projector (not mesh planes) — project onto any surface
- Direction-aware: splatter decals orient based on hit direction vector
- Surface-aware: different patterns on floor (pool) vs wall (drip/run)
- Accumulation: multiple hits in same area increase opacity, never exceeding max
- Performance: decals use shared material instances, GPU instancing enabled

#### Blood Particle VFX (Unity)
New action for `unity_vfx`: `create_blood_particle_vfx`

```python
{
    "action": "create_blood_particle_vfx",
    "vfx_variants": {
        "hit_small": {
            "particle_count": 8-15,
            "velocity": 3.0,
            "spread_angle": 30,
            "size": [0.02, 0.08],
            "lifetime": 0.5,
            "gravity": 9.8,
            "color_over_life": [(0.6, 0.02, 0.02) → (0.2, 0.01, 0.01)],
            "spawns_decal_on_collision": True,
        },
        "hit_critical": {
            "particle_count": 25-40,
            "velocity": 5.0,
            "spread_angle": 60,
            "size": [0.03, 0.12],
            "lifetime": 0.8,
            "gravity": 9.8,
            "sub_emitter": "blood_mist",  # secondary mist particles
            "spawns_decal_on_collision": True,
        },
        "blood_mist": {
            "particle_count": 5-10,
            "velocity": 0.5,
            "size": [0.2, 0.5],
            "lifetime": 1.5,
            "gravity": 0,
            "color": (0.3, 0.01, 0.01, 0.3),
            "fade": True,
        },
        "bleed_drip": {
            "particle_count": 1,          # drip every 0.3s
            "emit_rate": 3,
            "velocity": 0,
            "size": 0.03,
            "lifetime": 2.0,
            "gravity": 9.8,
            "trail_enabled": True,        # thin trail behind drip
            "spawns_decal_on_collision": True,
        },
        "execution_burst": {
            "particle_count": 60-100,
            "velocity": 8.0,
            "spread_angle": 120,
            "size": [0.05, 0.2],
            "lifetime": 1.2,
            "gravity": 9.8,
            "sub_emitter": "blood_mist",
            "screen_overlay": True,       # blood on camera lens
            "spawns_decal_on_collision": True,
        },
    },
}
```

#### Blood Textures (Blender Pipeline)
The `blender_texture` handler must generate these blood texture assets:

| Texture Name | Size | Channels | Generation Method |
|-------------|------|----------|-------------------|
| `blood_splatter_atlas` | 2048×2048 | RGBA | 8×8 grid of 64 unique splatter variations, procedural noise + physics sim |
| `blood_pool_normal` | 512×512 | RGB normal | Subtle ripple/meniscus normal map for standing blood |
| `blood_trail_mask` | 512×2048 | Grayscale alpha | Smear pattern, tileable along length |
| `blood_drip_sheet` | 1024×1024 | RGBA | 4×4 grid of drip/run patterns for vertical surfaces |
| `blood_handprint` | 256×256 | RGBA | Single handprint with finger detail |
| `blood_footprint` | 256×512 | RGBA | Boot/bare foot blood print |
| `gore_wound_atlas` | 1024×1024 | RGBA + Normal | 4×4 wound types (slash, puncture, bite, claw) |

**Procedural blood generation recipe:**
1. Base shape: Voronoi cell + noise displacement for irregular edges
2. Color: gradient from center (bright `vb_blood_fresh`) to edge (darker `vb_blood_dried`)
3. Detail: thin tendrils extending from main body (Perlin worm paths)
4. Transparency: solid center, alpha falloff at edges
5. Normal map: concave meniscus in center (blood thickness), flat at edges

#### Corruption-Blood Interaction
When corruption level > 50%, blood changes:
- Color shifts from red to purple-black (lerp toward `vb_corruption_veins` color)
- Blood pool material gains faint emission glow (0.1 intensity, purple tint)
- Blood mist particles change from red to violet
- Drip trails leave corruption stain (darker, semi-permanent)

---

### 19Q. SETTLEMENT VARIETY — BEYOND CITIES

Codex MUST implement generation specs for ALL settlement types, not just walled cities.

#### Village / Hamlet (5-15 buildings)
```python
{
    "type": "village",
    "building_count": 5-15,
    "layout": "cluster" | "linear_road" | "crossroads",
    "features": {
        "has_well": True,         # village center
        "has_inn": bool,
        "has_chapel": bool,
        "has_mill": bool,         # watermill if near river, windmill otherwise
        "has_market": bool,       # open stalls, not market hall
        "farmland": bool,         # surrounding crop fields
    },
}
```
- No walls. Open settlement merged with terrain.
- Buildings: small cottages (6m×5m), 1 floor, thatch roofs
- Farmland: grid of crop row meshes (0.3m height, tiling wheat/vegetable texture) surrounding village
- Animal pens: low fence enclosures (1m height) with straw floor

#### Outpost / Watchtower
```python
{
    "type": "outpost",
    "garrison_size": 2-8,
    "structure": "tower" | "fort" | "signal_fire",
    "road_attached": bool,    # sits along a road
}
```
- Tower: single tall structure (10-15m), 3 floors, ladder access, beacon platform
- Fort: small palisade enclosure (15m×15m), 1-2 buildings inside, gate

#### Port / Harbor District
```python
{
    "type": "harbor",
    "dock_count": 3-8,
    "warehouse_count": 2-5,
    "has_lighthouse": bool,
    "has_shipyard": bool,
}
```
- Docks: timber pier structures extending into water, mooring posts, rope coils
- Warehouses: large single-floor buildings (12m×8m), wide double doors
- Lighthouse: tall cylindrical tower (15-20m), lamp platform, spiral stairs
- Crane: wooden dockside crane mesh, riggable for animation

#### Graveyard / Cemetery
```python
{
    "type": "graveyard",
    "grave_count": 20-100,
    "has_mausoleum": bool,
    "has_chapel": bool,
    "corruption_level": float,
}
```
- Headstones: 5 variants (simple cross, rounded, pointed, broken, ornate), 0.5-1.2m height
- Graves: mounded earth rectangles (2m × 1m × 0.15m)
- Iron fence perimeter: 1.5m height, gate entrance
- Mausoleum: stone building (3m×3m×3m), heavy door, interior crypt (if walkable)
- Corrupted variant: glowing ground, cracked headstones, risen-dead props

---

### 19R. ENVIRONMENT MESH INTEGRATION STANDARDS

Every generated environment MUST pass these integration checks before export:

#### Terrain-to-Structure Blending
1. **Foundation embedding:** All buildings sink 0.1-0.3m into terrain. NO floating buildings.
2. **Terrain sculpt around foundations:** Terrain vertices within 2m of building auto-flatten to building base height
3. **Dirt/debris ring:** 0.5m material transition zone around every structure base (grass → dirt → stone)
4. **Retaining walls:** On slopes > 10°, auto-generate stone retaining wall mesh between building base and downhill terrain

#### Vegetation-to-Structure Clearance
1. No trees within 3m of building walls
2. No grass within 0.5m of road edges
3. Overgrowth ivy/moss ONLY on structures flagged `overgrown=True`
4. Tree roots do not clip through roads or foundations

#### Water-to-Terrain Blending
1. Shore material transition: 3m zone from water edge blends terrain material to mud/sand
2. Water level matches terrain at shore — NO visible gap between water mesh and terrain
3. River banks have exposed soil/rock texture
4. Puddles after rain: random small water planes (0.5-1.5m) in low terrain areas

#### Prop-to-Surface Alignment
1. ALL props raycast down to surface — no floating objects
2. Leaning props (ladders, signs): correct rotation to lean against nearest wall
3. Hanging props (lanterns, signs): positioned at attachment point, chain/rope mesh connecting to structure
4. Stacked props (crates, barrels): lower items support upper items, contact points aligned

#### Unity Export Markers
Every environment export MUST include these empties/markers for Unity runtime:
```
SPAWN_Player_001          — Player start position
SPAWN_NPC_XXX             — NPC spawn positions
NPC_Patrol_*              — Patrol waypoints (Section 19N)
INTERACT_*                — Interaction triggers (Section 19N)
LOOT_Container_*          — Lootable containers
LIGHT_Marker_*            — Light placement guides (matches Section 19E)
AUDIO_Zone_*              — Ambient audio trigger zones
PHASE_TRIGGER_*           — Boss phase triggers (if boss arena)
NAVMESH_Exclude_*         — Areas to exclude from navmesh bake (water, cliffs)
CAMERA_Hint_*             — Suggested camera angles for cinematics
WEATHER_Zone_*            — Per-area weather override triggers
```

---

## FINAL WORD

This is the most comprehensive MCP game development toolkit ever built. 41 free tools, 350+ existing actions, 58 new commands, 300+ new tests, 10 edit handlers, and AAA quality standards covering materials, geometry, lighting, interiors, city composition, wilderness locations, water bodies, blood/gore, NPC infrastructure, road design, and environment integration.

**What this delivers at 9/10+:**
- **Every building** has real door openings, weathered surfaces, and district-appropriate style variation (not sealed boxes, not copy-paste)
- **Every interior** has 15-80 placed props per room with storytelling detail, NPC patrol routes, and interaction zones (not empty boxes)
- **Every city** has 30+ unique material types, proper lighting, intelligent streets, and district personality (not a tech demo)
- **Every road** conforms to terrain, has proper cross-section geometry, bridges over water, and connects logically to buildings (not texture strips)
- **Every wilderness** — bandit camps, ruins, caves, boss arenas — has purpose-built geometry with loot, patrol, and encounter markers
- **Every water body** — ponds, lakes, rivers, oceans — has shore blending, proper materials, and integration with terrain and structures
- **Every texture** at correct texel density, baked, weathered, and surviving export (not blank white)
- **Every combat hit** produces directional blood VFX, surface-aware decals, and corruption-tinted gore (not generic red flash)
- **Every tree** has real branches, bark, leaves, and LODs (not cones)
- **Every terrain** at 1024×1024 with DLA erosion and height-based materials (not grid artifacts)
- **Every asset** within poly budget, LOD chain, collision mesh, and MeshLint validated
- **Every NPC** has patrol waypoints, interaction zones, and navmesh-compatible spaces to exist in
- **Every environment** properly blends terrain/structures/vegetation/water with no floating buildings, clipping trees, or seam gaps

**What 9/10+ means honestly:** This will compete with Fable and Skyrim for procedural world quality. The material system (41 PBR sets), blood/gore pipeline, NPC infrastructure, and environment integration standards push this beyond what most indie studios achieve. The remaining gap to full AAA (hand-crafted unique landmarks, 50-artist polish, motion-captured NPC behaviors) is a studio-scale effort — but for a solo dev with AI-powered procedural generation, this is the ceiling.

---

*CODEX HANDOFF ULTIMATE v3.0 — 2026-03-27*
*Author: Claude AI (Senior Game Developer)*
*For: Codex AI (Implementation Agent)*
*41 tools. 58+ new commands. 300+ new tests. 41 materials. 18 quality standards (19A-19R). Zero gaps.*
