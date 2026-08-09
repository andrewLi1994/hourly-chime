from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from hourly_chime import providers


class _Handler(BaseHTTPRequestHandler):
    status = 200
    response: object = {"choices": [{"finish_reason": "stop", "message": {"content": "  **Drink water.**\n"}}]}
    received: dict[str, object] = {}

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.__class__.received = {
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "body": json.loads(self.rfile.read(length)),
        }
        body = json.dumps(self.__class__.response).encode()
        self.send_response(self.__class__.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


class ProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}/v1"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self) -> None:
        _Handler.status = 200
        _Handler.response = {"choices": [{"finish_reason": "stop", "message": {"content": "  **Drink water.**\n"}}]}

    def test_openai_compatible_request_and_cleanup(self) -> None:
        provider = providers.OpenAICompatibleProvider(self.base_url, "demo", "secret", 2, "custom")
        result = provider.generate("hydrate", "en")
        self.assertEqual(result.text, "Drink water.")
        self.assertEqual(_Handler.received["path"], "/v1/chat/completions")
        self.assertEqual(_Handler.received["authorization"], "Bearer secret")
        self.assertFalse(_Handler.received["body"]["stream"])
        self.assertEqual(_Handler.received["body"]["max_tokens"], 192)

    def test_gemini_disables_thinking_for_25_flash(self) -> None:
        provider = providers.OpenAICompatibleProvider(self.base_url, "gemini-2.5-flash", "secret", 2, "gemini")
        provider.generate("hydrate", "zh")
        self.assertEqual(_Handler.received["body"]["reasoning_effort"], "none")

    def test_length_limited_response_is_not_previewed(self) -> None:
        _Handler.response = {"choices": [{"finish_reason": "length", "message": {"content": "你的细胞在呼"}}]}
        provider = providers.OpenAICompatibleProvider(self.base_url, "gemini-2.5-flash", "secret", 2, "gemini")
        with self.assertRaises(providers.ProviderError) as raised:
            provider.generate("hydrate", "zh")
        self.assertEqual(raised.exception.code, "truncated_response")

    def test_overlong_text_is_rejected_instead_of_cut_mid_sentence(self) -> None:
        with self.assertRaises(providers.ProviderError) as raised:
            providers.sanitize_text("a" * 301)
        self.assertEqual(raised.exception.code, "invalid_response")

    def test_http_errors_are_classified(self) -> None:
        for status, expected in ((401, "auth"), (429, "rate_limit"), (500, "network")):
            with self.subTest(status=status):
                _Handler.status = status
                provider = providers.OpenAICompatibleProvider(self.base_url, "demo", "secret", 2, "custom")
                with self.assertRaises(providers.ProviderError) as raised:
                    provider.generate("hydrate", "en")
                self.assertEqual(raised.exception.code, expected)

    def test_malformed_response_is_rejected(self) -> None:
        _Handler.response = {"wrong": True}
        provider = providers.OpenAICompatibleProvider(self.base_url, "demo", "secret", 2, "custom")
        with self.assertRaises(providers.ProviderError) as raised:
            provider.generate("hydrate", "en")
        self.assertEqual(raised.exception.code, "invalid_response")

    def test_codex_flags_and_structured_output(self) -> None:
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {"HOURLY_CHIME_HOME": folder}), mock.patch(
            "hourly_chime.providers.resolve_codex_executable", return_value="/fake/codex"
        ), mock.patch("hourly_chime.providers.subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stdout='{"text":"Drink water."}', stderr="")
            result = providers.CodexProvider(executable="/fake/codex").generate("hydrate", "en")
        command = run.call_args.args[0]
        for flag in ("--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "--output-schema"):
            self.assertIn(flag, command)
        self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
        self.assertEqual(result.text, "Drink water.")

    def test_codex_login_failure_is_classified(self) -> None:
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {"HOURLY_CHIME_HOME": folder}), mock.patch(
            "hourly_chime.providers.resolve_codex_executable", return_value="/fake/codex"
        ), mock.patch("hourly_chime.providers.subprocess.run") as run:
            run.return_value = mock.Mock(returncode=1, stdout="", stderr="Please login")
            with self.assertRaises(providers.ProviderError) as raised:
                providers.CodexProvider(executable="/fake/codex").generate("hydrate", "en")
        self.assertEqual(raised.exception.code, "not_logged_in")


if __name__ == "__main__":
    unittest.main()
