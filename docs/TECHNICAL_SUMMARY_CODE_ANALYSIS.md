# Technical Summary: Code Analysis Techniques

Quick reference for choosing analysis tools and techniques for the VeilBreakers code reviewer.

---

## What Each Technique Can Detect

### Regex (Current Baseline)
- Text patterns: function names, import statements
- **Cannot:** type errors, scope violations, logic bugs, null safety

### AST (Tree-sitter, etc.)
- Structure: function definitions, class hierarchies, nested blocks
- Naming: variable names, function calls
- **Cannot:** semantic meaning (is this variable defined? what's its type?)

### Semantic Analysis (Roslyn, Astroid, Mypy)
- Scope: variable defined? accessed in right scope?
- Types: parameter type matches argument?
- **Cannot:** cross-file tracking, complex control flow reasoning

### Data Flow (CodeQL, Infer)
- Tracking: where does this variable flow?
- Null safety: checked for null before use?
- Taint tracking: untrusted input reaches sink?
- **Cannot:** understand intent/logic correctness

### Control Flow (CodeQL, Infer)
- Reachability: can this code execute?
- Loop detection: is this a loop? how deep?
- Dominance: which block dominates which?
- **Cannot:** predict runtime values

### Symbolic Execution (Infer, research tools)
- Path exploration: what inputs trigger this path?
- Constraint solving: is this condition satisfiable?
- **Cannot:** scale to large programs; all paths are expensive

### LLM Reasoning (Claude, GPT)
- Logic: does this code do what the author intended?
- Edge cases: what if input is null/empty/huge?
- Architecture: is this pattern the right approach?
- **Cannot:** be precise on domain-unknown bugs; hallucinates

---

## Tools Comparison (Practical)

### For C#

**Roslyn** (Best, requires .NET)
- Pros: Full semantic analysis, type information, incremental
- Cons: Requires .NET SDK in project
- Detection: Type errors, scope violations, null safety, null-coalescing patterns
- Performance: 100ms per file
- Cost: Free (built-in)

**Tree-sitter** (Good, no SDK required)
- Pros: Fast, no dependencies, easy to embed
- Cons: No semantic information (just structure)
- Detection: Naming conventions, structural patterns, code style
- Performance: 50ms per file
- Cost: Free

**Semgrep** (Good, multi-language)
- Pros: Semantic patterns, multiple languages, active community
- Cons: Community edition limited to intra-file
- Detection: Security patterns, code quality, custom rules
- Performance: 200ms per file (CE), faster with Pro
- Cost: Free (CE), subscription (Pro)

### For Python

**Astroid + Pylint** (Best for structure)
- Pros: Scope/name resolution, widely used
- Cons: No full type inference without annotations
- Detection: Undefined names, unused variables, cyclic imports
- Performance: 100ms per file
- Cost: Free

**Mypy** (Best for types)
- Pros: Type checking, PEP 484 support, incremental
- Cons: Requires type annotations to be effective
- Detection: Type mismatches, missing returns, attribute errors
- Performance: 50ms per file
- Cost: Free

**Semgrep** (Good for patterns)
- Pros: Language-agnostic rules, easy to write
- Cons: Limited by pattern scope
- Detection: Security, style, custom patterns
- Performance: 200ms per file
- Cost: Free (CE)

---

## Quick Decision Tree

```
Do you need to detect...

TYPE ERRORS (int used as string)?
├─ YES: Roslyn (C#) or Mypy (Python)
└─ NO: Continue

UNDEFINED VARIABLES?
├─ YES: Roslyn, Astroid, or tree-sitter + manual rules
└─ NO: Continue

CROSS-FILE DATA FLOW (input from file A → used unsafely in file B)?
├─ YES: CodeQL or Semgrep Pro
└─ NO: Continue

NULL POINTER DEREFERENCES?
├─ YES: Roslyn, Infer, or LLM reasoning
└─ NO: Continue

LOGIC ERRORS (code looks correct but is wrong)?
├─ YES: LLM (Claude) + static analysis as grounding
└─ NO: Continue

SIMPLE PATTERNS (naming, style, structure)?
├─ YES: Tree-sitter or Semgrep
└─ NO: Continue

→ Probably need multiple tools in combination
```

---

## Embedding in Python: Easy vs Hard

### Easy (Recommended for v1)
- **Tree-sitter:** `pip install tree-sitter` + download C# grammar
- **Astroid:** `pip install astroid`
- **Mypy:** `pip install mypy`
- **Semgrep:** `pip install semgrep` or subprocess call

### Hard (v2+)
- **Roslyn:** Requires running .NET process (can be done via subprocess but complex)
- **CodeQL:** Requires installing CodeQL CLI, learning QL
- **Infer:** Requires OCaml runtime, complex setup

### Not Suitable for Embedding (Use as Subprocess)
- **Roslyn:** Best via subprocess + environment check
- **CodeQL:** CLI only
- **Infer:** CLI only

---

## Performance Budget for Integration

**Assume 300 files in VeilBreakers codebase:**

| Tool | Per-File | Total | Memory | Notes |
|------|----------|-------|--------|-------|
| Tree-sitter | 50ms | 15s | Low | Fast, suitable for CI |
| Regex | 10ms | 3s | Minimal | Baseline (too limited) |
| Astroid | 100ms | 30s | Medium | Python scope analysis |
| Semgrep | 200ms | 60s | Medium | Good coverage |
| Roslyn | 100ms | 30s | Medium | If .NET SDK available |
| CodeQL | 5s | 1500s | High | Only for deep analysis |

**Recommendation:** Multi-tier scanning
- Tier 1 (CI/CD, real-time): Tree-sitter + Astroid (45s)
- Tier 2 (on-demand): Add Roslyn/Semgrep (2+ minutes)
- Tier 3 (manual review): Add LLM (expensive, gated)

---

## Game Dev Specifics

### VeilBreakers Patterns We Could Detect

**Easy (regex, AST):**
- Uninitialized serialized fields
- Missing null checks on component casts
- Subscription without unsubscription
- Coroutine not awaited

**Medium (semantic analysis):**
- Object retrieved from pool, used after return
- Component accessed before Awake()
- Event fired after scene unload
- Ability cooldown not tracked

**Hard (data flow + domain knowledge):**
- Synergy corruption tier not validated before use
- Loot table reference broken by respawn
- Component lifecycle order violations
- Shader variable set twice without use

### Domain Knowledge Required

To detect game-dev bugs, the code reviewer needs:
1. Component lifecycle (Awake → OnEnable → Start → ...)
2. Object pooling patterns (Return() marks object as "dead")
3. Serialization rules (what can/can't be serialized)
4. VeilBreakers systems (synergy, corruption, abilities, loot)

**Solution:** Create rule database (YAML or JSON) that encodes these patterns, then apply with Semgrep or custom AST walker.

---

## Recommended Next Steps

### Phase 1: Expand Regex (v6.1)
- Keep current 201 rules
- Add AST-based enhancements using tree-sitter

### Phase 2: Semantic Layer (v7.0)
- Integrate Roslyn for C# (if .NET SDK available) OR enhance tree-sitter manually
- Integrate Astroid/Mypy for Python
- Build game-dev pattern database

### Phase 3: Reasoning Layer (v7.5)
- Gate LLM reasoning behind confidence threshold
- Use for complex patterns (not covered by static analysis)
- Provide context: function code, call sites, documentation

### Phase 4: Cross-File Analysis (v8.0)
- Evaluate CodeQL or Semgrep Pro for taint tracking
- Detect data flow bugs (input → processing → dangerous sink)

---

## Key Takeaway

**No single tool is sufficient.** Production code analysis uses 3-5 techniques in combination:

1. **Regex:** Fast, high-precision, limited scope
2. **AST:** Structural understanding, fast
3. **Semantic:** Type/scope information, medium speed
4. **Data flow:** Taint tracking, logic across files (expensive)
5. **LLM:** Reasoning about intent and edge cases (very expensive)

**For VeilBreakers:**
- Start with Tier 1-2 (regex + semantic)
- Add Tier 3 (LLM) for hard cases only
- Build game-dev rule database to catch domain-specific bugs
