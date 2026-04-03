# Deep Bug Scan: Unity Template C# Correctness

**Date:** 2026-04-02
**Scope:** 10 most complex unity_templates files - semantic/runtime correctness of generated C#
**Focus:** NEW bugs only - not Shader.Find null, unsanitized names, deprecated APIs, heightmap endianness, resolution validation

---

## Critical Bugs (Will crash or produce wrong behavior at runtime)

### BUG-CS-001: VB_WaypointManager is both singleton AND trigger receiver on same object
**File:** `world_templates.py` - `generate_fast_travel_script()`
**Lines:** ~1269-1374
**Problem:** `VB_WaypointManager` has `DontDestroyOnLoad` singleton pattern AND `OnTriggerEnter()` on the same class. The manager object is created as a standalone empty GameObject. It will NEVER receive trigger events because:
1. It has no Collider component
2. It's a singleton manager, not placed at waypoint locations
3. The `OnTriggerEnter` checks `gameObject.name` as waypointId, but the manager's name is "VB_WaypointManager"

The architecture is confused -- individual waypoint GameObjects need the trigger collider, but the manager has the trigger code. The `DiscoverWaypoint(string)` public method is the only way this actually works.

**Severity:** HIGH - Trigger-based waypoint discovery is completely broken
**Fix:** Extract trigger logic into a separate `VB_WaypointTrigger` MonoBehaviour placed on each waypoint object, which calls `VB_WaypointManager.Instance.DiscoverWaypoint(waypointId)`.

---

### BUG-CS-002: `position != default` is always true for non-origin positions but ALSO true for Vector3.zero
**File:** `world_templates.py` - `generate_fast_travel_script()`
**Line:** ~1347
**Code:** `if (player != null && position != default)`
**Problem:** `default` for `Vector3` is `Vector3.zero`. This means if someone intentionally teleports to world origin (0,0,0), the position won't be applied. More critically, `Vector3` is a struct and `!=` uses approximate comparison -- this is technically correct but semantically wrong. Should use a nullable or explicit sentinel value.

**Severity:** MEDIUM - Teleporting to (0,0,0) silently fails

---

### BUG-CS-003: InteriorStreamingManager.MemoryBudgetMB crashes on empty scenes
**File:** `world_templates.py` - `generate_interior_streaming_script()`
**Lines:** ~3159-3168
**Code:**
```csharp
foreach (var kvp in _loadedInteriors)
    total += UnityEngine.Profiling.Profiler.GetRuntimeMemorySizeLong(
        kvp.Value.Scene.GetRootGameObjects()[0]) / (1024f * 1024f);
```
**Problem:** `GetRootGameObjects()[0]` throws `IndexOutOfRangeException` if the loaded scene has zero root GameObjects. Additionally, `GetRuntimeMemorySizeLong` on a single root GameObject does NOT measure the entire scene's memory -- it only measures that one object, not its children, meshes, textures, etc.

**Severity:** HIGH - Crash on access to empty scene + always returns wrong memory estimate

---

### BUG-CS-004: CrossfadeAudio volume comparison after assignment always evaluates wrong
**File:** `world_templates.py` - `generate_interior_streaming_script()`
**Line:** ~3321
**Code:** `if (fadeOut.volume <= 0f) fadeOut.Stop();`
**Problem:** This line comes AFTER `fadeOut.volume = 0f;` on line 3319, so the condition is always true. But the real bug is that when transitioning to exterior (`targetClip == null`), the fadeIn source is `_exteriorAmbientSource` and `fadeOut` is `_interiorAmbientSource`. If no interior clip was ever set, `_interiorAmbientSource.clip` is null and calling Stop() is harmless but misleading. The bigger issue: `_exteriorAmbientSource` is faded in but was never given a clip or started playing, so volume goes to 1.0 on a silent source.

**Severity:** MEDIUM - Audio crossfade produces silence in both directions on first use

---

