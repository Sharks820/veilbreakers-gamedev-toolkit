"""Unity QA C# template generators.

Generates C# scripts for quality assurance, debugging, and observability:

1. **VBBridgeServer.cs** -- ``[InitializeOnLoad]`` static class with a
   background ``TcpListener`` thread, ``ConcurrentQueue`` for thread-safe
   command passing, and ``EditorApplication.update`` for main-thread
   dispatch.  Mirrors the proven Blender bridge pattern
   (``blender_addon/socket_server.py`` on port 9876) but targets Unity
   Editor on port 9877.

2. **VBBridgeCommands.cs** -- Static class with a ``COMMAND_HANDLERS``
   dictionary mapping command type strings to handler methods.  Includes
   an embedded MiniJSON parser (MIT licensed) since ``JsonUtility``
   cannot deserialize ``Dictionary<string, object>``.

3. **VBCrashReporting.cs** -- Sentry SDK initialization with configurable
   DSN, breadcrumbs, environment tagging, and fallback console logging.

4. **VBAnalytics.cs** -- Singleton analytics manager with event buffering,
   JSON file logging, session management, and typed convenience methods.

5. **VBLiveInspector.cs** -- IMGUI EditorWindow for inspecting live
   GameObject component field values during Play Mode via Reflection.

Exports:
    generate_bridge_server_script      -- VBBridgeServer.cs generator
    generate_bridge_commands_script    -- VBBridgeCommands.cs generator
    generate_crash_reporting_script    -- VBCrashReporting.cs generator
    generate_analytics_script          -- VBAnalytics.cs generator
    generate_live_inspector_script     -- VBLiveInspector.cs generator
"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_cs_string(value: str) -> str:
    """Escape a value for safe embedding inside a C# string literal."""
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    return value


_CS_RESERVED = frozenset({
    "abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char",
    "checked", "class", "const", "continue", "decimal", "default", "delegate",
    "do", "double", "else", "enum", "event", "explicit", "extern", "false",
    "finally", "fixed", "float", "for", "foreach", "goto", "if", "implicit",
    "in", "int", "interface", "internal", "is", "lock", "long", "namespace",
    "new", "null", "object", "operator", "out", "override", "params", "private",
    "protected", "public", "readonly", "ref", "return", "sbyte", "sealed",
    "short", "sizeof", "stackalloc", "static", "string", "struct", "switch",
    "this", "throw", "true", "try", "typeof", "uint", "ulong", "unchecked",
    "unsafe", "ushort", "using", "virtual", "void", "volatile", "while",
})


def _safe_namespace(ns: str) -> str:
    """Sanitize a C# namespace string."""
    sanitized = re.sub(r"[^a-zA-Z0-9_.]", "", ns)
    sanitized = re.sub(r"\.{2,}", ".", sanitized).strip(".")
    if not sanitized:
        return "Generated"
    segments = sanitized.split(".")
    fixed: list[str] = []
    for seg in segments:
        if not seg:
            continue
        if seg[0].isdigit():
            seg = f"_{seg}"
        if seg in _CS_RESERVED:
            seg = f"@{seg}"
        fixed.append(seg)
    return ".".join(fixed) or "Generated"


def _wrap_namespace(lines: list[str], namespace: str) -> list[str]:
    """Wrap lines in a namespace block if namespace is non-empty."""
    if not namespace:
        return lines
    ns = _safe_namespace(namespace)
    wrapped = [f"namespace {ns}", "{"]
    for line in lines:
        if line.strip():
            wrapped.append(f"    {line}")
        else:
            wrapped.append("")
    wrapped.append("}")
    return wrapped


# ---------------------------------------------------------------------------
# generate_bridge_server_script
# ---------------------------------------------------------------------------

def generate_bridge_server_script(port: int = 9877, namespace: str = "") -> str:
    """Generate VBBridgeServer.cs: ``[InitializeOnLoad]`` TCP bridge server.

    The server runs a background ``TcpListener`` thread that accepts
    connections, reads length-prefixed JSON commands, queues them into a
    ``ConcurrentQueue<CommandEnvelope>``, and waits for the main-thread
    ``EditorApplication.update`` callback to execute each command via
    ``VBBridgeCommands.Dispatch``.  Results are sent back to the client
    with the same 4-byte big-endian length prefix protocol used by the
    Blender bridge.

    Args:
        port: TCP port to listen on (default 9877).
        namespace: Optional C# namespace to wrap the class in.

    Returns:
        Complete C# source string for VBBridgeServer.cs.
    """
    lines: list[str] = [
        "using UnityEngine;",
        "using UnityEditor;",
        "using System;",
        "using System.Collections.Concurrent;",
        "using System.IO;",
        "using System.Net;",
        "using System.Net.Sockets;",
        "using System.Text;",
        "using System.Threading;",
        "",
        "[InitializeOnLoad]",
        "public static class VBBridgeServer",
        "{",
        "    private static TcpListener _listener;",
        "    private static Thread _listenerThread;",
        "    private static bool _running;",
        "    private static readonly ConcurrentQueue<CommandEnvelope> _commandQueue = new ConcurrentQueue<CommandEnvelope>();",
        f"    private static int _port = {port};",
        "",
        "    // ----- Lifecycle -----",
        "",
        "    static VBBridgeServer()",
        "    {",
        "        Start();",
        "        EditorApplication.update += ProcessCommands;",
        "        AssemblyReloadEvents.beforeAssemblyReload += Stop;",
        "        EditorApplication.quitting += Stop;",
        "    }",
        "",
        "    static void Start()",
        "    {",
        "        if (_running) return;",
        "        _running = true;",
        "        _listenerThread = new Thread(ListenerLoop) { IsBackground = true };",
        "        _listenerThread.Start();",
        '        Debug.Log("[VBBridge] Listening on localhost:" + _port);',
        "    }",
        "",
        "    static void Stop()",
        "    {",
        "        _running = false;",
        "        try { _listener?.Stop(); } catch (Exception) { }",
        "        if (_listenerThread != null && _listenerThread.IsAlive)",
        "        {",
        "            _listenerThread.Join(2000);",
        "        }",
        '        Debug.Log("[VBBridge] Server stopped.");',
        "    }",
        "",
        "    // ----- Network -----",
        "",
        "    static void ListenerLoop()",
        "    {",
        "        _listener = new TcpListener(IPAddress.Loopback, _port);",
        "        _listener.Start();",
        "        while (_running)",
        "        {",
        "            try",
        "            {",
        "                if (!_listener.Pending()) { Thread.Sleep(50); continue; }",
        "                TcpClient client = _listener.AcceptTcpClient();",
        "                ThreadPool.QueueUserWorkItem(_ => HandleClient(client));",
        "            }",
        "            catch (Exception ex) when (ex is SocketException || ex is ObjectDisposedException)",
        "            {",
        "                if (ex is ObjectDisposedException) break;",
        "                if (_running) throw;",
        "            }",
        "        }",
        "    }",
        "",
        "    static void HandleClient(TcpClient client)",
        "    {",
        "        try",
        "        {",
        "            using (NetworkStream stream = client.GetStream())",
        "            {",
        "                client.NoDelay = true;",
        "                // Read 4-byte big-endian length prefix",
        "                byte[] lenBytes = ReadExactly(stream, 4);",
        "                int len = (lenBytes[0] << 24) | (lenBytes[1] << 16) | (lenBytes[2] << 8) | lenBytes[3];",
        "                if (len <= 0 || len > 10 * 1024 * 1024) { stream.Close(); return; }",
        "                byte[] jsonBytes = ReadExactly(stream, len);",
        "                string json = Encoding.UTF8.GetString(jsonBytes);",
        "",
        "                CommandEnvelope envelope = new CommandEnvelope",
        "                {",
        "                    RequestJson = json,",
        "                    DoneEvent = new ManualResetEventSlim(false)",
        "                };",
        "                _commandQueue.Enqueue(envelope);",
        "                envelope.DoneEvent.Wait(TimeSpan.FromSeconds(300));",
        "",
        "                // Send response with 4-byte length prefix",
        '                byte[] responseBytes = Encoding.UTF8.GetBytes(envelope.ResponseJson ?? "{}");',
        "                byte[] responseLen = new byte[4];",
        "                responseLen[0] = (byte)(responseBytes.Length >> 24);",
        "                responseLen[1] = (byte)(responseBytes.Length >> 16);",
        "                responseLen[2] = (byte)(responseBytes.Length >> 8);",
        "                responseLen[3] = (byte)(responseBytes.Length);",
        "                stream.Write(responseLen, 0, 4);",
        "                stream.Write(responseBytes, 0, responseBytes.Length);",
        "            }",
        "        }",
        '        catch (Exception e) { Debug.LogError("[VBBridge] Client error: " + e.Message); }',
        "        finally",
        "        {",
        "            try { client.Close(); } catch (Exception) { }",
        "        }",
        "    }",
        "",
        "    // ----- Main-Thread Dispatch -----",
        "",
        "    static void ProcessCommands()",
        "    {",
        "        CommandEnvelope envelope;",
        "        if (_commandQueue.TryDequeue(out envelope))",
        "        {",
        "            try",
        "            {",
        "                envelope.ResponseJson = VBBridgeCommands.Dispatch(envelope.RequestJson);",
        "            }",
        "            catch (Exception e)",
        "            {",
        '                envelope.ResponseJson = "{\\"status\\":\\"error\\",\\"message\\":\\"" + EscapeJson(e.Message) + "\\"}";',
        "            }",
        "            finally",
        "            {",
        "                envelope.DoneEvent.Set();",
        "            }",
        "        }",
        "    }",
        "",
        "    // ----- Helpers -----",
        "",
        "    static byte[] ReadExactly(Stream stream, int count)",
        "    {",
        "        byte[] buffer = new byte[count];",
        "        int offset = 0;",
        "        while (offset < count)",
        "        {",
        "            int read = stream.Read(buffer, offset, count - offset);",
        '            if (read == 0) throw new IOException("Connection closed before reading " + count + " bytes.");',
        "            offset += read;",
        "        }",
        "        return buffer;",
        "    }",
        "",
        "    static string EscapeJson(string s)",
        "    {",
        '        if (s == null) return "";',
        '        return s.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"").Replace("\\n", "\\\\n").Replace("\\r", "\\\\r");',
        "    }",
        "",
        "    // ----- CommandEnvelope -----",
        "",
        "    public class CommandEnvelope",
        "    {",
        "        public string RequestJson;",
        "        public string ResponseJson;",
        "        public ManualResetEventSlim DoneEvent;",
        "    }",
        "}",
    ]

    lines = _wrap_namespace(lines, namespace)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# generate_bridge_commands_script
# ---------------------------------------------------------------------------

