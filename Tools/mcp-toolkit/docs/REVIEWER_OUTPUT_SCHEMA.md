# Reviewer Output Schema

The CLI emits JSON with this stable top-level shape:

```json
{
  "total_issues": 1,
  "total_collected": 1,
  "critical": 1,
  "high": 0,
  "medium": 0,
  "low": 0,
  "errors_bugs": 1,
  "optimizations": 0,
  "strengthening": 0,
  "hard_correctness": 1,
  "semantic": 0,
  "heuristic": 0,
  "avg_confidence": 75.0,
  "avg_priority": 95.0,
  "review_scope": "production",
  "issues": [
    {
      "rule_id": "PY-SEC-01",
      "severity": "CRITICAL",
      "category": "Security",
      "file": "path/to/file.py",
      "line": 12,
      "description": "eval() usage -- arbitrary code execution risk",
      "fix": "Replace with ast.literal_eval() or redesign.",
      "matched_text": "result = eval(user_input)",
      "finding_type": "BUG",
      "confidence": 95,
      "priority": 95,
      "reasoning": "",
      "layer": "hard_correctness",
      "requires_context": false
    }
  ],
  "agent_brief": "REVIEW SUMMARY ...",
  "files_scanned": 1,
  "files_collected": 1,
  "scan_roots": ["path/to/root"],
  "context_available": false,
  "ast_findings": 0,
  "tool_findings": 0,
  "tools_used": ["ruff"]
}
```

Notes:
- `issues` may be compacted or empty when `--compact` or `--summary-only` is used.
- `patches` and `total_patches` are present when `--fix` is used. Each patch entry includes `file`, `rule_ids`, `applied`, `backup_file`, and a unified `diff`.
- `scan_roots` is relative-display metadata for humans and agents.
- `layer` is one of `hard_correctness`, `semantic`, or `heuristic`.
- `category` is one of `Security`, `Bug`, `Performance`, `Quality`, or `Framework`.
- `finding_type` is one of `ERROR`, `BUG`, `OPTIMIZATION`, or `STRENGTHENING`.

Example fix invocation:

```bash
vb-review . --scope production --profile general --fix
vb-review some_file.py --scope advisory --profile general --fix --apply
```
