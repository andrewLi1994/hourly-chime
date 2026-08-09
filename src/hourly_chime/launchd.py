from __future__ import annotations

import html
import os
import subprocess
from pathlib import Path

from . import paths


PLAY_LABEL = "com.andrewli.hourlychime.play"
REFRESH_LABEL = "com.andrewli.hourlychime.refresh"


def plist_path(label: str) -> Path:
    return paths.launch_agents_dir() / f"{label}.plist"


def _plist(label: str, minute: int, job: str) -> str:
    chimectl = html.escape(str(paths.venv_chimectl_path()))
    working = html.escape(str(paths.app_home()))
    stdout = html.escape(str(paths.log_dir() / f"{job}.stdout.log"))
    stderr = html.escape(str(paths.log_dir() / f"{job}.stderr.log"))
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{chimectl}</string>
        <string>run</string>
        <string>{job}</string>
    </array>
    <key>WorkingDirectory</key><string>{working}</string>
    <key>StartCalendarInterval</key>
    <dict><key>Minute</key><integer>{minute}</integer></dict>
    <key>ProcessType</key><string>Background</string>
    <key>LowPriorityIO</key><true/>
    <key>KeepAlive</key><false/>
    <key>StandardOutPath</key><string>{stdout}</string>
    <key>StandardErrorPath</key><string>{stderr}</string>
</dict>
</plist>
'''


def write_plists() -> list[Path]:
    paths.ensure_layout()
    paths.launch_agents_dir().mkdir(parents=True, exist_ok=True)
    specs = [(PLAY_LABEL, 0, "play"), (REFRESH_LABEL, 55, "refresh")]
    written: list[Path] = []
    for label, minute, job in specs:
        target = plist_path(label)
        target.write_text(_plist(label, minute, job), encoding="utf-8")
        written.append(target)
    return written


def is_loaded(label: str) -> bool:
    result = subprocess.run(
        ["/bin/launchctl", "print", f"gui/{os.getuid()}/{label}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def enable() -> None:
    written = write_plists()
    for label, target in zip((PLAY_LABEL, REFRESH_LABEL), written, strict=True):
        if is_loaded(label):
            continue
        result = subprocess.run(
            ["/bin/launchctl", "bootstrap", f"gui/{os.getuid()}", str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"无法加载 {label}")


def disable() -> None:
    for label in (PLAY_LABEL, REFRESH_LABEL):
        if not is_loaded(label):
            continue
        result = subprocess.run(
            ["/bin/launchctl", "bootout", f"gui/{os.getuid()}/{label}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"无法停止 {label}")


def status() -> dict[str, bool]:
    return {"play": is_loaded(PLAY_LABEL), "refresh": is_loaded(REFRESH_LABEL)}
