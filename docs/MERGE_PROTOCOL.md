# 4-Terminal Merge Protocol

## Branch Structure
```
master (Phase 1 committed)
├── audit/rigging        (Terminal 1)
├── audit/animation      (Terminal 2)
├── audit/unity-vfx      (Terminal 3)
└── audit/infrastructure (Terminal 4)
```

## Merge Order (DO THIS SEQUENCE)
Merge in dependency order to minimize conflicts:

1. **Terminal 4 (infrastructure)** first — touches shared infra, no deps on others
2. **Terminal 1 (rigging)** second — rig templates must exist before animation
3. **Terminal 2 (animation)** third — animations consume T1 rigs, produce for T3
4. **Terminal 3 (unity-vfx)** last — consumes T2 timing data and animation conventions

```bash
# Step 1: Merge T4
git checkout master
git merge audit/infrastructure
python -m pytest tests/ --tb=short -q   # must pass
git push origin master

# Step 2: Merge T1
git merge audit/rigging
python -m pytest tests/ --tb=short -q   # must pass
git push origin master

# Step 3: Merge T2
git merge audit/animation
python -m pytest tests/ --tb=short -q   # must pass — fix conflicts if any
git push origin master

# Step 4: Merge T3
git merge audit/unity-vfx
python -m pytest tests/ --tb=short -q   # must pass — fix conflicts if any
git push origin master
```

## Post-Merge: Handler Registration
After all 4 branches are merged, integrate the registration files:

1. Read `docs/T1_REGISTRATIONS.md`, `T2_REGISTRATIONS.md`, `T4_REGISTRATIONS.md`
2. Add all listed imports and COMMAND_HANDLERS entries to `blender_addon/handlers/__init__.py`
3. Add all listed action Literals to `blender_server.py` tool definitions
4. Run full test suite one final time

## Post-Merge: Gap Files
Check for cross-terminal gaps:
- `docs/GAPS_FROM_T1.md`
- `docs/GAPS_FROM_T2.md`
- `docs/GAPS_FROM_T3.md`
- `docs/GAPS_FROM_T4.md`

Any gaps noted by one terminal about another terminal's files should be addressed now.

## Post-Merge: Final Validation
```bash
cd Tools/mcp-toolkit
python -m pytest tests/ --tb=short -q          # all tests pass
python -m pytest tests/ --cov --cov-report=term-missing -q  # coverage report
```

## Conflict Resolution
If a merge produces conflicts:
- File ownership is defined in each TERMINAL_*.md doc
- The terminal that OWNS the file gets final say on its content
- For `handlers/__init__.py`: combine both sides' additions (they should be in different sections)
- For `blender_server.py`: combine both sides' action Literal additions
