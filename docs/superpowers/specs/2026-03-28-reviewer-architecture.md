# VB Code Reviewer Architecture Specification

**Date**: 2026-03-28
**Status**: Implementation specification
**Goal**: Intelligent, context-aware, cross-file code reviewer achieving <3% false positive rate

## Executive Summary

This document specifies the architecture for the next-generation VB Code Reviewer. The design synthesizes:

- The 3-layer architecture recommendation from `REVIEWER_OPTIMIZATION_HANDOFF.md`
- The file structure from `2026-03-22-unified-code-reviewer-design.md`
- Findings from 30+ Python rules false positive root cause analysis
- Microsoft.Unity.Analyzers research for Unity-specific suppressor patterns
- Production code analyzer best practices

**Target**: <3% FP rate across all modes (production/semantic/advisory)

---

## 1. Multi-Pass Scanning Engine

The scanner operates in **three sequential passes**, each building on the previous:

### Pass 1: Symbol Collection

**Purpose**: Build a symbol table and call graph for cross-file context.

**Implementation**:
- Parse files to extract definitions: classes, methods, fields, properties
- Track imports and namespace usage
- Build intra-file call graph (method A calls method B)
- Store in shared `SymbolTable` dataclass

**Output**: `SymbolTable` containing:
```python
@dataclass
class SymbolTable:
    definitions: dict[str, Definition]      # name -> Definition(line, type, scope)
    references: dict[str, list[Reference]]   # name -> [file, line, context]
    call_graph: dict[str, set[str]]           # method -> set of called methods
    imports: dict[str, set[str]]              # file -> set of imported names
    types: dict[str, TypeInfo]                # type name -> TypeInfo(bases, generic_params)
```

### Pass 2: Context Resolution

**Purpose**: Enrich findings with cross-file semantic context.