def generate_bridge_commands_script(namespace: str = "") -> str:
    """Generate VBBridgeCommands.cs: command dispatch + handler methods.

    Includes an embedded MiniJSON parser (MIT licensed, standard Unity
    practice) for ``Dictionary<string, object>`` deserialization since
    ``JsonUtility`` cannot handle generic dictionaries.

    Handlers:
        ping, recompile, execute_menu_item, enter_play_mode,
        exit_play_mode, screenshot, console_logs, read_result,
        get_game_objects

    Args:
        namespace: Optional C# namespace to wrap the class in.

    Returns:
        Complete C# source string for VBBridgeCommands.cs.
    """
    lines: list[str] = [
        "using UnityEngine;",
        "using UnityEditor;",
        "using System;",
        "using System.Collections.Generic;",
        "using System.IO;",
        "using System.Text;",
        "",
        "public static class VBBridgeCommands",
        "{",
        "    // ----- Handler Registry -----",
        "",
        "    private static readonly Dictionary<string, Func<Dictionary<string, object>, Dictionary<string, object>>>",
        "        HANDLERS = new Dictionary<string, Func<Dictionary<string, object>, Dictionary<string, object>>>()",
        "    {",
        '        ["ping"] = HandlePing,',
        '        ["recompile"] = HandleRecompile,',
        '        ["execute_menu_item"] = HandleExecuteMenuItem,',
        '        ["enter_play_mode"] = HandleEnterPlayMode,',
        '        ["exit_play_mode"] = HandleExitPlayMode,',
        '        ["screenshot"] = HandleScreenshot,',
        '        ["console_logs"] = HandleConsoleLogs,',
        '        ["read_result"] = HandleReadResult,',
        '        ["get_game_objects"] = HandleGetGameObjects,',
        "    };",
        "",
        "    // ----- Dispatch -----",
        "",
        "    public static string Dispatch(string requestJson)",
        "    {",
        "        Dictionary<string, object> request = MiniJSON.Deserialize(requestJson) as Dictionary<string, object>;",
        "        if (request == null)",
        '            return SerializeResponse("error", null, "Failed to parse request JSON");',
        "",
        '        string commandType = request.ContainsKey("type") ? request["type"].ToString() : "unknown";',
        "        Dictionary<string, object> parameters = null;",
        '        if (request.ContainsKey("params") && request["params"] is Dictionary<string, object>)',
        '            parameters = (Dictionary<string, object>)request["params"];',
        "        else",
        "            parameters = new Dictionary<string, object>();",
        "",
        "        Func<Dictionary<string, object>, Dictionary<string, object>> handler;",
        "        if (HANDLERS.TryGetValue(commandType, out handler))",
        "        {",
        "            try",
        "            {",
        "                Dictionary<string, object> result = handler(parameters);",
        '                return SerializeResponse("success", result, null);',
        "            }",
        "            catch (Exception e)",
        "            {",
        '                return SerializeResponse("error", null, e.Message);',
        "            }",
        "        }",
        '        return SerializeResponse("error", null, "Unknown command: " + commandType);',
        "    }",
        "",
        "    // ----- Handlers -----",
        "",
        "    static Dictionary<string, object> HandlePing(Dictionary<string, object> p)",
        "    {",
        '        return new Dictionary<string, object> { ["status"] = "success", ["result"] = "pong" };',
        "    }",
        "",
        "    static Dictionary<string, object> HandleRecompile(Dictionary<string, object> p)",
        "    {",
        "        AssetDatabase.Refresh(ImportAssetOptions.ForceUpdate);",
        '        return new Dictionary<string, object> { ["refreshed"] = true };',
        "    }",
        "",
        "    static Dictionary<string, object> HandleExecuteMenuItem(Dictionary<string, object> p)",
        "    {",
        '        string menuPath = p.ContainsKey("menu_path") ? p["menu_path"].ToString() : "";',
        "        bool ok = EditorApplication.ExecuteMenuItem(menuPath);",
        '        return new Dictionary<string, object> { ["executed"] = ok, ["menu_path"] = menuPath };',
        "    }",
        "",
        "    static Dictionary<string, object> HandleEnterPlayMode(Dictionary<string, object> p)",
        "    {",
        "        EditorApplication.EnterPlaymode();",
        '        return new Dictionary<string, object> { ["is_playing"] = true };',
        "    }",
        "",
        "    static Dictionary<string, object> HandleExitPlayMode(Dictionary<string, object> p)",
        "    {",
        "        EditorApplication.ExitPlaymode();",
        '        return new Dictionary<string, object> { ["is_playing"] = false };',
        "    }",
        "",
        "    static Dictionary<string, object> HandleScreenshot(Dictionary<string, object> p)",
        "    {",
        '        string path = p.ContainsKey("path") ? p["path"].ToString() : "Screenshots/vb_bridge_capture.png";',
        "        string dir = Path.GetDirectoryName(path);",
        "        if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))",
        "            Directory.CreateDirectory(dir);",
        "        ScreenCapture.CaptureScreenshot(path);",
        "        // CaptureScreenshot is async (end-of-frame). Poll for file existence.",
        "        string fullPath = Path.GetFullPath(path);",
        "        int maxWaitMs = 5000;",
        "        int waited = 0;",
        "        while (!File.Exists(fullPath) && waited < maxWaitMs)",
        "        {",
        "            Thread.Sleep(100);",
        "            waited += 100;",
        "        }",
        '        bool success = File.Exists(fullPath);',
        '        return new Dictionary<string, object> { ["path"] = fullPath, ["captured"] = success };',
        "    }",
        "",
        "    static Dictionary<string, object> HandleConsoleLogs(Dictionary<string, object> p)",
        "    {",
        '        int count = p.ContainsKey("count") ? Convert.ToInt32(p["count"]) : 50;',
        '        string filter = p.ContainsKey("filter") ? p["filter"].ToString().ToLower() : "all";',
        "        List<Dictionary<string, object>> logs = new List<Dictionary<string, object>>();",
        "",
        "        // Collect via LogEntries reflection (internal Unity API)",
        '        Type logEntriesType = Type.GetType("UnityEditor.LogEntries, UnityEditor");',
        "        if (logEntriesType != null)",
        "        {",
        '            var getCount = logEntriesType.GetMethod("GetCount",',
        "                System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.Public);",
        '            var startGetting = logEntriesType.GetMethod("StartGettingEntries",',
        "                System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.Public);",
        '            var endGetting = logEntriesType.GetMethod("EndGettingEntries",',
        "                System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.Public);",
        '            var getEntry = logEntriesType.GetMethod("GetEntryInternal",',
        "                System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.Public);",
        "",
        '            Type logEntryType = System.Type.GetType("UnityEditor.LogEntry, UnityEditor");',
        "",
        "            if (getCount != null)",
        "            {",
        "                int total = (int)getCount.Invoke(null, null);",
        "                int start = Math.Max(0, total - count);",
        "",
        "                if (startGetting != null) startGetting.Invoke(null, null);",
        "                try",
        "                {",
        "                    for (int i = start; i < total; i++)",
        "                    {",
        '                        string message = "LogEntry_" + i;',
        '                        string stackTrace = "";',
        '                        string logType = "Log";',
        "",
        "                        if (getEntry != null && logEntryType != null)",
        "                        {",
        "                            object entry = System.Activator.CreateInstance(logEntryType);",
        "                            getEntry.Invoke(null, new object[] { i, entry });",
        '                            var msgField = logEntryType.GetField("message");',
        "                            if (msgField != null) message = msgField.GetValue(entry)?.ToString() ?? \"\";",
        '                            var modeField = logEntryType.GetField("mode");',
        "                            if (modeField != null)",
        "                            {",
        "                                int mode = (int)modeField.GetValue(entry);",
        '                                if ((mode & (1 << 0)) != 0) logType = "Error";',
        '                                else if ((mode & (1 << 1)) != 0) logType = "Assert";',
        '                                else if ((mode & (1 << 9)) != 0) logType = "Warning";',
        '                                else if ((mode & (1 << 21)) != 0) logType = "Exception";',
        '                                else logType = "Log";',
        "                            }",
        "                        }",
        "",
        "                        // Apply filter",
        '                        if (filter != "all")',
        "                        {",
        "                            if (!logType.Equals(filter, StringComparison.OrdinalIgnoreCase))",
        "                                continue;",
        "                        }",
        "",
        "                        logs.Add(new Dictionary<string, object>",
        "                        {",
        '                            ["message"] = message,',
        '                            ["type"] = logType,',
        '                            ["stackTrace"] = stackTrace',
        "                        });",
        "                    }",
        "                }",
        "                catch (Exception) { /* reflection may fail on some Unity versions */ }",
        "                finally",
        "                {",
        "                    if (endGetting != null) endGetting.Invoke(null, null);",
        "                }",
        "            }",
        "        }",
        '        return new Dictionary<string, object> { ["logs"] = logs };',
        "    }",
        "",
        "    static Dictionary<string, object> HandleReadResult(Dictionary<string, object> p)",
        "    {",
        '        string resultPath = p.ContainsKey("path") ? p["path"].ToString() : "Temp/vb_result.json";',
        "        if (!File.Exists(resultPath))",
        '            return new Dictionary<string, object> { ["exists"] = false, ["content"] = null };',
        "        string content = File.ReadAllText(resultPath);",
        "        object parsed = MiniJSON.Deserialize(content);",
        '        return new Dictionary<string, object> { ["exists"] = true, ["content"] = parsed };',
        "    }",
        "",
        "    static Dictionary<string, object> HandleGetGameObjects(Dictionary<string, object> p)",
        "    {",
        "        List<Dictionary<string, object>> roots = new List<Dictionary<string, object>>();",
        "        foreach (GameObject go in UnityEngine.SceneManagement.SceneManager.GetActiveScene().GetRootGameObjects())",
        "        {",
        "            roots.Add(SerializeGameObject(go));",
        "        }",
        '        return new Dictionary<string, object> { ["game_objects"] = roots };',
        "    }",
        "",
        "    // ----- Helpers -----",
        "",
        "    static Dictionary<string, object> SerializeGameObject(GameObject go)",
        "    {",
        "        var result = new Dictionary<string, object>",
        "        {",
        '            ["name"] = go.name,',
        '            ["active"] = go.activeSelf',
        "        };",
        "",
        "        // Components",
        "        var comps = new List<string>();",
        "        foreach (Component c in go.GetComponents<Component>())",
        "        {",
        "            if (c != null) comps.Add(c.GetType().Name);",
        "        }",
        '        result["components"] = comps;',
        "",
        "        // Children (recursive)",
        "        var children = new List<Dictionary<string, object>>();",
        "        for (int i = 0; i < go.transform.childCount; i++)",
        "        {",
        "            children.Add(SerializeGameObject(go.transform.GetChild(i).gameObject));",
        "        }",
        '        result["children"] = children;',
        "",
        "        return result;",
        "    }",
        "",
        "    static string SerializeResponse(string status, Dictionary<string, object> result, string message)",
        "    {",
        "        StringBuilder sb = new StringBuilder();",
        '        sb.Append("{\\"status\\":\\"");',
        "        sb.Append(EscapeJsonValue(status));",
        '        sb.Append("\\"");',
        "",
        "        if (result != null)",
        "        {",
        '            sb.Append(",\\"result\\":");',
        "            sb.Append(MiniJSON.Serialize(result));",
        "        }",
        "",
        "        if (message != null)",
        "        {",
        '            sb.Append(",\\"message\\":\\"");',
        "            sb.Append(EscapeJsonValue(message));",
        '            sb.Append("\\"");',
        "        }",
        "",
        '        sb.Append("}");',
        "        return sb.ToString();",
        "    }",
        "",
        "    static string EscapeJsonValue(string s)",
        "    {",
        '        if (s == null) return "";',
        '        return s.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"").Replace("\\n", "\\\\n").Replace("\\r", "\\\\r");',
        "    }",
        "",
    ]

    # MiniJSON section uses a raw triple-quoted string to avoid
    # Python/C# quote escaping conflicts with char literals.
    _minijson = r"""    // =================================================================
    // MiniJSON -- Lightweight JSON parser (MIT License)
    // Embedded because JsonUtility cannot handle Dictionary<string,object>
    // =================================================================

    public static class MiniJSON
    {
        public static object Deserialize(string json)
        {
            if (json == null) return null;
            return Parser.Parse(json);
        }

        public static string Serialize(object obj)
        {
            return Serializer.Serialize(obj);
        }

        sealed class Parser : IDisposable
        {
            StringReader _reader;

            Parser(string jsonString) { _reader = new StringReader(jsonString); }
            public void Dispose() { _reader.Dispose(); }

            public static object Parse(string jsonString)
            {
                using (var p = new Parser(jsonString)) { return p.ParseValue(); }
            }

            object ParseValue()
            {
                EatWhitespace();
                int peek = _reader.Peek();
                if (peek == -1) return null;
                char c = (char)peek;
                if (c == '{') return ParseObject();
                if (c == '[') return ParseArray();
                if (c == '"') return ParseString();
                if (c == '-' || char.IsDigit(c)) return ParseNumber();
                string word = ParseWord();
                if (word == "true") return true;
                if (word == "false") return false;
                if (word == "null") return null;
                return word;
            }

            Dictionary<string, object> ParseObject()
            {
                _reader.Read(); // consume opening brace
                var dict = new Dictionary<string, object>();
                while (true)
                {
                    EatWhitespace();
                    int peek = _reader.Peek();
                    if (peek == -1) break;
                    if ((char)peek == '}') { _reader.Read(); break; }
                    if ((char)peek == ',') { _reader.Read(); continue; }
                    string key = ParseString();
                    EatWhitespace();
                    _reader.Read(); // :
                    dict[key] = ParseValue();
                }
                return dict;
            }

            List<object> ParseArray()
            {
                _reader.Read(); // [
                var list = new List<object>();
                while (true)
                {
                    EatWhitespace();
                    int peek = _reader.Peek();
                    if (peek == -1) break;
                    if ((char)peek == ']') { _reader.Read(); break; }
                    if ((char)peek == ',') { _reader.Read(); continue; }
                    list.Add(ParseValue());
                }
                return list;
            }

            string ParseString()
            {
                _reader.Read(); // opening quote
                var sb = new StringBuilder();
                while (true)
                {
                    int c = _reader.Read();
                    if (c == -1 || c == '"') break;
                    if (c == '\\')
                    {
                        int next = _reader.Read();
                        switch ((char)next)
                        {
                            case '"': sb.Append('"'); break;
                            case '\\': sb.Append('\\'); break;
                            case '/': sb.Append('/'); break;
                            case 'n': sb.Append('\n'); break;
                            case 'r': sb.Append('\r'); break;
                            case 't': sb.Append('\t'); break;
                            default: sb.Append((char)next); break;
                        }
                    }
                    else sb.Append((char)c);
                }
                return sb.ToString();
            }

            object ParseNumber()
            {
                var sb = new StringBuilder();
                bool isFloat = false;
                while (true)
                {
                    int peek = _reader.Peek();
                    if (peek == -1) break;
                    char c = (char)peek;
                    if (c == '.' || c == 'e' || c == 'E') isFloat = true;
                    if (char.IsDigit(c) || c == '-' || c == '+' || c == '.' || c == 'e' || c == 'E')
                    { sb.Append(c); _reader.Read(); }
                    else break;
                }
                string numStr = sb.ToString();
                if (isFloat) { double d; double.TryParse(numStr, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out d); return d; }
                else { long l; long.TryParse(numStr, out l); return l; }
            }

            string ParseWord()
            {
                var sb = new StringBuilder();
                while (true)
                {
                    int peek = _reader.Peek();
                    if (peek == -1) break;
                    char c = (char)peek;
                    if (char.IsLetterOrDigit(c)) { sb.Append(c); _reader.Read(); }
                    else break;
                }
                return sb.ToString();
            }

            void EatWhitespace()
            {
                while (true)
                {
                    int peek = _reader.Peek();
                    if (peek == -1) break;
                    if (!char.IsWhiteSpace((char)peek)) break;
                    _reader.Read();
                }
            }

            class StringReader : IDisposable
            {
                string _s; int _pos;
                public StringReader(string s) { _s = s ?? ""; _pos = 0; }
                public int Peek() { return _pos < _s.Length ? _s[_pos] : -1; }
                public int Read() { return _pos < _s.Length ? _s[_pos++] : -1; }
                public void Dispose() { }
            }
        }

        sealed class Serializer
        {
            StringBuilder _sb = new StringBuilder();

            public static string Serialize(object obj)
            {
                var s = new Serializer();
                s.SerializeValue(obj);
                return s._sb.ToString();
            }

            void SerializeValue(object val)
            {
                if (val == null) { _sb.Append("null"); return; }
                if (val is string s) { SerializeString(s); return; }
                if (val is bool b) { _sb.Append(b ? "true" : "false"); return; }
                if (val is IDictionary<string, object> dict) { SerializeDict(dict); return; }
                if (val is IList<object> list) { SerializeList(list); return; }
                if (val is IList<string> slist) { SerializeStringList(slist); return; }
                if (val is IList<Dictionary<string, object>> dlist) { SerializeDictList(dlist); return; }
                _sb.Append(Convert.ToString(val, System.Globalization.CultureInfo.InvariantCulture));
            }

            void SerializeString(string s)
            {
                _sb.Append('"');
                foreach (char c in s)
                {
                    switch (c)
                    {
                        case '"': _sb.Append("\\\""); break;
                        case '\\': _sb.Append("\\\\"); break;
                        case '\n': _sb.Append("\\n"); break;
                        case '\r': _sb.Append("\\r"); break;
                        case '\t': _sb.Append("\\t"); break;
                        default: _sb.Append(c); break;
                    }
                }
                _sb.Append('"');
            }

            void SerializeDict(IDictionary<string, object> dict)
            {
                _sb.Append('{');
                bool first = true;
                foreach (var kv in dict)
                {
                    if (!first) _sb.Append(',');
                    SerializeString(kv.Key);
                    _sb.Append(':');
                    SerializeValue(kv.Value);
                    first = false;
                }
                _sb.Append('}');
            }

            void SerializeList(IList<object> list)
            {
                _sb.Append('[');
                for (int i = 0; i < list.Count; i++)
                {
                    if (i > 0) _sb.Append(',');
                    SerializeValue(list[i]);
                }
                _sb.Append(']');
            }

            void SerializeStringList(IList<string> list)
            {
                _sb.Append('[');
                for (int i = 0; i < list.Count; i++)
                {
                    if (i > 0) _sb.Append(',');
                    SerializeString(list[i]);
                }
                _sb.Append(']');
            }

            void SerializeDictList(IList<Dictionary<string, object>> list)
            {
                _sb.Append('[');
                for (int i = 0; i < list.Count; i++)
                {
                    if (i > 0) _sb.Append(',');
                    SerializeDict(list[i]);
                }
                _sb.Append(']');
            }
        }
    }
}"""

    # Append MiniJSON lines to main body
    lines.extend(_minijson.split("\n"))
    lines.append("")

    lines = _wrap_namespace(lines, namespace)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# generate_test_runner_handler
