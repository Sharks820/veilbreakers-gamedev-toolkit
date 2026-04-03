# Loop Prevention and Recovery System -- Design Document

**Date**: 2026-04-03
**Status**: DRAFT
**Scope**: `Tools/mcp-toolkit/` -- Blender TCP client, socket server, compose_map pipeline, Tripo clients

---

## 1. Current State Analysis

### 1.1 Retry/Timeout Inventory

| Component | File | Retry Count | Backoff | Timeout | Circuit Breaker |
|---|---|---|---|---|---|
| BlenderConnection._sync_send | shared/blender_client.py:215 | 1 (reconnect once) | None | 300s (socket-level) | NO |
| BlenderMCPServer._handle_client | blender_addon/socket_server.py:112 | 0 | N/A | 300s (result_event.wait) | NO |
| TripoGenerator.generate_from_text | shared/tripo_client.py:122 | 3 | Exponential (1s, 2s, 4s) | 300s (polling) | NO |
| TripoGenerator._download_file | shared/tripo_client.py:48 | 3 | Exponential (1s, 2s, 4s) | Inherited | NO |
| TripoStudioClient.wait_for_task | shared/tripo_studio_client.py:220 | Infinite (polling loop) | Adaptive (running_left_time) | 300s | NO |
| fal_client.generate_concept_art | shared/fal_client.py:84 | 0 | N/A | 30s (httpx) | NO |
| PipelineRunner | shared/pipeline_runner.py | 0 | N/A | 300s (inherited) | NO |
| compose_map | blender_server.py:2685 | 0 per step | N/A | 300s per Blender cmd | NO |

### 1.2 Identified Loop Scenarios

**Scenario A: Large Payload Timeout Loop**
```
Client sends complex compose_map with 10+ locations
  -> Blender generates town (takes 400s)
  -> Client socket timeout at 300s
  -> Client reconnects (BlenderConnection._sync_send retry)
  -> Re-sends SAME command
  -> Blender is still busy from first command
  -> Second command queues behind the first
  -> Both eventually timeout
  -> External caller (Claude) retries the entire tool call
  -> Infinite loop
```

**Scenario B: Compose Map Restart-from-Zero**
```
compose_map reaches step 7 (vegetation) after 180s of work
  -> vegetation scatter fails (OOM, timeout, or Blender crash)
  -> No checkpoint_dir was provided (user forgot or default)
  -> Error returns to Claude
  -> Claude retries compose_map with same params
  -> Steps 1-6 re-execute from scratch (another 180s)
  -> Fails at step 7 again
  -> Infinite loop
```

**Scenario C: Tripo Studio Infinite Polling**
```
TripoStudioClient.wait_for_task polls forever if:
  -> Task status is stuck on "running" and never transitions
  -> running_left_time keeps reporting > 0
  -> timeout param defaults to 300s but could be overridden to very high
  -> API returns 429/503, parsed as error, but generate_from_text catches ALL exceptions
     and returns {"status": "failed"} -- Claude retries the entire tool call
```

**Scenario D: Blender Frozen -- Client Can't Distinguish**
```
Blender processes a heavy mesh operation (e.g. 500K terrain)
  -> Blender main thread is locked (bpy timer can't fire)
  -> Server can't respond to any commands
  -> Client timeout at 300s
  -> Client reconnects, sends same command
  -> New connection accepted by OS, but handler thread blocks on command_queue
     because main thread timer is still processing the previous command
  -> Stacked commands: first finishes, second finishes, third queued by Claude retry...
```

### 1.3 Root Causes

1. **No operation deduplication** -- Same command sent multiple times gets executed multiple times
2. **No client-side circuit breaker** -- After N failures of the same operation, client still retries
3. **Checkpoint not mandatory** -- compose_map checkpointing is opt-in; most calls don't use it
4. **Timeout is flat** -- 300s for both "delete an object" (10ms) and "generate a town" (120s)
5. **No heartbeat** -- Client cannot distinguish "still working" from "frozen/crashed"
6. **No complexity estimation** -- No pre-flight check for operation feasibility
7. **No progressive degradation** -- If generation fails at full quality, there's no fallback

---

## 2. Architecture

