from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from . import audio, launchd, paths, providers, state
from .config import ConfigError, default_config, load_config, save_config, validate_config
from .runtime import JobLocked, run_play, run_refresh


def emit(payload: dict[str, Any], human: str | None = None, json_mode: bool = False) -> None:
    if json_mode:
        print(json.dumps({"schema_version": 1, **payload}, ensure_ascii=False))
    else:
        print(human or payload.get("message", "完成"))


def fail(code: str, message: str, json_mode: bool = False) -> int:
    emit({"ok": False, "error_code": code, "message": message}, json_mode=json_mode)
    return 1


def next_at(minute: int) -> str:
    now = datetime.now().astimezone()
    candidate = now.replace(minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(hours=1)
    return candidate.isoformat(timespec="minutes")


def command_status(args: argparse.Namespace) -> int:
    config = load_config()
    current_state = state.load_state()
    jobs = launchd.status()
    payload = {
        "ok": True,
        "enabled": jobs["play"] and jobs["refresh"],
        "jobs": jobs,
        "provider": config["provider"].get("preset") or config["provider"]["kind"],
        "next_play_at": next_at(0),
        "next_refresh_at": next_at(55),
        "last_play": current_state.get("last_play"),
        "last_refresh": current_state.get("last_refresh"),
        "cache_available": audio.validate_audio(paths.cache_audio_path()),
    }
    emit(payload, "已启用" if payload["enabled"] else "未启用", args.json)
    return 0


def command_enable(args: argparse.Namespace) -> int:
    launchd.enable()
    emit({"ok": True, "message": "整点播报已启用"}, json_mode=args.json)
    return 0


def command_disable(args: argparse.Namespace) -> int:
    launchd.disable()
    emit({"ok": True, "message": "整点播报已暂停"}, json_mode=args.json)
    return 0


def _play_named(kind: str) -> str:
    config = load_config()
    volume = float(config["audio"]["volume"])
    if kind == "chime":
        audio.play_file(paths.audio_dir() / config["audio"]["chime_file"], volume)
        return "整点提示音测试完成"
    if kind == "music":
        audio.play_file(paths.audio_dir() / config["audio"]["music_file"], volume)
        return "音乐测试完成"
    if kind == "voice":
        if audio.validate_audio(paths.cache_audio_path()):
            audio.play_file(paths.cache_audio_path(), volume)
        else:
            audio.say(config["audio"]["fallback_text"])
        return "语音测试完成"
    audio.play_file(paths.audio_dir() / config["audio"]["chime_file"], volume)
    if audio.validate_audio(paths.cache_audio_path()):
        audio.play_file(paths.cache_audio_path(), volume)
    else:
        audio.say(config["audio"]["fallback_text"])
    return "完整播放测试完成"


def command_test(args: argparse.Namespace) -> int:
    message = _play_named(args.kind)
    emit({"ok": True, "message": message}, json_mode=args.json)
    return 0


def command_refresh(args: argparse.Namespace) -> int:
    result = run_refresh(force=True)
    ok = result["status"] == "refreshed"
    emit({"ok": ok, **result}, json_mode=args.json)
    return 0 if ok else 1


def command_run(args: argparse.Namespace) -> int:
    result = run_play(allow_late=args.allow_late) if args.job == "play" else run_refresh(force=False)
    emit({"ok": result["status"] != "error", **result}, json_mode=args.json)
    return 0 if result["status"] != "error" else 1


def _provider_test_payload(raw: dict[str, Any]) -> dict[str, Any]:
    provider_config = raw.get("provider")
    template = raw.get("template")
    if not isinstance(provider_config, dict) or not isinstance(template, dict):
        raise ValueError("需要 provider 和 template")
    if template.get("language") not in {"zh", "en", "ja"} or not str(template.get("prompt", "")).strip():
        raise ValueError("模板提示词或语言无效")
    provider = providers.build_provider(provider_config, api_key_override=str(raw.get("api_key", "")) or None)
    generated = provider.generate(str(template["prompt"]), str(template["language"]))
    return {
        "ok": True,
        "provider": generated.provider,
        "model": generated.model,
        "latency_ms": generated.latency_ms,
        "sample_text": generated.text,
    }


def command_provider_test(args: argparse.Namespace) -> int:
    try:
        raw = json.load(sys.stdin)
        payload = _provider_test_payload(raw)
    except providers.ProviderError as exc:
        return fail(exc.code, str(exc), True)
    except (ValueError, json.JSONDecodeError) as exc:
        return fail("invalid_input", str(exc), True)
    emit(payload, json_mode=True)
    return 0


def command_config(args: argparse.Namespace) -> int:
    if args.action == "get":
        emit({"ok": True, "config": load_config()}, json_mode=True)
        return 0
    if args.action == "apply":
        try:
            data = json.load(sys.stdin)
            save_config(data)
        except (ConfigError, json.JSONDecodeError) as exc:
            return fail("invalid_config", str(exc), True)
        emit({"ok": True, "message": "配置已保存"}, json_mode=True)
        return 0
    validate_config(load_config())
    emit({"ok": True, "message": "配置有效"}, json_mode=args.json)
    return 0


def _codex_status() -> dict[str, Any]:
    executable = providers.resolve_codex_executable()
    if not executable:
        return {"available": False, "logged_in": False}
    try:
        result = subprocess.run(
            [executable, "login", "status"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        logged_in = result.returncode == 0 and "logged in" in (result.stdout + result.stderr).lower()
    except (OSError, subprocess.TimeoutExpired):
        logged_in = False
    return {"available": True, "logged_in": logged_in, "path": executable}


def command_doctor(args: argparse.Namespace) -> int:
    try:
        config = load_config()
        config_ok = True
        config_error = None
    except ConfigError as exc:
        config = default_config()
        config_ok = False
        config_error = str(exc)
    checks = {
        "config": {"ok": config_ok, "message": config_error},
        "python": {"ok": True, "path": sys.executable},
        "edge_tts": {"ok": importlib.util.find_spec("edge_tts") is not None},
        "openclaw": {"ok": bool(shutil.which("openclaw") or Path("/opt/homebrew/bin/openclaw").is_file())},
        "codex": _codex_status(),
        "chime_audio": {"ok": audio.validate_audio(paths.audio_dir() / config["audio"]["chime_file"])},
        "music_audio": {"ok": audio.validate_audio(paths.audio_dir() / config["audio"]["music_file"])},
        "cache": {"ok": audio.validate_audio(paths.cache_audio_path())},
        "launchd": launchd.status(),
    }
    required_ok = checks["config"]["ok"] and checks["edge_tts"]["ok"] and checks["chime_audio"]["ok"] and checks["music_audio"]["ok"]
    emit({"ok": required_ok, "checks": checks}, "诊断完成", args.json)
    return 0 if required_ok else 1


def command_logs(args: argparse.Namespace) -> int:
    log_path = paths.log_dir() / "hourly-chime.log"
    if args.follow:
        return subprocess.call(["/usr/bin/tail", "-f", str(log_path)])
    if not log_path.exists():
        print("暂无日志")
        return 0
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    print("\n".join(lines[-args.lines :]))
    return 0


def command_launchd_install(args: argparse.Namespace) -> int:
    written = launchd.write_plists()
    emit({"ok": True, "files": [str(path) for path in written]}, json_mode=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chimectl", description="Hourly Chime 控制与诊断")
    sub = parser.add_subparsers(dest="command", required=True)

    status_parser = sub.add_parser("status")
    status_parser.add_argument("--json", action="store_true")
    status_parser.set_defaults(func=command_status)
    for name, func in (("enable", command_enable), ("disable", command_disable)):
        item = sub.add_parser(name)
        item.add_argument("--json", action="store_true")
        item.set_defaults(func=func)

    test_parser = sub.add_parser("test")
    test_parser.add_argument("kind", choices=["chime", "voice", "music", "full"])
    test_parser.add_argument("--json", action="store_true")
    test_parser.set_defaults(func=command_test)

    refresh_parser = sub.add_parser("refresh")
    refresh_parser.add_argument("--json", action="store_true")
    refresh_parser.set_defaults(func=command_refresh)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("job", choices=["play", "refresh"])
    run_parser.add_argument("--allow-late", action="store_true")
    run_parser.add_argument("--json", action="store_true")
    run_parser.set_defaults(func=command_run)

    doctor_parser = sub.add_parser("doctor")
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.set_defaults(func=command_doctor)

    logs_parser = sub.add_parser("logs")
    logs_parser.add_argument("--follow", action="store_true")
    logs_parser.add_argument("--lines", type=int, default=100)
    logs_parser.set_defaults(func=command_logs)

    provider_parser = sub.add_parser("provider")
    provider_sub = provider_parser.add_subparsers(dest="provider_command", required=True)
    provider_test = provider_sub.add_parser("test")
    provider_test.add_argument("--stdin-json", action="store_true")
    provider_test.set_defaults(func=command_provider_test)

    config_parser = sub.add_parser("config")
    config_parser.add_argument("action", choices=["get", "apply", "validate"], default="validate", nargs="?")
    config_parser.add_argument("--json", action="store_true")
    config_parser.set_defaults(func=command_config)

    launchd_parser = sub.add_parser("launchd-install", help=argparse.SUPPRESS)
    launchd_parser.set_defaults(func=command_launchd_install)
    return parser


def main(argv: list[str] | None = None) -> int:
    paths.ensure_layout()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except JobLocked as exc:
        return fail("already_running", str(exc), getattr(args, "json", False))
    except (ConfigError, RuntimeError, OSError) as exc:
        return fail("runtime_error", str(exc), getattr(args, "json", False))


if __name__ == "__main__":
    raise SystemExit(main())
