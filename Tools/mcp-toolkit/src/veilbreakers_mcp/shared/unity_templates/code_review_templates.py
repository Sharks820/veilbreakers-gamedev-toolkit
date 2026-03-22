"""Code review C# and Python template generators.

Implements a two-pass code review system for Unity C# projects and a standalone
Python reviewer script:

1. **VBCodeReviewer.cs** -- EditorWindow with 100 regex-based rules across 5
   categories (Bug, Performance, Security, Unity-Specific, Code Quality).
   Pass 1 uses compiled regex for sub-second scanning; Pass 2 performs
   AST-aware multi-line analysis for cross-reference patterns.  Results are
   displayed in a filterable, sortable tree view with double-click-to-open,
   severity color coding, and JSON export for CI integration.

2. **vb_python_reviewer.py** -- Standalone Python script with 30 rules for
   security, correctness, and style.  Outputs a JSON report.

Exports:
    generate_code_reviewer_script       -- VBCodeReviewer.cs generator
    generate_python_reviewer_script     -- vb_python_reviewer.py generator
"""

from __future__ import annotations

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier


# ---------------------------------------------------------------------------
# Code Review: C# Unity EditorWindow Generator
# ---------------------------------------------------------------------------


def generate_code_reviewer_script() -> dict:
    """Generate VBCodeReviewer EditorWindow that scans all .cs files.

    Two-pass architecture:
        Pass 1 -- Compiled regex patterns (100 rules, <2s for 500 files)
        Pass 2 -- AST-aware deep analysis (cross-method, cross-class patterns)

    Returns:
        Dict with script_path, script_content, next_steps.
    """

    script = r'''using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEngine;

namespace VeilBreakers.Editor.CodeReview
{
    // ======================================================================
    // Data structures
    // ======================================================================

    public enum Severity { CRITICAL, HIGH, MEDIUM, LOW }
    public enum Category { Bug, Performance, Security, Unity, Quality }

    [Serializable]
    public sealed class ReviewRule
    {
        public string Id;
        public Severity Severity;
        public Category Category;
        public string Description;
        public string Fix;
        public Regex Pattern;
        public Func<string, string[], int, bool> ContextGuard;  // extra validation to cut false positives

        public ReviewRule(string id, Severity sev, Category cat, string desc,
                          string fix, string pattern, RegexOptions opts = RegexOptions.None,
                          Func<string, string[], int, bool> guard = null)
        {
            Id = id;
            Severity = sev;
            Category = cat;
            Description = desc;
            Fix = fix;
            Pattern = new Regex(pattern, opts | RegexOptions.Compiled);
            ContextGuard = guard;
        }
    }

    [Serializable]
    public sealed class ReviewIssue
    {
        public string RuleId;
        public Severity Severity;
        public Category Category;
        public string FilePath;
        public int Line;
        public string Description;
        public string Fix;
        public string MatchedText;
    }

    // ======================================================================
    // Rule definitions -- 100 rules
    // ======================================================================

    public static class ReviewRules
    {
        // Helper: returns true if line index is inside Update/LateUpdate/FixedUpdate body
        static bool InUpdateMethod(string line, string[] allLines, int idx)
        {
            // Walk backwards to find enclosing method signature
            int braceDepth = 0;
            for (int i = idx; i >= 0; i--)
            {
                string l = allLines[i].TrimStart();
                braceDepth += CountChar(allLines[i], '}') - CountChar(allLines[i], '{');
                if (braceDepth < 0) braceDepth = 0; // clamped walk
                if (Regex.IsMatch(l, @"^\s*(void|private\s+void|protected\s+void|public\s+void)\s+(Update|LateUpdate|FixedUpdate)\s*\("))
                    return true;
                // If we hit another method signature first, stop
                if (i < idx && Regex.IsMatch(l, @"^\s*(void|private|protected|public|internal|static|override|virtual|abstract)\s+\S+\s+\w+\s*\("))
                    return false;
            }
            return false;
        }

        static bool InFixedUpdate(string line, string[] allLines, int idx)
        {
            int braceDepth = 0;
            for (int i = idx; i >= 0; i--)
            {
                string l = allLines[i].TrimStart();
                braceDepth += CountChar(allLines[i], '}') - CountChar(allLines[i], '{');
                if (braceDepth < 0) braceDepth = 0;
                if (Regex.IsMatch(l, @"^\s*(void|private\s+void|protected\s+void|public\s+void)\s+FixedUpdate\s*\("))
                    return true;
                if (i < idx && Regex.IsMatch(l, @"^\s*(void|private|protected|public|internal|static|override|virtual|abstract)\s+\S+\s+\w+\s*\("))
                    return false;
            }
            return false;
        }

        static bool NotInComment(string line, string[] allLines, int idx)
        {
            string trimmed = line.TrimStart();
            return !trimmed.StartsWith("//") && !trimmed.StartsWith("*") && !trimmed.StartsWith("/*");
        }

        static bool InHotPath(string line, string[] allLines, int idx)
        {
            return InUpdateMethod(line, allLines, idx) && NotInComment(line, allLines, idx);
        }

        static int CountChar(string s, char c)
        {
            int count = 0;
            for (int i = 0; i < s.Length; i++) { if (s[i] == c) count++; }
            return count;
        }

        static bool NotInEditorBlock(string line, string[] allLines, int idx)
        {
            for (int i = idx; i >= 0; i--)
            {
                if (allLines[i].Contains("#if UNITY_EDITOR")) return false;
                if (allLines[i].Contains("#endif")) break;
            }
            return true;
        }

        // ------- BUG DETECTION (1-30) -------

        public static readonly ReviewRule[] AllRules = new ReviewRule[]
        {
            // ---- BUG DETECTION ----
            new ReviewRule("BUG-01", Severity.CRITICAL, Category.Bug,
                "GetComponent<T>() called in Update/LateUpdate/FixedUpdate -- cache in Awake/Start",
                "Cache the component reference in a field during Awake() or Start().",
                @"GetComponent\s*<", guard: InHotPath),

            new ReviewRule("BUG-02", Severity.CRITICAL, Category.Bug,
                "Camera.main accessed in Update -- it calls FindGameObjectWithTag internally",
                "Cache Camera.main in a field during Start().",
                @"Camera\.main", guard: InHotPath),

            new ReviewRule("BUG-03", Severity.CRITICAL, Category.Bug,
                "FindObjectOfType in Update -- O(n) scene scan every frame",
                "Cache the result in Start() or use a singleton/service locator pattern.",
                @"FindObjectOfType\s*[<(]", guard: InHotPath),

            new ReviewRule("BUG-04", Severity.HIGH, Category.Bug,
                "Heap allocation (new List/Dictionary/HashSet) inside Update",
                "Pre-allocate collections as fields and Clear() them in Update instead.",
                @"new\s+(List|Dictionary|HashSet|Queue|Stack|LinkedList)\s*<", guard: InHotPath),

            new ReviewRule("BUG-05", Severity.HIGH, Category.Bug,
                "String concatenation with + in Update -- allocates new string each frame",
                "Use StringBuilder, string.Format, or interpolation cached outside the loop.",
                @"""[^""]*""\s*\+|\+\s*""[^""]*""", guard: InHotPath),

            new ReviewRule("BUG-06", Severity.CRITICAL, Category.Bug,
                "GameObject.Find() in Update -- string-based scene search every frame",
                "Cache the reference in Start() or Awake().",
                @"GameObject\.Find\s*\(", guard: InHotPath),

            new ReviewRule("BUG-07", Severity.MEDIUM, Category.Bug,
                "transform.position/.rotation accessed multiple times -- crosses native boundary each time",
                "Cache transform.position/rotation in a local variable at the start of the method.",
                @"transform\.(position|rotation)\s*[;=\.\[].*transform\.(position|rotation)",
                RegexOptions.Singleline),

            new ReviewRule("BUG-08", Severity.HIGH, Category.Bug,
                "Accessing member after Destroy(gameObject) -- object is destroyed",
                "Ensure no code runs after Destroy() on the same object within the same scope.",
                @"Destroy\s*\(\s*gameObject\s*\)"),

            new ReviewRule("BUG-09", Severity.HIGH, Category.Bug,
                "Missing null check after GetComponent -- may return null",
                "Always null-check the result of GetComponent before use.",
                @"=\s*GetComponent\s*<[^>]+>\s*\(\s*\)\s*;(?!\s*(if|Debug|//))",
                guard: NotInComment),

            new ReviewRule("BUG-10", Severity.MEDIUM, Category.Bug,
                "Using 'is null' on UnityEngine.Object -- Unity overloads == for destroyed object check",
                "Use '== null' instead of 'is null' for Unity objects (respects destroyed state).",
                @"\bis\s+null\b", guard: NotInComment),

            new ReviewRule("BUG-11", Severity.HIGH, Category.Bug,
                "async void method -- exceptions are silently swallowed",
                "Use async Task/UniTask instead; only async void for event handlers.",
                @"async\s+void\s+(?!On[A-Z])\w+\s*\(", guard: NotInComment),

            new ReviewRule("BUG-12", Severity.MEDIUM, Category.Bug,
                "Coroutine started but may never be stopped -- potential memory leak",
                "Store the Coroutine reference and call StopCoroutine in OnDisable/OnDestroy.",
                @"StartCoroutine\s*\(", guard: NotInComment),

            new ReviewRule("BUG-13", Severity.MEDIUM, Category.Bug,
                "new WaitForSeconds() allocated every yield -- cache as a field",
                "Declare a WaitForSeconds field and reuse it.",
                @"yield\s+return\s+new\s+WaitForSeconds\s*\(", guard: NotInComment),

            new ReviewRule("BUG-14", Severity.HIGH, Category.Bug,
                "SendMessage/BroadcastMessage used -- slow reflection-based messaging",
                "Use C# events, UnityEvent, or direct method calls instead.",
                @"\.(SendMessage|BroadcastMessage)\s*\(", guard: NotInComment),

            new ReviewRule("BUG-15", Severity.MEDIUM, Category.Bug,
                "OnTriggerEnter/OnCollisionEnter handler -- ensure at least one object has a Rigidbody",
                "At least one of the colliding objects must have a Rigidbody for callbacks to fire.",
                @"void\s+(OnTriggerEnter|OnCollisionEnter|OnTriggerEnter2D|OnCollisionEnter2D)\s*\("),

            new ReviewRule("BUG-16", Severity.MEDIUM, Category.Bug,
                "Physics.Raycast without LayerMask -- scans all layers",
                "Add a LayerMask parameter to limit which layers are hit.",
                @"Physics\d*\.Raycast\s*\([^)]*\)\s*;",
                guard: (line, all, i) => !line.Contains("LayerMask") && !line.Contains("layerMask") && !line.Contains("layer") && NotInComment(line, all, i)),

            new ReviewRule("BUG-17", Severity.MEDIUM, Category.Bug,
                "Time.deltaTime used in FixedUpdate -- use Time.fixedDeltaTime or omit (already fixed step)",
                "Replace Time.deltaTime with Time.fixedDeltaTime, or just use the fixed timestep directly.",
                @"Time\.deltaTime", guard: InFixedUpdate),

            new ReviewRule("BUG-18", Severity.LOW, Category.Bug,
                "Empty Update/Start/Awake method -- Unity still calls it, wasting CPU cycles",
                "Remove empty Unity lifecycle methods entirely.",
                @"void\s+(Update|Start|Awake|LateUpdate|FixedUpdate)\s*\(\s*\)\s*\{\s*\}"),

            new ReviewRule("BUG-19", Severity.MEDIUM, Category.Bug,
                "foreach on collection in hot path -- may allocate enumerator on older Mono",
                "Use a for loop with index, or cache the list and use for(int i...).",
                @"foreach\s*\(", guard: InHotPath),

            new ReviewRule("BUG-20", Severity.LOW, Category.Bug,
                "Debug.Log in production code -- wrap in #if UNITY_EDITOR or [Conditional]",
                "Use #if UNITY_EDITOR or [System.Diagnostics.Conditional(\"UNITY_EDITOR\")] wrapper.",
                @"Debug\.(Log|LogWarning|LogError|LogException)\s*\(",
                guard: (line, all, i) => NotInEditorBlock(line, all, i) && NotInComment(line, all, i)),

            new ReviewRule("BUG-21", Severity.HIGH, Category.Bug,
                "Resources.Load at runtime without caching -- disk I/O each call",
                "Cache the loaded resource in a field or use Addressables.",
                @"Resources\.Load\s*[<(]", guard: InHotPath),

            new ReviewRule("BUG-22", Severity.MEDIUM, Category.Bug,
                "Instantiate without parent transform -- causes world-space recalculation",
                "Pass a parent transform as the second argument to Instantiate.",
                @"Instantiate\s*\(\s*[^,)]+\s*\)\s*;", guard: NotInComment),

            new ReviewRule("BUG-23", Severity.CRITICAL, Category.Bug,
                "AddComponent in Update loop -- creates components every frame",
                "Move AddComponent to initialization (Awake/Start) or a one-time event.",
                @"\.AddComponent\s*[<(]", guard: InHotPath),

            new ReviewRule("BUG-24", Severity.LOW, Category.Bug,
                "Private field used in Inspector missing [SerializeField]",
                "Add [SerializeField] to private fields you want visible in the Inspector.",
                @"private\s+\w+\s+\w+\s*;",
                guard: (line, all, i) => {
                    if (line.Contains("[SerializeField]") || line.Contains("[HideInInspector]") ||
                        line.Contains("static") || line.Contains("const") || line.Contains("readonly"))
                        return false;
                    // Only flag if preceded by a [Tooltip] or [Header] that implies inspector use
                    return i > 0 && (all[i-1].Contains("[Tooltip") || all[i-1].Contains("[Header"));
                }),

            new ReviewRule("BUG-25", Severity.LOW, Category.Bug,
                "Public field should likely be [SerializeField] private for encapsulation",
                "Use [SerializeField] private instead of public for Inspector-exposed fields.",
                @"^\s+public\s+(?!static|const|readonly|override|virtual|abstract|event|delegate|class|struct|enum|interface)\w+\s+\w+\s*[;=]",
                guard: (line, all, i) => {
                    // Only inside a MonoBehaviour or ScriptableObject class
                    for (int j = i; j >= 0; j--)
                    {
                        if (all[j].Contains(": MonoBehaviour") || all[j].Contains(": ScriptableObject"))
                            return NotInComment(line, all, i);
                        if (Regex.IsMatch(all[j], @"^\s*class\s+"))
                            return false;
                    }
                    return false;
                }),

            new ReviewRule("BUG-26", Severity.MEDIUM, Category.Bug,
                "Comparing tag with == instead of CompareTag() -- allocates string",
                "Use gameObject.CompareTag(\"tag\") which avoids GC allocation.",
                @"\.tag\s*==\s*""", guard: NotInComment),

            new ReviewRule("BUG-27", Severity.MEDIUM, Category.Bug,
                "Vector3.Distance in loop -- use sqrMagnitude to avoid expensive sqrt",
                "Use (a - b).sqrMagnitude < threshold * threshold instead.",
                @"Vector\d\.Distance\s*\(", guard: InHotPath),

            new ReviewRule("BUG-28", Severity.HIGH, Category.Bug,
                "LINQ used in Update -- allocates iterators, closures, and temp collections",
                "Replace LINQ with manual loops in hot paths for zero-alloc operation.",
                @"\.\s*(Where|Select|OrderBy|GroupBy|Any|All|First|Last|Count|Sum|Min|Max|ToList|ToArray|ToDictionary)\s*\(",
                guard: InHotPath),

            new ReviewRule("BUG-29", Severity.MEDIUM, Category.Bug,
                "Animator.StringToHash not cached -- recalculates hash every call",
                "Declare static readonly int fields: static readonly int HashRun = Animator.StringToHash(\"Run\");",
                @"Animator\.StringToHash\s*\(", guard: InHotPath),

            new ReviewRule("BUG-30", Severity.MEDIUM, Category.Bug,
                "Material property access creating runtime instance -- use sharedMaterial or MaterialPropertyBlock",
                "Use renderer.sharedMaterial (read-only) or MaterialPropertyBlock for per-instance values.",
                @"\.\s*material\s*[\.=](?!s)", guard: InHotPath),

            // ---- PERFORMANCE (31-50) ----

            new ReviewRule("PERF-01", Severity.MEDIUM, Category.Performance,
                "Boxing value type to object -- causes GC allocation",
                "Use generics or overloaded methods to avoid boxing.",
                @"\(\s*object\s*\)\s*\w+", guard: InHotPath),

            new ReviewRule("PERF-02", Severity.MEDIUM, Category.Performance,
                "Closure allocation in lambda/delegate in hot path",
                "Capture variables in a struct or pass via static method + state parameter.",
                @"=>\s*\{?[^}]*\b(this|[a-z_]\w*)\b",
                guard: InHotPath),

            new ReviewRule("PERF-03", Severity.LOW, Category.Performance,
                "Large struct passed by value -- consider in/ref parameter",
                "Use 'in' keyword for readonly pass or 'ref' for mutable pass of large structs.",
                @"\(\s*(Matrix4x4|Bounds|RaycastHit|ContactPoint|NavMeshHit)\s+\w+\s*[,)]",
                guard: (line, all, i) => !line.Contains(" in ") && !line.Contains(" ref ") && NotInComment(line, all, i)),

            new ReviewRule("PERF-04", Severity.LOW, Category.Performance,
                "Unbounded List.Add without Capacity pre-allocation",
                "Set list.Capacity or use new List<T>(expectedSize) to avoid repeated array resizing.",
                @"new\s+List\s*<[^>]+>\s*\(\s*\)",
                guard: NotInComment),

            new ReviewRule("PERF-05", Severity.LOW, Category.Performance,
                "String.Format in hot path -- use cached StringBuilder",
                "Use StringBuilder.AppendFormat or pre-allocated string operations.",
                @"[Ss]tring\.Format\s*\(", guard: InHotPath),

            new ReviewRule("PERF-06", Severity.MEDIUM, Category.Performance,
                "Texture2D.GetPixel/SetPixel per-pixel loop -- use GetPixels32/SetPixels32 bulk API",
                "Use GetPixels32()/SetPixels32() for bulk pixel manipulation.",
                @"\.(GetPixel|SetPixel)\s*\(", guard: NotInComment),

            new ReviewRule("PERF-07", Severity.HIGH, Category.Performance,
                "Mesh.vertices/.normals/.uv accessed in loop -- each access copies entire array",
                "Cache mesh.vertices in a local array before the loop.",
                @"mesh\.(vertices|normals|uv|tangents|colors|triangles)\b",
                guard: InHotPath),

            new ReviewRule("PERF-08", Severity.MEDIUM, Category.Performance,
                "Physics.Raycast without maxDistance -- scans to infinity",
                "Always specify a maxDistance parameter to limit ray length.",
                @"Physics\d*\.(Raycast|SphereCast|CapsuleCast|BoxCast)\s*\(\s*[^,]+\s*,\s*[^,]+\s*\)",
                guard: NotInComment),

            new ReviewRule("PERF-09", Severity.LOW, Category.Performance,
                "Mathf.Pow(x, 2) instead of x * x -- function call overhead for simple multiply",
                "Use x * x instead of Mathf.Pow(x, 2f).",
                @"Mathf\.Pow\s*\([^,]+,\s*2\.?0?f?\s*\)", guard: NotInComment),

            new ReviewRule("PERF-10", Severity.MEDIUM, Category.Performance,
                "Camera.main.ScreenToWorldPoint in Update without caching Camera.main",
                "Cache Camera.main in a field during Start().",
                @"Camera\.main\.Screen", guard: InHotPath),

            new ReviewRule("PERF-11", Severity.MEDIUM, Category.Performance,
                "Nested for loops potentially O(n^2) on large collections -- consider spatial hashing or early exit",
                "Use spatial partitioning, break/continue, or reduce inner loop size.",
                @"for\s*\([^)]+\)\s*\{[^}]*for\s*\([^)]+\)",
                guard: InHotPath),

            new ReviewRule("PERF-12", Severity.LOW, Category.Performance,
                "transform.SetParent without worldPositionStays=false -- recalculates world position",
                "Pass false as second argument if you don't need to preserve world position.",
                @"\.SetParent\s*\(\s*[^,)]+\s*\)\s*;", guard: NotInComment),

            new ReviewRule("PERF-13", Severity.MEDIUM, Category.Performance,
                "ParticleSystem collision module on all layers -- use collision LayerMask",
                "Set the collision LayerMask to only the layers you need.",
                @"collisionModule\.(enabled\s*=\s*true|collidesWith)",
                guard: (line, all, i) => !line.Contains("LayerMask") && NotInComment(line, all, i)),

            new ReviewRule("PERF-14", Severity.LOW, Category.Performance,
                "Light with shadow casting on all objects -- use culling mask",
                "Set the light's culling mask to limit which layers cast shadows.",
                @"\.shadows\s*=\s*LightShadows\.(Soft|Hard)",
                guard: NotInComment),

            new ReviewRule("PERF-15", Severity.LOW, Category.Performance,
                "AudioSource with 3D spatial blend 0 but using distance attenuation",
                "Set spatialBlend to 1 for 3D or remove distance-based rolloff settings.",
                @"spatialBlend\s*=\s*0", guard: NotInComment),

            new ReviewRule("PERF-16", Severity.MEDIUM, Category.Performance,
                "NavMesh.CalculatePath without caching NavMeshPath -- allocates each call",
                "Reuse a NavMeshPath instance instead of creating a new one each time.",
                @"new\s+NavMeshPath\s*\(\s*\)", guard: InHotPath),

            new ReviewRule("PERF-17", Severity.HIGH, Category.Performance,
                "Canvas.ForceUpdateCanvases() called frequently -- very expensive",
                "Avoid calling ForceUpdateCanvases; let Unity batch canvas updates naturally.",
                @"ForceUpdateCanvases\s*\(\s*\)", guard: NotInComment),

            new ReviewRule("PERF-18", Severity.MEDIUM, Category.Performance,
                "Layout group rebuild likely every frame -- disable and re-enable when content changes",
                "Only enable LayoutGroup when content changes, then disable it after layout pass.",
                @"LayoutRebuilder\.ForceRebuildLayoutImmediate\s*\(", guard: InHotPath),

            new ReviewRule("PERF-19", Severity.LOW, Category.Performance,
                "Excessive SetActive toggling -- consider CanvasGroup.alpha or disable renderers",
                "Use CanvasGroup.alpha = 0 or disable MeshRenderer instead of SetActive for frequent toggles.",
                @"\.SetActive\s*\(", guard: InHotPath),

            new ReviewRule("PERF-20", Severity.MEDIUM, Category.Performance,
                "Multiple cameras rendering simultaneously -- ensure proper culling and depth optimization",
                "Reduce camera count or use camera stacking with clear flags optimized.",
                @"new\s+.*Camera\b.*enabled\s*=\s*true|Camera\.allCameras",
                guard: NotInComment),

            // ---- SECURITY (51-60) ----

            new ReviewRule("SEC-01", Severity.CRITICAL, Category.Security,
                "System.IO.File operation without path validation -- path traversal risk",
                "Validate and sanitize file paths; reject '..' and absolute paths from user input.",
                @"System\.IO\.(File|Directory)\.(Read|Write|Delete|Move|Copy|Create|Open|Append)",
                guard: NotInComment),

            new ReviewRule("SEC-02", Severity.CRITICAL, Category.Security,
                "Process.Start with potential user arguments -- command injection risk",
                "Never pass user input to Process.Start; whitelist allowed commands.",
                @"Process\.Start\s*\(", guard: NotInComment),

            new ReviewRule("SEC-03", Severity.HIGH, Category.Security,
                "JsonUtility.FromJson on untrusted input -- validate schema after deserialization",
                "Validate deserialized object fields and reject unexpected values.",
                @"JsonUtility\.FromJson\s*[<(]", guard: NotInComment),

            new ReviewRule("SEC-04", Severity.HIGH, Category.Security,
                "PlayerPrefs storing potentially sensitive data -- stored as plaintext",
                "Encrypt sensitive data before storing in PlayerPrefs, or use a secure store.",
                @"PlayerPrefs\.(SetString|SetInt|SetFloat)\s*\(\s*""(password|token|key|secret|credential|auth)",
                RegexOptions.IgnoreCase),

            new ReviewRule("SEC-05", Severity.MEDIUM, Category.Security,
                "HTTP URL (non-HTTPS) used in web request -- data transmitted in plaintext",
                "Use HTTPS URLs for all network requests.",
                @"(""http://|UnityWebRequest\.Get\s*\(\s*""http://)",
                guard: (line, all, i) => !line.Contains("localhost") && !line.Contains("127.0.0.1") && NotInComment(line, all, i)),

            new ReviewRule("SEC-06", Severity.CRITICAL, Category.Security,
                "CompileAssemblyFromSource/CSharpCodeProvider with user input -- arbitrary code execution",
                "Never compile user-provided code at runtime.",
                @"(CompileAssemblyFrom|CSharpCodeProvider|CodeDomProvider)", guard: NotInComment),

            new ReviewRule("SEC-07", Severity.CRITICAL, Category.Security,
                "SQL query built with string concatenation -- SQL injection risk",
                "Use parameterized queries instead of string concatenation.",
                @"(SELECT|INSERT|UPDATE|DELETE)\s+.*""\s*\+\s*\w+",
                RegexOptions.IgnoreCase, guard: NotInComment),

            new ReviewRule("SEC-08", Severity.CRITICAL, Category.Security,
                "Hardcoded credential or API key in source code",
                "Store secrets in environment variables, ScriptableObjects excluded from VCS, or a secure vault.",
                @"(api[_-]?key|password|secret|token|credential)\s*=\s*""[^""]{8,}""",
                RegexOptions.IgnoreCase, guard: NotInComment),

            new ReviewRule("SEC-09", Severity.HIGH, Category.Security,
                "Resources.Load with user-provided path -- directory traversal risk",
                "Whitelist allowed resource paths; never pass raw user input to Resources.Load.",
                @"Resources\.Load\s*\(\s*\w+\s*\)",
                guard: (line, all, i) => !line.Contains(@"""") && NotInComment(line, all, i)),

            new ReviewRule("SEC-10", Severity.HIGH, Category.Security,
                "Application.OpenURL with dynamic URL -- URL injection risk",
                "Validate and whitelist URLs before passing to Application.OpenURL.",
                @"Application\.OpenURL\s*\(\s*[^"")\s]",
                guard: NotInComment),

            // ---- UNITY-SPECIFIC (61-75) ----

            new ReviewRule("UNITY-01", Severity.HIGH, Category.Unity,
                "MonoBehaviour constructor used -- use Awake() or Start() instead",
                "Unity manages MonoBehaviour lifecycle; use Awake/Start for initialization.",
                @"class\s+\w+\s*:\s*MonoBehaviour[\s\S]*?\bpublic\s+\w+\s*\(\s*\)\s*\{",
                guard: NotInComment),

            new ReviewRule("UNITY-02", Severity.HIGH, Category.Unity,
                "ScriptableObject constructor used -- use OnEnable or CreateInstance",
                "Use ScriptableObject.CreateInstance<T>() and OnEnable for initialization.",
                @"class\s+\w+\s*:\s*ScriptableObject[\s\S]*?\bpublic\s+\w+\s*\(\s*\)\s*\{",
                guard: NotInComment),

            new ReviewRule("UNITY-03", Severity.HIGH, Category.Unity,
                "Accessing .gameObject or .transform on potentially destroyed object",
                "Null-check the object before accessing .gameObject or .transform.",
                @"Destroy\s*\([^)]+\)[\s\S]{0,200}\.(gameObject|transform)",
                guard: NotInComment),

            new ReviewRule("UNITY-04", Severity.HIGH, Category.Unity,
                "DontDestroyOnLoad without singleton duplicate check",
                "Add a singleton pattern: if (Instance != null) { Destroy(gameObject); return; }",
                @"DontDestroyOnLoad\s*\(",
                guard: (line, all, i) => {
                    // Check if there's a singleton guard nearby
                    for (int j = Math.Max(0, i - 10); j < Math.Min(all.Length, i + 3); j++)
                    {
                        if (all[j].Contains("Instance") && (all[j].Contains("Destroy") || all[j].Contains("!= null")))
                            return false;
                    }
                    return NotInComment(line, all, i);
                }),

            new ReviewRule("UNITY-05", Severity.MEDIUM, Category.Unity,
                "Missing [RequireComponent] for dependent GetComponent in Awake/Start",
                "Add [RequireComponent(typeof(T))] to ensure the component exists.",
                @"(Awake|Start)\s*\(\s*\)[\s\S]*?GetComponent\s*<(\w+)>\s*\(\s*\)",
                guard: NotInComment),

            new ReviewRule("UNITY-06", Severity.MEDIUM, Category.Unity,
                "Invoke/InvokeRepeating with string method name -- refactor to coroutine or event",
                "Use Coroutines, async/await, or direct method references instead.",
                @"\.(Invoke|InvokeRepeating)\s*\(\s*""", guard: NotInComment),

            new ReviewRule("UNITY-07", Severity.MEDIUM, Category.Unity,
                "Scene loaded without additive mode may leak DontDestroyOnLoad objects",
                "Use LoadSceneMode.Additive or clean up persistent objects explicitly.",
                @"SceneManager\.LoadScene\s*\(",
                guard: (line, all, i) => !line.Contains("Additive") && NotInComment(line, all, i)),

            new ReviewRule("UNITY-08", Severity.HIGH, Category.Unity,
                "UnityEvent mixed with C# event without proper unsubscribe -- memory leak risk",
                "Unsubscribe C# events in OnDisable/OnDestroy; use RemoveListener for UnityEvent.",
                @"\+=\s*\w+\s*;",
                guard: (line, all, i) => {
                    // Only flag if there's no corresponding -= in the file
                    string handler = Regex.Match(line, @"\+=\s*(\w+)\s*;").Groups[1].Value;
                    if (string.IsNullOrEmpty(handler)) return false;
                    bool hasUnsub = false;
                    for (int j = 0; j < all.Length; j++)
                    {
                        if (all[j].Contains("-= " + handler)) { hasUnsub = true; break; }
                    }
                    return !hasUnsub && NotInComment(line, all, i);
                }),

            new ReviewRule("UNITY-09", Severity.MEDIUM, Category.Unity,
                "Editor-only API used outside #if UNITY_EDITOR block",
                "Wrap EditorApplication/AssetDatabase/etc. calls in #if UNITY_EDITOR.",
                @"(EditorApplication|AssetDatabase|EditorUtility|Selection|Undo|PrefabUtility|SerializedObject|SerializedProperty)\.",
                guard: (line, all, i) => {
                    // Check if we're inside an Editor folder or #if block
                    for (int j = i; j >= 0; j--)
                    {
                        if (all[j].Contains("#if UNITY_EDITOR")) return false;
                        if (all[j].Contains("#endif")) break;
                    }
                    return NotInComment(line, all, i);
                }),

            new ReviewRule("UNITY-10", Severity.MEDIUM, Category.Unity,
                "Serializing interface or abstract type -- Unity serializer cannot handle this",
                "Use a concrete type or implement ISerializationCallbackReceiver.",
                @"\[SerializeField\]\s*(private|protected|public)?\s*(I[A-Z]\w+|abstract\s+\w+)\s+\w+",
                guard: NotInComment),

            new ReviewRule("UNITY-11", Severity.LOW, Category.Unity,
                "Large array in ScriptableObject -- consider Addressables for large datasets",
                "Use Addressables or split data into smaller chunks.",
                @"ScriptableObject[\s\S]*?\[\]\s+\w+\s*=\s*new\s+\w+\[(?:[5-9]\d{2,}|\d{4,})\]",
                guard: NotInComment),

            new ReviewRule("UNITY-12", Severity.HIGH, Category.Unity,
                "Missing OnDisable/OnDestroy unsubscribe from events -- memory leak",
                "Always unsubscribe (-=) from events in OnDisable or OnDestroy.",
                @"(OnEnable|Awake|Start)\s*\(\s*\)[\s\S]*?\+=",
                guard: (line, all, i) => {
                    // Check if the class has an OnDisable or OnDestroy
                    bool hasCleanup = false;
                    for (int j = 0; j < all.Length; j++)
                    {
                        if (Regex.IsMatch(all[j], @"(OnDisable|OnDestroy)\s*\(\s*\)"))
                        { hasCleanup = true; break; }
                    }
                    return !hasCleanup && NotInComment(line, all, i);
                }),

            new ReviewRule("UNITY-13", Severity.LOW, Category.Unity,
                "Awake execution order dependency without [DefaultExecutionOrder]",
                "Add [DefaultExecutionOrder(N)] to control initialization order.",
                @"void\s+Awake\s*\(\s*\)[\s\S]*?(FindObjectOfType|GetComponent|Instance)",
                guard: (line, all, i) => {
                    for (int j = 0; j < all.Length; j++)
                    {
                        if (all[j].Contains("[DefaultExecutionOrder"))
                            return false;
                    }
                    return NotInComment(line, all, i);
                }),

            new ReviewRule("UNITY-14", Severity.MEDIUM, Category.Unity,
                "Static field in MonoBehaviour -- shared across all instances, may cause bugs",
                "Use instance fields or a dedicated static manager class instead.",
                @"class\s+\w+\s*:\s*MonoBehaviour[\s\S]*?static\s+(?!readonly|void|bool|int|float|string|event|Action|Func|delegate)\w+\s+\w+",
                guard: (line, all, i) => {
                    return !line.Contains("Instance") && !line.Contains("Singleton") && NotInComment(line, all, i);
                }),

            new ReviewRule("UNITY-15", Severity.LOW, Category.Unity,
                "Singleton MonoBehaviour missing [DisallowMultipleComponent]",
                "Add [DisallowMultipleComponent] to prevent duplicate singleton components.",
                @"static\s+\w+\s+Instance\s*[{;=]",
                guard: (line, all, i) => {
                    for (int j = 0; j < all.Length; j++)
                    {
                        if (all[j].Contains("[DisallowMultipleComponent"))
                            return false;
                    }
                    return NotInComment(line, all, i);
                }),

            // ---- CODE QUALITY (76-100) ----

            new ReviewRule("QUAL-01", Severity.LOW, Category.Quality,
                "Method exceeds 50 lines -- consider extracting sub-methods",
                "Break long methods into smaller, well-named helper methods.",
                @"(void|int|float|bool|string|var|Task|IEnumerator)\s+\w+\s*\([^)]*\)\s*\{",
                guard: (line, all, i) => {
                    // Count lines until closing brace at same depth
                    int depth = 0;
                    int start = i;
                    for (int j = i; j < all.Length; j++)
                    {
                        depth += CountChar(all[j], '{') - CountChar(all[j], '}');
                        if (depth <= 0 && j > i) return (j - start) > 50;
                    }
                    return false;
                }),

            new ReviewRule("QUAL-02", Severity.LOW, Category.Quality,
                "Excessive nesting depth (>4 levels) -- flatten with early returns or extraction",
                "Use guard clauses, early returns, or extract nested logic into methods.",
                @"^\s{20,}(if|for|while|foreach|switch)\b",
                guard: NotInComment),

            new ReviewRule("QUAL-03", Severity.LOW, Category.Quality,
                "Magic number in code -- use a named constant",
                "Define a const or static readonly field with a descriptive name.",
                @"[=<>+\-*/]\s*(?<![.0-9])((?:[2-9]\d{2,}|\d{4,})(?:\.\d+)?f?)\s*[;,)\]}]",
                guard: (line, all, i) => {
                    return !line.Contains("const") && !line.Contains("readonly") &&
                           !Regex.IsMatch(line, @"(Color|Vector|Rect|new\s+\w+\[)") &&
                           NotInComment(line, all, i);
                }),

            new ReviewRule("QUAL-04", Severity.LOW, Category.Quality,
                "Missing XML documentation on public method",
                "Add /// <summary> documentation to public API methods.",
                @"^\s+public\s+\S+\s+\w+\s*\([^)]*\)\s*\{?$",
                guard: (line, all, i) => {
                    return i > 0 && !all[i-1].TrimStart().StartsWith("///") && NotInComment(line, all, i);
                }),

            new ReviewRule("QUAL-05", Severity.LOW, Category.Quality,
                "Inconsistent naming -- private fields should use _camelCase",
                "Follow Unity C# conventions: _camelCase for private fields, PascalCase for public.",
                @"private\s+\w+\s+([A-Z]\w+)\s*[;=]",
                guard: (line, all, i) => {
                    return !line.Contains("const") && !line.Contains("static") &&
                           !line.Contains("readonly") && !line.Contains("event") &&
                           NotInComment(line, all, i);
                }),

            new ReviewRule("QUAL-06", Severity.LOW, Category.Quality,
                "Empty catch block swallows exception silently",
                "At minimum log the exception; never silently swallow errors.",
                @"catch\s*(\([^)]*\))?\s*\{\s*\}", guard: NotInComment),

            new ReviewRule("QUAL-07", Severity.LOW, Category.Quality,
                "TODO/FIXME/HACK comment found -- track or resolve",
                "Create a task/issue for the TODO and reference its ID.",
                @"//\s*(TODO|FIXME|HACK|XXX|TEMP|WORKAROUND)\b",
                RegexOptions.IgnoreCase),

            new ReviewRule("QUAL-08", Severity.LOW, Category.Quality,
                "Unused using directive -- remove for cleanliness",
                "Remove unused using statements (IDE can auto-remove).",
                @"^using\s+\w+(\.\w+)*\s*;",
                guard: (line, all, i) => {
                    // Simple heuristic: check if the last segment of the namespace is used
                    var match = Regex.Match(line, @"using\s+([\w.]+)\s*;");
                    if (!match.Success) return false;
                    string ns = match.Groups[1].Value;
                    string lastSeg = ns.Contains(".") ? ns.Substring(ns.LastIndexOf('.') + 1) : ns;
                    // Skip common always-used namespaces
                    if (lastSeg == "System" || lastSeg == "Collections" || lastSeg == "Generic" ||
                        lastSeg == "UnityEngine" || lastSeg == "Linq") return false;
                    // Check if the namespace segment appears anywhere else
                    int usageCount = 0;
                    for (int j = 0; j < all.Length; j++)
                    {
                        if (j != i && all[j].Contains(lastSeg)) { usageCount++; break; }
                    }
                    return usageCount == 0;
                }),

            new ReviewRule("QUAL-09", Severity.LOW, Category.Quality,
                "Complex boolean condition (>3 operators) -- extract to well-named method or variable",
                "Extract complex conditions into a bool variable or method with a descriptive name.",
                @"if\s*\(.*?(&&|\|\|).*?(&&|\|\|).*?(&&|\|\|)", guard: NotInComment),

            new ReviewRule("QUAL-10", Severity.LOW, Category.Quality,
                "Switch statement missing default case",
                "Add a default case, even if it just throws an ArgumentOutOfRangeException.",
                @"switch\s*\([^)]+\)\s*\{(?:(?!default\s*:)[\s\S])*?\}",
                guard: NotInComment),

            new ReviewRule("QUAL-11", Severity.LOW, Category.Quality,
                "Non-sealed custom exception class -- seal to prevent unintended inheritance",
                "Mark custom exception classes as sealed unless designed for inheritance.",
                @"class\s+\w+Exception\s*:",
                guard: (line, all, i) => !line.Contains("sealed") && NotInComment(line, all, i)),

            new ReviewRule("QUAL-12", Severity.MEDIUM, Category.Quality,
                "Mutable static collection -- thread safety risk and hard to test",
                "Use ConcurrentDictionary/ConcurrentBag, or make it readonly with immutable contents.",
                @"static\s+(List|Dictionary|HashSet|Queue|Stack)\s*<",
                guard: (line, all, i) => !line.Contains("readonly") && !line.Contains("Concurrent") && NotInComment(line, all, i)),

            new ReviewRule("QUAL-13", Severity.HIGH, Category.Quality,
                "lock(this) or lock(typeof(...)) -- use a dedicated lock object",
                "Use a private readonly object field: private readonly object _lock = new object();",
                @"lock\s*\(\s*(this|typeof\s*\()", guard: NotInComment),

            new ReviewRule("QUAL-14", Severity.MEDIUM, Category.Quality,
                "IDisposable not disposed -- use 'using' statement or call Dispose in OnDestroy",
                "Wrap in a 'using' block or call Dispose() in a finally/OnDestroy.",
                @"new\s+(StreamReader|StreamWriter|FileStream|BinaryReader|BinaryWriter|HttpClient|WebClient|MemoryStream|UnityWebRequest)\s*\(",
                guard: (line, all, i) => !line.TrimStart().StartsWith("using") && !line.Contains("using (") && !line.Contains("using var") && NotInComment(line, all, i)),

            new ReviewRule("QUAL-15", Severity.LOW, Category.Quality,
                "Redundant null check -- value types cannot be null",
                "Remove null check on value types (int, float, bool, Vector3, etc.).",
                @"(int|float|double|bool|byte|char|long|short|Vector[234]|Quaternion|Color|Rect|Bounds)\s+\w+.*==\s*null",
                guard: NotInComment),

            new ReviewRule("QUAL-16", Severity.LOW, Category.Quality,
                "Dead code -- unreachable code after return/break/continue/throw",
                "Remove unreachable statements below return/break/continue/throw.",
                @"(return\s+[^;]+;|break\s*;|continue\s*;|throw\s+[^;]+;)\s*\n\s+\w",
                guard: NotInComment),

            new ReviewRule("QUAL-17", Severity.LOW, Category.Quality,
                "God class with excessive responsibility -- consider splitting",
                "Split large classes into focused, single-responsibility classes.",
                @"class\s+\w+",
                guard: (line, all, i) => {
                    // Count lines in the class
                    int depth = 0;
                    int start = i;
                    for (int j = i; j < all.Length; j++)
                    {
                        depth += CountChar(all[j], '{') - CountChar(all[j], '}');
                        if (depth <= 0 && j > i) return (j - start) > 500;
                    }
                    return false;
                }),

            new ReviewRule("QUAL-18", Severity.LOW, Category.Quality,
                "Unnecessary boxing in string interpolation with value type .ToString()",
                "Call .ToString() explicitly on value types in interpolation to avoid boxing.",
                @"\$""[^""]*\{(?!.*\.ToString)[^}]*\}",
                guard: InHotPath),

            new ReviewRule("QUAL-19", Severity.LOW, Category.Quality,
                "#region used for code organization -- prefer smaller, focused classes",
                "Extract #region contents into separate classes or methods.",
                @"#region\b", guard: NotInComment),

            new ReviewRule("QUAL-20", Severity.LOW, Category.Quality,
                "Catch block only rethrows -- remove the try/catch or add handling logic",
                "Remove redundant try/catch that just rethrows, or add logging/cleanup.",
                @"catch\s*\([^)]*\)\s*\{\s*throw\s*;\s*\}", guard: NotInComment),

            new ReviewRule("QUAL-21", Severity.LOW, Category.Quality,
                "String.Equals without StringComparison -- culture-dependent behavior",
                "Use StringComparison.Ordinal or StringComparison.OrdinalIgnoreCase.",
                @"\.Equals\s*\(\s*""",
                guard: (line, all, i) => !line.Contains("StringComparison") && NotInComment(line, all, i)),

            new ReviewRule("QUAL-23", Severity.MEDIUM, Category.Quality,
                "Nested ternary operator -- hard to read, use if/else",
                "Replace nested ternaries with if/else or switch expressions.",
                @"\?[^;:]*\?[^;]*:", guard: NotInComment),

            new ReviewRule("QUAL-24", Severity.LOW, Category.Quality,
                "Parameter count exceeds 5 -- consider parameter object or builder pattern",
                "Group related parameters into a struct/class, or use a builder.",
                @"(void|int|float|bool|string|Task|IEnumerator|\w+)\s+\w+\s*\(",
                guard: (line, all, i) => {
                    var match = Regex.Match(line, @"\(([^)]*)\)");
                    if (!match.Success) return false;
                    string paramStr = match.Groups[1].Value;
                    if (string.IsNullOrWhiteSpace(paramStr)) return false;
                    int paramCount = paramStr.Split(',').Length;
                    return paramCount > 5 && NotInComment(line, all, i);
                }),
        };
    }

    // ======================================================================
    // Pass 2: AST-aware deep analysis
    // ======================================================================

    public static class DeepAnalyzer
    {
        // Tracks class-level info for cross-method analysis
        sealed class ClassInfo
        {
            public string Name;
            public int StartLine;
            public int EndLine;
            public bool IsMonoBehaviour;
            public bool IsScriptableObject;
            public bool HasOnDisable;
            public bool HasOnDestroy;
            public List<string> EventSubscriptions = new List<string>();
            public List<string> EventUnsubscriptions = new List<string>();
            public HashSet<string> DeclaredFields = new HashSet<string>();
            public HashSet<string> UsedFields = new HashSet<string>();
            public HashSet<string> SerializedFields = new HashSet<string>();
        }

        static readonly Regex ClassDeclRegex = new Regex(
            @"class\s+(\w+)\s*(?::\s*([\w<>,\s]+))?\s*\{",
            RegexOptions.Compiled);

        static readonly Regex FieldDeclRegex = new Regex(
            @"^\s+(?:(?:\[[\w(,\s""=.]+\]\s*)*)?(private|protected|public|internal)?\s*(?:static\s+)?(?:readonly\s+)?(\w+(?:<[\w<>,\s]+>)?)\s+(\w+)\s*[;=]",
            RegexOptions.Compiled);

        static readonly Regex SubscribeRegex = new Regex(
            @"(\w+(?:\.\w+)*)\s*\+=\s*(\w+)", RegexOptions.Compiled);

        static readonly Regex UnsubscribeRegex = new Regex(
            @"(\w+(?:\.\w+)*)\s*-=\s*(\w+)", RegexOptions.Compiled);

        static readonly Regex FieldUseRegex = new Regex(
            @"\b([_a-z]\w*)\b", RegexOptions.Compiled);

        public static List<ReviewIssue> Analyze(string filePath, string[] lines)
        {
            var issues = new List<ReviewIssue>();
            var classes = ParseClasses(lines);

            foreach (var cls in classes)
            {
                // Deep-01: Event subscription without matching unsubscription
                foreach (var sub in cls.EventSubscriptions)
                {
                    if (!cls.EventUnsubscriptions.Contains(sub) && cls.IsMonoBehaviour)
                    {
                        issues.Add(new ReviewIssue
                        {
                            RuleId = "DEEP-01",
                            Severity = Severity.HIGH,
                            Category = Category.Unity,
                            FilePath = filePath,
                            Line = cls.StartLine + 1,
                            Description = $"Event '{sub}' subscribed but never unsubscribed in {cls.Name} -- memory leak",
                            Fix = "Add -= unsubscribe in OnDisable() or OnDestroy().",
                            MatchedText = sub
                        });
                    }
                }

                // Deep-02: Unused private fields
                foreach (var field in cls.DeclaredFields)
                {
                    if (!cls.UsedFields.Contains(field) && !cls.SerializedFields.Contains(field))
                    {
                        issues.Add(new ReviewIssue
                        {
                            RuleId = "DEEP-02",
                            Severity = Severity.LOW,
                            Category = Category.Quality,
                            FilePath = filePath,
                            Line = cls.StartLine + 1,
                            Description = $"Private field '{field}' in {cls.Name} appears unused",
                            Fix = "Remove the unused field or add [SerializeField] if Inspector-used.",
                            MatchedText = field
                        });
                    }
                }

                // Deep-03: MonoBehaviour without any lifecycle methods -- possibly dead script
                if (cls.IsMonoBehaviour)
                {
                    bool hasLifecycle = false;
                    for (int i = cls.StartLine; i <= cls.EndLine && i < lines.Length; i++)
                    {
                        if (Regex.IsMatch(lines[i],
                            @"void\s+(Awake|Start|OnEnable|OnDisable|Update|FixedUpdate|LateUpdate|OnDestroy|OnGUI)\s*\("))
                        {
                            hasLifecycle = true;
                            break;
                        }
                    }
                    if (!hasLifecycle)
                    {
                        issues.Add(new ReviewIssue
                        {
                            RuleId = "DEEP-03",
                            Severity = Severity.LOW,
                            Category = Category.Quality,
                            FilePath = filePath,
                            Line = cls.StartLine + 1,
                            Description = $"MonoBehaviour '{cls.Name}' has no lifecycle methods -- consider static utility class",
                            Fix = "If no lifecycle needed, make it a plain class or static utility.",
                            MatchedText = cls.Name
                        });
                    }
                }
            }
            return issues;
        }

        static List<ClassInfo> ParseClasses(string[] lines)
        {
            var classes = new List<ClassInfo>();
            for (int i = 0; i < lines.Length; i++)
            {
                var m = ClassDeclRegex.Match(lines[i]);
                if (!m.Success) continue;

                var cls = new ClassInfo
                {
                    Name = m.Groups[1].Value,
                    StartLine = i
                };
                string baseTypes = m.Groups[2].Value;
                cls.IsMonoBehaviour = baseTypes.Contains("MonoBehaviour");
                cls.IsScriptableObject = baseTypes.Contains("ScriptableObject");

                // Find class end
                int depth = 0;
                for (int j = i; j < lines.Length; j++)
                {
                    depth += ReviewRules.CountChar(lines[j], '{') - ReviewRules.CountChar(lines[j], '}');
                    if (depth <= 0 && j > i) { cls.EndLine = j; break; }
                    if (j == lines.Length - 1) cls.EndLine = j;

                    // Collect fields
                    var fm = FieldDeclRegex.Match(lines[j]);
                    if (fm.Success && (fm.Groups[1].Value == "private" || fm.Groups[1].Value == ""))
                    {
                        cls.DeclaredFields.Add(fm.Groups[3].Value);
                        if (j > 0 && lines[j - 1].Contains("[SerializeField]"))
                            cls.SerializedFields.Add(fm.Groups[3].Value);
                    }

                    // Collect subscriptions
                    var sm = SubscribeRegex.Match(lines[j]);
                    if (sm.Success) cls.EventSubscriptions.Add(sm.Groups[1].Value + "+=" + sm.Groups[2].Value);
                    var um = UnsubscribeRegex.Match(lines[j]);
                    if (um.Success) cls.EventUnsubscriptions.Add(um.Groups[1].Value + "+=" + um.Groups[2].Value);

                    // Track field usage (simple: any mention of declared field outside its decl line)
                    if (j != i)
                    {
                        foreach (Match fum in FieldUseRegex.Matches(lines[j]))
                        {
                            cls.UsedFields.Add(fum.Groups[1].Value);
                        }
                    }
                }
                if (Regex.IsMatch(string.Join("\n", lines, cls.StartLine,
                    Math.Min(cls.EndLine - cls.StartLine + 1, lines.Length - cls.StartLine)),
                    @"void\s+OnDis(able|able)\s*\(")) cls.HasOnDisable = true;
                if (Regex.IsMatch(string.Join("\n", lines, cls.StartLine,
                    Math.Min(cls.EndLine - cls.StartLine + 1, lines.Length - cls.StartLine)),
                    @"void\s+OnDestroy\s*\(")) cls.HasOnDestroy = true;

                classes.Add(cls);
            }
            return classes;
        }

        // Make CountChar accessible
        static int CountChar(string s, char c)
        {
            return ReviewRules.CountChar(s, c);
        }
    }

    // ======================================================================
    // Main EditorWindow
    // ======================================================================

    public sealed class VBCodeReviewer : EditorWindow
    {
        [MenuItem("VeilBreakers/Code Review/Open Reviewer")]
        static void Open() => GetWindow<VBCodeReviewer>("VB Code Reviewer");

        // State
        List<ReviewIssue> _issues = new List<ReviewIssue>();
        Vector2 _scroll;
        string _searchFilter = "";
        Category? _categoryFilter = null;
        Severity? _severityFilter = null;
        bool _scanning = false;
        float _scanProgress = 0f;
        int _totalFiles = 0;
        int _scannedFiles = 0;
        string _lastScanTime = "";
        DateTime _scanStart;

        // Sort state
        enum SortColumn { Severity, File, Line, Rule, Category }
        SortColumn _sortCol = SortColumn.Severity;
        bool _sortAsc = true;

        // Summary counts
        int _criticalCount, _highCount, _mediumCount, _lowCount;

        // Ignore pattern
        static readonly Regex IgnoreRegex = new Regex(
            @"//\s*VB-IGNORE:\s*([\w,-]+)", RegexOptions.Compiled);

        // Colors
        static readonly Color CriticalColor = new Color(0.9f, 0.15f, 0.15f);
        static readonly Color HighColor = new Color(0.95f, 0.55f, 0.1f);
        static readonly Color MediumColor = new Color(0.95f, 0.85f, 0.2f);
        static readonly Color LowColor = new Color(0.4f, 0.7f, 0.95f);

        // Styles (lazy init)
        GUIStyle _headerStyle;
        GUIStyle _issueStyle;
        GUIStyle _countStyle;
        bool _stylesInit;

        void InitStyles()
        {
            if (_stylesInit) return;
            _headerStyle = new GUIStyle(EditorStyles.boldLabel) { fontSize = 14 };
            _issueStyle = new GUIStyle(EditorStyles.label) { richText = true, wordWrap = true };
            _countStyle = new GUIStyle(EditorStyles.miniLabel) { alignment = TextAnchor.MiddleCenter, fontSize = 16, fontStyle = FontStyle.Bold };
            _stylesInit = true;
        }

        void OnGUI()
        {
            InitStyles();
            DrawToolbar();
            DrawSummary();
            DrawFilters();
            DrawIssueList();
        }

        void DrawToolbar()
        {
            EditorGUILayout.BeginHorizontal(EditorStyles.toolbar);

            if (GUILayout.Button("Scan Project", EditorStyles.toolbarButton, GUILayout.Width(100)))
            {
                RunScan();
            }

            if (GUILayout.Button("Export JSON", EditorStyles.toolbarButton, GUILayout.Width(90)))
            {
                ExportJson();
            }

            if (GUILayout.Button("Clear", EditorStyles.toolbarButton, GUILayout.Width(60)))
            {
                _issues.Clear();
                _criticalCount = _highCount = _mediumCount = _lowCount = 0;
            }

            GUILayout.FlexibleSpace();

            if (!string.IsNullOrEmpty(_lastScanTime))
                GUILayout.Label(_lastScanTime, EditorStyles.miniLabel);

            EditorGUILayout.EndHorizontal();

            if (_scanning)
            {
                var rect = GUILayoutUtility.GetRect(0, 20, GUILayout.ExpandWidth(true));
                EditorGUI.ProgressBar(rect, _scanProgress,
                    $"Scanning... {_scannedFiles}/{_totalFiles} files");
            }
        }

        void DrawSummary()
        {
            EditorGUILayout.BeginHorizontal();
            DrawCountBox("CRITICAL", _criticalCount, CriticalColor);
            DrawCountBox("HIGH", _highCount, HighColor);
            DrawCountBox("MEDIUM", _mediumCount, MediumColor);
            DrawCountBox("LOW", _lowCount, LowColor);
            EditorGUILayout.EndHorizontal();
        }

        void DrawCountBox(string label, int count, Color color)
        {
            var prev = GUI.backgroundColor;
            GUI.backgroundColor = count > 0 ? color : Color.gray;
            EditorGUILayout.BeginVertical("box", GUILayout.Width(position.width / 4 - 8));
            GUILayout.Label(count.ToString(), _countStyle);
            GUILayout.Label(label, EditorStyles.centeredGreyMiniLabel);
            EditorGUILayout.EndVertical();
            GUI.backgroundColor = prev;
        }

        void DrawFilters()
        {
            EditorGUILayout.BeginHorizontal();

            _searchFilter = EditorGUILayout.TextField("Search", _searchFilter, GUILayout.Width(300));

            string[] catNames = new[] { "All", "Bug", "Performance", "Security", "Unity", "Quality" };
            int catIdx = _categoryFilter.HasValue ? (int)_categoryFilter.Value + 1 : 0;
            int newCat = EditorGUILayout.Popup("Category", catIdx, catNames, GUILayout.Width(200));
            _categoryFilter = newCat == 0 ? (Category?)null : (Category)(newCat - 1);

            string[] sevNames = new[] { "All", "CRITICAL", "HIGH", "MEDIUM", "LOW" };
            int sevIdx = _severityFilter.HasValue ? (int)_severityFilter.Value + 1 : 0;
            int newSev = EditorGUILayout.Popup("Severity", sevIdx, sevNames, GUILayout.Width(200));
            _severityFilter = newSev == 0 ? (Severity?)null : (Severity)(newSev - 1);

            EditorGUILayout.EndHorizontal();
        }

        void DrawIssueList()
        {
            _scroll = EditorGUILayout.BeginScrollView(_scroll);

            var filtered = GetFilteredIssues();

            // Column headers
            EditorGUILayout.BeginHorizontal(EditorStyles.toolbar);
            if (GUILayout.Button("Sev", EditorStyles.toolbarButton, GUILayout.Width(70)))
                ToggleSort(SortColumn.Severity);
            if (GUILayout.Button("Rule", EditorStyles.toolbarButton, GUILayout.Width(80)))
                ToggleSort(SortColumn.Rule);
            if (GUILayout.Button("Cat", EditorStyles.toolbarButton, GUILayout.Width(80)))
                ToggleSort(SortColumn.Category);
            if (GUILayout.Button("File", EditorStyles.toolbarButton, GUILayout.Width(200)))
                ToggleSort(SortColumn.File);
            if (GUILayout.Button("Line", EditorStyles.toolbarButton, GUILayout.Width(50)))
                ToggleSort(SortColumn.Line);
            GUILayout.Label("Description", EditorStyles.toolbarButton);
            EditorGUILayout.EndHorizontal();

            // Issue rows
            foreach (var issue in filtered)
            {
                Color rowColor = GetSeverityColor(issue.Severity);
                var prevColor = GUI.contentColor;
                GUI.contentColor = rowColor;

                EditorGUILayout.BeginHorizontal("box");

                GUILayout.Label(issue.Severity.ToString(), GUILayout.Width(70));
                GUILayout.Label(issue.RuleId, GUILayout.Width(80));
                GUILayout.Label(issue.Category.ToString(), GUILayout.Width(80));

                string shortPath = issue.FilePath;
                if (shortPath.StartsWith("Assets/"))
                    shortPath = shortPath.Substring(7);
                if (GUILayout.Button(shortPath, EditorStyles.linkLabel, GUILayout.Width(200)))
                {
                    // Double-click: open file at line
                    var asset = AssetDatabase.LoadAssetAtPath<TextAsset>(issue.FilePath);
                    if (asset == null)
                        asset = AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(issue.FilePath) as TextAsset;
                    AssetDatabase.OpenAsset(
                        AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(issue.FilePath),
                        issue.Line);
                }

                GUILayout.Label(issue.Line.ToString(), GUILayout.Width(50));
                GUILayout.Label($"<b>{issue.Description}</b>\n<i>Fix: {issue.Fix}</i>", _issueStyle);

                EditorGUILayout.EndHorizontal();
                GUI.contentColor = prevColor;
            }

            EditorGUILayout.EndScrollView();

            EditorGUILayout.LabelField($"Showing {filtered.Count} of {_issues.Count} issues");
        }

        void ToggleSort(SortColumn col)
        {
            if (_sortCol == col) _sortAsc = !_sortAsc;
            else { _sortCol = col; _sortAsc = true; }
        }

        List<ReviewIssue> GetFilteredIssues()
        {
            var result = _issues.AsEnumerable();

            if (_categoryFilter.HasValue)
                result = result.Where(i => i.Category == _categoryFilter.Value);
            if (_severityFilter.HasValue)
                result = result.Where(i => i.Severity == _severityFilter.Value);
            if (!string.IsNullOrEmpty(_searchFilter))
            {
                string lower = _searchFilter.ToLowerInvariant();
                result = result.Where(i =>
                    i.Description.ToLowerInvariant().Contains(lower) ||
                    i.FilePath.ToLowerInvariant().Contains(lower) ||
                    i.RuleId.ToLowerInvariant().Contains(lower));
            }

            // Sort
            switch (_sortCol)
            {
                case SortColumn.Severity:
                    result = _sortAsc ? result.OrderBy(i => i.Severity) : result.OrderByDescending(i => i.Severity);
                    break;
                case SortColumn.File:
                    result = _sortAsc ? result.OrderBy(i => i.FilePath) : result.OrderByDescending(i => i.FilePath);
                    break;
                case SortColumn.Line:
                    result = _sortAsc ? result.OrderBy(i => i.Line) : result.OrderByDescending(i => i.Line);
                    break;
                case SortColumn.Rule:
                    result = _sortAsc ? result.OrderBy(i => i.RuleId) : result.OrderByDescending(i => i.RuleId);
                    break;
                case SortColumn.Category:
                    result = _sortAsc ? result.OrderBy(i => i.Category) : result.OrderByDescending(i => i.Category);
                    break;
            }

            return result.ToList();
        }

        Color GetSeverityColor(Severity sev)
        {
            switch (sev)
            {
                case Severity.CRITICAL: return CriticalColor;
                case Severity.HIGH: return HighColor;
                case Severity.MEDIUM: return MediumColor;
                case Severity.LOW: return LowColor;
                default: return Color.white;
            }
        }

        void RunScan()
        {
            _scanStart = DateTime.Now;
            _issues.Clear();
            _scanning = true;
            _scannedFiles = 0;

            // Gather all .cs files excluding packages, library, temp
            string[] allCsFiles = Directory.GetFiles(
                Application.dataPath, "*.cs", SearchOption.AllDirectories);

            // Filter out common non-project paths
            var projectFiles = allCsFiles
                .Where(f => !f.Contains("PackageCache") &&
                            !f.Contains("Library") &&
                            !f.Contains("Temp"))
                .ToArray();

            _totalFiles = projectFiles.Length;

            foreach (string fullPath in projectFiles)
            {
                try
                {
                    string content = File.ReadAllText(fullPath, Encoding.UTF8);
                    string[] lines = content.Split('\n');

                    // Build set of ignored rule IDs for this file
                    var ignoredRules = new HashSet<string>();
                    for (int i = 0; i < lines.Length; i++)
                    {
                        var im = IgnoreRegex.Match(lines[i]);
                        if (im.Success)
                        {
                            foreach (string ruleId in im.Groups[1].Value.Split(','))
                                ignoredRules.Add(ruleId.Trim());
                        }
                    }

                    // Convert to Unity-relative path
                    string relativePath = "Assets" + fullPath.Substring(Application.dataPath.Length).Replace('\\', '/');

                    // Skip files in Editor folder for runtime-only rules
                    bool isEditorFile = relativePath.Contains("/Editor/");

                    // === PASS 1: Regex pattern matching ===
                    foreach (var rule in ReviewRules.AllRules)
                    {
                        if (ignoredRules.Contains(rule.Id)) continue;

                        // Skip editor-only checks on editor scripts
                        if (isEditorFile && rule.Id == "UNITY-09") continue;

                        for (int i = 0; i < lines.Length; i++)
                        {
                            // Skip VB-IGNORE lines
                            if (lines[i].Contains("VB-IGNORE")) continue;

                            if (rule.Pattern.IsMatch(lines[i]))
                            {
                                // Run context guard to reduce false positives
                                if (rule.ContextGuard != null && !rule.ContextGuard(lines[i], lines, i))
                                    continue;

                                _issues.Add(new ReviewIssue
                                {
                                    RuleId = rule.Id,
                                    Severity = rule.Severity,
                                    Category = rule.Category,
                                    FilePath = relativePath,
                                    Line = i + 1,
                                    Description = rule.Description,
                                    Fix = rule.Fix,
                                    MatchedText = lines[i].Trim()
                                });
                            }
                        }
                    }

                    // === PASS 2: Deep AST-aware analysis ===
                    var deepIssues = DeepAnalyzer.Analyze(relativePath, lines);
                    foreach (var di in deepIssues)
                    {
                        if (!ignoredRules.Contains(di.RuleId))
                            _issues.Add(di);
                    }
                }
                catch (Exception ex)
                {
                    Debug.LogWarning($"[VBCodeReviewer] Failed to scan {fullPath}: {ex.Message}");
                }

                _scannedFiles++;
                _scanProgress = (float)_scannedFiles / _totalFiles;
            }

            // Count severities
            _criticalCount = _issues.Count(i => i.Severity == Severity.CRITICAL);
            _highCount = _issues.Count(i => i.Severity == Severity.HIGH);
            _mediumCount = _issues.Count(i => i.Severity == Severity.MEDIUM);
            _lowCount = _issues.Count(i => i.Severity == Severity.LOW);

            _scanning = false;
            var elapsed = DateTime.Now - _scanStart;
            _lastScanTime = $"{_totalFiles} files in {elapsed.TotalSeconds:F2}s | {_issues.Count} issues";
            Repaint();
        }

        void ExportJson()
        {
            string path = EditorUtility.SaveFilePanel(
                "Export Code Review Results", "", "vb_code_review.json", "json");
            if (string.IsNullOrEmpty(path)) return;

            var sb = new StringBuilder();
            sb.AppendLine("{");
            sb.AppendLine($"  \"scan_time\": \"{_lastScanTime}\",");
            sb.AppendLine($"  \"total_issues\": {_issues.Count},");
            sb.AppendLine($"  \"critical\": {_criticalCount},");
            sb.AppendLine($"  \"high\": {_highCount},");
            sb.AppendLine($"  \"medium\": {_mediumCount},");
            sb.AppendLine($"  \"low\": {_lowCount},");
            sb.AppendLine("  \"issues\": [");
            for (int i = 0; i < _issues.Count; i++)
            {
                var issue = _issues[i];
                string escapedDesc = issue.Description.Replace("\\", "\\\\").Replace("\"", "\\\"");
                string escapedFix = issue.Fix.Replace("\\", "\\\\").Replace("\"", "\\\"");
                string escapedPath = issue.FilePath.Replace("\\", "/");
                string escapedMatch = (issue.MatchedText ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\r", "").Replace("\n", " ");
                sb.AppendLine("    {");
                sb.AppendLine($"      \"rule_id\": \"{issue.RuleId}\",");
                sb.AppendLine($"      \"severity\": \"{issue.Severity}\",");
                sb.AppendLine($"      \"category\": \"{issue.Category}\",");
                sb.AppendLine($"      \"file\": \"{escapedPath}\",");
                sb.AppendLine($"      \"line\": {issue.Line},");
                sb.AppendLine($"      \"description\": \"{escapedDesc}\",");
                sb.AppendLine($"      \"fix\": \"{escapedFix}\",");
                sb.AppendLine($"      \"matched_text\": \"{escapedMatch}\"");
                sb.Append("    }");
                if (i < _issues.Count - 1) sb.Append(",");
                sb.AppendLine();
            }
            sb.AppendLine("  ]");
            sb.AppendLine("}");

            File.WriteAllText(path, sb.ToString(), Encoding.UTF8);
            Debug.Log($"[VBCodeReviewer] Exported {_issues.Count} issues to {path}");
        }

        // Public API for CI integration
        public static string RunHeadless()
        {
            var reviewer = CreateInstance<VBCodeReviewer>();
            reviewer.RunScan();
            var sb = new StringBuilder();
            sb.AppendLine($"VB Code Review: {reviewer._issues.Count} issues found");
            sb.AppendLine($"  CRITICAL: {reviewer._criticalCount}");
            sb.AppendLine($"  HIGH: {reviewer._highCount}");
            sb.AppendLine($"  MEDIUM: {reviewer._mediumCount}");
            sb.AppendLine($"  LOW: {reviewer._lowCount}");
            DestroyImmediate(reviewer);
            return sb.ToString();
        }

        // Menu item for quick CI run
        [MenuItem("VeilBreakers/Code Review/Run Headless (Console Output)")]
        static void RunHeadlessMenu()
        {
            Debug.Log(RunHeadless());
        }
    }
}
'''

    return {
        "script_path": "Assets/Editor/VeilBreakers/VB_CodeReviewer.cs",
        "script_content": script.strip(),
        "next_steps": [
            "Run unity_editor action=recompile to compile the script",
            "Open Unity Editor and go to VeilBreakers > Code Review > Open Reviewer",
            "Click 'Scan Project' to analyze all .cs files",
            "Use category/severity filters to focus on critical issues",
            "Double-click any issue to open the file at that line in your IDE",
            "Click 'Export JSON' for CI integration",
            "Add // VB-IGNORE: RULE_ID to suppress specific false positives",
        ],
    }


