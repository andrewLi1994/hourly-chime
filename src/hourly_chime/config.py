from __future__ import annotations

import copy
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import paths


class ConfigError(ValueError):
    pass


DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "schedule": {
        "dnd": {
            "enabled": True,
            "start_minute": 22 * 60,
            "end_minute": 8 * 60,
            "step_minutes": 15,
        },
        "music_hour": 17,
        "late_tolerance_minutes": 3,
    },
    "audio": {
        "chime_file": "hourly-chime.wav",
        "music_file": "hourly-music.wav",
        "volume": 1.0,
        "fallback_text": "Time to stay hydrated and drink some water.",
        "voices": {
            "zh": "zh-CN-XiaoxiaoNeural",
            "en": "en-US-AvaNeural",
            "ja": "ja-JP-NanamiNeural",
        },
    },
    "provider": {
        "kind": "openclaw",
        "preset": "openclaw",
        "base_url": "",
        "model": "",
        "credential_id": "",
        "timeout_seconds": 25,
        "codex_path": "",
    },
    "templates": [
        {
            "id": "hydration-default",
            "name": "喝水提醒",
            "prompt": "Give me a short, simple and friendly reminder to drink water.",
            "language": "en",
            "enabled": True,
        }
    ],
    "limits": {"max_daily_ai_calls": 20},
}


def default_config() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_CONFIG)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def _valid_custom_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme == "https" and parsed.netloc:
        return True
    return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}


def validate_config(data: dict[str, Any]) -> dict[str, Any]:
    _require(isinstance(data, dict), "配置必须是 JSON 对象")
    _require(data.get("schema_version") == 1, "不支持的 schema_version")

    schedule = data.get("schedule")
    _require(isinstance(schedule, dict), "缺少 schedule")
    dnd = schedule.get("dnd")
    _require(isinstance(dnd, dict), "缺少 schedule.dnd")
    _require(isinstance(dnd.get("enabled"), bool), "dnd.enabled 必须是布尔值")
    start = dnd.get("start_minute")
    end = dnd.get("end_minute")
    step = dnd.get("step_minutes")
    _require(isinstance(start, int) and 0 <= start < 1440, "dnd.start_minute 无效")
    _require(isinstance(end, int) and 0 <= end < 1440, "dnd.end_minute 无效")
    _require(start != end, "静音开始和结束不能相同")
    _require(step == 15, "首版仅支持 15 分钟粒度")
    _require(start % step == 0 and end % step == 0, "静音时间必须对齐 15 分钟")
    _require(isinstance(schedule.get("music_hour"), int) and 0 <= schedule["music_hour"] <= 23, "music_hour 无效")
    tolerance = schedule.get("late_tolerance_minutes")
    _require(isinstance(tolerance, int) and 0 <= tolerance <= 15, "late_tolerance_minutes 无效")

    audio = data.get("audio")
    _require(isinstance(audio, dict), "缺少 audio")
    _require(isinstance(audio.get("chime_file"), str) and audio["chime_file"], "chime_file 无效")
    _require(isinstance(audio.get("music_file"), str) and audio["music_file"], "music_file 无效")
    _require(Path(audio["chime_file"]).name == audio["chime_file"], "chime_file 必须是音频目录内的文件名")
    _require(Path(audio["music_file"]).name == audio["music_file"], "music_file 必须是音频目录内的文件名")
    volume = audio.get("volume")
    _require(isinstance(volume, (int, float)) and 0 <= volume <= 1, "volume 必须在 0 到 1 之间")
    _require(isinstance(audio.get("fallback_text"), str) and audio["fallback_text"].strip(), "fallback_text 无效")
    voices = audio.get("voices")
    _require(isinstance(voices, dict) and all(voices.get(key) for key in ("zh", "en", "ja")), "voices 配置不完整")

    provider = data.get("provider")
    _require(isinstance(provider, dict), "缺少 provider")
    kind = provider.get("kind")
    _require(kind in {"openclaw", "codex", "openai_compatible", "static"}, "provider.kind 无效")
    timeout = provider.get("timeout_seconds")
    _require(isinstance(timeout, int) and 5 <= timeout <= 120, "provider.timeout_seconds 无效")
    if kind == "openai_compatible":
        _require(provider.get("preset") in {"gemini", "nvidia", "custom"}, "provider.preset 无效")
        _require(_valid_custom_url(str(provider.get("base_url", ""))), "Provider URL 必须使用 HTTPS；本机地址除外")
        _require(bool(str(provider.get("model", "")).strip()), "Provider model 不能为空")
        _require(bool(str(provider.get("credential_id", "")).strip()), "Provider credential_id 不能为空")

    templates = data.get("templates")
    _require(isinstance(templates, list) and templates, "至少需要一个提醒模板")
    enabled = 0
    ids: set[str] = set()
    for template in templates:
        _require(isinstance(template, dict), "模板必须是对象")
        template_id = template.get("id")
        _require(isinstance(template_id, str) and template_id and template_id not in ids, "模板 ID 缺失或重复")
        ids.add(template_id)
        _require(isinstance(template.get("name"), str) and template["name"].strip(), "模板名称不能为空")
        _require(isinstance(template.get("prompt"), str) and template["prompt"].strip(), "模板提示词不能为空")
        _require(template.get("language") in {"zh", "en", "ja"}, "模板语言必须是 zh、en 或 ja")
        _require(isinstance(template.get("enabled"), bool), "模板 enabled 必须是布尔值")
        enabled += int(template["enabled"])
    _require(enabled > 0, "至少需要启用一个模板")

    limits = data.get("limits")
    _require(isinstance(limits, dict), "缺少 limits")
    max_calls = limits.get("max_daily_ai_calls")
    _require(isinstance(max_calls, int) and 1 <= max_calls <= 200, "max_daily_ai_calls 无效")
    return data


def load_config(path: Path | None = None) -> dict[str, Any]:
    target = path or paths.config_path()
    if not target.exists():
        data = default_config()
        save_config(data, target)
        return data
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"无法读取配置: {exc}") from exc
    audio = data.get("audio")
    migrated = False
    if isinstance(audio, dict):
        if audio.get("chime_file") in {
            "airport-chime.mp3",
            "gracesoundproductions-airport-announcement-call-chime-start-and-finish-342984.mp3",
        }:
            audio["chime_file"] = "hourly-chime.wav"
            migrated = True
        if audio.get("music_file") == "Japanese_Music.mp3":
            audio["music_file"] = "hourly-music.wav"
            migrated = True
    validated = validate_config(data)
    if migrated:
        save_config(validated, target)
    return validated


def save_config(data: dict[str, Any], path: Path | None = None) -> None:
    validate_config(data)
    target = path or paths.config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def new_credential_id() -> str:
    return str(uuid.uuid4())
