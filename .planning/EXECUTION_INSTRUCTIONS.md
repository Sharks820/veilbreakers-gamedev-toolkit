# v8.0 Execution Instructions — READ FIRST ON EVERY CONTEXT RESET

## User's Exact Instructions
- Fix ALL 750+ items from MASTER_IMPLEMENTATION_LIST.md
- 5+ Sonnet implementation agents running AT ALL TIMES
- Haiku agent for commits, pushes, memory updates, plan % tracking after every confirmed task
- After EVERY phase: Opus verification scan + Gemini verification scan — if ANY bug found, re-scan until phase is CLEAN on first pass by BOTH agents
- FULLY AUTONOMOUS — no stopping to ask questions
- Continue until rate limited — the ONLY acceptable reason to stop
- Use /gsd:execute-phase for each phase
- Best execution path: fix dependencies BEFORE dependent phases

## Phase Execution Order
1. Test suite overhaul (63% false confidence → real assertions)
2. Camera system (AI needs eyes)
3. Checkpoint system (crash resilience)
4. Core pipeline CRASH/CRITICAL bugs
5. Materials & PBR correctness
6. Building architecture quality
7. Interior system overhaul
8. Style enforcement & weathering
9. Animation, rigging & export/import
10. City mapping, props, terrain & final sweep

## Agent Model Allocation
- **Sonnet** (5+ parallel): Implementation code fixes
- **Opus**: Phase verification scans, quality review
- **Haiku**: Git commits, memory updates, progress tracking
- **Gemini**: Post-phase verification (user runs `gemini -p "scan phase N..."`)

## Key Files
- `.planning/MASTER_IMPLEMENTATION_LIST.md` — ALL 750+ items with checkboxes
- `.planning/research/` — 8 research documents for reference
- `tests/test_integration_pipelines.py` — 62 integration tests (already written)
- `CLAUDE.md` — Project instructions
- Memory: `project_v8_mega_scan.md` — Session summary

## Verification Protocol Per Phase
1. Run all tests: `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q`
2. Launch Opus scan agent on phase files
3. User runs Gemini scan on phase files
4. If ANY issue found → fix → re-scan
5. Only mark phase complete when BOTH Opus AND Gemini pass clean

## Command Prompts for User
After each phase, user should run in a separate terminal:
```
gemini -p "Scan Tools/mcp-toolkit/ for any bugs or errors in [PHASE DOMAIN FILES]. Report every issue found."
```

## RESUME AFTER /CLEAR
On the FIRST message after context clear, say:
```
Read .planning/EXECUTION_INSTRUCTIONS.md and .planning/MASTER_IMPLEMENTATION_LIST.md then continue autonomous execution of v8.0 Phase 1. 5+ Sonnet agents at all times. No questions. Fix everything.
```

## ALREADY IN PROGRESS
- 5 Sonnet agents were launched for Phase 1 Wave 1 before /clear
- They may have completed — check test files for changes
- Run `git status` and `python -m pytest tests/ -x -q` to see current state
- Continue with Phase 1 Wave 2, then Phase 2 (Camera), etc.
- Agent 49+50 confirmed: checkpoint wipes data (14 bugs), 63% tests false confidence