# ---------------------------------------------------------------------------

_VALID_QA_TEST_MODES = frozenset({"EditMode", "PlayMode", "Both"})


def generate_test_runner_handler(
    test_mode: str = "EditMode",
    test_filter: str = "",
    timeout_seconds: int = 60,
    namespace: str = "",
) -> str:
    """Generate VBTestRunner.cs: bridge-compatible test runner handler.

    Creates a C# editor script that uses ``TestRunnerApi`` with ``ICallbacks``
    to execute EditMode/PlayMode tests and writes structured JSON results to
    ``Temp/vb_test_results.json``.

    Args:
        test_mode: ``"EditMode"``, ``"PlayMode"``, or ``"Both"``.
        test_filter: Optional test name filter substring.
        timeout_seconds: Maximum time to wait for test completion.
        namespace: Optional C# namespace to wrap the class in.

    Returns:
        Complete C# source string for VBTestRunner.cs.

    Raises:
        ValueError: If test_mode is not a valid value.
    """
    if test_mode not in _VALID_QA_TEST_MODES:
        raise ValueError(
            f"test_mode must be one of {sorted(_VALID_QA_TEST_MODES)}, "
            f"got '{test_mode}'"
        )

    safe_filter = _sanitize_cs_string(test_filter)
    safe_mode = _sanitize_cs_string(test_mode)

    # Build filter name line if provided
    filter_name_line = ""
    if test_filter:
        filter_name_line = (
            '                testNames = new[] { "'
            + safe_filter
            + '" },'
        )

    # Build test mode expression
    if test_mode == "Both":
        mode_expr = "TestMode.EditMode | TestMode.PlayMode"
    else:
        mode_expr = "TestMode." + safe_mode

    lines: list[str] = [
        "using UnityEngine;",
        "using UnityEditor;",
        "using UnityEditor.TestTools.TestRunner.Api;",
        "using System;",
        "using System.Collections.Generic;",
        "using System.Diagnostics;",
        "using System.IO;",
        "using System.Linq;",
        "using System.Text;",
        "",
        "public class VBTestRunner",
        "{",
        '    [MenuItem("VeilBreakers/QA/Run Tests")]',
        "    public static void Execute()",
        "    {",
        "        var api = ScriptableObject.CreateInstance<TestRunnerApi>();",
        "        var collector = new VBTestResultCollector();",
        "        api.RegisterCallbacks(collector);",
        "",
        "        var stopwatch = new Stopwatch();",
        "        stopwatch.Start();",
        "",
        "        api.Execute(new ExecutionSettings",
        "        {",
        "            runSynchronously = true,",
        "            filters = new[] { new Filter",
        "            {",
        "                testMode = " + mode_expr + ",",
    ]

    if filter_name_line:
        lines.append(filter_name_line)

    lines.extend([
        "            }}",
        "        });",
        "",
        "        stopwatch.Stop();",
        "        double totalDuration = stopwatch.Elapsed.TotalSeconds;",
        "",
        "        // Build JSON result",
        "        var sb = new StringBuilder();",
        '        sb.Append("{");',
        '        sb.Append("\\"total\\": " + collector.Details.Count + ", ");',
        '        sb.Append("\\"passed\\": " + collector.PassCount + ", ");',
        '        sb.Append("\\"failed\\": " + collector.FailCount + ", ");',
        '        sb.Append("\\"skipped\\": " + collector.SkipCount + ", ");',
        '        sb.Append("\\"duration\\": " + totalDuration.ToString("F3") + ", ");',
        '        sb.Append("\\"test_mode\\": \\"' + safe_mode + '\\", ");',
        '        sb.Append("\\"tests\\": [");',
        "",
        "        for (int i = 0; i < collector.Details.Count; i++)",
        "        {",
        "            var d = collector.Details[i];",
        '            if (i > 0) sb.Append(", ");',
        '            sb.Append("{");',
        '            sb.Append("\\"testName\\": \\"" + EscapeJson(d.testName) + "\\", ");',
        '            sb.Append("\\"result\\": \\"" + d.result + "\\", ");',
        '            sb.Append("\\"message\\": \\"" + EscapeJson(d.message) + "\\", ");',
        '            sb.Append("\\"stackTrace\\": \\"" + EscapeJson(d.stackTrace) + "\\", ");',
        '            sb.Append("\\"duration\\": " + d.duration.ToString("F4"));',
        '            sb.Append("}");',
        "        }",
        "",
        '        sb.Append("]}");',
        '        File.WriteAllText("Temp/vb_test_results.json", sb.ToString());',
        '        UnityEngine.Debug.Log("[VBTestRunner] Tests complete: "',
        '            + collector.PassCount + " passed, "',
        '            + collector.FailCount + " failed, "',
        '            + collector.SkipCount + " skipped");',
        "    }",
        "",
        "    static string EscapeJson(string s)",
        "    {",
        '        if (s == null) return "";',
        '        return s.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"").Replace("\\n", "\\\\n").Replace("\\r", "\\\\r");',
        "    }",
        "}",
        "",
        "public class VBTestResultCollector : ICallbacks",
        "{",
        "    public int PassCount;",
        "    public int FailCount;",
        "    public int SkipCount;",
        "    public List<TestDetail> Details = new List<TestDetail>();",
        "",
        "    public void RunStarted(ITestAdaptor testsToRun) { }",
        "",
        "    public void RunFinished(ITestResultAdaptor result)",
        "    {",
        "        PassCount = result.PassCount;",
        "        FailCount = result.FailCount;",
        "        SkipCount = result.SkipCount;",
        "    }",
        "",
        "    public void TestStarted(ITestAdaptor test) { }",
        "",
        "    public void TestFinished(ITestResultAdaptor result)",
        "    {",
        "        if (!result.HasChildren)",
        "        {",
        "            Details.Add(new TestDetail",
        "            {",
        "                testName = result.Test.FullName,",
        '                result = result.TestStatus == TestStatus.Passed ? "Passed"',
        '                    : result.TestStatus == TestStatus.Failed ? "Failed" : "Skipped",',
        "                message = result.Message ?? \"\",",
        "                stackTrace = result.StackTrace ?? \"\",",
        "                duration = (float)result.Duration",
        "            });",
        "        }",
        "    }",
        "",
        "    public class TestDetail",
        "    {",
        "        public string testName;",
        "        public string result;",
        "        public string message;",
        "        public string stackTrace;",
        "        public float duration;",
        "    }",
        "}",
    ])

    lines = _wrap_namespace(lines, namespace)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# generate_play_session_script
