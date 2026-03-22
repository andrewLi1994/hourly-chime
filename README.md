# Hourly Chime (Mac 整点报时)

一个简单的 macOS 整点报时 Python 脚本，支持静音时段，并在整点播放机场提示音及 AI 喝水提醒，特定时间播放音乐。

## 功能介绍

- **机场提示音报时**：每小时自动播放机场风格的提示音，代替传统的时间播报。
- **AI 喝水提醒**：提示音播放后，通过 OpenClaw Agent 获取一句有趣的英文喝水提醒。
- **音乐播放**：支持在特定时间（如每天下午 5 点）播放指定的 MP3 音乐文件。
- **勿扰模式 (DND)**：可以设置静音时段（默认 22:00 - 08:00）。
- **后台运行**：提供 `.plist` 配置文件，支持作为 macOS Launch Agent 在后台运行。

## 环境要求

- **macOS**: 使用系统自带的 `say` 和 `afplay` 指令。
- **Python 3**: 脚本执行环境。
- **OpenClaw CLI**: 用于生成 AI 提醒。请确保已安装并配置好 `main` 代理。

## 文件组成

- `hourly_chime.py`: 核心脚本。
- `com.user.hourlychime.plist`: macOS 后台服务配置文件。
- `Japanese_Music.mp3`: 17:00 播放的音乐文件。
- `gracesoundproductions-airport-announcement-call-...mp3`: 机场提示音文件。
- `.gitignore`: 忽略系统无用文件。

## 如何使用

### 1. 直接运行 (测试)
```bash
python3 hourly_chime.py
```

### 2. 测试特定功能
- 测试整体流程（提示音 + AI 提醒）：`python3 hourly_chime.py --test`
- 测试点位音乐播放：`python3 hourly_chime.py --test-music`

### 3. 设置为后台自动运行 (Launch Agent)
1. 修改 `com.user.hourlychime.plist` 中的文件路径为你的实际路径。
2. 将该文件复制到 `~/Library/LaunchAgents/`：
   ```bash
   cp com.user.hourlychime.plist ~/Library/LaunchAgents/
   ```
3. 加载并启动：
   ```bash
   launchctl load ~/Library/LaunchAgents/com.user.hourlychime.plist
   ```

## 配置说明
你可以在 `hourly_chime.py` 的 `--- 配置 ---` 部分修改：
- `DND_START` & `DND_END`: 静音时段。
- `SPEECH_RATE`: 语速。
- `VOICE`: 使用的语音包（如 `Mei-Jia`）。
- `MUSIC_HOUR`: 播放音乐的小时。
