import subprocess
import time
from datetime import datetime
import sys
import os
import json
import re
import threading
import asyncio
import edge_tts
import tempfile

# --- 配置 ---
# 静音时段 (小时, 24小时制)
# 例如：22 表示晚上 10 点，8 表示早上 8 点
# 如果当前小时在 [DND_START, DND_END) 范围内，则不报时
DND_START = 22  # 22:00 开始静音
DND_END = 8     # 08:00 结束静音

# --- 默认语音配置 (支持中英日自动切换) ---
VOICES = {
    "zh": "zh-CN-XiaoxiaoNeural",
    "en": "en-US-AvaNeural",
    "ja": "ja-JP-NanamiNeural"
}

# 机场整点报时音 (文件名较长，建议保持原样或重命名)
CHIME_AUDIO = "gracesoundproductions-airport-announcement-call-chime-start-and-finish-342984.mp3"

# 5 点整播放的音乐设置
MUSIC_FILE = "Japanese_Music.mp3"
MUSIC_HOUR = 17  # 17:00 是下午 5 点

def get_voice_for_text(text):
    """根据文本内容自动选择最合适的语音"""
    # 检查是否包含日语假名 (Hiragana/Katakana)
    if re.search(r'[\u3040-\u309F\u30A0-\u30FF]', text):
        return VOICES["ja"]
    # 检查是否包含中文字符
    if re.search(r'[\u4E00-\u9FFF]', text):
        return VOICES["zh"]
    # 默认使用英文
    return VOICES["en"]

async def generate_speech(text, voice, output_file):
    """异步生成语音文件"""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

def speak(text):
    """调用 Edge TTS 播放语音 (优先使用预生成的缓存)"""
    global cached_audio_path
    
    with cache_lock:
        # 必须文本内容完全匹配且文件存在，才使用缓存
        if cached_reminder == text and cached_audio_path and os.path.exists(cached_audio_path):
            print(f"使用预生成缓存播报...")
            try:
                subprocess.run(["afplay", cached_audio_path], check=True)
                return
            except Exception as e:
                print(f"缓存播放失败: {e}")

    # Fallback: 如果没有缓存，则现场生成 (现有逻辑)
    voice = get_voice_for_text(text)
    print(f"无缓存，正在现场生成语音 [{voice}] 播报: {text}")
    
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
        tmp_path = tmp_file.name
        
    try:
        asyncio.run(generate_speech(text, voice, tmp_path))
        subprocess.run(["afplay", tmp_path], check=True)
    except Exception as e:
        print(f"播报失败: {e}")
        try:
            subprocess.run(["say", text])
        except:
            pass
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def play_music(file_path):
    """调用 macOS 'afplay' 命令播放音乐"""
    if not os.path.exists(file_path):
        print(f"错误: 找不到音乐文件: {file_path}")
        return
    
    print(f"正在播放音乐: {os.path.basename(file_path)}")
    try:
        subprocess.run(["afplay", file_path], check=True)
    except subprocess.CalledProcessError as e:
        print(f"音乐播放失败: {e}")
    except FileNotFoundError:
        print("错误: 找不到 'afplay' 命令。")

