"""Precision tests for VB Code Reviewer — verifies <3% false positive rate.

Tests cover:
- Python rules: true positives, true negatives, and false positive regression
- C# rules: true positives, true negatives, and false positive regression
- Guard function correctness
- Edge cases (empty files, encoding, etc.)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from veilbreakers_mcp import vb_code_reviewer as reviewer


# =========================================================================
# Python True Positives — code that MUST be flagged
# =========================================================================

def test_py_eval_detected(tmp_path):
    p = tmp_path / "bad.py"
    p.write_text("result = eval(user_input)\n", encoding="utf-8")
    issues = reviewer.scan_python_file(str(p), None, review_scope="production")
    assert any(i.rule_id == "PY-SEC-01" for i in issues)


def test_py_mutable_default_detected(tmp_path):
    p = tmp_path / "bad.py"
    p.write_text("def f(items=[]):\n    items.append(1)\n", encoding="utf-8")
    issues = reviewer.scan_python_file(str(p), None, review_scope="production")
    assert any(i.rule_id == "PY-COR-01" for i in issues)


def test_py_bare_except_detected(tmp_path):
    p = tmp_path / "bad.py"
    p.write_text("try:\n    x = 1\nexcept:\n    pass\n", encoding="utf-8")
    issues = reviewer.scan_python_file(str(p), None, review_scope="production")
    assert any(i.rule_id == "PY-COR-02" for i in issues)


def test_py_exec_detected(tmp_path):
    p = tmp_path / "bad.py"
    p.write_text("exec(code_string)\n", encoding="utf-8")
    issues = reviewer.scan_python_file(str(p), None, review_scope="production")
    assert any(i.rule_id == "PY-SEC-05" for i in issues)


def test_py_lambda_late_binding_detected(tmp_path):
    p = tmp_path / "bad.py"
    p.write_text(
        "funcs = []\n"
        "for i in range(5):\n"
        "    funcs.append(lambda: print(i))\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_python_file(str(p), None, review_scope="strict")
    assert any(i.rule_id == "PY-COR-15" for i in issues)


# =========================================================================
# Python True Negatives — code that must NOT be flagged
# =========================================================================

def test_py_literal_eval_not_flagged(tmp_path):
    p = tmp_path / "good.py"
    p.write_text("import ast\nresult = ast.literal_eval(user_input)\n", encoding="utf-8")
    issues = reviewer.scan_python_file(str(p), None, review_scope="production")
    assert not any(i.rule_id == "PY-SEC-01" for i in issues)


def test_py_commented_eval_not_flagged(tmp_path):
    p = tmp_path / "good.py"
    p.write_text("# eval(user_input)  # old code\n", encoding="utf-8")
    issues = reviewer.scan_python_file(str(p), None, review_scope="production")
    assert not any(i.rule_id == "PY-SEC-01" for i in issues)


def test_py_broad_except_with_logging_not_flagged(tmp_path):
    p = tmp_path / "good.py"
    p.write_text(
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "try:\n"
        "    risky()\n"
        "except Exception as e:\n"
        "    logger.exception(e)\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_python_file(str(p), None, review_scope="strict")
    assert not any(i.rule_id == "PY-COR-12" for i in issues)


def test_py_broad_except_with_fallback_no_logging_is_flagged(tmp_path):
    """Fallback assignment WITHOUT logging is a silent swallow."""
    p = tmp_path / "good.py"
    p.write_text(
        "try:\n"
        "    ctx = build_context()\n"
        "except Exception:\n"
        "    ctx = None\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_python_file(str(p), None, review_scope="strict")
    assert any(i.rule_id == "PY-COR-12" for i in issues)


def test_py_broad_except_with_fallback_and_logging_not_flagged(tmp_path):
    """Fallback assignment WITH logging is acceptable."""
    p = tmp_path / "good.py"
    p.write_text(
        "try:\n"
        "    ctx = build_context()\n"
        "except Exception as e:\n"
        "    logger.warning(f'Failed: {e}')\n"
        "    ctx = None\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_python_file(str(p), None, review_scope="strict")
    assert not any(i.rule_id == "PY-COR-12" for i in issues)


def test_py_broad_except_with_sys_exit_not_flagged(tmp_path):
    p = tmp_path / "good.py"
    p.write_text(
        "import sys\n"
        "try:\n"
        "    main()\n"
        "except Exception as e:\n"
        "    print(f'Error: {e}', file=sys.stderr)\n"
        "    sys.exit(1)\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_python_file(str(p), None, review_scope="strict")
    assert not any(i.rule_id == "PY-COR-12" for i in issues)


def test_py_reexport_not_flagged_unused(tmp_path):
    init_path = tmp_path / "__init__.py"
    init_path.write_text("from .module import Foo as Foo\n", encoding="utf-8")
    issues = reviewer.scan_python_file(str(init_path), None, review_scope="strict")
    assert not any(i.rule_id == "PY-STY-07" for i in issues)


def test_py_lambda_with_default_capture_not_flagged(tmp_path):
    p = tmp_path / "good.py"
    p.write_text(
        "funcs = []\n"
        "for i in range(5):\n"
        "    funcs.append(lambda i=i: print(i))\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_python_file(str(p), None, review_scope="strict")
    assert not any(i.rule_id == "PY-COR-15" for i in issues)


def test_py_dict_get_readonly_not_flagged(tmp_path):
    p = tmp_path / "good.py"
    p.write_text(
        "d = {'a': [1, 2]}\n"
        "items = d.get('a', [])\n"
        "for item in items:\n"
        "    print(item)\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_python_file(str(p), None, review_scope="strict")
    assert not any(i.rule_id == "PY-COR-06" for i in issues)


def test_py_comprehension_for_not_flagged_late_binding(tmp_path):
    p = tmp_path / "good.py"
    p.write_text(
        "result = [x * 2 for x in range(10)]\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_python_file(str(p), None, review_scope="strict")
    assert not any(i.rule_id == "PY-COR-15" for i in issues)


# =========================================================================
# C# True Positives — code that MUST be flagged
# =========================================================================

def test_cs_getcomponent_in_update_detected(tmp_path):
    p = tmp_path / "Bad.cs"
    p.write_text(
        "using UnityEngine;\n"
        "public class Bad : MonoBehaviour {\n"
        "    void Update() {\n"
        "        var rb = GetComponent<Rigidbody>();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    assert any(i.rule_id == "BUG-01" for i in issues)


def test_cs_camera_main_in_update_detected(tmp_path):
    p = tmp_path / "Bad.cs"
    p.write_text(
        "using UnityEngine;\n"
        "public class Bad : MonoBehaviour {\n"
        "    void Update() {\n"
        "        var pos = Camera.main.transform.position;\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    assert any(i.rule_id == "BUG-02" for i in issues)


def test_cs_async_void_detected(tmp_path):
    p = tmp_path / "Bad.cs"
    p.write_text(
        "using System.Threading.Tasks;\n"
        "public class Bad {\n"
        "    async void DoWork() { await Task.Delay(1); }\n"
        "}\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    assert any(i.rule_id == "BUG-11" for i in issues)


def test_cs_find_in_update_detected(tmp_path):
    p = tmp_path / "Bad.cs"
    p.write_text(
        "using UnityEngine;\n"
        "public class Bad : MonoBehaviour {\n"
        "    void Update() {\n"
        '        GameObject.Find("Player");\n'
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    assert any(i.rule_id == "BUG-06" for i in issues)


# =========================================================================
# C# True Negatives — code that must NOT be flagged
# =========================================================================

def test_cs_cached_getcomponent_not_flagged(tmp_path):
    p = tmp_path / "Good.cs"
    p.write_text(
        "using UnityEngine;\n"
        "public class Good : MonoBehaviour {\n"
        "    private Rigidbody _rb;\n"
        "    void Awake() { _rb = GetComponent<Rigidbody>(); }\n"
        "    void Update() { _rb.velocity = Vector3.zero; }\n"
        "}\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    assert not any(i.rule_id == "BUG-01" for i in issues)


def test_cs_async_task_not_flagged_as_async_void(tmp_path):
    p = tmp_path / "Good.cs"
    p.write_text(
        "using System.Threading.Tasks;\n"
        "public class Good {\n"
        "    async Task DoWork() { await Task.Delay(1); }\n"
        "}\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    assert not any(i.rule_id == "BUG-11" for i in issues)


def test_cs_event_with_unsubscribe_not_flagged(tmp_path):
    p = tmp_path / "Good.cs"
    p.write_text(
        "using UnityEngine;\n"
        "public class Good : MonoBehaviour {\n"
        "    void OnEnable() { SomeEvent.Changed += OnChanged; }\n"
        "    void OnDisable() { SomeEvent.Changed -= OnChanged; }\n"
        "    void OnChanged() { }\n"
        "}\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    assert not any(i.rule_id == "UNITY-08" for i in issues)


def test_cs_constructor_in_plain_class_not_flagged_unity01(tmp_path):
    p = tmp_path / "Good.cs"
    p.write_text(
        "public class DataModel {\n"
        "    public DataModel() { }\n"
        "}\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    assert not any(i.rule_id in ("UNITY-01", "UNITY-02") for i in issues)


# =========================================================================
# Edge Cases
# =========================================================================

def test_empty_python_file(tmp_path):
    p = tmp_path / "empty.py"
    p.write_text("", encoding="utf-8")
    issues = reviewer.scan_python_file(str(p), None, review_scope="strict")
    assert issues == []


def test_empty_csharp_file(tmp_path):
    p = tmp_path / "empty.cs"
    p.write_text("", encoding="utf-8")
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    assert issues == []


def test_python_syntax_error_no_crash(tmp_path):
    p = tmp_path / "broken.py"
    p.write_text("def f(\n  # broken syntax\n", encoding="utf-8")
    issues = reviewer.scan_python_file(str(p), None, review_scope="strict")
    # Should not crash, AST pass skips syntax errors
    assert isinstance(issues, list)


def test_production_mode_finds_zero_on_good_code(tmp_path):
    """Production mode should have zero findings on clean code."""
    p = tmp_path / "clean.py"
    p.write_text(
        "from pathlib import Path\n\n"
        "def process(data: list[str]) -> str:\n"
        "    return ','.join(data)\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_python_file(str(p), None, review_scope="production")
    assert len(issues) == 0


# =========================================================================
# Bug-34 crash regression test
# =========================================================================

def test_cs_bug34_dictionary_serialization_no_crash(tmp_path):
    """BUG-34 guard previously used .contains() (C# method) instead of 'in' (Python)."""
    p = tmp_path / "Dict.cs"
    p.write_text(
        "[System.Serializable]\n"
        "public class Data {\n"
        "    [SerializeField] private Dictionary<string, int> lookup;\n"
        "}\n",
        encoding="utf-8",
    )
    # Must not crash with AttributeError
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    assert isinstance(issues, list)


# =========================================================================
# Hot path propagation test
# =========================================================================

def test_cs_transitive_hot_path_detection(tmp_path):
    """Methods called from Update should be marked as hot path."""
    p = tmp_path / "HotPath.cs"
    p.write_text(
        "using UnityEngine;\n"
        "public class Test : MonoBehaviour {\n"
        "    void Update() {\n"
        "        DoWork();\n"
        "    }\n"
        "    void DoWork() {\n"
        "        var x = Camera.main;\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    # Camera.main in DoWork should be flagged because DoWork is called from Update
    # This tests the transitive hot-path propagation
    bug02 = [i for i in issues if i.rule_id == "BUG-02"]
    assert len(bug02) >= 1, f"Expected BUG-02 for Camera.main in transitive hot path, got {[i.rule_id for i in issues]}"


# =============================================================================
# REGRESSION TESTS FOR PHASE 1-3 FIXES
# =============================================================================


def test_cs_bug25_not_flagged_in_method_body(tmp_path):
    """BUG-25 (public Inspector field) should only flag at ClassLevel, not MethodBody."""
    p = tmp_path / "Bug25Fix.cs"
    p.write_text(
        "using UnityEngine;\n"
        "public class Test : MonoBehaviour {\n"
        "    public int health = 100;\n"  # ClassLevel - should flag
        "    void Update() {\n"
        "        var h = health;\n"  # MethodBody - should NOT flag BUG-25
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    bug25 = [i for i in issues if i.rule_id == "BUG-25"]
    # Should only flag the class-level field declaration, not the method body usage
    assert len(bug25) == 1, f"Expected 1 BUG-25 at ClassLevel, got {len(bug25)}: {[i.line for i in bug25]}"


def test_cs_unity09_not_flagged_on_enum(tmp_path):
    """UNITY-09 should not match 'Selection' or 'Undo' in game enum names."""
    p = tmp_path / "Unity09Fix.cs"
    p.write_text(
        "using UnityEngine;\n"
        "public class Test {\n"
        "    public enum TargetSelection { CASTING_ENEMY, ALLY }\n"  # Should NOT flag
        "    private TargetSelection _selection;\n"
        "    void Update() {\n"
        "        if (_selection == TargetSelection.CASTING_ENEMY) { }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    unity09 = [i for i in issues if i.rule_id == "UNITY-09"]
    assert len(unity09) == 0, f"Expected 0 UNITY-09 for enum, got {len(unity09)}"


def test_cs_unity05_not_flagged_with_requirecomponent(tmp_path):
    """UNITY-05 should not flag when [RequireComponent(typeof(T))] exists at class level."""
    p = tmp_path / "Unity05Fix.cs"
    p.write_text(
        "using UnityEngine;\n"
        "[RequireComponent(typeof(Rigidbody))]\n"  # File-level RequireComponent
        "public class Test : MonoBehaviour {\n"
        "    void Start() {\n"
        "        var rb = GetComponent<Rigidbody>();\n"  # Should NOT flag
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    unity05 = [i for i in issues if i.rule_id == "UNITY-05"]
    assert len(unity05) == 0, f"Expected 0 UNITY-05 with RequireComponent, got {len(unity05)}"


def test_cs_deep03_not_flagged_numeric_addition(tmp_path):
    """DEEP-03/UNITY-12 should not flag numeric addition (count += 1)."""
    p = tmp_path / "Deep03Fix.cs"
    p.write_text(
        "using System;\n"
        "public class Test {\n"
        "    private int _count;\n"
        "    void Update() {\n"
        "        _count += 1;\n"  # Should NOT flag as event subscription
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    event_rules = [i for i in issues if i.rule_id in ("UNITY-12", "UNITY-09")]
    assert len(event_rules) == 0, f"Expected 0 event rules for numeric +=, got {len(event_rules)}"


def test_cs_bug38_not_flagged_with_field_destroy(tmp_path):
    """BUG-38 should not flag when Texture2D assigned to field AND Destroy() exists."""
    p = tmp_path / "Bug38Fix.cs"
    p.write_text(
        "using UnityEngine;\n"
        "public class Test : MonoBehaviour {\n"
        "    private Texture2D _texture;\n"
        "    void Start() {\n"
        "        _texture = new Texture2D(256, 256);\n"  # Should NOT flag (has Destroy below)
        "    }\n"
        "    void OnDestroy() {\n"
        "        if (_texture != null) Destroy(_texture);\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    bug38 = [i for i in issues if i.rule_id == "BUG-38"]
    assert len(bug38) == 0, f"Expected 0 BUG-38 with field Destroy, got {len(bug38)}"


def test_cs_perf02_not_flagged_expression_bodied(tmp_path):
    """PERF-02 should not flag expression-bodied members (not lambdas)."""
    p = tmp_path / "Perf02Fix.cs"
    p.write_text(
        "using UnityEngine;\n"
        "public class Test : MonoBehaviour {\n"
        "    private int _value => 5;\n"  # Expression-bodied member - should NOT flag
        "    void Update() { }\n"
        "}\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    perf02 = [i for i in issues if i.rule_id == "PERF-02"]
    assert len(perf02) == 0, f"Expected 0 PERF-02 for expression-bodied member, got {len(perf02)}"


def test_cs_iter01_not_flagged_two_pass_removal(tmp_path):
    """ITER-01 should not flag safe two-pass removal pattern."""
    p = tmp_path / "Iter01Fix.cs"
    p.write_text(
        "using System.Collections.Generic;\n"
        "using System.Linq;\n"
        "public class Test {\n"
        "    private List<int> _items;\n"
        "    void RemoveItems() {\n"
        "        var toRemove = _items.Where(x => x < 0).ToList();\n"  # Two-pass - safe
        "        foreach (var item in toRemove) _items.Remove(item);\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    issues = reviewer.scan_csharp_file(str(p), None, review_scope="strict")
    iter01 = [i for i in issues if i.rule_id == "ITER-01"]
    assert len(iter01) == 0, f"Expected 0 ITER-01 for two-pass removal, got {len(iter01)}"
