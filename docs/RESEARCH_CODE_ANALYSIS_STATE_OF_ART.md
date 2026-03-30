# Research: Code Analysis Beyond Regex — State of the Art

**Date:** March 2026
**Context:** Evaluating semantic analysis techniques for detecting bugs, logic errors, and design flaws that regex cannot catch. This research informs design decisions for the VeilBreakers MCP code reviewer.

---

## Executive Summary

Modern code analysis has evolved far beyond simple pattern matching. Today's tools leverage multiple complementary techniques:

1. **AST-based analysis** — Parsing code into structured trees for syntax-aware matching
2. **Semantic analysis** — Control flow graphs (CFGs), data flow analysis (DFA), taint tracking
3. **Symbolic execution** — Exploring multiple execution paths to find bugs
4. **Abstract interpretation** — Sound over-approximation of program behavior
5. **LLM-augmented review** — AI reasoning about code structure and logic

**Key Finding:** There is no silver bullet. Each technique excels at different problem categories, and production tools combine multiple strategies.

---

## 1. AST-Based Static Analysis for C#

### Roslyn Analyzers

**What They Are:**
Roslyn is the .NET Compiler Platform—the C# compiler itself exposed as APIs. Roslyn analyzers hook into the compilation process and inspect code through three layers:

1. **Syntax tree** — Structure of the code (literals, operators, statements)
2. **Semantic model** — Meaning of the code (types, symbols, inheritance)
3. **Symbol information** — What each identifier refers to (class definitions, method calls)

**How They Work:**
- Parse C# code into an AST during compilation
- Inspect syntax and semantic information
- Apply custom rules to detect violations
- Produce warnings/errors with fix suggestions
- Run at design-time (as you type), build-time, or on-demand

**What They Can Catch (vs Regex):**
- Type errors: `typeof(int) == typeof(string)` (always false)
- Call chain analysis: method exists? parameters match? return type used correctly?
- Variable scope: reading uninitialized variables, using variables from wrong scope
- Null reference: tracking nullable vs non-nullable types
- Resource leaks: detecting `using` statement violations
- Inheritance violations: abstract method overrides
- Complex control flow patterns: unreachable code, incomplete switch cases

**Integration:**
- **Language:** C#/.NET only
- **Offline:** Yes, fully offline (part of build process)
- **Embedded:** Yes, via NuGet packages
- **API:** `Microsoft.CodeAnalysis.*` namespaces in .NET projects
- **Maturity:** Production-grade, Microsoft-supported

**Performance:**
- Fast for single-file analysis
- Scales to large projects (used in Visual Studio)
- Incremental analysis on changes

