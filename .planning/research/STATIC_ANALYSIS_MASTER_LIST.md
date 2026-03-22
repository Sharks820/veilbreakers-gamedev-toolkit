# Static Analysis & Code Review Master List

## Research Summary

Comprehensive analysis of code review and static analysis tools for Unity C# and Python,
focused on our use case: **generated C# code** (from Python MCP tools) and **Python server code**.

### Tools Evaluated
- **Microsoft.Unity.Analyzers** (UNT0001-UNT0036) -- official Roslyn analyzers for Unity
- **UnityEngineAnalyzer** (UEA0001-UEA0013) -- community Roslyn analyzers
- **PVS-Studio GameDev Guardian** (V4001-V4006) -- commercial Unity diagnostics
- **ReSharper/Rider Unity Plugin** -- JetBrains performance analysis
- **SonarQube sonar-dotnet** -- 6000+ C# rules
- **Semgrep** -- pattern-based C# and Python analysis (99%+ C# parse rate)
- **.NET Roslyn Analyzers** (CAxxxx) -- Microsoft code quality rules
- **Ruff** -- 800+ Python rules, 10-100x faster than alternatives
- **Bandit** -- Python security scanner (47 built-in checks)
- **mypy** -- Python type checker (strict mode)

### Applicability to Generated C#
Our tools generate C# editor scripts from Python. Key considerations:
- Generated code runs in Unity Editor context (not player runtime)
- Code uses UnityEditor/UnityEngine APIs extensively
- Scripts are written to disk and compiled by Unity
- Path construction, file I/O, and string interpolation are common patterns
- No end-user input handling (editor-only), but path traversal still matters

---

## CATEGORY 1: BUG DETECTION (Rules 1-25)

### 1. NULL-REF-001: Null Reference on Destroyed Unity Object
- **Severity:** CRITICAL
- **Source:** Microsoft.Unity.Analyzers UNT0007, UNT0008, UNT0023, UNT0029
- **Description:** Unity overrides `==` operator on UnityEngine.Object. Using `?.`, `??`, `??=`, or C# pattern matching `is null` bypasses Unity's null check and will NOT detect destroyed objects. A destroyed GameObject is not C#-null but is Unity-null.
- **Detection Pattern:** `obj?.method`, `obj ?? fallback`, `obj ??= new`, `obj is null`, `obj is not null` where obj derives from UnityEngine.Object
- **Fix:** Use explicit `if (obj == null)` or `if (obj != null)` which invokes Unity's custom equality operator
- **False Positive Rate:** Very low -- any use of these operators on UnityEngine.Object is almost certainly a bug

### 2. NULL-REF-002: Unchecked GetComponent Result
- **Severity:** HIGH
- **Source:** Custom / ReSharper Unity
- **Description:** `GetComponent<T>()` returns null if component not found. Using result without null check causes NullReferenceException.
- **Detection Pattern:** `GetComponent<T>().member` without preceding null check; `var x = GetComponent<T>(); x.Method()` without `if (x != null)`
- **Fix:** Use `TryGetComponent<T>(out var component)` or add null check

### 3. NULL-REF-003: Coroutine Accessing Destroyed Object
- **Severity:** HIGH
- **Source:** Custom
- **Description:** Coroutines continue running after yield even if the spawning GameObject is destroyed. Accessing `this`, `gameObject`, or cached references after yield throws MissingReferenceException.
- **Detection Pattern:** Any member access after `yield return` without null/destroyed check
- **Fix:** Add `if (this == null) yield break;` or `if (gameObject == null) yield break;` after each yield

### 4. NULL-REF-004: Async Task Accessing Destroyed Object
- **Severity:** HIGH
- **Source:** Custom
- **Description:** Unlike coroutines, async Tasks are NOT tied to GameObjects. They continue executing even after the spawning object is destroyed, and run on thread pool by default.
- **Detection Pattern:** `async void` or `async Task` methods accessing Unity API after `await`
- **Fix:** Use `Awaitable` (Unity 2023+) or check `this != null` after each await; never use `async void`

### 5. RACE-001: Main Thread API Access from Background Thread
- **Severity:** CRITICAL
- **Source:** Unity Runtime / Custom
- **Description:** Almost all Unity APIs must be called from the main thread. Calling them from async Tasks, threads, or Jobs causes crashes or undefined behavior.
- **Detection Pattern:** Unity API calls inside `Task.Run`, `Thread`, or Job struct `Execute()`
- **Fix:** Use `UnityMainThreadDispatcher` or `Awaitable.MainThreadAsync()`

### 6. RACE-002: Shared Mutable State Without Synchronization
- **Severity:** HIGH
- **Source:** SonarQube / Custom
- **Description:** Static fields or shared collections modified from multiple threads (e.g., Update + async callback) without locks.
- **Detection Pattern:** Static mutable field accessed in both Update-family methods and async/threaded code
- **Fix:** Use `ConcurrentDictionary`, `Interlocked`, or `lock` statements

### 7. LOOP-001: Potential Infinite Loop in While
- **Severity:** CRITICAL
- **Source:** Custom
- **Description:** `while(true)` or `while(condition)` where condition variable is never modified inside loop body and no `break`/`return`/`yield` exists.
- **Detection Pattern:** While loop where loop variable is not assigned within body; for loop where iterator is not incremented
- **Fix:** Ensure loop has exit condition; add safety counter `if (++safety > 10000) break;`

### 8. LOOP-002: Off-by-One in Array/List Iteration
- **Severity:** MEDIUM
- **Source:** Roslyn CA / Custom
- **Description:** Using `<=` instead of `<` in `for (int i = 0; i <= array.Length; i++)` causes IndexOutOfRangeException.
- **Detection Pattern:** `i <= collection.Length` or `i <= collection.Count` in for loop bound
- **Fix:** Use `<` not `<=` for zero-based indexing

### 9. LOGIC-001: Unreachable Code After Return/Break/Throw
- **Severity:** MEDIUM
- **Source:** Roslyn CS0162, Ruff F811
- **Description:** Code after unconditional return, break, continue, or throw is dead and indicates logic error.
- **Detection Pattern:** Statements following return/break/throw in same block
- **Fix:** Remove dead code or fix control flow logic

### 10. LOGIC-002: Assignment in Conditional (= vs ==)
- **Severity:** HIGH
- **Source:** Roslyn CS / Ruff E711
- **Description:** Using `=` instead of `==` in if/while conditions silently assigns and always evaluates to assigned value.
- **Detection Pattern:** `if (x = value)` instead of `if (x == value)`
- **Fix:** Use `==` for comparison

### 11. LOGIC-003: Floating Point Equality Comparison
- **Severity:** MEDIUM
- **Source:** SonarQube S1244 / Custom
- **Description:** `float == float` comparisons are unreliable due to floating point precision. Common in Unity transform/physics code.
- **Detection Pattern:** `floatA == floatB` or `floatA != floatB`
- **Fix:** Use `Mathf.Approximately(a, b)` or `Mathf.Abs(a - b) < epsilon`

