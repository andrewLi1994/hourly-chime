# Hourly Chime

macOS 低 RAM 整点播报工具。后台没有常驻 Python 循环：`launchd` 在每小时 `:00` 启动一次播放任务，在 `:55` 启动一次缓存任务，任务完成后进程退出。

## 默认行为

- 22:00–08:00 静音，可在原生 SwiftUI 的 24 小时环形表盘中调整。
- 17:00 只播放项目生成的短音乐。
- 其余整点播放项目生成的提示音，再播放已生成的提醒缓存。
- 播放任务绝不联网；缓存坏掉时使用 macOS `say` 的固定提醒。
- 缓存失败会保留上一次有效 MP3，整点任务迟到超过 3 分钟会静默跳过。

## 安装

```zsh
./scripts/build_app.sh
./scripts/install.sh
```

安装器会创建独立 venv、两个 `KeepAlive=false` LaunchAgent、运行目录、`~/Applications/Hourly Chime.app` 和桌面快捷方式。安装后默认不启用，先完成诊断、音频、Provider 和首个缓存测试：

```zsh
CHIMECTL="$HOME/Library/Application Support/HourlyChime/venv/bin/chimectl"
"$CHIMECTL" doctor --json
"$CHIMECTL" test full
"$CHIMECTL" provider test --stdin-json
"$CHIMECTL" refresh
"$CHIMECTL" enable
```

应用不会覆盖 `~/Applications` 中已有的同名应用。卸载默认保留配置和缓存：

```zsh
./scripts/uninstall.sh
./scripts/uninstall.sh --purge  # 明确删除全部用户数据
```

## 稳定 CLI

```text
chimectl status [--json]
chimectl enable|disable
chimectl test chime|voice|music|full
chimectl refresh
chimectl doctor [--json]
chimectl logs [--follow]
chimectl provider test --stdin-json
chimectl config get|apply|validate
chimectl run play|refresh
```

运行文件位于 `~/Library/Application Support/HourlyChime`：

```text
config.json          非密钥配置
state.json           最近任务、模板、Provider、耗时与错误
audio/               项目生成的提示音与短音乐
cache/               原子替换的提醒 MP3 与元数据
logs/                1 MiB × 5 滚动日志
venv/                独立 Python 环境
codex-workspace/     Codex 隔离空目录
```

Gemini、NVIDIA 和 Custom 的 API Key 存入 macOS Keychain；JSON 只保留随机 `credential_id`。原生 Keychain Helper 自己读取密钥并完成 HTTPS 请求，Python 只能收到生成后的提醒文本，不调用 `/usr/bin/security`，因此后台刷新不会反复弹出钥匙串授权框。Helper 固定从本地配置读取 Provider 地址，Custom 非本机地址必须使用 HTTPS。Codex Provider 使用当前登录的 Codex CLI、stdin 提示词、临时会话、只读沙箱、忽略用户配置/规则及 JSON Schema 输出；`chimectl doctor` 只检查登录状态，不读取或显示 `auth.json`。

## 开发验证

```zsh
PYTHONPATH=src python3 -m unittest discover -s tests -v
SDKROOT=/Library/Developer/CommandLineTools/SDKs/MacOSX15.5.sdk swift build --package-path ui/HourlyChimeApp
```

本机 Command Line Tools 26.0 的默认 SDK 与 Swift 编译器补丁版本不一致；构建脚本会优先选用同机可用、且能被 Swift 6.2 编译的 macOS 15.5 SDK。目标系统仍为 macOS 14 及以上。

## 音频来源

仓库内的 `assets/audio/hourly-chime.wav` 与 `hourly-music.wav` 由
`scripts/generate_audio.py` 使用纯数学波形确定性生成，不包含采样、录音或第三方音频。
执行该脚本可以重建完全相同的 WAV 文件。早期来源不明的 MP3 已从当前版本以及分支、标签可达的 Git 历史中移除。

旧的 `hourly_chime.py` 仅作兼容入口，不再运行全天循环；旧的常驻 LaunchAgent plist 已删除。
