# Agent Execution Quality Protocol — Terrain Generation Toolkit

**Scope:** Every AI agent (Claude Opus, Codex gpt-5.4, Gemini, GSD subagents)
that touches any `terrain_*.py` file, `_terrain_noise.py`, `_terrain_erosion.py`,
terrain tests, or the terrain pipeline in `blender_server.py`.

**Authority:** This protocol is mandatory. Agents that skip steps produce
regressions that cost 10x to fix downstream. No exceptions.

**Working directory for all commands:** `Tools/mcp-toolkit/`

---

## 1. PRE-EDIT PROTOCOL

Execute ALL of the following BEFORE making any terrain code change.

### 1.1 Run the pre-flight briefer

```bash
cd Tools/mcp-toolkit
python scripts/brief_agent.py
```

Read the output and note:
- `contract_bundles` — which bundles exist and their status
- `known_bugs` — bugs that may affect your work
- `sibling_passes` — all registered passes (avoid duplicating or conflicting)
- `orphan_deltas` — deltas not wired into the integrator

**Decision gate:** If your target file's bundle has `status: broken`, STOP.
Fix the broken state first or escalate (see section 5).

### 1.2 Identify channel contract

For every file you plan to edit, determine:

```bash
grep -n "requires_channels\|produces_channels\|consumes_channels" blender_addon/handlers/<target_file>.py
```

Document which channels the file reads and writes. Your edit MUST NOT:
- Remove a channel from `produces_channels` that another pass depends on
- Add a channel to `requires_channels` without verifying the producer pass runs first
- Write to `stack.height` directly (only the integrator pass may do this)

Cross-check against the Unity-ready channel table in `TERRAIN_AGENT_PROTOCOL.md` section 8.

### 1.3 Check existing test coverage

```bash
python -m pytest tests/ -q --co | grep -i "<module_name>"
```

If there are fewer than 3 test functions covering the module, you MUST write
tests as part of your edit (TDD preferred: write failing test first).

### 1.4 Read relevant FINDINGS entries

Before editing, search the audit findings for context:

```bash
grep -r "<file_or_feature_keyword>" .planning/terrain_audit_2026-04-11/
```

This prevents re-introducing fixed bugs or conflicting with planned work in
another phase.

### 1.5 Record the quality baseline

```bash
python scripts/quality_lint.py blender_addon/handlers/<target_file>.py 2>&1 | tail -5
python -m pytest tests/ -q --tb=no 2>&1 | tail -3
```

Write down:
- **LINT_BASELINE:** number of findings for the target file
- **TEST_BASELINE:** total passed / total collected

These numbers are your ceiling. Your edit must not increase them.

### 1.6 Pre-edit checklist (must be TRUE before proceeding)

- [ ] brief_agent.py output reviewed
- [ ] Channel contract of target file documented
- [ ] Test coverage checked (>= 3 tests exist, or you will write them)
- [ ] Relevant FINDINGS entries read
- [ ] LINT_BASELINE and TEST_BASELINE recorded

---

## 2. POST-EDIT PROTOCOL

Execute ALL of the following AFTER every terrain code change, BEFORE committing.

### 2.1 AST quality lint (L2)

```bash
python scripts/quality_lint.py blender_addon/handlers/<changed_files>
```

**Threshold:** Findings MUST be <= LINT_BASELINE from step 1.5.
If findings increased, fix them before proceeding.

For full handler scan (required before any commit):
```bash
python scripts/quality_lint.py blender_addon/handlers/
```
**Hard ceiling:** <= 16 findings total across all handlers.

### 2.2 Run relevant tests

```bash
python -m pytest tests/<relevant_test_files> -q --tb=short
```

**Threshold:** ALL relevant tests must pass. Zero tolerance for new failures.

Then run the full suite:
```bash
python -m pytest tests/ -q --tb=line
```

**Threshold:** Pass count >= TEST_BASELINE from step 1.5. No new failures.

### 2.3 Test substance audit (L5)

If you wrote or modified any test files:

```bash
python scripts/test_substance_lint.py tests/<changed_test_files>
```

**Threshold:** `real_ratio >= 0.50`

Every new test MUST satisfy the "would stub pass?" rule:
- Replace the function under test with `pass` / `return None` / `return {}`
- Your test MUST FAIL in that scenario
- If it would still pass, the test is SHALLOW or TAUTOLOGICAL — rewrite it

### 2.4 Import chain verification

