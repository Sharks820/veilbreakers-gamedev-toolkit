# Codex Work Scope: Quality Infrastructure + Reviewer Ship Prep

> **Generated**: 2026-04-09 by Opus after 4-agent FP audit, architecture audit, and terrain audit
> **Branch**: `feature/terrain-world-foundation`
> **Test baseline**: 20,824 pass / 2 skip / 0 fail
> **Reviewer baseline**: Python advisory 16 findings, C# advisory 10 findings

---

## CRITICAL CONTEXT — READ BEFORE ANY WORK

### What was already done this session (UNCOMMITTED, in working tree)

These changes exist in the working tree and must be COMMITTED first before starting new work:

1. **Phase 0 — 13 bug-ratifying tests deleted** across 7 files:
   - `test_terrain_advanced.py` — removed `test_result_clamped_0_1`
   - `test_terrain_erosion.py` — removed `test_does_not_create_values_outside_bounds`
   - `test_terrain_flatten.py` — removed `test_flatten_output_clipped`
   - `test_terrain_caves.py` — removed `test_carve_cave_volume_returns_delta_without_mutation`
   - `test_aaa_final_verification.py` — removed `test_all_phase39_test_count_80_plus`
   - `test_vegetation_system.py` — removed `test_water_level_filtering`
   - `test_armor_meshes.py` — removed 7 `test_*_invalid_style_fallback` methods

2. **Phase 1 — 4 new reviewer rules** in `_rules_python.py`:
   - PY-COR-16 (discarded `_name = func()`)
   - PY-COR-17 (frozen dataclass + mutable field)
   - PY-COR-18 (validator self-rollback)
   - PY-COR-19 (fallback-before-primary)
   - Plus 20 corpus fixtures in `tests/fixtures/reviewer_known_bugs.py`

3. **Reviewer FP overhaul** — multiple files:
   - `_rules_python.py`: PY-RES-03 deleted (48 FPs), PY-COR-09 deleted (7 FPs), PY-COR-10/12 tightened, BLE-02 demoted, BLE-04 anti-pattern fixed, PY-SEC-05 noqa added
   - `vb_code_reviewer.py`: RUFF scope-gate added to `_merge_tool_finding`, F821 added to `_RUFF_HEURISTIC_CODES` then removed (stays in HARD_BUG)
   - `test_reviewer_precision.py`: BLE-02 test updated to strict scope

4. **Codex terrain fixes** (also uncommitted):
   - `environment.py`: Optional import (cosmetic/tooling)
   - `terrain_materials.py`: `all_keys` → `mat_keys` (REAL NameError fix)
   - `vegetation_system.py`: `_setup_billboard_lod` import (REAL NameError fix)
   - `review_server.py`: anti-speculation prompt + JSON validation
   - `_tool_runner.py`: improved `_map_ruff_severity` granularity

### Step 0: Commit all uncommitted work