```
                    MCP Tool Call (from Claude)
                            |
                    +-------v--------+
                    | OperationGuard |  <-- NEW: circuit breaker + dedup
                    +-------+--------+
                            |
              +-------------v--------------+
              | ComplexityEstimator        |  <-- NEW: pre-flight sizing
              | - estimate_timeout()       |
              | - estimate_payload_size()  |
              | - should_split()           |
              +-------------+--------------+
                            |
              +-------------v--------------+
              | BlenderConnection          |  MODIFIED
              | - send_command()           |
              | - send_command_with_hb()   |  <-- NEW: heartbeat-aware
              | - _operation_registry      |  <-- NEW: dedup tracking
              +-------------+--------------+
                            |
                     TCP (localhost:9876)
                            |
              +-------------v--------------+
              | BlenderMCPServer           |  MODIFIED
              | - _handle_client()         |
              | - _send_heartbeats()       |  <-- NEW: progress pings
              | - _command_dedup_cache     |  <-- NEW: reject duplicates
              +-------------+--------------+
                            |
              +-------------v--------------+
              | compose_map / generators   |  MODIFIED
              | - auto-checkpoint          |  <-- checkpoint always on
              | - step-level recovery      |
              | - progressive degradation  |
              +----------------------------+
```

---

## 3. Component Designs

### 3.1 Circuit Breaker (`shared/circuit_breaker.py`) -- Priority 1

Prevents repeated failure of the same operation from consuming resources indefinitely.

```python
"""Circuit breaker for Blender operations.

States:
  CLOSED   -- normal operation, failures counted
  OPEN     -- failures exceeded threshold, all calls rejected immediately
  HALF_OPEN -- after cooldown, allow one probe call through
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class OperationRecord:
    fingerprint: str
    failure_count: int = 0
    last_failure_time: float = 0.0
    last_error: str = ""
    state: CircuitState = CircuitState.CLOSED


class CircuitBreaker:
    """Track operation failures and break retry loops.

    Parameters
    ----------
    max_failures : int
        Number of failures before circuit opens (default 3).
    cooldown_seconds : float
        Time before OPEN transitions to HALF_OPEN (default 60).
    """

    def __init__(self, max_failures: int = 3, cooldown_seconds: float = 60.0):
        self.max_failures = max_failures
        self.cooldown = cooldown_seconds
        self._records: dict[str, OperationRecord] = {}

    @staticmethod
    def fingerprint(command_type: str, params: dict[str, Any]) -> str:
        """Stable hash of a command for dedup/tracking."""
        # Normalize by sorting keys, exclude volatile fields
        stable = {k: v for k, v in sorted(params.items())
                  if k not in ("timestamp", "request_id")}
        raw = f"{command_type}:{json.dumps(stable, sort_keys=True, default=str)}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def check(self, fingerprint: str) -> tuple[bool, str]:
        """Check if operation is allowed.

        Returns (allowed, reason).
        """
        rec = self._records.get(fingerprint)
        if rec is None:
            return True, ""

        if rec.state == CircuitState.CLOSED:
            return True, ""

        if rec.state == CircuitState.OPEN:
            elapsed = time.monotonic() - rec.last_failure_time
            if elapsed >= self.cooldown:
                rec.state = CircuitState.HALF_OPEN
                return True, "half_open_probe"
            return False, (
                f"Circuit OPEN: operation failed {rec.failure_count} times. "
                f"Last error: {rec.last_error}. "
                f"Retry available in {int(self.cooldown - elapsed)}s. "
                f"Suggestion: reduce complexity or change parameters."
            )

        # HALF_OPEN -- allow one probe
        return True, "half_open_probe"

    def record_success(self, fingerprint: str) -> None:
        """Reset circuit on success."""
        if fingerprint in self._records:
            del self._records[fingerprint]

    def record_failure(self, fingerprint: str, error: str) -> None:
        """Record a failure. Opens circuit if threshold exceeded."""
        rec = self._records.get(fingerprint)
        if rec is None:
            rec = OperationRecord(fingerprint=fingerprint)
            self._records[fingerprint] = rec

        rec.failure_count += 1
        rec.last_failure_time = time.monotonic()
        rec.last_error = error[:200]

        if rec.failure_count >= self.max_failures:
            rec.state = CircuitState.OPEN

    def reset(self, fingerprint: str | None = None) -> None:
        """Manually reset one or all circuits."""
        if fingerprint:
            self._records.pop(fingerprint, None)
        else:
            self._records.clear()
```

**Integration point**: `BlenderConnection.send_command()` wraps every call with `check()` / `record_success()` / `record_failure()`.

### 3.2 Timeout Scaling (`shared/timeout_scaling.py`) -- Priority 1

