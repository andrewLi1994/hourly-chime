#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:A:h}
PROJECT_ROOT=${SCRIPT_DIR:h}
SOURCE_ICON="$PROJECT_ROOT/assets/AppIcon-1024.png"
ICONSET_DIR="$PROJECT_ROOT/.build/AppIcon.iconset"
OUTPUT_ICON="$PROJECT_ROOT/assets/AppIcon.icns"

[[ -f "$SOURCE_ICON" ]] || { print -u2 "缺少 $SOURCE_ICON"; exit 1; }
mkdir -p "$ICONSET_DIR"
sips -z 1024 1024 "$SOURCE_ICON" --out "$SOURCE_ICON" >/dev/null

for spec in \
  "16 icon_16x16.png" \
  "32 icon_16x16@2x.png" \
  "32 icon_32x32.png" \
  "64 icon_32x32@2x.png" \
  "128 icon_128x128.png" \
  "256 icon_128x128@2x.png" \
  "256 icon_256x256.png" \
  "512 icon_256x256@2x.png" \
  "512 icon_512x512.png" \
  "1024 icon_512x512@2x.png"; do
  size=${spec%% *}
  name=${spec#* }
  sips -z "$size" "$size" "$SOURCE_ICON" --out "$ICONSET_DIR/$name" >/dev/null
done

if ! iconutil -c icns "$ICONSET_DIR" -o "$OUTPUT_ICON" 2>/dev/null; then
  # Some Command Line Tools 26 builds reject otherwise valid iconsets. Pillow
  # writes the same multi-resolution ICNS container as a deterministic fallback.
  python3 "$SCRIPT_DIR/make_icns.py" "$SOURCE_ICON" "$OUTPUT_ICON"
fi
print "$OUTPUT_ICON"