```bash
cd Tools/mcp-toolkit
git add \
  tests/test_terrain_advanced.py tests/test_terrain_erosion.py \
  tests/test_terrain_flatten.py tests/test_terrain_caves.py \
  tests/test_aaa_final_verification.py tests/test_vegetation_system.py \
  tests/test_armor_meshes.py \
  src/veilbreakers_mcp/_rules_python.py \
  tests/fixtures/reviewer_known_bugs.py \
  src/veilbreakers_mcp/vb_code_reviewer.py \
  tests/test_reviewer_precision.py \
  blender_addon/handlers/environment.py \
  blender_addon/handlers/terrain_materials.py \
  blender_addon/handlers/vegetation_system.py \
  src/veilbreakers_mcp/review_server.py \
  src/veilbreakers_mcp/_tool_runner.py \
  tests/test_review_server.py tests/test_vb_code_reviewer.py \
  tests/test_addon_toolchain.py tests/test_terrain_assets.py \
  tests/test_terrain_ecosystem.py tests/test_terrain_iteration.py \
  tests/test_terrain_master_registrar.py tests/test_terrain_validation.py \
  tests/test_terrain_water_vegetation_depth.py \
  blender_addon/handlers/addon_toolchain.py \
  blender_addon/handlers/terrain_assets.py \
  blender_addon/handlers/terrain_bundle_j.py \
  blender_addon/handlers/terrain_pass_dag.py \
  blender_addon/handlers/terrain_unity_export.py \
  blender_addon/handlers/terrain_validation.py \
  blender_addon/handlers/terrain_vegetation_depth.py

git commit -m "fix(quality): Phase 0+1 quality infra + reviewer FP overhaul + terrain fixes

- Delete 13 bug-ratifying tests that locked bugs as features
- Add PY-COR-16/17/18/19 reviewer rules + 20 corpus fixtures
- Reviewer FP overhaul: 508→16 findings (97% noise reduction)
  - Delete PY-RES-03 (48 FPs, 0% precision on max() zero-guards)
  - Delete PY-COR-09 (7 FPs, 0% precision on json.load)
  - Tighten PY-COR-12 guard (4 suppression patterns for silent swallow)
  - Fix RUFF scope-gate leak in _merge_tool_finding
  - Demote BLE-02 to heuristic (85% FP rate)
  - Fix BLE-04 anti-pattern regex (.use_nodes read-check)
- Fix terrain_materials.py NameError (all_keys→mat_keys)
- Fix vegetation_system.py NameError (_setup_billboard_lod import)
- Tighten review_server.py prompts against speculation"
```

Run `python -m pytest tests/ -q` after commit to confirm 20,824 pass.

---

## BLOCK A: Quality Infrastructure (Phases 2-10)

These phases build the 7-layer defense-in-depth system designed after the terrain audit found 31 P0 bugs that 20,816 tests ratified instead of blocking.

### A1: Phase 2 — Terrain Contract YAML (L0)

**Goal**: Machine-readable source of truth for terrain pipeline contracts.

**Files to create**:
- `.planning/contracts/terrain.yaml`

**What to include per bundle (A through R)**:
```yaml
bundle_a:
  name: "Foundation"
  status: "complete"  # honest, not stamped
  passes:
    - name: "pass_terrain_foundation"
      produces_channels: ["height", "moisture", "temperature"]
      mutates: ["stack.height"]
      registered_in: "terrain_master_registrar.py"
      entry_point: "blender_addon/handlers/terrain_foundation.py:pass_terrain_foundation"
  functions:
    - name: "generate_heightmap"
      file: "blender_addon/handlers/_terrain_noise.py"
      returns: "np.ndarray"
      shape: "[resolution, resolution]"
      range: "world_units"  # NOT 0-1 normalized
```

**Source of truth**: Read `docs/terrain_ultra_implementation_plan_2026-04-08.md` (5157 lines) and cross-reference actual code in `blender_addon/handlers/terrain_*.py`.

**Acceptance**: Every claimed function exists (grep confirms), every `produces_channels` entry matches what the code actually writes.

### A2: Phase 3 — L2 Stub/Orphan AST Lint

**Goal**: Block stub-pass, orphan-delta, and other structural bugs at edit time.

**File to create**: `scripts/quality_lint.py` (~600 LOC)

**Patterns to detect**:
| Pattern | ID | Description |
|---|---|---|
| STUB-PASS | L2-01 | Registered pass function body is `pass`/`return None`/single-line |
| ORPHAN-DELTA | L2-02 | `_name = func()` where name starts with `_` and is never read (same as PY-COR-16 but AST-based) |
| FROZEN-MUTABLE | L2-03 | `@dataclass(frozen=True)` with Dict/List/Set field |
| SILENT-SWALLOW | L2-04 | `except Exception: pass` without intent comment |
| BARE-EXCEPT | L2-05 | `except:` (no type) |
| CUBE-FALLBACK | L2-06 | `_make_box(0,0,0,1,1,1)` or similar default-geometry return in generator |
| REGISTRAR-INCOMPLETE | L2-07 | `register_all_terrain_passes` doesn't cover all bundles in contract YAML |
| WRONG-ARITY-CALL | L2-08 | Function called with wrong number of positional args (AST inspect) |