Replace the flat 300s timeout with operation-aware scaling.

```python
"""Per-operation timeout estimation.

Maps command types to expected duration ranges based on parameter complexity.
"""

# Base timeouts in seconds (min, typical, max)
TIMEOUT_PROFILES: dict[str, tuple[int, int, int]] = {
    # Fast ops (< 5s)
    "clear_scene": (2, 5, 15),
    "get_object_info": (1, 2, 5),
    "get_viewport_screenshot": (2, 5, 15),
    "select_object": (1, 2, 5),
    "delete_objects": (2, 5, 15),

    # Medium ops (5-30s)
    "create_primitive": (3, 10, 30),
    "import_model": (5, 15, 60),
    "mesh_repair": (5, 20, 60),
    "uv_unwrap": (5, 30, 90),
    "apply_material": (3, 10, 30),
    "env_carve_river": (5, 20, 60),
    "env_create_water": (3, 10, 30),

    # Heavy ops (30-120s)
    "env_generate_terrain": (30, 60, 180),
    "env_scatter_vegetation": (20, 60, 180),
    "env_scatter_props": (15, 45, 120),
    "env_generate_road": (10, 30, 90),

    # Very heavy ops (60-600s)
    "world_generate_town": (60, 120, 360),
    "world_generate_castle": (60, 120, 360),
    "world_generate_dungeon": (30, 90, 240),
    "world_generate_multi_floor_dungeon": (60, 180, 480),
    "world_generate_cave": (30, 60, 180),
    "world_generate_ruins": (30, 60, 180),
    "world_generate_boss_arena": (30, 90, 240),
    "world_generate_building": (20, 60, 180),
    "world_generate_linked_interior": (30, 90, 240),
    "terrain_create_biome_material": (10, 30, 90),
    "setup_dark_fantasy_lighting": (5, 15, 45),
    "terrain_spline_deform": (10, 30, 90),
}

# Default for unknown commands
DEFAULT_TIMEOUT = (10, 60, 300)


def estimate_timeout(
    command_type: str,
    params: dict,
    safety_factor: float = 1.5,
) -> int:
    """Estimate appropriate timeout for a Blender command.

    Returns timeout in seconds, using the typical duration * safety_factor,
    capped at the max profile value * safety_factor.
    """
    profile = TIMEOUT_PROFILES.get(command_type, DEFAULT_TIMEOUT)
    _min, typical, _max = profile

    # Adjust for known complexity multipliers
    multiplier = 1.0

    # Terrain resolution scales quadratically
    if "resolution" in params:
        res = int(params["resolution"])
        if res > 256:
            multiplier *= (res / 256) ** 1.5

    # Building count / district count
    for key in ("districts", "building_count", "num_floors", "floors"):
        if key in params:
            count = int(params[key])
            if count > 3:
                multiplier *= count / 3.0

    # Vegetation / prop instance count
    for key in ("max_instances", "count"):
        if key in params:
            count = int(params[key])
            if count > 1000:
                multiplier *= count / 1000.0

    timeout = int(typical * multiplier * safety_factor)
    hard_cap = int(_max * safety_factor * 2)
    return min(timeout, hard_cap)
```

**Integration point**: `BlenderConnection.send_command()` calls `estimate_timeout()` and sets `self._socket.settimeout()` per-command.

### 3.3 Heartbeat Protocol -- Priority 2

Allow the server to signal "still alive" during long operations so the client doesn't timeout prematurely.

**Wire protocol change** (backward compatible):

```
Current: Client sends command -> waits for single response
New:     Client sends command -> receives 0+ heartbeats -> receives final response

Heartbeat message: length-prefixed JSON with {"_heartbeat": true, "progress": 0.45, "step": "generating walls"}
Final response: same as current (no _heartbeat key)
```

**Server side** (`socket_server.py`):

```python
def _process_commands(self) -> float:
    # ... existing code ...
    # Before executing handler, start heartbeat thread
    heartbeat_cancel = threading.Event()

    def _heartbeat_loop(sock, cancel_event):
        while not cancel_event.wait(timeout=5.0):
            try:
                hb = json.dumps({"_heartbeat": True, "ts": time.time()}).encode()
                sock.sendall(struct.pack(">I", len(hb)) + hb)
            except (BrokenPipeError, OSError):
                break

    hb_thread = threading.Thread(target=_heartbeat_loop, args=(client_sock, heartbeat_cancel))
    hb_thread.start()

    try:
        result = handler(params)
    finally:
        heartbeat_cancel.set()
        hb_thread.join(timeout=2)
    # ... existing response code ...
```