# ---------------------------------------------------------------------------

def generate_play_session_script(
    steps: list[dict] | None = None,
    timeout_per_step: float = 10.0,
    namespace: str = "",
) -> str:
    """Generate VBPlaySession.cs: automated play session runner.

    Creates a C# editor script that enters Play Mode, runs a coroutine
    processing sequential steps (move_to, interact, wait, verify_state),
    and writes structured JSON results to ``Temp/vb_play_session_results.json``.

    Args:
        steps: List of step dicts. Each dict has ``action``, and action-specific
            params (``position``, ``target``, ``seconds``, ``expected``).
            Defaults to a single wait step.
        timeout_per_step: Maximum seconds per step before timeout.
        namespace: Optional C# namespace to wrap the class in.

    Returns:
        Complete C# source string for VBPlaySession.cs.
    """
    if steps is None:
        steps = [{"action": "wait", "seconds": 2, "expected": "game_loaded"}]

    # Serialize steps into C# array initializer
    step_entries: list[str] = []
    for i, step in enumerate(steps):
        action = _sanitize_cs_string(step.get("action", "wait"))
        expected = _sanitize_cs_string(step.get("expected", ""))
        target = _sanitize_cs_string(step.get("target", ""))
        seconds = step.get("seconds", 0)
        pos = step.get("position", [0, 0, 0])
        if not isinstance(pos, (list, tuple)) or len(pos) < 3:
            pos = [0, 0, 0]

        entry_lines = [
            "            new StepDef {",
            '                action = "' + action + '",',
            '                expected = "' + expected + '",',
            '                target = "' + target + '",',
            "                seconds = " + str(float(seconds)) + "f,",
            "                position = new Vector3("
            + str(float(pos[0])) + "f, "
            + str(float(pos[1])) + "f, "
            + str(float(pos[2])) + "f)",
            "            }",
        ]
        step_entries.append("\n".join(entry_lines))

    steps_init = ",\n".join(step_entries)

    lines: list[str] = [
        "using UnityEngine;",
        "using UnityEditor;",
        "using System;",
        "using System.Collections;",
        "using System.Collections.Generic;",
        "using System.Diagnostics;",
        "using System.IO;",
        "using System.Text;",
        "",
        "public class VBPlaySession",
        "{",
        "    private static List<StepResult> _results = new List<StepResult>();",
        "    private static int _currentStep;",
        "    private static bool _running;",
        "    private static StepDef[] _steps;",
        "    private static float _timeoutPerStep = " + str(float(timeout_per_step)) + "f;",
        "",
        '    [MenuItem("VeilBreakers/QA/Run Play Session")]',
        "    public static void Execute()",
        "    {",
        "        _results.Clear();",
        "        _currentStep = 0;",
        "        _running = true;",
        "",
        "        _steps = new StepDef[]",
        "        {",
        steps_init,
        "        };",
        "",
        "        EditorApplication.EnterPlaymode();",
        "        EditorApplication.playModeStateChanged += OnPlayModeChanged;",
        "    }",
        "",
        "    static void OnPlayModeChanged(PlayModeStateChange state)",
        "    {",
        "        if (state == PlayModeStateChange.EnteredPlayMode && _running)",
        "        {",
        "            var runner = new GameObject(\"VBPlaySessionRunner\").AddComponent<PlaySessionCoroutine>();",
        "            runner.Steps = _steps;",
        "            runner.TimeoutPerStep = _timeoutPerStep;",
        "            runner.OnComplete = OnSessionComplete;",
        "        }",
        "    }",
        "",
        "    static void OnSessionComplete(List<StepResult> results)",
        "    {",
        "        _results = results;",
        "        _running = false;",
        "        EditorApplication.playModeStateChanged -= OnPlayModeChanged;",
        "",
        "        // Write results before exiting play mode",
        "        int passed = 0;",
        "        int failed = 0;",
        "        foreach (var r in _results)",
        "        {",
        "            if (r.passed) passed++;",
        "            else failed++;",
        "        }",
        "",
        "        var sb = new StringBuilder();",
        '        sb.Append("{");',
        '        sb.Append("\\"total_steps\\": " + _results.Count + ", ");',
        '        sb.Append("\\"passed\\": " + passed + ", ");',
        '        sb.Append("\\"failed\\": " + failed + ", ");',
        '        sb.Append("\\"steps\\": [");',
        "",
        "        for (int i = 0; i < _results.Count; i++)",
        "        {",
        "            var r = _results[i];",
        '            if (i > 0) sb.Append(", ");',
        '            sb.Append("{");',
        '            sb.Append("\\"action\\": \\"" + r.action + "\\", ");',
        '            sb.Append("\\"expected\\": \\"" + r.expected + "\\", ");',
        '            sb.Append("\\"actual\\": \\"" + r.actual + "\\", ");',
        '            sb.Append("\\"passed\\": " + (r.passed ? "true" : "false") + ", ");',
        '            sb.Append("\\"duration\\": " + r.duration.ToString("F4"));',
        '            sb.Append("}");',
        "        }",
        "",
        '        sb.Append("]}");',
        '        File.WriteAllText("Temp/vb_play_session_results.json", sb.ToString());',
        "",
        "        EditorApplication.ExitPlaymode();",
        '        UnityEngine.Debug.Log("[VBPlaySession] Complete: " + passed + " passed, " + failed + " failed");',
        "    }",
        "",
        "    public class StepDef",
        "    {",
        "        public string action;",
        "        public string expected;",
        "        public string target;",
        "        public float seconds;",
        "        public Vector3 position;",
        "    }",
        "",
        "    public class StepResult",
        "    {",
        "        public string action;",
        "        public string expected;",
        "        public string actual;",
        "        public bool passed;",
        "        public float duration;",
        "    }",
        "}",
        "",
        "public class PlaySessionCoroutine : MonoBehaviour",
        "{",
        "    public VBPlaySession.StepDef[] Steps;",
        "    public float TimeoutPerStep;",
        "    public Action<List<VBPlaySession.StepResult>> OnComplete;",
        "",
        "    private List<VBPlaySession.StepResult> _results = new List<VBPlaySession.StepResult>();",
        "",
        "    IEnumerator Start()",
        "    {",
        "        yield return null; // Wait one frame for scene initialization",
        "",
        "        foreach (var step in Steps)",
        "        {",
        "            var result = new VBPlaySession.StepResult",
        "            {",
        "                action = step.action,",
        "                expected = step.expected,",
        '                actual = "",',
        "                passed = false,",
        "                duration = 0f",
        "            };",
        "",
        "            float startTime = Time.realtimeSinceStartup;",
        "",
        '            if (step.action == "move_to")',
        "            {",
        '                GameObject player = GameObject.FindWithTag("Player");',
        "                if (player != null)",
        "                {",
        "                    var agent = player.GetComponent<UnityEngine.AI.NavMeshAgent>();",
        "                    if (agent != null)",
        "                        agent.SetDestination(step.position);",
        "                    else",
        "                        player.transform.position = step.position;",
        '                    result.actual = "moved_to_" + step.position;',
        "                    result.passed = true;",
        "                }",
        "                else",
        "                {",
        '                    result.actual = "player_not_found";',
        "                }",
        "            }",
        '            else if (step.action == "interact")',
        "            {",
        "                GameObject target = GameObject.Find(step.target);",
        "                if (target != null)",
        "                {",
        '                    target.SendMessage("Interact", SendMessageOptions.DontRequireReceiver);',
        '                    result.actual = step.target + "_interacted";',
        "                    result.passed = true;",
        "                }",
        "                else",
        "                {",
        '                    result.actual = "target_not_found";',
        "                }",
        "            }",
        '            else if (step.action == "wait")',
        "            {",
        "                yield return new WaitForSeconds(step.seconds);",
        '                result.actual = "waited_" + step.seconds + "s";',
        "                result.passed = true;",
        "            }",
        '            else if (step.action == "verify_state")',
        "            {",
        "                GameObject target = GameObject.Find(step.target);",
        "                if (target != null)",
        "                {",
        '                    result.actual = "found_" + step.target;',
        "                    result.passed = result.actual.Contains(step.expected)",
        "                        || step.expected == result.actual;",
        "                }",
        "                else",
        "                {",
        '                    result.actual = "target_not_found";',
        "                }",
        "            }",
        "",
        "            result.duration = Time.realtimeSinceStartup - startTime;",
        "",
        "            // Timeout check",
        "            if (result.duration > TimeoutPerStep && !result.passed)",
        "            {",
        '                result.actual = "timeout";',
        "            }",
        "",
        "            _results.Add(result);",
        "            yield return null;",
        "        }",
        "",
        "        OnComplete?.Invoke(_results);",
        "        Destroy(gameObject);",
        "    }",
        "}",
    ]

    lines = _wrap_namespace(lines, namespace)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# generate_profiler_handler
# ---------------------------------------------------------------------------