**Implementation**: Use Python `ast` module. Parse each file, walk the AST, check patterns. Exit code 1 if any found.

**Test**: `tests/test_quality_lint.py` with fixture files that trigger each pattern.

### A3: Phase 4 — L4 Honesty Linter

**Goal**: Cross-check Appendix D / contract YAML against real code.

**File to create**: `scripts/honesty_lint.py` (~300 LOC)

**What it checks**:
1. Every `[x]` checkbox in plan markdown → function exists with >5 LOC body
2. Every `Status: COMPLETE` header → all sub-items checked
3. Contract YAML `status: complete` → all functions exist and are non-stub

**Source files to scan**:
- `docs/terrain_ultra_implementation_plan_2026-04-08.md` (Appendix D at line 3331)
- `.planning/contracts/terrain.yaml` (from Phase 2)
- `blender_addon/handlers/terrain_*.py`

### A4: Phase 5 — L3 Contract Test Generator + 13 Barrier Classes

**Goal**: Auto-generate tests from contract YAML. Each barrier class catches one pathology.

**Files to create**:
- `scripts/regen_contract_tests.py` (~400 LOC)
- `tests/contract/test_terrain_contracts.py` (auto-generated, committed)
- `tests/barriers/test_barrier_*.py` (13 files, one per barrier)

**The 13 barrier test classes** (each gets its own test file):

1. **no-stub-pass** — every registered pass mutates >=1 `produces_channel`
2. **delta-applied** — AST scan for `_delta = X` patterns where delta is never applied
3. **frozen-dataclass-hashable** — every `@dataclass(frozen=True)` class is `hash()`-able
4. **validator-no-self-rollback** — `validate_*` methods don't call `.rollback()`
5. **registrar-completeness** — `register_all_terrain_passes(strict=True)` covers every bundle
6. **mcp-tool-roundtrip** — every MCP action dispatches against a smoke fixture
7. **validation-full-runs** — at least one test runs `pass_validation_full` E2E
8. **manifest-schema-roundtrip** — `export_unity_manifest` validates against `validate_bit_depth_contract`
9. **axis-convention-on-export** — Unity export has Y-up or explicit swap
10. **advertised-detector-wired** — helpers in `__all__` reachable from registered pass
11. **honesty-roundtrip** — every `[x]` claim → function with >5 LOC body
12. **generator-not-stub** — mesh generators output != `_make_box(0,0,0,1,1,1)`
13. **builder-bsdf-wired** — material builders wire BSDF inputs to non-default sources

**Test substance bar**: Every barrier test MUST fail if you replace the target function body with `pass`. Verify this during development.

### A5: Phase 6 — L6 Full Integration Gate

**Goal**: Single test that runs the full terrain pipeline and catches >=12 of the 31 P0 bugs.

**File to create**: `tests/integration/test_full_terrain_pipeline.py` (~200 LOC)

**What it does**:
1. Create a 64x64 TerrainMaskStack
2. Run `register_all_terrain_passes(strict=True)`
3. Execute bundles A→D in order (foundation, cliffs, waterfalls, validation)
4. Assert: `stack.height` was mutated (not all zeros)
5. Assert: waterfall deltas were applied (not zero)
6. Assert: cave deltas were applied (not zero)
7. Assert: validation passes without rollback
8. Assert: Unity export produces Y-up or explicit swap
9. Assert: manifest schema roundtrips

### A6: Phase 7 — L5 Test Substance Auditor

**Goal**: Per-test classification (REAL/SHALLOW/TAUTOLOGICAL/SNAPSHOT) with CI gate.

**File to create**: `scripts/test_substance_lint.py` (~400 LOC)

**Classification logic**:
- **REAL**: Test fails if function body replaced with `pass`/`return None`/`return _make_box(0,0,0,1,1,1)`
- **SHALLOW**: Test only asserts `is not None`, `len > 0`, `isinstance`, type checks
- **TAUTOLOGICAL**: Test asserts something that's always true regardless of input
- **SNAPSHOT**: Test only compares to a saved snapshot, no behavioral assertion