**Client side** (`blender_client.py`):

```python
def _send_on_socket(self, command_type, params):
    # ... send command ...
    # Receive loop: skip heartbeats, return on real response
    while True:
        length_bytes = self._receive_exactly(4)
        length = struct.unpack(">I", length_bytes)[0]
        response_bytes = self._receive_exactly(length)
        response_data = json.loads(response_bytes)

        if response_data.get("_heartbeat"):
            # Reset socket timeout -- server is alive
            self._socket.settimeout(self.timeout)
            continue

        # Real response
        response = BlenderResponse(**response_data)
        if response.status == "error":
            raise BlenderCommandError(response)
        return response.result
```

### 3.4 Mandatory Auto-Checkpoint for compose_map -- Priority 1

Make checkpointing always-on instead of opt-in. Use a temp directory if no `checkpoint_dir` is provided.

```python
# In blender_server.py, compose_map action:

# Auto-assign checkpoint directory if not provided
if not checkpoint_dir:
    import tempfile
    checkpoint_dir = os.path.join(
        tempfile.gettempdir(), "veilbreakers_checkpoints"
    )
    resume = True  # Always attempt resume from auto-checkpoints
```

This single change prevents Scenario B entirely. If compose_map is called again with the same map_name and seed, it picks up where it left off instead of restarting from scratch.

### 3.5 Progressive Complexity Reduction -- Priority 2

When an operation fails, automatically retry with reduced complexity before giving up.

```python
"""Progressive degradation for generation operations.

Each generator has "complexity knobs" that can be dialed down on failure.
"""

DEGRADATION_PROFILES: dict[str, list[dict]] = {
    "world_generate_town": [
        # Level 0: full quality (default)
        {},
        # Level 1: reduce building count, simpler roofs
        {"building_count_scale": 0.6, "roof_style": "simple_gable",
         "skip_interior_details": True},
        # Level 2: minimal buildings, no props
        {"building_count_scale": 0.3, "roof_style": "flat",
         "skip_interior_details": True, "skip_props": True,
         "skip_chimneys": True},
    ],
    "env_generate_terrain": [
        {},
        {"resolution_scale": 0.5, "erosion": "none"},
        {"resolution_scale": 0.25, "erosion": "none", "skip_detail_noise": True},
    ],
    "env_scatter_vegetation": [
        {},
        {"max_instances_scale": 0.5},
        {"max_instances_scale": 0.2, "skip_grass": True},
    ],
}


async def try_with_degradation(
    blender, command_type: str, params: dict,
    circuit_breaker: CircuitBreaker,
) -> tuple[Any, int]:
    """Try command at full quality, degrade on failure.

    Returns (result, degradation_level).
    """
    profile = DEGRADATION_PROFILES.get(command_type, [{}])

    for level, overrides in enumerate(profile):
        degraded_params = {**params, **overrides}

        # Apply scale factors
        if "resolution_scale" in overrides:
            if "resolution" in degraded_params:
                degraded_params["resolution"] = int(
                    params["resolution"] * overrides["resolution_scale"]
                )
            del degraded_params["resolution_scale"]

        if "building_count_scale" in overrides:
            for key in ("districts", "building_count"):
                if key in degraded_params:
                    degraded_params[key] = max(1, int(
                        params.get(key, 3) * overrides["building_count_scale"]
                    ))
            del degraded_params["building_count_scale"]

        if "max_instances_scale" in overrides:
            if "max_instances" in degraded_params:
                degraded_params["max_instances"] = max(100, int(
                    params.get("max_instances", 1000) * overrides["max_instances_scale"]
                ))
            del degraded_params["max_instances_scale"]

        try:
            result = await blender.send_command(command_type, degraded_params)
            return result, level
        except Exception as exc:
            if level == len(profile) - 1:
                # Last level -- give up
                raise
            # Log and try next degradation level
            logger.warning(
                "Operation %s failed at quality level %d, degrading: %s",
                command_type, level, exc,
            )

    raise RuntimeError("Exhausted all degradation levels")
```

### 3.6 Server-Side Command Deduplication -- Priority 2

Prevent the same command from executing concurrently when the client reconnects and re-sends.