def get_ai_reminder():
    """使用 OpenClaw CLI 调用 main 代理获取 AI 喝水提醒"""
    print("正在通过 OpenClaw Agent 获取 AI 喝水提醒...")
    cmd = [
        "openclaw", "agent", 
        "--agent", "main", 
        "--message", "Give me a short, simple and fun English ONLY reminder to drink water. One sentence only, and don't use any emojis and name.", 
        "--json"
    ]
    try:
        # 设置 20 秒超时
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            # 从 JSON 路径中提取文本 (data['result']['payloads'][0]['text'])
            try:
                text = data['result']['payloads'][0]['text']
                # 清理 Markdown 符号（如 * _ #），防止 say 读出这些符号
                return re.sub(r'[*_#]', '', text).strip()
            except (KeyError, IndexError):
                print("解析 AI 响应失败，数据格式可能不匹配。")
        else:
            print(f"OpenClaw Agent 返回错误: {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        print("获取 AI 提醒超时。")
    except Exception as e:
        print(f"AI 获取失败: {e}")
    
    return "Time to stay hydrated and drink some water."

# --- 缓存系统 ---
cached_reminder = None
cached_audio_path = None
cache_lock = threading.RLock()

def update_cache():
    """异步更新 AI 提醒缓存（文本 + 音频）"""
    global cached_reminder, cached_audio_path
    
    # 1. 获取文字提醒
    new_reminder = get_ai_reminder()
    
    # 2. 预生成音频文件
    voice = get_voice_for_text(new_reminder)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 使用固定名称的缓存文件
    new_audio_path = os.path.join(script_dir, "reminder_cache.mp3")
    
    try:
        print(f"正在预生成音频缓存 [{voice}]...")
        asyncio.run(generate_speech(new_reminder, voice, new_audio_path))
        
        with cache_lock:
            cached_reminder = new_reminder
            cached_audio_path = new_audio_path
        print(f"缓存已更新 (文本+音频): {cached_reminder}")
        
    except Exception as e:
        print(f"预生成音频失败: {e}")
        with cache_lock:
            cached_reminder = new_reminder
            cached_audio_path = None


def is_dnd_time():
    """判断是否在勿扰模式内"""
    now = datetime.now()
    hour = now.hour
    
    if DND_START > DND_END:
        # 跨午夜的情况 (如 22点 到 8点)
        return hour >= DND_START or hour < DND_END
    else:
        # 同一天的情况 (如 1点 到 5点)
        return DND_START <= hour < DND_END

def main():
    # 测试模式：直接报时并退出
    if "--test" in sys.argv:
        print("--- 测试模式 ---")
        # 确保有缓存
        if not cached_reminder:
            print("正在获取测试提醒...")
            update_cache()
            
        # 播放机场提示音
        script_dir = os.path.dirname(os.path.abspath(__file__))
        chime_path = os.path.join(script_dir, CHIME_AUDIO)
        play_music(chime_path)
        
        # 立即使用缓存播报
        current_reminder = "Time to stay hydrated."
        with cache_lock:
            if cached_reminder:
                current_reminder = cached_reminder
        
        speak(current_reminder)
        return

    # 音乐播放测试
    if "--test-music" in sys.argv:
        print("--- 音乐播放测试 ---")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        music_path = os.path.join(script_dir, MUSIC_FILE)
        play_music(music_path)
        return

    print("整点报时脚本已启动...")
    print(f"勿扰模式设置: {DND_START:02d}:00 - {DND_END:02d}:00")
    print(f"5 点整特殊播报: {MUSIC_FILE}")
    
    # 启动时后台异步预加载第一次提醒
    print("正在启动首次 AI 提醒预加载 (后台)...")
    threading.Thread(target=update_cache, daemon=True).start()
    
    last_chime_hour = -1
    
    try:
        while True:
            now = datetime.now()
            current_hour = now.hour
            current_minute = now.minute
            
            # 判断是否到了整点且这一小时还没报过
            if current_minute == 0 and current_hour != last_chime_hour:
                if not is_dnd_time():
                    if current_hour == MUSIC_HOUR:
                        # 5 点整播放音乐
                        script_dir = os.path.dirname(os.path.abspath(__file__))
                        music_path = os.path.join(script_dir, MUSIC_FILE)
                        play_music(music_path)
                    else:
                        # 核心逻辑：即时播放缓存内容，然后后台更新下一条
                        script_dir = os.path.dirname(os.path.abspath(__file__))
                        chime_path = os.path.join(script_dir, CHIME_AUDIO)
                        
                        # 1. 播放提示音 (阻塞)
                        play_music(chime_path)
                        
                        # 2. 立即从缓存播报 AI 提醒 (零延迟)
                        current_reminder = "Time to stay hydrated and drink some water."
                        with cache_lock:
                            if cached_reminder:
                                current_reminder = cached_reminder
                        speak(current_reminder)
                        
                        # 3. 异步获取下一小时的提醒
                        threading.Thread(target=update_cache, daemon=True).start()
                else:
                    print(f"[{now.strftime('%H:%M:%S')}] 处于勿扰时段，跳过报时。")
                last_chime_hour = current_hour
            
            # 每隔 30 秒检查一次即可，节省 CPU
            time.sleep(30)
            
    except KeyboardInterrupt:
        print("\n脚本已停止。")

if __name__ == "__main__":
    main()
