#!/usr/bin/env python3
"""L1 Pre-flight briefer -- inject terrain contract state before edits.

Usage: python scripts/brief_agent.py
Outputs JSON to stdout.

Reads .planning/contracts/terrain.yaml (if exists) and extracts:
  - contract_bundles: list of bundle summaries (name, status, pass count, stub count)
  - known_bugs: list of known bug descriptions from contract
  - sibling_passes: list of pass names (for cross-pass awareness)
  - orphan_deltas: list of any orphan delta warnings from contract
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List


def _parse_yaml_lightweight(text: str) -> Dict[str, Any]:
    """Minimal YAML-like parser for the terrain contract format.

    This is NOT a full YAML parser. It handles the specific structure of
    terrain.yaml: top-level keys, nested lists with '- key: value' items,
    and quoted string values. For production use, install PyYAML.
    """
    result: Dict[str, Any] = {}
    current_bundle: Dict[str, Any] = {}
    current_bundle_key: str = ""
    current_list_key: str = ""
    current_list: List[Any] = []
    current_item: Dict[str, Any] = {}
    indent_stack: List[int] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())

        # Top-level key (no indent or metadata-level)
        if indent == 0 and ":" in stripped and not stripped.startswith("-"):
            # Save previous bundle
            if current_bundle_key and current_bundle:
                result[current_bundle_key] = current_bundle

            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")

            if val:
                result[key] = val
                current_bundle_key = ""
                current_bundle = {}
            else:
                current_bundle_key = key
                current_bundle = {}
                current_list_key = ""
                current_list = []
            continue

        # Inside a bundle
        if current_bundle_key:
            # Sub-key like "  name:", "  passes:", "  status:"
            if not stripped.startswith("-") and ":" in stripped:
                # Save previous list
                if current_list_key and current_list:
                    current_bundle[current_list_key] = current_list

                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip().strip('"').strip("'")

                if val:
                    current_bundle[key] = val
                    current_list_key = ""
                    current_list = []
                else:
                    current_list_key = key
                    current_list = []
                continue

            # List item
            if stripped.startswith("- "):
                # Save previous item
                if current_item:
                    current_list.append(current_item)
                    current_item = {}

                rest = stripped[2:].strip()
                if ":" in rest:
                    key, _, val = rest.partition(":")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    current_item = {key: val}
                else:
                    current_list.append(rest.strip('"').strip("'"))
                continue

            # Continuation of list item (indented key: value under a -)
            if ":" in stripped and current_item is not None:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                # Handle boolean/numeric
                if val.lower() == "true":
                    val = True
                elif val.lower() == "false":
                    val = False
                elif val.isdigit():
                    val = int(val)
                current_item[key] = val
                continue

    # Flush remaining
    if current_item:
        current_list.append(current_item)
    if current_list_key and current_list:
        current_bundle[current_list_key] = current_list
    if current_bundle_key and current_bundle:
        result[current_bundle_key] = current_bundle

    return result


def load_contract(contract_path: str) -> Dict[str, Any]:
    """Load terrain contract YAML and extract structured data."""
    path = Path(contract_path)
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8", errors="replace")
    return _parse_yaml_lightweight(text)


def extract_briefing(contract: Dict[str, Any]) -> Dict[str, Any]:
    """Extract briefing data from parsed contract."""
    bundles: List[Dict[str, Any]] = []
    known_bugs: List[str] = []
    sibling_passes: List[str] = []
    orphan_deltas: List[str] = []

    for key, value in contract.items():
        if not key.startswith("bundle_") or not isinstance(value, dict):
            continue

        bundle_name = value.get("name", key)
        bundle_status = value.get("status", "unknown")
        passes = value.get("passes", [])
        helpers = value.get("helpers", [])

        stub_count = 0
        pass_names: List[str] = []
        bundle_bugs: List[str] = []

        for p in passes:
            if isinstance(p, dict):
                pname = p.get("name", "")
                if pname:
                    pass_names.append(pname)
                    sibling_passes.append(f"{key}::{pname}")
                if p.get("is_stub", False):
                    stub_count += 1
                bugs = p.get("known_bugs", [])
                if isinstance(bugs, list):
                    for bug in bugs:
                        if isinstance(bug, str):
                            bundle_bugs.append(f"{key}::{pname}: {bug}")
                        elif isinstance(bug, dict):
                            desc = bug.get("description", bug.get("bug", str(bug)))
                            bundle_bugs.append(f"{key}::{pname}: {desc}")

        bundles.append({
            "key": key,
            "name": bundle_name,
            "status": bundle_status,
            "pass_count": len(passes),
            "helper_count": len(helpers) if isinstance(helpers, list) else 0,
            "stub_count": stub_count,
        })
        known_bugs.extend(bundle_bugs)

    return {
        "contract_bundles": bundles,
        "known_bugs": known_bugs,
        "sibling_passes": sibling_passes,
        "orphan_deltas": orphan_deltas,
    }


def main() -> int:
    # Find contract file
    search_paths = [
        ".planning/contracts/terrain.yaml",
        "contracts/terrain.yaml",
        "terrain.yaml",
    ]

    contract_path: str | None = None
    search_roots = [Path(".")] + [Path(*[".."] * i) for i in range(1, 4)]
    for root in search_roots:
        for sp in search_paths:
            full = root / sp
            if full.exists():
                contract_path = str(full)
                break
        if contract_path:
            break

    if contract_path:
        contract = load_contract(contract_path)
        briefing = extract_briefing(contract)
        briefing["_source"] = contract_path
        briefing["_metadata"] = {
            "version": contract.get("metadata", {}).get("version", "unknown")
            if isinstance(contract.get("metadata"), dict)
            else "unknown",
            "total_bundles": contract.get("metadata", {}).get("total_bundles", 0)
            if isinstance(contract.get("metadata"), dict)
            else 0,
        }
    else:
        briefing = {
            "contract_bundles": [],
            "known_bugs": [],
            "sibling_passes": [],
            "orphan_deltas": [],
            "_source": None,
            "_metadata": {"version": "none", "total_bundles": 0},
        }

    print(json.dumps(briefing, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
