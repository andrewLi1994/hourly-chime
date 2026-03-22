import subprocess
import time
from datetime import datetime
import sys
import os
import json
import re

# --- 配置 ---
# 静音时段 (小时, 24小时制)
# 例如：22 表示晚上 10 点，8 表示早上 8 点
# 如果当前小时在 [DND_START, DND_END) 范围内，则不报时
DND_START = 22  # 22:00 开始静音
DND_END = 8     # 08:00 结束静音

# 播放语速 (默认 175)
SPEECH_RATE = 200

# 使用的语音 (可选: Ting-Ting, Mei-Jia, Sin-Ji 等)
# 留空使用系统默认
VOICE = "Mei-Jia" 

# 机场整点报时音 (文件名较长，建议保持原样或重命名)
CHIME_AUDIO = "gracesoundproductions-airport-announcement-call-chime-start-and-finish-342984.mp3"

# 5 点整播放的音乐设置
MUSIC_FILE = "Japanese_Music.mp3"
MUSIC_HOUR = 17  # 17:00 是下午 5 点

def speak(text):
    """调用 macOS 'say' 命令进行播报"""
    print(f"正在播报: {text}")
    cmd = ["say", "-r", str(SPEECH_RATE)]
    if VOICE:
        cmd.extend(["-v", VOICE])
    cmd.append(text)
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"语音播报失败: {e}")
    except FileNotFoundError:
        print("错误: 找不到 'say' 命令。请确保在 macOS 上运行。")

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
        "--message", "Give me a short, simple and fun English ONLY reminder to drink water. One sentence only, and don't use any emojis.", 
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

def get_chime_text():
    """根据当前时间生成报时文本"""
    now = datetime.now()
    hour = now.hour
    
    # 转换为 12 小时制播报更自然
    period = "上午" if hour < 12 else "下午"
    display_hour = hour if hour <= 12 else hour - 12
    if display_hour == 0: display_hour = 12
    
    return f"现在是{period}{display_hour}点整。"

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
        # 播放机场提示音
        script_dir = os.path.dirname(os.path.abspath(__file__))
        chime_path = os.path.join(script_dir, CHIME_AUDIO)
        play_music(chime_path)
        
        # 获取并播报 AI 提醒
        reminder = get_ai_reminder()
        speak(reminder)
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
                        # 播放机场提示音代替文字报时
                        script_dir = os.path.dirname(os.path.abspath(__file__))
                        chime_path = os.path.join(script_dir, CHIME_AUDIO)
                        play_music(chime_path)
                        
                        # 获取并播报 AI 提醒
                        reminder = get_ai_reminder()
                        speak(reminder)
                else:
                    print(f"[{now.strftime('%H:%M:%S')}] 处于勿扰时段，跳过报时。")
                last_chime_hour = current_hour
            
            # 每隔 30 秒检查一次即可，节省 CPU
            time.sleep(30)
            
    except KeyboardInterrupt:
        print("\n脚本已停止。")

if __name__ == "__main__":
    main()
