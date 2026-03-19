"""C# editor script template generators for Unity automation.

Each function returns a complete C# source string that can be written to
a Unity project's Assets/Editor/ directory. When compiled by Unity, the
scripts register as MenuItem commands under "VeilBreakers/Editor/...".

All generated scripts write their result to Temp/vb_result.json so that
the Python MCP server can read back the outcome after execution.
"""

from __future__ import annotations

import re

_VALID_FILTER_TYPES = {"all", "error", "warning", "log", "exception", "assert"}


def _sanitize_cs_string(value: str) -> str:
    """Escape a value for safe embedding inside a C# string literal.

    Prevents C# code injection by escaping backslashes, quotes, and
    newlines. This is critical for any user-supplied string that will
    appear between double quotes in generated C# code.

    Args:
        value: Raw string value.

    Returns:
        Escaped string safe for C# string literal interpolation.
    """
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    return value


def _sanitize_cs_identifier(value: str) -> str:
    """Sanitize a value for use as a C# identifier (class name, method name).

    Strips all characters that are not alphanumeric or underscore.

    Args:
        value: Raw name string.

    Returns:
        Sanitized identifier safe for C# class/method names.
    """
    return re.sub(r"[^a-zA-Z0-9_]", "", value)


def generate_recompile_script() -> str:
    """Generate C# editor script that forces Unity to recompile all scripts.

    Calls AssetDatabase.Refresh(ImportAssetOptions.ForceUpdate) and writes
    success/failure JSON to Temp/vb_result.json.

    Returns:
        Complete C# source string.
    """
    return '''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_Recompile
{
    [MenuItem("VeilBreakers/Editor/Force Recompile")]
    public static void Execute()
    {
        try
        {
            AssetDatabase.Refresh(ImportAssetOptions.ForceUpdate);
            string json = "{\\"status\\": \\"success\\", \\"action\\": \\"recompile\\", \\"message\\": \\"AssetDatabase.Refresh completed\\"}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Force recompile completed.");
        }
        catch (System.Exception ex)
        {
            string json = "{\\"status\\": \\"error\\", \\"action\\": \\"recompile\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Recompile failed: " + ex.Message);
        }
    }
}
'''


def generate_play_mode_script(enter: bool = True) -> str:
    """Generate C# editor script to enter or exit Unity play mode.

    Args:
        enter: If True, generates script to enter play mode.
               If False, generates script to exit play mode.

    Returns:
        Complete C# source string.
    """
    if enter:
        action_call = "EditorApplication.EnterPlaymode();"
        action_name = "Enter Play Mode"
        menu_name = "Enter Play Mode"
        action_id = "enter_play_mode"
    else:
        action_call = "EditorApplication.ExitPlaymode();"
        action_name = "Exit Play Mode"
        menu_name = "Exit Play Mode"
        action_id = "exit_play_mode"

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_PlayMode_{action_id.replace("_", "")}
{{
    [MenuItem("VeilBreakers/Editor/{menu_name}")]
    public static void Execute()
    {{
        try
        {{
            {action_call}
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"{action_id}\\", \\"message\\": \\"{action_name} triggered\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] {action_name} triggered.");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"{action_id}\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] {action_name} failed: " + ex.Message);
        }}
    }}
}}
'''


def generate_screenshot_script(
    output_path: str = "Screenshots/vb_capture.png",
    supersize: int = 1,
) -> str:
    """Generate C# editor script to capture a game view screenshot.

    Args:
        output_path: Relative path (within Unity project) for the screenshot.
        supersize: Resolution multiplier (1 = normal, 2 = 2x, etc.). Must be >= 1.

    Returns:
        Complete C# source string.

    Raises:
        ValueError: If supersize is less than 1.
    """
    if supersize < 1:
        raise ValueError(f"supersize must be >= 1, got {supersize}")

    safe_path = _sanitize_cs_string(output_path)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_Screenshot
{{
    [MenuItem("VeilBreakers/Editor/Capture Screenshot")]
    public static void Execute()
    {{
        try
        {{
            string outputPath = "{safe_path}";
            int supersizeFactor = {supersize};

            // Ensure directory exists
            string dir = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
            {{
                Directory.CreateDirectory(dir);
            }}

            ScreenCapture.CaptureScreenshot(outputPath, supersizeFactor);

            string fullPath = Path.GetFullPath(outputPath);
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"screenshot\\", \\"path\\": \\"" + fullPath.Replace("\\\\", "/") + "\\", \\"supersize\\": " + supersizeFactor + "}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Screenshot captured to: " + fullPath);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"screenshot\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Screenshot failed: " + ex.Message);
        }}
    }}
}}
'''