### 12. LOGIC-004: Integer Division Truncation
- **Severity:** MEDIUM
- **Source:** SonarQube S2184
- **Description:** `int / int` truncates result. `int x = 1/3;` gives 0, not 0.333f.
- **Detection Pattern:** Integer division assigned to float/double, or integer division in expression expecting float result
- **Fix:** Cast one operand: `(float)a / b`

### 13. DISPOSE-001: IDisposable Not Disposed
- **Severity:** HIGH
- **Source:** Roslyn CA2000, SonarQube S3966
- **Description:** Objects implementing IDisposable (streams, readers, HTTP clients) not disposed, causing resource leaks.
- **Detection Pattern:** `new StreamReader(...)` or similar without `using` statement or `Dispose()` call
- **Fix:** Wrap in `using` statement or `using` declaration

### 14. DISPOSE-002: Double Dispose
- **Severity:** MEDIUM
- **Source:** SonarQube S3966
- **Description:** Disposing same object twice (explicit Dispose + using block) can throw ObjectDisposedException.
- **Detection Pattern:** Object in `using` block also has explicit `.Dispose()` call
- **Fix:** Remove redundant Dispose call

### 15. ENUM-001: Missing Default Case in Switch on Enum
- **Severity:** MEDIUM
- **Source:** Roslyn CS8509 / Custom
- **Description:** Switch on enum without default/exhaustive cases silently falls through when new enum values are added.
- **Detection Pattern:** Switch statement/expression on enum type missing `default` case or not covering all values
- **Fix:** Add `default: throw new ArgumentOutOfRangeException()`

### 16. TYPE-001: Invalid Cast Without Type Check
- **Severity:** HIGH
- **Source:** Roslyn / Custom
- **Description:** Direct cast `(T)obj` throws InvalidCastException if types don't match. Common when deserializing or processing heterogeneous collections.
- **Detection Pattern:** Direct cast without preceding `is T` check or `as T` with null check
- **Fix:** Use `if (obj is T typed)` or `obj as T` with null check

### 17. COLLECTION-001: Collection Modified During Enumeration
- **Severity:** HIGH
- **Source:** SonarQube / Custom
- **Description:** Adding/removing from collection while iterating with foreach throws InvalidOperationException.
- **Detection Pattern:** Add/Remove/Clear on collection inside foreach loop over same collection
- **Fix:** Iterate over `.ToList()` copy, or use for loop iterating backwards

### 18. STRING-001: String.Format Argument Count Mismatch
- **Severity:** HIGH
- **Source:** Roslyn CA2241, SonarQube S2275
- **Description:** `string.Format("{0} {1} {2}", a, b)` -- fewer args than placeholders throws FormatException.
- **Detection Pattern:** Format string placeholder count != argument count
- **Fix:** Match placeholder indices to argument count; prefer string interpolation `$"{a} {b}"`

### 19. ASYNC-001: Async Void Method
- **Severity:** HIGH
- **Source:** Roslyn VSTHRD100, Custom
- **Description:** `async void` methods swallow exceptions and cannot be awaited. Only valid for event handlers.
- **Detection Pattern:** Method signature `async void MethodName()` not matching event handler signature
- **Fix:** Change to `async Task MethodName()` or `async Awaitable MethodName()`

### 20. ASYNC-002: Missing Await on Task
- **Severity:** HIGH
- **Source:** Roslyn CS4014
- **Description:** Calling async method without `await` causes fire-and-forget execution; exceptions are lost.
- **Detection Pattern:** Call to method returning Task/Task<T> without await, assignment, or explicit discard
- **Fix:** Add `await` or assign to variable for later awaiting

### 21. EXCEPTION-001: Catching Generic Exception
- **Severity:** MEDIUM
- **Source:** Roslyn CA1031, SonarQube S2221
- **Description:** `catch (Exception)` catches everything including OutOfMemoryException, StackOverflowException. Hides bugs.
- **Detection Pattern:** `catch (Exception)` or `catch (Exception ex)` without rethrowing specific types
- **Fix:** Catch specific exception types

### 22. EXCEPTION-002: Empty Catch Block
- **Severity:** HIGH
- **Source:** SonarQube S108, Ruff B001
- **Description:** `catch { }` silently swallows all errors, hiding bugs completely.
- **Detection Pattern:** Catch block with empty body or only comment
- **Fix:** At minimum log the exception: `Debug.LogException(ex)`

### 23. EQUALITY-001: Overriding Equals Without GetHashCode
- **Severity:** HIGH
- **Source:** Roslyn CA / SonarQube S1206
- **Description:** If Equals is overridden but GetHashCode is not, objects will behave incorrectly in Dictionary/HashSet.
- **Detection Pattern:** Class overrides `Equals` but not `GetHashCode` (or vice versa)
- **Fix:** Always override both together

### 24. MATH-001: Division by Zero
- **Severity:** CRITICAL
- **Source:** Custom
- **Description:** Dividing by variable that could be zero without guard. Common with `count`, `length`, normalized vectors.
- **Detection Pattern:** Division by variable not guarded by `!= 0` check; `1f / magnitude` without magnitude check
- **Fix:** Add zero check: `if (divisor != 0)` or use `Mathf.Max(divisor, 0.0001f)`

### 25. SCOPE-001: Variable Shadowing
- **Severity:** MEDIUM
- **Source:** Roslyn CS / Ruff F811
- **Description:** Local variable with same name as field, parameter, or outer scope variable. Causes confusion about which variable is being modified.
- **Detection Pattern:** Local variable declaration matching name of field or parameter in scope
- **Fix:** Rename local variable or use `this.fieldName` explicitly

---

## CATEGORY 2: PERFORMANCE (Rules 26-50)

### 26. PERF-001: GetComponent in Update/FixedUpdate/LateUpdate
- **Severity:** CRITICAL
- **Source:** Microsoft.Unity.Analyzers UNT0014, PVS-Studio V4005, ReSharper Unity
- **Description:** GetComponent performs component lookup every call. In Update (called every frame), this is extremely wasteful.
- **Detection Pattern:** `GetComponent<T>()`, `GetComponentInChildren<T>()`, `GetComponentInParent<T>()` called inside Update/FixedUpdate/LateUpdate or methods called from them
- **Fix:** Cache in `Awake()` or `Start()`: `private T _cached; void Awake() { _cached = GetComponent<T>(); }`

### 27. PERF-002: Find Methods in Hot Path
- **Severity:** CRITICAL
- **Source:** UnityEngineAnalyzer UEA0005, PVS-Studio V4005, ReSharper Unity
- **Description:** `GameObject.Find()`, `FindObjectOfType()`, `FindObjectsOfType()`, `FindWithTag()` iterate entire scene graph. Catastrophic in Update.
- **Detection Pattern:** Any `Find*` call inside Update-family methods, coroutines, or methods reachable from them
- **Fix:** Cache references in Awake/Start; use singleton pattern, dependency injection, or events

