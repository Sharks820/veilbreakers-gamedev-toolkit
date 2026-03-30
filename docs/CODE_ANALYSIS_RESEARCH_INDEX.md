# Code Analysis Research Index

**Research Date:** March 29, 2026
**Topic:** State of the art in code analysis beyond regex — semantic analysis techniques, tools, and implementation roadmap for VeilBreakers code reviewer

---

## Documents in This Research

### 1. RESEARCH_SUMMARY.md (342 lines)
**Quick-start executive summary**
- What regex cannot catch
- Key findings at a glance
- Tools ranked by usefulness
- Performance budget
- Recommendations
- **Read this first if you're in a hurry**

### 2. RESEARCH_CODE_ANALYSIS_STATE_OF_ART.md (768 lines)
**Comprehensive technical deep-dive**
- 9 major analysis techniques explained:
  1. AST-based static analysis (Roslyn, tree-sitter)
  2. Abstract interpretation & symbolic execution
  3. Semantic analysis (control/data flow)
  4. CodeQL and its capabilities
  5. Semgrep pattern matching
  6. Tree-sitter parsing
  7. Python analysis tools
  8. LLM-augmented review
  9. Emerging techniques (FalconEYE)
- Comparison matrix of tools
- Detailed performance characteristics
- What regex fundamentally cannot detect
- All references cited
- **Read this for complete understanding**