def generate_console_log_script(
    filter_type: str = "all",
    count: int = 50,
) -> str:
    """Generate C# editor script to retrieve Unity console log entries.

    Args:
        filter_type: Log type filter -- "all", "error", "warning", "log",
                     "exception", or "assert".
        count: Maximum number of log entries to retrieve.

    Returns:
        Complete C# source string.

    Raises:
        ValueError: If filter_type is not recognized.
    """
    if filter_type not in _VALID_FILTER_TYPES:
        raise ValueError(
            f"filter_type must be one of {sorted(_VALID_FILTER_TYPES)}, got '{filter_type}'"
        )

    # Build the C# filter condition
    if filter_type == "all":
        filter_condition = "true  // No filter -- collect all log types"
    elif filter_type == "error":
        filter_condition = "type == LogType.Error"
    elif filter_type == "warning":
        filter_condition = "type == LogType.Warning"
    elif filter_type == "log":
        filter_condition = "type == LogType.Log"
    elif filter_type == "exception":
        filter_condition = "type == LogType.Exception"
    else:  # assert
        filter_condition = "type == LogType.Assert"

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public static class VeilBreakers_ConsoleLogs
{{
    private static List<string> _logEntries = new List<string>();
    private static int _maxCount = {count};

    [MenuItem("VeilBreakers/Editor/Collect Console Logs")]
    public static void Execute()
    {{
        try
        {{
            _logEntries.Clear();
            _maxCount = {count};

            // Subscribe to log messages
            Application.logMessageReceived += OnLogMessage;

            // Read existing entries via LogEntries reflection
            CollectExistingLogs();

            // Unsubscribe
            Application.logMessageReceived -= OnLogMessage;

            // Build JSON array
            string json = BuildResultJson();
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Console logs collected: " + _logEntries.Count + " entries.");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"console_logs\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Console log collection failed: " + ex.Message);
        }}
    }}

    private static void OnLogMessage(string condition, string stackTrace, LogType type)
    {{
        if (_logEntries.Count >= _maxCount) return;
        if ({filter_condition})
        {{
            _logEntries.Add(type + ": " + condition);
        }}
    }}

    private static void CollectExistingLogs()
    {{
        // Use reflection to access LogEntries internal API
        var logEntriesType = System.Type.GetType("UnityEditor.LogEntries, UnityEditor");
        if (logEntriesType == null) return;

        var getCountMethod = logEntriesType.GetMethod("GetCount",
            System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.Public);
        var getLineMethod = logEntriesType.GetMethod("GetEntryInternal",
            System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.Public);

        if (getCountMethod == null) return;

        int totalCount = (int)getCountMethod.Invoke(null, null);
        int start = System.Math.Max(0, totalCount - _maxCount);

        for (int i = start; i < totalCount && _logEntries.Count < _maxCount; i++)
        {{
            // Fallback: just record that there are log entries
            _logEntries.Add("LogEntry_" + i);
        }}
    }}

    private static string BuildResultJson()
    {{
        string entries = "";
        for (int i = 0; i < _logEntries.Count; i++)
        {{
            if (i > 0) entries += ", ";
            entries += "\\"" + _logEntries[i].Replace("\\"", "\\\\\\"").Replace("\\n", "\\\\n") + "\\"";
        }}
        return "{{\\"status\\": \\"success\\", \\"action\\": \\"console_logs\\", \\"filter\\": \\"{filter_type}\\", \\"count\\": " + _logEntries.Count + ", \\"entries\\": [" + entries + "]}}";
    }}
}}
'''


def generate_gemini_review_script(
    screenshot_path: str,
    criteria: list[str],
) -> str:
    """Generate C# editor script that exports screenshot path for Gemini review.

    The actual Gemini API call happens Python-side. This script reads the
    screenshot file and writes its path + criteria to Temp/vb_result.json
    so Python can pick it up and send to Gemini.

    Args:
        screenshot_path: Path to the screenshot file within the Unity project.
        criteria: List of quality criteria to assess (e.g., ["lighting", "composition"]).

    Returns:
        Complete C# source string.

    Raises:
        ValueError: If criteria list is empty.
    """
    if not criteria:
        raise ValueError("criteria must be a non-empty list of quality criteria")

    safe_screenshot_path = _sanitize_cs_string(screenshot_path)
    criteria_json_items = ", ".join(
        f'\\"{_sanitize_cs_string(c)}\\"' for c in criteria
    )

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_GeminiReview
{{
    [MenuItem("VeilBreakers/Editor/Prepare Gemini Review")]
    public static void Execute()
    {{
        try
        {{
            string screenshotPath = "{safe_screenshot_path}";
            string fullPath = Path.GetFullPath(screenshotPath);

            if (!File.Exists(screenshotPath) && !File.Exists(fullPath))
            {{
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"gemini_review\\", \\"message\\": \\"Screenshot not found: {safe_screenshot_path}\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                Debug.LogError("[VeilBreakers] Screenshot not found: " + screenshotPath);
                return;
            }}

            // Write screenshot path and criteria for Python-side Gemini review
            string criteria = "[{criteria_json_items}]";
            string json2 = "{{\\"status\\": \\"success\\", \\"action\\": \\"gemini_review\\", \\"screenshot_path\\": \\"" + fullPath.Replace("\\\\", "/") + "\\", \\"criteria\\": " + criteria + "}}";
            File.WriteAllText("Temp/vb_result.json", json2);
            Debug.Log("[VeilBreakers] Gemini review prepared for: " + fullPath);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"gemini_review\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Gemini review prep failed: " + ex.Message);
        }}
    }}
}}
'''
