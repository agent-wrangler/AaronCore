import unittest

from brain import provider_runtime


class ProviderRuntimeTests(unittest.TestCase):
    def test_build_anthropic_url_supports_official_v1_base(self):
        self.assertEqual(
            provider_runtime.build_anthropic_url("https://api.anthropic.com/v1"),
            "https://api.anthropic.com/v1/messages",
        )

    def test_build_anthropic_url_supports_official_root_base(self):
        self.assertEqual(
            provider_runtime.build_anthropic_url("https://api.anthropic.com"),
            "https://api.anthropic.com/v1/messages",
        )

    def test_build_anthropic_url_keeps_legacy_gateway_shape(self):
        self.assertEqual(
            provider_runtime.build_anthropic_url("https://gateway.example.internal/v1"),
            "https://gateway.example.internal/anthropic/v1/messages",
        )


if __name__ == "__main__":
    unittest.main()
