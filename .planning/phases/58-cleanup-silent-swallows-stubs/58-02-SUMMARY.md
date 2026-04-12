---
phase: "58"
plan: "02"
subsystem: "blender-addon, mcp-server, terrain-pipeline"
tags: [silent-swallow, frozen-mutable, lifecycle, tcp-protocol, dead-code]
dependency_graph:
  requires: []
  provides: [hot-reload-safety, tcp-validation, immutable-state, diagnostic-logging]
  affects: [socket_server, terrain_semantics, terrain_morphology, terrain_pipeline, terrain_master_registrar, terrain_bundle_n, terrain_checkpoints, blender_server]
tech_stack:
  added: [types.MappingProxyType]
  patterns: [debug-logging-on-non-fatal-exceptions, mapping-proxy-for-frozen-dataclass-defaults]
key_files:
  created:
    - Tools/mcp-toolkit/tests/test_lifecycle_hot_reload.py
    - Tools/mcp-toolkit/tests/test_tcp_protocol.py
    - Tools/mcp-toolkit/tests/test_state_frozen_mutable.py
  modified:
    - Tools/mcp-toolkit/blender_addon/__init__.py
    - Tools/mcp-toolkit/blender_addon/socket_server.py
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_pipeline.py
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_master_registrar.py
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_semantics.py
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_morphology.py
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_bundle_n.py
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_checkpoints.py
    - Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py
decisions:
  - "Used MappingProxyType for frozen dataclass defaults instead of tuple-of-pairs for backward compatibility"
  - "All non-fatal exceptions log at debug level to avoid noisy console output"
metrics:
  duration_seconds: 1105
  completed: "2026-04-12T14:30:35Z"
  tasks_completed: 6
  tests_added: 28
  files_modified: 9
  files_created: 3
  quality_lint_before: 16
  quality_lint_after: 13
---

# Phase 58 Plan 02: Clusters F-K Silent Swallows and Stubs Summary

Fix addon lifecycle/hot reload, TCP protocol validation, frozen-mutable state, dead code wiring, and MCP layer silent swallows across 9 source files with 28 new tests.

## Tasks Completed

| Task | Cluster | Commit | Description |
|------|---------|--------|-------------|
| 1 | F090-F097 | d1c774d | Addon lifecycle/hot-reload safety |
| 2 | F098-F104 | 57aaef4 | TCP protocol validation bugs |
| 3 | F170-F187 | 18cf694 | Frozen-mutable state in dataclasses |
| 4 | F214-F224 | 42844da | Dead code wiring in bundle N registrar |
| 5 | F225-F240 | 47e783b | MCP layer silent swallows in compose/checkpoint |
| 6 | (extra) | f5c1b5a | Autosave checkpoint silent swallow |

## Changes by Cluster

### F090-F097: Addon Lifecycle / Hot Reload
- **__init__.py**: `register()` now stops any existing server before re-registering, preventing port-bind failures on Blender F3/F5 hot reload
- **socket_server.py**: `stop()` drains the command queue, setting error responses on all pending events so waiting threads don't hang
- **terrain_pipeline.py**: Documented `register_default_passes()` idempotency (overwrite semantics)
- **terrain_master_registrar.py**: `_safe_import_registrar` now splits `ImportError` (debug) from unexpected exceptions (warning) instead of bare `except Exception`

### F098-F104: TCP Protocol Bugs
- **socket_server.py**: Zero-length messages now rejected with clear `ValueError`
- **socket_server.py**: Invalid JSON caught separately with descriptive error message (was caught by broad except with "Server error" prefix)
- **socket_server.py**: `socket.timeout` added to the header-read catch list so idle timeouts don't produce confusing tracebacks

### F170-F187: Frozen-Mutable State
- **terrain_semantics.py**: `HeroFeatureSpec.parameters` changed from `Dict[str, Any]` with `dict` default to `Mapping[str, Any]` with `MappingProxyType({})` default
- **terrain_semantics.py**: `TerrainIntentState.composition_hints` same treatment; removed REVIEW-IGNORE comment
- **terrain_morphology.py**: `MorphologyTemplate.params` same treatment; removed REVIEW-IGNORE comment
- Quality lint L2-03 FROZEN-MUTABLE findings: 3 -> 0

### F214-F224: Dead Code Wiring
- **terrain_bundle_n.py**: Replaced 6 dead `_ = module.func` assignments with structured `_EXPECTED_CALLABLES` dict and `getattr` validation loop that logs warnings for missing callables

### F225-F240 + F320-F331: MCP Layer / blender_server Stubs
- **blender_server.py**: 14 silent `except Exception: pass` blocks in compose_map and generate_map_package replaced with `logger.debug(...)` calls
- **terrain_checkpoints.py**: Autosave wrapper silent pass replaced with `logger.debug`

## Quality Lint Results

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Total findings | 16 | 13 | -3 |
| FROZEN-MUTABLE (L2-03) | 3 | 0 | -3 |
| SILENT-SWALLOW (L2-04) | 9 | 9 | 0 (remaining are in read-only files) |
| STUB-PASS (L2-01) | 3 | 3 | 0 (terrain_twelve_step.py is read-only) |
| ORPHAN-DELTA (L2-02) | 1 | 1 | 0 (worldbuilding.py is read-only) |

## Test Results

- 28 new tests added across 3 test files
- All 28 pass
- Full suite: 21,468 passed, 35 failed (all 35 failures pre-existing, verified by stash comparison)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing functionality] Added terrain_checkpoints autosave logging**
- **Found during:** Task 5 (MCP layer)
- **Issue:** terrain_checkpoints.py autosave wrapper had bare `except: pass` same as blender_server
- **Fix:** Added logging import and `logger.debug` call
- **Files modified:** terrain_checkpoints.py
- **Commit:** f5c1b5a

## Known Stubs

None in files modified by this plan.

## Self-Check: PASSED
