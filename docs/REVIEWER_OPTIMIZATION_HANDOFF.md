# Reviewer Optimization Handoff

Date: 2026-03-27
Repo: `veilbreakers-gamedev-toolkit`
Focus: reviewer architecture, false positives, best-practice direction, and remaining issues

## Executive Summary

The reviewer problem was not just "bad thresholds." The core issue was architectural:

- the Python reviewer had two sources of truth
- the default scan scope mixed production code, tests, temp files, and audit scripts
- weak C# regex heuristics were emitted like real bug findings
- Unity headless review could silently skip files due to swallowed exceptions

The right long-term design is:

1. deterministic blocking review for production code only
2. semantic project-specific review for Unity/VeilBreakers patterns
3. advisory heuristic review in non-blocking or strict/audit modes

## Changes Already Landed

These changes are already in the worktree:

- Canonical Python reviewer source:
  - `Tools/mcp-toolkit/src/veilbreakers_mcp/vb_python_reviewer.py`
- Generated Python reviewer now ships the canonical file instead of embedding a second copy:
  - `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/code_review_templates.py`
- Python reviewer now supports scoped review:
  - `production`
  - `strict`
- Default `production` scope skips:
  - `tests/`
  - `testdata/`
  - `fixtures/`
  - `_tmp*`
  - backup/output temp paths
- Strict-only noisy Python rules in default review:
  - `PY-COR-13`
  - `PY-STY-05`
  - `PY-STY-06`
  - `PY-STY-08`
  - `PY-STY-09`
- `PY-COR-10` no longer fires on float-equality test asserts
- `PY-COR-13` now only flags local project lazy imports, not stdlib imports
- Unity reviewer now:
  - reports scan errors instead of swallowing them
  - skips Python tests/temp files in generated review script
- Weak C# regex rules are now explicitly marked as semantic-tier advisory candidates instead of being treated as trustworthy bug rules
- Unity MCP schema-title stripping was added to reduce schema token waste
- Unity template helper now preserves extra metadata fields instead of discarding them

## Verified Precision Delta

Measured on `Tools/mcp-toolkit`:

- old Python reviewer run: `4225` findings
- new `production` run: `255` findings
- new `strict --include-tests --include-temp` run: `1236` findings

This confirms the main false-positive flood was caused by bad scope and over-broad advisory rules, not a genuinely broken codebase.

## Root Causes Of False Positives

### 1. Wrong Default Scope

The reviewer was scanning:

- production Python
- Blender addon code
- tests
- fixtures
- temp scripts
- audit artifacts
- backups

and reporting all of them in one stream.

This guaranteed noise. Tests intentionally use patterns that should not be treated like production bugs.

### 2. Regex/Light AST Treated As Semantic Analysis

Several rules require type or runtime knowledge the reviewer did not have.

Examples:

- `BUG-31`: Unity destroyed-object null semantics require symbol resolution
- `BUG-15`: collision callback presence does not prove Rigidbody correctness
- `BUG-16`: missing `LayerMask` is often advice, not a correctness defect
- `BUG-19`: `foreach` allocation depends on runtime/backend/collection type
- `BUG-25`: public fields can be intentional authoring/data patterns
- `PERF-02`: closure allocation depends on capture behavior and runtime
- `PERF-12`: `SetParent(false)` is not always correct
- `PERF-15`: `spatialBlend=0` is valid for 2D audio

### 3. Style Guidance Was Mixed With Bug Findings

The reviewer surfaced style/refactor guidance as if it were correctness.

Worst offenders on Python:

- `PY-STY-06` missing `__all__`
- `PY-STY-08` missing return annotations
- `PY-STY-09` long functions
- `PY-COR-13` lazy imports

These may be useful in audit mode, but they should not dominate default bug review.

### 4. Precision Tests Were Too Weak

The system had limited negative-fixture discipline.

That means a rule could be "technically implemented" but still produce large volumes of bad findings without getting caught in tests.

## Remaining False-Positive / Accuracy Problems

These are still the main remaining issues after the redesign.

### Python Remaining Production Noise

The current `production` Python reviewer output is now mostly concentrated in:

- `PY-STY-07` unused imports: `176`
- `PY-COR-12` broad catches: `34`
- `PY-STY-01` `os.path` advisory: `23`

#### `PY-STY-07` unused imports

This is now the biggest remaining noise cluster.

Some of these are likely real cleanup items.
Some are likely false positives from:

- type-only or runtime-conditional use patterns
- delayed Blender runtime access
- compatibility/import side effects
- module-structured helper imports not visible to simple AST name checks

Best practice:

- keep this advisory, not blocking
- suppress when:
  - module is Blender runtime glue
  - import appears in compatibility/bootstrap modules
  - import is clearly intentional side-effect wiring
- add precision fixtures using real repo samples

