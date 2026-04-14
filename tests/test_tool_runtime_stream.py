import unittest

from decision.tool_runtime.stream import (
    _result_to_terminal_record,
    _result_to_terminal_records,
)


class ToolRuntimeStreamTests(unittest.TestCase):
    def test_result_to_terminal_record_rebuilds_runtime_state_from_result_payload(self):
        record = _result_to_terminal_record(
            {
                "tool_used": "write_file",
                "success": True,
                "tool_response": "write_file completed but verification failed",
                "action_summary": "updated target file",
                "status": "verify_failed",
                "next_action": "retry_or_close",
                "runtime_state": {
                    "status": "verify_failed",
                    "next_action": "retry_or_close",
                },
                "verification": {
                    "status": "failed",
                    "detail": "Expected output file is still missing",
                },
                "fs_target": {
                    "path": "C:/repo/result.txt",
                    "kind": "file",
                },
            }
        )

        self.assertIsNotNone(record)
        self.assertEqual((record.run_meta.get("runtime_state") or {}).get("status"), "verify_failed")
        self.assertEqual((record.run_meta.get("verification") or {}).get("status"), "failed")
        self.assertEqual(
            ((record.run_meta.get("runtime_state") or {}).get("fs_target") or {}).get("path"),
            "C:/repo/result.txt",
        )

    def test_result_to_terminal_records_rebuilds_runtime_state_for_batch_rows(self):
        records = _result_to_terminal_records(
            {
                "tool_results": [
                    {
                        "name": "open_target",
                        "success": True,
                        "status": "waiting_user",
                        "next_action": "wait_for_user",
                        "runtime_state": {
                            "status": "waiting_user",
                            "next_action": "wait_for_user",
                            "blocker": "Please finish login first",
                        },
                        "verification": {
                            "status": "failed",
                            "detail": "Please finish login first",
                        },
                    }
                ]
            }
        )

        self.assertEqual(len(records), 1)
        self.assertEqual((records[0].run_meta.get("runtime_state") or {}).get("status"), "waiting_user")
        self.assertEqual((records[0].run_meta.get("verification") or {}).get("detail"), "Please finish login first")


if __name__ == "__main__":
    unittest.main()
