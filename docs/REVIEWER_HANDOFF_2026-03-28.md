# Reviewer Handoff

Date: 2026-03-28
Repo: `veilbreakers-gamedev-toolkit`
Focus: unified Python/C# reviewer quality, false-positive reduction, semantic context, and agent usefulness

## Executive Summary

The unified reviewer is materially stronger than it was at the start of today’s work, but it is not yet at the final “best possible forever” state.

Major progress landed in four areas:

- real reviewer bugs were fixed
- the context engine now does more real work instead of exposing dead/stubbed paths
- strict-mode false-positive spam was reduced substantially
- dedicated unified-reviewer regression tests were added

This means the reviewer is more useful for agents right now, especially for:

- identifying higher-confidence correctness issues
- avoiding some previous false positives in Python and C#
- giving clearer strengthening output without as much repetition
- supporting semantic Unity/C# checks better than before

## What Changed Today

### 1. Core reviewer fixes

#### `Tools/mcp-toolkit/src/veilbreakers_mcp/_rules_python.py`

- fixed broken re-export regex/backreference logic for unused import suppression
- improved late-binding detection to avoid regex-string/self-hit noise and to stop scanning once indentation exits the loop block
- improved broad-except handling so logged/structured-return cases are less likely to be treated as silent swallows
- reduced heuristic noise for private/internal modules

#### `Tools/mcp-toolkit/src/veilbreakers_mcp/_context_engine.py`

- added real variable-state tracking
- added null-check tracking for Python and C# indexing
- added event unsubscription tracking
- fixed `get_callers()` file filtering to stop using imprecise `endswith(...)`
- replaced broad fallback Unity-object guesses with more explicit base-type propagation
- fixed hot-path propagation direction so hot-path reachability follows callees instead of callers

#### `Tools/mcp-toolkit/src/veilbreakers_mcp/_rules_csharp.py`

- replaced stubbed `DEEP_CHECKS` with real semantic check functions
- fixed `count_char()` loop behavior so it no longer relies on ineffective `for`-loop index mutation
- narrowed `BUG-55` to teardown methods (`OnDisable` / `OnDestroy`)
- narrowed `GAME-05` so it targets likely `ParticleSystem.Play()` cases instead of any `.Play()`
- moved `UNITY-12` toward a semantic teardown-strengthening role instead of broad overlap
- fixed one-line method-boundary handling for helper logic used by semantic rules

#### `Tools/mcp-toolkit/src/veilbreakers_mcp/vb_code_reviewer.py`

- fixed C# hot-path classification for nested braces inside hot methods
- tightened method detection so constructs like `if (...)` are not misread as methods
- replaced repeated line-prefix joins with offset-based pattern scanning
- kept C# DEEP checks out of `production` scope
- added heuristic strengthening curation so strict-mode output keeps representative advice instead of repeating the same low-value hints per file

### 2. New tests added

New test file:

- `Tools/mcp-toolkit/tests/test_vb_code_reviewer.py`

Coverage includes:

- re-exported import suppression
- private/internal module noise suppression
- nested-brace C# hot-path classification
- context-engine variable-state population
- `BUG-55` teardown narrowing
- `GAME-05` target narrowing
- strengthening-output curation

## Files Modified Today

