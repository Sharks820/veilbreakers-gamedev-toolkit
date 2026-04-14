# Design — Four-Repo Split: Terrain, Architecture, Shared, Toolkit

**Date:** 2026-04-13
**Author:** Conner (Sharks820)
**Status:** Draft — pending spec-reviewer + user approval
**Supersedes boundary portion of:** `2026-04-03-terrain-world-generation-overhaul-design.md`
**Companion research:** `.planning/research/TERRAIN_DEEP_RESEARCH_2026-04-13.md`

---

## Summary

Split the VeilBreakers MCP toolkit monorepo into four dedicated git repositories to establish clean domain boundaries, enable each domain to evolve independently, and unblock the three CRITICAL terrain wiring failures identified in the 2026-04-13 deep research.

- **veilbreakers-gamedev-toolkit** (existing) — platform shell: Blender addon, MCP servers, addon primitives, unsorted flat handlers, `.mcp.json`.
- **veilbreakers-terrain** (new, public, MIT) — all terrain/water/caves/waterfalls + environmental props + biomes.
- **veilbreakers-architecture** (new, public, MIT) — all buildings/settlements/dungeons/castles/interiors/modular kits + worldbuilding coordinator.
- **veilbreakers-shared** (new, public, MIT) — addon helpers + code-reviewer MCP.

Integration via editable pip installs from sibling disk paths. Execution is **strictly two-phase**: Phase 1 is a mechanical extraction with history (zero behavior change, test count invariant); Phase 2 fixes the three CRITICAL wiring blockers from the 4/13 research.

---

## Goals

1. Each domain gets a crisp repo boundary with its own issues, PRs, tags, and CI.
2. Terrain and architecture never import each other — domain coupling is forbidden and lint-enforced.
3. Code reviewer becomes a standalone, reusable MCP that other projects can adopt (`pip install veilbreakers-shared`).
4. 20,900+ existing tests stay green through Phase 1. Test-count invariant across all 4 repos.
5. Phase 2 closes the three CRITICAL terrain wiring failures: 3D cave voxel meshes, volumetric waterfall meshes, WaterNetwork→mesh bridge (6 disconnection points).

## Non-Goals (explicit)

- Moving the ~86 unsorted flat handlers (animation, armor, character, weapon, combat, atmospheric, decal, loot, encounter, boss, hair, clothing, etc.) — they stay flat in the toolkit's `handlers/`. Splitting them into further dedicated repos is future work.
- 4/13 research Priorities 4–7 (water flow shader, 5-layer terrain texturing, stitching-band blending, forests/clearings) — each deserves its own follow-up spec.
- Restructuring the MCP server process architecture (`blender_server.py`, `unity_server.py` layout).
- Publishing the new packages to PyPI. Public GitHub repos only for now; PyPI is a later decision.
- Breaking up the 5453-line `environment.py` monolith or the 8070-line `worldbuilding.py` monolith — they move as whole files in Phase 1 and can be split in later specs.

---

## Repository Layout

### veilbreakers-gamedev-toolkit (existing — trimmed)

```
Tools/mcp-toolkit/
├── blender_addon/
│   ├── __init__.py          # addon entry, gains bootstrap check for vb_* packages
│   ├── socket_server.py
│   ├── security.py
│   └── handlers/
│       ├── __init__.py      # action dispatch (imports from vb_terrain, vb_architecture)
│       ├── scene.py objects.py viewport.py materials.py export.py mesh.py execute.py
│       └── (~86 unsorted flat handlers)
├── src/veilbreakers_mcp/
│   ├── blender_server.py    # stays
│   ├── unity_server.py      # stays
│   ├── unity_tools/         # stays
│   └── shared/              # stays (blender_client, config, asset_catalog, etc.)
├── tests/
│   ├── shared/              # addon-primitive tests + cross-cutting integration
│   └── (non-domain flat tests)
├── scripts/
│   └── check_import_direction.py  # new: enforces repo boundary
└── .mcp.json                # vb-review rewired to point at veilbreakers-shared
```

### veilbreakers-terrain (new)