def generate_profiler_handler(
    target_frame_time_ms: float = 16.67,
    max_draw_calls: int = 2000,
    max_memory_mb: int = 1024,
    sample_frames: int = 60,
    namespace: str = "",
) -> str:
    """Generate VBProfiler.cs: GPU/CPU profiler with budget comparison.

    Creates a C# editor script that uses ``ProfilerRecorder.StartNew()``
    to sample frame time, draw calls, batches, memory, and triangles over
    N frames. Compares against budget targets and writes structured JSON
    results to ``Temp/vb_profiler_results.json``.

    Args:
        target_frame_time_ms: Frame time budget in milliseconds.
        max_draw_calls: Maximum draw calls budget.
        max_memory_mb: Maximum memory usage in MB.
        sample_frames: Number of frames to sample.
        namespace: Optional C# namespace to wrap the class in.

    Returns:
        Complete C# source string for VBProfiler.cs.
    """
    lines: list[str] = [
        "using UnityEngine;",
        "using UnityEditor;",
        "using Unity.Profiling;",
        "using System;",
        "using System.Collections;",
        "using System.Collections.Generic;",
        "using System.IO;",
        "using System.Text;",
        "",
        "public class VBProfiler",
        "{",
        "    private static bool _sampling;",
        "    private static int _frameCount;",
        "    private static int _targetFrames = " + str(int(sample_frames)) + ";",
        "    private static float _targetFrameTimeMs = " + str(float(target_frame_time_ms)) + "f;",
        "    private static int _maxDrawCalls = " + str(int(max_draw_calls)) + ";",
        "    private static int _maxMemoryMb = " + str(int(max_memory_mb)) + ";",
        "",
        "    private static ProfilerRecorder _frameTimeRecorder;",
        "    private static ProfilerRecorder _drawCallsRecorder;",
        "    private static ProfilerRecorder _batchesRecorder;",
        "    private static ProfilerRecorder _memoryRecorder;",
        "    private static ProfilerRecorder _trianglesRecorder;",
        "",
        "    private static List<double> _frameTimeSamples = new List<double>();",
        "    private static List<long> _drawCallSamples = new List<long>();",
        "    private static List<long> _batchSamples = new List<long>();",
        "    private static List<long> _memorySamples = new List<long>();",
        "    private static List<long> _triangleSamples = new List<long>();",
        "",
        '    [MenuItem("VeilBreakers/QA/Profile Scene")]',
        "    public static void Execute()",
        "    {",
        "        _frameCount = 0;",
        "        _frameTimeSamples.Clear();",
        "        _drawCallSamples.Clear();",
        "        _batchSamples.Clear();",
        "        _memorySamples.Clear();",
        "        _triangleSamples.Clear();",
        "",
        '        _frameTimeRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Internal, "Main Thread");',
        '        _drawCallsRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Render, "Draw Calls Count");',
        '        _batchesRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Render, "SetPass Calls Count");',
        '        _memoryRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Memory, "System Used Memory");',
        '        _trianglesRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Render, "Triangles Count");',
        "",
        "        _sampling = true;",
        "        EditorApplication.update += SampleFrame;",
        '        UnityEngine.Debug.Log("[VBProfiler] Started profiling for " + _targetFrames + " frames...");',
        "    }",
        "",
        "    static void SampleFrame()",
        "    {",
        "        if (!_sampling) return;",
        "",
        "        // Convert nanoseconds to milliseconds for frame time",
        "        double frameTimeMs = _frameTimeRecorder.LastValue / 1000000.0;",
        "        _frameTimeSamples.Add(frameTimeMs);",
        "        _drawCallSamples.Add(_drawCallsRecorder.LastValue);",
        "        _batchSamples.Add(_batchesRecorder.LastValue);",
        "        _memorySamples.Add(_memoryRecorder.LastValue);",
        "        _triangleSamples.Add(_trianglesRecorder.LastValue);",
        "",
        "        _frameCount++;",
        "        if (_frameCount >= _targetFrames)",
        "        {",
        "            FinishSampling();",
        "        }",
        "    }",
        "",
        "    static void FinishSampling()",
        "    {",
        "        _sampling = false;",
        "        EditorApplication.update -= SampleFrame;",
        "",
        "        _frameTimeRecorder.Dispose();",
        "        _drawCallsRecorder.Dispose();",
        "        _batchesRecorder.Dispose();",
        "        _memoryRecorder.Dispose();",
        "        _trianglesRecorder.Dispose();",
        "",
        "        // Compute min/avg/max for frame time",
        "        double ftMin = double.MaxValue, ftMax = 0, ftSum = 0;",
        "        foreach (var v in _frameTimeSamples) { if (v < ftMin) ftMin = v; if (v > ftMax) ftMax = v; ftSum += v; }",
        "        double ftAvg = ftSum / _frameTimeSamples.Count;",
        "",
        "        // Compute min/avg/max for draw calls",
        "        long dcMin = long.MaxValue, dcMax = 0, dcSum = 0;",
        "        foreach (var v in _drawCallSamples) { if (v < dcMin) dcMin = v; if (v > dcMax) dcMax = v; dcSum += v; }",
        "        double dcAvg = (double)dcSum / _drawCallSamples.Count;",
        "",
        "        // Compute min/avg/max for batches",
        "        long btMin = long.MaxValue, btMax = 0, btSum = 0;",
        "        foreach (var v in _batchSamples) { if (v < btMin) btMin = v; if (v > btMax) btMax = v; btSum += v; }",
        "        double btAvg = (double)btSum / _batchSamples.Count;",
        "",
        "        // Compute min/avg/max for memory (bytes -> MB)",
        "        long memMin = long.MaxValue, memMax = 0, memSum = 0;",
        "        foreach (var v in _memorySamples) { if (v < memMin) memMin = v; if (v > memMax) memMax = v; memSum += v; }",
        "        double memAvgMb = ((double)memSum / _memorySamples.Count) / (1024.0 * 1024.0);",
        "        double memMinMb = memMin / (1024.0 * 1024.0);",
        "        double memMaxMb = memMax / (1024.0 * 1024.0);",
        "",
        "        // Compute min/avg/max for triangles",
        "        long triMin = long.MaxValue, triMax = 0, triSum = 0;",
        "        foreach (var v in _triangleSamples) { if (v < triMin) triMin = v; if (v > triMax) triMax = v; triSum += v; }",
        "        double triAvg = (double)triSum / _triangleSamples.Count;",
        "",
        "        // Budget comparison",
        "        bool ftPassed = ftAvg <= _targetFrameTimeMs;",
        "        bool dcPassed = dcAvg <= _maxDrawCalls;",
        "        bool memPassed = memAvgMb <= _maxMemoryMb;",
        "",
        "        var recommendations = new List<string>();",
        "        if (!ftPassed)",
        '            recommendations.Add("Frame time avg (" + ftAvg.ToString("F2") + "ms) exceeds budget (" + _targetFrameTimeMs + "ms). Reduce per-frame workload.");',
        "        if (!dcPassed)",
        '            recommendations.Add("Draw calls avg (" + dcAvg.ToString("F0") + ") exceeds budget (" + _maxDrawCalls + "). Enable GPU instancing or batching.");',
        "        if (!memPassed)",
        '            recommendations.Add("Memory avg (" + memAvgMb.ToString("F1") + "MB) exceeds budget (" + _maxMemoryMb + "MB). Compress textures or unload unused assets.");',
        "",
        "        // Build JSON",
        "        var sb = new StringBuilder();",
        '        sb.Append("{");',
        '        sb.Append("\\"frames_sampled\\": " + _frameCount + ", ");',
        '        sb.Append("\\"metrics\\": {");',
        "",
        "        // frame_time_ms",
        '        sb.Append("\\"frame_time_ms\\": {");',
        '        sb.Append("\\"min\\": " + ftMin.ToString("F3") + ", ");',
        '        sb.Append("\\"avg\\": " + ftAvg.ToString("F3") + ", ");',
        '        sb.Append("\\"max\\": " + ftMax.ToString("F3") + ", ");',
        '        sb.Append("\\"budget\\": " + _targetFrameTimeMs + ", ");',
        '        sb.Append("\\"passed\\": " + (ftPassed ? "true" : "false"));',
        '        sb.Append("}, ");',
        "",
        "        // draw_calls",
        '        sb.Append("\\"draw_calls\\": {");',
        '        sb.Append("\\"min\\": " + dcMin + ", ");',
        '        sb.Append("\\"avg\\": " + dcAvg.ToString("F0") + ", ");',
        '        sb.Append("\\"max\\": " + dcMax + ", ");',
        '        sb.Append("\\"budget\\": " + _maxDrawCalls + ", ");',
        '        sb.Append("\\"passed\\": " + (dcPassed ? "true" : "false"));',
        '        sb.Append("}, ");',
        "",
        "        // batches",
        '        sb.Append("\\"batches\\": {");',
        '        sb.Append("\\"min\\": " + btMin + ", ");',
        '        sb.Append("\\"avg\\": " + btAvg.ToString("F0") + ", ");',
        '        sb.Append("\\"max\\": " + btMax);',
        '        sb.Append("}, ");',
        "",
        "        // memory_mb",
        '        sb.Append("\\"memory_mb\\": {");',
        '        sb.Append("\\"min\\": " + memMinMb.ToString("F1") + ", ");',
        '        sb.Append("\\"avg\\": " + memAvgMb.ToString("F1") + ", ");',
        '        sb.Append("\\"max\\": " + memMaxMb.ToString("F1") + ", ");',
        '        sb.Append("\\"budget\\": " + _maxMemoryMb + ", ");',
        '        sb.Append("\\"passed\\": " + (memPassed ? "true" : "false"));',
        '        sb.Append("}, ");',
        "",
        "        // triangles",
        '        sb.Append("\\"triangles\\": {");',
        '        sb.Append("\\"min\\": " + triMin + ", ");',
        '        sb.Append("\\"avg\\": " + triAvg.ToString("F0") + ", ");',
        '        sb.Append("\\"max\\": " + triMax);',
        '        sb.Append("}");',
        "",
        '        sb.Append("}, ");',
        "",
        "        // recommendations",
        '        sb.Append("\\"recommendations\\": [");',
        "        for (int i = 0; i < recommendations.Count; i++)",
        "        {",
        '            if (i > 0) sb.Append(", ");',
        '            sb.Append("\\"" + recommendations[i].Replace("\\"", "\\\\\\"") + "\\"");',
        "        }",
        '        sb.Append("]");',
        "",
        '        sb.Append("}");',
        '        File.WriteAllText("Temp/vb_profiler_results.json", sb.ToString());',
        '        UnityEngine.Debug.Log("[VBProfiler] Profiling complete. " + recommendations.Count + " recommendation(s).");',
        "    }",
        "}",
    ]

    lines = _wrap_namespace(lines, namespace)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# generate_memory_leak_script
# ---------------------------------------------------------------------------

