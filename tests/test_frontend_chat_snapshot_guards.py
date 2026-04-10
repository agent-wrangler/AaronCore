import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendChatSnapshotGuardTests(unittest.TestCase):
    def test_view_switch_snapshots_chat_before_replacing_dom(self):
        text = (ROOT / "static/js/app/views.js").read_text(encoding="utf-8")
        self.assertIn("var previousTab=window._currentTab||1;", text)
        self.assertIn(
            "if(previousTab===1 && n!==1 && typeof window._snapshotChatHistory==='function'){",
            text,
        )

    def test_composer_only_persists_real_chat_snapshots(self):
        text = (ROOT / "static/js/chat/composer.js").read_text(encoding="utf-8")
        self.assertIn("function _snapshotChatHistory(options){", text)
        self.assertIn("window._looksLikeChatSnapshot(currentHtml)", text)
        self.assertIn("window._snapshotChatHistory=_snapshotChatHistory;", text)

    def test_boot_no_longer_clears_restored_snapshot_on_empty_history(self):
        text = (ROOT / "static/js/app/boot.js").read_text(encoding="utf-8")
        self.assertIn("function _restoreChatFromSnapshot(chat, keepScroll){", text)
        self.assertIn("if(!_restoreChatFromSnapshot(chat, keepScroll)){", text)
        self.assertNotRegex(
            text,
            re.compile(
                r"if\(items\.length===0\)\{\s*if\(_restoredTimelineSnapshot\)\{\s*chat\.innerHTML='';\s*chatHistory='';",
                re.S,
            ),
        )


if __name__ == "__main__":
    unittest.main()
