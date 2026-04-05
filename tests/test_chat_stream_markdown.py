import unittest

from routes.chat_stream_markdown import MarkdownIncrementalStream, find_markdown_commit_boundary


class ChatStreamMarkdownTests(unittest.TestCase):
    def test_paragraph_stays_in_tail_until_blank_line(self):
        stream = MarkdownIncrementalStream()
        payload = stream.feed("A paragraph that is still open")
        self.assertEqual([], payload["append"])
        self.assertEqual("A paragraph that is still open", payload["tail"])
        self.assertIn("<p>", payload["tail_html"])

        payload = stream.feed("\n\n")
        self.assertEqual("", payload["tail"])
        self.assertEqual(1, len(payload["append"]))
        self.assertEqual("A paragraph that is still open\n\n", payload["append"][0]["markdown"])
        self.assertIn("<p>", payload["append"][0]["html"])

    def test_code_block_waits_until_fence_closed(self):
        stream = MarkdownIncrementalStream()
        payload = stream.feed("```python\nprint('hi')\n")
        self.assertEqual([], payload["append"])
        self.assertEqual("```python\nprint('hi')\n", payload["tail"])
        self.assertIn("<pre><code", payload["tail_html"])

        payload = stream.feed("```\n")
        self.assertEqual("", payload["tail"])
        self.assertEqual(1, len(payload["append"]))
        self.assertIn("<pre><code", payload["append"][0]["html"])

    def test_flush_commits_remaining_tail(self):
        stream = MarkdownIncrementalStream()
        stream.feed("Last paragraph without blank line")
        payload = stream.flush()
        self.assertEqual("", payload["tail"])
        self.assertEqual(1, len(payload["append"]))
        self.assertEqual("Last paragraph without blank line", payload["append"][0]["markdown"])

    def test_reset_clears_previous_state(self):
        stream = MarkdownIncrementalStream()
        stream.feed("Old content\n\n")
        stream.reset()
        payload = stream.feed("New content\n\n")
        self.assertEqual(1, len(payload["append"]))
        self.assertEqual("New content\n\n", payload["append"][0]["markdown"])

    def test_boundary_detects_closed_blocks_only(self):
        self.assertEqual(0, find_markdown_commit_boundary("A plain sentence"))
        self.assertGreater(find_markdown_commit_boundary("Heading\n\n"), 0)
        self.assertEqual(0, find_markdown_commit_boundary("```py\nx=1\n"))
        self.assertGreater(find_markdown_commit_boundary("```py\nx=1\n```\n"), 0)
        self.assertEqual(0, find_markdown_commit_boundary("- half a list item"))
        self.assertEqual(0, find_markdown_commit_boundary("## half a heading"))

    def test_list_item_waits_for_line_break(self):
        stream = MarkdownIncrementalStream()
        payload = stream.feed("- A")
        self.assertEqual([], payload["append"])
        self.assertEqual("- A", payload["tail"])

        payload = stream.feed("sk why:\n")
        self.assertEqual("", payload["tail"])
        self.assertEqual(1, len(payload["append"]))
        self.assertEqual("- Ask why:\n", payload["append"][0]["markdown"])

    def test_stream_html_strips_decorative_bold_markers(self):
        stream = MarkdownIncrementalStream()
        payload = stream.feed("来，接下一个**：")
        self.assertEqual("来，接下一个**：", payload["tail"])
        self.assertNotIn("**", payload["tail_html"])
        self.assertIn("来，接下一个：", payload["tail_html"])

    def test_committed_html_strips_decorative_bold_markers(self):
        stream = MarkdownIncrementalStream()
        payload = stream.feed("我是程序员**，我的生活只有两个状态**：\n\n")
        self.assertEqual("", payload["tail"])
        self.assertEqual(1, len(payload["append"]))
        self.assertNotIn("**", payload["append"][0]["html"])
        self.assertNotIn("<strong>", payload["append"][0]["html"])


if __name__ == "__main__":
    unittest.main()