```bash
python -c "from blender_addon.handlers.terrain_master_registrar import register_all_terrain_passes; print('OK')"
```

If this fails, your edit broke an import chain. Fix before proceeding.

### 2.5 Channel contract verification

For any pass you modified or created, verify the channel declarations match reality:

```bash
grep -n "stack.set\|stack.get" blender_addon/handlers/<changed_file>.py
```

Every `stack.set("X", ...)` call MUST have `"X"` listed in the pass's `produces_channels`.
Every `stack.get("X")` call MUST have `"X"` listed in the pass's `requires_channels`.

**Mismatch = hard reject.** The channel contract is the pipeline's type system.

### 2.6 Terrain statistics capture (when applicable)

If your edit changes height generation, erosion, or any geometry-producing pass,
capture statistics from the test pipeline:

```bash
python -m pytest tests/test_terrain_pipeline_smoke.py -q -s 2>&1 | grep -E "height_range|slope_|drainage|vertex_count"
```

Or from a dedicated stats test if one exists. Compare against known-good baselines:

| Metric | Acceptable range | Hard reject |
|---|---|---|
| Height range (meters) | 10-2000 for standard terrain | < 1 or > 10000 |
| Mean slope (degrees) | 5-45 | < 1 or > 70 |
| Slope std deviation | > 3 | < 0.5 (flat = broken) |
| Drainage connectivity | > 60% cells reachable | < 30% |
| Vertex count (256x256) | 50K-120K | > 500K |

If statistics deviate beyond these ranges, your edit likely introduced a math bug.

### 2.7 Code reviewer (for non-trivial changes)

For any change > 50 lines or any change to core pipeline files:

```bash
PYTHONPATH=src python src/veilbreakers_mcp/vb_code_reviewer.py blender_addon/handlers/<changed_files> --scope advisory --profile blender
```

Address any P0/P1 findings before committing.

### 2.8 Post-edit checklist (must be TRUE before committing)

- [ ] quality_lint findings <= LINT_BASELINE (and <= 16 total handlers)
- [ ] All relevant tests pass
- [ ] Full suite pass count >= TEST_BASELINE
- [ ] test_substance_lint real_ratio >= 0.50 (if tests changed)
- [ ] Import chain verification passed
- [ ] Channel contract: stack.set/get matches produces/requires declarations
- [ ] Terrain statistics within acceptable range (if geometry changed)
- [ ] Code reviewer findings addressed (if change > 50 lines)

---

## 3. VISUAL VERIFICATION PROTOCOL

### 3.1 When visual verification is required

Visual verification is REQUIRED for edits that change:
- Height generation or erosion algorithms
- Cliff, cave, waterfall, or any geometry-producing pass
- Material assignment or texture layering
- Scatter placement (trees, rocks, detail objects)
- Mesh builder output (vertex positions, normals, UV layout)
- LOD generation or export geometry

Visual verification is NOT required for:
- Test-only changes
- Documentation or config changes
- Pure refactoring that does not change output (verified by determinism test)
- Channel wiring fixes (verified by pipeline tests)

### 3.2 How to verify visually

**IMPORTANT:** Only capture viewport screenshots when the user explicitly requests
visual verification, or when the task acceptance criteria specifically require it.
Do not auto-screenshot after every edit.

When visual verification is triggered:

1. **Generate the terrain** in Blender using the test pipeline or MCP tool:
   ```
   asset_pipeline action=compose_terrain_node with seed=42 (deterministic)
   ```

2. **Capture a contact sheet** (4-angle view):
   ```
   blender_viewport action=contact_sheet max_size=500
   ```

3. **Viewport settings for QA:**
   - Shading: Material Preview (not Solid — shows material zones)
   - Overlays: Wireframe ON at 0.3 opacity (shows mesh density)
   - Camera: Orthographic top-down + 3/4 perspective (two views minimum)
   - For height/slope verification: use vertex color display of the height channel

4. **What to check:**
   - No visible cube/box fallback geometry
   - Cliff faces have anatomy (lip, face, ledges, talus) not just steep slopes
   - Water features are 3D volumetric (not flat planes)
   - Material transitions are gradual (no hard-edge zoning)
   - Terrain has visible erosion channels and ridges (not smooth noise)
   - No floating geometry or Z-fighting
   - Scale looks correct (trees/objects proportional to terrain)

### 3.3 Pass / fail criteria

