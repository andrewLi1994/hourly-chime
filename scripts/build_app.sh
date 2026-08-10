#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:A:h}
PROJECT_ROOT=${SCRIPT_DIR:h}
PACKAGE_DIR="$PROJECT_ROOT/ui/HourlyChimeApp"
BUILD_ROOT="$PROJECT_ROOT/.build/swift-release"
APP_BUNDLE="$PROJECT_ROOT/dist/Hourly Chime.app"
SDK_PATH="/Library/Developer/CommandLineTools/SDKs/MacOSX15.5.sdk"

if [[ ! -d "$SDK_PATH" ]]; then
  SDK_PATH=$(xcrun --sdk macosx --show-sdk-path)
fi

export SDKROOT="$SDK_PATH"
export CLANG_MODULE_CACHE_PATH="$PROJECT_ROOT/.build/clang-module-cache"
export SWIFTPM_MODULECACHE_OVERRIDE="$PROJECT_ROOT/.build/swift-module-cache"

"$SCRIPT_DIR/make_icon.sh" >/dev/null
swift build -c release --package-path "$PACKAGE_DIR" --scratch-path "$BUILD_ROOT"

EXECUTABLE=$(find "$BUILD_ROOT" -type f -path '*/release/HourlyChimeApp' -perm +111 -print -quit)
KEYCHAIN_HELPER=$(find "$BUILD_ROOT" -type f -path '*/release/HourlyChimeKeychainHelper' -perm +111 -print -quit)
[[ -n "$EXECUTABLE" ]] || { print -u2 "找不到 Swift release 可执行文件"; exit 1; }
[[ -n "$KEYCHAIN_HELPER" ]] || { print -u2 "找不到 Keychain Helper 可执行文件"; exit 1; }

mkdir -p "$APP_BUNDLE/Contents/MacOS" "$APP_BUNDLE/Contents/Resources" "$APP_BUNDLE/Contents/Helpers"
cp "$EXECUTABLE" "$APP_BUNDLE/Contents/MacOS/HourlyChimeApp"
cp "$KEYCHAIN_HELPER" "$APP_BUNDLE/Contents/Helpers/HourlyChimeKeychainHelper"
cp "$PACKAGE_DIR/Info.plist" "$APP_BUNDLE/Contents/Info.plist"
cp "$PROJECT_ROOT/assets/AppIcon.icns" "$APP_BUNDLE/Contents/Resources/AppIcon.icns"
codesign --force --sign - --identifier com.andrewli.hourlychime.keychain-helper "$APP_BUNDLE/Contents/Helpers/HourlyChimeKeychainHelper" >/dev/null
codesign --force --deep --sign - "$APP_BUNDLE" >/dev/null
print "$APP_BUNDLE"