- `Tools/mcp-toolkit/src/veilbreakers_mcp/_rules_python.py`
- `Tools/mcp-toolkit/src/veilbreakers_mcp/_context_engine.py`
- `Tools/mcp-toolkit/src/veilbreakers_mcp/_rules_csharp.py`
- `Tools/mcp-toolkit/src/veilbreakers_mcp/vb_code_reviewer.py`
- `Tools/mcp-toolkit/tests/test_vb_code_reviewer.py`
- `opencode.json`
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/opencode.json`

## Verification Completed

### Diagnostics

All modified reviewer source files were checked with LSP diagnostics and are clean.

### Tests

Passed:

- `pytest Tools/mcp-toolkit/tests/test_vb_code_reviewer.py -q` → `7 passed`
- `pytest Tools/mcp-toolkit/tests/test_vb_python_reviewer.py -q` → `6 passed`

### Import / integration

Verified all reviewer modules load together:

- `_context_engine.py`
- `_rules_python.py`
- `_rules_csharp.py`
- `vb_code_reviewer.py`

### Validation scans

Measured on:

- `Tools/mcp-toolkit/src/veilbreakers_mcp`

Results over the course of today’s work:

- earlier strict validation: `308` findings
- intermediate improved strict validation: `291`
- later improved strict validation: `183`
- final strict validation: `144`

Final strict profile:

- `total_issues = 144`
- `semantic = 5`
- `heuristic = 139`
- `errors_bugs = 5`
- `strengthening = 139`

Top remaining strict rules:

- `PY-STY-07` unused imports: `60`
- `PY-STY-06` missing `__all__`: `44`
- `PY-STY-09` long functions: `23`
- `PY-STY-01` os.path preference: `9`
- `PY-COR-12` broad except: `3`

Final production profile:

- `total_issues = 0`
- `hard_correctness = 0`
- `errors_bugs = 0`

## Current Reality Check

This reviewer is better, more trustworthy, and more agent-usable than it was at the start of the session.

However:

- strict mode is still dominated by strengthening heuristics rather than bug findings
- production mode is still extremely conservative
- the reviewer is not yet proven to be under `<3%` false positives across the whole intended use surface
- Python strengthening output is still the largest remaining noise source

So the state is:

- **much improved**
- **good enough to help agents today**
- **not yet final-best-state**

## Highest-Value Remaining Gaps

### 1. `PY-STY-07` still dominates strict mode

Even after improvements, unused-import reporting is still the largest strict-mode bucket.

What is still missing:

- richer re-export detection
- package-level/public-API awareness beyond simple `__all__`
- stronger whole-codebase intent checks for imports that support runtime glue, registries, decorators, or indirect usage

### 2. `PY-STY-06` is still noisy

Missing `__all__` is often advisory, but still too common in the strict report.

What is still missing:

- stronger public-API detection
- module-role awareness
- package/private/internal module heuristics beyond filename-prefix checks

### 3. `PY-STY-09` still uses mostly raw size

Function length is useful as a strengthening signal, but raw line count remains a blunt instrument.

What is still missing:

- complexity weighting
- exemption for data tables / registries / declarative rule builders
- stronger scoring based on branching and nesting instead of only size

### 4. Production mode is safe but under-sensitive

`production` currently returns `0` findings on the reviewer project. That avoids spam, but may also be too conservative for real bug discovery.

What is still missing:

- better calibration for which semantic bug checks are precise enough for production
- confidence-weighted emission rules for non-heuristic findings

### 5. Confidence scoring is still mostly static

Confidence is attached per rule, but not deeply recalibrated using:

- code context richness
- guard strength
- semantic confirmation depth
- historical false-positive behavior

## Recommended Next Steps

### Priority 1 — keep reducing strict false positives without losing real signal

1. **Upgrade `PY-STY-07` to be more codebase-aware**
   - detect package-level re-export intent more reliably
   - treat registry/decorator/runtime-glue imports as likely-meaningful
   - use whole-project reference search where confidence is otherwise weak

2. **Refine `PY-STY-06` public API detection**
   - stop assuming every module with multiple public names should define `__all__`
   - add module-role heuristics for implementation files, registries, templates, and internal support code

3. **Replace raw function-length warnings with scored maintainability analysis**
   - combine size + branching + nesting + repeated patterns
   - exempt declarative builder functions and rule registries when appropriate

### Priority 2 — make production mode stronger without becoming noisy

4. **Promote only truly high-confidence semantic rules into production**
   - based on demonstrated precision, not aspiration
   - likely candidates come from the new C# DEEP checks once tuned further

5. **Implement dynamic confidence calibration**
   - confidence should rise when semantic context confirms a finding
   - confidence should fall when heuristics are weak or project intent is ambiguous

### Priority 3 — improve agent usefulness and fix quality

6. **Upgrade explanations and fixes**
   - make fixes more situational, not just generic one-liners
   - include “why this is probably real here” in more findings
   - include better strengthening recommendations when suggesting refactors/optimizations

7. **Add more precision fixtures**
   - negative fixtures for false-positive-prone rules
   - multi-file semantic fixtures for cross-file validation claims
   - explicit production-vs-strict expectation tests

### Priority 4 — reviewer quality program

8. **Create a persistent reviewer benchmark pack**
   - true-positive cases
   - known false-positive cases
   - expected confidence bands
   - expected production/strict outputs

This is the fastest way to keep pushing toward the `<3%` false-positive goal without regressing behavior.

## Suggested Immediate Next Agent Task

If another agent picks this up next, the best immediate follow-up is:

**“Reduce `PY-STY-07`, `PY-STY-06`, and `PY-STY-09` strict-mode noise using codebase-aware heuristics and add precision fixtures proving the reduction.”**

That is the highest-leverage remaining work for trust, speed, and agent usefulness.