| Result | Condition |
|---|---|
| **PASS** | All geometry looks intentional, no fallback shapes, materials transition smoothly, erosion visible |
| **CONDITIONAL PASS** | Minor visual issues noted but not blocking (e.g., slightly aggressive erosion in one corner) — document and continue |
| **FAIL** | Cube/box fallbacks visible, terrain is flat/featureless, materials are single-color, geometry clearly broken, Z-fighting present |

On FAIL: revert the change (see section 4) and diagnose the root cause before reattempting.

---

## 4. ROLLBACK PROTOCOL

### 4.1 When to revert

Revert IMMEDIATELY (do not attempt to fix forward) when:

| Trigger | Action |
|---|---|
| quality_lint findings increased above LINT_BASELINE | `git checkout -- <files>` |
| Any test that previously passed now fails | `git checkout -- <files>` |
| Import chain (`register_all_terrain_passes`) broken | `git checkout -- <files>` |
| Terrain statistics outside hard-reject bounds | `git checkout -- <files>` |
| Visual verification FAIL (cube fallbacks, flat terrain) | `git checkout -- <files>` |

### 4.2 When to fix forward

Fix forward (do not revert) when:

- quality_lint findings decreased or stayed the same, but a NEW pattern type appeared
- Tests pass but test_substance_lint dropped below 0.50 (add more real tests)
- Code reviewer found P1 issues (address them in the same commit)

### 4.3 Git rollback procedure

**Single-file revert (preferred):**
```bash
git diff blender_addon/handlers/<file>.py     # review what changed
git checkout -- blender_addon/handlers/<file>.py   # revert
```

**Multi-file revert to last known-good state:**
```bash
git stash                    # save work in progress
git stash show -p            # review what was stashed
# Run tests to confirm clean state
python -m pytest tests/ -q --tb=no
# If clean: examine stash, extract good parts, discard bad
git stash pop                # restore and fix selectively
# OR
git stash drop               # abandon if unsalvageable
```

**Full commit revert (if already committed):**
```bash
git log --oneline -5         # find the bad commit
git revert <commit_hash>     # create a revert commit (safe, preserves history)
```

**NEVER use `git reset --hard` unless explicitly instructed by the user.**

### 4.4 Post-rollback verification

After ANY rollback, re-run the full gate:

```bash
python scripts/quality_lint.py blender_addon/handlers/
python -m pytest tests/ -q --tb=line
python -c "from blender_addon.handlers.terrain_master_registrar import register_all_terrain_passes; print('OK')"
```

All three must pass before resuming work.

---

## 5. QUALITY ESCALATION

### 5.1 Escalate to human review when:

| Situation | Escalation action |
|---|---|
| Visual quality ambiguous (not clearly pass or fail) | Capture contact sheet, describe what you see, ask user to judge |
| Two valid architectural approaches conflict | Document both approaches with trade-offs, let user decide |
| Edit would change `TerrainPassController` core logic | Flag with "ARCHITECTURE CHANGE" label, describe impact on all passes |
| Edit affects > 5 terrain files simultaneously | Describe the cross-cutting change, risk assessment, rollback plan |
| Channel contract change removes or renames a channel | Document all consumers/producers affected, get explicit approval |
| Test suite has > 3 pre-existing failures you cannot explain | Do not add more. List the failures and escalate. |
| brief_agent.py shows `known_bugs` that interact with your change | Call out the interaction explicitly, propose fix order |
| quality_lint findings at 16 (ceiling) and your change needs one more | Propose which existing finding to fix to make room |

### 5.2 Escalation format

When escalating, provide:

```
ESCALATION: <one-line summary>
CONTEXT: <what you were trying to do>
BLOCKER: <what prevented completion>
OPTIONS:
  A) <option with trade-offs>
  B) <option with trade-offs>
RECOMMENDATION: <which option and why>
RISK IF IGNORED: <what breaks if this is not addressed>
```

### 5.3 Do NOT escalate when:

- Tests fail and the cause is obvious (fix it)
- quality_lint catches your own new code (fix it)
- A file you need to edit has existing lint warnings (fix the warnings as part of your change)
- The code reviewer flags style issues (fix them)

---

## 6. MULTI-AGENT COORDINATION RULES

When multiple agents work in parallel on terrain code:

### 6.1 File ownership

- Each agent gets EXCLUSIVE write access to assigned files
- Read access to ALL files is unrestricted
- If you need a change in a file you do not own, emit:
  ```
  DEPENDENCY: <file> needs <change description>
  ```
  and STOP that subtask. The orchestrator will route it.

