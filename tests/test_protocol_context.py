import unittest
from pathlib import Path
from unittest.mock import patch

from decision.tool_runtime.protocol_context import apply_protocol_context


def _resolve_user_file_target(path: str) -> Path:
    return Path(str(path)).resolve()


def _is_allowed_user_target(_path: Path) -> bool:
    return True


class ProtocolContextFollowupTests(unittest.TestCase):
    def test_blocks_generic_target_for_non_referential_update(self):
        ctx = {
            "fs_target": {"path": "C:/Users/36459/Desktop", "option": "inspect", "source": "runtime"},
            "path": "C:/Users/36459/Desktop",
        }

        with patch("core.context_pull.pull_context_data", return_value={}), patch(
            "core.task_store.get_latest_structured_fs_target",
            return_value=None,
        ):
            result = apply_protocol_context(
                "folder_explore",
                ctx,
                "it still fails",
                {},
                resolve_user_file_target=_resolve_user_file_target,
                is_allowed_user_target=_is_allowed_user_target,
            )

        self.assertNotIn("fs_target", result)
        self.assertEqual(result.get("path"), "")

    def test_keeps_generic_target_for_bare_followup_command(self):
        ctx = {
            "fs_target": {"path": "C:/Users/36459/Desktop", "option": "inspect", "source": "runtime"},
            "path": "C:/Users/36459/Desktop",
        }

        with patch("core.context_pull.pull_context_data", return_value={}), patch(
            "core.task_store.get_latest_structured_fs_target",
            return_value=None,
        ):
            result = apply_protocol_context(
                "folder_explore",
                ctx,
                "continue",
                {},
                resolve_user_file_target=_resolve_user_file_target,
                is_allowed_user_target=_is_allowed_user_target,
            )

        self.assertEqual((result.get("fs_target") or {}).get("path"), "C:/Users/36459/Desktop")

    def test_keeps_generic_target_for_referential_fs_followup(self):
        ctx = {
            "fs_target": {"path": "C:/Users/36459/Desktop", "option": "inspect", "source": "runtime"},
            "path": "C:/Users/36459/Desktop",
        }

        with patch("core.context_pull.pull_context_data", return_value={}), patch(
            "core.task_store.get_latest_structured_fs_target",
            return_value=None,
        ):
            result = apply_protocol_context(
                "folder_explore",
                ctx,
                "open that folder",
                {},
                resolve_user_file_target=_resolve_user_file_target,
                is_allowed_user_target=_is_allowed_user_target,
            )

        self.assertEqual((result.get("fs_target") or {}).get("path"), "C:/Users/36459/Desktop")

    def test_blocks_generic_target_for_resume_without_reference(self):
        ctx = {
            "fs_target": {"path": "C:/Users/36459/Desktop", "option": "inspect", "source": "runtime"},
            "path": "C:/Users/36459/Desktop",
        }

        with patch("core.context_pull.pull_context_data", return_value={}), patch(
            "core.task_store.get_latest_structured_fs_target",
            return_value=None,
        ):
            result = apply_protocol_context(
                "folder_explore",
                ctx,
                "continue the report",
                {},
                resolve_user_file_target=_resolve_user_file_target,
                is_allowed_user_target=_is_allowed_user_target,
            )

        self.assertNotIn("fs_target", result)
        self.assertEqual(result.get("path"), "")

    def test_latest_generic_target_still_rehydrates_for_referential_question(self):
        with patch("core.context_pull.pull_context_data", return_value={}), patch(
            "core.task_store.get_latest_structured_fs_target",
            return_value={"path": "C:/Users/36459/Desktop", "option": "inspect", "source": "memory"},
        ):
            result = apply_protocol_context(
                "folder_explore",
                {},
                "\u5b83\u5728\u54ea",
                {},
                resolve_user_file_target=_resolve_user_file_target,
                is_allowed_user_target=_is_allowed_user_target,
            )

        self.assertEqual((result.get("fs_target") or {}).get("source"), "memory")
        self.assertEqual((result.get("fs_target") or {}).get("path"), "C:/Users/36459/Desktop")

    def test_latest_generic_target_stays_blocked_for_non_followup_request(self):
        with patch("core.context_pull.pull_context_data", return_value={}), patch(
            "core.task_store.get_latest_structured_fs_target",
            return_value={"path": "C:/Users/36459/Desktop", "option": "inspect", "source": "memory"},
        ):
            result = apply_protocol_context(
                "folder_explore",
                {},
                "summarize the bug report",
                {},
                resolve_user_file_target=_resolve_user_file_target,
                is_allowed_user_target=_is_allowed_user_target,
            )

        self.assertNotIn("fs_target", result)


if __name__ == "__main__":
    unittest.main()
