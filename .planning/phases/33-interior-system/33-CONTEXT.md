# Phase 33: Interior System -- Context

**Auto-generated:** 2026-03-31
**Status:** Ready for execution

## Phase Goal

Interior generation produces purpose-driven room layouts with spatially-aware furniture placement, decorative clutter, practical lighting, and occlusion zones. Interiors feel lived-in, not empty boxes.

## Key Requirement

**MESH-03:** Interior rooms have purpose-driven furniture placement with spatial relationships (chairs face tables, beds have nightstands, work triangles in kitchens), 5-15 props per room, path to door always clear.

## Existing Code (Pure Logic, No bpy)

- `_building_grammar.py`: `_ROOM_CONFIGS` (22 room types), `generate_interior_layout()` with collision avoidance
- `building_interior_binding.py`: `BUILDING_ROOM_MAP`, `STYLE_MATERIAL_MAP`, `align_rooms_to_building()`, `generate_interior_spec_from_building()`
- `_mesh_bridge.py`: `FURNITURE_GENERATOR_MAP` (44 entries mapping furniture types to mesh generators)
- `worldbuilding.py`: `handle_generate_interior()` creates Blender objects from layout data

## What Gets Enhanced

All changes in `_building_grammar.py` (pure-logic module). The handler in `worldbuilding.py` gets a small update to consume new light source data.

## Success Criteria

1. Room purpose templates define spatial relationship graphs
2. Furniture placement uses constraint satisfaction: 0.3m wall clearance, 1m door corridor, wall alignment, no interpenetration
3. Decorative clutter scatter: 5-15 props per room using Poisson disk
4. Lighting placement: torches at doorways, candles on tables, fireplace emissive, min 2 light sources (2700-3500K)
5. Contact sheet of tavern/bedroom/blacksmith comparable to Skyrim interior cells
