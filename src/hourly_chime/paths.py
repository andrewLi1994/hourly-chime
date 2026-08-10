from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "HourlyChime"
BUNDLE_ID = "com.andrewli.hourlychime"


def app_home() -> Path:
    override = os.environ.get("HOURLY_CHIME_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / "Library" / "Application Support" / APP_NAME


def config_path() -> Path:
    return app_home() / "config.json"


def state_path() -> Path:
    return app_home() / "state.json"


def cache_dir() -> Path:
    return app_home() / "cache"


def cache_audio_path() -> Path:
    return cache_dir() / "reminder.mp3"


def cache_metadata_path() -> Path:
    return cache_dir() / "reminder.json"


def audio_dir() -> Path:
    return app_home() / "audio"


def log_dir() -> Path:
    return app_home() / "logs"


def lock_dir() -> Path:
    return app_home() / "locks"


def codex_workspace() -> Path:
    return app_home() / "codex-workspace"


def bin_dir() -> Path:
    return app_home() / "bin"


def keychain_helper_path() -> Path:
    override = os.environ.get("HOURLY_CHIME_KEYCHAIN_HELPER")
    if override:
        return Path(override).expanduser().resolve()
    return bin_dir() / "hourly-chime-keychain"


def launch_agents_dir() -> Path:
    override = os.environ.get("HOURLY_CHIME_LAUNCH_AGENTS")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / "Library" / "LaunchAgents"


def venv_chimectl_path() -> Path:
    return app_home() / "venv" / "bin" / "chimectl"


def ensure_layout() -> None:
    for path in (app_home(), cache_dir(), audio_dir(), log_dir(), lock_dir(), codex_workspace(), bin_dir()):
        path.mkdir(parents=True, exist_ok=True)
