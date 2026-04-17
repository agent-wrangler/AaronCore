import asyncio
import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import routes.data as data_module
from storage import chat_attachments as attachment_module


class ChatAttachmentStorageTests(unittest.TestCase):
    def test_persist_inline_chat_images_writes_public_attachment_and_delete_cleans_up(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            original_dir = attachment_module.CHAT_UPLOADS_DIR
            attachment_module.CHAT_UPLOADS_DIR = root
            try:
                payload = base64.b64encode(b"\x89PNG\r\n\x1a\nfake-png").decode("ascii")
                attachments = attachment_module.persist_inline_chat_images([payload])

                self.assertEqual(len(attachments), 1)
                self.assertEqual(attachments[0]["mime"], "image/png")

                saved_path = root / Path(attachments[0]["path"])
                self.assertTrue(saved_path.is_file())

                public_items = attachment_module.build_public_chat_attachments(attachments)
                self.assertEqual(len(public_items), 1)
                self.assertEqual(public_items[0]["url"], "/chat-uploads/" + attachments[0]["path"])

                attachment_module.delete_chat_attachments(attachments)
                self.assertFalse(saved_path.exists())
            finally:
                attachment_module.CHAT_UPLOADS_DIR = original_dir


class ChatAttachmentHistoryRouteTests(unittest.TestCase):
    def test_history_route_surfaces_attachment_urls(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            original_dir = attachment_module.CHAT_UPLOADS_DIR
            attachment_module.CHAT_UPLOADS_DIR = root
            try:
                target_dir = root / "20260417"
                target_dir.mkdir(parents=True, exist_ok=True)
                (target_dir / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\nfake-png")

                history = [
                    {
                        "role": "user",
                        "content": "look",
                        "time": "2026-04-17T12:00:00",
                        "attachments": [
                            {"type": "image", "path": "20260417/shot.png", "mime": "image/png"}
                        ],
                    }
                ]

                with patch.object(data_module.S, "load_msg_history", return_value=history), patch.object(
                    data_module.S, "get_text_history", return_value=""
                ):
                    result = asyncio.run(data_module.get_history(limit=40, offset=0))

                row = result["history"][0]
                self.assertEqual(row["attachments"][0]["url"], "/chat-uploads/20260417/shot.png")
            finally:
                attachment_module.CHAT_UPLOADS_DIR = original_dir


if __name__ == "__main__":
    unittest.main()
