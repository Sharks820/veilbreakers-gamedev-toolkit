# VeilBreakers MCP Toolkit -- Claude Code Instructions

You are AI game development assistant for **VeilBreakers**, a dark fantasy action RPG. You have 37 compound MCP tools (15 Blender, 22 Unity) that give you direct control over both applications.

## Project Structure

```
Tools/mcp-toolkit/           # MCP server source
  src/veilbreakers_mcp/
    blender_server.py        # 15 Blender compound tools
    unity_server.py          # 22 Unity compound tools
  blender_addon/             # Blender socket addon (handlers/)
  tests/                     # pytest suite
.mcp.json                    # MCP server config (vb-blender, vb-unity, vb-review)
.planning/                   # Phase plans, research, state tracking
```

## Tool Architecture

All tools use a **compound pattern**: one tool name per domain, `action` param selects operation. This gives 350 operations across 37 tools.

- **Blender tools** connect via TCP to Blender (localhost:9876). Most mutations return viewport screenshots.
- **Unity tools** generate C# editor scripts, write to Unity project, return `next_steps` for compile+execute.

**Tool documentation is provided via MCP server system-reminder — do not duplicate here.**

## Workflow Rules

1. **Always verify visually** after Blender mutations. Use `blender_viewport` action=`contact_sheet` for thorough review.
2. **Pipeline order**: repair -> UV -> texture -> rig -> animate -> export. Do not skip steps.
3. **Unity two-step**: Tool writes script, you must recompile + execute. Follow `next_steps`.
4. **Game readiness**: Run `blender_mesh` action=`game_check` before export. Run `unity_performance` action=`profile_scene` after setup.
5. **Use seeds** for reproducible environment/worldbuilding generation.
6. **Batch when possible**: `asset_pipeline` action=`batch_process`, `blender_animation` action=`batch_export`.
7. **For terrain/world work, inspect the live Blender toolchain first.** Call `asset_pipeline` with `action="inspect_external_toolchain"` and prefer `agent_contract.workflow_presets.terrain_unity_ready_free` as the default free Unity-ready terrain workflow on this PC.
8. **Do not infer addon availability from installed files alone.** Use the returned `agent_contract.selection`, `workflow_presets`, `warnings`, and `blender_runtime` fields as the source of truth for active Blender capabilities.

## Available MCP Tools & Plugins (USE THESE)

All agents (including GSD subagents) have access to these tools. **Prefer MCP tools over raw Grep/Glob when they fit.**

### Code Navigation & Quality
- **Context7** (`mcp__plugin_context7_context7__resolve-library-id` → `query-docs`): Look up current docs for ANY library/framework/SDK. Use even when you think you know the answer — training data may be stale. Resolve library ID first, then query.
- **zread** (`mcp__zread__get_repo_structure`, `read_file`, `search_doc`): Browse GitHub repo structure, read files, search docs/issues/commits for any public repo.
- **Episodic Memory** (`mcp__plugin_episodic-memory_episodic-memory__search`, `read`): Search past conversations for decisions, solutions, prior art. Use BEFORE starting work to avoid reinventing.

### Web Research
- **Web Search Prime** (`mcp__web-search-prime__web_search_prime`): Web search with domain filtering, recency filters, content size control. Good for current events, recent API changes.
- **Web Reader** (`mcp__web-reader__webReader`): Fetch any URL and convert to markdown. Better than WebFetch for clean content extraction.
- **WebSearch** (built-in): Alternate web search. Include Sources section when using.
- **WebFetch** (built-in): Fetch + AI-process URL content. Use web-reader for raw content, this for summarized.

### Visual Analysis (zai)
- **analyze_image**: General image analysis fallback
- **analyze_video**: Video content analysis (MP4/MOV, 8MB max)
- **analyze_data_visualization**: Charts, graphs, dashboards → insights
- **diagnose_error_screenshot**: Error messages, stack traces → solutions
- **extract_text_from_screenshot**: OCR for code, terminal output, docs
- **ui_to_artifact**: Screenshot → code/prompt/spec/description
- **ui_diff_check**: Compare expected vs actual UI screenshots
- **understand_technical_diagram**: Architecture, flowcharts, UML, ER diagrams

### Game Development (VeilBreakers MCP)
- **vb-blender** (16 tools): Direct Blender control via TCP. See `.claude/skills/vb-mcp-tools/SKILL.md`.
- **vb-unity** (22 tools): Unity C# editor script generation. Always follow `next_steps`.
- **vb-review** (4 tools): Multi-model code review via Gemini CLI plus OpenRouter. Use `review_consensus` for side-by-side reviewer runs and metrics.

### Tool Selection Priority
1. **Context7** for library/framework questions (not raw web search)
2. **Episodic Memory** before starting any non-trivial task
3. **zread** for understanding external GitHub repos
4. **Web Reader** for fetching specific URLs
5. **Web Search Prime** for current events / recent changes
6. **zai tools** for any visual analysis, screenshots, diagrams
7. **Grep/Glob/Read** for local codebase navigation (always available)

## Quality Infrastructure

The project has a 7-layer defense-in-depth system for terrain code quality:

- **L0**: Contract YAML (`.planning/contracts/terrain.yaml`) — machine-readable source of truth
- **L1**: Pre-flight briefer (`scripts/brief_agent.py`) — run before touching terrain_*.py
- **L2**: AST lint (`scripts/quality_lint.py`) — detects stubs, orphan deltas, frozen-mutable, silent-swallow
- **L3**: Contract tests (`tests/contract/`) — auto-generated from YAML
- **L4**: Honesty lint (`scripts/honesty_lint.py`) — cross-checks plan claims against code
- **L5**: Test substance lint (`scripts/test_substance_lint.py`) — classifies tests as REAL/SHALLOW/TAUTOLOGICAL
- **L6**: Integration gate (`tests/integration/test_full_terrain_pipeline.py`) — end-to-end pipeline

### Before Committing Terrain Code
```bash
cd Tools/mcp-toolkit
python scripts/quality_lint.py blender_addon/handlers/  # Must be <=16 findings
python -m pytest tests/ -q --tb=line                      # Must pass (20,900+)
```

### Before Touching terrain_*.py
```bash
python scripts/brief_agent.py  # Shows contract state, known bugs, sibling passes
```

### After Writing Tests
```bash
python scripts/test_substance_lint.py tests/  # real_ratio must be >= 0.50
```

### Code Reviewer
```bash
PYTHONPATH=src python src/veilbreakers_mcp/vb_code_reviewer.py <path> --scope advisory --profile general
```

Profiles: `general` (Python+C# core), `blender` (+ BLE rules), `unity` (+ Unity rules), `all` (everything).

## Planning Files

Phase plans are in `.planning/phases/`. Current project state is in `.planning/STATE.md`. Requirements in `.planning/REQUIREMENTS.md`. Roadmap in `.planning/ROADMAP.md`.
