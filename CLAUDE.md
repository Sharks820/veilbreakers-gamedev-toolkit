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
.mcp.json                    # MCP server config (vb-blender, vb-unity)
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

### Tool Selection Priority
1. **Context7** for library/framework questions (not raw web search)
2. **Episodic Memory** before starting any non-trivial task
3. **zread** for understanding external GitHub repos
4. **Web Reader** for fetching specific URLs
5. **Web Search Prime** for current events / recent changes
6. **zai tools** for any visual analysis, screenshots, diagrams
7. **Grep/Glob/Read** for local codebase navigation (always available)

## Planning Files

Phase plans are in `.planning/phases/`. Current project state is in `.planning/STATE.md`. Requirements in `.planning/REQUIREMENTS.md`. Roadmap in `.planning/ROADMAP.md`.
