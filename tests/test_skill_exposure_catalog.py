import unittest
from unittest.mock import patch
import json
from pathlib import Path

import core.skills as skills_module
import core.tool_adapter as tool_adapter_module


_RUNTIME_METADATA_DIRS = (Path("tools/agent"), Path("skills/builtin"))


def _metadata_path(skill_name: str) -> Path:
    for base in _RUNTIME_METADATA_DIRS:
        candidate = base / f"{skill_name}.json"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(skill_name)


def _iter_metadata_paths():
    seen = set()
    for base in _RUNTIME_METADATA_DIRS:
        if not base.exists():
            continue
        for path in sorted(base.glob("*.json")):
            if path.name.startswith(".") or path.name in seen:
                continue
            seen.add(path.name)
            yield path


def _fake_skill(exposure_scope: str, *, enabled: bool = True):
    return {
        "name": f"skill_{exposure_scope}",
        "description": "test skill",
        "parameters": {
            "type": "object",
            "properties": {"user_input": {"type": "string"}},
            "required": ["user_input"],
        },
        "execute": lambda *_args, **_kwargs: None,
        "status": "ready" if enabled else "disabled",
        "enabled": enabled,
        "exposure_scope": exposure_scope,
    }


class SkillExposureCatalogTests(unittest.TestCase):
    def test_operational_skill_jsons_declare_catalog_metadata(self):
        required = {
            "capability_kind",
            "substrate_layer",
            "protocol_family",
            "protocol_subfamily",
            "exposure_scope",
            "surfacing_profile",
            "user_view_scope",
            "operation_kind",
            "effect_level",
            "risk_level",
            "trust_level",
        }
        for path in _iter_metadata_paths():
            data = json.loads(path.read_text(encoding="utf-8"))
            missing = sorted(key for key in required if not data.get(key))
            self.assertEqual(missing, [], f"{path.name} missing metadata: {missing}")

    def test_runtime_root_does_not_keep_internal_worker_or_state_artifacts(self):
        disallowed = {
            "_qq_monitor_worker.py",
            "_qq_open_group.py",
            "_qq_worker.py",
            "_wechat_monitor_worker.py",
            "_wechat_open_chat.py",
            "_wechat_worker.py",
            "_web_chat_worker.py",
            ".article_state.json",
            "news_config.json",
        }
        root_names = {path.name for path in Path("core/skills").iterdir()}
        self.assertTrue(disallowed.isdisjoint(root_names), root_names & disallowed)

    def test_internal_runtime_capabilities_are_hidden_from_user_view(self):
        expected_hidden = {
            "content_task": "hidden",
            "development_flow": "hidden",
            "task_plan": "hidden",
            "model_config": "hidden",
        }
        for skill_name, expected_scope in expected_hidden.items():
            data = json.loads(_metadata_path(skill_name).read_text(encoding="utf-8"))
            self.assertEqual(data.get("user_view_scope"), expected_scope, skill_name)

    def test_user_visible_skill_metadata_matches_real_capabilities(self):
        expected = {
            "article": ("写文章", "内容创作"),
            "draw": ("AI画图", "内容创作"),
            "news": ("新闻抓取", "信息查询"),
            "stock": ("股票查询", "信息查询"),
            "story": ("讲故事", "内容创作"),
            "weather": ("天气查询", "信息查询"),
        }
        for skill_name, (expected_name, expected_category) in expected.items():
            data = json.loads(_metadata_path(skill_name).read_text(encoding="utf-8"))
            self.assertEqual(data.get("name"), expected_name, skill_name)
            self.assertEqual(data.get("category"), expected_category, skill_name)

    def test_registry_returns_only_matching_exposed_skills(self):
        fake_registry = {
            "protocol_visible": _fake_skill("tool_call"),
            "cod_visible": _fake_skill("tool_call_cod"),
            "catalog_only": _fake_skill("catalog_only"),
            "disabled_visible": _fake_skill("tool_call", enabled=False),
        }

        with patch.dict(skills_module._skill_registry, fake_registry, clear=True):
            tool_call_skills = skills_module.get_exposed_skills("tool_call")
            cod_skills = skills_module.get_exposed_skills({"tool_call", "tool_call_cod"})

        self.assertIn("protocol_visible", tool_call_skills)
        self.assertNotIn("cod_visible", tool_call_skills)
        self.assertNotIn("catalog_only", tool_call_skills)
        self.assertNotIn("disabled_visible", tool_call_skills)
        self.assertIn("protocol_visible", cod_skills)
        self.assertIn("cod_visible", cod_skills)

    def test_registry_returns_only_matching_surfaced_skills(self):
        fake_registry = {
            "protocol_visible": {**_fake_skill("tool_call"), "surfacing_profile": "tool_only"},
            "workflow_visible": {**_fake_skill("tool_call"), "surfacing_profile": "contextual"},
            "manual_visible": {**_fake_skill("catalog_only"), "surfacing_profile": "manual_only"},
        }

        with patch.dict(skills_module._skill_registry, fake_registry, clear=True):
            contextual = skills_module.get_surfaced_skills("contextual")
            manual = skills_module.get_surfaced_skills({"manual_only", "contextual"})

        self.assertNotIn("protocol_visible", contextual)
        self.assertIn("workflow_visible", contextual)
        self.assertIn("workflow_visible", manual)
        self.assertIn("manual_visible", manual)

    def test_registry_returns_only_matching_user_visible_skills(self):
        fake_registry = {
            "hidden_protocol": {**_fake_skill("tool_call"), "user_view_scope": "hidden"},
            "default_skill": {**_fake_skill("tool_call"), "user_view_scope": "default"},
            "advanced_skill": {**_fake_skill("catalog_only"), "user_view_scope": "advanced"},
        }

        with patch.dict(skills_module._skill_registry, fake_registry, clear=True):
            default_view = skills_module.get_user_view("default")
            expanded_view = skills_module.get_user_view("default,advanced")

        self.assertIn("default_skill", default_view)
        self.assertNotIn("hidden_protocol", default_view)
        self.assertNotIn("advanced_skill", default_view)
        self.assertIn("default_skill", expanded_view)
        self.assertIn("advanced_skill", expanded_view)
        self.assertNotIn("hidden_protocol", expanded_view)

    def test_tool_view_and_surfacing_view_return_runtime_specific_shapes(self):
        fake_registry = {
            "protocol_visible": {
                **_fake_skill("tool_call"),
                "capability_kind": "protocol_tool",
                "substrate_layer": "protocol",
                "protocol_family": "filesystem",
                "protocol_subfamily": "filesystem_read",
                "surfacing_profile": "tool_only",
                "operation_kind": "inspect",
                "effect_level": "read_only",
                "risk_level": "low",
                "trust_level": "trusted_local",
                "priority": 8,
                "category": "本地探索",
                "discovery_tags": ["filesystem_read"],
                "user_view_scope": "hidden",
            },
            "workflow_visible": {
                **_fake_skill("tool_call"),
                "capability_kind": "workflow_skill",
                "substrate_layer": "skill",
                "protocol_family": "planning",
                "protocol_subfamily": "workflow_planning",
                "surfacing_profile": "contextual",
                "operation_kind": "plan",
                "effect_level": "state_write",
                "risk_level": "medium",
                "trust_level": "trusted_state",
                "priority": 35,
                "category": "任务",
                "discovery_tags": ["planning"],
                "user_view_scope": "default",
            },
        }

        with patch.dict(skills_module._skill_registry, fake_registry, clear=True):
            tool_view = skills_module.get_tool_view("tool_call")
            surfacing_view = skills_module.get_surfacing_view("contextual")
            user_view = skills_module.get_user_view("default")

        self.assertIn("parameters", tool_view["protocol_visible"])
        self.assertIn("protocol_subfamily", tool_view["protocol_visible"])
        self.assertNotIn("discovery_tags", tool_view["protocol_visible"])
        self.assertIn("workflow_visible", surfacing_view)
        self.assertIn("discovery_tags", surfacing_view["workflow_visible"])
        self.assertNotIn("parameters", surfacing_view["workflow_visible"])
        self.assertIn("workflow_visible", user_view)
        self.assertIn("user_view_scope", user_view["workflow_visible"])
        self.assertNotIn("parameters", user_view["workflow_visible"])

    def test_catalog_summary_groups_skills_by_kind_scope_and_profile(self):
        fake_registry = {
            "protocol_visible": {
                **_fake_skill("tool_call"),
                "capability_kind": "protocol_tool",
                "substrate_layer": "protocol",
                "protocol_subfamily": "filesystem_read",
                "surfacing_profile": "tool_only",
                "operation_kind": "inspect",
                "effect_level": "read_only",
                "risk_level": "low",
                "trust_level": "trusted_local",
                "user_view_scope": "hidden",
            },
            "workflow_visible": {
                **_fake_skill("tool_call"),
                "capability_kind": "workflow_skill",
                "substrate_layer": "skill",
                "protocol_subfamily": "workflow_planning",
                "surfacing_profile": "contextual",
                "operation_kind": "plan",
                "effect_level": "state_write",
                "risk_level": "medium",
                "trust_level": "trusted_state",
                "user_view_scope": "default",
            },
            "manual_visible": {
                **_fake_skill("catalog_only"),
                "capability_kind": "domain_skill",
                "substrate_layer": "skill",
                "protocol_subfamily": "content_generation",
                "surfacing_profile": "manual_only",
                "operation_kind": "mutate",
                "effect_level": "local_write",
                "risk_level": "high",
                "trust_level": "trusted_local",
                "user_view_scope": "advanced",
                "status": "disabled",
                "enabled": False,
            },
        }

        with patch.dict(skills_module._skill_registry, fake_registry, clear=True):
            summary = skills_module.get_skill_catalog_summary()

        self.assertEqual(summary.get("total"), 3)
        self.assertEqual(summary.get("enabled"), 2)
        self.assertEqual(summary.get("by_kind", {}).get("protocol_tool"), 1)
        self.assertEqual(summary.get("by_kind", {}).get("workflow_skill"), 1)
        self.assertEqual(summary.get("by_exposure_scope", {}).get("catalog_only"), 1)
        self.assertEqual(summary.get("by_surfacing_profile", {}).get("manual_only"), 1)
        self.assertEqual(summary.get("by_operation_kind", {}).get("inspect"), 1)
        self.assertEqual(summary.get("by_effect_level", {}).get("local_write"), 1)
        self.assertEqual(summary.get("by_risk_level", {}).get("high"), 1)
        self.assertEqual(summary.get("by_protocol_subfamily", {}).get("workflow_planning"), 1)
        self.assertEqual(summary.get("by_trust_level", {}).get("trusted_state"), 1)
        self.assertEqual(summary.get("by_user_view_scope", {}).get("advanced"), 1)

    def test_build_tools_list_uses_exposure_scope_filter(self):
        with patch.object(
            tool_adapter_module,
            "_get_all_skills",
            return_value={
                "protocol_visible": _fake_skill("tool_call"),
                "catalog_only": _fake_skill("catalog_only"),
            },
        ), patch.object(tool_adapter_module, "_get_exposed_skills", None):
            tools = tool_adapter_module.build_tools_list()

        names = [item.get("function", {}).get("name") for item in tools if isinstance(item, dict)]
        self.assertIn("protocol_visible", names)
        self.assertNotIn("catalog_only", names)

    def test_build_tools_list_cod_accepts_cod_scope(self):
        with patch.object(
            tool_adapter_module,
            "_get_all_skills",
            return_value={
                "protocol_visible": _fake_skill("tool_call"),
                "cod_visible": _fake_skill("tool_call_cod"),
                "catalog_only": _fake_skill("catalog_only"),
            },
        ), patch.object(tool_adapter_module, "_get_exposed_skills", None):
            tools = tool_adapter_module.build_tools_list_cod()

        names = [item.get("function", {}).get("name") for item in tools if isinstance(item, dict)]
        self.assertIn("protocol_visible", names)
        self.assertIn("cod_visible", names)
        self.assertNotIn("catalog_only", names)

    def test_skill_entry_infers_discovery_metadata(self):
        entry = skills_module._build_skill_entry(
            "folder_explore",
            meta={
                "category": "本地探索",
                "keywords": ["看看目录", "浏览文件夹"],
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            },
            execute=lambda *_args, **_kwargs: None,
        )

        self.assertEqual(entry.get("surfacing_profile"), "tool_only")
        self.assertEqual(entry.get("protocol_family"), "filesystem")
        self.assertEqual(entry.get("operation_kind"), "inspect")
        self.assertEqual(entry.get("effect_level"), "read_only")
        self.assertEqual(entry.get("risk_level"), "low")
        self.assertEqual(entry.get("protocol_subfamily"), "filesystem_read")
        self.assertEqual(entry.get("trust_level"), "trusted_local")
        self.assertEqual(entry.get("user_view_scope"), "hidden")
        self.assertIn("protocol_tool", entry.get("discovery_tags") or [])
        self.assertIn("filesystem", entry.get("discovery_tags") or [])
        self.assertIn("arg:path", entry.get("discovery_tags") or [])


if __name__ == "__main__":
    unittest.main()
