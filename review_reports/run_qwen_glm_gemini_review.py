from pathlib import Path
from veilbreakers_mcp.review_server import review_consensus

diff = Path(r"C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\review_reports\current_terrain_review_diff.patch").read_text(encoding="utf-8")
report = review_consensus(
    diff=diff,
    context="Current branch: feature/terrain-world-foundation. Review the current uncommitted terrain/world changes for real bugs, regressions, missing wiring, stale tests, and behavior gaps. Prefer correctness over style.",
    instructions="Review as a senior engineer. Focus on real bugs/errors/gaps in the patch. Ignore stylistic nits. Call out missing test coverage only when it creates real risk.",
    models=["qwen/qwen3.6-plus:free", "glm-5.0-turbo", "gemini-3.1-flash-lite-preview"],
    min_agreement=2,
    max_tokens=1600,
    save_path=r"C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\review_reports\qwen_glm_gemini_terrain_review_20260405.json",
)
print(report)
