# Reviewer Rules

The reviewer ships with profile-aware rule sets:

| Profile | Languages | Purpose |
|---|---|---|
| `general` | Python, C# | General software correctness/security/perf review. |
| `unity` | Python, C# | `general` plus Unity/game-engine specific C# rules and deep checks. |
| `blender` | Python, C# | `general` plus Blender-specific Python rules. |
| `all` | Python, C# | Full internal superset for VeilBreakers. |

Precision status:
- `production` scope is the ship gate. It is tuned to keep only high-confidence hard-correctness findings.
- `advisory` adds semantic rules.
- `strict` adds heuristic rules for deeper review.
- Truth-set benchmarking is still being built; treat any row marked `pending` as not yet benchmark-certified.

Core general rules added in this pass:

| Rule ID | Severity | Layer | Profile | Description | Precision |
|---|---|---|---|---|---|
| `PY-SEC-08` | `HIGH` | `semantic` | `general` | User-controlled path reaches filesystem op without normalization. | pending |
| `PY-SEC-09` | `HIGH` | `semantic` | `general` | Requests call uses user-controlled URL/host. | pending |
| `PY-SEC-10` | `HIGH` | `hard_correctness` | `general` | `render_template_string(...)` with dynamic input. | pending |
| `PY-COR-20` | `HIGH` | `hard_correctness` | `general` | Await while holding a lock. | pending |
| `PY-COR-21` | `MEDIUM` | `semantic` | `general` | Global mutable state updated without obvious lock. | pending |
| `PY-COR-22` | `MEDIUM` | `semantic` | `general` | `asyncio.gather(...)` without local error collection. | pending |
| `PY-PERF-04` | `LOW` | `heuristic` | `general` | Logger f-string eagerly formats disabled log messages. | pending |
| `PY-RES-08` | `MEDIUM` | `semantic` | `general` | `subprocess.Popen(...)` never waited/communicated. | pending |
| `PY-RES-09` | `MEDIUM` | `semantic` | `general` | Requests call without timeout. | pending |
| `PY-COR-23` | `LOW` | `heuristic` | `general` | Optional-style result dereferenced without nearby `None` check. | pending |
| `CS-COR-01` | `MEDIUM` | `semantic` | `general` | `HttpClient` created inside `using`. | pending |
| `CS-COR-02` | `MEDIUM` | `semantic` | `general` | Async method creates `FileStream` without async disposal. | pending |
| `CS-COR-03` | `LOW` | `heuristic` | `general` | Null-forgiving operator without justification comment. | pending |
| `CS-COR-04` | `LOW` | `heuristic` | `general` | Long null-conditional chain hides propagation. | pending |
| `CS-COR-05` | `HIGH` | `hard_correctness` | `general` | `lock` used inside async method. | pending |
| `CS-COR-06` | `HIGH` | `hard_correctness` | `general` | `.Result` or `.Wait()` on a task. | pending |
| `CS-COR-07` | `HIGH` | `semantic` | `general` | Singleton registration captures scoped dependency. | pending |
| `CS-PERF-01` | `MEDIUM` | `semantic` | `general` | `.ToList()` inside a loop. | pending |
| `CS-PERF-02` | `LOW` | `heuristic` | `general` | `.Where(...).Count()` double-enumeration. | pending |
| `CS-SEC-01` | `CRITICAL` | `hard_correctness` | `general` | Raw SQL string concatenation/interpolation. | pending |

Current CLI entry points:
- `python -m veilbreakers_mcp.vb_code_reviewer`
- `vb-review`

Useful examples:

```bash
vb-review . --scope production --profile general
vb-review Assets/Scripts --lang cs --scope strict --profile unity
git diff --unified=0 | vb-review . --lang py --profile general --diff -
cat some_file.py | vb-review --stdin --lang py --profile general
```
