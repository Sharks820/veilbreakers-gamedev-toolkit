"""Unity TCP bridge addon C# template generators.

Generates two C# scripts that form the Unity-side TCP bridge addon:

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

Exports:
    generate_bridge_server_script   -- VBBridgeServer.cs generator
    generate_bridge_commands_script -- VBBridgeCommands.cs generator
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
        "            catch (SocketException) { if (_running) throw; }",
        "            catch (ObjectDisposedException) { break; }",
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
        "        finally { try { client.Close(); } catch (Exception) { } }",
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
        '        return new Dictionary<string, object> { ["path"] = Path.GetFullPath(path), ["captured"] = true };',
        "    }",
        "",
        "    static Dictionary<string, object> HandleConsoleLogs(Dictionary<string, object> p)",
        "    {",
        '        int count = p.ContainsKey("count") ? Convert.ToInt32(p["count"]) : 50;',
        '        string filter = p.ContainsKey("filter") ? p["filter"].ToString() : "all";',
        "        List<Dictionary<string, object>> logs = new List<Dictionary<string, object>>();",
        "",
        "        // Collect via LogEntries reflection (internal Unity API)",
        '        Type logEntriesType = Type.GetType("UnityEditor.LogEntries, UnityEditor");',
        "        if (logEntriesType != null)",
        "        {",
        '            var getCount = logEntriesType.GetMethod("GetCount",',
        "                System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.Public);",
        "            if (getCount != null)",
        "            {",
        "                int total = (int)getCount.Invoke(null, null);",
        "                int start = Math.Max(0, total - count);",
        "                for (int i = start; i < total; i++)",
        "                {",
        "                    logs.Add(new Dictionary<string, object>",
        "                    {",
        '                        ["message"] = "LogEntry_" + i,',
        '                        ["type"] = "Log",',
        '                        ["stackTrace"] = ""',
        "                    });",
        "                }",
        "            }",
        "        }",
        '        return new Dictionary<string, object> { ["logs"] = logs };',
        "    }",
        "",
        "    static Dictionary<string, object> HandleReadResult(Dictionary<string, object> p)",
        "    {",
        '        string resultPath = "Temp/vb_result.json";',
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
                _reader.Read(); // {
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
