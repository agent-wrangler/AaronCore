import queue
import unittest

import routes.chat as chat_module
from brain.stream_runtime import _runtime_ui_lang, reset_runtime_ui_lang, set_runtime_ui_lang


class ChatThreadContextTests(unittest.TestCase):
    def test_start_context_thread_preserves_runtime_ui_lang(self):
        seen = queue.Queue()
        token = set_runtime_ui_lang("en")
        try:
            worker = chat_module._start_context_thread(lambda: seen.put(_runtime_ui_lang()))
            worker.join(timeout=2)
        finally:
            reset_runtime_ui_lang(token)
        self.assertFalse(worker.is_alive())
        self.assertEqual(seen.get(timeout=1), "en")


if __name__ == "__main__":
    unittest.main()
