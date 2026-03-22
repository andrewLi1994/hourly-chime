# Hourly Chime (Mac 整点报时)

一个简单的 macOS 整点报时 Python 脚本，支持静音时段，并在整点播放机场提示音及 AI 喝水提醒，特定时间播放音乐。

- **高质量 AI 语音报时**：集成 Microsoft Edge TTS (Azure Neural Voices)，提供媲美真人的自然语音播报。
- **自动语言识别**：脚本自动识别 AI 提醒内容的语言（中、英、日），并无缝切换对应最自然的人声。
- **零延迟播报**：引入音频预缓存（Pre-caching）机制，在后台提前生成语音 MP3，整点报时瞬间响起，彻底消除网络生成的延迟感。
- **机场提示音**：每小时报时前播放经典的机场风格提示音。
- **音乐播放**：支持在特定时间（如每天下午 5 点）播放指定的 MP3 音乐文件。
- **勿扰模式 (DND)**：可灵活设置静音时段（默认 22:00 - 08:00）。
- **后台运行**：提供 `.plist` 配置支持作为 macOS Launch Agent 在后台常驻。

## 环境要求

- **macOS**: 使用系统自带的 `afplay` 指令播放音频。
- **Python 3**: 脚本执行环境。
- **Python 库**: `pip3 install edge-tts`
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
你可以在 `hourly_chime.py` 的配置部分修改：
- `DND_START` & `DND_END`: 静音时段。
- `VOICES`: 设置中、英、日三种语言对应的 Edge TTS 角色（默认已选择最佳组合）。
- `MUSIC_HOUR`: 播放音乐的小时。