**CI gate**: `real_ratio >= 0.5` or fail. Current ratio is ~38% — the barrier classes from Phase 5 will push it above 50%.

### A7: Phase 8 — L1 Pre-flight Briefer

**Goal**: Inject TRUE state into every agent before it edits terrain code.

**Files to create**:
- `scripts/brief_agent.py` (~200 LOC)

**What it outputs** (JSON to stdout):
```json
{
  "contract": { "bundle_a": { "status": "complete", "passes": [...] } },
  "known_bugs": [ { "id": "P0-008", "file": "terrain_caves.py:821", "desc": "discarded delta" } ],
  "sibling_passes": [ "pass_terrain_foundation", "pass_cliffs", ... ],
  "orphan_deltas": [ "terrain_caves.py:821", "terrain_caves.py:831" ]
}
```

### A8: Phase 9 — CLAUDE.md + GSD Wiring + Hooks

**Goal**: Wire all quality layers into the development workflow.

**Changes**:
1. Add to CLAUDE.md:
   - "Before EVERY commit, run `python scripts/quality_lint.py blender_addon/handlers/`"
   - "Before touching terrain_*.py, run `python scripts/brief_agent.py`"
   - "After writing tests, run `python scripts/test_substance_lint.py tests/`"

2. Add to `.claude/settings.json` hooks:
   - PostToolUse Edit/Write on `terrain_*.py` → `python scripts/quality_lint.py`
   - PostToolUse Edit/Write on `tests/test_*.py` → `python scripts/test_substance_lint.py` (warn-only)

### A9: Phase 10 — Headless Blender Integration Gates

**Goal**: ~30 behavioral tests that run in headless Blender.

**File to create**: `tests/integration/test_blender_behavioral.py`

**Requires**: Blender in PATH with `--background` mode. Tests use `bpy` directly.

**What to test**:
- Each registered terrain pass actually mutates the mesh in Blender
- Material builders create valid node trees
- Export produces valid FBX/glTF

**Note**: This phase can be deferred if Blender is not available in CI. Mark as optional.

---

## BLOCK B: Reviewer Ship Prep (General Python + C#)

These changes make the reviewer usable for ALL Python and C# projects, not just VeilBreakers.

### B1: Fix `_is_production_code_path` (HARD BLOCKER)

**File**: `src/veilbreakers_mcp/vb_code_reviewer.py`

**Problem**: Currently only recognizes `src/veilbreakers_mcp/`, `blender_addon/`, `Assets/` as production code. Non-VB repos scan ZERO files in production scope.

**Fix**: In `general` profile mode, treat ALL non-test/non-temp files as production. Keep VB-specific paths for `--profile blender` and `--profile unity`.

```python
def _is_production_code_path(filepath: str, profile: str = "general") -> bool:
    if profile == "general":
        return not _is_test_path(filepath) and not _is_temp_path(filepath)
    # VB-specific paths for blender/unity profiles
    ...
```

### B2: Split C# Rules — Core vs Unity Profile

**Current**: `_rules_csharp.py` has 186 rules, 151 are Unity-specific.

**Action**:
1. Create `_rules_csharp_core.py` with the 35 general-purpose rules:
   - SEC-01/02/06/07/08, SAVE-01
   - ASYNC-01/02/03, BUG-11/49/64/65/68
   - QUAL-01 through QUAL-17
   - PERF-23/26/29
   - ITER-01, TASK-01
2. Create `_rules_csharp_unity.py` with the remaining 151 rules + all 14 DEEP_CHECKS + `CSharpLineClassifier.HotPath` machinery
3. In `vb_code_reviewer.py`, load rules based on `--profile` flag

### B3: Add `--profile` CLI Flag

**File**: `src/veilbreakers_mcp/vb_code_reviewer.py`

**Add**:
```
--profile {general,unity,blender,all}  (default: general)
```