### 28. PERF-003: Camera.main in Loop
- **Severity:** HIGH
- **Source:** ReSharper Unity, PVS-Studio V4005
- **Description:** `Camera.main` calls `FindObjectWithTag("MainCamera")` internally every time. Not cached.
- **Detection Pattern:** `Camera.main` access inside Update-family methods or loops
- **Fix:** Cache: `private Camera _mainCam; void Start() { _mainCam = Camera.main; }`

### 29. PERF-004: String Concatenation in Update
- **Severity:** HIGH
- **Source:** PVS-Studio V4002, UnityEngineAnalyzer
- **Description:** String concatenation creates new string objects each time, generating garbage every frame. Especially bad in UI text updates.
- **Detection Pattern:** `string + string`, `$"{interpolation}"`, `string.Format` inside Update-family methods
- **Fix:** Use `StringBuilder` and `.Clear()` each frame, or cache and only update on change

### 30. PERF-005: Boxing in Hot Path
- **Severity:** HIGH
- **Source:** PVS-Studio V4001, Microsoft.Unity.Analyzers
- **Description:** Casting struct (int, float, Vector3, etc.) to interface or object allocates on heap. Hidden in string.Format, LINQ, Debug.Log.
- **Detection Pattern:** Struct cast to `object` or interface; `string.Format("{0}", structValue)`; `Debug.Log("pos: " + transform.position)`
- **Fix:** Use generic overloads; avoid casting structs to interfaces; use `$"{value}"` cautiously (still boxes in some cases)

### 31. PERF-006: LINQ in Update/Hot Path
- **Severity:** HIGH
- **Source:** Custom / PVS-Studio
- **Description:** LINQ methods (Where, Select, Any, etc.) allocate iterators, delegates, and intermediate collections every call. Terrible for per-frame code.
- **Detection Pattern:** Any `System.Linq` method call inside Update-family or frequently-called methods
- **Fix:** Use manual for loops; or ZLinq for zero-allocation LINQ

### 32. PERF-007: foreach on Non-Struct Enumerator
- **Severity:** MEDIUM
- **Source:** UnityEngineAnalyzer UEA0007, PVS-Studio
- **Description:** `foreach` on some collections (Dictionary, custom IEnumerable) allocates enumerator on heap. List<T> and array foreach are safe (struct enumerator).
- **Detection Pattern:** `foreach` on Dictionary, Hashtable, or custom IEnumerable in Update-family methods
- **Fix:** Use `for` loop with indexer where possible; or manually call `GetEnumerator()` on struct enumerators

### 33. PERF-008: Allocating Arrays from Unity API Properties
- **Severity:** HIGH
- **Source:** PVS-Studio V4004, Microsoft.Unity.Analyzers UNT0026
- **Description:** Properties like `Mesh.vertices`, `Mesh.normals`, `Physics.RaycastAll`, `Input.touches` create NEW arrays every access.
- **Detection Pattern:** Accessing `.vertices`, `.normals`, `.triangles`, `.colors`, `.uv`, `Input.touches` in loop or Update; `Renderer.materials` vs `Renderer.sharedMaterials`
- **Fix:** Cache the array: `var verts = mesh.vertices;` before loop; use non-allocating APIs like `Physics.RaycastNonAlloc`

### 34. PERF-009: Non-Allocating Physics API Not Used
- **Severity:** HIGH
- **Source:** Microsoft.Unity.Analyzers UNT0028
- **Description:** `Physics.RaycastAll`, `Physics.OverlapSphere`, etc. allocate new arrays. Non-allocating versions exist.
- **Detection Pattern:** `Physics.RaycastAll()`, `Physics.OverlapSphere()`, `Physics.OverlapBox()`, `Physics.SphereCastAll()`
- **Fix:** Use `Physics.RaycastNonAlloc()`, `Physics.OverlapSphereNonAlloc()`, etc. with pre-allocated buffer

### 35. PERF-010: SendMessage / BroadcastMessage
- **Severity:** HIGH
- **Source:** ReSharper Unity, UnityEngineAnalyzer
- **Description:** Uses reflection to find methods by string name. ~1000x slower than direct calls. Also breaks refactoring.
- **Detection Pattern:** `SendMessage("MethodName")`, `BroadcastMessage("MethodName")`, `SendMessageUpwards("MethodName")`
- **Fix:** Use direct method calls, events, interfaces, or UnityEvents

### 36. PERF-011: String-Based Invoke/InvokeRepeating
- **Severity:** MEDIUM
- **Source:** ReSharper Unity
- **Description:** `Invoke("MethodName", delay)` uses reflection. Slower and breaks with refactoring.
- **Detection Pattern:** `Invoke("string")`, `InvokeRepeating("string", ...)`
- **Fix:** Use coroutines: `StartCoroutine(DelayedCall())` or `Awaitable.WaitForSecondsAsync()`

### 37. PERF-012: Instantiate Without Parent (Extra Transform)
- **Severity:** MEDIUM
- **Source:** Custom
- **Description:** `Instantiate(prefab)` then `SetParent(parent)` causes double transform calculation. Use overload with parent.
- **Detection Pattern:** `Instantiate(prefab)` followed by `.SetParent()` or `.transform.parent =`
- **Fix:** `Instantiate(prefab, parent)` or `Instantiate(prefab, position, rotation, parent)`

### 38. PERF-013: SetPosition and SetRotation Separately
- **Severity:** MEDIUM
- **Source:** Microsoft.Unity.Analyzers UNT0022, UNT0032, UNT0036
- **Description:** Setting `transform.position` and `transform.rotation` separately triggers two hierarchy updates. Combined API is faster.
- **Detection Pattern:** Sequential `transform.position = x; transform.rotation = y;` on same transform
- **Fix:** Use `transform.SetPositionAndRotation(pos, rot)` or `transform.SetLocalPositionAndRotation(pos, rot)`

### 39. PERF-014: Scalar Before Vector Math
- **Severity:** LOW
- **Source:** Microsoft.Unity.Analyzers UNT0024, PVS-Studio V4006
- **Description:** `vector * scalar * scalar` does 2 vector multiplications. `scalar * scalar * vector` does 1 float mult + 1 vector mult.
- **Detection Pattern:** `Vector3 * float * float` where scalar operations could be grouped first
- **Fix:** Reorder: `float * float * Vector3` to minimize vector operations

### 40. PERF-015: SetPixels Instead of SetPixels32
- **Severity:** MEDIUM
- **Source:** Microsoft.Unity.Analyzers UNT0017
- **Description:** `Texture2D.SetPixels()` is significantly slower than `SetPixels32()` which works with Color32 (byte-based).
- **Detection Pattern:** `texture.SetPixels(...)` call
- **Fix:** Use `texture.SetPixels32(...)` with `Color32[]`

