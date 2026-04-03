# Bug Scan: Configuration, Dependencies, and Packaging

**Date:** 2026-04-02
**Scope:** pyproject.toml, .mcp.json, __init__.py files, all import statements across MCP toolkit
**Confidence:** HIGH (verified by reading every import line and cross-referencing pyproject.toml)

---

## Summary

Found **12 bugs** across configuration, dependency management, packaging, and security categories. The most critical is a **wrong Google AI SDK package** in pyproject.toml that causes runtime ImportError whenever Gemini review is used. The already-known `httpx` missing dependency and `tempfile.mktemp` issues are confirmed and detailed below.

---

## BUG-CFG-001: Wrong Google AI SDK package (CRITICAL)

**File:** `Tools/mcp-toolkit/pyproject.toml` line 18, `src/veilbreakers_mcp/shared/gemini_client.py` line 84
**Severity:** CRITICAL -- runtime ImportError
**Status:** NEW

pyproject.toml declares:
```
"google-genai>=1.0.0"
```

But the code imports:
```python
import google.generativeai as genai  # gemini_client.py:84
```

`google-genai` provides `google.genai` (the newer SDK). `google-generativeai` provides `google.generativeai` (the older SDK). These are **different packages** with incompatible APIs.

**Verified:** `python -c "import google.generativeai"` raises `ModuleNotFoundError` even though `google-genai==1.68.0` is installed.