**Implementation**:
- For each potential finding, resolve symbol references
- Determine if `UnityEngine.Object` is actually a Unity type (not plain C# object)
- Check if method is transitively called from Update/FixedUpdate (hot path)
- Verify null check coverage using def-use chains

**Key Enrichments**:
- `is_hot_path`: Boolean indicating if method is called from Unity lifecycle
- `null_check_coverage`: Percentage of nullable references with null guards
- `symbol_resolution`: Whether type was resolved (increases confidence)

### Pass 3: Rule Detection with Context

**Purpose**: Apply rules with full context awareness.

**Implementation**:
- Run regex/AST patterns against pre-classified lines
- Apply context guards using enriched data from Pass 2
- Compute final confidence score based on context factors
- Emit to appropriate output tier

**Context-Aware Guards**:
```python
def _check_destroyed_null_semantics(line, all_lines, idx, context):
    """BUG-31: Only fire if we can verify it's a UnityEngine.Object."""
    if not context.symbol_resolved:
        return False  # Cannot confirm type - lower confidence instead
    return context.type_is_unity_object

def _check_hot_path_allocation(line, all_lines, idx, context):
    """PERF-02: Only flag if in hot path AND loop-countable."""
    if not context.is_hot_path:
        return False
    return context.has_loop_context
```

---

## 2. Cross-File Context Building

### Symbol Table Structure

```python
@dataclass
class Definition:
    file: str
    line: int
    name: str
    type: str  # "class", "method", "field", "property"
    signature: str  # Full signature for methods
    scope: str  # "class", "struct", "interface"
    is_static: bool
    visibility: str  # "public", "private", "protected", "internal"

@dataclass
class Reference:
    file: str
    line: int
    column: int
    context: str  # "call", "type_use", "inheritance", "attribute"
    resolved_symbol: Optional[str]
```

### Call Graph Construction

**Algorithm**:
1. Parse each file for method definitions
2. Regex-match method calls within method bodies
3. Map call targets to definitions (intra-file) or defer (cross-file)
4. BFS from Unity lifecycle methods (Update, FixedUpdate, LateUpdate) to mark transitively hot methods

**Hot Path Detection**:
```python
def compute_hot_methods(symbol_table: SymbolTable) -> set[str]:
    hot = {"Update", "FixedUpdate", "LateUpdate", "OnGUI", "OnAnimatorIK"}
    queue = list(hot)
    visited = set(hot)
    
    while queue:
        method = queue.pop(0)
        for caller in symbol_table.call_graph.get(method, []):
            if caller not in visited:
                visited.add(caller)
                queue.append(caller)
    return visited
```

### Definition-Use Chains

Track null check coverage per variable:
```python
@dataclass
class VariableState:
    name: str
    defined_at: tuple[str, int]  # file, line
    null_checks: list[tuple[int, str]]  # (line, check_type: "if != null", "?.", "!")
    uses: list[tuple[str, int]]  # (file, line)
    is_nullable: bool
```

---

## 3. Three-Layer Output Model

### Layer 1: Hard Correctness (Blocking)

**When**: Default `production` scope, `--severity HIGH+`

**Rules** (deterministic, no false positives):
- Python: `ruff` equivalent checks, critical security issues
- C#: Unity null reference crashes, resource leaks, threading race conditions

**Output Class**: `ERROR`, `BUG`

**Example Rules**:
- `PY-SEC-01`: eval() usage → CRITICAL
- `PY-SEC-02`: os.system with shell=True → CRITICAL
- `BUG-01`: GetComponent in Update without caching → CRITICAL
- `BUG-06`: Missing Destroy in OnDisable → CRITICAL
- `SEC-01`: Hardcoded API key → CRITICAL

### Layer 2: Semantic Project Review (Non-blocking by default)

**When**: `advisory` mode or `--include-semantic`

**Rules** (require symbol resolution or Unity semantics):
- Unity lifecycle misuse
- UnityEngine.Object null semantics
- Scene/prefab assumptions
- Performance patterns with evidence

**Output Class**: `BUG`, `OPTIMIZATION`

**Example Rules**:
- `BUG-31`: Destroyed object access (semantic: requires Roslyn symbol resolution)
- `BUG-15`: Physics without Rigidbody (semantic: requires type context)
- `BUG-19`: foreach allocation (semantic: requires hot-path evidence)
- `PERF-02`: Closure in Update (semantic: requires call graph)

### Layer 3: Heuristic Audit (Strict mode only)

**When**: `strict` scope

**Rules**:
- Style guidance
- Long function advice
- Import hygiene
- Refactor suggestions

**Output Class**: `ADVISORY`

**Example Rules**:
- `PY-STY-06`: Missing `__all__`
- `PY-STY-08`: Missing return annotations
- `PY-STY-09`: Function exceeds 60 lines
- `QUAL-01`: God method (>200 lines)

---

## 4. Confidence Scoring

### Multi-Factor Confidence Model

**Base Confidence**: Derived from rule severity
```python
SEVERITY_BASE = {
    Severity.CRITICAL: 95,
    Severity.HIGH: 85,
    Severity.MEDIUM: 75,
    Severity.LOW: 70,
}
```

**Context Multipliers** (applied to base):
| Factor | Condition | Modifier |
|--------|-----------|----------|
| Symbol Resolved | Type resolved via cross-file analysis | +15% |
| Hot Path Confirmed | Called from Update via call graph | +10% |
| Null Check Coverage | >80% of nullable refs guarded | +8% |
| Anti-pattern Present | Known safe pattern detected nearby | -30% |
| Guard Evaluated | Custom guard returned True | +5% |
| Scope Mismatch | Rule requires HotPath but line is Cold | -25% |

**Confidence Formula**:
```
final_confidence = min(100, base_confidence * (1 + sum(modifiers)))
```

**Confidence Labels**:
| Range | Label | Meaning |
|-------|-------|---------|
| 90-100% | CERTAIN | Deterministic, no context needed |
| 75-89% | HIGH | Context strongly supports finding |
| 50-74% | LIKELY | Pattern matches, context inconclusive |
| <50% | POSSIBLE | Heuristic only, verify manually |

---

## 5. Rule Classification by Tier

### Keep (Deterministic - Layer 1)

These rules fire based on syntactic patterns that cannot produce false positives:

**Python**:
| Rule ID | Description | Reason |
|---------|-------------|--------|
| PY-SEC-01 | eval() usage | Always dangerous |
| PY-SEC-02 | os.system shell=True | Always dangerous |
| PY-SEC-03 | pickle.load untrusted | Always dangerous |
| PY-SEC-04 | f-string SQL injection | Always dangerous |
| PY-COR-01 | Mutable default arg | Always a bug |
| PY-COR-02 | Bare except: | Always catches SystemExit |

**C#**:
| Rule ID | Description | Reason |
|---------|-------------|--------|
| BUG-01 | GetComponent in Update | Always missing cache |
| BUG-06 | Destroy missing OnDisable | Always resource leak |
| BUG-07 | Coroutine without StopCoroutine | Always potential leak |
| SEC-01 | Hardcoded password | Always security risk |
| SEC-02 | SQL injection | Always dangerous |

### Rewrite (Context-Dependent - Move to Layer 2)

These require semantic analysis, not regex:

| Rule ID | Current Problem | Required Fix |
|---------|-----------------|--------------|
| BUG-31 | Regex cannot verify UnityEngine.Object | Roslyn symbol resolution |
| BUG-15 | Cannot verify Rigidbody presence | Type context from symbol table |
| BUG-16 | Regex cannot determine LayerMask intent | Call site analysis |
| BUG-19 | Cannot determine collection type | Runtime type resolution |
| BUG-25 | Public fields are sometimes intentional | Authoring pattern detection |
| PERF-02 | Cannot verify loop context | Call graph + hot path |
| PERF-12 | SetParent(false) is sometimes correct | Intent analysis |
| PERF-15 | spatialBlend=0 is valid for 2D | Platform/context detection |

**C# Regex → Python Regex Mapping**:
```python
# Named groups: C# (?<name>...) -> Python (?P<name>...)
C#: r"GetComponent<(?<type>\w+)>"
PY: r"GetComponent<(?P<type>\w+)>"

# Verbatim strings: C# @"..." -> Python r"..."
C#: r@"void\s+OnDisable\s*\(\s*\)\s*\{"
PY: r"void\s+OnDisable\s*\(\s*\)\s*\{"

# Options: C# RegexOptions -> Python re flags
C#: RegexOptions.Multiline | RegexOptions.IgnoreCase
PY: re.MULTILINE | re.IGNORECASE
```

### Drop (High False Positive Rate)

| Rule ID | FP Rate | Reason |
|---------|---------|--------|
| PY-STY-07 | 40%+ | Cannot detect conditional/dynamic imports |
| PY-COR-12 | 30%+ | Logs and returns are valid broad catches |
| PY-STY-01 | 100% advisory | Style only, not a defect |

---

## 6. New Gap Rules (P0/P1)

### P0: Addressable Leak Detection (UNITY-18)

```python
# Pattern: Load addressable without tracking reference for unloading
RULES.append(Rule(
    id="UNITY-18",
    severity=Severity.CRITICAL,
    category=Category.Unity,
    description="Addressable operation without corresponding async handle tracking",
    fix="Store AsyncOperationHandle and call addressable.Release() when done",
    pattern=re.compile(r"Addressables\.(Load|Instantiate)Async"),
    guard=lambda line, all_lines, idx, ctx: not _has_corresponding_release(all_lines, idx),
    confidence=88,
))
```

### P0: EventBus Memory Leak (UNITY-19)

```python
# Pattern: EventBus.Register without Unregister in OnDisable
RULES.append(Rule(
    id="UNITY-19",
    severity=Severity.CRITICAL,
    category=Category.Unity,
    description="EventBus.Register without matching Unregister in OnDisable",
    fix="Add EventBus.Unregister(this) in OnDisable",
    pattern=re.compile(r"EventBus<.*>\.Register"),
    guard=lambda line, all_lines, idx, ctx: not _has_matching_unregister(all_lines, idx),
    confidence=92,
))
```

### P1: ScriptableObject Mutation at Runtime (UNITY-20)

```python
# Pattern: ScriptableObject.CreateInstance followed by field modification
RULES.append(Rule(
    id="UNITY-20",
    severity=Severity.HIGH,
    category=Category.Unity,
    description="Runtime modification of ScriptableObject - changes lost on reload",
    fix="Create in-memory copy with CreateInstance, or use asset instance for persistence",
    pattern=re.compile(r"ScriptableObject\.CreateInstance"),
    guard=lambda line, all_lines, idx, ctx: _is_modified_after_creation(all_lines, idx),
    confidence=78,
))
```

### P1: PrimeTween Lifecycle (UNITY-21)

```python
# Pattern: PrimeTween usage without proper cancellation
RULES.append(Rule(
    id="UNITY-21",
    severity=Severity.HIGH,
    category=Category.Unity,
    description="PrimeTween created without storing reference for cancellation",
    fix="Store Tween and call .Kill() in OnDisable or when no longer needed",
    pattern=re.compile(r"PrimeTween\.(\w+)\."),
    guard=lambda line, all_lines, idx, ctx: not _has_kill_call(all_lines, idx),
    confidence=72,
))
```

### P1: Coroutine Without Yield Return (UNITY-22)

```python
# Pattern: IEnumerator method without yield return (dead coroutine)
RULES.append(Rule(
    id="UNITY-22",
    severity=Severity.HIGH,
    category=Category.Unity,
    description="IEnumerator method never yields - will run once and block",
    fix="Add yield return statements or use regular method",
    pattern=re.compile(r"IEnumerator\s+\w+\s*\("),
    guard=lambda line, all_lines, idx, ctx: not _has_yield_return(all_lines, idx),
    confidence=85,
))
```

---

## 7. Unity-Specific Suppressor Patterns

### SerializeField Suppression

Unity's `[SerializeField]` intentionally leaves fields uninitialized:
```csharp
[SerializeField] private GameObject prefab;  // CS0649 suppressed
```

**Implementation**:
```python
SUPPRESSOR_PATTERNS = {
    "CS0649": [
        r"\[SerializeField\]",
        r"\[Optional\]",
    ],
    "UNT0001": [  # Inefficient coroutine
        r"yield\s+return\s+null",  # Intentionally one-frame wait
    ],
}
```

### Runtime Invocation Guards

Suppress rules when inside known runtime patterns:
```python
RUNTIME_GUARD_PATTERNS = {
    "Update": r"void\s+(Update|FixedUpdate|LateUpdate|OnGUI)\s*\(",
    "Editor": r"#if\s+UNITY_EDITOR",
    "Serialization": r"\[OnSerializing\]|\[OnDeserialized\]",
}
```

### Update/Start/OnEnable/OnDisable Pair Checking

**BUG-06 Expanded**:
```python
def _check_lifecycle_pairs(all_lines, idx, rule_id):
    """Check for Register/Unregister, Enable/Disable pairs."""
    method_start = _find_method_start(all_lines, idx)
    method_name = _extract_method_name(all_lines[method_start])
    
    pairs = {
        "OnEnable": ["OnDisable"],
        "OnDisable": ["OnEnable"],
        "Start": ["OnDestroy", "OnDisable"],
        "Register": ["Unregister"],
        "Subscribe": ["Unsubscribe"],
    }
    
    if method_name in pairs:
        partner_methods = pairs[method_name]
        has_partner = any(
            any(method in line for line in all_lines)
            for method in partner_methods
        )
        if not has_partner:
            return True  # Flag as issue
    return False
```

---

## 8. FP Validation Strategy

### Precision Fixtures

Every rule requires **three fixture types**:

#### Positive Fixtures (Must Match)
```python
POSITIVE_FIXTURES = {
    "PY-SEC-01": [
        "eval(user_input)",  # Must flag
        "result = eval('1+1')",  # Must flag
    ],
    "BUG-01": [
        "void Update() { var rb = GetComponent<Rigidbody>(); }",  # Must flag
    ],
}
```

#### Negative Fixtures (Must NOT Match)
```python
NEGATIVE_FIXTURES = {
    "PY-SEC-01": [
        "import ast; ast.literal_eval(x)",  # Safe alternative
        "# This is commented eval(something)",  # Commented
    ],
    "BUG-01": [
        "void Awake() { rb = GetComponent<Rigidbody>(); }",  # Cached in Awake
        "[SerializeField] private Rigidbody rb;",  # Serialized field
    ],
}
```

#### Regression Fixtures (Real Repo Samples)
```python
REGRESSION_FIXTURES = {
    "PY-COR-12": [
        # Real-world broad catches that are intentional
        "except Exception as e: logger.exception(e); return error_response()",
        "except Exception: return json.dumps({'status': 'error'})",
    ],
}
```

### Validation Test

```python
def test_rule_precision(rule_id, fixtures):
    positive_results = [rule.matches(f) for f in fixtures["positive"]]
    negative_results = [not rule.matches(f) for f in fixtures["negative"]]
    regression_results = [rule.matches(f) for f in fixtures["regression"]]
    
    precision = sum(positive_results) / len(positive_results)
    recall = sum(negative_results) / len(negative_results)
    
    assert precision >= 0.95, f"Rule {rule_id} precision: {precision} < 95%"
    assert recall >= 0.90, f"Rule {rule_id} recall: {recall} < 90%"
```

---

## 9. Implementation Phased Approach

### Phase 1: Foundation (Week 1-2)

**Goal**: Core infrastructure with minimal rule set

**Deliverables**:
- [ ] `vb_code_reviewer.py` skeleton with multi-pass engine
- [ ] `SymbolTable` and context dataclasses
- [ ] CLI with `--scope production|advisory|strict`
- [ ] Basic Python Layer 1 rules (10 rules)
- [ ] Basic C# Layer 1 rules (20 rules)

**Test**: Verify baseline scanning works on toolkit

### Phase 2: Context (Week 3-4)

**Goal**: Cross-file analysis and confidence scoring

**Deliverables**:
- [ ] Symbol table population (definitions, references)
- [ ] Call graph construction with hot-path detection
- [ ] Definition-use chain tracking
- [ ] Confidence score computation

**Test**: Compare Layer 2 rules with/without context

### Phase 3: Detection (Week 5-6)

**Goal**: Full rule implementation

**Deliverables**:
- [ ] All 30 Python rules migrated
- [ ] All 105 C# rules migrated (with semantic tier for weak ones)
- [ ] 5 new gap rules (UNITY-18 to UNITY-22)
- [ ] Unity-specific suppressor patterns

**Test**: Run against VB3DCurrent, measure FP rate

### Phase 4: Verification (Week 7-8)

**Goal**: Precision validation and tuning

**Deliverables**:
- [ ] Positive/negative fixture suite for every rule
- [ ] FP rate measurement pipeline
- [ ] Iterative FP reduction
- [ ] Performance optimization

**Target**: <3% FP rate verified

---

## 10. File Structure

```
Tools/mcp-toolkit/src/veilbreakers_mcp/
├── vb_code_reviewer.py          # Unified entry point + CLI
├── _rules_python.py             # Python rules (30 rules)
├── _rules_csharp.py             # C# rules (105+ rules)
├── _context_engine.py          # Symbol table, call graph, context
├── _suppressors.py             # Unity-specific suppressor patterns
├── vb_python_reviewer.py       # Backward compat wrapper
└── tests/
    ├── test_context_engine.py  # Symbol table tests
    ├── test_rules_python.py    # Python rule fixtures
    ├── test_rules_csharp.py    # C# rule fixtures
    ├── test_precision.py       # FP validation tests
    └── fixtures/
        ├── python_positive/    # Must-match samples
        ├── python_negative/    # Must-not-match samples
        ├── csharp_positive/
        ├── csharp_negative/
        └── regression/         # Real repo samples
```

---

## 11. CLI Interface

### Command Line Arguments

```bash
# Production scan (default)
python vb_code_reviewer.py path/to/code/ --scope production

# Include semantic analysis
python vb_code_reviewer.py Assets/ --scope advisory

# Full forensic scan
python vb_code_reviewer.py . --scope strict

# Language-specific
python vb_code_reviewer.py . --lang cs
python vb_code_reviewer.py Tools/ --lang py

# Severity filter
python vb_code_reviewer.py . --severity HIGH

# JSON output
python vb_code_reviewer.py . --output report.json

# Confidence filter
python vb_code_reviewer.py . --min-confidence 75
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Clean (no issues at threshold) |
| 1 | Issues found at threshold |
| 2 | Invalid arguments |
| 3 | Scan error (file not found, parse error) |

### Output Formats

**Human**:
```
[!!!] #1  CRITICAL  |  Bug  |  BUG-01
       Line 47: GetComponent<T>() in Update -- cache in Awake/Start
       Fix: Cache the component reference in a field during Awake()
       Confidence: 95%  |  Priority: P0-CRITICAL
```

**JSON**:
```json
{
  "total_issues": 12,
  "critical": 2,
  "high": 3,
  "medium": 5,
  "low": 2,
  "files_scanned": 168,
  "avg_confidence": 82.3,
  "issues": [
    {
      "rule_id": "BUG-01",
      "severity": "CRITICAL",
      "confidence": 95,
      "priority": "P0-CRITICAL",
      "layer": "hard_correctness",
      "file": "Assets/Scripts/Combat/BattleManager.cs",
      "line": 47,
      "description": "GetComponent<T>() in Update without caching",
      "fix": "Cache in Awake/Start"
    }
  ]
}
```

---

## 12. Testing Strategy

### Per-Rule Fixtures

**Structure**:
```
tests/fixtures/
├── rules/
│   ├── PY-SEC-01/
│   │   ├── positive.json    # 5+ must-match samples
│   │   ├── negative.json    # 5+ must-not-match samples
│   │   └── regression.json   # 3+ real-repo samples
│   ├── BUG-01/
│   │   ├── positive.cs
│   │   ├── negative.cs
│   │   └── regression.cs
│   └── ...
```

### Fixture Format

```json
{
  "rule_id": "PY-SEC-01",
  "description": "eval() usage - arbitrary code execution risk",
  "positive": [
    {
      "code": "eval(user_input)",
      "expected": true,
      "reason": "Direct eval call"
    }
  ],
  "negative": [
    {
      "code": "ast.literal_eval(x)",
      "expected": false,
      "reason": "Safe alternative"
    }
  ],
  "regression": [
    {
      "source_file": "Tools/mcp-toolkit/src/veilbreakers_mcp/_utils.py",
      "line": 42,
      "expected": true,
      "reason": "Real production bug"
    }
  ]
}
```

### Continuous Validation

```bash
# Run precision tests
pytest tests/test_precision.py -v

# Run with coverage
pytest tests/ --cov=vb_code_reviewer --cov-report=html

# FP rate measurement
python -m pytest tests/ --tb=no -q | grep "FP rate"
```

---

## 13. Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| FP Rate | <3% | Precision tests / real repo scan |
| Scan Speed | 1000 files/min | `time python vb_code_reviewer.py` |
| Memory | <500MB | Peak RSS on full scan |
| Cold Start | <2s | Time to first finding |

### Optimization Strategies

1. **Fast-check pre-filtering**: Extract 4+ character literal from regex for quick skip
2. **Parallel file processing**: Use `concurrent.futures.ThreadPoolExecutor`
3. **Lazy symbol resolution**: Only resolve symbols when context guard requires it
4. **Incremental scan**: Cache symbol table, re-scan only changed files

---

## Appendix A: Rule ID Reference

### Python Rules (30)

| ID | Category | Tier | Status |
|----|----------|------|--------|
| PY-SEC-01 to PY-SEC-07 | Security | L1 | Keep |
| PY-COR-01 to PY-COR-12 | Correctness | L1/L2 | Keep/Rewrite |
| PY-COR-13 to PY-COR-15 | Correctness | L2 | Rewrite |
| PY-PERF-01 to PY-PERF-03 | Performance | L2 | Keep |
| PY-STY-01 to PY-STY-09 | Quality | L3 | Mixed |

### C# Rules (105+)

| ID | Category | Tier | Status |
|----|----------|------|--------|
| BUG-01 to BUG-33 | Bug | L1/L2 | Keep/Rewrite |
| PERF-01 to PERF-22 | Performance | L1/L2 | Keep/Rewrite |
| SEC-01 to SEC-10 | Security | L1 | Keep |
| UNITY-01 to UNITY-17 | Unity | L1/L2 | Keep/Rewrite |
| UNITY-18 to UNITY-22 | Unity | P0/P1 | New |
| QUAL-01 to QUAL-23 | Quality | L3 | Mixed |
| DEEP-01 to DEEP-06 | Deep | L2 | Keep |

---

## Appendix B: C# Regex → Python Mapping

| C# Pattern | Python Equivalent |
|------------|------------------|
| `(?<name>...)` | `(?P<name>...)` |
| `@"..."` (verbatim) | `r"..."` |
| `RegexOptions.Compiled` | (not needed) |
| `RegexOptions.Singleline` | `re.DOTALL` |
| `RegexOptions.Multiline` | `re.MULTILINE` |
| `RegexOptions.IgnoreCase` | `re.IGNORECASE` |

---

## Appendix C: Confidence Decision Tree

```
                    ┌─────────────────────┐
                    │   Start Evaluation  │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                                 ▼
     ┌───────────────┐                 ┌───────────────┐
     │Symbol Resolved│                 │ No Symbol Info│
     │   (Type OK)   │                 └───────┬───────┘
     └───────┬───────┘                         │
             │                    ┌────────────┴────────────┐
             ▼                    ▼                         ▼
    ┌────────────────┐    ┌──────────────┐     ┌──────────────────┐
    │ Hot Path: Yes  │    │Layer 3 Only? │     │ Low Confidence   │
    └───────┬────────┘    └───────┬───────┘     │ (Possible flag)  │
            │                     │              └────────┬─────────┘
            ▼                     │                       │
    ┌───────────────┐             ▼                       │
    │ Has Anti-Pat? │      ┌──────────────┐              │
    └───────┬───────┘      │ Advisory Only│              │
            │              └──────────────┘              │
            ▼                                           │
    ┌───────────────┐                                   │
    │ CONFIDENCE=95%│                                   │
    └───────────────┘                                   ▼
                                        ┌──────────────────────┐
                                        │ CONFIGURED BY RULE   │
                                        │ (base +/- modifiers) │
                                        └──────────────────────┘
```

---

## Document History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-03-28 | 1.0 | VB Code Reviewer | Initial specification |

---

*End of Specification*