```
veilbreakers-terrain/
├── src/vb_terrain/
│   ├── __init__.py          # public API: re-exports handle_* + dataclasses
│   ├── terrain_caves.py
│   ├── terrain_waterfalls.py
│   ├── terrain_waterfalls_volumetric.py
│   ├── _water_network.py
│   ├── _water_network_ext.py
│   ├── environment.py       # 5453-line monolith, whole-file move
│   ├── environment_scatter.py
│   ├── coastline.py
│   ├── atmospheric_volumes.py
│   ├── _biome_grammar.py
│   ├── _terrain_*.py        # all erosion, depth, noise, world files
│   ├── terrain_*.py         # ~100 terrain domain files
│   ├── cave_voxel_carver.py # NEW, Phase 2
│   └── VERTEX_COLOR_ENCODING.md  # NEW, Phase 2
├── tests/
│   ├── test_terrain_*.py
│   ├── test_water_*.py
│   ├── test_cave_voxel_carver.py       # NEW
│   ├── test_waterfall_volumetric.py    # NEW
│   └── test_water_network_bridge.py    # NEW
├── contracts/
│   └── terrain.yaml         # copied from toolkit's .planning/contracts/terrain.yaml
├── scripts/
│   ├── quality_lint.py      # package-scoped
│   ├── brief_agent.py
│   ├── honesty_lint.py
│   └── test_substance_lint.py
├── pyproject.toml           # deps: vb-addon-shared, scikit-image>=0.22, trimesh>=4.0
├── README.md
├── LICENSE                  # MIT
├── .gitignore
└── .github/workflows/ci.yml # pytest matrix
```

### veilbreakers-architecture (new)

```
veilbreakers-architecture/
├── src/vb_architecture/
│   ├── __init__.py
│   ├── _building_grammar.py
│   ├── _settlement_grammar.py
│   ├── _dungeon_gen.py
│   ├── building_interior_binding.py
│   ├── building_quality.py
│   ├── dungeon_themes.py
│   ├── modular_building_kit.py
│   ├── settlement_generator.py
│   ├── worldbuilding.py         # 8070-line coordinator, whole-file move
│   └── worldbuilding_layout.py
├── tests/
├── contracts/
│   └── architecture.yaml    # new, starts minimal with TODOs
├── scripts/                 # same quality tooling
├── pyproject.toml           # deps: vb-addon-shared, vb-terrain (read-only consumer for compose_map)
├── README.md
├── LICENSE                  # MIT
├── .gitignore
└── .github/workflows/ci.yml
```

### veilbreakers-shared (new)

```
veilbreakers-shared/
├── packages/
│   ├── vb_addon_shared/
│   │   ├── src/vb_addon_shared/
│   │   │   ├── __init__.py
│   │   │   ├── context.py            # was _context.py
│   │   │   ├── mesh_bridge.py        # was _mesh_bridge.py (44KB)
│   │   │   ├── shared_utils.py
│   │   │   ├── action_compat.py
│   │   │   └── scatter_engine.py
│   │   ├── tests/
│   │   └── pyproject.toml
│   └── vb_code_reviewer/
│       ├── src/vb_code_reviewer/
│       │   ├── __init__.py
│       │   ├── reviewer.py           # was vb_code_reviewer.py (3426 lines)
│       │   ├── python_reviewer.py
│       │   ├── ast_analyzer.py
│       │   ├── context_engine.py
│       │   ├── rules_python.py       # 2408 lines
│       │   ├── rules_csharp.py
│       │   ├── rules_csharp_core.py
│       │   ├── rules_csharp_unity.py
│       │   ├── tool_runner.py
│       │   ├── types.py
│       │   └── review_server.py      # 1178 lines — MCP server entry
│       ├── tests/
│       └── pyproject.toml            # entry_point: vb-review-mcp
├── pyproject.toml                    # workspace root
├── README.md
├── LICENSE                           # MIT
└── .github/workflows/ci.yml
```

---

## Dependency Graph (lint-enforced)

```
veilbreakers-terrain ───┐
                        ├──► veilbreakers-shared (vb_addon_shared)
veilbreakers-architecture ─┘

veilbreakers-architecture ──► veilbreakers-terrain  (read-only: compose_map uses WaterNetwork, terrain heightmap)
                                                     NOT the reverse.

veilbreakers-gamedev-toolkit ──► all three
```

**Rules:**
- `vb_terrain` **may not** import `vb_architecture` (enforced).
- `vb_architecture` **may** import `vb_terrain` as a read-only consumer (e.g., `worldbuilding.py` reads heightmap + WaterNetwork from terrain to place settlements). This one-way coupling matches the physical reality that settlements sit on terrain, not the other way around.
- Neither may import from `veilbreakers-gamedev-toolkit`.
- `vb_addon_shared` and `vb_code_reviewer` have zero dependencies on the three other repos.
- Lint: `scripts/check_import_direction.py` (lives in toolkit repo, CI-enforced on all four) walks AST of each package and fails the build on violations.

