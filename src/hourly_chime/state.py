from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

from . import paths


def default_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "last_template_id": None,
        "last_play": None,
        "last_refresh": None,
        "daily_usage": {"date": date.today().isoformat(), "count": 0},
    }


def load_state(path: Path | None = None) -> dict[str, Any]:
    target = path or paths.state_path()
    if not target.exists():
        return default_state()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_state()
    if data.get("schema_version") != 1:
        return default_state()
    today = date.today().isoformat()
    if data.get("daily_usage", {}).get("date") != today:
        data["daily_usage"] = {"date": today, "count": 0}
    return data


def save_state(data: dict[str, Any], path: Path | None = None) -> None:
    target = path or paths.state_path()
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


def event(status: str, message: str, **extra: Any) -> dict[str, Any]:
    result = {
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "message": message,
    }
    result.update(extra)
    return result
