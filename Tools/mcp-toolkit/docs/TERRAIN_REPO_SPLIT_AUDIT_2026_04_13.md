# Terrain Repo Split Audit — 2026-04-13

## Keep In Terrain Repo

- `env_generate_terrain` with `use_controller=True`
- `TerrainPassController` and registered terrain passes
- `env_carve_river` as an internal hydrology primitive, not a public authoring entrypoint
- `env_carve_water_basin` as an internal basin primitive, not a public authoring entrypoint
- `env_create_water`
- `env_generate_waterfall` only when driven from heightmap / water-network context
- `env_create_cave_entrance`
- `prepare_heightmap_raw_u16` and Unity export validation

## Quarantine From Public Runtime

- `env_generate_world_terrain`
- `env_generate_canyon`
- `env_generate_cliff_face`
- `env_generate_swamp_terrain`
- `env_generate_natural_arch`
- `env_generate_geyser`
- `env_generate_sinkhole`
- `env_generate_floating_rocks`
- `env_generate_ice_formation`
- `env_generate_lava_flow`

These commands should remain importable for compatibility tests only. Public runtime calls should fail closed and direct callers to the controller-backed terrain path.

## Move Out Of Terrain Repo

- `world_generate_building`
- `world_generate_castle`
- `world_generate_ruins`
- `world_generate_interior`
- `world_generate_modular_kit`
- `world_generate_town`
- `world_generate_settlement`
- `world_generate_location`
- settlement prop prefetch / storytelling prop helpers

These are worldbuilding or settlement concerns, not terrain-core concerns.

## External Tool Candidates

- `Hydra`
  - Use for erosion and canyon shaping.
  - Best fit as imported code or pass-level integration.
  - License: MIT.
- `WhiteboxTools`
  - Use for hydrology preprocessing: flow accumulation, drainage, stream extraction.
  - Best fit as an upstream terrain analysis tool feeding Blender.
  - License: MIT.
- `OpenScatter`
  - Use as a Blender-side scatter tool for forest starts, shrubs, logs, and bankside clutter.
  - Best fit as a tool integration first, not vendored code.
  - License: GPL-3.0.
- `BlenderGeoModeller` plus `GemPy`
  - Use for cave/underground authoring experiments and terrain void volumes.
  - Best fit as a specialized research branch, not immediate runtime integration.
  - Licenses: MIT / EUPL-1.2.

## Immediate Rule

If a terrain feature cannot be expressed through the controller-backed terrain pipeline plus internal river/basin/waterfall primitives, it should not be exposed as a public terrain runtime command.