Rule loading logic:
- `general`: Python core + C# core only (no BLE-*, no UNITY-*, no GAME-*)
- `unity`: general + `_rules_csharp_unity.py`
- `blender`: general + BLE-01..04
- `all`: everything (current behavior)

### B4: Rename `VB-IGNORE` → `REVIEW-IGNORE`

**Find-and-replace** across all rule files:
- `_rules_python.py`: ~50 occurrences
- `_rules_csharp.py`: ~186 occurrences
- `vb_code_reviewer.py`: ~10 occurrences
- Keep backward compat: also match `VB-IGNORE` as alias for 1 release cycle

### B5: Rename `Category.Unity` → `Category.Framework`

**File**: `src/veilbreakers_mcp/_types.py`

Change `Unity = 4` to `Framework = 4`. Update all references.

### B6: Fix Path Display in Human Report

**File**: `src/veilbreakers_mcp/vb_code_reviewer.py`

In `_print_human_report`, remove VB-specific path shortening (`veilbreakers_mcp/`, `Assets/`). Use generic relative-to-scan-root.

### B7: Add General Python Rules (~15 rules)

**File**: `src/veilbreakers_mcp/_rules_python.py`

Add these missing categories with >=2 rules each:

| Category | Rules to add |
|---|---|
| OWASP Web | `PY-SEC-08` path traversal (`../` in user input), `PY-SEC-09` SSRF (`requests.get(user_url)`), `PY-SEC-10` template injection (`render_template_string(user_input)`) |
| Concurrency | `PY-COR-20` `threading.Lock` held across `await`, `PY-COR-21` shared mutable global without lock, `PY-COR-22` `asyncio.gather` without `return_exceptions` |
| Logging | `PY-PERF-04` f-string in `logger.error(f"...")` (formats even when disabled) |
| Resource | `PY-RES-08` `subprocess.Popen` without `communicate()` (zombie process), `PY-RES-09` `requests.get` without timeout |
| Type safety | `PY-COR-23` `Optional` return without caller None check within 5 lines |

Each rule needs:
- Pattern regex + anti_patterns + guard function
- At least 2 positive fixtures in `tests/fixtures/reviewer_known_bugs.py`
- Scan against real codebase to verify 0 FPs before shipping

### B8: Add General C# Rules (~15 rules)

**File**: `src/veilbreakers_mcp/_rules_csharp_core.py` (new file from B2)

| Category | Rules to add |
|---|---|
| Dispose | `CS-COR-01` `HttpClient` in `using` block (should be singleton/IHttpClientFactory), `CS-COR-02` `Stream` without async dispose |
| Null safety | `CS-COR-03` `!` (null-forgiving) without justification comment, `CS-COR-04` `?.` chain producing null silently |
| LINQ | `CS-PERF-01` `.ToList()` inside loop (materializes repeatedly), `CS-PERF-02` `.Where().Count()` (use `.Count(predicate)`) |
| Async | `CS-COR-05` `lock` inside `async` method (blocks thread pool), `CS-COR-06` `.Result` or `.Wait()` on hot path |
| DI | `CS-COR-07` captive dependency (scoped service in singleton) |
| Security | `CS-SEC-01` SQL string concatenation in EF raw query |

### B9: Add `--stdin` Support

**File**: `src/veilbreakers_mcp/vb_code_reviewer.py`

Add `--stdin` flag that reads file content from stdin with `--lang py|cs` to specify language. Enables: `cat file.py | vb-review --stdin --lang py`

### B10: README with Per-Rule Precision Table

**File**: `Tools/mcp-toolkit/docs/REVIEWER_RULES.md`

Auto-generate from rule definitions:
```markdown
| Rule ID | Severity | Layer | Description | Precision | Profile |
|---------|----------|-------|-------------|-----------|---------|
| PY-SEC-01 | CRITICAL | hard | eval() usage | 100% | core |
| PY-COR-16 | CRITICAL | semantic | Discarded return value | 100% | core |
...
```

---

## BLOCK C: Unity Quality Twins

### C1: L2 C# Stub/Orphan Roslyn Lint

