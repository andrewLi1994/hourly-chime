"""Generate Hourly Chime's bundled audio without third-party samples.

The output is deterministic 16-bit mono PCM WAV. Keeping the generator in the
repository makes the provenance auditable and lets a clean checkout recreate
the exact assets.
"""

from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path


SAMPLE_RATE = 22_050


def envelope(position: float, duration: float, attack: float = 0.025, release: float = 0.35) -> float:
    attack_gain = min(1.0, position / attack)
    release_gain = min(1.0, max(0.0, duration - position) / release)
    return attack_gain * release_gain


def add_tone(buffer: list[float], start: float, duration: float, frequency: float, gain: float) -> None:
    first = int(start * SAMPLE_RATE)
    count = int(duration * SAMPLE_RATE)
    for offset in range(count):
        index = first + offset
        if index >= len(buffer):
            break
        time = offset / SAMPLE_RATE
        # A restrained bell timbre built only from sine partials.
        value = (
            math.sin(2 * math.pi * frequency * time)
            + 0.28 * math.sin(2 * math.pi * frequency * 2.01 * time)
            + 0.10 * math.sin(2 * math.pi * frequency * 3.98 * time)
        )
        decay = math.exp(-2.2 * time / max(duration, 0.01))
        buffer[index] += value * gain * decay * envelope(time, duration)


def write_wav(path: Path, samples: list[float]) -> None:
    peak = max(1.0, max(abs(value) for value in samples))
    scale = 0.88 * 32767 / peak
    frames = b"".join(struct.pack("<h", int(max(-32768, min(32767, value * scale)))) for value in samples)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(frames)


def generate_chime(path: Path) -> None:
    samples = [0.0] * int(3.4 * SAMPLE_RATE)
    for start, frequency, gain in (
        (0.00, 659.25, 0.48),
        (0.42, 987.77, 0.42),
        (0.84, 1318.51, 0.36),
        (1.55, 987.77, 0.30),
    ):
        add_tone(samples, start, 1.55, frequency, gain)
    write_wav(path, samples)


def generate_music(path: Path) -> None:
    duration = 18.0
    samples = [0.0] * int(duration * SAMPLE_RATE)
    # An original, calm pentatonic sequence for the 17:00 special cue.
    melody = [523.25, 659.25, 783.99, 987.77, 783.99, 659.25, 587.33, 783.99, 880.00, 1046.50, 880.00, 783.99]
    for index, frequency in enumerate(melody):
        start = index * 1.35
        add_tone(samples, start, 1.75, frequency, 0.24)
        add_tone(samples, start, 1.75, frequency / 2, 0.13)
    for start, root in ((0.0, 261.63), (5.4, 220.00), (10.8, 196.00), (14.85, 261.63)):
        add_tone(samples, start, 4.0, root, 0.08)
        add_tone(samples, start, 4.0, root * 1.5, 0.055)
    write_wav(path, samples)


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    audio_dir = root / "assets" / "audio"
    generate_chime(audio_dir / "hourly-chime.wav")
    generate_music(audio_dir / "hourly-music.wav")
    print(audio_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