### BUG-CS-005: Weather system GetMaxEmissionRate hardcodes weather states ignoring user-customized states
**File:** `world_templates.py` - `generate_weather_system_script()`
**Lines:** ~2031-2033
**Code:** `switch (state) { case WeatherState.Rain: return 500f; ... default: return 0f; }`
**Problem:** The `weather_states` parameter allows custom state names (e.g., "Sandstorm", "Blizzard"), and these are added to the enum. But `GetMaxEmissionRate()`, `GetFogDensity()`, and `GetFogColor()` only handle the 5 hardcoded states (Clear/Rain/Snow/Fog/Storm). Custom states fall through to `default` returning 0 emission rate, meaning custom weather transitions produce zero particles.

**Severity:** HIGH - Custom weather states are visually broken

---

### BUG-CS-006: DayNightCycle lighting interpolation wraps incorrectly at midnight boundary
**File:** `world_templates.py` - `generate_day_night_cycle_script()`
**Lines:** ~2167-2179
**Problem:** The preset finding loop `for (int i = 0; i < _presets.Length; i++)` finds prev/next by scanning linearly. When `_timeOfDay` is 23.5 (between Night at 22.0 and Midnight at 0.0), the loop sets `prev = Night` (hour=22) but `next` stays as `_presets[0]` which is Dawn (hour=5.0), skipping Midnight entirely. The range calculation `next.hour - prev.hour` = 5.0 - 22.0 = -17.0, then `+= 24` = 7.0. Offset = 23.5 - 22.0 = 1.5. t = 1.5/7.0 = 0.214. This interpolates between Night and Dawn instead of Night and Midnight, causing a sudden brightness jump.

**Severity:** HIGH - Lighting discontinuity at the midnight wrap-around boundary

---

### BUG-CS-007: VB_PlayerCombat references non-existent types without using directives
**File:** `vb_combat_templates.py` - `generate_player_combat_script()`
**Lines:** ~134-140
**Code:**
```csharp
using VeilBreakers.Combat;
using VeilBreakers;
using VeilBreakers.Systems;
using VeilBreakers.Data;
```
Then uses `DamageResult`, `DamageCalculator`, `DamageType.PHYSICAL`, `Combatant`, `EventBus` -- all project-specific types. The class is generated inside `namespace VeilBreakers.Combat`, which means `DamageResult` must exist in that or an imported namespace. If it doesn't exist in the project, the script won't compile at all.

**Problem:** This is WIRING code (documented at top), but the generated script provides no compile guard, no `#if` directive, and no fallback. A user generating this into a fresh project gets immediate compile errors with zero guidance.

**Severity:** MEDIUM - Won't compile without existing VeilBreakers combat framework

---

### BUG-CS-008: Combo VFX ChromaticAberrationPulse animates Volume.weight, not ChromaticAberration override
**File:** `combat_vfx_templates.py` - `generate_combo_vfx_script()`
**Lines:** ~619-648
**Problem:** The code creates a `VolumeProfile` but never adds a `ChromaticAberration` override to it. It then animates `postVolume.weight` between 0 and `intensity`. Since the profile has no overrides at all, changing weight does nothing visible. The function is named `ChromaticAberrationPulse` but produces zero chromatic aberration.

**Severity:** HIGH - Screen effect completely non-functional

---

### BUG-CS-009: Cinemachine impulse source type string is wrong for Cinemachine 3.x
**File:** `combat_vfx_templates.py` - `generate_combo_vfx_script()`
**Lines:** ~653-659
**Code:**
```csharp
var impulseType = System.Type.GetType("Cinemachine.CinemachineImpulseSource, Cinemachine");
```
**Problem:** In Cinemachine 3.x (Unity.Cinemachine package), the namespace is `Unity.Cinemachine`, not `Cinemachine`. The assembly is also `Unity.Cinemachine` not `Cinemachine`. This reflection lookup will always return null, silently disabling screen shake. The camera_templates.py file correctly uses `using Unity.Cinemachine;` showing the rest of the codebase knows the correct namespace.

**Severity:** HIGH - Screen shake silently disabled in all combo VFX

---

### BUG-CS-010: VB_SettingsMenu slider callbacks leak on every BindUI() call
**File:** `game_templates.py` - `generate_settings_menu_script()`
**Lines:** ~1818-1826
**Problem:** `BindSlider()` calls `slider.RegisterValueChangedCallback(evt => onChange?.Invoke(evt.newValue))` with a lambda. Unlike the named callback methods for dropdowns/toggles which can be unregistered via `UnregisterAllCallbacks()`, slider lambdas CANNOT be unregistered because the lambda reference is lost. Every call to `RevertPending()` or `ResetToDefaults()` calls `BindUI()` which re-registers NEW lambda callbacks without removing old ones, causing the callback to fire N times after N revert operations.

