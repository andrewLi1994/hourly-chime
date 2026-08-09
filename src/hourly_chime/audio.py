from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from .logging_utils import get_logger


logger = get_logger("hourly_chime.audio")


class AudioError(RuntimeError):
    pass


class SpeechProvider(Protocol):
    def synthesize(self, text: str, voice: str, destination: Path) -> None: ...


def validate_audio(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size >= 1024
    except OSError:
        return False


def play_file(path: Path, volume: float = 1.0) -> None:
    if not validate_audio(path):
        raise AudioError(f"音频文件不可用: {path}")
    logger.info("开始播放 file=%s volume=%.2f", path.name, volume)
    result = subprocess.run(
        ["/usr/bin/afplay", "-v", f"{volume:.2f}", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AudioError(result.stderr.strip() or f"无法播放 {path.name}")
    logger.info("播放完成 file=%s", path.name)


def say(text: str) -> None:
    logger.info("缓存不可用，调用系统 say")
    result = subprocess.run(["/usr/bin/say", text], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AudioError(result.stderr.strip() or "系统语音播放失败")


async def _generate_edge_tts(text: str, voice: str, output: Path) -> None:
    try:
        import edge_tts
    except ImportError as exc:
        raise AudioError("未安装 edge-tts") from exc
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output))


def synthesize_atomic(text: str, voice: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".reminder.", suffix=".mp3", dir=destination.parent)
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        logger.info("开始生成语音缓存 voice=%s", voice)
        asyncio.run(_generate_edge_tts(text, voice, tmp_path))
        if not validate_audio(tmp_path):
            raise AudioError("Edge TTS 生成的音频无效")
        os.replace(tmp_path, destination)
        logger.info("语音缓存原子替换完成 bytes=%s", destination.stat().st_size)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


class EdgeSpeechProvider:
    """Speech-provider boundary used by refresh jobs and test doubles."""

    def synthesize(self, text: str, voice: str, destination: Path) -> None:
        synthesize_atomic(text, voice, destination)