### 6.2 Verification gate (after all parallel agents complete)

The orchestrator runs a merge verification BEFORE any push:

```bash
# 1. Merge conflict check
git merge --no-commit --no-ff <agent_branch>   # dry run

# 2. Import chain
python -c "from blender_addon.handlers.terrain_master_registrar import register_all_terrain_passes; print('OK')"

# 3. Full test suite
python -m pytest tests/ -q --tb=line --timeout=300

# 4. Quality lint
python scripts/quality_lint.py blender_addon/handlers/

# 5. Test substance
python scripts/test_substance_lint.py tests/

# 6. Regression check
# Test count must be >= previous phase baseline
```

If ANY check fails, identify which agent's changes caused it, reject that
agent's commit, and re-dispatch.

### 6.3 Agent naming convention

```
Phase-XX-Agent-Y  (e.g., Phase-52-Agent-A)
```

Each agent's prompt MUST include:
- `YOUR FILES (exclusive write):` [list]
- `READ-ONLY FILES (do not modify):` [everything else]
- `LINT_BASELINE:` [number from pre-phase scan]
- `TEST_BASELINE:` [number from pre-phase scan]

---

## 7. QUICK REFERENCE — COMMAND CHEAT SHEET

All commands assume `cd Tools/mcp-toolkit` as working directory.

```bash
# PRE-EDIT
python scripts/brief_agent.py                                    # L1: contract state
grep -n "requires_channels\|produces_channels" handlers/<f>.py   # channel contract
python -m pytest tests/ -q --co | grep -c test_                  # test count baseline
python scripts/quality_lint.py handlers/<f>.py                   # lint baseline

# POST-EDIT
python scripts/quality_lint.py handlers/<changed_files>          # L2: <= baseline
python scripts/quality_lint.py blender_addon/handlers/           # L2: <= 16 total
python -m pytest tests/<relevant> -q --tb=short                  # targeted tests
python -m pytest tests/ -q --tb=line                             # full suite
python scripts/test_substance_lint.py tests/<changed>            # L5: >= 0.50
python -c "from blender_addon.handlers.terrain_master_registrar import register_all_terrain_passes; print('OK')"

# REVIEW (changes > 50 lines)
PYTHONPATH=src python src/veilbreakers_mcp/vb_code_reviewer.py handlers/<f> --scope advisory --profile blender

# ROLLBACK
git checkout -- handlers/<f>.py                                  # single file
git stash                                                        # save WIP
git revert <hash>                                                # undo commit

# VISUAL (only when user requests or acceptance criteria require it)
# Use MCP: asset_pipeline compose_terrain_node seed=42
# Use MCP: blender_viewport contact_sheet max_size=500
```

---

## 8. DECISION TREE — WHAT TO DO WHEN THINGS GO WRONG

```
Edit made
  |
  v
Run quality_lint
  |-- Findings <= baseline --> continue
  |-- Findings > baseline  --> Can you fix the new findings?
  |     |-- Yes --> fix them, re-run
  |     |-- No  --> REVERT (section 4.1)
  |
Run tests
  |-- All pass, count >= baseline --> continue
  |-- New failure --> Is the cause in YOUR change?
  |     |-- Yes --> fix it, re-run
  |     |-- No  --> Is it a pre-existing failure? 
  |           |-- Yes (documented) --> continue, note it
  |           |-- No (unknown)     --> ESCALATE (section 5.1)
  |-- Pass count dropped --> Did you DELETE tests?
        |-- Intentionally (removing bug-ratifying tests) --> OK, document
        |-- Accidentally --> REVERT
  |
Run import chain
  |-- OK    --> continue
  |-- FAIL  --> REVERT immediately, import chains must never break
  |
Run test_substance_lint (if tests changed)
  |-- real_ratio >= 0.50 --> continue
  |-- real_ratio < 0.50  --> Add more REAL tests, do not commit shallow tests
  |
Channel contract check
  |-- Matches --> continue
  |-- Mismatch --> Fix declarations to match actual stack.set/get usage
  |
All gates passed --> COMMIT
```

---

_This protocol supplements `TERRAIN_AGENT_PROTOCOL.md` (pass-writing rules)
and `CLAUDE.md` (quality infrastructure). Together they form the complete
terrain development contract._

_Last updated: 2026-04-12_