**Fix options:**
1. Change pyproject.toml to `"google-generativeai>=0.8.0"` (matches existing code)
2. OR rewrite `gemini_client.py` to use `from google import genai` (matches installed package, but requires API rewrite since `genai.configure()` and `genai.GenerativeModel()` don't exist in the new SDK)

**Recommendation:** Option 1 is safest (no code changes needed beyond dependency). If upgrading to the newer SDK, the entire `_call_via_sdk` method needs rewriting.

---

## BUG-CFG-002: httpx not in pyproject.toml (KNOWN)

**File:** `Tools/mcp-toolkit/pyproject.toml`
**Severity:** HIGH -- runtime ImportError
**Status:** KNOWN (previously identified)

httpx is imported in 4 files:
- `shared/fal_client.py:113` (lazy import)
- `shared/gemini_client.py:112` (lazy import)
- `shared/texture_ops.py:843` (lazy import)
- `shared/tripo_studio_client.py:26` (top-level import -- fails on module load)

`tripo_studio_client.py` does a **top-level** `import httpx`, meaning importing this module will crash if httpx is not installed. The other three are lazy imports inside functions.

httpx is currently installed as a transitive dependency of some other package, but this is fragile.

**Fix:** Add `"httpx>=0.27.0"` to pyproject.toml dependencies.

---

## BUG-CFG-003: tempfile.mktemp usage (KNOWN -- security + deprecation)

**File:** `src/veilbreakers_mcp/_tool_runner.py` line 392
**Severity:** MEDIUM -- deprecated, TOCTOU race condition
**Status:** KNOWN (previously identified)

```python
output_path = tempfile.mktemp(suffix=".xml")
```

`tempfile.mktemp()` is deprecated since Python 3.0 due to a time-of-check-time-of-use (TOCTOU) race condition. Between when the name is generated and when the file is created, another process could create a file with the same name.

**Fix:** Replace with:
```python
with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
    output_path = f.name
```

---

## BUG-CFG-004: Version mismatch between pyproject.toml and __init__.py

**File:** `pyproject.toml` line 3, `src/veilbreakers_mcp/__init__.py` line 1
**Severity:** LOW -- cosmetic but confusing
**Status:** NEW

pyproject.toml: `version = "3.1.0"`
__init__.py: `__version__ = "0.1.0"`

Any code or tool that reads `veilbreakers_mcp.__version__` gets the wrong version. This includes introspection tools, logging, and any version-check logic.

**Fix:** Update `__init__.py` to `__version__ = "3.1.0"` and ideally use `importlib.metadata.version("veilbreakers-mcp")` for single-source versioning.

---

## BUG-CFG-005: xml.etree.ElementTree used for untrusted XML parsing

**File:** `src/veilbreakers_mcp/_tool_runner.py` line 407
**Severity:** LOW-MEDIUM -- the XML comes from roslynator output, not user input
**Status:** NEW

```python
import xml.etree.ElementTree as ET
tree = ET.parse(output_path)
```

The project already depends on `defusedxml` and uses it correctly in `wcag_checker.py` and `ui_templates.py`. But `_tool_runner.py` uses the stdlib `xml.etree.ElementTree.parse()` which is vulnerable to XML entity expansion attacks (billion laughs, external entity injection).

Since the XML comes from a locally-run tool (roslynator), risk is low. But for consistency with the project's own security patterns, it should use `defusedxml`.

**Fix:** Replace with `import defusedxml.ElementTree as ET`.

---

## BUG-CFG-006: Mixed secure/insecure XML handling in same file

**File:** `src/veilbreakers_mcp/shared/unity_templates/ui_templates.py` lines 16-17
**Severity:** LOW -- Element/SubElement/tostring are not parsing functions
**Status:** NEW (but not actually dangerous)

```python
from xml.etree.ElementTree import Element, SubElement, indent, tostring
from defusedxml.ElementTree import fromstring, ParseError
```

This is actually **correct**: the file uses `defusedxml` for `fromstring()` (which parses untrusted XML) and stdlib `Element`/`SubElement`/`tostring` (which construct/serialize XML, not parse it). No actual bug, but worth documenting as a pattern that looks suspicious but is fine.

**Status:** FALSE POSITIVE -- no fix needed.

---

## BUG-CFG-007: Blender addon bl_info version vs pyproject.toml version

**File:** `blender_addon/__init__.py` line 3
**Severity:** LOW -- cosmetic
**Status:** NEW

```python
bl_info = {
    "version": (0, 1, 0),
    ...
}
```

This should track the project version (3.1.0) or at least the addon's own version. Blender's addon manager shows this version to users.

**Fix:** Update to `"version": (3, 1, 0)`.

---

## BUG-CFG-008: opensimplex imported in Blender addon but only in pyproject.toml for MCP server

**File:** `blender_addon/handlers/_terrain_noise.py` line 37, `pyproject.toml` line 15
**Severity:** LOW -- works because it has a fallback
**Status:** NEW

```python
from opensimplex import OpenSimplex as _RealOpenSimplex
```

opensimplex is listed in pyproject.toml (MCP server dependencies), but the Blender addon runs in Blender's own Python, which does NOT install pyproject.toml dependencies. The addon would need opensimplex installed separately in Blender's Python.

However, reviewing the code, `_terrain_noise.py` has a try/except fallback that provides a pure-Python SimplexNoise implementation when opensimplex is not available. So this is a **performance concern** (fallback is slower) rather than a crash.

**Fix:** Document that `opensimplex` should be pip-installed into Blender's Python for best performance, similar to the existing xatlas note.

---

## BUG-CFG-009: numpy used in Blender addon with top-level imports

**File:** Multiple files in `blender_addon/handlers/` (environment.py, environment_scatter.py, mesh_smoothing.py, terrain_advanced.py, worldbuilding_layout.py, _biome_grammar.py, _dungeon_gen.py, _terrain_depth.py, _terrain_noise.py, _terrain_erosion.py)
**Severity:** LOW -- Blender ships with numpy
**Status:** FALSE POSITIVE

numpy is imported at the top level in ~15 Blender addon handler files. Blender 4.2+ ships numpy as a bundled dependency, so this works. No fix needed.

---

## BUG-CFG-010: .mcp.json uses ${VAR} env var syntax but JSON doesn't support variable expansion

**File:** `.mcp.json` lines 9-13, 22-23
**Severity:** INFO -- depends on MCP client implementation
**Status:** NEW

```json
"ELEVENLABS_API_KEY": "${ELEVENLABS_API_KEY}",
"GEMINI_API_KEY": "${GEMINI_API_KEY}",
```

Standard JSON has no variable expansion. This relies on the MCP client (Claude Desktop / Claude Code) interpreting `${...}` syntax. Claude Desktop does support this, so it works in practice.

**Fix:** None needed if only used with Claude Desktop/Code. Document this dependency for portability.

---

## BUG-CFG-011: pydantic is an implicit transitive dependency

**File:** `src/veilbreakers_mcp/shared/models.py` line 2
**Severity:** LOW -- works but fragile
**Status:** NEW

```python
from pydantic import BaseModel, Field
```

pyproject.toml lists `pydantic-settings>=2.0` which pulls in `pydantic` as a transitive dependency. But `pydantic` itself is not explicitly listed. If `pydantic-settings` ever drops its pydantic dependency or changes its version requirement, this could break.

Additionally, `mcp[cli]>=1.26.0` also depends on pydantic, providing double coverage. Risk is very low.

**Fix (optional):** Add `"pydantic>=2.0"` to pyproject.toml for explicitness.

---

## BUG-CFG-012: Python >=3.12 requirement may conflict with Blender's Python

**File:** `pyproject.toml` line 4
**Severity:** INFO
**Status:** NEW

```
requires-python = ">=3.12"
```

This applies to the MCP server package. The Blender addon runs in Blender's bundled Python:
- Blender 4.2: Python 3.11
- Blender 4.3+: Python 3.12

If anyone tries to install the MCP server package into Blender 4.2's Python, pip will refuse. This is actually **correct behavior** since the MCP server should not be installed into Blender -- but it's worth noting.

The Blender addon itself does not use any Python 3.12+ features (no type union syntax `X | Y` at runtime, etc.), so it works fine in Blender 4.2's Python 3.11.

**Fix:** None needed. The separation between MCP server (installed via uv) and Blender addon (loaded by Blender) is correct.

---

## Additional Checks Performed (No Bugs Found)

### Missing __init__.py files
All package directories have `__init__.py`:
- `src/veilbreakers_mcp/__init__.py` -- exists
- `src/veilbreakers_mcp/shared/__init__.py` -- exists
- `src/veilbreakers_mcp/shared/unity_templates/__init__.py` -- exists
- `src/veilbreakers_mcp/unity_tools/__init__.py` -- exists
- `blender_addon/__init__.py` -- exists
- `blender_addon/handlers/__init__.py` -- exists

No missing `__init__.py` files found.

### Circular imports
No circular import patterns detected. The import graph flows cleanly:
- `blender_server.py` -> `shared/*` (blender_client, config, image_utils, texture_ops, etc.)
- `unity_server.py` -> `unity_tools/__init__.py` -> individual tool modules -> `shared/*`
- No back-references from shared to server modules

### Entry points
Both entry points in pyproject.toml are correct:
```
vb-blender-mcp = "veilbreakers_mcp.blender_server:main"
vb-unity-mcp = "veilbreakers_mcp.unity_server:main"
```
These match the actual module paths and function names.

### Platform-specific issues
No platform-specific code found in the MCP server (no `os.name`, `sys.platform`, or `platform.system()` checks). subprocess calls use list args (not shell=True), which is cross-platform safe.

### setup.py / setup.cfg / requirements.txt
None exist -- the project uses only pyproject.toml with hatchling build backend. This is correct modern Python packaging.

### Dependency version constraints
Most constraints use `>=` (minimum version), which is appropriate for an application (not a library). No overly-pinned exact versions. No upper bounds that would cause resolver conflicts.

---

## Bug Summary Table

| ID | Severity | Status | Description | Fix Complexity |
|----|----------|--------|-------------|---------------|
| CFG-001 | CRITICAL | NEW | Wrong Google AI SDK package (google-genai vs google-generativeai) | Change 1 line in pyproject.toml |
| CFG-002 | HIGH | KNOWN | httpx not in pyproject.toml | Add 1 line |
| CFG-003 | MEDIUM | KNOWN | tempfile.mktemp deprecated/insecure | Replace with NamedTemporaryFile |
| CFG-004 | LOW | NEW | __init__.py version "0.1.0" vs pyproject "3.1.0" | Update 1 line |
| CFG-005 | LOW-MED | NEW | xml.etree.ElementTree for XML parsing instead of defusedxml | Import swap |
| CFG-006 | FALSE POS | -- | Mixed xml imports in ui_templates.py (actually correct) | None |
| CFG-007 | LOW | NEW | Blender addon bl_info version (0,1,0) outdated | Update version tuple |
| CFG-008 | LOW | NEW | opensimplex needed in Blender Python for performance | Documentation |
| CFG-009 | FALSE POS | -- | numpy in Blender addon (ships with Blender) | None |
| CFG-010 | INFO | NEW | ${VAR} in .mcp.json relies on MCP client expansion | Documentation |
| CFG-011 | LOW | NEW | pydantic is implicit transitive dep, not explicit | Add to pyproject.toml |
| CFG-012 | INFO | NEW | Python >=3.12 vs Blender 4.2 Python 3.11 | None (correct design) |

**Total real bugs: 8** (excluding 2 false positives and 2 info-level notes)
**Critical/High: 2** (CFG-001, CFG-002)
**Medium: 1** (CFG-003)
**Low: 5** (CFG-004, CFG-005, CFG-007, CFG-008, CFG-011)
