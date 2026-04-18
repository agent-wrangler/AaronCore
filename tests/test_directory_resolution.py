import unittest

from decision.tool_runtime.directory_resolution import looks_like_directory_resolution_request


class DirectoryResolutionRequestTests(unittest.TestCase):
    def test_accepts_explicit_location_request_with_structured_target(self):
        self.assertTrue(
            looks_like_directory_resolution_request(
                "which folder is it in",
                has_structured_target=True,
            )
        )

    def test_accepts_referential_location_followup(self):
        self.assertTrue(
            looks_like_directory_resolution_request(
                "\u5b83\u5728\u54ea",
                has_structured_target=True,
            )
        )

    def test_rejects_resume_text_without_location_focus(self):
        self.assertFalse(
            looks_like_directory_resolution_request(
                "continue the report",
                has_structured_target=True,
            )
        )

    def test_rejects_location_query_without_structured_target(self):
        self.assertFalse(
            looks_like_directory_resolution_request(
                "where is it",
                has_structured_target=False,
            )
        )


if __name__ == "__main__":
    unittest.main()