### 41. PERF-016: Reflection in Update
- **Severity:** HIGH
- **Source:** Microsoft.Unity.Analyzers UNT0018, PVS-Studio
- **Description:** `System.Reflection` calls (GetType, GetMethod, GetField, etc.) are expensive and should never be in hot paths.
- **Detection Pattern:** Any `System.Reflection` usage in Update-family methods
- **Fix:** Cache reflection results in Awake/Start or use compile-time alternatives

### 42. PERF-017: Debug.Log in Production/Hot Path
- **Severity:** MEDIUM
- **Source:** ReSharper Unity
- **Description:** `Debug.Log` is expensive even in release builds (string formatting, stack trace capture). Generates garbage.
- **Detection Pattern:** `Debug.Log*` calls inside Update-family methods or hot loops
- **Fix:** Use `[Conditional("UNITY_EDITOR")]` wrapper or #if preprocessor directives

### 43. PERF-018: Empty Unity Messages (Awake/Start/Update)
- **Severity:** LOW
- **Source:** Microsoft.Unity.Analyzers UNT0001
- **Description:** Unity calls magic methods (Update, Awake, Start, etc.) via reflection even if empty. Each has overhead.
- **Detection Pattern:** Empty method body for any Unity message (Update, Start, Awake, OnEnable, etc.)
- **Fix:** Remove empty Unity message methods entirely

### 44. PERF-019: Tag Comparison with == Instead of CompareTag
- **Severity:** MEDIUM
- **Source:** Microsoft.Unity.Analyzers UNT0002
- **Description:** `gameObject.tag == "Player"` allocates a new string. `CompareTag` does not.
- **Detection Pattern:** `gameObject.tag == "string"` or `other.tag == "string"`
- **Fix:** `gameObject.CompareTag("Player")`

### 45. PERF-020: Unnecessary gameObject.gameObject
- **Severity:** LOW
- **Source:** Microsoft.Unity.Analyzers UNT0019
- **Description:** `gameObject.gameObject` is redundant indirection that returns same reference.
- **Detection Pattern:** `gameObject.gameObject` chain
- **Fix:** Remove redundant `.gameObject`

### 46. PERF-021: Closure Allocation in Hot Path
- **Severity:** HIGH
- **Source:** PVS-Studio V4003
- **Description:** Lambda/delegate capturing local variables allocates closure object each time. In Update, this means per-frame allocation.
- **Detection Pattern:** Lambda or delegate expression capturing local variable inside Update-family method
- **Fix:** Use static lambda, cached delegate, or manual state passing

### 47. PERF-022: Coroutine Yielding New WaitForSeconds
- **Severity:** MEDIUM
- **Source:** Custom
- **Description:** `yield return new WaitForSeconds(1f)` allocates every iteration. Cache the wait object.
- **Detection Pattern:** `yield return new WaitForSeconds(...)` or `new WaitForEndOfFrame()` inside loop
- **Fix:** `private static readonly WaitForSeconds _wait = new(1f);` then `yield return _wait;`

### 48. PERF-023: Excessive Object Pooling Missed
- **Severity:** MEDIUM
- **Source:** Custom
- **Description:** Frequent Instantiate/Destroy cycles (bullets, effects, enemies) cause GC spikes.
- **Detection Pattern:** `Instantiate()` called frequently (inside coroutine loop or Update) paired with `Destroy()` on same prefab type
- **Fix:** Use object pooling (UnityEngine.Pool.ObjectPool or custom pool)

### 49. PERF-024: Deep Hierarchy SetActive Cascade
- **Severity:** MEDIUM
- **Source:** Custom
- **Description:** `SetActive(true/false)` on deep hierarchy triggers OnEnable/OnDisable on all children. Very expensive.
- **Detection Pattern:** `SetActive()` called frequently on root of deep hierarchy
- **Fix:** Use CanvasGroup.alpha for UI; disable components instead of GameObjects; flatten hierarchies

### 50. PERF-025: Non-Generic GetComponent
- **Severity:** LOW
- **Source:** Microsoft.Unity.Analyzers UNT0003
- **Description:** `GetComponent(typeof(T))` is slower than `GetComponent<T>()` and requires casting.
- **Detection Pattern:** `GetComponent(typeof(T))` instead of `GetComponent<T>()`
- **Fix:** Use generic version: `GetComponent<T>()`

---

## CATEGORY 3: SECURITY (Rules 51-65)

### 51. SEC-001: Path Traversal in File Operations
- **Severity:** CRITICAL
- **Source:** Roslyn CA3003, Semgrep, SonarQube
- **Description:** Concatenating user input into file paths allows `../../` traversal outside intended directory. Critical for our generated C# which writes files to Unity project.
- **Detection Pattern:** `Path.Combine(basePath, userInput)` without canonicalization; string interpolation in file paths `$"{dir}/{name}"`
- **Fix:** `Path.GetFullPath()` then validate starts with expected base path; reject `..` sequences

### 52. SEC-002: Unsafe Deserialization
- **Severity:** CRITICAL
- **Source:** Roslyn CA2300-CA2302, SonarQube, OWASP
- **Description:** `BinaryFormatter.Deserialize()`, `JsonConvert.DeserializeObject<T>()` with TypeNameHandling, or `XmlSerializer` on untrusted data can execute arbitrary code.
- **Detection Pattern:** `BinaryFormatter`, `SoapFormatter`, `NetDataContractSerializer` usage; `JsonConvert.DeserializeObject` with `TypeNameHandling.All/Auto/Objects`
- **Fix:** Use `JsonUtility.FromJson<T>()` (Unity) or `System.Text.Json` with safe settings; never use `BinaryFormatter`

### 53. SEC-003: SQL Injection (if using SQLite/DB)
- **Severity:** CRITICAL
- **Source:** Roslyn CA, Semgrep, SonarQube S2077
- **Description:** String concatenation in SQL queries allows injection. Relevant if using SQLite for save data.
- **Detection Pattern:** `$"SELECT * FROM table WHERE name = '{input}'"` or `"SELECT" + variable`
- **Fix:** Use parameterized queries: `cmd.Parameters.AddWithValue("@name", input)`

### 54. SEC-004: Hardcoded Credentials/API Keys
- **Severity:** CRITICAL
- **Source:** Semgrep, Bandit B105-B107, SonarQube S6418
- **Description:** API keys, passwords, tokens embedded directly in source code. Our Python server uses API keys for fal.ai, Tripo3D, ElevenLabs.
- **Detection Pattern:** `password = "..."`, `api_key = "..."`, `token = "..."` in string literals; any variable named `key`, `secret`, `token`, `password` with string literal value
- **Fix:** Use environment variables: `os.environ.get("API_KEY")` or `.env` file (excluded from git)

### 55. SEC-005: Command Injection
- **Severity:** CRITICAL
- **Source:** Roslyn CA, Semgrep, Bandit B602-B605
- **Description:** Passing unsanitized input to `Process.Start()`, `System.Diagnostics.Process`, or `subprocess` in Python.
- **Detection Pattern:** `Process.Start(userInput)`, `subprocess.call(f"command {input}")`, shell=True with variable args
- **Fix:** Use allowlist of commands; sanitize/validate all inputs; avoid shell=True

