# Blender External Toolchain

This toolkit now exposes external-addon capability checks through MCP so AI
agents can inspect and configure the Blender stack without raw `execute_code`.

## MCP actions

- `asset_pipeline action=inspect_external_toolchain`
  - Returns detected addon availability, the selected worldbuilding stack, and an `agent_contract` describing how AI agents should use the installed stack.
- `asset_pipeline action=configure_external_toolchain`
  - Persists the selected toolchain on the active Blender scene as
    `scene["vb_external_toolchain"]`, including inventory, selected pipeline, and `agent_contract`.

## Selected pipeline keys

- `terrain`
  - `world_creator`, `terrain_mixer`, or `native_terrain`
- `terrain_helpers`
  - optional helper addons such as `ant_landscape` or `srtm_terrain_importer`
- `scatter`
  - `geo_scatter` or `native_scatter`
- `scatter_helpers`
  - optional Blender-side helpers such as `bagapie` and `secret_paint`
- `vegetation_assets`
  - `botaniq` or `procedural_vegetation`
- `architecture`
  - `archipack` or `native_architecture`
- `interior_authoring`
  - `bonsai`, architecture-driven fallback, or `native_interiors`
- `layout_variation`
  - `wfc_3d_generator` or `native_layout_variation`
- `layout_helpers`
  - optional parametric helpers such as `sverchok`
- `surface_detail`
  - `decalmachine` or `native_surface_detail`
- `uv`
  - `uvpackmaster` or `native_uv`
- `lod`
  - `lodgen` or `native_lod`
- `export_packaging`
  - `gamiflow`, `easymesh_batch_exporter`, or `native_export_packaging`
- `quality_helpers`
  - optional QA helpers such as `texel_density_checker` and `textools`
- `modeling_helpers`
  - optional helpers such as `rmkit`, `edgeflow`, `modifier_list`, `nd_primitives`, `bool_tool`, and `looptools`
- `asset_sources`
  - optional asset libraries such as `blenderkit`
- `lighting_preset`
  - `forest_review` while authoring, otherwise a darker biome preset

## Current practical rule

If an addon is not installed in Blender, the toolkit does not pretend it is
available. It falls back to the native VB pipeline and reports the missing
addon explicitly.

## Agent Contract

The returned `agent_contract` is the stable hand-off format for Claude/agents.
It contains:

- `automation_targets`
  - which toolchain to use for terrain, interiors, layout variation, UVs, LODs, export packaging, and quality checks
- `authoring_rules`
  - practical rules for what should stay in Blender versus Unity
- `entrypoints`
  - the MCP actions agents should call first
- `warnings`
  - known compatibility or authentication caveats
