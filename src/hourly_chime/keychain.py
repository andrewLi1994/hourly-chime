from __future__ import annotations

import json
import subprocess
from typing import Any

from . import paths


class HelperError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _invoke(command: str, payload: dict[str, Any] | None = None, timeout: int = 10) -> dict[str, Any]:
    helper = paths.keychain_helper_path()
    if not helper.is_file():
        raise HelperError("missing_helper", "找不到原生 Keychain Helper，请重新安装 Hourly Chime")
    try:
        result = subprocess.run(
            [str(helper), command],
            input=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HelperError("timeout", "Keychain Helper 调用超时") from exc
    except OSError as exc:
        raise HelperError("missing_helper", f"无法启动 Keychain Helper: {exc}") from exc
    try:
        response = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HelperError("helper_error", "Keychain Helper 返回格式无效") from exc
    if not isinstance(response, dict) or not response.get("ok"):
        code = str(response.get("error_code", "helper_error")) if isinstance(response, dict) else "helper_error"
        message = str(response.get("message", "Keychain Helper 执行失败")) if isinstance(response, dict) else "Keychain Helper 执行失败"
        raise HelperError(code, message)
    return response


def generate(prepared_prompt: str, timeout: int) -> dict[str, Any]:
    return _invoke("generate", {"prompt": prepared_prompt}, timeout=timeout + 5)


def status() -> dict[str, Any]:
    try:
        response = _invoke("status")
        return {"ok": True, "credential_available": bool(response.get("credential_available"))}
    except HelperError as exc:
        return {"ok": False, "credential_available": False, "error_code": exc.code, "message": str(exc)}