### 3. TECHNICAL_SUMMARY_CODE_ANALYSIS.md
**Quick reference & decision guide**
- What each technique can detect (table)
- Tools comparison (C#, Python)
- Decision tree for tool selection
- Easy vs hard integration
- Performance budget for 300 files
- Game dev specifics
- Recommended phase plan
- Key takeaways
- **Read this for implementation planning**

---

## Key Findings (TL;DR)

### What Regex Cannot Catch

| Bug Type | Regex | Tree-sitter | Semantic | Data Flow |
|----------|-------|------------|----------|-----------|
| Undefined variable | ✗ | ✓ | ✓ | ✓ |
| Type mismatch | ✗ | ✗ | ✓ | ✓ |
| Null dereference | ✗ | ✗ | ✓ | ✓ |
| Cross-file taint | ✗ | ✗ | ✗ | ✓ |
| Unreachable code | ✗ | ✓ | ✓ | ✓ |
| Scope violation | ✗ | ✓ | ✓ | ✓ |

**Bottom line:** Regex catches ~5% of semantic bugs. Adding semantic analysis covers another 20-30%. Data flow covers another 10%.

---

## Recommended Tools for VeilBreakers

### Tier A: High Value, Easy Integration (v7.0)

1. **Tree-sitter (C# + Python)**
   - No dependencies
   - 50ms per file
   - Detects: scope violations, naming, structure
   - Adds: 10-15 patterns

2. **Roslyn (C# only, optional)**
   - Type checking, null safety
   - 100ms per file
   - Requires .NET SDK
   - Adds: 20-30 patterns

3. **Astroid (Python)**
   - Scope/name resolution
   - 100ms per file
   - Adds: 10-15 patterns

### Tier B: High Value, More Complex (v8.0+)

4. **Semgrep (C# + Python)**
   - Pattern matching in YAML
   - Free community edition
   - Cross-file analysis with Pro
   - Adds: 20+ patterns

5. **CodeQL (for complex logic)**
   - Data flow & taint tracking
   - Steep learning curve
   - Powerful but expensive
   - Adds: 20+ patterns

6. **LLM (Claude, GPT)**
   - Logic errors, edge cases
   - Expensive & hallucinates
   - Gate behind threshold
   - Adds: 10-15 patterns

---

## Implementation Timeline

### Phase 7 (2-3 weeks): Semantic Layer
- Tree-sitter for C# (2-3 days) → +10-15 patterns
- Optional Roslyn (3-5 days) → +20-30 patterns
- Astroid for Python (1-2 days) → +10-15 patterns

### Phase 8 (1 week): Integration & Polish
- Game dev rule database (2-3 days)
- Testing & tuning (3-4 days)

### Phase 9+ (Future): Data Flow
- Manual control flow graphs (3-5 days)
- Semgrep Pro or CodeQL (ongoing)

**Total effort:** ~3-4 weeks for 40-60 new bug patterns
**Total scan time:** 30-50 seconds for 300 files (up from 3 seconds, but worth it)

---

## Performance Budget

| Phase | Tools | Per-File | 300 Files | Patterns |
|-------|-------|----------|-----------|----------|
| v6.0 | Regex | 10ms | 3s | 201 |
| v7.0 | + Semantic | 110-160ms | 33-48s | +40-60 |
| v8.0 | + Data Flow | 200ms | 60s | +20 |

---

## What Each Technique Does Uniquely

### Regex
- Fast text matching
- Hardcoded secrets, imports, naming
- **Cannot:** understand context

### Tree-sitter (AST)
- Parse code into structure tree
- Find scope violations, undefined names
- **Cannot:** understand semantics (types, meaning)

### Semantic Analysis (Roslyn, Astroid)
- Understand scope, names, types
- Detect type mismatches, null safety
- **Cannot:** cross-file analysis

### Data Flow (CodeQL, Infer)
- Track how data flows through code
- Detect taint (input → dangerous sink)
- **Cannot:** be fast or easy

### Control Flow
- Build graphs of execution paths
- Detect unreachable code
- **Cannot:** be complete (path explosion)

### LLM Reasoning
- Understand intent and logic
- Catch missing edge cases
- **Cannot:** be precise; hallucinates

---

## Decision: Which Tool First?

**If .NET SDK is in project:**
→ **Roslyn** (will catch most C# bugs)

**If no .NET SDK:**
→ **Tree-sitter** (no dependencies, covers both languages)

**For Python:**
→ **Astroid** (always add this)

**For highest coverage:**
→ **Semgrep** + custom YAML rules

**Recommendation:** Start with Tree-sitter + Astroid (zero friction), then add Roslyn if .NET available. Pilot Semgrep for game-dev patterns.

---

## False Positive Risk

Current: ~2% (regex only)
After semantic layer: ~3-4%
After data flow: ~4-5%
After LLM: ~5-8%

**Mitigation:** Use confidence scores; only report findings with > 80% confidence

---

## Key Limitations

- **Roslyn:** C# only, requires .NET SDK
- **Tree-sitter:** No semantic info (structure only)
- **Astroid:** Python only, limited type inference
- **Semgrep:** Steep rule-writing curve (but rewarding)
- **CodeQL:** Very slow, requires QL queries
- **LLM:** Expensive, hallucinates

---

## Next Steps

1. **Read RESEARCH_SUMMARY.md** (5 min) — Quick overview
2. **Read TECHNICAL_SUMMARY_CODE_ANALYSIS.md** (10 min) — Decision guide
3. **Check if .NET SDK is available** in project
4. **Decide:** Roslyn-first or Tree-sitter-first?
5. **Implement Phase 7** in next cycle
6. **Expect:** 40-60 new bug patterns detected

---

## Questions Answered

**Q: What can detect semantic bugs that regex can't?**
A: AST parsing, type checking, data flow analysis, control flow analysis, symbolic execution, and LLM reasoning. See comparison matrix in RESEARCH_SUMMARY.md.

**Q: Can we embed these tools in a Python MCP tool?**
A: Yes. Tree-sitter (pip install), Astroid (pip install), Roslyn (subprocess), CodeQL (subprocess), Semgrep (pip install). See integration complexity in TECHNICAL_SUMMARY.

**Q: What's the performance hit?**
A: 10ms (regex) → 110ms (tree-sitter+Roslyn) per file. For 300 files: 3s → 33s. Acceptable trade-off.

**Q: How many new bugs can we detect?**
A: 40-60 additional patterns beyond current 201. That's a 20-30% increase in coverage.

**Q: Which tool should we implement first?**
A: If .NET SDK available: **Roslyn**. If not: **Tree-sitter**. Then add **Astroid** for Python.

---

## References

All references are cited in RESEARCH_CODE_ANALYSIS_STATE_OF_ART.md with clickable links:

- Roslyn analyzers (Microsoft Learn)
- Tree-sitter (GitHub, py-tree-sitter)
- SonarQube, NDepend, PVS-Studio documentation
- Infer (Facebook)
- CodeQL (GitHub)
- Semgrep
- Python tools (Astroid, Mypy, Pyflakes)
- LLM code review patterns
- Control flow & data flow analysis papers

---

**Research completed:** March 29, 2026
**Status:** Ready for implementation planning
**Next action:** Schedule Phase 7 (semantic layer) work