Detect empty `Update()`/`Start()`, swallow-catch, generated scripts that never execute, MonoBehaviours never added to any scene. Use tree-sitter-c-sharp since Roslyn requires .NET SDK.

### C2: L5 C# Test Substance Auditor

EditMode/PlayMode test classifier: REAL / SHALLOW / TAUTOLOGICAL / SNAPSHOT. Detect `Assert.IsNotNull`-only, `Assert.AreEqual` on primitives, prefab-instantiation without behavior assertion.

### C3: L6 PlayMode Integration Gate

Single PlayMode test per MCP-generated subsystem (VFX, Audio, UI, Gameplay, World) that enters play mode, spawns the generated prefab, and asserts behavioral mutation.

### C4: 85% Pathology-Coverage Gate

Per barrier class: build a pathology corpus (real audit bugs + mutmut mutants for Python). Barrier class must catch >=85% of its corpus or CI fails.

---

## BLOCK D: Ship-Critical Gaps (found during ultrathink review)

These were missing from the original scope. Each is required for either internal quality or external shippability.

### D1: Diff-Only Scanning Mode (`--diff`)

**Problem**: The reviewer scans whole directories. For agent and CI workflows, scanning only changed lines saves 90%+ of time and tokens.

**File**: `src/veilbreakers_mcp/vb_code_reviewer.py`

**Add**: `--diff` flag that accepts a unified diff (from `git diff` or stdin) and only runs rules against changed/added lines. Findings on untouched lines are suppressed. This is how agents should invoke the reviewer before every commit.

**Implementation**: Parse unified diff to extract (file, line_range) pairs. When scanning, only emit findings where `issue.line` falls within a changed range. Reuse existing `scan_python_file`/`scan_csharp_file` but filter output.

### D2: Auto-Fix Suggestions as Patches

**Problem**: The `fix` field on each rule is a text description ("Replace with X"). For agent consumption, returning an actual diff/patch is 10x more useful — agents can apply fixes directly.

**File**: `src/veilbreakers_mcp/_rules_python.py`, `_rules_csharp_core.py`

**Add**: Optional `auto_fix` callable on each Rule that takes `(line, all_lines, idx)` and returns `(old_text, new_text)` or None. Start with the 10 highest-confidence rules where the fix is mechanical:
- PY-COR-01: `def f(x=[])` → `def f(x=None):\n    if x is None: x = []`
- PY-COR-03: `== None` → `is None`
- PY-COR-10: `== 0.5` → `math.isclose(x, 0.5)`
- PY-SEC-01: `eval(x)` → `ast.literal_eval(x)`
- PY-STY-01: `os.path.join(a, b)` → `Path(a) / b`

**Output**: When `--fix` flag is passed, emit patches instead of findings. When `--fix --apply` is passed, apply them in-place (with backup).

### D3: Reviewer Self-Test (eat your own dogfood)

**File**: `tests/test_reviewer_self_scan.py`

**What it does**: Run the reviewer on its own source code (`src/veilbreakers_mcp/`) in production scope. Assert zero CRITICAL/HIGH findings. This catches the embarrassing case where the reviewer flags its own patterns as bugs.

```python
def test_reviewer_does_not_flag_itself():
    report = scan_directory("src/veilbreakers_mcp/", review_scope="production")
    critical_high = [i for i in report["issues"] if i["severity"] in ("CRITICAL", "HIGH")]
    assert len(critical_high) == 0, f"Reviewer flags itself: {critical_high}"
```

### D4: Truth Set as Executable Test Suite

**Problem**: B10 generates a documentation table but doesn't create a runnable precision test. Without an automated precision gate, precision will regress silently.

**Files to create**:
- `tests/truth_set/python/` — 50 known-bug files + 50 known-clean files
- `tests/truth_set/csharp/` — 50 known-bug files + 50 known-clean files
- `tests/test_reviewer_truth_set.py`

**Truth set structure** (each file is labeled):
```python
# tests/truth_set/python/bug_mutable_default.py
# TRUTH: PY-COR-01 should fire on line 3
def bad_function(items=[]):  # line 3
    items.append(1)
    return items
```

