import os
import tempfile
import unittest
from pathlib import Path

from nes_monitor.config import load_config
from nes_monitor.notify import _ntfy


class ConfigTests(unittest.TestCase):
    def test_ntfy_env_overrides_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.ini"
            path.write_text(
                "[forum]\nurl = https://example.test/forum/\n[notify]\nntfy_url = https://example.test/old\n",
                encoding="utf-8",
            )
            os.environ["NES_NTFY_URL"] = "https://ntfy.home.example/forum-monitor-topic"
            os.environ["NES_NTFY_TOKEN"] = "tk_test"
            try:
                config = load_config(path)
            finally:
                del os.environ["NES_NTFY_URL"]
                del os.environ["NES_NTFY_TOKEN"]
        self.assertEqual(config.ntfy_url, "https://ntfy.home.example/forum-monitor-topic")
        self.assertEqual(config.ntfy_token, "tk_test")


class NtfyRequestTests(unittest.TestCase):
    def test_token_is_sent_as_bearer(self):
        seen = {}

        def capture(request, name):
            seen["url"] = request.full_url
            seen["auth"] = request.get_header("Authorization")
            seen["name"] = name
            return True

        import nes_monitor.notify as notify

        original = notify._post
        notify._post = capture
        try:
            ok = _ntfy(
                "https://ntfy.home.example/forum-monitor-topic",
                "tk_test",
                "Title",
                "Body",
                "https://example.test/thread",
            )
        finally:
            notify._post = original
        self.assertTrue(ok)
        self.assertEqual(seen["url"], "https://ntfy.home.example/forum-monitor-topic")
        self.assertEqual(seen["auth"], "Bearer tk_test")
        self.assertEqual(seen["name"], "ntfy")


if __name__ == "__main__":
    unittest.main()
