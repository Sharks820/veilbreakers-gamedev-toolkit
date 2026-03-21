# Terminal 4: Infrastructure, Polish & Environment Generation

## Git Setup (DO THIS FIRST)
```bash
cd C:/Users/Conner/OneDrive/Documents/veilbreakers-gamedev-toolkit
git pull origin master
git checkout -b audit/infrastructure
```
Commit to `audit/infrastructure` branch. Do NOT commit to master.

---

## Scope
Token efficiency, defusedxml, testing infrastructure, shader pragmas, environment/worldbuilding generation, project metadata, and legacy cleanup. Also: structured logging but ONLY for files you own.

## YOUR Files (ONLY touch these)
```
# Infrastructure / shared
src/veilbreakers_mcp/shared/gemini_client.py
src/veilbreakers_mcp/shared/wcag_checker.py
src/veilbreakers_mcp/shared/unity_templates/ui_templates.py
src/veilbreakers_mcp/shared/config.py
src/veilbreakers_mcp/shared/texture_ops.py
src/veilbreakers_mcp/shared/texture_validation.py
src/veilbreakers_mcp/shared/palette_validator.py
src/veilbreakers_mcp/shared/asset_catalog.py
src/veilbreakers_mcp/blender_server.py
src/veilbreakers_mcp/unity_server.py
src/veilbreakers_mcp/unity_tools/__init__.py

# Environment & worldbuilding (Blender side)
blender_addon/handlers/environment.py
blender_addon/handlers/worldbuilding.py

# Shader pragmas
src/veilbreakers_mcp/shared/unity_templates/shader_templates.py

# World templates (town/building generation)
src/veilbreakers_mcp/shared/unity_templates/world_templates.py

# Project config
pyproject.toml

# Legacy cleanup
asset-pipeline/
blender-gamedev/
unity-enhanced/

# Tests
tests/test_environment*.py
tests/test_worldbuilding*.py
tests/test_shader*.py
tests/test_wcag*.py
tests/test_texture*.py
```

## DO NOT TOUCH (owned by other terminals)
```
blender_addon/handlers/rig_*.py             # Terminal 1
blender_addon/handlers/animation_*.py       # Terminal 2
src/veilbreakers_mcp/shared/_combat_timing.py  # Terminal 2
src/veilbreakers_mcp/shared/unity_templates/vfx_templates.py       # Terminal 3
src/veilbreakers_mcp/shared/unity_templates/vfx_mastery_templates.py # Terminal 3
src/veilbreakers_mcp/shared/unity_templates/animation_templates.py   # Terminal 3
src/veilbreakers_mcp/shared/unity_templates/cinematic_templates.py   # Terminal 3
src/veilbreakers_mcp/shared/unity_templates/camera_templates.py      # Terminal 3
src/veilbreakers_mcp/unity_tools/vfx.py     # Terminal 3
src/veilbreakers_mcp/unity_tools/camera.py  # Terminal 3
```

## Token Efficiency Scope Restriction
P4-I2 and P4-I3 (token efficiency) originally said "audit all 37 tools." However, several tool files are owned by other terminals. You may ONLY optimize tokens in:
- `blender_server.py` (all 15 Blender tools — you own this)
- `unity_server.py` (entry point)
- `unity_tools/__init__.py` (registration)
- Unity tool files NOT owned by T3: `unity_tools/scene.py`, `unity_tools/gameplay.py`, `unity_tools/game.py`, `unity_tools/content.py`, `unity_tools/code.py`, `unity_tools/data.py`, `unity_tools/editor.py`, `unity_tools/build.py`, `unity_tools/performance.py`, `unity_tools/prefab.py`, `unity_tools/settings.py`, `unity_tools/assets.py`, `unity_tools/audio.py`, `unity_tools/ui.py`, `unity_tools/ux.py`, `unity_tools/world.py`, `unity_tools/qa.py`, `unity_tools/quality.py`, `unity_tools/pipeline.py`, `unity_tools/shader.py`

Do NOT optimize tokens in `unity_tools/vfx.py` or `unity_tools/camera.py` (T3 owns those).

## Logging Scope Restriction
P4-I6 (add logging) applies ONLY to files you own. Do NOT add logging to files owned by other terminals. After all terminals merge, a follow-up pass can add logging everywhere.

---

## Interface Contract