**Precision test**:
```python
def test_python_precision_above_95_percent():
    tp, fp, fn = 0, 0, 0
    for truth_file in glob("tests/truth_set/python/*.py"):
        expected = parse_truth_labels(truth_file)
        actual = scan_python_file(truth_file, None, "advisory")
        # Compare expected vs actual, count TP/FP/FN
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    assert precision >= 0.95, f"Python precision {precision:.1%} below 95%"
```

### D5: Embedded Language Boundary Detection

**Problem**: Python files with embedded C# strings (f-strings generating Unity scripts) cause FPs. The reviewer doesn't know when it's inside a template string containing another language.

**Fix**: In `scan_python_file`, detect triple-quoted strings and f-strings that contain C# markers (`;`, `void `, `public `, `class `, `using `, `namespace `). Skip reviewer rules on lines that are inside these embedded-language blocks. The `_is_in_triple_quote` function already exists — extend it to also tag the language of the embedded content.

### D6: CI Integration Templates

**Files to create**:
- `docs/ci/github-actions.yml` — GitHub Actions workflow that runs reviewer on PRs
- `docs/ci/azure-devops.yml` — Azure DevOps pipeline

**Template content**:
```yaml
# .github/workflows/code-review.yml
name: Code Review
on: [pull_request]
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install vb-code-reviewer
      - run: vb-review . --scope production --profile general --output report.json
      - run: python -c "import json; r=json.load(open('report.json')); exit(1 if r['critical']>0 else 0)"
```

### D7: Packaging for Distribution

**Problem**: The reviewer is buried inside `veilbreakers_mcp` package. For distribution, it needs its own entry point.

**Files to create/modify**:
- `pyproject.toml` — add `[project.scripts]` entry: `vb-review = "veilbreakers_mcp.vb_code_reviewer:main"`
- Or create a separate `vb-code-reviewer` package that imports from the core

**Minimum**: Ensure `python -m veilbreakers_mcp.vb_code_reviewer` works as a standalone CLI without needing the full MCP server running.

### D8: JSON Output Contract for Agent Consumption

**Problem**: The JSON output format is undocumented. Agents and CI need a stable contract.

**File to create**: `docs/REVIEWER_OUTPUT_SCHEMA.md`

**Document the schema**:
```json
{
  "total_issues": 16,
  "critical": 1,
  "high": 2,
  "medium": 8,
  "low": 5,
  "review_scope": "advisory",
  "issues": [
    {
      "rule_id": "PY-COR-17",
      "severity": "CRITICAL",
      "category": "Bug",
      "file": "path/to/file.py",
      "line": 31,
      "description": "...",
      "fix": "...",
      "confidence": 90,
      "layer": "semantic",
      "profile": "core"
    }
  ]
}
```

Add `profile` field to each Issue so consumers know which profile flagged it.

### D9: Rule Authoring Guide

**File to create**: `docs/WRITING_RULES.md`

**Content**: How to write a new rule — pattern design, guard function patterns, anti-pattern design, testing requirements (must have >=2 fixtures, must scan real code for 0 FP, must pass substance bar).

This is critical for the user's goal of other people contributing rules or creating custom profiles.

---

## BLOCK E: Competitive Differentiators (what makes this worth shipping)

These are NOT required for v1 but are the features that make this reviewer worth using over ruff/pylint/SonarQube/Semgrep alone.

### E1: Multi-Model Consensus Review (already exists)

`review_server.py` already does multi-model consensus via Gemini/GLM/OpenRouter. This is unique — no other reviewer does this. To ship:
- Make the prompts configurable (not VB-hardcoded)
- Add a `--consensus` flag to the CLI that pipes static findings through LLM review
- Document the consensus scoring algorithm

### E2: Guard Function Architecture (already exists)

The guard function system (anti_patterns + callable guards + context dict) is more sophisticated than any regex-based tool. This IS the moat — it's why we can hit <5% FP while ruff/pylint can't. Document this as a feature.