### 56. SEC-006: Insecure Random for Security
- **Severity:** MEDIUM
- **Source:** Roslyn CA5394, Bandit B311, SonarQube S2245
- **Description:** `System.Random` and `random.random()` (Python) are predictable. Not suitable for tokens, keys, salts.
- **Detection Pattern:** `new Random()` used for token/key generation; `random.randint()` for secrets
- **Fix:** Use `System.Security.Cryptography.RandomNumberGenerator` (C#) or `secrets` module (Python)

### 57. SEC-007: Insecure HTTP (No TLS)
- **Severity:** MEDIUM
- **Source:** Semgrep, Bandit B309
- **Description:** Using `http://` instead of `https://` for API calls. Our tools make API calls to fal.ai, Tripo3D, ElevenLabs.
- **Detection Pattern:** `http://` in URL strings (not localhost/127.0.0.1)
- **Fix:** Use `https://` for all external API calls

### 58. SEC-008: XML External Entity (XXE) Processing
- **Severity:** HIGH
- **Source:** Roslyn CA3075, SonarQube
- **Description:** `XmlDocument` or `XmlReader` with default settings can process external entities, allowing file disclosure.
- **Detection Pattern:** `new XmlDocument()` without setting `XmlResolver = null`; `XmlReaderSettings` without `DtdProcessing = DtdProcessing.Prohibit`
- **Fix:** Set `XmlResolver = null` and `DtdProcessing = DtdProcessing.Prohibit`

### 59. SEC-009: Regex Denial of Service (ReDoS)
- **Severity:** MEDIUM
- **Source:** SonarQube S2631, Semgrep
- **Description:** Regex with nested quantifiers `(a+)+` can cause catastrophic backtracking on malicious input.
- **Detection Pattern:** Regex patterns with nested quantifiers, overlapping alternation, or unbounded repetition
- **Fix:** Use `Regex` with `RegexOptions.NonBacktracking` (.NET 7+) or timeout; simplify patterns

### 60. SEC-010: Logging Sensitive Data
- **Severity:** MEDIUM
- **Source:** Custom, SonarQube S5042
- **Description:** Logging API keys, tokens, passwords, or user credentials to console/file.
- **Detection Pattern:** `Debug.Log(apiKey)`, `print(f"token: {token}")`, logging variables named password/key/secret/token
- **Fix:** Redact sensitive values in logs: `Debug.Log($"API call with key: {key[..4]}***")`

### 61. SEC-011: Unsafe YAML Loading (Python)
- **Severity:** HIGH
- **Source:** Bandit B506, Semgrep
- **Description:** `yaml.load(data)` without SafeLoader can execute arbitrary Python code.
- **Detection Pattern:** `yaml.load(data)` or `yaml.load(data, Loader=yaml.FullLoader)`
- **Fix:** `yaml.safe_load(data)` or `yaml.load(data, Loader=yaml.SafeLoader)`

### 62. SEC-012: Pickle Deserialization (Python)
- **Severity:** HIGH
- **Source:** Bandit B301, Semgrep
- **Description:** `pickle.loads()` on untrusted data can execute arbitrary code.
- **Detection Pattern:** `pickle.load()`, `pickle.loads()` on data from network/file
- **Fix:** Use JSON serialization; if pickle required, validate source authenticity

### 63. SEC-013: eval/exec Usage (Python)
- **Severity:** CRITICAL
- **Source:** Bandit B307, Ruff S307
- **Description:** `eval()` and `exec()` execute arbitrary code strings. Our blender_execute tool specifically blocks these.
- **Detection Pattern:** `eval(...)`, `exec(...)` calls
- **Fix:** Use `ast.literal_eval()` for data parsing; avoid entirely for code execution

### 64. SEC-014: Temporary File Race Condition (Python)
- **Severity:** MEDIUM
- **Source:** Bandit B108, B605
- **Description:** Using `tempfile.mktemp()` (deprecated) creates TOCTOU race condition.
- **Detection Pattern:** `tempfile.mktemp()` usage
- **Fix:** Use `tempfile.mkstemp()` or `tempfile.NamedTemporaryFile()`

### 65. SEC-015: Assert Used for Validation
- **Severity:** MEDIUM
- **Source:** Bandit B101, Ruff S101
- **Description:** `assert` statements are stripped in optimized Python bytecode (-O flag). Using them for input validation is unsafe.
- **Detection Pattern:** `assert user_input`, `assert len(data) > 0` for validation logic
- **Fix:** Use `if not condition: raise ValueError("...")` for validation

---

## CATEGORY 4: UNITY-SPECIFIC (Rules 66-85)

### 66. UNITY-001: Physics Code in Update Instead of FixedUpdate
- **Severity:** HIGH
- **Source:** Microsoft.Unity.Analyzers UNT0004, Custom
- **Description:** Rigidbody manipulation (AddForce, velocity, MovePosition) in Update causes frame-rate-dependent physics. Also: using `Time.fixedDeltaTime` in Update or `Time.deltaTime` in FixedUpdate.
- **Detection Pattern:** `rigidbody.AddForce()`, `rigidbody.velocity =`, `rigidbody.MovePosition()` inside Update/LateUpdate; `Time.fixedDeltaTime` in Update
- **Fix:** Move physics code to FixedUpdate; use `Time.deltaTime` (Unity auto-returns fixedDeltaTime inside FixedUpdate)

### 67. UNITY-002: Destroy on Transform
- **Severity:** HIGH
- **Source:** Microsoft.Unity.Analyzers UNT0030
- **Description:** `Destroy(transform)` or `DestroyImmediate(transform)` destroys the Transform component, which destroys the entire GameObject. Likely unintended.
- **Detection Pattern:** `Destroy(*.transform)` or `DestroyImmediate(*.transform)`
- **Fix:** Use `Destroy(gameObject)` if intended; or `Destroy(GetComponent<T>())` for specific component

### 68. UNITY-003: Unused Coroutine Return Value
- **Severity:** HIGH
- **Source:** Microsoft.Unity.Analyzers UNT0012
- **Description:** Calling coroutine method without `StartCoroutine()` just creates the IEnumerator but never runs it.
- **Detection Pattern:** `MyCoroutine();` without `StartCoroutine(MyCoroutine())`
- **Fix:** `StartCoroutine(MyCoroutine());`

### 69. UNITY-004: ScriptableObject/MonoBehaviour Created with new
- **Severity:** CRITICAL
- **Source:** Microsoft.Unity.Analyzers UNT0010, UNT0011
- **Description:** `new MonoBehaviour()` or `new ScriptableObject()` bypasses Unity's creation pipeline. Object won't be properly initialized.
- **Detection Pattern:** `new MonoBehaviourSubclass()`, `new ScriptableObject()`
- **Fix:** Use `gameObject.AddComponent<T>()` for MonoBehaviour; `ScriptableObject.CreateInstance<T>()` for ScriptableObject

### 70. UNITY-005: Incorrect Unity Message Signature
- **Severity:** HIGH
- **Source:** Microsoft.Unity.Analyzers UNT0006
- **Description:** Unity messages (Update, OnCollisionEnter, etc.) must have exact signatures. Wrong parameter types or return types cause silent failures.
- **Detection Pattern:** Method named like Unity message but with wrong parameter types (e.g., `OnCollisionEnter(Collider c)` instead of `OnCollisionEnter(Collision c)`)
- **Fix:** Match exact Unity message signatures from documentation

### 71. UNITY-006: Incorrect Unity Message Case
- **Severity:** HIGH
- **Source:** Microsoft.Unity.Analyzers UNT0033
- **Description:** Unity messages are case-sensitive. `update()` or `Oncolliderienter()` silently does nothing.
- **Detection Pattern:** Method name similar to but not exactly matching Unity message name
- **Fix:** Use exact casing: `Update`, `OnCollisionEnter`, `Awake`, etc.

### 72. UNITY-007: SerializeField on Invalid Type
- **Severity:** MEDIUM
- **Source:** Microsoft.Unity.Analyzers UNT0013
- **Description:** `[SerializeField]` on static, const, readonly, property, or non-serializable type has no effect.
- **Detection Pattern:** `[SerializeField]` on static/const/readonly fields, properties, or dictionary/custom class without [Serializable]
- **Fix:** Remove attribute or fix field type; ensure custom classes have `[Serializable]`

### 73. UNITY-008: Missing [InitializeOnLoad] Static Constructor
- **Severity:** MEDIUM
- **Source:** Microsoft.Unity.Analyzers UNT0009
- **Description:** `[InitializeOnLoad]` requires a static constructor to work. Without it, the attribute does nothing.
- **Detection Pattern:** Class with `[InitializeOnLoad]` attribute but no `static ClassName() { }` constructor
- **Fix:** Add static constructor

### 74. UNITY-009: MenuItem on Non-Static Method
- **Severity:** MEDIUM
- **Source:** Microsoft.Unity.Analyzers UNT0020
- **Description:** `[MenuItem]` attribute only works on static methods. On instance methods, the menu item won't appear.
- **Detection Pattern:** `[MenuItem("...")]` on non-static method
- **Fix:** Make method static

### 75. UNITY-010: Coroutine Leak on Disabled/Destroyed Object
- **Severity:** HIGH
- **Source:** Custom
- **Description:** Coroutines stop when the MonoBehaviour is disabled or the GameObject is destroyed, but resources they manage (event subscriptions, file handles) are not cleaned up.
- **Detection Pattern:** Coroutine that subscribes to events or opens resources without corresponding cleanup in OnDisable/OnDestroy
- **Fix:** Track coroutines and cleanup in OnDisable; use try/finally in coroutines; StopAllCoroutines in OnDisable

### 76. UNITY-011: Event Subscription Without Unsubscription
- **Severity:** HIGH
- **Source:** Custom / SonarQube
- **Description:** Subscribing to events in OnEnable without unsubscribing in OnDisable causes memory leaks and ghost callbacks.
- **Detection Pattern:** `event += handler` in OnEnable/Awake/Start without corresponding `event -= handler` in OnDisable/OnDestroy
- **Fix:** Always pair subscribe/unsubscribe: OnEnable/OnDisable or Start/OnDestroy

### 77. UNITY-012: DontDestroyOnLoad Duplicate
- **Severity:** MEDIUM
- **Source:** Custom
- **Description:** `DontDestroyOnLoad(gameObject)` without singleton check creates duplicates when scene reloads.
- **Detection Pattern:** `DontDestroyOnLoad()` without preceding instance check/destroy pattern
- **Fix:** Implement singleton pattern with destroy-duplicate check

### 78. UNITY-013: RequireComponent Missing
- **Severity:** LOW
- **Source:** Custom
- **Description:** Script uses `GetComponent<T>()` in Awake/Start but doesn't have `[RequireComponent(typeof(T))]`, allowing missing component at runtime.
- **Detection Pattern:** `GetComponent<T>()` in Awake/Start without `[RequireComponent(typeof(T))]` on class
- **Fix:** Add `[RequireComponent(typeof(T))]` attribute to class

### 79. UNITY-014: Animator String Parameter (Non-Hashed)
- **Severity:** MEDIUM
- **Source:** Custom / ReSharper Unity
- **Description:** `animator.SetFloat("Speed", 1f)` looks up parameter by string every call. Hashing is much faster.
- **Detection Pattern:** `animator.SetFloat("string")`, `animator.SetBool("string")`, `animator.SetTrigger("string")`, `animator.SetInteger("string")`
- **Fix:** Cache hash: `private static readonly int SpeedHash = Animator.StringToHash("Speed"); animator.SetFloat(SpeedHash, 1f);`

### 80. UNITY-015: Material Property Without PropertyToID
- **Severity:** MEDIUM
- **Source:** Custom / ReSharper Unity
- **Description:** `material.SetFloat("_Metallic", 1f)` uses string lookup. `Shader.PropertyToID` caches faster int lookup.
- **Detection Pattern:** `material.SetFloat("string")`, `material.SetColor("string")`, `material.SetTexture("string")`
- **Fix:** `private static readonly int MetallicID = Shader.PropertyToID("_Metallic"); material.SetFloat(MetallicID, 1f);`

### 81. UNITY-016: Resources.Load in Hot Path
- **Severity:** HIGH
- **Source:** Custom
- **Description:** `Resources.Load()` is synchronous disk I/O. In Update or frequently-called methods, causes frame hitches.
- **Detection Pattern:** `Resources.Load()` inside Update-family methods or frequently-called paths
- **Fix:** Load in Awake/Start and cache; or use Addressables for async loading

### 82. UNITY-017: Incorrect Layer Mask Usage
- **Severity:** MEDIUM
- **Source:** Custom
- **Description:** Using layer index directly instead of bit-shifted mask in Physics calls: `Physics.Raycast(ray, mask: 8)` checks layer 8 only if bit 3 is set (8 = 0b1000), not layer 8.
- **Detection Pattern:** Raw integer in layerMask parameter without `1 << layerNumber` or `LayerMask.GetMask()`
- **Fix:** `LayerMask.GetMask("LayerName")` or `1 << layerNumber`

### 83. UNITY-018: Additive Scene Loading Without Unloading
- **Severity:** MEDIUM
- **Source:** Custom
- **Description:** `SceneManager.LoadSceneAsync(name, LoadSceneMode.Additive)` without corresponding unload causes memory growth.
- **Detection Pattern:** `LoadSceneMode.Additive` usage without corresponding `UnloadSceneAsync` in lifecycle
- **Fix:** Track loaded scenes and unload when no longer needed

### 84. UNITY-019: OnGUI Used for Runtime UI
- **Severity:** HIGH
- **Source:** Custom
- **Description:** `OnGUI()` is called multiple times per frame, generates massive garbage, and is meant for editor tools only. Runtime UI should use UI Toolkit or UGUI.
- **Detection Pattern:** `OnGUI()` method in non-Editor scripts (scripts not in Editor/ folder)
- **Fix:** Use UI Toolkit (UIDocument) or UGUI (Canvas) for runtime UI

### 85. UNITY-020: Editor-Only Code in Runtime Script
- **Severity:** HIGH
- **Source:** Custom
- **Description:** `UnityEditor` namespace usage in runtime scripts causes build failures. Must be wrapped in `#if UNITY_EDITOR`.
- **Detection Pattern:** `using UnityEditor;` or `UnityEditor.*` usage in scripts outside Editor/ folder without `#if UNITY_EDITOR` preprocessor guard
- **Fix:** Wrap in `#if UNITY_EDITOR ... #endif` or move to Editor/ folder

---

## CATEGORY 5: CODE QUALITY (Rules 86-100)

### 86. QUALITY-001: Dead Code / Unused Private Method
- **Severity:** LOW
- **Source:** Roslyn IDE0051, SonarQube S1144, Ruff F841
- **Description:** Private methods/variables never called/used. NOTE: In Unity, methods like Update/Start are called via reflection and are NOT dead code.
- **Detection Pattern:** Private method/field with no references (excluding Unity messages)
- **Fix:** Remove unused code (but verify against Unity message list first)
- **Unity Caveat:** SonarQube false-positives on Unity magic methods (Awake, Start, Update, OnEnable, etc.)

### 87. QUALITY-002: Overly Complex Method (Cyclomatic Complexity)
- **Severity:** MEDIUM
- **Source:** SonarQube S3776, Ruff C901
- **Description:** Methods with cyclomatic complexity > 15 are hard to understand, test, and maintain.
- **Detection Pattern:** Method with > 15 branches (if/else/switch/for/while/&&/||)
- **Fix:** Extract sub-methods; use strategy pattern; reduce nesting

### 88. QUALITY-003: God Class (Too Many Responsibilities)
- **Severity:** MEDIUM
- **Source:** SonarQube S1200, Custom
- **Description:** Class with > 500 lines or > 20 methods doing too many things. Common in Unity MonoBehaviours.
- **Detection Pattern:** Class LOC > 500, method count > 20, or field count > 15
- **Fix:** Split into focused components; use composition over inheritance

### 89. QUALITY-004: Magic Numbers
- **Severity:** LOW
- **Source:** SonarQube S109, Ruff
- **Description:** Numeric literals in code without explanation: `if (health > 100)`, `transform.position += Vector3.up * 0.05f`
- **Detection Pattern:** Numeric literal (other than 0, 1, -1) in comparison or calculation without const/readonly field
- **Fix:** Extract to named constant: `private const float HoverSpeed = 0.05f;`

### 90. QUALITY-005: Deeply Nested Code (> 3 levels)
- **Severity:** MEDIUM
- **Source:** SonarQube S3776, Custom
- **Description:** Code nested > 3 levels deep is hard to read and indicates complex logic needing refactoring.
- **Detection Pattern:** Indentation level > 3 (if inside if inside for inside if)
- **Fix:** Use early returns, guard clauses, extract methods

### 91. QUALITY-006: Long Parameter List (> 5 params)
- **Severity:** LOW
- **Source:** SonarQube S107, Custom
- **Description:** Methods with many parameters are hard to call correctly and indicate need for data object.
- **Detection Pattern:** Method with > 5 parameters
- **Fix:** Create parameter object/struct; use builder pattern

### 92. QUALITY-007: Duplicate Code Blocks
- **Severity:** MEDIUM
- **Source:** SonarQube S1192, Custom
- **Description:** Same code block (> 5 lines) appears multiple times. Bug fixes must be applied in all locations.
- **Detection Pattern:** Code blocks with > 80% textual similarity appearing 2+ times
- **Fix:** Extract to shared method

### 93. QUALITY-008: TODO/FIXME/HACK Comments Left in Code
- **Severity:** LOW
- **Source:** SonarQube S1135, Custom
- **Description:** Technical debt markers left in code. Acceptable during development but should be tracked.
- **Detection Pattern:** `// TODO`, `// FIXME`, `// HACK`, `// XXX`, `# TODO` comments
- **Fix:** Create issue/ticket and either fix or document the debt

### 94. QUALITY-009: Inconsistent Naming Convention
- **Severity:** LOW
- **Source:** Roslyn IDE1006, Ruff N801-N818
- **Description:** C#: fields should be _camelCase, properties PascalCase, methods PascalCase. Python: snake_case functions, PascalCase classes.
- **Detection Pattern:** Public field not PascalCase; private field not _prefixed; Python function not snake_case
- **Fix:** Follow language conventions; use .editorconfig for enforcement

### 95. QUALITY-010: Missing XML Documentation on Public API
- **Severity:** LOW
- **Source:** Roslyn CS1591, Custom
- **Description:** Public methods/classes without XML documentation. Important for our MCP tool API surface.
- **Detection Pattern:** Public method/class/property without `///` summary comment
- **Fix:** Add `/// <summary>` documentation

### 96. QUALITY-011: Method Too Long (> 50 lines)
- **Severity:** MEDIUM
- **Source:** SonarQube, Custom
- **Description:** Methods over 50 lines are hard to understand and test. Common in Unity initialization code.
- **Detection Pattern:** Method body > 50 lines (excluding blank lines and comments)
- **Fix:** Extract logical sections into named helper methods

### 97. QUALITY-012: Unused Import/Using Statement
- **Severity:** LOW
- **Source:** Roslyn IDE0005, Ruff F401
- **Description:** Unused `using` directives (C#) or `import` statements (Python) add clutter.
- **Detection Pattern:** `using Namespace;` where no type from that namespace is referenced
- **Fix:** Remove unused usings; organize imports

### 98. QUALITY-013: Mutable Default Argument (Python)
- **Severity:** HIGH
- **Source:** Ruff B006, Pylint W0102
- **Description:** `def func(items=[])` shares the default list across all calls. Classic Python gotcha.
- **Detection Pattern:** Function parameter with default value of `[]`, `{}`, `set()`, or any mutable type
- **Fix:** `def func(items=None): items = items or []`

### 99. QUALITY-014: Bare Except (Python)
- **Severity:** HIGH
- **Source:** Ruff E722, Bandit B001
- **Description:** `except:` catches everything including KeyboardInterrupt and SystemExit. Use specific exceptions.
- **Detection Pattern:** `except:` without exception type
- **Fix:** `except Exception as e:` at minimum; prefer specific types

### 100. QUALITY-015: Return Type Inconsistency (Python)
- **Severity:** MEDIUM
- **Source:** mypy, Ruff
- **Description:** Function returns different types on different paths (e.g., sometimes dict, sometimes None, sometimes string).
- **Detection Pattern:** Function with return statements yielding different types; missing return type annotation
- **Fix:** Add type annotations; use `Optional[T]` for nullable returns; be consistent

---

## TOOL RECOMMENDATIONS FOR OUR STACK

### For Generated C# (Unity Editor Scripts)
| Tool | Purpose | Integration |
|------|---------|-------------|
| Microsoft.Unity.Analyzers | Unity-specific bugs (UNT0001-0036) | Include as DLL in Unity project |
| Roslyn .NET Analyzers | General C# quality (CAxxxx) | Built into .NET SDK |
| Custom Semgrep rules | Pattern-match our generated code | CLI / CI |
| PVS-Studio (if budget) | Deepest Unity analysis (V4001-V4006) | IDE plugin |

### For Python Server Code
| Tool | Purpose | Integration |
|------|---------|-------------|
| Ruff | Linting + formatting (replaces flake8/black/isort) | Pre-commit / CI |
| mypy (strict) | Type checking | Pre-commit / CI |
| Bandit | Security scanning | CI |
| Semgrep | Custom security/quality rules | CI |

### Recommended Ruff Configuration
```toml
[tool.ruff]
select = ["E", "F", "W", "B", "I", "N", "S", "UP", "SIM", "C901", "RUF"]
line-length = 120

[tool.ruff.per-file-ignores]
"tests/**" = ["S101"]  # Allow assert in tests
```

### Recommended mypy Configuration
```toml
[tool.mypy]
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

---

## PRIORITY MATRIX

### P0 -- Ship-Blocking (fix immediately)
Rules: 1, 3, 4, 5, 7, 26, 27, 51, 52, 54, 55, 63, 66, 69, 70, 85

### P1 -- High Impact (fix before release)
Rules: 2, 6, 8, 10, 13, 17, 19, 20, 21, 22, 28, 29, 30, 31, 33, 34, 35, 36, 37, 41, 42, 46, 53, 56, 58, 61, 62, 67, 68, 71, 75, 76, 77, 81, 84, 98, 99

### P2 -- Medium Impact (quality improvement)
Rules: 9, 11, 12, 14, 15, 16, 18, 23, 25, 32, 38, 39, 40, 43, 44, 47, 48, 49, 57, 59, 60, 64, 65, 72, 73, 74, 79, 80, 82, 83, 86, 87, 88, 90, 91, 92, 96, 97, 100

### P3 -- Low Impact (nice to have)
Rules: 24, 45, 50, 78, 89, 93, 94, 95

---

## IMPLEMENTATION PLAN FOR VB-TOOLKIT

### Phase 1: Python Server Hardening
1. Add `ruff` to `pyproject.toml` dev dependencies with rules above
2. Add `mypy` strict mode checking
3. Run `bandit` on all Python source
4. Write 5 custom Semgrep rules for our specific patterns (path construction, API key handling)

### Phase 2: Generated C# Validation
1. Build AST-level checks in Python BEFORE writing C# to disk
2. Check for: UNT0007/0008 (null coalescing on Unity objects), UNT0010/0011 (new MonoBehaviour), path traversal
3. Add template-level linting: validate generated code patterns at template time
4. Consider shipping Microsoft.Unity.Analyzers DLL with the toolkit

### Phase 3: Custom Semgrep Rules for Generated Code
Priority custom rules to write:
- `vb-csharp-null-coalescing-unity-object` (UNT0007/0008 equivalent)
- `vb-csharp-getcomponent-in-update` (PERF-001)
- `vb-csharp-find-in-update` (PERF-002)
- `vb-csharp-physics-in-update` (UNITY-001)
- `vb-csharp-path-traversal` (SEC-001)
- `vb-csharp-editor-code-in-runtime` (UNITY-020)
- `vb-python-hardcoded-api-key` (SEC-004)
- `vb-python-unsafe-yaml` (SEC-011)

---

## SOURCES

- [Microsoft.Unity.Analyzers - GitHub](https://github.com/microsoft/Microsoft.Unity.Analyzers)
- [Microsoft.Unity.Analyzers Rule Index](https://github.com/microsoft/Microsoft.Unity.Analyzers/blob/main/doc/index.md)
- [UnityEngineAnalyzer - GitHub](https://github.com/vad710/UnityEngineAnalyzer)
- [Unity Roslyn Analyzers Manual](https://docs.unity3d.com/Manual/roslyn-analyzers.html)
- [PVS-Studio Unity Diagnostics](https://pvs-studio.com/en/blog/posts/csharp/1071/)
- [PVS-Studio GameDev Guardian](https://pvs-studio.com/en/blog/posts/csharp/1269/)
- [JetBrains ReSharper Unity - Performance Critical Context](https://github.com/JetBrains/resharper-unity/wiki/Performance-critical-context-and-costly-methods)
- [JetBrains Unity Performance Best Practices](https://blog.jetbrains.com/dotnet/2019/02/21/performance-indicators-unity-code-rider/)
- [SonarQube C# Rules](https://rules.sonarsource.com/csharp/)
- [SonarSource sonar-dotnet - GitHub](https://github.com/SonarSource/sonar-dotnet)
- [Semgrep C# Documentation](https://semgrep.dev/docs/languages/csharp)
- [Semgrep Rules Repository - GitHub](https://github.com/semgrep/semgrep-rules)
- [Semgrep .NET Security Rules - GitHub](https://github.com/tuannq2299/semgrep-rules)
- [Ruff Linter Documentation](https://docs.astral.sh/ruff/linter/)
- [Ruff Rules Reference](https://docs.astral.sh/ruff/rules/)
- [Ruff - GitHub](https://github.com/astral-sh/ruff)
- [Bandit Python Security Scanner - GitHub](https://github.com/PyCQA/bandit)
- [mypy Documentation](https://mypy.readthedocs.io/en/stable/)
- [.NET Roslyn Analyzers - GitHub](https://github.com/dotnet/roslyn-analyzers)
- [Unity GC Best Practices Manual](https://docs.unity3d.com/2022.2/Documentation/Manual/performance-garbage-collection-best-practices.html)
- [Zero Allocation C# in Unity - Seba's Lab](https://www.sebaslab.com/zero-allocation-code-in-unity/)
- [Unity Performance Recommendations - Microsoft Mixed Reality](https://learn.microsoft.com/en-us/windows/mixed-reality/develop/unity/performance-recommendations-for-unity)
- [OWASP Secure Code Review Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secure_Code_Review_Cheat_Sheet.html)
- [OWASP Insecure Deserialization](https://owasp.org/www-community/vulnerabilities/Insecure_Deserialization)
- [CVE-2025-59489 Unity Arbitrary Code Execution](https://flatt.tech/research/posts/arbitrary-code-execution-in-unity-runtime/)
- [Roslyn CA3003 Path Injection - Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca3003)
- [Python Linter Comparison - Ruff vs Flake8 vs Pylint](https://pythonspeed.com/articles/pylint-flake8-ruff/)
- [Best Code Review Tools Python 2026](https://dev.to/rahulxsingh/best-code-review-tools-for-python-in-2026-linters-sast-and-ai-5pb)
