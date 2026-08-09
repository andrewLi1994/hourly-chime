#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:A:h}
USER_HOME=$(dscl . -read /Users/$(id -un) NFSHomeDirectory | awk '{print $2}')
APP_HOME="$USER_HOME/Library/Application Support/HourlyChime"
TARGET_APP="$USER_HOME/Applications/Hourly Chime.app"
DESKTOP_LINK="$USER_HOME/Desktop/Hourly Chime.app"
LAUNCH_AGENT_DIR="$USER_HOME/Library/LaunchAgents"

if [[ -x "$APP_HOME/venv/bin/chimectl" ]]; then
  "$APP_HOME/venv/bin/chimectl" disable >/dev/null 2>&1 || true
fi

rm -f "$LAUNCH_AGENT_DIR/com.andrewli.hourlychime.play.plist"
rm -f "$LAUNCH_AGENT_DIR/com.andrewli.hourlychime.refresh.plist"
rm -f "$DESKTOP_LINK"
rm -rf "$TARGET_APP"

if [[ "${1:-}" == "--purge" ]]; then
  EXPECTED="$USER_HOME/Library/Application Support/HourlyChime"
  [[ "$APP_HOME" == "$EXPECTED" ]] || { print -u2 "拒绝清理非预期目录"; exit 2; }
  rm -rf "$APP_HOME"
  print "应用与用户数据已删除。"
else
  print "应用已删除；配置、缓存和日志仍保留在：$APP_HOME"
fi