### E3: Tool Chaining with Graceful Degradation (already exists)

The `_tool_runner.py` wraps ruff, mypy, opengrep, dotnet-analyzers, ast-grep — all optional. The reviewer works without any of them but gets better with each one. This is a great UX pattern.

---

## EXECUTION ORDER (updated)

```
Step 0: COMMIT all uncommitted work (see git add/commit above)
        Run: python -m pytest tests/ -q  →  expect 20,824 pass

BLOCK B (reviewer ship — DO FIRST, unblocks everything):
  B1 (30 min, hard blocker)
  B2 + B3 (6h, enables profiles)
  B4 + B5 + B6 (2h, cosmetic but required for external use)
  D1 (2h, diff-only mode — critical for agent/CI use)
  D5 (2h, embedded language detection — fixes known FP class)
  D3 (1h, self-test)
  B7 + B8 (8h, general rules — fills coverage gaps)
  D2 (4h, auto-fix patches — high agent value)
  D4 (4h, truth set — enables precision regression testing)
  D8 (1h, output schema doc)
  B9 + B10 (2h, stdin + rule table)
  D6 + D7 + D9 (3h, CI templates + packaging + rule guide)

BLOCK A (quality infra — protects VB project):
  A1 → A2 → A3 → A4 → A5 → A6 → A7 → A8 → A9

BLOCK C (Unity twins — after A and B):
  C1 → C2 → C3 → C4

BLOCK E (differentiators — v2):
  E1 → E2 → E3

Total estimated: ~70-80 hours across all blocks
```

**WHY Block B first**: The reviewer is the foundation for everything else. Block A's quality lint (A2), honesty linter (A3), and test substance auditor (A6) all depend on the reviewer being trustworthy. Ship the reviewer, THEN build quality infra on top of it.

```
Step 0: COMMIT all uncommitted work (see git add/commit above)
        Run: python -m pytest tests/ -q  →  expect 20,824 pass

BLOCK A (quality infra — protects VB project):
  A1 → A2 → A3 → A4 → A5 → A6 → A7 → A8 → A9 (A9 optional/deferred)

BLOCK B (reviewer ship — enables general Python/C# use):
  B1 (30 min, unblocks everything)
  B2 + B3 (together, 6h)
  B4 + B5 + B6 (cosmetic, 2h)
  B7 + B8 (new rules, 8h)
  B9 + B10 (polish, 2h)

BLOCK C (Unity twins — after A and B):
  C1 → C2 → C3 → C4

Total estimated effort: ~50-60 hours across all blocks
```

## VERIFICATION COMMANDS

After EVERY phase, run:
```bash
cd Tools/mcp-toolkit
python -m py_compile <changed_files>
python -m pytest tests/ -q --tb=line
# For reviewer changes specifically:
PYTHONPATH=src python src/veilbreakers_mcp/vb_code_reviewer.py blender_addon/handlers/ --scope advisory
# Expect: <=20 findings (16 is current baseline)
```

## KNOWN BUGS STILL OPEN (DO NOT regress these)

From the terrain audit (31 P0 bugs), these are the most critical unfixed ones:
1. `terrain_caves.py:821` — `_delta = carve_cave_volume(...)` discarded (PY-COR-16 catches it)
2. `terrain_caves.py:831` — `_damp = generate_damp_mask(...)` discarded (PY-COR-16 catches it)
3. `terrain_morphology.py:31` — `MorphologyTemplate` frozen+mutable Dict (PY-COR-17 catches it)
4. `terrain_semantics.py:669,743` — `TerrainIntentState`/`HeroFeatureSpec` frozen+mutable (PY-COR-17 catches it)
5. `terrain_waterfalls.py:592-697` — pool/outflow deltas never applied
6. `terrain_pass_dag.py:99-147` — execute_parallel is serial under coarse lock
7. `terrain_unity_export.py:155-175` — no Blender Z-up → Unity Y-up axis swap

These bugs should be FIXED in the relevant phase (A4/A5 barrier tests will enforce this), NOT worked around or test-ratified.
