# Blender External Toolchain

This toolkit now exposes external-addon capability checks through MCP so AI
agents can inspect and configure the Blender stack without raw `execute_code`.

## MCP actions

- `asset_pipeline action=inspect_external_toolchain`
  - Returns detected addon availability, the selected worldbuilding stack, and an `agent_contract` describing how AI agents should use the installed stack.
  - Also returns `blender_runtime`, including the active Blender line, the recommended line (`4.5 LTS`), and whether the current runtime should be treated as `recommended`, `experimental`, or `legacy`.
- `asset_pipeline action=configure_external_toolchain`
  - Persists the selected toolchain on the active Blender scene as
    `scene["vb_external_toolchain"]`, including inventory, selected pipeline, and `agent_contract`.

## Selected pipeline keys

- `terrain`
  - `world_creator`, `terrain_mixer`, or `native_terrain`
- `terrain_helpers`
  - optional helper addons such as `ant_landscape` or `srtm_terrain_importer`
- `scatter`
  - `geo_scatter`, `bagapie`, `secret_paint`, `openscatter`, or `native_scatter`
- `scatter_helpers`
  - optional Blender-side helpers such as `bagapie` and `secret_paint`
- `vegetation_assets`
  - `botaniq` or `procedural_vegetation`
- `architecture`
  - `archipack` or `native_architecture`
- `interior_authoring`
  - architecture-driven fallback such as `archimesh`, or `native_interiors`
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

If an addon is installed but not enabled, it is reported in inventory but it is
not treated as part of the active agent contract. Selection now keys off
enabled addons so agents do not plan around operators that Blender has not
registered for the current session.

## Agent Contract

The returned `agent_contract` is the stable hand-off format for Claude/agents.
It contains:

- `automation_targets`
  - which toolchain to use for terrain, interiors, layout variation, UVs, LODs, export packaging, and quality checks
  - plus the active automation bridge and remote asset-generation source when present
- `authoring_rules`
  - practical rules for what should stay in Blender versus Unity
- `entrypoints`
  - the MCP actions agents should call first
- `warnings`
  - known compatibility or authentication caveats
- `workflow_presets`
  - stable recommended presets that other agents, including Claude, can consume without inferring the tool stack

## Recommended Preset

The current stable preset for this machine is:

- `agent_contract.workflow_presets.terrain_unity_ready_free`
  - terrain authoring: `terrain_mixer`
  - terrain helpers: `ant_landscape`, `srtm_terrain_importer`
  - scatter: `bagapie`
  - scatter helper: `secret_paint`
  - interiors: `archimesh`
  - layout variation: `wfc_3d_generator`
  - export: `gamiflow`
  - quality gate: `texel_density_checker`
  - pass sequence: `macro_world -> structural_masks -> erosion -> navmesh -> prepare_heightmap_raw_u16 -> validation_full`

Claude or any other agent should prefer this preset over ad-hoc addon guessing when building a Unity-ready terrain workflow on this PC.
