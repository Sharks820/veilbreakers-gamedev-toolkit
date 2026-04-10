"""General-purpose C# rule subset for non-Unity projects."""

from __future__ import annotations

import re

from veilbreakers_mcp._rules_csharp import RULES as ALL_RULES
from veilbreakers_mcp._rules_csharp import _create_rule
from veilbreakers_mcp._types import Category, FindingType, Severity


CORE_RULE_IDS = frozenset(
    {
        "SEC-01",
        "SEC-02",
        "SEC-06",
        "SEC-07",
        "SEC-08",
        "SAVE-01",
        "ASYNC-01",
        "ASYNC-02",
        "ASYNC-03",
        "BUG-11",
        "BUG-49",
        "BUG-64",
        "BUG-65",
        "BUG-68",
        "QUAL-01",
        "QUAL-02",
        "QUAL-03",
        "QUAL-04",
        "QUAL-05",
        "QUAL-06",
        "QUAL-07",
        "QUAL-08",
        "QUAL-09",
        "QUAL-10",
        "QUAL-11",
        "QUAL-12",
        "QUAL-13",
        "QUAL-14",
        "QUAL-15",
        "QUAL-16",
        "QUAL-17",
        "PERF-23",
        "PERF-26",
        "PERF-29",
        "ITER-01",
        "TASK-01",
    }
)


RULES = [rule for rule in ALL_RULES if rule.id in CORE_RULE_IDS]


def _inside_async_method(
    line: str, all_lines: list[str], idx: int, _ctx=None
) -> bool:
    for j in range(idx, max(-1, idx - 20), -1):
        if re.search(r"\basync\b", all_lines[j]):
            return True
        if re.search(r"^\s*(public|private|protected|internal)\b.*\(", all_lines[j]):
            break
    return False


def _captured_scoped_dependency(
    line: str, all_lines: list[str], idx: int, _ctx=None
) -> bool:
    scoped_types: set[str] = set()
    for candidate in all_lines:
        match = re.search(r"AddScoped<\s*([\w\.]+)\s*>", candidate)
        if match:
            scoped_types.add(match.group(1).split(".")[-1])
    if not scoped_types:
        return False
    for scoped_type in scoped_types:
        if re.search(
            rf"AddSingleton<[^>]+>\s*\(\s*sp\s*=>.*GetRequiredService<\s*{re.escape(scoped_type)}\s*>",
            line,
        ):
            return True
    return False


def _autofix_where_count(
    line: str, _all_lines: list[str], idx: int
) -> dict[str, object] | None:
    match = re.search(
        r"\.Where\s*\((?P<predicate>[^)]*)\)\.Count\s*\(\s*\)", line
    )
    if not match:
        return None
    predicate = match.group("predicate").strip()
    replaced = (
        f"{line[:match.start()]}.Count({predicate}){line[match.end():]}"
    )
    if replaced == line:
        return None
    return {
        "edits": [{"start": idx, "end": idx + 1, "replacement": [replaced]}]
    }


