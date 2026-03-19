---
phase: 08-gameplay-ai-performance
plan: 03
status: complete
completed: 2026-03-19
tests_passed: 1668/1668
---

# 08-03 Summary: Wire Gameplay + Performance Tools into Unity Server

## What was done

Wired `gameplay_templates.py` (7 generators) and `performance_templates.py` (5 generators) into `unity_server.py` as two new compound MCP tools: `unity_gameplay` and `unity_performance`. Unity server now has 7 total compound tools.

## Artifacts

| File | Changes | Purpose |
|------|---------|---------|
| `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_server.py` | +2 compound tools, +12 handler functions, +2 import blocks | 7 MOB actions + 5 PERF actions dispatching to template generators |

## Compound tools (7 total)

| # | Tool | Actions | Status |
|---|------|---------|--------|
| 1 | `unity_editor` | 5 | existing |
| 2 | `unity_vfx` | 10 | existing |
| 3 | `unity_audio` | 6 | existing |
| 4 | `unity_ui` | 5 | existing |
| 5 | `unity_scene` | 7 | existing |
| 6 | `unity_gameplay` | 7 | **new** |
| 7 | `unity_performance` | 5 | **new** |

## unity_gameplay actions (7)

| Action | Req | Generator | Validator | Output path |
|--------|-----|-----------|-----------|-------------|
| `create_mob_controller` | MOB-01 | `generate_mob_controller_script` | `_validate_mob_params` | `Assets/Scripts/Runtime/AI/` |
| `create_aggro_system` | MOB-02 | `generate_aggro_system_script` | -- | `Assets/Scripts/Runtime/AI/` |
| `create_patrol_route` | MOB-03 | `generate_patrol_route_script` | -- | `Assets/Scripts/Runtime/AI/` |
| `create_spawn_system` | MOB-04 | `generate_spawn_system_script` | `_validate_spawn_params` | `Assets/Scripts/Runtime/Spawning/` |
| `create_behavior_tree` | MOB-05 | `generate_behavior_tree_script` | -- | `Assets/Scripts/Runtime/BehaviorTree/` |
| `create_combat_ability` | MOB-06 | `generate_combat_ability_script` | `_validate_ability_params` | `Assets/Scripts/Runtime/Combat/` |
| `create_projectile_system` | MOB-07 | `generate_projectile_script` | `_validate_projectile_params` | `Assets/Scripts/Runtime/Combat/` |

## unity_performance actions (5)

| Action | Req | Generator | Validator | Output path |
|--------|-----|-----------|-----------|-------------|
| `profile_scene` | PERF-01 | `generate_scene_profiler_script` | -- | `Assets/Editor/Generated/Performance/` |
| `setup_lod_groups` | PERF-02 | `generate_lod_setup_script` | `_validate_lod_screen_percentages` | `Assets/Editor/Generated/Performance/` |
| `bake_lightmaps` | PERF-03 | `generate_lightmap_bake_script` | -- | `Assets/Editor/Generated/Performance/` |
| `audit_assets` | PERF-04 | `generate_asset_audit_script` | -- | `Assets/Editor/Generated/Performance/` |
| `automate_build` | PERF-05 | `generate_build_automation_script` | -- | `Assets/Editor/Generated/Performance/` |

## Key design decisions

- Gameplay scripts written to `Assets/Scripts/Runtime/` (MonoBehaviours, not editor scripts)
- Performance scripts written to `Assets/Editor/Generated/Performance/` (editor-only MenuItem commands)
- `ability_range` param in MCP tool maps to `range` param in `generate_combat_ability_script` (avoids shadowing Python builtin)
- LOD screen_percentages validated in handler before passing to generator (generator also validates internally)
- All handlers follow existing pattern: validate -> generate -> _write_to_unity -> JSON response with next_steps
- Default `allowed_audio_formats` = ["Vorbis", "AAC"], default `screen_percentages` = [0.6, 0.3, 0.15]
