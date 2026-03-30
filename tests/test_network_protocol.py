import unittest

import core.network_protocol as network_protocol_module


class NetworkProtocolTests(unittest.TestCase):
    def test_domestic_model_api_prefers_direct_even_when_proxy_env_exists(self):
        target = network_protocol_module.classify_remote_target("https://api.minimaxi.com/v1/chat/completions")
        env_status = {
            "has_proxy_env": True,
            "has_local_proxy": True,
            "local_proxy_alive": True,
            "target_dns_ok": True,
        }

        decision = network_protocol_module.decide_network_route(target, env_status)

        self.assertEqual(decision.get("route"), "direct")
        self.assertEqual(decision.get("reason"), "domestic_direct_host")

    def test_non_domestic_model_api_keeps_proxy_route_when_proxy_available(self):
        target = network_protocol_module.classify_remote_target("https://api.openai.com/v1/chat/completions")
        env_status = {
            "has_proxy_env": True,
            "has_local_proxy": True,
            "local_proxy_alive": True,
            "target_dns_ok": True,
        }

        decision = network_protocol_module.decide_network_route(target, env_status)

        self.assertEqual(decision.get("route"), "proxy")
        self.assertEqual(decision.get("reason"), "proxy_env_available")


if __name__ == "__main__":
    unittest.main()
