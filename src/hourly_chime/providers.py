from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from . import keychain, paths


class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class GeneratedText:
    text: str
    provider: str
    model: str
    latency_ms: int


class TextProvider(Protocol):
    def generate(self, prompt: str, language: str) -> GeneratedText: ...


LANGUAGE_NAMES = {"zh": "Simplified Chinese", "en": "English", "ja": "Japanese"}


def build_prompt(template_prompt: str, language: str) -> str:
    language_name = LANGUAGE_NAMES.get(language, "English")
    return (
        f"Create one concise reminder in {language_name}. "
        "Return plain text only: exactly one sentence, no Markdown, no emoji, no greeting, and no name. "
        f"Reminder brief: {template_prompt.strip()}"
    )


def sanitize_text(value: str) -> str:
    text = re.sub(r"[`*_#]", "", str(value))
    text = re.sub(r"\s+", " ", text).strip().strip('"\'“”‘’')
    if not text:
        raise ProviderError("invalid_response", "Provider 返回了空文本")
    if len(text) > 300:
        raise ProviderError("invalid_response", "Provider 返回文本超过 300 字符")
    return text


def _error_for_http(code: int) -> ProviderError:
    if code in {401, 403}:
        return ProviderError("auth", "Provider 认证失败")
    if code == 429:
        return ProviderError("rate_limit", "Provider 已达到速率限制")
    return ProviderError("network", f"Provider 返回 HTTP {code}")


class OpenAICompatibleProvider:
    def __init__(self, base_url: str, model: str, api_key: str, timeout: int, name: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.name = name

    def _endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def generate(self, prompt: str, language: str) -> GeneratedText:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": build_prompt(prompt, language)}],
            "max_tokens": 192,
            "temperature": 0.8,
            "stream": False,
        }
        if self.name == "gemini":
            # Gemini 2.5 Flash dynamically thinks by default. A tiny reminder
            # does not need reasoning; disabling it prevents the completion
            # budget being consumed before the sentence is finished.
            body["reasoning_effort"] = "none" if "gemini-2.5-flash" in self.model.lower() else "low"
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self._endpoint(),
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error = _error_for_http(exc.code)
            exc.close()
            raise error from exc
        except TimeoutError as exc:
            raise ProviderError("timeout", "Provider 调用超时") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise ProviderError("timeout", "Provider 调用超时") from exc
            raise ProviderError("network", f"Provider 网络错误: {exc.reason}") from exc
        try:
            data = json.loads(raw)
            choice = data["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ProviderError("truncated_response", "Provider 输出被长度限制截断，请重试")
            text = choice["message"]["content"]
        except ProviderError:
            raise
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("invalid_response", "Provider 响应格式不兼容") from exc
        return GeneratedText(
            sanitize_text(text),
            self.name,
            self.model,
            int((time.monotonic() - started) * 1000),
        )


class OpenClawProvider:
    def __init__(self, timeout: int = 25, executable: str | None = None):
        self.timeout = timeout
        self.executable = executable or shutil.which("openclaw") or "/opt/homebrew/bin/openclaw"

    def generate(self, prompt: str, language: str) -> GeneratedText:
        started = time.monotonic()
        try:
            result = subprocess.run(
                [
                    self.executable,
                    "agent",
                    "--agent",
                    "main",
                    "--message",
                    build_prompt(prompt, language),
                    "--json",
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ProviderError("missing_executable", "找不到 OpenClaw") from exc
        except subprocess.TimeoutExpired as exc:
            raise ProviderError("timeout", "OpenClaw 调用超时") from exc
        if result.returncode != 0:
            message = result.stderr.strip() or "OpenClaw 返回错误"
            raise ProviderError("provider_error", message[:300])
        try:
            data = json.loads(result.stdout)
            text = data["result"]["payloads"][0]["text"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("invalid_response", "OpenClaw 响应格式不兼容") from exc
        return GeneratedText(
            sanitize_text(text),
            "openclaw",
            "main",
            int((time.monotonic() - started) * 1000),
        )


CODEX_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string", "maxLength": 300}},
    "required": ["text"],
    "additionalProperties": False,
}


def resolve_codex_executable(configured: str = "") -> str | None:
    candidates = [
        configured,
        shutil.which("codex") or "",
        "/Applications/ChatGPT.app/Contents/Resources/codex",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


class CodexProvider:
    def __init__(self, timeout: int = 45, model: str = "", executable: str = ""):
        self.timeout = timeout
        self.model = model
        self.executable = resolve_codex_executable(executable)

    def generate(self, prompt: str, language: str) -> GeneratedText:
        if not self.executable:
            raise ProviderError("missing_executable", "找不到 Codex CLI")
        paths.ensure_layout()
        schema_path = paths.codex_workspace() / "reminder-schema.json"
        schema_path.write_text(json.dumps(CODEX_SCHEMA), encoding="utf-8")
        command = [
            self.executable,
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--output-schema",
            str(schema_path),
            "--color",
            "never",
            "-C",
            str(paths.codex_workspace()),
        ]
        if self.model:
            command.extend(["--model", self.model])
        command.append("-")
        started = time.monotonic()
        try:
            result = subprocess.run(
                command,
                input=build_prompt(prompt, language),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderError("timeout", "Codex 调用超时") from exc
        if result.returncode != 0:
            stderr = result.stderr.lower()
            if "login" in stderr or "auth" in stderr:
                raise ProviderError("not_logged_in", "Codex 尚未登录")
            if "rate" in stderr or "limit" in stderr:
                raise ProviderError("rate_limit", "Codex 已达到使用限制")
            raise ProviderError("provider_error", (result.stderr.strip() or "Codex 返回错误")[-300:])
        try:
            data = json.loads(result.stdout)
            text = data["text"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ProviderError("invalid_response", "Codex 未返回预期的结构化文本") from exc
        return GeneratedText(
            sanitize_text(text),
            "codex",
            self.model or "default",
            int((time.monotonic() - started) * 1000),
        )


class StaticProvider:
    def __init__(self, text: str):
        self.text = text

    def generate(self, prompt: str, language: str) -> GeneratedText:
        return GeneratedText(sanitize_text(self.text), "static", "fallback", 0)


def build_provider(provider_config: dict[str, Any], api_key_override: str | None = None) -> TextProvider:
    kind = provider_config.get("kind")
    timeout = int(provider_config.get("timeout_seconds", 25))
    if kind == "openclaw":
        return OpenClawProvider(timeout=timeout)
    if kind == "codex":
        return CodexProvider(
            timeout=max(timeout, 45),
            model=str(provider_config.get("model", "")),
            executable=str(provider_config.get("codex_path", "")),
        )
    if kind == "static":
        return StaticProvider(str(provider_config.get("text", "Time to drink water.")))
    if kind == "openai_compatible":
        secret = api_key_override or keychain.read_secret(str(provider_config.get("credential_id", "")))
        return OpenAICompatibleProvider(
            base_url=str(provider_config["base_url"]),
            model=str(provider_config["model"]),
            api_key=secret,
            timeout=timeout,
            name=str(provider_config.get("preset", "custom")),
        )
    raise ProviderError("not_configured", "未配置可用的 Provider")
