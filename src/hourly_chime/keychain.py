from __future__ import annotations

import subprocess


SERVICE = "com.andrewli.hourlychime.ai"


class KeychainError(RuntimeError):
    pass


def read_secret(credential_id: str) -> str:
    if not credential_id:
        raise KeychainError("credential_id 为空")
    try:
        result = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                SERVICE,
                "-a",
                credential_id,
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise KeychainError(f"无法访问 Keychain: {exc}") from exc
    if result.returncode != 0:
        raise KeychainError("Keychain 中未找到当前 Provider 的 API Key")
    secret = result.stdout.strip()
    if not secret:
        raise KeychainError("Keychain 中的 API Key 为空")
    return secret