**Severity:** HIGH - Slider values applied N times after N settings reverts, causing exponential volume jumps and other setting cascades

---

### BUG-CS-011: VB_HttpClient static class has instance coroutine methods
**File:** `game_templates.py` - `generate_http_client_script()`
**Lines:** ~2251-2255
**Code:**
```csharp
public static IEnumerator Get<T>(string url, Action<HttpResponse<T>> callback)
```
**Problem:** The pre-Unity 6 coroutine fallback path returns `IEnumerator` from a `static` class. These must be called with `StartCoroutine()` on a MonoBehaviour instance. But `VB_HttpClient` is a static class with no instance. The caller must know to call `someMonoBehaviour.StartCoroutine(VB_HttpClient.Get<T>(...))`, which is undocumented and counter-intuitive. The Unity 6 `Awaitable` path works fine since `await` doesn't need an instance.

**Severity:** MEDIUM - Pre-Unity-6 path requires undocumented MonoBehaviour host

---

### BUG-CS-012: Encounter manager victory check loop has short-circuit logic error
**File:** `encounter_templates.py` - `generate_encounter_system_script()`
**Lines:** ~264-276
**Problem:** The victory condition check iterates ALL conditions in a `foreach` but uses simple `if` statements that can set `waveComplete = true` and then continue checking. If `victoryConditions = ["all_dead", "timer"]`, and all enemies are dead at the 30-second mark (before the 60s timeLimit), the first check sets `waveComplete = true`, but the loop continues and the timer check also passes. This isn't a logic error per se (both conditions being met is fine), BUT: the conditions are meant to be OR'd (any one satisfied = wave complete). The code works by accident for OR semantics but doesn't support AND semantics if ever needed. More importantly, the `"boss_dead"` condition is identical to `"all_dead"` -- same check, same result. It doesn't actually verify a boss-type enemy was killed.

**Severity:** LOW-MEDIUM - `boss_dead` condition is misleading; functionally identical to `all_dead`

---

### BUG-CS-013: VB_Door MoveRoutine Animator path waits for wrong state
**File:** `world_templates.py` - `generate_door_system_script()`
**Lines:** ~3686-3691
**Code:**
```csharp
_animator.SetTrigger(opening ? _openTrigger : _closeTrigger);
yield return null; // let trigger propagate
AnimatorStateInfo info = _animator.GetCurrentAnimatorStateInfo(0);
yield return new WaitForSeconds(info.length);
```
**Problem:** After setting a trigger and yielding one frame, the Animator may still be in the PREVIOUS state (triggers don't transition instantly; they require the current state's exit time or HasExitTime=false). `GetCurrentAnimatorStateInfo(0)` returns the OLD state's info, so `info.length` is the PREVIOUS animation's length, not the door open/close animation length. The door will finish its state transition after the wrong duration.

**Severity:** HIGH - Door open/close timing is wrong when using Animator path

---

### BUG-CS-014: CinemachineRotationComposer.Damping type mismatch between camera types
**File:** `camera_templates.py` - `generate_cinemachine_setup_script()`
**Lines:** ~156 vs ~165 vs ~181
**Problem:** For "orbital" camera: `composer.Damping = new Vector2(...)` (correct for RotationComposer).
For "dolly" camera: `composer.Damping = new Vector3(...)` (WRONG -- RotationComposer.Damping is Vector2, not Vector3).
This will cause a compile error for dolly camera type.

**Severity:** HIGH - Dolly camera generation produces non-compiling C#

---

