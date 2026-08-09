from __future__ import annotations

import copy
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from hourly_chime import paths, runtime, state
from hourly_chime.config import ConfigError, default_config, load_config, save_config
from hourly_chime.providers import GeneratedText


class IsolatedHomeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.env = mock.patch.dict(
            os.environ,
            {
                "HOURLY_CHIME_HOME": str(self.home),
                "HOURLY_CHIME_LAUNCH_AGENTS": str(self.home / "LaunchAgents"),
            },
        )
        self.env.start()
        paths.ensure_layout()

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()


class ConfigTests(IsolatedHomeTest):
    def test_default_config_is_atomic_and_cross_midnight(self) -> None:
        config = load_config()
        self.assertEqual(config["schedule"]["dnd"]["start_minute"], 1320)
        self.assertEqual(config["schedule"]["dnd"]["end_minute"], 480)
        self.assertTrue(runtime.is_dnd(datetime(2026, 8, 9, 22, 0), config))
        self.assertTrue(runtime.is_dnd(datetime(2026, 8, 10, 7, 59), config))
        self.assertFalse(runtime.is_dnd(datetime(2026, 8, 10, 8, 0), config))
        self.assertEqual(paths.config_path().stat().st_mode & 0o777, 0o600)

    def test_same_endpoints_and_path_traversal_are_rejected(self) -> None:
        config = default_config()
        config["schedule"]["dnd"]["end_minute"] = 1320
        with self.assertRaises(ConfigError):
            save_config(config)
        config = default_config()
        config["audio"]["chime_file"] = "../secret.mp3"
        with self.assertRaises(ConfigError):
            save_config(config)

    def test_disabled_dnd_preserves_values(self) -> None:
        config = default_config()
        config["schedule"]["dnd"]["enabled"] = False
        save_config(config)
        loaded = load_config()
        self.assertEqual((loaded["schedule"]["dnd"]["start_minute"], loaded["schedule"]["dnd"]["end_minute"]), (1320, 480))
        self.assertFalse(runtime.is_dnd(datetime(2026, 8, 9, 23, 0), loaded))


class RuntimeTests(IsolatedHomeTest):
    def setUp(self) -> None:
        super().setUp()
        self.config = default_config()
        save_config(self.config)
        for name in ("hourly-chime.wav", "hourly-music.wav"):
            (paths.audio_dir() / name).write_bytes(b"a" * 2048)

    def test_legacy_audio_names_are_migrated(self) -> None:
        legacy = default_config()
        legacy["audio"]["chime_file"] = "airport-chime.mp3"
        legacy["audio"]["music_file"] = "Japanese_Music.mp3"
        save_config(legacy)
        loaded = load_config()
        self.assertEqual(loaded["audio"]["chime_file"], "hourly-chime.wav")
        self.assertEqual(loaded["audio"]["music_file"], "hourly-music.wav")

    def test_late_play_is_silently_skipped(self) -> None:
        result = runtime.run_play(datetime(2026, 8, 9, 12, 4))
        self.assertEqual(result["status"], "skipped_late")

    def test_music_hour_only_plays_music(self) -> None:
        with mock.patch("hourly_chime.runtime.audio.play_file") as play, mock.patch("hourly_chime.runtime.audio.say") as say:
            result = runtime.run_play(datetime(2026, 8, 9, 17, 0))
        self.assertEqual(result["status"], "played_music")
        self.assertEqual(play.call_count, 1)
        say.assert_not_called()

    def test_play_never_constructs_a_text_provider(self) -> None:
        paths.cache_audio_path().write_bytes(b"m" * 2048)
        with mock.patch("hourly_chime.runtime.providers.build_provider") as provider, mock.patch("hourly_chime.runtime.audio.play_file"):
            result = runtime.run_play(datetime(2026, 8, 9, 12, 0))
        self.assertEqual(result["status"], "played_cache")
        provider.assert_not_called()

    def test_refresh_skips_quiet_and_music_targets(self) -> None:
        quiet = runtime.run_refresh(now=datetime(2026, 8, 9, 21, 55))
        music = runtime.run_refresh(now=datetime(2026, 8, 9, 16, 55))
        self.assertEqual(quiet["status"], "skipped_schedule")
        self.assertEqual(music["status"], "skipped_schedule")

    def test_template_rotation_avoids_immediate_repeat(self) -> None:
        templates = [
            {"id": "one", "enabled": True},
            {"id": "two", "enabled": True},
        ]
        self.assertEqual(runtime.select_template(templates, "one")["id"], "two")

    def test_refresh_updates_cache_and_daily_limit_preserves_old_cache(self) -> None:
        self.config["limits"]["max_daily_ai_calls"] = 1
        save_config(self.config)
        fake_provider = mock.Mock()
        fake_provider.generate.return_value = GeneratedText("Drink some water.", "fake", "tiny", 4)

        def synthesize(text: str, voice: str, destination: Path) -> None:
            destination.write_bytes(b"n" * 2048)

        with mock.patch("hourly_chime.runtime.providers.build_provider", return_value=fake_provider), mock.patch(
            "hourly_chime.runtime.audio.synthesize_atomic", side_effect=synthesize
        ):
            first = runtime.run_refresh(now=datetime.now().replace(hour=11, minute=55, second=0, microsecond=0))
            before = paths.cache_audio_path().read_bytes()
            second = runtime.run_refresh(now=datetime.now().replace(hour=12, minute=55, second=0, microsecond=0))
        self.assertEqual(first["status"], "refreshed")
        self.assertEqual(second["status"], "skipped_limit")
        self.assertEqual(paths.cache_audio_path().read_bytes(), before)
        self.assertEqual(fake_provider.generate.call_count, 1)

    def test_failed_synthesis_keeps_existing_cache(self) -> None:
        paths.cache_audio_path().write_bytes(b"o" * 2048)
        fake_provider = mock.Mock()
        fake_provider.generate.return_value = GeneratedText("Drink water.", "fake", "tiny", 1)
        with mock.patch("hourly_chime.runtime.providers.build_provider", return_value=fake_provider), mock.patch(
            "hourly_chime.runtime.audio.synthesize_atomic", side_effect=RuntimeError("tts down")
        ):
            result = runtime.run_refresh(force=True, now=datetime.now().replace(hour=12, minute=55))
        self.assertEqual(result["status"], "error")
        self.assertEqual(paths.cache_audio_path().read_bytes(), b"o" * 2048)


if __name__ == "__main__":
    unittest.main()
