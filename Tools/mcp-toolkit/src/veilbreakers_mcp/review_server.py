"""MCP server exposing multi-provider review helpers.

The server can talk to Gemini, Z.AI GLM, or OpenRouter-backed models in two ways:
- If the matching ``*_COMMAND`` variable is set, it invokes that local CLI and
  sends the review prompt on stdin.
- Otherwise it calls the matching API endpoint using the configured API key and
  base URL.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
import shutil
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("review")

DEFAULT_MODEL = "qwen/qwen3.6-plus:free"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_GLM_BASE_URL = "https://api.z.ai/api/coding/paas/v4"
DEFAULT_REVIEW_MODELS = (
    "qwen/qwen3.6-plus:free",
    "glm-5.0-turbo",
    "gemini-3.1-flash-lite-preview",
)
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_CLI_MODEL_ALIASES = {
    "gemini-3.1-flash-lite-preview": "gemini-3-flash-preview",
}
GLM_API_MODEL_ALIASES = {
    "glm-5.0-turbo": "glm-5-turbo",
}


def _load_local_env() -> None:
    project_root = Path(__file__).resolve().parents[4]
    for name in (".env", "pipeline.local.env"):
        path = project_root / name
        if path.exists():
            load_dotenv(path, override=False)


_load_local_env()


def _resolve_model(model: str | None = None) -> str:
    return (
        model
        or os.environ.get("REVIEW_MODEL")
        or os.environ.get("OPENROUTER_MODEL")
        or DEFAULT_MODEL
    ).strip()


def _resolve_provider(model: str) -> str:
    normalized = model.strip().lower()
    if normalized.startswith("gemini-"):
        return "gemini"
    if normalized.startswith("glm-"):
        return "glm"
    return "openrouter"


def _resolve_api_key(provider: str) -> str | None:
    if provider == "gemini":
        key_names = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GEMINI_API_KEY")
    elif provider == "glm":
        key_names = ("GLM_API_KEY", "ZAI_API_KEY", "BIGMODEL_API_KEY")
    else:
        key_names = ("OPENROUTER_API_KEY",)
    for key_name in key_names:
        value = os.environ.get(key_name)
        if value:
            return value.strip()
    return None


def _resolve_base_url(provider: str) -> str:
    if provider == "gemini":
        return (
            os.environ.get("GEMINI_BASE_URL")
            or os.environ.get("GOOGLE_GEMINI_BASE_URL")
            or DEFAULT_GEMINI_BASE_URL
        ).rstrip("/")
    if provider == "glm":
        return (
            os.environ.get("GLM_BASE_URL")
            or os.environ.get("ZAI_BASE_URL")
            or os.environ.get("BIGMODEL_BASE_URL")
            or DEFAULT_GLM_BASE_URL
        ).rstrip("/")
    return (
        os.environ.get("OPENROUTER_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or DEFAULT_OPENROUTER_BASE_URL
    ).rstrip("/")


def _resolve_command(provider: str) -> str | None:
    if provider == "gemini":
        return os.environ.get("GEMINI_COMMAND")
    if provider == "glm":
        return os.environ.get("GLM_COMMAND") or os.environ.get("ZAI_COMMAND")
    return os.environ.get("OPENROUTER_COMMAND")


def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _resolve_cli_model(provider: str, model: str) -> str:
    if provider != "gemini":
        return model
    env_key = "GEMINI_CLI_MODEL_ALIAS_" + re.sub(r"[^A-Z0-9]+", "_", model.upper()).strip("_")
    env_override = os.environ.get(env_key)
    if env_override:
        return env_override.strip()
    return GEMINI_CLI_MODEL_ALIASES.get(model, model)


def _resolve_api_model(provider: str, model: str) -> str:
    if provider == "glm":
        env_key = "GLM_API_MODEL_ALIAS_" + re.sub(r"[^A-Z0-9]+", "_", model.upper()).strip("_")
        env_override = os.environ.get(env_key)
        if env_override:
            return env_override.strip()
        return GLM_API_MODEL_ALIASES.get(model, model)
    return model


def _build_review_messages(
    *,
    diff: str,
    context: str = "",
    instructions: str = "",
) -> list[dict[str, str]]:
    system_prompt = (
        "You are a meticulous senior code reviewer. "
        "Review the diff for correctness, regressions, wiring mistakes, stale assumptions, "
        "missing tests, and seam/continuity issues. "
        "Return only concrete findings ordered by severity. "
        "If no issues are found, return exactly 'No findings.'."
    )

    sections = []
    if context.strip():
        sections.append(f"Context:\n{context.strip()}")
    if instructions.strip():
        sections.append(f"Extra instructions:\n{instructions.strip()}")
    sections.append(f"Diff:\n{diff.strip()}")

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n\n".join(sections)},
    ]


def _build_structured_review_messages(
    *,
    diff: str,
    context: str = "",
    instructions: str = "",
) -> list[dict[str, str]]:
    system_prompt = (
        "You are a meticulous senior code reviewer. "
        "Return valid JSON only. "
        "Respond with a JSON array of finding objects. "
        "Each object must include: "
        "title, severity, file, function, evidence, recommendation, confidence. "
        "Severity must be one of Critical, High, Medium, Low. "
        "If there are no findings, return an empty JSON array []. "
        "Do not include any prose outside the JSON."
    )

    sections = []
    if context.strip():
        sections.append(f"Context:\n{context.strip()}")
    if instructions.strip():
        sections.append(f"Extra instructions:\n{instructions.strip()}")
    sections.append(f"Diff:\n{diff.strip()}")

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n\n".join(sections)},
    ]


def _coerce_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _messages_to_prompt(messages: list[dict[str, str]]) -> str:
    return "\n\n".join(message["content"] for message in messages if message.get("content"))


def _extract_system_and_user_prompt(messages: list[dict[str, str]]) -> tuple[str, str]:
    system_parts: list[str] = []
    user_parts: list[str] = []
    for message in messages:
        content = message.get("content", "")
        if message.get("role") == "system":
            if content:
                system_parts.append(content)
        else:
            if content:
                user_parts.append(content)
    return "\n\n".join(system_parts), "\n\n".join(user_parts)


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def _coerce_confidence(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip().lower()
        try:
            return float(stripped)
        except ValueError:
            severity_map = {
                "critical": 0.95,
                "high": 0.75,
                "medium": 0.5,
                "low": 0.25,
            }
            return severity_map.get(stripped, 0.0)
    return 0.0


def _parse_structured_findings(text: str) -> list[dict[str, Any]]:
    """Parse JSON findings emitted by a structured review prompt."""
    cleaned = _strip_code_fences(text)
    if not cleaned or cleaned.lower() in {"no findings", "no findings."}:
        return []
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fall back to extracting a JSON object/array from a noisy response.
        start_candidates = [idx for idx in (cleaned.find("["), cleaned.find("{")) if idx != -1]
        end_candidates = [idx for idx in (cleaned.rfind("]"), cleaned.rfind("}")) if idx != -1]
        if not start_candidates or not end_candidates:
            return []
        start = min(start_candidates)
        end = max(end_candidates)
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return []

    if isinstance(parsed, dict):
        findings = parsed.get("findings", [])
    else:
        findings = parsed

    if not isinstance(findings, list):
        raise ValueError("Structured review did not produce a list of findings.")

    normalized: list[dict[str, Any]] = []
    for item in findings:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "title": str(item.get("title", "")).strip(),
                "severity": str(item.get("severity", "")).strip(),
                "file": str(item.get("file", "")).strip() or None,
                "function": str(item.get("function", "")).strip() or None,
                "evidence": str(item.get("evidence", "")).strip(),
                "recommendation": str(item.get("recommendation", "")).strip(),
                "confidence": _coerce_confidence(item.get("confidence", 0.0)),
            }
        )
    return normalized


def _extract_completion_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError("Review response did not include any choices.")
    message = choices[0].get("message") or {}
    text = _coerce_message_content(message.get("content"))
    if not text.strip():
        raise RuntimeError("Review response did not include review text.")
    return text.strip()


def _extract_gemini_completion_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini response did not include any candidates.")
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    text = _coerce_message_content(parts)
    if not text.strip():
        raise RuntimeError("Gemini response did not include review text.")
    return text.strip()


def _invoke_cli(prompt: str, model: str, provider: str) -> str | None:
    command = _resolve_command(provider)
    if not command:
        return None

    timeout_env = {
        "gemini": "GEMINI_TIMEOUT_SECONDS",
        "glm": "GLM_TIMEOUT_SECONDS",
        "openrouter": "OPENROUTER_TIMEOUT_SECONDS",
    }
    args_env = {
        "gemini": "GEMINI_COMMAND_ARGS",
        "glm": "GLM_COMMAND_ARGS",
        "openrouter": "OPENROUTER_COMMAND_ARGS",
    }
    model_env = {
        "gemini": "GEMINI_MODEL",
        "glm": "GLM_MODEL",
        "openrouter": "OPENROUTER_MODEL",
    }
    timeout_seconds = float(
        os.environ.get(timeout_env.get(provider, "OPENROUTER_TIMEOUT_SECONDS"), "180")
    )
    args = shlex.split(command)
    extra_args = shlex.split(os.environ.get(args_env.get(provider, "OPENROUTER_COMMAND_ARGS"), ""))
    env_model = os.environ.get(model_env.get(provider, "OPENROUTER_MODEL"), model)
    cli_model = _resolve_cli_model(provider, model)
    if provider == "gemini" and "--model" not in args and "-m" not in args:
        args = [*args, "--model", cli_model]
    resolved_executable = shutil.which(args[0]) or args[0]
    executable_suffix = Path(resolved_executable).suffix.lower()
    run_args = [*args, *extra_args]
    if os.name == "nt" and executable_suffix in {".cmd", ".bat"} and Path(args[0]).name.lower() not in {"cmd", "cmd.exe"}:
        run_args = ["cmd", "/c", *run_args]
    proc = subprocess.run(
        run_args,
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        env={
            **os.environ,
            "REVIEW_MODEL": env_model,
            "GEMINI_MODEL": env_model,
            "GLM_MODEL": env_model,
            "OPENROUTER_MODEL": env_model,
        },
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        stdout = proc.stdout.strip()
        message = stderr or stdout or f"{provider.upper()} CLI exited with {proc.returncode}"
        raise RuntimeError(message)

    output = proc.stdout.strip() or proc.stderr.strip()
    if not output:
        raise RuntimeError(f"{provider.upper()} CLI returned no output.")
    return output

def _invoke_openrouter_api(
    messages: list[dict[str, str]],
    model: str,
    *,
    temperature: float,
    max_tokens: int,
) -> str:
    api_key = _resolve_api_key("openrouter")
    if not api_key:
        raise RuntimeError(
            "No OpenRouter API key configured. Set OPENROUTER_API_KEY, or set OPENROUTER_COMMAND for a local CLI."
        )

    base_url = _resolve_base_url("openrouter")
    endpoint = f"{base_url}/chat/completions"
    payload: dict[str, Any] = {
        "model": _resolve_api_model("openrouter", model),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "provider": {
            "allow_fallbacks": _env_flag("OPENROUTER_ALLOW_FALLBACKS", True),
            "sort": os.environ.get("OPENROUTER_PROVIDER_SORT", "throughput"),
        },
    }
    data_collection = os.environ.get("OPENROUTER_DATA_COLLECTION", "").strip().lower()
    if data_collection in {"allow", "deny"}:
        payload["provider"]["data_collection"] = data_collection
    data = json.dumps(payload).encode("utf-8")
    timeout_seconds = float(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "180"))
    retry_attempts = max(int(os.environ.get("OPENROUTER_RETRY_ATTEMPTS", "4")), 1)
    retry_base_seconds = float(os.environ.get("OPENROUTER_RETRY_BASE_SECONDS", "2"))
    raw = ""
    last_error: Exception | None = None
    for attempt in range(retry_attempts):
        request = urllib.request.Request(
            endpoint,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "veilbreakers-reviewer/1.0",
                "HTTP-Referer": "https://veilbreakers.local",
                "X-Title": "veilbreakers-gamedev-toolkit",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                last_error = None
                break
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            should_retry = exc.code in {408, 409, 429, 500, 502, 503, 504} and attempt + 1 < retry_attempts
            if should_retry:
                delay = float(retry_after) if retry_after else retry_base_seconds * (2**attempt)
                time.sleep(delay)
                continue
            raise RuntimeError(f"OpenRouter API error {exc.code}: {body or exc.reason}") from exc
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt + 1 < retry_attempts:
                time.sleep(retry_base_seconds * (2**attempt))
                continue
            raise RuntimeError(f"OpenRouter API request failed: {exc.reason}") from exc

    if last_error is not None:
        raise RuntimeError(f"OpenRouter API request failed: {last_error}")

    try:
        response_json = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenRouter API returned invalid JSON: {raw[:500]}") from exc

    return _extract_completion_text(response_json)


def _invoke_glm_api(
    messages: list[dict[str, str]],
    model: str,
    *,
    temperature: float,
    max_tokens: int,
) -> str:
    api_key = _resolve_api_key("glm")
    if not api_key:
        raise RuntimeError(
            "No GLM API key configured. Set GLM_API_KEY or ZAI_API_KEY, or set GLM_COMMAND for a local CLI."
        )

    base_url = _resolve_base_url("glm")
    endpoint = f"{base_url}/chat/completions"
    resolved_model = _resolve_api_model("glm", model)
    payload: dict[str, Any] = {
        "model": resolved_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "thinking": {
            "type": os.environ.get("GLM_THINKING_TYPE", os.environ.get("ZAI_THINKING_TYPE", "disabled")).strip()
            or "disabled"
        },
    }
    data = json.dumps(payload).encode("utf-8")
    timeout_seconds = float(os.environ.get("GLM_TIMEOUT_SECONDS", os.environ.get("ZAI_TIMEOUT_SECONDS", "180")))
    retry_attempts = max(int(os.environ.get("GLM_RETRY_ATTEMPTS", os.environ.get("ZAI_RETRY_ATTEMPTS", "4"))), 1)
    retry_base_seconds = float(os.environ.get("GLM_RETRY_BASE_SECONDS", os.environ.get("ZAI_RETRY_BASE_SECONDS", "2")))
    raw = ""
    last_error: Exception | None = None
    for attempt in range(retry_attempts):
        request = urllib.request.Request(
            endpoint,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "veilbreakers-reviewer/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                last_error = None
                break
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            should_retry = exc.code in {408, 409, 429, 500, 502, 503, 504} and attempt + 1 < retry_attempts
            if should_retry:
                delay = float(retry_after) if retry_after else retry_base_seconds * (2**attempt)
                time.sleep(delay)
                continue
            raise RuntimeError(f"GLM API error {exc.code}: {body or exc.reason}") from exc
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt + 1 < retry_attempts:
                time.sleep(retry_base_seconds * (2**attempt))
                continue
            raise RuntimeError(f"GLM API request failed: {exc.reason}") from exc

    if last_error is not None:
        raise RuntimeError(f"GLM API request failed: {last_error}")

    try:
        response_json = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"GLM API returned invalid JSON: {raw[:500]}") from exc

    return _extract_completion_text(response_json)


def _invoke_gemini_api(messages: list[dict[str, str]], model: str, *, temperature: float, max_tokens: int) -> str:
    api_key = _resolve_api_key("gemini")
    if not api_key:
        raise RuntimeError(
            "No Gemini API key configured. Set GEMINI_API_KEY or GOOGLE_API_KEY, or set GEMINI_COMMAND for a local CLI."
        )

    system_prompt, user_prompt = _extract_system_and_user_prompt(messages)
    base_url = _resolve_base_url("gemini")
    endpoint = f"{base_url}/models/{model}:generateContent"
    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_prompt.strip():
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=data,
        method="POST",
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "veilbreakers-reviewer/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=float(os.environ.get("GEMINI_TIMEOUT_SECONDS", "180"))) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API error {exc.code}: {body or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini API request failed: {exc.reason}") from exc

    try:
        response_json = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini API returned invalid JSON: {raw[:500]}") from exc

    return _extract_gemini_completion_text(response_json)


def _invoke_api(
    messages: list[dict[str, str]],
    model: str,
    *,
    temperature: float,
    max_tokens: int,
    provider: str,
) -> str:
    if provider == "gemini":
        return _invoke_gemini_api(messages, model, temperature=temperature, max_tokens=max_tokens)
    if provider == "glm":
        return _invoke_glm_api(messages, model, temperature=temperature, max_tokens=max_tokens)
    return _invoke_openrouter_api(messages, model, temperature=temperature, max_tokens=max_tokens)


def _run_review(
    *,
    diff: str,
    context: str = "",
    instructions: str = "",
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> str:
    resolved_model = _resolve_model(model)
    provider = _resolve_provider(resolved_model)
    messages = _build_review_messages(
        diff=diff,
        context=context,
        instructions=instructions,
    )

    prompt = _messages_to_prompt(messages)
    cli_output = _invoke_cli(prompt, resolved_model, provider)
    if cli_output is not None:
        return cli_output

    return _invoke_api(
        messages,
        resolved_model,
        temperature=temperature,
        max_tokens=max_tokens,
        provider=provider,
    )


def _run_structured_review(
    *,
    diff: str,
    context: str = "",
    instructions: str = "",
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> list[dict[str, Any]]:
    resolved_model = _resolve_model(model)
    provider = _resolve_provider(resolved_model)
    messages = _build_structured_review_messages(
        diff=diff,
        context=context,
        instructions=instructions,
    )

    prompt = _messages_to_prompt(messages)
    cli_output = _invoke_cli(prompt, resolved_model, provider)
    if cli_output is not None:
        return _parse_structured_findings(cli_output)

    raw = _invoke_api(
        messages,
        resolved_model,
        temperature=temperature,
        max_tokens=max_tokens,
        provider=provider,
    )
    return _parse_structured_findings(raw)


def _normalize_finding_key(finding: dict[str, Any]) -> str:
    pieces = [
        str(finding.get("file") or "").lower(),
        str(finding.get("function") or "").lower(),
        str(finding.get("title") or "").lower(),
    ]
    combined = " ".join(piece for piece in pieces if piece).strip()
    combined = re.sub(r"[^a-z0-9]+", " ", combined)
    combined = re.sub(r"\s+", " ", combined).strip()
    words = combined.split()
    return " ".join(words[:16])


def _severity_rank(severity: str) -> int:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return order.get(severity.strip().lower(), 4)


def _merge_consensus_findings(model_results: list[dict[str, Any]], min_agreement: int = 2) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {}
    for model_result in model_results:
        model_name = model_result["model"]
        for finding in model_result.get("findings", []):
            key = _normalize_finding_key(finding)
            if not key:
                continue
            bucket = buckets.setdefault(
                key,
                {
                    "key": key,
                    "title": finding.get("title") or key,
                    "severity": finding.get("severity") or "Unknown",
                    "file": finding.get("file"),
                    "function": finding.get("function"),
                    "evidence": finding.get("evidence", ""),
                    "recommendation": finding.get("recommendation", ""),
                    "confidence": finding.get("confidence", 0.0),
                    "models": [],
                    "findings": [],
                },
            )
            bucket["models"].append(model_name)
            bucket["findings"].append(
                {
                    "model": model_name,
                    "title": finding.get("title") or "",
                    "severity": finding.get("severity") or "Unknown",
                    "file": finding.get("file"),
                    "function": finding.get("function"),
                    "evidence": finding.get("evidence", ""),
                    "recommendation": finding.get("recommendation", ""),
                    "confidence": finding.get("confidence", 0.0),
                }
            )

            if _severity_rank(str(finding.get("severity") or "")) < _severity_rank(str(bucket["severity"])):
                bucket["severity"] = finding.get("severity") or bucket["severity"]
            if not bucket.get("file") and finding.get("file"):
                bucket["file"] = finding.get("file")
            if not bucket.get("function") and finding.get("function"):
                bucket["function"] = finding.get("function")
            if finding.get("confidence", 0.0) > bucket.get("confidence", 0.0):
                bucket["confidence"] = finding.get("confidence", 0.0)
                bucket["evidence"] = finding.get("evidence", bucket.get("evidence", ""))
                bucket["recommendation"] = finding.get("recommendation", bucket.get("recommendation", ""))

    consensus = []
    model_specific = []
    for bucket in buckets.values():
        bucket["models"] = sorted(set(bucket["models"]))
        bucket["agreement"] = len(bucket["models"])
        if bucket["agreement"] >= min_agreement:
            consensus.append(bucket)
        else:
            model_specific.append(bucket)

    consensus.sort(key=lambda item: (_severity_rank(str(item.get("severity", ""))), -item["agreement"], item["key"]))
    model_specific.sort(key=lambda item: (_severity_rank(str(item.get("severity", ""))), -item["agreement"], item["key"]))

    return {
        "consensus_findings": consensus,
        "model_specific_findings": model_specific,
    }


def _write_json_report(report: dict[str, Any], save_path: str = "", save_dir: str = "") -> str | None:
    """Persist a report to disk and return the written path."""
    target: Path | None = None
    if save_path.strip():
        target = Path(save_path)
    elif save_dir.strip():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        diff_hash = report.get("diff_sha256", "report")
        target = Path(save_dir) / f"review-{stamp}-{diff_hash[:12]}.json"
    if target is None:
        return None

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return str(target)


def _load_truth_findings(truth_path: str) -> list[dict[str, Any]]:
    path = Path(truth_path)
    if not path.exists():
        raise FileNotFoundError(f"Truth file does not exist: {truth_path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        findings = data.get("findings", [])
    else:
        findings = data
    if not isinstance(findings, list):
        raise ValueError("Truth file must contain a JSON array or an object with a 'findings' list.")
    normalized: list[dict[str, Any]] = []
    for item in findings:
        if not isinstance(item, dict):
            continue
        raw_category = str(item.get("category", "real")).strip().lower()
        classification = str(
            item.get("classification") or item.get("subcategory") or raw_category or "real"
        ).strip().lower()
        if raw_category in {"real", "other"}:
            category = raw_category
        else:
            aliases = {
                "real_bug": ("real", "real_bug"),
                "real_test_issue": ("real", "real_test_issue"),
                "bug": ("real", "real_bug"),
                "test": ("real", "real_test_issue"),
                "design_concern": ("other", "design_concern"),
                "intentional": ("other", "intentional_change"),
                "intentional_not_bug": ("other", "intentional_change"),
                "non_defect": ("other", "non_defect"),
            }
            category, classification = aliases.get(raw_category, ("real", classification))
        if category == "real" and classification == "real":
            classification = "real_bug"
        if category == "other" and classification == "other":
            classification = "other"
        normalized.append({**item, "category": category, "classification": classification})
    return normalized


def _score_finding_sets(predicted: list[dict[str, Any]], truth: list[dict[str, Any]]) -> dict[str, Any]:
    predicted_by_key = {
        key: item for item in predicted if (key := _normalize_finding_key(item))
    }
    truth_by_key = {
        key: item for item in truth if (key := _normalize_finding_key(item))
    }
    predicted_keys = set(predicted_by_key)
    real_truth_keys = {key for key, item in truth_by_key.items() if item.get("category") != "other"}
    other_truth_keys = {key for key, item in truth_by_key.items() if item.get("category") == "other"}
    matched_real_keys = predicted_keys & real_truth_keys
    matched_other_keys = predicted_keys & other_truth_keys
    true_positives = len(matched_real_keys)
    other_match_count = len(matched_other_keys)
    false_positives = len(predicted_keys - real_truth_keys - other_truth_keys)
    missed = len(real_truth_keys - predicted_keys)
    predicted_count = len(predicted_keys)
    truth_count = len(real_truth_keys)
    useful_signal_count = true_positives + other_match_count
    precision = true_positives / predicted_count if predicted_count else 0.0
    recall = true_positives / truth_count if truth_count else 0.0
    fpr = false_positives / predicted_count if predicted_count else 0.0
    miss_rate = missed / truth_count if truth_count else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    useful_signal_rate = useful_signal_count / predicted_count if predicted_count else 0.0
    strict_accuracy = precision
    other_breakdown: dict[str, int] = {}
    for key in matched_other_keys:
        classification = str(truth_by_key[key].get("classification", "other")).strip() or "other"
        other_breakdown[classification] = other_breakdown.get(classification, 0) + 1
    return {
        "true_positive_count": true_positives,
        "other_match_count": other_match_count,
        "false_positive_count": false_positives,
        "missed_bug_count": missed,
        "predicted_count": predicted_count,
        "truth_count": truth_count,
        "other_truth_count": len(other_truth_keys),
        "precision": precision,
        "recall": recall,
        "false_positive_rate": fpr,
        "miss_rate": miss_rate,
        "f1": f1,
        "strict_accuracy": strict_accuracy,
        "useful_signal_count": useful_signal_count,
        "useful_signal_rate": useful_signal_rate,
        "other_breakdown": dict(sorted(other_breakdown.items())),
        "other_matches": [
            {
                "title": str(truth_by_key[key].get("title", "")).strip(),
                "severity": str(truth_by_key[key].get("severity", "")).strip(),
                "file": str(truth_by_key[key].get("file", "")).strip() or None,
                "function": str(truth_by_key[key].get("function", "")).strip() or None,
                "category": "other",
                "classification": str(truth_by_key[key].get("classification", "other")).strip() or "other",
            }
            for key in sorted(matched_other_keys)
        ],
    }


def _load_json_reports(history_dir: str) -> list[dict[str, Any]]:
    root = Path(history_dir)
    if not root.exists():
        raise FileNotFoundError(f"History directory does not exist: {history_dir}")
    if not root.is_dir():
        raise NotADirectoryError(f"History path is not a directory: {history_dir}")

    reports: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.json")):
        try:
            reports.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            logger.warning("Skipping unreadable history file %s: %s", path, exc)
    return reports


def _summarize_history_reports(reports: list[dict[str, Any]], top_n: int = 10) -> dict[str, Any]:
    model_stats: dict[str, dict[str, Any]] = {}
    key_stats: dict[str, dict[str, Any]] = {}

    for report in reports:
        for model_result in report.get("models", []):
            model_name = model_result.get("model", "unknown")
            stats = model_stats.setdefault(
                model_name,
                {
                    "runs": 0,
                    "findings": 0,
                    "errors": 0,
                    "consensus_hits": 0,
                    "true_positive_count": 0,
                    "other_match_count": 0,
                    "false_positive_count": 0,
                    "missed_bug_count": 0,
                    "predicted_count": 0,
                    "truth_count": 0,
                    "other_truth_count": 0,
                    "other_breakdown": {},
                },
            )
            stats["runs"] += 1
            stats["findings"] += int(model_result.get("finding_count", 0) or 0)
            if model_result.get("status") != "ok":
                stats["errors"] += 1

        evaluation = report.get("evaluation") or {}
        for model_name, metrics in (evaluation.get("models") or {}).items():
            stats = model_stats.setdefault(
                model_name,
                {
                    "runs": 0,
                    "findings": 0,
                    "errors": 0,
                    "consensus_hits": 0,
                    "true_positive_count": 0,
                    "other_match_count": 0,
                    "false_positive_count": 0,
                    "missed_bug_count": 0,
                    "predicted_count": 0,
                    "truth_count": 0,
                    "other_truth_count": 0,
                    "other_breakdown": {},
                },
            )
            for key_name in (
                "true_positive_count",
                "other_match_count",
                "false_positive_count",
                "missed_bug_count",
                "predicted_count",
                "truth_count",
                "other_truth_count",
            ):
                stats[key_name] += int(metrics.get(key_name, 0) or 0)
            for key_name, count in (metrics.get("other_breakdown") or {}).items():
                stats["other_breakdown"][key_name] = stats["other_breakdown"].get(key_name, 0) + int(count or 0)

        for item in report.get("consensus_findings", []):
            key = str(item.get("key") or item.get("title") or "").strip()
            if not key:
                continue
            stats = key_stats.setdefault(
                key,
                {"count": 0, "titles": set(), "models": set(), "severities": set()},
            )
            stats["count"] += 1
            stats["titles"].add(str(item.get("title") or ""))
            stats["models"].update(item.get("models", []))
            if item.get("severity"):
                stats["severities"].add(str(item.get("severity")))
            for model_name in item.get("models", []):
                if model_name in model_stats:
                    model_stats[model_name]["consensus_hits"] += 1

    for stats in model_stats.values():
        predicted_count = int(stats.get("predicted_count", 0) or 0)
        truth_count = int(stats.get("truth_count", 0) or 0)
        tp = int(stats.get("true_positive_count", 0) or 0)
        other_count = int(stats.get("other_match_count", 0) or 0)
        fp = int(stats.get("false_positive_count", 0) or 0)
        fn = int(stats.get("missed_bug_count", 0) or 0)
        stats["precision"] = tp / predicted_count if predicted_count else 0.0
        stats["recall"] = tp / truth_count if truth_count else 0.0
        stats["false_positive_rate"] = fp / predicted_count if predicted_count else 0.0
        stats["miss_rate"] = fn / truth_count if truth_count else 0.0
        stats["strict_accuracy"] = stats["precision"]
        stats["useful_signal_count"] = tp + other_count
        stats["useful_signal_rate"] = stats["useful_signal_count"] / predicted_count if predicted_count else 0.0
        stats["f1"] = (
            2 * stats["precision"] * stats["recall"] / (stats["precision"] + stats["recall"])
            if (stats["precision"] + stats["recall"])
            else 0.0
        )

    ranked_keys = sorted(
        key_stats.items(),
        key=lambda kv: (-kv[1]["count"], kv[0]),
    )[:top_n]

    return {
        "history_runs": len(reports),
        "model_stats": model_stats,
        "top_recurring_findings": [
            {
                "key": key,
                "count": stats["count"],
                "titles": sorted(t for t in stats["titles"] if t),
                "models": sorted(stats["models"]),
                "severities": sorted(stats["severities"]),
            }
            for key, stats in ranked_keys
        ],
    }


@mcp.tool()
def review_diff(
    diff: str,
    context: str = "",
    instructions: str = "",
    model: str = "",
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> str:
    """Review a unified diff and return concrete findings only."""
    return _run_review(
        diff=diff,
        context=context,
        instructions=instructions,
        model=model or None,
        temperature=temperature,
        max_tokens=max_tokens,
    )


@mcp.tool()
def review_text(
    text: str,
    instructions: str = "",
    model: str = "",
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> str:
    """Review arbitrary text."""
    return _run_review(
        diff=text,
        context="",
        instructions=instructions,
        model=model or None,
        temperature=temperature,
        max_tokens=max_tokens,
    )


@mcp.tool()
def review_consensus(
    diff: str,
    context: str = "",
    instructions: str = "",
    models: list[str] | None = None,
    min_agreement: int = 2,
    save_path: str = "",
    save_dir: str = "",
    truth_path: str = "",
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> str:
    """Run multiple reviewers and return a JSON consensus report."""
    model_list = list(models) if models else list(DEFAULT_REVIEW_MODELS)
    if min_agreement < 1:
        raise ValueError("min_agreement must be at least 1")
    if min_agreement > len(model_list):
        raise ValueError("min_agreement cannot exceed the number of models")

    model_results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(model_list)) as executor:
        future_map = {
            executor.submit(
                _run_structured_review,
                diff=diff,
                context=context,
                instructions=instructions,
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
            ): model_name
            for model_name in model_list
        }
        for future in as_completed(future_map):
            model_name = future_map[future]
            try:
                findings = future.result()
                model_results.append(
                    {
                        "model": model_name,
                        "provider": _resolve_provider(model_name),
                        "status": "ok",
                        "finding_count": len(findings),
                        "findings": findings,
                    }
                )
            except Exception as exc:  # pragma: no cover - surfaced as data for the caller
                model_results.append(
                    {
                        "model": model_name,
                        "provider": _resolve_provider(model_name),
                        "status": "error",
                        "error": str(exc),
                        "finding_count": 0,
                        "findings": [],
                    }
                )

    model_results.sort(key=lambda item: model_list.index(item["model"]))
    merged = _merge_consensus_findings(model_results, min_agreement=min_agreement)
    diff_hash = hashlib.sha256(diff.encode("utf-8")).hexdigest()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diff_sha256": diff_hash,
        "models": model_results,
        "min_agreement": min_agreement,
        **merged,
    }
    if truth_path.strip():
        truth_findings = _load_truth_findings(truth_path)
        report["evaluation"] = {
            "truth_path": truth_path,
            "truth_count": len({_normalize_finding_key(item) for item in truth_findings if _normalize_finding_key(item)}),
            "models": {
                model_result["model"]: _score_finding_sets(model_result.get("findings", []), truth_findings)
                for model_result in model_results
                if model_result.get("status") == "ok"
            },
            "consensus": _score_finding_sets(merged.get("consensus_findings", []), truth_findings),
        }
    saved_path = _write_json_report(report, save_path=save_path, save_dir=save_dir)
    if saved_path:
        report["saved_to"] = saved_path
    return json.dumps(report, indent=2, sort_keys=True)


@mcp.tool()
def review_history_summary(
    history_dir: str,
    top_n: int = 10,
) -> str:
    """Summarize saved review reports to measure consistency over time."""
    reports = _load_json_reports(history_dir)
    summary = _summarize_history_reports(reports, top_n=top_n)
    summary["history_dir"] = history_dir
    return json.dumps(summary, indent=2, sort_keys=True)


def main() -> None:
    """Entry point for the review MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