```python
# In socket_server.py, add to _handle_client:

import hashlib

class BlenderMCPServer:
    def __init__(self, ...):
        # ...
        self._active_commands: dict[str, threading.Event] = {}
        self._active_results: dict[str, dict] = {}
        self._dedup_lock = threading.Lock()

    def _command_fingerprint(self, command: dict) -> str:
        raw = json.dumps(command, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _handle_client(self, client_sock):
        # ... after parsing command ...
        fp = self._command_fingerprint(command)

        with self._dedup_lock:
            if fp in self._active_commands:
                # Same command is already executing -- wait for its result
                existing_event = self._active_commands[fp]
                existing_event.wait(timeout=300)
                response = self._active_results.get(fp, {
                    "status": "error",
                    "message": "Duplicate command timed out"
                })
                # Send existing result to the new client
                # (skip re-execution)
                ...
                return

            event = threading.Event()
            self._active_commands[fp] = event

        try:
            # Normal execution path...
            result_event = threading.Event()
            result_container = {}
            self.command_queue.put((command, result_event, result_container))
            result_event.wait(timeout=300)
            response = result_container.get("response", {"status": "error", "message": "Timeout"})
            self._active_results[fp] = response
        finally:
            with self._dedup_lock:
                event.set()
                # Clean up after a delay to catch late duplicates
                def _cleanup():
                    import time
                    time.sleep(10)
                    with self._dedup_lock:
                        self._active_commands.pop(fp, None)
                        self._active_results.pop(fp, None)
                threading.Thread(target=_cleanup, daemon=True).start()
```

### 3.7 Complexity Estimation / Pre-flight Check -- Priority 3

Estimate whether an operation will succeed before sending it.

```python
def estimate_operation_complexity(command_type: str, params: dict) -> dict:
    """Pre-flight complexity estimation.

    Returns:
        {
            "estimated_duration_s": 120,
            "estimated_memory_mb": 2048,
            "risk_level": "high",  # low/medium/high/extreme
            "warnings": ["Terrain resolution 512 may cause OOM on 8GB systems"],
            "suggestions": ["Reduce resolution to 256 for safer execution"],
            "should_split": False,
        }
    """
    duration = estimate_timeout(command_type, params, safety_factor=1.0)
    memory_mb = _estimate_memory(command_type, params)

    risk = "low"
    warnings = []
    suggestions = []

    if duration > 120:
        risk = "medium"
    if duration > 300:
        risk = "high"
        warnings.append(f"Estimated {duration}s -- may timeout")
        suggestions.append("Consider splitting into smaller operations")
    if memory_mb > 4096:
        risk = "extreme"
        warnings.append(f"Estimated {memory_mb}MB RAM -- may OOM")

    return {
        "estimated_duration_s": duration,
        "estimated_memory_mb": memory_mb,
        "risk_level": risk,
        "warnings": warnings,
        "suggestions": suggestions,
        "should_split": risk in ("high", "extreme"),
    }


def _estimate_memory(command_type: str, params: dict) -> int:
    """Rough memory estimate in MB."""
    base = 200  # Blender base overhead

    if "resolution" in params:
        res = int(params["resolution"])
        # Heightmap: res^2 * 12 bytes per vertex (position + normal)
        base += (res * res * 12) // (1024 * 1024)

    if "max_instances" in params:
        count = int(params["max_instances"])
        # Each scatter instance: ~2KB (transforms + mesh ref)
        base += (count * 2048) // (1024 * 1024)

    if command_type.startswith("world_generate_town"):
        districts = int(params.get("districts", 3))
        base += districts * 300  # ~300MB per district

    return base
```

---

## 4. Implementation Priority Order

| Priority | Component | Effort | Impact | Risk |
|---|---|---|---|---|
| **P1** | 3.4 Mandatory Auto-Checkpoint | 1 hour | HIGH -- prevents restart-from-zero loops | Very low -- backward compatible |
| **P1** | 3.1 Circuit Breaker | 3 hours | HIGH -- stops infinite retry loops | Low -- additive, no protocol changes |
| **P1** | 3.2 Timeout Scaling | 2 hours | HIGH -- prevents premature timeouts on heavy ops | Low -- replaces single constant |
| **P2** | 3.5 Progressive Degradation | 4 hours | MEDIUM -- auto-recovers from OOM/complexity | Medium -- needs per-generator tuning |
| **P2** | 3.3 Heartbeat Protocol | 4 hours | MEDIUM -- distinguishes alive vs frozen | Medium -- wire protocol change |
| **P2** | 3.6 Server-Side Dedup | 3 hours | MEDIUM -- prevents duplicate execution | Medium -- threading complexity |
| **P3** | 3.7 Complexity Estimation | 3 hours | LOW -- informational, enables future splitting | Low -- pure computation |
| **P3** | Operation Splitting | 8+ hours | MEDIUM -- prevents oversized payloads | High -- requires generator refactoring |