---

## Integration Model — Editable Pip Installs

All four repos sit as siblings on disk:

```
C:\Users\Conner\OneDrive\Documents\
├── veilbreakers-gamedev-toolkit\   (existing)
├── veilbreakers-terrain\           (new)
├── veilbreakers-architecture\      (new)
└── veilbreakers-shared\            (new)
```

Setup commands (one-time, documented in each repo's README):

```bash
# In toolkit's uv venv and in Blender's bundled Python:
pip install -e ../veilbreakers-shared/packages/vb_addon_shared
pip install -e ../veilbreakers-shared/packages/vb_code_reviewer
pip install -e ../veilbreakers-terrain
pip install -e ../veilbreakers-architecture
```

**Addon bootstrap** (`blender_addon/__init__.py` gains a small preflight check):

```python
def _preflight_check_packages():
    """Verify sibling repos are installed. Fail loudly with setup hint if not."""
    missing = []
    for pkg in ("vb_addon_shared", "vb_terrain", "vb_architecture"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        raise ImportError(
            f"VeilBreakers addon missing required packages: {missing}. "
            f"Run: pip install -e ../veilbreakers-{{name}} for each. "
            f"See docs/REPO_SETUP.md in the toolkit repo."
        )
```

No `sys.path` hackery. Proper pip installs only. Addon zip build (future CI work) will bundle the sister repos' `src/` trees in at package time.

---

## Phase 1 — Mechanical Extraction With History

**Prerequisite** (one atomic commit in toolkit, before any extraction):
- Commit the 4 currently-dirty files + clean up `Temp/` scratch work.
- Record baseline: `pytest -q 2>&1 | tail -3` → `N` passed, `S` skipped, `X` xfailed. Write to `docs/superpowers/specs/2026-04-13-repo-split-BASELINE.md`.
- Tag: `git tag pre-split-baseline`.

### Step 1 — Extract `veilbreakers-shared`

```bash
cd C:/Users/Conner/OneDrive/Documents
git clone veilbreakers-gamedev-toolkit veilbreakers-shared
cd veilbreakers-shared
git filter-repo \
  --path Tools/mcp-toolkit/blender_addon/handlers/_context.py \
  --path Tools/mcp-toolkit/blender_addon/handlers/_mesh_bridge.py \
  --path Tools/mcp-toolkit/blender_addon/handlers/_shared_utils.py \
  --path Tools/mcp-toolkit/blender_addon/handlers/_action_compat.py \
  --path Tools/mcp-toolkit/blender_addon/handlers/_scatter_engine.py \
  --path Tools/mcp-toolkit/src/veilbreakers_mcp/vb_code_reviewer.py \
  --path Tools/mcp-toolkit/src/veilbreakers_mcp/vb_python_reviewer.py \
  --path Tools/mcp-toolkit/src/veilbreakers_mcp/_ast_analyzer.py \
  --path Tools/mcp-toolkit/src/veilbreakers_mcp/_context_engine.py \
  --path Tools/mcp-toolkit/src/veilbreakers_mcp/_rules_python.py \
  --path Tools/mcp-toolkit/src/veilbreakers_mcp/_rules_csharp.py \
  --path Tools/mcp-toolkit/src/veilbreakers_mcp/_rules_csharp_core.py \
  --path Tools/mcp-toolkit/src/veilbreakers_mcp/_rules_csharp_unity.py \
  --path Tools/mcp-toolkit/src/veilbreakers_mcp/_tool_runner.py \
  --path Tools/mcp-toolkit/src/veilbreakers_mcp/_types.py \
  --path Tools/mcp-toolkit/src/veilbreakers_mcp/review_server.py \
  --path-glob "Tools/mcp-toolkit/tests/test_reviewer_*.py" \
  --path-glob "Tools/mcp-toolkit/tests/test_vb_code_reviewer_*.py"
```

Then reorganize with `git mv` into `packages/vb_addon_shared/src/vb_addon_shared/` and `packages/vb_code_reviewer/src/vb_code_reviewer/`. Rename files to drop leading underscores on public modules. Write `pyproject.toml` per package + workspace root. Add README, LICENSE, `.gitignore`, CI. Create GitHub repo under `Sharks820/veilbreakers-shared`, push.

### Step 2 — Extract `veilbreakers-terrain`

Same pattern. `git filter-repo` preserves history for every `terrain_*.py`, `_terrain_*.py`, `_water_*.py`, `_biome_grammar.py`, `environment.py`, `environment_scatter.py`, `coastline.py`, `atmospheric_volumes.py`, and every matching `tests/test_*.py`. Reorganize into `src/vb_terrain/`. Copy `.planning/contracts/terrain.yaml` → `contracts/terrain.yaml`. Copy `scripts/quality_lint.py` + `brief_agent.py` + `honesty_lint.py` + `test_substance_lint.py` and generalize each to accept `--package-root` (they currently hard-code paths). `pyproject.toml` depends on `vb-addon-shared` + dev deps `scikit-image>=0.22`, `trimesh>=4.0`. Create GitHub repo, push.

### Step 3 — Extract `veilbreakers-architecture`

Same pattern. Files matching `*building*`, `*settlement*`, `*dungeon*`, `*castle*`, `*interior*`, `modular_*`, `worldbuilding*`. Depends on `vb-addon-shared` and `vb-terrain` (one-way consumer). Fresh starter `contracts/architecture.yaml` with TODO markers for kit/grammar/settlement contracts (full contract design is future work). Create GitHub repo, push.

### Step 4 — Remove extracted files from toolkit

On branch `feature/repo-split-phase1` in toolkit:
- `git rm` every file that was extracted into the three new repos.
- Do NOT rewrite toolkit history — a normal `git rm` commit is sufficient and safer than filter-repo. The files' history remains in each new repo where they now live.
- One commit: `"refactor(split): remove terrain/architecture/shared files — migrated to dedicated repos"`.

### Step 5 — Rewire toolkit against new repos

- Run the four `pip install -e ../veilbreakers-*` commands.
- Rewrite `blender_addon/handlers/__init__.py` dispatch imports from `from .terrain_caves import handle_X` → `from vb_terrain import handle_X` for every moved handler. Action names are unchanged; the MCP public surface is byte-identical.
- Rewrite `.mcp.json` `vb-review` entry:
  ```json
  "vb-review": {
    "type": "stdio",
    "command": "uv",
    "args": ["--directory", "../veilbreakers-shared/packages/vb_code_reviewer", "run", "vb-review-mcp"]
  }
  ```
- Add preflight check in addon `__init__.py`.
- Add `scripts/check_import_direction.py` — AST walker that fails if `vb_terrain` imports `vb_architecture` or vice versa.
- One commit per logical change: `"refactor(split): rewire handler imports against vb_terrain"`, `"refactor(split): rewire handler imports against vb_architecture"`, `"refactor(split): rewire vb-review MCP to veilbreakers-shared"`, `"infra(split): import direction enforcement lint"`.

### Step 6 — Validate

| Gate | Command | Pass condition |
|---|---|---|
| G1. Tests invariant | `pytest -q` in each of 4 repos, sum counts | Σ passed == `N`, Σ skipped == `S`, Σ xfailed == `X` |
| G2. Quality lint clean | `python scripts/quality_lint.py --package-root src/vb_terrain` in terrain repo | ≤ 16 findings |
| G3. Import direction | `python scripts/check_import_direction.py` in toolkit | passes |
| G4. Addon loads | Start Blender, enable addon, check status bar | "Server auto-started" appears |
| G5. MCP smoke | `blender_scene action=get_scene_info` via vb-blender | returns OK |
| G6. Reviewer smoke | `review_text` via new vb-review endpoint | returns analysis |
| G7. Git bisect works | `git bisect` any single step's commit | narrows to ≤ one extraction step |

Each repo gets `v0.1.0` tag once G1–G7 pass.

### Step 7 — GitHub setup

Push three new repos as public under `Sharks820`. Each gets README with "What this is / How to install / How to develop / License MIT". CI runs `pytest` + `quality_lint` on push. Protect `main` branches. Enable Dependabot for security updates.

---

## Phase 2 — Three CRITICAL Wiring Fixes

All Phase 2 work is in `veilbreakers-terrain` repo. Architecture and shared untouched. Each fix ships as its own commit range + test suite + visual verification.

### Fix 1 — 3D Cave Voxel Carving

**Bug (4/13 research #9, critical):** `terrain_caves.py:867` writes `cave_height_delta` but it's never applied; caves exist only as 2D mask-stack metadata.

**Implementation:**

New file: `src/vb_terrain/cave_voxel_carver.py`.

1. Accept cave archetype paths (existing output of `terrain_caves.py`) as centerlines.
2. Create 3D numpy voxel grid sized to terrain bounds × configurable Z resolution (default 1m voxels, configurable).
3. For each centerline point: carve sphere/ellipsoid (radius from archetype width, Z-axis scale from archetype curvature).
4. Apply 3D cellular automata, 26-neighbor rule, 2–3 passes. Organic wall smoothing without losing centerline topology.
5. Extract surface mesh: `skimage.measure.marching_cubes` → verts, faces, normals.
6. Boolean difference: `trimesh.boolean.difference(terrain_surface_mesh, cave_volume_mesh)` to carve the entrance opening.
7. Flip interior face normals so the player inside the cave sees walls.
8. Return `TrimeshResult` dataclass; caller writes to Blender via existing `_shared.mesh_bridge`.

**Integration:** `terrain_pipeline.py` `pass_caves` gains a call to `cave_voxel_carver.carve(...)` after archetype placement, before validation.

**Tests:** `tests/test_cave_voxel_carver.py` — voxel grid sizing, single sphere carve, multi-point path carve, CA smoothing regression, marching cubes extraction, boolean difference, normal orientation, edge cases (degenerate path, single-voxel path, path outside terrain bounds). Real-geometry only — no mocks. `test_substance_lint.py` must classify ≥ 80% as REAL.

**Visual verification:** Generate a cave with 3 archetypes, render contact sheet from 6 angles, confirm interior walls visible from inside and entrance visible from outside.

### Fix 2 — Volumetric Waterfall Mesh

**Bug (4/13 research #4, #5, #6, critical):** `terrain_waterfalls_volumetric.py:60` names and validates 7 functional objects but never instantiates them; `waterfall_pool_delta` is written but never applied; every waterfall ships as a flat plane despite the spec mandating 3D volume.

**Memory cross-reference:** user memory `feedback_waterfall_must_have_volume.md` — waterfalls MUST be 3D volumetric meshes (thick tapered prism, rounded front), never flat planes. This fix directly addresses that feedback.

**Implementation:**

Extend `src/vb_terrain/terrain_waterfalls_volumetric.py`:

1. Implement `build_volumetric_mesh(profile: WaterfallVolumetricProfile) -> Mesh`:
   - Thick tapered prism (wider at lip, narrower at plunge).
   - 48 verts/m density along fall height.
   - Rounded front face via parametric curve (not flat).
   - Hollow back (not player-facing).
2. Implement `create_functional_objects(chain: WaterfallChain) -> list[bpy.types.Object]` producing all 7:
   - `sheet_volume` — main curtain.
   - `foam_layer` — foam cap at lip and base.
   - `mist_volume` — particle-anchor volume around plunge.
   - `pool_basin` — carved pool geometry (uses `waterfall_pool_delta`).
   - `splash_ring` — impact ring at pool surface.
   - `plunge_column` — vertical shaft from lip to pool.
   - `downstream_jet` — outflow direction hint.
3. Apply `waterfall_pool_delta` to pool basin geometry (fix the dead-code write).

**Integration:** `environment.py:handle_generate_waterfall` (line 2202, in `vb_terrain/environment.py` after Phase 1) consumes the profile and instantiates the 7 objects per chain, grouped under a chain collection.

**Tests:** `tests/test_waterfall_volumetric.py` — profile→mesh conversion, vertex density validation, front-face curvature validation, all 7 objects spawned, pool delta applied and visible in geometry, chain collection hierarchy correct.

**Visual verification:** Generate a 3-drop waterfall chain, render contact sheet, confirm volume visible from side (not flat plane), foam + mist objects present, pool carved at base.

### Fix 3 — WaterNetwork → Mesh Bridge

**Bug (4/13 research #2, #8, and 6 documented disconnection points):** The `WaterNetwork` graph is computed but never reaches the mesh generators. Six specific breakage points.

**Implementation:** In `compose_map` (lives in architecture's `worldbuilding.py` after Phase 1 but calls `vb_terrain.WaterNetwork`):

1. Build `WaterNetwork` from heightmap **first**, before any water pass.
2. Thread the network instance into every downstream pass (fix each of the 6 breaks):
   - `pass_waterfalls(river_network=network, ...)` — replace `None`.
   - `wet_rock_mask(water_network=network, ...)` — replace `None`.
   - `pass_water_variants` now invokes its own `detect_rapids / detect_eddies / detect_pools / detect_meanders / detect_cascades / detect_confluences` against the network.
   - `handle_create_water` consumes tile contracts from `_water_network.py:394`.
   - Volumetric functional objects: covered by Fix 2.
   - `compose_map` passes the network into geometry stage, not just the mask stage.
3. Fix vertex-color flow encoding: R channel was erroneously storing shore-proximity. Reassign: R = flow_speed (0–1 normalized), G = flow_direction_x (−1..1 mapped to 0..1), B = flow_direction_z, A = foam_intensity. Document in new `src/vb_terrain/VERTEX_COLOR_ENCODING.md`.

**Tests:** `tests/test_water_network_bridge.py` — each of 6 disconnection points explicitly tested (spy that asserts network instance arrives); vertex-color encoding round-trip test; detector invocation counts match expected river topology; end-to-end: build small heightmap → compose_map → verify all 6 sites received the same network instance (identity check, not equality).

**Visual verification:** Generate a test map with a river+waterfall chain, render contact sheet, confirm shore proximity no longer corrupts R channel and that a shader sampling R shows flow-speed gradient (fastest at rapids, zero at pools).

### Phase 2 validation gates

| Gate | Command | Pass condition |
|---|---|---|
| P1. All Phase 1 gates still pass | run Phase 1 G1–G7 | all green |
| P2. New tests pass | `pytest tests/test_cave_voxel_carver.py tests/test_waterfall_volumetric.py tests/test_water_network_bridge.py` | all green |
| P3. Test substance | `python scripts/test_substance_lint.py tests/` | ≥ 50% REAL for new tests |
| P4. Honesty lint | `python scripts/honesty_lint.py src/vb_terrain/` | no divergence |
| P5. Visual cave | contact sheet | interior walls carved, entrance visible |
| P6. Visual waterfall | contact sheet | 3D volume, 7 functional objects, pool carved |
| P7. Visual water | contact sheet | flow-speed encoded in R channel |

---

## Quality Infrastructure Per Repo

Per the user's decision that terrain and architecture each get their own quality infra (not shared):

**Each domain repo owns:**
- Its own `contracts/{terrain,architecture}.yaml`.
- Its own `scripts/quality_lint.py` + `brief_agent.py` + `honesty_lint.py` + `test_substance_lint.py` — generalized from the toolkit's current versions to accept `--package-root` and `--contract` arguments.
- Its own `.github/workflows/ci.yml` running the above in CI.

**Toolkit repo owns:**
- `scripts/check_import_direction.py` — the cross-repo boundary enforcer. Run in toolkit's CI against all four installed repos.
- Cross-repo integration tests in `tests/integration/` that exercise the full stack (terrain → compose_map → architecture → Blender addon).

**Shared repo owns:**
- No domain quality infra. Each of its two packages (`vb_addon_shared`, `vb_code_reviewer`) has its own `pytest` + `ruff` in CI.

---

## Test Reorganization

Per the decision "you choose best practice here to keep tests accurate and functional":

- **Mirror the package layout.** Each repo's tests live inside the repo. Test discovery is local to that repo's `pyproject.toml`.
- **Keep conftest.py per-repo.** Fixtures scoped to what the repo actually needs.
- **Cross-repo integration tests stay in toolkit** (`Tools/mcp-toolkit/tests/integration/`) — they require all four repos installed and exercise end-to-end flows.
- **Shared test utilities** (if discovered during Phase 1 — e.g., Blender mock fixtures used by multiple repos) go into `veilbreakers-shared/packages/vb_addon_shared/testing/` and are importable as `from vb_addon_shared.testing import ...`.
- **Test naming unchanged.** `test_terrain_caves.py` stays `test_terrain_caves.py` — only its location moves.

---

## Git History Approach

Per the decision "you choose best practices":

- **`git filter-repo`** for extraction into new repos. Preserves per-file history end-to-end. `git blame` and `git log --follow` on any extracted file in the new repos shows the same authorship + commit timeline as the toolkit repo does today.
- **Plain `git rm`** in the toolkit to remove extracted files. Do not rewrite toolkit history. The files' history is already preserved in the new repos where they now live; rewriting toolkit history would invalidate every existing branch/tag/PR/clone.
- **Atomic commits per step** in each new repo. Phase 1 Steps 1–7 each produce one commit (or a small tight cluster). `git bisect` narrows any regression to one step.
- **Phase 2 commits per fix.** Fix 1 (cave voxels) is one coherent commit range. Fix 2 (waterfall volumes) another. Fix 3 (water bridge) another.
- **No `--force-push` after initial push.** Once the three new repos are pushed public, their history is append-only.

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Test count drifts during Phase 1 | Loses the invariant gate, can't prove no-behavior-change | Each extraction step is atomic commit; `pytest -q` diff after every step; if non-zero diff, revert that step and investigate |
| Circular dep resurfaces | Import error at addon load | `check_import_direction.py` CI gate blocks merges; addon preflight catches runtime too |
| Editable pip install fragility across machines | New dev can't run the toolkit | Document exact `pip install -e` commands in `docs/REPO_SETUP.md`; provide `scripts/bootstrap_dev.ps1` that runs all four installs |
| Blender's bundled Python can't find packages | Addon fails to load | Addon preflight check raises with clear remediation message naming the specific missing package |
| `git filter-repo` removes too much or too little | History in new repos is wrong or incomplete | Dry-run each filter-repo into a scratch directory first; diff the file set against the intended extraction manifest before cloning for real |
| 4/13 research bugs #1, #3, #7 etc. (non-critical but related) | Still present after Phase 2 | Explicitly scoped out; file as follow-up issues in `veilbreakers-terrain` repo |
| Visual verification regresses silently | Phase 2 tests pass but Blender output looks wrong | Each Phase 2 fix's definition-of-done includes a contact-sheet render committed to the terrain repo's `tests/visual_baselines/` folder |

---

## Success Criteria (whole spec)

1. Four repos exist, three new public on GitHub under Sharks820.
2. `Σ pytest -q` pass count across all four repos equals pre-split baseline `N`.
3. Addon loads in Blender with all four repos pip-installed; MCP servers respond to smoke tests.
4. `.mcp.json`'s `vb-review` points at `veilbreakers-shared` and returns valid analysis.
5. `check_import_direction.py` passes — no `vb_terrain ↔ vb_architecture` coupling.
6. Phase 2 fixes produce visibly correct output: cave with interior walls, waterfall with volume + 7 functional objects, water with correct flow-speed vertex color encoding.
7. No user memory feedback violated (volumetric waterfalls, 3D caves, visual verification loop all honored).

---

## Open Items Deferred to Follow-Up Specs

1. Break up `environment.py` (5453 lines) and `worldbuilding.py` (8070 lines).
2. 4/13 research Priorities 4–7: water flow animation shader, 5-layer terrain texturing shader, stitching-band blending, forests/clearings.
3. Split the ~86 unsorted flat handlers in the toolkit into further dedicated repos (e.g., `veilbreakers-animation`, `veilbreakers-character`, `veilbreakers-combat`).
4. PyPI publication of `vb-addon-shared`, `vb-code-reviewer`, `vb-terrain`, `vb-architecture`.
5. CI integration for addon zip build that bundles the sibling repos' `src/` trees.
6. Flesh out `contracts/architecture.yaml` with kit/grammar/settlement contracts.
7. Cross-repo integration test suite expansion in the toolkit.

---

## Appendix A: Complete File Extraction Manifest

### Going to `veilbreakers-shared/packages/vb_addon_shared/`

From `Tools/mcp-toolkit/blender_addon/handlers/`:
- `_context.py` → `context.py`
- `_mesh_bridge.py` → `mesh_bridge.py`
- `_shared_utils.py` → `shared_utils.py`
- `_action_compat.py` → `action_compat.py`
- `_scatter_engine.py` → `scatter_engine.py`

### Going to `veilbreakers-shared/packages/vb_code_reviewer/`

From `Tools/mcp-toolkit/src/veilbreakers_mcp/`:
- `vb_code_reviewer.py` → `reviewer.py`
- `vb_python_reviewer.py` → `python_reviewer.py`
- `_ast_analyzer.py` → `ast_analyzer.py`
- `_context_engine.py` → `context_engine.py`
- `_rules_python.py` → `rules_python.py`
- `_rules_csharp.py` → `rules_csharp.py`
- `_rules_csharp_core.py` → `rules_csharp_core.py`
- `_rules_csharp_unity.py` → `rules_csharp_unity.py`
- `_tool_runner.py` → `tool_runner.py`
- `_types.py` → `types.py`
- `review_server.py` → `review_server.py` (entry point `vb-review-mcp`)
- Matching tests: `tests/test_reviewer_*.py`, `tests/test_vb_code_reviewer_*.py`

### Going to `veilbreakers-terrain/src/vb_terrain/`

From `Tools/mcp-toolkit/blender_addon/handlers/`:
- Every `terrain_*.py` (100 files).
- Every `_terrain_*.py` (4 files: `_terrain_depth`, `_terrain_erosion`, `_terrain_noise`, `_terrain_world`).
- Every `_water_*.py` (2 files: `_water_network`, `_water_network_ext`).
- `_biome_grammar.py`.
- `environment.py` (whole 5453-line file).
- `environment_scatter.py`.
- `coastline.py`.
- `atmospheric_volumes.py`.
- Matching tests: `tests/test_terrain_*.py`, `tests/test_water_*.py`, `tests/test_cave*.py`, `tests/test_waterfall*.py`, `tests/test_erosion*.py`, `tests/test_environment_*.py` where environment-specific.

### Going to `veilbreakers-architecture/src/vb_architecture/`

From `Tools/mcp-toolkit/blender_addon/handlers/`:
- `_building_grammar.py`
- `_settlement_grammar.py`
- `_dungeon_gen.py`
- `building_interior_binding.py`
- `building_quality.py`
- `dungeon_themes.py`
- `modular_building_kit.py`
- `settlement_generator.py`
- `worldbuilding.py` (whole 8070-line file)
- `worldbuilding_layout.py`
- Matching tests.

### Staying in `veilbreakers-gamedev-toolkit`

From `Tools/mcp-toolkit/blender_addon/handlers/` (~86 flat files):
- Addon primitives: `scene.py`, `objects.py`, `viewport.py`, `materials.py`, `export.py`, `mesh.py`, `execute.py`, `prop_quality.py`.
- `addon_toolchain.py`.
- Animation (14): `animation.py`, `animation_abilities.py`, `animation_blob.py`, `animation_combat.py`, `animation_environment.py`, `animation_export.py`, `animation_gaits.py`, `animation_hover.py`, `animation_ik.py`, `animation_locomotion.py`, `animation_monster.py`, `animation_production.py`, `animation_social.py`, `animation_spellcast.py`.
- Armor/weapon/equipment: `armor_meshes.py`, `armor_sets.py`, `weapon_quality.py`, `equipment.py`, `equipment_fitting.py`, `class_equipment.py`, `clothing_system.py`, `legendary_weapons.py`, `enchantment_overlay.py`.
- Character: `_character_lod.py`, `_character_quality.py`, `character_advanced.py`, `character_skin_modifier.py`, `creature_anatomy.py`, `eye_mesh.py`, `facial_topology.py`, `hair_system.py`, `wrinkle_maps.py`.
- Combat/encounter: `_combat_timing.py`, `encounter_spaces.py`, `boss_presence.py`, `collision_generator.py`.
- VFX/lighting/atmospherics handled by toolkit: `decal_system.py`, `destruction_system.py`, `drivers.py`, `light_integration.py`, `loot_display.py`, `map_composer.py` (stays — coordinator of animation/props, not worldbuilding).
- Mesh/topology: `curves.py`, `geometry_nodes.py`, `lod_pipeline.py`, `text_objects.py`, `udim_support.py`, `uv.py`, `vertex_colors.py`, `vertex_paint_live.py`, `weathering.py`.
- Texture: `texture.py`, `texture_painting.py`, `texture_quality.py`.
- Vegetation (stays — general scatter, not terrain-specific): `vegetation_lsystem.py`, `vegetation_serializer.py`, `vegetation_system.py`.
- World: `world_map.py` (UI/2D world map, not terrain).
- Autonomy: `autonomous_loop.py`.
- MCP servers: all of `Tools/mcp-toolkit/src/veilbreakers_mcp/` except the reviewer files listed above.

(Final reconciliation during Phase 1 Step 1 dry-run will confirm exact counts.)

---

## Appendix B: New Dependencies (introduced by Phase 2)

| Package | Version | Purpose | Repo that declares it |
|---|---|---|---|
| `scikit-image` | `>=0.22` | `skimage.measure.marching_cubes` for cave mesh extraction | `veilbreakers-terrain` |
| `trimesh` | `>=4.0` | `trimesh.boolean.difference` for cave-into-terrain carving | `veilbreakers-terrain` |

Both are pure-Python-accessible wheels, no native-build friction on Windows + Blender's bundled Python.

---

**End of design.**
