# VeilBreakers Agent Directives

These repo-level rules apply to Codex-style agents working in this codebase.

## Terrain Tooling

Before planning or changing terrain/worldbuilding behavior:

1. Call the Blender asset pipeline tool with `action="inspect_external_toolchain"`.
2. Treat the returned live contract as authoritative for Blender capabilities on this PC.
3. Prefer `agent_contract.workflow_presets.terrain_unity_ready_free` as the default free Unity-ready terrain workflow unless the user explicitly asks for a different stack.
4. Use `agent_contract.selection`, `workflow_presets`, `warnings`, `disabled_but_installed`, and `blender_runtime` instead of guessing from installed addon folders.

## Blender Runtime

- Production target: `Blender 4.5 LTS`
- `Blender 5.0.x` is experimental on this machine and should not be assumed stable for headless automation

## Terrain Passes

- Route terrain mutation through `TerrainPassController`
- Keep Unity export paths deterministic
- Ensure `prepare_heightmap_raw_u16` is present before `validation_full` for Unity-ready terrain workflows unless explicitly opted out
