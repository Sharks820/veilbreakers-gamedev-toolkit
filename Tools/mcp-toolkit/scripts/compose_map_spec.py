#!/usr/bin/env python
"""Run the Blender compose_map pipeline from a JSON spec file."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="Path to the map spec JSON file.")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Where to write the compose_map JSON result.",
    )
    parser.add_argument(
        "--capture-viewport",
        action="store_true",
        help="Capture the final viewport screenshot in addition to terrain gate shots.",
    )
    return parser.parse_args()


async def _run(spec_path: Path, output_path: Path, capture_viewport: bool) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))
    from veilbreakers_mcp.blender_server import asset_pipeline

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    result = await asset_pipeline(
        action="compose_map",
        map_spec=spec,
        capture_viewport=capture_viewport,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if (
        isinstance(result, list)
        and len(result) == 1
        and isinstance(result[0], str)
    ):
        serialized = result[0]
    elif isinstance(result, str):
        serialized = result
    else:
        serialized = json.dumps(result, indent=2, default=str)
    output_path.write_text(serialized, encoding="utf-8")
    print(serialized)
    return 0


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args.spec, args.output, args.capture_viewport))


if __name__ == "__main__":
    raise SystemExit(main())
