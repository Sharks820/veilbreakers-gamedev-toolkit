# Review Plugin

This plugin exposes multi-model review tools to Codex through MCP.

## Configuration

Use one of these modes:

- OpenRouter API mode: set `OPENROUTER_API_KEY`.
- GLM subscription API mode: set `GLM_API_KEY` or `ZAI_API_KEY`. The default base URL is `https://api.z.ai/api/coding/paas/v4`.
- Gemini CLI mode: set `GEMINI_COMMAND` to a local command that reads the prompt from stdin, for example `gemini -p "" --output-format text`. The server adds `--model` automatically if you do not supply one.
- Gemini API mode: set `GEMINI_API_KEY` or `GOOGLE_API_KEY`.

Optional overrides:

- `REVIEW_MODEL` defaults to `qwen/qwen3.6-plus:free`
- `OPENROUTER_MODEL` can override the default OpenRouter model
- `OPENROUTER_BASE_URL` defaults to `https://openrouter.ai/api/v1`
- `OPENROUTER_COMMAND_ARGS` adds extra OpenRouter CLI arguments if you use an OpenRouter CLI shim
- `OPENROUTER_TIMEOUT_SECONDS` controls the OpenRouter request timeout
- `OPENROUTER_RETRY_ATTEMPTS` controls retry count for transient upstream rate limits
- `OPENROUTER_RETRY_BASE_SECONDS` controls exponential backoff base delay
- `OPENROUTER_ALLOW_FALLBACKS` defaults to enabled
- `OPENROUTER_PROVIDER_SORT` defaults to `throughput`
- `GLM_MODEL` defaults to the requested GLM model when you target GLM models
- `GLM_BASE_URL` defaults to `https://api.z.ai/api/coding/paas/v4`
- `GLM_COMMAND` or `ZAI_COMMAND` can override the GLM transport with a local CLI
- `GLM_COMMAND_ARGS` adds extra GLM CLI arguments
- `GLM_TIMEOUT_SECONDS` controls the GLM timeout
- `GLM_RETRY_ATTEMPTS` controls retry count for transient GLM upstream failures
- `GLM_RETRY_BASE_SECONDS` controls exponential backoff base delay
- `GLM_THINKING_TYPE` defaults to `disabled` so reviewer runs return final findings instead of reasoning traces
- `GEMINI_MODEL` defaults to `gemini-3.1-flash-lite-preview` when you target Gemini models
- `GEMINI_BASE_URL` can override the Gemini endpoint
- `GEMINI_COMMAND_ARGS` adds extra Gemini CLI arguments
- `GEMINI_TIMEOUT_SECONDS` controls the Gemini timeout

## Tools

- `review_diff(diff, context, instructions, model, temperature, max_tokens)`
- `review_text(text, instructions, model, temperature, max_tokens)`
- `review_consensus(diff, context, instructions, models, min_agreement, truth_path, save_dir, temperature, max_tokens)`
- `review_history_summary(history_dir, top_n)`

## How To Use It Well

- Break large reviews into scoped segments before sending them to the models.
- Prefer one subsystem or one coherent file group per review run, for example:
  - terrain handlers
  - Unity orchestration
  - worldbuilding
  - tests for one feature slice
- Do not send an entire broad branch diff when it spans unrelated systems unless you also run segmented follow-up reviews.
- Keep the context focused on the segment being reviewed and state the risk you care about most, such as correctness, regressions, missing wiring, or test gaps.
- Use the consensus report as the merge step after segmented runs, not as a substitute for segmentation.

Recommended review models:

- OpenRouter default: `qwen/qwen3.6-plus:free`
- Z.AI GLM turbo secondary: `glm-5.0-turbo` reviewer label, resolved to the direct API model code `glm-5-turbo`
- Gemini CLI peer reviewer: `gemini-3.1-flash-lite-preview`

The consensus tool runs the selected models in parallel and returns a JSON
report containing consensus findings plus model-specific outliers. If you pass
`truth_path`, it also includes precision/recall-style metrics per model and for
the consensus result so you can track true finds, useful non-defect findings,
false positives, and missed bugs over time. Truth entries may include
`category` plus `classification` so "other" findings retain their real subtype
such as `design_concern` or `intentional_change`.