RULES.extend(
    [
        _create_rule(
            "CS-COR-01",
            Severity.MEDIUM,
            Category.Quality,
            "HttpClient is created inside a using scope -- repeated construction can exhaust sockets",
            "Prefer IHttpClientFactory or a long-lived HttpClient instance.",
            r"using\s+(?:var|\()\s+\w+\s*=\s*new\s+HttpClient\s*\(",
            scope="AnyMethod",
            file_filter="All",
            finding_type=FindingType.STRENGTHENING,
            anti_patterns=[r"//\s*(?:VB|REVIEW)-IGNORE", r"IHttpClientFactory"],
            layer="semantic",
        ),
        _create_rule(
            "CS-COR-02",
            Severity.MEDIUM,
            Category.Bug,
            "Async method creates FileStream without async disposal",
            "Use await using var stream = new FileStream(...) in async methods.",
            r"new\s+FileStream\s*\(",
            scope="AnyMethod",
            file_filter="All",
            anti_patterns=[r"//\s*(?:VB|REVIEW)-IGNORE", r"await\s+using", r"using\s+var"],
            guard=_inside_async_method,
            layer="semantic",
        ),
        _create_rule(
            "CS-COR-03",
            Severity.LOW,
            Category.Quality,
            "Null-forgiving operator used without explanation",
            "Add a justification comment or replace with an explicit null check.",
            r"\w+!\.",
            scope="AnyMethod",
            file_filter="All",
            finding_type=FindingType.STRENGTHENING,
            anti_patterns=[r"//\s*(?:VB|REVIEW)-IGNORE", r"//\s*(null-ok|justified|safe)"],
            layer="heuristic",
        ),
        _create_rule(
            "CS-COR-04",
            Severity.LOW,
            Category.Quality,
            "Long null-conditional chain may hide unexpected null propagation",
            "Break the chain apart and handle the null case explicitly.",
            r"\?\.\w+\?\.",
            scope="AnyMethod",
            file_filter="All",
            finding_type=FindingType.STRENGTHENING,
            anti_patterns=[r"//\s*(?:VB|REVIEW)-IGNORE"],
            layer="heuristic",
        ),
        _create_rule(
            "CS-PERF-01",
            Severity.MEDIUM,
            Category.Performance,
            "ToList() inside a loop repeatedly materializes collections",
            "Materialize once outside the loop or iterate the source directly.",
            r"\.ToList\s*\(",
            scope="AnyMethod",
            file_filter="All",
            anti_patterns=[r"//\s*(?:VB|REVIEW)-IGNORE"],
            guard=lambda line, all_lines, idx, ctx=None: any(
                re.search(r"^\s*(for|foreach|while)\b", all_lines[j])
                for j in range(max(0, idx - 5), idx)
            ),
            layer="semantic",
        ),
        _create_rule(
            "CS-PERF-02",
            Severity.LOW,
            Category.Performance,
            "Where(...).Count() enumerates twice",
            "Use Count(predicate) instead of Where(...).Count().",
            r"\.Where\s*\([^)]*\)\.Count\s*\(",
            scope="AnyMethod",
            file_filter="All",
            finding_type=FindingType.OPTIMIZATION,
            anti_patterns=[r"//\s*(?:VB|REVIEW)-IGNORE"],
            layer="heuristic",
            auto_fix=_autofix_where_count,
        ),
        _create_rule(
            "CS-COR-05",
            Severity.HIGH,
            Category.Bug,
            "lock used inside async method -- blocks threads and can deadlock",
            "Use SemaphoreSlim or refactor so the lock is released before awaits.",
            r"^\s*lock\s*\(",
            scope="AnyMethod",
            file_filter="All",
            anti_patterns=[r"//\s*(?:VB|REVIEW)-IGNORE"],
            guard=_inside_async_method,
            layer="hard_correctness",
        ),
        _create_rule(
            "CS-COR-06",
            Severity.HIGH,
            Category.Bug,
            "Blocking on Task with .Result/.Wait() can deadlock and stalls threads",
            "Await the task instead of blocking synchronously.",
            r"(\.Result\b|\.Wait\s*\(\s*\))",
            scope="AnyMethod",
            file_filter="All",
            anti_patterns=[r"//\s*(?:VB|REVIEW)-IGNORE", r"Task\.CompletedTask"],
            layer="hard_correctness",
        ),
        _create_rule(
            "CS-COR-07",
            Severity.HIGH,
            Category.Bug,
            "Singleton registration captures a scoped service",
            "Do not resolve scoped services from AddSingleton; refactor to scoped/transient or use a factory at call time.",
            r"AddSingleton<",
            scope="AnyMethod",
            file_filter="All",
            anti_patterns=[r"//\s*(?:VB|REVIEW)-IGNORE"],
            guard=_captured_scoped_dependency,
            layer="semantic",
        ),
        _create_rule(
            "CS-SEC-01",
            Severity.CRITICAL,
            Category.Security,
            "Raw SQL query concatenates/interpolates data -- injection risk",
            "Use parameterized FromSqlInterpolated/ExecuteSqlInterpolated or query parameters.",
            r"(FromSqlRaw|ExecuteSqlRaw)\s*\(\s*(\$|@?\"[^\"]*\"?\s*\+)",
            scope="AnyMethod",
            file_filter="All",
            anti_patterns=[r"//\s*(?:VB|REVIEW)-IGNORE", r"FromSqlInterpolated", r"ExecuteSqlInterpolated"],
            layer="hard_correctness",
        ),
    ]
)


__all__ = ["CORE_RULE_IDS", "RULES"]
