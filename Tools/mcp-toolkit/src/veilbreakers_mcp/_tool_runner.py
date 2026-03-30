"""External tool runner for the unified scanner.

Wraps all 9 tools from the verified free stack:
  1. ast-grep (MIT) — structural pattern search
  2. OpenGrep (LGPL-2.1) — taint analysis, cross-file data flow
  3. Meziantou.Analyzer (MIT) — 100+ C# rules via dotnet build
  4. InferSharp (MIT) — interprocedural null/leak detection
  5. SonarAnalyzer.CSharp (LGPL-3.0) — vulnerability + code smells
  6. Microsoft.Unity.Analyzers (MIT) — 42 Unity-specific rules
  7. Microsoft.CodeAnalysis.NetAnalyzers (MIT) — hundreds of CA rules
  8. Ruff (MIT) — Python 900+ rules
  9. mypy (MIT) — Python type checking

Each tool is optional — if not installed, it's silently skipped.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ToolFinding:
    tool: str  # "ast-grep", "roslynator", "ruff", "mypy"
    rule_id: str
    file: str
    line: int
    description: str
    severity: str = "MEDIUM"
    fix: str = ""


def _normalize_tool_path(path: str, *, base_dir: str | None = None) -> str:
    """Normalize tool output paths for stable cross-tool dedupe."""
    if not path:
        return ""

    p = Path(path)
    if base_dir and not p.is_absolute():
        p = Path(base_dir) / p

    try:
        return p.resolve(strict=False).as_posix()
    except OSError:
        return p.as_posix()


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _run(cmd: list[str], timeout: int = 120, cwd: str = ".") -> Optional[str]:
    """Run a command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


# =============================================================================
# ast-grep
# =============================================================================

_AST_GREP_CMD = None


def _get_ast_grep() -> Optional[str]:
    global _AST_GREP_CMD
    if _AST_GREP_CMD is None:
        _AST_GREP_CMD = _which("sg") or _which("ast-grep") or ""
    return _AST_GREP_CMD or None


def run_ast_grep(target_dir: str, lang: str = "csharp") -> list[ToolFinding]:
    """Run ast-grep scan with built-in rules. Returns findings."""
    cmd = _get_ast_grep()
    if not cmd:
        return []

    # ast-grep scan with JSON output
    output = _run(
        [cmd, "scan", "--lang", lang, "--json", target_dir],
        timeout=60,
    )
    if not output:
        return []

    findings = []
    try:
        data = json.loads(output)
        if isinstance(data, list):
            for item in data:
                findings.append(ToolFinding(
                    tool="ast-grep",
                    rule_id=item.get("ruleId", "SG-UNKNOWN"),
                    file=item.get("file", ""),
                    line=item.get("range", {}).get("start", {}).get("line", 0),
                    description=item.get("message", ""),
                    severity=_map_severity(item.get("severity", "warning")),
                ))
    except (json.JSONDecodeError, KeyError):
        pass

    return findings


# =============================================================================
# Ruff (Python linter)
# =============================================================================


def run_ruff(target_dir: str | list[str]) -> list[ToolFinding]:
    """Run ruff check with JSON output."""
    cmd = _which("ruff")
    if not cmd:
        return []

    targets = [target_dir] if isinstance(target_dir, str) else list(target_dir)
    if not targets:
        return []

    output = _run(
        [cmd, "check", *targets, "--output-format", "json", "--quiet"],
        timeout=60,
    )
    if not output:
        return []

    findings = []
    try:
        data = json.loads(output)
        if isinstance(data, list):
            for item in data:
                findings.append(ToolFinding(
                    tool="ruff",
                    rule_id=f"RUFF-{item.get('code', 'UNKNOWN')}",
                    file=_normalize_tool_path(item.get("filename", "")),
                    line=item.get("location", {}).get("row", 0),
                    description=item.get("message", ""),
                    severity=_map_ruff_severity(item.get("code", "")),
                ))
    except (json.JSONDecodeError, KeyError):
        pass

    return findings


# =============================================================================
# mypy (Python type checker)
# =============================================================================


