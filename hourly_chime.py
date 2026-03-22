import subprocess
import time
from datetime import datetime
import sys
import os

# --- 配置 ---
# 静音时段 (小时, 24小时制)
# 例如：22 表示晚上 10 点，8 表示早上 8 点
# 如果当前小时在 [DND_START, DND_END) 范围内，则不报时
DND_START = 22  # 22:00 开始静音
DND_END = 8     # 08:00 结束静音

# 播放语速 (默认 175)
SPEECH_RATE = 180

# 使用的语音 (可选: Ting-Ting, Mei-Jia, Sin-Ji 等)
# 留空使用系统默认
VOICE = "Mei-Jia" 

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
        speak(get_chime_text())
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
                        # 其他整点播报语音
                        text = get_chime_text()
                        speak(text)
                else:
                    print(f"[{now.strftime('%H:%M:%S')}] 处于勿扰时段，跳过报时。")
                last_chime_hour = current_hour
            
            # 每隔 30 秒检查一次即可，节省 CPU
            time.sleep(30)
            
    except KeyboardInterrupt:
        print("\n脚本已停止。")

if __name__ == "__main__":
    main()
