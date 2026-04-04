import unittest

from decision.tool_runtime.memory_tools import format_recall


class MemoryToolRuntimeTests(unittest.TestCase):
    def test_format_recall_accepts_current_l2_and_l3_shapes(self):
        l2_results = [
            {
                "user_text": "\u6211\u4eec\u524d\u9762\u804a\u8fc7 state_data \u600e\u4e48\u5206",
                "ai_text": "\u540e\u6765\u6536\u6210\u4e86 state_data \u4e0b\u56db\u4e2a store",
            }
        ]
        l3_events = [
            "\u7528\u6237\u628a memory=\u4ee3\u7801\uff0cstate_data=\u6570\u636e\u603b\u4ed3 \u8fd9\u4e2a\u8fb9\u754c\u5b9a\u4e0b\u6765\u4e86\u3002"
        ]

        result = format_recall(l2_results, l3_events)

        self.assertIn("\u6211\u4eec\u524d\u9762\u804a\u8fc7 state_data \u600e\u4e48\u5206", result)
        self.assertIn("state_data \u4e0b\u56db\u4e2a store", result)
        self.assertIn("memory=\u4ee3\u7801", result)

    def test_format_recall_skips_non_dict_l2_entries_without_crashing(self):
        result = format_recall(["bad-entry"], ["\u4e00\u6761\u957f\u671f\u8bb0\u5fc6"])

        self.assertIn("\u4e00\u6761\u957f\u671f\u8bb0\u5fc6", result)


if __name__ == "__main__":
    unittest.main()