def generate_memory_leak_script(
    growth_threshold_mb: int = 10,
    sample_interval_seconds: int = 5,
    sample_count: int = 10,
    namespace: str = "",
) -> str:
    """Generate VBMemoryLeakDetector.cs: managed/native memory leak detector.

    Creates a C# editor script that uses ``ProfilerRecorder`` to capture
    memory snapshots at intervals during Play Mode. Compares baseline vs
    final usage, computes growth rate, and flags leaks if total growth
    exceeds the threshold.

    Args:
        growth_threshold_mb: Memory growth threshold in MB to flag a leak.
        sample_interval_seconds: Seconds between memory samples.
        sample_count: Number of samples to take.
        namespace: Optional C# namespace to wrap the class in.

    Returns:
        Complete C# source string for VBMemoryLeakDetector.cs.
    """
    lines: list[str] = [
        "using UnityEngine;",
        "using UnityEditor;",
        "using Unity.Profiling;",
        "using System;",
        "using System.Collections;",
        "using System.Collections.Generic;",
        "using System.IO;",
        "using System.Text;",
        "",
        "public class VBMemoryLeakDetector",
        "{",
        "    private static bool _sampling;",
        "    private static int _samplesTaken;",
        "    private static int _targetSamples = " + str(int(sample_count)) + ";",
        "    private static float _sampleIntervalSeconds = " + str(float(sample_interval_seconds)) + "f;",
        "    private static float _growthThresholdMb = " + str(float(growth_threshold_mb)) + "f;",
        "    private static float _nextSampleTime;",
        "",
        "    private static ProfilerRecorder _gcMemoryRecorder;",
        "    private static ProfilerRecorder _sysMemoryRecorder;",
        "",
        "    private static double _managedBaselineMb;",
        "    private static double _nativeBaselineMb;",
        "    private static double _peakManagedMb;",
        "    private static double _peakNativeMb;",
        "",
        "    private static List<Dictionary<string, object>> _samples = new List<Dictionary<string, object>>();",
        "",
        '    [MenuItem("VeilBreakers/QA/Detect Memory Leaks")]',
        "    public static void Execute()",
        "    {",
        "        if (!EditorApplication.isPlaying)",
        "        {",
        '            UnityEngine.Debug.LogWarning("[VBMemoryLeakDetector] Must be in Play Mode to detect memory leaks. Enter Play Mode first.");',
        "            return;",
        "        }",
        "",
        "        _samplesTaken = 0;",
        "        _samples.Clear();",
        "        _peakManagedMb = 0;",
        "        _peakNativeMb = 0;",
        "",
        '        _gcMemoryRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Memory, "GC Reserved Memory");',
        '        _sysMemoryRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Memory, "System Used Memory");',
        "",
        "        // Capture baseline",
        "        _managedBaselineMb = _gcMemoryRecorder.LastValue / (1024.0 * 1024.0);",
        "        _nativeBaselineMb = _sysMemoryRecorder.LastValue / (1024.0 * 1024.0);",
        "",
        "        _nextSampleTime = Time.realtimeSinceStartup + _sampleIntervalSeconds;",
        "        _sampling = true;",
        "        EditorApplication.update += SampleMemory;",
        '        UnityEngine.Debug.Log("[VBMemoryLeakDetector] Started sampling. Baseline: managed="',
        '            + _managedBaselineMb.ToString("F1") + "MB, native="',
        '            + _nativeBaselineMb.ToString("F1") + "MB");',
        "    }",
        "",
        "    static void SampleMemory()",
        "    {",
        "        if (!_sampling) return;",
        "",
        "        if (!EditorApplication.isPlaying)",
        "        {",
        "            FinishSampling();",
        "            return;",
        "        }",
        "",
        "        if (Time.realtimeSinceStartup < _nextSampleTime) return;",
        "",
        "        double managedMb = _gcMemoryRecorder.LastValue / (1024.0 * 1024.0);",
        "        double nativeMb = _sysMemoryRecorder.LastValue / (1024.0 * 1024.0);",
        "",
        "        if (managedMb > _peakManagedMb) _peakManagedMb = managedMb;",
        "        if (nativeMb > _peakNativeMb) _peakNativeMb = nativeMb;",
        "",
        "        var sample = new Dictionary<string, object>",
        "        {",
        '            ["timestamp"] = Time.realtimeSinceStartup,',
        '            ["managed_mb"] = managedMb,',
        '            ["native_mb"] = nativeMb,',
        '            ["delta_managed"] = managedMb - _managedBaselineMb,',
        '            ["delta_native"] = nativeMb - _nativeBaselineMb',
        "        };",
        "        _samples.Add(sample);",
        "",
        "        _samplesTaken++;",
        "        _nextSampleTime = Time.realtimeSinceStartup + _sampleIntervalSeconds;",
        "",
        "        if (_samplesTaken >= _targetSamples)",
        "        {",
        "            FinishSampling();",
        "        }",
        "    }",
        "",
        "    static void FinishSampling()",
        "    {",
        "        _sampling = false;",
        "        EditorApplication.update -= SampleMemory;",
        "",
        "        double finalManagedMb = _gcMemoryRecorder.LastValue / (1024.0 * 1024.0);",
        "        double finalNativeMb = _sysMemoryRecorder.LastValue / (1024.0 * 1024.0);",
        "",
        "        _gcMemoryRecorder.Dispose();",
        "        _sysMemoryRecorder.Dispose();",
        "",
        "        double growthManaged = finalManagedMb - _managedBaselineMb;",
        "        double growthNative = finalNativeMb - _nativeBaselineMb;",
        "        double totalGrowth = growthManaged + growthNative;",
        "        double totalTime = _samplesTaken * _sampleIntervalSeconds;",
        "        double growthRate = totalTime > 0 ? totalGrowth / totalTime : 0;",
        "        bool leakDetected = totalGrowth > _growthThresholdMb;",
        "",
        "        // Build JSON",
        "        var sb = new StringBuilder();",
        '        sb.Append("{");',
        '        sb.Append("\\"baseline\\": {");',
        '        sb.Append("\\"managed_mb\\": " + _managedBaselineMb.ToString("F2") + ", ");',
        '        sb.Append("\\"native_mb\\": " + _nativeBaselineMb.ToString("F2"));',
        '        sb.Append("}, ");',
        "",
        '        sb.Append("\\"final\\": {");',
        '        sb.Append("\\"managed_mb\\": " + finalManagedMb.ToString("F2") + ", ");',
        '        sb.Append("\\"native_mb\\": " + finalNativeMb.ToString("F2"));',
        '        sb.Append("}, ");',
        "",
        '        sb.Append("\\"growth\\": {");',
        '        sb.Append("\\"managed_mb\\": " + growthManaged.ToString("F2") + ", ");',
        '        sb.Append("\\"native_mb\\": " + growthNative.ToString("F2") + ", ");',
        '        sb.Append("\\"total_mb\\": " + totalGrowth.ToString("F2"));',
        '        sb.Append("}, ");',
        "",
        '        sb.Append("\\"growth_rate_per_second_mb\\": " + growthRate.ToString("F4") + ", ");',
        '        sb.Append("\\"leak_detected\\": " + (leakDetected ? "true" : "false") + ", ");',
        '        sb.Append("\\"threshold_mb\\": " + _growthThresholdMb + ", ");',
        '        sb.Append("\\"peak_managed_mb\\": " + _peakManagedMb.ToString("F2") + ", ");',
        '        sb.Append("\\"peak_native_mb\\": " + _peakNativeMb.ToString("F2") + ", ");',
        "",
        '        sb.Append("\\"samples\\": [");',
        "        for (int i = 0; i < _samples.Count; i++)",
        "        {",
        "            var s = _samples[i];",
        '            if (i > 0) sb.Append(", ");',
        '            sb.Append("{");',
        '            sb.Append("\\"timestamp\\": " + s["timestamp"] + ", ");',
        '            sb.Append("\\"managed_mb\\": " + s["managed_mb"] + ", ");',
        '            sb.Append("\\"native_mb\\": " + s["native_mb"] + ", ");',
        '            sb.Append("\\"delta_managed\\": " + s["delta_managed"] + ", ");',
        '            sb.Append("\\"delta_native\\": " + s["delta_native"]);',
        '            sb.Append("}");',
        "        }",
        '        sb.Append("]");',
        "",
        '        sb.Append("}");',
        '        File.WriteAllText("Temp/vb_memory_results.json", sb.ToString());',
        "",
        "        string status = leakDetected ? \"LEAK DETECTED\" : \"No leak detected\";",
        '        UnityEngine.Debug.Log("[VBMemoryLeakDetector] " + status',
        '            + ". Growth: " + totalGrowth.ToString("F2") + "MB"',
        '            + " (threshold: " + _growthThresholdMb + "MB)");',
        "    }",
        "}",
    ]

    lines = _wrap_namespace(lines, namespace)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# analyze_csharp_static (Python-side static analysis)
# ---------------------------------------------------------------------------

ANTI_PATTERNS: dict[str, dict] = {
    "camera_main_in_update": {
        "pattern": r"Camera\.main",
        "context": r"void\s+(Update|FixedUpdate|LateUpdate)\s*\(",
        "severity": "warning",
        "message": "Camera.main in Update loop -- cache in Awake/Start",
        "fix": "private Camera _mainCam; void Awake() { _mainCam = Camera.main; }",
    },
    "getcomponent_in_update": {
        "pattern": r"GetComponent<\w+>\(\)",
        "context": r"void\s+(Update|FixedUpdate|LateUpdate)\s*\(",
        "severity": "warning",
        "message": "GetComponent in Update loop -- cache in Awake/Start",
        "fix": "Cache the component in a field during Awake() or Start()",
    },
    "find_object_at_runtime": {
        "pattern": r"FindObjectOfType|FindObjectsOfType|FindFirstObjectByType",
        "context": r"void\s+(Update|FixedUpdate|LateUpdate|OnTrigger|OnCollision)",
        "severity": "error",
        "message": "FindObjectOfType in hot path -- use cached references",
        "fix": "Cache the reference in Awake/Start or use dependency injection",
    },
    "string_concat_in_update": {
        "pattern": r'\+\s*"[^"]*"|\"\s*\+',
        "context": r"void\s+(Update|FixedUpdate|LateUpdate)\s*\(",
        "severity": "info",
        "message": "String concatenation in Update -- use StringBuilder or interpolation cache",
        "fix": "Use StringBuilder or cache the formatted string",
    },
    "linq_in_update": {
        "pattern": r"\.(Where|Select|Any|All|First|Last|Count|OrderBy|GroupBy|ToList|ToArray)\s*\(",
        "context": r"void\s+(Update|FixedUpdate|LateUpdate)\s*\(",
        "severity": "warning",
        "message": "LINQ in Update loop -- allocates enumerators each frame",
        "fix": "Pre-compute LINQ results or use manual loops",
    },
    "new_allocation_in_update": {
        "pattern": r"\bnew\s+\w+[<\[\(]",
        "context": r"void\s+(Update|FixedUpdate|LateUpdate)\s*\(",
        "severity": "warning",
        "message": "Allocation in Update loop -- consider object pooling",
        "fix": "Use object pooling or pre-allocate collections",
    },
}

# Hot method names that indicate performance-critical code paths
_HOT_METHODS = frozenset({
    "Update", "FixedUpdate", "LateUpdate",
    "OnTriggerEnter", "OnTriggerStay", "OnTriggerExit",
    "OnCollisionEnter", "OnCollisionStay", "OnCollisionExit",
})


def analyze_csharp_static(
    source_code: str,
    file_path: str = "<unknown>",
) -> dict:
    """Perform regex-based static analysis on C# source code.

    Scans for common Unity performance anti-patterns within hot method
    bodies (Update, FixedUpdate, LateUpdate, OnTrigger*, OnCollision*).

    Args:
        source_code: Complete C# source code string.
        file_path: File path for reporting (not accessed, just metadata).

    Returns:
        Dict with keys: file_path, findings_count, findings (list of dicts),
        summary (errors, warnings, infos counts).
    """
    if not source_code or not source_code.strip():
        return {
            "file_path": file_path,
            "findings_count": 0,
            "findings": [],
            "summary": {"errors": 0, "warnings": 0, "infos": 0},
        }

    lines = source_code.split("\n")
    findings: list[dict] = []

    # Track which method body each line belongs to using brace counting
    in_hot_method = False
    hot_method_name = ""
    brace_depth = 0
    method_start_depth = 0

    for line_num, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Detect entry into a hot method
        if not in_hot_method:
            for method_name in _HOT_METHODS:
                # Match method declarations like: void Update() {
                # or: void Update()
                pattern = r"void\s+" + re.escape(method_name) + r"\s*\("
                if re.search(pattern, stripped):
                    in_hot_method = True
                    hot_method_name = method_name
                    method_start_depth = brace_depth
                    break

        # Count braces on this line
        for ch in stripped:
            if ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
                # Check if we've exited the hot method
                if in_hot_method and brace_depth <= method_start_depth:
                    in_hot_method = False
                    hot_method_name = ""

        # If we're inside a hot method, check for anti-patterns
        if in_hot_method:
            for rule_name, rule in ANTI_PATTERNS.items():
                if re.search(rule["pattern"], stripped):
                    # Verify the context matches (some rules are specific)
                    context_pattern = rule.get("context", "")
                    if context_pattern:
                        # Check if hot_method_name matches context
                        context_methods = re.findall(
                            r"Update|FixedUpdate|LateUpdate|OnTrigger|OnCollision",
                            context_pattern,
                        )
                        method_prefix = hot_method_name
                        # For OnTrigger/OnCollision, match prefix
                        matches_context = any(
                            method_prefix.startswith(cm)
                            for cm in context_methods
                        )
                        if not matches_context:
                            continue

                    findings.append({
                        "rule_name": rule_name,
                        "severity": rule["severity"],
                        "line_number": line_num,
                        "line_content": stripped,
                        "message": rule["message"],
                        "fix": rule.get("fix", ""),
                    })

    # Build summary
    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    infos = sum(1 for f in findings if f["severity"] == "info")

    return {
        "file_path": file_path,
        "findings_count": len(findings),
        "findings": findings,
        "summary": {"errors": errors, "warnings": warnings, "infos": infos},
    }


# ---------------------------------------------------------------------------
# generate_crash_reporting_script
# ---------------------------------------------------------------------------

