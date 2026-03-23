# Unified Code Reviewer -- Design Spec

**Date**: 2026-03-22
**Status**: Approved for implementation
**Goal**: Single Python CLI that reviews both C# and Python files using the same 210+ rules from the Unity EditorWindow, runnable directly from Claude Code without Unity.

## Problem

The VB code reviewer (210 C# rules, 46 Python rules, anti-pattern suppression, <1% FP rate) only runs inside Unity as a C# EditorWindow. The standalone Python reviewer (`vb_python_reviewer.py`) handles only Python with 30 rules. We need the full ruleset accessible from Claude Code for everyday development.

## Architecture: Approach B -- Modular Rule Files

```
Tools/mcp-toolkit/src/veilbreakers_mcp/
  vb_code_reviewer.py        # Unified entry point + scanner engine + CLI
  _rules_python.py           # 30+ Python rules as Rule() objects
  _rules_csharp.py           # 105+ C# rules as Rule() objects
  vb_python_reviewer.py      # (kept for backward compat, imports from above)
```

### Core Components

#### 1. Scanner Engine (`vb_code_reviewer.py`)

Reuses the existing `Rule`, `Issue`, `_suppressed_by_anti()` infrastructure from `vb_python_reviewer.py`.

New additions:
- **Language detection**: `.cs` -> C#, `.py` -> Python, `--lang` override
- **C# line classifier**: Pre-scan pass that tags each line as one of:
  - `HotPath` (inside Update/FixedUpdate/LateUpdate/OnGUI)
  - `Comment` (// or /* */ blocks)
  - `StringLiteral` (inside multiline string)
  - `EditorBlock` (inside #if UNITY_EDITOR)
  - `Attribute` ([SerializeField] etc.)
  - `Cold` (everything else)
- **Scope-aware matching**: Rules declare `scope` (HotPath/AnyMethod/ClassLevel/FileLevel), scanner respects it
- **InsidePattern/NotInsidePattern**: Rules can require/exclude specific method contexts
- **File filter**: Rules can target Runtime/EditorOnly/All files (based on path containing /Editor/)

#### 2. C# Rules (`_rules_csharp.py`)

Port all 105 C# rules from `code_review_templates.py` as Python `Rule()` objects:

**Categories (with counts from template):**
- BUG-01 to BUG-33: Unity anti-patterns, null checks, disposal, threading
- PERF-01 to PERF-22: Hot path allocations, LINQ in Update, boxing
- SEC-01 to SEC-10: SQL injection, hardcoded secrets, insecure random
- UNITY-01 to UNITY-17: Coroutine misuse, serialization, lifecycle
- QUAL-01 to QUAL-23: God methods, dead code, naming conventions

**Each rule has:**
- `pattern`: Python regex (port from C# Regex -- mostly 1:1 compatible)
- `anti_patterns`: List of suppression regexes (same patterns, ported)
- `anti_radius`: Lines around match to check anti-patterns (default 3)
- `severity`, `category`, `confidence`, `priority`
- `scope`: Which line contexts the rule fires in
- `fix`: Actionable fix description
- `reasoning`: For low-confidence findings

**Deep analysis rules (DEEP-01 to DEEP-06):**
These require multi-pass analysis (method boundaries, variable tracking, coroutine lifecycle, cognitive complexity). Port as Python functions that operate on the full file AST/line array rather than single-line regex.

#### 3. Python Rules (`_rules_python.py`)

Extract existing 30 rules from `vb_python_reviewer.py` into this module. No logic changes, just relocation.

#### 4. CLI Interface

```bash
# Scan directory (auto-detect languages)
python vb_code_reviewer.py path/to/scan/

# Scan specific language
python vb_code_reviewer.py Assets/Scripts/ --lang cs

# Filter severity
python vb_code_reviewer.py . --severity HIGH

# JSON output for Claude consumption
python vb_code_reviewer.py . --output report.json

# Scan both projects at once
python vb_code_reviewer.py Assets/Scripts/ Tools/mcp-toolkit/src/ --output report.json
```

**Exit codes:** 0 = clean, 1 = issues found, 2 = invalid args

**Human-readable output** (same format as existing Python reviewer):
```
======================================================================
  File 1: Scripts/Combat/BattleManager.cs  [3 findings] (1 critical)
======================================================================

  [!!!] #1  CRITICAL  |  Correctness  |  Bug
       Line 47: GetComponent<T>() in Update -- cache in Awake/Start
       Fix: Cache the component reference in a field during Awake() or Start().
       Code: var rb = GetComponent<Rigidbody>();
       Rule: BUG-01  |  Confidence: 95%  |  Priority: 95/100
```

**JSON output** (for Claude Code consumption):
```json
{
  "total_issues": 12,
  "critical": 2, "high": 3, "medium": 5, "low": 2,
  "files_scanned": 168,
  "issues": [
    {
      "rule_id": "BUG-01",
      "severity": "CRITICAL",
      "file": "Assets/Scripts/Combat/BattleManager.cs",
      "line": 47,
      "description": "GetComponent<T>() in Update -- cache in Awake/Start",
      "fix": "Cache the component reference in a field during Awake() or Start().",
      "confidence": 95,
      "priority": 95
    }
  ]
}
```

### Backward Compatibility

- `vb_python_reviewer.py` stays as-is but imports rules from `_rules_python.py`
- Unity EditorWindow (`code_review_templates.py`) unchanged -- it's the C# version
- Both share the same rule IDs and severities

### Rule Porting Strategy

C# Regex patterns are ~95% compatible with Python `re`. Known differences to handle:
- Named groups: `(?<name>...)` in C# -> `(?P<name>...)` in Python
- `RegexOptions.Singleline` -> `re.DOTALL`
- `RegexOptions.Multiline` -> `re.MULTILINE`
- `RegexOptions.IgnoreCase` -> `re.IGNORECASE`
- Verbatim strings `@"..."` in C# -> raw strings `r"..."` in Python (already the case in template)

### Testing

- Port existing Python reviewer tests to cover unified scanner
- Add C# scanning tests with sample .cs snippets
- Verify rule parity: count rules in Python reviewer vs C# template, ensure match
- FP validation: run against VB3DCurrent's 168 .cs files, confirm <5% FP rate

### Implementation Order

1. Create `_rules_python.py` -- extract existing Python rules from `vb_python_reviewer.py`
2. Create `_rules_csharp.py` -- port all 105 C# rules from template
3. Create `vb_code_reviewer.py` -- unified scanner with C# line classifier + CLI
4. Add DEEP-01 to DEEP-06 multi-pass analysis
5. Update `vb_python_reviewer.py` to import from `_rules_python.py`
6. Test against VB3DCurrent + toolkit, validate FP rate
7. Run against VB3DCurrent, fix any FP issues in rules