**Total estimated effort**: ~28 hours

**Recommended execution order**: P1 items first (6 hours, covers 80% of loop scenarios), then P2 (11 hours), then P3 (11 hours).

---

## 5. Risk Assessment

### 5.1 Risks by Component

| Component | Risk | Mitigation |
|---|---|---|
| Circuit Breaker | False positives -- blocks a legitimately retryable operation | Conservative threshold (3 failures), manual reset API, fingerprint excludes volatile params |
| Timeout Scaling | Underestimate -- still timeout on heavy ops | Safety factor 1.5x + hard cap at 2x max profile; heartbeat (P2) makes this less critical |
| Heartbeat Protocol | Wire protocol backward compatibility | Heartbeat uses existing length-prefixed framing; old clients that don't expect heartbeats will parse them as unknown responses (needs version negotiation) |
| Auto-Checkpoint | Stale checkpoint loaded for changed spec | `validate_checkpoint_compatibility()` already checks seed + location count; add spec hash check |
| Progressive Degradation | Wrong knobs -- degrades something the user needs | Always report degradation level in response; user can force `quality_level=0` to disable |
| Server Dedup | Race condition between fingerprint check and execution | `_dedup_lock` serializes check+register; 10s TTL on results prevents unbounded memory |

### 5.2 Backward Compatibility

- **Circuit breaker**: Fully additive. Old behavior = circuit always CLOSED.
- **Timeout scaling**: Clients that pass explicit `timeout` override the estimate. Default behavior changes from flat 300s to dynamic, but typical ops get the same or higher timeout.
- **Heartbeat**: Requires coordinated client+server upgrade. Version negotiation: client sends `{"_protocol_version": 2}` in first message; server only sends heartbeats if version >= 2.
- **Auto-checkpoint**: Always backward compatible. Existing `checkpoint_dir` callers see no change. New callers get auto-checkpointing for free.
- **Progressive degradation**: Opt-in per call site. Existing generators unchanged unless wrapped in `try_with_degradation()`.

### 5.3 Testing Strategy

1. **Circuit breaker**: Unit tests with mock failures; verify state transitions CLOSED->OPEN->HALF_OPEN->CLOSED
2. **Timeout scaling**: Parametric tests: known commands produce expected timeouts; unknown commands get safe defaults
3. **Heartbeat**: Integration test with real Blender connection; verify heartbeat messages received during long ops
4. **Auto-checkpoint**: Test compose_map with simulated mid-pipeline failure; verify resume picks up correctly
5. **Progressive degradation**: Mock generator that fails at level 0, succeeds at level 1; verify params are correctly degraded
6. **Server dedup**: Send duplicate commands concurrently; verify only one execution, both clients get same result

---

## 6. File Layout (New Files)

```
src/veilbreakers_mcp/shared/
    circuit_breaker.py       # CircuitBreaker class
    timeout_scaling.py       # estimate_timeout(), TIMEOUT_PROFILES
    complexity_estimator.py  # estimate_operation_complexity()
    degradation.py           # DEGRADATION_PROFILES, try_with_degradation()
```

Modified files:
```
src/veilbreakers_mcp/shared/blender_client.py   # Circuit breaker + timeout scaling + heartbeat receive
blender_addon/socket_server.py                    # Heartbeat send + command dedup
src/veilbreakers_mcp/blender_server.py           # Auto-checkpoint + degradation wrappers
```

---

## 7. Quick Win Checklist (Can Ship Today)

These require minimal code changes and prevent the most common loops:

- [ ] **Auto-checkpoint**: Add 4 lines to compose_map to default checkpoint_dir to tempdir
- [ ] **Timeout override for heavy commands**: In compose_map, set `self.blender.timeout = 600` before generating towns/castles, reset after
- [ ] **Max retry annotation in error messages**: When compose_map step fails, include `"retry_count": N, "max_retries_reached": bool` in the failure dict so Claude knows not to retry
- [ ] **Tripo Studio polling guard**: Cap `wait_for_task` at absolute 600s regardless of input timeout parameter