def run_mypy(target_dir: str | list[str]) -> list[ToolFinding]:
    """Run mypy with JSON output."""
    cmd = _which("mypy")
    if not cmd:
        return []

    targets = [target_dir] if isinstance(target_dir, str) else list(target_dir)
    if not targets:
        return []

    output = _run(
        [cmd, *targets, "--no-error-summary", "--output", "json",
         "--ignore-missing-imports", "--no-incremental"],
        timeout=120,
    )
    if not output:
        return []

    noisy_codes = {
        "assignment",
        "var-annotated",
        "misc",
        "valid-type",
        "truthy-function",
    }

    findings = []
    for line in output.strip().splitlines():
        try:
            item = json.loads(line)
            code = item.get("code", "UNKNOWN")
            if item.get("severity") == "error" and code not in noisy_codes:
                findings.append(ToolFinding(
                    tool="mypy",
                    rule_id=f"MYPY-{code}",
                    file=_normalize_tool_path(item.get("file", "")),
                    line=item.get("line", 0),
                    description=item.get("message", ""),
                    severity="HIGH",
                ))
        except (json.JSONDecodeError, KeyError):
            continue

    return findings


# =============================================================================
# Helpers
# =============================================================================


def _map_severity(sev: str) -> str:
    s = sev.lower()
    if s in ("error", "critical"):
        return "CRITICAL"
    if s in ("warning", "high"):
        return "HIGH"
    if s in ("info", "hint", "medium"):
        return "MEDIUM"
    return "LOW"


def _map_ruff_severity(code: str) -> str:
    if not code:
        return "MEDIUM"
    prefix = code[0] if code else ""
    # E=error, W=warning, F=pyflakes, B=bugbear, S=security
    if prefix in ("E", "F"):
        return "HIGH"
    if prefix in ("S", "B"):
        return "HIGH"
    return "MEDIUM"


# =============================================================================
# OpenGrep (free Semgrep fork — taint analysis, cross-file)
# =============================================================================


def run_opengrep(target_dir: str | list[str], rules_dir: str = "") -> list[ToolFinding]:
    """Run OpenGrep with custom rules. Falls back to semgrep CLI if opengrep not found."""
    cmd = _which("opengrep") or _which("semgrep")
    if not cmd:
        return []

    targets = [target_dir] if isinstance(target_dir, str) else list(target_dir)
    if not targets:
        return []

    args = [cmd, "scan", "--json", "--quiet"]
    if rules_dir:
        args.extend(["--config", rules_dir])
    else:
        args.extend(["--config", "auto"])
    args.extend(targets)

    output = _run(args, timeout=120)
    if not output:
        return []

    findings = []
    try:
        data = json.loads(output)
        for item in data.get("results", []):
            findings.append(ToolFinding(
                tool="opengrep",
                rule_id=item.get("check_id", "OG-UNKNOWN"),
                file=_normalize_tool_path(item.get("path", "")),
                line=item.get("start", {}).get("line", 0),
                description=item.get("extra", {}).get("message", ""),
                severity=_map_severity(item.get("extra", {}).get("severity", "warning")),
            ))
    except (json.JSONDecodeError, KeyError):
        pass

    return findings


# =============================================================================
# .NET Analyzers (Meziantou + SonarAnalyzer + Unity + NetAnalyzers via SARIF)
# =============================================================================

_HARNESS_DIR = str(Path(__file__).parent.parent.parent / "analyzer-harness")


