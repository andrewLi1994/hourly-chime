#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:A:h}
PROJECT_ROOT=${SCRIPT_DIR:h}
USER_HOME=$(dscl . -read /Users/$(id -un) NFSHomeDirectory | awk '{print $2}')
APP_HOME="$USER_HOME/Library/Application Support/HourlyChime"
VENV_DIR="$APP_HOME/venv"
TARGET_APP="$USER_HOME/Applications/Hourly Chime.app"
SOURCE_APP="$PROJECT_ROOT/dist/Hourly Chime.app"
DESKTOP_LINK="$USER_HOME/Desktop/Hourly Chime.app"
CHIME_SOURCE="$PROJECT_ROOT/assets/audio/hourly-chime.wav"
MUSIC_SOURCE="$PROJECT_ROOT/assets/audio/hourly-music.wav"

mkdir -p "$APP_HOME/audio" "$APP_HOME/cache" "$APP_HOME/logs" "$APP_HOME/locks" "$APP_HOME/codex-workspace" "$USER_HOME/Applications"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  /opt/homebrew/bin/python3 -m venv --system-site-packages "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install --no-deps "$PROJECT_ROOT"
if ! "$VENV_DIR/bin/python" -c 'import edge_tts' 2>/dev/null; then
  "$VENV_DIR/bin/python" -m pip install 'edge-tts==7.2.8'
fi

if [[ ! -f "$CHIME_SOURCE" || ! -f "$MUSIC_SOURCE" ]]; then
  python3 "$SCRIPT_DIR/generate_audio.py" "$PROJECT_ROOT" >/dev/null
fi
[[ -f "$APP_HOME/audio/hourly-chime.wav" ]] || cp "$CHIME_SOURCE" "$APP_HOME/audio/hourly-chime.wav"
[[ -f "$APP_HOME/audio/hourly-music.wav" ]] || cp "$MUSIC_SOURCE" "$APP_HOME/audio/hourly-music.wav"
if [[ ! -f "$APP_HOME/cache/reminder.mp3" && -f "$PROJECT_ROOT/reminder_cache.mp3" ]]; then
  cp "$PROJECT_ROOT/reminder_cache.mp3" "$APP_HOME/cache/reminder.mp3"
fi

"$VENV_DIR/bin/chimectl" config validate >/dev/null
"$VENV_DIR/bin/chimectl" launchd-install >/dev/null

if [[ ! -d "$SOURCE_APP" ]]; then
  "$SCRIPT_DIR/build_app.sh" >/dev/null
fi
if [[ -e "$TARGET_APP" ]]; then
  print -u2 "未覆盖已有应用：$TARGET_APP"
else
  ditto "$SOURCE_APP" "$TARGET_APP"
fi
if [[ ! -e "$DESKTOP_LINK" ]]; then
  ln -s "$TARGET_APP" "$DESKTOP_LINK"
fi

print "安装完成，但播报仍保持禁用。"
print "先运行：$VENV_DIR/bin/chimectl doctor --json"
