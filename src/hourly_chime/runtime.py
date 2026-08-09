from __future__ import annotations

import fcntl
import json
import os
import random
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from . import audio, paths, providers, state
from .config import load_config
from .logging_utils import get_logger


logger = get_logger("hourly_chime.runtime")


class JobLocked(RuntimeError):
    pass


@contextmanager
def job_lock(name: str) -> Iterator[None]:
    paths.ensure_layout()
    lock_path = paths.lock_dir() / f"{name}.lock"
    handle = lock_path.open("a+")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise JobLocked(f"{name} 已在运行") from exc
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def minute_of_day(moment: datetime) -> int:
    return moment.hour * 60 + moment.minute


def is_dnd(moment: datetime, config: dict[str, Any]) -> bool:
    dnd = config["schedule"]["dnd"]
    if not dnd["enabled"]:
        return False
    current = minute_of_day(moment)
    start = int(dnd["start_minute"])
    end = int(dnd["end_minute"])
    if start < end:
        return start <= current < end
    return current >= start or current < end


def next_whole_hour(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


def should_refresh_for(moment: datetime, config: dict[str, Any]) -> bool:
    return not is_dnd(moment, config) and moment.hour != config["schedule"]["music_hour"]


def select_template(
    templates: list[dict[str, Any]],
    last_template_id: str | None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    available = [template for template in templates if template.get("enabled")]
    if not available:
        raise ValueError("没有启用的提醒模板")
    choices = [item for item in available if item["id"] != last_template_id] or available
    return (rng or random.SystemRandom()).choice(choices)


def _audio_path(filename: str) -> Path:
    return paths.audio_dir() / filename


def _save_cache_metadata(data: dict[str, Any]) -> None:
    target = paths.cache_metadata_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def run_play(now: datetime | None = None, allow_late: bool = False) -> dict[str, Any]:
    moment = now or datetime.now().astimezone()
    config = load_config()
    current_state = state.load_state()
    with job_lock("play"):
        tolerance = config["schedule"]["late_tolerance_minutes"]
        if not allow_late and moment.minute > tolerance:
            result = state.event("skipped_late", "启动时间超过允许窗口", minute=moment.minute)
            current_state["last_play"] = result
            state.save_state(current_state)
            logger.info("播放任务迟到，静默跳过 minute=%s", moment.minute)
            return result
        if is_dnd(moment, config):
            result = state.event("skipped_dnd", "当前处于静音时段")
            current_state["last_play"] = result
            state.save_state(current_state)
            logger.info("当前处于静音时段，跳过播放")
            return result

        volume = float(config["audio"]["volume"])
        try:
            if moment.hour == config["schedule"]["music_hour"]:
                audio.play_file(_audio_path(config["audio"]["music_file"]), volume)
                result = state.event("played_music", "特殊音乐播放完成")
            else:
                audio.play_file(_audio_path(config["audio"]["chime_file"]), volume)
                if audio.validate_audio(paths.cache_audio_path()):
                    audio.play_file(paths.cache_audio_path(), volume)
                    result = state.event("played_cache", "整点提示音和缓存提醒播放完成")
                else:
                    audio.say(config["audio"]["fallback_text"])
                    result = state.event("played_fallback", "缓存不可用，已使用系统语音")
        except Exception as exc:
            logger.exception("播放任务失败")
            result = state.event("error", str(exc)[:300])
        current_state["last_play"] = result
        state.save_state(current_state)
        return result


def run_refresh(
    force: bool = False,
    now: datetime | None = None,
    config_override: dict[str, Any] | None = None,
    api_key_override: str | None = None,
) -> dict[str, Any]:
    moment = now or datetime.now().astimezone()
    config = config_override or load_config()
    current_state = state.load_state()
    with job_lock("refresh"):
        target = next_whole_hour(moment)
        if not force and not should_refresh_for(target, config):
            result = state.event("skipped_schedule", "下一整点无需生成语音", target=target.isoformat())
            current_state["last_refresh"] = result
            state.save_state(current_state)
            return result

        usage = current_state.setdefault("daily_usage", {})
        today = moment.date().isoformat()
        if usage.get("date") != today:
            usage.update({"date": today, "count": 0})
        max_calls = config["limits"]["max_daily_ai_calls"]
        if not force and int(usage.get("count", 0)) >= max_calls:
            result = state.event("skipped_limit", "已达到每日 AI 调用上限")
            current_state["last_refresh"] = result
            state.save_state(current_state)
            return result

        template = select_template(config["templates"], current_state.get("last_template_id"))
        try:
            provider = providers.build_provider(config["provider"], api_key_override=api_key_override)
            logger.info("开始刷新缓存 template_id=%s provider=%s", template["id"], config["provider"].get("preset") or config["provider"].get("kind"))
            generated = provider.generate(template["prompt"], template["language"])
            usage["count"] = int(usage.get("count", 0)) + 1
            voice = config["audio"]["voices"][template["language"]]
            audio.synthesize_atomic(generated.text, voice, paths.cache_audio_path())
            metadata = {
                "schema_version": 1,
                "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "template_id": template["id"],
                "template_name": template["name"],
                "language": template["language"],
                "text": generated.text,
                "provider": generated.provider,
                "model": generated.model,
                "latency_ms": generated.latency_ms,
            }
            _save_cache_metadata(metadata)
            current_state["last_template_id"] = template["id"]
            result = state.event(
                "refreshed",
                "语音缓存已更新",
                template_id=template["id"],
                provider=generated.provider,
                model=generated.model,
                latency_ms=generated.latency_ms,
            )
            logger.info("缓存刷新完成 template_id=%s provider=%s latency_ms=%s", template["id"], generated.provider, generated.latency_ms)
        except providers.ProviderError as exc:
            logger.warning("Provider 刷新失败 code=%s message=%s", exc.code, exc)
            result = state.event("error", str(exc)[:300], error_code=exc.code)
        except Exception as exc:
            logger.exception("缓存刷新失败")
            result = state.event("error", str(exc)[:300], error_code="refresh_error")
        current_state["last_refresh"] = result
        state.save_state(current_state)
        return result