#### `PY-COR-12` broad `except Exception`

Current rule still flags many logged safety-net blocks.

This is too coarse.

Best practice:

- severity split:
  - real bug when broad catch swallows silently
  - advisory when broad catch logs and returns structured failure
- suppress or demote when block:
  - logs with context
  - returns explicit error payload
  - guards external tool/runtime boundaries

#### `PY-STY-01` `os.path` guidance

This is a style recommendation, not a defect.

Best practice:

- advisory only
- never blocking
- optionally hidden from default production mode entirely

### C# Remaining Accuracy Problem

The weak C# regex rules are still not truly fixed. They were only reclassified and documented.

That was the correct immediate move, but not the final solution.

They still need semantic replacement.

## Weak C# Regex Rules That Must Move To Semantic Tier

These should not remain regex bug rules:

- `BUG-15`
- `BUG-16`
- `BUG-19`
- `BUG-25`
- `BUG-31`
- `PERF-02`
- `PERF-12`
- `PERF-15`

### Why

- they depend on actual types
- they depend on Unity object semantics
- they depend on runtime/backend behavior
- they depend on gameplay intent
- line-level regex cannot prove them

## Best-Practice Reviewer Architecture

### Layer 1: Hard Correctness

Default and blocking.

Python:

- `ruff`
- `pyright`
- custom deterministic VeilBreakers checks only

C#:

- Roslyn analyzers
- Unity-specific analyzers
- deterministic project checks only

Output class:

- `error`
- `bug`

No style noise.

### Layer 2: Semantic Project Review

Non-blocking by default, but high-value.

Used for:

- Unity lifecycle misuse
- UnityEngine.Object semantics
- scene/prefab assumptions
- hot-path performance patterns with evidence
- project-specific gameplay/tooling constraints

This layer should use:

- Roslyn symbols/types for C#
- richer Python AST/context rules for project patterns

Output class:

- `bug`
- `optimization`
- `advisory`

### Layer 3: Heuristic Audit Review

Strict mode only.

Includes:

- style guidance
- long-function advice
- annotation suggestions
- import hygiene
- refactor suggestions

Output class:

- `advisory`

Never the main blocking signal.

## Best Default Scope

### Production Review

Should include:

- `Tools/mcp-toolkit/src/veilbreakers_mcp`
- `Tools/mcp-toolkit/blender_addon`
- actual Unity runtime/editor code under review

Should exclude by default:

- `tests/`
- `fixtures/`
- `testdata/`
- `_tmp*`
- backup folders
- audit artifacts
- scratch scripts
- generated temp output

### Strict Review

Should include everything, but findings must remain classified by strength.

## Best Next Implementation Steps

### Priority 1: Roslyn Semantic Tier

Implement real C# semantic analysis for the weak rules.

Minimum target set:

1. `BUG-31`
   - resolve actual `UnityEngine.Object` symbols
   - only warn when the expression is really a Unity object

2. `BUG-15`
   - use class/component context
   - ideally inspect prefab/scene assumptions when available

3. `BUG-16`
   - downgrade unless surrounding call-site context proves it is risky

4. `BUG-19` and `PERF-02`
   - require hot-path evidence plus allocation-risk evidence

5. `BUG-25`
   - keep advisory/design only

### Priority 2: Python Production Precision Pass

Next rules to tighten:

1. `PY-STY-07`
2. `PY-COR-12`
3. optionally hide `PY-STY-01` from default production output

### Priority 3: Precision Fixture Suite

For every custom rule:

- one positive fixture
- one negative fixture
- one real repo regression fixture when possible

Without this, false positives will drift back.

## Recommended Product Behavior

Expose three user-facing review modes:

### `review production`

- high precision
- production code only
- blocking

### `review advisory`

- production code
- non-blocking
- includes project heuristics and optimization guidance

### `review strict`

- full forensic scan
- includes tests/temp/style/advisory content

## Current Worktree Files Relevant To Reviewer Redesign

- `Tools/mcp-toolkit/src/veilbreakers_mcp/vb_python_reviewer.py`
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/code_review_templates.py`
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_tools/_common.py`
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_tools/__init__.py`
- `Tools/mcp-toolkit/tests/test_unity_common.py`
- `Tools/mcp-toolkit/tests/test_vb_python_reviewer.py`
- `Tools/mcp-toolkit/tests/test_code_review_templates.py`

## Verification Already Run

- targeted reviewer/tooling tests passed
- Unity/QA template tests passed
- full toolkit suite passed:
  - `17929 passed, 1 skipped`

## Bottom Line

The best approach is not more regex.

The best approach is:

1. deterministic blocking review for production code
2. Roslyn-backed semantic review for context-sensitive C# findings
3. advisory heuristic review in strict mode
4. strong precision fixtures so the reviewer cannot regress back into noise

