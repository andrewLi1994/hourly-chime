from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hourly_chime import keychain


class KeychainHelperClientTests(unittest.TestCase):
    def test_generate_sends_only_the_prepared_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            helper = Path(folder) / "helper"
            helper.touch()
            completed = mock.Mock(
                returncode=0,
                stdout=json.dumps({"ok": True, "content": "Drink water.", "latency_ms": 5}),
                stderr="",
            )
            with mock.patch("hourly_chime.keychain.paths.keychain_helper_path", return_value=helper), mock.patch(
                "hourly_chime.keychain.subprocess.run", return_value=completed
            ) as run:
                response = keychain.generate("prepared reminder", 25)
        self.assertTrue(response["ok"])
        self.assertEqual(run.call_args.args[0], [str(helper), "generate"])
        payload = json.loads(run.call_args.kwargs["input"])
        self.assertEqual(payload, {"prompt": "prepared reminder"})

    def test_helper_error_preserves_classification(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            helper = Path(folder) / "helper"
            helper.touch()
            completed = mock.Mock(
                returncode=0,
                stdout=json.dumps({"ok": False, "error_code": "auth", "message": "Provider 认证失败"}),
                stderr="",
            )
            with mock.patch("hourly_chime.keychain.paths.keychain_helper_path", return_value=helper), mock.patch(
                "hourly_chime.keychain.subprocess.run", return_value=completed
            ):
                with self.assertRaises(keychain.HelperError) as raised:
                    keychain.generate("prepared reminder", 25)
        self.assertEqual(raised.exception.code, "auth")

    def test_missing_helper_never_falls_back_to_security_cli(self) -> None:
        with tempfile.TemporaryDirectory() as folder, mock.patch(
            "hourly_chime.keychain.paths.keychain_helper_path", return_value=Path(folder) / "missing"
        ), mock.patch("hourly_chime.keychain.subprocess.run") as run:
            with self.assertRaises(keychain.HelperError) as raised:
                keychain.generate("prepared reminder", 25)
        self.assertEqual(raised.exception.code, "missing_helper")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
