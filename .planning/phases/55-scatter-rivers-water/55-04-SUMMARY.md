---
phase: "55"
plan: "04"
subsystem: "socket-server, settlement, handler-wiring"
tags: [race-condition, bug-fix, dead-code-wiring, socket, settlement, terrain]
dependency_graph:
  requires: []
  provides: [socket-race-fixes, settlement-floor-distribution, weathering-timeline-wiring, live-preview-wiring]
  affects: [blender_addon/socket_server.py, blender_addon/handlers/settlement_generator.py, blender_addon/handlers/__init__.py, blender_server.py]
tech_stack:
  added: []
  patterns: [threading-event-synchronization, queue-drain-on-shutdown]
key_files:
  created: []
  modified:
    - Tools/mcp-toolkit/blender_addon/socket_server.py
    - Tools/mcp-toolkit/blender_addon/handlers/settlement_generator.py
    - Tools/mcp-toolkit/blender_addon/handlers/__init__.py
    - Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py
    - Tools/mcp-toolkit/tests/test_socket_server.py
decisions:
  - "Used threading.Event for start() synchronization rather than polling"
  - "Distributed rooms across floors using modulo assignment matching concentric_organic path"
  - "Wired weathering timeline and live preview as socket command handlers with MCP tool actions"
metrics:
  duration: "~8 min"
  completed: "2026-04-12"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 5
  tests_added: 5
  tests_total_passing: 21253
---

# Phase 55 Plan 04: Handler Bugs + Socket + Wiring Summary

Socket server race-condition fixes, settlement interior furnishing bug fix, and terrain handler wiring for weathering timeline and live preview.

## Task 1: Fix Socket Server Race Conditions (17f1b7a)

**Problem:** `BlenderMCPServer` had multiple race conditions:
1. `_server_socket` written from background thread after `start()` returns -- `stop()` could run before socket exists
2. No lock protecting `_server_socket` access between `stop()` and `_server_loop()`
3. Pending commands left in queue on shutdown, causing 300s client hangs
4. `_process_commands` timer continued polling after `running=False`
5. Invalid JSON payloads caused unhandled exceptions

**Fix:**
- Added `_socket_lock` (threading.Lock) protecting `_server_socket` read/write
- Added `_started_event` (threading.Event) so `start()` blocks until socket is bound
- Added queue drain in `stop()` -- pending commands get error response immediately
- `_process_commands` returns 0.0 (stop timer) when `running=False`
- Added JSON decode error handling with descriptive error message

**Tests:** 5 new regression tests covering lock existence, event existence, queue drain, timer stop, and invalid JSON rejection.

## Task 2: Fix Settlement Interior Furnishing Bug (ca5ee0f)

**Problem:** District and default layout paths in `generate_settlement()` placed ALL room types on EVERY floor of multi-floor buildings. A 2-floor tavern with 5 rooms would get 10 rooms (5 duplicated). The `generate_concentric_districts` path already had the correct fix.

**Fix:** Applied the `rooms_per_floor` distribution pattern (modulo assignment) to both the district path and the default path, matching the concentric_organic implementation. Also added missing "armory" room type to `ROOM_FURNISHINGS` and `_ROOM_LIGHTS` dictionaries.

**Tests:** 532 settlement tests pass unchanged (behavior was already tested at the data level).

## Task 3: Wire Zero-Caller Functions (e3936fd)

**Problem:** `terrain_live_preview.py` (LivePreviewSession, edit_hero_feature) and `terrain_weathering_timeline.py` (generate_weathering_timeline, apply_weathering_event, WeatheringEvent, WEATHER_KINDS) were defined but never imported into the handler registry or exposed via MCP.

**Fix:**
- Added imports in `handlers/__init__.py`
- Registered `terrain_generate_weathering_timeline` and `terrain_edit_hero_feature` as COMMAND_HANDLERS
- Added `generate_weathering_timeline` and `edit_hero_feature` actions to `blender_environment` MCP tool in `blender_server.py`

## Deviations from Plan

None -- plan executed as written.

## Self-Check: PASSED

All 5 modified files verified on disk. All 3 commit hashes verified in git log.