### Shader Naming
You own the generic dissolve shader in `shader_templates.py`. Terminal 3 is creating a separate `VB_EvolutionDissolve` shader in their VFX templates. Your generic dissolve should remain named `VB_Dissolve`. No conflict.

### Token Efficiency Must Be Backward Compatible
When you remove redundant docstrings or compact parameters:
- Do NOT change tool names
- Do NOT change action names or their string values
- Do NOT remove any parameter — only shorten descriptions or merge related optional params into JSON objects
- The MCP tool interface must remain identical from the caller's perspective

### Environment Handler Functions
If you add new handler functions in `environment.py` or `worldbuilding.py`, follow the same registration protocol as T1/T2:
1. Create the function in the handler file
2. Document registrations in `docs/T4_REGISTRATIONS.md`
3. Do NOT edit `handlers/__init__.py` directly

---

## Tasks

### P4-I2: Token Efficiency — Remove Docstring Duplication (4h)
**What:** ~10,500 tokens wasted on duplicated text (same info in tool description + param help).

**How:**
- Audit each `@mcp.tool()` definition in `blender_server.py` and `unity_tools/*.py` (your scope only)
- Remove parameter `description` fields where the param name is self-explanatory (e.g., `name: str` doesn't need `description="The name"`)
- Keep descriptions only for non-obvious params (e.g., `brand` needs to list valid values)
- Shorten verbose help text: "The path to the file on disk" → "File path"
- Measure before/after: count total characters in all tool schemas

### P4-I3: Token Efficiency — Compact Optional Parameters (8h)
**What:** ~7,348 tokens from verbose optional param schemas.

**How:**
- Identify groups of related optional params that are always used together
- Merge into single JSON object params where logical:
  - `bloom_intensity` + `bloom_threshold` → `bloom: {"intensity": 1.0, "threshold": 0.9}`
  - `fog_color` + `fog_density` + `fog_start` → `fog: {...}`
- Update handler code to unpack the JSON object
- MUST be backward compatible — if someone passes the old flat params, they should still work
- Measure token savings

### P4-I5: Add defusedxml (2h)
**What:** XML parsing vulnerable to billion-laughs and XXE.

**How:**
1. Add `defusedxml>=0.7.1` to `[project.dependencies]` in `pyproject.toml`
2. In `src/veilbreakers_mcp/shared/wcag_checker.py`: replace `import xml.etree.ElementTree as ET` with `import defusedxml.ElementTree as ET`
3. In `src/veilbreakers_mcp/shared/unity_templates/ui_templates.py`: same replacement
4. Run tests to verify nothing breaks

### P4-I6: Add Structured Logging (16h — YOUR files only)
**What:** Add logging to files you own that currently have none.

**How:**
- Add to each file:
  ```python
  import logging
  logger = logging.getLogger(__name__)
  ```
- Add `logger.info()` at function entry points for key operations
- Add `logger.warning()` for fallback/degraded code paths
- Add `logger.error()` in except blocks
- Do NOT change any logic — only ADD log statements
- Files to add logging to (check which ones already have it):
  - `blender_server.py`, `wcag_checker.py`, `ui_templates.py`, `config.py`, `texture_ops.py`, `texture_validation.py`, `palette_validator.py`, `asset_catalog.py`, `environment.py`, `worldbuilding.py`, `shader_templates.py`, `world_templates.py`

### P4-I7: Add pytest-cov (4h)
**How:**
1. Add to `pyproject.toml` under `[project.optional-dependencies]`:
   ```toml
   dev = ["pytest", "pytest-asyncio", "pytest-cov", ...]
   ```
2. Add coverage config:
   ```toml
   [tool.coverage.run]
   source = ["src/veilbreakers_mcp"]
   omit = ["*/tests/*"]

   [tool.coverage.report]
   fail_under = 80
   show_missing = true
   skip_covered = true
   ```
3. Verify: `python -m pytest tests/ --cov --cov-report=term-missing -q`

### P4-I9: Update pyproject.toml Version (0.5h)
- Change `version = "0.1.0"` to `version = "3.1.0"`

### P4-I10: Remove Legacy Directories (1h)
- Check if `asset-pipeline/`, `blender-gamedev/`, `unity-enhanced/` exist at repo root
- Verify they're not imported/referenced by any active code:
  ```bash
  grep -r "asset-pipeline\|blender-gamedev\|unity-enhanced" src/ blender_addon/ tests/
  ```
- If safe, delete them
- If referenced, note in GAPS file

### P5-Q9: Terrain Generation at 4096+ (12h)
**File:** `blender_addon/handlers/environment.py`

**What:** Capped at 1024x1024, unvectorized Python loops.

**How:**
- Replace Python loops with numpy array operations for heightmap generation
- fBm noise: `heightmap = sum(amplitude * noise(x * frequency, y * frequency) for each octave)` — vectorize with numpy meshgrid
- Increase resolution cap: `max_resolution = 8192` (support 4096 and 8192)
- Add thermal erosion alongside existing hydraulic:
  - Thermal: material slides to neighbors if slope > talus angle
  - Iterate 100+ times for visible effect
- Increase hydraulic erosion max iterations from 500 to 10000
- Performance target: 4096x4096 heightmap in under 30 seconds

### P5-Q10: Town Generation — Euclidean Voronoi (16h)
**File:** `blender_addon/handlers/worldbuilding.py`

**What:** Manhattan distance produces diamonds. Need proper Voronoi.

**How:**
- Replace Manhattan distance (`abs(dx) + abs(dy)`) with Euclidean (`sqrt(dx² + dy²)`)
- Add road network: connect district centers with A* pathfinding, add secondary streets
- Add geography: accept terrain heightmap, don't place buildings on slopes >30° or underwater
- Add special districts: market_square (center, larger), residential, commercial, industrial
- Road geometry: create mesh strips along road paths with configurable width

### P5-Q11: Building Grammar with Openings (12h)
**File:** `blender_addon/handlers/worldbuilding.py`

**What:** All buildings are solid boxes. No windows or doors.

**How:**
- Window openings: boolean difference on wall mesh using small rectangular prisms
- Door cutouts: boolean difference at ground level, wider than windows
- Style-aware opening shapes:
  - Gothic: pointed arch (V-shape top)
  - Medieval: small square windows, rounded door arch
  - Industrial: large rectangular windows, roll-up doors
- Add sill geometry below windows, lintel above
- LOD-aware: LOD0 = full detail with openings, LOD1 = simplified (no sills/lintels), LOD2 = solid box

### P5-Q12: Shadow/Fog Pragmas for Shaders (4h)
**File:** `src/veilbreakers_mcp/shared/unity_templates/shader_templates.py`

**What:** Dissolve and force-field shaders missing shadow/fog support.

**How:**
- Audit every shader generation function in `shader_templates.py`
- Add to each shader's Pass that's missing them:
  ```hlsl
  #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
  #pragma multi_compile _ _ADDITIONAL_LIGHTS
  #pragma multi_compile_fog
  ```
- Add ShadowCaster pass to shaders that cast shadows:
  ```hlsl
  Pass {
      Name "ShadowCaster"
      Tags { "LightMode" = "ShadowCaster" }
      // ... standard shadow caster implementation
  }
  ```
- Verify generated shaders are valid URP ShaderLab

---

## Post-Task Protocol

### After EACH task:
1. Run your relevant tests:
   ```bash
   cd Tools/mcp-toolkit && python -m pytest tests/ -k "environment or worldbuilding or shader or wcag or texture or security" --tb=short -q
   ```
2. Full suite regression check:
   ```bash
   cd Tools/mcp-toolkit && python -m pytest tests/ --tb=short -q
   ```
3. If ANY failures, fix and re-scan. Repeat until CLEAN.
4. Pull and rebase:
   ```bash
   git fetch origin master && git rebase origin/master
   git add <your-files-only>
   git commit -m "$(cat <<'EOF'
   <type>: <description>

   Co-Authored-By: Claude <noreply@anthropic.com>
   EOF
   )"
   ```

### Commit types: `feat:` (new), `fix:` (bug), `chore:` (infra), `perf:` (token efficiency)

### If you find gaps in OTHER terminals' files:
Write to `docs/GAPS_FROM_T4.md` — do NOT edit their files.

---

## Quality Bar
- Token reduction must be measurable (document before/after counts)
- defusedxml must be a real dependency that installs
- Logging must not change ANY existing behavior
- Terrain 4096x4096 completes in under 30 seconds
- Town Voronoi districts are visually round/organic, not diamond-shaped
- Building windows are actual boolean cutouts, not textures
- All shader pragmas produce valid URP shaders
- pyproject.toml version = "3.1.0"
- Legacy directories removed (if safe)
- All new code has tests
- All tests pass after every commit
