import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import routes.skills as skills_route


class SkillDocsRouteTests(unittest.TestCase):
    def test_native_skill_doc_prefers_system_scope_when_both_exist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_root = Path(tmpdir)
            system_dir = docs_root / ".system" / "weather"
            user_dir = docs_root / "weather"
            system_dir.mkdir(parents=True, exist_ok=True)
            user_dir.mkdir(parents=True, exist_ok=True)
            (system_dir / "SKILL.md").write_text(
                "---\n"
                'name: "Weather System"\n'
                'description: "System weather skill."\n'
                "---\n\n"
                "# Weather System\n\n"
                "System body.\n",
                encoding="utf-8",
            )
            (user_dir / "SKILL.md").write_text(
                "---\n"
                'name: "Weather User"\n'
                'description: "User weather skill."\n'
                "---\n\n"
                "# Weather User\n\n"
                "User body.\n",
                encoding="utf-8",
            )

            with patch.object(skills_route, "_NATIVE_SKILL_DOCS_DIR", docs_root):
                detail = skills_route._load_native_skill_doc("weather", {"id": "weather", "source": "native"})

        self.assertEqual(detail["name"], "Weather System")
        self.assertEqual(detail["doc_scope"], "system")

    def test_load_native_skill_doc_prefers_markdown_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_root = Path(tmpdir)
            skill_dir = docs_root / ".system" / "weather"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                'name: "Weather"\n'
                'description: "Check a city forecast."\n'
                'default_prompt: "Check Shanghai weather."\n'
                "---\n\n"
                "# Weather\n\n"
                "Use this skill when the user needs a short forecast.\n",
                encoding="utf-8",
            )

            detail = None
            with patch.object(skills_route, "_NATIVE_SKILL_DOCS_DIR", docs_root):
                detail = skills_route._load_native_skill_doc(
                    "weather",
                    {
                        "id": "weather",
                        "name": "天气查询",
                        "description": "fallback description",
                        "enabled": True,
                        "source": "native",
                    },
                )

            self.assertEqual(detail["name"], "Weather")
            self.assertEqual(detail["description"], "Check a city forecast.")
            self.assertEqual(detail["default_prompt"], "Check Shanghai weather.")
            self.assertIn("short forecast", detail["body_markdown"])
            self.assertTrue(detail["has_example_prompt"])
            self.assertEqual(detail["doc_scope"], "system")

    def test_get_user_view_enriches_native_skill_cards_with_doc_metadata(self):
        fake_skill = {
            "name": "天气查询",
            "description": "fallback description",
            "priority": 6,
            "category": "信息查询",
            "status": "ready",
            "enabled": True,
            "source": "native",
            "capability_kind": "domain_skill",
            "substrate_layer": "skill",
            "protocol_family": "live_data",
            "exposure_scope": "tool_call",
            "stateful": False,
            "surfacing_profile": "contextual",
            "discovery_tags": [],
            "operation_kind": "query",
            "effect_level": "external_lookup",
            "risk_level": "low",
            "protocol_subfamily": "live_data_query",
            "trust_level": "external_data",
            "user_view_scope": "default",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            docs_root = Path(tmpdir)
            skill_dir = docs_root / ".system" / "weather"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                'name: "Weather"\n'
                'description: "Check a city forecast."\n'
                "---\n\n"
                "# Weather\n\n"
                "Use this skill when the user needs a short forecast.\n",
                encoding="utf-8",
            )

            with patch.object(skills_route, "_NATIVE_SKILL_DOCS_DIR", docs_root), patch.object(
                skills_route.S, "NOVA_CORE_READY", True
            ), patch.object(skills_route.S, "get_user_visible_skills", return_value={"weather": fake_skill}):
                result = asyncio.run(skills_route.get_user_view("default"))

        self.assertTrue(result["ready"])
        self.assertEqual(len(result["skills"]), 1)
        self.assertEqual(result["skills"][0]["name"], "Weather")
        self.assertEqual(result["skills"][0]["description"], "Check a city forecast.")

    def test_get_skill_detail_returns_markdown_body_for_native_skill(self):
        fake_skill = {
            "name": "天气查询",
            "description": "fallback description",
            "priority": 6,
            "category": "信息查询",
            "status": "ready",
            "enabled": True,
            "source": "native",
            "capability_kind": "domain_skill",
            "substrate_layer": "skill",
            "protocol_family": "live_data",
            "exposure_scope": "tool_call",
            "stateful": False,
            "surfacing_profile": "contextual",
            "discovery_tags": [],
            "operation_kind": "query",
            "effect_level": "external_lookup",
            "risk_level": "low",
            "protocol_subfamily": "live_data_query",
            "trust_level": "external_data",
            "user_view_scope": "default",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            docs_root = Path(tmpdir)
            skill_dir = docs_root / ".system" / "weather"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                'name: "Weather"\n'
                'description: "Check a city forecast."\n'
                'default_prompt: "Check Shanghai weather."\n'
                "---\n\n"
                "# Weather\n\n"
                "Use this skill when the user needs a short forecast.\n\n"
                "## Rules\n\n"
                "- Confirm the city before answering.\n",
                encoding="utf-8",
            )

            with patch.object(skills_route, "_NATIVE_SKILL_DOCS_DIR", docs_root), patch.object(
                skills_route.S, "NOVA_CORE_READY", True
            ), patch.object(skills_route.S, "get_all_skills_for_ui", return_value={"weather": fake_skill}):
                result = asyncio.run(skills_route.get_skill_detail("weather"))

        self.assertTrue(result["ready"])
        self.assertEqual(result["skill"]["name"], "Weather")
        self.assertEqual(result["skill"]["default_prompt"], "Check Shanghai weather.")
        self.assertIn("Confirm the city", result["skill"]["body_markdown"])
        self.assertIn("<h2>Rules</h2>", result["skill"]["body_html"])


if __name__ == "__main__":
    unittest.main()