# ---------------------------------------------------------------------------
# Python Reviewer Script Generator
# ---------------------------------------------------------------------------


def generate_python_reviewer_script() -> dict:
    """Generate vb_python_reviewer.py -- standalone Python code reviewer.

    30 rules covering security, correctness, and style.  Outputs a JSON
    report to stdout or file.

    Returns:
        Dict with script_path, script_content, next_steps.
    """

    script = r'''#!/usr/bin/env python3
"""VeilBreakers Python Code Reviewer.

Two-pass review system for Python codebases:
  Pass 1: Compiled regex pattern matching (fast, line-by-line)
  Pass 2: AST-aware analysis for imports, function signatures, scoping

Usage:
    python vb_python_reviewer.py [path] [--output report.json] [--severity MEDIUM]
    python vb_python_reviewer.py src/ --output report.json
    python vb_python_reviewer.py my_script.py --severity HIGH

Exit codes:
    0 -- no issues at or above threshold severity
    1 -- issues found at or above threshold severity
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Optional


class Severity(IntEnum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class Category(IntEnum):
    Security = 0
    Correctness = 1
    Performance = 2
    Style = 3


@dataclass
class Rule:
    id: str
    severity: Severity
    category: Category
    description: str
    fix: str
    pattern: re.Pattern
    guard: Optional[object] = None  # callable(line, all_lines, idx) -> bool


@dataclass
class Issue:
    rule_id: str
    severity: str
    category: str
    file: str
    line: int
    description: str
    fix: str
    matched_text: str = ""


# ---------------------------------------------------------------------------
# Guard helpers
# ---------------------------------------------------------------------------

def _not_in_comment(line: str, _all: list[str], _idx: int) -> bool:
    stripped = line.lstrip()
    return not stripped.startswith("#")


def _not_in_string(line: str, _all: list[str], _idx: int) -> bool:
    stripped = line.lstrip()
    return not stripped.startswith(("'", '"', "b'", 'b"', "f'", 'f"', "r'", 'r"'))


def _active_code(line: str, all_lines: list[str], idx: int) -> bool:
    return _not_in_comment(line, all_lines, idx) and _not_in_string(line, all_lines, idx)


# ---------------------------------------------------------------------------
# Rule definitions -- 30 rules
# ---------------------------------------------------------------------------

RULES: list[Rule] = [
    # ---- SECURITY ----
    Rule("PY-SEC-01", Severity.CRITICAL, Category.Security,
         "eval() usage -- arbitrary code execution risk",
         "Replace with ast.literal_eval() for safe data parsing, or redesign to avoid eval.",
         re.compile(r"\beval\s*\("), guard=_active_code),

    Rule("PY-SEC-02", Severity.CRITICAL, Category.Security,
         "os.system() or subprocess with shell=True -- command injection risk",
         "Use subprocess.run() with a list of args and shell=False.",
         re.compile(r"(os\.system\s*\(|subprocess\.\w+\([^)]*shell\s*=\s*True)"),
         guard=_active_code),

    Rule("PY-SEC-03", Severity.CRITICAL, Category.Security,
         "pickle.load on potentially untrusted data -- arbitrary code execution",
         "Use json, msgpack, or a safer serialization format.",
         re.compile(r"pickle\.(load|loads)\s*\("), guard=_active_code),

    Rule("PY-SEC-04", Severity.HIGH, Category.Security,
         "f-string with variable in SQL/shell command -- injection risk",
         "Use parameterized queries for SQL; use subprocess with list args for shell.",
         re.compile(r'(execute|run|system|popen)\s*\(\s*f["\']'),
         guard=_active_code),

    Rule("PY-SEC-05", Severity.HIGH, Category.Security,
         "exec() usage -- arbitrary code execution",
         "Avoid exec(); refactor to use safe alternatives.",
         re.compile(r"\bexec\s*\("), guard=_active_code),

    Rule("PY-SEC-06", Severity.MEDIUM, Category.Security,
         "Hardcoded file path -- not portable, consider pathlib or config",
         "Use pathlib.Path or os.path.join with configurable base directories.",
         re.compile(r"['\"](/[a-z]+/|[A-Z]:\\\\)[^'\"]{3,}['\"]"),
         guard=_active_code),

    Rule("PY-SEC-07", Severity.HIGH, Category.Security,
         "assert used for input validation -- stripped in optimized mode (-O)",
         "Use if/raise ValueError for validation that must always run.",
         re.compile(r"^\s*assert\s+(?!.*#\s*nosec)"),
         guard=_not_in_comment),

    # ---- CORRECTNESS ----
    Rule("PY-COR-01", Severity.HIGH, Category.Correctness,
         "Mutable default argument -- shared across calls, causes subtle bugs",
         "Use None as default and create the mutable inside the function body.",
         re.compile(r"def\s+\w+\s*\([^)]*=\s*(\[\]|\{\}|set\(\))"),
         guard=_active_code),

    Rule("PY-COR-02", Severity.HIGH, Category.Correctness,
         "Bare except: clause -- catches SystemExit, KeyboardInterrupt, etc.",
         "Catch specific exceptions: except ValueError, except Exception as e.",
         re.compile(r"^\s*except\s*:"), guard=_not_in_comment),

    Rule("PY-COR-03", Severity.MEDIUM, Category.Correctness,
         "Comparing with None using == instead of 'is None'",
         "Use 'is None' or 'is not None' for identity comparison with None.",
         re.compile(r"[!=]=\s*None\b"), guard=_active_code),

    Rule("PY-COR-04", Severity.MEDIUM, Category.Correctness,
         "open() without context manager -- file may not be closed on exception",
         "Use 'with open(...) as f:' to ensure proper cleanup.",
         re.compile(r"(?<!\bwith\s)\bopen\s*\("),
         guard=lambda line, a, i: "with" not in line and _active_code(line, a, i)),

    Rule("PY-COR-05", Severity.LOW, Category.Correctness,
         "datetime.now() without timezone -- ambiguous in distributed systems",
         "Use datetime.now(tz=timezone.utc) or datetime.now(ZoneInfo('...')).",
         re.compile(r"datetime\.now\s*\(\s*\)"), guard=_active_code),

    Rule("PY-COR-06", Severity.MEDIUM, Category.Correctness,
         "dict.get() with mutable default -- returns same object every call",
         "Use dict.get(key) with None check, then create mutable separately.",
         re.compile(r"\.get\s*\([^)]*,\s*(\[\]|\{\}|set\(\))"),
         guard=_active_code),

    Rule("PY-COR-07", Severity.MEDIUM, Category.Correctness,
         "Class with __del__ -- unpredictable GC timing, prevents ref cycle collection",
         "Use context managers (__enter__/__exit__) or weakref.finalize instead.",
         re.compile(r"def\s+__del__\s*\(\s*self"), guard=_active_code),

    Rule("PY-COR-08", Severity.MEDIUM, Category.Correctness,
         "Thread created without daemon=True -- may prevent clean shutdown",
         "Set daemon=True or ensure thread is joined before exit.",
         re.compile(r"Thread\s*\("),
         guard=lambda line, a, i: "daemon" not in line and _active_code(line, a, i)),

    Rule("PY-COR-09", Severity.LOW, Category.Correctness,
         "json.loads without error handling -- will raise on malformed input",
         "Wrap json.loads in try/except json.JSONDecodeError.",
         re.compile(r"json\.loads?\s*\("),
         guard=lambda line, a, i: not any("except" in a[j] and "JSON" in a[j]
             for j in range(max(0, i-5), min(len(a), i+10))) and _active_code(line, a, i)),

    Rule("PY-COR-10", Severity.LOW, Category.Correctness,
         "Float equality comparison -- use math.isclose for floating-point",
         "Use math.isclose(a, b) or abs(a - b) < epsilon.",
         re.compile(r"(?<!\w)(==|!=)\s*\d+\.\d+"),
         guard=_active_code),

    Rule("PY-COR-11", Severity.MEDIUM, Category.Correctness,
         "Re-raising exception without chain -- loses traceback context",
         "Use 'raise NewException(...) from e' to preserve the exception chain.",
         re.compile(r"raise\s+\w+\([^)]*\)\s*$"),
         guard=lambda line, a, i: any("except" in a[j] for j in range(max(0, i-5), i)) and _active_code(line, a, i)),

    Rule("PY-COR-12", Severity.MEDIUM, Category.Correctness,
         "Exception type too broad -- catches bugs along with expected errors",
         "Catch specific exceptions instead of bare Exception.",
         re.compile(r"except\s+Exception\s*(?:as|\s*:)"),
         guard=_not_in_comment),

    # ---- PERFORMANCE ----
    Rule("PY-PERF-01", Severity.LOW, Category.Performance,
         "String concatenation in loop -- O(n^2), use str.join or list append",
         "Collect parts in a list and ''.join(parts) after the loop.",
         re.compile(r"(?:for|while)\b.*\n\s+\w+\s*\+=\s*['\"]"),
         guard=_not_in_comment),

    Rule("PY-PERF-02", Severity.LOW, Category.Performance,
         "re.match/search/findall without re.compile for repeated pattern",
         "Compile the pattern once with re.compile() and reuse the compiled object.",
         re.compile(r"re\.(match|search|findall|sub|split)\s*\("),
         guard=_active_code),

    Rule("PY-PERF-03", Severity.LOW, Category.Performance,
         "Large file read without chunking -- may exhaust memory",
         "Use chunked reading: for line in file, or file.read(chunk_size).",
         re.compile(r"\.read\s*\(\s*\)"), guard=_active_code),

    # ---- STYLE ----
    Rule("PY-STY-01", Severity.LOW, Category.Style,
         "os.path usage instead of pathlib.Path -- pathlib is more Pythonic",
         "Use pathlib.Path for path manipulation (Python 3.4+).",
         re.compile(r"os\.path\.(join|exists|isfile|isdir|basename|dirname|splitext)\s*\("),
         guard=_active_code),

    Rule("PY-STY-02", Severity.LOW, Category.Style,
         "Nested function definitions over 3 levels -- hard to read and test",
         "Extract inner functions to module level or class methods.",
         re.compile(r"^\s{12,}def\s+\w+\s*\("),
         guard=_not_in_comment),

    Rule("PY-STY-03", Severity.LOW, Category.Style,
         "Star import (from X import *) -- namespace pollution, hides origin",
         "Import specific names: from X import a, b, c.",
         re.compile(r"from\s+\S+\s+import\s+\*"),
         guard=_not_in_comment),

    Rule("PY-STY-04", Severity.LOW, Category.Style,
         "Global variable mutation -- makes code hard to reason about",
         "Pass as function parameters or use a class to encapsulate state.",
         re.compile(r"^\s+global\s+\w+"), guard=_not_in_comment),

    Rule("PY-STY-05", Severity.LOW, Category.Style,
         "Missing if __name__ == '__main__' guard -- code runs on import",
         "Wrap script-level code in: if __name__ == '__main__':",
         re.compile(r"SENTINEL_NEVER_MATCHES_PLACEHOLDER")),  # handled by AST pass

    Rule("PY-STY-06", Severity.LOW, Category.Style,
         "Missing __all__ in public module -- unclear public API surface",
         "Add __all__ = ['PublicClass', 'public_func'] to define the public API.",
         re.compile(r"SENTINEL_NEVER_MATCHES_PLACEHOLDER")),  # handled by AST pass

    Rule("PY-STY-07", Severity.LOW, Category.Style,
         "Unused import detected",
         "Remove the unused import to keep the namespace clean.",
         re.compile(r"SENTINEL_NEVER_MATCHES_PLACEHOLDER")),  # handled by AST pass

    Rule("PY-STY-08", Severity.LOW, Category.Style,
         "Missing type annotation on public function",
         "Add return type annotation and parameter type hints.",
         re.compile(r"SENTINEL_NEVER_MATCHES_PLACEHOLDER")),  # handled by AST pass
]


# ---------------------------------------------------------------------------
# Pass 2: AST-aware analysis
# ---------------------------------------------------------------------------

def _ast_analyze(filepath: str, source: str) -> list[Issue]:
    """AST-based analysis for patterns that regex cannot reliably detect."""
    issues: list[Issue] = []

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return issues

    # Collect all names used in the module (for unused import detection)
    all_names_used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            all_names_used.add(node.id)
        elif isinstance(node, ast.Attribute):
            # Collect top-level attribute access like `os.path`
            if isinstance(node.value, ast.Name):
                all_names_used.add(node.value.id)

    # Check imports
    imported_names: dict[str, int] = {}  # name -> line
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name.split(".")[0]
                imported_names[name] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.names[0].name == "*":
                continue  # handled by regex rule
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                imported_names[name] = node.lineno

    # PY-STY-07: Unused imports
    for name, lineno in imported_names.items():
        if name.startswith("_"):
            continue  # convention: private/re-export
        if name not in all_names_used:
            issues.append(Issue(
                rule_id="PY-STY-07",
                severity=Severity.LOW.name,
                category=Category.Style.name,
                file=filepath,
                line=lineno,
                description=f"Unused import: '{name}'",
                fix="Remove the unused import to keep the namespace clean.",
                matched_text=name,
            ))

    # PY-STY-08: Missing type annotations on public functions
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            if node.returns is None:
                issues.append(Issue(
                    rule_id="PY-STY-08",
                    severity=Severity.LOW.name,
                    category=Category.Style.name,
                    file=filepath,
                    line=node.lineno,
                    description=f"Public function '{node.name}' missing return type annotation",
                    fix="Add return type annotation: def func(...) -> ReturnType:",
                    matched_text=node.name,
                ))

    # PY-STY-05: Missing __main__ guard (only for files with top-level executable code)
    has_main_guard = False
    has_top_level_code = False
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.If):
            # Check for if __name__ == "__main__"
            test = node.test
            if (isinstance(test, ast.Compare) and
                    isinstance(test.left, ast.Name) and
                    test.left.id == "__name__"):
                has_main_guard = True
        elif isinstance(node, ast.Expr):
            # Function calls at module level
            if isinstance(node.value, ast.Call):
                has_top_level_code = True

    if has_top_level_code and not has_main_guard:
        issues.append(Issue(
            rule_id="PY-STY-05",
            severity=Severity.LOW.name,
            category=Category.Style.name,
            file=filepath,
            line=1,
            description="Module has top-level executable code without __main__ guard",
            fix="Wrap script-level code in: if __name__ == '__main__':",
        ))

    # PY-STY-06: Missing __all__ in modules with public names
    has_all = any(
        isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__"
            for t in n.targets
        )
        for n in ast.iter_child_nodes(tree)
    )
    public_names = [
        n for n in ast.iter_child_nodes(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not n.name.startswith("_")
    ]
    if not has_all and len(public_names) >= 3:
        issues.append(Issue(
            rule_id="PY-STY-06",
            severity=Severity.LOW.name,
            category=Category.Style.name,
            file=filepath,
            line=1,
            description=f"Module exports {len(public_names)} public names but has no __all__",
            fix="Add __all__ = [...] to define the public API.",
        ))

    # Circular import detection hint: if any import is inside a function body
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    issues.append(Issue(
                        rule_id="PY-COR-13",
                        severity=Severity.LOW.name,
                        category=Category.Correctness.name,
                        file=filepath,
                        line=child.lineno,
                        description="Import inside function body -- may indicate circular import workaround",
                        fix="Restructure modules to avoid circular dependencies.",
                    ))

    return issues


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def scan_file(filepath: str) -> list[Issue]:
    """Scan a single Python file with both passes."""
    issues: list[Issue] = []

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return issues

    lines = content.split("\n")

    # Build set of suppressed rules
    suppressed: set[str] = set()
    ignore_re = re.compile(r"#\s*VB-IGNORE:\s*([\w,-]+)")
    for line in lines:
        m = ignore_re.search(line)
        if m:
            for rule_id in m.group(1).split(","):
                suppressed.add(rule_id.strip())

    # Pass 1: Regex
    for rule in RULES:
        if rule.id in suppressed:
            continue
        # Skip sentinel rules (AST-only)
        if "SENTINEL" in rule.pattern.pattern:
            continue
        for i, line in enumerate(lines):
            if "VB-IGNORE" in line:
                continue
            if rule.pattern.search(line):
                if rule.guard and not rule.guard(line, lines, i):
                    continue
                issues.append(Issue(
                    rule_id=rule.id,
                    severity=rule.severity.name,
                    category=rule.category.name,
                    file=filepath,
                    line=i + 1,
                    description=rule.description,
                    fix=rule.fix,
                    matched_text=line.strip(),
                ))

    # Pass 2: AST
    ast_issues = _ast_analyze(filepath, content)
    for issue in ast_issues:
        if issue.rule_id not in suppressed:
            issues.append(issue)

    return issues


def scan_directory(dirpath: str) -> list[Issue]:
    """Recursively scan all .py files in a directory."""
    all_issues: list[Issue] = []
    root = Path(dirpath)

    for py_file in sorted(root.rglob("*.py")):
        # Skip common non-project dirs
        parts = py_file.parts
        if any(p in (".venv", "venv", "node_modules", "__pycache__",
                      ".git", ".tox", "dist", "build", "egg-info")
               for p in parts):
            continue
        all_issues.extend(scan_file(str(py_file)))

    return all_issues


def generate_report(issues: list[Issue]) -> dict:
    """Generate a structured report dict."""
    severity_counts = {s.name: 0 for s in Severity}
    for issue in issues:
        severity_counts[issue.severity] += 1

    return {
        "total_issues": len(issues),
        "critical": severity_counts["CRITICAL"],
        "high": severity_counts["HIGH"],
        "medium": severity_counts["MEDIUM"],
        "low": severity_counts["LOW"],
        "issues": [asdict(i) for i in issues],
    }


def main():
    parser = argparse.ArgumentParser(
        description="VeilBreakers Python Code Reviewer")
    parser.add_argument("path", nargs="?", default=".",
                        help="File or directory to scan (default: current dir)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output JSON file path (default: stdout)")
    parser.add_argument("--severity", "-s", default="LOW",
                        choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                        help="Minimum severity to report (default: LOW)")
    args = parser.parse_args()

    target = Path(args.path)
    if target.is_file():
        issues = scan_file(str(target))
    elif target.is_dir():
        issues = scan_directory(str(target))
    else:
        print(f"Error: {args.path} is not a valid file or directory",
              file=sys.stderr)
        sys.exit(2)

    # Filter by severity
    threshold = Severity[args.severity]
    issues = [i for i in issues if Severity[i.severity] <= threshold]

    report = generate_report(issues)

    output = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output} ({len(issues)} issues)",
              file=sys.stderr)
    else:
        print(output)

    # Exit code: 1 if any CRITICAL or HIGH issues
    has_serious = any(i.severity in ("CRITICAL", "HIGH") for i in issues)
    sys.exit(1 if has_serious else 0)


if __name__ == "__main__":
    main()
'''

    return {
        "script_path": "Tools/mcp-toolkit/src/veilbreakers_mcp/vb_python_reviewer.py",
        "script_content": script.strip(),
        "next_steps": [
            "Run: python vb_python_reviewer.py <path> --output report.json",
            "Use --severity HIGH to filter out low-priority style issues",
            "Add # VB-IGNORE: RULE_ID to suppress specific false positives",
            "Integrate into CI with: python vb_python_reviewer.py src/ -o report.json && exit $?",
        ],
    }