### BUG-CS-015: Terrain building blend DepressTerrain heightmap axis mapping swapped
**File:** `world_templates.py` - `generate_terrain_building_blend_script()`
**Lines:** ~2589-2600
**Code:**
```csharp
float relX = (buildingPos.x - terrainPos.x) / terrainData.size.x;
float relZ = (buildingPos.z - terrainPos.z) / terrainData.size.z;
int centerX = Mathf.Clamp(Mathf.RoundToInt(relX * mapW), 0, mapW - 1);
int centerZ = Mathf.Clamp(Mathf.RoundToInt(relZ * mapH), 0, mapH - 1);
```
Then:
```csharp
float[,] heights = terrainData.GetHeights(startX, startZ, width, height);
```
**Problem:** `TerrainData.GetHeights(xBase, yBase, width, height)` uses `yBase` for the Z-axis in world space. The parameter names are misleading: the first two params are `xBase` (terrain-local X index) and `yBase` (terrain-local Z index). The code passes `startX` (derived from world X) and `startZ` (derived from world Z) which IS correct. However, the later loop `heights[z, x]` indexes as `[row, col]` where row corresponds to the Z-axis. The distance calculation uses `startX + x - centerX` and `startZ + z - centerZ` which correctly maps. **This one is actually fine on closer inspection.** Retracted.

---

### BUG-CS-016: VB_InputConfig never unregisters lambda callbacks from InputActionMap on destroy
**File:** `game_templates.py` - `generate_input_config_script()`
**Lines:** ~1500-1514
**Code:**
```csharp
_gameplayMap["Move"].performed += ctx => OnMove?.Invoke(ctx.ReadValue<Vector2>());
```
**Problem:** Lambda callbacks registered on InputActions are never unregistered in `OnDisable()` or `OnDestroy()`. The class calls `_inputActions?.Disable()` in `OnDisable()` which prevents the actions from firing, but the delegates remain registered. If the MonoBehaviour is destroyed and recreated (e.g., scene reload), old delegates pointing to destroyed objects remain, causing either null reference exceptions or double-firing when the input asset is shared.

**Severity:** MEDIUM - Memory leak + potential NullReferenceException after scene reload

---

### BUG-CS-017: PressurePlatePuzzle weight tracking doesn't handle rapid enter/exit
**File:** `world_templates.py` - `generate_puzzle_mechanics_script()`
**Lines:** ~1466-1491
**Problem:** `OnTriggerEnter` adds `rb.mass` and calls `CheckSolved()`. `OnTriggerExit` subtracts `rb.mass` but does NOT call `CheckSolved()`. If the exact solution weight is reached while an object is on the plate, then another object enters pushing weight over, then exits back to the exact weight -- `CheckSolved()` is only called on enter, not on exit. The puzzle can only be solved during `OnTriggerEnter`, never during `OnTriggerExit`.

**Severity:** MEDIUM - Puzzle unsolvable in legitimate scenarios involving weight reduction

---

## Summary

| ID | Severity | File | Bug |
|----|----------|------|-----|
| CS-001 | HIGH | world_templates | WaypointManager trigger code on wrong object |
| CS-002 | MEDIUM | world_templates | Vector3.zero sentinel blocks teleport to origin |
| CS-003 | HIGH | world_templates | MemoryBudgetMB crashes on empty scene + wrong estimate |
| CS-004 | MEDIUM | world_templates | Audio crossfade broken on first use |
| CS-005 | HIGH | world_templates | Custom weather states get zero particles |
| CS-006 | HIGH | world_templates | Day/night lighting jumps at midnight boundary |
| CS-007 | MEDIUM | vb_combat_templates | Won't compile without full VB combat framework |
| CS-008 | HIGH | combat_vfx_templates | ChromaticAberration effect completely non-functional |
| CS-009 | HIGH | combat_vfx_templates | Cinemachine 3.x namespace wrong, shake disabled |
| CS-010 | HIGH | game_templates | Settings slider callbacks leak exponentially |
| CS-011 | MEDIUM | game_templates | Pre-Unity6 HTTP needs undocumented MonoBehaviour host |
| CS-012 | LOW | encounter_templates | boss_dead identical to all_dead |
| CS-013 | HIGH | world_templates | Door Animator path waits for wrong animation length |
| CS-014 | HIGH | camera_templates | Dolly camera Damping type mismatch won't compile |
| CS-016 | MEDIUM | game_templates | InputConfig lambda callbacks never unregistered |
| CS-017 | MEDIUM | world_templates | PressurePlate only checks solved on enter, not exit |

**Total NEW bugs found: 16**
- HIGH: 8
- MEDIUM: 7
- LOW: 1