def generate_crash_reporting_script(
    dsn: str = "",
    environment: str = "development",
    enable_breadcrumbs: bool = True,
    sample_rate: float = 1.0,
    namespace: str = "",
) -> str:
    """Generate VBCrashReporting.cs: Sentry SDK crash reporting setup.

    Produces a runtime script that initializes the Sentry Unity SDK via
    ``[RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]``.
    When DSN is empty, all capture calls fall back to Unity ``Debug.Log``
    instead of sending to Sentry.

    Args:
        dsn: Sentry DSN endpoint. Empty string enables fallback logging.
        environment: Environment tag (development, staging, production).
        enable_breadcrumbs: Hook Application.logMessageReceived for breadcrumbs.
        sample_rate: Event sample rate (0.0 to 1.0).
        namespace: Optional C# namespace to wrap the class in.

    Returns:
        Complete C# source string for VBCrashReporting.cs.
    """
    safe_dsn = _sanitize_cs_string(dsn)
    safe_env = _sanitize_cs_string(environment)

    lines: list[str] = [
        "// VBCrashReporting.cs -- Generated by VeilBreakers MCP Toolkit",
        "// Requires Sentry Unity SDK: install via UPM or add to manifest.json",
        "// If DSN is empty, all capture calls fall back to Debug.Log",
        "#if SENTRY_AVAILABLE",
        "using Sentry;",
        "using Sentry.Unity;",
        "#endif",
        "using UnityEngine;",
        "",
        "public static class VBCrashReporting",
        "{",
        '    private static string _dsn = "' + safe_dsn + '";',
        "    private static bool _initialized = false;",
        "",
        "    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]",
        "    static void Initialize()",
        "    {",
        "        if (_initialized) return;",
        "        _initialized = true;",
        "",
        '        if (string.IsNullOrEmpty(_dsn))',
        "        {",
        '            Debug.Log("[VBCrashReporting] No DSN configured -- using fallback console logging.");',
        "            return;",
        "        }",
        "",
        "#if SENTRY_AVAILABLE",
        "        SentrySdk.Init(options =>",
        "        {",
        '            options.Dsn = "' + safe_dsn + '";',
        '            options.Environment = "' + safe_env + '";',
        "            options.SampleRate = " + str(sample_rate) + "f;",
        "            options.AutoSessionTracking = true;",
        "        });",
        '        Debug.Log("[VBCrashReporting] Sentry initialized for environment: ' + safe_env + '");',
    ]

    if enable_breadcrumbs:
        lines.extend([
            "",
            "        Application.logMessageReceived += OnLogMessageReceived;",
        ])

    lines.extend([
        "#endif",
        "    }",
    ])

    if enable_breadcrumbs:
        lines.extend([
            "",
            "    static void OnLogMessageReceived(string condition, string stackTrace, LogType type)",
            "    {",
            "        if (type == LogType.Warning || type == LogType.Error || type == LogType.Exception)",
            "        {",
            "#if SENTRY_AVAILABLE",
            "            SentrySdk.AddBreadcrumb(",
            "                message: condition,",
            '                category: "unity.log",',
            "                level: type == LogType.Warning ? BreadcrumbLevel.Warning : BreadcrumbLevel.Error",
            "            );",
            "#endif",
            "        }",
            "    }",
        ])

    lines.extend([
        "",
        "    // ----- Public Helpers -----",
        "",
        "    public static void CaptureException(System.Exception e)",
        "    {",
        '        if (string.IsNullOrEmpty(_dsn))',
        "        {",
        '            Debug.LogError("[VBCrashReporting] Exception: " + e.Message + "\\n" + e.StackTrace);',
        "            return;",
        "        }",
        "#if SENTRY_AVAILABLE",
        "        SentrySdk.CaptureException(e);",
        "#endif",
        "    }",
        "",
        "    public static void CaptureMessage(string msg, string level = \"Info\")",
        "    {",
        '        if (string.IsNullOrEmpty(_dsn))',
        "        {",
        '            Debug.Log("[VBCrashReporting] Message (" + level + "): " + msg);',
        "            return;",
        "        }",
        "#if SENTRY_AVAILABLE",
        "        SentrySdk.CaptureMessage(msg);",
        "#endif",
        "    }",
        "",
        "    public static void SetTag(string key, string value)",
        "    {",
        '        if (string.IsNullOrEmpty(_dsn))',
        "        {",
        '            Debug.Log("[VBCrashReporting] SetTag: " + key + " = " + value);',
        "            return;",
        "        }",
        "#if SENTRY_AVAILABLE",
        "        SentrySdk.ConfigureScope(scope => scope.SetTag(key, value));",
        "#endif",
        "    }",
        "",
        "    public static void SetUser(string id, string username)",
        "    {",
        '        if (string.IsNullOrEmpty(_dsn))',
        "        {",
        '            Debug.Log("[VBCrashReporting] SetUser: " + id + " (" + username + ")");',
        "            return;",
        "        }",
        "#if SENTRY_AVAILABLE",
        "        SentrySdk.ConfigureScope(scope =>",
        "        {",
        "            scope.User = new SentryUser",
        "            {",
        "                Id = id,",
        "                Username = username",
        "            };",
        "        });",
        "#endif",
        "    }",
        "}",
    ])

    lines = _wrap_namespace(lines, namespace)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# generate_analytics_script
# ---------------------------------------------------------------------------

_DEFAULT_EVENT_NAMES = [
    "level_start",
    "level_complete",
    "item_acquired",
    "enemy_killed",
    "player_death",
    "session_start",
    "session_end",
]


def _event_method_name(event_name: str) -> str:
    """Convert snake_case event name to PascalCase method name."""
    return "Track" + "".join(word.capitalize() for word in event_name.split("_"))


def _event_method_params(event_name: str) -> str:
    """Return typed parameters for a convenience event method."""
    param_map = {
        "level_start": "int level",
        "level_complete": "int level, float duration",
        "item_acquired": "string itemName, string rarity",
        "enemy_killed": "string enemyType, int damage",
        "player_death": "string cause, int level",
        "session_start": "",
        "session_end": "",
    }
    return param_map.get(event_name, "")


def _event_method_body(event_name: str) -> list[str]:
    """Return the body lines for a convenience event method."""
    body_map = {
        "level_start": [
            "        var props = new Dictionary<string, object>",
            "        {",
            '            ["level"] = level',
            "        };",
            '        TrackEvent("level_start", props);',
        ],
        "level_complete": [
            "        var props = new Dictionary<string, object>",
            "        {",
            '            ["level"] = level,',
            '            ["duration"] = duration',
            "        };",
            '        TrackEvent("level_complete", props);',
        ],
        "item_acquired": [
            "        var props = new Dictionary<string, object>",
            "        {",
            '            ["itemName"] = itemName,',
            '            ["rarity"] = rarity',
            "        };",
            '        TrackEvent("item_acquired", props);',
        ],
        "enemy_killed": [
            "        var props = new Dictionary<string, object>",
            "        {",
            '            ["enemyType"] = enemyType,',
            '            ["damage"] = damage',
            "        };",
            '        TrackEvent("enemy_killed", props);',
        ],
        "player_death": [
            "        var props = new Dictionary<string, object>",
            "        {",
            '            ["cause"] = cause,',
            '            ["level"] = level',
            "        };",
            '        TrackEvent("player_death", props);',
        ],
        "session_start": [
            '        TrackEvent("session_start", null);',
        ],
        "session_end": [
            '        TrackEvent("session_end", null);',
        ],
    }
    default_body = [
        '        TrackEvent("' + event_name + '", null);',
    ]
    return body_map.get(event_name, default_body)


def generate_analytics_script(
    event_names: list[str] | None = None,
    flush_interval_seconds: int = 30,
    max_buffer_size: int = 100,
    log_file_path: str = "Analytics/events.json",
    namespace: str = "",
) -> str:
    """Generate VBAnalytics.cs: singleton analytics manager.

    Produces a runtime MonoBehaviour singleton that buffers events in
    memory and flushes them to a JSON file on disk. Generates typed
    convenience methods for each event name.

    Args:
        event_names: List of event names to generate typed methods for.
            Defaults to standard game events if None.
        flush_interval_seconds: Seconds between automatic flushes.
        max_buffer_size: Max events before forced flush.
        log_file_path: Path relative to Application.persistentDataPath.
        namespace: Optional C# namespace to wrap the class in.

    Returns:
        Complete C# source string for VBAnalytics.cs.
    """
    if event_names is None:
        event_names = list(_DEFAULT_EVENT_NAMES)

    safe_log_path = _sanitize_cs_string(log_file_path)

    lines: list[str] = [
        "// VBAnalytics.cs -- Generated by VeilBreakers MCP Toolkit",
        "using UnityEngine;",
        "using System;",
        "using System.Collections.Generic;",
        "using System.IO;",
        "",
        "public class VBAnalytics : MonoBehaviour",
        "{",
        "    // ----- Singleton -----",
        "",
        "    private static VBAnalytics _instance;",
        "    public static VBAnalytics Instance",
        "    {",
        "        get",
        "        {",
        "            if (_instance == null)",
        "            {",
        '                GameObject go = new GameObject("[VBAnalytics]");',
        "                _instance = go.AddComponent<VBAnalytics>();",
        "                DontDestroyOnLoad(go);",
        "            }",
        "            return _instance;",
        "        }",
        "    }",
        "",
        "    // ----- Configuration -----",
        "",
        "    private string _sessionId;",
        "    private List<Dictionary<string, object>> _eventBuffer = new List<Dictionary<string, object>>();",
        "    private float _lastFlushTime;",
        "    private int _flushIntervalSeconds = " + str(flush_interval_seconds) + ";",
        "    private int _maxBufferSize = " + str(max_buffer_size) + ";",
        '    private string _logFilePath = "' + safe_log_path + '";',
        "",
        "    // ----- Lifecycle -----",
        "",
        "    void Awake()",
        "    {",
        "        if (_instance != null && _instance != this)",
        "        {",
        "            Destroy(gameObject);",
        "            return;",
        "        }",
        "        _instance = this;",
        "        DontDestroyOnLoad(gameObject);",
        "",
        "        _sessionId = Guid.NewGuid().ToString();",
        "        _lastFlushTime = Time.realtimeSinceStartup;",
        '        TrackSessionStart();',
        "    }",
        "",
        "    void Update()",
        "    {",
        "        if (Time.realtimeSinceStartup - _lastFlushTime >= _flushIntervalSeconds)",
        "        {",
        "            FlushEvents();",
        "            _lastFlushTime = Time.realtimeSinceStartup;",
        "        }",
        "    }",
        "",
        "    void OnApplicationQuit()",
        "    {",
        '        TrackSessionEnd();',
        "        FlushEvents();",
        "    }",
        "",
        "    // ----- Core API -----",
        "",
        "    public void TrackEvent(string eventName, Dictionary<string, object> properties = null)",
        "    {",
        "        var eventRecord = new Dictionary<string, object>",
        "        {",
        '            ["eventName"] = eventName,',
        '            ["timestamp"] = DateTime.UtcNow.ToString("o"),',
        '            ["sessionId"] = _sessionId',
        "        };",
        "",
        "        if (properties != null)",
        "        {",
        "            foreach (var kv in properties)",
        "            {",
        '                eventRecord["prop_" + kv.Key] = kv.Value;',
        "            }",
        "        }",
        "",
        "        _eventBuffer.Add(eventRecord);",
        "",
        "        if (_eventBuffer.Count >= _maxBufferSize)",
        "        {",
        "            FlushEvents();",
        "            _lastFlushTime = Time.realtimeSinceStartup;",
        "        }",
        "    }",
        "",
        "    public void FlushEvents()",
        "    {",
        "        if (_eventBuffer.Count == 0) return;",
        "",
        "        // Sanitize: strip any directory traversal from the configured path",
        "        string safePath = _logFilePath.Replace(\"..\", \"\").TrimStart(Path.DirectorySeparatorChar).TrimStart(Path.AltDirectorySeparatorChar);",
        "        if (Path.IsPathRooted(safePath)) safePath = Path.GetFileName(safePath);",
        "        string fullPath = Path.Combine(Application.persistentDataPath, safePath);",
        "        string dir = Path.GetDirectoryName(fullPath);",
        "        if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))",
        "            Directory.CreateDirectory(dir);",
        "",
        "        // Serialize events as JSON array",
        "        string json = SerializeEventsToJson(_eventBuffer);",
        "",
        "        // Append to file",
        "        File.AppendAllText(fullPath, json + \"\\n\");",
        "",
        "        _eventBuffer.Clear();",
        '        Debug.Log("[VBAnalytics] Flushed events to: " + fullPath);',
        "    }",
        "",
        "    // ----- JSON Serialization -----",
        "",
        "    private string SerializeEventsToJson(List<Dictionary<string, object>> events)",
        "    {",
        '        var sb = new System.Text.StringBuilder();',
        '        sb.Append("[");',
        "        for (int i = 0; i < events.Count; i++)",
        "        {",
        '            if (i > 0) sb.Append(",");',
        '            sb.Append("{");',
        "            bool first = true;",
        "            foreach (var kv in events[i])",
        "            {",
        '                if (!first) sb.Append(",");',
        '                sb.Append("\\"");',
        "                sb.Append(EscapeJsonString(kv.Key));",
        '                sb.Append("\\":");',
        "                if (kv.Value is string s)",
        "                {",
        '                    sb.Append("\\"");',
        "                    sb.Append(EscapeJsonString(s));",
        '                    sb.Append("\\"");',
        "                }",
        "                else if (kv.Value is bool b)",
        "                {",
        '                    sb.Append(b ? "true" : "false");',
        "                }",
        "                else if (kv.Value == null)",
        "                {",
        '                    sb.Append("null");',
        "                }",
        "                else",
        "                {",
        "                    sb.Append(kv.Value.ToString());",
        "                }",
        "                first = false;",
        "            }",
        '            sb.Append("}");',
        "        }",
        '        sb.Append("]");',
        "        return sb.ToString();",
        "    }",
        "",
        "    private string EscapeJsonString(string s)",
        "    {",
        '        if (s == null) return "";',
        '        return s.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"").Replace("\\n", "\\\\n").Replace("\\r", "\\\\r");',
        "    }",
        "",
        "    // ----- Typed Convenience Methods -----",
        "",
    ]

    # Generate typed convenience methods for each event name
    for event_name in event_names:
        method_name = _event_method_name(event_name)
        params = _event_method_params(event_name)
        body_lines = _event_method_body(event_name)

        lines.append("    public void " + method_name + "(" + params + ")")
        lines.append("    {")
        lines.extend(body_lines)
        lines.append("    }")
        lines.append("")

    lines.append("}")

    lines = _wrap_namespace(lines, namespace)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# generate_live_inspector_script
