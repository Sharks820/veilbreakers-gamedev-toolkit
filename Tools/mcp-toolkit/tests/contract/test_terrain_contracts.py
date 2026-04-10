"""
test_terrain_contracts.py -- pytest suite validating terrain.yaml contract.

Tests:
  - test_contract_yaml_loads: YAML is valid and parseable
  - test_bundle_count_matches_metadata: metadata.total_bundles matches actual count
  - test_pass_files_exist: every claimed file path resolves on disk
  - test_all_pass_functions_exist: every pass has a defined function in its file
  - test_no_stub_passes: no pass has is_stub=True in the contract
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent  # veilbreakers-gamedev-toolkit
CONTRACT_PATH = REPO_ROOT / ".planning" / "contracts" / "terrain.yaml"
HANDLERS_DIR = REPO_ROOT / "Tools" / "mcp-toolkit" / "blender_addon" / "handlers"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _load_contract() -> dict:
    with open(CONTRACT_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _parse_file_ref(file_ref: str) -> tuple[str, int | None]:
    if ":" in file_ref:
        parts = file_ref.rsplit(":", 1)
        try:
            return parts[0], int(parts[1])
        except ValueError:
            return file_ref, None
    return file_ref, None


def _function_exists(source_path: Path, func_name: str) -> bool:
    try:
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
    except (SyntaxError, OSError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return True
    return False


def _bundle_keys(contract: dict) -> list[str]:
    return sorted(k for k in contract if k.startswith("bundle_"))


def _all_passes(contract: dict) -> list[tuple[str, dict]]:
    """Yield (bundle_name, pass_dict) for every pass across all bundles."""
    result = []
    for bkey in _bundle_keys(contract):
        bundle = contract[bkey]
        bname = bundle.get("name", bkey)
        for p in bundle.get("passes", []):
            result.append((bname, p))
    return result


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------
@pytest.fixture(scope="module")
def contract() -> dict:
    return _load_contract()


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------
def test_contract_yaml_loads(contract: dict):
    """The YAML is valid, parseable, and contains metadata."""
    assert contract is not None
    assert "metadata" in contract
    assert "version" in contract["metadata"]


def test_bundle_count_matches_metadata(contract: dict):
    """metadata.total_bundles matches actual bundle count."""
    expected = contract["metadata"]["total_bundles"]
    actual = len(_bundle_keys(contract))
    assert actual == expected, (
        f"metadata.total_bundles={expected} but found {actual} bundle keys: "
        f"{_bundle_keys(contract)}"
    )


def test_pass_files_exist(contract: dict):
    """Every claimed pass file path resolves to a real file on disk."""
    missing = []
    for bname, p in _all_passes(contract):
        filename, _ = _parse_file_ref(p["file"])
        fpath = HANDLERS_DIR / filename
        if not fpath.is_file():
            missing.append(f"{bname}/{p['name']}: {filename}")
    assert not missing, f"Missing files:\n" + "\n".join(f"  - {m}" for m in missing)


def test_all_pass_functions_exist(contract: dict):
    """Every pass has an importable (defined) function in its file."""
    not_found = []
    for bname, p in _all_passes(contract):
        filename, _ = _parse_file_ref(p["file"])
        fpath = HANDLERS_DIR / filename
        if not fpath.is_file():
            continue  # covered by test_pass_files_exist
        if not _function_exists(fpath, p["name"]):
            not_found.append(f"{bname}/{p['name']} not in {filename}")
    assert not not_found, (
        f"Functions not found:\n" + "\n".join(f"  - {n}" for n in not_found)
    )


def test_no_stub_passes(contract: dict):
    """No pass in the contract should have is_stub=True."""
    stubs = []
    for bname, p in _all_passes(contract):
        if p.get("is_stub", False):
            stubs.append(f"{bname}/{p['name']}")
    assert not stubs, f"Stub passes found:\n" + "\n".join(f"  - {s}" for s in stubs)
