# Hourly Chime (Mac 整点报时)

一个简单的 macOS 整点报时 Python 脚本，支持自定义播报文字、静音时段，并在特定时间播放音乐。

## 功能介绍

- **整点报时**：每小时自动播报当前时间。
- **音乐播放**：支持在特定时间（如每天下午 5 点）播放指定的 MP3 音乐文件。
- **勿扰模式 (DND)**：可以设置静音时段（默认 22:00 - 08:00）。
- **后台运行**：提供 `.plist` 配置文件，支持作为 macOS Launch Agent 在后台静默运行。

## 文件组成

- `hourly_chime.py`: 核心脚本。
- `com.user.hourlychime.plist`: macOS 后台服务配置文件。
- `Japanese_Music.mp3`: 5 点整播放的音乐文件。
- `.gitignore`: 忽略系统无用文件。

## 如何使用

### 1. 直接运行 (测试)
```bash
python3 hourly_chime.py
```

### 2. 测试特定功能
- 测试语音播报：`python3 hourly_chime.py --test`
- 测试 5 点音乐播放：`python3 hourly_chime.py --test-music`

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
- `VOICE`: 使用的语音包。
- `MUSIC_HOUR`: 播放音乐的小时。
