#!/bin/bash

# --- 这里的脚本旨在测试 macOS 的音频输出是否正常 ---

echo "=== 1. 测试系统音效 (Glass.aiff) ==="
afplay /System/Library/Sounds/Glass.aiff
if [ $? -eq 0 ]; then
    echo "系统音效播放成功。"
else
    echo "系统音效播放失败，请检查音量或输出设备。"
fi

echo -e "\n=== 2. 测试系统语音 (say) ==="
say "Hello, this is a test of the macOS speech system."
if [ $? -eq 0 ]; then
    echo "系统语音执行成功。"
else
    echo "系统语音执行失败。"
fi

echo -e "\n=== 3. 检查当前音量设置 ==="
osascript -e "get volume settings"

echo -e "\n=== 提示 ==="
echo "如果你听不到任何声音："
echo "1. 检查菜单栏的“声音”图标，确认输出设备是“扬声器”而不是耳机或 Apple TV。"
echo "2. 确认静音没有开启。"
echo "3. 检查‘系统设置 -> 声音’中的主音量。"