**References:**
- [Microsoft Learn: Code analysis using Roslyn analyzers](https://learn.microsoft.com/en-us/visualstudio/code-quality/roslyn-analyzers-overview)
- [Writing your own Roslyn analyzer](https://medium.com/@denmaklucky/writing-your-own-roslyn-analyzer-enhancing-c-code-analysis-f4b74696cfcd)

---

### SonarQube, NDepend, PVS-Studio

These tools extend basic AST analysis with semantic rules and metrics:

**SonarQube:**
- Open-source, multi-language (20+ languages)
- Detects: bugs, code smells, security vulnerabilities, duplicated code
- Architecture: Parse code → apply rules → report violations
- Can integrate with Roslyn results via plugins
- Server-based (can be cloud or on-premise)

**NDepend:**
- .NET-focused static analyzer
- Specializes in: OOP design patterns, dependencies, breaking changes, mutability analysis
- Uses custom query language (CQLinq) for rule definition
- Can output to SonarQube

**PVS-Studio:**
- C, C++, C#, Java
- Focuses on: null pointer dereferences, buffer overflows, logic errors
- Uses both AST analysis and pattern matching
- Commercial, with Roslyn API integration for C#

**What They Add Beyond Roslyn:**
- Cross-file analysis (whole-program semantics)
- Custom rule frameworks
- Historical tracking (regression detection)
- Metrics (complexity, duplication, coverage)

**Integration Complexity:** Medium-High (require build system integration, separate analysis passes)

---

## 2. Abstract Interpretation and Symbolic Execution

### Core Concepts

**Abstract Interpretation:**
- Computes sound over-approximation of all possible runtime states
- Tracks program behavior as it would execute, but using abstract domains (e.g., "value is positive" instead of exact value)
- Guarantees no false negatives (finds all bugs in its problem space)
- May have false positives

**Symbolic Execution:**
- Explores execution paths treating inputs as symbolic variables
- Solves constraints to determine what inputs trigger specific code paths
- Under-approximates feasible states (may miss some paths)
- Expensive: exponential in number of paths

**Combined Approach:**
Recent research shows synergistic combinations (AISE, etc.) that weave both techniques to balance precision and scalability.

**What They Can Detect:**
- Memory safety violations: use-after-free, buffer overflows
- Null pointer dereferences with path conditions
- Integer overflow, division by zero
- Concurrency bugs: race conditions, deadlocks
- Taint tracking: unsanitized input reaching vulnerable sinks

**For Game Development:**
- Object pooling violations (object used after return to pool)
- Coroutine lifetime bugs (accessing destroyed GameObjects)
- Component dependency violations (accessing component before Awake)
- Event subscription leaks (listener never unregistered)

**References:**
- [Wikipedia: Abstract Interpretation](https://en.wikipedia.org/wiki/Abstract_interpretation)
- [CMU Lecture: Symbolic Execution](https://www.cs.cmu.edu/~aldrich/courses/17-355-18sp/notes/notes14-symbolic-execution.pdf)

---

### Facebook Infer

**What It Is:**
Industrial-strength static analyzer from Facebook (now Meta), used in production at scale.

**Architecture:**
1. **Capture phase:** Translate source code to intermediate representation (SIL, based on Separation Logic)
2. **Analysis phase:** Apply abstract interpretation using bi-abduction (decompose procedures independently)
3. **Report phase:** Output findings with evidence traces

**How It Works:**
- Converts all code (Java, C, C++, Objective-C) to SIL intermediate language
- Uses Separation Logic to reason about memory
- Analyzes procedures independently (scalable to large codebases)
- Incremental: only re-analyzes changed files
- Catches bugs without running the code

**What It Can Find:**
- Memory leaks, null pointer dereferences
- Resource ownership violations
- Integer overflow
- Deadlocks

**For C#/Unity:**
Infer# is a port targeting .NET/C#, but less mature than core Infer.

**Integration:** Requires translation to SIL; not easily embedded in Python tool

**Maturity:** Production-grade, used at Meta

**References:**
- [Facebook Infer GitHub](https://github.com/facebook/infer)
- [Scaling Static Analyses at Facebook (CACM)](https://cacm.acm.org/research/scaling-static-analyses-at-facebook/)

---

## 3. Semantic Analysis: Control Flow & Data Flow

### Concepts

**Control Flow Graph (CFG):**
- Node = basic block (straight-line code)
- Edge = possible jump (branch, loop, exception)
- Enables: loop detection, unreachable code, dominance analysis

**Data Flow Analysis:**
- Tracks how values propagate through the program
- Detects: uninitialized variables, dead assignments, variables used but never set
- Can track: definitions, uses, live variables, reaching definitions

**Taint Tracking:**
- Special case of data flow analysis
- Marks untrusted input (source) and tracks where it flows
- Detects if it reaches vulnerable operation (sink) without sanitization
- Example: HTTP parameter → SQL query without escaping

**What They Can Detect:**
- **Logic bugs:** variable set but never read; read but never set
- **Security:** injection vulnerabilities, path traversal, TOCTOU (time-of-check-time-of-use)
- **Concurrency:** data races (with additional thread-awareness)
- **Game dev:** shader variable set twice without use, entity destroyed then referenced

**References:**
- [Semantic Designs: Control and Data Flow Analysis](https://www.semanticdesigns.com/Products/DMS/FlowAnalysis.html)
- [GeeksforGeeks: Data Flow Analysis in Compiler](https://www.geeksforgeeks.org/data-flow-analysis-compiler/)
- [Detecting Condition-Related Bugs with CFG Neural Networks](https://dl.acm.org/doi/10.1145/3597926.3598142)

---

## 4. CodeQL (GitHub Advanced Security)

### What It Is

GitHub's industrial-strength code analysis engine. Used to secure GitHub.com itself.

**Architecture:**
1. **Parser:** Convert source code to Abstract Syntax Tree
2. **Relational model:** Convert AST to queryable database
3. **Query language:** QL (declarative query language, like Prolog)
4. **Dataflow library:** Cross-file, cross-function tracking

**How It Works:**
- Parse code into queryable relations (predicates)
- Write queries in QL to express bugs/vulnerabilities
- Queries can express: data flow, control flow, call chains, type relationships
- Run on entire codebase; answer is set of matching code locations

**Supported Languages:**
- Actively maintained: C/C++, C#, Go, Java, JavaScript, Python, Ruby
- Community: TypeScript, Swift, and others

**What It Can Find:**
- **Local data flow:** within a function, track value through assignments
- **Global data flow:** across functions and files with taint tracking
- **Control flow patterns:** unreachable code, impossible conditions
- **Type analysis:** type mismatches, null dereferences
- **API misuse:** calling methods in wrong order, missing error checks
- **Complex vulnerability patterns:** e.g., SQL injection through multiple file boundaries

**Data Flow Capabilities:**
- **Local dataflow:** Same function, precise but limited
- **Global dataflow:** Multiple functions and files, less precise but more powerful
- **Taint tracking:** Tracks input → processing → sink
- **Flow labels:** Different taint categories (SQL, HTML, etc.)

**Example Queries:**
- Find all calls to `execute()` where input comes from user without validation
- Find all `File.Open()` calls where path is constructed from user input
- Find all SQL queries that concatenate user strings

**Integration with Python Tool:**
- GitHub provides CodeQL CLI (command-line)
- Can invoke from Python via subprocess
- Queries are YAML + QL (text files)
- **Limitation:** Requires creating/maintaining QL queries (steep learning curve)

**Maturity:** Production-grade, battle-tested on GitHub.com

**Cost:** Free for public repositories; paid for private

**References:**
- [CodeQL GitHub](https://github.com/github/codeql)
- [About data flow analysis in CodeQL](https://codeql.github.com/docs/writing-codeql-queries/about-data-flow-analysis/)
- [CodeQL queries for C#](https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-csharp/)

---

## 5. Semgrep

### What It Is

Open-source semantic code scanner with pattern matching that understands code structure, not just text.

**Philosophy:**
"Semantic grep"—search code using patterns that look like code itself, not regex.

**How It Works:**
1. Parse code into AST
2. Match patterns (expressed as code snippets) against AST
3. Apply user-defined or prebuilt rules
4. Report matches with severity/metadata

**Supported Languages:**
30+ including Python, C#, Go, Java, JavaScript, TypeScript, Rust, C/C++, Ruby, Swift, Kotlin, and more.

**What It Can Find:**
- **Security:** SQL injection, XSS, CSRF, insecure deserialization, hardcoded secrets
- **Code quality:** Anti-patterns, API misuse, performance issues
- **Compliance:** OWASP, CWE, regulatory patterns
- **Custom rules:** Write domain-specific checks

**What It Can Match (vs Regex):**
- Operator precedence: `a + b * c` (structure-aware)
- Function calls across multiple lines
- Method chaining: `foo().bar().baz()`
- Variable scope: `x = 1; if (cond) { use(x); }` (scope-aware)
- Type context: find only `String.concat()`, not any `concat()`

**Pattern Syntax Example:**
```yaml
# Find user input going to SQL query
- pattern-either:
    - patterns:
        - pattern: $DB.query($QUERY)
        - pattern-where: user_input($QUERY)
```

**Two Editions:**

**Semgrep Community Edition (CE):**
- Open source (LGPL)
- Intra-file analysis (single file)
- Pattern matching + basic data flow
- 30+ language support
- Can run locally, code never leaves machine
- Performance: seconds to minutes per file

**Semgrep Pro/Code:**
- Paid offering
- Cross-file analysis (inter-procedural)
- Full taint tracking
- Dataflow tracing across function calls and files
- Higher accuracy, fewer false positives
- Can track: user input → processing → dangerous sink across files

**For Game Development:**
Could detect:
- Object pooling violations: `pool.Return(obj); use(obj);`
- Component lifecycle: accessing component before Awake
- Event listener leaks: subscribing without unsubscribing

**Integration with Python:**
- **CLI:** Invoke `semgrep` command-line tool from subprocess
- **Python SDK:** Community SDK available (third-party)
- **Rules:** Write as YAML files (no programming required)
- **Offline:** Yes, fully offline for CE
- **Cost:** Free (CE) or subscription (Pro)

**Maturity:** Production-grade, used by many enterprises

**Limitations:**
- CE has limited dataflow (intra-file only)
- No path sensitivity: all execution paths considered feasible
- No pointer/shape analysis: aliasing missed in non-trivial cases
- No array element tracking

**References:**
- [Semgrep GitHub](https://github.com/semgrep/semgrep)
- [Rule pattern syntax](https://semgrep.dev/docs/writing-rules/pattern-syntax)
- [Semgrep dataflow overview](https://semgrep.dev/docs/writing-rules/data-flow/data-flow-overview)
- [Cross-file analysis with Pro Engine](https://semgrep.dev/docs/semgrep-code/semgrep-pro-engine-data-flow)

---

## 6. Tree-sitter

### What It Is

Incremental parsing library and grammar system. Parses code without requiring a language compiler.

**Key Property:** Language-agnostic, C runtime, no dependencies, easily embedded.

**How It Works:**
1. Define grammar in tree-sitter's grammar language
2. Compile to C parser
3. Parse code → Concrete Syntax Tree (CST)
4. Query with pattern matching

**C# Support:**
- Official C# grammar available (GitHub: tree-sitter/tree-sitter-c-sharp)
- Based on Roslyn grammar with adaptations
- No .NET SDK required
- Supports C# 1.0 through 13.0

**Comparison to Roslyn:**
| Aspect | Roslyn | Tree-sitter |
|--------|--------|-------------|
| **Dependency** | Requires .NET SDK | No dependencies |
| **Semantic info** | Full type information | Structure only |
| **Languages** | C# only | 30+ languages |
| **Incremental** | Limited | Excellent |
| **Error recovery** | Good | Excellent |
| **For game dev** | Better (full semantics) | Sufficient (structure) |

**Python Bindings:**
- `py-tree-sitter` package on PyPI
- No external dependencies (wheels provided)
- Easy to use: parse, walk tree, query patterns

**What It Can Find:**
- **Structure patterns:** function definitions, class hierarchies, imports
- **Naming violations:** PascalCase vs camelCase
- **Code style:** indentation, bracket placement
- **Simple control flow:** nested loops, deep indentation
- **NOT:** type errors, data flow, semantic violations

**Not Suitable For:**
- Detecting null pointer dereferences
- Type mismatches
- Cross-file dependencies
- Taint tracking

**Integration with Python:**
Excellent. Easy to embed, query syntax is straightforward.

**Maturity:** Mature, used in production (GitHub's code viewer, various IDEs)

**References:**
- [Tree-sitter C# grammar](https://github.com/tree-sitter/tree-sitter-c-sharp)
- [py-tree-sitter documentation](https://tree-sitter.github.io/py-tree-sitter/)
- [Tree-sitter Python guide](https://til.simonwillison.net/python/tree-sitter)

---

## 7. Python Code Analysis Tools

### Built-in AST Module

**Capabilities:**
- Parse Python source into Abstract Syntax Tree
- Walk tree, inspect nodes (function defs, assignments, calls)
- Extract type comments (PEP 484)
- Fully offline, no dependencies

**Limitations:**
- No semantic information (can't resolve names, types)
- No control/data flow
- Limited to Python syntax validation

**Use Case:** Structural analysis (find all classes, functions, imports)

### Astroid (Pylint Foundation)

**What It Is:**
Enhanced AST library used by Pylint.

**Capabilities:**
- Extends Python AST with semantic information
- Limited type inference
- Tracks scopes, name resolution
- Detects: unused variables, undefined names, duplicate code

**Limitations:**
- No full type analysis (limited inference)
- Single-file scope
- Slower than regex (but more accurate)

### Mypy

**What It Is:**
Optional static type checker for Python.

**Capabilities:**
- Type inference from annotations and code patterns
- Detects: type mismatches, attribute errors, missing returns
- Respects PEP 484 type hints

**Limitations:**
- Requires type annotations to be effective
- No data flow beyond types
- Single-file scope

### Pyflakes

**What It Is:**
Fast, lightweight code checker.

**Capabilities:**
- Detects: unused imports, undefined names, redefined variables
- Fast (parses once, checks immediately)

**Limitations:**
- No type checking
- Limited to obvious mistakes
- Less comprehensive than Pylint

**For Game Development:**
- Astroid for unused variables, undefined names
- Mypy for type safety (with type hints)
- Both are insufficient for semantic game dev bugs (coroutine misuse, component lifecycle)

**References:**
- [Astroid documentation](https://pylint.pycqa.org/projects/astroid/en/latest/)
- [Mypy documentation](https://www.mypy-lang.org/)

---

## 8. LLM-Augmented Code Review

### Architecture Pattern

Many teams are combining traditional static analysis with LLM (Claude, GPT-4) for code review:

```
Code Diff
  ↓
Extract Changed Lines
  ↓
Run Linters (Pylint, etc.)
  ↓
Feed to LLM: [code diff] + [lint output] + [team standards]
  ↓
LLM Analyzes: logic, performance, maintainability, security
  ↓
Classify Issues: Red (block), Yellow (warning), Green (OK)
  ↓
Post Review to PR
```

### What LLMs Can Catch (vs Pure Static Analysis)

**Strengths:**
- Logic errors that compile but produce wrong results
- Missing edge cases (what if input is null, empty, negative?)
- Performance bottlenecks (implicit quadratic loops)
- Maintainability issues (confusing variable names, missing abstractions)
- Documentation gaps
- Architectural violations (mixing concerns)
- Domain-specific issues (game dev: GameObject lifecycle, serialization, pooling)

**Weaknesses:**
- Can hallucinate findings (false positives)
- Expensive (cloud API costs)
- Slow (seconds per review)
- Can miss obvious bugs (not trained on latest patterns)
- Context limited (token budget)

### Best Practices

1. **Hybrid approach:** Static analysis for high-precision findings, LLM for reasoning
2. **Gate-keeping:** LLMs should not block merges alone; flag for human review
3. **Agentic loops:** Let LLM ask for clarification, request full function context
4. **Taxonomy:** Categorize findings (bug, style, performance, security) separately
5. **Cost control:** Use cheaper models (Claude Haiku) for high-volume, fallback to Opus for nuanced issues

### For VeilBreakers Toolkit

**Opportunity:**
- Use static analysis for high-precision findings (Roslyn for C#, Astroid for Python)
- Use Claude for semantic reasoning (Are these lines reachable? Does this logic make sense?)
- Avoid false positives by requiring confidence thresholds

**Challenge:**
- LLM may not understand VeilBreakers-specific patterns (ability synergy system, corruption mechanics)
- Mitigate: seed LLM with domain knowledge (provide ruleset or documentation)

**References:**
- [DEV Community: Code review with private LLM](https://dev.to/rokicool/code-review-with-private-llm-in-pipeline-simple-28eb)
- [Medium: LLM-Powered Code Review in Azure DevOps](https://medium.com/@darshan.innovation/automated-code-reviews-with-llms-in-azure-devops-for-python-and-or-pyspark-projects-35531284e611)
- [ProjectDiscovery: AI code review can't catch everything](https://projectdiscovery.io/blog/ai-code-review-vs-neo)

---

## 9. Emerging: LLM-Based Semantic Analysis (FalconEYE)

### Concept

Pure LLM-based code scanning without pattern matching.

**FalconEYE Architecture:**
1. **Context enrichment:** Retrieve similar code patterns from codebase (RAG)
2. **LLM analysis:** Code is analyzed by local LLM for security/logic issues
3. **Enrichment loop:** Findings sent back to LLM with full code for details
4. **Output:** Line numbers, vulnerable code, exploit description, fixes

**Advantages:**
- Understands business logic, architectural patterns
- Detects context-aware vulnerabilities (knows how data is used)
- No pattern matching overhead

**Disadvantages:**
- Very expensive (LLM inference per file)
- Can hallucinate findings
- Slow (not real-time)
- Not deterministic

**Maturity:** Research/early-stage; FalconEYE is proof-of-concept

**For Game Development:**
- Could understand "this async method could be called after scene unload"
- Could understand "this component expects to be initialized in Awake but is being used in OnEnable"
- Would require game development knowledge injection (docs, examples)

**References:**
- [FalconEYE GitHub](https://github.com/FalconEYE-ai/FalconEYE)
- [SecureFalcon Paper](https://arxiv.org/abs/2307.06616)

---

## 10. Comparison Matrix: Tools and Their Capabilities

| Tool | Languages | Local Data Flow | Global Data Flow | Type Analysis | Performance | Offline | Embed in Python | Maturity |
|------|-----------|---|---|---|---|---|---|---|
| **Roslyn** | C# only | ✓ | ✓ | ✓✓ | Fast | Yes | Via .NET SDK | Production |
| **SonarQube** | 20+ | ✓ | ✓ | ✓ | Medium | Server | Yes (API) | Production |
| **Infer** | Java, C/C++, ObjC | ✓ | ✓✓ | ✓ | Fast (incremental) | Yes | Difficult | Production |
| **CodeQL** | 6 active | ✓ | ✓✓ | ✓ | Slow (thorough) | Yes | CLI invocation | Production |
| **Semgrep** | 30+ | ✓ | ✓ (Pro only) | ✓ | Very fast | Yes | CLI/SDK | Production |
| **Tree-sitter** | 30+ | ✓ (structure) | ✗ | ✗ | Very fast | Yes | ✓✓ | Mature |
| **Mypy** | Python | ✓ | Limited | ✓ (types) | Fast | Yes | ✓ | Production |
| **Astroid** | Python | ✓ | Limited | Limited | Fast | Yes | ✓ | Production |
| **LLM (Claude)** | All | Reasoning | Reasoning | Reasoning | Slow | No (API) | ✓ | New |

---

## 11. Recommended Architecture for VeilBreakers Code Reviewer

### Three-Tier Approach

**Tier 1: Fast, High-Precision (Tree-sitter + AST)**
- Parse C# with tree-sitter (no .NET SDK needed)
- Parse Python with built-in ast module
- Detect: naming violations, structural issues, obvious style problems
- **Cost:** Milliseconds per file
- **False positives:** Very low

**Tier 2: Semantic Analysis (Roslyn for C#, Astroid for Python)**
- C#: Invoke Roslyn API (requires .NET project in same repo)
- Python: Use astroid for name resolution, scope analysis
- Detect: undefined variables, unused imports, undefined names, simple type mismatches
- **Cost:** Seconds per file
- **False positives:** Low

**Tier 3: Reasoning (Claude API, gated)**
- Use for complex patterns (control flow, logic bugs)
- Provide context: function code, call sites, documentation
- Gate behind confidence threshold (only flag uncertain/complex issues)
- **Cost:** Expensive (~$0.01 per review)
- **False positives:** Medium (hallucination risk)

### Fallback Strategy

If .NET SDK not available (Roslyn not accessible):
- Use tree-sitter + semantic analysis of AST directly
- Will lose type information but retain structural analysis
- Suitable for quick scans, CI/CD integration

### Pattern Database

Build curated rule database for game development:
- **Unity patterns:** Component lifecycle (Awake/OnEnable/Start), coroutine misuse, GameObject destruction
- **Ability system:** Synergy validation, cooldown tracking, corruption tier checks
- **Serialization:** SerializeField usage, scene references in persistent objects

---

## 12. What Regex Fundamentally Cannot Catch

**Can't Detect:**
1. **Scope violations:** Variable used outside scope, accessed in wrong function
2. **Type mismatches:** Parameter type doesn't match argument type
3. **Control flow:** Code is unreachable, condition always true/false
4. **Data flow:** Uninitialized variable used, defined but never read
5. **Resource leaks:** File opened, never closed (across multiple files)
6. **Null safety:** Pointer dereferenced after null check
7. **Concurrency:** Race conditions, deadlock patterns
8. **API misuse:** Methods called in wrong order, missing initialization

**Example:**
```csharp
// Regex cannot detect this bug:
var config = GetConfigOrNull();
DoSomething(config.Value);  // ← NullReferenceException if config is null
```

Regex can match the pattern `DoSomething(.*\.)` but cannot understand that `config` might be null.

---

## 13. Performance Characteristics

| Approach | Per-File Time | Codebase Time | Memory |
|----------|---|---|---|
| Regex | 10ms | 10s (1000 files) | Minimal |
| Tree-sitter | 50ms | 50s (1000 files) | Low |
| Roslyn | 100ms | 100s+ | Medium |
| CodeQL | 5s+ | Hours+ | High |
| Semgrep | 200ms | 200s (1000 files) | Medium |
| LLM (Claude) | 2s+ | Days+ | API cost |

**For typical VeilBreakers project (300 files):**
- **Fast tier:** 5-10 seconds
- **Semantic tier:** 30-50 seconds
- **Full analysis:** 10+ minutes
- **With LLM:** Hours (and expensive)

---

## Recommendations

### For VeilBreakers Code Reviewer (Next Phase)

1. **Implement Tier 1 first:** Tree-sitter for C# and Python (fast, no .NET requirement)
2. **Add Tier 2:** If .NET SDK available, plug in Roslyn; otherwise, enhance tree-sitter with manual semantic rules
3. **Reserve Tier 3:** For future (Claude-based refinement when specific bugs are hard to categorize)
4. **Build pattern database:** Encode VeilBreakers-specific rules (component lifecycle, ability system, etc.)

### Open Questions to Investigate

1. **Roslyn from Python:** Can we invoke Roslyn from a Python subprocess? (Likely yes, via `dotnet` CLI)
2. **AST-based dataflow:** How much can we achieve with manual CFG/DFA on tree-sitter output?
3. **Semgrep for game dev:** Can we express VeilBreakers patterns in Semgrep YAML?
4. **CodeQL for C#:** Does GitHub maintain good C# queries for game-dev-specific bugs?

### Tools Worth Piloting

1. **Semgrep Community:** Easy integration, fast, supports both C# and Python
2. **Roslyn (if .NET SDK available):** Gold standard for C#
3. **Mypy + Astroid (for Python):** Mature, well-integrated

---

## References

### Roslyn and .NET
- [Microsoft: Roslyn analyzers overview](https://learn.microsoft.com/en-us/visualstudio/code-quality/roslyn-analyzers-overview)
- [Medium: Writing your own Roslyn analyzer](https://medium.com/@denmaklucky/writing-your-own-roslyn-analyzer-enhancing-c-code-analysis-f4b74696cfcd)
- [Microsoft: Roslyn SDK tutorials](https://learn.microsoft.com/en-us/dotnet/csharp/roslyn-sdk/tutorials/how-to-write-csharp-analyzer-code-fix)

### SonarQube, NDepend, PVS-Studio
- [PVS-Studio Blog: Roslyn-based analyzer creation](https://medium.com/pvs-studio/creating-roslyn-api-based-static-analyzer-for-c-c0d7c27489f9)
- [NDepend integration with SonarQube](https://www.ndepend.com/docs/sonarqube-integration-ndepend)

### Abstract Interpretation & Symbolic Execution
- [Wikipedia: Abstract interpretation](https://en.wikipedia.org/wiki/Abstract_interpretation)
- [CMU: Symbolic execution lecture](https://www.cs.cmu.edu/~aldrich/courses/17-355-18sp/notes/notes14-symbolic-execution.pdf)
- [Stanford: Symbolic execution with abstraction](https://cs.stanford.edu/people/saswat/research/SymExAbstraction.pdf)

### Facebook Infer
- [Infer GitHub](https://github.com/facebook/infer)
- [CACM: Scaling Static Analyses at Facebook](https://cacm.acm.org/research/scaling-static-analyses-at-facebook/)

### CodeQL
- [CodeQL GitHub](https://github.com/github/codeql)
- [CodeQL: About data flow analysis](https://codeql.github.com/docs/writing-codeql-queries/about-data-flow-analysis/)
- [CodeQL: C# data flow guide](https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-csharp/)

### Semgrep
- [Semgrep GitHub](https://github.com/semgrep/semgrep)
- [Semgrep: Rule pattern syntax](https://semgrep.dev/docs/writing-rules/pattern-syntax)
- [Semgrep: Dataflow analysis](https://semgrep.dev/docs/writing-rules/data-flow/data-flow-overview)
- [Semgrep: Cross-file analysis (Pro)](https://semgrep.dev/docs/semgrep-code/semgrep-pro-engine-data-flow)

### Tree-sitter
- [Tree-sitter GitHub](https://github.com/tree-sitter/tree-sitter)
- [Tree-sitter C# grammar](https://github.com/tree-sitter/tree-sitter-c-sharp)
- [py-tree-sitter documentation](https://tree-sitter.github.io/py-tree-sitter/)
- [Simon Willison: Using tree-sitter with Python](https://til.simonwillison.net/python/tree-sitter)

### Python Analysis
- [Python AST documentation](https://docs.python.org/3/library/ast.html)
- [Astroid documentation](https://pylint.pycqa.org/projects/astroid/en/latest/)
- [Real Python: ast module](https://realpython.com/ref/stdlib/ast/)

### Control Flow & Data Flow
- [Semantic Designs: CFG and DFA](https://www.semanticdesigns.com/Products/DMS/FlowAnalysis.html)
- [GeeksforGeeks: Data flow analysis in compilers](https://www.geeksforgeeks.org/data-flow-analysis-compiler/)
- [ISSTA: Detecting condition-related bugs with CFG neural networks](https://dl.acm.org/doi/10.1145/3597926.3598142)

### LLM-Augmented Review
- [DEV Community: Code review with private LLM](https://dev.to/rokicool/code-review-with-private-llm-in-pipeline-simple-28eb)
- [Medium: LLM code review in Azure DevOps](https://medium.com/@darshan.innovation/automated-code-reviews-with-llms-in-azure-devops-for-python-and-or-pyspark-projects-35531284e611)
- [ProjectDiscovery: AI code review limitations](https://projectdiscovery.io/blog/ai-code-review-vs-neo)

### FalconEYE / SecureFalcon
- [FalconEYE GitHub](https://github.com/FalconEYE-ai/FalconEYE)
- [SecureFalcon Paper (arXiv)](https://arxiv.org/abs/2307.06616)

---

**Document End**