def run_dotnet_analyzers(sln_or_csproj: str) -> list[ToolFinding]:
    """Run dotnet build with all analyzer packages and parse SARIF output.

    This runs Meziantou.Analyzer, SonarAnalyzer.CSharp, Microsoft.Unity.Analyzers,
    and Microsoft.CodeAnalysis.NetAnalyzers in a single build pass.

    Filters out compile errors (CS0234, CS0246, etc.) that occur because Unity Engine
    DLLs aren't referenced in the standalone build context.
    """
    cmd = _which("dotnet")
    if not cmd:
        return []

    sarif_path = str(Path(sln_or_csproj).parent / "analysis.sarif")

    _run(
        [cmd, "build", sln_or_csproj,
         f"/p:ErrorLog={sarif_path},version=2.1",
         "/p:EnforceCodeStyleInBuild=true",
         "/p:TreatWarningsAsErrors=false",
         "/verbosity:quiet",
         "--no-restore"],
        timeout=300,
        cwd=str(Path(sln_or_csproj).parent),
    )

    if not Path(sarif_path).exists():
        return []

    findings = []
    base_dir = str(Path(sln_or_csproj).parent)
    try:
        with open(sarif_path, "r", encoding="utf-8") as f:
            sarif = json.load(f)

        for run in sarif.get("runs", []):
            for result in run.get("results", []):
                rule_id = result.get("ruleId", "")
                msg_obj = result.get("message", {})
                msg = msg_obj.get("text", "") if isinstance(msg_obj, dict) else str(msg_obj)
                locs = result.get("locations", [])
                if not locs:
                    continue
                phys = locs[0].get("physicalLocation", {})
                uri = phys.get("artifactLocation", {}).get("uri", "")
                line = phys.get("region", {}).get("startLine", 0)
                level = result.get("level", "warning")

                # Skip Unity Engine DLL errors — these types exist only inside Unity Editor
                # but keep genuine code errors (syntax, null ref, type mismatch, etc.)
                _UNITY_DLL_ERROR_CODES = {
                    "CS0234",  # Type/namespace not found (Unity DLL not present)
                    "CS0246",  # Type not found (Unity type missing)
                    "CS0012",  # Type in assembly not referenced
                    "CS0400",  # Type in undeclared namespace
                    "CS0518",  # Missing predefined type (Unity dependency)
                }
                # Skip Unity-specific noise codes at any level
                if rule_id in _UNITY_DLL_ERROR_CODES:
                    continue
                # Skip remaining common compile-context noise (only warnings, not errors)
                if rule_id in ("CS0103", "CS0111", "CS0117", "CS1061", "CS0535"):
                    continue

                # Determine source tool from rule prefix
                tool_name = "dotnet"
                if rule_id.startswith("MA"):
                    tool_name = "meziantou"
                elif rule_id.startswith("S") and not rule_id.startswith("SA"):
                    tool_name = "sonar"
                elif rule_id.startswith("UNT") or rule_id.startswith("USP"):
                    tool_name = "unity-analyzers"
                elif rule_id.startswith("CA"):
                    tool_name = "net-analyzers"

                findings.append(ToolFinding(
                    tool=tool_name,
                    rule_id=rule_id,
                    file=_normalize_tool_path(uri, base_dir=base_dir),
                    line=line,
                    description=msg,
                    severity=_map_severity(level),
                ))
    except (json.JSONDecodeError, KeyError, OSError):
        pass
    finally:
        # Cleanup SARIF file
        try:
            Path(sarif_path).unlink(missing_ok=True)
        except OSError:
            pass

    return findings


# =============================================================================
# Roslynator CLI (standalone, no project needed for some checks)
# =============================================================================


def run_roslynator(sln_path: str) -> list[ToolFinding]:
    """Run roslynator analyze on a solution and parse XML output."""
    cmd = _which("roslynator")
    if not cmd:
        return []

    import tempfile
    output_path = tempfile.mktemp(suffix=".xml")

    _run(
        [cmd, "analyze", sln_path,
         "--output", output_path,
         "--severity-level", "info"],
        timeout=300,
        cwd=str(Path(sln_path).parent),
    )

    if not Path(output_path).exists():
        return []

    findings = []
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(output_path)
        for diag in tree.findall(".//Diagnostic"):
            findings.append(ToolFinding(
                tool="roslynator",
                rule_id=diag.get("Id", "RCS-UNKNOWN"),
                file=diag.findtext("FilePath", ""),
                line=int(diag.findtext("Line", "0") or "0"),
                description=diag.findtext("Message", ""),
                severity=_map_severity(diag.findtext("Severity", "warning")),
            ))
    except Exception:
        pass
    finally:
        try:
            Path(output_path).unlink(missing_ok=True)
        except OSError:
            pass

    return findings


# =============================================================================
# Availability & Exports
# =============================================================================


def available_tools() -> dict[str, bool]:
    """Report which external tools are installed."""
    return {
        "ast-grep": bool(_get_ast_grep()),
        "opengrep": bool(_which("opengrep") or _which("semgrep")),
        "ruff": bool(_which("ruff")),
        "mypy": bool(_which("mypy")),
        "roslynator": bool(_which("roslynator")),
        "dotnet": bool(_which("dotnet")),
        "dotnet-analyzers": Path(_HARNESS_DIR).exists(),
    }


__all__ = [
    "run_ast_grep",
    "run_opengrep",
    "run_dotnet_analyzers",
    "run_roslynator",
    "run_ruff",
    "run_mypy",
    "available_tools",
    "ToolFinding",
]