# ---------------------------------------------------------------------------

def generate_live_inspector_script(
    update_interval_frames: int = 10,
    max_tracked_objects: int = 20,
    namespace: str = "",
) -> str:
    """Generate VBLiveInspector.cs: IMGUI EditorWindow for live state inspection.

    Produces an EditorWindow that polls selected GameObjects during Play
    Mode, enumerating component fields and properties via Reflection.
    Supports pinning objects for comparison, search/filter, and special
    formatting for common types (Vector3, Color, bool).

    Args:
        update_interval_frames: Frames between refresh polls.
        max_tracked_objects: Maximum objects in the pinned list.
        namespace: Optional C# namespace to wrap the class in.

    Returns:
        Complete C# source string for VBLiveInspector.cs.
    """
    lines: list[str] = [
        "// VBLiveInspector.cs -- Generated by VeilBreakers MCP Toolkit",
        "using UnityEngine;",
        "using UnityEditor;",
        "using System;",
        "using System.Collections.Generic;",
        "using System.Reflection;",
        "using System.Linq;",
        "",
        "public class VBLiveInspector : EditorWindow",
        "{",
        '    [MenuItem("VeilBreakers/QA/Live Inspector")]',
        "    public static void ShowWindow()",
        "    {",
        '        GetWindow<VBLiveInspector>("VB Live Inspector");',
        "    }",
        "",
        "    // ----- Configuration -----",
        "",
        "    private int _updateIntervalFrames = " + str(update_interval_frames) + ";",
        "    private int _maxTrackedObjects = " + str(max_tracked_objects) + ";",
        "    private int _frameCounter;",
        "",
        "    // ----- State -----",
        "",
        "    private Vector2 _scrollPosition;",
        "    private string _searchFilter = \"\";",
        "    private List<GameObject> _pinnedObjects = new List<GameObject>();",
        "    private Dictionary<string, bool> _componentFoldouts = new Dictionary<string, bool>();",
        "    private Dictionary<int, ComponentData[]> _cachedData = new Dictionary<int, ComponentData[]>();",
        "",
        "    // ----- Data Structures -----",
        "",
        "    private struct FieldData",
        "    {",
        "        public string Name;",
        "        public string TypeName;",
        "        public object Value;",
        "    }",
        "",
        "    private struct ComponentData",
        "    {",
        "        public string Name;",
        "        public FieldData[] Fields;",
        "    }",
        "",
        "    // ----- Lifecycle -----",
        "",
        "    void OnEnable()",
        "    {",
        "        EditorApplication.update += OnEditorUpdate;",
        "    }",
        "",
        "    void OnDisable()",
        "    {",
        "        EditorApplication.update -= OnEditorUpdate;",
        "    }",
        "",
        "    void OnEditorUpdate()",
        "    {",
        "        if (!EditorApplication.isPlaying) return;",
        "",
        "        _frameCounter++;",
        "        if (_frameCounter < _updateIntervalFrames) return;",
        "        _frameCounter = 0;",
        "",
        "        RefreshCachedData();",
        "        Repaint();",
        "    }",
        "",
        "    // ----- Data Collection -----",
        "",
        "    void RefreshCachedData()",
        "    {",
        "        _cachedData.Clear();",
        "",
        "        // Current selection",
        "        if (Selection.activeGameObject != null)",
        "        {",
        "            CacheGameObjectData(Selection.activeGameObject);",
        "        }",
        "",
        "        // Pinned objects",
        "        for (int i = _pinnedObjects.Count - 1; i >= 0; i--)",
        "        {",
        "            if (_pinnedObjects[i] == null)",
        "            {",
        "                _pinnedObjects.RemoveAt(i);",
        "                continue;",
        "            }",
        "            CacheGameObjectData(_pinnedObjects[i]);",
        "        }",
        "    }",
        "",
        "    void CacheGameObjectData(GameObject go)",
        "    {",
        "        int id = go.GetInstanceID();",
        "        if (_cachedData.ContainsKey(id)) return;",
        "",
        "        Component[] components = go.GetComponents<Component>();",
        "        var compDataList = new List<ComponentData>();",
        "",
        "        foreach (Component comp in components)",
        "        {",
        "            if (comp == null) continue;",
        "            Type compType = comp.GetType();",
        "",
        "            // Get public fields",
        "            FieldInfo[] fields = compType.GetFields(BindingFlags.Public | BindingFlags.Instance);",
        "            PropertyInfo[] properties = compType.GetProperties(BindingFlags.Public | BindingFlags.Instance);",
        "",
        "            var fieldDataList = new List<FieldData>();",
        "",
        "            foreach (FieldInfo fi in fields)",
        "            {",
        "                try",
        "                {",
        "                    fieldDataList.Add(new FieldData",
        "                    {",
        "                        Name = fi.Name,",
        "                        TypeName = fi.FieldType.Name,",
        "                        Value = fi.GetValue(comp)",
        "                    });",
        "                }",
        "                catch (Exception) { }",
        "            }",
        "",
        "            foreach (PropertyInfo pi in properties)",
        "            {",
        "                if (!pi.CanRead || pi.GetIndexParameters().Length > 0) continue;",
        "                try",
        "                {",
        "                    fieldDataList.Add(new FieldData",
        "                    {",
        "                        Name = pi.Name,",
        "                        TypeName = pi.PropertyType.Name,",
        "                        Value = pi.GetValue(comp)",
        "                    });",
        "                }",
        "                catch (Exception) { }",
        "            }",
        "",
        "            compDataList.Add(new ComponentData",
        "            {",
        "                Name = compType.Name,",
        "                Fields = fieldDataList.ToArray()",
        "            });",
        "        }",
        "",
        "        _cachedData[id] = compDataList.ToArray();",
        "    }",
        "",
        "    // ----- IMGUI -----",
        "",
        "    void OnGUI()",
        "    {",
        "        // Play Mode check",
        "        if (!EditorApplication.isPlaying)",
        "        {",
        '            EditorGUILayout.HelpBox("Enter Play Mode to inspect live state", MessageType.Warning);',
        "            return;",
        "        }",
        "",
        "        // Search filter",
        '        _searchFilter = EditorGUILayout.TextField("Search", _searchFilter);',
        "        EditorGUILayout.Space();",
        "",
        "        // Pin current selection button",
        "        EditorGUILayout.BeginHorizontal();",
        '        if (GUILayout.Button("Pin Selected") && Selection.activeGameObject != null)',
        "        {",
        "            if (!_pinnedObjects.Contains(Selection.activeGameObject) && _pinnedObjects.Count < _maxTrackedObjects)",
        "            {",
        "                _pinnedObjects.Add(Selection.activeGameObject);",
        "            }",
        "        }",
        '        if (GUILayout.Button("Clear Pins"))',
        "        {",
        "            _pinnedObjects.Clear();",
        "        }",
        '        EditorGUILayout.LabelField("Pinned: " + _pinnedObjects.Count + "/" + _maxTrackedObjects);',
        "        EditorGUILayout.EndHorizontal();",
        "        EditorGUILayout.Space();",
        "",
        "        // Scroll view",
        "        _scrollPosition = EditorGUILayout.BeginScrollView(_scrollPosition);",
        "",
        "        // Current selection",
        "        if (Selection.activeGameObject != null)",
        "        {",
        "            DrawGameObjectInspector(Selection.activeGameObject, true);",
        "        }",
        "",
        "        // Pinned objects",
        "        foreach (GameObject pinned in _pinnedObjects)",
        "        {",
        "            if (pinned != null && pinned != Selection.activeGameObject)",
        "            {",
        "                DrawGameObjectInspector(pinned, false);",
        "            }",
        "        }",
        "",
        "        EditorGUILayout.EndScrollView();",
        "    }",
        "",
        "    void DrawGameObjectInspector(GameObject go, bool isSelection)",
        "    {",
        '        string prefix = isSelection ? "[Selected] " : "[Pinned] ";',
        "        EditorGUILayout.LabelField(prefix + go.name, EditorStyles.boldLabel);",
        '        EditorGUILayout.LabelField("Active: " + go.activeSelf + "  Layer: " + LayerMask.LayerToName(go.layer));',
        "",
        "        int id = go.GetInstanceID();",
        "        ComponentData[] compData;",
        "        if (!_cachedData.TryGetValue(id, out compData)) return;",
        "",
        "        foreach (ComponentData cd in compData)",
        "        {",
        "            string foldoutKey = id + \"_\" + cd.Name;",
        "            if (!_componentFoldouts.ContainsKey(foldoutKey))",
        "                _componentFoldouts[foldoutKey] = false;",
        "",
        "            _componentFoldouts[foldoutKey] = EditorGUILayout.Foldout(_componentFoldouts[foldoutKey], cd.Name, true);",
        "",
        "            if (_componentFoldouts[foldoutKey])",
        "            {",
        "                EditorGUI.indentLevel++;",
        "                foreach (FieldData fd in cd.Fields)",
        "                {",
        "                    // Apply search filter",
        "                    if (!string.IsNullOrEmpty(_searchFilter) &&",
        "                        !fd.Name.ToLower().Contains(_searchFilter.ToLower()))",
        "                        continue;",
        "",
        "                    // Check for FSM/state machine state",
        '                    if (fd.Name == "currentState" || fd.Name == "_state")',
        "                    {",
        '                        EditorGUILayout.LabelField("STATE: " + fd.Name, fd.Value != null ? fd.Value.ToString() : "null", EditorStyles.helpBox);',
        "                        continue;",
        "                    }",
        "",
        "                    DrawFieldValue(fd);",
        "                }",
        "                EditorGUI.indentLevel--;",
        "            }",
        "        }",
        "",
        "        EditorGUILayout.Space();",
        "    }",
        "",
        "    void DrawFieldValue(FieldData fd)",
        "    {",
        "        string label = fd.Name + \" (\" + fd.TypeName + \")\";",
        "",
        "        if (fd.Value == null)",
        "        {",
        '            EditorGUILayout.LabelField(label, "null");',
        "            return;",
        "        }",
        "",
        "        // Special formatting for common types",
        '        if (fd.TypeName == "Vector3" && fd.Value is Vector3 v3)',
        "        {",
        '            EditorGUILayout.LabelField(label, "x:" + v3.x.ToString("F2") + " y:" + v3.y.ToString("F2") + " z:" + v3.z.ToString("F2"));',
        "        }",
        '        else if (fd.TypeName == "Color" && fd.Value is Color col)',
        "        {",
        "            EditorGUILayout.BeginHorizontal();",
        "            EditorGUILayout.LabelField(label);",
        "            EditorGUILayout.ColorField(col);",
        "            EditorGUILayout.EndHorizontal();",
        "        }",
        '        else if (fd.TypeName == "Boolean" && fd.Value is bool bVal)',
        "        {",
        "            EditorGUILayout.Toggle(label, bVal);",
        "        }",
        "        else",
        "        {",
        "            EditorGUILayout.LabelField(label, fd.Value.ToString());",
        "        }",
        "    }",
        "}",
    ]

    lines = _wrap_namespace(lines, namespace)
    return "\n".join(lines) + "\n"
