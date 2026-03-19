# Phase 07 Plan 04 Summary: UI System (UXML/USS, WCAG, Screenshot Diff)

**Status:** COMPLETE
**Date:** 2026-03-19

## What was built

### New files
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/ui_templates.py` (293 lines) -- UXML/USS generators and layout validator: `generate_uxml_screen`, `generate_uss_stylesheet`, `generate_responsive_test_script`, `validate_uxml_layout`
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/wcag_checker.py` (315 lines) -- WCAG 2.1 AA contrast checking: `relative_luminance`, `contrast_ratio`, `check_wcag_aa`, `parse_color`, `validate_uxml_contrast`
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/screenshot_diff.py` (142 lines) -- Visual regression detection: `compare_screenshots`, `generate_diff_image`
- `Tools/mcp-toolkit/tests/test_ui_templates.py` (179 lines) -- 41 tests for UXML/USS generators and responsive test scripts
- `Tools/mcp-toolkit/tests/test_ui_validation.py` (145 lines) -- 18 tests for layout validation (zero-size, duplicates, overflow, parse errors)
- `Tools/mcp-toolkit/tests/test_wcag_checker.py` (203 lines) -- 29 tests for WCAG luminance, contrast ratio, AA check, color parsing, UXML+USS validation
- `Tools/mcp-toolkit/tests/test_screenshot_diff.py` (186 lines) -- 12 tests for image comparison, threshold behavior, diff generation, size handling

### Modified files
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_server.py` -- Added `unity_ui` compound tool with 5 actions (`generate_ui_screen`, `validate_layout`, `test_responsive`, `check_contrast`, `compare_screenshots`) + imports for ui_templates, wcag_checker, screenshot_diff

## Test results
- 100 new tests pass (41 ui_templates + 18 ui_validation + 29 wcag_checker + 12 screenshot_diff)
- 1381 total tests pass (zero regressions)

## Requirements covered
- **UI-02:** Layout validation -- `validate_uxml_layout` detects zero-size elements, duplicate names, overflow
- **UI-03:** Responsive testing -- `generate_responsive_test_script` produces C# that captures at 5 resolutions (720p, 1080p, 1440p, 4K, 800x600)
- **UI-05:** UXML/USS generation -- `generate_uxml_screen` + `generate_uss_stylesheet` with dark fantasy theme (#1a1a2e bg, #e6e6ff text, #4a0e4e accent, hover glow)
- **UI-06:** WCAG contrast checking -- W3C-compliant relative luminance + contrast ratio, AA threshold (4.5:1 normal, 3.0:1 large text), USS color parsing
- **UI-07:** Visual regression -- Pillow-based pixel comparison with configurable threshold, red-highlighted diff image generation

## Architecture

### UXML/USS Generation
- `generate_uxml_screen(spec)` takes a dict with title + elements list, recursively builds XML tree via `xml.etree.ElementTree`, produces valid UXML with `xmlns:ui="UnityEngine.UIElements"`
- Supports 7 element types: label, button, image, panel, input, slider, toggle -- each mapped to Unity UI Toolkit tags
- `generate_uss_stylesheet(theme)` outputs complete USS with all VeilBreakers selectors and dark fantasy theming

### WCAG Checker
- Exact W3C sRGB linearization formula with 0.04045 threshold
- `validate_uxml_contrast` handles XML namespace expansion (`{UnityEngine.UIElements}Label`), walks UXML tree inheriting background colors, checks text elements against WCAG AA
- `parse_color` supports #RGB, #RRGGBB, #RRGGBBAA, rgb(), rgba() formats

### Screenshot Diff
- Uses Pillow `ImageChops.difference()` with per-channel noise threshold (10/255) to ignore gamma/compression artifacts
- Generates red-highlighted diff overlay on dimmed reference image
- Auto-resizes current to match reference if sizes differ

### unity_ui Compound Tool
The `unity_ui` tool in `unity_server.py` has 5 actions:
1. `generate_ui_screen` -- generates UXML+USS, writes to Unity project, runs auto-validation and contrast check
2. `validate_layout` -- reads UXML from file or inline content, returns issues
3. `test_responsive` -- generates C# editor script, writes to Assets/Editor/Generated/UI/
4. `check_contrast` -- reads UXML+USS from files or inline, returns per-element WCAG results
5. `compare_screenshots` -- compares two images, returns diff percentage and highlighted diff image
